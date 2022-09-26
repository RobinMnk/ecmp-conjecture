import itertools

import more_itertools
import copy

from model import *


def get_ecmp_congestion(dag: DAG, sources: list[int]) -> float:
    node_val = [1 if i in sources else 0 for i in range(dag.num_nodes)]

    congestion = 0
    for node in topologicalSort(dag):
        degree = len(dag.neighbors[node])
        if degree > 0:
            value = node_val[node] / degree
            for nb in dag.neighbors[node]:
                node_val[nb] += value
                congestion = max(congestion, value)

    return congestion


def get_ecmp_DAG(dag: DAG, sources: list[int]) -> ECMP_Sol:
    node_val = [1 if i in sources else 0 for i in range(dag.num_nodes)]
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
            pwset.pop()
            edges.append(pwset)
    return edges


def iterate_sub_DAG(dag: DAG):
    edges = _get_removable_edges(dag)

    for pos in itertools.product(*edges):
        cp = copy.deepcopy(dag)
        for i in pos:
            for node, nb in i:
                del cp.neighbors[node][nb]
        yield cp


def get_optimal_ECMP_sub_DAG(dag: DAG, sources: list[int]) -> ECMP_Sol:
    best = ECMP_Sol(None, dag.num_nodes, [])
    for sub_dag in iterate_sub_DAG(dag):
        result = get_ecmp_DAG(sub_dag, sources)
        if result.congestion < best.congestion:
            best = result
    return best
