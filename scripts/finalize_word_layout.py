#!/usr/bin/env python3
"""Apply layout corrections to Word-saved submission copies without changing text."""
from pathlib import Path
import copy,hashlib,json,re
from lxml import etree
from revise_anatomy_manuscript import ROOT,W,NS,E,visible,read_package,write_package,xmlbytes,fields_digest,set_figure
from prepare_seizure_submission import props,put


def supplement_layout(body):
    """Keep each supplementary table with its caption and explanatory note."""
    tables=body.findall('w:tbl',NS)
    for i,t in enumerate(tables):
        pr=t.find('w:tblPr',NS)
        put(pr,'tblLayout',type='fixed')
        margins=put(pr,'tblCellMar')
        for edge in ('left','right'):put(margins,edge,w=90,type='dxa')
        if i==1:
            widths=[2600,1100,1800,2100,1760]
            for col,width in zip(t.find('w:tblGrid',NS),widths):col.set('{'+W+'}w',str(width))
            for row in t.findall('w:tr',NS):
                for cell,width in zip(row.findall('w:tc',NS),widths):
                    put(cell.find('w:tcPr',NS),'tcW',w=width,type='dxa')
        if i:
            previous=t.getprevious()
            if previous is None or previous.get('{'+W+'}rsidR')!='A11A0001':
                p=E('p');p.set('{'+W+'}rsidR','A11A0001')
                pp=props(p);put(pp,'pageBreakBefore');put(pp,'spacing',before=0,after=0,line=20,lineRule='exact')
                t.addprevious(p)


def main():
    records=[]
    for filename in ('anatomy_of_RTM_Seizure.docx','anatomy_of_RTM_Seizure_Highlights.docx','anatomy_of_RTM_Seizure_Supplement.docx'):
        path=ROOT/filename;parts=read_package(path);r=etree.fromstring(parts['word/document.xml']);b=r.find('w:body',NS)
        before=fields_digest(r);text_before=r.xpath('.//w:t/text()',namespaces=NS)
        marks_before=[x.get('{'+W+'}fldCharType') for x in r.findall('.//w:fldChar',NS)]
        for p in b.findall('.//w:tbl//w:p',NS):put(props(p),'keepNext')
        for p in b.findall('w:p',NS):
            if visible(p)=='1. Introduction':put(props(p),'pageBreakBefore')
            if not visible(p).strip() and p.findall('.//w:fldChar',NS):
                pr=props(p);put(pr,'spacing',before=0,after=0,line=20,lineRule='exact');put(pr,'keepNext',val=0)
                rr=pr.find('w:rPr',NS)
                if rr is None:rr=E('rPr');pr.append(rr)
                put(rr,'sz',val=2)
                for run in p.findall('w:r',NS):
                    rp=run.find('w:rPr',NS)
                    if rp is None:rp=E('rPr');run.insert(0,rp)
                    put(rp,'sz',val=2)
        for rr in r.findall('.//w:r',NS):
            if rr.find('w:footnoteReference',NS) is not None:
                pr=rr.find('w:rPr',NS)
                if pr is None:pr=E('rPr');rr.insert(0,pr)
                put(pr,'vertAlign',val='superscript');put(pr,'sz',val=18)
        if filename=='anatomy_of_RTM_Seizure.docx':
            set_figure(parts,r,2,ROOT/'output/seizure_figures/Figure_2.png',6.5)
        if filename=='anatomy_of_RTM_Seizure_Supplement.docx':supplement_layout(b)
        for name in list(parts):
            if re.fullmatch(r'word/header\d+\.xml',name):
                h=etree.fromstring(parts[name])
                for rr in h.findall('.//w:r',NS):
                    pr=rr.find('w:rPr',NS)
                    if pr is None:pr=E('rPr');rr.insert(0,pr)
                    color=put(pr,'color',val='000000');color.attrib.pop('{'+W+'}themeColor',None)
                parts[name]=xmlbytes(h)
        assert fields_digest(r)==before
        assert r.xpath('.//w:t/text()',namespaces=NS)==text_before
        assert [x.get('{'+W+'}fldCharType') for x in r.findall('.//w:fldChar',NS)]==marks_before
        parts['word/document.xml']=xmlbytes(r);write_package(path,parts)
        records.append({'path':str(path),'unchanged_text_and_field_instructions':True,'sha256_after_layout_patch':hashlib.sha256(path.read_bytes()).hexdigest()})
    (ROOT/'output/revision_2026-11-12/layout_corrections.json').write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(records,indent=2))

if __name__=='__main__':main()
