from multiprocessing import Process

from model import *
from optimal_solver import calculate_optimal_solution
from ecmp import get_ALL_optimal_ECMP_sub_DAGs, get_ALL_optimal_single_forwarding_DAGs, get_optimal_ECMP_sub_DAG, \
    iterate_sub_DAG, get_ecmp_DAG
from conjectures import MAIN_CONJECTURE, LOADS_CONJECTURE, Conjecture

CHECK_ON_OPTIMAL_SUB_DAGS_ONLY = 0
CHECK_ON_ALL_SUB_DAGS = 1

ECMP_FORWARDING = "ecmp"
INTEGRAL_FORWARDING = "single_forwarding"


class InstanceGenerator:
    def __init__(self, max_nodes: int, arbitrary_demands=True):
        if max_nodes > 20:
            raise RuntimeWarning("The value for max_nodes is too large. Expect long runtime!")

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
            return True

        return False

    @classmethod
    def _check_on_all_sub_DAGs(cls, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, solution = time_execution(cls._check_conjectures_for_every_sub_DAG, opt_solution, inst, index)

        if solution is not None:
            logger.info(f"Verified all conjectures across all sub-DAGs"
                        f"\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")
            return True

        return False

    @classmethod
    def verify_instance(cls, inst: Instance, index: int, show_results=False):
        logger = get_logger()
        sol_time, opt_solution = time_execution(calculate_optimal_solution, inst)
        logger.info(f"Calculated optimal solution\t{f'({sol_time:0.2f}s)' if sol_time > 1 else ''}")

        if opt_solution is None:
            logger.info("-> Infeasible Instance!")
            return True

        if show_results:
            show_graph(inst, f"output_{index}", opt_solution.dag)

        if cls.checking_type == CHECK_ON_OPTIMAL_SUB_DAGS_ONLY:
            return cls._check_on_optimal_only(opt_solution, inst, index)
        elif cls.checking_type == CHECK_ON_ALL_SUB_DAGS:
            return cls._check_on_all_sub_DAGs(opt_solution, inst, index)

        raise RuntimeError("Invalid value for verification_type.")


def run_single_test_suite(generator: InstanceGenerator, num_iterations=100, show_results=False, log_to_stdout=True):
    setup_logger(log_to_stdout)
    logger = get_logger()

    for i in range(num_iterations):
        logger.info("-" * 72)
        logger.info(f"Begin Iteration {i + 1}:")
        inst = next(generator)
        success = ConjectureManager.verify_instance(inst, i, show_results=show_results)
        if not success:
            logger.error("=" * 50)
            logger.error(f"  !!! {multiprocessing.current_process().name} FOUND A COUNTER EXAMPLE !!!")
            logger.error("=" * 50)
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

        opt_sol = calculate_optimal_solution(inst)
        print(f"Optimal Congestion: {opt_sol.opt_congestion:0.4f}")
        show_graph(inst, "_before", opt_sol.dag)

        trimmed_inst = Instance(opt_sol.dag, inst.sources, inst.target, inst.demands)
        show_graph(trimmed_inst, "_after", opt_sol.dag)

        print("Calculating ECMP opt_sol")
        ecmp_sols: list[ECMP_Sol] = get_ALL_optimal_ECMP_sub_DAGs(opt_sol.dag, inst)
        print(f"ECMP Congestion: {ecmp_sols[0].congestion}")

        factor = ecmp_sols[0].congestion / opt_sol.opt_congestion
        print(f"Factor: {factor}")

        show_graph(trimmed_inst, "_ecmp", ecmp_sols[0].dag)


if __name__ == '__main__':
    # ig = InstanceGenerator(12, True)
    #
    # ConjectureManager.setup(CHECK_ON_ALL_SUB_DAGS)
    # ConjectureManager.register(MAIN_CONJECTURE, LOADS_CONJECTURE, LOADS_CONJECTURE.implies(MAIN_CONJECTURE))

    inspect_instance(1, "examples")
    # run_single_test_suite(ig, 200)
    # run_multiprocessing_suite(ig, 8, 10000)
