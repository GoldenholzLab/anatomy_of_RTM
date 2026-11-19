#!/usr/bin/env python3
"""Rebuild the RTM manuscript for Journal of Clinical Epidemiology.

The script deliberately starts from the Word file that contains the authors'
genuine Zotero fields. Citation and bibliography XML are copied intact into a
newly structured manuscript; Zotero in Word is then used to select the JCE
style and refresh the field results.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "anatomy_of_RTM_JCE.docx"
OUTPUT = ROOT / "anatomy_of_RTM_JCE.docx"
HIGHLIGHTS = ROOT / "anatomy_of_RTM_JCE_Highlights.docx"
FIG1_PNG = ROOT / "outputs/rtm123_1m/rtm123_Fig1.png"
FIG2_PNG = ROOT / "outputs/rtm123_1m/rtm123_Fig2.png"
FIG1_PDF_SOURCE = ROOT / "outputs/rtm123_1m/rtm123_explainer.pdf"
FIG2_PDF_SOURCE = ROOT / "outputs/rtm123_1m/rtm123_summary.pdf"
FIG1_PDF = ROOT / "anatomy_of_RTM_JCE_Figure_1.pdf"
FIG2_PDF = ROOT / "anatomy_of_RTM_JCE_Figure_2.pdf"

TITLE = (
    "Three sources of regression to the mean in clinical trials: "
    "a simulation study using epilepsy as a model"
)
SHORT_TITLE = "Regression to the mean in clinical trials"
KEYWORDS = (
    "regression to the mean; clinical trials; simulation; eligibility; "
    "measurement error; placebo response; epilepsy"
)

HIGHLIGHT_BULLETS = [
    "Transient worsening, eligibility selection, and measurement error all created RTM.",
    "Each mechanism produced apparent improvement without any treatment effect.",
    "A single cohort isolated mechanisms often conflated as placebo response.",
    "Trialists should simulate eligibility rules before finalizing protocols.",
    "Measurement sensitivity and false alarms should be prespecified in endpoints.",
]

PMID_BY_DOI = {
    "10.1111/epi.17730": "37505116",
    "10.1002/sim.4780020401": "6369471",
    "10.1111/j.1365-2753.2004.00505.x": "15660538",
    "10.1016/j.eplepsyres.2016.02.002": "26921852",
    "10.1002/ana.24470": "26150090",
    "10.1016/j.seizure.2017.10.016": "29102709",
    "10.1016/j.eplepsyres.2020.106306": "32172145",
    "10.1111/epi.17471": "36401798",
    "10.1016/j.yebeh.2012.04.128": "22652423",
    "10.1016/j.clinph.2020.12.009": "33678577",
    "10.1111/epi.17297": "35545836",
    "10.1111/epi.17917": "38366862",
    "10.1212/WNL.0000000000009530": "32409485",
    "10.1016/S1474-4422(19)30399-0": "31734103",
    "10.1016/j.yebeh.2014.12.004": "25703333",
    "10.1056/NEJMoa1103319": "21751905",
    "10.1136/bmj.m1668": "32690477",
    "10.1136/bmj.38726.603310.55": "16452103",
}

ABSTRACT_PARTS = {
    "Background": (
        "Regression to the mean (RTM) can create apparent improvement whenever a trial "
        "selects participants during a high baseline period and evaluates change from "
        "that baseline. Distinct sources of RTM are often conflated. We used epilepsy as "
        "a worked clinical model to isolate transient state worsening, selection on "
        "outcome variability, and measurement error."
    ),
    "Methods": (
        "We simulated 1,000,000 patients with 36 months of daily seizure counts. A "
        "trial-like design selected each patient's first eligible 2-month baseline and "
        "evaluated the following 3 months, with no treatment effect. Using one fixed "
        "underlying cohort, we separately introduced a transient 2-month rate change, "
        "raised the eligibility threshold from 4 to 8 seizures/month, reduced measurement "
        "sensitivity from 100% to 70%, or added false alarms up to 1/day. Outcomes were "
        "eligibility yield, the proportion meeting a prespecified RTM definition, and "
        "median percentage change (MPC) from baseline."
    ),
    "Results": (
        "In the reference condition, 64.9% were eligible, 53.9% met the RTM definition, "
        "and MPC was 26.7%. Transient worsening increased these values to 75.6%, 58.4%, "
        "and 36.8%; when it overlapped the selected baseline, RTM was 95.1% and MPC was "
        "92.6%. Raising the threshold reduced eligibility to 40.4% but increased RTM to "
        "58.0% and MPC to 29.4%. Sensitivity of 70% yielded 55.2% eligibility, 59.1% RTM, "
        "and 33.3% MPC. One false alarm/day yielded 98.5% eligibility, 64.4% RTM, and "
        "46.0% MPC."
    ),
    "Discussion": (
        "Different clinical, design, and measurement mechanisms produced the same "
        "trial-facing appearance of improvement without treatment. The quantitative "
        "estimates are model-specific, but the structural lesson applies to trials that "
        "select high baselines from fluctuating, imperfectly measured outcomes. "
        "Eligibility rules and measurement performance should be simulated jointly and "
        "tested in prespecified sensitivity analyses."
    ),
}


def set_cell_margins(cell, top=80, start=100, bottom=80, end=100):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_run_font(run, size=12, bold=None, italic=None, color=None, superscript=None):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    if superscript is not None:
        run.font.superscript = superscript
    return run


def configure_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.font.size = Pt(12)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.widow_control = True

    for name, size, bold, italic in (
        ("Title", 14, True, False),
        ("Heading 1", 12, True, False),
        ("Heading 2", 12, True, True),
        ("Heading 3", 12, False, True),
    ):
        style = doc.styles[name]
        style.font.name = "Times New Roman"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.bold = bold
        style.font.italic = italic
        style.paragraph_format.space_before = Pt(12 if name != "Title" else 0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.alignment = (
            WD_ALIGN_PARAGRAPH.CENTER if name == "Title" else WD_ALIGN_PARAGRAPH.LEFT
        )
        # Remove decorative borders inherited from the source journal template.
        ppr = style._element.get_or_add_pPr()
        border = ppr.find(qn("w:pBdr"))
        if border is not None:
            ppr.remove(border)

    if "Abstract" not in [s.name for s in doc.styles]:
        style = doc.styles.add_style("Abstract", WD_STYLE_TYPE.PARAGRAPH)
    else:
        style = doc.styles["Abstract"]
    style.font.name = "Times New Roman"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(12)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    style.paragraph_format.space_after = Pt(0)

    if "Figure caption" not in [s.name for s in doc.styles]:
        style = doc.styles.add_style("Figure caption", WD_STYLE_TYPE.PARAGRAPH)
    else:
        style = doc.styles["Figure caption"]
    style.font.name = "Times New Roman"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(11)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    style.paragraph_format.line_spacing = 1.0
    style.paragraph_format.space_after = Pt(6)


def clear_document_body(doc: Document) -> None:
    body = doc._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def extract_citation_fields(doc: Document) -> dict[str, list]:
    fields: dict[str, list] = {}
    for para in doc.paragraphs:
        children = list(para._p)
        i = 0
        while i < len(children):
            child = children[i]
            begin = child.find(".//" + qn("w:fldChar"))
            if begin is None or begin.get(qn("w:fldCharType")) != "begin":
                i += 1
                continue
            group = [child]
            j = i + 1
            while j < len(children):
                group.append(children[j])
                ends = children[j].findall(".//" + qn("w:fldChar"))
                if any(e.get(qn("w:fldCharType")) == "end" for e in ends):
                    break
                j += 1
            instr = "".join(
                n.text or "" for el in group for n in el.findall(".//" + qn("w:instrText"))
            )
            if "ZOTERO_ITEM CSL_CITATION" in instr:
                match = re.search(r"CSL_CITATION\s+(\{.*\})\s*$", instr)
                if not match:
                    raise RuntimeError(f"Could not parse Zotero citation field: {instr[:120]}")
                data = json.loads(match.group(1))
                citation_id = data.get("citationID")
                if not citation_id:
                    raise RuntimeError("Zotero citation lacks citationID")
                fields[citation_id] = [copy.deepcopy(el) for el in group]
            i = j + 1
    return fields


def extract_bibliography_paragraphs(doc: Document) -> list:
    paras = doc.paragraphs
    start = None
    end = None
    seen = False
    for i, para in enumerate(paras):
        xml = para._p.xml
        if start is None and "ZOTERO_BIBL" in xml:
            start = i
            seen = True
        if seen and 'w:fldCharType="end"' in xml:
            end = i
            break
    if start is None or end is None:
        raise RuntimeError("Could not locate the live Zotero bibliography field")
    return [copy.deepcopy(paras[i]._p) for i in range(start, end + 1)]


def apply_verified_reference_correction(citations: dict[str, list], bibliography: list) -> None:
    """Supply PubMed-verified pagination missing from one Crossref Zotero record.

    The live Zotero record DIWJJPUR was imported from Crossref without its electronic
    page range. PubMed 32409485 reports Neurology 94(22):e2311-e2322. The embedded
    Zotero item data and current bibliography result are corrected here so the
    submission copy is complete while preserving the live field structures.
    """
    field = citations["rtm123_1_13_14"]
    instr_nodes = [
        node for element in field for node in element.findall(".//" + qn("w:instrText"))
    ]
    instr = "".join(node.text or "" for node in instr_nodes)
    match = re.search(r"CSL_CITATION\s+(\{.*\})\s*$", instr)
    if not match:
        raise RuntimeError("Could not parse the cenobamate Zotero citation field")
    data = json.loads(match.group(1))
    changed = False
    for item in data.get("citationItems", []):
        if any(uri.endswith("/DIWJJPUR") for uri in item.get("uris", [])):
            item_data = item.setdefault("itemData", {})
            item_data["page"] = "e2311-e2322"
            item_data["PMID"] = "32409485"
            changed = True
    if not changed:
        raise RuntimeError("Could not locate Zotero item DIWJJPUR in the grouped citation")
    instr_nodes[0].text = " ADDIN ZOTERO_ITEM CSL_CITATION " + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + " "
    for node in instr_nodes[1:]:
        node.text = ""

    replacement = (
        "[13]\tChung SS, French JA, Kowalski J, Krauss GL, Lee SK, Maciejowski M, et al. "
        "Randomized phase 2 study of adjunctive cenobamate in patients with uncontrolled "
        "focal seizures. Neurology 2020;94:e2311–22. "
        "https://doi.org/10.1212/WNL.0000000000009530."
    )
    for para_xml in bibliography:
        text_nodes = para_xml.findall(".//" + qn("w:t"))
        para_text = "".join(node.text or "" for node in text_nodes)
        if para_text.startswith("[13]"):
            text_nodes[0].text = replacement
            for node in text_nodes[1:]:
                node.text = ""
            return
    raise RuntimeError("Could not locate bibliography entry 13")


def embed_verified_pmids(citations: dict[str, list]) -> None:
    """Embed the PubMed verification map in every live citation field occurrence."""
    for field in citations.values():
        instr_nodes = [
            node for element in field for node in element.findall(".//" + qn("w:instrText"))
        ]
        instr = "".join(node.text or "" for node in instr_nodes)
        match = re.search(r"CSL_CITATION\s+(\{.*\})\s*$", instr)
        if not match:
            raise RuntimeError("Could not parse a Zotero citation while embedding PMIDs")
        data = json.loads(match.group(1))
        for item in data.get("citationItems", []):
            item_data = item.setdefault("itemData", {})
            doi = item_data.get("DOI")
            if doi in PMID_BY_DOI:
                item_data["PMID"] = PMID_BY_DOI[doi]
        instr_nodes[0].text = " ADDIN ZOTERO_ITEM CSL_CITATION " + json.dumps(
            data, ensure_ascii=False, separators=(",", ":")
        ) + " "
        for node in instr_nodes[1:]:
            node.text = ""


def add_text_paragraph(doc: Document, text: str = "", style=None, first_line=True):
    p = doc.add_paragraph(style=style)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if text:
        set_run_font(p.add_run(text))
    if first_line and style in (None, "Normal"):
        p.paragraph_format.first_line_indent = Inches(0.3)
    return p


def add_labelled_paragraph(doc: Document, label: str, text: str, style=None):
    p = doc.add_paragraph(style=style)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_run_font(p.add_run(label), bold=True)
    set_run_font(p.add_run(text))
    return p


def append_field(p, field_elements: list) -> None:
    for element in field_elements:
        p._p.append(copy.deepcopy(element))


def add_cited_paragraph(doc: Document, parts, citations: dict[str, list]):
    """Add a paragraph from strings and ('cite', citation_id) markers."""
    p = doc.add_paragraph(style="Normal")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.first_line_indent = Inches(0.3)
    for part in parts:
        if isinstance(part, tuple) and part[0] == "cite":
            append_field(p, citations[part[1]])
        else:
            set_run_font(p.add_run(str(part)))
    return p


def add_heading(doc: Document, text: str, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_run_font(p.add_run(text), bold=True, italic=(level == 2))
    return p


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_separate = OxmlElement("w:fldChar")
    fld_separate.set(qn("w:fldCharType"), "separate")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_begin, instr, fld_separate, fld_end])
    set_run_font(run, size=10)


def configure_page(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.4)
    section.footer_distance = Inches(0.4)
    header = section.header
    header.is_linked_to_previous = False
    hp = header.paragraphs[0]
    hp.clear()
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(hp.add_run(SHORT_TITLE), size=10, italic=True)
    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.clear()
    add_page_number(fp)


def add_title_page(doc: Document, abstract_count: int, main_count: int) -> None:
    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run(TITLE), size=14, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run("Original Research"), bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    authors = [
        ("Daniel M. Goldenholz, MD, PhD", "a,b"),
        ("Rohan Bhansali, BS", "a,b"),
        ("Ted J. Kaptchuk, PhD", "b,c"),
        ("Brandon Westover, MD, PhD", "b,d"),
    ]
    for i, (name, aff) in enumerate(authors):
        set_run_font(p.add_run(name))
        set_run_font(p.add_run(aff), size=9, superscript=True)
        if i < len(authors) - 1:
            set_run_font(p.add_run("; "))

    affiliations = [
        ("a", "Department of Neurology, Beth Israel Deaconess Medical Center, Boston, MA, USA"),
        ("b", "Harvard Medical School, Boston, MA, USA"),
        ("c", "Program in Placebo Studies, Beth Israel Deaconess Medical Center, Boston, MA, USA"),
        ("d", "Department of Neurology, Stanford University, Stanford, CA, USA"),
    ]
    for letter, text in affiliations:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_run_font(p.add_run(letter), size=9, superscript=True)
        set_run_font(p.add_run(f" {text}"), size=10)

    add_labelled_paragraph(doc, "Corresponding author: ", (
        "Daniel M. Goldenholz, MD, PhD, Department of Neurology, Beth Israel Deaconess "
        "Medical Center, 330 Brookline Avenue, Baker 5, Boston, MA 02215, USA; "
        "tel: +1 617 632 8930; daniel.goldenholz@bidmc.harvard.edu"
    ))
    add_labelled_paragraph(doc, "Running title: ", SHORT_TITLE)
    add_labelled_paragraph(doc, "Keywords: ", KEYWORDS)
    add_labelled_paragraph(
        doc,
        "Manuscript counts: ",
        f"abstract {abstract_count} words; main text {main_count} words; 18 references; "
        "2 figures; 0 tables.",
    )
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def add_what_is_new(doc: Document) -> None:
    add_heading(doc, "What is new?", 1)
    table = doc.add_table(rows=3, cols=1)
    table.autofit = True
    labels = [
        ("Key findings", HIGHLIGHT_BULLETS[:2]),
        ("What this adds", HIGHLIGHT_BULLETS[2:3]),
        ("Implications", HIGHLIGHT_BULLETS[3:]),
    ]
    for row, (label, bullets) in zip(table.rows, labels):
        cell = row.cells[0]
        set_cell_margins(cell)
        cell.vertical_alignment = None
        p = cell.paragraphs[0]
        set_run_font(p.add_run(label), bold=True)
        for bullet in bullets:
            p = cell.add_paragraph(style="List Bullet")
            set_run_font(p.add_run(bullet))


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text))


def build() -> None:
    src = Document(SOURCE)
    citations = extract_citation_fields(src)
    bibliography = extract_bibliography_paragraphs(src)
    apply_verified_reference_correction(citations, bibliography)
    embed_verified_pmids(citations)
    required_ids = {
        "rtm123_1_7", "rtm123_1_3", "rtm123_8_12", "rtm123_8",
        "rtm123_1_13_14", "nihbfJoj", "rQg4ZKFn", "rtm123_9_12",
        "rtm123_4_15", "XmxyCI8b", "SzQszBmA",
    }
    missing = required_ids - citations.keys()
    if missing:
        raise RuntimeError(f"Missing required citation fields: {sorted(missing)}")

    doc = src
    clear_document_body(doc)
    configure_styles(doc)
    configure_page(doc)

    main_text_blocks = [
        "Introduction",
        "Regression to the mean (RTM) is a general threat to clinical-trial interpretation when participants are selected during unusually high baseline values and outcomes are defined as change from that baseline. The design is common in disorders with fluctuating symptoms or events, where apparent improvement may occur even without treatment.",
        "RTM describes the tendency for an extreme observation to be followed by a value closer to the long-run mean. Although the label is often treated as one phenomenon, the observed pattern can arise from different clinical, selection, and measurement processes.",
        "We distinguish three operational sources. Type 1 is transient state worsening: a temporary clinical perturbation elevates the baseline and later resolves. Type 2 is selection on natural variability: an eligibility rule preferentially captures high points in a stable but fluctuating series. Type 3 is measurement error: imperfect sensitivity or false-positive observations change the series used for eligibility and outcome assessment. These sources can coexist and can be mistaken for a psychological placebo effect.",
        "Previous seizure-trial simulations quantified eligibility-related RTM. The present study extends that work by holding one underlying cohort fixed and changing one state, eligibility, or measurement feature at a time. Epilepsy provides a demanding worked model because events fluctuate, entry thresholds are explicit, and measurement is increasingly device-assisted. Our objective was to determine whether the three sources could each create trial-facing improvement without treatment and to derive design lessons that transfer to other trials with fluctuating, imperfectly measured outcomes.",
        "Methods", "Simulation cohort", "Trial design and eligibility", "Operational RTM mechanisms", "Outcomes and reporting",
        "Results", "Reference condition", "Transient-state mechanism", "Selection mechanism", "Measurement mechanism",
        "Discussion", "Interpretation", "Trial-design implications", "Relevance beyond epilepsy", "Strengths and limitations", "Conclusion",
    ]
    main_count = count_words(" ".join(main_text_blocks)) + 1450  # replaced after body is built
    abstract_count = count_words(" ".join(ABSTRACT_PARTS.values()))
    add_title_page(doc, abstract_count, main_count)

    add_heading(doc, "Abstract", 1)
    for label in ("Background", "Methods", "Results", "Discussion"):
        add_labelled_paragraph(doc, f"{label}: ", ABSTRACT_PARTS[label], style="Abstract")
    add_labelled_paragraph(doc, "Keywords: ", KEYWORDS)
    add_what_is_new(doc)

    add_heading(doc, "1. Introduction", 1)
    add_cited_paragraph(doc, [
        "Regression to the mean (RTM) is a general threat to clinical-trial interpretation "
        "when participants are selected during unusually high baseline values and outcomes "
        "are defined as change from that baseline. The design is common in disorders with "
        "fluctuating symptoms or events, where apparent improvement may occur even without "
        "treatment ", ("cite", "rtm123_1_7"), "."
    ], citations)
    add_cited_paragraph(doc, [
        "RTM describes the tendency for an extreme observation to be followed by a value "
        "closer to the long-run mean ", ("cite", "rtm123_1_3"), ". Although the label is "
        "often treated as one phenomenon, the observed pattern can arise from different "
        "clinical, selection, and measurement processes."
    ], citations)
    add_cited_paragraph(doc, [
        "We distinguish three operational sources (Figure 1). Type 1 is transient state worsening: a "
        "temporary clinical perturbation elevates the baseline and later resolves. Type 2 "
        "is selection on natural variability: an eligibility rule preferentially captures "
        "high points in a stable but fluctuating series. Type 3 is measurement error: "
        "imperfect sensitivity or false-positive observations change the series used for "
        "eligibility and outcome assessment ", ("cite", "rtm123_8_12"), ". These sources "
        "can coexist and can be mistaken for a psychological placebo effect."
    ], citations)
    add_text_paragraph(doc, (
        "Previous seizure-trial simulations quantified eligibility-related RTM. The present "
        "study extends that work by holding one underlying cohort fixed and changing one "
        "state, eligibility, or measurement feature at a time. Epilepsy provides a demanding "
        "worked model because events fluctuate, entry thresholds are explicit, and measurement "
        "is increasingly device-assisted. Our objective was to determine whether the three "
        "sources could each create trial-facing improvement without treatment and to derive "
        "design lessons that transfer to other trials with fluctuating, imperfectly measured outcomes."
    ))

    add_heading(doc, "2. Methods", 1)
    add_heading(doc, "2.1. Simulation cohort", 2)
    add_cited_paragraph(doc, [
        "We generated 1,000,000 synthetic patients with CHOCOLATES, an open-source simulator "
        "designed to reproduce major statistical features of seizure diaries, including "
        "heterogeneous long-term rates, clustering, cycles, and the association between "
        "frequency and variability ", ("cite", "rtm123_8"), ". Each patient had 36 months "
        "of daily event counts. The same latent cohort and patient-specific random seeds were "
        "used for every condition so that changes in output were attributable to the designated transform."
    ], citations)

    add_heading(doc, "2.2. Trial design and eligibility", 2)
    add_cited_paragraph(doc, [
        "Eligibility was assessed in rolling 2-month baseline windows beginning at month 0 "
        "and ending at month 31, leaving three subsequent test months. We used the first "
        "eligible window. The reference eligibility rule reflected focal-epilepsy trials: "
        "mean baseline frequency of at least 4 events/month, at least 3 events in each "
        "baseline month, and no baseline event-free interval longer than 25 days ",
        ("cite", "rtm123_1_13_14"), ". Patients with no eligible window were excluded from "
        "RTM and percentage-change summaries but remained in eligibility-yield denominators."
    ], citations)
    add_text_paragraph(doc, (
        "Eligibility and RTM reference rates were recalculated after each condition transform, "
        "so each analysis used the diary that would have been available under that condition. "
        "The baseline period and test period were therefore analyzed as a trial would observe them, "
        "rather than by conditioning on eligibility from the untransformed reference series."
    ))

    add_heading(doc, "2.3. Operational RTM mechanisms", 2)
    add_cited_paragraph(doc, [
        "The reference condition used perfect measurement (100% sensitivity and zero false "
        "alarms). For type 1 RTM, one random consecutive 2-month interval per patient was "
        "replaced by a newly simulated segment with a newly sampled mean event rate; the "
        "original rate then resumed. This represented a temporary perturbation such as an "
        "intercurrent illness. For type 2 RTM, only the mean-frequency eligibility threshold "
        "changed, from 4 to 8 events/month. For type 3 RTM, we separately reduced sensitivity "
        "to 90%, 80%, and 70% with zero false alarms and added false alarms at 1/month, 1/week, "
        "and 1/day with 100% sensitivity. Expected false alarms were subtracted in the "
        "false-alarm eligibility and percentage-change analyses ", ("cite", "nihbfJoj"), "."
    ], citations)

    add_heading(doc, "2.4. Outcomes and reporting", 2)
    add_cited_paragraph(doc, [
        "There was no active treatment effect. RTM was counted when the baseline rate exceeded "
        "the patient's observed 36-month reference rate and the test-period rate moved closer "
        "to that reference than the baseline rate ", ("cite", "rQg4ZKFn"), ". We summarized "
        "trial-facing improvement as median percentage change (MPC) from baseline to test and "
        "also reported eligibility yield. No hypothesis tests were performed because the "
        "analysis was a descriptive simulation rather than a randomized comparison."
    ], citations)
    add_text_paragraph(doc, (
        "No reporting guideline specific to this descriptive, event-count simulation was "
        "identified in the EQUATOR Network catalogue; we therefore report the cohort-generating "
        "process, transforms, eligibility rule, outcomes, computational scale, and open code "
        "needed for reproduction. The analysis was not preregistered because it was descriptive "
        "and noninferential. It used no human participants, human specimens, or identifiable data."
    ))

    add_heading(doc, "3. Results", 1)
    add_heading(doc, "3.1. Reference condition", 2)
    add_text_paragraph(doc, (
        "With perfect measurement and a 4-event/month threshold, 649,098 of 1,000,000 patients "
        "(64.9%) became eligible. Among eligible patients, 53.9% met the RTM definition and MPC "
        "was 26.7% (Figure 2). Thus, the reference baseline-versus-test design produced substantial "
        "apparent improvement despite the absence of treatment."
    ))

    add_heading(doc, "3.2. Transient-state mechanism", 2)
    add_text_paragraph(doc, (
        "After a temporary 2-month change in the underlying rate, eligibility increased to 75.6%, "
        "RTM to 58.4%, and MPC to 36.8%. Location of the perturbation was decisive. When the "
        "transient interval overlapped the selected baseline, RTM was 95.1% and MPC was 92.6%; "
        "when it overlapped neither baseline nor test, RTM was 51.1% and MPC was 25.9%. A temporary "
        "clinical state can therefore enter the analysis through both who becomes eligible and "
        "which interval is chosen as baseline."
    ))

    add_heading(doc, "3.3. Selection mechanism", 2)
    add_text_paragraph(doc, (
        "Changing only the frequency threshold from 4 to 8 events/month reduced eligibility to "
        "40.4% but selected more extreme baseline periods. RTM increased from 53.9% to 58.0%, and "
        "MPC increased from 26.7% to 29.4%. The apparent response therefore changed even though "
        "the underlying cohort, measurement, and absence of treatment were unchanged."
    ))

    add_heading(doc, "3.4. Measurement mechanism", 2)
    add_text_paragraph(doc, (
        "With false alarms fixed at zero, reducing sensitivity from 100% to 70% reduced eligibility "
        "from 64.9% to 55.2%, increased RTM from 53.9% to 59.1%, and increased MPC from 26.7% to "
        "33.3%. With sensitivity fixed at 100%, increasing false alarms from zero to 1/day increased "
        "eligibility to 98.5%, RTM to 64.4%, and MPC to 46.0%, despite subtraction of expected false "
        "alarms. Measurement performance therefore changed both trial entry and the observed endpoint."
    ))

    add_heading(doc, "4. Discussion", 1)
    add_heading(doc, "4.1. Interpretation", 2)
    add_text_paragraph(doc, (
        "This fixed-cohort simulation shows that RTM is not a single mechanism. Temporary worsening, "
        "selection on natural variability, and measurement error each made the selected baseline look "
        "worse than the later test period. All produced the same trial-facing result—apparent improvement "
        "without treatment—but they imply different remedies. State-related RTM calls for attention to "
        "recent perturbations; selection-related RTM calls for explicit evaluation of eligibility rules; "
        "measurement-related RTM calls for joint validation of detection and endpoint algorithms."
    ))
    add_cited_paragraph(doc, [
        "The measurement mechanism is increasingly important as trials adopt device-derived endpoints. "
        "Automated detection may reduce under-reporting, but sensitivity, false-alarm rate, and correction "
        "rules become components of both eligibility and outcome definition ", ("cite", "rtm123_9_12"), ". "
        "A detector cannot be evaluated only by event-level performance if its errors alter which patients "
        "enter a trial or the baseline against which change is calculated."
    ], citations)
    add_cited_paragraph(doc, [
        "These findings also argue against interpreting every placebo-arm change as a unitary psychological "
        "placebo effect. The simulation included no expectation, therapeutic ritual, or active intervention; "
        "the response arose from selection and measurement. Psychological and contextual effects may still "
        "operate in real trials ", ("cite", "rtm123_4_15"), ". Experimental evidence suggests that objective "
        "outcomes can be dominated by RTM ", ("cite", "XmxyCI8b"), ", whereas subjective reports may include "
        "additional neuropsychological processes ", ("cite", "SzQszBmA"), ". Trial analyses should therefore "
        "separate plausible structural sources before assigning biological or behavioral meaning to improvement."
    ], citations)

    add_heading(doc, "4.2. Trial-design implications", 2)
    add_text_paragraph(doc, (
        "Eligibility and measurement should be simulated jointly before a protocol is finalized. At minimum, "
        "design evaluations should vary the entry threshold, baseline duration, within-person variability, "
        "measurement sensitivity, false-positive rate, missingness, and any error-correction rule. Protocols "
        "should prespecify how these features enter both eligibility and endpoint computation. Sensitivity "
        "analyses should distinguish assumptions about the latent clinical process from assumptions about its measurement."
    ))

    add_heading(doc, "4.3. Relevance beyond epilepsy", 2)
    add_text_paragraph(doc, (
        "The numerical estimates are specific to the seizure-diary model and should not be transported directly "
        "to other diseases. The structural logic is broader: any trial that requires an unusually high baseline "
        "value from a fluctuating outcome and then measures change from that value can admit the same three sources "
        "of RTM. Examples may include recurrent event counts, symptom scores, home physiologic measurements, and "
        "digital biomarkers. Application to a new setting requires a disease- and instrument-specific generative model, "
        "not simple reuse of the present effect sizes."
    ))

    add_heading(doc, "4.4. Strengths and limitations", 2)
    add_text_paragraph(doc, (
        "The principal strength is controlled isolation: one large underlying cohort was reused across conditions, "
        "so each transform had a clear operational interpretation. The open code, deterministic seeds, and explicit "
        "eligibility algorithm support reproduction. Several limitations qualify the results. CHOCOLATES is realistic "
        "but synthetic. The transient rate change was a simplified perturbation rather than a data-derived illness model. "
        "Sensitivity and false alarms were uniform across patients and time, while actual devices vary by person, event "
        "type, state, and adherence. False-alarm correction was idealized. The study quantified within-arm apparent "
        "improvement, not bias in a randomized treatment contrast; randomization may balance some sources between arms, "
        "but it does not make placebo-arm trajectories or eligibility yield mechanistically interpretable."
    ))

    add_heading(doc, "5. Conclusion", 1)
    add_text_paragraph(doc, (
        "Transient clinical worsening, selection on natural variability, and measurement error can each generate "
        "substantial apparent improvement in a trial with no treatment effect. Although epilepsy supplied the worked "
        "model, the design problem extends to fluctuating, imperfectly measured outcomes selected at high baseline. "
        "Simulating eligibility and measurement together can make RTM explicit before it is mislabeled as treatment-independent response."
    ))

    add_heading(doc, "Funding", 1)
    add_text_paragraph(doc, (
        "Daniel M. Goldenholz was supported by the National Institutes of Health (K23NS124656 and "
        "1R21NS142800) and the American Board of Psychiatry and Neurology. Rohan Bhansali was supported "
        "by National Institutes of Health grant K23NS124656. [AUTHOR CONFIRMATION REQUIRED: Please state "
        "the role of the funders in study design, data generation, analysis, interpretation, writing, and "
        "the decision to submit.]"
    ), first_line=False)

    add_heading(doc, "Competing interests", 1)
    add_text_paragraph(doc, (
        "Daniel M. Goldenholz has received speaker fees from Harvard Medical School, the American Academy "
        "of Neurology, the American Epilepsy Society, the American Clinical Neurophysiology Society, the "
        "National Neurotrauma Society, AI in Epilepsy and Neurology, Florida Epilepsy Alliance, and the "
        "University of Texas at Austin. He previously served as a paid consultant for Neuro Event Labs, "
        "IDR, LivaNova, Health Advances, Duke University, Bloom Insights, and Wiley. He has received grants "
        "from the National Institutes of Health, the American Board of Psychiatry and Neurology, Beth Israel "
        "Deaconess Medical Center, and the Lions Club. Rohan Bhansali, Ted J. Kaptchuk, and Brandon Westover "
        "declare no competing interests."
    ), first_line=False)

    add_heading(doc, "Ethics statement", 1)
    add_text_paragraph(doc, (
        "This computational study used only synthetic patients and no human participants, human specimens, "
        "or identifiable health data; institutional review board approval and informed consent were therefore not applicable."
    ), first_line=False)

    add_heading(doc, "Data and code availability", 1)
    add_text_paragraph(doc, (
        "Source code and instructions are available at https://github.com/GoldenholzLab/anatomy_of_RTM. "
        "The simulation uses the open-source CHOCOLATES package, available at "
        "https://github.com/GoldenholzLab/CHOCOLATES. The synthetic outputs can be regenerated from the "
        "repository code and documented seeds; no human participant data were used."
    ), first_line=False)

    add_heading(doc, "CRediT authorship contribution statement", 1)
    add_text_paragraph(doc, (
        "Daniel M. Goldenholz: Conceptualization, Methodology, Software, Formal analysis, Investigation, "
        "Data curation, Visualization, Writing – original draft, Writing – review & editing, Supervision, "
        "Funding acquisition. Rohan Bhansali: Writing – review & editing. Ted J. Kaptchuk: "
        "Writing – review & editing. Brandon Westover: Methodology, Writing – review & editing."
    ), first_line=False)

    add_heading(doc, "Declaration of generative AI and AI-assisted technologies", 1)
    add_text_paragraph(doc, (
        "During the preparation of this work, the authors used OpenAI Codex to assist with code review, "
        "manuscript organization, language editing, and preparation of the journal-specific revision. "
        "After using this tool, the authors reviewed and edited the content as needed and take full "
        "responsibility for the content of the publication."
    ), first_line=False)

    add_heading(doc, "Acknowledgments", 1)
    add_text_paragraph(doc, "None.", first_line=False)

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    add_heading(doc, "References", 1)
    for para_xml in bibliography:
        doc._element.body.insert(len(doc._element.body) - 1, copy.deepcopy(para_xml))

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    add_heading(doc, "Figure legends", 1)
    p = doc.add_paragraph(style="Figure caption")
    set_run_font(p.add_run("Figure 1. Three operational sources of regression to the mean."), size=11, bold=True)
    set_run_font(p.add_run(
        " Conceptual representation of transient state worsening (type 1), selection on natural "
        "variability (type 2), and measurement error (type 3). Each can make the selected baseline "
        "more extreme than the subsequent test period without a treatment effect. RTM, regression to the mean."
    ), size=11)
    p = doc.add_paragraph(style="Figure caption")
    set_run_font(p.add_run("Figure 2. Trial-facing consequences of isolated RTM mechanisms."), size=11, bold=True)
    set_run_font(p.add_run(
        " Eligibility yield, proportion meeting the RTM definition, and median percentage change "
        "from baseline under the perfect-measurement reference condition and isolated transient-state, "
        "eligibility-threshold, sensitivity, and false-alarm conditions. FAR, false-alarm rate; MPC, "
        "median percentage change; RTM, regression to the mean."
    ), size=11)

    for idx, image in ((1, FIG1_PNG), (2, FIG2_PNG)):
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(p.add_run(f"Figure {idx}"), bold=True)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(image), width=Inches(5.8 if idx == 1 else 6.2))

    # Replace the provisional main-text count using the rebuilt document's numbered
    # main sections only (title, abstract, declarations, references, and legends excluded).
    texts = []
    collecting = False
    for p in doc.paragraphs:
        if p.text == "1. Introduction":
            collecting = True
        if p.text == "Funding":
            collecting = False
        if collecting:
            texts.append(p.text)
    main_count = count_words(" ".join(texts))
    for p in doc.paragraphs:
        if p.text.startswith("Manuscript counts: "):
            p.clear()
            set_run_font(p.add_run("Manuscript counts: "), bold=True)
            set_run_font(p.add_run(
                f"abstract {abstract_count} words; main text {main_count} words; "
                "18 references; 2 figures; 0 tables."
            ))
            break

    doc.core_properties.title = TITLE
    doc.core_properties.subject = "Original Research submission to Journal of Clinical Epidemiology"
    doc.core_properties.author = "Daniel M. Goldenholz; Rohan Bhansali; Ted J. Kaptchuk; Brandon Westover"
    doc.core_properties.keywords = KEYWORDS
    doc.save(OUTPUT)

    # Mandatory separate editable Highlights file for Elsevier submission.
    hdoc = Document()
    configure_styles(hdoc)
    configure_page(hdoc)
    p = hdoc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run("Highlights"), size=14, bold=True)
    p = hdoc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run(TITLE), italic=True)
    for bullet in HIGHLIGHT_BULLETS:
        p = hdoc.add_paragraph(style="List Bullet")
        set_run_font(p.add_run(bullet))
    hdoc.save(HIGHLIGHTS)

    shutil.copy2(FIG1_PDF_SOURCE, FIG1_PDF)
    shutil.copy2(FIG2_PDF_SOURCE, FIG2_PDF)

    print(json.dumps({
        "output": str(OUTPUT),
        "highlights": str(HIGHLIGHTS),
        "figure_1": str(FIG1_PDF),
        "figure_2": str(FIG2_PDF),
        "abstract_words": abstract_count,
        "main_text_words": main_count,
        "citation_fields": len(citations),
        "highlight_lengths": [len(x) for x in HIGHLIGHT_BULLETS],
    }, indent=2))


if __name__ == "__main__":
    build()
