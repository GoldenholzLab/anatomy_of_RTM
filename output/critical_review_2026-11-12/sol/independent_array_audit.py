"""Read saved arrays and DOCX tables without calling production classifiers."""
from pathlib import Path
from zipfile import ZipFile
from fractions import Fraction
import csv
import hashlib
import json
import math
import sys
import numpy as np
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).resolve().parent
RESULT = ROOT / 'outputs/rtm123_type3_1m'
def rows(name):
    return list(csv.DictReader((RESULT / name).open()))
summary = rows('condition_summary.csv')
meta = json.loads((RESULT / 'run_manifest.json').read_text())
n, months, days = 1_000_000, 36, 30
raw = np.memmap(ROOT / 'outputs/rtm123_1m/daily_counts.int16.memmap', dtype='int16', mode='r', shape=(n, months * days))
monthly = raw.reshape(n, months, days).sum(axis=2, dtype=np.int64)
latent = np.load(ROOT / 'outputs/rtm123_1m/latent_msf.npy', mmap_mode='r')
raw_totals = monthly.sum(axis=1)
perfect = np.load(RESULT / 'patient_condition_flags/baseline_perfect.npz')
fixed_starts = perfect['first_start']
fixed_e = perfect['eligible']
answer = {'environment': {'python': sys.version, 'numpy': np.__version__}, 'conditions': [], 'docx_table_checks': [], 'source_hashes': {}}
for row in summary:
    name = row['condition']
    with np.load(RESULT / f'patient_condition_flags/{name}.npz') as z:
        a = {key: z[key] for key in z.files if key not in ('cache_json', 'condition_json')}
        cache = json.loads(str(z['cache_json']))
    e, m, t = a['eligible'], a['rtm'], a['true_rtm']
    N = int(e.sum())
    counts = {'both_count': int((e & m & t).sum()), 'type3_count': int((e & m & ~t).sum()), 'true_only_count': int((e & ~m & t).sum()), 'neither_count': int((e & ~m & ~t).sum())}
    assert sum(counts.values()) == N
    assert not ((m | t) & ~e).any()
    assert np.array_equal(a['type3_rtm'], m & ~t)
    assert np.array_equal(a['both_rtm'], m & t)
    assert np.array_equal(a['true_only_rtm'], ~m & t)
    assert np.array_equal(e, a['first_start'] >= 0)
    assert a['first_start'].min() >= -1 and a['first_start'].max() <= 31
    q = (Fraction(row['far_per_day']).limit_denominator(1_000_000)*30).denominator
    sens = Fraction(row['sensitivity'])
    R = np.rint(a['true_reference'][e] * months).astype(np.int64)
    B = np.rint(a['baseline'][e]*2*q).astype(np.int64)
    T = np.rint(a['test'][e]*3*q).astype(np.int64)
    BT = np.rint(a['true_baseline'][e]*2).astype(np.int64)
    TT = np.rint(a['true_test'][e]*3).astype(np.int64)
    def classify(B, T, R, reference_months, p=Fraction(1), q=1):
        b = B*reference_months*p.denominator - 2*R*p.numerator*q
        t = T*reference_months*p.denominator - 3*R*p.numerator*q
        return (b > 0) & (3*b > 2*abs(t))
    em = classify(B,T,R,36,sens,q)
    et = classify(BT,TT,R,36)
    assert np.array_equal(em,m[e]) and np.array_equal(et,t[e])
    pc = 100*(1-a['test'][e]/a['baseline'][e])
    np.testing.assert_allclose(pc,a['pc'][e],atol=1e-10,rtol=0)
    rcounts={'n_eligible':N,'rtm_count':int(m.sum()),'true_rtm_count':int(t.sum()),**counts,'n_mpc':int(np.isfinite(pc).sum())}
    for key,value in rcounts.items(): assert int(row[key]) == value,(name,key)
    rates={'fraction_eligible':N/n,'fraction_RTM':m.sum()/N,'fraction_true_RTM':t.sum()/N,'fraction_type3':counts['type3_count']/N,'type3_share_measured_RTM':counts['type3_count']/m.sum(),'net_measurement_difference_pp':100*(counts['type3_count']-counts['true_only_count'])/N,'MPC':np.median(pc)}
    for key,value in rates.items(): assert abs(float(row[key])-value) < 1e-11,(name,key)
    zscore=1.959963984540054
    for prefix, k in [('fraction_RTM',int(m.sum())),('fraction_type3',counts['type3_count'])]:
        p=k/N;d=1+zscore**2/N;c=(p+zscore**2/(2*N))/d;h=zscore*math.sqrt(p*(1-p)/N+zscore**2/(4*N*N))/d
        assert abs(float(row[prefix+'_ci_lo'])-max(0,c-h))<1e-12
        assert abs(float(row[prefix+'_ci_hi'])-min(1,c+h))<1e-12
    vals=np.sort(pc);lo=max(0,math.floor(N/2-.98*math.sqrt(N))-1);hi=min(N-1,math.ceil(N/2+.98*math.sqrt(N)))
    assert float(row['MPC_ci_lo'])==vals[lo] and float(row['MPC_ci_hi'])==vals[hi]
    if name != 'type1_transient_msf':
        assert np.array_equal(a['true_reference']*36, raw_totals)
        ix=np.flatnonzero(e);s=a['first_start'][e].astype(int)
        assert np.array_equal(BT, monthly[ix,s]+monthly[ix,s+1])
        assert np.array_equal(TT, monthly[ix,s+2]+monthly[ix,s+3]+monthly[ix,s+4])
    f=a['fixed_eligible'];NF=int(f.sum());pcf=a['fixed_pc'][f]
    assert NF==int(row['n_fixed'])
    assert int((a['fixed_baseline'][f]==0).sum())==int(row['fixed_n_zero_baseline'])
    assert int(np.isfinite(pcf).sum())==int(row['fixed_n_mpc'])
    assert abs(np.nanmedian(pcf)-float(row['fixed_MPC']))<1e-11
    assert abs(a['fixed_rtm'][f].mean()-float(row['fixed_fraction_RTM']))<1e-12
    assert abs(a['fixed_type3_rtm'][f].mean()-float(row['fixed_fraction_type3']))<1e-12
    if name.startswith('type3'):
        assert np.array_equal(f,fixed_e) and np.array_equal(a['fixed_first_start'],fixed_starts)
        fix=np.flatnonzero(f);fs=fixed_starts[f].astype(int)
        fb=monthly[fix,fs]+monthly[fix,fs+1]
        ft=monthly[fix,fs+2]+monthly[fix,fs+3]+monthly[fix,fs+4]
        ftrue=classify(fb,ft,raw_totals[f],36)
        assert np.array_equal(a['fixed_type3_rtm'][f],a['fixed_rtm'][f]&~ftrue)
    for wr in rows('first_eligible_windows.csv'):
        if wr['condition']==name:
            nc=int((a['first_start']==int(wr['first_eligible_month'])).sum())
            assert nc==int(wr['n_patients']) and abs(nc/n-float(wr['fraction_raw']))<1e-12
    # Sensitivity analysis from saved totals only. Membership and trial window stay fixed.
    outside=R-BT-TT
    lm=classify(B,T,outside,31,sens,q);lt=classify(BT,TT,outside,31)
    tie_m=int(((B*36*sens.denominator-2*R*sens.numerator*q>0)&(3*(B*36*sens.denominator-2*R*sens.numerator*q)==2*abs(T*36*sens.denominator-3*R*sens.numerator*q))).sum())
    ent={'condition':name,'n_eligible':N,**counts,**rates,'fixed_n':NF,'fixed_n_mpc':int(np.isfinite(pcf).sum()),'fixed_n_zero_baseline':int((a['fixed_baseline'][f]==0).sum()),'fixed_MPC':float(np.nanmedian(pcf)),'strict_distance_ties_measured':tie_m,'leave_trial_out_reference_sensitivity':{'measured_rtm_pct':100*lm.mean(),'true_rtm_pct':100*lt.mean(),'type3_pct':100*(lm&~lt).mean(),'measured_classifications_changed':int((lm!=m[e]).sum()),'true_classifications_changed':int((lt!=t[e]).sum())},'cache_analysis_hash_matches':cache['source_sha256']==meta['analysis_source_sha256'],'true_zero_baseline_n':int((a['true_baseline'][e]==0).sum())}
    if name=='type1_transient_msf':
        s=a['first_start'];j=a['shock_start'];ob=(j<s+2)&(s<j+2)&e;ot=(j<s+5)&(s+2<j+2)&e
        ent['overlap_direction']=[]
        for label, mask in [('baseline',ob&~ot),('baseline_and_test',ob&ot),('test',ot&~ob),('neither',e&~ob&~ot)]:
            for dr,dmask in [('all',np.ones(n,dtype=bool)),('higher',a['shock_msf']>latent),('lower',a['shock_msf']<latent)]:
                z=mask&dmask
                ent['overlap_direction'].append({'overlap':label,'direction':dr,'n':int(z.sum()),'rtm_pct':100*float(m[z].mean()),'MPC':float(np.median(a['pc'][z]))})
    answer['conditions'].append(ent)
    print(name,N,counts['type3_count'],'PASS',flush=True)

ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
def tables(name):
    with ZipFile(ROOT/name) as z: root=E.fromstring(z.read('word/document.xml'))
    return [[[''.join(c.xpath('.//w:t/text()',namespaces=ns)) for c in row.xpath('./w:tc',namespaces=ns)] for row in table.xpath('./w:tr',namespaces=ns)] for table in root.xpath('//w:tbl',namespaces=ns)]
main=tables('anatomy_of_RTM_Seizure.docx')[0]
sup=tables('anatomy_of_RTM_Seizure_Supplement.docx')
fnum=lambda x:f'{int(x):,}'
for i,row in enumerate(summary,1):
    expected=[fnum(row['n_eligible'])]+[f'{float(row[k])*100:.1f}' for k in ['fraction_RTM','fraction_true_RTM','fraction_type3']]+[f'{float(row["MPC"]):.1f}']
    assert main[i][1:]==expected,(i,main[i],expected)
    expected=[fnum(row[k]) for k in ['n_eligible','both_count','type3_count','true_only_count','neither_count']]
    assert sup[0][i][1:]==expected
    expected=[f'{float(row["fraction_type3"])*100:.1f}',f'{float(row["fraction_type3_ci_lo"])*100:.1f} to {float(row["fraction_type3_ci_hi"])*100:.1f}',f'{float(row["type3_share_measured_RTM"])*100:.1f}',f'{float(row["net_measurement_difference_pp"]):.1f}']
    assert sup[1][i][1:]==expected
fixedrows=[r for r in summary if r['rtm_type']=='baseline' or r['rtm_type'].startswith('type3')]
for i,row in enumerate(fixedrows,1):
    expected=[fnum(row['n_fixed']),f'{float(row["fixed_fraction_RTM"])*100:.1f}',f'{float(row["fixed_fraction_type3"])*100:.1f}',fnum(row['fixed_n_zero_baseline']),fnum(row['fixed_n_mpc']),f'{float(row["fixed_MPC"]):.1f}']
    assert sup[2][i][1:]==expected
answer['docx_table_checks']={'main_Table1':'all 9 rows PASS','supplement_S1':'all 9 rows PASS','supplement_S2':'all 9 rows including Wilson intervals PASS','supplement_S3':'all 7 rows PASS'}
for fname,info in meta['cohort_content'].items():
    file={'daily_counts':'daily_counts.int16.memmap','latent_msf':'latent_msf.npy','seeds':'patient_seeds.npy'}[fname]
    p=ROOT/'outputs/rtm123_1m'/file;h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    assert h.hexdigest()==info['sha256']
    answer['source_hashes'][str(p)]={'sha256':h.hexdigest(),'matches_manifest':True}
for p,wanted in [(ROOT/'rtm_anatomy/rtm123.py',meta['analysis_source_sha256']),(Path(meta['transient_simulator']['source_path']),meta['transient_simulator']['source_sha256'])]:
    got=hashlib.sha256(p.read_bytes()).hexdigest();assert got==wanted;answer['source_hashes'][str(p)]={'sha256':got,'matches_manifest':True}
(DEST/'independent_array_audit.json').write_text(json.dumps(answer,indent=2)+'\n')
print('All array, table, interval and input hash checks passed.')
