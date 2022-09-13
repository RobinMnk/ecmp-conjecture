from collections import namedtuple

import random
import graphviz

DAG = namedtuple("DAG", "num_nodes, list_edges")
Instance = namedtuple("Instance", "dag, sources, target")


def build_random_DAG(num_nodes, prob_edge):
    edges = list()
    for start in range(num_nodes):
        for end in range(start+1, num_nodes):
            if random.random() < prob_edge:
                edges.append(tuple([start, end]))
            if random.random() < prob_edge:
                edges.append(tuple([end, start]))

    num_sources = random.randint(2, num_nodes - 2)
    sources = random.sample(range(1, num_nodes - 1), num_sources)
    return Instance(DAG(num_nodes, edges), sources, 0)

def instance_to_dot(instance: Instance):
    dot = graphviz.Digraph('ecmp-test', comment='ECMP Test')
    dot.node(str(0), "target", color="red")
    for node in range(1, instance.dag.num_nodes):
        dot.node(str(node), str(node+1), color="blue" if node in instance.sources else "black")

    for edge in instance.dag.list_edges:
        dot.edge(str(edge[0]), str(edge[1]))

    print(dot.source)


if __name__ == '__main__':
    random.seed(31415926535)

    inst = build_random_DAG(4, 0.5)
    instance_to_dot(inst)
