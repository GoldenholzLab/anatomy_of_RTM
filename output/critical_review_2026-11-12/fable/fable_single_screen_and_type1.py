"""Fable review, check 6: split each condition by whether the person qualified at the first screen (month 0),
and describe who lands in the transient baseline-overlap stratum. Read-only on saved arrays."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "outputs" / "rtm123_type3_1m" / "patient_condition_flags"
NAMES = ["baseline_perfect", "type1_transient_msf", "type2_threshold_8", "type3_sensitivity_90",
         "type3_sensitivity_80", "type3_sensitivity_70", "type3_far_1_per_month",
         "type3_far_1_per_week", "type3_far_1_per_day"]
out = {"by_screen": {}}
for name in NAMES:
    with np.load(RUN / f"{name}.npz") as z:
        e, fs, rtm, t3, pc = z["eligible"], z["first_start"], z["rtm"], z["type3_rtm"], z["pc"]
    first, later = e & (fs == 0), e & (fs > 0)
    out["by_screen"][name] = {
        "pct_of_all_eligible_at_month0": round(100 * first.mean(), 2),
        "pct_of_enrolled_from_month0": round(100 * first.sum() / e.sum(), 2),
        "month0": {"rtm": round(100 * rtm[first].mean(), 2), "type3": round(100 * t3[first].mean(), 2),
                   "mpc": round(float(np.nanmedian(pc[first])), 2)},
        "later": {"rtm": round(100 * rtm[later].mean(), 2), "type3": round(100 * t3[later].mean(), 2),
                  "mpc": round(float(np.nanmedian(pc[later])), 2)},
        "all": {"rtm": round(100 * rtm[e].mean(), 2), "type3": round(100 * t3[e].mean(), 2),
                "mpc": round(float(np.nanmedian(pc[e])), 2)},
    }
with np.load(RUN / "baseline_perfect.npz") as z:
    pe, pfs = z["eligible"], z["first_start"]
with np.load(RUN / "type1_transient_msf.npz") as z:
    e, fs, ss, sm = z["eligible"], z["first_start"].astype(int), z["shock_start"].astype(int), z["shock_msf"]
base_only = e & ((ss == fs) | (ss == fs - 1))
out["transient_baseline_only_stratum"] = {
    "n": int(base_only.sum()),
    "pct_never_eligible_without_transient": round(100 * float((~pe[base_only]).mean()), 2),
    "pct_same_window_as_without_transient": round(100 * float((pe & (pfs == fs))[base_only].mean()), 2),
    "pct_of_transient_enrolled": round(100 * base_only.sum() / e.sum(), 2),
    "chance_share_if_timing_ignored_pct": round(100 * 2 / 35, 2),
}
out["transient_newly_eligible"] = {
    "n_eligible_only_with_transient": int((e & ~pe).sum()),
    "n_eligible_only_without_transient": int((pe & ~e).sum()),
}
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parent / "fable_single_screen_and_type1.json").write_text(json.dumps(out, indent=1) + "\n")
