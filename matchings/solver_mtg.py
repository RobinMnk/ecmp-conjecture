from collections import defaultdict

import gurobipy as gp
from gurobipy import GRB

from model import DAG, Solution, InstanceMTG


def optimal_solution_mtg(inst: InstanceMTG):
    "n, m, edges, out_degrees"

    try:
        # print("..Setup Model")
        # Create a new model
        model = gp.Model("dag_opt_mtg")
        model.setParam("OutputFlag", 0)

        """ Add Variables """
        # Congestion variable

        loads_top = list()
        edges = list()
        for i in range(inst.n):
            loads_top.append(
                model.addVar(name=f"d_{i}", obj=0.0, lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, column=None)
            )
            edges.append([
                model.addVar(name=f"e_{i}{j}", obj=0.0, lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, column=None)
                for j in inst.edges[i]
            ])

        """ Set Objective """
        model.setObjective(sum(loads_top), GRB.MAXIMIZE)

        """ Add constraints """
        for i in range(inst.n):
            model.addConstr(
                loads_top[i] == sum(edges[i]),
                name=f"Loads {i}"
            )
            for j in range(len(edges[i])):
                model.addConstr(edges[i][j] <= 1, name=f"OPT=1, {i}{j}")

        for j in range(inst.m):
            model.addConstr(sum(edges[i][k] for i in range(inst.n) for k in range(inst.m) if j in inst.edges[i] and k == inst.edges[i].index(j)) <= inst.out_degrees[j], name=f"out_deg {j}")

            # model.addConstr(sum(edges[i][inst.edges[i].index(j)] for i in range(inst.n) if j in inst.edges[i]) <= inst.out_degrees[j], name=f"out_deg {j}")

        """ Optimize """
        # print("..Solve")
        model.optimize()

        if model.status == GRB.INFEASIBLE:
            return None

        """ Output solution """
        volume = model.ObjVal

        # Build Solution DAG
        sol_dag_edges = defaultdict(lambda: defaultdict(float))
        parents = defaultdict(list)

        for i in range(1, inst.n):
            for j in range(len(inst.edges[i])):
                val = edges[i][j].X
                sol_dag_edges[i][inst.n + j] = val
                parents[inst.n + j].append(i)

        best_loads = [loads_top[i].X for i in range(inst.n)]

        model.dispose()

        sol_dag = DAG(inst.n + inst.m, sol_dag_edges, parents)
        solution = Solution(sol_dag, volume)

        return solution, best_loads

    except gp.GurobiError as e:
        print('Error code ' + str(e.message) + ': ' + str(e))

    # except AttributeError:
    #     print('Encountered an attribute error')

    return None