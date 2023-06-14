import math

from ecmp import get_ecmp_DAG
from model import DAG, Instance, show_graph, save_instance, _eps, make_parents, save_instance_temp, ECMP_Sol


def path_to(a, b, active_edges):
    if a == b or b in active_edges[a]:
        return [a]
    else:
        for nb in active_edges[a]:
            p = path_to(nb, b, active_edges)
            if p:
                return [b] + p
        return None


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

    def check_invariant(self, active_nodes):

        leaving_edges = [
            (z, n) for z in active_nodes for n in self.active_edges[z]
            if n not in active_nodes and n not in self.violated_nodes
        ]

        if len(leaving_edges) > 0 and all(e in self.marked for e in leaving_edges):
            self.show()
            print(active_nodes)
            print(leaving_edges)
            raise Exception(f"Invariant failed for set: {active_nodes}")

        # for z in active_nodes:
        #     if len([e for e in self.active_edges[z] if e not in active_nodes and e not in self.violated_nodes]) > 0:
        #         deg = len(self.active_edges[z])
        #         pz = math.ceil(self.loads[z] / (alpha * self.OPT))
        #         mz = deg - pz
        #
        #         need = mz <= pz - 2
        #
        #         if not need:
        #             self.show()
        #             print(z)
        #             print((pz-1)/(pz+mz))
        #             raise Exception(f"Invariant failed for set: {active_nodes}")

        # for z in active_nodes:
        #     for N in [(z, n) for n in zip(more_itertools.powerset(list(self.dag.neighbors[z].keys())))]:
        #         if len(N[1]) <= len(self.active_edges[z]):
        #             continue
        #
        #         foundOne = False
        #         for S in more_itertools.powerset(active_nodes):
        #             if len(S) == 0:
        #                 continue
        #
        #             edge_set = [(a, e) for a in S for e in self.dag.neighbors[a] if (a, e) not in N and e not in S]
        #             demands = sum(self.inst.demands[v] for v in S)
        #
        #             if len(edge_set) * self.OPT < demands:
        #                 foundOne = True
        #                 break
        #
        #         if not foundOne:
        #             self.show()
        #             print(z)
        #             print(N)
        #             raise Exception(f"Invariant failed for set: {active_nodes}")

    # def prune(self, cutoff, active_nodes):
    #     changes_made = False
    #     for z in active_nodes:
    #         f = self.loads[z] / len(self.active_edges[z])
    #         for nb in self.active_edges[z]:
    #             if nb == 0:
    #                 continue
    #             desc = [z for z in range(cutoff, self.dag.num_nodes)
    #                     if self.has_path_to_node_set(nb, [z], active_edges_only=True)]
    #             if len(desc) > 0 and all(self.loads[w] <= self.alpha * self.OPT * len(self.dag.neighbors[w]) - f for w in desc):
    #                 self.active_edges[z].remove(nb)
    #                 if (z, nb) in self.marked:
    #                     self.marked.remove((z, nb))
    #                 changes_made = True
    #     return changes_made

    def update_loads(self, end):
        """ loads can (and should) be maintained automatically, this version is very inefficient """
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst)
        self.loads = [ld for ld in sol.loads]
        for node in reversed(range(end, dag.num_nodes)):
            if node in self.violated_nodes:
                continue

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
                    self.removed.append((node, smallest_neighbor))
                    self.update_loads(end)
                    return

    def show(self):
        trimmed_inst = Instance(self.dag, self.inst.sources, self.inst.target, self.loads)
        dag = DAG(self.dag.num_nodes, self.active_edges, [])
        sol = get_ecmp_DAG(dag, self.inst)
        show_graph(trimmed_inst, "_ecmp", sol.dag)


    def check_invariant2(self, current, active_nodes):
        # k = len([
        #     (z, n) for z in active_nodes for n in self.active_edges[z]
        #     if n not in active_nodes and n not in self.violated_nodes
        #     if self.loads[z] / len(self.active_edges[z]) < (self.alpha / 2) * self.OPT
        # ])
        #
        # degrees_X = sum(len(self.dag.neighbors[a]) for a in self.violated_nodes)
        # val = degrees_X
        #
        for z in active_nodes:
            if len(self.active_edges[z]) == 1:
                continue
            f = self.loads[z] / len(self.active_edges[z])
            if f >= self.alpha * self.OPT / 2:
                continue
        #
            pz = math.ceil(self.loads[z] / (self.alpha * self.OPT))
            mz = len(self.active_edges[z]) - pz

            if mz > 1:
                self.show()
                print("Invariant failed! mz > 1")
                save_instance_temp(self.inst)
                raise Exception("Assumption failed")

            # if mz == 1:
            #     if pz < 3:
            #         print("Assumption failed!, pz too small")
            #         save_instance_temp(self.inst)
            #         raise Exception("Assumption failed")

            # continue
        #     val += (pz - 1) / (pz + mz)
        #
        # if not val >= k / 2:
        #     self.show()
        #     print("Invariant failed!")
        #     # raise Exception("Invariant failed!")

            for nb in self.active_edges[z]:
                if nb == 0:
                    continue

                candidate_nodes = [
                    w for w in range(1, self.dag.num_nodes)
                    if path_to(nb, w, self.active_edges) is not None
                    and self.loads[w] > self.alpha * self.OPT * (len(self.dag.neighbors[w]) - 0.5)
                ]

                # if len(candidate_nodes) < len(self.active_edges[z]) / 2 - 1:
                #     self.show()
                #     edge = (z, nb)
                #     print("Invariant failed!")
                    # raise Exception("Invariant failed!")

                if len(candidate_nodes) == 0:
                    # self.show()
                    # save_instance_temp(self.inst)
                    # raise Exception("Invariant failed!")

                    # before = max(self.loads[x] / len(self.active_edges[x]) for x in range(current, self.dag.num_nodes) if len(self.active_edges[x]) > 0 and x not in self.violated_nodes)

                    for e in self.marked:
                        u, _ = e
                        if z == u:
                            self.marked.remove(e)
                    self.update_loads(current)

                    active_nodes = self.get_active_nodes()
                    if z not in active_nodes:
                        continue

                    if nb not in self.active_edges[z]:
                        continue

                    candidate_nodes = [
                        w for w in range(1, self.dag.num_nodes)
                        if path_to(nb, w, self.active_edges) is not None
                           and self.loads[w] > self.alpha * self.OPT * (len(self.dag.neighbors[w]) - 0.5)
                    ]

                    # after = max(self.loads[x] / len(self.active_edges[x]) for x in range(current, self.dag.num_nodes) if len(self.active_edges[x]) > 0 and x not in self.violated_nodes)

                    # # Check can remove edge (z, nb)
                    # es = [[e for e in self.active_edges[z]] for z in range(self.dag.num_nodes)]
                    # es[z].remove(nb)
                    # dag = DAG(self.dag.num_nodes, es, [])
                    # sol = get_ecmp_DAG(dag, self.inst)
                    # cong = max(sol.loads[x] / len(es[x]) for x in range(current, dag.num_nodes) if len(es[x]) > 0 and x not in self.violated_nodes)
                    #
                    # mycong = max(self.loads[x] / len(self.active_edges[x]) for x in range(current, dag.num_nodes) if len(self.active_edges[x]) > 0 and x not in self.violated_nodes)

                    # if after > before:
                    if len(candidate_nodes) == 0:
                        self.show()
                        print("Invariant failed! no violated node in desc")
                        save_instance_temp(self.inst)
                        raise Exception("Invariant failed!")
        return True


    def fixup(self, current):
        self.violated_nodes = [current]
        self.removed = list()

        while any(self.is_node_violated(v) for v in self.violated_nodes):

            shrunk_violated = [v for v in self.violated_nodes if self.is_node_violated(v)]
            if len(shrunk_violated) < len(self.violated_nodes):
                self.violated_nodes = shrunk_violated
                continue

            active_nodes = self.get_active_nodes()
            candidate_edges = [
                (node, nb) for node in active_nodes for nb in self.dag.neighbors[node]
                if nb not in self.active_edges[node]
                and nb not in self.violated_nodes
            ]  # all inactive edges leaving an active node

            # if not self.check_invariant2(current, active_nodes):
            #     active_nodes = self.get_active_nodes()
            #     candidate_edges = [
            #         (node, nb) for node in active_nodes for nb in self.dag.neighbors[node]
            #         if nb not in self.active_edges[node]
            #            and nb not in self.violated_nodes
            #     ]

            # self.check_invariant2(current, active_nodes)

            if not candidate_edges:
                # self.check_invariant(active_nodes)

                # Resetting violated node set
                shrunk_violated = [v for v in self.violated_nodes if self.is_node_violated(v)]
                if len(shrunk_violated) < len(self.violated_nodes):
                    self.violated_nodes = shrunk_violated
                    continue

                # Need to increase alpha!
                low_edges = [
                    (z, n) for z in active_nodes for n in self.active_edges[z]
                    if n not in active_nodes and n not in self.violated_nodes
                    if self.loads[z] / len(self.active_edges[z]) < (self.alpha / 2) * self.OPT
                ]
                num_low_edges = len(low_edges)
                Phi = sum(self.loads[z] / len(self.active_edges[z]) for z, _ in low_edges)
                degrees_X = sum(len(self.dag.neighbors[a]) for a in self.violated_nodes)
                degrees_A = sum(len(self.dag.neighbors[a]) for a in active_nodes)

                demands_A = sum(self.inst.demands[z] for z in active_nodes)
                demands_X = sum(self.inst.demands[z] for z in self.violated_nodes)

                new_alpha = 2 - (degrees_X + num_low_edges) / (2 * (degrees_X + num_low_edges) + degrees_A)
                # new_alpha = 2 / (1 + (self.OPT * degrees_X) / (demands_X + demands_A))
                # new_alpha = 2*((demands_A+demands_X-Phi)/self.OPT)/((demands_A+demands_X)/self.OPT + degrees_X - num_low_edges)

                if new_alpha < self.alpha:
                    save_instance("tmp", self.inst, 1)
                    self.show()
                    raise Exception(f"Alpha should only increase! {self.alpha:0.3f}  ->  {new_alpha:0.3f}")

                # print(f"Increasing alpha:  {self.alpha:0.3f}  ->  {new_alpha:0.3f}")

                if new_alpha == self.alpha:
                    # self.prune(current, active_nodes)
                    self.show()
                    save_instance("tmp", self.inst, 1)
                    raise Exception(f"Infinite Loop during fixup for nodes {self.violated_nodes}")
                    # self.marked = []

                self.alpha = new_alpha
                self.marked = []
                self.update_loads(current)
                continue

            edge = min(candidate_edges,
                       key=lambda x: -1 if x[1] == 0 else (
                           self.loads[x[1]] / len(self.dag.neighbors[x[1]])
                           if len(self.dag.neighbors[x[1]]) > 0
                           else self.dag.num_nodes
                       ))
            start, end = edge

            if edge in self.removed:
                self.marked.append(edge)
            else:
                relief_edges = [
                    x for x in self.active_edges[start]
                    if (start, x) not in candidate_edges
                    and self.has_path_to_violated(x, active_edges_only=False)
                ]

                neighbor_to_delete = relief_edges[0]
                self.active_edges[start].remove(neighbor_to_delete)
                self.removed.append((start, neighbor_to_delete))

            self.active_edges[start].append(end)

            candidate_edges.remove(edge)
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

    def solve(self, dag: DAG, inst: Instance, OPT) -> ECMP_Sol:
        self.dag = dag
        self.inst = inst
        self.OPT = OPT + _eps
        self.loads = [ld for ld in inst.demands]
        self.active_edges = [list() for _ in range(dag.num_nodes)]
        self.violated_nodes.clear()
        self.marked = list()

        for node in reversed(list(range(1, dag.num_nodes))):
            self.process_node(node)

        # print(f"Succeeded with alpha = {self.alpha:0.3f}")

        # if self.alpha >= 2:
        #     save_instance("tmp", self.inst, 1)
        #     raise Exception("Assumption failed, alpha >= 2")

        dag = DAG(dag.num_nodes, self.active_edges, make_parents(self.active_edges))
        return get_ecmp_DAG(dag, inst)
