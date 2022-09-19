import itertools

import more_itertools
import copy

from model import *


def topologicalSortUtil(dag: DAG, node: int, visited, stack):
    visited[node] = True

    for nb in dag.neighbors[node]:
        if not visited[nb]:
            topologicalSortUtil(dag, nb, visited, stack)

    stack.append(node)


def topologicalSort(dag: DAG):
    visited = [False] * dag.num_nodes
    stack = []

    for i in range(dag.num_nodes):
        if not visited[i]:
            topologicalSortUtil(dag, i, visited, stack)

    return reversed(stack)


def get_ecmp_congestion(dag: DAG, sources) -> float:
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


def get_ecmp_DAG(dag: DAG, sources):
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

    return congestion, DAG(dag.num_nodes, edges)


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


