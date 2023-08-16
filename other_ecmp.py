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
    begin = False

    num_cycles = 0

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

    def potential(self):
        return sum(
            self.dag.neighbors[z][nb]
            for z in range(self.num_nodes)
            for nb in self.active_edges[z]
            if len(self.active_edges[z]) > 1
        )

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

        # for node in reversed(range(1, self.dag.num_nodes)):
        #     if sol.loads[node] == self.loads[node]:
        #         continue
        #
        #     if len(self.active_edges[node]) > 1 \
        #             and sol.loads[node] > self.loads[node] \
        #             and sol.loads[node] > self.alpha * self.OPT * self.active_degree(node) \
        #             and self.active_degree(node) < self.general_degree(node):
        #         min_nb = min([
        #             nb for nb in self.dag.neighbors[node]
        #             if nb not in self.active_edges[node]
        #         ], key=lambda x: self.dag.neighbors[node][x])
        #         self.add_edge(node, min_nb)
        #         return
        #
        #     self.loads[node] = sol.loads[node]

        # self.show()

        # print(f"\t\t\t\t\t\t\t\t\t\tPotential: {self.potential():.1f}")

    # def propagate(self, node):
    #
    #     for nb in self.active_edges[node]:
    #         self.propagate(nb)

    # def propagate_reduce(self, node, val):
    #     if node == 0:
    #         return
    #
    #     self.loads[node] -= val
    #     forwarded = val / len(self.active_edges[node])
    #
    #     #  Maintain Invariant after flow reduction
    #     t_nb = self.check_invariant_node(node)
    #     while t_nb is not None:
    #         fl = self.loads[node] / len(self.active_edges[node])
    #         self.remove_edge(node, t_nb)
    #         self.propagate_reduce(t_nb, fl)
    #
    #         new_fl = self.loads[node] / len(self.active_edges[node])
    #         diff = new_fl - fl
    #         forwarded += diff / len(self.active_edges[node])
    #         t_nb = self.check_invariant_node(node)
    #
    #     for nb in self.active_edges[node]:
    #         self.propagate_increase(nb, forwarded)
    #
    # def propagate_increase(self, node, val):
    #     if node == 0:
    #         return
    #
    #     self.loads[node] += val
    #     forwarded = val / len(self.active_edges[node])
    #
    #     made_update = False
    #     while not made_update and self.loads[node] > self.alpha * self.OPT * len(self.active_edges[node]):
    #         fl = self.loads[node] / len(self.active_edges[node])
    #         num_packets = math.ceil(self.loads[node] / (self.alpha * self.OPT))
    #         made_update = True
    #
    #         if num_packets < len(self.dag.neighbors[node]):
    #             # Try to open new edge
    #             for nb in self.dag.neighbors[node]:
    #                 if nb not in self.active_edges[node] and fl >= self.dag.neighbors[node][nb]:
    #                     print(f"Opening {node} -> {nb}")
    #                     self.add_edge(node, nb)
    #                     new_fl = self.loads[node] / len(self.active_edges[node])
    #                     diff = new_fl - fl
    #                     forwarded += diff / len(self.active_edges[node])
    #                     made_update = False
    #                     break
    #
    #     for nb in self.active_edges[node]:
    #         self.propagate_increase(nb, forwarded)

    def open_all_possible_edges(self, node):

        print(f"Opening all possible edges for {node}")

        self.active_edges[node].clear()

        neighbors = sorted(self.dag.neighbors[node].keys(),
                           key=lambda x: self.dag.neighbors[node][x],
                           reverse=True
                           )

        degree = len(self.dag.neighbors[node])
        best = -1
        new_nbs = list()
        for num_edges in range(1, degree + 1):
            fl = self.loads[node] / num_edges

            st = 0
            while st < degree and fl < self.dag.neighbors[node][neighbors[st]]:
                st += 1

            if st + num_edges > degree:
                continue

            nbs = neighbors[st:st + num_edges]

            current = sum(
                self.dag.neighbors[node][nb]
                for nb in nbs
            )

            if current > best:
                best = current
                new_nbs = nbs

        for nb in new_nbs:
            self.active_edges[node].append(nb)

        self.update_loads()

    def dfs(self, node):
        if node == 0:
            return

        print(f" DFS node {node}, from {self.active_edges[node]}")

        if len(self.dag.neighbors[node]) >= len(self.active_edges[node]) > 1:

            pot = sum(
                self.dag.neighbors[node][nb]
                for nb in self.active_edges[node]
            )
            self.active_edges[node].clear()

            neighbors = sorted(self.dag.neighbors[node].keys(),
                               key=lambda x: self.dag.neighbors[node][x],
                               reverse=True
                               )

            # num_edges = 0
            # for nb in neighbors:
            #     next_fl = self.loads[node] / (num_edges + 1)
            #     if num_edges > 0 and next_fl < self.dag.neighbors[node][nb]:
            #         break
            #
            #     self.add_edge(node, nb, verbose=False)
            #     num_edges += 1

            degree = len(self.dag.neighbors[node])
            best = -1
            new_nbs = list()
            for num_edges in range(1, degree + 1):
                fl = self.loads[node] / num_edges

                st = 0
                while st < degree and fl < self.dag.neighbors[node][neighbors[st]]:
                    st += 1

                if st + num_edges > degree:
                    continue

                nbs = neighbors[st:st + num_edges]

                current = sum(
                    self.dag.neighbors[node][nb]
                    for nb in nbs
                )

                if current > best:
                    best = current
                    new_nbs = nbs

            for nb in new_nbs:
                self.add_edge(node, nb, verbose=False)

            new_pot = sum(
                self.dag.neighbors[node][nb]
                for nb in self.active_edges[node]
            )

            print(f"   to {self.active_edges[node]} ({new_pot:.2f})")

            # if new_pot + _eps < pot:
            #     raise Exception("Potential decreased!")

            self.update_loads()

        # t_nb = self.check_invariant_node(node)
        # # print(f"{node}: {t_nb}")
        # while t_nb is not None:
        #     num_packets = math.ceil(self.loads[node] / (self.alpha * self.OPT))
        #     if len(self.active_edges[node]) == num_packets:
        #         raise Exception("HERE")
        #     self.remove_edge(node, t_nb)
        #     self.dfs(t_nb)
        #     t_nb = self.check_invariant_node(node)
        #
        # made_update = False
        # while not made_update and self.loads[node] > self.alpha * self.OPT * len(self.active_edges[node]):
        #     fl = self.loads[node] / len(self.active_edges[node])
        #     num_packets = math.ceil(self.loads[node] / (self.alpha * self.OPT))
        #     made_update = True
        #
        #     if num_packets < len(self.dag.neighbors[node]):
        #         pot_fl = self.loads[node] / (len(self.active_edges[node]) + 1)
        #         # Try to open new edge
        #         for nb in self.dag.neighbors[node]:
        #             if nb not in self.active_edges[node] and pot_fl >= self.dag.neighbors[node][nb]:
        #                 self.add_edge(node, nb)
        #                 made_update = False
        #                 break

        for nb in list(self.dag.neighbors[node].keys()):
            self.dfs(nb)


    def trivial_open_edges_for_violated(self):
        for node in self.violated_nodes:
            if self.active_degree(node) < self.general_degree(node):
                min_nb = min([
                    nb for nb in self.dag.neighbors[node]
                    if nb not in self.active_edges[node]
                ], key=lambda x: self.dag.neighbors[node][x])
                self.add_edge(node, min_nb)
                return True

        return False

    def fixup(self):
        # self.violated_nodes = [current]
        # self.removed = list()
        # self.marked = list()
        # self.update_loads(current)

        sequence = list()

        counter = 0

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

            # print(f"Potential: {self.potential():.1f}")

            if counter > 1000:
                self.show([e for e, _ in sequence])
                # self.show(sequence)
                # save_instance_temp(self.inst)
                stop = True
                if stop:
                    raise Exception("Infinite Loop")
                else:
                    continue

            # print(self.violated_nodes)

            if not candidate_edges:
                self.remove_all_low_edges(max(self.violated_nodes))
                continue

                # self.show()
                # # save_instance_temp(self.inst)
                # raise Exception("No candidate edges available!!")

            # edge = min(candidate_edges,
            #            key=lambda x: -1 if x[1] == 0 else (
            #                self.loads[x[1]] / len(self.dag.neighbors[x[1]])
            #                + (max(self.inst.demands) + 1 if x in self.removed else 0)
            #                if len(self.dag.neighbors[x[1]]) > 0
            #                else max(self.inst.demands) + 1
            #            ))
            # edge = min(candidate_edges, key=lambda x: float("inf") if x in self.removed else self.dag.neighbors[x[0]][x[1]])
            edge = min(candidate_edges, key=lambda x: x[1])  # self.dag.neighbors[x[0]][x[1]])
            start, end = edge

            # entry = (edge, hash_edge_set(self.active_edges))
            # if entry in sequence:
            #     # self.marked.append(edge)
            #     # smallest_neighbor = min(self.active_edges[start])
            #     # self.active_edges[start].remove(smallest_neighbor)
            #     # self.active_edges[start].append(end)
            #
            #     # self.show([e for e,_ in sequence])
            #
            #     # self.update_loads(current)
            #     # sequence.clear()
            #
            #     for (f, t), _ in sequence:
            #         if t not in self.active_edges[f]:
            #             self.active_edges[f].append(t)
            #
            #     self.update_loads()
            #     continue

            # sequence.append(entry)

            # sequence.append(edge)

            relief_edges = [
                x for x in self.active_edges[start]
                if (start, x) not in candidate_edges
                   and self.has_path_to_violated(x, active_edges_only=False)
            ]

            fl = self.flow_leaving(start)

            neighbor_to_delete = min(relief_edges, key=lambda x: self.dag.neighbors[start][x])
            self.remove_edge(start, neighbor_to_delete)

            # print(f"{edge}  <-   {(start, neighbor_to_delete)}")

            # len(self.active_edges[start]) == 0 \
            if fl >= self.dag.neighbors[start][end]:
                self.add_edge(start, end)

            # self.dfs(start)
            # print(f"\nStarting DFS from {neighbor_to_delete}")
            # self.dfs(neighbor_to_delete)
            # for nb in self.active_edges[start]:
            #     print(f"\nStarting DFS from {nb}")
            #     self.dfs(nb)
            # self.check_invariant(0)

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
                self.show([(node, troubled_nb)])
                # save_instance_temp(self.inst)
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

        self.begin = True

        # print(f"Starting Potential: {self.potential():0.1f}")

        self.fixup()

        dag = DAG(dag.num_nodes, self.active_edges, make_parents(self.active_edges))
        return get_ecmp_DAG(dag, inst)
