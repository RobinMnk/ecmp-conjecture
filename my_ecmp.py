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
        sol = get_ecmp_DAG(dag, self.inst)
        show_graph(trimmed_inst, "_ecmp", sol.dag, highlighted)

    def is_node_violated(self, node):
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

    def update_loads(self, end):
        """ loads can (and should) be maintained automatically, this version is very inefficient """
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst)
        self.loads = [ld for ld in sol.loads]
        for node in reversed(range(end, dag.num_nodes)):
            if node in self.violated_nodes:
                continue

            # if any(z == node for z, _ in self.marked) and self.loads[node] < self.opt_node_loads[node]:
            #     save_instance_temp(self.inst)
            #     raise Exception("Marked Parent Node below threshold!!")

            num_packets = math.ceil(self.loads[node] / (self.alpha * self.OPT))
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
                    self.update_loads(end)
                    return

        self.violated_nodes = [v for v in self.violated_nodes if self.is_node_violated(v)]

    def fixup(self, current):
        self.violated_nodes = [current]
        self.removed = list()
        # self.marked = list()
        # self.update_loads(current)

        sequence = list()

        while any(self.is_node_violated(v) for v in self.violated_nodes):
            active_nodes = self.get_active_nodes()
            candidate_edges = [
                (node, nb) for node in active_nodes for nb in self.dag.neighbors[node]
                if nb not in self.active_edges[node]
                   and nb not in self.violated_nodes
            ]  # all inactive edges leaving an active node

            # print(self.violated_nodes)

            self.check_invariant(current)

            # critical_edges = [
            #     (z, n) for z in active_nodes for n in self.active_edges[z]
            #     if n not in active_nodes and n not in self.violated_nodes
            #     if self.loads[z] / len(self.active_edges[z]) < (self.alpha / 2) * self.OPT
            #     # if (z,n) in self.marked
            # ]
            #
            # if any(
            #         self.loads[z] / len(self.active_edges[z]) < self.dag.neighbors[z][re]
            #         # and self.loads[nb] < self.alpha * self.OPT * (len(self.dag.neighbors[nb]) - 0.5)
            #         for z, _ in critical_edges
            #         for re in self.active_edges[z]
            #         if (z, re) not in candidate_edges
            #             and self.has_path_to_violated(re, active_edges_only=False)
            # ):
            #     # self.show(critical_edges)
            #     # print("Noooo")
            #     save_instance_temp(self.inst)
            #     raise Exception("Assumption failed")

            if not candidate_edges:
                # shrunk_violated = [v for v in self.violated_nodes if self.is_node_violated(v)]
                # if len(shrunk_violated) < len(self.violated_nodes):
                #     self.violated_nodes = shrunk_violated
                #     continue

                raise Exception("Cannot happen now!")

                # Need to increase alpha!
                num_low_edges = len([
                    (z, n) for z in active_nodes for n in self.active_edges[z]
                    if n not in active_nodes and n not in self.violated_nodes
                    if self.loads[z] / len(self.active_edges[z]) < (self.alpha / 2) * self.OPT
                ])
                degrees_X = sum(len(self.dag.neighbors[a]) for a in self.violated_nodes if self.is_node_violated(a))
                degrees_A = sum(len(self.dag.neighbors[a]) for a in active_nodes)

                new_alpha = 2 - (degrees_X + num_low_edges) / (2 * (degrees_X + num_low_edges) + degrees_A)

                # print(f"Increasing alpha:  {self.alpha:0.3f}  ->  {new_alpha:0.3f}")

                if new_alpha < self.alpha:
                    self.show()
                    save_instance_temp(self.inst)
                    raise Exception("Alpha should only increase!")

                if new_alpha == self.alpha:
                    self.show()
                    save_instance_temp(self.inst)
                    skip = True
                    if skip:
                        raise Exception(f"Infinite Loop during fixup for nodes {self.violated_nodes}")

                self.alpha = new_alpha
                self.marked.clear()
                self.update_loads(current)
                continue

            # edge = min(candidate_edges,
            #            key=lambda x: -1 if x[1] == 0 else (
            #                self.loads[x[1]] / len(self.dag.neighbors[x[1]])
            #                + (max(self.inst.demands) + 1 if x in self.removed else 0)
            #                if len(self.dag.neighbors[x[1]]) > 0
            #                else max(self.inst.demands) + 1
            #            ))
            edge = min(candidate_edges, key=lambda x: float("inf") if x in self.removed else x[1])
            start, end = edge

            entry = (edge, hash_edge_set(self.active_edges))
            if entry in sequence:
                self.marked.append(edge)
                smallest_neighbor = min(self.active_edges[start])
                self.active_edges[start].remove(smallest_neighbor)
                self.active_edges[start].append(end)

                self.update_loads(current)
                sequence.clear()
                continue

            sequence.append(entry)

            relief_edges = [
                x for x in self.active_edges[start]
                if (start, x) not in candidate_edges
                and self.has_path_to_violated(x, active_edges_only=False)
            ]

            neighbor_to_delete = relief_edges[0]

            if (start, neighbor_to_delete) in self.marked:
                self.marked.append(edge)
                self.marked.remove((start, neighbor_to_delete))
            else:
                self.active_edges[start].remove(neighbor_to_delete)
                self.removed.append((start, neighbor_to_delete))

            # print(f"{edge}  <-   {(start, neighbor_to_delete)}")

            self.active_edges[start].append(end)
            self.update_loads(current)

    def process_node(self, node):
        if node == 0 or self.loads[node] == 0:
            return

        num_packets = math.ceil(self.loads[node] / (self.alpha * self.OPT))
        degree = len(self.dag.neighbors[node])

        if num_packets > degree:
            # Call Fixup Routine!
            self.fixup(node)
            num_packets = math.ceil(self.loads[node] / (self.alpha * self.OPT))

        # activate highest num_packets out-edges in top. order
        for neighbor in list(reversed(self.dag.neighbors[node]))[:num_packets]:
            # Activate edge node -> neighbor
            if neighbor not in self.active_edges[node]:
                self.active_edges[node].append(neighbor)
                self.loads[neighbor] += self.loads[node] / num_packets

    def find(self, node, value):
        if node == 0 or len(self.active_edges[node]) == 0:
            return False

        if self.loads[node] + value > self.alpha * self.OPT * len(self.dag.neighbors[node]):
            return True

        return any([
            self.find(nb, value) for nb in self.active_edges[node]
        ])

    def check_invariant(self, start=1):
        for z in range(start, self.dag.num_nodes):
            if len(self.active_edges[z]) == 0:
                continue

            if z in self.violated_nodes:
                continue

            num_packets = math.ceil(self.loads[z] / (self.alpha * self.OPT))
            if len(self.active_edges[z]) == num_packets:
                continue

            if self.loads[z] < self.opt_node_loads[z]:
                self.show(self.active_edges[z])
                raise Exception("sefsef")

            # fl = self.loads[z] / len(self.active_edges[z])
            # for nb in self.active_edges[z]:
            #     if fl < self.dag.neighbors[z][nb] and not self.loads[nb] + fl > self.alpha * self.OPT * len(self.dag.neighbors[nb]):  # and not self.find(nb, fl):
            #         # self.show([(z, nb)])
            #         save_instance_temp(self.inst)
            #         # skip = False
            #         # if not skip:
            #         raise Exception("NOPEEE")

    def solve(self, dag: DAG, inst: Instance, OPT) -> ECMP_Sol:
        self.dag = dag
        self.inst = inst
        self.OPT = OPT + _eps
        self.loads = [ld for ld in inst.demands]
        self.active_edges = [list() for _ in range(dag.num_nodes)]
        self.violated_nodes.clear()
        self.marked = list()

        self.opt_node_loads = get_node_loads(dag, inst)

        # print()

        for node in reversed(list(range(1, dag.num_nodes))):
            self.process_node(node)

        # self.show()

        # for z in range(1, self.dag.num_nodes):
        #     if self.loads[z] == 0:
        #         continue
        #
        #     fl = self.loads[z] / len(self.active_edges[z])
        #
        #     if fl >= self.alpha * self.OPT / 2:
        #         continue
        #
        #     if any(z == t for t, _ in self.marked) and self.loads[z] < self.opt_node_loads[z]:
        #         self.show([(z, self.active_edges[z][0])])
        #         raise Exception("Noooo")

            #
            # for nb in self.active_edges[z]:
            #     if (z, nb) in self.marked and fl < self.dag.neighbors[z][nb]:
            #         # self.marked.remove((z, nb))
            #         # self.active_edges[z].remove(nb)
            #         # self.update_loads(0)
            #         self.show([(z, nb)])
            #         raise Exception("Noooo")
        # print("Found critical edge!")
        # sol, dag = self.dag_with_deletion([(z, nb)])
        # if sol.congestion > self.alpha:
        # save_instance_temp(self.inst)
        # raise Exception("Noooo")

        # if self.alpha >= 2:
        #     raise Exception("Alpha >= 2")

        # print(f"{self.num_cycles} Cycles removed.")

        self.check_invariant()

        dag = DAG(dag.num_nodes, self.active_edges, make_parents(self.active_edges))
        return get_ecmp_DAG(dag, inst)
