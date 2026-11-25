"""
exporters.py — turns the agents' output into downloadable files.
Supports: PDF, Word (.docx), Markdown (.md)
"""
import re
from datetime import datetime
from io import BytesIO

from fpdf import FPDF
from fpdf.fonts import FontFace
from docx import Document
from docx.shared import Pt, RGBColor


# ── Text cleaning ──────────────────────────────────────────────────────────────
_REPLACEMENTS = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2022": "-", "\u2026": "...",
    "\u00a0": " ", "\u2192": "->", "\u2713": "v", "\u2714": "v",
}


def _pdf_safe(text: str) -> str:
    """The built-in PDF fonts only support Latin-1, so swap/strip other chars."""
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "ignore").decode("latin-1")


def _clean_line(line: str) -> str:
    line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
    line = re.sub(r"__(.+?)__", r"\1", line)
    line = re.sub(r"`(.+?)`", r"\1", line)
    return line


def _nice(name: str) -> str:
    return name.title().replace("Gdd", "GDD")



def _blocks(text: str):
    """Yield ("table", rows) for markdown tables and ("line", text) for the rest."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                is_sep = all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c) and any(cells)
                if not is_sep:
                    rows.append(cells)
                i += 1
            width = max((len(r) for r in rows), default=0)
            rows = [r + [""] * (width - len(r)) for r in rows]
            if rows:
                yield "table", rows
        else:
            yield "line", lines[i]
            i += 1


# ── Markdown ───────────────────────────────────────────────────────────────────
def _brief(options) -> str:
    return "  |  ".join(f"{k}: {v}" for k, v in (options or {}).items())


def build_markdown(game_idea: str, results: dict, options: dict | None = None) -> str:
    date = datetime.now().strftime("%d %B %Y")
    md = [
        "# Game Design Document",
        f"**Game Idea:** {game_idea}",
        f"**Generated:** {date}  |  **By:** Game Design Studio (multi-agent AI)",
        *([f"**Design brief:** {_brief(options)}"] if options else []),
        "",
    ]
    for title, data in results.items():
        md += [f"## {_nice(title)}", "", data["output"], "", "---", ""]
    return "\n".join(md)


# ── PDF ────────────────────────────────────────────────────────────────────────
class _GDDPdf(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Game Design Studio  -  Page {self.page_no()}", align="C")


def build_pdf(game_idea: str, results: dict, options: dict | None = None) -> bytes:
    pdf = _GDDPdf(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)

    # Cover page
    pdf.add_page()
    pdf.set_fill_color(124, 58, 237)
    pdf.rect(0, 0, 210, 6, "F")
    pdf.ln(55)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_text_color(30, 30, 50)
    pdf.cell(0, 14, "GAME DESIGN DOCUMENT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 15)
    pdf.set_text_color(124, 58, 237)
    pdf.multi_cell(0, 9, _pdf_safe(game_idea.strip().title()), align="C",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 6, datetime.now().strftime("Generated on %d %B %Y"),
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Created by 6 AI agents  |  Game Design Studio",
             align="C", new_x="LMARGIN", new_y="NEXT")
    if options:
        pdf.ln(8)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(124, 58, 237)
        pdf.cell(0, 6, "DESIGN BRIEF", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(60, 60, 70)
        for k, v in options.items():
            pdf.cell(0, 6, _pdf_safe(f"{k}: {v}"), align="C", new_x="LMARGIN", new_y="NEXT")

    # One section per agent
    for title, data in results.items():
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 17)
        pdf.set_text_color(124, 58, 237)
        pdf.cell(0, 10, _pdf_safe(_nice(title)), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(220, 220, 230)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.ln(4)

        for kind, item in _blocks(data["output"]):
            if kind == "table":
                ncols = len(item[0])
                weights = [max(6, min(40, max(len(r[c]) for r in item))) for c in range(ncols)]
                pdf.ln(2)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 50)
                pdf.set_fill_color(255, 255, 255)
                head = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=(124, 58, 237))
                with pdf.table(col_widths=tuple(weights), line_height=5.2,
                               text_align="LEFT", padding=1.5,
                               headings_style=head,
                               cell_fill_color=(246, 244, 252), cell_fill_mode="ROWS",
                               borders_layout="HORIZONTAL_LINES") as table:
                    for r in item:
                        row = table.row()
                        for cell in r:
                            row.cell(_pdf_safe(_clean_line(cell)))
                pdf.ln(3)
                continue

            line = _pdf_safe(_clean_line(item)).rstrip()
            if not line.strip():
                pdf.ln(2)
                continue

            if line.lstrip().startswith("#"):                      # heading
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(30, 30, 50)
                pdf.multi_cell(0, 7, line.lstrip("# ").strip(),
                               new_x="LMARGIN", new_y="NEXT")
            elif re.match(r"^\s*[-*+]\s+", line):                   # bullet
                pdf.set_font("Helvetica", "", 10.5)
                pdf.set_text_color(50, 50, 60)
                text = re.sub(r"^\s*[-*+]\s+", "", line)
                pdf.set_x(24)
                pdf.multi_cell(0, 6, "-  " + text, new_x="LMARGIN", new_y="NEXT")
            elif re.match(r"^\s*\d+[.)]\s+", line):                 # numbered
                pdf.set_font("Helvetica", "", 10.5)
                pdf.set_text_color(50, 50, 60)
                pdf.set_x(22)
                pdf.multi_cell(0, 6, line.strip(), new_x="LMARGIN", new_y="NEXT")
            elif re.fullmatch(r"\s*([-*_]\s*){3,}", line):           # --- divider
                pdf.ln(1)
            else:                                                   # paragraph
                pdf.set_font("Helvetica", "", 10.5)
                pdf.set_text_color(50, 50, 60)
                pdf.multi_cell(0, 6, line.strip(), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


# ── Word ───────────────────────────────────────────────────────────────────────
def build_docx(game_idea: str, results: dict, options: dict | None = None) -> bytes:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)

    title = doc.add_heading("Game Design Document", 0)
    title.runs[0].font.color.rgb = RGBColor(0x7C, 0x3A, 0xED)
    doc.add_paragraph(f"Game Idea: {game_idea.strip().title()}")
    doc.add_paragraph(datetime.now().strftime("Generated on %d %B %Y  |  Game Design Studio"))
    if options:
        doc.add_paragraph(f"Design brief — {_brief(options)}")

    for name, data in results.items():
        doc.add_page_break()
        doc.add_heading(_nice(name), 1)
        for kind, item in _blocks(data["output"]):
            if kind == "table":
                table = doc.add_table(rows=len(item), cols=len(item[0]))
                table.style = "Table Grid"
                for ri, r in enumerate(item):
                    for ci, cell in enumerate(r):
                        c = table.cell(ri, ci)
                        c.text = _clean_line(cell)
                        if ri == 0:
                            for run in c.paragraphs[0].runs:
                                run.bold = True
                doc.add_paragraph()
                continue

            line = _clean_line(item).rstrip()
            if not line.strip() or re.fullmatch(r"\s*([-*_]\s*){3,}", line):
                continue
            if line.lstrip().startswith("#"):
                doc.add_heading(line.lstrip("# ").strip(), 2)
            elif re.match(r"^\s*[-*+]\s+", line):
                doc.add_paragraph(re.sub(r"^\s*[-*+]\s+", "", line), style="List Bullet")
            elif re.match(r"^\s*\d+[.)]\s+", line):
                doc.add_paragraph(re.sub(r"^\s*\d+[.)]\s+", "", line), style="List Number")
            else:
                doc.add_paragraph(line.strip())

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()