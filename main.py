import time

from model import *
from optimal_solver import calculate_optimal_solution
from ecmp import get_ecmp_congestion

if __name__ == '__main__':
    # random.seed(31415926535)
    seed = time.time()
    random.seed(seed)

    success = True
    max_factor = 0
    for i in range(50):
        size = random.randint(4, 4)
        prob = random.random()

        print(f"Building Instance on {size} nodes with edge probability {prob}")
        inst = build_random_DAG(size, prob)

        print("Calculating optimal solution")
        solution = calculate_optimal_solution(inst)

        if solution is None:
            print("Error in computing optimal solution")
            continue

        # show_graph(inst, solution.dag)
        print("Calculating ECMP solution")
        ecmp_cong = get_ecmp_congestion(solution.dag, inst.sources)
        print(f"ECMP Congestion: {ecmp_cong}")

        factor = ecmp_cong / solution.opt_congestion
        max_factor = max(max_factor, factor)
        print(f"Factor: {factor}")

        if max_factor >= 2 or max_factor < 1:
            show_graph(inst, f"graph{i}", solution.dag)

    print(" ------------------------------ ")
    print(f"{seed=}")
    print(f"{max_factor}")
    print("SUCCESS!" if max_factor < 2 else "FAIL!")


