import pickle
import os
from multiprocessing import Process

from model import *
from optimal_solver import calculate_optimal_solution
from ecmp import get_optimal_ECMP_sub_DAG, get_ALL_optimal_ECMP_sub_DAGs, check_conjectures_for_every_sub_DAG, \
    check_sequentially_for_every_sub_DAG, get_ALL_optimal_single_forwarding_DAGs
from conjectures import check_all_conjectures


def check_on_optimal_only(opt_solution: Solution, inst: Instance, index: int):
    logger = get_logger()
    ecmp_time, ecmp_solutions = time_execution(get_ALL_optimal_single_forwarding_DAGs, opt_solution.dag, inst.sources)
    if not ecmp_solutions:
        show_graph(inst, "_NO_SINGLE", opt_solution.dag)
        save_instance("examples", inst, 0)
        exit(0)
    logger.info(f"Verified conjectures on optimal sub-DAGs only\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")
    return check_all_conjectures(opt_solution, ecmp_solutions, inst, index)


def check_on_all_sub_DAGs(opt_solution: Solution, inst: Instance, index: int):
    logger = get_logger()
    ecmp_time, solution = time_execution(check_conjectures_for_every_sub_DAG, opt_solution, inst, index)
    logger.info(f"Verified all conjectures across all sub-DAGs\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

    if solution is None:
        save_instance("examples", inst, index)
        show_graph(inst, "_FAILURE", opt_solution.dag)
        print("FAIL")

    return solution is not None


def check_loads_first(opt_solution: Solution, inst: Instance, index: int):
    logger = get_logger()
    ecmp_time, solution = time_execution(check_sequentially_for_every_sub_DAG, opt_solution, inst, index)
    logger.info(f"Calculated ECMP solutions\t{f'({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

    if solution is None:
        save_instance("examples", inst, index)
        show_graph(inst, "_FAILURE", opt_solution.dag)

    return solution is not None


def verify_instance(inst: Instance, index: int, show_results=False):
    logger = get_logger()
    sol_time, opt_solution = time_execution(calculate_optimal_solution, inst)
    logger.info(f"Calculated optimal solution\t{f'({sol_time:0.2f}s)' if sol_time > 1 else ''}")

    if opt_solution is None:
        logger.info("-> Infeasible Model!")
        return True

    if show_results:
        show_graph(inst, f"graph_{index}", opt_solution.dag)

    return verification_function(opt_solution, inst, index)


def test_suite(num_tests=100, show_results=False, log_to_stdout=True):
    setup_logger(log_to_stdout)
    logger = get_logger()

    random_bytes = os.urandom(8)
    seed = int.from_bytes(random_bytes, byteorder="big")
    random.seed(seed)

    for i in range(num_tests):
        size = random.randint(4, MAX_NUM_NODES)
        prob = random.random() * 0.7 + 0.1
        logger.info("-" * 72)
        logger.info(f"Iteration {i}: Building Instance on {size} nodes with edge probability {prob:0.3f}")
        inst = build_random_DAG(size, prob)
        success = verify_instance(inst, i, show_results=show_results)
        if not success:
            logger.error("")
            print(f"!!! {multiprocessing.current_process().name} FOUND A COUNTER EXAMPLE !!!")
            exit(0)

    logger.info("")
    logger.info("=" * 40)
    logger.info(" " * 15 + "SUCCESS!!" + " " * 15)
    logger.info("=" * 40)

    print(f"{multiprocessing.current_process().name} terminated - no counterexample found!")


def inspect_instance(inst_id):
    with open(f"graph/errors_loads/ex_{inst_id}.pickle", "rb") as f:
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


def inspect(inst_id: int, folder: str):
    with open(f"graph/{folder}/ex_{inst_id}.pickle", "rb") as f:
        inst = pickle.load(f)
        opt_sol = calculate_optimal_solution(inst)
        # ecmp_sols: list[ECMP_Sol] = get_ALL_optimal_ECMP_sub_DAGs(opt_sol.dag, inst.sources)
        ecmp_sols: list[ECMP_Sol] = get_ALL_optimal_single_forwarding_DAGs(opt_sol.dag, inst.sources)

        trimmed_inst = Instance(opt_sol.dag, inst.sources, inst.target)

        # s = [
        #     (sum([len(sol.dag.neighbors[i]) for i in range(ecmp_sols[0].dag.num_nodes)]), index)
        #     for index, sol in enumerate(ecmp_sols)
        # ]
        # smallest_dag = ecmp_sols[min(s)[1]]

        show_graph(trimmed_inst, "_OPT", opt_sol.dag)
        show_graph(trimmed_inst, "_TRIMMED", ecmp_sols[0].dag)

        # verification_function(opt_sol, inst, 90000 + inst_id)

        # check_all_conjectures(opt_sol, ecmp_sols, inst, 90000 + inst_id)

        # print(all([
        #     all([a == b for (a, b) in zip(sol.loads, get_node_loads(sol.dag, inst.sources))])
        #     for sol in ecmp_sols
        # ]))


def run_multiprocessing(num_processes, num_iterations):
    procs = []
    for i in range(min(num_processes, 8)):
        proc = Process(target=test_suite, args=(num_iterations, False, False))
        procs.append(proc)
        proc.start()

    for proc in procs:
        proc.join()


""" Setup """
MAX_NUM_NODES = 6
verification_function = check_on_optimal_only


if __name__ == '__main__':
    # inspect(0, "examples")
    # test_suite(50)
    run_multiprocessing(8, 1000)
