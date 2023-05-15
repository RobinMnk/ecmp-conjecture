import math
import random
import traceback

from ecmp import get_ecmp_DAG
from model import DAG, Instance, show_graph, save_instance

alpha = 2


def path_to(a, b, active_edges):
    if b in active_edges[a]:
        return [a]
    else:
        for nb in active_edges[a]:
            p = path_to(nb, b, active_edges)
            if p:
                return [b] + p
        return []

_eps = 0.000001

class MySolver:
    dag = None
    inst = None
    OPT = 1
    loads = list()
    active_edges = list()
    violated_nodes = list()
    marked = list()
    removed = list()

    def is_node_violated(self, node):
        return node > 0 and self.loads[node] > alpha * self.OPT * len(self.dag.neighbors[node])

    def does_need_repackaging(self, node):
        return node > 0 and math.ceil(self.loads[node] / (alpha * self.OPT)) < len(self.active_edges[node])

    def has_path_to_violated(self, a, active_edges_only=True):
        if a in self.violated_nodes:  # or any(v in self.active_edges[a] for v in self.violated_nodes):
            return True
        else:
            edge_set = self.active_edges if active_edges_only else self.dag.neighbors
            return any(self.has_path_to_violated(nb) for nb in edge_set[a])

    def has_inactive_path_below(self, a, thresh):
        if a < thresh:
            return True
        else:
            return any(
                self.has_inactive_path_below(nb, thresh) for nb in self.dag.neighbors[a]
                if nb not in self.active_edges[a]
                and nb not in self.violated_nodes
                )

    def get_active_nodes(self):
        """ can (and should) be maintained automatically, this version is very inefficient """
        return [
            node for node in range(1, self.dag.num_nodes)
            # if any(not self.has_path_to_violated(nb, self.active_edges) for nb in self.dag.neighbors[node]) and
            if (self.has_path_to_violated(node) or any(node == x for (x, _) in self.marked))
            and node not in self.violated_nodes
        ]

    def propagate(self, node, change):
        self.loads[node] += change

        # while math.ceil(self.loads[node] / (alpha * self.OPT)) < len(self.active_edges[node]):
        #     # Need to re-package, delete an outgoing edge
        #     deleted_neighbor = self.active_edges[node][0]
        #     lost_flow = (self.loads[node] - change) / len(self.active_edges[node])
        #
        #
        #     deleted_neighbor = random.choice(self.active_edges[node])
        #     lost_flow = (self.loads[node] - change) / len(self.active_edges[node])
        #     self.propagate(deleted_neighbor, stop, -lost_flow)
        #     self.active_edges[node].remove(deleted_neighbor)

        if change < 0:
            for nb in self.active_edges[node]:
                self.propagate(nb, change / len(self.active_edges[node]))
        else:
            num_packets = math.ceil(self.loads[node] / (alpha * self.OPT))

            if num_packets == len(self.active_edges[node]):
                # No repackaging necessary
                for nb in self.active_edges[node]:
                    self.propagate(nb, change / len(self.active_edges[node]))

            else:
                # Need to add new edge
                degree = len(self.dag.neighbors[node])

                if num_packets > degree:
                    # Call Fixup Routine!
                    self.violated_nodes.append(node)

                else:
                    # activate highest num_packets out-edges in top. order
                    for neighbor in list(reversed(self.dag.neighbors[node]))[:num_packets]:
                        # Activate edge node -> neighbor
                        if neighbor in self.active_edges[node]:
                            # already active
                            update = (self.loads[node]) / num_packets - (self.loads[node] - change) / len(self.active_edges[node])
                            self.propagate(neighbor, update)
                        else:
                            self.active_edges[node].append(neighbor)
                            self.loads[neighbor] += self.loads[node] / num_packets

        # if self.is_node_violated(node):
        #     self.violated_nodes.append(node)

        # self.process_node(node)

        # self.active_edges[node].clear()

    def update_loads(self, end):
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst)
        self.loads = [ld for ld in sol.loads]
        for node in reversed(range(end, dag.num_nodes)):
            if node in self.violated_nodes:
                continue

            num_packets = math.ceil(self.loads[node] / (alpha * self.OPT))
            old_degree = len(self.active_edges[node])

            if num_packets > old_degree:
                if num_packets > len(self.dag.neighbors[node]):
                    self.violated_nodes.append(node)
                else:
                    # Need to add another edge
                    new_neighbor = max([x for x in self.dag.neighbors[node] if x not in self.active_edges[node]])
                    self.active_edges[node].append(new_neighbor)
                    self.update_loads(end)
                    return

            elif num_packets < old_degree:
                candidates = [e for e in self.active_edges[node] if (node, e) not in self.marked]
                if candidates:
                    smallest_neighbor = min(candidates)
                    self.active_edges[node].remove(smallest_neighbor)
                    self.removed.append((node, smallest_neighbor))
                    self.update_loads(end)
                    return

    def show(self):
        # self.update_loads(0)
        trimmed_inst = Instance(self.dag, self.inst.sources, self.inst.target, self.loads)
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst)
        show_graph(trimmed_inst, "_ecmp", sol.dag)


    def apply_candidate_edge_rebalancing(self, edge, candidate_edges):
        start, end = edge
        # volume = self.loads[start] / len(self.active_edges[start])
        # print(f" - rebalancing with edge ({start}, {end})")

        # Delete edge on path to v
        # neighbor_to_delete = random.choice(list(x for x in self.active_edges[start] if (start, x) not in candidate_edges))

        # if edge in removed_edges:
        #     self.marked.append((start, neighbor_to_delete))
        # else:

        if edge in self.removed:
            self.marked.append(edge)
        else:
            relief_edges = [
                x for x in self.active_edges[start]
                if (start, x) not in candidate_edges
                   and self.has_path_to_violated(x, active_edges_only=False)
            ]
            # new_relief_edges = [e for e in relief_edges if e not in removed_edges]
            # if len(new_relief_edges) == 0:
            #     # No other way -> split
            #     shared_neighbor = relief_edges[0]
            #     self.marked.append((start, shared_neighbor))
            #     self.marked.append(edge)
            # else:
            if len(relief_edges) == 0:
                return False

            neighbor_to_delete = relief_edges[0]
            self.active_edges[start].remove(neighbor_to_delete)
            self.removed.append((start, neighbor_to_delete))

        # self.propagate(neighbor_to_delete, -volume)

        # Activate candidate edge
        self.active_edges[start].append(end)
        # self.propagate(end, volume)+
        return True


    def fixup(self, current):
        iteration_count = 0
        self.violated_nodes = [current]
        self.removed = list()

        while any(self.is_node_violated(v) for v in self.violated_nodes):
            # v = random.choice(self.violated_nodes)
            # if self.loads[v] <= alpha * self.OPT * len(self.dag.neighbors[v]):
            #     self.violated_nodes.remove(v)
            #     continue
            iteration_count += 1
            if iteration_count == 10 * self.dag.num_nodes:
                self.show()
                save_instance("tmp", self.inst, 1)
                raise Exception(f"Endless Loop during fixup for nodes {self.violated_nodes}")

            # print(self.violated_nodes)

            active_nodes = self.get_active_nodes()
            candidate_edges = [
                (node, nb) for node in active_nodes for nb in self.dag.neighbors[node]
                if nb not in self.active_edges[node]
                and (nb not in self.violated_nodes or (node, nb) in self.marked)
                # and not self.has_path_to_violated(nb, active_edges_only=False)
                # and self.has_inactive_path_below(nb, min(self.violated_nodes))
            ]  # all inactive edges leaving an active node

            if not candidate_edges:
                # print("Resetting violated node set")
                self.violated_nodes = [v for v in self.violated_nodes if self.is_node_violated(v)]
                continue
                # self.show()
                # save_instance("tmp", self.inst, 1)
                # raise RuntimeError(f"No Candidate Edges during fixup for nodes {self.violated_nodes}")

            candidate_edges.sort(key=lambda x: self.loads[x[1]] / len(self.active_edges[x[1]]) if len(self.active_edges[x[1]]) > 0 else self.dag.num_nodes, reverse=True)

            # candidate_edges.sort(key=lambda x: x[1], reverse=False)

            edge = candidate_edges[0]

            while not self.apply_candidate_edge_rebalancing(edge, candidate_edges):
                candidate_edges.remove(edge)
                if not candidate_edges:
                    # print("Resetting violated node set")
                    self.violated_nodes = [v for v in self.violated_nodes if self.is_node_violated(v)]
                    edge = None
                    break
                edge = candidate_edges[0]

            if edge is None:
                continue

            candidate_edges.remove(edge)
            self.update_loads(current)

            # self.violated_nodes = [v for v in self.violated_nodes if self.is_node_violated(v)]

        #     new_violated_nodes = []
        #     for v in self.violated_nodes:
        #         if self.is_node_violated(v):
        #             new_violated_nodes.append(v)
        #         elif v > stop:
        #             restored_nodes.append(v)
        #     self.violated_nodes = new_violated_nodes
        #
        # for node in restored_nodes:
        #     self.process_node(node)

    def process_node(self, node):
        if node == 0 or self.loads[node] == 0:
            return

        # self.active_edges[node].clear()
        num_packets = math.ceil(self.loads[node] / (alpha * self.OPT))
        degree = len(self.dag.neighbors[node])

        if num_packets > degree:
            # Call Fixup Routine!
            # print(f" Calling fixup for node {node}")
            self.fixup(node)
            num_packets = math.ceil(self.loads[node] / (alpha * self.OPT))

        # activate highest num_packets out-edges in top. order
        for neighbor in list(reversed(self.dag.neighbors[node]))[:num_packets]:
            # Activate edge node -> neighbor
            if neighbor not in self.active_edges[node]:
                self.active_edges[node].append(neighbor)
                self.loads[neighbor] += self.loads[node] / num_packets

    def solve(self, dag: DAG, inst: Instance, OPT):
        self.dag = dag
        self.inst = inst
        self.OPT = OPT + _eps
        self.loads = [ld for ld in inst.demands]
        self.active_edges = [list() for _ in range(dag.num_nodes)]
        self.violated_nodes.clear()
        self.marked = list()

        for node in reversed(list(range(1, dag.num_nodes))):
            self.process_node(node)

        self.update_loads(0)

        # self.show()
        #
        # print(f"marked: {self.marked}")

        try:
            congestion = max(self.loads[i] / len(self.active_edges[i]) for i in range(1, dag.num_nodes) if self.loads[i] > 0)

            # print(f"ECMP Congestion:  {congestion}")

            if congestion > 2 * self.OPT:
                print("ERROR: COUNTEREXAMPLE!!!!")
                self.show()
                save_instance("tmp", inst, 1)
                exit(1)
        except:
            traceback.print_exc()
            lst = [i for i in range(1, dag.num_nodes) if self.loads[i] > 0 and len(self.active_edges[i]) == 0]
            print(f"ERROR: Positive load but no outgoing edge!!!!\n{lst=}")
            self.show()
            save_instance("tmp", inst, 1)
            exit(1)


        dag = DAG(dag.num_nodes, self.active_edges, [])
        return get_ecmp_DAG(dag, inst)
