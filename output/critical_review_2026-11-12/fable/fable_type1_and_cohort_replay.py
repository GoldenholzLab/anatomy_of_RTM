"""Fable review, check 4: regenerate sample cohort rows and replay the transient-rate condition.

Read-only. Loads the sibling simulator file without writing bytecode. The
transient recipe is re-implemented here from the manuscript and manifest
description; only the simulator itself is shared with production. Also measures
how often the simulator's cycle component is active at one sample per day.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
COHORT = ROOT / "outputs" / "rtm123_1m"
RUN = ROOT / "outputs" / "rtm123_type3_1m"
SIM = ROOT.parent / "CHOCOLATE" / "realSim_turbo.py"
OUT = Path(__file__).resolve().parent / "fable_type1_cohort_replay.json"
MONTHS, DPM, N = 36, 30, 1_000_000


def load_sim():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("fable_sim", SIM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seed_for(*parts):
    d = hashlib.blake2b(digest_size=8)
    for p in parts:
        d.update(str(p).encode()); d.update(b"|")
    return int.from_bytes(d.digest(), "little") & ((1 << 63) - 1)


def zero_run(x):
    nz = np.flatnonzero(np.r_[True, x > 0, True])
    return int(np.max(np.diff(nz) - 1))


def main(n=1500, offset=400_000):
    sim = load_sim()
    daily = np.memmap(COHORT / "daily_counts.int16.memmap", dtype=np.int16, mode="r", shape=(N, MONTHS * DPM))
    seeds = np.load(COHORT / "patient_seeds.npy", mmap_mode="r")
    latent = np.load(COHORT / "latent_msf.npy", mmap_mode="r")
    ids = np.arange(offset, offset + n)
    with np.load(RUN / "patient_condition_flags" / "type1_transient_msf.npz") as z:
        saved = {k: z[k][ids] for k in ("first_start", "rtm", "shock_start", "shock_msf", "true_reference",
                                         "baseline", "test", "pc")}
    report = {"simulator_sha256": hashlib.sha256(SIM.read_bytes()).hexdigest(),
              "numpy_version": np.__version__, "n": int(n), "first_id": int(offset)}
    gen_diff = 0
    t1 = {"shock_start": 0, "shock_msf": 0, "first_start": 0, "rtm": 0, "true_reference": 0, "baseline": 0, "test": 0}
    for j, i in enumerate(ids):
        seed = int(seeds[i])
        # 1. Does today's simulator file regenerate the stored history from the stored seed?
        gen, rate = sim.simple_CHOCOLATES(daysNeeded=MONTHS * DPM, rng=np.random.default_rng(seed))
        if (not np.array_equal(np.asarray(gen, dtype=np.int16), daily[i])
                or np.float32(np.asarray(rate).item()) != latent[i]):
            gen_diff += 1
        # 2. Transient-rate condition, written from the Methods text.
        rng = np.random.default_rng(seed_for("type1", seed))
        start = int(rng.integers(0, MONTHS - 2 + 1))
        msf = float(np.asarray(sim.get_mSF(requested_msf=-1, rng=rng)).item())
        seg, _ = sim.simple_CHOCOLATES(daysNeeded=2 * DPM, defaultSeizureFreq=msf, rng=rng)
        hist = np.asarray(daily[i]).astype(np.int64).copy()
        hist[start * DPM:(start + 2) * DPM] = np.asarray(seg, dtype=np.int16)
        mon = hist.reshape(MONTHS, DPM).sum(1)
        first = -1
        for s in range(MONTHS - 4):
            if mon[s] + mon[s + 1] >= 8 and min(mon[s], mon[s + 1]) >= 3 and zero_run(hist[s * DPM:(s + 2) * DPM]) <= 25:
                first = s
                break
        ref = Fraction(int(mon.sum()), MONTHS)
        t1["shock_start"] += int(start != int(saved["shock_start"][j]))
        t1["shock_msf"] += int(abs(np.float32(msf) - saved["shock_msf"][j]) > 0)
        t1["first_start"] += int(first != int(saved["first_start"][j]))
        t1["true_reference"] += int(abs(float(ref) - saved["true_reference"][j]) > 1e-10)
        if first >= 0:
            B = Fraction(int(mon[first:first + 2].sum()), 2)
            T = Fraction(int(mon[first + 2:first + 5].sum()), 3)
            rtm = B > ref and abs(T - ref) < B - ref
            t1["rtm"] += int(rtm != bool(saved["rtm"][j]))
            t1["baseline"] += int(abs(float(B) - saved["baseline"][j]) > 1e-10)
            t1["test"] += int(abs(float(T) - saved["test"][j]) > 1e-10)
    report["cohort_rows_not_regenerated"] = gen_diff
    report["type1_differences_vs_saved"] = t1
    report["type1_replay_matches_saved"] = all(v == 0 for v in t1.values())

    # 3. Cycle component at one sample per day: how many simulated people get a nonzero cycle?
    rng = np.random.default_rng(7)
    active = 0
    trials = 100_000
    for _ in range(trials):
        cp = sim.make_key_cycle_params(rng=rng)
        if len(cp) == 0:
            continue
        freqs, amps = cp
        if any((1 > 2 * f) and a != 0 for f, a in zip(freqs, amps)):
            active += 1
    report["pct_people_with_active_cycle_at_daily_sampling"] = 100 * active / trials

    # 4. Size of the transient relative to the person's own rate.
    with np.load(RUN / "patient_condition_flags" / "type1_transient_msf.npz") as z:
        shock = z["shock_msf"].astype(np.float64)
    lat = np.asarray(latent, dtype=np.float64)
    ratio = shock / lat
    report["transient_vs_own_latent_rate"] = {
        "pct_higher": 100 * float((shock > lat).mean()),
        "ratio_quantiles_5_25_50_75_95": [float(x) for x in np.quantile(ratio, [0.05, 0.25, 0.5, 0.75, 0.95])],
        "pct_ratio_above_3": 100 * float((ratio > 3).mean()),
        "pct_ratio_below_one_third": 100 * float((ratio < 1 / 3).mean()),
    }
    print(json.dumps(report, indent=1))
    OUT.write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
