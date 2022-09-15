from main import *

import gurobipy as gp
from gurobipy import GRB


def _rec_generate_all_paths(G: DAG, node: int, target: int, visited: list, edge_dict: dict, path: list):
    if node == target:
        pathname = f"path:{'-'.join(map(lambda x: str(x), path))}"
        for i in range(len(path) - 1):
            edge = tuple([path[i], path[i+1]])
            edge_dict[edge].append(pathname)
        yield pathname
    else:
        for nb in G.neighbors[node]:
            if nb not in path:
                path.append(nb)
                yield from _rec_generate_all_paths(G, nb, target, visited, edge_dict, path)
                path.pop()


def generate_all_paths(G: DAG, source: int, target: int, edge_dict: dict):
    visited = [False for _ in range(G.num_nodes)]
    yield from _rec_generate_all_paths(G, source, target, visited, edge_dict, [source])


def calculate_optimal_solution(instance: Instance):
    dag: DAG = instance.dag
    sources = instance.sources
    target = instance.target

    try:
        # Create a new model
        m = gp.Model("ecmp_opt")

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
        for s in sources:
            m.addConstr(sum(path_vars[s]) >= 1, name=f"source:{s}")

        m.update()  # necessary to ensure we can access the variables by name below!
        for k, v in edge_dict.items():
            m.addConstr(sum([m.getVarByName(f"{name}") for name in v]) <= cong, name=f"edge:{k}")

        """ Optimize """
        m.optimize()

        """ Output solution """
        for v in m.getVars():
            print('%s %g' % (v.VarName, v.X))

        print('Obj: %g' % m.ObjVal)

    except gp.GurobiError as e:
        print('Error code ' + str(e.errno) + ': ' + str(e))

    except AttributeError:
        print('Encountered an attribute error')


if __name__ == '__main__':
    random.seed(31415926535)

    inst = build_random_DAG(10, 0.4)
    instance_to_dot(inst)

    calculate_optimal_solution(inst)
