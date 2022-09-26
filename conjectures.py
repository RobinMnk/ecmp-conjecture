from model import *

import pickle
import os


def check_congestion(opt_solution: Solution, ecmp_solution: ECMP_Sol, instance=None):
    return ecmp_solution.congestion < 2 * opt_solution.opt_congestion


def check_loads(opt_solution: Solution, ecmp_solution: ECMP_Sol, instance: Instance):
    optimal_loads = get_node_loads(opt_solution.dag, instance.sources)
    return compare_node_loads(ecmp_solution.loads, optimal_loads, instance.sources)


class Conjecture:
    def __init__(self, name, verification_function):
        self.name = name
        self.verification_function = verification_function

    def check(self, opt_solution: Solution, ecmp_solution: ECMP_Sol, inst: Instance, index: int):
        logger = get_logger()
        success = self.verification_function(opt_solution, ecmp_solution, instance=inst)
        if not success:
            # FAIL
            logger.error("")
            logger.error("=" * 40)
            logger.error(" " * 10 + "COUNTEREXAMPLE FOUND!!" + " " * 10)
            logger.error("=" * 40)
            os.makedirs(f"graph/errors_{self.name}", exist_ok=True)
            with open(f"graph/errors_{self.name}/ex_{index}.pickle", "wb") as f:
                pickle.dump(inst, f, pickle.HIGHEST_PROTOCOL)
                show_graph(inst, f"errors_{self.name}/ex_{index}", opt_solution.dag)

            return False

        return True


MAIN_CONJECTURE = Conjecture("congestion", check_congestion)
LOADS_CONJECTURE = Conjecture("loads", check_loads)
ALL_CONJECTURES = [
    MAIN_CONJECTURE, LOADS_CONJECTURE
]


def check_all_conjectures(opt_solution: Solution, ecmp_solution: ECMP_Sol, inst: Instance, index: int):
    return all(
        conj.check(opt_solution, ecmp_solution, inst, index)
        for conj in ALL_CONJECTURES
    )

