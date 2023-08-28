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

    opt_node_loads = list()

    def active_degree(self, node):
        return len(self.active_edges[node])

    def general_degree(self, node):
        return len(self.dag.neighbors[node])

    def flow_leaving(self, node):
        return self.loads[node] / self.active_degree(node) if self.active_degree(node) > 0 else 0

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

    def add_edge(self, start, end, verbose=False, check_invariant=False):
        if end in self.active_edges[start]:
            raise Exception("ERROR: Edge already exists!")

        if check_invariant and len(self.active_edges[start]) > 0 and self.dag.neighbors[start][end] > self.loads[
            start] / (len(self.active_edges[start]) + 1):
            raise Exception("Adding this edge violates invariant!")

        if verbose:
            print(f"  Adding {start} -> {end}")
        self.active_edges[start].append(end)
        self.update_loads()

    def remove_edge(self, start, end, verbose=False):
        if verbose:
            print(f"  Removing {start} -> {end}")
        self.active_edges[start].remove(end)
        self.update_loads()

    def is_node_blockaded(self, node):
        return node > 0 and self.loads[node] > self.alpha * self.OPT * len(self.dag.neighbors[node])

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
        self.violated_nodes = [v for v in range(self.dag.num_nodes) if self.is_node_violated(v)]

    def trivial_open_edges_for_violated(self):
        for node in sorted(self.violated_nodes, reverse=True):
            if self.active_degree(node) < self.general_degree(node):
                min_nb = min([
                    nb for nb in self.dag.neighbors[node]
                    if nb not in self.active_edges[node]
                ], key=lambda x: self.dag.neighbors[node][x])
                self.add_edge(node, min_nb)
                # print(f"Opening edges @ {node}")
                return True

        return False

    def fixup(self):
        counter = 0
        sequence = list()
        self.violated_nodes = [v for v in range(self.dag.num_nodes) if self.is_node_violated(v)]
        # removed = list()

        while self.violated_nodes:
            if self.trivial_open_edges_for_violated():
                continue

            active_nodes = self.get_active_nodes()
            candidate_edges = [
                (node, nb) for node in active_nodes for nb in self.dag.neighbors[node]
                if nb not in self.active_edges[node]
                   and nb not in self.violated_nodes
                # and (node, nb) not in self.removed
            ]  # all inactive edges leaving an active node

            counter += 1

            if counter > self.dag.num_nodes:
                print(sequence)
                # self.show(sequence)
                save_instance_temp(self.inst)
                raise Exception("Infinite Loop")

            # print(self.violated_nodes)

            if not candidate_edges:
                self.remove_all_low_edges()
                continue
                # raise Exception("No candidate edges available!!")

            edge = min(candidate_edges, key=lambda x: x[1])  # self.dag.neighbors[x[0]][x[1]])
            start, end = edge

            # if edge in sequence:
            #     cycle = sequence[sequence.index(edge):]
            #     print(f"Cycle of length {len(cycle)} detected: {cycle}")
            #     self.show(cycle)
            #
            #     for z, nb in cycle:
            #         if nb not in self.active_edges[z]:
            #             self.add_edge(z, nb)
            #
            #     # max_parent = max([p for p,_ in cycle])
            #     # self.violated_nodes.append(max_parent)
            #     sequence.clear()
            #     continue

            sequence.append(edge)

            relief_edges = [
                x for x in self.active_edges[start]
                if (start, x) not in candidate_edges
                and self.has_path_to_violated(x, active_edges_only=False)
            ]

            neighbor_to_delete = max(relief_edges)

            # if (start, end) in removed:
            #     self.add_edge(start, end)
            #     print(f" + ({start} -> {end})")
            # else:
            # fl = self.flow_leaving(start)

            self.remove_edge(start, neighbor_to_delete)
            self.add_edge(start, end)

            # print(f" + ({start} -> {end})")
            # print(f" - ({start} -> {neighbor_to_delete})")

    def check_invariant_node(self, node):
        if self.loads[node] == 0 or len(self.active_edges[node]) < 2:
            return None

        num_packets = math.ceil(self.loads[node] / (self.alpha * self.OPT))
        # if len(self.active_edges[node]) < num_packets:
        #     raise Exception("HERE")

        fl = self.loads[node] / len(self.active_edges[node])

        for nb in self.active_edges[node]:
            if fl + _eps < self.dag.neighbors[node][nb]:
                return nb

        return None

    def check_invariant(self, end=0):
        for node in range(end, self.dag.num_nodes):
            troubled_nb = self.check_invariant_node(node)

            if troubled_nb is not None:
                # self.show([(node, troubled_nb)])
                save_instance_temp(self.inst)
                raise Exception(f"Invariant failed on Edge ({node} -> {troubled_nb}) \n "
                                f"It has load {self.flow_leaving(node):.2f} "
                                f"but opt flow is {self.dag.neighbors[node][troubled_nb]:.2f}")

    def process_node(self, node):
        if self.loads[node] == 0 or len(self.active_edges[node]) <= 1:
            return

        num_packets = math.ceil(self.loads[node] / (self.alpha * self.OPT))
        while len(self.active_edges[node]) > num_packets:
            fl = self.loads[node] / len(self.active_edges[node])

            if any(fl + _eps < self.dag.neighbors[node][nb] for nb in self.active_edges[node]):
                smallest_neighbor = min(self.active_edges[node],
                                        key=lambda x: self.dag.neighbors[node][x]
                                        )
                self.remove_edge(node, smallest_neighbor)
            else:
                break

    def remove_all_low_edges(self, bottom=0):
        for node in reversed(range(bottom, self.num_nodes)):
            self.process_node(node)
            # self.check_invariant(node)

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

        self.fixup()

        dag = DAG(dag.num_nodes, self.active_edges, make_parents(self.active_edges))
        return get_ecmp_DAG(dag, inst)
