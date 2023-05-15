import math

from ecmp import get_ecmp_DAG
from model import DAG, Instance, show_graph, save_instance, _eps, make_parents

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
            if self.has_path_to_violated(node) #  or any(node == x for (x, _) in self.marked)
            and node not in self.violated_nodes
        ]

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
        trimmed_inst = Instance(self.dag, self.inst.sources, self.inst.target, self.loads)
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst)
        show_graph(trimmed_inst, "_ecmp", sol.dag)

    def apply_candidate_edge_rebalancing(self, edge, candidate_edges):
        start, end = edge

        if edge in self.removed:
            self.marked.append(edge)
        else:
            relief_edges = [
                x for x in self.active_edges[start]
                if (start, x) not in candidate_edges
                   and self.has_path_to_violated(x, active_edges_only=False)
            ]

            if len(relief_edges) == 0:
                return False

            neighbor_to_delete = relief_edges[0]
            self.active_edges[start].remove(neighbor_to_delete)
            self.removed.append((start, neighbor_to_delete))

        self.active_edges[start].append(end)
        return True

    def fixup(self, current):
        iteration_count = 0
        self.violated_nodes = [current]
        self.removed = list()

        while any(self.is_node_violated(v) for v in self.violated_nodes):
            iteration_count += 1
            if iteration_count > 10 * self.dag.num_nodes:
                save_instance("tmp", self.inst, 1)
                raise Exception(f"Endless Loop during fixup for nodes {self.violated_nodes}")

            active_nodes = self.get_active_nodes()
            candidate_edges = [
                (node, nb) for node in active_nodes for nb in self.dag.neighbors[node]
                if nb not in self.active_edges[node]
                # and (nb not in self.violated_nodes or (node, nb) in self.marked)
                and nb not in self.violated_nodes
                # and not self.has_path_to_violated(nb, active_edges_only=False)
                # and self.has_inactive_path_below(nb, min(self.violated_nodes))
            ]  # all inactive edges leaving an active node

            if not candidate_edges:
                # print("Resetting violated node set")
                self.violated_nodes = [v for v in self.violated_nodes if self.is_node_violated(v)]
                continue

            candidate_edges.sort(key=lambda x: self.loads[x[1]] / len(self.active_edges[x[1]]) if len(self.active_edges[x[1]]) > 0 else self.dag.num_nodes, reverse=True)

            edge = candidate_edges[0]

            while not self.apply_candidate_edge_rebalancing(edge, candidate_edges):
                candidate_edges.remove(edge)
                if not candidate_edges:
                    self.violated_nodes = [v for v in self.violated_nodes if self.is_node_violated(v)]
                    edge = None
                    break
                edge = candidate_edges[0]

            if edge is None:
                continue

            candidate_edges.remove(edge)
            self.update_loads(current)

    def process_node(self, node):
        if node == 0 or self.loads[node] == 0:
            return

        num_packets = math.ceil(self.loads[node] / (alpha * self.OPT))
        degree = len(self.dag.neighbors[node])

        if num_packets > degree:
            # Call Fixup Routine!
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

        dag = DAG(dag.num_nodes, self.active_edges, make_parents(self.active_edges))
        return get_ecmp_DAG(dag, inst)
