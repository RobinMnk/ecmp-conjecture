import pickle

from model import *

import gurobipy as gp
from gurobipy import GRB


def _rec_generate_all_paths(G: DAG, node: int, target: int, visited: list, edge_dict: dict, path: list):
    if node == target:
        pathname = f"path:{'-'.join(map(lambda x: str(x), path))}"
        for i in range(len(path) - 1):
            edge = (path[i], path[i + 1])
            edge_dict[edge].append(pathname)
        yield pathname
    else:
        for nb in G.neighbors[node]:
            if nb not in path:
                path.append(nb)
                yield from _rec_generate_all_paths(G, nb, target, visited, edge_dict, path)
                path.pop()


def generate_all_paths(G: DAG, source: int, target: int, edge_dict: dict):
    visited = [False] * G.num_nodes
    yield from _rec_generate_all_paths(G, source, target, visited, edge_dict, [source])


def _rec_find_cycles(G: DAG, node, visited, cycle):
    visited[node] = True
    cycle.append(node)

    for nb in G.neighbors[node]:
        if not visited[nb]:
            c = _rec_find_cycles(G, nb, visited, cycle)
            if c is not None:
                return c
        elif nb in cycle:
            return cycle[cycle.index(nb):]

    cycle.remove(node)
    return None


def _remove_cycle(G: DAG, cycle):
    val = G.num_nodes
    for i in range(len(cycle)):
        from_id = cycle[i]
        to_id = cycle[(i + 1) % len(cycle)]
        if to_id not in G.neighbors[from_id]:
            return
        val = min(val, G.neighbors[from_id][to_id])

    for i in range(len(cycle)):
        from_id = cycle[i]
        to_id = cycle[(i + 1) % len(cycle)]
        G.neighbors[from_id][to_id] -= val
        if G.neighbors[from_id][to_id] < 1e-15:
            del G.neighbors[from_id][to_id]


def remove_cycles(graph: DAG):
    count = 0

    def check_from_all_nodes():
        visited = [False] * graph.num_nodes
        for node in range(graph.num_nodes):
            if not visited[node]:
                cycle = _rec_find_cycles(graph, node, visited, [])
                if cycle is not None:
                    _remove_cycle(graph, cycle)
                    return True
        return False

    while check_from_all_nodes():
        count += 1
        if count > 100:
            with open(f"graph/progr_error/graph.pickle", "wb") as f:
                pickle.dump(graph, f, pickle.HIGHEST_PROTOCOL)
            with open(f"graph/progr_error/graph.txt", "w") as f:
                f.write("Could not remove all cycles!")

    check_from_all_nodes()


def add_path_to_DAG(dag: DAG, path: str, val: float):
    nodes = list(map(int, path[5:].split("-")))
    for i in range(len(nodes) - 1):
        from_id = nodes[i]
        to_id = nodes[i + 1]

        # if from_id in dag.neighbors[to_id]:
        #     # dag already has back edge
        #     back_edge = dag.neighbors[to_id][from_id]
        #     if val >= back_edge:
        #         del dag.neighbors[to_id][from_id]
        #         dag.neighbors[from_id][to_id] += val - back_edge
        #     else:
        #         dag.neighbors[to_id][from_id] -= val
        # else:
        dag.neighbors[from_id][to_id] += val


def calculate_optimal_solution(instance: Instance):
    dag: DAG = instance.dag
    sources = instance.sources
    target = instance.target
    demands = instance.demands

    try:
        # print("..Setup Model")
        # Create a new model
        m = gp.Model("ecmp_opt")
        m.setParam("OutputFlag", 0)

        """ Add Variables """
        # Congestion variable
        cong = m.addVar(name="cong", obj=1.0, lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, column=None)

        # Add a variable for each source -> target path, for each source
        path_vars = dict()
        edge_dict = defaultdict(list)
        for s in sources:
            path_vars[s] = list()
            for p in generate_all_paths(dag, s, target, edge_dict):
                path_vars[s].append(
                    m.addVar(name=p, obj=0.0, lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, column=None)
                )

        """ Set Objective """
        m.setObjective(cong, GRB.MINIMIZE)

        """ Add constraints """
        for i, s in enumerate(sources):
            m.addConstr(sum(path_vars[s]) >= demands[i], name=f"source:{s}")

        m.update()  # necessary to ensure we can access the variables by name below!
        for k, v in edge_dict.items():
            m.addConstr(sum([m.getVarByName(f"{name}") for name in v]) <= cong, name=f"edge:{k}")

        """ Optimize """
        # print("..Solve")
        m.optimize()

        if m.status == GRB.INFEASIBLE:
            return None

        """ Output solution """
        # print("..Construct Solution")
        solution_dag = DAG(dag.num_nodes, defaultdict(lambda: defaultdict(float)))
        opt_cong = m.ObjVal
        for v in m.getVars():
            if v.VarName != "cong":
                if v.X > 0:
                    add_path_to_DAG(solution_dag, v.VarName, v.X)

        m.dispose()

        remove_cycles(solution_dag)

        solution = Solution(solution_dag, opt_cong)

        return solution

    except gp.GurobiError as e:
        print('Error code ' + str(e.message) + ': ' + str(e))

    # except AttributeError:
    #     print('Encountered an attribute error')

    return None
