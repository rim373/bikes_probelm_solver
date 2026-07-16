"""
config.py
=========
Central configuration for the Velo'v (Lyon) BSRP solver.

All tunables live here and are imported by data/velov_loader.py.
The database path (and optionally the table name) are read from a `.env`
file at the project root -- see `.env.example`. This keeps machine-specific
paths out of the source code.
"""

import os

try:
    from dotenv import load_dotenv
    # Load the .env sitting next to this file, regardless of the current cwd.
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    # python-dotenv not installed: the .env file will be IGNORED. Warn loudly
    # unless the user has exported VELOV_DB manually.
    if not os.environ.get("VELOV_DB"):
        import warnings
        warnings.warn(
            "python-dotenv is not installed, so .env is ignored and VELOV_DB is "
            "unset. Run 'pip install python-dotenv' (or 'pip install -r "
            "requirements.txt'), or export VELOV_DB manually.",
            RuntimeWarning,
        )

# ============================ DATABASE (from .env) ============================
# Set VELOV_DB (and optionally VELOV_TABLE) in your .env file.
DB_PATH = os.environ.get("VELOV_DB", "")
TABLE   = os.environ.get("VELOV_TABLE", "velov")

# ============================ INSTANCE SELECTION =============================
N_STATIONS     = 5             # stations to include. KEEP SMALL (<=12) for the
                                 # stochastic solver: it runs 3**n scenarios!
M_TRUCKS       = 2               # number of repositioning trucks
TRUCK_CAPACITY = 30              # bikes a truck can carry

# Depot = node 0. If None -> centroid of the selected stations is used.
DEPOT_LATLON   = None            # e.g. (45.7578, 4.8320)

# Point around which the N nearest stations are picked.
# If None -> centroid of ALL stations in the DB.
CENTER_LATLON  = None            # e.g. (45.7640, 4.8357)  (Lyon Part-Dieu)

# Time (HH:MM) at which we read the "current" state of each station.
SNAPSHOT_TIME  = "05:00"
# Window over which we measure the typical drain used to derive 'demand'.
WINDOW_START   = "07:00"
WINDOW_END     = "10:00"
WEEKDAYS_ONLY  = True            # ignore weekends when aggregating

# ============================ CONSTANTS =====================================
R_EARTH_KM = 6371.0              # Earth radius, used by the Haversine formula
