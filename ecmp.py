import itertools

import more_itertools
import copy

from model import *


def get_ecmp_DAG(dag: DAG, inst: Instance, all_checks=True) -> ECMP_Sol:
    node_val = [d for d in inst.demands]
    edges = defaultdict(lambda: defaultdict(float))
    parents = defaultdict(list)

    congestion = 0
    for node in reversed(range(1, inst.dag.num_nodes)):  # topologicalSort(dag):
        degree = len(dag.neighbors[node])
        if len(set(dag.neighbors[node])) < len(dag.neighbors[node]):
            raise Exception(f"Double edges not allowed!\n{node} -> {dag.neighbors[node]}")
        if all_checks and node_val[node] > 0 and len(dag.neighbors[node]) == 0:
            raise Exception(f"Node {node} has positive load but no outgoing edge!")
        if degree > 0:
            value = node_val[node] / degree
            for nb in dag.neighbors[node]:
                node_val[nb] += value
                congestion = max(congestion, value)
                edges[node][nb] += value
                parents[nb].append(node)

    return ECMP_Sol(DAG(dag.num_nodes, edges, parents), congestion, node_val)


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
