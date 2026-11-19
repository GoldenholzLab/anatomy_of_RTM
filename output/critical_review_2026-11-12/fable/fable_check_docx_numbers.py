"""Fable review, check 5: compare every table cell and in-text number in the two Seizure DOCX files
with values recomputed from the saved arrays (fable_saved_array_check.json).

Read-only on the DOCX files. Also counts words and checks Highlights length.
"""
from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
ORDER = ["baseline_perfect", "type1_transient_msf", "type2_threshold_8", "type3_sensitivity_90",
         "type3_sensitivity_80", "type3_sensitivity_70", "type3_far_1_per_month",
         "type3_far_1_per_week", "type3_far_1_per_day"]
FIXED_ORDER = [ORDER[0]] + ORDER[3:]


def visible_text(p):
    """Paragraph text as displayed: skips field instructions, keeps cached field results."""
    out, depth_instr = [], 0
    for el in p.iter():
        tag = etree.QName(el).localname
        if tag == "fldChar":
            kind = el.get("{%s}fldCharType" % W)
            if kind == "begin":
                depth_instr += 1
            elif kind == "separate":
                depth_instr -= 1
        elif tag == "t" and depth_instr == 0:
            out.append(el.text or "")
        elif tag == "noBreakHyphen":
            out.append("-")
    return "".join(out)


def tables(path):
    doc = etree.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    result = []
    for tbl in doc.find("w:body", NS).findall("w:tbl", NS):
        rows = []
        for tr in tbl.findall("w:tr", NS):
            rows.append([" ".join(visible_text(p) for p in tc.findall("w:p", NS)).strip()
                         for tc in tr.findall("w:tc", NS)])
        result.append(rows)
    return result


def body_paragraphs(path):
    doc = etree.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    out = []
    for el in doc.find("w:body", NS):
        if etree.QName(el).localname == "p":
            style = el.find("w:pPr/w:pStyle", NS)
            out.append((style.get("{%s}val" % W) if style is not None else "", visible_text(el)))
    return out


def num(text):
    return float(text.replace(",", ""))


def main():
    calc = json.loads((HERE / "fable_saved_array_check.json").read_text())["conditions"]
    fixed_true_only = json.loads((HERE / "fable_saved_array_check.json").read_text())["fixed_enrollment_true_only"]
    problems, checked = [], 0

    def cmp(label, shown, value, places):
        nonlocal checked
        checked += 1
        if abs(num(shown) - round(value, places)) > 10 ** (-places) / 2 + 1e-9:
            problems.append(f"{label}: document shows {shown}, recomputed {value}")

    main_doc = ROOT / "anatomy_of_RTM_Seizure.docx"
    supp = ROOT / "anatomy_of_RTM_Seizure_Supplement.docx"
    t1 = tables(main_doc)[0]
    for row, name in zip(t1[1:], ORDER):
        c = calc[name]
        cmp(f"Table 1 {name} n", row[1], c["n_eligible"], 0)
        cmp(f"Table 1 {name} measured", row[2], c["pct_measured_rtm"], 1)
        cmp(f"Table 1 {name} true", row[3], c["pct_true_rtm"], 1)
        cmp(f"Table 1 {name} type3", row[4], c["pct_type3"], 1)
        cmp(f"Table 1 {name} mpc", row[5], c["mpc"], 1)
    s1, s2, s3 = tables(supp)
    for row, name in zip(s1[1:], ORDER):
        c = calc[name]
        for j, key in enumerate(["n_eligible", "both", "type3", "true_only", "neither"], start=1):
            cmp(f"Table S1 {name} {key}", row[j], c[key], 0)
        if sum(int(num(x)) for x in row[2:6]) != int(num(row[1])):
            problems.append(f"Table S1 {name}: categories do not sum to eligible n")
    for row, name in zip(s2[1:], ORDER):
        c = calc[name]
        cmp(f"Table S2 {name} type3", row[1], c["pct_type3"], 1)
        lo, hi = row[2].split(" to ")
        cmp(f"Table S2 {name} ci lo", lo, c["type3_wilson_pct"][0], 1)
        cmp(f"Table S2 {name} ci hi", hi, c["type3_wilson_pct"][1], 1)
        cmp(f"Table S2 {name} share", row[3], c["type3_share_of_measured_pct"], 1)
        cmp(f"Table S2 {name} net", row[4], c["net_pp"], 1)
    for row, name in zip(s3[1:], FIXED_ORDER):
        c = calc[name]
        cmp(f"Table S3 {name} fixed n", row[1], c["fixed_n"], 0)
        cmp(f"Table S3 {name} rtm", row[2], c["fixed_pct_rtm"], 1)
        cmp(f"Table S3 {name} type3", row[3], c["fixed_pct_type3"], 1)
        cmp(f"Table S3 {name} zero B", row[4], c["fixed_zero_baseline_n"], 0)
        cmp(f"Table S3 {name} mpc n", row[5], c["fixed_mpc_n"], 0)
        cmp(f"Table S3 {name} mpc", row[6], c["fixed_mpc"], 1)

    # In-text numbers, typed here from the extracted text and matched to recomputed values.
    overlap = {(r["overlap"], r["shock_msf_relation"]): r
               for r in csv.DictReader((ROOT / "outputs/rtm123_type3_1m/type1_overlap_summary.csv").open())}
    b, t1c, t2c, s70, fd = (calc[k] for k in ("baseline_perfect", "type1_transient_msf", "type2_threshold_8",
                                              "type3_sensitivity_70", "type3_far_1_per_day"))
    text_claims = [
        ("eligible n perfect", "649,098", b["n_eligible"], 0), ("eligible % perfect", "64.9", b["pct_eligible"], 1),
        ("RTM perfect", "53.8", b["pct_measured_rtm"], 1), ("MPC perfect", "26.7", b["mpc"], 1),
        ("eligible transient", "75.6", t1c["pct_eligible"], 1), ("RTM transient", "58.3", t1c["pct_measured_rtm"], 1),
        ("MPC transient", "36.8", t1c["mpc"], 1),
        ("transient baseline-only RTM", "95.1", 100 * float(overlap[("baseline", "all")]["fraction_RTM"]), 1),
        ("transient baseline-only MPC", "92.6", float(overlap[("baseline", "all")]["MPC"]), 1),
        ("transient neither RTM", "51.0", 100 * float(overlap[("neither", "all")]["fraction_RTM"]), 1),
        ("transient neither MPC", "25.9", float(overlap[("neither", "all")]["MPC"]), 1),
        ("eligible threshold 8", "40.4", t2c["pct_eligible"], 1), ("RTM threshold 8", "57.9", t2c["pct_measured_rtm"], 1),
        ("MPC threshold 8", "29.4", t2c["mpc"], 1),
        ("eligible sens 70", "55.2", s70["pct_eligible"], 1), ("RTM sens 70", "59.0", s70["pct_measured_rtm"], 1),
        ("MPC sens 70", "33.3", s70["mpc"], 1), ("Type 3 sens 70", "7.7", s70["pct_type3"], 1),
        ("eligible FAR day", "98.5", fd["pct_eligible"], 1), ("RTM FAR day", "69.9", fd["pct_measured_rtm"], 1),
        ("MPC FAR day", "46.0", fd["mpc"], 1), ("Type 3 FAR day", "41.6", fd["pct_type3"], 1),
        ("Type 3 share FAR day", "59.4", fd["type3_share_of_measured_pct"], 1),
        ("measured-only n FAR day", "409,581", fd["type3"], 0), ("true-only n FAR day", "55,966", fd["true_only"], 0),
        ("net pp FAR day", "35.9", fd["net_pp"], 1),
        ("fixed RTM sens 70", "50.0", s70["fixed_pct_rtm"], 1), ("fixed RTM FAR day", "41.6", fd["fixed_pct_rtm"], 1),
        ("fixed MPC sens 70", "26.3", s70["fixed_mpc"], 1), ("fixed MPC FAR day", "17.6", fd["fixed_mpc"], 1),
        ("fixed MPC n sens 70", "649,090", s70["fixed_mpc_n"], 0), ("fixed MPC n FAR day", "631,490", fd["fixed_mpc_n"], 0),
    ]
    paras = body_paragraphs(main_doc)
    full = " ".join(t for _, t in paras)
    for label, shown, value, places in text_claims:
        cmp("text " + label, shown, value, places)
        if shown not in full:
            problems.append(f"text {label}: the string {shown} is not in the manuscript")

    # Table 1 arithmetic a reader can do: measured minus true versus the net difference in Table S2.
    rounding_notes = []
    for row, srow, name in zip(t1[1:], s2[1:], ORDER):
        diff = round(num(row[2]) - num(row[3]), 1)
        if abs(diff - num(srow[4])) > 1e-9:
            rounding_notes.append(f"{name}: Table 1 gives {row[2]} - {row[3]} = {diff}; Table S2 net difference is {srow[4]}")

    # Word counts.
    idx = {t.strip(): i for i, (s, t) in enumerate(paras)}
    abstract = [t for s, t in paras if s == "Abstract"]
    start = idx["1. Introduction"]
    stop = idx["Funding"]
    body = [t for s, t in paras[start:stop] if s != "Figurecaption"]
    body_no_headings = [t for s, t in paras[start:stop] if s not in ("Figurecaption", "Heading1", "Heading2")]
    wc = lambda parts: sum(len(re.findall(r"\S+", p)) for p in parts)
    highlights = [t for s, t in body_paragraphs(ROOT / "anatomy_of_RTM_Seizure_Highlights.docx") if s == "ListBullet"]
    counts = {
        "abstract_words": wc(abstract), "abstract_words_claimed": 207,
        "main_text_words_with_headings": wc(body), "main_text_words_without_headings": wc(body_no_headings),
        "main_text_words_claimed": 1809,
        "references_in_bibliography": sum(1 for s, t in paras if s == "Bibliography" and re.match(r"\[\d+\]", t)),
        "highlight_lengths_chars": [len(h) for h in highlights],
    }
    cited = set()
    for m in re.finditer(r"\[(\d+(?:[–,]\d+)*)\]", " ".join(t for s, t in paras[:stop])):
        for part in m.group(1).split(","):
            if "–" in part:
                a, z = part.split("–")
                cited.update(range(int(a), int(z) + 1))
            else:
                cited.add(int(part))
    counts["distinct_reference_numbers_cited_in_text"] = sorted(cited)
    result = {"cells_and_claims_checked": checked, "problems": problems,
              "rounding_notes": rounding_notes, "counts": counts,
              "fixed_enrollment_true_only_pct": {k: round(v["pct_true_only"], 2) for k, v in fixed_true_only.items()}}
    print(json.dumps(result, indent=1, ensure_ascii=False))
    (HERE / "fable_docx_number_check.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
