#!/usr/bin/env python3
"""Post-review descriptive diagnostics from retained data, without simulation.

Primary outputs are read-only. New results go to the required destination.
Alternative references and random windows are separate estimands, not corrected
versions of the primary result or additive causal decompositions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.stats import poisson

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'outputs/rtm123_type3_1m'
COHORT = ROOT / 'outputs/rtm123_1m'


def pct(mask):
    return float(100 * np.mean(mask)) if len(mask) else None


def write_rows(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def true_entry_at_selected_window(daily, ids, starts, threshold):
    passes = np.zeros(len(ids), dtype=bool)
    for a in range(0, len(ids), 20_000):
        b = min(a + 20_000, len(ids))
        x = daily[ids[a:b, None], starts[a:b, None] * 30 + np.arange(60)]
        counts = x.reshape(-1, 2, 30).sum(2, dtype=np.int64)
        streak = np.zeros(b-a, dtype=np.int16)
        longest = streak.copy()
        for day in range(60):
            streak = np.where(x[:, day] == 0, streak + 1, 0)
            longest = np.maximum(longest, streak)
        passes[a:b] = (counts.sum(1) >= 2*threshold) & (counts.min(1) >= 3) & (longest <= 25)
    return passes


def exact_rtm(bn, tn, total, q=1, sensitivity=1):
    s = Fraction(str(sensitivity))
    bd = bn * 36 * s.denominator - 2 * total * s.numerator * q
    td = tn * 36 * s.denominator - 3 * total * s.numerator * q
    return (bd > 0) & (3 * bd > 2 * np.abs(td))


def at_window(monthly, ids, starts):
    total = monthly[ids].sum(1, dtype=np.int64)
    b = monthly[ids, starts].astype(np.int64) + monthly[ids, starts+1]
    t = monthly[ids, starts+2].astype(np.int64) + monthly[ids, starts+3] + monthly[ids, starts+4]
    result = exact_rtm(b, t, total)
    positive = b > 0
    pc = 100 * (1 - (2*t[positive])/(3*b[positive]))
    return {'n': len(ids), 'rtm_n': int(result.sum()), 'rtm_pct': pct(result), 'mpc_n': int(positive.sum()), 'zero_baseline_n': int((~positive).sum()), 'MPC': float(np.median(pc))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads((COHORT/'cohort_metadata.json').read_text())
    n = meta['n_patients']
    assert n == 1_000_000 and meta['days'] == 1080
    daily = np.memmap(COHORT/'daily_counts.int16.memmap', mode='r', dtype=np.int16, shape=(n,1080))
    monthly = np.empty((n,36), dtype=np.int32)
    for a in range(0,n,20_000):
        monthly[a:a+20_000] = daily[a:a+20_000].reshape(-1,36,30).sum(2, dtype=np.int32)
    totals = monthly.sum(1, dtype=np.int64)
    rows = list(csv.DictReader((RUN/'condition_summary.csv').open()))
    with np.load(RUN/'patient_condition_flags/baseline_perfect.npz') as z:
        perfect_e = z['eligible']
        perfect_rtm = z['rtm']
        perfect_start = z['first_start'].astype(np.int64)
    enrollment_rows, screen_rows, reference_rows, fixed_rows = [], [], [], []
    checks = []
    transient = {}
    for row in rows:
        name = row['condition']
        with np.load(RUN/f'patient_condition_flags/{name}.npz') as z:
            eligible = z['eligible']
            ids = np.flatnonzero(eligible)
            starts = z['first_start'][ids].astype(np.int64)
            measured = z['rtm'][ids]
            truth = z['true_rtm'][ids]
            type3 = z['type3_rtm'][ids]
            assert np.array_equal(type3, measured & ~truth)
            assert int(type3.sum()) == int(row['type3_count'])
            for label, mask in [('First screen', z['first_start']==0), ('Later screen', z['first_start']>0)]:
                group = eligible & mask
                screen_rows.append({'condition':name, 'screen':label, 'n':int(group.sum()), 'share_selected_pct':100*int(group.sum())/len(ids), 'measured_rtm_pct':pct(z['rtm'][group]), 'type3_pct':pct(z['type3_rtm'][group]), 'MPC':float(np.median(z['pc'][group]))})
            if row['rtm_type'] != 'type1':
                passes = true_entry_at_selected_window(daily, ids, starts, float(row['threshold']))
                assert len(ids) == int(row['n_eligible'])
                if float(row['far_per_day']) == 0:
                    assert passes.all(), name
                enrollment_rows.append({'condition':name, 'selected_n':len(ids), 'true_entry_pass_n':int(passes.sum()), 'true_entry_fail_n':int((~passes).sum()), 'true_entry_pass_pct':pct(passes), 'type3_pass_n':int((type3 & passes).sum()), 'type3_fail_n':int((type3 & ~passes).sum()), 'type3_pct_within_pass':pct(type3[passes]), 'type3_pct_within_fail':pct(type3[~passes]), 'type3_fail_share_pct':100*int((type3 & ~passes).sum())/int(type3.sum()) if type3.any() else None})
                assert np.allclose(z['true_reference'][ids], totals[ids]/36, rtol=0, atol=1e-12)
                if float(row['far_per_day']) > 0:
                    correction = Fraction(str(float(row['far_per_day']))).limit_denominator(1_000_000)*30
                    q = correction.denominator
                    bn = np.rint(z['baseline'][ids]*2*q).astype(np.int64)
                    tn = np.rint(z['test'][ids]*3*q).astype(np.int64)
                    primary = exact_rtm(bn,tn,totals[ids],q=q)
                    assert np.array_equal(primary, measured), name
                    lam = float(correction)
                    values = np.arange(int(monthly.max())+1)
                    k = np.floor(lam-values).astype(np.int64)
                    lookup = lam*poisson.sf(k-1,lam)+(values-lam)*poisson.sf(k,lam)
                    for true_count in [0,1,3,10,29,30,31,100]:
                        p = np.arange(0,250)
                        brute = np.sum(np.maximum(true_count+p-lam,0)*poisson.pmf(p,lam))
                        assert abs(brute-lookup[true_count]) < 2e-10
                    expected_ref = np.empty(n, dtype=float)
                    for a in range(0,n,20_000):
                        expected_ref[a:a+20_000] = lookup[monthly[a:a+20_000]].mean(1)
                    b,t = bn/(2*q),tn/(3*q)
                    alt = (t < b) & ((b+t)-2*expected_ref[ids] > 1e-10)
                    assert not np.any(alt & ~primary), name
                    gap = expected_ref[ids]-totals[ids]/36
                    assert gap.min() > -1e-10
                    reference_rows.append({'condition':name,'selected_n':len(ids),'primary_measured_rtm_pct':pct(primary),'expected_reference_measured_rtm_pct':pct(alt),'primary_type3_pct':pct(primary & ~truth),'expected_reference_type3_pct':pct(alt & ~truth),'changed_measured_labels':int((primary != alt).sum()),'mean_reference_increase_events_per_month':float(gap.mean()),'max_reference_increase_events_per_month':float(gap.max())})
            if row['rtm_type'] == 'baseline' or row['rtm_type'].startswith('type3'):
                fixed = z['fixed_eligible']
                assert np.array_equal(fixed,perfect_e)
                assert np.array_equal(z['fixed_first_start'][fixed],perfect_start[fixed])
                m = z['fixed_rtm'][fixed]
                tr = perfect_rtm[fixed]
                mo = z['fixed_type3_rtm'][fixed]
                to = tr & ~m
                assert np.array_equal(mo,m & ~tr)
                fixed_rows.append({'condition':name,'fixed_n':int(fixed.sum()),'both_n':int((m & tr).sum()),'type3_n':int(mo.sum()),'true_only_n':int(to.sum()),'neither_n':int((~m & ~tr).sum()),'measured_rtm_pct':pct(m),'true_rtm_pct':pct(tr),'type3_pct':pct(mo),'true_only_pct':pct(to),'net_pp':100*float(m.mean()-tr.mean())})
            if row['rtm_type'] == 'type1':
                latent = np.load(COHORT/'latent_msf.npy')
                ratio = z['shock_msf'].astype(float)/latent.astype(float)
                shock = z['shock_start'].astype(int)
                start = z['first_start'].astype(int)
                baseline_overlap = (shock < start+2) & (start < shock+2)
                test_overlap = (shock < start+5) & (start+2 < shock+2)
                baseline_only = eligible & baseline_overlap & ~test_overlap
                transient = {'rate_ratio_quantiles_5_50_95':np.quantile(ratio,[.05,.5,.95]).tolist(),'baseline_only_n':int(baseline_only.sum()),'baseline_only_never_perfect_eligible_n':int((baseline_only & ~perfect_e).sum()),'baseline_only_never_perfect_eligible_pct':pct(~perfect_e[baseline_only])}
            checks.append({'condition':name,'primary_partition_and_n':'PASS'})
        print(name, 'PASS', flush=True)
    # New random-window diagnostic; membership remains selected on the perfect detector.
    rng = np.random.default_rng(20261113)
    random_starts = rng.integers(0,32,size=n)
    ids = np.flatnonzero(perfect_e)
    comparator = {'seed':20261113,'selected_window':at_window(monthly,ids,perfect_start[ids]),'random_window_same_perfect_selected_people':at_window(monthly,ids,random_starts[ids]),'all_people_random_window':at_window(monthly,np.arange(n),random_starts),'interpretation':'Post hoc descriptive comparator. Membership remains selected in the same-people row. Random windows need not meet eligibility. Differences are not additive causal effects.'}
    assert comparator['selected_window']['rtm_n'] == int(perfect_rtm.sum())
    write_rows(args.output_dir/'same_window_true_entry.csv',enrollment_rows)
    write_rows(args.output_dir/'screen_timing.csv',screen_rows)
    write_rows(args.output_dir/'expected_reference_sensitivity.csv',reference_rows)
    write_rows(args.output_dir/'fixed_paired_classifications.csv',fixed_rows)
    report = {'post_hoc':True,'full_cohort_n':n,'checks':checks,'reference_definition':'Average conditional expectation of max(true monthly count + Poisson(expected monthly alarms) - expected monthly alarms, 0) over the retained 36-month true path. Enrollment, windows and true RTM flags remain primary. Alternative references change the measured estimand. Strict floating margin tolerance is 1e-10 events/month.','transient':transient,'comparator':comparator,'analysis_source_sha256':hashlib.sha256((ROOT/'rtm_anatomy/rtm123.py').read_bytes()).hexdigest(),'diagnostic_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'numpy_version':np.__version__}
    (args.output_dir/'diagnostics.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
