#!/usr/bin/env python3
"""Check paired outputs, including a Fraction-based reference calculation."""
import argparse
import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rtm_anatomy.rtm123 import default_condition_specs


def main(directory):
    checks=[]
    run_manifest=json.loads((directory/'run_manifest.json').read_text())
    metadata=run_manifest['cohort_metadata']
    months=int(metadata['months']); days_per_month=int(metadata['days_per_month'])
    n_raw=int(metadata['n_patients'])
    raw_daily=np.memmap(Path(run_manifest['cohort_dir'])/'daily_counts.int16.memmap', dtype=np.int16, mode='r', shape=(n_raw,months*days_per_month))
    assert int(raw_daily.min())>=0
    raw_monthly=raw_daily.reshape(n_raw,months,days_per_month).sum(axis=2,dtype=np.int32)
    raw_reference=raw_monthly.sum(axis=1)/months
    summaries={r['condition']:r for r in csv.DictReader((directory/'condition_summary.csv').open())}
    with np.load(directory/'patient_condition_flags'/'baseline_perfect.npz') as z:
        perfect_starts=z['first_start']; perfect_eligible=z['eligible']
    input_hashes={}
    analysis_path=Path(__file__).resolve().parents[1]/'rtm_anatomy/rtm123.py'
    assert hashlib.sha256(analysis_path.read_bytes()).hexdigest()==run_manifest['analysis_source_sha256']
    rng=np.random.default_rng(12112026)
    for spec in default_condition_specs():
        with np.load(directory/'patient_condition_flags'/f'{spec.name}.npz') as z:
            a={k:z[k] for k in z.files if k not in ('cache_json','condition_json')}
            cache=json.loads(str(z['cache_json']))
        input_hashes[spec.name]=hashlib.sha256((directory/'patient_condition_flags'/f'{spec.name}.npz').read_bytes()).hexdigest()
        assert cache['source_sha256']==run_manifest['analysis_source_sha256']
        assert all(v.shape==(n_raw,) for v in a.values())
        e=a['eligible'];m=a['rtm'];t=a['true_rtm'];n=int(e.sum())
        assert np.array_equal(a['type3_rtm'],m & ~t)
        assert np.array_equal(a['both_rtm'],m & t)
        assert np.array_equal(a['true_only_rtm'],t & ~m)
        assert not np.any(m & ~e) and not np.any(t & ~e)
        assert int((a['both_rtm']&e).sum()+(a['type3_rtm']&e).sum()+(a['true_only_rtm']&e).sum()+((~m&~t)&e).sum())==n
        if spec.sensitivity==1 and spec.far_per_day==0:
            assert np.array_equal(m,t)
            assert not a['type3_rtm'].any()
        q=(Fraction(str(spec.far_per_day)).limit_denominator(1_000_000)*days_per_month).denominator
        assert np.array_equal(e,a['first_start']>=0)
        assert np.all(a['first_start'][e]<=months-5)
        assert np.all(a['baseline'][e]>0)
        assert np.all(np.isnan(a['pc'][~e]))
        # Recompute strict comparisons for every eligible patient from saved
        # sufficient statistics, without calling the production classifier.
        ref_total=np.rint(a['true_reference'][e]*months).astype(np.int64)
        bn=np.rint(a['baseline'][e]*2*q).astype(np.int64)
        tn=np.rint(a['test'][e]*3*q).astype(np.int64)
        bt=np.rint(a['true_baseline'][e]*2).astype(np.int64)
        tt=np.rint(a['true_test'][e]*3).astype(np.int64)
        sensitivity=Fraction(str(spec.sensitivity)).limit_denominator(1_000_000)
        ref_num=ref_total*sensitivity.numerator*q
        scale=months*sensitivity.denominator
        b_delta=bn*scale-2*ref_num
        t_delta=tn*scale-3*ref_num
        expected_m=(b_delta>0)&(3*b_delta>2*np.abs(t_delta))
        tb_delta=bt*months-2*ref_total
        tt_delta=tt*months-3*ref_total
        expected_t=(tb_delta>0)&(3*tb_delta>2*np.abs(tt_delta))
        assert np.array_equal(m[e],expected_m)
        assert np.array_equal(t[e],expected_t)
        np.testing.assert_allclose(a['reference'],spec.sensitivity*a['true_reference'],rtol=0,atol=1e-12)
        np.testing.assert_allclose(a['pc'][e],100*(1-a['test'][e]/a['baseline'][e]),rtol=0,atol=1e-10)
        selected=np.flatnonzero(e)
        if not spec.type1_intervention:
            np.testing.assert_array_equal(a['true_reference'],raw_reference)
            starts=a['first_start'][e].astype(np.int64)
            expected_true_baseline=(raw_monthly[selected,starts]+raw_monthly[selected,starts+1])/2
            expected_true_test=(raw_monthly[selected,starts+2]+raw_monthly[selected,starts+3]+raw_monthly[selected,starts+4])/3
            np.testing.assert_array_equal(a['true_baseline'][e],expected_true_baseline)
            np.testing.assert_array_equal(a['true_test'][e],expected_true_test)
        sampled=rng.choice(selected,min(2000,len(selected)),replace=False)
        for i in sampled:
            ref=Fraction(int(round(a['true_reference'][i]*months)),months)
            b=Fraction(int(round(a['baseline'][i]*2*q)),2*q)
            test=Fraction(int(round(a['test'][i]*3*q)),3*q)
            measured_ref=ref*Fraction(str(spec.sensitivity))
            observed=b>measured_ref and abs(test-measured_ref)<abs(b-measured_ref)
            bt=Fraction(int(round(a['true_baseline'][i]*2)),2)
            tt=Fraction(int(round(a['true_test'][i]*3)),3)
            latent=bt>ref and abs(tt-ref)<abs(bt-ref)
            assert observed==bool(m[i]) and latent==bool(t[i])
        fixed=a['fixed_eligible']
        assert int(np.isfinite(a['fixed_pc'][fixed]).sum())+int((a['fixed_baseline'][fixed]==0).sum())==int(fixed.sum())
        if spec.rtm_type.startswith('type3'):
            assert np.array_equal(fixed,perfect_eligible)
            assert np.array_equal(a['fixed_first_start'],perfect_starts)
        assert np.all(np.isnan(a['fixed_pc'][~fixed]))
        assert not np.any(a['fixed_rtm'] & ~fixed)
        assert not np.any(a['fixed_type3_rtm'] & ~a['fixed_rtm'])
        row=summaries[spec.name]
        expected_counts={'n_raw':n_raw,'n_eligible':n,'rtm_count':int(m.sum()),
                         'true_rtm_count':int(t.sum()),'type3_count':int((m&~t).sum()),
                         'true_only_count':int((t&~m).sum()),'both_count':int((t&m).sum()),
                         'neither_count':int((e&~m&~t).sum()),'n_mpc':int(np.isfinite(a['pc'][e]).sum()),
                         'n_fixed':int(fixed.sum()),'fixed_n_zero_baseline':int((a['fixed_baseline'][fixed]==0).sum()),
                         'fixed_n_mpc':int(np.isfinite(a['fixed_pc'][fixed]).sum())}
        for key,value in expected_counts.items(): assert int(row[key])==value,(spec.name,key)
        expected_rates={'fraction_eligible':n/n_raw,'fraction_RTM':m.sum()/n,
                        'fraction_true_RTM':t.sum()/n,'fraction_type3':(m&~t).sum()/n,
                        'type3_share_measured_RTM':(m&~t).sum()/m.sum(),
                        'net_measurement_difference_pp':100*(int(m.sum())-int(t.sum()))/n,
                        'MPC':np.nanmedian(a['pc'][e]),'fixed_MPC':np.nanmedian(a['fixed_pc'][fixed]),
                        'fixed_fraction_RTM':a['fixed_rtm'][fixed].mean(),
                        'fixed_fraction_type3':a['fixed_type3_rtm'][fixed].mean()}
        for key,value in expected_rates.items():
            np.testing.assert_allclose(float(row[key]),value,rtol=0,atol=1e-12,err_msg=f'{spec.name}: {key}')
        checks.append({'condition':spec.name,'n_raw':n_raw,'all_selected_integer_recheck':'PASS',
                       'summary_recalculation':'PASS','fixed_windows_and_denominators':'PASS',
                       'true_statistics_vs_raw_cohort':'not applicable to replaced Type1 diary' if spec.type1_intervention else 'PASS','n_selected':n,'paired_partition':'PASS',
                       'fraction_oracle_n':len(sampled),'fraction_oracle':'PASS',
                       'n_type3':int(a['type3_rtm'][e].sum()),
                       'n_true_only':int(a['true_only_rtm'][e].sum())})
    manifest={'checks':checks,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'passed':True,
              'run_manifest_sha256':hashlib.sha256((directory/'run_manifest.json').read_bytes()).hexdigest(),
              'condition_summary_sha256':hashlib.sha256((directory/'condition_summary.csv').read_bytes()).hexdigest(),
              'patient_flags_sha256':input_hashes,
              'scope':'Full-array identities and saved-statistic classifications; all true-count statistics checked against original daily histories in the eight conditions without replacement; independent Fraction sample. Independent detector/selection replay is recorded separately.'}
    (directory/'validation.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);main(p.parse_args().directory)
