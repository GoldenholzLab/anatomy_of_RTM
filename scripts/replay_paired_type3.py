#!/usr/bin/env python3
"""Replay retained diary samples independently of the analysis classifier."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from rtm_anatomy.rtm123 import (load_cohort, default_condition_specs, build_type1_diary,
                               simple_chocolates, simulator_fingerprint)


def seed_for(*parts):
    digest = hashlib.blake2b(digest_size=8)
    for part in parts:
        digest.update(str(part).encode('utf-8'))
        digest.update(b'|')
    return int.from_bytes(digest.digest(), 'little') & ((1 << 63) - 1)


def rtm(baseline, test, reference):
    return baseline > reference and abs(test-reference) < abs(baseline-reference)


def main(args):
    if args.evidence is None:
        args.evidence = args.output_dir/'raw_replay_validation.json'
    meta, daily, latent, seeds = load_cohort(args.cohort_dir)
    months, days_per_month = meta['months'], meta['days_per_month']
    ids = np.random.default_rng(args.seed).choice(meta['n_patients'], min(args.n, meta['n_patients']), replace=False)
    with np.load(args.output_dir/'patient_condition_flags/baseline_perfect.npz') as z:
        fixed_starts = z['first_start'][ids]
    results = []
    for spec in default_condition_specs():
        keys = ('first_start', 'rtm', 'true_rtm', 'type3_rtm', 'baseline', 'test',
                'reference', 'true_reference', 'true_baseline', 'true_test',
                'fixed_first_start', 'fixed_eligible', 'fixed_rtm', 'fixed_type3_rtm',
                'fixed_baseline', 'fixed_pc')
        with np.load(args.output_dir/'patient_condition_flags'/f'{spec.name}.npz') as z:
            arrays = {key: z[key][ids] for key in keys}
        differences = []
        for j, idx in enumerate(ids):
            true_daily = daily[idx].astype(np.int64)
            if spec.type1_intervention:
                true_daily = build_type1_diary(true_daily, float(latent[idx]), int(seeds[idx]),
                                              months, days_per_month)[0].astype(np.int64)
            rng = np.random.default_rng(seed_for('detector', spec.name, int(seeds[idx])))
            observed = true_daily.copy() if spec.sensitivity == 1 else rng.binomial(true_daily, spec.sensitivity)
            if spec.far_per_day:
                observed += rng.poisson(spec.far_per_day, size=observed.shape)
            correction = Fraction(str(spec.far_per_day)).limit_denominator(1_000_000)*days_per_month
            q = correction.denominator
            numerator = np.maximum(observed.reshape(months, days_per_month).sum(1)*q-correction.numerator, 0)
            daily_check = np.maximum(observed-int(np.round(spec.far_per_day)), 0)
            true_monthly = true_daily.reshape(months, days_per_month).sum(1)
            reference = Fraction(int(true_monthly.sum()), months)
            measured_reference = reference*Fraction(str(spec.sensitivity))
            start = -1
            for candidate in range(months-4):
                if int(numerator[candidate:candidate+2].sum()) < spec.threshold*2*q:
                    continue
                if int(numerator[candidate:candidate+2].min()) < 3*q:
                    continue
                baseline_daily = daily_check[candidate*days_per_month:(candidate+2)*days_per_month]
                boundaries = np.flatnonzero(np.r_[True, baseline_daily > 0, True])
                if int(np.max(np.diff(boundaries)-1)) <= 25:
                    start = candidate
                    break
            checks = {'first_start': start, 'reference': float(measured_reference),
                      'true_reference': float(reference)}
            fixed_start = int(fixed_starts[j]) if spec.rtm_type.startswith('type3') else start
            for prefix, selected_start in [('', start), ('fixed_', fixed_start)]:
                if prefix:
                    checks.update(fixed_first_start=selected_start, fixed_eligible=selected_start >= 0)
                if selected_start < 0:
                    checks.update({prefix+'rtm': False, prefix+'type3_rtm': False})
                    continue
                s = selected_start
                baseline = Fraction(int(numerator[s:s+2].sum()), 2*q)
                test = Fraction(int(numerator[s+2:s+5].sum()), 3*q)
                true_baseline = Fraction(int(true_monthly[s:s+2].sum()), 2)
                true_test = Fraction(int(true_monthly[s+2:s+5].sum()), 3)
                measured_rtm = rtm(baseline, test, measured_reference)
                true_rtm = rtm(true_baseline, true_test, reference)
                checks.update({prefix+'rtm': measured_rtm,
                               prefix+'type3_rtm': measured_rtm and not true_rtm,
                               prefix+'baseline': float(baseline)})
                if prefix:
                    checks['fixed_pc'] = 100*(1-float(test)/float(baseline)) if baseline else np.nan
                else:
                    checks.update(test=float(test), true_baseline=float(true_baseline),
                                  true_test=float(true_test), true_rtm=true_rtm)
            for key, expected in checks.items():
                actual = arrays[key][j]
                if isinstance(expected, (float, np.floating)):
                    same = np.isclose(expected, actual, atol=1e-10, rtol=0, equal_nan=True)
                else:
                    same = expected == actual
                if not same:
                    differences.append({'patient': int(idx), 'key': key,
                                        'expected': str(expected), 'actual': str(actual)})
        results.append({'condition': spec.name, 'sample_n': len(ids), 'differences': differences})
        print(f'{spec.name}: {len(ids)} replayed, {len(differences)} differences', flush=True)
    generation_differences = []
    for idx in ids:
        generated, rate = simple_chocolates(meta['days'], rng=np.random.default_rng(int(seeds[idx])))
        if not np.array_equal(np.asarray(generated, dtype=np.int16), daily[idx]):
            generation_differences.append({'patient': int(idx), 'key': 'daily_counts'})
        if np.float32(np.asarray(rate).item()) != latent[idx]:
            generation_differences.append({'patient': int(idx), 'key': 'latent_msf'})
    print(f'Cohort generation: {len(ids)} replayed, {len(generation_differences)} differences', flush=True)
    evidence = {'passed': all(not row['differences'] for row in results) and not generation_differences,
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'run_manifest_sha256': hashlib.sha256((args.output_dir/'run_manifest.json').read_bytes()).hexdigest(),
                'sample_seed': args.seed, 'sample_ids_sha256': hashlib.sha256(ids.tobytes()).hexdigest(),
                'cohort_dir': str(args.cohort_dir.resolve()), 'output_dir': str(args.output_dir.resolve()),
                'conditions': results, 'cohort_generation_sample_n': len(ids),
                'cohort_generation_differences': generation_differences,
                'current_simulator': simulator_fingerprint(),
                'limit': 'Type1 replacement segments reuse the production generator; detector, eligibility, rational RTM and fixed-window calculations are independently implemented. Sampled regeneration agreement does not prove the historical generator version or full-cohort identity.'}
    args.evidence.write_text(json.dumps(evidence, indent=2)+'\n')
    if not evidence['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort-dir', type=Path, default=PROJECT_ROOT/'outputs/rtm123_1m')
    parser.add_argument('--output-dir', type=Path, default=PROJECT_ROOT/'outputs/rtm123_type3_1m')
    parser.add_argument('--evidence', type=Path, default=None)
    parser.add_argument('--n', type=int, default=500)
    parser.add_argument('--seed', type=int, default=11212026)
    main(parser.parse_args())
