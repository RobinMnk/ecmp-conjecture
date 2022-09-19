from collections import namedtuple, defaultdict

import random
import graphviz

DAG = namedtuple("DAG", "num_nodes, neighbors")
Instance = namedtuple("Instance", "dag, sources, target")
Solution = namedtuple("Solution", "dag, opt_congestion")


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


def instance_to_dot(instance: Instance, solution: DAG = None):
    dot = graphviz.Digraph('ecmp-test', comment='ECMP Test')
    dot.node(str(0), "target", color="red")
    for node in range(1, instance.dag.num_nodes):
        dot.node(str(node), str(node), color="blue" if node in instance.sources else "black")

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
