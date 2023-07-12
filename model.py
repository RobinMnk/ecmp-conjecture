import logging
import multiprocessing
import os
import pickle
import sys
import time
from collections import namedtuple, defaultdict

import random
import graphviz

PREVENT_INSTANCE_OVERWRITE = False
TESTCASE_RUNNING = False

DAG = namedtuple("DAG", "num_nodes, neighbors, parents")
Instance = namedtuple("Instance", "dag, sources, target, demands")
InstanceMTG = namedtuple("Instance", "n, m, edges, parents, top_loads, out_degrees")
Solution = namedtuple("Solution", "dag, opt_congestion")
ECMP_Sol = namedtuple("ECMP_Sol", "dag, congestion, loads")

max_incoming_edges = 1000
max_outgoing_edges = 1000

_eps = 0.00000001


def build_random_DAG(num_nodes, prob_edge, arbitrary_demands=False):
    edges = defaultdict(list)
    parents = defaultdict(list)
    num_ingoing_edges = [0] * num_nodes
    num_outgoing_edges = [0] * num_nodes

    # Enforces that all edges go from larger indices to lower indices
    # n -> 0 is always a topological ordering
    for start in range(1, num_nodes):
        for end in range(max(0, 0), start):  #  - num_nodes // 3
            if random.random() < prob_edge \
                    and num_ingoing_edges[end] < max_incoming_edges \
                    and num_outgoing_edges[start] < max_outgoing_edges:
                edges[start].append(end)
                parents[end].append(start)
                num_ingoing_edges[end] += 1
                num_outgoing_edges[start] += 1

    num_sources = random.randint(1, num_nodes-2)
    sources = random.sample(range(1, num_nodes), num_sources)
    demands = [(random.randint(1, num_nodes) if i in sources else 0) for i in range(num_nodes)]\
        if arbitrary_demands else [1 if i in sources else 0 for i in range(num_nodes)]
    return Instance(DAG(num_nodes, edges, parents), sources, 0, demands)


def topologicalSortUtil(dag: DAG, node: int, visited, stack):
    visited[node] = True

    for nb in dag.neighbors[node]:
        if not visited[nb]:
            topologicalSortUtil(dag, nb, visited, stack)

    stack.append(node)


def make_parents(neighbors):
    parents = [[] for _ in range(len(neighbors))]
    for i, nbs in enumerate(neighbors):
        for nb in nbs:
            parents[nb].append(i)
    return parents


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


def instance_to_dot(instance: Instance, solution: DAG = None, highlighted=None):
    if highlighted is None:
        highlighted = list()
    dot = graphviz.Digraph('ecmp-test', comment='ECMP Test')
    dot.node(str(0), "target", color="red")
    node_loads = instance.demands  # [0] * instance.dag.num_nodes #  get_node_loads(solution, instance)
    for node in range(1, instance.dag.num_nodes):
        if len(instance.dag.neighbors[node]) + len(instance.dag.parents[node]) > 0:
            load_label = f"{node_loads[node]:.2f}".rstrip("0").rstrip(".") if node_loads[node] > 0 else ""
            dot.node(str(node), str(node), color="blue" if node in instance.sources else "black", xlabel=load_label)

            for nb in instance.dag.neighbors[node]:
                sol_val = solution.neighbors[node] if solution is not None else []
                part_of_solution = nb in sol_val and sol_val[nb] > 0
                edge_color = "red" if (node, nb) in highlighted else ("green" if part_of_solution else "black")
                label = f"{sol_val[nb]:.3f}".rstrip("0").rstrip(".") if part_of_solution else None
                dot.edge(str(node), str(nb), color=edge_color, label=label)

    return dot.source


def show_graph(instance: Instance, name: str, solution: DAG = None, highlighted=None):
    if highlighted is None:
        highlighted = list()
    dot_source = instance_to_dot(instance, solution, highlighted)
    s = graphviz.Source(dot_source, filename=f"output/{name}", format="svg")
    s.render() #  engine="circo")

def compare_node_loads(ecmp_loads, opt_loads, sources):
    for i, (a, b) in enumerate(zip(ecmp_loads, opt_loads)):
        # if i in sources and a > 2 * b:
        if a > 2 * b:
            return i
    return None


def calculate_max_degree_ratio(dag: DAG):
    in_degrees = [0] * dag.num_nodes
    out_degrees = [0] * dag.num_nodes

    for start in range(dag.num_nodes):
        for end in dag.neighbors[start]:
            out_degrees[start] += 1
            in_degrees[end] += 1

    return max([in_degrees[i] / out_degrees[i] for i in range(dag.num_nodes) if out_degrees[i] > 0])



def get_logger():
    return logging.getLogger(multiprocessing.current_process().name + '_worker')


def setup_logger(log_to_stdout=False):
    os.makedirs("output/logs", exist_ok=True)
    fh = logging.FileHandler('output//logs/' + multiprocessing.current_process().name + '_worker.log', mode="w")
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
    os.makedirs(f"output/{path}", exist_ok=True)
    file = f"output/{path}/ex_{index}.pickle"
    if path != "tmp" and (PREVENT_INSTANCE_OVERWRITE or (path == "failures" and not TESTCASE_RUNNING)):
        idx = index
        while os.path.exists(file):
            idx += 1
            file = f"output/{path}/ex_{idx}.pickle"
        if idx != index:
            print(f"WARN: file {path}/ex_{index} already existed. Instead saved as {path}/ex_{idx}")
    with open(file, "wb") as f:
        pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)


def save_instance_temp(inst: Instance):
    os.makedirs("output/tmp", exist_ok=True)
    file = f"output/tmp/ex_1.pickle"
    with open(file, "wb") as f:
        pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
