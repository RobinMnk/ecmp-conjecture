import math
import random

from ecmp import get_ecmp_DAG
from model import DAG, Instance, show_graph

alpha = 2


def path_to(a, b, active_edges):
    if b in active_edges[a]:
        return [a]
    else:
        for nb in active_edges[a]:
            p = path_to(nb, b, active_edges)
            if p:
                return [b] + p
        return []


def has_path_to(a, b, active_edges):
    if b in active_edges[a]:
        return True
    else:
        return any(has_path_to(nb, b, active_edges) for nb in active_edges[a])


def get_active_nodes(v, dag: DAG, active_edges):
    """ can (and should) be maintained automatically, this version is very inefficient """
    return [
        node for node in range(v, dag.num_nodes)
        if any(not has_path_to(nb, v, active_edges) for nb in dag.neighbors[node]) and has_path_to(node, v, active_edges)
    ]


def propagate(loads, node, change, active_edges):
    loads[node] += change
    for nb in active_edges[node]:
        propagate(loads, nb, change / len(active_edges[node]), active_edges)


def show(dag: DAG, active_edges, trimmed_inst: Instance):
    dag = DAG(dag.num_nodes, active_edges, [])
    sol = get_ecmp_DAG(dag, trimmed_inst)
    show_graph(trimmed_inst, "_ecmp", sol.dag)


def fixup(v, active_edges, dag: DAG, OPT, loads, trimmed_inst):
    active_nodes = get_active_nodes(v, dag, active_edges)
    candidate_edges = [
        (node, nb) for node in active_nodes for nb in dag.neighbors[node]
        if nb not in active_edges[node] and nb != v
    ]

    extra_load = loads[v] - alpha * OPT * len(dag.neighbors[v])

    if extra_load > len(candidate_edges) * alpha + OPT:
        print("ERROR: cannot find enough candidate edges!")

    while loads[v] > alpha * OPT * len(dag.neighbors[v]):
        edge = random.choice(candidate_edges)
        start, end = edge
        volume = loads[start] / len(active_edges[start])

        # Delete edge on path to v
        neighbor_to_delete = random.choice(list(x for x in active_edges[start] if (start, x) not in candidate_edges))
        propagate(loads, neighbor_to_delete, -volume, active_edges)
        active_edges[start].remove(neighbor_to_delete)

        # Activate candidate edge
        propagate(loads, end, volume, active_edges)
        active_edges[start].append(end)
        candidate_edges.remove(edge)


def solve(dag: DAG, inst: Instance, OPT):
    loads = [ld for ld in inst.demands]
    active_edges = [list() for _ in range(dag.num_nodes)]

    trimmed_inst = Instance(dag, inst.sources, inst.target, inst.demands)

    for node in reversed(range(1, dag.num_nodes)):
        if loads[node] == 0: continue
        num_packets = math.ceil(loads[node] / (alpha * OPT))
        degree = len(dag.neighbors[node])

        if num_packets > degree:
            # Call Fixup Routine!
            fixup(node, active_edges, dag, OPT, loads, trimmed_inst)
            num_packets = math.ceil(loads[node] / (alpha * OPT))

        for neighbor in random.sample(list(dag.neighbors[node]), num_packets):
            # Activate edge node -> neighbor
            active_edges[node].append(neighbor)
            loads[neighbor] += loads[node] / num_packets

    dag = DAG(dag.num_nodes, active_edges, [])
    return get_ecmp_DAG(dag, inst)
