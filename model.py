import logging
import multiprocessing
import pickle
import sys
import time
from collections import namedtuple, defaultdict

import random
import graphviz

DAG = namedtuple("DAG", "num_nodes, neighbors")
Instance = namedtuple("Instance", "dag, sources, target, demands")
Solution = namedtuple("Solution", "dag, opt_congestion")
ECMP_Sol = namedtuple("ECMP_Sol", "dag, congestion, loads")

max_incoming_edges = 1000
max_outgoing_edges = 2


def build_random_DAG(num_nodes, prob_edge, arbitrary_demands=False):
    edges = defaultdict(list)
    num_ingoing_edges = [0] * num_nodes
    num_outgoing_edges = [0] * num_nodes

    for start in range(num_nodes):
        for end in range(start + 1, num_nodes):
            if random.random() < prob_edge \
                    and num_ingoing_edges[end] < max_incoming_edges \
                    and num_outgoing_edges[start] < max_outgoing_edges:
                edges[start].append(end)
                num_ingoing_edges[end] += 1
                num_outgoing_edges[start] += 1
            if random.random() < prob_edge \
                    and num_ingoing_edges[start] < max_incoming_edges \
                    and num_outgoing_edges[end] < max_outgoing_edges:
                edges[end].append(start)
                num_ingoing_edges[start] += 1
                num_outgoing_edges[end] += 1

    num_sources = random.randint(2, num_nodes - 2)
    sources = random.sample(range(1, num_nodes - 1), num_sources)
    demands = [random.randint(2, 10) for _ in range(len(sources))] if arbitrary_demands else [1] * len(sources)
    return Instance(DAG(num_nodes, edges), sources, 0, demands)


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


def get_node_loads(dag: DAG, inst: Instance):
    node_loads = [0] * inst.dag.num_nodes
    for s, d in zip(inst.sources, inst.demands):
        node_loads[s] = d

    for node in topologicalSort(dag):
        for nb in dag.neighbors[node]:
            node_loads[nb] += dag.neighbors[node][nb]

    return node_loads


def get_edge_loads(dag: DAG):
    edge_loads = defaultdict(float)

    for node in topologicalSort(dag):
        for nb in dag.neighbors[node]:
            edge = (node, nb)
            edge_loads[edge] += dag.neighbors[node][nb]

    return edge_loads


def instance_to_dot(instance: Instance, solution: DAG = None):
    dot = graphviz.Digraph('ecmp-test', comment='ECMP Test')
    dot.node(str(0), "target", color="red")
    node_loads = get_node_loads(solution, instance)
    for node in range(1, instance.dag.num_nodes):
        if len(instance.dag.neighbors[node]) > 0:
            load_label = f"{node_loads[node]:.2f}".rstrip("0").rstrip(".")
            dot.node(str(node), str(node), color="blue" if node in instance.sources else "black", xlabel=load_label)

            for nb in instance.dag.neighbors[node]:
                sol_val = solution.neighbors[node]
                part_of_solution = nb in sol_val
                edge_color = "green" if part_of_solution else "black"
                label = f"{sol_val[nb]:.3f}".rstrip("0").rstrip(".") if part_of_solution else None
                dot.edge(str(node), str(nb), color=edge_color, label=label)

    return dot.source


def show_graph(instance: Instance, name: str, solution: DAG = None):
    dot_source = instance_to_dot(instance, solution)
    s = graphviz.Source(dot_source, filename=f"graph/{name}", format="svg")
    s.render(engine="circo")


def compare_node_loads(ecmp_loads, opt_loads, sources):
    for i, (a, b) in enumerate(zip(ecmp_loads, opt_loads)):
        # if i in sources and a > 2 * b:
        if a > 2 * b:
            return i
    return None


def get_logger():
    return logging.getLogger(multiprocessing.current_process().name + '_worker')


def setup_logger(log_to_stdout=False):
    fh = logging.FileHandler('graph//logs/' + multiprocessing.current_process().name + '_worker.log')
    fmt = logging.Formatter('%(asctime)-6s: %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(fmt)

    local_logger = get_logger()
    local_logger.addHandler(fh)
    if log_to_stdout:
        local_logger.addHandler(logging.StreamHandler(sys.stdout))
    local_logger.setLevel(logging.DEBUG)


def time_execution(function, *parameters):
    start = time.time()
    res = function(*parameters)
    end = time.time()
    return end - start, res


def save_instance(path: str, inst: Instance, index: int):
    with open(f"graph/{path}/ex_{index}.pickle", "wb") as f:
        pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
