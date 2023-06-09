import random
from collections import defaultdict

from matchings.opt_solver_mtg import optimal_solution_mtg
from model import show_graph, InstanceMTG, Instance, DAG


def generate_instance(n, m):
    edges = defaultdict(list)
    parents = [list() for _ in range(m)]
    for i in range(n):
        num_neighbors = random.randint(1, int(m))
        neighbors = random.sample(range(m), num_neighbors)
        edges[i] = neighbors
        for nb in neighbors:
            parents[nb].append(i)

    top_loads = [random.randint(1, 3) for _ in range(n)]
    out_degrees = [random.randint(1, 4) for _ in range(m)]
    return InstanceMTG(n, m, edges, parents, top_loads, out_degrees)


def run():
    inst = generate_instance(6, 4)
    solution = optimal_solution_mtg(inst)
    if solution is None:
        print("Infeasible instance")
        return
    print(f"Cong: {solution.opt_congestion}")
    dag = DAG(inst.n + inst.m, [[inst.n + nb for nb in inst.edges[i]] for i in range(inst.n)] + [[] for _ in range(inst.m)], inst.parents)
    new_inst = Instance(dag, [i for i in range(inst.n) if inst.top_loads[i] > 0], 100, [x / solution.opt_congestion for x in inst.top_loads] + [0] * inst.m)
    show_graph(new_inst, "_mtg", solution.dag)
    print("Done")

