import math

from ecmp import get_ecmp_DAG
from model import DAG, Instance, show_graph, _eps, make_parents, ECMP_Sol, save_instance_temp


def path_to(a, b, active_edges):
    if a == b or b in active_edges[a]:
        return [a]
    else:
        for nb in active_edges[a]:
            p = path_to(nb, b, active_edges)
            if p:
                return [b] + p
        return None


def get_node_loads(dag: DAG, inst: Instance):
    node_loads = [0] * inst.dag.num_nodes
    for i, d in enumerate(inst.demands):
        node_loads[i] = d

    for node in reversed(range(1, dag.num_nodes)):
        for nb in dag.neighbors[node]:
            node_loads[nb] += dag.neighbors[node][nb]

    return node_loads


def hash_edge_set(edge_set):
    hash = 0
    for z, lst in enumerate(edge_set):
        for nb in lst:
            hash += ((432 * z + 5324) * (523467 * nb + 96234) + 543) % 67939
    return (sum(len(edge_set[z]) for z in range(len(edge_set))) * 80347 * hash + 241) % 79194553883


class MySolver:
    dag = None
    inst = None
    OPT = 1
    loads = list()
    active_edges = list()
    violated_nodes = list()
    marked = list()
    removed = list()
    alpha = 2
    num_nodes: int

    num_cycles = 0

    opt_node_loads = list()

    def dag_with_deletion(self, with_deletion=None):
        if with_deletion is None:
            with_deletion = list()
        other_edges = [[nb for nb in self.active_edges[z]] for z in range(self.dag.num_nodes)]
        if with_deletion:
            for fr, to in with_deletion:
                if to in other_edges[fr]:
                    other_edges[fr].remove(to)
        dag = DAG(self.dag.num_nodes, other_edges, [])
        sol = get_ecmp_DAG(dag, self.inst)
        return sol, dag

    def show(self, highlighted=None):
        if highlighted is None:
            highlighted = list()
        trimmed_inst = Instance(self.dag, self.inst.sources, self.inst.target, self.loads)
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst, all_checks=False)
        show_graph(trimmed_inst, "_ecmp", sol.dag, highlighted)

    def is_node_violated(self, node):
        return node > 0 and self.loads[node] > self.alpha * self.OPT * len(self.active_edges[node])
        # return node > 0 and self.loads[node] > self.alpha * self.OPT * len(self.dag.neighbors[node])

    def has_path_to_violated(self, a, active_edges_only=True):
        if a in self.violated_nodes:  # or any(v in self.active_edges[a] for v in self.violated_nodes):
            return True
        else:
            edge_set = self.active_edges if active_edges_only else self.dag.neighbors
            return any(self.has_path_to_violated(nb) for nb in edge_set[a])

    def get_active_nodes(self):
        return [
            node for node in range(1, self.dag.num_nodes)
            if self.has_path_to_violated(node)
               and node not in self.violated_nodes
        ]

    def update_loads(self):
        """ loads can (and should) be maintained automatically, this version is very inefficient """
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst, all_checks=False)
        self.loads = [ld for ld in sol.loads]

        for node in range(self.num_nodes - 1, 0, -1):
            self.process_node(node)

    # def propagate(self, node, val):
    #     self.loads[node] += val
    #
    #     fl = self.loads[node] / len(self.active_edges)
    #
    #     if self.is_node_violated(node):
    #         self.violated_nodes.append(node)
    #
    #     made_change = True
    #     while made_change:
    #         made_change = False
    #         fl = self.loads[node] / len(self.active_edges[node])
    #
    #         if any(fl + _eps < self.dag.neighbors[node][nb] for nb in self.active_edges[node]):
    #             smallest_neighbor = min(self.active_edges[node], key=lambda x: self.dag.neighbors[node][x])
    #             self.active_edges[node].remove(smallest_neighbor)
    #
    #     for nb in self.active_edges[node]:
    #
    #         if fl < self.dag.neighbors[node][nb]:
    #             self.active_edges[node].remove(nb)
    #
    #
    #         self.propagate(nb, val / len(self.active_edges[node]))

    def fixup(self):
        # self.violated_nodes = [current]
        # self.removed = list()
        # self.marked = list()
        # self.update_loads(current)

        sequence = list()

        counter = 0

        while any(self.is_node_violated(v) for v in range(self.dag.num_nodes)):
            self.violated_nodes = [v for v in range(self.dag.num_nodes) if self.is_node_violated(v) ]
            active_nodes = self.get_active_nodes()
            candidate_edges = [
                (node, nb) for node in active_nodes for nb in self.dag.neighbors[node]
                if nb not in self.active_edges[node]
                   and nb not in self.violated_nodes
            ]  # all inactive edges leaving an active node

            counter += 1

            if counter > 1000:
                self.show(sequence)
                # save_instance_temp(self.inst)
                stop = True
                if stop:
                    raise Exception("Infinite Loop")

            # print(self.violated_nodes)

            if not candidate_edges:
                self.show()
                print("WHY")

            #     # shrunk_violated = [v for v in self.violated_nodes if self.is_node_violated(v)]
            #     # if len(shrunk_violated) < len(self.violated_nodes):
            #     #     self.violated_nodes = shrunk_violated
            #     #     continue
            #
            #     raise Exception("Cannot happen now!")
            #
            #     # Need to increase alpha!
            #     num_low_edges = len([
            #         (z, n) for z in active_nodes for n in self.active_edges[z]
            #         if n not in active_nodes and n not in self.violated_nodes
            #         if self.loads[z] / len(self.active_edges[z]) < (self.alpha / 2) * self.OPT
            #     ])
            #     degrees_X = sum(len(self.dag.neighbors[a]) for a in self.violated_nodes if self.is_node_violated(a))
            #     degrees_A = sum(len(self.dag.neighbors[a]) for a in active_nodes)
            #
            #     new_alpha = 2 - (degrees_X + num_low_edges) / (2 * (degrees_X + num_low_edges) + degrees_A)
            #
            #     # print(f"Increasing alpha:  {self.alpha:0.3f}  ->  {new_alpha:0.3f}")
            #
            #     if new_alpha < self.alpha:
            #         self.show()
            #         save_instance_temp(self.inst)
            #         raise Exception("Alpha should only increase!")
            #
            #     if new_alpha == self.alpha:
            #         self.show()
            #         save_instance_temp(self.inst)
            #         skip = True
            #         if skip:
            #             raise Exception(f"Infinite Loop during fixup for nodes {self.violated_nodes}")
            #
            #     self.alpha = new_alpha
            #     self.marked.clear()
            #     self.update_loads(current)
            #     continue

            # edge = min(candidate_edges,
            #            key=lambda x: -1 if x[1] == 0 else (
            #                self.loads[x[1]] / len(self.dag.neighbors[x[1]])
            #                + (max(self.inst.demands) + 1 if x in self.removed else 0)
            #                if len(self.dag.neighbors[x[1]]) > 0
            #                else max(self.inst.demands) + 1
            #            ))
            edge = min(candidate_edges, key=lambda x: float("inf") if x in self.removed else self.dag.neighbors[x[0]][x[1]])
            start, end = edge

            entry = (edge, hash_edge_set(self.active_edges))
            if entry in sequence:
                # self.marked.append(edge)
                # smallest_neighbor = min(self.active_edges[start])
                # self.active_edges[start].remove(smallest_neighbor)
                # self.active_edges[start].append(end)

                # self.show([e for e,_ in sequence])

                # self.update_loads(current)
                # sequence.clear()
                continue
            #
            sequence.append(entry)

            # sequence.append(edge)

            relief_edges = [
                x for x in self.active_edges[start]
                if (start, x) not in candidate_edges
                and self.has_path_to_violated(x, active_edges_only=False)
            ]

            neighbor_to_delete = relief_edges[0]

            # if (start, neighbor_to_delete) in self.marked:
            #     self.marked.append(edge)
            #     self.marked.remove((start, neighbor_to_delete))
            # else:

            fl = self.loads[start] / len(self.active_edges[start])

            self.active_edges[start].remove(neighbor_to_delete)
            self.removed.append((start, neighbor_to_delete))
            # self.propagate(neighbor_to_delete, - fl)

            # print(f"{edge}  <-   {(start, neighbor_to_delete)}")

            if fl >= self.dag.neighbors[start][end]:
                self.active_edges[start].append(end)
                # self.propagate(end, fl)

            self.update_loads()
            # self.check_invariant(0)

    def check_invariant(self, end):
        for node in range(end, self.dag.num_nodes):
            if self.loads[node] == 0 or len(self.active_edges[node]) < 2:
                continue

            fl = self.loads[node] / len(self.active_edges[node])

            for nb in self.active_edges[node]:
                if fl + _eps < self.dag.neighbors[node][nb]:
                    self.show([(node, nb)])
                    raise Exception("Invariant failed!")

    def process_node(self, node):
        if self.loads[node] == 0:
            return

        while len(self.active_edges[node]) > 1:
            fl = self.loads[node] / len(self.active_edges[node])

            if any(fl + _eps < self.dag.neighbors[node][nb] for nb in self.active_edges[node]):
                smallest_neighbor = min(self.active_edges[node], key=lambda x: self.dag.neighbors[node][x])
                self.active_edges[node].remove(smallest_neighbor)
                self.update_loads()
            else:
                break

    def remove_all_low_edges(self):
        for node in range(self.num_nodes - 1, 0, -1):
            self.process_node(node)
            self.check_invariant(node)

    def solve(self, dag: DAG, inst: Instance, OPT) -> ECMP_Sol:
        self.dag = dag
        self.inst = inst
        self.OPT = OPT + _eps
        self.loads = [ld for ld in inst.demands]
        self.num_nodes = dag.num_nodes
        # self.active_edges = [list() for _ in range(dag.num_nodes)]
        self.active_edges = [list(self.dag.neighbors[z].keys()) for z in range(self.dag.num_nodes)]
        self.update_loads()
        self.violated_nodes.clear()
        self.marked = list()

        self.opt_node_loads = get_node_loads(dag, inst)

        self.remove_all_low_edges()

        self.fixup()

        dag = DAG(dag.num_nodes, self.active_edges, make_parents(self.active_edges))
        return get_ecmp_DAG(dag, inst)
