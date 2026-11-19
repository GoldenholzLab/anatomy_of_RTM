#!/usr/bin/env python3
"""Package the reviewed Anatomy manuscript for Seizure without changing results.

This stage reads the reviewed working DOCX. It never rewrites it or any RTM3
file. Live Zotero instructions are retained for refresh through Word/Zotero.
"""
from pathlib import Path
from lxml import etree
import copy
import csv
import json
import re
from revise_anatomy_manuscript import (ROOT,OUTPUTS,W,NS,E,run,paragraph,visible,replace,
    read_package,write_package,xmlbytes,fields_digest,table,pct,num,count,set_figure)

SOURCE=ROOT/'anatomy_of_RTM_revised.docx'
DEST=ROOT/'anatomy_of_RTM_Seizure.docx'


def props(p):
    pr=p.find('w:pPr',NS)
    if pr is None:pr=E('pPr');p.insert(0,pr)
    return pr


def put(pr,tag,**attrs):
    e=pr.find('w:'+tag,NS)
    if e is None:e=E(tag);pr.append(e)
    for key,value in attrs.items():e.set('{'+W+'}'+key,str(value))
    return e


def set_style(parts):
    root=etree.fromstring(parts['word/styles.xml'])
    for style in root.findall('w:style',NS):
        sid=style.get('{'+W+'}styleId')
        if sid in ('Normal','Title','Heading1','Heading2','Heading3','Abstract','Figurecaption','Bibliography','FootnoteText'):
            rpr=style.find('w:rPr',NS)
            if rpr is None:rpr=E('rPr');style.append(rpr)
            put(rpr,'rFonts',ascii='Times New Roman',hAnsi='Times New Roman',eastAsia='Times New Roman')
            put(rpr,'color',val='000000')
            put(rpr,'sz',val=28 if sid=='Title' else 20 if sid in ('Figurecaption','FootnoteText') else 24)
            for k in ('asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme'):
                rpr.find('w:rFonts',NS).attrib.pop('{'+W+'}'+k,None)
            ppr=style.find('w:pPr',NS)
            if ppr is None:ppr=E('pPr');style.append(ppr)
            put(ppr,'spacing',before=0,after=0,line=240 if sid in ('Figurecaption','FootnoteText') else 480,lineRule='auto')
            put(ppr,'widowControl')
            border=ppr.find('w:pBdr',NS)
            if border is not None:ppr.remove(border)
            if sid in ('Title','Heading1','Heading2','Heading3'):put(rpr,'b')
    parts['word/styles.xml']=xmlbytes(root)


def add_abbreviation_footnote(parts,anchor):
    path='word/footnotes.xml'
    foot=etree.fromstring(parts[path]) if path in parts else etree.Element('{'+W+'}footnotes',nsmap={'w':W})
    used=[int(n.get('{'+W+'}id')) for n in foot]
    fid=max(used+[0])+1
    note=E('footnote',id=fid);p=paragraph('', 'FootnoteText')
    r=E('r');r.append(E('footnoteRef'));p.append(r)
    p.append(run(' RTM, regression to the mean; MPC, median percentage change; FAR, false-alarm rate.',size=20))
    note.append(p);foot.append(note);parts[path]=xmlbytes(foot)
    r=E('r');pr=E('rPr');pr.append(E('rStyle',val='FootnoteReference'));r.append(pr);r.append(E('footnoteReference',id=fid));anchor.append(r)
    pr.append(E('vertAlign',val='superscript'));pr.append(E('sz',val=18))
    relroot=etree.fromstring(parts['word/_rels/document.xml.rels']);reltype='http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes'
    if not any(x.get('Type')==reltype for x in relroot):
        x=etree.SubElement(relroot,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
        x.set('Id','rIdAnatomyFootnotes');x.set('Type',reltype);x.set('Target','footnotes.xml')
    parts['word/_rels/document.xml.rels']=xmlbytes(relroot)
    ct=etree.fromstring(parts['[Content_Types].xml'])
    if not any(x.get('PartName')=='/word/footnotes.xml' for x in ct):
        x=etree.SubElement(ct,'{http://schemas.openxmlformats.org/package/2006/content-types}Override')
        x.set('PartName','/word/footnotes.xml');x.set('ContentType','application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml')
    parts['[Content_Types].xml']=xmlbytes(ct)


def create_companion(parts,path,nodes):
    clone=copy.deepcopy(parts);r=etree.fromstring(clone['word/document.xml']);b=r.find('w:body',NS)
    sect=copy.deepcopy(b.find('w:sectPr',NS))
    for x in list(b):b.remove(x)
    for x in nodes:b.append(x)
    b.append(sect);clone['word/document.xml']=xmlbytes(r)
    if 'docProps/core.xml' in clone:
        core=etree.fromstring(clone['docProps/core.xml'])
        title=core.find('{http://purl.org/dc/elements/1.1/}title')
        if title is not None:title.text=visible(nodes[0])
        clone['docProps/core.xml']=xmlbytes(core)
    # Unused package relationships are harmless; retain the source package's
    # styles, numbering and artwork rather than reconstructing the DOCX.
    if 'word/settings.xml' in clone:
        settings=etree.fromstring(clone['word/settings.xml'])
        track=settings.find('w:trackRevisions',NS)
        if track is not None:settings.remove(track)
        clone['word/settings.xml']=xmlbytes(settings)
    write_package(path,clone)


def main():
    parts=read_package(SOURCE);r=etree.fromstring(parts['word/document.xml']);b=r.find('w:body',NS)
    digest=fields_digest(r);paras=list(b.findall('w:p',NS))
    field_marks=sorted(x.get('{'+W+'}fldCharType') for x in r.findall('.//w:fldChar',NS))
    # Remove the JCE-specific context panel, retaining all scientific body text.
    for p in paras:
        text=visible(p)
        if text=='What is new?':
            following=p.getnext()
            if following is not None and following.tag=='{'+W+'}tbl':b.remove(following)
            b.remove(p)
        elif text.startswith('Keywords:') and b.index(p)<12:b.remove(p)
        elif text=='Original Research':replace(p,'Full-length original research article')
        elif text.startswith('Background and Objective:'):replace(p,text.replace('Background and Objective:','Purpose:',1))
        elif text.startswith('Discussion: Detector errors'):replace(p,text.replace('Discussion:','Conclusion:',1))
        elif text.startswith('Running title:'):replace(p,'Running title: Regression to the mean in epilepsy trials')
    pictures=b.xpath('./w:p[.//w:drawing]',namespaces=NS)
    captions=[p for p in b.findall('w:p',NS) if re.match(r'Figure [12]\. ',visible(p))]
    assert len(pictures)==2 and len(captions)==2
    for p in pictures+captions:b.remove(p)
    for p in list(b.findall('w:p',NS)):
        if visible(p) in ('Figure legends','Figure 1','Figure 2'):b.remove(p)
    table_title=next(p for p in b.findall('w:p',NS) if visible(p).startswith('Table 1.'))
    table_node=table_title.getnext();table_note=table_node.getnext()
    for p in (table_title,table_node,table_note):b.remove(p)
    intro_anchor=next(p for p in b.findall('w:p',NS) if visible(p).startswith('Previous seizure-trial simulations'))
    results_anchor=next(p for p in b.findall('w:p',NS) if visible(p).startswith('At 70% sensitivity'))
    detail_anchor=next(p for p in b.findall('w:p',NS) if visible(p).startswith('At one false alarm/day,'))
    for anchor,nodes in ((intro_anchor,[pictures[0],captions[0]]),(results_anchor,[pictures[1],captions[1]]),
                         (detail_anchor,[table_node,table_title,table_note])):
        for node in nodes:anchor.addnext(node);anchor=node
    # Avoid residual standalone page breaks from the old end-of-file figures.
    first_break_kept=False
    for p in list(b.findall('w:p',NS)):
        structural=p.xpath('.//w:fldChar | .//w:instrText | .//w:bookmarkStart | .//w:bookmarkEnd | .//w:commentRangeStart | .//w:commentRangeEnd | .//w:footnoteReference',namespaces=NS)
        if not visible(p).strip() and not p.findall('.//w:drawing',NS) and not structural:
            page_break=p.find('.//w:br[@w:type="page"]',NS)
            if page_break is not None and not first_break_kept:first_break_kept=True
            else:b.remove(p)
    for p in b.findall('w:p',NS):
        pr=props(p)
        for tag in ('ind','keepNext','pageBreakBefore'):
            item=pr.find('w:'+tag,NS)
            if item is not None:pr.remove(item)
        if p in pictures:
            put(pr,'spacing',before=120,after=0,line=240,lineRule='auto');put(pr,'keepNext');put(pr,'jc',val='center')
        elif p in captions or p is table_title or p is table_note:
            put(pr,'pStyle',val='Figurecaption');put(pr,'spacing',before=60,after=120,line=240,lineRule='auto')
            if p is table_title:put(pr,'keepNext')
        else:
            put(pr,'spacing',before=0,after=0,line=480,lineRule='auto')
            sid=pr.find('w:pStyle',NS)
            if sid is not None and sid.get('{'+W+'}val') in ('Heading1','Heading2'):put(pr,'keepNext')
    # Simple black headings and typography, retaining all citation field XML.
    set_style(parts)
    journal_figure=ROOT/'output/seizure_figures/Figure_2.png'
    if journal_figure.exists():set_figure(parts,r,2,journal_figure,6.5)
    introduction=next(p for p in b.findall('w:p',NS) if visible(p)=='1. Introduction')
    put(props(introduction),'pageBreakBefore')
    for cell_p in b.findall('.//w:tbl//w:p',NS):put(props(cell_p),'keepNext')
    for name in list(parts):
        if re.fullmatch(r'word/header\d+\.xml',name):
            header=etree.fromstring(parts[name])
            for t in header.findall('.//w:t',NS):
                if t.text=='Regression to the mean in clinical trials':t.text='Regression to the mean in epilepsy trials'
            for color in header.findall('.//w:color',NS):
                color.set('{'+W+'}val','000000');color.attrib.pop('{'+W+'}themeColor',None)
            parts[name]=xmlbytes(header)
    for p in b.findall('w:p',NS):
        if p in pictures:continue
        for rr in p.findall('w:r',NS):
            pr=rr.find('w:rPr',NS)
            if pr is not None:
                for child in pr.findall('w:color',NS):child.set('{'+W+'}val','000000');child.attrib.pop('{'+W+'}themeColor',None)
    for rr in b.findall('.//w:tbl//w:r',NS):
        pr=rr.find('w:rPr',NS)
        if pr is None:pr=E('rPr');rr.insert(0,pr)
        put(pr,'sz',val=20)
    # Footnote is anchored in first-page manuscript information.
    info=next(p for p in b.findall('w:p',NS) if visible(p).startswith('Manuscript counts:'))
    add_abbreviation_footnote(parts,info)
    abstract=[];main_text=[];in_abstract=False;in_main=False
    for p in b.findall('w:p',NS):
        text=visible(p)
        if text=='Abstract':in_abstract=True;continue
        if in_abstract and text.startswith('Keywords:'):in_abstract=False
        if in_abstract:abstract.append(text)
        if text=='1. Introduction':in_main=True
        if text=='Funding':in_main=False
        if in_main and p not in pictures+captions and p not in (table_title,table_note):main_text.append(text)
    abstract_words=len(' '.join(abstract).split());main_words=len(' '.join(main_text).split())
    assert abstract_words<=250 and main_words<=4000
    # Preserve the native footnote when replacing the information line.
    note_runs=[copy.deepcopy(x) for x in info if x.findall('w:footnoteReference',NS)]
    replace(info,f'Manuscript counts: abstract {abstract_words} words; main text {main_words} words; 18 references; 2 figures; 1 table. Supplementary tables supplied separately.')
    for x in note_runs:info.append(x)
    assert fields_digest(r)==digest,'Journal preparation altered live Zotero field instructions'
    assert sorted(x.get('{'+W+'}fldCharType') for x in r.findall('.//w:fldChar',NS))==field_marks,'Journal preparation removed field boundary marks'
    parts['word/document.xml']=xmlbytes(r)
    if 'docProps/core.xml' in parts:
        core=etree.fromstring(parts['docProps/core.xml'])
        title=core.find('{http://purl.org/dc/elements/1.1/}title')
        if title is not None:title.text=visible(b.findall('w:p',NS)[0])
        subject=core.find('{http://purl.org/dc/elements/1.1/}subject')
        if subject is not None:subject.text='Prepared for Seizure: European Journal of Epilepsy'
        parts['docProps/core.xml']=xmlbytes(core)
    write_package(DEST,parts)
    highlights=[
      'Type 3 requires measured RTM absent on true counts in the same person and window.',
      'Measurement-only RTM differs from overall RTM and the net measurement difference.',
      'Detector errors alter both enrollment and measured baseline-to-test trajectories.',
      'Within-arm improvement does not establish effects on treatment contrasts or power.'
    ]
    assert 3<=len(highlights)<=5 and max(map(len,highlights))<=85
    create_companion(parts,ROOT/'anatomy_of_RTM_Seizure_Highlights.docx',
        [paragraph('Highlights','Title')]+[paragraph(x,'ListBullet') for x in highlights])
    rows=list(csv.DictReader((OUTPUTS/'condition_summary.csv').open()))
    labels={row['condition']:row['label'] for row in rows}
    paired_rows=[[labels[x['condition']],count(x),count(x,'both_count'),count(x,'type3_count'),count(x,'true_only_count'),count(x,'neither_count')] for x in rows]
    prevalence_rows=[[labels[x['condition']],pct(x,'fraction_type3'),f"{pct(x,'fraction_type3_ci_lo')} to {pct(x,'fraction_type3_ci_hi')}",pct(x,'type3_share_measured_RTM'),num(x,'net_measurement_difference_pp')] for x in rows]
    fixed=[x for x in rows if x['rtm_type']=='baseline' or x['rtm_type'].startswith('type3')]
    fixed_rows=[[labels[x['condition']],count(x,'n_fixed'),pct(x,'fixed_fraction_RTM'),pct(x,'fixed_fraction_type3'),count(x,'fixed_n_zero_baseline'),count(x,'fixed_n_mpc'),num(x,'fixed_MPC')] for x in fixed]
    nodes=[paragraph('Supplementary paired classifications and fixed enrollment results','Title'),
      paragraph('All counts describe synthetic participants from the Anatomy simulation. The four paired categories use each condition\'s enrolled participants and its selected trial windows. Type 3 is the measured-only category. Fixed enrollment retains the perfect-detector participants and their baseline windows. These comparisons do not separate additive causal components.'),
      table(['Condition','Eligible n','Both RTM n','Type 3 n','True only n','Neither n'],paired_rows,[2860,1300,1300,1300,1300,1300]),
      paragraph('Table S1. Paired classifications among all condition-selected participants','Figurecaption'),
      paragraph('The four category counts sum to eligible n in every row. True-count eligibility is not applied as an additional filter.'),
      table(['Condition','Type 3 %','95% Wilson CI','Share of measured RTM %','Net difference pp'],prevalence_rows,[2860,1300,1800,1700,1700]),
      paragraph('Table S2. Type 3 prevalence, share of measured RTM and net measurement difference','Figurecaption'),
      paragraph('The net difference equals measured-only minus true-only prevalence. Confidence intervals describe Monte Carlo precision under the model. Perfect detection has no disagreement by construction; any small positive Wilson upper bound is an interval-formula property.'),
      table(['Condition','Fixed n','RTM %','Type 3 %','Zero B n','MPC n','MPC %'],fixed_rows,[2400,1160,1160,1160,1160,1160,1160]),
      paragraph('Table S3. Fixed perfect-detector enrollment and baseline windows','Figurecaption'),
      paragraph('RTM and Type 3 percentages use all fixed participants. Zero B n counts zero measured baselines. MPC excludes those baselines and uses MPC n. The people and baseline windows are held fixed, so these rows do not represent enrollment using the imperfect detector. RTM, regression to the mean; MPC, median percentage reduction; FAR, false-alarm rate; CI, confidence interval; pp, percentage points.')]
    create_companion(parts,ROOT/'anatomy_of_RTM_Seizure_Supplement.docx',nodes)
    (ROOT/'output/revision_2026-11-12/submission_packaging.json').write_text(json.dumps({
      'source_reviewed_manuscript':str(SOURCE),'manuscript':str(DEST),'abstract_words':abstract_words,'main_words':main_words,
      'figures':2,'tables':1,'references':18,'highlights_characters':list(map(len,highlights)),
      'guide_url':'https://www.sciencedirect.com/journal/seizure-european-journal-of-epilepsy/publish/guide-for-authors',
      'guide_verified':'2026-11-12 via browser after user completed verification',
      'live_field_instructions_sha256_before_Word_refresh':digest},indent=2)+'\n')
    print(DEST,abstract_words,main_words)

if __name__=='__main__':main()
