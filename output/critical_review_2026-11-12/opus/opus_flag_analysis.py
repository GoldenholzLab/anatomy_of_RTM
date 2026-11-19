"""Independent analyses from saved per-patient flag caches (read-only).

Usage: python3 -I opus_flag_analysis.py <flags_dir> <out_json>
"""
import json
import sys
from pathlib import Path

import numpy as np

flags = Path(sys.argv[1])
out = Path(sys.argv[2])
names = ["baseline_perfect", "type1_transient_msf", "type2_threshold_8", "type3_sensitivity_90",
         "type3_sensitivity_80", "type3_sensitivity_70", "type3_far_1_per_month",
         "type3_far_1_per_week", "type3_far_1_per_day"]
base = np.load(flags / "baseline_perfect.npz")
base_elig = base["eligible"].copy()
base_start = base["first_start"].copy()
result = {}
for name in names:
    d = np.load(flags / f"{name}.npz")
    e = d["eligible"]
    n = int(e.sum())
    pc = d["pc"][e]
    med = float(np.median(pc))
    at_med = float(np.mean(np.isclose(pc, med, atol=1e-9)))
    # Mass exactly at 33.33 (test total equals baseline total) and lattice structure
    at_third = float(np.mean(np.isclose(pc, 100 / 3, atol=1e-9)))
    below = float(np.mean(pc < med - 1e-9))
    above = float(np.mean(pc > med + 1e-9))
    mean_pc = float(np.mean(pc))
    # interpolated (mid-distribution) median: the value where CDF crosses 0.5 linearly within the tie
    r = {
        "n_eligible": n,
        "recomputed_rtm": int(d["rtm"][e].sum()),
        "recomputed_true_rtm": int(d["true_rtm"][e].sum()),
        "recomputed_type3": int(d["type3_rtm"][e].sum()),
        "recomputed_true_only": int(d["true_only_rtm"][e].sum()),
        "MPC": med,
        "share_exactly_at_median": at_med,
        "share_below_median": below,
        "share_above_median": above,
        "share_pc_exactly_33.33": at_third,
        "mean_pc": mean_pc,
        "mean_baseline": float(np.mean(d["baseline"][e])),
        "mean_test": float(np.mean(d["test"][e])),
        "mean_reference": float(np.mean(d["reference"][e])),
        "mean_true_test": float(np.mean(d["true_test"][e])),
        "mean_true_reference": float(np.mean(d["true_reference"][e])),
        "mean_test_minus_reference": float(np.mean(d["test"][e] - d["reference"][e])),
    }
    t3 = d["type3_rtm"] & e
    if t3.any():
        tb = d["true_baseline"][t3]
        tr = d["true_reference"][t3]
        tt = d["true_test"][t3]
        r["type3_true_baseline_not_above_ref"] = float(np.mean(tb <= tr))
        r["type3_true_baseline_zero"] = float(np.mean(tb == 0))
        r["type3_true_reference_lt_1_per_month"] = float(np.mean(tr < 1))
        r["type3_true_reference_lt_2_per_month"] = float(np.mean(tr < 2))
        r["type3_true_reference_median"] = float(np.median(tr))
        r["type3_true_baseline_median"] = float(np.median(tb))
        r["type3_measured_baseline_median"] = float(np.median(d["baseline"][t3]))
        r["type3_measured_test_median"] = float(np.median(d["test"][t3]))
        r["type3_true_test_median"] = float(np.median(tt))
    # true-count eligibility of condition-selected participants under the reference rule
    r["selected_also_eligible_on_true_counts_any_window"] = float(np.mean(base_elig[e]))
    r["selected_same_window_as_perfect"] = float(np.mean(base_start[e] == d["first_start"][e]))
    sel_not_true_elig = e & ~base_elig
    r["n_selected_not_true_eligible"] = int(sel_not_true_elig.sum())
    if sel_not_true_elig.any():
        r["type3_rate_among_selected_not_true_eligible"] = float(np.mean(d["type3_rtm"][sel_not_true_elig]))
        r["share_of_type3_from_not_true_eligible"] = float(d["type3_rtm"][sel_not_true_elig].sum() / max(1, t3.sum()))
        r["true_ref_median_not_true_eligible"] = float(np.median(d["true_reference"][sel_not_true_elig]))
    # fixed-enrollment
    fe = d["fixed_eligible"]
    r["fixed_n"] = int(fe.sum())
    r["fixed_eligible_equals_baseline"] = bool(np.array_equal(fe, base_elig))
    r["fixed_start_equals_baseline"] = bool(np.array_equal(d["fixed_first_start"], base_start))
    fpc = d["fixed_pc"][fe]
    fpc = fpc[np.isfinite(fpc)]
    if fpc.size:
        fmed = float(np.median(fpc))
        r["fixed_MPC"] = fmed
        r["fixed_share_exactly_at_median"] = float(np.mean(np.isclose(fpc, fmed, atol=1e-9)))
        r["fixed_mean_pc"] = float(np.mean(fpc))
    if name == "type1_transient_msf":
        r["shock_start_range"] = [int(d["shock_start"].min()), int(d["shock_start"].max())]
    result[name] = r

# Type 1 relation: ratio of shock mSF to original latent mSF
lat_path = flags.parents[2] / "rtm123_1m" / "latent_msf.npy"
if lat_path.exists():
    lat = np.load(lat_path, mmap_mode="r")
    d = np.load(flags / "type1_transient_msf.npz")
    ratio = d["shock_msf"].astype(float) / np.asarray(lat, dtype=float)
    q = np.quantile(ratio, [0.05, 0.25, 0.5, 0.75, 0.95])
    result["type1_rate_ratio_quantiles_5_25_50_75_95"] = q.tolist()
    result["type1_share_ratio_gt_2_or_lt_half"] = float(np.mean((ratio > 2) | (ratio < 0.5)))
    result["type1_share_ratio_gt_10_or_lt_0.1"] = float(np.mean((ratio > 10) | (ratio < 0.1)))
    e = d["eligible"]
    bl = base_elig
    result["type1_eligible_but_not_baseline_eligible"] = int((e & ~bl).sum())
    result["type1_baseline_eligible_but_not_type1_eligible"] = int((~e & bl).sum())
    result["latent_msf_quantiles_5_25_50_75_95"] = np.quantile(np.asarray(lat, float), [0.05, 0.25, 0.5, 0.75, 0.95]).tolist()

out.write_text(json.dumps(result, indent=1))
print(json.dumps(result, indent=1))
