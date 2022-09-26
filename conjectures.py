from model import *

import pickle
import os


class Conjecture:
    def __init__(self, name, verification_function, failure_message):
        self.name = name
        self.verification_function = verification_function
        self.failure_message = failure_message

    def check(self, opt_solution: Solution, ecmp_solutions: list[ECMP_Sol], inst: Instance, index: int):
        success = self.verification_function(opt_solution, ecmp_solutions, inst)
        if not success:
            # FAIL
            self.print_failure(opt_solution, ecmp_solutions, inst, index)
            return False

        return True

    def print_failure(self, opt_solution: Solution, ecmp_solutions: list[ECMP_Sol], inst: Instance, index: int):
        logger = get_logger()
        logger.error("")
        logger.error("=" * 40)
        logger.error(" " * 10 + "COUNTEREXAMPLE FOUND!!" + " " * 10)
        logger.error("=" * 40)
        os.makedirs(f"graph/errors_{self.name}", exist_ok=True)
        with open(f"graph/errors_{self.name}/ex_{index}.pickle", "wb") as f:
            pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
            show_graph(inst, f"errors_{self.name}/ex_{index}", opt_solution.dag)

        with open(f"graph/errors_{self.name}/ex_{index}_fail.txt", "w") as f:
            f.write(self.failure_message(opt_solution, ecmp_solutions, inst))


MAIN_CONJECTURE = Conjecture(
    "congestion",
    lambda opt_sol, ecmp_sols, inst: ecmp_sols[0].congestion < 2 * opt_sol.opt_congestion,
    lambda opt_sol, ecmp_sols, inst:
    f"Optimal Congestion: {opt_sol.opt_congestion}\nECMP Congestion: {ecmp_sols.congestion}\n"
)


def check_loads(opt_solution: Solution, ecmp_solutions: list[ECMP_Sol], instance: Instance):
    optimal_loads = get_node_loads(opt_solution.dag, instance.sources)
    return any([
        compare_node_loads(ecmp_sol.loads, optimal_loads, instance.sources) is None
        for ecmp_sol in ecmp_solutions
    ])


def loads_failed(opt_solution: Solution, ecmp_solutions: [ECMP_Sol], instance: Instance):
    optimal_loads = get_node_loads(opt_solution.dag, instance.sources)

    output = ""
    for i, ecmp_sol in enumerate(ecmp_solutions):
        trimmed_inst = Instance(opt_solution.dag, instance.sources, instance.target)
        show_graph(trimmed_inst, f"_THIS_{i}", ecmp_sol.dag)
        failed_node = compare_node_loads(ecmp_sol.loads, optimal_loads, instance.sources)
        output += f"Error in sub-DAG with index {i}:\n" \
                  f"Load at node {failed_node} too high:\n" \
                  f"opt. load: {optimal_loads[failed_node]}\n" \
                  f"ecmp load: {ecmp_sol.loads[failed_node]}\n\n" \
                  f"All opt. loads: {optimal_loads}\n" \
                  f"All ecmp loads: {ecmp_sol.loads}\n" \
                  + "-" * 40 + "\n"
    return output


LOADS_CONJECTURE = Conjecture(
    "loads",
    check_loads,
    loads_failed
)


def check_same_edges(opt_solution: Solution, ecmp_sols: list[ECMP_Sol], instance: Instance):
    num_edges = sum([len(ecmp_sols[0].dag.neighbors[i]) for i in range(ecmp_sols[0].dag.num_nodes)])
    return all([
        sum([
            len(sol.dag.neighbors[i]) for i in range(ecmp_sols[0].dag.num_nodes)
        ]) == num_edges
        for sol in ecmp_sols
    ])


# !!!!!!!!!! PROVED WRONG !!!!!!!!!!
SAME_NUMBER_OF_EDGES_CONJECTURE = Conjecture(
    "same_edges",
    check_same_edges,
    lambda opt_sol, ecmp_sols, inst: f"Graph has {inst.dag.num_nodes} nodes\n" + "\n".join([str(
        sum([len(sol.dag.neighbors[i]) for i in range(ecmp_sols[0].dag.num_nodes)])
    ) for sol in ecmp_sols])
)
# !!!!!!!!!! PROVED WRONG !!!!!!!!!!


ALL_CONJECTURES = [
    MAIN_CONJECTURE, LOADS_CONJECTURE
]


def check_all_conjectures(opt_solution: Solution, ecmp_solutions: list[ECMP_Sol], inst: Instance, index: int):
    return all(
        conj.check(opt_solution, ecmp_solutions, inst, index)
        for conj in ALL_CONJECTURES
    )
