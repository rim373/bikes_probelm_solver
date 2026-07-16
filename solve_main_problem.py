import argparse
import http.server

from amplpy import AMPL
import gravis as gv
import matplotlib.pyplot as plt
import mpld3
import numpy as np

from data import (
    n,
    param_mp
)
from utils import load_param, draw_graph, show_mp_solution, check_solution, extract_paths

parser = argparse.ArgumentParser()
parser.add_argument(
    "--mode",
    type=str,
    default="none",
    choices=["none", "mpl", "gv", "mpld3"],
    help="the plotting mode",
)
ARGS = parser.parse_args()

ampl = AMPL()
ampl.read("models/main_problem_v1.mod")

load_param(ampl, param_mp)

# Specify the solver to use (e.g., HiGHS, CPLEX, Gurobi)
ampl.option["solver"] = "gurobi"

if __name__ == "__main__":
    # Solve the problem
    ampl.solve()

    # Stop if the model was not solved
    assert ampl.solve_result == "solved"

    path_total, paths = extract_paths(ampl)
    draw_graph(path_total)
    G = show_mp_solution(ampl)

    if ARGS.mode == "mpl":
        plt.show()
    elif ARGS.mode == "mpld3":
        mpld3.show()
    elif ARGS.mode == "gv":
        fig = gv.d3(
            G,
            edge_size_data_source = 'weight',
        )
        fig.export_html("gravis_graph.html", overwrite=True)
        server = http.server.HTTPServer(("127.0.0.1", 8000), http.server.SimpleHTTPRequestHandler)
        print("Please visit http://localhost:8000/gravis_graph.html")
        server.serve_forever()
    elif ARGS.mode == "none":
        pass
    else:
        raise ValueError(f"ARGS.mode '{ARGS.mode}' is unknown")
