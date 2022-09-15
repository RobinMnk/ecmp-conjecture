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
