#!/usr/bin/env python3
"""Revise the existing DOCX through OOXML while retaining live Zotero fields.

Scientific text is derived from the paired analysis outputs. The Seizure stage
uses the independently reviewed scientific version and only changes packaging.
Final pagination, citation refreshes and saves are performed in Microsoft Word.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / 'outputs/rtm123_type3_1m'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W, 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
TITLE = 'The anatomy of regression to the mean in simulated epilepsy trials'
KEYWORDS = 'natural history; seizure variability; measurement error; eligibility; digital biomarker; placebo response'

def E(tag, **attrs):
    e=etree.Element('{'+W+'}'+tag)
    for k,v in attrs.items(): e.set('{'+W+'}'+k,str(v))
    return e

def run(text, size=None, bold=False):
    r=E('r')
    if size or bold:
        pr=E('rPr')
        if size: pr.append(E('sz',val=size))
        if bold: pr.append(E('b'))
        r.append(pr)
    t=E('t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=text;r.append(t)
    return r

def paragraph(text, style=None):
    p=E('p')
    if style:
        pr=E('pPr');pr.append(E('pStyle',val=style));p.append(pr)
    p.append(run(text));return p

def visible(p): return ''.join(p.xpath('.//w:t/text()',namespaces=NS))

def field_groups(p):
    groups=[];current=None;depth=0
    for child in p:
        chars=child.findall('.//w:fldChar',NS)
        begins=sum(x.get('{'+W+'}fldCharType')=='begin' for x in chars)
        ends=sum(x.get('{'+W+'}fldCharType')=='end' for x in chars)
        if begins and current is None: current=[]
        if current is not None:
            current.append(copy.deepcopy(child));depth+=begins-ends
            if depth==0: groups.append(current);current=None
    if current: raise ValueError('Unclosed field in edited paragraph')
    return groups

def replace(p,text):
    groups=field_groups(p)
    markers=re.findall(r'\[C(\d+)\]',text)
    if sorted(int(x) for x in markers)!=list(range(1,len(groups)+1)):
        raise ValueError(f'Citation placeholders do not match fields: {visible(p)[:80]}')
    pr=p.find('w:pPr',NS)
    for child in list(p):
        if child is not pr: p.remove(child)
    for chunk in re.split(r'(\[C\d+\])',text):
        if re.fullmatch(r'\[C\d+\]',chunk):
            for element in groups[int(chunk[2:-1])-1]: p.append(element)
        elif chunk:p.append(run(chunk))

def read_package(path):
    with ZipFile(path) as z:return {n:z.read(n) for n in z.namelist()}

def write_package(path,parts):
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)

def xmlbytes(root):return etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)

def pct(row,key='fraction_RTM'):return f'{100*float(row[key]):.1f}'
def num(row,key='MPC'):return f'{float(row[key]):.1f}'
def count(row,key='n_eligible'):return f'{int(row[key]):,}'

def table(headers,rows,widths=None):
    widths=widths or [int(9360/len(headers))]*len(headers)
    t=E('tbl');pr=E('tblPr');pr.append(E('tblW',w=9360,type='dxa'))
    borders=E('tblBorders')
    for k in ('top','bottom','insideH'):borders.append(E(k,val='single',sz=4,color='999999'))
    for k in ('left','right','insideV'):borders.append(E(k,val='nil'))
    pr.append(borders);t.append(pr)
    grid=E('tblGrid')
    for width in widths:grid.append(E('gridCol',w=width))
    t.append(grid)
    for i,row in enumerate([headers]+rows):
        tr=E('tr');trpr=E('trPr');trpr.append(E('cantSplit'))
        if i==0:trpr.append(E('tblHeader'))
        tr.append(trpr)
        for value,width in zip(row,widths):
            tc=E('tc');tcpr=E('tcPr');tcpr.append(E('tcW',w=width,type='dxa'));tc.append(tcpr)
            p=E('p');ppr=E('pPr');ppr.append(E('spacing',before=60,after=60,line=240,lineRule='auto'));p.append(ppr)
            p.append(run(str(value),size=18,bold=i==0));tc.append(p);tr.append(tc)
        t.append(tr)
    return t

def insert_after(anchor,nodes):
    for node in nodes:anchor.addnext(node);anchor=node

def set_figure(parts,root,figure_number,new_path,width_inches=None):
    blip=root.findall('.//a:blip',NS)[figure_number-1]
    rels=etree.fromstring(parts['word/_rels/document.xml.rels'])
    rid=blip.get('{'+NS['r']+'}embed')
    target=next(r.get('Target') for r in rels if r.get('Id')==rid)
    parts['word/'+target]=new_path.read_bytes()
    if width_inches:
        from PIL import Image
        with Image.open(new_path) as im:ratio=im.height/im.width
        inline=next(a for a in blip.iterancestors() if etree.QName(a).localname in ('inline','anchor'))
        cx=int(width_inches*914400);cy=int(cx*ratio)
        for ext in inline.xpath('.//wp:extent | .//a:xfrm/a:ext',namespaces=NS):
            ext.set('cx',str(cx));ext.set('cy',str(cy))

def fields_digest(root):
    return hashlib.sha256('\n'.join(root.xpath('.//w:instrText/text()',namespaces=NS)).encode()).hexdigest()

def science():
    source=ROOT/'anatomy_of_RTM_JCE.docx';dest=ROOT/'anatomy_of_RTM_revised.docx'
    parts=read_package(source);root=etree.fromstring(parts['word/document.xml'])
    old_digest=fields_digest(root);paras=root.findall('.//w:body//w:p',NS);p={i+1:x for i,x in enumerate(paras)}
    rows=list(csv.DictReader((OUTPUTS/'condition_summary.csv').open()))
    d={r['condition']:r for r in rows};b=d['baseline_perfect'];state=d['type1_transient_msf'];sel=d['type2_threshold_8'];s=d['type3_sensitivity_70'];far=d['type3_far_1_per_day']
    overlap=list(csv.DictReader((OUTPUTS/'type1_overlap_summary.csv').open()))
    base_overlap=next(r for r in overlap if r['overlap']=='baseline' and r['shock_msf_relation']=='all')
    neither=next(r for r in overlap if r['overlap']=='neither' and r['shock_msf_relation']=='all')
    replacements={
      1:TITLE,
      10:'Keywords: '+KEYWORDS,
      14:'Background and Objective: Regression to the mean (RTM) can resemble improvement in epilepsy trials without treatment. We examined transient rate changes, eligibility selection and detector errors, distinguishing observed RTM from measurement-only Type 3 RTM.',
      15:'Methods: We reused 1,000,000 simulated 36-month seizure histories. Each condition selected its first eligible two-month baseline and following three-month test period. We varied a transient rate change, the entry threshold, sensitivity and false alarms. Type 3 required RTM on corrected measured counts but not true counts for the same participant and window. Both classifications used a finite true-count reference, scaled by sensitivity for measured counts.',
      16:f'Results: With perfect detection, {pct(b,"fraction_eligible")}% were eligible, {pct(b)}% met observed RTM and median seizure-frequency reduction was {num(b)}%. Transient rate changes and a higher entry threshold yielded {pct(state)}% and {pct(sel)}% observed RTM. At 70% sensitivity, observed RTM was {pct(s)}% and Type 3 affected {pct(s,"fraction_type3")}% of eligible participants. At one false alarm/day, corresponding values were {pct(far)}% and {pct(far,"fraction_type3")}%; Type 3 represented {pct(far,"type3_share_measured_RTM")}% of measured RTM cases.',
      17:'Discussion: Detector errors changed both enrollment and measured trajectories. Measurement-only Type 3 was a paired classification, not the total change between detector settings or an additive causal component. Trial simulations should evaluate eligibility and measurement together; effects on randomized treatment contrasts and power were not assessed.',
      18:'Keywords: '+KEYWORDS,
      21:'Transient rate changes and eligibility selection altered apparent improvement.',
      22:'Type 3 required measured RTM absent on true counts in the same person and window.',
      24:'Paired classifications separated measurement-only cases from overall observed RTM.',
      26:'Eligibility and measurement should be evaluated jointly in trial simulations.',
      27:'These within-arm results do not establish effects on treatment contrasts or power.',
      31:'We distinguish three operational forms of RTM (Figure 1). Type 1 describes return after a temporary state worsening. Type 2 describes return associated with selection on natural variability. Measurement error can alter the counts used for eligibility and outcome assessment [C1]. We define Type 3 more narrowly as RTM present on measured counts but absent on true counts for the same participant and baseline/test window. Selection and measurement effects can coexist; these definitions do not partition observed RTM into additive causal components.',
      32:'Previous seizure-trial simulations quantified eligibility-related RTM. We reused a common underlying simulated population while varying state, entry or measurement inputs one at a time. Eligibility and baseline timing were re-evaluated under each condition. We examined whether these changes produced apparent improvement without treatment and quantified measurement-only Type 3 through paired measured and true-count classifications.',
      35:'We generated 1,000,000 synthetic patients with CHOCOLATES, an open-source simulator of heterogeneous seizure rates, clustering, cycles and the association between frequency and variability [C1]. Each patient had 36 months of daily counts, with 30 days per month. The same underlying histories and patient-specific seeds were reused across conditions. The original cohort was retained; the paired classification analysis was added during manuscript revision and was not prespecified.',
      38:'The common underlying population was fixed, while eligibility and the first qualifying baseline window were re-evaluated after each condition transform. Thus, enrolled membership and trial timing could change. A separate measurement sensitivity analysis retained both membership and baseline windows from the perfect-detector condition. This fixed-enrollment comparison describes measurement changes in the same people and windows; it does not represent enrollment using the imperfect detector.',
      40:'The reference condition used 100% sensitivity and no false alarms. For the transient-state condition, one random consecutive two-month interval per patient was replaced with a newly simulated segment at a newly sampled rate, after which the original diary resumed. The sampled rate could be higher or lower; baseline-overlap strata characterize the temporary-worsening example. For the selection condition, the mean-frequency threshold changed from 4 to 8 events/month. Measurement conditions separately reduced sensitivity to 90%, 80% or 70% without false alarms, or added independent Poisson alarms at 1/month, 1/week or 1/day with full sensitivity. The known expected monthly alarm count was subtracted and negative corrected counts were set to zero [C1]. Fractional expected counts were retained. For the 25-day rule only, daily recorded counts were reduced by the rounded expected daily alarm count and floored at zero. These idealized corrections do not identify individual false alarms or establish optimal trial efficiency.',
      42:'There was no active treatment effect. Observed RTM required a baseline rate above the reference and a test rate strictly closer to it [C1]. The finite reference was the mean true monthly count over the same 36-month condition-specific history, including its trial window. Corrected measured counts were compared with this reference multiplied by sensitivity; true counts used the unscaled reference. This internal finite-history design differs from a separate reference diary. Integer cross-products and rational correction factors made exact ties fail the strict RTM criterion. Apparent improvement was median percentage change (MPC), positive for seizure-frequency reduction.',
      43:'This descriptive simulation used no human participants or identifiable data and was not preregistered. Clinical reporting checklists for randomized trials, observational studies and diagnostic-accuracy studies do not match this synthetic, noninferential design. We report the generating process, condition transforms, selection algorithm, paired definitions, seeds and computational scale, with source code at https://github.com/GoldenholzLab/anatomy_of_RTM. The revision protocol and outputs are documented in the repository.',
      46:f'With perfect detection and the 4-event/month threshold, {count(b)} of 1,000,000 patients ({pct(b,"fraction_eligible")}%) became eligible. Among eligible patients, observed RTM was {pct(b)}% and MPC was {num(b)}% (Table 1; Figure 2). Measured and true-count classifications agreed for every participant, giving zero Type 3 cases.',
      48:f'With the temporary rate change, eligibility was {pct(state,"fraction_eligible")}%, observed RTM {pct(state)}% and MPC {num(state)}%. When the replaced interval overlapped baseline only, RTM was {pct(base_overlap)}% and MPC {num(base_overlap)}%; when it overlapped neither baseline nor test, corresponding values were {pct(neither)}% and {num(neither)}%. State changes could affect who qualified and which window became baseline. With perfect detection, all measured RTM in this condition was also present on true counts.',
      50:f'Raising the entry threshold from 4 to 8 events/month reduced eligibility to {pct(sel,"fraction_eligible")}%, with observed RTM of {pct(sel)}% and MPC of {num(sel)}%. The underlying histories and absence of treatment were unchanged. Measured and true-count classifications remained identical.',
      52:f'At 70% sensitivity without false alarms, eligibility was {pct(s,"fraction_eligible")}%, observed RTM {pct(s)}% and MPC {num(s)}%. Type 3 affected {pct(s,"fraction_type3")}% of eligible participants. At full sensitivity and one false alarm/day, eligibility was {pct(far,"fraction_eligible")}%, observed RTM {pct(far)}% and MPC {num(far)}%. Type 3 affected {pct(far,"fraction_type3")}% of eligible participants and represented {pct(far,"type3_share_measured_RTM")}% of measured RTM cases. Table 1 and Figure 2 distinguish these outcomes.',
      55:'Changing one simulation input at a time showed how state, entry and measurement conditions altered apparent improvement without treatment. This controls the input being varied; it does not isolate independent causal RTM components. Detector errors changed enrollment and trial timing as well as measured trajectories. Type 3 identifies the paired measured-only classification within a selected person and window. It is neither the whole observed-RTM proportion under an imperfect detector nor the change in that proportion between conditions.',
      56:'Device-derived endpoints can reduce reporting errors, but sensitivity, false-alarm rates and correction rules become part of eligibility and outcome definitions [C1]. Measurement-only cases quantify one consequence under an assumed truth model. Measurement can also remove RTM classifications that are present on true counts, so Type 3 prevalence is not the net measured-minus-true RTM difference. A detector therefore needs evaluation within its intended trial design, beyond event-level performance alone.',
      59:'Design simulations should vary the entry threshold, baseline duration, within-person variability, sensitivity, false alarms, missingness and correction rules. Protocols should state how these enter eligibility and endpoint calculations. Comparisons should distinguish a common potential population with condition-specific enrollment from fixed enrolled membership and fixed trial windows. Paired classifications require a stated truth model and compatible reference scales. Reduced observed RTM alone does not demonstrate greater trial efficiency.',
      61:'The numerical estimates are specific to the seizure-diary model, rolling selection design, internal finite-history reference and correction rules. They should not be transported directly to another study or disease. The definitions can be applied to other fluctuating outcomes, but measurement-only Type 3 requires paired measured and true-count classifications, or an explicitly justified reference standard. Direct numerical comparison with a fixed-baseline study or a study using a separate long-term diary would mix designs.',
      63:'The common underlying population and reproducible seeds allow controlled changes to simulation inputs. Several limitations remain. CHOCOLATES is synthetic and its empirical calibration diaries may contain reporting errors, so treating generated counts as biological truth is an idealization. The transient replacement was not a data-derived illness model. Detector performance was constant across people and time; daily sampling cannot address within-day cycles or time-dependent errors. The 36-month reference is finite and includes the trial window. Monthly flooring and the rounded daily interval correction can affect selection. Type 3 depends on these modeling choices and is not a separate biological cause. Fixed-enrollment comparisons do not provide an additive causal decomposition. The analysis assessed within-arm apparent improvement, not bias in a randomized treatment contrast, statistical power or optimal trial efficiency.',
      65:'Transient rate changes, eligibility selection and detector errors can alter apparent improvement in simulated epilepsy trials without treatment. Measurement-only Type 3 RTM occurs when measured counts meet the RTM criterion and true counts do not for the same selected participant and window. Joint simulation of eligibility and measurement can distinguish this category from overall observed RTM while preserving the limits of within-arm inference.',
      73:'Source code, deterministic seeds, paired classification outputs and reproduction instructions are available in the anatomy_of_RTM repository, https://github.com/GoldenholzLab/anatomy_of_RTM. The simulator is available at https://github.com/GoldenholzLab/CHOCOLATES. The original and revised synthetic outputs are kept separately; no human participant data were used.',
      77:'During preparation of this work, the authors used OpenAI Codex to assist with analysis code, verification, manuscript revision and figure preparation. The authors are responsible for reviewing and verifying the content and take full responsibility for the published work.',
      103:'Figure 1. Operational RTM definitions. The first two columns illustrate return after temporary worsening and selection on natural variability. The Type 3 example meets RTM on measured counts but not true counts for the same person and window. B1 and B2 are baseline months; T1 to T3 are test months; ref is the reference rate. These examples do not partition observed RTM into additive causal components.',
      104:'Figure 2. Enrollment and paired RTM outcomes under each condition. A, eligibility yield among 1,000,000 potential participants. B, observed and true-count RTM among the same condition-selected participants and trial windows. C, measured-only Type 3 and true-only classifications, both using all selected participants as denominator. D, median percentage reduction from baseline to test without treatment. The reference uses true full-history counts, scaled by sensitivity for measured counts. FAR, false-alarm rate; sens., sensitivity. All plotted values are descriptive model outputs.'}
    for idx,text in replacements.items():replace(p[idx],text)
    paired_text='For every condition-selected participant, we applied the RTM rule to measured and true counts at the same selected baseline/test window, without an additional true-count eligibility filter. The four mutually exclusive groups were RTM on both scales, measured only, true only, or neither. Type 3 was the measured-only group. Its prevalence used all selected participants as denominator; its share of measured RTM used measured RTM cases. The net measured-minus-true difference equals measured-only minus true-only prevalence and is a separate quantity.'
    stats_text='Observed RTM used all selected participants. MPC excluded zero measured baselines, which have undefined percentage change, and we report these exclusions for fixed enrollment. Wilson 95% confidence intervals describe Type 3 prevalence, and order-statistic intervals describe the median. These intervals quantify Monte Carlo precision under the assumed model, not model uncertainty. No hypothesis tests or randomized treatment contrasts were performed.'
    insert_after(p[42],[paragraph(paired_text),paragraph(stats_text)])
    detail=(f'At one false alarm/day, {count(far,"type3_count")} selected participants had measured-only RTM and {count(far,"true_only_count")} had true-only RTM. The net measured-minus-true difference was {num(far,"net_measurement_difference_pp")} percentage points, distinct from Type 3 prevalence. With perfect-detector enrollment and baseline windows retained, observed RTM was {pct(s,"fixed_fraction_RTM")}% at 70% sensitivity and {pct(far,"fixed_fraction_RTM")}% at one false alarm/day. Corresponding MPCs were {num(s,"fixed_MPC")}% and {num(far,"fixed_MPC")}%, based on {count(s,"fixed_n_mpc")} and {count(far,"fixed_n_mpc")} positive measured baselines. Full paired counts and fixed-enrollment denominators are in the supplementary tables.')
    insert_after(p[52],[paragraph(detail)])
    abstract_words=sum(len(visible(p[i]).split()) for i in (14,15,16,17))
    main_nodes=[];in_main=False
    for node in root.find('w:body',NS):
        if node is p[29]:in_main=True
        if node is p[66]:in_main=False
        if in_main:main_nodes.append(node)
    main_words=sum(len(visible(node).split()) for node in main_nodes)
    replace(p[11],f'Manuscript counts: abstract {abstract_words} words; main text {main_words} words; 18 references; 2 figures; 1 table. Supplementary paired and fixed-enrollment tables supplied separately.')
    set_figure(parts,root,1,OUTPUTS/'rtm123_explainer.png',6.0)
    set_figure(parts,root,2,OUTPUTS/'rtm123_summary.png',6.5)
    table_rows=[]
    labels=['Perfect detector','Transient rate change','Entry threshold 8/month','Sensitivity 90%','Sensitivity 80%','Sensitivity 70%','FAR 1/month','FAR 1/week','FAR 1/day']
    for label,row in zip(labels,rows):table_rows.append([label,count(row),pct(row),pct(row,'fraction_true_RTM'),pct(row,'fraction_type3'),num(row)])
    body=root.find('w:body',NS);sect=body.find('w:sectPr',NS)
    nodes=[paragraph('Table 1. Enrollment, paired RTM classifications and apparent improvement','Heading2'),
           table(['Condition','Eligible n','Measured RTM %','True RTM %','Type 3 %','MPC %'],table_rows,[2760,1440,1320,1320,1200,1320]),
           paragraph('RTM percentages use all participants selected under that condition. Type 3 is measured RTM absent on true counts in the same person and window; it overlaps the measured-RTM column. MPC is median percentage reduction. All primary selected baselines were positive. Conditions without measurement error have zero Type 3 by construction. FAR, false-alarm rate.')]
    for node in nodes:body.insert(body.index(sect),node)
    assert fields_digest(root)==old_digest,'Live field instructions changed'
    parts['word/document.xml']=xmlbytes(root);write_package(dest,parts)
    (ROOT/'output/revision_2026-11-12/science_manifest.json').write_text(json.dumps({'source':str(source),'output':str(dest),'field_instructions_sha256':old_digest,'source_docx_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'analysis_version':'paired-type3-v2'},indent=2)+'\n')
    print(dest)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['science'],default='science');args=parser.parse_args();science()
