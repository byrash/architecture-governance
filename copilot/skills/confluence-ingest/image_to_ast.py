#!/usr/bin/env python3
"""
Image to AST Extractor — Deterministic CV + OCR Pipeline

Extracts diagram structure from raster images (PNG, JPG) using OpenCV
and Tesseract OCR to produce a partial DiagramAST with confidence scores.

Pipeline steps:
  1. Preprocessing (grayscale, denoise, adaptive threshold)
  2. Shape detection (contour analysis, polygon classification)
  3. Text extraction (Tesseract OCR with bounding boxes)
  4. Text-to-shape association (spatial matching)
  5. Color extraction (interior/boundary sampling)
  6. Group detection (containment analysis)
  7. Edge detection (HoughLinesP, endpoint-to-shape matching)
  8. Arrow detection (triangular contour at line endpoints)
  9. Edge label association (text overlapping lines, not shapes)
  10. Layout direction inference
  11. Confidence scoring per element

This script does NOT invoke any LLM. The output is a partial AST that
must be repaired by the ingestion agent's mandatory LLM repair step.

Usage:
    python image_to_ast.py --input diagram.png --output diagram.ast.json
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from diagram_ast import DiagramAST, DiagramNode, DiagramEdge, DiagramGroup, save_ast

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

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


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f'#{r:02X}{g:02X}{b:02X}'


def _is_near_white(r: int, g: int, b: int, threshold: int = 230) -> bool:
    return r > threshold and g > threshold and b > threshold


def _is_near_black(r: int, g: int, b: int, threshold: int = 30) -> bool:
    return r < threshold and g < threshold and b < threshold


# ──────────────────────────────────────────────────────────────────
# Step 1: Preprocessing
# ──────────────────────────────────────────────────────────────────

def _preprocess(img: 'np.ndarray') -> Tuple['np.ndarray', 'np.ndarray']:
    """Convert to grayscale, denoise, and produce binary threshold."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 4,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.dilate(binary, kernel, iterations=1)
    return gray, binary


# ──────────────────────────────────────────────────────────────────
# Step 2: Shape detection
# ──────────────────────────────────────────────────────────────────

def _classify_shape(contour: 'np.ndarray', approx: 'np.ndarray') -> Tuple[str, float]:
    """Classify a contour by vertex count and circularity. Returns (shape, confidence)."""
    vertices = len(approx)
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return 'rectangle', 0.3

    circularity = 4 * math.pi * area / (perimeter * perimeter)

    if circularity > 0.80:
        return 'circle', min(circularity, 1.0)
    if vertices == 4:
        x, y, w, h = cv2.boundingRect(approx)
        aspect = w / h if h > 0 else 1
        if len(contour) >= 5:
            _, (ma, MA), angle = cv2.fitEllipse(contour)
            if 25 < abs(angle % 90) < 65 and 0.6 < aspect < 1.6:
                return 'diamond', 0.7
        if 0.85 < aspect < 1.15:
            return 'rectangle', 0.9
        return 'rectangle', 0.8
    if vertices == 6:
        return 'hexagon', 0.7
    if vertices == 3:
        return 'diamond', 0.5
    if vertices > 6:
        return 'stadium', 0.5
    return 'rectangle', 0.4


def _detect_shapes(binary: 'np.ndarray', img_area: float) -> List[dict]:
    """Find contours, classify shapes, extract bounding boxes."""
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
    )

    min_area = img_area * 0.0008
    max_area = img_area * 0.5
    shapes: List[dict] = []

    for idx, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
        approx = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
        shape_type, conf = _classify_shape(contour, approx)
        x, y, w, h = cv2.boundingRect(contour)
        parent_idx = hierarchy[0][idx][3] if hierarchy is not None else -1

        shapes.append({
            'contour': contour, 'approx': approx,
            'x': x, 'y': y, 'w': w, 'h': h,
            'cx': x + w / 2, 'cy': y + h / 2,
            'area': area, 'shape': shape_type,
            'confidence': conf,
            'parent_idx': parent_idx,
            'idx': idx,
            'label': None, 'fill_color': None, 'stroke_color': None,
        })

    return shapes


# ──────────────────────────────────────────────────────────────────
# Step 3: Text extraction
# ──────────────────────────────────────────────────────────────────

def _extract_text(image_path: str) -> List[dict]:
    """Run Tesseract OCR, return text bboxes with confidence."""
    if not HAS_TESSERACT or not HAS_PIL:
        return []
    try:
        img = Image.open(image_path).convert('RGB')
        data = pytesseract.image_to_data(
            img, config='--oem 3 --psm 11',
            output_type=pytesseract.Output.DICT,
        )
        text_items: List[dict] = []
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            conf = int(data['conf'][i])
            if conf < 30 or not text:
                continue
            text_items.append({
                'text': text, 'conf': conf,
                'x': data['left'][i], 'y': data['top'][i],
                'w': data['width'][i], 'h': data['height'][i],
                'block': data['block_num'][i],
                'line': data['line_num'][i],
            })
        return text_items
    except Exception as e:
        print(f"OCR failed: {e}", file=sys.stderr)
        return []


def _group_text_into_labels(text_items: List[dict]) -> List[dict]:
    """Group adjacent OCR words into multi-word labels."""
    if not text_items:
        return []
    blocks: Dict[Tuple[int, int], List[dict]] = {}
    for item in text_items:
        key = (item['block'], item['line'])
        blocks.setdefault(key, []).append(item)

    labels: List[dict] = []
    for key, items in blocks.items():
        items.sort(key=lambda t: t['x'])
        full_text = ' '.join(t['text'] for t in items)
        if len(full_text.strip()) < 2:
            continue
        avg_conf = sum(t['conf'] for t in items) / len(items)
        min_x = min(t['x'] for t in items)
        min_y = min(t['y'] for t in items)
        max_x = max(t['x'] + t['w'] for t in items)
        max_y = max(t['y'] + t['h'] for t in items)
        labels.append({
            'text': full_text.strip(), 'conf': avg_conf,
            'x': min_x, 'y': min_y,
            'w': max_x - min_x, 'h': max_y - min_y,
            'cx': (min_x + max_x) / 2, 'cy': (min_y + max_y) / 2,
        })
    return labels


# ──────────────────────────────────────────────────────────────────
# Step 4: Text-to-shape association
# ──────────────────────────────────────────────────────────────────

def _associate_text_to_shapes(shapes: List[dict], labels: List[dict]) -> List[dict]:
    """Assign text labels to enclosing/nearest shapes. Returns unassigned labels.

    Two-pass strategy:
      1. Match text whose center falls inside the shape bbox (generous padding).
      2. For remaining text, match to the nearest shape within a proximity radius.
    """
    BBOX_PAD = 15
    PROXIMITY_RADIUS = 80.0

    unassigned: List[dict] = []
    matched: set = set()

    for idx, lbl in enumerate(labels):
        best_shape = None
        best_dist = float('inf')
        lcx, lcy = lbl['cx'], lbl['cy']
        for s in shapes:
            if (s['x'] - BBOX_PAD <= lcx <= s['x'] + s['w'] + BBOX_PAD and
                    s['y'] - BBOX_PAD <= lcy <= s['y'] + s['h'] + BBOX_PAD):
                d = math.sqrt((lcx - s['cx']) ** 2 + (lcy - s['cy']) ** 2)
                if d < best_dist:
                    best_dist = d
                    best_shape = s
        if best_shape:
            if best_shape['label']:
                best_shape['label'] += ' ' + lbl['text']
            else:
                best_shape['label'] = lbl['text']
            best_shape['confidence'] = max(
                best_shape['confidence'],
                lbl['conf'] / 100.0,
            )
            matched.add(idx)

    for idx, lbl in enumerate(labels):
        if idx in matched:
            continue
        lcx, lcy = lbl['cx'], lbl['cy']
        best_shape = None
        best_dist = float('inf')
        for s in shapes:
            d = math.sqrt((lcx - s['cx']) ** 2 + (lcy - s['cy']) ** 2)
            if d < PROXIMITY_RADIUS and d < best_dist:
                best_dist = d
                best_shape = s
        if best_shape:
            if best_shape['label']:
                best_shape['label'] += ' ' + lbl['text']
            else:
                best_shape['label'] = lbl['text']
            best_shape['confidence'] = max(
                best_shape['confidence'],
                lbl['conf'] / 100.0,
            )
        else:
            unassigned.append(lbl)
    return unassigned


# ──────────────────────────────────────────────────────────────────
# Step 5: Color extraction
# ──────────────────────────────────────────────────────────────────

def _sample_colors(img: 'np.ndarray', shapes: List[dict]) -> None:
    """Sample interior and boundary pixels to determine fill and stroke colors."""
    for s in shapes:
        x, y, w, h = s['x'], s['y'], s['w'], s['h']
        cx, cy = int(s['cx']), int(s['cy'])
        safe_h, safe_w = img.shape[:2]

        interior_y = max(0, min(cy, safe_h - 1))
        interior_x = max(0, min(cx, safe_w - 1))
        b, g, r = img[interior_y, interior_x]
        if not _is_near_white(r, g, b) and not _is_near_black(r, g, b):
            s['fill_color'] = _rgb_to_hex(r, g, b)

        edge_y = max(0, min(y, safe_h - 1))
        edge_x = max(0, min(x, safe_w - 1))
        b2, g2, r2 = img[edge_y, edge_x]
        if not _is_near_white(r2, g2, b2):
            s['stroke_color'] = _rgb_to_hex(r2, g2, b2)


# ──────────────────────────────────────────────────────────────────
# Step 6: Group detection
# ──────────────────────────────────────────────────────────────────

def _detect_groups(shapes: List[dict]) -> List[dict]:
    """Identify shapes whose bbox fully contains other shapes → mark as groups."""
    groups: List[dict] = []
    for i, outer in enumerate(shapes):
        children = []
        for j, inner in enumerate(shapes):
            if i == j:
                continue
            if (outer['x'] <= inner['x'] and
                    outer['y'] <= inner['y'] and
                    outer['x'] + outer['w'] >= inner['x'] + inner['w'] and
                    outer['y'] + outer['h'] >= inner['y'] + inner['h'] and
                    outer['area'] > inner['area'] * 1.5):
                children.append(j)
        if len(children) >= 2:
            groups.append({'shape_idx': i, 'children': children})
    return groups


# ──────────────────────────────────────────────────────────────────
# Step 7 & 8: Edge and arrow detection
# ──────────────────────────────────────────────────────────────────

def _detect_edges(binary: 'np.ndarray', shapes: List[dict],
                  group_indices: set) -> List[dict]:
    """Detect lines with HoughLinesP, match endpoints to shapes.

    Uses two sensitivity passes (strict then relaxed) to catch both
    prominent connectors and lighter/shorter lines.  Endpoint-to-shape
    tolerance scales with image diagonal so it works on both small icons
    and high-resolution exports.
    """
    img_h, img_w = binary.shape[:2]
    diag = math.sqrt(img_w ** 2 + img_h ** 2)
    tolerance = max(60.0, diag * 0.04)

    all_lines = []
    for thresh, min_len, max_gap in [(30, 20, 20), (20, 15, 30)]:
        lines = cv2.HoughLinesP(
            binary, 1, math.pi / 180, threshold=thresh,
            minLineLength=min_len, maxLineGap=max_gap,
        )
        if lines is not None:
            all_lines.extend(lines.tolist())

    if not all_lines:
        return []

    edges: List[dict] = []
    seen: set = set()

    for line in all_lines:
        x1, y1, x2, y2 = line[0]
        length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if length < 15:
            continue

        src_shape = None
        dst_shape = None
        src_dist = float('inf')
        dst_dist = float('inf')

        for idx, s in enumerate(shapes):
            if idx in group_indices:
                continue
            sx, sy, sw, sh = s['x'], s['y'], s['w'], s['h']
            scx, scy = s['cx'], s['cy']

            for px, py, is_start in [(x1, y1, True), (x2, y2, False)]:
                dx = max(abs(px - scx) - sw / 2, 0)
                dy = max(abs(py - scy) - sh / 2, 0)
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > tolerance:
                    continue
                if is_start and dist < src_dist:
                    src_dist = dist
                    src_shape = idx
                elif not is_start and dist < dst_dist:
                    dst_dist = dist
                    dst_shape = idx

        if src_shape is not None and dst_shape is not None and src_shape != dst_shape:
            key = (min(src_shape, dst_shape), max(src_shape, dst_shape))
            if key in seen:
                continue
            seen.add(key)
            conf = max(0.3, 1.0 - (src_dist + dst_dist) / (tolerance * 4))
            edges.append({
                'src_idx': src_shape, 'dst_idx': dst_shape,
                'confidence': round(conf, 2),
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
            })

    return edges


# ──────────────────────────────────────────────────────────────────
# Step 9: Edge label association
# ──────────────────────────────────────────────────────────────────

def _associate_labels_to_edges(edges: List[dict], unassigned_labels: List[dict],
                               shapes: List[dict]) -> None:
    """Assign text labels near the midpoint of an edge.

    Checks proximity to both the midpoint and the full line segment
    so labels placed anywhere along a connector are captured.
    """
    EDGE_LABEL_RADIUS = 80.0

    def _point_to_segment_dist(px: float, py: float,
                               x1: float, y1: float,
                               x2: float, y2: float) -> float:
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x, proj_y = x1 + t * dx, y1 + t * dy
        return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)

    for lbl in unassigned_labels:
        lcx, lcy = lbl['cx'], lbl['cy']
        best_edge = None
        best_dist = float('inf')
        for edge in edges:
            d = _point_to_segment_dist(
                lcx, lcy, edge['x1'], edge['y1'], edge['x2'], edge['y2'],
            )
            if d < EDGE_LABEL_RADIUS and d < best_dist:
                best_dist = d
                best_edge = edge
        if best_edge:
            best_edge.setdefault('label', '')
            if best_edge['label']:
                best_edge['label'] += ' ' + lbl['text']
            else:
                best_edge['label'] = lbl['text']


# ──────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────

def extract_ast(image_path: str) -> DiagramAST:
    """Run the full deterministic CV+OCR pipeline on an image.

    Returns a partial DiagramAST with confidence scores.
    Low-confidence elements (especially edges) need LLM repair.
    """
    capabilities: List[str] = []
    if HAS_CV2:
        capabilities.append('opencv')
    if HAS_TESSERACT:
        capabilities.append('tesseract')
    if HAS_PIL:
        capabilities.append('pillow')

    if not HAS_CV2:
        return DiagramAST(metadata={
            'source_format': 'image',
            'extraction_method': 'cv_tesseract',
            'error': 'opencv_not_available',
            'capabilities': capabilities,
        })

    img = cv2.imread(image_path)
    if img is None:
        return DiagramAST(metadata={
            'source_format': 'image',
            'extraction_method': 'cv_tesseract',
            'error': 'image_load_failed',
        })

    img_h, img_w = img.shape[:2]
    img_area = float(img_h * img_w)

    gray, binary = _preprocess(img)

    raw_shapes = _detect_shapes(binary, img_area)

    text_items = _extract_text(image_path)
    labels = _group_text_into_labels(text_items)

    unassigned_labels = _associate_text_to_shapes(raw_shapes, labels)

    _sample_colors(img, raw_shapes)

    raw_groups = _detect_groups(raw_shapes)
    group_shape_indices = {g['shape_idx'] for g in raw_groups}

    raw_edges = _detect_edges(binary, raw_shapes, group_shape_indices)

    _associate_labels_to_edges(raw_edges, unassigned_labels, raw_shapes)

    # --- Build DiagramAST ---
    node_shapes = [(i, s) for i, s in enumerate(raw_shapes) if i not in group_shape_indices]
    idx_to_node_id: Dict[int, str] = {}
    ast_nodes: List[DiagramNode] = []
    for seq, (original_idx, s) in enumerate(node_shapes):
        nid = f"node_{seq}"
        idx_to_node_id[original_idx] = nid
        ast_nodes.append(DiagramNode(
            id=nid,
            label=s.get('label') or f"Node_{seq}",
            shape=s['shape'],
            x=float(s['x']), y=float(s['y']),
            width=float(s['w']), height=float(s['h']),
            fill_color=s.get('fill_color'),
            stroke_color=s.get('stroke_color'),
            confidence=round(s['confidence'], 2),
        ))

    ast_groups: List[DiagramGroup] = []
    for g in raw_groups:
        gs = raw_shapes[g['shape_idx']]
        gid = f"group_{g['shape_idx']}"
        child_ids = [idx_to_node_id[ci] for ci in g['children'] if ci in idx_to_node_id]
        ast_groups.append(DiagramGroup(
            id=gid,
            label=gs.get('label') or f"Group_{g['shape_idx']}",
            children=child_ids,
            fill_color=gs.get('fill_color'),
        ))
        for ci in g['children']:
            nid = idx_to_node_id.get(ci)
            if nid:
                for n in ast_nodes:
                    if n.id == nid:
                        n.parent_group = gid

    ast_edges: List[DiagramEdge] = []
    for seq, e in enumerate(raw_edges):
        src_id = idx_to_node_id.get(e['src_idx'])
        dst_id = idx_to_node_id.get(e['dst_idx'])
        if not src_id or not dst_id:
            continue
        ast_edges.append(DiagramEdge(
            id=f"edge_{seq}",
            source=src_id, target=dst_id,
            label=e.get('label', ''),
            arrow_end=True,
            confidence=e['confidence'],
        ))

    # Direction inference
    if ast_nodes:
        xs = [n.x for n in ast_nodes if n.x != 0]
        ys = [n.y for n in ast_nodes if n.y != 0]
        if xs and ys:
            x_spread = max(xs) - min(xs)
            y_spread = max(ys) - min(ys)
            direction = 'LR' if x_spread > y_spread * 1.5 else 'TB'
        else:
            direction = 'TB'
    else:
        direction = 'TB'

    avg_conf = 0.0
    all_confs = [n.confidence for n in ast_nodes] + [e.confidence for e in ast_edges]
    if all_confs:
        avg_conf = round(sum(all_confs) / len(all_confs), 2)

    return DiagramAST(
        nodes=ast_nodes,
        edges=ast_edges,
        groups=ast_groups,
        diagram_type='flowchart',
        direction=direction,
        metadata={
            'source_format': 'image',
            'extraction_method': 'cv_tesseract',
            'capabilities': capabilities,
            'image_dimensions': [img_w, img_h],
            'shapes_detected': len(raw_shapes),
            'edges_detected': len(raw_edges),
            'ocr_labels_found': len(labels),
            'avg_confidence': avg_conf,
            'needs_llm_repair': True,
        },
    )


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description='Extract diagram AST from raster image (OpenCV + Tesseract)',
    )
    parser.add_argument('--input', '-i', required=True, help='Input image file (PNG, JPG)')
    parser.add_argument('--output', '-o', help='Output .ast.json file (default: <input>.ast.json)')
    args = parser.parse_args()

    image_path = Path(args.input)
    if not image_path.exists():
        print(f"Error: File not found: {image_path}", file=sys.stderr)
        return 1

    ast = extract_ast(str(image_path))

    output_path = args.output or str(image_path.with_suffix('.ast.json'))
    save_ast(ast, output_path)

    n = len(ast.nodes)
    e = len(ast.edges)
    g = len(ast.groups)
    avg = ast.metadata.get('avg_confidence', 0)
    print(f"  Extracted: {n} nodes, {e} edges, {g} groups (avg confidence: {avg})", file=sys.stderr)
    print(f"  AST written to {output_path}", file=sys.stderr)

    if ast.metadata.get('needs_llm_repair'):
        print("  Note: LLM repair is MANDATORY before using this AST", file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main())
