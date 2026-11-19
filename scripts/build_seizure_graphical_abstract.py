#!/usr/bin/env python3
"""Create vector and TIFF graphical abstracts from the reviewed paired outputs."""
from pathlib import Path
import csv
import os

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/seizure_graphical_abstract'
OUT.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR',str(OUT/'.matplotlib-cache'))
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch


def main():
    rows={r['condition']:r for r in csv.DictReader((ROOT/'outputs/rtm123_type3_1m/condition_summary.csv').open())}
    low=100*float(rows['type3_sensitivity_70']['fraction_type3'])
    alarm=100*float(rows['type3_far_1_per_day']['fraction_type3'])
    plt.rcParams.update({'font.family':'Arial','pdf.fonttype':42,'ps.fonttype':42})
    fig,ax=plt.subplots(figsize=(13.28,5.31));fig.subplots_adjust(0,0,1,1)
    ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    ax.text(.5,.94,'The anatomy of RTM in epilepsy trials',ha='center',va='center',fontsize=25,weight='bold')
    ax.text(.5,.84,'1,000,000 simulated participants; no treatment effect',ha='center',va='center',fontsize=19,color='#435166')
    xs=[.17,.5,.83]
    headings=['Vary an input','Reapply eligibility','Compare both scales']
    texts=['Transient clinical state\nEntry threshold\nDetector performance',
           'First eligible 2-month baseline\nFollowed by 3 test months\nEnrollment can change',
           'Type 3 = measured RTM\nwith true-count RTM absent\nSame person and trial window']
    for x,h,t in zip(xs,headings,texts):
        ax.text(x,.66,h,ha='center',va='center',fontsize=20,weight='bold',color='#14243A')
        ax.text(x,.48,t,ha='center',va='center',fontsize=17,linespacing=1.45,color='#14243A')
    for x in (.33,.66):ax.add_patch(FancyArrowPatch((x-.025,.5),(x+.025,.5),arrowstyle='-|>',mutation_scale=25,color='#435166',lw=2))
    ax.text(.5,.22,f'Type 3 among eligible participants: {low:.1f}% at 70% sensitivity; {alarm:.1f}% at 1 false alarm/day',
            ha='center',va='center',fontsize=18,weight='bold',color='#6730A5')
    ax.text(.5,.15,'The sensitivity condition has no false alarms; the false-alarm condition has 100% sensitivity.',
            ha='center',va='center',fontsize=13,color='#435166')
    ax.text(.5,.095,'Measurement-only RTM is distinct from total observed RTM and its change between conditions.',
            ha='center',va='center',fontsize=16,color='#435166')
    ax.text(.5,.035,'RTM, regression to the mean. Numerical estimates depend on the model and trial-selection design.',
            ha='center',va='center',fontsize=12,color='#435166')
    for suffix in ('png','pdf','tiff'):
        path=OUT/('anatomy_of_RTM_Seizure_graphical_abstract.'+suffix)
        kwargs={'pil_kwargs':{'compression':'tiff_lzw'}} if suffix=='tiff' else {}
        fig.savefig(path,dpi=300,**kwargs)
        print(path)
    plt.close(fig)

if __name__=='__main__':main()
