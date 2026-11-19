#!/usr/bin/env python3
"""Add the critical review's reporting details to Word-saved submission copies.

The document body and title/keyword metadata change. Existing fields, images,
styles and relationships are retained. Open both outputs in Microsoft Word for final
pagination checks and native saves. This script does not refresh citations.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
from pathlib import Path

from lxml import etree

from revise_anatomy_manuscript import (
    ROOT, OUTPUTS, NS, W, E, run, visible, replace, table,
    read_package, write_package, xmlbytes, fields_digest,
)
from prepare_seizure_submission import props, put


def text_paragraph(template, text, *, page_break=False, caption=False):
    node = copy.deepcopy(template)
    assert not node.xpath('.//w:fldChar | .//w:instrText', namespaces=NS)
    replace(node, text)
    pr = props(node)
    for tag in ('keepNext', 'pageBreakBefore'):
        old = pr.find('w:' + tag, NS)
        if old is not None:
            pr.remove(old)
    put(pr, 'spacing', before=80, after=80, line=240, lineRule='auto')
    if page_break:
        put(pr, 'pageBreakBefore')
    if caption:
        put(pr, 'keepNext')
    return node


def new_table(headers, rows, widths):
    node = table(headers, rows, widths)
    put(node.find('w:tblPr', NS), 'tblLayout', type='fixed')
    for para in node.findall('.//w:p', NS):
        put(props(para), 'keepNext')
    return node


def append_diagnostics(root):
    body = root.find('w:body', NS)
    diag = ROOT/'output/critical_review_2026-11-12/parent/diagnostics'
    rows = list(csv.DictReader((OUTPUTS/'condition_summary.csv').open()))
    labels = {x['condition']:label for x,label in zip(rows, [
        'Perfect detector','Transient rate change','Entry threshold 8/month',
        'Sensitivity 90%','Sensitivity 80%','Sensitivity 70%',
        'FAR 1/month','FAR 1/week','FAR 1/day'])}
    tables = body.findall('w:tbl', NS)
    # Use the same condition names as the main table.
    for node in tables[:3]:
        for tr,row in zip(node.findall('w:tr',NS)[1:], rows if node is not tables[2] else [x for x in rows if x['rtm_type']=='baseline' or x['rtm_type'].startswith('type3')]):
            replace(tr.find('w:tc/w:p',NS),labels[row['condition']])
    fixed = list(csv.DictReader((diag/'fixed_paired_classifications.csv').open()))
    summaries = {r['condition']:r for r in rows}
    fixed_rows = []
    for r in fixed:
        s=summaries[r['condition']]
        fixed_rows.append([labels[r['condition']],f"{int(r['fixed_n']):,}",f"{float(r['measured_rtm_pct']):.1f}",f"{float(r['type3_pct']):.1f}",f"{float(r['true_only_pct']):.1f}",f"{float(r['net_pp']):.1f}",f"{int(s['fixed_n_zero_baseline']):,}",f"{int(s['fixed_n_mpc']):,}",f"{float(s['fixed_MPC']):.1f}"])
    replacement = new_table(['Condition','Fixed n','RTM %','Type 3 %','True only %','Net pp','Zero B n','MPC n','MPC %'],fixed_rows,[2100,1050,800,800,900,900,850,1050,910])
    tables[2].getparent().replace(tables[2],replacement)
    for p in body.findall('w:p',NS):
        if visible(p).startswith('RTM and Type 3 percentages use all fixed participants.'):
            p.append(run(' True only denotes true RTM absent on measured counts. Net pp is measured minus true RTM, equivalently Type 3 minus true-only prevalence. The true RTM rate is 53.8% in every fixed row. Differences calculated from unrounded values can differ from subtraction of displayed rounded percentages.'))
        if visible(p).startswith('The net difference equals measured-only'):
            p.append(run(' Differences use unrounded values; subtraction of rounded percentages can differ by 0.1 percentage points.'))
    template=next(p for p in body.findall('w:p',NS) if visible(p).startswith('The four category counts'))
    caption=next(p for p in body.findall('w:p',NS) if visible(p).startswith('Table S1.'))
    def para(text,**kw):
        return text_paragraph(caption if kw.get('caption') else template,text,**kw)
    nodes=[]
    entry=[r for r in csv.DictReader((diag/'same_window_true_entry.csv').open()) if r['condition'].startswith('type3_far')]
    entry_rows=[[labels[r['condition']],f"{int(r['selected_n']):,}",f"{int(r['true_entry_pass_n']):,}",f"{float(r['true_entry_pass_pct']):.1f}",f"{float(r['type3_pct_within_pass']):.1f}",f"{float(r['type3_pct_within_fail']):.1f}",f"{float(r['type3_fail_share_pct']):.1f}"] for r in entry]
    nodes += [para('Table S7. True-count entry rules in detector-selected false-alarm windows',page_break=True,caption=True),
        new_table(['Condition','Selected n','True pass n','True pass %','Type 3 within pass %','Type 3 within fail %','Fail share of Type 3 %'],entry_rows,[1500,1300,1300,1000,1400,1400,1460]),
        para('Pass and fail apply the original entry rule to true counts in the baseline window selected using measured counts. True pass % uses all detector-selected participants. Type 3 within pass and within fail use the respective subgroup as denominator. Fail share uses all Type 3 cases. The pass and fail groups partition the selected population. All selected participants in the sensitivity-only conditions pass the true-count rule. This post hoc split describes enrollment composition and does not redefine the primary Type 3 population or assign a causal contribution to enrollment.'),
        para('At one false alarm/day, 391,290 of 985,321 detector-selected participants meet the true-count entry rule. Type 3 occurs in 61,303 of that group and 348,278 of the 594,031 who fail it. Thus, 85.0% of the primary Type 3 cases are in the latter group.')]
    refs=list(csv.DictReader((diag/'expected_reference_sensitivity.csv').open()))
    refrows=[[labels[r['condition']],f"{int(r['selected_n']):,}",f"{float(r['primary_measured_rtm_pct']):.1f}",f"{float(r['expected_reference_measured_rtm_pct']):.1f}",f"{float(r['primary_type3_pct']):.1f}",f"{float(r['expected_reference_type3_pct']):.1f}",f"{float(r['mean_reference_increase_events_per_month']):.2f}"] for r in refs]
    nodes += [para('Table S8. Post hoc sensitivity to the measured reference after flooring',page_break=True,caption=True),
        new_table(['Condition','Selected n','Primary RTM %','Expected-ref RTM %','Primary Type 3 %','Expected-ref Type 3 %','Mean ref shift /month'],refrows,[1500,1300,1250,1400,1250,1400,1260]),
        para('The primary measured reference is the finite true-count mean multiplied by sensitivity. For the alternative reference, we calculate the conditional expected corrected measured count for each retained true month, including independent Poisson alarms, expected-alarm subtraction and flooring at zero. We average those expectations over the same 36-month true path. Enrollment, selected windows, measured baseline and test counts, and the true RTM classification remain unchanged. The displayed shift is the selected-population mean increase in reference events/month.'),
        para('These full-cohort calculations change the measured-reference convention and therefore the estimand. They quantify a model dependency, rather than replace the primary analysis or estimate model uncertainty. At one false alarm/day, the expected measured reference is 1.09 events/month higher on average and 62,787 measured RTM classifications are removed. Type 3 remains present under this alternative, but its numerical prevalence is lower.')]
    screen=list(csv.DictReader((diag/'screen_timing.csv').open()))
    for number,which in [(9,'First screen'),(10,'Later screen')]:
        selected=[r for r in screen if r['screen']==which]
        data=[[labels[r['condition']],f"{int(r['n']):,}",f"{float(r['share_selected_pct']):.1f}",f"{float(r['measured_rtm_pct']):.1f}",f"{float(r['type3_pct']):.1f}",f"{float(r['MPC']):.1f}"] for r in selected]
        nodes += [para(f'Table S{number}. Outcomes among participants qualifying at the '+('first screen' if number==9 else 'later screens'),page_break=True,caption=True),
            new_table(['Condition','Participants n','Share selected %','RTM %','Type 3 %','MPC %'],data,[2760,1500,1500,1200,1200,1200]),
            para('The first screen starts at month 0. Later screens have first qualifying start months 1 to 31. Share selected uses each condition\'s total enrolled population; outcome percentages use the row population. Tables S9 and S10 partition enrollment and recombine to the primary RTM and Type 3 rates. Medians do not combine by weighted averaging. These post hoc selected strata describe repeated screening and are not randomized groups.')]
    diagnostic=json.loads((diag/'diagnostics.json').read_text())
    c=diagnostic['comparator'];selected=c['selected_window'];random=c['random_window_same_perfect_selected_people']
    data=[[label,f"{int(r['n']):,}",f"{r['rtm_pct']:.1f}",f"{int(r['mpc_n']):,}",f"{r['MPC']:.1f}"] for label,r in [('First eligible window',selected),('Random window, same people',random)]]
    nodes += [para('Table S11. Operational RTM at selected and random windows',page_break=True,caption=True),
        new_table(['Window rule','Participants n','RTM %','MPC n','MPC %'],data,[3300,1700,1300,1760,1300]),
        para('Both rows retain the 649,098 perfect-detector enrollees. In the second row, one start month is drawn uniformly from 0 to 31 for each retained person with NumPy generator seed 20261113, without checking counts. Random windows need not pass the trial entry rule. The RTM denominator includes all retained people; MPC excludes 7,736 zero random baselines. The internal true reference and two-baseline/three-test-month lengths are unchanged.'),
        para('Operational RTM can occur without selecting an unusually high window. The same-person random-window rate is 25.7%, with median reduction 0.0% among positive baselines. This is a post hoc descriptive comparator within an already selected population. The difference from 53.8% is not an additive causal estimate of selection-driven RTM.')]
    sect=body.find('w:sectPr',NS)
    for node in nodes:sect.addprevious(node)


def extend_main(root, references):
    body=root.find('w:body',NS)
    # Publication name and both existing affiliations confirmed by the author
    # in this review conversation on November 13, 2026.
    for text_node in body.findall('.//w:t',NS):
        if text_node.text and 'Brandon Westover' in text_node.text:
            text_node.text=text_node.text.replace('Brandon Westover','M. Brandon Westover')
    paragraphs=body.findall('w:p',NS)
    def find(prefix):
        hits=[p for p in paragraphs if visible(p).startswith(prefix)]
        assert len(hits)==1,prefix
        return hits[0]
    p=find('Results: With perfect detection,')
    text=visible(p).replace('At 70% sensitivity, observed RTM was 59.0% and Type 3 affected 7.7% of eligible participants.','At 70% sensitivity, observed RTM was 59.0%; Type 3 and true-only RTM occurred in 7.7% and 4.8% of detector-selected participants, respectively.').replace('At one false alarm/day, corresponding values were 69.9% and 41.6%;','At one false alarm/day, observed RTM was 69.9% and Type 3 prevalence was 41.6%;').replace('Type 3 represented 59.4% of measured RTM cases.','Type 3 represented 59.4% of measured RTM cases under the specified correction and reference rules.')
    text=text.replace('and Type 3 prevalence was 41.6%;', 'and Type 3 prevalence was 41.6% among detector-selected participants; 85.0% of these cases failed true-count entry.')
    replace(p,text)
    # Reuse the existing live single-item citation for reference 1. No Zotero
    # library import is needed, and its cached number remains valid here.
    import uuid
    for source in paragraphs:
        instructions=source.xpath('.//w:instrText/text()',namespaces=NS)
        if len(instructions)!=1 or 'CSL_CITATION ' not in instructions[0]:
            continue
        payload=json.loads(instructions[0].split('CSL_CITATION ',1)[1])
        if len(payload['citationItems'])==1 and payload['citationItems'][0].get('id')==677:
            citation_runs=[];inside=False
            for node in source:
                marks=node.findall('.//w:fldChar',NS)
                if any(m.get('{'+W+'}fldCharType')=='begin' for m in marks):inside=True
                if inside:citation_runs.append(copy.deepcopy(node))
                if inside and any(m.get('{'+W+'}fldCharType')=='end' for m in marks):break
            break
    else:
        raise AssertionError('Existing live reference 1 citation not found')
    instruction=next(n for node in citation_runs for n in node.findall('.//w:instrText',NS))
    payload['citationID']='review_'+uuid.uuid4().hex[:12]
    instruction.text=' ADDIN ZOTERO_ITEM CSL_CITATION '+json.dumps(payload,ensure_ascii=False)+' '
    p=find('Previous seizure-trial simulations')
    opening,rest=visible(p).split('. ',1)
    replace(p,opening+' ')
    for node in citation_runs:p.append(node)
    p.append(run('. '+rest))
    p=find('We distinguish three operational forms of RTM')
    p.append(run(' The transient experiment includes upward and downward changes; Figure 1 illustrates an upward change.'))
    p=find('Eligibility was assessed in rolling')
    replace(p,'Eligibility was assessed in rolling 2-month baseline windows with start months 0 to 31, leaving three subsequent test months. We used the first eligible window. The entry rule required a mean baseline frequency of at least 4 events/month, at least 3 events in each baseline month, and no baseline event-free interval longer than 25 days. The 25-day limit follows the Krauss et al. trial; Chung et al. used 21 days [C1]. We used 30-day months in place of the trials\' 4-week segments. Patients with no eligible window were excluded from RTM and percentage-change summaries but remained in eligibility-yield denominators.')
    p=find('The reference condition used 100% sensitivity')
    p.append(run(' Detections are independent binomial thinnings of true events. Counts are not divided by sensitivity before applying the entry thresholds. The rounded daily alarm subtraction is zero at 1/month and 1/week, so raw recorded events enter the 25-day check in those settings. The replacement-to-original sampled rate ratio has 5th and 95th percentiles 0.07 and 14.41.'))
    p=find('This descriptive simulation used no human participants')
    p.append(run(' The additional enrollment, screening-time, random-window and expected-reference diagnostics in Tables S7 to S11 were added in response to critical review and were also post hoc.'))
    p=find('With perfect detection and the 4-event/month')
    p.append(run(' Of the enrollees, 330,389 qualified at the first screen, with 38.3% RTM and 14.6% MPC; the remaining 318,709 qualified later, with 69.8% RTM and 40.0% MPC. A random-window diagnostic in the same people gave 25.7% RTM and 0.0% MPC among positive baselines, so the operational prevalence is not itself an excess attributable to selection. Tables S9 to S11 give the definitions and denominators.'))
    p=find('With the temporary rate change, eligibility was')
    p.append(run(' In the baseline-only stratum, 77.8% never qualified in the perfect-detector reference condition.'))
    p=find('At one false alarm/day, 409,581')
    for text in reversed([
        'At one false alarm/day, only 39.7% of detector-selected participants meet the entry rule on true counts in that window. Of Type 3 cases, 85.0% occur in those who fail that rule; prevalence within the true-rule-passing subgroup is 15.7% (Table S7).',
        'With enrollment and counts retained but the measured reference replaced by its conditional expectation after flooring, measured RTM is 63.6% and Type 3 is 37.3% (Table S8). This alternative changes the measured-reference convention.',
        'Fixed enrollment produces more true-only than measured-only cases in every imperfect-detector condition. At 70% sensitivity these proportions are 9.1% and 5.4%, giving a net reduction of 3.7 percentage points (Table S3).',
    ]):
        new=copy.deepcopy(p);replace(new,text);p.addnext(new)
    p=find('RTM percentages use all participants selected')
    p.append(run(' These are operational prevalences, not excesses attributable to selection. MPC uses discrete count ratios, so ties can give identical medians and interval endpoints. Net differences elsewhere use unrounded values.'))
    p=find('The common underlying population and reproducible seeds')
    p.append(run(' The rolling design permits up to 32 monthly screens and differs from a single prospective baseline. Enrollment composition, reference convention and correction rules materially affect the numerical estimates.'))
    p=find('During preparation of this work, the authors used OpenAI Codex')
    replace(p,'During preparation of this work, the authors used OpenAI Codex and Anthropic Claude to assist with analysis code, verification, critical review, manuscript revision and figure preparation. The authors are responsible for reviewing and verifying the content and take full responsibility for the published work.')
    p=find('Figure 1. Operational RTM definitions.')
    p.append(run(' RTM 1, 2 and 3 label Types 1, 2 and 3. The Type 3 illustration uses full sensitivity, so the two references coincide; reduced-sensitivity conditions use the scaling defined in Methods.'))
    p=find('Figure 2. Enrollment and paired RTM outcomes')
    p.append(run(' In A and D, colors distinguish input-condition families; condition names identify each bar.'))
    # New references are supplied from verified local Zotero items. Refresh in Word.
    if references is not None:
        def citation(item_key):
            import uuid
            item=references[item_key]
            uri=item['id']
            payload={'citationID':'review_'+uuid.uuid4().hex[:12], 'properties':{'formattedCitation':'[citation pending Word refresh]','plainCitation':'[citation pending Word refresh]','noteIndex':0}, 'citationItems':[{'id':uri,'uris':[uri],'itemData':item}], 'schema':'https://github.com/citation-style-language/schema/raw/master/csl-citation.json'}
            nodes=[]
            for kind in ('begin','instruction','separate','text','end'):
                r=E('r')
                if kind=='instruction':
                    t=E('instrText');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=' ADDIN ZOTERO_ITEM CSL_CITATION '+json.dumps(payload,ensure_ascii=False)+' ';r.append(t)
                elif kind=='text':r.append(E('t'));r[0].text='[citation pending Word refresh]'
                else:r.append(E('fldChar',fldCharType=kind))
                nodes.append(r)
            return nodes
        def cited_paragraph(anchor,text,key):
            p=copy.deepcopy(find('This descriptive simulation used no human participants'))
            replace(p,text+' ')
            for node in citation(key):p.append(node)
            anchor.addnext(p)
            return p
        cited_paragraph(find('Design simulations should vary'), 'A subsequent re-review of earlier work found that separating eligibility from baseline reduced RTM yet worsened simulated trial efficiency. This reinforces the need to evaluate randomized contrasts and resource burden directly.', 'counterintuitive')
        cited_paragraph(find('The numerical estimates are specific'), 'A related device-sensitivity preprint used a single baseline and reported 38.2% RTM and 14.7% MPC with perfect detection. Our first-screen subset gives 38.3% and 14.6%. This descriptive comparison illustrates design dependence; it is not a replication of that study or a claim that screening explains every cross-study difference.', 'device_preprint')
        cited_paragraph(find('We generated 1,000,000 synthetic patients'), 'An earlier preprint of this manuscript described measurement conditions as Type 3. The present revision uses a participant-level paired definition and reports condition totals separately.', 'anatomy_preprint')
    # Count the final text, including inserted related-work paragraphs.
    abstract=[];main=[];in_abstract=False;in_main=False
    for p in body.findall('w:p',NS):
        text=visible(p)
        if text=='Abstract':in_abstract=True;continue
        if text.startswith('Keywords:'):in_abstract=False
        if in_abstract:abstract.append(text)
        if text=='1. Introduction':in_main=True
        if text=='Funding':in_main=False
        if in_main and not p.findall('.//w:drawing',NS) and not text.startswith(('Figure 1.','Figure 2.','Table 1.','RTM percentages use')):main.append(text)
    # Each new single-item citation becomes one citation token after Word's
    # Zotero refresh, rather than the four-word temporary cached marker.
    aw=len(' '.join(abstract).split());mw=len(' '.join(main).replace('[citation pending Word refresh]','[ref]').split());assert aw<=250 and mw<=4000
    p=find('Manuscript counts:')
    for t in p.findall('.//w:t',NS):
        if 'main text' in (t.text or ''):t.text=re.sub(r'abstract \d+ words; main text \d+ words',f'abstract {aw} words; main text {mw} words',t.text)
        if references is not None and '18 references' in (t.text or ''):t.text=t.text.replace('18 references','21 references')


def replace_plain_fragment(node, old, new):
    matches = [t for t in node.findall('.//w:t', NS) if old in (t.text or '')]
    assert len(matches) == 1, (old, len(matches))
    matches[0].text = matches[0].text.replace(old, new, 1)


def revise_main(root):
    body = root.find('w:body', NS)
    paragraphs = body.findall('w:p', NS)
    changes = []

    def find(prefix):
        found = [p for p in paragraphs if visible(p).startswith(prefix)]
        assert len(found) == 1, prefix
        return found[0]

    p = find('We generated 1,000,000 synthetic patients')
    replace_plain_fragment(
        p, 'an open-source simulator of heterogeneous seizure rates, clustering, cycles and the association between frequency and variability',
        'an open-source configurable simulator of seizure occurrence',
    )
    p.append(run(' The available daily generator retains sparse long-period cyclic modulation; its settings and the limits of historical source provenance are described in the supplementary methods.'))
    changes.append('Methods 2.1: qualify the daily cycle configuration and refer to supplementary methods.')

    p = find('Observed RTM used all selected participants.')
    p.append(run(' Tables S5 and S6 report the median intervals for primary and fixed enrollment, respectively.'))
    changes.append('Methods 2.4: locate the reported median intervals.')

    p = find('With the temporary rate change, eligibility was')
    p.append(run(' Table S4 reports every overlap stratum by sampled rate direction. For baseline-only overlap, RTM was 98.9% with a higher sampled rate and 30.6% with a lower sampled rate.'))
    changes.append('Results 3.2: report direction heterogeneity and cite Table S4.')

    p = find('The common underlying population and reproducible seeds')
    replace_plain_fragment(
        p, 'daily sampling cannot address within-day cycles or time-dependent errors.',
        'daily sampling cannot address within-day cycles or time-dependent errors. The available cycle settings omit weekly and 4-to-45-day modulation and retain 90-to-450-day modulation with probability 0.011649, so robustness to other cycle distributions was not assessed.',
    )
    changes.append('Limitations 4.4: state the restricted cycle settings.')

    p = find('The project repository is https://github.com/')
    p.append(run(' The original cohort lacks a contemporaneous generator-source fingerprint. The current source snapshot and successful sampled seeded replays document present compatibility rather than establish the historical generator identity.'))
    changes.append('Data and code availability: acknowledge the historical provenance gap.')

    # Preserve the live footnote and all existing formatting in the count line.
    main = []
    in_main = False
    for p in paragraphs:
        txt = visible(p)
        if txt == '1. Introduction':
            in_main = True
        if txt == 'Funding':
            in_main = False
        if in_main and not p.findall('.//w:drawing', NS) and not txt.startswith(('Figure 1.', 'Figure 2.', 'Table 1.', 'RTM percentages use')):
            main.append(txt)
    count = len(' '.join(main).split())
    p = find('Manuscript counts:')
    replace_plain_fragment(p, 'main text 1809 words', f'main text {count} words')
    return changes


def revise_supplement(root):
    body = root.find('w:body', NS)
    assert len(body.findall('w:tbl', NS)) == 3, 'Use the Word-saved supplement with three original tables.'
    paragraphs = body.findall('w:p', NS)
    note = next(p for p in paragraphs if visible(p).startswith('The four category counts'))
    caption = next(p for p in paragraphs if visible(p).startswith('Table S1.'))
    title = paragraphs[0]
    replace(title, 'Supplementary methods and simulation results')
    nodes = []

    def para(text, **kwargs):
        return text_paragraph(caption if kwargs.get('caption') else note, text, **kwargs)

    rows = list(csv.DictReader((OUTPUTS / 'condition_summary.csv').open()))
    labels = {
        'baseline_perfect': 'Perfect detector',
        'type1_transient_msf': 'Transient rate change',
        'type2_threshold_8': 'Entry threshold 8/month',
        'type3_sensitivity_90': 'Sensitivity 90%',
        'type3_sensitivity_80': 'Sensitivity 80%',
        'type3_sensitivity_70': 'Sensitivity 70%',
        'type3_far_1_per_month': 'FAR 1/month',
        'type3_far_1_per_week': 'FAR 1/week',
        'type3_far_1_per_day': 'FAR 1/day',
    }
    strata = list(csv.DictReader((OUTPUTS / 'type1_overlap_summary.csv').open()))
    overlap_labels = {'baseline': 'Baseline only', 'baseline_and_test': 'Baseline and test', 'test': 'Test only', 'neither': 'Neither', 'not_eligible': 'Never eligible'}
    strata_rows = []
    for overlap, label in overlap_labels.items():
        for direction in ('all', 'higher', 'lower'):
            row = next(x for x in strata if x['overlap'] == overlap and x['shock_msf_relation'] == direction)
            enrolled = int(row['n_eligible']) > 0
            strata_rows.append([label, 'Pooled' if direction == 'all' else direction.capitalize(), f"{int(row['n_raw']):,}", f"{100*float(row['fraction_RTM']):.1f}" if enrolled else 'NA', f"{float(row['MPC']):.1f}" if enrolled else 'NA'])
    nodes.extend([
        para('Table S4. Transient replacement by overlap and sampled rate direction', page_break=True, caption=True),
        new_table(['Overlap', 'Sampled rate', 'Participants n', 'RTM %', 'MPC %'], strata_rows, [2580,1700,1800,1640,1640]),
        para('Higher and lower compare the sampled replacement monthly seizure-frequency parameter with the original sampled parameter. They do not describe realized count changes or verified clinical worsening. Each enrolled row uses its participant count as denominator. Pooled overlap groups contain 756,179 eligible participants; 243,821 never qualified. Never-eligible outcomes are undefined, shown as NA. Negative MPC denotes a median increase. These selected strata are descriptive and do not estimate causal effects of rate direction.'),
    ])

    primary = [[labels[x['condition']], f"{int(x['n_mpc']):,}", f"{float(x['MPC']):.2f}", f"{float(x['MPC_ci_lo']):.2f} to {float(x['MPC_ci_hi']):.2f}"] for x in rows]
    nodes.extend([
        para('Table S5. Median percentage reduction with condition-specific enrollment', page_break=True, caption=True),
        new_table(['Condition', 'MPC n', 'MPC %', '95% median CI'], primary, [3300,1700,1500,2860]),
        para('MPC uses positive measured baselines among participants selected under each condition. All primary selected baselines were positive. The approximate order-statistic intervals describe Monte Carlo precision under the assumed model. They do not measure uncertainty in the simulator or clinical transportability. Discrete percentage changes can give identical interval endpoints.'),
    ])
    fixed = [x for x in rows if x['rtm_type'] == 'baseline' or x['rtm_type'].startswith('type3')]
    fixed_rows = [[labels[x['condition']], f"{int(x['fixed_n_mpc']):,}", f"{float(x['fixed_MPC']):.2f}", f"{float(x['fixed_MPC_ci_lo']):.2f} to {float(x['fixed_MPC_ci_hi']):.2f}"] for x in fixed]
    nodes.extend([
        para('Table S6. Median percentage reduction with fixed enrollment and windows', page_break=True, caption=True),
        new_table(['Condition', 'MPC n', 'MPC %', '95% median CI'], fixed_rows, [3300,1700,1500,2860]),
        para('Membership and baseline windows are those of the 649,098 perfect-detector participants. MPC excludes zero measured baselines, as counted in Table S3. These intervals use the same approximate order-statistic method as Table S5 and describe simulation-conditional precision.'),
        para('Supplementary generator settings and source provenance', page_break=True, caption=True),
        para('The available generator calls simple_CHOCOLATES at one sample per day, with clustering enabled and default cycle settings. Its sampling rule excludes the 12-hour and 24-hour components. The weekly component has zero amplitude, and the 4-to-45-day component has zero selection probability. A 90-to-450-day component is selected with probability 0.011649. Thus, 98.8351% of newly generated histories have no nonzero explicit cycle waveform under these defaults. This does not imply absence of stochastic variability or clustering. Nonzero retained waveforms are normalized to unit peak. Robustness to other cycle distributions was not assessed.'),
        para('The retained million-person cohort has master seed 20260531 and patient-specific seeds, but its original metadata does not identify the historical generator-source bytes. During this review, the current source reproduced 1,024 sampled retained histories exactly. This supports compatibility for those histories. It does not establish the historical source identity for the full cohort. The revised transient analysis records the current simulator SHA-256 as b038553df164160290b427e577ba53cb6b983db38f00a281f9a773a91a1d6b99. The local review archive retains those exact source bytes. Public reproduction also requires a retrievable source snapshot, the retained cohort and seeds, paired outputs, manifest and numerical environment.'),
    ])
    sect = body.find('w:sectPr', NS)
    for node in nodes:
        if sect is None:
            body.append(node)
        else:
            sect.addprevious(node)
    return ['Supplement: add complete Type 1 overlap/direction strata, primary and fixed median intervals, and generator/provenance details.']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination-dir', type=Path, required=True)
    parser.add_argument('--references-json', type=Path)
    args = parser.parse_args()
    references=json.loads(args.references_json.read_text()) if args.references_json else None
    args.destination_dir.mkdir(parents=True, exist_ok=True)
    record = []
    for filename, patch in (
        ('anatomy_of_RTM_Seizure.docx', revise_main),
        ('anatomy_of_RTM_Seizure_Supplement.docx', revise_supplement),
    ):
        source = ROOT / filename
        destination = args.destination_dir / filename
        assert destination.resolve() != source.resolve(), 'Write a separate review copy before replacing an authoritative document.'
        parts = read_package(source)
        root = etree.fromstring(parts['word/document.xml'])
        before_fields = fields_digest(root)
        old_instructions=root.xpath('.//w:instrText/text()',namespaces=NS)
        before_marks = [n.get('{'+W+'}fldCharType') for n in root.findall('.//w:fldChar', NS)]
        protected = root.xpath('.//w:ins | .//w:del | .//w:commentRangeStart | .//w:commentRangeEnd | .//w:commentReference', namespaces=NS)
        protected_before = [etree.tostring(n) for n in protected]
        original_tables = [etree.tostring(t) for t in root.findall('.//w:tbl', NS)]
        changes = patch(root)
        if filename=='anatomy_of_RTM_Seizure.docx':
            extend_main(root,references)
        else:
            append_diagnostics(root)
        new_instructions=root.xpath('.//w:instrText/text()',namespaces=NS)
        cursor=iter(new_instructions)
        assert all(any(new==old for new in cursor) for old in old_instructions)
        marks=[n.get('{'+W+'}fldCharType') for n in root.findall('.//w:fldChar', NS)]
        added=(1+(3 if references is not None else 0)) if filename=='anatomy_of_RTM_Seizure.docx' else 0
        assert all(marks.count(k)==before_marks.count(k)+added for k in ('begin','separate','end'))
        assert [etree.tostring(n) for n in protected] == protected_before
        if filename=='anatomy_of_RTM_Seizure.docx':
            assert [etree.tostring(t) for t in root.findall('.//w:tbl', NS)][:len(original_tables)] == original_tables
        parts['word/document.xml'] = xmlbytes(root)
        if 'docProps/core.xml' in parts:
            core=etree.fromstring(parts['docProps/core.xml'])
            title=core.find('{http://purl.org/dc/elements/1.1/}title')
            if title is not None:title.text=visible(root.find('w:body/w:p',NS))
            keywords=core.find('{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}keywords')
            keyword_line=next((visible(p) for p in root.findall('w:body/w:p',NS) if visible(p).startswith('Keywords:')),None)
            if keywords is not None and keyword_line:keywords.text=keyword_line.split(':',1)[1].strip()
            parts['docProps/core.xml']=xmlbytes(core)
        if 'docProps/app.xml' in parts:
            app=etree.fromstring(parts['docProps/app.xml'])
            titles=app.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}TitlesOfParts/{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}vector/{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}lpstr')
            if len(titles)==1:titles[0].text=visible(root.find('w:body/w:p',NS))
            parts['docProps/app.xml']=xmlbytes(app)
        write_package(destination, parts)
        with __import__('zipfile').ZipFile(source) as old, __import__('zipfile').ZipFile(destination) as new:
            assert old.namelist() == new.namelist()
            assert all(old.read(n) == new.read(n) for n in old.namelist() if n not in ('word/document.xml','docProps/core.xml','docProps/app.xml'))
        record.append({'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'destination': str(destination), 'destination_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'original_live_field_instructions_sha256': before_fields, 'original_live_field_instructions_preserved':True,'new_live_citations':added,'related_work_citations_pending':references is None and filename=='anatomy_of_RTM_Seizure.docx','changes': changes})
    (args.destination_dir / 'reporting_changes.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
