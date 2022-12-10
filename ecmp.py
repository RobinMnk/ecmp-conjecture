import itertools
from typing import NewType

import more_itertools
import copy

from conjectures import check_all_conjectures, Conjecture, MAIN_CONJECTURE, LOADS_CONJECTURE
from model import *


def get_ecmp_DAG(dag: DAG, inst: Instance) -> ECMP_Sol:
    node_val = [0] * inst.dag.num_nodes
    for s, d in zip(inst.sources, inst.demands):
        node_val[s] = d

    edges = defaultdict(lambda: defaultdict(int))

    congestion = 0
    for node in topologicalSort(dag):
        degree = len(dag.neighbors[node])
        if degree > 0:
            value = node_val[node] / degree
            for nb in dag.neighbors[node]:
                node_val[nb] += value
                congestion = max(congestion, value)
                edges[node][nb] += value

    return ECMP_Sol(DAG(dag.num_nodes, edges), congestion, node_val)


def _get_removable_edges(dag: DAG):
    edges = list()
    for node in range(dag.num_nodes):
        if len(dag.neighbors[node]) > 1:
            pwset = list(more_itertools.powerset((node, nb) for nb in dag.neighbors[node]))
            pwset.pop()  # remove empty edgeset
            edges.append(pwset)
    return edges


def _get_single_forwarding_removable_edges(dag: DAG):
    edges = list()
    for node in range(dag.num_nodes):
        if len(dag.neighbors[node]) > 1:
            row = list()
            lst = [(node, nb) for nb in dag.neighbors[node]]
            for entry in lst:
                row.append([x for x in lst if x != entry])
            edges.append(row)
    return edges


def iterate_sub_DAG(dag: DAG, mode="ecmp"):
    """
        Parameters:
                dag (DAG): The DAG to iterate
                mode ("ecmp" | "single_forwarding"): the type of returned sub-DAG

        Returns:
                Generator to iterate all sub DAGs based on mode
    """
    if mode == "ecmp":
        edges = _get_removable_edges(dag)
    elif mode == "single_forwarding":
        edges = _get_single_forwarding_removable_edges(dag)
    else:
        print("iterate_sub_DAG got unexpected 'mode' parameter.\nExpected 'ecmp' or 'single_forwarding'")
        return None

    if not edges:
        yield dag
        return None

    for pos in itertools.product(*edges):
        cp = copy.deepcopy(dag)
        for i in pos:
            for node, nb in i:
                del cp.neighbors[node][nb]
        yield cp


def get_optimal_ECMP_sub_DAG(dag: DAG, inst: Instance) -> ECMP_Sol:
    best = ECMP_Sol(None, dag.num_nodes, [])
    for sub_dag in iterate_sub_DAG(dag):
        result = get_ecmp_DAG(sub_dag, inst)
        if result.congestion < best.congestion:
            best = result
    return best


def get_ALL_optimal_ECMP_sub_DAGs(dag: DAG, inst: Instance) -> list[ECMP_Sol]:
    all_best = []
    best_congestion = float('inf')
    for sub_dag in iterate_sub_DAG(dag):
        result = get_ecmp_DAG(sub_dag, inst)
        if result.congestion < best_congestion:
            all_best = [result]
            best_congestion = result.congestion
        if result.congestion == best_congestion:
            all_best.append(result)
    return all_best


def check_conjectures_for_every_sub_DAG(opt_solution: Solution, inst: Instance, index: int) -> ECMP_Sol:
    solution = None
    verbose = Conjecture.VERBOSE
    Conjecture.VERBOSE = False
    for sub_dag in iterate_sub_DAG(opt_solution.dag):
        result = get_ecmp_DAG(sub_dag, inst)
        if check_all_conjectures(opt_solution, [result], inst, index):
            solution = result
    Conjecture.VERBOSE = verbose
    return solution


def check_sequentially_for_every_sub_DAG(opt_solution: Solution, inst: Instance, index: int) -> bool:
    verbose = Conjecture.VERBOSE
    Conjecture.VERBOSE = False
    success = True
    for sub_dag in iterate_sub_DAG(opt_solution.dag):
        result = get_ecmp_DAG(sub_dag, inst.sources)
        if LOADS_CONJECTURE.check(opt_solution, [result], inst, index) and \
                not MAIN_CONJECTURE.check(opt_solution, [result], inst, index):
            success = False
            break

    Conjecture.VERBOSE = verbose
    return success


def get_ALL_optimal_single_forwarding_DAGs(dag: DAG, inst: Instance) -> list[ECMP_Sol]:
    all_best = []
    best_congestion = float('inf')
    for sub_dag in iterate_sub_DAG(dag, mode="single_forwarding"):
        result = get_ecmp_DAG(sub_dag, inst)
        if result.congestion < best_congestion:
            all_best = [result]
            best_congestion = result.congestion
        if result.congestion == best_congestion:
            all_best.append(result)
    return all_best
