<div align="center">
<h1>Bike-sharing Repositionning Problem (BSRP) Solver 🚲⚙️</h1>
<img width=800 alt="6s_CARA_algo.gif" src="./gallery/6s_CARA_algo.gif" /> <br />
<b><i> From real bike-sharing data find 🧠 the best trucks routes to redistribute bikes 🚴 to match stochastic user demand ✅ using exact methods. </i></b>
<br />
</div>

## About
This project uses [AMPL](https://ampl.com) to model the problem and leverages the [AMPL Python API](https://amplpy.ampl.com) to solve it. The mathematical model is described in a [typst document](https://typst.app).

It runs **only on real data**: instances are built directly from a Velo'v (Lyon) status-snapshot database. There is no synthetic instance generator anymore — every number (station positions, availability, demand) comes from the database.

## Setup repository
After cloning this repository you must:
1. [Install dependencies](#install-dependencies)
2. [Setup AMPL](#setup-ampl)
3. [Point the solver at your database](#configure-your-database)

If you're not interested in the details jump to [Quick start](#quick-start)

### Quick start
This is a wrap up of the following sections.
#### Setup AMPL
First you need to get an AMPL License, [register](https://portal.ampl.com/user/ampl/request/amplce/trial) **with your academic email** to get free access to commercial solvers (e.g. Gurobi, CPLEX, etc).

Then export your AMPL License UUID as an environment variable
First you need to export your AMPL License UUID, to get one [register **with your academic email**](https://portal.ampl.com/user/ampl/request/amplce/trial):
```bash
# Note: the starting whitespace is important not to add this sensitive information to your bash history (adapt it if not using bash)
 export AMPL_LICENSE_UUID=<your license uuid>
```
#### Create virtual enviroment
```bash
# Create venv
mkdir venv
python -m venv venv
# Enter venv
source venv/Scripts/activate
```
#### Install package dependencies
```bash
# Install system-wide non-python packages
winget install graphviz

# Install python dependencies
python -m pip install -r requirements.txt

# Setup amplpy
python -m pip install amplpy --upgrade
python -m amplpy.modules install highs gurobi
python -m amplpy.modules activate $AMPL_LICENSE_UUID
```


> [!important]
> `gravis` (used for the optional interactive graph export) imports `pkg_resources`, which was **removed in setuptools 81**. If you hit `ModuleNotFoundError: No module named 'pkg_resources'`, pin an older setuptools:
> ```bash
> pip install "setuptools<81"
> ```
> This is already pinned in `requirements.txt`.



## Configure your database
Instances are built from a **Velo'v (Lyon) SQLite database** of 1-minute status snapshots. The database is expected to be a single table with these columns:

```
id, date, station_id, name, lat, lon, address, capacity,
num_bikes_available, num_bikes_disabled, num_docks_available,
num_docks_disabled, is_installed, is_renting, is_returning, is_ok
```

First, tell the solver where your database is. Copy the template and edit it:
```bash
cp .env.example .env
# then edit .env and set VELOV_DB to the absolute path of your .db file
```

All other settings live in [`config.py`](./config.py) at the project root (the DB path and table name are read from `.env`):

| Parameter | Meaning |
| --- | --- |
| `VELOV_DB` (in `.env`) | absolute path to your `.db` file |
| `VELOV_TABLE` (in `.env`) | table name inside the DB |
| `N_STATIONS` | how many stations to include. **Keep small (≤ 12)** for the stochastic solver: it runs `3**n` scenarios |
| `M_TRUCKS` | number of repositioning trucks |
| `TRUCK_CAPACITY` | bikes a truck can carry |
| `DEPOT_LATLON` | depot (node 0) lat/lon; `None` → centroid of the selected stations |
| `CENTER_LATLON` | point around which the `N_STATIONS` nearest stations are picked; `None` → centroid of all stations |
| `SNAPSHOT_TIME` | time (`HH:MM`) at which current bikes/docks are read |
| `WINDOW_START` / `WINDOW_END` | window used to derive `demand` from how bike counts change |
| `WEEKDAYS_ONLY` | ignore weekends when aggregating |

### How the instance is built
- **Distances** (`cost` matrix) are computed from each station's `lat`/`lon` with the **Haversine** (great-circle) formula, in km. These are straight-line distances, not road distances.
- **`avail_bikes` / `avail_docks`** are read from the snapshot at `SNAPSHOT_TIME` (median across matching days).
- **`demand`** is *derived*, since the DB has no trip table: a station that typically **loses** bikes over `[WINDOW_START, WINDOW_END]` gets a positive demand (deliver bikes), one that **fills up** gets a negative demand (remove bikes).

To sanity-check what will be fed to the solver, run the loader directly:
```bash
cd data
python velov_loader.py   # prints the selected stations, availability and derived demand
```

## Solve problems
The active instance is defined by [`data/data_velov.py`](./data/data_velov.py) and loaded through [`data/default.py`](./data/default.py). Three scripts are provided:
- [`solve_main_problem.py`](./solve_main_problem.py) solves only the Main Problem (MP): the truck routes.
- [`solve_recourse_problem.py`](./solve_recourse_problem.py) solves only the Recourse Problem (RP): the bike movements for a given route.
- [`solve_stochastic_problem.py`](./solve_stochastic_problem.py) iteratively solves MPs and RPs until convergence to solve the Stochastic Problem (SP).

Run them for example with:
```bash
python solve_main_problem.py
python solve_stochastic_problem.py
```

> [!warning]
> The stochastic solver enumerates `3**N_STATIONS` demand scenarios. Keep `N_STATIONS` small (≤ ~12). For routing only (`solve_main_problem.py`) you can use more stations.

> [!tip]
> You can use `python -i solve_main_problem.py` to execute the script in interactive mode, opening the Python interpreter
> at the end of the script, providing you with the opportunity to post-process results by-hand.
