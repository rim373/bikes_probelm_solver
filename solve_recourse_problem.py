from amplpy import AMPL
import matplotlib.pyplot as plt

from data import (
    instance_name,
    param_rp_full
)
from utils import load_param, draw_graph, show_rp_solution, check_solution

ampl = AMPL()
ampl.read("models/recourse_problem_v2.mod")

print(f"Use instance: '{instance_name}'")

load_param(ampl, param_rp_full)
draw_graph(param_rp_full["path"])

# Specify the solver to use (e.g., HiGHS, CPLEX, Gurobi)
ampl.option["solver"] = "gurobi"

if __name__ == "__main__":
    # Solve the problem
    ampl.solve()

    # Stop if the model was not solved
    assert ampl.solve_result == "solved"

    obj = ampl.get_objective("DemandDissatisfaction")
    print("Objective is:", obj.get().value())
    print("Solution is:", ampl.get_solution())

    check_solution(ampl, param_rp_full)
    df = show_rp_solution(ampl)
    plt.show()
