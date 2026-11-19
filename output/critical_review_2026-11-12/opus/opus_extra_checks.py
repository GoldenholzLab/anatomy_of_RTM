"""Extra read-only checks: fixed-enrollment true-only counts, Type 1 rate ratios. Usage: python3 -I -B opus_extra_checks.py <repo_root> <out_json>"""
import json, sys
from pathlib import Path
import numpy as np
root = Path(sys.argv[1]); out = Path(sys.argv[2])
fd = root / "outputs/rtm123_type3_1m/patient_condition_flags"
b = np.load(fd / "baseline_perfect.npz")
be, brtm = b["eligible"], b["rtm"]
res = {"fixed_enrollment_true_only": {}}
for name in ["type3_sensitivity_90", "type3_sensitivity_80", "type3_sensitivity_70",
             "type3_far_1_per_month", "type3_far_1_per_week", "type3_far_1_per_day"]:
    d = np.load(fd / f"{name}.npz")
    fe = d["fixed_eligible"]; assert np.array_equal(fe, be)
    n = int(fe.sum())
    fm = d["fixed_rtm"] & fe; ft3 = d["fixed_type3_rtm"] & fe
    # fixed true RTM equals perfect-detector RTM in the same window (same true counts and reference)
    assert np.array_equal(ft3, fm & ~brtm & fe)
    true_only = int((brtm & ~d["fixed_rtm"] & fe).sum())
    res["fixed_enrollment_true_only"][name] = {
        "n": n, "fixed_measured_rtm_pct": 100 * fm.sum() / n, "fixed_true_rtm_pct": 100 * (brtm & fe).sum() / n,
        "fixed_type3_pct": 100 * ft3.sum() / n, "fixed_true_only_pct": 100 * true_only / n,
        "fixed_net_pp": 100 * (int(ft3.sum()) - true_only) / n}
lat = np.load(root / "outputs/rtm123_1m/latent_msf.npy", mmap_mode="r").astype(float)
t1 = np.load(fd / "type1_transient_msf.npz")
ratio = t1["shock_msf"].astype(float) / lat
res["type1_ratio_quantiles_5_25_50_75_95"] = np.quantile(ratio, [.05, .25, .5, .75, .95]).tolist()
res["type1_share_ratio_gt10_or_lt0.1"] = float(np.mean((ratio > 10) | (ratio < 0.1)))
res["latent_msf_quantiles_5_25_50_75_95"] = np.quantile(lat, [.05, .25, .5, .75, .95]).tolist()
e = t1["eligible"]; s = t1["first_start"]; sh = t1["shock_start"]
base_only = e & (sh < s + 2) & (s < sh + 2) & ~((sh < s + 5) & (s + 2 < sh + 2))
res["type1_baseline_only_n"] = int(base_only.sum())
res["type1_baseline_only_not_perfect_eligible_share"] = float(np.mean(~be[base_only]))
res["type1_baseline_only_median_latent_msf"] = float(np.median(lat[base_only]))
res["type1_baseline_only_median_ratio"] = float(np.median(ratio[base_only]))
res["type1_eligible_not_perfect_eligible"] = int((e & ~be).sum())
res["type1_perfect_eligible_not_type1_eligible"] = int((~e & be).sum())
out.write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
