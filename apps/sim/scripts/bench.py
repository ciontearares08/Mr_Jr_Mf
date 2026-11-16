import datetime as dt
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sim.apsim import run_season

# Resolve the path to the weather fixture we used in S2-01
WEATHER_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "Copenhagen_Weather.met"

def run_single_simulation(run_id: int) -> None:
    # Use a fixed date to guarantee identical execution times
    sowing = dt.date(2025, 4, 15)
    run_season(weather_path=WEATHER_PATH, sowing_date=sowing)

def main() -> None:
    if not WEATHER_PATH.is_file():
        raise FileNotFoundError(f"Weather file not found at {WEATHER_PATH}")

    print("Warming up .NET (Running 1 warmup season)...")
    run_single_simulation(0)

    print("\nRunning 20 seasons sequentially...")
    start_seq = time.perf_counter()
    for i in range(20):
        run_single_simulation(i)
    seq_time = time.perf_counter() - start_seq
    print(f"Sequential total: {seq_time:.2f} seconds ({seq_time/20:.2f}s per run)")

    print("\nRunning 20 seasons in a process pool...")
    start_par = time.perf_counter()
    with ProcessPoolExecutor() as pool:
        list(pool.map(run_single_simulation, range(20)))
    par_time = time.perf_counter() - start_par
    print(f"Process Pool total: {par_time:.2f} seconds")

if __name__ == "__main__":
    main()