import pickle
import os
from multiprocessing import Process

from model import *
from optimal_solver import calculate_optimal_solution
from ecmp import get_optimal_ECMP_sub_DAG
from conjectures import check_all_conjectures


def verify_instance(inst: Instance, index: int, show_results=False):
    logger = get_logger()
    logger.info("Calculating optimal solution")
    solution = calculate_optimal_solution(inst)

    if solution is None:
        logger.info("-> Infeasible Model!")
        return True

    if show_results:
        show_graph(inst, f"graph_{index}", solution.dag)

    logger.info("Calculating ECMP solution")
    ecmp_sol = get_optimal_ECMP_sub_DAG(solution.dag, inst.sources)

    return check_all_conjectures(solution, ecmp_sol, inst, index)


def test_suite(num_tests=100, show_results=False, log_to_stdout=True):
    setup_logger(log_to_stdout)
    logger = get_logger()

    random_bytes = os.urandom(8)
    seed = int.from_bytes(random_bytes, byteorder="big")
    random.seed(seed)

    for i in range(num_tests):
        size = random.randint(4, MAX_NUM_NODES)
        prob = random.random() * 0.8
        logger.info("-" * 72)
        logger.info(f"Iteration {i}: Building Instance on {size} nodes with edge probability {prob:0.3f}")
        inst = build_random_DAG(size, prob)
        success = verify_instance(inst, i, show_results=show_results)
        if not success:
            logger.error("")
            exit(0)

    logger.info("")
    logger.info("=" * 40)
    logger.info(" " * 15 + "SUCCESS!!" + " " * 15)
    logger.info("=" * 40)

    print(f"{multiprocessing.current_process().name} terminated - no counterexample found!")


def inspect_instance(id):
    with open(f"graph/graph{id}.pickle", "rb") as f:
        inst = pickle.load(f)

        solution = calculate_optimal_solution(inst)
        print(f"Optimal Congestion: {solution.opt_congestion:0.4f}")
        show_graph(inst, "_before", solution.dag)

        trimmed_inst = Instance(solution.dag, inst.sources, inst.target)
        show_graph(trimmed_inst, "_after", solution.dag)

        optimal_loads = get_node_loads(solution.dag, inst.sources)

        print("Calculating ECMP solution")
        ecmp_sol: ECMP_Sol = get_optimal_ECMP_sub_DAG(solution.dag, inst.sources)
        print(f"ECMP Congestion: {ecmp_sol.congestion}")

        factor = ecmp_sol.congestion / solution.opt_congestion
        print(f"Factor: {factor}")

        show_graph(trimmed_inst, "_with_ecmp", ecmp_sol.dag)

        compare_node_loads(ecmp_sol.loads, optimal_loads, inst.sources)


def run_multiprocessing(num_processes, num_iterations):
    procs = []
    for i in range(min(num_processes, 8)):
        proc = Process(target=test_suite, args=(num_iterations, False, False))
        procs.append(proc)
        proc.start()

    for proc in procs:
        proc.join()


MAX_NUM_NODES = 10


if __name__ == '__main__':
    # inspect_instance(332)
    # test_suite(50)
    run_multiprocessing(4, 200)


