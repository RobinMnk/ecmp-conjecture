import math
import random

from ecmp import get_ecmp_DAG
from model import DAG, Instance, show_graph

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

    def is_node_violated(self, node):
        return node > 0 and self.loads[node] > alpha * self.OPT * len(self.dag.neighbors[node])

    def has_path_to_violated(self, a, active_edges):
        if any(v in active_edges[a] for v in self.violated_nodes):
            return True
        else:
            return any(self.has_path_to_violated(nb, active_edges) for nb in active_edges[a])

    def get_active_nodes(self):
        """ can (and should) be maintained automatically, this version is very inefficient """
        return [
            node for node in range(1, self.dag.num_nodes)
            if any(not self.has_path_to_violated(nb, self.active_edges) for nb in self.dag.neighbors[node])
            and self.has_path_to_violated(node, self.active_edges)
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


    def show(self):
        trimmed_inst = Instance(self.dag, self.inst.sources, self.inst.target, self.loads)
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst)
        show_graph(trimmed_inst, "_ecmp", sol.dag)

    def fixup(self, stop):
        restored_nodes = list()
        while self.violated_nodes:
            # v = random.choice(self.violated_nodes)
            # if self.loads[v] <= alpha * self.OPT * len(self.dag.neighbors[v]):
            #     self.violated_nodes.remove(v)
            #     continue

            active_nodes = self.get_active_nodes()
            candidate_edges = [
                (node, nb) for node in active_nodes for nb in self.dag.neighbors[node]
                if nb not in self.active_edges[node]
            ]  # all inactive edges leaving an active node

            edge = random.choice(candidate_edges)
            start, end = edge
            volume = self.loads[start] / len(self.active_edges[start])
            print(f" - rebalancing with edge ({start}, {end})")

            # Delete edge on path to v
            neighbor_to_delete = random.choice(list(x for x in self.active_edges[start] if (start, x) not in candidate_edges))
            self.active_edges[start].remove(neighbor_to_delete)
            self.propagate(neighbor_to_delete, -volume)

            # Activate candidate edge
            self.active_edges[start].append(end)
            self.propagate(end, volume)
            candidate_edges.remove(edge)

            new_violated_nodes = []
            for v in self.violated_nodes:
                if self.is_node_violated(v):
                    new_violated_nodes.append(v)
                elif v > stop:
                    restored_nodes.append(v)
            self.violated_nodes = new_violated_nodes

        for node in restored_nodes:
            self.process_node(node)

    def process_node(self, node):
        if node == 0 or self.loads[node] == 0:
            return

        # self.active_edges[node].clear()
        num_packets = math.ceil(self.loads[node] / (alpha * self.OPT))
        degree = len(self.dag.neighbors[node])

        if num_packets > degree:
            # Call Fixup Routine!
            self.violated_nodes = [node]
            print(f" Calling fixup for node {node}")
            self.fixup(node)
            num_packets = math.ceil(self.loads[node] / (alpha * self.OPT))

        # activate highest num_packets out-edges in top. order
        for neighbor in list(reversed(self.dag.neighbors[node]))[:num_packets]:
            # Activate edge node -> neighbor
            self.active_edges[node].append(neighbor)
            self.loads[neighbor] += self.loads[node] / num_packets

    def solve(self, dag: DAG, inst: Instance, OPT):
        self.dag = dag
        self.inst = inst
        self.OPT = OPT
        self.loads = [ld for ld in inst.demands]
        self.active_edges = [list() for _ in range(dag.num_nodes)]
        self.violated_nodes.clear()

        for node in reversed(range(1, dag.num_nodes)):
            self.process_node(node)

        self.show()

        dag = DAG(dag.num_nodes, self.active_edges, [])
        return get_ecmp_DAG(dag, inst)
