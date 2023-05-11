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
        cong = model.addVar(name="cong", obj=1.0, lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, column=None)

        out_flow = []
        for i in range(inst.n):
            out_flow.append([
                model.addVar(name=f"x_{i}{j}", obj=0.0, lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, column=None)
                for j in range(inst.m)
            ])

        """ Set Objective """
        model.setObjective(cong, GRB.MINIMIZE)

        """ Add constraints """
        for i in range(inst.n):
            model.addConstr(
                sum(out_flow[i][j] for j in inst.edges[i]) == inst.top_loads[i], name=f"out_flow {i}"
            )
            for j in inst.edges[i]:
                model.addConstr(out_flow[i][j] <= cong, name=f"cong {i}{j}")

        for j in range(inst.m):
            model.addConstr(sum(out_flow[i][j] for i in inst.parents[j]) <= inst.out_degrees[j], name=f"out_deg {j}")

        """ Optimize """
        # print("..Solve")
        model.optimize()

        if model.status == GRB.INFEASIBLE:
            return None

        """ Output solution """
        opt_cong = model.ObjVal

        # Build Solution DAG
        sol_dag_edges = defaultdict(lambda: defaultdict(float))
        parents = defaultdict(list)

        for i in range(1, inst.n):
            for j in range(len(inst.edges[i])):
                val = out_flow[i][j].X / opt_cong
                if val > 0:
                    sol_dag_edges[i][inst.n + j] = val
                    parents[inst.n + j].append(i)

        model.dispose()

        sol_dag = DAG(inst.n + inst.m, sol_dag_edges, parents)
        solution = Solution(sol_dag, opt_cong)

        return solution

    except gp.GurobiError as e:
        print('Error code ' + str(e.message) + ': ' + str(e))

    # except AttributeError:
    #     print('Encountered an attribute error')

    return None