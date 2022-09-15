from model import *
from optimal_solver import calculate_optimal_solution

if __name__ == '__main__':
    random.seed(31415926535)

    inst = build_random_DAG(10, 0.5)

    solution = calculate_optimal_solution(inst)

    if solution is None:
        print("Error in computing optimal solution")
        exit(1)

    show_graph(inst, solution)


