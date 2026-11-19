"""Fable review, check 3: what does the RTM indicator read when nothing selects the window?

Read-only. Uses the raw true daily histories for all 1,000,000 patients and the
saved perfect-detector flags. Writes one JSON file into the fable folder.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
COHORT = ROOT / "outputs" / "rtm123_1m"
RUN = ROOT / "outputs" / "rtm123_type3_1m"
OUT = Path(__file__).resolve().parent / "fable_comparator_results.json"
MONTHS, DPM, N = 36, 30, 1_000_000


def rtm_at(monthly: np.ndarray, starts: np.ndarray):
    """Strict integer RTM rule at the given start month for each row."""
    rows = np.arange(monthly.shape[0])
    total = monthly.sum(1).astype(np.int64)
    b = (monthly[rows, starts] + monthly[rows, starts + 1]).astype(np.int64)
    t = (monthly[rows, starts + 2] + monthly[rows, starts + 3] + monthly[rows, starts + 4]).astype(np.int64)
    bd = b * MONTHS - 2 * total
    td = t * MONTHS - 3 * total
    above = bd > 0
    rtm = above & (3 * bd > 2 * np.abs(td))
    with np.errstate(divide="ignore", invalid="ignore"):
        pc = np.where(b > 0, 100 * (1 - (t / 3) / (b / 2)), np.nan)
    return above, rtm, pc


def main():
    daily = np.memmap(COHORT / "daily_counts.int16.memmap", dtype=np.int16, mode="r", shape=(N, MONTHS * DPM))
    monthly = np.empty((N, MONTHS), dtype=np.int32)
    step = 100_000
    for s in range(0, N, step):
        monthly[s:s + step] = np.asarray(daily[s:s + step]).reshape(-1, MONTHS, DPM).sum(2, dtype=np.int32)
    latent = np.load(COHORT / "latent_msf.npy")
    with np.load(RUN / "patient_condition_flags" / "baseline_perfect.npz") as z:
        elig = z["eligible"]; first = z["first_start"].astype(np.int64); saved_rtm = z["rtm"]; saved_pc = z["pc"]
    with np.load(RUN / "patient_condition_flags" / "type3_far_1_per_day.npz") as z:
        far_elig = z["eligible"]; far_true_rtm = z["true_rtm"]

    rng = np.random.default_rng(20261112)
    rand_start = rng.integers(0, 32, size=N)
    report = {}

    # Reproduce the reported perfect-detector figure from raw counts first.
    idx = np.flatnonzero(elig)
    above, rtm, pc = rtm_at(monthly[idx], first[idx])
    report["perfect_selected_window"] = {
        "n": int(idx.size), "pct_rtm": 100 * float(rtm.mean()),
        "matches_saved_flags": bool(np.array_equal(rtm, saved_rtm[idx])),
        "pct_baseline_above_ref": 100 * float(above.mean()),
        "pct_rtm_given_above": 100 * float(rtm[above].mean()),
        "mpc": float(np.nanmedian(pc)),
    }
    # Same enrolled people, window drawn at random with no reference to their counts.
    above, rtm, pc = rtm_at(monthly[idx], rand_start[idx])
    report["perfect_enrolled_people_random_window"] = {
        "n": int(idx.size), "pct_rtm": 100 * float(rtm.mean()),
        "pct_baseline_above_ref": 100 * float(above.mean()),
        "pct_rtm_given_above": 100 * float(rtm[above].mean()),
        "mpc_positive_baselines": float(np.nanmedian(pc)),
        "n_zero_baseline": int(np.isnan(pc).sum()),
    }
    # Everyone, random window, no eligibility at all.
    above, rtm, pc = rtm_at(monthly, rand_start)
    report["all_patients_random_window"] = {
        "n": N, "pct_rtm": 100 * float(rtm.mean()),
        "pct_baseline_above_ref": 100 * float(above.mean()),
        "pct_rtm_given_above": 100 * float(rtm[above].mean()),
        "mpc_positive_baselines": float(np.nanmedian(pc)),
        "n_zero_baseline": int(np.isnan(pc).sum()),
    }
    # Enrolled people split by whether they qualified in the very first window.
    for label, mask in (("first_window_month0", elig & (first == 0)), ("later_window", elig & (first > 0))):
        report["perfect_" + label] = {
            "n": int(mask.sum()), "pct_of_enrolled": 100 * float(mask.sum() / elig.sum()),
            "pct_rtm": 100 * float(saved_rtm[mask].mean()), "mpc": float(np.nanmedian(saved_pc[mask])),
        }
    # A single prospective screen: only the month-0 window is ever assessed.
    report["single_screen_design"] = {
        "pct_eligible_of_all": 100 * float((elig & (first == 0)).mean()),
        "pct_rtm": report["perfect_first_window_month0"]["pct_rtm"],
        "mpc": report["perfect_first_window_month0"]["mpc"],
    }
    # Context for the 34.1% true-count RTM among FAR 1/day selections.
    idx = np.flatnonzero(far_elig)
    above, rtm, _ = rtm_at(monthly[idx], rand_start[idx])
    report["far_1_per_day_selected_people"] = {
        "n": int(idx.size), "pct_true_rtm_at_selected_window": 100 * float(far_true_rtm[idx].mean()),
        "pct_true_rtm_at_random_window": 100 * float(rtm.mean()),
    }
    # Cohort description.
    tot = monthly.sum(1) / MONTHS
    report["cohort"] = {
        "latent_msf_median": float(np.median(latent)), "latent_msf_mean": float(latent.mean()),
        "observed_36mo_mean_median": float(np.median(tot)), "observed_36mo_mean_mean": float(tot.mean()),
        "pct_latent_msf_ge_4": 100 * float((latent >= 4).mean()),
        "pct_zero_seizures_in_36mo": 100 * float((tot == 0).mean()),
        "daily_count_max": int(np.asarray(daily[:200000]).max()),
    }
    print(json.dumps(report, indent=1))
    OUT.write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
