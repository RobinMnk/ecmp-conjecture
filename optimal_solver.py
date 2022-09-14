from main import *

import gurobipy as gp
from gurobipy import GRB


def calculate_optimal_solution(instance: Instance):
    try:
        # Create a new model
        m = gp.Model("ecmp_opt")






    except gp.GurobiError as e:
        print('Error code ' + str(e.errno) + ': ' + str(e))

    except AttributeError:
        print('Encountered an attribute error')
