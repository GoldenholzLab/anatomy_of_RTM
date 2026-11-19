#!/usr/bin/env python3
"""Check paired outputs, including a Fraction-based reference calculation."""
import argparse
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
    rng=np.random.default_rng(12112026)
    for spec in default_condition_specs():
        with np.load(directory/'patient_condition_flags'/f'{spec.name}.npz') as z:
            a={k:z[k] for k in z.files if k not in ('cache_json','condition_json')}
        e=a['eligible'];m=a['rtm'];t=a['true_rtm'];n=int(e.sum())
        assert np.array_equal(a['type3_rtm'],m & ~t)
        assert np.array_equal(a['both_rtm'],m & t)
        assert np.array_equal(a['true_only_rtm'],t & ~m)
        assert not np.any(m & ~e) and not np.any(t & ~e)
        assert int((a['both_rtm']&e).sum()+(a['type3_rtm']&e).sum()+(a['true_only_rtm']&e).sum()+((~m&~t)&e).sum())==n
        if spec.sensitivity==1 and spec.far_per_day==0:
            assert np.array_equal(m,t)
            assert not a['type3_rtm'].any()
        q=(Fraction(str(spec.far_per_day)).limit_denominator(1_000_000)*30).denominator
        selected=np.flatnonzero(e)
        sampled=rng.choice(selected,min(2000,len(selected)),replace=False)
        for i in sampled:
            ref=Fraction(int(round(a['true_reference'][i]*36)),36)
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
        checks.append({'condition':spec.name,'n_selected':n,'paired_partition':'PASS',
                       'fraction_oracle_n':len(sampled),'fraction_oracle':'PASS',
                       'n_type3':int(a['type3_rtm'][e].sum()),
                       'n_true_only':int(a['true_only_rtm'][e].sum())})
    manifest={'checks':checks,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'passed':True}
    (directory/'validation.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);main(p.parse_args().directory)
