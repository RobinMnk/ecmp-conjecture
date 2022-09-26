import logging
import multiprocessing
import sys
from collections import namedtuple, defaultdict

import random
import graphviz

DAG = namedtuple("DAG", "num_nodes, neighbors")
Instance = namedtuple("Instance", "dag, sources, target")
Solution = namedtuple("Solution", "dag, opt_congestion")
ECMP_Sol = namedtuple("ECMP_Sol", "dag, congestion, loads")


def build_random_DAG(num_nodes, prob_edge):
    edges = defaultdict(list)
    for start in range(num_nodes):
        for end in range(start + 1, num_nodes):
            if random.random() < prob_edge:
                edges[start].append(end)
            if random.random() < prob_edge:
                edges[end].append(start)

    num_sources = random.randint(2, num_nodes - 2)
    sources = random.sample(range(1, num_nodes - 1), num_sources)
    return Instance(DAG(num_nodes, edges), sources, 0)


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


def get_node_loads(dag: DAG, sources):
    node_loads = [1 if i in sources else 0 for i in range(dag.num_nodes)]

    for node in topologicalSort(dag):
        for nb in dag.neighbors[node]:
            node_loads[nb] += dag.neighbors[node][nb]

    return node_loads


def instance_to_dot(instance: Instance, solution: DAG = None):
    dot = graphviz.Digraph('ecmp-test', comment='ECMP Test')
    dot.node(str(0), "target", color="red")
    node_loads = get_node_loads(solution, instance.sources)
    for node in range(1, instance.dag.num_nodes):
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
        if i in sources and a > 2 * b:
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

