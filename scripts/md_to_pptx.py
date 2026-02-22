#!/usr/bin/env python3
"""Convert docs/lifecycle.md into a PowerPoint presentation with rendered Mermaid diagrams."""

import re
import os
import json
import subprocess
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)
BG_COLOR = RGBColor(0xFF, 0xFF, 0xFF)
TITLE_COLOR = RGBColor(0x1A, 0x1A, 0x2E)
BODY_COLOR = RGBColor(0x44, 0x44, 0x44)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MMDC = "mmdc"


def parse_slides(md_path: Path) -> list[dict]:
    text = md_path.read_text()
    sections = re.split(r"\n---\n", text)
    slides = []

    for section in sections:
        title_m = re.search(r"^##\s+(.+)$", section, re.MULTILINE)
        if not title_m:
            continue

        raw_title = title_m.group(1).strip()
        title = re.sub(r"^Slide\s+\d+:\s*", "", raw_title)

        mermaid_m = re.search(r"```mermaid\n(.*?)```", section, re.DOTALL)
        mermaid_code = mermaid_m.group(1).strip() if mermaid_m else None

        legend_m = re.search(r'<p align="right">.*?</p>', section, re.DOTALL)
        legend_html = legend_m.group(0) if legend_m else None

        tp_m = re.search(
            r"### Talking Points\n(.*?)(?=### Speaker Notes|$)", section, re.DOTALL
        )
        talking_points = tp_m.group(1).strip() if tp_m else ""

        sn_m = re.search(r"### Speaker Notes\n(.*?)$", section, re.DOTALL)
        speaker_notes = sn_m.group(1).strip() if sn_m else ""

        slides.append(
            {
                "title": title,
                "mermaid": mermaid_code,
                "legend_html": legend_html,
                "talking_points": talking_points,
                "speaker_notes": speaker_notes,
            }
        )

    return slides


def parse_legend(html: str) -> list[tuple[str, str]]:
    """Return [(hex_color, label), ...] from the legend HTML."""
    pairs = []
    for m in re.finditer(r"background:(#[0-9A-Fa-f]{6})", html):
        color = m.group(1)
        after = html[m.end() :]
        label_m = re.search(r"</span>\s*(.+?)(?:\s*<span|</sub>|$)", after)
        if label_m:
            label = re.sub(r"&nbsp;", " ", label_m.group(1)).strip().rstrip(";")
            pairs.append((color, label))
    return pairs


def render_mermaid(mermaid_code: str, out_png: Path, config_path: Path) -> bool:
    with tempfile.NamedTemporaryFile(
        suffix=".mmd", mode="w", delete=False
    ) as tmp:
        tmp.write(mermaid_code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                MMDC,
                "-i", tmp_path,
                "-o", str(out_png),
                "-c", str(config_path),
                "-b", "white",
                "-s", "3",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"  mmdc error: {result.stderr[:500]}")
            return False
        return out_png.exists()
    finally:
        os.unlink(tmp_path)


def hex_to_rgb(h: str) -> RGBColor:
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def set_slide_bg(slide, color: RGBColor):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_title_slide(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    set_slide_bg(slide, BG_COLOR)

    txbox = slide.shapes.add_textbox(
        Inches(1), Inches(2.5), SLIDE_WIDTH - Inches(2), Inches(2)
    )
    tf = txbox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Architecture Governance"
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = TITLE_COLOR
    p.alignment = PP_ALIGN.CENTER

    p2 = tf.add_paragraph()
    p2.text = "Lifecycle & Governance Model"
    p2.font.size = Pt(24)
    p2.font.color.rgb = BODY_COLOR
    p2.alignment = PP_ALIGN.CENTER
    p2.space_before = Pt(12)


def add_content_slide(
    prs: Presentation,
    title: str,
    diagram_png: Path | None,
    legend_items: list[tuple[str, str]],
    talking_points: str,
    speaker_notes: str,
):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    set_slide_bg(slide, BG_COLOR)

    title_box = slide.shapes.add_textbox(
        Inches(0.5), Inches(0.25), SLIDE_WIDTH - Inches(1), Inches(0.7)
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = TITLE_COLOR
    p.alignment = PP_ALIGN.LEFT

    img_top = Inches(1.1)
    img_max_w = SLIDE_WIDTH - Inches(1)
    img_max_h = Inches(5.4)

    if diagram_png and diagram_png.exists():
        from PIL import Image

        with Image.open(diagram_png) as im:
            orig_w, orig_h = im.size

        aspect = orig_w / orig_h
        target_h = img_max_h
        target_w = Emu(int(target_h * aspect))

        if target_w > img_max_w:
            target_w = img_max_w
            target_h = Emu(int(target_w / aspect))

        left = (SLIDE_WIDTH - target_w) // 2
        slide.shapes.add_picture(
            str(diagram_png), left, img_top, target_w, target_h
        )

    if legend_items:
        legend_top = Inches(6.7)
        legend_box = slide.shapes.add_textbox(
            Inches(0.5), legend_top, SLIDE_WIDTH - Inches(1), Inches(0.4)
        )
        tf_leg = legend_box.text_frame
        tf_leg.word_wrap = True
        p_leg = tf_leg.paragraphs[0]
        p_leg.alignment = PP_ALIGN.RIGHT

        for i, (color, label) in enumerate(legend_items):
            run_dot = p_leg.add_run()
            run_dot.text = "\u25A0 "
            run_dot.font.size = Pt(10)
            run_dot.font.color.rgb = hex_to_rgb(color)

            run_lbl = p_leg.add_run()
            suffix = "     " if i < len(legend_items) - 1 else ""
            run_lbl.text = label + suffix
            run_lbl.font.size = Pt(10)
            run_lbl.font.color.rgb = BODY_COLOR

    notes_slide = slide.notes_slide
    notes_tf = notes_slide.notes_text_frame
    if talking_points:
        notes_tf.text = "TALKING POINTS:\n" + talking_points
    if speaker_notes:
        p_sn = notes_tf.add_paragraph()
        p_sn.text = "\nSPEAKER NOTES:\n" + speaker_notes


def main():
    md_path = PROJECT_ROOT / "docs" / "lifecycle.md"
    out_dir = PROJECT_ROOT / "output"
    diagrams_dir = out_dir / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "theme": "default",
    }
    config_path = out_dir / "mermaid-config.json"
    config_path.write_text(json.dumps(config))

    print("Parsing lifecycle.md ...")
    slides = parse_slides(md_path)
    print(f"Found {len(slides)} slides")

    for i, s in enumerate(slides):
        if s["mermaid"]:
            png_path = diagrams_dir / f"slide_{i + 1}.png"
            print(f"Rendering diagram for Slide {i + 1}: {s['title']} ...")
            ok = render_mermaid(s["mermaid"], png_path, config_path)
            s["diagram_png"] = png_path if ok else None
            if not ok:
                print(f"  WARNING: Failed to render diagram for slide {i + 1}")
        else:
            s["diagram_png"] = None

    print("Building PowerPoint ...")
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    add_title_slide(prs)

    for s in slides:
        legend_items = parse_legend(s["legend_html"]) if s["legend_html"] else []
        add_content_slide(
            prs,
            s["title"],
            s["diagram_png"],
            legend_items,
            s["talking_points"],
            s["speaker_notes"],
        )

    pptx_path = out_dir / "architecture-governance-lifecycle.pptx"
    prs.save(str(pptx_path))
    print(f"\nDone! PowerPoint saved to: {pptx_path}")


if __name__ == "__main__":
    main()
