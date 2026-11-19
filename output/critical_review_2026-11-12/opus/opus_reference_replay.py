"""Subsample replay of detector conditions with alternative measured-scale references.

Read-only with respect to repository data. Writes only the JSON given as argv[2].

1. Reproduces saved per-patient flags with the current analysis code on a random
   subsample (exactness check).
2. For each detector condition, reclassifies measured RTM in the same selected
   window against alternative measured-scale references:
   a. 'expected': mean over the 36 months of E[corrected month | true month],
      the analogue of s*R that accounts for alarm subtraction and flooring.
   b. 'empirical': the observed corrected 36-month mean of the same measured diary.
   and reports Type 3 prevalence/share under each.
3. Splits Type 3 by whether the participant would pass the reference
   eligibility rule on true counts in any window.

Usage: python3 -I -B opus_reference_replay.py <repo_root> <out_json> [n] [seed]
"""
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.stats import poisson, binom

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
SEED = int(sys.argv[4]) if len(sys.argv) > 4 else 20261112
sys.path.insert(0, str(root))
from rtm_anatomy import rtm123 as R  # noqa: E402

meta, daily, latent, seeds = R.load_cohort(root / "outputs/rtm123_1m")
months, dpm = int(meta["months"]), int(meta["days_per_month"])
flags_dir = root / "outputs/rtm123_type3_1m/patient_condition_flags"
ids = np.sort(np.random.default_rng(SEED).choice(int(meta["n_patients"]), N, replace=False))
with np.load(flags_dir / "baseline_perfect.npz") as z:
    base_start = z["first_start"][ids]
    base_elig = z["eligible"][ids]

specs = {s.name: s for s in R.default_condition_specs()}
targets = ["type3_sensitivity_90", "type3_sensitivity_70", "type3_far_1_per_month",
           "type3_far_1_per_week", "type3_far_1_per_day"]


def expected_corrected_month(true_month_counts, sens, far_per_day):
    """E[max(Binom(x, s) + Poisson(30*far) - c, 0)] for each month, c = 30*far."""
    lam = far_per_day * dpm
    c = float(Fraction(str(far_per_day)).limit_denominator(1_000_000) * dpm)
    out_vals = np.empty(len(true_month_counts))
    nmax = int(lam + 12 * np.sqrt(lam) + 30) if lam > 0 else 0
    n_alarm = np.arange(nmax + 1)
    p_alarm = poisson.pmf(n_alarm, lam) if lam > 0 else np.array([1.0])
    for i, x in enumerate(true_month_counts):
        x = int(x)
        k = np.arange(x + 1)
        p_det = binom.pmf(k, x, sens) if sens < 1 else np.r_[np.zeros(x), 1.0]
        tot = (k[:, None] + n_alarm[None, :]).ravel()
        prob = (p_det[:, None] * p_alarm[None, :]).ravel()
        out_vals[i] = float(np.sum(prob * np.maximum(tot - c, 0.0)))
    return out_vals


def rtm(b, t, ref):
    return (b > ref) and (abs(t - ref) < (b - ref))


report = {"n_subsample": N, "seed": SEED, "conditions": {}}
for name in targets:
    spec = specs[name]
    with np.load(flags_dir / f"{name}.npz") as z:
        saved = {k: z[k][ids] for k in ("eligible", "first_start", "rtm", "true_rtm", "type3_rtm",
                                        "true_only_rtm", "fixed_rtm", "fixed_type3_rtm", "pc", "fixed_pc")}
    mism = 0
    cnt = dict(sel=0, m_code=0, t_code=0, t3_code=0, to_code=0,
               m_exp=0, t3_exp=0, to_exp=0, m_emp=0, t3_emp=0, to_emp=0,
               t3_not_true_elig=0, sel_not_true_elig=0)
    gap = []
    for j, idx in enumerate(ids):
        true_daily = np.asarray(daily[idx], dtype=np.int16)
        res = R.evaluate_patient(true_daily, float(latent[idx]), int(seeds[idx]), spec, months, dpm,
                                 R.DEFAULT_MONTHLY_MIN, R.DEFAULT_MAX_SEIZURE_FREE_DAYS,
                                 int(base_start[j]))
        for key in ("eligible", "first_start", "rtm", "true_rtm", "type3_rtm", "true_only_rtm",
                    "fixed_rtm", "fixed_type3_rtm"):
            if bool(res[key] != saved[key][j]) if key != "first_start" else int(res[key]) != int(saved[key][j]):
                mism += 1
                break
        if not res["eligible"]:
            continue
        cnt["sel"] += 1
        cnt["m_code"] += res["rtm"]
        cnt["t_code"] += res["true_rtm"]
        cnt["t3_code"] += res["type3_rtm"]
        cnt["to_code"] += res["true_only_rtm"]
        if not base_elig[j]:
            cnt["sel_not_true_elig"] += 1
            cnt["t3_not_true_elig"] += res["type3_rtm"]
        # Rebuild measured monthly corrected counts exactly as the code does
        rng = np.random.default_rng(R.stable_seed("detector", spec.name, int(seeds[idx])))
        _, monthly = R.apply_detector(true_daily, spec.sensitivity, spec.far_per_day, rng,
                                      spec.correct_far, dpm)
        true_monthly = R.monthly_from_daily(true_daily, dpm)
        s = res["first_start"]
        b = monthly[s:s + 2].mean()
        t = monthly[s + 2:s + 5].mean()
        ref_exp = expected_corrected_month(true_monthly, spec.sensitivity, spec.far_per_day).mean()
        ref_emp = monthly.mean()
        gap.append(ref_exp - res["reference"])
        m_exp = rtm(b, t, ref_exp)
        m_emp = rtm(b, t, ref_emp)
        tr = res["true_rtm"]
        cnt["m_exp"] += m_exp
        cnt["t3_exp"] += m_exp and not tr
        cnt["to_exp"] += tr and not m_exp
        cnt["m_emp"] += m_emp
        cnt["t3_emp"] += m_emp and not tr
        cnt["to_emp"] += tr and not m_emp
    sel = cnt["sel"]
    pct = lambda k: 100.0 * cnt[k] / sel
    report["conditions"][name] = {
        "patients_with_any_flag_mismatch_vs_saved": mism,
        "selected": sel,
        "code_reference": {"measured_rtm_pct": pct("m_code"), "true_rtm_pct": pct("t_code"),
                           "type3_pct": pct("t3_code"), "true_only_pct": pct("to_code"),
                           "type3_share_of_measured": 100.0 * cnt["t3_code"] / max(1, cnt["m_code"])},
        "expected_corrected_reference": {"measured_rtm_pct": pct("m_exp"), "type3_pct": pct("t3_exp"),
                                         "true_only_pct": pct("to_exp"),
                                         "type3_share_of_measured": 100.0 * cnt["t3_exp"] / max(1, cnt["m_exp"])},
        "empirical_measured_reference": {"measured_rtm_pct": pct("m_emp"), "type3_pct": pct("t3_emp"),
                                         "true_only_pct": pct("to_emp"),
                                         "type3_share_of_measured": 100.0 * cnt["t3_emp"] / max(1, cnt["m_emp"])},
        "mean_expected_ref_minus_code_ref": float(np.mean(gap)),
        "median_expected_ref_minus_code_ref": float(np.median(gap)),
        "selected_not_true_eligible_pct": pct("sel_not_true_elig"),
        "type3_from_not_true_eligible_share": cnt["t3_not_true_elig"] / max(1, cnt["t3_code"]),
    }
    print(name, json.dumps(report["conditions"][name], indent=1), flush=True)

out.write_text(json.dumps(report, indent=1))
