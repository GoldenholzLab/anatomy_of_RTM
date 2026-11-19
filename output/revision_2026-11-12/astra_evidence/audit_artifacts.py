"""Check the review rerun, protected originals and scientific DOCX package."""
from pathlib import Path
from zipfile import ZipFile
import csv
import hashlib
import json
import subprocess
import sys

import numpy as np
from lxml import etree

ROOT=Path(__file__).resolve().parents[3]
EVIDENCE=Path(__file__).resolve().parent
CURRENT=ROOT/'outputs/rtm123_type3_1m'
BEFORE=EVIDENCE/'before_review/rtm123_type3_1m'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'm':'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def package(path):
    with ZipFile(path) as z:return {n:z.read(n) for n in z.namelist()}


def visible(p):return ''.join(p.xpath('.//w:t/text()',namespaces=NS))


def main():
    result={'passed':True,'source_sha256':sha(__file__)}
    originals=json.loads((EVIDENCE/'original_outputs_before.json').read_text())
    assert all(sha(ROOT/path)==expected for path,expected in originals.items())
    result['original_cohort_and_outputs_unchanged_n']=len(originals)
    protected=json.loads((EVIDENCE/'protected_files_before.json').read_text())
    assert all(sha(path)==record['sha256'] for path,record in protected.items())
    result['protected_docx_unchanged_n']=len(protected)
    comparisons=[]
    for path in sorted((CURRENT/'patient_condition_flags').glob('*.npz')):
        with np.load(path) as a, np.load(BEFORE/'patient_condition_flags'/path.name) as b:
            keys=[key for key in a.files if key not in ('cache_json','condition_json')]
            assert set(keys)==set(b.files)-{'cache_json','condition_json'}
            differences=[key for key in keys if not np.array_equal(a[key],b[key],equal_nan=True)]
            assert not differences,(path.name,differences)
            comparisons.append({'condition':path.stem,'n_people':len(a['eligible']),
                                'n_arrays':len(keys),'changed_arrays':differences})
    result['before_after_patient_arrays']=comparisons
    csv_names=['condition_summary.csv','first_eligible_windows.csv','type1_overlap_summary.csv',
               'condition_summary_with_deltas.csv','paper_table.csv','paired_classification.csv',
               'fixed_enrollment_summary.csv']
    assert all((CURRENT/n).read_bytes()==(BEFORE/n).read_bytes() for n in csv_names)
    result['identical_summary_csvs']=csv_names
    source=package(ROOT/'anatomy_of_RTM_JCE.docx')
    revised=package(ROOT/'anatomy_of_RTM_revised.docx')
    assert set(source)==set(revised)
    changed=[name for name in source if source[name]!=revised[name]]
    assert set(changed)<= {'word/document.xml','word/media/image1.png','word/media/image2.png'}
    for name,content in revised.items():
        if name.endswith('.xml') or name.endswith('.rels'):etree.fromstring(content)
    old=etree.fromstring(source['word/document.xml']);new=etree.fromstring(revised['word/document.xml'])
    assert old.xpath('.//w:instrText/text()',namespaces=NS)==new.xpath('.//w:instrText/text()',namespaces=NS)
    counts={}
    for key in ['w:instrText','w:fldChar','w:commentRangeStart','w:commentRangeEnd','w:commentReference',
                'w:bookmarkStart','w:bookmarkEnd','w:ins','w:del','m:oMath']:
        counts[key]=len(new.xpath('.//'+key,namespaces=NS))
        assert counts[key]==len(old.xpath('.//'+key,namespaces=NS))
    rows=list(csv.DictReader((CURRENT/'condition_summary.csv').open()))
    tbl=next(t for t in new.xpath('.//w:tbl',namespaces=NS) if 'Measured RTM %' in visible(t))
    tr=tbl.findall('w:tr',NS)[1:]
    assert len(tr)==len(rows)
    for xmlrow,data in zip(tr,rows):
        actual=[visible(tc) for tc in xmlrow.findall('w:tc',NS)][1:]
        expected=[f"{int(data['n_eligible']):,}",f"{100*float(data['fraction_RTM']):.1f}",
                  f"{100*float(data['fraction_true_RTM']):.1f}",f"{100*float(data['fraction_type3']):.1f}",f"{float(data['MPC']):.1f}"]
        assert actual==expected,(actual,expected)
    rels=etree.fromstring(revised['word/_rels/document.xml.rels'])
    for blip,name in zip(new.findall('.//a:blip',NS),['rtm123_explainer.png','rtm123_summary.png']):
        rid=blip.get('{'+NS['r']+'}embed');target=next(r.get('Target') for r in rels if r.get('Id')==rid)
        assert revised['word/'+target]==(CURRENT/name).read_bytes()
    doc_manifest=json.loads((ROOT/'output/revision_2026-11-12/science_manifest.json').read_text())
    assert sha(ROOT/'anatomy_of_RTM_revised.docx')==doc_manifest['output_docx_sha256']
    assert all(sha(ROOT/path)==digest for path,digest in doc_manifest['analysis_inputs_sha256'].items())
    result['docx']={'changed_package_parts':changed,'preserved_element_counts':counts,
                    'table_numeric_cells_checked':len(rows)*5,'embedded_figures_match':True,
                    'sha256':sha(ROOT/'anatomy_of_RTM_revised.docx'),
                    'word_visual_verification':'pending coordinator'}
    current_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    assert current_sha==json.loads((BEFORE/'run_manifest.json').read_text())['git_sha']
    assert branch=='main'
    result['git']={'branch':branch,'head':current_sha,'unchanged':True}
    (EVIDENCE/'review_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
