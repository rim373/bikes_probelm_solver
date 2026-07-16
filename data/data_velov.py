# Real Velo'v (Lyon) instance, built directly from the status-snapshot DB.
#
# This project runs ONLY on real data: there is no synthetic instance
# generator anymore. All numbers come from your database via velov_loader.
#
# To change the instance edit config.py (DB path lives in the .env file).
import hashlib

import numpy as np

from . import velov_loader

# Read the database and derive the arrays (distances, availability, demand).
_inst = velov_loader.build()

# --- General parameters -------------------------------------------------
n = _inst["n"]
m = _inst["m"]
_truck_capacity = _inst["truck_capacity"]

# --- Instance identity (used for metrics filenames and printing) --------
instance_desc = _inst["desc"]
instance_name = "VELOV_LYON_{}s_{}t_snap{}".format(
    n, m, _inst["snapshot_time"].replace(":", "")
)
instance_id = hashlib.md5(instance_desc.encode("utf-8")).hexdigest()[:5]

# --- Main Problem parameters (routing) ----------------------------------
# matches models/main_problem_v1.mod
param_mp = {
    "n": n,
    "m": m,
    "big_M_n": n,
    "cost": np.asarray(_inst["cost"], dtype=float),
}

# --- Recourse Problem parameters (bike movements) -----------------------
# matches models/recourse_problem_v2.mod
param_rp = {
    "n": n,
    "truck_capacity": _truck_capacity,
    "big_M": _truck_capacity,
    "avail_bikes": np.asarray(_inst["avail_bikes"], dtype=int),
    "avail_docks": np.asarray(_inst["avail_docks"], dtype=int),
    "demand": np.asarray(_inst["demand"], dtype=int),
}

# --- Real station identities (handy for post-processing) ----------------
station_ids = _inst["station_ids"]
station_names = _inst["station_names"]
