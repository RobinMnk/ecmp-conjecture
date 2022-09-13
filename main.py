import itertools
from collections import namedtuple

import random

DAG = namedtuple("DAG", "num_nodes, list_edges")
Instance = namedtuple("Instance", "dag, sources, target")


def build_random_DAG(num_nodes, prob_edge):
    edges = list()
    for pair in itertools.product(range(num_nodes), range(num_nodes)):
        if pair[0] == pair[1]: continue

        if random.random() < prob_edge:
            edges.append(tuple(pair))
        if random.random() < prob_edge:
            edges.append(tuple(reversed(pair)))

    num_sources = random.randint(2, num_nodes - 2)
    sources = random.sample(range(1, num_nodes-1), num_sources)
    return Instance(DAG(num_nodes, edges), sources, 0)


if __name__ == '__main__':
    random.seed(31415926535)

    inst = build_random_DAG(5, 0.2)
    print(inst)
