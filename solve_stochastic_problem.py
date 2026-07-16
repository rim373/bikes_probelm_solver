import argparse
import copy
import pickle
import time
import re

from amplpy import AMPL
import matplotlib.pyplot as plt
import numpy as np

from data import (
    n,
    m,
    param_mp,
    param_rp,
    instance_name, instance_desc, instance_id,
)
from utils import load_param, draw_graph, show_rp_solution, extract_paths, show_metrics


alpha = 0.9
N = 3**n

parser = argparse.ArgumentParser()
parser.add_argument(
    "--export",
    action="store_true",
    help="Export MP model and data at each iteration",
)
parser.add_argument(
    "--show",
    action="store_true",
    help="At the end of the algorithm, show intermediate RP and MP solutions. This can significantly slow the solving as it requires opening dozens of figures.",
)
parser.add_argument(
    "--no-sols-metrics",
    dest="save_solutions",
    action="store_false", # if used that means we don't want to store solutions in metrics, so 'ARGS.save_solutions == False'
    help="Don't save MP and RP solutions in metrics. This significantly reduces metrics object size.",
)
ARGS = parser.parse_args()


def solve_MP(mp):
    # Main problem
    load_param(mp, param_mp)
    mp.solve()
    return mp.solve_result == "solved"


def enumerate_Omega(demand):
    def enumerate_modifiers(modifier, i):
        if i == len(modifier):
            yield modifier
        else:
            for j in [-1, 0, 1]:
                modifier[i] = j
                yield from enumerate_modifiers(modifier, i+1)

    iter_realizations = enumerate_modifiers([None]*len(demand), 0)
    demand = np.array(demand)
    for modifier in iter_realizations:
        yield demand + np.array(modifier)


def solve_all_RP(rp, paths):
    # Recourse problems solution
    rpj_obj = []
    if ARGS.save_solutions is True:
        rpj_sols = [[] for s in range(m)]

    # Iterate over realization of the demand stochastic variable
    iter_demand = enumerate_Omega(param_rp["demand"])
    print()
    for j, demand in enumerate(iter_demand):
        y0 = np.zeros(m)
        y = np.zeros(n)
        if ARGS.show is True and (demand == param_rp["demand"]).all():
            fig, axs = plt.subplots(m)
        for s in range(m):
            # Solve 1 RP
            param = copy.deepcopy(param_rp)
            param["path"] = paths[s]
            param["demand"] = demand
            load_param(rp, param)
            rp.solve(verbose=False, return_output=False)
            if rp.solve_result != "solved":
                # A single scenario failing to solve must not abort the whole run.
                # Fall back to the no-op recourse (y = 0 for this subtour).
                if not getattr(solve_all_RP, "_warned_status", False):
                    print(
                        "\n[warn] Recourse Problem status '{}' (not 'solved') at "
                        "realization {}, subtour {}, demand={}. Falling back to "
                        "no-op (y=0). Further warnings suppressed."
                        .format(rp.solve_result, j, s, list(demand))
                    )
                    solve_all_RP._warned_status = True
                if ARGS.save_solutions is True:
                    rpj_sols[s].append([(i, 0) for i in range(n + 1)])
                continue

            # Draw
            if ARGS.show is True and (demand == param_rp["demand"]).all():
                show_rp_solution(rp, ax = axs[s])

            # Aggregate solutions of all RP^s
            y_sol = rp.get_variable("y").to_list()
            if ARGS.save_solutions is True:
                rpj_sols[s].append(y_sol)
            _, y0[s] = y_sol[0]
            for i, y_i in y_sol:
                if i != 0:
                    y[i-1] += y_i
        # Add RP solution for this realization of the demand
        rpj_obj.append(np.linalg.norm(demand - y))
        print(f"\rRealization {j}", end="")

        if ARGS.show is True and (demand == param_rp["demand"]).all():
            plt.show(block=False)
    if ARGS.save_solutions is True:
        metrics["rpj_sols"].append(rpj_sols)
    print()
    return rpj_obj


def compute_obj(rpj_obj, mp_obj):
    assert N == len(rpj_obj)
    # All RPs have the same probability p^j = 1 / N
    return mp_obj * alpha + sum(rpj_obj) / N * (1 - alpha)


def draw_mp(paths):
    """DEPRECATED"""
    print("DEPRECATED: draw_mp")
    # Draw
    for s in range(m):
        draw_graph(paths[s])
        input("look at the graph !!!")
    draw_graph(paths.sum(axis = 0))


def report_metrics():
    metrics["mp_objs"].append(mp_obj)
    metrics["mp_total_solve_time"].append(float(re.search(r"[0-9]+(?:.[0-9]+)?", mp.get_output("display _total_solve_time;")).group()))
    metrics["mp_solve_time"].append(float(re.search(r"[0-9]+(?:.[0-9]+)?", mp.get_output("display _solve_time;")).group()))

    metrics["sp_objs"].append(sp_obj)
    metrics["best_obj"].append(best_obj)
    metrics["rpj_objs"].append(copy.deepcopy(rpj_obj))
    metrics["rp_total_solve_time"].append(float(re.search(r"[0-9]+(?:.[0-9]+)?", rp.get_output("display _total_solve_time;")).group()))
    metrics["rp_solve_time"].append(float(re.search(r"[0-9]+(?:.[0-9]+)?", rp.get_output("display _solve_time;")).group()))
    metrics["elapsed_time"].append(time.time() - start)


def save_metrics(metrics, instance_name):
    instance_name = instance_name if instance_name != "" else "NONAME_INSTANCE"
    with open(f"metrics_{instance_name}.pickle", "wb") as f:
        pickle.dump(metrics, f)


if __name__ == "__main__":
    mp = AMPL()
    start = time.time()
    mp.read("models/main_problem_v1.mod")
    mp.option["solver"] = "gurobi"

    rp = AMPL()
    rp.read("models/recourse_problem_v2.mod")
    rp.option["solver"] = "gurobi"

    # rp : a single rp or the RP in general
    # rpj : array of rp^j given realization of the demand indexed j
    # obj (resp. sol): a single objective value (resp. solution array)
    # objs (resp. sols): an array containing objectives values (resp. solutions arrays) of each iteration of the algo
    metrics = {
        "instance" : (instance_name, instance_desc, instance_id),
        "metadata" : {"alpha": alpha},
        "models_versions" : (mp.get_option("model_version"), rp.get_option("model_version")),
        "mp_objs" : [],
        "mp_total_solve_time" : [],
        "mp_solve_time" : [],
        "elapsed_time" : [],
        "sp_objs": [],
        "best_obj": [],
        "rpj_objs" : [],
        "rp_total_solve_time" : [],
        "rp_solve_time" : [],

        "mp_sols": [],
        "rpj_sols": [],
    }

    ### Step 0
    # Solve MP
    solve_MP(mp)
    mp_obj = mp.get_objective("TotalCost").value()

    # MP solution post-treatment
    total_path, paths = extract_paths(mp)
    if ARGS.save_solutions is True:
        metrics["mp_sols"].append((total_path, paths))

    # Export data
    draw_graph(total_path, filename = f"graph_mp0.png")

    # Solve RPs
    rpj_obj = solve_all_RP(rp, paths)

    # Compute SP obj
    sp_obj = compute_obj(rpj_obj, mp_obj)

    # Initialize best solution
    best_p = 0
    best_obj = sp_obj

    # report metrics
    report_metrics()

    # Add constraints to MP to start looping
    mp.eval("""param bestObj;
            subject to costLimit : totalCost < bestObj;"""
        )

    ### Boucle
    p = 1
    forbiddenPath = None
    try:
        while mp.solve_result == "solved":
            print("---")
            print(f"Iteration {p}:")

            # Add forbidden path constraint
            mp.eval("param forbiddenPath" + str(p) + " {NODES, NODES} binary;"\
                    "subject to forceAnotherSolution" + str(p) + " : sum{i in NODES, j in NODES} (forbiddenPath" + str(p) + "[i, j] - sum{s in SUBTOURS} path[i, j, s])^2 >= 1;"
            )

            # Update param of MP
            param_mp["bestObj"] = best_obj
            forbiddenPath = total_path
            param_mp[f"forbiddenPath{p}"] = forbiddenPath

            # Solve MP
            if not solve_MP(mp):
                break
            mp_obj = mp.get_objective("TotalCost").value()

            # MP solution post-treatment
            total_path, paths = extract_paths(mp)
            if ARGS.save_solutions is True:
                metrics["mp_sols"].append((total_path, paths))

            # Export data
            draw_graph(total_path, filename = f"graph_mp{p}.png")
            if ARGS.export:
                mp.export_model(f"mp{p}.mod")
                mp.export_data(f"mp{p}.dat")

            # Solve RPs
            rpj_obj = solve_all_RP(rp, paths)

            # Compute SP obj
            sp_obj = compute_obj(rpj_obj, mp_obj)

            # Update best solution
            if sp_obj < best_obj:
                best_obj = sp_obj
                best_p = p
            print(f"Obj: {sp_obj}, best is {best_obj} (it. {best_p})")
            print(f"  MP: {mp_obj} | RPs: {sum(rpj_obj) / N}")

            # report metrics
            report_metrics()

            p+=1
    except KeyboardInterrupt:
        print(f"Resolution interrupted during step {p}")
    else:
        print("Stochastic problem solved.")
    finally:
        print(f"Best objective is {best_obj} at step {best_p} (see model data at step {best_p} for path)")
        print("See metrics for plotting")
        save_metrics(metrics, instance_name)
        show_metrics(metrics)
