from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import hashlib,json,subprocess
root=Path('/Users/dgoldenh/Documents/GitHub/anatomy_of_RTM'); out=root/'output/critical_review_2026-11-12/astra'
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
manifest={}
for name in ['anatomy_of_RTM_Seizure.docx','anatomy_of_RTM_Seizure_Supplement.docx']:
 p=root/name; stem=p.stem; manifest[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size,'mtime':p.stat().st_mtime}
 with ZipFile(p) as z:
  doc=E.fromstring(z.read('word/document.xml')); lines=[]; equations=[]; fields=[]
  for i,para in enumerate(doc.xpath('//w:body//w:p',namespaces=ns),1):
   text=''.join(para.xpath('.//w:t/text() | .//m:t/text()',namespaces=ns))
   if text:lines.append(f'P{i:03}: {text}')
   for eq in para.xpath('.//m:oMath',namespaces=ns): equations.append({'paragraph':i,'text':''.join(eq.xpath('.//m:t/text()',namespaces=ns)),'xml':E.tostring(eq,encoding='unicode')})
   instr=para.xpath('.//w:instrText/text()',namespaces=ns)
   if instr: fields.append({'paragraph':i,'instructions':instr,'visible_text':text})
  tables=[]
  for i,t in enumerate(doc.xpath('//w:tbl',namespaces=ns),1):
   rows=[]
   for row in t.xpath('./w:tr',namespaces=ns): rows.append([' | '.join(''.join(p.xpath('.//w:t/text() | .//m:t/text()',namespaces=ns)) for p in c.xpath('.//w:p',namespaces=ns)) for c in row.xpath('./w:tc',namespaces=ns)])
   tables.append({'table':i,'rows':rows})
  (out/f'{stem}.txt').write_text('\n'.join(lines)+'\n')
  (out/f'{stem}_structure.json').write_text(json.dumps({'tables':tables,'equations':equations,'fields':fields,'tracked_insertions':len(doc.xpath('//w:ins',namespaces=ns)),'tracked_deletions':len(doc.xpath('//w:del',namespaces=ns))},indent=2))
  for n in z.namelist():
   if n.startswith('word/media/'):
    (out/f'{stem}_{Path(n).name}').write_bytes(z.read(n))
  (out/f'{stem}_document.xml').write_bytes(z.read('word/document.xml'))
(out/'source_snapshot.json').write_text(json.dumps(manifest,indent=2))
(out/'git_status_initial.txt').write_text(subprocess.check_output(['git','status','--short'],cwd=root,text=True))
print(json.dumps(manifest,indent=2))
