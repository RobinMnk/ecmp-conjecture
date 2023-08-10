from model import *

import gurobipy as gp
from gurobipy import GRB


def dd():
    return defaultdict(float)


def optimal_solution_in_DAG(instance: Instance) -> Solution:
    dag: DAG = instance.dag
    demands = instance.demands
    n = dag.num_nodes

    try:
        # print("..Setup Model")
        # Create a new model
        m = gp.Model("dag_opt")
        m.setParam("OutputFlag", 0)

        """ Add Variables """
        # Congestion variable
        cong = m.addVar(name="cong", obj=1.0, lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, column=None)

        out_flow = [[]]
        for i in range(1, n):
            out_flow.append([
                m.addVar(name=f"x_{i}{j}", obj=0.0, lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, column=None)
                for j in range(n)
            ])

        """ Set Objective """
        m.setObjective(cong, GRB.MINIMIZE)

        """ Add constraints """
        for i in range(1, n):
            m.addConstr(
                sum(out_flow[i][j] for j in dag.neighbors[i]) == demands[i] + sum(out_flow[p][i] for p in dag.parents[i]),
                name=f"Constr. {i}"
            )
            for j in dag.neighbors[i]:
                m.addConstr(out_flow[i][j] <= cong, name=f"cong {i}{j}")

        """ Optimize """
        # print("..Solve")
        m.optimize()

        if m.status == GRB.INFEASIBLE:
            return None

        """ Output solution """
        opt_cong = m.ObjVal

        # Build Solution DAG
        sol_dag_edges = defaultdict(dd)
        parents = defaultdict(list)

        for i in range(1, n):
            for j in range(n):
                val = out_flow[i][j].X
                if val > 0:
                    sol_dag_edges[i][j] = val
                    parents[j].append(i)

        m.dispose()

        sol_dag = DAG(n, sol_dag_edges, parents)
        solution = Solution(sol_dag, opt_cong)

        return solution

    except gp.GurobiError as e:
        print('Error code ' + str(e.message) + ': ' + str(e))

    # except AttributeError:
    #     print('Encountered an attribute error')

    return None