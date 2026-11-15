#!/usr/bin/env python3
"""CV spec (Markdown or JSON) -> DOCX -> PDF -> verification. One file per CV variant.

    build_cv.py cv/frontend-pl.md [...]
    build_cv.py --demo

JSON spec contract: {"meta": {...}, "page": {...}, "styles": [...], "blocks": [...]}
Block: {"type": "paragraph"|"bullet", "style": "<name>", "text": "..."} or
       {"type": "paragraph", "style": "...", "runs": [{"text": "...", "bold": true}]}
Output goes next to the spec: <name>.docx, <name>.pdf, <name>.txt, <name>.verify.json
Needs python-docx, PyMuPDF and LibreOffice (soffice) on PATH.
"""
from pathlib import Path
import json
import re
import subprocess
import sys
import unicodedata
import zipfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

LANG = {"pl": "pl-PL", "en": "en-GB", "de": "de-DE"}


# --- Markdown input ----------------------------------------------------------
# CV variants are written in .md; styles and page geometry are shared by every
# variant, so they live here instead of in one JSON copy per variant.

PAGE = {"width_mm": 210, "height_mm": 297,
        "margins_mm": {"top": 14, "bottom": 14, "left": 18, "right": 18}}

STYLES = [
    {"name": "CVName", "size_pt": 23, "bold": True, "color": "153E50", "keep_with_next": True, "space_after": 1},
    {"name": "CVHeadline", "size_pt": 11, "bold": True, "color": "153E50", "keep_with_next": True, "space_after": 3},
    {"name": "CVContact", "size_pt": 9, "color": "404A53", "space_after": 2},
    {"name": "CVSection", "size_pt": 10.5, "bold": True, "color": "153E50",
     "space_before": 6, "space_after": 3, "keep_with_next": True},
    {"name": "CVBody", "size_pt": 10.5, "color": "202A33"},
    {"name": "CVRole", "size_pt": 10.5, "bold": True, "color": "202A33",
     "space_before": 4, "keep_with_next": True},
    {"name": "CVNote", "size_pt": 8, "color": "6A4B30", "space_after": 2},
]


def split_bold(text):
    """**bold** -> runs. The rest stays in the regular weight."""
    text = re.sub(r"`([^`]+)`", r"\1", text)
    parts, runs = re.split(r"\*\*(.+?)\*\*", text), []
    for index, part in enumerate(parts):
        if part:
            runs.append({"text": part, "bold": index % 2 == 1})
    return runs or [{"text": ""}]


def parse_md(path):
    raw = path.read_text(encoding="utf-8")
    meta = {"lang": "pl", "author": "", "max_pages": 2}
    if raw.startswith("---\n"):
        front, _, raw = raw[4:].partition("\n---\n")
        for line in front.splitlines():
            key, _, value = line.partition(":")
            if key.strip():
                meta[key.strip()] = value.strip()
    meta["max_pages"] = int(meta["max_pages"])

    blocks = []
    for line in raw.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            style, text, kind = "CVSection", line[4:], "paragraph"
        elif line.startswith("## "):
            style, text, kind = "CVHeadline", line[3:], "paragraph"
        elif line.startswith("# "):
            style, text, kind = "CVName", line[2:], "paragraph"
        elif line.startswith("> "):
            style, text, kind = "CVContact", line[2:], "paragraph"
        elif line.startswith("! "):
            style, text, kind = "CVNote", line[2:], "paragraph"
        elif line.startswith("- "):
            style, text, kind = "CVBody", line[2:], "bullet"
        elif re.fullmatch(r"\*\*.+\*\*", line.strip()):
            style, text, kind = "CVRole", line.strip()[2:-2], "paragraph"
        else:
            style, text, kind = "CVBody", line, "paragraph"
        blocks.append({"type": kind, "style": style, "runs": split_bold(text)})

    assert blocks, f"{path.name}: empty document"
    styles = STYLES
    if "body_pt" in meta:  # optional front-matter key: body and role text size for a baseline that must stay on one page
        size = float(meta["body_pt"])
        styles = [dict(s, size_pt=size) if s["name"] in ("CVBody", "CVRole") else s for s in STYLES]
    return {"meta": meta, "page": PAGE, "styles": styles, "blocks": blocks}


def add_style(doc, spec):
    style = doc.styles.add_style(spec["name"], 1) if spec["name"] not in doc.styles else doc.styles[spec["name"]]
    font = style.font
    font.name = spec.get("font", "Liberation Sans")
    font.size = Pt(spec["size_pt"])
    font.bold = spec.get("bold", False)
    if "color" in spec:
        font.color.rgb = RGBColor.from_string(spec["color"])
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(attr), font.name)
    fmt = style.paragraph_format
    fmt.space_before = Pt(spec.get("space_before", 0))
    fmt.space_after = Pt(spec.get("space_after", 3))
    fmt.line_spacing = spec.get("line_spacing", 1.02)
    fmt.widow_control = True
    fmt.keep_with_next = spec.get("keep_with_next", False)
    return style


def set_lang(paragraph, code):
    """Language on every run; otherwise Word marks the whole text as a foreign language."""
    for run in paragraph.runs:
        rpr = run._r.get_or_add_rPr()
        lang = OxmlElement("w:lang")
        lang.set(qn("w:val"), code)
        rpr.append(lang)


def build_docx(spec, out):
    doc = Document()
    page = spec["page"]
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(page["width_mm"]), Mm(page["height_mm"])
    m = page["margins_mm"]
    section.top_margin, section.bottom_margin = Mm(m["top"]), Mm(m["bottom"])
    section.left_margin, section.right_margin = Mm(m["left"]), Mm(m["right"])
    section.header_distance, section.footer_distance = Mm(5), Mm(6)

    normal = doc.styles["Normal"]
    normal.font.name = "Liberation Sans"
    normal.font.size = Pt(10.5)
    for s in spec["styles"]:
        add_style(doc, s)

    code = LANG.get(spec.get("meta", {}).get("lang", "pl"), "pl-PL")
    for block in spec["blocks"]:
        p = doc.add_paragraph(style=block["style"])
        if block["type"] == "bullet":
            p.paragraph_format.left_indent = Mm(5)
            p.paragraph_format.first_line_indent = Mm(-3)
            p.add_run("• ")
        for run_spec in block.get("runs") or [{"text": block.get("text", "")}]:
            run = p.add_run(run_spec["text"])
            if run_spec.get("bold"):
                run.bold = True
        if block.get("align") == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_lang(p, code)

    meta = spec.get("meta", {})
    doc.core_properties.title = meta.get("title", "CV")
    doc.core_properties.author = meta.get("author", "")
    doc.core_properties.subject = meta.get("subject", "")
    doc.core_properties.keywords = meta.get("keywords", "")
    doc.save(out)
    return doc


def to_pdf(docx_path):
    subprocess.run(
        ["soffice", "--headless", "-env:UserInstallation=file:///tmp/cv-lo-profile",
         "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
        check=True, capture_output=True, timeout=180,
    )
    pdf = docx_path.with_suffix(".pdf")
    if not pdf.exists():
        raise RuntimeError(f"LibreOffice did not produce {pdf}")
    return pdf


def normalize(value):
    return "".join(unicodedata.normalize("NFKC", value).replace("­", "").split())


def verify(docx_path, pdf_path, margins_mm, max_pages):
    """The check of this generator: the PDF holds all DOCX text, stays inside the
    margins, no lines overlap and every font is embedded."""
    import pymupdf
    word = Document(docx_path)
    pdf = pymupdf.open(pdf_path)
    expected = [p.text for p in word.paragraphs if p.text.strip()]
    actual = "\n".join(page.get_text(sort=True) for page in pdf)
    missing = [p for p in expected if normalize(p) not in normalize(actual)]
    assert not missing, f"Missing in PDF: {missing[:3]}"
    assert len(pdf) <= max_pages, f"{len(pdf)} pages, limit {max_pages}"
    assert not word.tables, "CV must be one column without tables (ATS)"
    assert "�" not in actual, "Replacement characters in the text layer"
    with zipfile.ZipFile(docx_path) as package:
        assert package.testzip() is None
    for ch in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ":
        if any(ch in p for p in expected):
            assert ch in actual, f"Diacritic {ch} lost in the PDF conversion"

    pt = lambda mm: mm * 72 / 25.4
    left, right = pt(margins_mm["left"]), pt(margins_mm["right"])
    top, bottom = pt(margins_mm["top"]), pt(margins_mm["bottom"])
    bounds = []
    for number, page in enumerate(pdf, start=1):
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"])
                if not text.strip():
                    continue
                lines.append((*line["bbox"], text))
        # Margins are measured per word, not per line bbox: a line bbox includes the
        # trailing space, which hangs outside the column and is not a violation.
        for x0, y0, x1, y1, word, *_ in page.get_text("words"):
            assert x0 >= left - 1 and y0 >= top - 1, (number, word, "outside the margin")
            assert x1 <= page.rect.width - right + 1, (number, word, "cut on the right")
            assert y1 <= page.rect.height - bottom + 1, (number, word, "cut at the bottom")
        for before, after in zip(sorted(lines, key=lambda i: (i[1], i[0]))[:-1],
                                 sorted(lines, key=lambda i: (i[1], i[0]))[1:]):
            assert before[3] <= after[1] + 0.6, ("overlapping lines", before[4], after[4])
        for font in page.get_fonts():
            assert len(pdf.extract_font(font[0])[3]) > 0, f"Font not embedded: {font[3]}"
        bounds.append({"page": number, "text_lines": len(lines),
                       "fill_pct": round(100 * max(l[3] for l in lines) / page.rect.height)})
    return {"pages": len(pdf), "paragraphs": len(expected), "bounds": bounds,
            "words": len(actual.split())}


def build(spec_path):
    spec = (parse_md(spec_path) if spec_path.suffix == ".md"
            else json.loads(spec_path.read_text(encoding="utf-8")))
    base = spec_path.with_suffix("")
    docx_path = base.with_suffix(".docx")
    build_docx(spec, docx_path)
    pdf_path = to_pdf(docx_path)
    report = verify(docx_path, pdf_path, spec["page"]["margins_mm"],
                    spec.get("meta", {}).get("max_pages", 2))
    text = "\n\n".join(p.text for p in Document(docx_path).paragraphs if p.text.strip())
    base.with_suffix(".txt").write_text(text + "\n", encoding="utf-8")
    report |= {"status": "PASS", "spec": spec_path.name,
               "artifacts": {e: str(base.with_suffix(e)) for e in (".docx", ".pdf", ".txt")}}
    base.with_suffix(".verify.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def demo():
    """Self-check: a minimal spec goes the whole way to a verified PDF."""
    import tempfile
    spec = {"meta": {"lang": "pl", "title": "demo", "max_pages": 1},
            "page": {"width_mm": 210, "height_mm": 297,
                     "margins_mm": {"top": 14, "bottom": 14, "left": 18, "right": 18}},
            "styles": [{"name": "CVBody", "size_pt": 10.5, "color": "202A33"}],
            "blocks": [{"type": "paragraph", "style": "CVBody", "text": "Zażółć gęślą jaźń — ĄĆĘŁŃÓŚŹŻ"},
                       {"type": "bullet", "style": "CVBody", "text": "Punkt z diakrytykami: część, wdrożenie"}]}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "demo.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        report = build(path)
        assert report["pages"] == 1, report
        assert "Zażółć" in path.with_suffix(".txt").read_text(encoding="utf-8")

        md = Path(tmp) / "demo-md.md"
        md.write_text("---\nlang: pl\nmax_pages: 1\n---\n# JAN PRZYKŁADOWY\n## Frontend Developer\n> Lublin · ąęćłńóśźż\n### PROFIL\nZdanie z **pogrubieniem** w środku.\n- Punkt listy: wdrożenie, część\n", encoding="utf-8")
        report = build(md)
        text = md.with_suffix(".txt").read_text(encoding="utf-8")
        assert "JAN PRZYKŁADOWY" in text and "• Punkt listy" in text, text
        assert "**" not in text, "bold markers leaked into the document"
        assert "`" not in text, "backticks leaked into the document"
        md.write_text("---\nlang: pl\nmax_pages: 1\nbody_pt: 9.5\n---\n# JAN PRZYKŁADOWY\nZdanie.\n", encoding="utf-8")
        sizes = {s["name"]: s["size_pt"] for s in parse_md(md)["styles"]}
        assert sizes["CVBody"] == 9.5 and sizes["CVRole"] == 9.5 and sizes["CVSection"] == 10.5, sizes
        assert {s["name"]: s["size_pt"] for s in STYLES}["CVBody"] == 10.5, "body_pt must not change the shared styles"
    print("demo OK")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--demo"]:
        demo()
    else:
        for arg in args:
            print(json.dumps(build(Path(arg).resolve()), ensure_ascii=False))
