from pathlib import Path
import json,csv,hashlib,importlib.util,sys
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[2];D=R/'outputs/rtm123_type3_1m'
rows=list(csv.DictReader((D/'condition_summary.csv').open()));checks=[];fail=[]
main=json.loads((P/'anatomy_of_RTM_Seizure_structure.json').read_text());supp=json.loads((P/'anatomy_of_RTM_Seizure_Supplement_structure.json').read_text())
def verify(got,want,tag):
 checks.append(tag)
 if got!=want:fail.append({'label':tag,'saved':got,'expected':want})
def pct(r,k):return f'{100*float(r[k]):.1f}'
def num(r,k):return f'{float(r[k]):.1f}'
def n(r,k):return f'{int(r[k]):,}'
for i,row in enumerate(rows,1):
 verify(main['tables'][0]['rows'][i][1:],[n(row,'n_eligible'),pct(row,'fraction_RTM'),pct(row,'fraction_true_RTM'),pct(row,'fraction_type3'),num(row,'MPC')],row['condition']+' Table1')
 verify(supp['tables'][0]['rows'][i][1:],[n(row,k) for k in ['n_eligible','both_count','type3_count','true_only_count','neither_count']],row['condition']+' S1')
 verify(supp['tables'][1]['rows'][i][1:],[pct(row,'fraction_type3'),pct(row,'fraction_type3_ci_lo')+' to '+pct(row,'fraction_type3_ci_hi'),pct(row,'type3_share_measured_RTM'),num(row,'net_measurement_difference_pp')],row['condition']+' S2')
fixed=[r for r in rows if r['rtm_type']=='baseline' or r['rtm_type'].startswith('type3')]
for i,row in enumerate(fixed,1):verify(supp['tables'][2]['rows'][i][1:],[n(row,'n_fixed'),pct(row,'fixed_fraction_RTM'),pct(row,'fixed_fraction_type3'),n(row,'fixed_n_zero_baseline'),n(row,'fixed_n_mpc'),num(row,'fixed_MPC')],row['condition']+' S3')
win=list(csv.DictReader((D/'first_eligible_windows.csv').open()))
for row in rows:
 name=row['condition']
 with np.load(D/'patient_condition_flags'/f'{name}.npz') as a:
  windows=a['first_start']; unique,counts=np.unique(windows,return_counts=True)
  wr=[r for r in win if r['condition']==name]
  verify({int(r['first_eligible_month']):int(r['n_patients']) for r in wr},dict(zip(map(int,unique),map(int,counts))),name+' window distribution')
with np.load(D/'patient_condition_flags/type1_transient_msf.npz') as z:a={k:z[k] for k in ['first_start','shock_start','shock_msf','eligible','rtm','pc']}
f=a['first_start'];s=a['shock_start'];b=(s<f+2)&(s+2>f);t=(s<f+5)&(s+2>f+2);over=np.where(f<0,'not_eligible',np.where(b&t,'baseline_and_test',np.where(b,'baseline',np.where(t,'test','neither'))));latent=np.load(R/'outputs/rtm123_1m/latent_msf.npy');relation=np.where(a['shock_msf']>latent,'higher',np.where(a['shock_msf']<latent,'lower','equal'))
strata=[]
for r in csv.DictReader((D/'type1_overlap_summary.csv').open()):
 mask=np.ones(1000000,dtype=bool)
 if r['overlap']!='all':mask &= over==r['overlap']
 if r['shock_msf_relation']!='all':mask &= relation==r['shock_msf_relation']
 e=mask&a['eligible'];ne=int(e.sum());nn=int(mask.sum());nr=int((e&a['rtm']).sum());mpc=float(np.nanmedian(a['pc'][e])) if ne else float('nan')
 verify(int(r['n_raw']),nn,str(r)+' raw');verify(int(r['n_eligible']),ne,str(r)+' eligible')
 if ne:verify(float(r['fraction_RTM']),nr/ne,str(r)+' rtm');verify(float(r['MPC']),mpc,str(r)+' mpc')
 strata.append({'overlap':r['overlap'],'direction':r['shock_msf_relation'],'n':ne,'rtm_pct':nr/ne*100 if ne else None,'MPC':mpc if ne else None})
# Consistency of every derived summary CSV cell with the main summary.
by={r['condition']:r for r in rows}
for name in ['paper_table.csv','paired_classification.csv','fixed_enrollment_summary.csv','condition_summary_with_deltas.csv']:
 for row in csv.DictReader((D/name).open()):
  for k,v in row.items():
   if k in by[row['condition']]:verify(v,by[row['condition']][k],name+' '+row['condition']+' '+k)
# Inspect the actual daily simulator cycle configuration with a fresh sample.
path=R.parent/'CHOCOLATE/realSim_turbo.py';spec=importlib.util.spec_from_file_location('cycle_probe',path);sim=importlib.util.module_from_spec(spec);spec.loader.exec_module(sim)
seed_values=np.load(R/'outputs/rtm123_1m/patient_seeds.npy',mmap_mode='r');ids=np.random.default_rng(77261112).choice(1000000,1024,replace=False);active=0;detail_match=0
raw=np.memmap(R/'outputs/rtm123_1m/daily_counts.int16.memmap',mode='r',dtype='int16',shape=(1000000,1080))
for idx in ids:
 rng=np.random.default_rng(int(seed_values[idx]));rate=sim.get_mSF(-1,rng=rng);d=sim.simulator_base(1,1080,defaultSeizureFreq=rate,rng=rng,returnDetails=True)
 active+=int(np.any(d[7]!=0));detail_match+=int(np.array_equal(d[0],raw[idx]))
cycle={'sample_n':1024,'nonzero_cycle_modulation':active,'raw_diary_matches':detail_match,'probability_nonzero_cycle_from_defaults':0.011649,'half_day_and_daily':'excluded by sampFreq > 2*frequency at sampFreq=1','weekly':'zero amplitude','4_to_45_day':'zero selection probability','90_to_450_day':'probability 0.011649; retained nonzero waveform normalized to unit peak'}
result={'checks_n':len(checks),'failures':fail,'tables':{'main':len(main['tables']),'supplement':len(supp['tables'])},'omml_count':{'main':len(main['equations']),'supplement':len(supp['equations'])},'strata':strata,'cycles':cycle}
(P/'document_and_strata_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
