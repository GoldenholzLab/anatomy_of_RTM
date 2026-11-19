"""Targeted 12,000-person replay for false-alarm correction/reference sensitivity."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import numpy as np
from scipy.stats import poisson

ROOT=Path(__file__).resolve().parents[3]
DEST=Path(__file__).resolve().parent
N=12_000
ids=np.sort(np.random.default_rng(633791).choice(1_000_000,N,replace=False))
seeds=np.load(ROOT/'outputs/rtm123_1m/patient_seeds.npy',mmap_mode='r')
diary=np.memmap(ROOT/'outputs/rtm123_1m/daily_counts.int16.memmap',dtype='int16',mode='r',shape=(1_000_000,1080))
true=np.asarray(diary[ids],dtype=np.int64)
truem=true.reshape(N,36,30).sum(2)
trueref=truem.mean(1)
def sseed(*parts):
    d=hashlib.blake2b(digest_size=8)
    for p in parts:d.update(str(p).encode());d.update(b'|')
    return int.from_bytes(d.digest(),'little')&((1<<63)-1)
name='type3_far_1_per_day'
observed=np.empty_like(true)
for j,i in enumerate(ids):observed[j]=true[j]+np.random.default_rng(sseed('detector',name,int(seeds[i]))).poisson(1,size=1080)
unfloored=observed.reshape(N,36,30).sum(2)-30
corrected=np.maximum(unfloored,0)
def select(monthly,daily):
    starts=np.full(N,-1)
    for j in range(32):
        possible=np.flatnonzero((starts<0)&(monthly[:,j:j+2].sum(1)>=8)&(monthly[:,j:j+2].min(1)>=3))
        for i in possible:
            zeros=run=0
            for c in daily[i,j*30:(j+2)*30]:
                run=run+1 if c<=0 else 0;zeros=max(zeros,run)
            if zeros<=25:starts[i]=j
    return starts
starts=select(corrected,np.maximum(observed-1,0));e=starts>=0
saved=np.load(ROOT/f'outputs/rtm123_type3_1m/patient_condition_flags/{name}.npz')
assert np.array_equal(starts,saved['first_start'][ids])
ix=np.flatnonzero(e);s=starts[e]
def getBT(x):
    return (x[ix,s]+x[ix,s+1])/2,(x[ix,s+2]+x[ix,s+3]+x[ix,s+4])/3
bt,tt=getBT(truem)
def rtm(b,t,r):return (b>r)&(abs(t-r)<(b-r))
def exact_rtm(b,t,total):
    bn=np.rint(2*b).astype(np.int64);tn=np.rint(3*t).astype(np.int64)
    db=bn*36-2*total;dt=tn*36-3*total
    return (db>0)&(3*db>2*abs(dt))
truth=exact_rtm(bt,tt,truem.sum(1)[e])
assert np.array_equal(truth,saved['true_rtm'][ids][e])
b,t=getBT(corrected)
# Use exact integer comparisons for the primary integer-rate reference.
R=truem.sum(1)[e];B=np.rint(2*b).astype(int);T=np.rint(3*t).astype(int)
primary=(B*36-2*R>0)&(3*(B*36-2*R)>2*abs(T*36-3*R))
assert np.array_equal(primary,saved['rtm'][ids][e])
# Exact conditional expected monthly floored count, given the retained true monthly count.
# For P~Poisson(30), E[(T+P-30)+] = 30 Pr(P>=k) + (T-30) Pr(P>k), k=floor(30-T).
k=30-truem
expected=30*poisson.sf(k-1,30)+(truem-30)*poisson.sf(k,30)
expected_ref=expected.mean(1)
# Sample verification of this formula against direct finite-sum expectations.
v=np.arange(0,200)
for z in [0,1,3,10,29,30,31,100]:
    brute=float((np.maximum(z+v-30,0)*poisson.pmf(v,30)).sum())
    fast=float(30*poisson.sf(29-z,30)+(z-30)*poisson.sf(30-z,30))
    assert abs(brute-fast)<1e-10
rows=[]
for label,bb,ttt,ref in [('primary_floored_internal_true_reference',b,t,trueref[e]),('floored_conditional_expected_reference',b,t,expected_ref[e]),('floored_measured_full_history_reference',b,t,corrected.mean(1)[e]),('unfloored_test_internal_true_reference',*getBT(unfloored),trueref[e])]:
    if label.startswith('primary_'):m=primary
    elif label=='unfloored_test_internal_true_reference':m=exact_rtm(bb,ttt,truem.sum(1)[e])
    elif label=='floored_measured_full_history_reference':m=exact_rtm(bb,ttt,corrected.sum(1)[e])
    else:m=rtm(bb,ttt,ref)
    rows.append({'scenario':label,'selected_n':int(e.sum()),'measured_rtm_pct':float(100*m.mean()),'type3_pct':float(100*(m&~truth).mean()),'MPC':float(np.median(100*(1-ttt/bb))),'measured_classifications_changed_vs_primary':int((m!=primary).sum())})
result={'sample_n':N,'sample_seed':633791,'sample_ids_sha256':hashlib.sha256(ids.tobytes()).hexdigest(),'sample_selected_n':int(e.sum()),'primary_window_and_classification_replay':'PASS','scenarios':rows,'reference_gap_selected':{'median':float(np.median((expected_ref-trueref)[e])),'mean':float(np.mean((expected_ref-trueref)[e]))},'daily_rule_sensitivity':[],'limitations':'Exploratory sample, not a replacement analysis. Alternative references change the estimand. Unfloored corrected values may be negative. The conditional expectation reference averages the retained true monthly path, not a newly simulated independent reference diary.'}
for label,dd in [('recorded_events_no_daily_subtraction',observed),('oracle_true_daily_events',true)]:
    ss=select(corrected,dd)
    result['daily_rule_sensitivity'].append({'daily_rule':label,'selected_n':int((ss>=0).sum()),'windows_changed':int((ss!=starts).sum()),'membership_changed':int(((ss>=0)!=e).sum())})
(DEST/'correction_sensitivity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
