from collections import namedtuple, defaultdict

import random
import graphviz

DAG = namedtuple("DAG", "num_nodes, neighbors")
Instance = namedtuple("Instance", "dag, sources, target")


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


def instance_to_dot(instance: Instance):
    dot = graphviz.Digraph('ecmp-test', comment='ECMP Test')
    dot.node(str(0), "target", color="red")
    for node in range(1, instance.dag.num_nodes):
        dot.node(str(node), str(node), color="blue" if node in instance.sources else "black")

        for nb in instance.dag.neighbors[node]:
            dot.edge(str(node), str(nb))

    s = graphviz.Source(dot.source, filename="graph/output", format="svg")
    s.render(engine="circo")


if __name__ == '__main__':
    random.seed(31415926535)

    inst = build_random_DAG(10, 0.4)
    instance_to_dot(inst)
