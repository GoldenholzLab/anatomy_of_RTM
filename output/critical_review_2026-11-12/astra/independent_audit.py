"""Read-only audit. Writes only beside this script. Does not call production analysis helpers."""
from pathlib import Path
import csv,json,hashlib,sys,math,importlib.util
from fractions import Fraction as F
from itertools import groupby
import numpy as np
from scipy.stats import norm,binom
ROOT=Path('/Users/dgoldenh/Documents/GitHub/anatomy_of_RTM'); OUT=Path(__file__).resolve().parent
D=ROOT/'outputs/rtm123_type3_1m'; C=ROOT/'outputs/rtm123_1m'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def seed(*parts):return int.from_bytes(hashlib.blake2b(''.join(str(x)+'|' for x in parts).encode(),digest_size=8).digest(),'little') & ((1<<63)-1)
def rtm(b,t,r):return t<b and b+t>2*r
mf=json.loads((D/'run_manifest.json').read_text()); conditions=mf['conditions']; rows=list(csv.DictReader((D/'condition_summary.csv').open()))
raw=np.memmap(C/'daily_counts.int16.memmap',dtype='int16',mode='r',shape=(1000000,1080)); latent=np.load(C/'latent_msf.npy',mmap_mode='r'); seeds=np.load(C/'patient_seeds.npy',mmap_mode='r')
monthly=raw.reshape(-1,36,30).sum(axis=2,dtype=np.int64); totals=monthly.sum(axis=1)
modpath=ROOT.parent/'CHOCOLATE/realSim_turbo.py'; ms=importlib.util.spec_from_file_location('review_chocolates',modpath); sim=importlib.util.module_from_spec(ms);ms.loader.exec_module(sim)
result={'environment':{'python':sys.version,'numpy':np.__version__},'failures':[],'conditions':[], 'source_hashes':{},'raw_range':[int(raw.min()),int(raw.max())]}
paths=[ROOT/'anatomy_of_RTM_Seizure.docx',ROOT/'anatomy_of_RTM_Seizure_Supplement.docx',ROOT/'rtm_anatomy/rtm123.py',ROOT/'tests/test_rtm123.py',ROOT/'notebooks/for_the_paper.ipynb',modpath]+list(D.glob('*.csv'))+list(D.glob('*.json'))+list((D/'patient_condition_flags').glob('*.npz'))+[C/'daily_counts.int16.memmap',C/'latent_msf.npy',C/'patient_seeds.npy']
for p in paths:result['source_hashes'][str(p)]=sha(p)
def check(ok,label):
 if not bool(ok):result['failures'].append(label)
check(sha(ROOT/'rtm_anatomy/rtm123.py')==mf['analysis_source_sha256'],'analysis_hash')
check(sha(modpath)==mf['transient_simulator']['source_sha256'],'simulator_hash')
for key,file in [('daily_counts','daily_counts.int16.memmap'),('latent_msf','latent_msf.npy'),('seeds','patient_seeds.npy')]:check(sha(C/file)==mf['cohort_content'][key]['sha256'],key+'_hash')
with np.load(D/'patient_condition_flags/baseline_perfect.npz') as z:perfect_start=z['first_start'];perfect_e=z['eligible'];perfect_rtm=z['rtm']
rng=np.random.default_rng(202611122357);random_ids=rng.choice(1000000,512,replace=False)
for spec,row in zip(conditions,rows):
 name=spec['name']; print(name,flush=True)
 with np.load(D/'patient_condition_flags'/f'{name}.npz') as z:
  a={k:z[k] for k in z.files if not k.endswith('_json')};cache=json.loads(str(z['cache_json'])); saved_spec=json.loads(str(z['condition_json']))
 check(saved_spec==spec,name+' spec');check(cache['source_sha256']==mf['analysis_source_sha256'],name+' source')
 e=a['eligible'];ids=np.flatnonzero(e);n=len(ids);m=a['rtm'];t=a['true_rtm'];fixed=a['fixed_eligible'];q=(F(str(spec['far_per_day'])).limit_denominator(1000000)*30).denominator;sens=F(str(spec['sensitivity']));corr=(F(str(spec['far_per_day'])).limit_denominator(1000000)*30);fn=int(fixed.sum())
 for k,v in [('n_eligible',n),('rtm_count',m.sum()),('true_rtm_count',t.sum()),('type3_count',(e&m&~t).sum()),('true_only_count',(e&t&~m).sum()),('both_count',(e&t&m).sum()),('neither_count',(e&~t&~m).sum()),('n_mpc',np.isfinite(a['pc'][e]).sum()),('n_fixed',fn),('fixed_n_zero_baseline',(fixed&(a['fixed_baseline']==0)).sum()),('fixed_n_mpc',np.isfinite(a['fixed_pc'][fixed]).sum())]:check(int(row[k])==int(v),name+' '+k)
 for k,v in [('type3_rtm',m&~t),('true_only_rtm',t&~m),('both_rtm',m&t),('eligible',a['first_start']>=0)]:check(np.array_equal(a[k],v),name+' '+k)
 check(not np.any((m|t)&~e),name+' excluded_rtm')
 b=np.rint(a['baseline'][e]*2*q).astype('int64');test=np.rint(a['test'][e]*3*q).astype('int64');total=np.rint(a['true_reference'][e]*36).astype('int64');bt=np.rint(a['true_baseline'][e]*2).astype('int64');tt=np.rint(a['true_test'][e]*3).astype('int64')
 expected=(2*test<3*b)&((3*b+2*test)*36*sens.denominator>12*q*total*sens.numerator)
 true_expected=(2*tt<3*bt)&((3*bt+2*tt)*36>12*total)
 check(np.array_equal(m[e],expected),name+' algebraic measured rule');check(np.array_equal(t[e],true_expected),name+' algebraic true rule')
 if not spec['type1_intervention']:
  starts=a['first_start'][e].astype(int)
  check(np.array_equal(a['true_reference'],totals/36),name+' raw references')
  check(np.array_equal(a['true_baseline'][e],(monthly[ids,starts]+monthly[ids,starts+1])/2),name+' raw baseline')
  check(np.array_equal(a['true_test'][e],(monthly[ids,starts+2]+monthly[ids,starts+3]+monthly[ids,starts+4])/3),name+' raw test')
 if name.startswith('type3'):
  check(np.array_equal(a['fixed_first_start'],perfect_start),name+' fixed starts'); check(np.array_equal(fixed,perfect_e),name+' fixed members')
  check(np.array_equal(a['fixed_type3_rtm'],a['fixed_rtm']&~perfect_rtm),name+' fixed type3 paired')
 if spec['sensitivity']==1 and spec['far_per_day']==0:check(np.array_equal(m,t),name+' perfect agreement')
 metrics={'fraction_eligible':n/1000000,'fraction_RTM':m.sum()/n,'fraction_true_RTM':t.sum()/n,'fraction_type3':(e&m&~t).sum()/n,'type3_share_measured_RTM':(e&m&~t).sum()/m.sum(),'net_measurement_difference_pp':100*(int(m.sum())-int(t.sum()))/n,'MPC':np.nanmedian(a['pc'][e]),'fixed_MPC':np.nanmedian(a['fixed_pc'][fixed]),'fixed_fraction_RTM':a['fixed_rtm'][fixed].mean(),'fixed_fraction_type3':a['fixed_type3_rtm'][fixed].mean()}
 for k,v in metrics.items():check(np.isclose(float(row[k]),v,atol=1e-12,rtol=0),name+' summary '+k)
 for k,count in [('fraction_RTM',int(m.sum())),('fraction_type3',int((e&m&~t).sum()))]:
  z=norm.ppf(.975);ph=count/n;center=(ph+z*z/(2*n))/(1+z*z/n);half=z/(1+z*z/n)*np.sqrt(ph*(1-ph)/n+z*z/(4*n*n))
  for suf,val in [('_ci_lo',max(0,center-half)),('_ci_hi',min(1,center+half))]:check(np.isclose(float(row[k+suf]),val,atol=1e-12,rtol=0),name+' '+k+suf)
 selected_sorted=np.sort(a['pc'][e]); medlo=selected_sorted[max(0,math.floor(n/2-.98*math.sqrt(n))-1)];medhi=selected_sorted[min(n-1,math.ceil(n/2+.98*math.sqrt(n)))];check(float(row['MPC_ci_lo'])==medlo and float(row['MPC_ci_hi'])==medhi,name+' medianCI')
 # New random and edge-stratified raw-diary replay. Generator is reused only to create the Type 1 segment.
 replay_ids=set(int(x) for x in random_ids)
 masks=[e&~m&~t,e&m&t,e&m&~t,e&~m&t,~e,a['first_start']==31,fixed&(a['fixed_baseline']==0)]
 if spec['type1_intervention']:
  for rel in [a['shock_msf']>latent,a['shock_msf']<latent]:
   masks += [e&rel&(a['shock_start']==a['first_start']), e&rel&(a['shock_start']==a['first_start']+2)]
 for mask in masks:
  pool=np.flatnonzero(mask)
  if pool.size:replay_ids.update(int(x) for x in rng.choice(pool,min(16,len(pool)),replace=False))
 diffs=[]
 for idx in sorted(replay_ids):
  d=raw[idx].astype('int64'); shock=-1; shockrate=np.nan
  if spec['type1_intervention']:
   srng=np.random.default_rng(seed('type1',int(seeds[idx])));shock=int(srng.integers(0,35));shockrate=float(srng.lognormal(1.2267388224600906,1.1457004817186776,size=1).astype('float32')[0]); segment,_=sim.simple_CHOCOLATES(60,defaultSeizureFreq=shockrate,rng=srng);d[30*shock:30*(shock+2)]=segment
  drng=np.random.default_rng(seed('detector',name,int(seeds[idx])))
  obs=d.copy() if sens==1 else drng.binomial(d,float(sens))
  if corr:obs=obs+drng.poisson(float(spec['far_per_day']),1080)
  dm=np.maximum(obs-round(spec['far_per_day']),0)
  nums=np.maximum(obs.reshape(36,30).sum(axis=1)*q-int(corr*q),0);tm=d.reshape(36,30).sum(axis=1);R=F(int(tm.sum()),36)
  first=-1
  for start in range(32):
   if nums[start]<3*q or nums[start+1]<3*q or nums[start]+nums[start+1]<2*q*spec['threshold']:continue
   gaps=[len(list(g)) for key,g in groupby(dm[30*start:30*(start+2)]==0) if key]
   if max(gaps,default=0)>25:continue
   first=start;break
  expect={'first_start':first,'eligible':first>=0,'shock_start':shock,'shock_msf':np.float32(shockrate),'reference':float(R*sens),'true_reference':float(R)}
  for prefix,s in [('',first),('fixed_',int(perfect_start[idx]) if name.startswith('type3') else first)]:
   if s<0:continue
   B=F(int(nums[s:s+2].sum()),2*q);T=F(int(nums[s+2:s+5].sum()),3*q);BT=F(int(tm[s:s+2].sum()),2);TT=F(int(tm[s+2:s+5].sum()),3);M=rtm(B,T,R*sens);TR=rtm(BT,TT,R)
   expect.update({prefix+'rtm':M,prefix+'type3_rtm':M and not TR,prefix+'baseline':float(B),prefix+'pc':float(100*(1-T/B)) if B else np.nan})
   if not prefix:expect.update(test=float(T),true_baseline=float(BT),true_test=float(TT),true_rtm=TR,both_rtm=M and TR,true_only_rtm=TR and not M)
  for key,v in expect.items():
   if isinstance(v,(float,np.floating)):same=np.isclose(a[key][idx],v,atol=1e-10,rtol=1e-14,equal_nan=True)
   else:same=a[key][idx]==v
   if not same:diffs.append({'patient':idx,'key':key,'saved':str(a[key][idx]),'replayed':str(v)})
 check(not diffs,name+' raw replay')
 cr={'condition':name,'n_selected':n,'metrics':{k:float(v) for k,v in metrics.items()},'MPC_95_interval':[float(medlo),float(medhi)],'raw_replay_n':len(replay_ids),'raw_replay_differences':diffs,'raw_replay_patient_ids':sorted(replay_ids)}
 # Leave the trial's five months out of the finite reference: a sensitivity diagnostic, not a proposed replacement.
 rr=(total-bt-tt);alt_m=(2*test<3*b)&((3*b+2*test)*31*sens.denominator>12*q*rr*sens.numerator);alt_t=(2*tt<3*bt)&((3*bt+2*tt)*31>12*rr)
 cr['outside_trial_reference_diagnostic']={'measured_pct':float(100*alt_m.mean()),'type3_pct':float(100*(alt_m&~alt_t).mean()),'measured_changed_n':int((alt_m!=m[e]).sum()),'type3_changed_n':int(((alt_m&~alt_t)!=a['type3_rtm'][e]).sum())}
 result['conditions'].append(cr)
 # Ensure source files did not change during this audit.
 (OUT/'independent_audit_results.json').write_text(json.dumps(result,indent=2)+'\n')
regen=[]
for idx in random_ids[:128]:
 generated,rate=sim.simple_CHOCOLATES(1080,rng=np.random.default_rng(int(seeds[idx])))
 if not np.array_equal(generated,raw[idx]) or np.float32(np.asarray(rate).item())!=latent[idx]:regen.append(int(idx))
result['original_generation_replay']={'n':128,'differences':regen};check(not regen,'generation replay')
result['changed_sources']=[str(p) for p in paths if sha(p)!=result['source_hashes'][str(p)]]
check(not result['changed_sources'],'sources changed during audit')
(OUT/'independent_audit_results.json').write_text(json.dumps(result,indent=2)+'\n')
print('Failures:',result['failures']); print('Replay sample sizes:',[x['raw_replay_n'] for x in result['conditions']]);print('Generation differences:',regen)
