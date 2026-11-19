"""Read-only OOXML extractor for the opus review.

Writes plain-text dumps of a DOCX: body paragraphs (with style), tables,
OMML equations rendered as linear text, field instructions vs cached results,
footnotes, and embedded media listing. Never writes into the DOCX.
"""
import sys
import zipfile
from pathlib import Path
from lxml import etree

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}
W = "{%s}" % NS["w"]
M = "{%s}" % NS["m"]


def omml_to_text(el):
    """Linearize an OMML element to readable text."""
    tag = etree.QName(el).localname
    kids = list(el)

    def sub(name):
        c = el.find("m:" + name, NS)
        return omml_to_text(c) if c is not None else ""

    if tag == "t":
        return el.text or ""
    if tag == "r":
        return "".join(omml_to_text(c) for c in kids if etree.QName(c).localname == "t")
    if tag == "f":
        return "(" + sub("num") + ")/(" + sub("den") + ")"
    if tag == "sSub":
        return sub("e") + "_{" + sub("sub") + "}"
    if tag == "sSup":
        return sub("e") + "^{" + sub("sup") + "}"
    if tag == "sSubSup":
        return sub("e") + "_{" + sub("sub") + "}^{" + sub("sup") + "}"
    if tag == "nary":
        chr_el = el.find("m:naryPr/m:chr", NS)
        op = chr_el.get(M + "val") if chr_el is not None else "∫"
        return op + "_{" + sub("sub") + "}^{" + sub("sup") + "}" + "[" + sub("e") + "]"
    if tag == "d":
        dpr = el.find("m:dPr", NS)
        beg, end = "(", ")"
        if dpr is not None:
            b = dpr.find("m:begChr", NS)
            e = dpr.find("m:endChr", NS)
            if b is not None:
                beg = b.get(M + "val", "")
            if e is not None:
                end = e.get(M + "val", "")
        parts = [omml_to_text(c) for c in el.findall("m:e", NS)]
        return beg + " | ".join(parts) + end
    if tag == "func":
        return sub("fName") + " " + sub("e")
    if tag == "limLow":
        return sub("e") + "_{" + sub("lim") + "}"
    if tag == "limUpp":
        return sub("e") + "^{" + sub("lim") + "}"
    if tag == "bar":
        return "bar(" + sub("e") + ")"
    if tag == "acc":
        chr_el = el.find("m:accPr/m:chr", NS)
        c = chr_el.get(M + "val") if chr_el is not None else "^"
        return "acc[" + c + "](" + sub("e") + ")"
    if tag == "rad":
        return "sqrt[" + sub("deg") + "](" + sub("e") + ")"
    if tag == "eqArr":
        return " ;; ".join(omml_to_text(c) for c in el.findall("m:e", NS))
    if tag == "m":
        rows = []
        for mr in el.findall("m:mr", NS):
            rows.append(" & ".join(omml_to_text(c) for c in mr.findall("m:e", NS)))
        return "[" + " \\\\ ".join(rows) + "]"
    if tag.endswith("Pr"):
        return ""
    return "".join(omml_to_text(c) for c in kids)


def para_text(p, fields_log):
    """Return paragraph text; OMML linearized inline as ⟦...⟧; fields annotated."""
    out = []
    field_stack = []  # each: dict(instr=[], result=[], phase)
    for node in p.iter():
        tag = node.tag
        if tag == M + "oMath" and node.getparent().tag != M + "oMathPara":
            out.append(" ⟦" + omml_to_text(node) + "⟧ ")
        elif tag == M + "oMathPara":
            out.append(" ⟦⟦" + " ;; ".join(omml_to_text(x) for x in node.findall("m:oMath", NS)) + "⟧⟧ ")
        # Skip text inside math (handled above)
        if tag in (W + "t", W + "delText", W + "instrText", W + "fldChar", W + "tab", W + "br", W + "fldSimple"):
            anc = node
            inside_math = False
            while anc is not None:
                if anc.tag in (M + "oMath", M + "oMathPara"):
                    inside_math = True
                    break
                anc = anc.getparent()
            if inside_math:
                continue
            if tag == W + "fldChar":
                t = node.get(W + "fldCharType")
                if t == "begin":
                    field_stack.append({"instr": [], "result": [], "phase": "instr"})
                elif t == "separate" and field_stack:
                    field_stack[-1]["phase"] = "result"
                elif t == "end" and field_stack:
                    f = field_stack.pop()
                    instr = "".join(f["instr"]).strip()
                    res = "".join(f["result"])
                    fields_log.append((instr[:200], res))
                    out.append("{FIELD:" + instr.split()[0] if instr else "{FIELD:")
                    out.append("|" + res + "}")
                continue
            if tag == W + "instrText":
                if field_stack:
                    field_stack[-1]["instr"].append(node.text or "")
                continue
            if tag == W + "delText":
                out.append("[DEL:" + (node.text or "") + "]")
                continue
            if tag == W + "tab":
                txt = "\t"
            elif tag == W + "br":
                txt = "\n"
            elif tag == W + "fldSimple":
                instr = node.get(W + "instr", "")
                res = "".join(t.text or "" for t in node.iter(W + "t"))
                fields_log.append((instr, res))
                continue
            else:
                txt = node.text or ""
                # check if inside fldSimple
                anc = node.getparent()
                in_simple = False
                while anc is not None and anc is not p:
                    if anc.tag == W + "fldSimple":
                        in_simple = True
                        break
                    anc = anc.getparent()
                if in_simple:
                    out.append("{FLDSIMPLE|" + txt + "}")
                    continue
            if field_stack and field_stack[-1]["phase"] == "result":
                field_stack[-1]["result"].append(txt)
            elif field_stack and field_stack[-1]["phase"] == "instr":
                field_stack[-1]["instr"].append(txt)
            else:
                # check for insertion/deletion wrappers
                out.append(txt)
    return "".join(out)


def dump(docx_path, out_dir):
    docx_path = Path(docx_path)
    out_dir = Path(out_dir)
    stem = "opus_" + docx_path.stem
    z = zipfile.ZipFile(docx_path)
    names = z.namelist()
    doc = etree.fromstring(z.read("word/document.xml"))
    body = doc.find("w:body", NS)
    fields_log = []
    lines = []
    tcount = 0
    for child in body:
        if child.tag == W + "p":
            sty = child.find("w:pPr/w:pStyle", NS)
            sname = sty.get(W + "val") if sty is not None else ""
            txt = para_text(child, fields_log)
            has_draw = child.find(".//w:drawing", NS) is not None
            prefix = "[%s]" % sname if sname else "[]"
            if has_draw:
                prefix += "[DRAWING]"
            lines.append(prefix + " " + txt)
        elif child.tag == W + "tbl":
            tcount += 1
            lines.append("=== TABLE %d ===" % tcount)
            for tr in child.findall("w:tr", NS):
                cells = []
                for tc in tr.findall("w:tc", NS):
                    ctext = " / ".join(para_text(pp, fields_log) for pp in tc.findall(".//w:p", NS))
                    cells.append(ctext.strip())
                lines.append(" || ".join(cells))
            lines.append("=== END TABLE %d ===" % tcount)
        elif child.tag == W + "sectPr":
            lines.append("[sectPr]")
    (out_dir / (stem + "_body.txt")).write_text("\n".join(lines))
    flines = ["INSTR\t=>\tCACHED"] + ["%s\t=>\t%s" % (a, b) for a, b in fields_log]
    (out_dir / (stem + "_fields.txt")).write_text("\n".join(flines))
    extra = []
    for part in ("word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"):
        if part in names:
            x = etree.fromstring(z.read(part))
            for p in x.iter(W + "p"):
                t = para_text(p, [])
                if t.strip():
                    extra.append(part + ": " + t)
    extra.append("MEDIA:")
    for n in names:
        if n.startswith("word/media") or n.startswith("word/embeddings"):
            extra.append("  %s %d" % (n, z.getinfo(n).file_size))
    # Tracked changes count
    ins = len(doc.findall(".//w:ins", NS))
    dels = len(doc.findall(".//w:del", NS))
    extra.append("TRACKED ins=%d del=%d" % (ins, dels))
    (out_dir / (stem + "_extra.txt")).write_text("\n".join(extra))
    print(docx_path.name, "paras/tables written; fields:", len(fields_log), "tables:", tcount, "ins/del", ins, dels)


if __name__ == "__main__":
    out = sys.argv[1]
    for p in sys.argv[2:]:
        dump(p, out)
