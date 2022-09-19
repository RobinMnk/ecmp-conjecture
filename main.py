import time
import pickle

from model import *
from optimal_solver import calculate_optimal_solution, remove_cycles
from ecmp import get_ecmp_congestion


def test_random():
    max_factor = 0
    for i in range(500):
        seed = int(time.time()) + 4132 * i
        random.seed(seed)
        size = 9 #  random.randint(4, 10)
        prob = 1 # random.randint(1, 32)

        print("\n--------------------------------------------------------------")
        print(f"Iteration {i}: Building Instance on {size} nodes with edge probability 1 / {prob}")
        inst = build_random_DAG(size, 1 / prob)

        print("Calculating optimal solution")
        solution = calculate_optimal_solution(inst)

        if solution is None:
            print("Error in computing optimal solution")
            continue

        with open(f"graph/temp.pickle", "wb") as f:
            pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)

        if not remove_cycles(solution.dag):
            print(f"\n\n\nERROR: graph{i}")
            show_graph(inst, f"graph{i}", solution.dag)
            with open(f"graph/graph{i}.pickle", "wb") as f:
                pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
            exit(1)

        print("Calculating ECMP solution")
        ecmp_cong = get_ecmp_congestion(solution.dag, inst.sources)
        print(f"ECMP Congestion: {ecmp_cong}")

        factor = ecmp_cong / solution.opt_congestion
        max_factor = max(max_factor, factor)
        print(f"Factor: {factor}")
        print(f"{seed=}")

        if ecmp_cong < solution.opt_congestion:
            print(f"\n\n\nERROR: graph{i}")
            show_graph(inst, f"graph{i}", solution.dag)
            with open(f"graph/graph{i}.pickle", "wb") as f:
                pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
            # exit(1)

        if max_factor >= 2 or max_factor < 1:
            print(f"\n\n\nFACTOR > 2: graph{i}")
            show_graph(inst, f"graph{i}", solution.dag)
            with open(f"graph/graph{i}.pickle", "wb") as f:
                pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
                break

    print(" ------------------------------ ")
    print(f"{max_factor}")
    print("SUCCESS!" if max_factor < 2 else "FAIL!")


if __name__ == '__main__':

    # test_random()
    # exit(0)

    graph_index = 4
    with open(f"graph/graph{graph_index}.pickle", "rb") as f:
        inst = pickle.load(f)

        solution = calculate_optimal_solution(inst)
        show_graph(inst, "_before", solution.dag)
        remove_cycles(solution.dag)

        trimmed_inst = Instance(solution.dag, inst.sources, inst.target)
        show_graph(trimmed_inst, "_after", solution.dag)


