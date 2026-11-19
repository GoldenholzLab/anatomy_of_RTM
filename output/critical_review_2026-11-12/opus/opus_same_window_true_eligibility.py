"""For condition-selected participants, does the true diary pass the reference entry rule in the same
selected baseline window? Read-only, uses saved first_start. Usage: python3 -I -B <script> <repo_root> <out_json> [n] [seed]"""
import json, sys
from pathlib import Path
import numpy as np
root = Path(sys.argv[1]).resolve(); out = Path(sys.argv[2])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 100000; seed = int(sys.argv[4]) if len(sys.argv) > 4 else 5
sys.path.insert(0, str(root))
from rtm_anatomy import rtm123 as R
meta, daily, latent, seeds = R.load_cohort(root / "outputs/rtm123_1m")
ids = np.sort(np.random.default_rng(seed).choice(int(meta["n_patients"]), n, replace=False))
res = {"n_subsample": n, "seed": seed}
for name in ["type3_sensitivity_70", "type3_far_1_per_month", "type3_far_1_per_week", "type3_far_1_per_day"]:
    with np.load(root / f"outputs/rtm123_type3_1m/patient_condition_flags/{name}.npz") as z:
        e = z["eligible"][ids]; s = z["first_start"][ids]; t3 = z["type3_rtm"][ids]; m = z["rtm"][ids]
    sel = np.flatnonzero(e)
    ok = np.zeros(sel.size, bool)
    for k, j in enumerate(sel):
        d = np.asarray(daily[ids[j]], np.int32)
        mon = d.reshape(36, 30).sum(1)
        st = int(s[j]); b = mon[st:st + 2]
        ok[k] = (b.mean() >= 4) and (b.min() >= 3) and (R.longest_zero_run(d[st * 30:(st + 2) * 30]) <= 25)
    t3s = t3[sel]; ms = m[sel]
    res[name] = {"selected": int(sel.size),
                 "pct_selected_true_eligible_same_window": 100 * ok.mean(),
                 "type3_pct_among_true_eligible_same_window": 100 * t3s[ok].mean(),
                 "type3_pct_among_not_true_eligible_same_window": 100 * t3s[~ok].mean() if (~ok).any() else None,
                 "share_of_type3_not_true_eligible_same_window": float((t3s & ~ok).sum() / max(1, t3s.sum())),
                 "measured_rtm_pct_among_true_eligible_same_window": 100 * ms[ok].mean()}
out.write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
