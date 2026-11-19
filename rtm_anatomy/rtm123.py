"""One-cohort RTM type 1/2/3 simulation helpers.

This module intentionally lives in the local `anatomy_of_RTM` repository. It
uses the CHOCOLATES simulator from a sibling checkout, but does not write to
that checkout.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from fractions import Fraction
import base64
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile
from typing import Callable, Iterable

import numpy as np

DAYS_PER_MONTH = 30
DEFAULT_MONTHS = 36
BASELINE_MONTHS = 2
TEST_MONTHS = 3
DEFAULT_MASTER_SEED = 20260531
DEFAULT_MONTHLY_MIN = 3
DEFAULT_MAX_SEIZURE_FREE_DAYS = 25
EPSILON = 1e-12
ANALYSIS_VERSION = "paired-type3-v3"

_CHOCOLATE_MODULE = None
_CHOCOLATE_SOURCE = None


@dataclass(frozen=True)
class ConditionSpec:
    """Simulation condition applied to the shared true-seizure cohort."""

    name: str
    label: str
    rtm_type: str
    threshold: int = 4
    sensitivity: float = 1.0
    far_per_day: float = 0.0
    far_label: str = "0/day"
    correct_far: bool = True
    type1_intervention: bool = False


@dataclass(frozen=True)
class CohortInfo:
    """Paths and metadata for a generated common cohort."""

    cohort_dir: Path
    n_patients: int
    months: int
    days_per_month: int
    completed_patients: int
    daily_counts_path: Path
    latent_msf_path: Path
    seeds_path: Path
    metadata_path: Path

    @property
    def days(self) -> int:
        return self.months * self.days_per_month


def project_root() -> Path:
    """Return the local anatomy_of_RTM project root."""

    return Path(__file__).resolve().parents[1]


def chocolate_repo_path() -> Path:
    """Return the CHOCOLATE repo path used for read-only simulator loading."""

    env_path = os.environ.get("CHOCOLATE_REPO")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return project_root().parent / "CHOCOLATE"


def load_chocolate_module():
    """Load CHOCOLATE's `realSim_turbo.py` without modifying that repository."""

    global _CHOCOLATE_MODULE, _CHOCOLATE_SOURCE
    if _CHOCOLATE_MODULE is not None:
        return _CHOCOLATE_MODULE

    module_path = chocolate_repo_path() / "realSim_turbo.py"
    if not module_path.exists():
        raise FileNotFoundError(
            f"Could not find CHOCOLATE realSim_turbo.py at {module_path}. "
            "Set CHOCOLATE_REPO to override the default sibling path."
        )
    spec = importlib.util.spec_from_file_location("chocolate_realsim_turbo", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {module_path}.")
    module = importlib.util.module_from_spec(spec)
    # The simulator checkout is read-only, including its bytecode cache.
    previous_bytecode_policy = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_bytecode_policy
    _CHOCOLATE_MODULE = module
    _CHOCOLATE_SOURCE = {
        "source_path": str(module_path.resolve()),
        "source_sha256": file_sha256(module_path),
    }
    return module


def file_sha256(path: str | Path) -> str:
    """Hash file contents without loading large cohort files into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def simulator_fingerprint() -> dict[str, str]:
    """Identify the simulator loaded for generation or a transient replacement."""

    load_chocolate_module()
    source = dict(_CHOCOLATE_SOURCE)
    current_path = chocolate_repo_path() / "realSim_turbo.py"
    if (source["source_path"] != str(current_path.resolve())
            or source["source_sha256"] != file_sha256(current_path)):
        raise RuntimeError("Simulator source changed after import; restart the analysis process.")
    return {**source, "numpy_version": np.__version__}


def generation_fingerprint() -> dict[str, str]:
    """Pin the generation wrapper as well as the imported simulator."""

    return {**simulator_fingerprint(), "cohort_generator_sha256": file_sha256(__file__)}


def cohort_fingerprint(cohort_dir: str | Path) -> dict[str, object]:
    """Identify every retained cohort input by content, not filesystem timestamps."""

    paths = cohort_paths(cohort_dir)
    return {
        name: {"sha256": file_sha256(paths[name]), "size_bytes": paths[name].stat().st_size}
        for name in ("daily_counts", "latent_msf", "seeds")
    }


def simple_chocolates(days_needed: int, rng: np.random.Generator, default_msf: float | None = None):
    """Call CHOCOLATE's simple_CHOCOLATES wrapper."""

    module = load_chocolate_module()
    return module.simple_CHOCOLATES(
        daysNeeded=days_needed,
        defaultSeizureFreq=default_msf,
        rng=rng,
    )


def sample_msf(rng: np.random.Generator) -> float:
    """Sample one CHOCOLATES latent monthly seizure frequency."""

    module = load_chocolate_module()
    return float(np.asarray(module.get_mSF(requested_msf=-1, rng=rng)).item())


def default_condition_specs() -> list[ConditionSpec]:
    """Return baseline plus the planned type 1, type 2, and type 3 conditions."""

    return [
        ConditionSpec(
            name="baseline_perfect",
            label="Baseline: perfect detector, 4/month",
            rtm_type="baseline",
        ),
        ConditionSpec(
            name="type1_transient_msf",
            label="Type 1: transient 2-month mSF change",
            rtm_type="type1",
            type1_intervention=True,
        ),
        ConditionSpec(
            name="type2_threshold_8",
            label="Type 2: eligibility threshold 8/month",
            rtm_type="type2",
            threshold=8,
        ),
        ConditionSpec(
            name="type3_sensitivity_90",
            label="Sensitivity 90%, FAR 0/day",
            rtm_type="type3_sensitivity",
            sensitivity=0.90,
        ),
        ConditionSpec(
            name="type3_sensitivity_80",
            label="Sensitivity 80%, FAR 0/day",
            rtm_type="type3_sensitivity",
            sensitivity=0.80,
        ),
        ConditionSpec(
            name="type3_sensitivity_70",
            label="Sensitivity 70%, FAR 0/day",
            rtm_type="type3_sensitivity",
            sensitivity=0.70,
        ),
        ConditionSpec(
            name="type3_far_1_per_month",
            label="FAR 1/month, sensitivity 100%",
            rtm_type="type3_far",
            far_per_day=1.0 / DAYS_PER_MONTH,
            far_label="1/month",
        ),
        ConditionSpec(
            name="type3_far_1_per_week",
            label="FAR 1/week, sensitivity 100%",
            rtm_type="type3_far",
            far_per_day=1.0 / 7.0,
            far_label="1/week",
        ),
        ConditionSpec(
            name="type3_far_1_per_day",
            label="FAR 1/day, sensitivity 100%",
            rtm_type="type3_far",
            far_per_day=1.0,
            far_label="1/day",
        ),
    ]


def parse_workers(value: str | int | None) -> int:
    """Parse worker-count input, accepting `auto` and `None`."""

    if value is None:
        return 1
    if isinstance(value, int):
        return max(1, value)
    text = str(value).strip().lower()
    if text == "auto":
        return max(1, (os.cpu_count() or 1) - 1)
    parsed = int(text)
    if parsed < 1:
        raise ValueError("workers must be positive or 'auto'.")
    return parsed


def stable_seed(*parts: object) -> int:
    """Return a deterministic 63-bit seed from arbitrary identifying parts."""

    digest = hashlib.blake2b(digest_size=8)
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"|")
    return int.from_bytes(digest.digest(), "little") & ((1 << 63) - 1)


def monthly_from_daily(daily_counts: np.ndarray, days_per_month: int = DAYS_PER_MONTH) -> np.ndarray:
    """Aggregate fixed-length daily diary data into monthly totals."""

    daily = np.asarray(daily_counts, dtype=np.int32)
    if daily.ndim != 1:
        raise ValueError("daily_counts must be one-dimensional.")
    if daily.size % days_per_month != 0:
        raise ValueError("daily_counts length must be divisible by days_per_month.")
    return daily.reshape(daily.size // days_per_month, days_per_month).sum(axis=1, dtype=np.int32)


def longest_zero_run(daily_counts: np.ndarray) -> int:
    """Return the longest consecutive run of zero-count days."""

    longest = 0
    current = 0
    for count in np.asarray(daily_counts):
        if int(count) <= 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def find_first_eligible_window(
    monthly_counts: np.ndarray,
    daily_counts: np.ndarray,
    threshold: int = 4,
    monthly_min: int = DEFAULT_MONTHLY_MIN,
    max_seizure_free_days: int = DEFAULT_MAX_SEIZURE_FREE_DAYS,
    days_per_month: int = DAYS_PER_MONTH,
) -> int:
    """Find the first 2-month baseline window satisfying the eligibility rule."""

    monthly = np.asarray(monthly_counts, dtype=float)
    daily = np.asarray(daily_counts, dtype=np.int32)
    if monthly.ndim != 1:
        raise ValueError("monthly_counts must be one-dimensional.")
    if daily.ndim != 1:
        raise ValueError("daily_counts must be one-dimensional.")
    if daily.size < monthly.size * days_per_month:
        raise ValueError("daily_counts is shorter than monthly_counts imply.")

    max_start = monthly.size - BASELINE_MONTHS - TEST_MONTHS
    if max_start < 0:
        return -1

    for start_month in range(max_start + 1):
        baseline_months = monthly[start_month : start_month + BASELINE_MONTHS]
        if float(np.mean(baseline_months)) < float(threshold):
            continue
        if np.any(baseline_months < monthly_min):
            continue
        day_start = start_month * days_per_month
        day_stop = (start_month + BASELINE_MONTHS) * days_per_month
        if longest_zero_run(daily[day_start:day_stop]) > max_seizure_free_days:
            continue
        return int(start_month)
    return -1


def percent_change(baseline_mean: float, test_mean: float) -> float:
    """Compute patient-level percentage change with baseline-zero protection."""

    if baseline_mean <= EPSILON:
        return float("nan")
    return float(100.0 * (1.0 - test_mean / baseline_mean))


def rtm_occurs(baseline_mean: float, test_mean: float, reference_mean: float) -> bool:
    """Evaluate the RTM definition used in the RTM papers."""

    return bool(
        baseline_mean > reference_mean
        and (baseline_mean - reference_mean) > abs(test_mean - reference_mean)
    )


def rtm_from_totals(
    baseline_numerator: int,
    test_numerator: int,
    reference_total: int,
    reference_months: int,
    sensitivity: float = 1.0,
    count_denominator: int = 1,
) -> bool:
    """Strict RTM comparison in integer arithmetic, including exact ties.

    Trial totals are count numerators divided by count_denominator. The
    reference is the finite true diary rate scaled by sensitivity. Fractions
    allow exact monthly correction at rates such as one false alarm/week.
    """
    scale = Fraction(str(sensitivity)).limit_denominator(1_000_000)
    denominator = reference_months * scale.denominator
    ref = int(reference_total) * scale.numerator * count_denominator
    b_distance = int(baseline_numerator) * denominator - BASELINE_MONTHS * ref
    t_distance = int(test_numerator) * denominator - TEST_MONTHS * ref
    return b_distance > 0 and TEST_MONTHS * b_distance > BASELINE_MONTHS * abs(t_distance)


def paired_rtm_at_window(
    measured_monthly: np.ndarray,
    true_monthly: np.ndarray,
    first_start: int,
    sensitivity: float,
    far_per_day: float,
    days_per_month: int,
) -> dict[str, object]:
    """Compare both scales for the same selected person and trial window.

    No additional true-count eligibility filter is applied. Type 3 is the
    measured-only classification, not a difference between condition means.
    """
    months = len(true_monthly)
    true_total = int(np.sum(true_monthly, dtype=np.int64))
    reference = sensitivity * true_total / months
    result = {"reference": reference, "true_reference": true_total / months,
              "rtm": False, "true_rtm": False, "type3_rtm": False,
              "true_only_rtm": False, "both_rtm": False,
              "baseline": float("nan"), "test": float("nan"),
              "true_baseline": float("nan"), "true_test": float("nan"),
              "pc": float("nan")}
    if first_start < 0:
        return result
    correction = Fraction(str(far_per_day)).limit_denominator(1_000_000) * days_per_month
    q = correction.denominator
    measured_numerators = np.rint(np.asarray(measured_monthly) * q).astype(np.int64)
    b = slice(first_start, first_start + BASELINE_MONTHS)
    t = slice(first_start + BASELINE_MONTHS, first_start + BASELINE_MONTHS + TEST_MONTHS)
    bn, tn = int(measured_numerators[b].sum()), int(measured_numerators[t].sum())
    bt, tt = int(true_monthly[b].sum()), int(true_monthly[t].sum())
    measured_rtm = rtm_from_totals(bn, tn, true_total, months, sensitivity, q)
    true_rtm = rtm_from_totals(bt, tt, true_total, months)
    baseline, test = bn / q / BASELINE_MONTHS, tn / q / TEST_MONTHS
    result.update(rtm=measured_rtm, true_rtm=true_rtm,
                  type3_rtm=measured_rtm and not true_rtm,
                  true_only_rtm=true_rtm and not measured_rtm,
                  both_rtm=measured_rtm and true_rtm,
                  baseline=baseline, test=test,
                  true_baseline=bt / BASELINE_MONTHS, true_test=tt / TEST_MONTHS,
                  pc=percent_change(baseline, test))
    return result


def binomial_ci(k: int, n: int) -> tuple[float, float]:
    """Wilson 95% confidence interval for a binomial proportion."""

    if n <= 0:
        return float("nan"), float("nan")
    z = 1.959963984540054
    p_hat = k / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z * z / (4.0 * n * n))) / denom
    return max(0.0, center - half), min(1.0, center + half)


def median_with_ci(values: np.ndarray) -> tuple[float, float, float]:
    """Median and approximate nonparametric 95% confidence interval."""

    finite = np.sort(np.asarray(values, dtype=float)[np.isfinite(values)])
    n_values = finite.size
    if n_values == 0:
        return float("nan"), float("nan"), float("nan")
    if n_values == 1:
        value = float(finite[0])
        return value, value, value
    lower_index = max(0, int(math.floor(0.5 * n_values - 0.98 * math.sqrt(n_values))) - 1)
    upper_index = min(n_values - 1, int(math.ceil(0.5 * n_values + 0.98 * math.sqrt(n_values))))
    return float(np.median(finite)), float(finite[lower_index]), float(finite[upper_index])


def cohort_paths(cohort_dir: str | Path) -> dict[str, Path]:
    """Return standard paths for one cohort directory."""

    directory = Path(cohort_dir)
    return {
        "metadata": directory / "cohort_metadata.json",
        "daily_counts": directory / "daily_counts.int16.memmap",
        "latent_msf": directory / "latent_msf.npy",
        "seeds": directory / "patient_seeds.npy",
    }


def write_json(path: str | Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _simulate_seed_chunk(
    seeds: np.ndarray,
    months: int,
    days_per_month: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate a chunk of CHOCOLATES diaries from patient-level seeds."""

    seed_values = np.asarray(seeds, dtype=np.int64)
    days_needed = months * days_per_month
    daily_counts = np.empty((seed_values.size, days_needed), dtype=np.int16)
    latent_rates = np.empty(seed_values.size, dtype=np.float32)

    for row, seed in enumerate(seed_values):
        rng = np.random.default_rng(int(seed))
        daily, latent = simple_chocolates(days_needed=days_needed, rng=rng)
        daily_counts[row, :] = np.asarray(daily, dtype=np.int16)
        latent_rates[row] = float(np.asarray(latent).item())
    return daily_counts, latent_rates


def split_array(values: np.ndarray, chunk_size: int) -> list[np.ndarray]:
    """Split an array into fixed-size chunks."""

    return [values[start : start + chunk_size] for start in range(0, values.size, chunk_size)]


def generate_common_cohort(
    output_dir: str | Path,
    n_patients: int = 1_000_000,
    months: int = DEFAULT_MONTHS,
    days_per_month: int = DAYS_PER_MONTH,
    chunk_size: int = 512,
    workers: int | str | None = 1,
    master_seed: int = DEFAULT_MASTER_SEED,
    resume: bool = True,
    progress: Callable[[str], None] | None = print,
) -> CohortInfo:
    """Create or resume the shared true-seizure cohort."""

    if months < BASELINE_MONTHS + TEST_MONTHS:
        raise ValueError("months must leave room for a 2-month baseline and 3-month test period.")
    if n_patients < 1:
        raise ValueError("n_patients must be positive.")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive.")

    worker_count = parse_workers(workers)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = cohort_paths(directory)
    days_needed = months * days_per_month

    reset = not resume or not paths["metadata"].exists()
    if reset:
        seed_rng = np.random.default_rng(master_seed)
        seeds = seed_rng.integers(
            low=0,
            high=np.iinfo(np.int64).max,
            size=n_patients,
            dtype=np.int64,
        )
        np.save(paths["seeds"], seeds)
        daily = np.memmap(
            paths["daily_counts"],
            dtype=np.int16,
            mode="w+",
            shape=(n_patients, days_needed),
        )
        latent = np.lib.format.open_memmap(
            paths["latent_msf"],
            mode="w+",
            dtype=np.float32,
            shape=(n_patients,),
        )
        daily.flush()
        latent.flush()
        metadata = {
            "n_patients": int(n_patients),
            "months": int(months),
            "days_per_month": int(days_per_month),
            "days": int(days_needed),
            "master_seed": int(master_seed),
            "completed_patients": 0,
            "created_unix_time": time.time(),
            "chocolate_repo": str(chocolate_repo_path()),
            "simulator": "CHOCOLATES/simple_CHOCOLATES",
            "generation_fingerprint": generation_fingerprint(),
        }
        write_json(paths["metadata"], metadata)
    else:
        metadata = read_json(paths["metadata"])
        expected = {
            "n_patients": int(n_patients),
            "months": int(months),
            "days_per_month": int(days_per_month),
            "master_seed": int(master_seed),
        }
        for key, value in expected.items():
            if int(metadata[key]) != value:
                raise ValueError(f"Existing cohort {key}={metadata[key]} does not match requested {value}.")
        seeds = np.load(paths["seeds"])
        daily = np.memmap(
            paths["daily_counts"],
            dtype=np.int16,
            mode="r+",
            shape=(n_patients, days_needed),
        )
        latent = np.load(paths["latent_msf"], mmap_mode="r+")

    completed = int(metadata.get("completed_patients", 0))
    if completed < 0 or completed > n_patients:
        raise ValueError("Cohort completion count is invalid.")
    if completed < n_patients and metadata.get("generation_fingerprint") != generation_fingerprint():
        raise ValueError("Cannot resume cohort generation with missing or changed simulator provenance.")
    if completed >= n_patients:
        if progress:
            progress(f"Cohort already complete: {n_patients:,} patients in {directory}.")
        return CohortInfo(
            cohort_dir=directory,
            n_patients=n_patients,
            months=months,
            days_per_month=days_per_month,
            completed_patients=n_patients,
            daily_counts_path=paths["daily_counts"],
            latent_msf_path=paths["latent_msf"],
            seeds_path=paths["seeds"],
            metadata_path=paths["metadata"],
        )

    batch_size = max(chunk_size, chunk_size * worker_count)
    executor: ProcessPoolExecutor | None = None
    if worker_count > 1:
        executor = ProcessPoolExecutor(max_workers=worker_count)

    try:
        for start in range(completed, n_patients, batch_size):
            stop = min(n_patients, start + batch_size)
            batch_seeds = seeds[start:stop]
            if executor is None:
                batch_daily, batch_latent = _simulate_seed_chunk(batch_seeds, months, days_per_month)
            else:
                futures = [
                    executor.submit(_simulate_seed_chunk, seed_chunk, months, days_per_month)
                    for seed_chunk in split_array(batch_seeds, chunk_size)
                ]
                results = [future.result() for future in futures]
                batch_daily = np.concatenate([result[0] for result in results], axis=0)
                batch_latent = np.concatenate([result[1] for result in results], axis=0)

            daily[start:stop, :] = batch_daily
            latent[start:stop] = batch_latent
            daily.flush()
            latent.flush()
            metadata["completed_patients"] = int(stop)
            metadata["updated_unix_time"] = time.time()
            write_json(paths["metadata"], metadata)
            if progress:
                progress(f"Generated common cohort patients {stop:,}/{n_patients:,}.")
    finally:
        if executor is not None:
            executor.shutdown(wait=True)

    return CohortInfo(
        cohort_dir=directory,
        n_patients=n_patients,
        months=months,
        days_per_month=days_per_month,
        completed_patients=n_patients,
        daily_counts_path=paths["daily_counts"],
        latent_msf_path=paths["latent_msf"],
        seeds_path=paths["seeds"],
        metadata_path=paths["metadata"],
    )


def load_cohort(cohort_dir: str | Path) -> tuple[dict, np.memmap, np.ndarray, np.ndarray]:
    """Load a common cohort as metadata, daily memmap, latent rates, and seeds."""

    paths = cohort_paths(cohort_dir)
    metadata = read_json(paths["metadata"])
    n_patients = int(metadata["n_patients"])
    days = int(metadata["days"])
    completed = int(metadata.get("completed_patients", 0))
    if n_patients < 1 or days != int(metadata["months"]) * int(metadata["days_per_month"]):
        raise ValueError("Cohort dimensions are invalid.")
    if completed != n_patients:
        raise ValueError(f"Cohort is incomplete: {completed}/{n_patients} patients generated.")
    if paths["daily_counts"].stat().st_size != n_patients * days * np.dtype(np.int16).itemsize:
        raise ValueError("Daily cohort file size does not match the recorded dimensions.")
    daily = np.memmap(paths["daily_counts"], dtype=np.int16, mode="r", shape=(n_patients, days))
    latent = np.load(paths["latent_msf"], mmap_mode="r")
    seeds = np.load(paths["seeds"], mmap_mode="r")
    if latent.shape != (n_patients,) or latent.dtype != np.dtype(np.float32):
        raise ValueError("Latent-rate cohort array has the wrong shape or dtype.")
    if seeds.shape != (n_patients,) or seeds.dtype != np.dtype(np.int64):
        raise ValueError("Patient-seed cohort array has the wrong shape or dtype.")
    return metadata, daily, latent, seeds


def apply_detector(
    true_daily: np.ndarray,
    sensitivity: float = 1.0,
    far_per_day: float = 0.0,
    rng: np.random.Generator | None = None,
    correct_far: bool = True,
    days_per_month: int = DAYS_PER_MONTH,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply detector sensitivity and FAR.

    Returns a daily count series for the daily eligibility rule and corrected
    monthly counts for eligibility, reference, baseline, and test summaries.
    """

    if rng is None:
        rng = np.random.default_rng()
    true_counts = np.asarray(true_daily, dtype=np.int32)
    if sensitivity < 0 or sensitivity > 1:
        raise ValueError("sensitivity must be in [0, 1].")
    if far_per_day < 0:
        raise ValueError("far_per_day must be nonnegative.")

    if sensitivity >= 1.0:
        detected = true_counts.copy()
    elif sensitivity <= 0.0:
        detected = np.zeros_like(true_counts, dtype=np.int32)
    else:
        detected = rng.binomial(true_counts, sensitivity).astype(np.int32)

    if far_per_day > 0.0:
        observed = detected + rng.poisson(far_per_day, size=true_counts.shape).astype(np.int32)
    else:
        observed = detected

    monthly = monthly_from_daily(observed, days_per_month=days_per_month).astype(float)
    daily_for_eligibility = observed.astype(np.int32, copy=True)

    if correct_far and far_per_day > 0.0:
        monthly_remover = float(Fraction(str(far_per_day)).limit_denominator(1_000_000) * days_per_month)
        monthly = np.maximum(monthly - monthly_remover, 0.0)
        daily_remover = int(np.round(far_per_day))
        if daily_remover > 0:
            daily_for_eligibility = np.maximum(daily_for_eligibility - daily_remover, 0).astype(np.int32)

    return daily_for_eligibility.astype(np.int16), monthly


def build_type1_diary(
    true_daily: np.ndarray,
    original_msf: float,
    seed: int,
    months: int = DEFAULT_MONTHS,
    days_per_month: int = DAYS_PER_MONTH,
    shock_start_month: int | None = None,
    shock_msf: float | None = None,
) -> tuple[np.ndarray, int, float]:
    """Replace one two-month interval with a newly sampled CHOCOLATES mSF segment."""

    if months < 2:
        raise ValueError("months must be at least 2 for the Type 1 shock.")
    rng = np.random.default_rng(stable_seed("type1", int(seed)))
    max_start = months - 2
    if shock_start_month is None:
        shock_start_month = int(rng.integers(0, max_start + 1))
    if not 0 <= shock_start_month <= max_start:
        raise ValueError("shock_start_month must allow a full two-month interval.")
    if shock_msf is None:
        shock_msf = sample_msf(rng)
    else:
        shock_msf = float(shock_msf)

    _ = original_msf
    replacement, _new_msf = simple_chocolates(
        days_needed=BASELINE_MONTHS * days_per_month,
        rng=rng,
        default_msf=shock_msf,
    )
    modified = np.asarray(true_daily, dtype=np.int16).copy()
    day_start = shock_start_month * days_per_month
    day_stop = day_start + BASELINE_MONTHS * days_per_month
    modified[day_start:day_stop] = np.asarray(replacement, dtype=np.int16)
    return modified, int(shock_start_month), float(shock_msf)


def evaluate_patient(
    true_daily: np.ndarray,
    latent_msf: float,
    seed: int,
    spec: ConditionSpec,
    months: int,
    days_per_month: int,
    monthly_min: int,
    max_seizure_free_days: int,
    fixed_first_start: int | None = None,
) -> dict[str, float | int | bool]:
    """Evaluate one patient under one condition."""

    patient_daily = np.asarray(true_daily, dtype=np.int16)
    shock_start = -1
    shock_msf = float("nan")
    if spec.type1_intervention:
        patient_daily, shock_start, shock_msf = build_type1_diary(
            patient_daily,
            original_msf=float(latent_msf),
            seed=int(seed),
            months=months,
            days_per_month=days_per_month,
        )

    detector_rng = np.random.default_rng(stable_seed("detector", spec.name, int(seed)))
    daily_for_eligibility, monthly_counts = apply_detector(
        patient_daily,
        sensitivity=spec.sensitivity,
        far_per_day=spec.far_per_day,
        rng=detector_rng,
        correct_far=spec.correct_far,
        days_per_month=days_per_month,
    )
    first_start = find_first_eligible_window(
        monthly_counts,
        daily_for_eligibility,
        threshold=spec.threshold,
        monthly_min=monthly_min,
        max_seizure_free_days=max_seizure_free_days,
        days_per_month=days_per_month,
    )
    if not spec.correct_far:
        raise ValueError("The paired Type 3 protocol requires expected-alarm-corrected counts.")
    true_monthly = monthly_from_daily(patient_daily, days_per_month)
    paired = paired_rtm_at_window(monthly_counts, true_monthly, first_start,
                                 spec.sensitivity, spec.far_per_day, days_per_month)
    fixed_start = first_start if fixed_first_start is None else fixed_first_start
    fixed = paired_rtm_at_window(monthly_counts, true_monthly, fixed_start,
                                spec.sensitivity, spec.far_per_day, days_per_month)
    return {"eligible": first_start >= 0, "first_start": int(first_start),
            "shock_start": shock_start, "shock_msf": shock_msf, **paired,
            "fixed_eligible": fixed_start >= 0, "fixed_first_start": fixed_start,
            "fixed_rtm": fixed["rtm"], "fixed_pc": fixed["pc"],
            "fixed_type3_rtm": fixed["type3_rtm"],
            "fixed_baseline": fixed["baseline"]}


def empty_condition_arrays(n_patients: int) -> dict[str, np.ndarray]:
    """Allocate compact per-patient condition arrays."""

    arrays = {
        "eligible": np.zeros(n_patients, dtype=bool),
        "first_start": np.full(n_patients, -1, dtype=np.int16),
        "rtm": np.zeros(n_patients, dtype=bool),
        "pc": np.full(n_patients, np.nan, dtype=np.float64),
        "baseline": np.full(n_patients, np.nan, dtype=np.float64),
        "test": np.full(n_patients, np.nan, dtype=np.float64),
        "reference": np.full(n_patients, np.nan, dtype=np.float64),
        "shock_start": np.full(n_patients, -1, dtype=np.int16),
        "shock_msf": np.full(n_patients, np.nan, dtype=np.float32),
    }
    for key in ("true_rtm", "type3_rtm", "true_only_rtm", "both_rtm", "fixed_eligible",
                "fixed_rtm", "fixed_type3_rtm"):
        arrays[key] = np.zeros(n_patients, dtype=bool)
    for key in ("true_reference", "true_baseline", "true_test", "fixed_pc", "fixed_baseline"):
        arrays[key] = np.full(n_patients, np.nan, dtype=np.float64)
    arrays["fixed_first_start"] = np.full(n_patients, -1, dtype=np.int16)
    return arrays


def fill_condition_arrays(arrays: dict[str, np.ndarray], row: int, result: dict[str, object]) -> None:
    """Insert one patient result into preallocated arrays."""

    for key in arrays:
        arrays[key][row] = result[key]


def summarize_condition(spec: ConditionSpec, arrays: dict[str, np.ndarray], n_raw: int) -> dict[str, object]:
    """Summarize one condition from per-patient arrays."""

    eligible = arrays["eligible"]
    n_eligible = int(np.sum(eligible))
    rtm_count = int(np.sum(arrays["rtm"][eligible])) if n_eligible else 0
    rtm_fraction = float(rtm_count / n_eligible) if n_eligible else float("nan")
    rtm_lo, rtm_hi = binomial_ci(rtm_count, n_eligible) if n_eligible else (float("nan"), float("nan"))
    paired_counts = {name: int(np.sum(arrays[key][eligible])) for name, key in
                     (("true_rtm", "true_rtm"), ("type3", "type3_rtm"),
                      ("true_only", "true_only_rtm"), ("both", "both_rtm"))}
    neither = n_eligible - paired_counts["both"] - paired_counts["type3"] - paired_counts["true_only"]
    type3_lo, type3_hi = binomial_ci(paired_counts["type3"], n_eligible)
    fixed_eligible = arrays["fixed_eligible"]
    n_fixed = int(np.sum(fixed_eligible))
    fixed_mpc, fixed_mpc_lo, fixed_mpc_hi = median_with_ci(arrays["fixed_pc"][fixed_eligible])
    mpc, mpc_lo, mpc_hi = median_with_ci(arrays["pc"][eligible]) if n_eligible else (
        float("nan"),
        float("nan"),
        float("nan"),
    )
    return {
        "condition": spec.name,
        "label": spec.label,
        "rtm_type": spec.rtm_type,
        "threshold": spec.threshold,
        "sensitivity": spec.sensitivity,
        "far_per_day": spec.far_per_day,
        "far_label": spec.far_label,
        "correct_far": spec.correct_far,
        "type1_intervention": spec.type1_intervention,
        "n_raw": int(n_raw),
        "n_eligible": n_eligible,
        "fraction_eligible": float(n_eligible / n_raw) if n_raw else float("nan"),
        "rtm_count": rtm_count,
        "true_rtm_count": paired_counts["true_rtm"],
        "type3_count": paired_counts["type3"],
        "true_only_count": paired_counts["true_only"],
        "both_count": paired_counts["both"],
        "neither_count": neither,
        "fraction_true_RTM": paired_counts["true_rtm"] / n_eligible if n_eligible else float("nan"),
        "fraction_type3": paired_counts["type3"] / n_eligible if n_eligible else float("nan"),
        "fraction_type3_ci_lo": type3_lo,
        "fraction_type3_ci_hi": type3_hi,
        "type3_share_measured_RTM": paired_counts["type3"] / rtm_count if rtm_count else float("nan"),
        "net_measurement_difference_pp": 100 * (paired_counts["type3"] - paired_counts["true_only"]) / n_eligible if n_eligible else float("nan"),
        "n_mpc": int(np.sum(np.isfinite(arrays["pc"][eligible]))),
        "n_fixed": n_fixed,
        "fixed_fraction_RTM": float(np.sum(arrays["fixed_rtm"][fixed_eligible])) / n_fixed if n_fixed else float("nan"),
        "fixed_fraction_type3": float(np.sum(arrays["fixed_type3_rtm"][fixed_eligible])) / n_fixed if n_fixed else float("nan"),
        "fixed_n_zero_baseline": int(np.sum(arrays["fixed_baseline"][fixed_eligible] == 0)),
        "fixed_n_mpc": int(np.sum(np.isfinite(arrays["fixed_pc"][fixed_eligible]))),
        "fixed_MPC": fixed_mpc, "fixed_MPC_ci_lo": fixed_mpc_lo, "fixed_MPC_ci_hi": fixed_mpc_hi,
        "fraction_RTM": rtm_fraction,
        "fraction_RTM_ci_lo": rtm_lo,
        "fraction_RTM_ci_hi": rtm_hi,
        "MPC": mpc,
        "MPC_ci_lo": mpc_lo,
        "MPC_ci_hi": mpc_hi,
        "baseline_mean": float(np.nanmean(arrays["baseline"][eligible])) if n_eligible else float("nan"),
        "test_mean": float(np.nanmean(arrays["test"][eligible])) if n_eligible else float("nan"),
        "reference_mean": float(np.nanmean(arrays["reference"][eligible])) if n_eligible else float("nan"),
        "median_first_eligible_month": float(np.median(arrays["first_start"][eligible])) if n_eligible else float("nan"),
    }


def first_eligible_window_rows(spec: ConditionSpec, arrays: dict[str, np.ndarray]) -> list[dict[str, object]]:
    """Build aggregate rows for the first eligible month distribution."""

    first_start = arrays["first_start"]
    n_raw = first_start.size
    rows: list[dict[str, object]] = []
    for month in sorted(int(value) for value in np.unique(first_start)):
        count = int(np.sum(first_start == month))
        rows.append(
            {
                "condition": spec.name,
                "label": spec.label,
                "first_eligible_month": month,
                "n_patients": count,
                "fraction_raw": float(count / n_raw) if n_raw else float("nan"),
            }
        )
    return rows


def intervals_overlap(start_a: int, stop_a: int, start_b: int, stop_b: int) -> bool:
    """Return whether two half-open intervals overlap."""

    return start_a < stop_b and start_b < stop_a


def type1_overlap_label(shock_start: int, first_start: int) -> str:
    """Classify where a Type 1 shock falls relative to the trial window."""

    if first_start < 0:
        return "not_eligible"
    shock_stop = shock_start + BASELINE_MONTHS
    baseline_start = first_start
    baseline_stop = first_start + BASELINE_MONTHS
    test_start = baseline_stop
    test_stop = test_start + TEST_MONTHS
    overlaps_baseline = intervals_overlap(shock_start, shock_stop, baseline_start, baseline_stop)
    overlaps_test = intervals_overlap(shock_start, shock_stop, test_start, test_stop)
    if overlaps_baseline and overlaps_test:
        return "baseline_and_test"
    if overlaps_baseline:
        return "baseline"
    if overlaps_test:
        return "test"
    return "neither"


def type1_overlap_rows(
    spec: ConditionSpec,
    arrays: dict[str, np.ndarray],
    original_msf: np.ndarray,
) -> list[dict[str, object]]:
    """Summarize Type 1 outcomes by shock-overlap stratum."""

    if not spec.type1_intervention:
        return []
    shock_start = arrays["shock_start"]
    first_start = arrays["first_start"]
    eligible = arrays["eligible"]
    shock_msf = arrays["shock_msf"]
    original = np.asarray(original_msf, dtype=float)

    overlap = np.asarray(
        [type1_overlap_label(int(s), int(f)) for s, f in zip(shock_start, first_start)],
        dtype=object,
    )
    relation = np.full(shock_start.size, "equal", dtype=object)
    relation[shock_msf > original] = "higher"
    relation[shock_msf < original] = "lower"
    relation[~np.isfinite(shock_msf)] = "unknown"

    rows: list[dict[str, object]] = []
    group_keys = [("all", "all")]
    group_keys.extend((str(o), "all") for o in sorted(set(overlap)))
    group_keys.extend((str(o), str(r)) for o in sorted(set(overlap)) for r in sorted(set(relation)))

    seen: set[tuple[str, str]] = set()
    for overlap_key, relation_key in group_keys:
        if (overlap_key, relation_key) in seen:
            continue
        seen.add((overlap_key, relation_key))
        mask = np.ones(shock_start.size, dtype=bool)
        if overlap_key != "all":
            mask &= overlap == overlap_key
        if relation_key != "all":
            mask &= relation == relation_key
        n_raw = int(np.sum(mask))
        if n_raw == 0:
            continue
        group_eligible = mask & eligible
        n_eligible = int(np.sum(group_eligible))
        rtm_count = int(np.sum(arrays["rtm"][group_eligible])) if n_eligible else 0
        rows.append(
            {
                "condition": spec.name,
                "overlap": overlap_key,
                "shock_msf_relation": relation_key,
                "n_raw": n_raw,
                "n_eligible": n_eligible,
                "fraction_eligible": float(n_eligible / n_raw),
                "fraction_RTM": float(rtm_count / n_eligible) if n_eligible else float("nan"),
                "MPC": float(np.nanmedian(arrays["pc"][group_eligible])) if n_eligible else float("nan"),
            }
        )
    return rows


def write_csv(path: str | Path, rows: Iterable[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    """Write dictionaries to CSV with stable field ordering."""

    row_list = list(rows)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in row_list:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in row_list:
            writer.writerow(row)


def read_csv_dicts(path: str | Path) -> list[dict[str, str]]:
    """Read a CSV into a list of dictionaries."""

    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def git_sha(repo_root: Path) -> str:
    """Return the current git SHA or `unknown`."""

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _evaluate_condition_chunk(payload: tuple) -> tuple[int, dict[str, np.ndarray]]:
    cohort_dir, spec, start, stop, monthly_min, max_zero, fixed_starts = payload
    metadata, daily, latent, seeds = load_cohort(cohort_dir)
    arrays = empty_condition_arrays(stop - start)
    for offset, row in enumerate(range(start, stop)):
        result = evaluate_patient(
            daily[row, :], float(latent[row]), int(seeds[row]), spec,
            int(metadata["months"]), int(metadata["days_per_month"]), monthly_min, max_zero,
            None if fixed_starts is None else int(fixed_starts[offset]))
        fill_condition_arrays(arrays, offset, result)
    return start, arrays


def _condition_cache_metadata(
    spec: ConditionSpec, metadata: dict, cohort_content: dict,
    monthly_min: int, max_seizure_free_days: int,
) -> dict[str, object]:
    return {
        "analysis_version": ANALYSIS_VERSION,
        "condition": asdict(spec),
        "monthly_min": monthly_min,
        "max_seizure_free_days": max_seizure_free_days,
        "source_sha256": file_sha256(__file__),
        "numpy_version": np.__version__,
        "cohort_metadata": metadata,
        "cohort_content": cohort_content,
        "simulator": simulator_fingerprint() if spec.type1_intervention else None,
        "fixed_enrollment_dependency": None,
    }


def _read_condition_cache(
    path: Path, expected_metadata: dict, n_patients: int,
) -> dict[str, np.ndarray] | None:
    """Read a complete compatible cache, or return None so it can be rebuilt."""

    try:
        with np.load(path, allow_pickle=False) as loaded:
            if json.loads(str(loaded["cache_json"])) != expected_metadata:
                return None
            if json.loads(str(loaded["condition_json"])) != expected_metadata["condition"]:
                return None
            schema = empty_condition_arrays(0)
            if set(loaded.files) != set(schema) | {"condition_json", "cache_json"}:
                return None
            arrays = {key: loaded[key] for key in schema}
            if any(value.shape != (n_patients,) or value.dtype != schema[key].dtype
                   for key, value in arrays.items()):
                return None
            months = int(expected_metadata["cohort_metadata"]["months"])
            for prefix in ("", "fixed_"):
                starts = arrays[prefix + "first_start"]
                if (np.any(starts < -1)
                        or np.any(starts > months - BASELINE_MONTHS - TEST_MONTHS)
                        or not np.array_equal(arrays[prefix + "eligible"], starts >= 0)):
                    return None
            return arrays
    except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile):
        return None


def run_condition(
    cohort_dir: str | Path,
    output_dir: str | Path,
    spec: ConditionSpec,
    chunk_size: int = 512,
    monthly_min: int = DEFAULT_MONTHLY_MIN,
    max_seizure_free_days: int = DEFAULT_MAX_SEIZURE_FREE_DAYS,
    resume: bool = True,
    progress: Callable[[str], None] | None = print,
    workers: int = 1,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    """Run one condition against the shared cohort and save per-patient flags."""

    metadata, daily, latent, seeds = load_cohort(cohort_dir)
    n_patients = int(metadata["n_patients"])
    months = int(metadata["months"])
    days_per_month = int(metadata["days_per_month"])
    destination = Path(output_dir)
    flags_dir = destination / "patient_condition_flags"
    flags_dir.mkdir(parents=True, exist_ok=True)
    flags_path = flags_dir / f"{spec.name}.npz"

    if chunk_size < 1 or workers < 1:
        raise ValueError("chunk_size and workers must be positive.")
    cohort_content = cohort_fingerprint(cohort_dir)
    cache_metadata = _condition_cache_metadata(
        spec, metadata, cohort_content, monthly_min, max_seizure_free_days)
    fixed_starts = None
    if spec.rtm_type.startswith("type3"):
        baseline_spec = default_condition_specs()[0]
        expected_baseline = _condition_cache_metadata(
            baseline_spec, metadata, cohort_content, monthly_min, max_seizure_free_days)
        baseline = _read_condition_cache(flags_dir / "baseline_perfect.npz", expected_baseline, n_patients)
        if baseline is None:
            raise ValueError("Perfect-detector enrollment cache is missing, incompatible or incomplete; "
                             "rerun baseline_perfect with the same cohort and eligibility rules.")
        fixed_starts = baseline["first_start"]
        cache_metadata["fixed_enrollment_dependency"] = {
            "cache_metadata_sha256": hashlib.sha256(
                json.dumps(expected_baseline, sort_keys=True).encode()).hexdigest(),
            "first_start_sha256": hashlib.sha256(fixed_starts.tobytes()).hexdigest(),
            "eligible_sha256": hashlib.sha256(baseline["eligible"].tobytes()).hexdigest(),
        }
        del baseline
    cache_json = json.dumps(cache_metadata, sort_keys=True)
    arrays = _read_condition_cache(flags_path, cache_metadata, n_patients) if resume else None
    if arrays is not None:
        if progress:
            progress(f"Loaded existing condition flags for {spec.name}.")
    else:
        arrays = empty_condition_arrays(n_patients)
        payloads = [(str(cohort_dir), spec, start, min(n_patients, start + chunk_size),
                     monthly_min, max_seizure_free_days,
                     None if fixed_starts is None else fixed_starts[start:start + chunk_size])
                    for start in range(0, n_patients, chunk_size)]
        executor = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
        try:
            results = executor.map(_evaluate_condition_chunk, payloads) if executor else map(_evaluate_condition_chunk, payloads)
            for start, chunk in results:
                stop = start + len(chunk["eligible"])
                for key in arrays:
                    arrays[key][start:stop] = chunk[key]
                if progress and (stop == n_patients or stop % (20 * chunk_size) == 0):
                    progress(f"{spec.name}: processed {stop:,}/{n_patients:,} patients.")
        finally:
            if executor:
                executor.shutdown(wait=True)
        np.savez_compressed(
            flags_path,
            **arrays,
            condition_json=np.asarray(json.dumps(asdict(spec), sort_keys=True)),
            cache_json=np.asarray(cache_json),
        )

    summary = summarize_condition(spec, arrays, n_raw=n_patients)
    return summary, first_eligible_window_rows(spec, arrays), type1_overlap_rows(spec, arrays, latent)


def run_all_conditions(
    cohort_dir: str | Path,
    output_dir: str | Path,
    condition_specs: list[ConditionSpec] | None = None,
    chunk_size: int = 512,
    resume: bool = True,
    progress: Callable[[str], None] | None = print,
    workers: int = 1,
) -> dict[str, Path]:
    """Run all planned RTM123 conditions and write summary artifacts."""

    specs = default_condition_specs() if condition_specs is None else condition_specs
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    first_window_rows: list[dict[str, object]] = []
    type1_rows_all: list[dict[str, object]] = []
    for spec in specs:
        summary, window_rows, type1_rows_for_spec = run_condition(
            cohort_dir=cohort_dir,
            output_dir=destination,
            spec=spec,
            chunk_size=chunk_size,
            resume=resume,
            progress=progress,
            workers=workers,
        )
        summaries.append(summary)
        first_window_rows.extend(window_rows)
        type1_rows_all.extend(type1_rows_for_spec)

    paths = {
        "condition_summary": destination / "condition_summary.csv",
        "first_eligible_windows": destination / "first_eligible_windows.csv",
        "type1_overlap_summary": destination / "type1_overlap_summary.csv",
        "manifest": destination / "run_manifest.json",
    }
    write_csv(paths["condition_summary"], summaries)
    write_csv(paths["first_eligible_windows"], first_window_rows)
    write_csv(paths["type1_overlap_summary"], type1_rows_all)

    metadata = read_json(cohort_paths(cohort_dir)["metadata"])
    write_json(
        paths["manifest"],
        {
            "completed": True,
            "analysis_version": ANALYSIS_VERSION,
            "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "numpy_version": np.__version__,
            "cohort_content": cohort_fingerprint(cohort_dir),
            "cohort_generation_fingerprint": metadata.get("generation_fingerprint"),
            "transient_simulator": simulator_fingerprint() if any(s.type1_intervention for s in specs) else None,
            "type3_definition": "measured RTM and not true-count RTM in the same detector-selected participant and trial window",
            "reference": "finite true full-diary monthly mean; scaled by sensitivity for corrected measured counts",
            "fixed_comparison": "perfect-detector enrollment and baseline windows retained; zero measured baselines excluded only from MPC",
            "cohort_dir": str(Path(cohort_dir).resolve()),
            "output_dir": str(destination.resolve()),
            "conditions": [asdict(spec) for spec in specs],
            "cohort_metadata": metadata,
            "git_sha": git_sha(project_root()),
            "python_version": sys.version,
            "platform": platform.platform(),
            "updated_unix_time": time.time(),
        },
    )
    return paths


def to_float(row: dict[str, str], key: str) -> float:
    """Read a float from a CSV row."""

    try:
        return float(row[key])
    except Exception:
        return float("nan")


def make_tables(input_dir: str | Path) -> dict[str, Path]:
    """Create paper-facing CSV tables and delta columns."""

    directory = Path(input_dir)
    rows = read_csv_dicts(directory / "condition_summary.csv")
    baseline = next((row for row in rows if row.get("condition") == "baseline_perfect"), None)
    if baseline is None:
        raise ValueError("condition_summary.csv does not contain baseline_perfect.")

    base_fraction_eligible = to_float(baseline, "fraction_eligible")
    base_fraction_rtm = to_float(baseline, "fraction_RTM")
    base_mpc = to_float(baseline, "MPC")
    enriched: list[dict[str, object]] = []
    paper_rows: list[dict[str, object]] = []
    for row in rows:
        fraction_eligible = to_float(row, "fraction_eligible")
        fraction_rtm = to_float(row, "fraction_RTM")
        mpc = to_float(row, "MPC")
        enriched_row: dict[str, object] = dict(row)
        enriched_row["delta_fraction_eligible_vs_baseline"] = fraction_eligible - base_fraction_eligible
        enriched_row["delta_fraction_RTM_vs_baseline"] = fraction_rtm - base_fraction_rtm
        enriched_row["delta_MPC_vs_baseline"] = mpc - base_mpc
        enriched.append(enriched_row)
        paper_rows.append(
            {
                "condition": row["condition"],
                "label": row["label"],
                "rtm_type": row["rtm_type"],
                "n_eligible": row["n_eligible"],
                "fraction_eligible": fraction_eligible,
                "fraction_RTM": fraction_rtm,
                "delta_fraction_RTM_vs_baseline": fraction_rtm - base_fraction_rtm,
                "MPC": mpc,
                "delta_MPC_vs_baseline": mpc - base_mpc,
                "fraction_true_RTM": row["fraction_true_RTM"],
                "fraction_type3": row["fraction_type3"],
                "type3_share_measured_RTM": row["type3_share_measured_RTM"],
                "net_measurement_difference_pp": row["net_measurement_difference_pp"],
            }
        )

    paths = {
        "condition_summary_with_deltas": directory / "condition_summary_with_deltas.csv",
        "paper_table": directory / "paper_table.csv",
        "paired_classification": directory / "paired_classification.csv",
        "fixed_enrollment": directory / "fixed_enrollment_summary.csv",
    }
    write_csv(paths["condition_summary_with_deltas"], enriched)
    write_csv(paths["paper_table"], paper_rows)
    paired_keys = ["condition", "n_eligible", "both_count", "type3_count", "true_only_count", "neither_count",
                   "rtm_count", "true_rtm_count", "fraction_RTM", "fraction_true_RTM", "fraction_type3",
                   "fraction_type3_ci_lo", "fraction_type3_ci_hi", "type3_share_measured_RTM", "net_measurement_difference_pp"]
    write_csv(paths["paired_classification"], [{key: row[key] for key in paired_keys} for row in rows])
    fixed_keys = ["condition", "n_fixed", "fixed_fraction_RTM", "fixed_fraction_type3", "fixed_n_zero_baseline",
                  "fixed_n_mpc", "fixed_MPC", "fixed_MPC_ci_lo", "fixed_MPC_ci_hi"]
    write_csv(paths["fixed_enrollment"], [{key: row[key] for key in fixed_keys} for row in rows
                                        if row["rtm_type"] == "baseline" or row["rtm_type"].startswith("type3")])
    return paths


def plot_value(value: str | float) -> float:
    """Parse a plotting value from CSV text."""

    try:
        return float(value)
    except Exception:
        return float("nan")


def make_figures(input_dir: str | Path) -> dict[str, Path]:
    """Generate manuscript-ready RTM123 summary figures."""

    os.environ.setdefault("MPLCONFIGDIR", str(Path(input_dir) / ".matplotlib-cache"))
    import matplotlib.pyplot as plt

    directory = Path(input_dir)
    table_path = directory / "condition_summary_with_deltas.csv"
    if not table_path.exists():
        make_tables(directory)
    rows = read_csv_dicts(table_path)
    short_labels = {"baseline_perfect": "Reference", "type1_transient_msf": "Transient rate",
                    "type2_threshold_8": "Threshold 8", "type3_sensitivity_90": "Sens. 90%",
                    "type3_sensitivity_80": "Sens. 80%", "type3_sensitivity_70": "Sens. 70%",
                    "type3_far_1_per_month": "FAR 1/month", "type3_far_1_per_week": "FAR 1/week",
                    "type3_far_1_per_day": "FAR 1/day"}
    labels = [short_labels.get(row["condition"], row["label"]) for row in rows]
    x = np.arange(len(rows), dtype=float)
    rtm_values = np.asarray([100.0 * plot_value(row["fraction_RTM"]) for row in rows], dtype=float)
    mpc_values = np.asarray([plot_value(row["MPC"]) for row in rows], dtype=float)
    eligible_values = np.asarray([100.0 * plot_value(row["fraction_eligible"]) for row in rows], dtype=float)

    colors = []
    for row in rows:
        rtm_type = row["rtm_type"]
        if rtm_type == "baseline":
            colors.append("#4B5563")
        elif rtm_type == "type1":
            colors.append("#2563EB")
        elif rtm_type == "type2":
            colors.append("#D97706")
        elif rtm_type == "type3_sensitivity":
            colors.append("#059669")
        else:
            colors.append("#7C3AED")

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, grid = plt.subplots(nrows=2, ncols=2, figsize=(11, 8))
    axes = grid.ravel()
    axes[0].bar(x, eligible_values, color=colors, alpha=0.88)
    axes[0].set_ylabel("Eligible (%)")
    axes[0].set_title("A  Eligibility yield", loc="left")
    true_rtm = np.array([100*plot_value(row["fraction_true_RTM"]) for row in rows])
    axes[1].bar(x-0.18, rtm_values, width=0.36, color="#4B5563", label="Measured counts")
    axes[1].bar(x+0.18, true_rtm, width=0.36, color="#AAB5C4", label="True counts")
    axes[1].set_ylabel("Eligible participants (%)")
    axes[1].set_title("B  Observed and true-count RTM", loc="left")
    axes[1].legend(fontsize=8)
    type3 = np.array([100*plot_value(row["fraction_type3"]) for row in rows])
    true_only = np.array([100*plot_value(row["true_only_count"])/plot_value(row["n_eligible"]) if plot_value(row["n_eligible"]) else np.nan for row in rows])
    axes[2].bar(x-0.18, type3, width=0.36, color="#7C3AED", label="Measured only (Type 3)")
    axes[2].bar(x+0.18, true_only, width=0.36, color="#AAB5C4", label="True only")
    axes[2].set_ylabel("Eligible participants (%)")
    axes[2].set_title("C  Paired classification disagreements", loc="left")
    axes[2].legend(fontsize=8)
    axes[3].bar(x, mpc_values, color=colors, alpha=0.88)
    axes[3].axhline(0, color="#111827", linewidth=0.8)
    axes[3].set_ylabel("Median percentage reduction (%)")
    axes[3].set_title("D  Apparent improvement without treatment", loc="left")

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, axis="y", color="#D1D5DB", linewidth=0.8)
        ax.grid(False, axis="x")

    fig.suptitle("Common underlying population; enrollment re-evaluated by condition", y=0.995, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    png_path = directory / "rtm123_summary.png"
    pdf_path = directory / "rtm123_summary.pdf"
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)
    return {"png": png_path, "pdf": pdf_path}


def encode_image_as_base64(path: str | Path) -> str:
    """Return a base64-encoded PNG image for notebook output embedding."""

    return base64.b64encode(Path(path).read_bytes()).decode("ascii")

