from __future__ import annotations

import os
from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


# -----------------------
# Branding / footer text
# -----------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")  # repo root/logo.png
DOC_VERSION = os.environ.get("DOC_VERSION", "ReDent Nova GmbH • Customer Complaint Form")


# -----------------------
# Text helpers
# -----------------------
def _wrap_text(text: str, max_width: float, font_name: str, font_size: int) -> List[str]:
    """
    Basic word-wrapping using ReportLab font metrics.
    Returns a list of lines that fit into max_width.
    """
    if text is None:
        return [""]

    s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = s.split("\n")

    lines: List[str] = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            lines.append("")
            continue

        words = p.split()
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if stringWidth(trial, font_name, font_size) <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                # If a single word is too long, hard-split it
                if stringWidth(w, font_name, font_size) > max_width:
                    chunk = ""
                    for ch in w:
                        trial2 = chunk + ch
                        if stringWidth(trial2, font_name, font_size) <= max_width:
                            chunk = trial2
                        else:
                            if chunk:
                                lines.append(chunk)
                            chunk = ch
                    if chunk:
                        cur = chunk
                    else:
                        cur = ""
                else:
                    cur = w
        if cur:
            lines.append(cur)

    return lines if lines else [""]


# ==========================================================
# Legacy renderer (schema/fields-based) — keep for fallback
# ==========================================================
def build_pdf_bytes(*, title: str, fields: Dict[str, Any]) -> bytes:
    """
    Minimal legacy PDF (kept so old payloads still work).
    If you don’t use old payloads anymore, it still won’t break anything.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_width, page_height = A4

    margin_x = 25 * mm
    top_y = page_height - 25 * mm
    y = top_y

    # Logo
    if os.path.exists(LOGO_PATH):
        logo_w = 70 * mm
        logo_h = 22 * mm
        c.drawImage(LOGO_PATH, margin_x, y - logo_h, width=logo_w, height=logo_h, preserveAspectRatio=True, mask="auto")
        y -= (logo_h + 8 * mm)

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin_x, y, title)
    y -= 10 * mm

    # Dump a few key fields (simple)
    c.setFont("Helvetica", 10)
    for k in ["submission_id", "timestamp"]:
        v = fields.get(k, "")
        c.drawString(margin_x, y, f"{k}: {v}")
        y -= 6 * mm

    y -= 4 * mm
    c.setFont("Helvetica", 9)

    # Print remaining fields
    for k, v in fields.items():
        if k in ("submission_id", "timestamp"):
            continue
        line = f"{k}: {v}"
        wrapped = _wrap_text(line, page_width - 2 * margin_x, "Helvetica", 9)
        for ln in wrapped:
            if y < 20 * mm:
                c.showPage()
                y = top_y
            c.drawString(margin_x, y, ln)
            y -= 5 * mm

    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(margin_x, 12 * mm, DOC_VERSION)

    c.save()
    return buf.getvalue()


# ==========================================================
# Dynamic renderer (sections/rows-based) — professional layout
# ==========================================================
def build_pdf_bytes_dynamic(
    *,
    title: str,
    complaint_id: str,
    timestamp: str,
    status: str,
    sections: List[Dict[str, Any]],
) -> bytes:
    """
    Dynamic, form-driven PDF (boxed two-column layout).
    """

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_width, page_height = A4

    margin_x = 18 * mm
    top_y = page_height - 18 * mm
    bottom_margin = 18 * mm

    # Layout sizes
    line_h = 5.5 * mm
    label_col_w = 70 * mm
    gap = 4 * mm
    value_col_w = page_width - (2 * margin_x + label_col_w + gap)

    # Typography
    title_size = 15
    section_size = 11
    label_font = "Helvetica-Bold"
    value_font = "Helvetica"
    label_size = 9
    value_size = 9

    page_num = 1
    y = top_y

    def draw_footer() -> None:
        c.setFont("Helvetica", 8)
        c.drawString(margin_x, 12 * mm, DOC_VERSION)
        c.drawRightString(page_width - margin_x, 12 * mm, f"Page {page_num}")

    def new_page(with_header: bool = True) -> None:
        nonlocal page_num, y
        draw_footer()
        c.showPage()
        page_num += 1
        y = top_y
        if with_header:
            draw_header()

    def ensure_space(height_needed: float) -> None:
        nonlocal y
        if y - height_needed < bottom_margin:
            new_page(with_header=True)

    def draw_header() -> None:
        nonlocal y

        # Logo centered
        if os.path.exists(LOGO_PATH):
            logo_w = 80 * mm
            logo_h = 24 * mm
            logo_x = (page_width - logo_w) / 2
            c.drawImage(LOGO_PATH, logo_x, y - logo_h, width=logo_w, height=logo_h, preserveAspectRatio=True, mask="auto")
            y -= (logo_h + 6 * mm)

        # Title
        c.setFont("Helvetica-Bold", title_size)
        c.drawCentredString(page_width / 2, y, title)
        y -= 9 * mm

        # Metadata header box
        box_w = page_width - 2 * margin_x
        box_h = 22 * mm
        box_x = margin_x
        box_y = y - box_h

        c.setStrokeColor(colors.black)
        c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=0)

        left_x = box_x + 6
        right_x = box_x + box_w / 2 + 6
        txt_y = box_y + box_h - 8

        c.setFont("Helvetica", 10)
        c.drawString(left_x, txt_y, f"Complaint ID: {complaint_id}")
        c.drawString(right_x, txt_y, f"Status: {status}")

        txt_y -= 11
        if timestamp:
            c.drawString(left_x, txt_y, f"Date: {timestamp}")

        y = box_y - 8 * mm

    def draw_section(section_title: str, rows: List[Dict[str, Any]]) -> None:
        nonlocal y

        # filter empty values
        filtered: List[tuple[str, str]] = []
        for r in rows or []:
            label = str(r.get("label") or "").strip()
            value = "" if r.get("value") is None else str(r.get("value")).strip()
            if label and value:
                filtered.append((label, value))
        if not filtered:
            return

        ensure_space(12 * mm)
        c.setFont("Helvetica-Bold", section_size)
        c.drawString(margin_x, y, section_title)
        y -= 7 * mm

        for label, value in filtered:
            label_lines = _wrap_text(label, label_col_w - 2, label_font, label_size)
            value_lines = _wrap_text(value, value_col_w - 4, value_font, value_size)

            label_block_h = max(line_h * len(label_lines), line_h)
            value_block_h = max(line_h * len(value_lines), line_h * 1.5)
            row_h = max(label_block_h, value_block_h) + 2 * mm

            ensure_space(row_h + 2 * mm)

            row_top = y
            row_bottom = y - row_h

            # Label (left)
            c.setFont(label_font, label_size)
            ly = row_top - 2
            for ln in label_lines:
                c.drawString(margin_x, ly, ln)
                ly -= line_h

            # Value box (right)
            box_x = margin_x + label_col_w + gap
            box_y = row_bottom + 2
            box_h = row_h - 4
            c.setStrokeColor(colors.black)
            c.rect(box_x, box_y, value_col_w, box_h, stroke=1, fill=0)

            c.setFont(value_font, value_size)
            ty = box_y + box_h - line_h
            for ln in value_lines:
                if ty < box_y + 2:
                    break
                c.drawString(box_x + 2, ty, ln)
                ty -= line_h

            y = row_bottom - 2 * mm

        y -= 4 * mm

    # Render
    draw_header()
    for sec in sections or []:
        sec_title = str(sec.get("title") or "Form Details").strip() or "Form Details"
        sec_rows = sec.get("rows") or []
        if isinstance(sec_rows, list):
            draw_section(sec_title, sec_rows)

    # finish
    draw_footer()
    c.save()
    return buf.getvalue()
