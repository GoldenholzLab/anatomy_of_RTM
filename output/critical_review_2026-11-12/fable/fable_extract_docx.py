"""Read-only OOXML extraction for the Fable review.

Opens a DOCX with zipfile, never writes to it, and prints body blocks in order.
Field instructions are shown as {FIELD: ...} and kept apart from cached field
results, which are shown as <<cached: ...>>. OMML is linearized as text.
"""
from __future__ import annotations

import sys
import zipfile
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": W, "m": M, "a": A, "wp": WP, "r": R}


def q(ns, tag):
    return "{%s}%s" % (ns, tag)


def omml(node):
    """Linearize an OMML node."""
    tag = etree.QName(node).localname
    kids = list(node)

    def sub(name):
        el = node.find("m:" + name, NS)
        return omml_children(el) if el is not None else ""

    if tag == "t":
        return node.text or ""
    if tag == "f":
        return "((%s)/(%s))" % (sub("num"), sub("den"))
    if tag == "sSub":
        return "%s_{%s}" % (sub("e"), sub("sub"))
    if tag == "sSup":
        return "%s^{%s}" % (sub("e"), sub("sup"))
    if tag == "sSubSup":
        return "%s_{%s}^{%s}" % (sub("e"), sub("sub"), sub("sup"))
    if tag == "rad":
        deg = sub("deg")
        return "root[%s](%s)" % (deg, sub("e")) if deg else "sqrt(%s)" % sub("e")
    if tag == "d":
        pr = node.find("m:dPr", NS)
        beg, end, sep = "(", ")", "|"
        if pr is not None:
            b = pr.find("m:begChr", NS)
            e = pr.find("m:endChr", NS)
            s = pr.find("m:sepChr", NS)
            if b is not None:
                beg = b.get(q(M, "val"), "")
            if e is not None:
                end = e.get(q(M, "val"), "")
            if s is not None:
                sep = s.get(q(M, "val"), "|")
        parts = [omml_children(e) for e in node.findall("m:e", NS)]
        return beg + sep.join(parts) + end
    if tag == "nary":
        pr = node.find("m:naryPr", NS)
        ch = "INT"
        if pr is not None:
            c = pr.find("m:chr", NS)
            if c is not None:
                ch = c.get(q(M, "val"), "INT")
        return "%s_{%s}^{%s}[%s]" % (ch, sub("sub"), sub("sup"), sub("e"))
    if tag == "func":
        return "%s(%s)" % (sub("fName"), sub("e"))
    if tag == "acc":
        pr = node.find("m:accPr", NS)
        ch = "^"
        if pr is not None:
            c = pr.find("m:chr", NS)
            if c is not None:
                ch = c.get(q(M, "val"), "^")
        return "acc[%s](%s)" % (ch, sub("e"))
    if tag == "bar":
        return "bar(%s)" % sub("e")
    if tag == "limLow":
        return "%s_lim{%s}" % (sub("e"), sub("lim"))
    if tag == "limUpp":
        return "%s^lim{%s}" % (sub("e"), sub("lim"))
    if tag == "m":
        rows = []
        for mr in node.findall("m:mr", NS):
            rows.append(" & ".join(omml_children(e) for e in mr.findall("m:e", NS)))
        return "[" + " ;; ".join(rows) + "]"
    if tag == "eqArr":
        return " ;; ".join(omml_children(e) for e in node.findall("m:e", NS))
    if tag in ("rPr", "ctrlPr", "fPr", "dPr", "naryPr", "sSubPr", "sSupPr",
               "sSubSupPr", "radPr", "funcPr", "accPr", "barPr", "oMathParaPr",
               "limLowPr", "limUppPr", "mPr", "eqArrPr", "groupChrPr", "boxPr",
               "borderBoxPr", "sPrePr", "phantPr"):
        return ""
    return "".join(omml(k) for k in kids)


def omml_children(node):
    return "".join(omml(k) for k in node)


def para_text(p, state):
    """Return text of a paragraph with field instructions and cached results marked."""
    out = []

    def walk(node):
        tag = etree.QName(node).localname if isinstance(node.tag, str) else ""
        ns = etree.QName(node).namespace if isinstance(node.tag, str) else ""
        if ns == M and tag in ("oMath", "oMathPara"):
            out.append(" [[OMML: %s]] " % omml(node))
            return
        if ns == W:
            if tag == "pPr":
                return
            if tag == "fldSimple":
                out.append("{FIELD: %s}" % node.get(q(W, "instr"), "").strip())
                out.append("<<cached: ")
                for k in node:
                    walk(k)
                out.append(">>")
                return
            if tag == "fldChar":
                t = node.get(q(W, "fldCharType"))
                if t == "begin":
                    state["depth"] += 1
                    state["mode"].append("instr")
                    out.append("{FIELD: ")
                elif t == "separate":
                    if state["mode"]:
                        state["mode"][-1] = "result"
                    out.append("}<<cached: ")
                elif t == "end":
                    if state["mode"]:
                        mode = state["mode"].pop()
                        out.append("}" if mode == "instr" else ">>")
                    state["depth"] -= 1
                return
            if tag == "instrText":
                txt = node.text or ""
                if len(txt) > 160 and not state.get("full_instr"):
                    txt = txt[:160] + " ...[%d chars]" % len(node.text)
                out.append(txt)
                return
            if tag == "t":
                out.append(node.text or "")
                return
            if tag == "delText":
                out.append("[[DEL: %s]]" % (node.text or ""))
                return
            if tag == "tab":
                out.append("\t")
                return
            if tag in ("br", "cr"):
                out.append(" / ")
                return
            if tag == "noBreakHyphen":
                out.append("-")
                return
            if tag == "footnoteReference":
                out.append("[^fn%s]" % node.get(q(W, "id")))
                return
            if tag == "commentReference":
                out.append("[comment %s]" % node.get(q(W, "id")))
                return
            if tag == "drawing":
                desc = node.find(".//wp:docPr", NS)
                blip = node.find(".//a:blip", NS)
                ext = node.find(".//wp:extent", NS)
                out.append("[[DRAWING name=%r descr=%r embed=%s extent=%s]]" % (
                    desc.get("name") if desc is not None else None,
                    desc.get("descr") if desc is not None else None,
                    blip.get(q(R, "embed")) if blip is not None else None,
                    (ext.get("cx"), ext.get("cy")) if ext is not None else None))
                return
            if tag == "ins":
                out.append("[[INS: ")
                for k in node:
                    walk(k)
                out.append("]]")
                return
            if tag == "rPr":
                if node.find("w:vanish", NS) is not None:
                    out.append("[[HIDDEN]]")
                va = node.find("w:vertAlign", NS)
                if va is not None:
                    v = va.get(q(W, "val"))
                    if v == "superscript":
                        out.append("^")
                    elif v == "subscript":
                        out.append("_")
                return
        for k in node:
            walk(k)

    walk(p)
    return "".join(out)


def style_of(p):
    s = p.find("w:pPr/w:pStyle", NS)
    return s.get(q(W, "val")) if s is not None else ""


def dump(path, full_instr=False):
    z = zipfile.ZipFile(path)
    doc = etree.fromstring(z.read("word/document.xml"))
    body = doc.find("w:body", NS)
    state = {"depth": 0, "mode": [], "full_instr": full_instr}
    idx = 0
    for el in body:
        tag = etree.QName(el).localname
        if tag == "p":
            txt = para_text(el, state)
            print("P%03d [%s] %s" % (idx, style_of(el), txt))
            idx += 1
        elif tag == "tbl":
            print("TABLE%03d" % idx)
            for r_i, tr in enumerate(el.findall("w:tr", NS)):
                cells = []
                for tc in tr.findall("w:tc", NS):
                    span = tc.find("w:tcPr/w:gridSpan", NS)
                    vm = tc.find("w:tcPr/w:vMerge", NS)
                    ctext = " / ".join(para_text(p, state) for p in tc.findall(".//w:p", NS))
                    extra = ""
                    if span is not None:
                        extra += "{span=%s}" % span.get(q(W, "val"))
                    if vm is not None:
                        extra += "{vmerge=%s}" % (vm.get(q(W, "val")) or "cont")
                    cells.append(extra + ctext)
                print("  R%02d | %s" % (r_i, " | ".join(cells)))
            idx += 1
        elif tag == "sectPr":
            print("SECTPR")
        else:
            print("OTHER <%s>" % tag)
    for part in ("word/footnotes.xml", "word/endnotes.xml", "word/comments.xml",
                 "word/header1.xml", "word/footer1.xml"):
        if part in z.namelist():
            root = etree.fromstring(z.read(part))
            ps = root.findall(".//w:p", NS)
            txts = [para_text(p, {"depth": 0, "mode": [], "full_instr": full_instr}) for p in ps]
            txts = [t for t in txts if t.strip()]
            print("PART %s: %s" % (part, txts))
    print("RELS:")
    rels = etree.fromstring(z.read("word/_rels/document.xml.rels"))
    for r in rels:
        print("  ", r.get("Id"), r.get("Type").rsplit("/", 1)[-1], r.get("Target"))
    for part in ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml"):
        print("PART %s: %s" % (part, z.read(part).decode("utf8")[:1500]))
    n_ins = len(doc.findall(".//w:ins", NS))
    n_del = len(doc.findall(".//w:del", NS))
    print("TRACKED: ins=%d del=%d" % (n_ins, n_del))


if __name__ == "__main__":
    dump(sys.argv[1], full_instr=len(sys.argv) > 2 and sys.argv[2] == "--full")
