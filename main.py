import traceback
from datetime import datetime
from multiprocessing import Process

import model
from dag_solver import optimal_solution_in_DAG
from model import *
from ecmp import get_ALL_optimal_ECMP_sub_DAGs, iterate_sub_DAG, get_ecmp_DAG, get_optimal_ECMP_sub_DAG
from conjectures import MAIN_CONJECTURE, Conjecture, LOADS_CONJECTURE, ALL_CONJECTURES, error_folder, _eps
from other_ecmp import MySolver

CHECK_ON_OPTIMAL_SUB_DAGS_ONLY = 0
CHECK_ON_ALL_SUB_DAGS = 1
CHECK_USING_SAME_DAG_AS_OPTIMAL = 2
CHECK_USING_ORIGINAL_GRAPH = 3
CHECK_WITH_MY_ALGORITHM = 4
CHECKING_TYPE_NAMES = ["CHECK_ON_OPTIMAL_SUB_DAGS_ONLY", "CHECK_ON_ALL_SUB_DAGS", "CHECK_USING_SAME_DAG_AS_OPTIMAL",
                       "CHECK_USING_ORIGINAL_GRAPH", "CHECK_WITH_MY_ALGORITHM"]

ECMP_FORWARDING = "ecmp"
INTEGRAL_FORWARDING = "single_forwarding"

RESULT_SUCCESS = 0
RESULT_COUNTEREXAMPLE = 1
RESULT_INFEASIBLE = 2
RESULT_ERROR = 3


class InstanceGenerator:
    def __init__(self, max_nodes: int, arbitrary_demands=True, force_size=False):
        # if max_nodes >= 50:
        #     raise RuntimeWarning("The value for max_nodes is too large. Expect (seriously) long runtime!")

        self.max_nodes = max_nodes
        self.arbitrary_demands = arbitrary_demands
        self.force_size = force_size

        random_bytes = os.urandom(8)
        seed = int.from_bytes(random_bytes, byteorder="big")
        random.seed(seed)
        logger = get_logger()
        logger.info(f"Used Seed: {seed}")
        print(f"Used Seed: {seed}")

    def __next__(self):
        size = self.max_nodes if self.force_size else random.randint(4, self.max_nodes)
        prob = random.random() * 0.5 + 0.1
        logger = get_logger()
        logger.info(f"Building Instance on {size} nodes with edge probability {prob:0.3f}")
        inst = build_random_DAG(size, prob, self.arbitrary_demands)
        return inst

    def __iter__(self):
        return self


def sanity_check(opt_solution: Solution, ecmp_solution: ECMP_Sol):
    return ecmp_solution.congestion + _eps > opt_solution.opt_congestion


class ConjectureManager:
    conjectures_to_check = []
    checking_type = CHECK_ON_OPTIMAL_SUB_DAGS_ONLY
    forwarding_type = ECMP_FORWARDING
    exit_on_counterexample = True
    conjecture_ids = tuple()
    log_run_to_file = True

    def __init__(self,
                 checking_type=CHECK_ON_OPTIMAL_SUB_DAGS_ONLY,
                 forwarding_type=ECMP_FORWARDING,
                 exit_on_counterexample=True,
                 log_run_to_file=True
                 ):
        self.checking_type = checking_type
        self.forwarding_type = forwarding_type
        self.exit_on_counterexample = exit_on_counterexample
        self.log_run_to_file = log_run_to_file

    def register(self, *conj):
        self.conjectures_to_check.extend(conj)

        # This needs to be a tuple, so it is always serializable
        self.conjecture_ids = tuple(list(self.conjecture_ids) + [c.name for c in conj])

    def recover(self):
        """ When passing the ConjectureManager Object to multiprocessing, the mutable list argument
            conjectures_to_check is empty in the new processes. Therefore, when using multiple processes
            we must recover the actual conjecture objects from their ids """
        self.conjectures_to_check = [ALL_CONJECTURES[i] for i in self.conjecture_ids]

    def __str__(self):
        return f"-Conjectures: [{','.join(c.name for c in self.conjectures_to_check)}]\n" \
               f"-Checking Type: {CHECKING_TYPE_NAMES[self.checking_type]}\n" \
               f"-Forwarding Type: {self.forwarding_type}\n"

    def _check_all_conjectures(self, opt_solution: Solution, ecmp_sols: list[ECMP_Sol], inst: Instance, index: int):
        if not all(sanity_check(opt_solution, ecmp_sol) for ecmp_sol in ecmp_sols):
            raise Exception(f"Sanity check failed: ECMP congestion lower than OPT")

        return all(
            conj.check(opt_solution, ecmp_sols, inst, index)
            for conj in self.conjectures_to_check
        )

    def _check_conjectures_for_every_sub_DAG(self, opt_solution: Solution, inst: Instance, index: int) -> ECMP_Sol:
        solution = None
        verbose = Conjecture.VERBOSE
        Conjecture.VERBOSE = False
        for sub_dag in iterate_sub_DAG(opt_solution.dag, mode=self.forwarding_type):
            result = get_ecmp_DAG(sub_dag, inst)
            if self._check_all_conjectures(opt_solution, [result], inst, index):
                solution = result
        Conjecture.VERBOSE = verbose
        return solution

    def _check_using_original_graph(self, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, ecmp_solution = time_execution(get_ecmp_DAG, inst.dag, inst)
        logger.info(f"Calculated optimal ECMP sub-DAGs\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

        if not ecmp_solution:
            show_graph(inst, f"ex_{index}", opt_solution.dag)
            save_instance("failures", inst, index)
            logger.error("There was an error. The optimal ECMP solution could not be calculated. "
                         f"Check the failures/ex_{index} files. Exiting.")
            exit(1)

        verification_time, solution = time_execution(
            self._check_all_conjectures, opt_solution, [ecmp_solution], inst, index
        )

        if solution:
            logger.info(f"Verified all conjectures for ECMP on same DAG as optimal flow"
                        f"\t{f'  ({verification_time:0.2f}s)' if verification_time > 1 else ''}")
            return RESULT_SUCCESS

        return RESULT_INFEASIBLE

    def _check_with_my_algorithm(self, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()

        try:
            solver = MySolver()
            ecmp_time, ecmp_solution = time_execution(solver.solve, opt_solution.dag, inst, opt_solution.opt_congestion)
            logger.info(
                f"Calculated ECMP solution with my Algorithm\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

            if not ecmp_solution:
                save_instance("failures", inst, index)
                logger.error("There was an error. The ECMP solution could not be calculated. "
                             f"Check the failures/ex_{index} files. Exiting.")
                exit(1)

            verification_time, solution = time_execution(
                self._check_all_conjectures, opt_solution, [ecmp_solution], inst, index
            )

            performance_ratio = ecmp_solution.congestion / opt_solution.opt_congestion

            if performance_ratio > solver.alpha + _eps:
                save_instance_temp(inst)
                raise Exception("Alpha not equal to performance ratio")

            if solution:
                logger.info(f"Verified all conjectures for ECMP with my Algorithm"
                            f"\t{f'  ({verification_time:0.2f}s)' if verification_time > 1 else ''}")
                return RESULT_SUCCESS

        except Exception as e:
            print(e)
            traceback.print_exc()
            # show_graph(inst, f"ex_{index}", opt_solution.dag)
            save_instance("failures", inst, index)
            logger.error("There was an error. The ECMP solution could not be calculated. "
                         f"Check the failures/ex_{index} files. Exiting.")
            exit(1)

        return RESULT_COUNTEREXAMPLE

    def _check_using_same_dag(self, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, ecmp_solution = time_execution(get_ecmp_DAG, opt_solution.dag, inst)
        logger.info(f"Calculated optimal ECMP sub-DAGs\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

        if not ecmp_solution:
            show_graph(inst, f"ex_{index}", opt_solution.dag)
            save_instance("failures", inst, index)
            logger.error("There was an error. The optimal ECMP solution could not be calculated. "
                         f"Check the failures/ex_{index} files. Exiting.")
            exit(1)

        verification_time, solution = time_execution(
            self._check_all_conjectures, opt_solution, [ecmp_solution], inst, index
        )

        if solution:
            logger.info(f"Verified all conjectures for ECMP on same DAG as optimal flow"
                        f"\t{f'  ({verification_time:0.2f}s)' if verification_time > 1 else ''}")
            return RESULT_SUCCESS

        return RESULT_COUNTEREXAMPLE

    def _check_on_optimal_only(self, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, ecmp_solutions = time_execution(get_ALL_optimal_ECMP_sub_DAGs, opt_solution.dag, inst)
        logger.info(f"Calculated optimal ECMP sub-DAGs\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")

        if not ecmp_solutions:
            show_graph(inst, f"ex_{index}", opt_solution.dag)
            save_instance("failures", inst, index)
            logger.error("There was an error. The optimal ECMP solution could not be calculated. "
                         f"Check the failures/ex_{index} files. Exiting.")
            exit(1)

        verification_time, solution = time_execution(
            self._check_all_conjectures, opt_solution, ecmp_solutions, inst, index
        )

        if solution:
            logger.info(f"Verified all conjectures for optimal ECMP DAGs"
                        f"\t{f'  ({verification_time:0.2f}s)' if verification_time > 1 else ''}")
            return RESULT_SUCCESS

        return RESULT_COUNTEREXAMPLE

    def _check_on_all_sub_DAGs(self, opt_solution: Solution, inst: Instance, index: int):
        logger = get_logger()
        ecmp_time, solution = time_execution(self._check_conjectures_for_every_sub_DAG, opt_solution, inst, index)

        if solution is not None:
            logger.info(f"Verified all conjectures across all sub-DAGs"
                        f"\t{f'  ({ecmp_time:0.2f}s)' if ecmp_time > 1 else ''}")
            return RESULT_SUCCESS

        return RESULT_COUNTEREXAMPLE

    def verify_instance(self, inst: Instance, index: int, show_results=False, opt_sol: Solution=None):
        logger = get_logger()
        if not self.conjectures_to_check:
            print("No Conjectures to check")
            logger.error("NO CONJECTURES TO CHECK!")
            return RESULT_ERROR

        if opt_sol is not None:
            opt_solution = opt_sol
        else:
            sol_time, opt_solution = time_execution(optimal_solution_in_DAG, inst)
            logger.info(f"Calculated optimal solution\t{f'({sol_time:0.2f}s)' if sol_time > 1 else ''}")

        if opt_solution is None:
            logger.info("-> Infeasible Instance!")
            return RESULT_INFEASIBLE

        if show_results:
            show_graph(inst, f"output_{index}", opt_solution.dag)

        if self.checking_type == CHECK_ON_OPTIMAL_SUB_DAGS_ONLY:
            return self._check_on_optimal_only(opt_solution, inst, index)
        elif self.checking_type == CHECK_ON_ALL_SUB_DAGS:
            return self._check_on_all_sub_DAGs(opt_solution, inst, index)
        elif self.checking_type == CHECK_USING_SAME_DAG_AS_OPTIMAL:
            return self._check_using_same_dag(opt_solution, inst, index)
        elif self.checking_type == CHECK_USING_ORIGINAL_GRAPH:
            return self._check_using_original_graph(opt_solution, inst, index)
        elif self.checking_type == CHECK_WITH_MY_ALGORITHM:
            return self._check_with_my_algorithm(opt_solution, inst, index)

        raise RuntimeError("Invalid value for verification_type.")

    def write_run_to_log(self, success, max_num_nodes, start_time, instances_checked):
        if self.log_run_to_file and instances_checked > 0:
            time_elapsed = time.time() - start_time
            with open("output/runs.log", "a") as f:
                f.write("-" * 17 + " Completed Run " + "-" * 17 + f"\n{datetime.now()}  ({time_elapsed:0.2f}s)\n")
                f.write(f"=== Result: {'SUCCESS' if success else 'COUNTEREXAMPLE FOUND'}! ===\n")
                f.write(str(self))
                if success:
                    f.write(f"Verified {instances_checked} feasible instances.\n")
                f.write(f"Largest instance had {max_num_nodes} nodes.\n")


def run_single_test_suite(generator: InstanceGenerator,
                          cm: ConjectureManager,
                          num_iterations=100,
                          show_results=False,
                          log_to_stdout=True,
                          multiprocessing_results=None
                          ):
    setup_logger(log_to_stdout)
    logger = get_logger()

    cm.recover()  # Only necessary when using multiprocessing to recover conjecture objects
    logger.info(cm)

    run_started = time.time()
    instances_checked = 0
    max_num_nodes = 0
    for i in range(num_iterations):
        logger.info("-" * 72)
        logger.info(f"Begin Iteration {i + 1}:")
        inst = next(generator)

        try:
            result = cm.verify_instance(inst, i, show_results=show_results)
        except:
            result = RESULT_ERROR

        if result == RESULT_SUCCESS:
            instances_checked += 1
            max_num_nodes = max(max_num_nodes, inst.dag.num_nodes)
        elif result == RESULT_COUNTEREXAMPLE:
            logger.error("=" * 50)
            logger.error(f"  !!! {multiprocessing.current_process().name} FOUND A COUNTER EXAMPLE !!!")
            logger.error("=" * 50)
            logger.info(f"Check errors folder, instance {i}")
            max_num_nodes = max(max_num_nodes, inst.dag.num_nodes)

            cm.write_run_to_log(False, max_num_nodes, run_started, 0)
            multiprocessing_results.put(False)
            return
            # exit(0)
        elif result == RESULT_ERROR:
            if multiprocessing_results is not None:
                multiprocessing_results.put(False)
            return
            # exit(1)

        if i % 500 == 0 and i > 0:
            print(f" - {multiprocessing.current_process().name} at iteration {i} / {num_iterations}\n"
                  f" - - Elapsed Time: {time.time() - run_started:0.2f}s\n"
                  f" - - Feasible Instances verified: {instances_checked}")

    logger.info("")
    logger.info("=" * 40)
    logger.info(" " * 15 + "SUCCESS!!" + " " * 15)
    logger.info("=" * 40)

    cm.write_run_to_log(True, max_num_nodes, run_started, instances_checked)

    print(f"{multiprocessing.current_process().name} terminated - no counterexample found!\t"
          f"({instances_checked} feasible instances checked)")

    if multiprocessing_results is not None:
        multiprocessing_results.put(True)


def check_single_instance(inst: Instance, cm: ConjectureManager, show_results=False, log_to_stdout=True, opt_sol: Solution = None):
    setup_logger(log_to_stdout)
    logger = get_logger()

    logger.info("-" * 72)
    id_ = random.randint(100, 10000)
    logger.info(f"Checking Single Instance: (ID: {id_})")
    result = cm.verify_instance(inst, 1, show_results=show_results, opt_sol=opt_sol)
    if result == RESULT_COUNTEREXAMPLE:
        logger.error("=" * 50)
        logger.error(f"  !!! {multiprocessing.current_process().name} FOUND A COUNTER EXAMPLE !!!")
        logger.error("=" * 50)
        logger.info(f"Check errors folder, instance {id_}")
        return False

    return True


def run_multiprocessing_suite(generator: InstanceGenerator, cm: ConjectureManager, num_processes, num_iterations):
    procs = []
    results = multiprocessing.Queue()
    for i in range(min(num_processes, 8)):
        proc = Process(target=run_single_test_suite, args=(generator, cm, num_iterations, False, False, results))
        procs.append(proc)
        proc.start()

    for proc in procs:
        proc.join()

    success = True
    count = 0
    for _ in range(num_processes):
        item = results.get()
        if item is None:
            break
        success &= item
        count += 1

    if count < num_processes:
        success = False

    if success:
        print("\n" + "=" * 15 + "  !! SUCCESS !!  " + "=" * 15)
    else:
        print("=" * 50)
        print(f"     !!! ERROR or COUNTER EXAMPLE FOUND !!!")
        print("=" * 50)

    exit(0)


def inspect_instance(inst_id: int, folder: str):
    # random.seed(9115232)  # errors_congestion_old 448
    random.seed(1194660667223394089)  # 328
    random.seed(11108484738710341480)  # 3126
    random.seed(5950291163594365085)  # failures 286

    with open(f"output/{folder}/ex_{inst_id}.pickle", "rb") as f:
        inst = pickle.load(f)

        opt_sol = optimal_solution_in_DAG(inst)
        print(f"Optimal Congestion: {opt_sol.opt_congestion:0.4f}")
        trimmed_inst = Instance(opt_sol.dag, inst.sources, inst.target, inst.demands)
        show_graph(trimmed_inst, "_trimmed", opt_sol.dag)

        sv = MySolver()
        ecmp_sol = sv.solve(opt_sol.dag, inst, opt_sol.opt_congestion)

        if ecmp_sol.congestion < opt_sol.opt_congestion - 0.0000001:
            raise Exception("Something went wrong here!")

        show_graph(trimmed_inst, "_ecmp", ecmp_sol.dag)
        print(f"ECMP Congestion: {ecmp_sol.congestion}")

        performance_ratio = ecmp_sol.congestion / opt_sol.opt_congestion

        print(f"Performance Ratio:  {performance_ratio:0.3f}")

        if performance_ratio > sv.alpha + _eps:
            raise Exception("Alpha not equal to performance ratio")

        if ecmp_sol.congestion > 2 * opt_sol.opt_congestion:
            raise Exception("Conjecture violated!")

        # trimmed_inst = Instance(opt_sol.dag, inst.sources, inst.target, inst.demands)
        # show_graph(trimmed_inst, "_after", opt_sol.dag)
        #
        # print("Calculating ECMP opt_sol")
        # ecmp_sols: list[ECMP_Sol] = [ get_ecmp_DAG(opt_sol.dag, inst)]
        # print(f"ECMP Congestion: {ecmp_sols[0].congestion}")
        #
        # show_graph(trimmed_inst, "_ecmp", ecmp_sols[0].dag)
        #
        # factor = ecmp_sols[0].congestion / opt_sol.opt_congestion
        # print(f"Performance Ratio: {factor}")
        #
        # print(f"1 + Max Degree Ratio = {1 + calculate_max_degree_ratio(ecmp_sols[0].dag)}")
        #
        # show_graph(trimmed_inst, "_ecmp", ecmp_sols[0].dag)


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
    # with open(f"output/new/ex_1002.pickle", "rb") as f:
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


def check_test_cases(cm):
    model.TESTCASE_RUNNING = True
    failure_directory = "output/failures"
    from_failure_ids = sorted(map(lambda file: int(file.split("_")[1].split(".")[0]), os.listdir(failure_directory)))
    from_failure_cases = list(map(lambda x: (x, f"ex_{x}", f"{failure_directory}/ex_{x}.pickle", ""), from_failure_ids))

    large_cases_dir = "output/large_instances"
    large_cases_ids = map(lambda file: int(file.split("_")[1].split(".")[0]), os.listdir(large_cases_dir))
    large_cases = list(map(lambda x: (x, f"inst_{x}_L", f"{large_cases_dir}/inst_{x}.pickle", f"{large_cases_dir}/sol_{x}.pickle"), large_cases_ids))

    test_cases = from_failure_cases + large_cases

    for inst_id, inst_name, path, solpath in test_cases:
        inst = None
        sol = None
        try:
            with open(path, "rb") as f:
                inst = pickle.load(f)

            if solpath:
                with open(solpath, "rb") as f:
                    sol = pickle.load(f)
        except:
            continue

        print(f"-- Checking Test {inst_name}:  \t", end="")

        if not check_single_instance(inst, cm, False, False, opt_sol=sol):
            exit(1)

        print("PASSED! -- ")

    logger = get_logger()
    logger.info("")
    logger.info("=" * 40)
    logger.info(" " * 15 + "SUCCESS!!" + " " * 15)
    logger.info("=" * 40)

    model.TESTCASE_RUNNING = False


def custom_instance2():
    neighbors = [
        [], [0], [0], [0], [0], [0], [1, 2, 3, 4, 5]
    ]

    parents = make_parents(neighbors)
    dag = DAG(len(neighbors), neighbors, parents)
    sources = [6]
    demands = [0, 0, 0, 0, 0, 0, 3]
    # sources = list(range(1, len(neighbors) + 1))
    # demands = [0] + [1] * (len(neighbors) - 1)
    inst = Instance(dag, sources, 0, demands)
    save_instance("failures", inst, 7012)
    show_graph(inst, "_tricky")


def create_large_instances(num):
    ig = InstanceGenerator(1000, False, force_size=True)
    successes = 0
    iterations = 0
    print(f"- - Begin instance 1 - -")
    while successes < num and iterations < 4 * num:
        iterations += 1
        inst = next(ig)
        sol_time, opt_solution = time_execution(optimal_solution_in_DAG, inst)
        print(f" Calculated optimal solution\t{f'({sol_time:0.2f}s)' if sol_time > 1 else ''}")

        if opt_solution is None:
            print("  -> Infeasible")
            continue

        inst_file = f"output/large_instances/inst_{successes}.pickle"
        with open(inst_file, "wb") as f:
            pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)

        sol_file = f"output/large_instances/sol_{successes}.pickle"
        with open(sol_file, "wb") as f:
            pickle.dump(opt_solution, f, pickle.HIGHEST_PROTOCOL)

        successes += 1
        print(" == SAVED ==\n")
        print(f"- - Begin instance {successes+1} - -")


if __name__ == '__main__':
    cm = ConjectureManager(CHECK_WITH_MY_ALGORITHM, ECMP_FORWARDING, log_run_to_file=False)
    cm.register(MAIN_CONJECTURE)

    # create_large_instances(10)

    check_test_cases(cm)
    # inspect_instance(570, "failures")

    # inspect_instance(1, error_folder(MAIN_CONJECTURE))
    # inspect_instance(570, "tricky")
    # inspect_instance(1, "tmp")
    # run_single_test_suite(ig, cm, 5000)

    # ig = InstanceGenerator(200, False)
    # run_multiprocessing_suite(ig, cm, 8, 50000)
