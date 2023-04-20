from datetime import datetime
from multiprocessing import Process

from dag_solver import optimal_solution_in_DAG
from model import *
# from optimal_solver import calculate_optimal_solution
from ecmp import get_ALL_optimal_ECMP_sub_DAGs, iterate_sub_DAG, get_ecmp_DAG, get_optimal_ECMP_sub_DAG
from conjectures import MAIN_CONJECTURE, LOADS_CONJECTURE, Conjecture, DEGREE_RATIO_LEMMA

CHECK_ON_OPTIMAL_SUB_DAGS_ONLY = 0
CHECK_ON_ALL_SUB_DAGS = 1
CHECK_USING_SAME_DAG_AS_OPTIMAL = 2
CHECK_USING_ORIGINAL_GRAPH = 3
CHECKING_TYPE_NAMES = ["CHECK_ON_OPTIMAL_SUB_DAGS_ONLY", "CHECK_ON_ALL_SUB_DAGS", "CHECK_USING_SAME_DAG_AS_OPTIMAL", "CHECK_USING_ORIGINAL_GRAPH"]

ECMP_FORWARDING = "ecmp"
INTEGRAL_FORWARDING = "single_forwarding"

RESULT_SUCCESS = 0
RESULT_COUNTEREXAMPLE = 1
RESULT_INFEASIBLE = 2
RESULT_ERROR = 3

class InstanceGenerator:
    def __init__(self, max_nodes: int, arbitrary_demands=True):
        if max_nodes >= 50:
            raise RuntimeWarning("The value for max_nodes is too large. Expect (seriously) long runtime!")

        self.max_nodes = max_nodes
        self.arbitrary_demands = arbitrary_demands

        random_bytes = os.urandom(8)
        seed = int.from_bytes(random_bytes, byteorder="big")
        random.seed(seed)

    def __next__(self):
        size = random.randint(4, self.max_nodes)
        prob = random.random() * 0.7 + 0.1
        logger = get_logger()
        logger.info(f"Building Instance on {size} nodes with edge probability {prob:0.3f}")
        inst = build_random_DAG(size, prob, self.arbitrary_demands)
        return inst

    def __iter__(self):
        return self


class ConjectureManager:
    conjectures_to_check = []
    checking_type = CHECK_ON_OPTIMAL_SUB_DAGS_ONLY
    forwarding_type = ECMP_FORWARDING
    exit_on_counterexample = True

    @classmethod
    def setup(cls,
              checking_type=CHECK_ON_OPTIMAL_SUB_DAGS_ONLY,
              forwarding_type=ECMP_FORWARDING,
              exit_on_counterexample=True
              ):
        cls.checking_type = checking_type
        cls.forwarding_type = forwarding_type
        cls.exit_on_counterexample = exit_on_counterexample

    @classmethod
    def register(cls, *conj):
        cls.conjectures_to_check.extend(conj)

    @classmethod
    def get_settings(cls):
        return f"-Conjectures: [{','.join(c.name for c in cls.conjectures_to_check)}]\n"\
               f"-Checking Type: {CHECKING_TYPE_NAMES[cls.checking_type]}\n" \
               f"-Forwarding Type: {cls.forwarding_type}\n"

    @classmethod
    def _check_all_conjectures(cls, opt_solution: Solution, ecmp_solutions: list[ECMP_Sol], inst: Instance, index: int):
        return all(
            conj.check(opt_solution, ecmp_solutions, inst, index)
            for conj in cls.conjectures_to_check
        )

    @classmethod
    def _check_conjectures_for_every_sub_DAG(cls, opt_solution: Solution, inst: Instance, index: int) -> ECMP_Sol:
        solution = None
        verbose = Conjecture.VERBOSE
        Conjecture.VERBOSE = False
        for sub_dag in iterate_sub_DAG(opt_solution.dag, mode=cls.forwarding_type):
            result = get_ecmp_DAG(sub_dag, inst)
            if cls._check_all_conjectures(opt_solution, [result], inst, index):
                solution = result
        Conjecture.VERBOSE = verbose
        return solution


    @classmethod
    def _check_using_original_graph(cls, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, ecmp_solution = time_execution(get_ecmp_DAG, inst.dag, inst)
        logger.info(f"Calculated optimal ECMP sub-DAGs\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

        if not ecmp_solution:
            show_graph(inst, f"ex_{index}", opt_solution.dag)
            save_instance("failures", inst, index)
            logger.error("There was an error. The optimal ECMP solution could be calculated. "
                         f"Check the failures/ex_{index} files. Exiting.")
            exit(1)

        verification_time, solution = time_execution(
            cls._check_all_conjectures, opt_solution, [ecmp_solution], inst, index
        )

        if solution:
            logger.info(f"Verified all conjectures for ECMP on same DAG as optimal flow"
                        f"\t{f'  ({verification_time:0.2f}s)' if verification_time > 1 else ''}")
            return RESULT_SUCCESS

        return RESULT_INFEASIBLE


    @classmethod
    def _check_using_same_dag(cls, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, ecmp_solution = time_execution(get_ecmp_DAG, opt_solution.dag, inst)
        logger.info(f"Calculated optimal ECMP sub-DAGs\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

        if not ecmp_solution:
            show_graph(inst, f"ex_{index}", opt_solution.dag)
            save_instance("failures", inst, index)
            logger.error("There was an error. The optimal ECMP solution could be calculated. "
                         f"Check the failures/ex_{index} files. Exiting.")
            exit(1)

        verification_time, solution = time_execution(
            cls._check_all_conjectures, opt_solution, [ecmp_solution], inst, index
        )

        if solution:
            logger.info(f"Verified all conjectures for ECMP on same DAG as optimal flow"
                        f"\t{f'  ({verification_time:0.2f}s)' if verification_time > 1 else ''}")
            return RESULT_SUCCESS

        return RESULT_INFEASIBLE

    @classmethod
    def _check_on_optimal_only(cls, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, ecmp_solutions = time_execution(get_ALL_optimal_ECMP_sub_DAGs, opt_solution.dag, inst)
        logger.info(f"Calculated optimal ECMP sub-DAGs\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

        if not ecmp_solutions:
            show_graph(inst, f"ex_{index}", opt_solution.dag)
            save_instance("failures", inst, index)
            logger.error("There was an error. The optimal ECMP solution could be calculated. "
                         f"Check the failures/ex_{index} files. Exiting.")
            exit(1)

        verification_time, solution = time_execution(
            cls._check_all_conjectures, opt_solution, ecmp_solutions, inst, index
        )

        if solution:
            logger.info(f"Verified all conjectures for optimal ECMP DAGs"
                        f"\t{f'  ({verification_time:0.2f}s)' if verification_time > 1 else ''}")
            return RESULT_SUCCESS

        return RESULT_COUNTEREXAMPLE

    @classmethod
    def _check_on_all_sub_DAGs(cls, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, solution = time_execution(cls._check_conjectures_for_every_sub_DAG, opt_solution, inst, index)

        if solution is not None:
            logger.info(f"Verified all conjectures across all sub-DAGs"
                        f"\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")
            return RESULT_SUCCESS

        return RESULT_COUNTEREXAMPLE

    @classmethod
    def verify_instance(cls, inst: Instance, index: int, show_results=False):
        logger = get_logger()
        sol_time, opt_solution = time_execution(optimal_solution_in_DAG, inst)
        logger.info(f"Calculated optimal solution\t{f'({sol_time:0.2f}s)' if sol_time > 1 else ''}")

        if opt_solution is None:
            logger.info("-> Infeasible Instance!")
            return RESULT_INFEASIBLE

        if show_results:
            show_graph(inst, f"output_{index}", opt_solution.dag)

        if cls.checking_type == CHECK_ON_OPTIMAL_SUB_DAGS_ONLY:
            return cls._check_on_optimal_only(opt_solution, inst, index)
        elif cls.checking_type == CHECK_ON_ALL_SUB_DAGS:
            return cls._check_on_all_sub_DAGs(opt_solution, inst, index)
        elif cls.checking_type == CHECK_USING_SAME_DAG_AS_OPTIMAL:
            return cls._check_using_same_dag(opt_solution, inst, index)
        elif cls.checking_type == CHECK_USING_ORIGINAL_GRAPH:
            return cls._check_using_original_graph(opt_solution, inst, index)

        raise RuntimeError("Invalid value for verification_type.")


def write_run_to_log(success, start_time, instances_checked):
    time_elapsed = time.time() - start_time
    with open("output/runs.log", "a") as f:
        f.write("-" * 17 + " Completed Run " + "-" * 17 + f"\n{datetime.now()}  (({time_elapsed:0.2f}s))\n")
        f.write(ConjectureManager.get_settings())
        if success:
            f.write(f"Verified in {instances_checked} feasible instances.\n")
        else:
            f.write(f"COUNTEREXAMPLE found!\n")


def run_single_test_suite(generator: InstanceGenerator, num_iterations=100, show_results=False, log_to_stdout=True):
    setup_logger(log_to_stdout)
    logger = get_logger()

    run_started = time.time()

    instances_checked = 0
    for i in range(num_iterations):
        logger.info("-" * 72)
        logger.info(f"Begin Iteration {i + 1}:")
        inst = next(generator)
        result = ConjectureManager.verify_instance(inst, i, show_results=show_results)
        if result == RESULT_SUCCESS:
            instances_checked += 1
        elif result == RESULT_COUNTEREXAMPLE:
            logger.error("=" * 50)
            logger.error(f"  !!! {multiprocessing.current_process().name} FOUND A COUNTER EXAMPLE !!!")
            logger.error("=" * 50)
            logger.info(f"Check errors folder, instance {i}")

            write_run_to_log(False, run_started, 0)
            exit(0)

    logger.info("")
    logger.info("=" * 40)
    logger.info(" " * 15 + "SUCCESS!!" + " " * 15)
    logger.info("=" * 40)

    write_run_to_log(True, run_started, instances_checked)

    print(f"{multiprocessing.current_process().name} terminated - no counterexample found!")


def check_single_instance(inst: Instance, show_results=False, log_to_stdout=True):
    setup_logger(log_to_stdout)
    logger = get_logger()

    logger.info("-" * 72)
    id_ = random.randint(100, 10000)
    logger.info(f"Checking Single Instance: (ID: {id_})")
    success = ConjectureManager.verify_instance(inst, 1, show_results=show_results)
    if not success:
        logger.error("=" * 50)
        logger.error(f"  !!! {multiprocessing.current_process().name} FOUND A COUNTER EXAMPLE !!!")
        logger.error("=" * 50)
        logger.info(f"Check errors folder, instance {id_}")
        exit(0)

    logger.info("")
    logger.info("=" * 40)
    logger.info(" " * 15 + "SUCCESS!!" + " " * 15)
    logger.info("=" * 40)

    print(f"{multiprocessing.current_process().name} terminated - no counterexample found!")


def run_multiprocessing_suite(generator: InstanceGenerator, num_processes, num_iterations):
    procs = []
    for i in range(min(num_processes, 8)):
        proc = Process(target=run_single_test_suite, args=(generator, num_iterations, False, False))
        procs.append(proc)
        proc.start()

    for proc in procs:
        proc.join()


def inspect_instance(inst_id: int, folder: str):
    with open(f"output/{folder}/ex_{inst_id}.pickle", "rb") as f:
        inst = pickle.load(f)

        opt_sol = optimal_solution_in_DAG(inst)
        print(f"Optimal Congestion: {opt_sol.opt_congestion:0.4f}")
        show_graph(inst, "_before", opt_sol.dag)

        trimmed_inst = Instance(opt_sol.dag, inst.sources, inst.target, inst.demands)
        show_graph(trimmed_inst, "_after", opt_sol.dag)

        print("Calculating ECMP opt_sol")
        ecmp_sols: list[ECMP_Sol] = [ get_ecmp_DAG(opt_sol.dag, inst)]
        print(f"ECMP Congestion: {ecmp_sols[0].congestion}")

        show_graph(trimmed_inst, "_ecmp", ecmp_sols[0].dag)

        factor = ecmp_sols[0].congestion / opt_sol.opt_congestion
        print(f"Performance Ratio: {factor}")

        print(f"1 + Max Degree Ratio = {1 + calculate_max_degree_ratio(ecmp_sols[0].dag)}")

        show_graph(trimmed_inst, "_ecmp", ecmp_sols[0].dag)


def custom_instance():
    num_nodes = 5
    sources = [1, 2, 3, 4]
    demands = [0.12, 2.07, 1.75, 0.76]

    edges = {
        0: [1, 4],
        1: [0, 2, 3],
        2: [1, 3],
        3: [1, 2, 4],
        4: [0, 3]
    }

    inst = Instance(DAG(num_nodes, edges), sources, 0, demands)

    opt_sol = optimal_solution_in_DAG(inst)
    print(f"Optimal Congestion: {opt_sol.opt_congestion:0.4f}")
    show_graph(inst, "_opt", opt_sol.dag)

    best_ecmp = get_optimal_ECMP_sub_DAG(opt_sol.dag, inst)
    print(f"Best ECMP Congestion: {best_ecmp.congestion:0.4f}")
    show_graph(inst, "_ecmp", best_ecmp.dag)

    return inst

def new_test():
    inst = build_random_DAG(50, 0.6, False)

    # save_instance("new", inst, 2)
    # with open(f"output/new/ex_2.pickle", "rb") as f:
    #     inst = pickle.load(f)

    show_graph(inst, "_new_dag")

    opt_sol = optimal_solution_in_DAG(inst)
    if opt_sol:
        print(f"Optimal Congestion: {opt_sol.opt_congestion:0.4f}")
        show_graph(inst, "_new_dag_sol", opt_sol.dag)

        best_ecmp = get_optimal_ECMP_sub_DAG(opt_sol.dag, inst)
        print(f"Best ECMP Congestion: {best_ecmp.congestion:0.4f}")
        show_graph(inst, "_new_dag_ecmp", best_ecmp.dag)
    else:
        print("Infeasible Model")


if __name__ == '__main__':
    ConjectureManager.setup(CHECK_ON_OPTIMAL_SUB_DAGS_ONLY, ECMP_FORWARDING)
    ConjectureManager.register(MAIN_CONJECTURE)
    # ConjectureManager.register(DEGREE_RATIO_LEMMA)

    ig = InstanceGenerator(30, False)
    # inspect_instance(149, "errors_congestion")
    run_single_test_suite(ig, 1000)
    # run_multiprocessing_suite(ig, 8, 10000)

