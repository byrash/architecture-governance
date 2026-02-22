#!/usr/bin/env python3
"""
Pre-extract deterministic features from diagram images before LLM vision calls.
Uses OCR (pytesseract), color analysis (Pillow), and shape detection (OpenCV)
to produce a structured context file that constrains LLM output.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f'#{r:02X}{g:02X}{b:02X}'


def extract_text_labels(image_path: str) -> List[str]:
    """Extract text labels from image using Tesseract OCR."""
    if not HAS_TESSERACT or not HAS_PIL:
        return []

    try:
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        custom_config = r'--oem 3 --psm 11'
        data = pytesseract.image_to_data(img, config=custom_config, output_type=pytesseract.Output.DICT)

        labels = []
        current_line = []
        current_block = -1

        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            conf = int(data['conf'][i])
            block = data['block_num'][i]

            if conf < 40:
                continue

            if block != current_block and current_line:
                line_text = ' '.join(current_line).strip()
                if len(line_text) >= 2:
                    labels.append(line_text)
                current_line = []

            current_block = block
            if text:
                current_line.append(text)

        if current_line:
            line_text = ' '.join(current_line).strip()
            if len(line_text) >= 2:
                labels.append(line_text)

        seen = set()
        unique_labels = []
        for label in labels:
            key = label.lower().strip()
            if key not in seen:
                seen.add(key)
                unique_labels.append(label)

        return unique_labels

    except Exception as e:
        print(f"OCR extraction failed: {e}", file=sys.stderr)
        return []


def extract_colors(image_path: str, top_n: int = 8) -> List[Dict]:
    """Extract dominant colors from diagram using Pillow."""
    if not HAS_PIL:
        return []

    try:
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        small = img.resize((200, 200), Image.Resampling.LANCZOS)
        pixels = list(small.getdata())

        bg_colors = {
            (255, 255, 255), (254, 254, 254), (253, 253, 253),
            (0, 0, 0), (240, 240, 240), (245, 245, 245),
            (250, 250, 250), (248, 248, 248),
        }

        def is_near_bg(r, g, b):
            for br, bg_, bb in bg_colors:
                if abs(r - br) < 15 and abs(g - bg_) < 15 and abs(b - bb) < 15:
                    return True
            if r > 230 and g > 230 and b > 230:
                return True
            return False

        quantized = []
        for r, g, b in pixels:
            if is_near_bg(r, g, b):
                continue
            qr = round(r / 16) * 16
            qg = round(g / 16) * 16
            qb = round(b / 16) * 16
            quantized.append((min(qr, 255), min(qg, 255), min(qb, 255)))

        if not quantized:
            return []

        counter = Counter(quantized)
        total_colored = len(quantized)

        results = []
        for (r, g, b), count in counter.most_common(top_n):
            pct = count / total_colored * 100
            if pct < 1.0:
                continue
            results.append({
                'hex': _rgb_to_hex(r, g, b),
                'pixel_count': count,
                'percentage': round(pct, 1),
            })

        return results

    except Exception as e:
        print(f"Color extraction failed: {e}", file=sys.stderr)
        return []


def detect_shapes(image_path: str) -> Dict[str, int]:
    """Detect shapes in diagram image using OpenCV contour analysis."""
    if not HAS_CV2:
        return {}

    try:
        img = cv2.imread(image_path)
        if img is None:
            return {}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = (img.shape[0] * img.shape[1]) * 0.001
        max_area = (img.shape[0] * img.shape[1]) * 0.5

        shapes = {'rectangles': 0, 'circles': 0, 'diamonds': 0, 'other': 0}

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue

            approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
            vertices = len(approx)

            circularity = 4 * 3.14159 * area / (perimeter * perimeter)

            if circularity > 0.75:
                shapes['circles'] += 1
            elif vertices == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect = float(w) / h if h > 0 else 0
                _, (ma, MA), angle = cv2.fitEllipse(contour) if len(contour) >= 5 else (0, (1, 1), 0)

                if 30 < abs(angle) < 60 and 0.7 < aspect < 1.4:
                    shapes['diamonds'] += 1
                else:
                    shapes['rectangles'] += 1
            elif vertices > 4:
                shapes['other'] += 1

        return shapes

    except Exception as e:
        print(f"Shape detection failed: {e}", file=sys.stderr)
        return {}


def detect_lines(image_path: str) -> Dict[str, int]:
    """Detect connecting lines in diagram using OpenCV Hough transform."""
    if not HAS_CV2:
        return {}

    try:
        img = cv2.imread(image_path)
        if img is None:
            return {}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        lines = cv2.HoughLinesP(edges, 1, 3.14159 / 180, threshold=50,
                                minLineLength=30, maxLineGap=10)

        if lines is None:
            return {'total': 0}

        return {'total': len(lines)}

    except Exception as e:
        print(f"Line detection failed: {e}", file=sys.stderr)
        return {}


def estimate_complexity(labels: List[str], shapes: Dict[str, int],
                        lines: Dict[str, int]) -> str:
    """Estimate diagram complexity."""
    total_shapes = sum(shapes.values()) if shapes else 0
    total_lines = lines.get('total', 0)
    total_labels = len(labels)

    score = total_shapes + total_lines + total_labels
    if score < 10:
        return 'simple'
    elif score < 30:
        return 'medium'
    else:
        return 'complex'


def preextract(image_path: str) -> dict:
    """Run all extraction steps and return structured context."""
    labels = extract_text_labels(image_path)
    colors = extract_colors(image_path)
    shapes = detect_shapes(image_path)
    lines = detect_lines(image_path)
    complexity = estimate_complexity(labels, shapes, lines)

    capabilities = []
    if HAS_TESSERACT:
        capabilities.append('ocr')
    if HAS_PIL:
        capabilities.append('color')
    if HAS_CV2:
        capabilities.append('shapes')

    return {
        'source': Path(image_path).name,
        'ocr_labels': labels,
        'colors': colors,
        'shapes': shapes,
        'lines': lines,
        'estimated_complexity': complexity,
        'extraction_capabilities': capabilities,
    }


def format_llm_context(context: dict) -> str:
    """Format pre-extracted context as text for LLM prompt injection."""
    parts = [
        "Pre-extracted facts (verified by OCR/CV):",
    ]

    if context.get('ocr_labels'):
        parts.append(f"- Text labels found: {context['ocr_labels']}")
    else:
        parts.append("- Text labels: (OCR unavailable or no text detected)")

    if context.get('colors'):
        color_desc = ', '.join(
            f"{c['hex']} ({c['percentage']}%)" for c in context['colors'][:6]
        )
        parts.append(f"- Colors: {color_desc}")

    if context.get('shapes'):
        shape_desc = ', '.join(
            f"{count} {name}" for name, count in context['shapes'].items() if count > 0
        )
        if shape_desc:
            parts.append(f"- Shapes: {shape_desc}")

    if context.get('lines', {}).get('total', 0) > 0:
        parts.append(f"- Lines/connections: {context['lines']['total']} detected")

    parts.append(f"- Estimated complexity: {context.get('estimated_complexity', 'unknown')}")

    if context.get('ocr_labels'):
        parts.append(f"\nYour Mermaid output MUST include ALL {len(context['ocr_labels'])} text labels listed above.")
    if context.get('colors'):
        parts.append("Use the exact hex colors listed above in style/classDef directives.")

    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(
        description='Pre-extract diagram features for LLM context')
    parser.add_argument('--input', '-i', required=True, help='Input image file path')
    parser.add_argument('--output', '-o', help='Output JSON file (default: <input>.context.json)')
    parser.add_argument('--format-prompt', action='store_true',
                        help='Also print LLM prompt context to stdout')
    args = parser.parse_args()

    image_path = Path(args.input)
    if not image_path.exists():
        print(f"Error: File not found: {image_path}", file=sys.stderr)
        return 1

    context = preextract(str(image_path))

    output_path = args.output or f"{image_path}.context.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(context, f, indent=2)
    print(f"Context saved to: {output_path}", file=sys.stderr)

    if args.format_prompt:
        print(format_llm_context(context))

    return 0


if __name__ == '__main__':
    sys.exit(main())
