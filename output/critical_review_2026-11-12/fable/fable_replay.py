"""Fable review, check 2: independent replay from raw daily histories plus sensitivity analyses.

Read-only on the cohort and saved outputs. Nothing is imported from
rtm_anatomy. The only shared recipe is the documented per-patient detector
seed (blake2b of "detector|<condition>|<seed>|"), needed to regenerate the same
detector noise. Results go to one JSON file in the fable folder.

Usage: python3 fable_replay.py [n_patients]
"""
from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
COHORT = ROOT / "outputs" / "rtm123_1m"
RUN = ROOT / "outputs" / "rtm123_type3_1m"
OUT = Path(__file__).resolve().parent / "fable_replay_results.json"
MONTHS, DPM, N = 36, 30, 1_000_000

# name, threshold, sensitivity (as Fraction), false alarms per day (as Fraction)
CONDITIONS = [
    ("baseline_perfect", 4, Fraction(1), Fraction(0)),
    ("type2_threshold_8", 8, Fraction(1), Fraction(0)),
    ("type3_sensitivity_90", 4, Fraction(9, 10), Fraction(0)),
    ("type3_sensitivity_80", 4, Fraction(8, 10), Fraction(0)),
    ("type3_sensitivity_70", 4, Fraction(7, 10), Fraction(0)),
    ("type3_far_1_per_month", 4, Fraction(1), Fraction(1, 30)),
    ("type3_far_1_per_week", 4, Fraction(1), Fraction(1, 7)),
    ("type3_far_1_per_day", 4, Fraction(1), Fraction(1)),
]


def detector_seed(name: str, seed: int) -> int:
    d = hashlib.blake2b(digest_size=8)
    for part in ("detector", name, seed):
        d.update(str(part).encode())
        d.update(b"|")
    return int.from_bytes(d.digest(), "little") & ((1 << 63) - 1)


def longest_zero_run(x: np.ndarray) -> int:
    nz = np.flatnonzero(np.r_[True, x > 0, True])
    return int(np.max(np.diff(nz) - 1))


def rtm_frac(b: Fraction, t: Fraction, ref: Fraction) -> bool:
    return b > ref and abs(t - ref) < (b - ref)


def replay_patient(true_daily: np.ndarray, seed: int, name: str, thr: int, sens: Fraction, far: Fraction):
    """Return a dict of replayed quantities for one patient and condition."""
    rng = np.random.default_rng(detector_seed(name, seed))
    true_daily = true_daily.astype(np.int32)
    obs = true_daily.copy()
    if sens < 1:
        obs = rng.binomial(true_daily, float(sens)).astype(np.int32)
    if far > 0:
        obs = obs + rng.poisson(float(far), size=obs.shape).astype(np.int32)
    exp_month = far * DPM                      # exact expected alarms per month
    q = exp_month.denominator
    raw_month = obs.reshape(MONTHS, DPM).sum(1).astype(np.int64)
    unfloored_num = raw_month * q - exp_month.numerator      # numerators over q, may be negative
    num = np.maximum(unfloored_num, 0)
    daily_rule = np.maximum(obs - int(round(float(far))), 0)
    true_month = true_daily.reshape(MONTHS, DPM).sum(1).astype(np.int64)
    start = -1
    for s in range(MONTHS - 4):
        if num[s] + num[s + 1] < 2 * thr * q:
            continue
        if min(num[s], num[s + 1]) < 3 * q:
            continue
        if longest_zero_run(daily_rule[s * DPM:(s + 2) * DPM]) > 25:
            continue
        start = s
        break
    true_ref = Fraction(int(true_month.sum()), MONTHS)
    out = {"start": start, "true_ref": true_ref}
    if start < 0:
        return out
    s = start
    B = Fraction(int(num[s:s + 2].sum()), 2 * q)
    T = Fraction(int(num[s + 2:s + 5].sum()), 3 * q)
    Tu = Fraction(int(unfloored_num[s + 2:s + 5].sum()), 3 * q)
    tB = Fraction(int(true_month[s:s + 2].sum()), 2)
    tT = Fraction(int(true_month[s + 2:s + 5].sum()), 3)
    meas_ref = sens * true_ref
    own_ref = Fraction(int(num.sum()), MONTHS * q)             # mean of corrected, floored measured counts
    # Reference that leaves the five trial months out, on each scale.
    outside = np.ones(MONTHS, bool)
    outside[s:s + 5] = False
    true_ref_out = Fraction(int(true_month[outside].sum()), int(outside.sum()))
    # Would the same window pass eligibility on true counts?
    tb0, tb1 = int(true_month[s]), int(true_month[s + 1])
    true_elig = (tb0 + tb1 >= 2 * 4 and min(tb0, tb1) >= 3
                 and longest_zero_run(true_daily[s * DPM:(s + 2) * DPM]) <= 25)
    out.update(
        B=B, T=T, tB=tB, tT=tT,
        m=rtm_frac(B, T, meas_ref), t=rtm_frac(tB, tT, true_ref),
        m_unfloored=rtm_frac(B, Tu, meas_ref),
        m_ownref=rtm_frac(B, T, own_ref),
        m_out=rtm_frac(B, T, sens * true_ref_out), t_out=rtm_frac(tB, tT, true_ref_out),
        true_elig=bool(true_elig),
        floored_test_month=bool(np.any(unfloored_num[s + 2:s + 5] < 0)),
        own_ref=own_ref,
    )
    return out


def main(n_replay: int):
    daily = np.memmap(COHORT / "daily_counts.int16.memmap", dtype=np.int16, mode="r", shape=(N, MONTHS * DPM))
    seeds = np.load(COHORT / "patient_seeds.npy", mmap_mode="r")
    ids = np.arange(n_replay)
    report = {"n_replayed": int(n_replay), "numpy_version": np.__version__, "conditions": {}}
    for name, thr, sens, far in CONDITIONS:
        with np.load(RUN / "patient_condition_flags" / f"{name}.npz", allow_pickle=False) as z:
            saved = {k: z[k][:n_replay] for k in ("first_start", "rtm", "true_rtm", "type3_rtm",
                                                    "baseline", "test", "true_baseline", "true_test",
                                                    "true_reference")}
        diffs = {"first_start": 0, "rtm": 0, "true_rtm": 0, "baseline": 0, "test": 0,
                 "true_baseline": 0, "true_test": 0, "true_reference": 0}
        c = dict(n=0, m=0, t=0, t3=0, to=0,
                 m_unfloored=0, t3_unfloored=0, m_ownref=0, t3_ownref=0,
                 m_out=0, t_out=0, t3_out=0, to_out=0,
                 true_elig=0, t3_true_elig=0, t3_true_inelig=0, floored=0,
                 own_ref_sum=0.0, meas_ref_sum=0.0)
        for i in ids:
            r = replay_patient(np.asarray(daily[i]), int(seeds[i]), name, thr, sens, far)
            diffs["first_start"] += int(r["start"] != int(saved["first_start"][i]))
            diffs["true_reference"] += int(abs(float(r["true_ref"]) - saved["true_reference"][i]) > 1e-10)
            if r["start"] < 0:
                continue
            diffs["rtm"] += int(r["m"] != bool(saved["rtm"][i]))
            diffs["true_rtm"] += int(r["t"] != bool(saved["true_rtm"][i]))
            for key, val in (("baseline", r["B"]), ("test", r["T"]),
                             ("true_baseline", r["tB"]), ("true_test", r["tT"])):
                diffs[key] += int(abs(float(val) - saved[key][i]) > 1e-10)
            c["n"] += 1
            c["m"] += r["m"]; c["t"] += r["t"]
            c["t3"] += r["m"] and not r["t"]; c["to"] += r["t"] and not r["m"]
            c["m_unfloored"] += r["m_unfloored"]; c["t3_unfloored"] += r["m_unfloored"] and not r["t"]
            c["m_ownref"] += r["m_ownref"]; c["t3_ownref"] += r["m_ownref"] and not r["t"]
            c["m_out"] += r["m_out"]; c["t_out"] += r["t_out"]
            c["t3_out"] += r["m_out"] and not r["t_out"]; c["to_out"] += r["t_out"] and not r["m_out"]
            c["true_elig"] += r["true_elig"]
            if r["m"] and not r["t"]:
                c["t3_true_elig"] += r["true_elig"]; c["t3_true_inelig"] += not r["true_elig"]
            c["floored"] += r["floored_test_month"]
            c["own_ref_sum"] += float(r["own_ref"]); c["meas_ref_sum"] += float(sens * r["true_ref"])
        n = c["n"]
        pct = lambda k: round(100 * c[k] / n, 3)
        rec = {
            "differences_vs_saved": diffs,
            "replay_matches_saved": all(v == 0 for v in diffs.values()),
            "n_selected": n, "pct_eligible": round(100 * n / n_replay, 3),
            "as_reported": {"measured_rtm": pct("m"), "true_rtm": pct("t"), "type3": pct("t3"), "true_only": pct("to")},
            "unfloored_test_counts": {"measured_rtm": pct("m_unfloored"), "type3": pct("t3_unfloored")},
            "own_measured_36mo_mean_as_reference": {"measured_rtm": pct("m_ownref"), "type3": pct("t3_ownref")},
            "reference_excluding_trial_window": {"measured_rtm": pct("m_out"), "true_rtm": pct("t_out"),
                                                  "type3": pct("t3_out"), "true_only": pct("to_out")},
            "pct_selected_passing_eligibility_on_true_counts_same_window": pct("true_elig"),
            "type3_split_pct_of_selected": {"true_eligible": pct("t3_true_elig"), "true_ineligible": pct("t3_true_inelig")},
            "pct_selected_with_a_floored_test_month": pct("floored"),
            "mean_own_measured_reference": round(c["own_ref_sum"] / n, 4),
            "mean_sensitivity_scaled_true_reference": round(c["meas_ref_sum"] / n, 4),
        }
        report["conditions"][name] = rec
        print(name, json.dumps(rec, indent=1), flush=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20000)
