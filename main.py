import multiprocessing
import time
import pickle
import os
import logging
from multiprocessing import Process

from model import *
from optimal_solver import calculate_optimal_solution, remove_cycles
from ecmp import get_ecmp_congestion, get_ecmp_DAG, iterate_sub_DAG


def get_logger():
    return logging.getLogger(multiprocessing.current_process().name + '_worker')


def verify_instance(inst: Instance, index: int):
    logger = get_logger()
    logger.info("Calculating optimal solution")
    solution = calculate_optimal_solution(inst)

    if solution is None:
        logger.info("-> Infeasible Model!")
        return True

    if not remove_cycles(solution.dag):
        with open(f"graph/errors/graph{index}.pickle", "wb") as f:
            pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
        with open(f"graph/errors/graph{index}.txt", "w") as f:
            f.write("Could not remove all cycles!")
        return False

    logger.info("Calculating ECMP solution")
    ecmp_cong = get_ecmp_congestion(solution.dag, inst.sources)

    if ecmp_cong < 2 * solution.opt_congestion:
        logger.info("-> Success")
        return True
    else:
        logger.info("..Iterate all sub-DAGs")
        for sub_dag in iterate_sub_DAG(solution.dag):
            ecmp_cong = get_ecmp_congestion(sub_dag, inst.sources)
            if ecmp_cong < 2 * solution.opt_congestion:
                # Success on sub-DAG
                logger.info("-> Success")
                return True

    # FAIL
    logger.error("")
    logger.error("=" * 40)
    logger.error(" " * 10 + "COUNTEREXAMPLE FOUND!!" + " " * 10)
    logger.error("=" * 40)
    os.makedirs("graph/counterexamples", exist_ok=True)
    with open(f"graph/counterexamples/graph{index}.pickle", "wb") as f:
        pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
        show_graph(inst, f"counterexamples/ex_{index}", solution.dag)

    print("=" * 40)
    print(" " * 10 + "COUNTEREXAMPLE FOUND!!" + " " * 10)
    print("=" * 40)

    return False


def setup_logger():
    fh = logging.FileHandler('graph//logs/' + multiprocessing.current_process().name + '_worker.log')
    fmt = logging.Formatter('%(asctime)-6s: %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(fmt)
    local_logger = get_logger()
    local_logger.addHandler(fh)
    local_logger.setLevel(logging.DEBUG)


def test_suite(num_tests=100):
    setup_logger()
    logger = get_logger()

    random_bytes = os.urandom(8)
    seed = int.from_bytes(random_bytes, byteorder="big")
    random.seed(seed)

    for i in range(num_tests):
        if i % (num_tests / 10) == 0:
            print(f"{multiprocessing.current_process().name} at Iteration {i}/{num_tests}")

        size = random.randint(4, 11)
        prob = random.random() * 0.8
        logger.info("-" * 25)
        logger.info(f"Iteration {i}: Building Instance on {size} nodes with edge probability {prob:0.3f}")
        inst = build_random_DAG(size, prob)
        success = verify_instance(inst, i)
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


def run_multiprocessing(num_processes, num_iterations):
    procs = []
    for i in range(min(num_processes, 8)):
        proc = Process(target=test_suite, args=(num_iterations,))
        procs.append(proc)
        proc.start()

    for proc in procs:
        proc.join()


if __name__ == '__main__':
    # test_suite(200)
    run_multiprocessing(8, 200)


