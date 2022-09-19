import time
import pickle

from model import *
from optimal_solver import calculate_optimal_solution, remove_cycles
from ecmp import get_ecmp_congestion, get_ecmp_DAG, iterate_sub_DAG


def verify_instance(inst: Instance, index: int):
    print("Calculating optimal solution")
    solution = calculate_optimal_solution(inst)

    if solution is None:
        print("-> Infeasible Model!")
        return True

    if not remove_cycles(solution.dag):
        with open(f"graph/errors/graph{index}.pickle", "wb") as f:
            pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
        with open(f"graph/errors/graph{index}.txt", "w") as f:
            f.write("Could not remove all cycles!")
        return False

    print("Calculating ECMP solution")
    ecmp_cong = get_ecmp_congestion(solution.dag, inst.sources)

    if ecmp_cong < 2 * solution.opt_congestion:
        print("-> Success")
        return True
    else:
        print("..Iterate all sub-DAGs")
        for sub_dag in iterate_sub_DAG(solution.dag):
            ecmp_cong = get_ecmp_congestion(sub_dag, inst.sources)
            if ecmp_cong < 2 * solution.opt_congestion:
                # Success on sub-DAG
                print("-> Success")
                return True

    # FAIL
    return False


def test_suite(num_tests=100):
    success = True
    for i in range(num_tests):
        seed = 543 * int(time.time()) - 4132 * i
        random.seed(seed)
        size = random.randint(4, 11)
        prob = random.random() * 0.8
        print("---------------------------------------------------------------------------")
        print(f"Iteration {i}: Building Instance on {size} nodes with edge probability {prob:0.3f}")
        inst = build_random_DAG(size, prob)
        success &= verify_instance(inst, i)

    print("\n\n\n===========================================================================")
    print(f"{success = }")


def inspect_instance(id):
    with open(f"graph/graph{id}.pickle", "rb") as f:
        inst = pickle.load(f)

        solution = calculate_optimal_solution(inst)
        show_graph(inst, "_before", solution.dag)
        remove_cycles(solution.dag)

        trimmed_inst = Instance(solution.dag, inst.sources, inst.target)
        show_graph(trimmed_inst, "_after", solution.dag)

        print("Calculating ECMP solution")
        ecmp_cong, ecmp_dag = get_ecmp_DAG(solution.dag, inst.sources)
        print(f"ECMP Congestion: {ecmp_cong}")

        factor = ecmp_cong / solution.opt_congestion
        print(f"Factor: {factor}")

        show_graph(trimmed_inst, "_with_ecmp", ecmp_dag)

        min_cong = ecmp_cong
        for sub_dag in iterate_sub_DAG(solution.dag):
            ecmp_cong = get_ecmp_congestion(sub_dag, inst.sources)
            print(f"ECMP Congestion: {ecmp_cong}")
            min_cong = min(min_cong, ecmp_cong)

        print(f"\n\nBest ECMP Congestion:  {min_cong}")


if __name__ == '__main__':
    test_suite(200)


