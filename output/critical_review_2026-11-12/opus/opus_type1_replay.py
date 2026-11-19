"""Replay the transient-state condition on a subsample with the current simulator (read-only).
Usage: python3 -I -B opus_type1_replay.py <repo_root> <out_json> [n] [seed]"""
import json, sys
from pathlib import Path
import numpy as np
root = Path(sys.argv[1]).resolve(); out = Path(sys.argv[2])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 2000; seed = int(sys.argv[4]) if len(sys.argv) > 4 else 99
sys.path.insert(0, str(root))
from rtm_anatomy import rtm123 as R
meta, daily, latent, seeds = R.load_cohort(root / "outputs/rtm123_1m")
spec = R.default_condition_specs()[1]
fp = R.simulator_fingerprint()
ids = np.sort(np.random.default_rng(seed).choice(int(meta["n_patients"]), n, replace=False))
with np.load(root / "outputs/rtm123_type3_1m/patient_condition_flags/type1_transient_msf.npz") as z:
    saved = {k: z[k][ids] for k in ("eligible", "first_start", "rtm", "true_rtm", "shock_start", "shock_msf", "pc")}
mism = 0
for j, i in enumerate(ids):
    r = R.evaluate_patient(np.asarray(daily[i], np.int16), float(latent[i]), int(seeds[i]), spec,
                           36, 30, R.DEFAULT_MONTHLY_MIN, R.DEFAULT_MAX_SEIZURE_FREE_DAYS)
    ok = (bool(r["eligible"]) == bool(saved["eligible"][j]) and int(r["first_start"]) == int(saved["first_start"][j])
          and bool(r["rtm"]) == bool(saved["rtm"][j]) and int(r["shock_start"]) == int(saved["shock_start"][j])
          and np.float32(r["shock_msf"]) == saved["shock_msf"][j]
          and ((np.isnan(r["pc"]) and np.isnan(saved["pc"][j])) or r["pc"] == saved["pc"][j]))
    mism += (not ok)
res = {"n": n, "seed": seed, "mismatches": int(mism), "simulator_sha256": fp["source_sha256"]}
out.write_text(json.dumps(res, indent=1)); print(res)
