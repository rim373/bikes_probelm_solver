"""
velov_loader.py
================
Turn a real Velo'v (Lyon) status-snapshot database into the arrays the BSRP
solver needs:

    - cost          : (n+1, n+1) distance matrix in km, node 0 = depot
    - avail_bikes   : (n,)  bikes physically present at each station
    - avail_docks   : (n,)  free docks at each station
    - demand        : (n,)  rebalancing target (+ = deliver bikes, - = remove bikes)

The database is expected to be ONE SQLite table (default name 'velov') holding
GBFS-style 1-minute snapshots with these columns:

    id, date, station_id, name, lat, lon, address, capacity,
    num_bikes_available, num_bikes_disabled, num_docks_available,
    num_docks_disabled, is_installed, is_renting, is_returning, is_ok

Because you only have *status* snapshots (no trip table), 'demand' is DERIVED
from how the bike counts change over time: a station that typically loses bikes
during the morning window should be pre-loaded (positive demand); one that fills
up should be emptied (negative demand).

All configuration lives in the project-root `config.py` (and the DB path in
`.env`). You can still override any value per call via build(...) keyword args.
"""

import os
import sqlite3

import numpy as np

# Import settings from the central config.py at the project root. This works
# both when the package is imported (project root on sys.path) and when the
# file is run directly from inside data/ (fallback adds the root to sys.path).
try:
    import config
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config

DB_PATH        = config.DB_PATH
TABLE          = config.TABLE
N_STATIONS     = config.N_STATIONS
M_TRUCKS       = config.M_TRUCKS
TRUCK_CAPACITY = config.TRUCK_CAPACITY
DEPOT_LATLON   = config.DEPOT_LATLON
CENTER_LATLON  = config.CENTER_LATLON
SNAPSHOT_TIME  = config.SNAPSHOT_TIME
WINDOW_START   = config.WINDOW_START
WINDOW_END     = config.WINDOW_END
WEEKDAYS_ONLY  = config.WEEKDAYS_ONLY
R_EARTH_KM     = config.R_EARTH_KM


def _haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R_EARTH_KM * np.arcsin(np.sqrt(a))


def _weekday_clause():
    if WEEKDAYS_ONLY:
        return "AND strftime('%w', date) IN ('1','2','3','4','5') "
    return ""


def _stations_catalog(con):
    """One representative row per station (most recent snapshot)."""
    q = (
        "SELECT s.station_id, s.name, s.lat, s.lon, s.capacity "
        "FROM {t} s "
        "JOIN (SELECT station_id, MAX(date) AS md FROM {t} GROUP BY station_id) l "
        "ON s.station_id = l.station_id AND s.date = l.md"
    ).format(t=TABLE)
    catalog = {}
    for sid, name, lat, lon, cap in con.execute(q):
        if lat is None or lon is None:
            continue
        if sid not in catalog:
            catalog[sid] = {"name": name, "lat": lat, "lon": lon, "capacity": cap}
    return catalog


def _values_at_time(con, sid, hhmm):
    """Return {date_str: (bikes, docks)} for the snapshot at HH:MM on each day."""
    q = (
        "SELECT strftime('%Y-%m-%d', date) AS d, "
        "       num_bikes_available, num_docks_available "
        "FROM {t} "
        "WHERE station_id = ? AND strftime('%H:%M', date) = ? "
        "{wd}"
    ).format(t=TABLE, wd=_weekday_clause())
    out = {}
    for d, bikes, docks in con.execute(q, (sid, hhmm)):
        if bikes is not None and docks is not None:
            out[d] = (bikes, docks)
    return out


def build(**overrides):
    """Read the DB and return a dict of solver-ready arrays and parameters."""
    global TABLE  # SQL helpers read this module global
    cfg = {
        "DB_PATH": DB_PATH, "TABLE": TABLE, "N_STATIONS": N_STATIONS,
        "M_TRUCKS": M_TRUCKS, "TRUCK_CAPACITY": TRUCK_CAPACITY,
        "DEPOT_LATLON": DEPOT_LATLON, "CENTER_LATLON": CENTER_LATLON,
        "SNAPSHOT_TIME": SNAPSHOT_TIME, "WINDOW_START": WINDOW_START,
        "WINDOW_END": WINDOW_END,
    }
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    TABLE = cfg["TABLE"]

    if not cfg["DB_PATH"] or not os.path.exists(cfg["DB_PATH"]):
        raise FileNotFoundError(
            "Database not found: '{}'. Set VELOV_DB in your .env file "
            "(see .env.example) or DB_PATH in config.py.".format(cfg["DB_PATH"])
        )

    con = sqlite3.connect(cfg["DB_PATH"])
    try:
        catalog = _stations_catalog(con)
        if len(catalog) == 0:
            raise RuntimeError("No stations with coordinates found in the DB.")

        sids = list(catalog.keys())
        lats = np.array([catalog[s]["lat"] for s in sids])
        lons = np.array([catalog[s]["lon"] for s in sids])

        # 1) choose the center, then keep the N nearest stations to it
        if cfg["CENTER_LATLON"] is not None:
            c_lat, c_lon = cfg["CENTER_LATLON"]
        else:
            c_lat, c_lon = lats.mean(), lons.mean()
        d_to_center = _haversine(lats, lons, c_lat, c_lon)
        n = min(cfg["N_STATIONS"], len(sids))
        keep = np.argsort(d_to_center)[:n]
        sel = [sids[i] for i in keep]
        sel_lat = lats[keep]
        sel_lon = lons[keep]
        names = [catalog[s]["name"] for s in sel]

        # 2) depot (node 0)
        if cfg["DEPOT_LATLON"] is not None:
            depot_lat, depot_lon = cfg["DEPOT_LATLON"]
        else:
            depot_lat, depot_lon = sel_lat.mean(), sel_lon.mean()

        node_lat = np.concatenate(([depot_lat], sel_lat))
        node_lon = np.concatenate(([depot_lon], sel_lon))

        # 3) distance matrix (km), symmetric, zero diagonal
        cost = np.zeros((n + 1, n + 1))
        for i in range(n + 1):
            cost[i] = _haversine(node_lat[i], node_lon[i], node_lat, node_lon)
        np.fill_diagonal(cost, 0.0)

        # 4) current availability from the SNAPSHOT_TIME (median across days)
        avail_bikes = np.zeros(n, dtype=int)
        avail_docks = np.zeros(n, dtype=int)
        # 5) demand from drain over [WINDOW_START, WINDOW_END]
        demand = np.zeros(n, dtype=int)

        for k, sid in enumerate(sel):
            snap = _values_at_time(con, sid, cfg["SNAPSHOT_TIME"])
            if snap:
                b = np.array([v[0] for v in snap.values()])
                d = np.array([v[1] for v in snap.values()])
                avail_bikes[k] = int(round(np.median(b)))
                avail_docks[k] = int(round(np.median(d)))

            start = _values_at_time(con, sid, cfg["WINDOW_START"])
            end = _values_at_time(con, sid, cfg["WINDOW_END"])
            common = set(start.keys()) & set(end.keys())
            if common:
                # drain = bikes_start - bikes_end  (>0 means station loses bikes)
                drains = np.array([start[d][0] - end[d][0] for d in common])
                demand[k] = int(round(np.median(drains)))
    finally:
        con.close()

    desc = ("Velo'v Lyon | {} stations near ({:.4f},{:.4f}) | snapshot {} | "
            "demand from drain {}-{}").format(
        n, c_lat, c_lon, cfg["SNAPSHOT_TIME"], cfg["WINDOW_START"], cfg["WINDOW_END"])

    result = {
        "n": n,
        "m": min(cfg["M_TRUCKS"], n),
        "truck_capacity": cfg["TRUCK_CAPACITY"],
        "cost": cost,
        "avail_bikes": avail_bikes,
        "avail_docks": avail_docks,
        "demand": demand,
        "station_ids": sel,
        "station_names": names,
        "desc": desc,
        "snapshot_time": cfg["SNAPSHOT_TIME"],
        "window": (cfg["WINDOW_START"], cfg["WINDOW_END"]),
    }
    return result


if __name__ == "__main__":
    inst = build()
    print(inst["desc"])
    print("stations   :", inst["station_names"])
    print("avail_bikes:", inst["avail_bikes"])
    print("avail_docks:", inst["avail_docks"])
    print("demand     :", inst["demand"])
    print("cost shape :", inst["cost"].shape)
