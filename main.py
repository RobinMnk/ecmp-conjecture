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
        dot.node(str(node), str(node + 1), color="blue" if node in instance.sources else "black")

        for nb in instance.dag.neighbors[node]:
            dot.edge(str(node), str(nb))

    print(dot.source)


def _rec_generate_all_paths(G: DAG, node: int, target: int, visited: list, path: list):

    if node == target:
        yield " - ".join(map(lambda x: str(x+1), path))
    else:
        for nb in G.neighbors[node]:
            if not nb in path:
                path.append(nb)
                yield from _rec_generate_all_paths(G, nb, target, visited, path)
                path.pop()


def generate_all_paths(G: DAG, source: int, target: int):
    visited = [False for _ in range(G.num_nodes)]
    yield from _rec_generate_all_paths(G, source, target, visited, [source])


if __name__ == '__main__':
    random.seed(31415926535)

    inst = build_random_DAG(5, 0.4)
    instance_to_dot(inst)

    for p in generate_all_paths(inst.dag, 2, 0):
        print(p)
