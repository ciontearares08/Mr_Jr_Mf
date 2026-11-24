"""Time APSIM seasons in three ways (S3-05).

The numbers decide the ensemble size N and which cloud we pick (S3-07).

What it does:
1. Prints the CPU and memory limits the container really has.
2. Runs one warm-up season that is not counted (.NET is slow)
3. Runs --runs seasons one after another and times each one.
4. Runs the same seasons in a pool of --workers processes, and times each run
   and the whole batch. This is how the sim service ran an ensemble before #47,
   kept for comparison.
5. Runs the same seasons in one APSIM process with run_seasons(), the way the
   sim service runs an ensemble since #47, and times the whole batch.
6. Prints the times, the speed-up of the pool and of one process, and the peak
   memory.

Every run uses the same weather file. The run time depends very little on the
weather, so that is enough for timing.

Run it from apps/sim:

    uv run python scripts/bench.py --runs 20 --workers 2

Add --output results.json to also save the numbers to a file. To see how the
time and memory of one process grow with the ensemble size, run it with the
sizes you plan to use, for example --runs 10, 14 and 20.
"""

import argparse
import datetime as dt
import json
import multiprocessing
import os
import resource
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sim.apsim import run_season, run_seasons

SIM_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WEATHER = SIM_DIR / "tests" / "fixtures" / "Copenhagen_2025-26.met"
DEFAULT_SOWING_DATE = dt.date(2025, 10, 1)

# Files where Linux shows the limits of the container (cgroup v2).
# Docker's --cpus and --memory end up in these files.
CPU_LIMIT_FILE = Path("/sys/fs/cgroup/cpu.max")
MEMORY_LIMIT_FILE = Path("/sys/fs/cgroup/memory.max")
MEMORY_PEAK_FILE = Path("/sys/fs/cgroup/memory.peak")

MB = 1024 * 1024

# One Season


def time_one_season(weather_path: Path, sowing_date: dt.date) -> tuple[float, float]:
    """Run one APSIM season and return (seconds, peak memory in MB).

    The peak memory is the largest APSIM process this Python process has run
    so far. run_season starts APSIM as a child process, and Linux remembers
    the largest memory use of the children (ru_maxrss, in kilobytes).
    """
    started = time.perf_counter()
    run_season(weather_path=weather_path, sowing_date=sowing_date)
    seconds = time.perf_counter() - started

    peak_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return seconds, peak_kb / 1024


# 3 ways to run many seasons


def run_one_after_another(
    runs: int, weather_path: Path, sowing_date: dt.date
) -> tuple[list[float], float, float]:
    """Run the seasons one by one.

    Returns the seconds of each run, the total seconds and the peak MB.
    """
    times = []
    peak_mb = 0.0
    started = time.perf_counter()

    for number in range(1, runs + 1):
        seconds, peak_mb = time_one_season(weather_path, sowing_date)
        times.append(seconds)
        print(f"  run {number:>2} of {runs}: {seconds:5.2f} s")

    total = time.perf_counter() - started
    return times, total, peak_mb


def run_in_pool(
    runs: int, workers: int, weather_path: Path, sowing_date: dt.date
) -> tuple[list[float], float, float]:
    """Run the seasons in a pool of worker processes, one APSIM process each.

    This is how the sim service ran an ensemble before #47. It is kept to
    compare with run_in_one_process.

    Returns the seconds of each run, the total seconds and the peak MB of one
    APSIM run. The total includes starting the worker processes, because an
    ensemble request paid for that too.
    """
    # "spawn" starts every worker as a fresh Python process, the same way the
    # sim service did before #47
    spawn = multiprocessing.get_context("spawn")
    started = time.perf_counter()

    with ProcessPoolExecutor(max_workers=workers, mp_context=spawn) as pool:
        futures = [
            pool.submit(time_one_season, weather_path, sowing_date) for _ in range(runs)
        ]
        results = [future.result() for future in futures]

    total = time.perf_counter() - started
    times = [seconds for seconds, _ in results]
    peak_mb = max(peak for _, peak in results)
    for number, seconds in enumerate(times, start=1):
        print(f"  run {number:>2} of {runs}: {seconds:5.2f} s")
    return times, total, peak_mb


def run_in_one_process(
    runs: int, weather_path: Path, sowing_date: dt.date
) -> tuple[float, float, int]:
    """Run all seasons in one APSIM process, like the sim service since #47.

    Returns the total seconds, the peak MB and how many seasons failed. There
    are no times per run, because all seasons share one APSIM run.

    The peak MB is the largest APSIM process run so far by this script. This
    mode runs last and its process holds every season, so it is normally the
    peak of this mode.
    """
    started = time.perf_counter()
    results = run_seasons(
        {f"run_{number}": weather_path for number in range(1, runs + 1)},
        sowing_date=sowing_date,
    )
    total = time.perf_counter() - started

    failed = sum(isinstance(result, Exception) for result in results.values())
    peak_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    print(f"  {runs} seasons in {total:5.2f} s, {failed} failed")
    return total, peak_kb / 1024, failed


# Container limits


def read_text(path: Path) -> str | None:
    """Return the text of a file, or None when it does not exist."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def cpu_limit() -> str:
    """Return the CPU limit of the container, for example "2.0 CPUs".

    cpu.max holds "quota period", for example "200000 100000" means 2 CPUs.
    "max" as the quota means there is no limit.
    """
    text = read_text(CPU_LIMIT_FILE)
    if text is None:
        return "unknown (no cgroup v2 file)"
    quota, period = text.split()
    if quota == "max":
        return "no limit"
    return f"{int(quota) / int(period):.1f} CPUs"


def memory_limit() -> str:
    """Return the memory limit of the container, for example "4096 MB"."""
    text = read_text(MEMORY_LIMIT_FILE)
    if text is None:
        return "unknown (no cgroup v2 file)"
    if text == "max":
        return "no limit"
    return f"{int(text) / MB:.0f} MB"


def container_memory_peak_mb() -> float | None:
    """Return the most memory the whole container has used since it started.

    This includes everything in the container (Python, every APSIM process
    running at the same time and `uv sync` before the script), so it is the
    number to compare with the memory limit of a cloud container.
    """
    text = read_text(MEMORY_PEAK_FILE)
    return None if text is None else int(text) / MB


# Report


def summary(times: list[float]) -> dict[str, float]:
    return {
        "min_s": min(times),
        "median_s": statistics.median(times),
        "mean_s": statistics.mean(times),
        "max_s": max(times),
    }


def print_summary(
    title: str, times: list[float], total: float, runs: int, peak_mb: float
) -> None:
    numbers = summary(times)
    print(f"\n{title}")
    print(
        f"  per run:  min {numbers['min_s']:.2f} s | median {numbers['median_s']:.2f} s"
        f" | mean {numbers['mean_s']:.2f} s | max {numbers['max_s']:.2f} s"
    )
    print(f"  total:    {total:.1f} s for {runs} runs")
    print(f"  peak memory of one APSIM run: {peak_mb:.0f} MB")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--runs", type=int, default=20, help="Seasons per method (default 20)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Worker processes in the pool. Set it to the CPU limit (default 2)",
    )
    parser.add_argument(
        "--weather",
        type=Path,
        default=DEFAULT_WEATHER,
        help="The .met file every run uses (default the 2025/26 fixture)",
    )
    parser.add_argument(
        "--sowing-date",
        type=dt.date.fromisoformat,
        default=DEFAULT_SOWING_DATE,
        help="Sowing date inside the weather file (default 2025-10-01)",
    )
    parser.add_argument(
        "--output", type=Path, help="Also save the numbers to this JSON file"
    )
    arguments = parser.parse_args()

    if arguments.runs < 1 or arguments.workers < 1:
        parser.error("--runs and --workers must be at least 1")
    return arguments


def main() -> None:
    arguments = parse_arguments()
    runs, workers = arguments.runs, arguments.workers
    weather, sowing_date = arguments.weather.resolve(), arguments.sowing_date

    # os.cpu_count() shows the CPUs of the whole machine, not the container's
    # limit. Compare it with the CPU limit to see whether they differ.
    print("Container")
    print(f"  CPU limit:         {cpu_limit()}")
    print(f"  CPUs Python sees:  {os.cpu_count()} (os.cpu_count)")
    print(f"  memory limit:      {memory_limit()}")
    print(f"  weather file:      {weather.name}, sown on {sowing_date}")

    print("\nWarm-up run (not counted)")
    warm_up_seconds, _ = time_one_season(weather, sowing_date)
    print(f"  {warm_up_seconds:.2f} s")

    print(f"\nOne after another: {runs} runs")
    sequential, sequential_total, sequential_peak = run_one_after_another(
        runs, weather, sowing_date
    )

    print(f"\nProcess pool: {runs} runs with {workers} workers")
    pooled, pooled_total, pooled_peak = run_in_pool(runs, workers, weather, sowing_date)

    print(f"\nOne APSIM process: {runs} runs")
    one_total, one_peak, one_failed = run_in_one_process(runs, weather, sowing_date)

    print_summary(
        "One after another", sequential, sequential_total, runs, sequential_peak
    )
    print_summary(
        f"Process pool ({workers} workers)", pooled, pooled_total, runs, pooled_peak
    )

    print("\nOne APSIM process")
    print(
        f"  per run:  {one_total / runs:.2f} s on average (all runs share one process)"
    )
    print(f"  total:    {one_total:.1f} s for {runs} runs, {one_failed} failed")
    print(f"  peak memory of the APSIM process: {one_peak:.0f} MB")

    # How many times faster each way finished the same work than one after another
    speed_up = sequential_total / pooled_total
    one_speed_up = sequential_total / one_total
    print(f"\nSpeed-up of the pool:           {speed_up:.2f}x")
    print(f"Speed-up of one APSIM process: {one_speed_up:.2f}x")

    container_peak = container_memory_peak_mb()
    if container_peak is not None:
        print(f"Peak memory of the whole container: {container_peak:.0f} MB")

    if arguments.output:
        results = {
            "cpu_limit": cpu_limit(),
            "cpus_python_sees": os.cpu_count(),
            "memory_limit": memory_limit(),
            "runs": runs,
            "workers": workers,
            "warm_up_s": warm_up_seconds,
            "one_after_another": {
                **summary(sequential),
                "total_s": sequential_total,
                "peak_run_mb": sequential_peak,
            },
            "pool": {
                **summary(pooled),
                "total_s": pooled_total,
                "peak_run_mb": pooled_peak,
            },
            "one_process": {
                "mean_s": one_total / runs,
                "total_s": one_total,
                "failed": one_failed,
                "peak_process_mb": one_peak,
            },
            "speed_up": speed_up,
            "one_process_speed_up": one_speed_up,
            "container_peak_mb": container_peak,
        }
        arguments.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Saved the numbers to {arguments.output}")


# The guard is needed with "spawn": every worker process loads this file again,
# and without it each worker would start its own benchmark.
if __name__ == "__main__":
    main()
