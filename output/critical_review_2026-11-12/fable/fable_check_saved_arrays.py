"""Fable review, check 1: recompute every reported number from the saved per-patient arrays.

Read-only. Loads outputs/rtm123_type3_1m/patient_condition_flags/*.npz and the
summary CSVs, recomputes classifications with float arithmetic written here
(no import from rtm_anatomy), and writes one JSON file into the fable folder.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "outputs" / "rtm123_type3_1m"
OUT = Path(__file__).resolve().parent / "fable_saved_array_check.json"

CONDITIONS = [
    ("baseline_perfect", 1.0, 0.0),
    ("type1_transient_msf", 1.0, 0.0),
    ("type2_threshold_8", 1.0, 0.0),
    ("type3_sensitivity_90", 0.9, 0.0),
    ("type3_sensitivity_80", 0.8, 0.0),
    ("type3_sensitivity_70", 0.7, 0.0),
    ("type3_far_1_per_month", 1.0, 1 / 30),
    ("type3_far_1_per_week", 1.0, 1 / 7),
    ("type3_far_1_per_day", 1.0, 1.0),
]


def wilson(k, n, z=1.959963984540054):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 23), b""):
            h.update(block)
    return h.hexdigest()


def main():
    summary = {r["condition"]: r for r in csv.DictReader((RUN / "condition_summary.csv").open())}
    validation = json.loads((RUN / "validation.json").read_text())
    manifest = json.loads((RUN / "run_manifest.json").read_text())
    report = {"hash_checks": {}, "conditions": {}}
    report["hash_checks"]["analysis_source_matches_manifest"] = (
        sha(ROOT / "rtm_anatomy" / "rtm123.py") == manifest["analysis_source_sha256"])
    report["hash_checks"]["condition_summary_matches_validation"] = (
        sha(RUN / "condition_summary.csv") == validation["condition_summary_sha256"])
    report["hash_checks"]["run_manifest_matches_validation"] = (
        sha(RUN / "run_manifest.json") == validation["run_manifest_sha256"])
    report["hash_checks"]["validate_script_matches_validation"] = (
        sha(ROOT / "scripts" / "validate_paired_type3.py") == validation["source_sha256"])

    for name, sens, far in CONDITIONS:
        path = RUN / "patient_condition_flags" / f"{name}.npz"
        npz_hash_ok = sha(path) == validation["patient_flags_sha256"][name]
        with np.load(path, allow_pickle=False) as z:
            a = {k: z[k] for k in z.files if k not in ("cache_json", "condition_json")}
            cache = json.loads(str(z["cache_json"]))
        e = a["eligible"]
        n = int(e.sum())
        B, T, R = a["baseline"][e], a["test"][e], a["reference"][e]
        tB, tT, tR = a["true_baseline"][e], a["true_test"][e], a["true_reference"][e]
        # Float reclassification with a tolerance band to count near-ties.
        tol = 1e-9
        m_float = (B - R > tol) & ((B - R) - np.abs(T - R) > tol)
        t_float = (tB - tR > tol) & ((tB - tR) - np.abs(tT - tR) > tol)
        near_tie_m = int(np.sum(np.abs((B - R) - np.abs(T - R)) <= tol) + np.sum(np.abs(B - R) <= tol))
        near_tie_t = int(np.sum(np.abs((tB - tR) - np.abs(tT - tR)) <= tol) + np.sum(np.abs(tB - tR) <= tol))
        m, t = a["rtm"][e], a["true_rtm"][e]
        type3 = int((m & ~t).sum())
        true_only = int((t & ~m).sum())
        both = int((m & t).sum())
        neither = int((~m & ~t).sum())
        pc = 100 * (1 - T / B)
        lo, hi = wilson(type3, n)
        fe = a["fixed_eligible"]
        nf = int(fe.sum())
        fpc = a["fixed_pc"][fe]
        fixed_rtm = int(a["fixed_rtm"][fe].sum())
        fixed_t3 = int(a["fixed_type3_rtm"][fe].sum())
        med = float(np.median(pc))
        row = summary[name]
        rec = {
            "npz_hash_matches_validation": npz_hash_ok,
            "cache_source_sha_matches_manifest": cache["source_sha256"] == manifest["analysis_source_sha256"],
            "cache_numpy_version": cache["numpy_version"],
            "n_eligible": n,
            "pct_eligible": 100 * n / e.size,
            "measured_rtm_n": int(m.sum()), "true_rtm_n": int(t.sum()),
            "both": both, "type3": type3, "true_only": true_only, "neither": neither,
            "partition_sums_to_n": both + type3 + true_only + neither == n,
            "pct_measured_rtm": 100 * m.mean(), "pct_true_rtm": 100 * t.mean(),
            "pct_type3": 100 * type3 / n, "type3_wilson_pct": [100 * lo, 100 * hi],
            "type3_share_of_measured_pct": 100 * type3 / max(1, int(m.sum())),
            "net_pp": 100 * (type3 - true_only) / n,
            "mpc": med,
            "mpc_atom_share_pct": 100 * float(np.mean(np.isclose(pc, med, atol=1e-9))),
            "float_reclass_disagreements_measured": int((m_float != m).sum()),
            "float_reclass_disagreements_true": int((t_float != t).sum()),
            "near_ties_measured": near_tie_m, "near_ties_true": near_tie_t,
            "share_first_start_0_pct": 100 * float(np.mean(a["first_start"][e] == 0)),
            "mean_baseline": float(B.mean()), "mean_test": float(T.mean()), "mean_reference": float(R.mean()),
            "mean_true_baseline": float(tB.mean()), "mean_true_test": float(tT.mean()),
            "mean_true_reference": float(tR.mean()),
            "true_baseline_at_or_below_true_ref_pct": 100 * float(np.mean(tB <= tR)),
            "fixed_n": nf,
            "fixed_pct_rtm": 100 * fixed_rtm / nf,
            "fixed_pct_type3": 100 * fixed_t3 / nf,
            "fixed_zero_baseline_n": int((a["fixed_baseline"][fe] == 0).sum()),
            "fixed_mpc_n": int(np.isfinite(fpc).sum()),
            "fixed_mpc": float(np.nanmedian(fpc)),
            "csv_agrees": all([
                int(row["n_eligible"]) == n, int(row["rtm_count"]) == int(m.sum()),
                int(row["true_rtm_count"]) == int(t.sum()), int(row["type3_count"]) == type3,
                int(row["true_only_count"]) == true_only, int(row["both_count"]) == both,
                int(row["neither_count"]) == neither,
                abs(float(row["MPC"]) - med) < 1e-9,
                abs(float(row["fixed_fraction_RTM"]) - fixed_rtm / nf) < 1e-12,
                abs(float(row["fixed_fraction_type3"]) - fixed_t3 / nf) < 1e-12,
                abs(float(row["fixed_MPC"]) - float(np.nanmedian(fpc))) < 1e-9,
                abs(float(row["fraction_type3_ci_lo"]) - lo) < 1e-12,
                abs(float(row["fraction_type3_ci_hi"]) - hi) < 1e-12,
            ]),
        }
        # Split Type 3 by why the true scale failed.
        t3 = m & ~t
        if type3:
            rec["type3_true_baseline_not_above_ref_pct"] = 100 * float(np.mean((tB <= tR)[t3]))
            rec["type3_true_baseline_above_ref_but_test_not_closer_pct"] = 100 * float(np.mean((tB > tR)[t3]))
        # Fixed-enrollment true-only share (true RTM at perfect windows is the perfect rtm flag).
        report["conditions"][name] = rec
        print(name, json.dumps(rec, indent=1))

    # Fixed-enrollment true-only: compare with the perfect-detector classification.
    with np.load(RUN / "patient_condition_flags" / "baseline_perfect.npz") as z:
        perfect_rtm = z["rtm"]; perfect_e = z["eligible"]
    report["fixed_enrollment_true_only"] = {}
    for name, sens, far in CONDITIONS[3:]:
        with np.load(RUN / "patient_condition_flags" / f"{name}.npz") as z:
            fr = z["fixed_rtm"]; ft3 = z["fixed_type3_rtm"]; fe = z["fixed_eligible"]
        assert np.array_equal(fe, perfect_e)
        tr = perfect_rtm[fe]; mr = fr[fe]
        report["fixed_enrollment_true_only"][name] = {
            "type3_matches_measured_and_not_true": bool(np.array_equal(ft3[fe], mr & ~tr)),
            "pct_true_only": 100 * float(np.mean(tr & ~mr)),
            "pct_type3": 100 * float(np.mean(mr & ~tr)),
            "net_pp": 100 * float(np.mean(mr) - np.mean(tr)),
        }
    print(json.dumps(report["fixed_enrollment_true_only"], indent=1))
    print(json.dumps(report["hash_checks"], indent=1))
    OUT.write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
