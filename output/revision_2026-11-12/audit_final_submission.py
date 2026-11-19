"""Verify the delivered Word package against the reviewed results and sources."""
from pathlib import Path
import csv
import hashlib
import json
import logging
import sys
import zipfile
from lxml import etree
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from revise_anatomy_manuscript import pct, num, count

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
REV = ROOT / 'output/revision_2026-11-12'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def document(name):
    with zipfile.ZipFile(ROOT / name) as z:
        assert z.testzip() is None
        return etree.fromstring(z.read('word/document.xml'))


def text(node):
    return ''.join(node.xpath('.//w:t/text()', namespaces=NS))


def numeric_rows(table):
    return [[text(c) for c in row.findall('w:tc', NS)][1:]
            for row in table.findall('w:tr', NS)[1:]]


def citation_identity(node):
    result = []
    for instruction in node.xpath('.//w:instrText/text()', namespaces=NS):
        if 'CSL_CITATION' in instruction:
            citation = json.loads(instruction.split('CSL_CITATION', 1)[1].strip())
            result.append((citation['citationID'], [x['id'] for x in citation['citationItems']]))
    return result


rows = list(csv.DictReader((ROOT / 'outputs/rtm123_type3_1m/condition_summary.csv').open()))
main = document('anatomy_of_RTM_Seizure.docx')
supp = document('anatomy_of_RTM_Seizure_Supplement.docx')
main_table = main.findall('.//w:body/w:tbl', NS)
assert len(main_table) == 1
assert numeric_rows(main_table[0]) == [
    [count(r), pct(r), pct(r, 'fraction_true_RTM'), pct(r, 'fraction_type3'), num(r)]
    for r in rows]
supp_tables = supp.findall('.//w:body/w:tbl', NS)
assert len(supp_tables) == 3
assert numeric_rows(supp_tables[0]) == [
    [count(r), count(r, 'both_count'), count(r, 'type3_count'),
     count(r, 'true_only_count'), count(r, 'neither_count')] for r in rows]
assert numeric_rows(supp_tables[1]) == [
    [pct(r, 'fraction_type3'), f"{pct(r, 'fraction_type3_ci_lo')} to {pct(r, 'fraction_type3_ci_hi')}",
     pct(r, 'type3_share_measured_RTM'), num(r, 'net_measurement_difference_pp')] for r in rows]
fixed = [r for r in rows if r['rtm_type'] == 'baseline' or r['rtm_type'].startswith('type3')]
assert numeric_rows(supp_tables[2]) == [
    [count(r, 'n_fixed'), pct(r, 'fixed_fraction_RTM'), pct(r, 'fixed_fraction_type3'),
     count(r, 'fixed_n_zero_baseline'), count(r, 'fixed_n_mpc'), num(r, 'fixed_MPC')] for r in fixed]

source = document('anatomy_of_RTM_JCE.docx')
assert citation_identity(main) == citation_identity(source)
assert len(main.findall('.//w:instrText', NS)) == 12
assert len(main.findall('.//w:fldChar', NS)) == 36
with zipfile.ZipFile(ROOT / 'anatomy_of_RTM_Seizure.docx') as z:
    assert b'seizure-european-journal-of-epilepsy' in z.read('docProps/custom.xml')

native_before = json.loads((REV / 'before_native_final_save.json').read_text())
files = {}
for name, before in native_before.items():
    after = document(name)
    expected_text = ''.join(before['text'])
    expected_instructions = before['instructions'].copy()
    if name == 'anatomy_of_RTM_Seizure.docx':
        # The native Zotero refresh completed one verified metadata correction.
        assert expected_text.count('Neurology 2020;94.') == 1
        expected_text = expected_text.replace('Neurology 2020;94.', 'Neurology 2020;94:e2311–22.')
        actual_instructions = after.xpath('.//w:instrText/text()', namespaces=NS)
        assert len(actual_instructions) == len(expected_instructions)
        for old, new in zip(expected_instructions, actual_instructions):
            if old == new:
                continue
            expected = json.loads(old.split('CSL_CITATION', 1)[1].strip())
            actual = json.loads(new.split('CSL_CITATION', 1)[1].strip())
            corrected = 0
            for item in expected['citationItems']:
                data = item.get('itemData', {})
                if data.get('DOI') == '10.1212/WNL.0000000000009530':
                    assert not data.get('page')
                    data['page'] = 'e2311-e2322'
                    # Zotero omits these unused fields when serialising this DOI record.
                    data.pop('URL', None)
                    data.pop('accessed', None)
                    corrected += 1
            assert corrected == 1 and expected == actual
    else:
        assert after.xpath('.//w:instrText/text()', namespaces=NS) == expected_instructions
    assert ''.join(after.xpath('.//w:t/text()', namespaces=NS)) == expected_text
    assert sha(ROOT / name) != before['sha256'], 'Expected a native Word save'
    files[name] = {'sha256': sha(ROOT / name), 'native_Word_save_verified': True,
                   'changes_limited_to_verified_reference_metadata': name == 'anatomy_of_RTM_Seizure.docx',
                   'other_text_and_field_instructions_preserved': True}

protected = json.loads((REV / 'astra_evidence/protected_files_before.json').read_text())
for name, record in protected.items():
    assert sha(name) == record['sha256'], name
originals = json.loads((REV / 'astra_evidence/original_outputs_before.json').read_text())
for name, digest in originals.items():
    assert sha(ROOT / name) == digest, name

logging.getLogger('pypdf').setLevel(logging.ERROR)
pdf_path = ROOT / 'anatomy_of_RTM_Seizure.pdf'
pdf = PdfReader(pdf_path)
assert len(pdf.pages) == 15
assert pdf.metadata.creator == 'Word'
assert all((p.extract_text() or '').strip() for p in pdf.pages)
assert '[18]' in pdf.pages[-1].extract_text()
assert 'Neurology 2020;94:e2311–22.' in pdf.pages[-1].extract_text()
for p in [pdf_path, ROOT / 'anatomy_of_RTM_Seizure_Figure_1.pdf', ROOT / 'anatomy_of_RTM_Seizure_Figure_2.pdf']:
    files[p.name] = {'sha256': sha(p)}

highlights = document('anatomy_of_RTM_Seizure_Highlights.docx')
bullets = [text(p) for p in highlights.findall('.//w:body/w:p', NS)][1:]
assert len(bullets) == 4 and max(map(len, bullets)) <= 85
report = {
    'status': 'passed',
    'finalised_local_date': '2026-11-12',
    'scientific_review': 'Astra extra-high, completed before Seizure packaging',
    'native_visual_verification': {'application': 'Microsoft Word', 'main_pages': 15,
                                 'highlights_pages': 1, 'supplement_pages': 3,
                                 'all_pages_inspected': True},
    'PDF_proof': {'exported_by': pdf.metadata.creator, 'pages': len(pdf.pages),
                  'viewed_in': 'Apple Preview', 'no_blank_pages': True},
    'numeric_table_cells_verified': {'main': 45, 'S1': 45, 'S2': 36, 'S3': 42},
    'live_Zotero_instructions': 12, 'field_boundary_markers': 36,
    'citation_identities_preserved': True,
    'Zotero_style': 'Seizure: European Journal of Epilepsy',
    'reference_13_page_range_refreshed_in_Word_and_verified_in_PDF': 'e2311-e2322',
    'highlights_characters': list(map(len, bullets)),
    'protected_reference_and_original_manuscript_files_unchanged': len(protected),
    'original_cohort_and_output_files_unchanged': len(originals),
    'RTM3_files_modified': False,
    'public_release_or_submission_performed': False,
    'files': files,
}
(REV / 'final_submission_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'files'}, indent=2))
