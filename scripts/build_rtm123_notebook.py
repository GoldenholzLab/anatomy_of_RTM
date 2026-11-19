#!/usr/bin/env python3
"""Present saved paired-analysis outputs without fabricating notebook executions."""
from pathlib import Path
import csv,json,os
import argparse
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Build a notebook snapshot from reviewed saved outputs; code cells remain unexecuted.')
parser.add_argument('--output-dir',type=Path,default=root/'outputs/rtm123_type3_1m')
parser.add_argument('--notebook',type=Path,default=root/'notebooks/for_the_paper.ipynb')
args=parser.parse_args()
out=args.output_dir.resolve()

def md(s):return {'cell_type':'markdown','metadata':{},'source':s.splitlines(True)}
def code(s):return {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':s.splitlines(True)}
def csv_table(path,columns):
 rows=list(csv.DictReader(path.open()))
 header='| '+' | '.join(columns)+' |\n| '+' | '.join(['---']*len(columns))+' |\n'
 return header+'\n'.join('| '+' | '.join(row[c] for c in columns)+' |' for row in rows)

cells=[md('# Paired Type 3 RTM analysis\n\nThis notebook presents a snapshot of the saved, reviewed Anatomy analysis. Code cells are supplied for reloading those files and have not been executed as part of notebook generation. The simulations and validation were run by the repository scripts. The original million-person cohort and original analysis outputs remain in `outputs/rtm123_1m`; the revised results are in `outputs/rtm123_type3_1m`.\n\nType 3 means measured RTM present and true-count RTM absent for the same detector-selected participant and trial window. It is distinct from overall observed RTM, the net measured-minus-true difference, and changes between conditions.'),
 code("from pathlib import Path\nimport csv, json\nROOT = Path.cwd()\nif not (ROOT / 'rtm_anatomy').exists():\n    ROOT = ROOT.parent\nOUTPUT_DIR = ROOT / 'outputs' / 'rtm123_type3_1m'\nmanifest = json.loads((OUTPUT_DIR / 'run_manifest.json').read_text())\nmanifest\n"),
 md('## Trial design\n\nThe common potential population is retained across conditions. Eligibility and the first qualifying two-month baseline are re-evaluated, leaving three test months. The true full-diary mean is a finite internal reference that includes the trial window. Measured corrected counts use that reference multiplied by sensitivity. Paired true-count classifications use the unscaled reference and the same trial window without an additional eligibility filter.'),
 md('## Main results\n\n'+csv_table(out/'paper_table.csv',['condition','n_eligible','fraction_RTM','fraction_true_RTM','fraction_type3','MPC'])),
 code("with (OUTPUT_DIR / 'condition_summary.csv').open() as handle:\n    summary = list(csv.DictReader(handle))\nsummary\n"),
 md('## Paired categories\n\nThe four category counts sum to the number selected. Type 3 uses the measured-only category.\n\n'+csv_table(out/'paired_classification.csv',['condition','n_eligible','both_count','type3_count','true_only_count','neither_count'])),
 md('## Figures\n\n![Operational definitions](../outputs/rtm123_type3_1m/rtm123_explainer.png)\n\n![Paired analysis results](../outputs/rtm123_type3_1m/rtm123_summary.png)'),
 md('## Fixed enrollment\n\nThese comparisons retain both the perfect-detector participants and their baseline windows. Observed RTM uses the full fixed denominator. MPC excludes zero measured baselines.\n\n'+csv_table(out/'fixed_enrollment_summary.csv',['condition','n_fixed','fixed_fraction_RTM','fixed_fraction_type3','fixed_n_zero_baseline','fixed_n_mpc','fixed_MPC'])),
 code("validation = json.loads((OUTPUT_DIR / 'validation.json').read_text())\nassert validation['passed']\nvalidation\n"),
 md('## Reproduction\n\nRun the commands in the repository README from the project root. Use a new output directory when rerunning the analysis. The review and correction record is in `output/revision_2026-11-12/astra_review.md`. The journal manuscript is `anatomy_of_RTM_Seizure.docx`.')]
notebook={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
relative_images=os.path.relpath(out,args.notebook.resolve().parent)
try:
    output_expression='ROOT / '+repr(str(out.relative_to(root)))
except ValueError:
    output_expression='Path('+repr(str(out))+')'
for i,cell in enumerate(cells):
    cell['id']=f'paired-rtm-{i}'
    source=''.join(cell['source']).replace('../outputs/rtm123_type3_1m/',relative_images+'/')
    source=source.replace("ROOT / 'outputs' / 'rtm123_type3_1m'",output_expression)
    cell['source']=source.splitlines(True)
args.notebook.parent.mkdir(parents=True,exist_ok=True)
args.notebook.write_text(json.dumps(notebook,indent=1)+'\n')
print(args.notebook)
