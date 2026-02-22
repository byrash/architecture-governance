#!/usr/bin/env python3
"""
Deterministic SVG-to-Mermaid converter.
Parses SVG XML structure (text, shapes, paths, styles) and produces Mermaid flowcharts.
Handles Draw.io-exported SVGs and generic vector diagrams.
Falls back gracefully when SVG contains only embedded raster images.
"""

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def is_embedded_raster(svg_content: str) -> bool:
    """Detect if SVG is just a wrapper around a raster bitmap."""
    try:
        root = ET.fromstring(svg_content)
    except ET.ParseError:
        return True

    ns = _get_namespaces(root)
    images = root.iter(f'{{{ns.get("", "")}}}image') if ns.get("") else root.iter('image')
    image_list = list(images)

    xlink_images = list(root.iter(f'{{{ns.get("xlink", "")}}}image')) if ns.get("xlink") else []
    image_list.extend(xlink_images)

    texts = _find_all_text(root, ns)
    rects = list(root.iter(f'{{{ns.get("", "")}}}rect')) if ns.get("") else list(root.iter('rect'))

    if image_list and not texts and len(rects) <= 1:
        return True

    for img in image_list:
        href = img.get('href', '') or img.get(f'{{{ns.get("xlink", "")}}}href', '')
        if href.startswith('data:image/png') or href.startswith('data:image/jpeg'):
            if not texts:
                return True

    return False


def _get_namespaces(root: ET.Element) -> Dict[str, str]:
    """Extract namespace map from root element."""
    nsmap = {}
    tag = root.tag
    if tag.startswith('{'):
        default_ns = tag[1:tag.index('}')]
        nsmap[''] = default_ns
    for key, val in root.attrib.items():
        if key.startswith('xmlns:'):
            prefix = key.split(':')[1]
            nsmap[prefix] = val
        elif key == 'xmlns':
            nsmap[''] = val
    return nsmap


def _find_all_text(root: ET.Element, ns: Dict[str, str]) -> List[str]:
    """Extract all text content from SVG."""
    texts = []
    default_ns = ns.get('', '')
    for elem in root.iter():
        tag = elem.tag
        if isinstance(tag, str):
            local = tag.split('}')[-1] if '}' in tag else tag
            if local in ('text', 'tspan'):
                t = (elem.text or '').strip()
                if t:
                    texts.append(t)
    return texts


def _parse_style(style_str: str) -> Dict[str, str]:
    """Parse CSS style string into dict."""
    result = {}
    if not style_str:
        return result
    for part in style_str.split(';'):
        part = part.strip()
        if ':' in part:
            k, v = part.split(':', 1)
            result[k.strip()] = v.strip()
    return result


def _get_fill(elem: ET.Element) -> Optional[str]:
    """Get fill color from element attributes or style."""
    fill = elem.get('fill')
    if fill and fill != 'none':
        return fill
    style = _parse_style(elem.get('style', ''))
    fill = style.get('fill')
    if fill and fill != 'none':
        return fill
    return None


def _get_stroke(elem: ET.Element) -> Optional[str]:
    """Get stroke color from element."""
    stroke = elem.get('stroke')
    if stroke and stroke != 'none':
        return stroke
    style = _parse_style(elem.get('style', ''))
    stroke = style.get('stroke')
    if stroke and stroke != 'none':
        return stroke
    return None


def _get_stroke_dash(elem: ET.Element) -> bool:
    """Check if element has dashed stroke."""
    dash = elem.get('stroke-dasharray', '')
    if dash and dash != 'none':
        return True
    style = _parse_style(elem.get('style', ''))
    dash = style.get('stroke-dasharray', '')
    return bool(dash and dash != 'none')


def _get_stroke_width(elem: ET.Element) -> float:
    """Get stroke width."""
    w = elem.get('stroke-width', '')
    if not w:
        style = _parse_style(elem.get('style', ''))
        w = style.get('stroke-width', '')
    try:
        return float(re.sub(r'[^\d.]', '', w))
    except (ValueError, TypeError):
        return 1.0


def _bbox(elem: ET.Element) -> Optional[Tuple[float, float, float, float]]:
    """Get bounding box (x, y, width, height) for shape elements."""
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

    try:
        if tag == 'rect':
            x = float(elem.get('x', 0))
            y = float(elem.get('y', 0))
            w = float(elem.get('width', 0))
            h = float(elem.get('height', 0))
            return (x, y, w, h)
        elif tag == 'circle':
            cx = float(elem.get('cx', 0))
            cy = float(elem.get('cy', 0))
            r = float(elem.get('r', 0))
            return (cx - r, cy - r, 2 * r, 2 * r)
        elif tag == 'ellipse':
            cx = float(elem.get('cx', 0))
            cy = float(elem.get('cy', 0))
            rx = float(elem.get('rx', 0))
            ry = float(elem.get('ry', 0))
            return (cx - rx, cy - ry, 2 * rx, 2 * ry)
    except (ValueError, TypeError):
        pass
    return None


def _center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    """Get center point of bbox."""
    return (bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2)


def _point_near_shape(px: float, py: float, bbox: Tuple[float, float, float, float],
                      tolerance: float = 30.0) -> bool:
    """Check if a point is near a shape boundary."""
    x, y, w, h = bbox
    cx, cy = x + w / 2, y + h / 2
    dx = max(abs(px - cx) - w / 2, 0)
    dy = max(abs(py - cy) - h / 2, 0)
    return math.sqrt(dx * dx + dy * dy) <= tolerance


def _sanitize_id(text: str) -> str:
    """Create a valid Mermaid node ID from text."""
    clean = re.sub(r'[^a-zA-Z0-9]', '_', text)
    clean = re.sub(r'_+', '_', clean).strip('_')
    if not clean or clean[0].isdigit():
        clean = 'n_' + clean
    return clean[:30]


def _detect_shape_type(elem: ET.Element) -> str:
    """Detect Mermaid shape type from SVG element."""
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    if tag == 'circle':
        return 'circle'
    if tag == 'ellipse':
        return 'ellipse'
    if tag in ('polygon', 'path'):
        return 'diamond'

    if tag == 'rect':
        rx = float(elem.get('rx', 0) or 0)
        ry = float(elem.get('ry', 0) or 0)
        if rx > 10 or ry > 10:
            return 'rounded'
        return 'rect'

    return 'rect'


def _shape_syntax(shape_type: str, label: str) -> str:
    """Return Mermaid node syntax for a shape type."""
    if shape_type == 'circle':
        return f'(("{label}"))'
    if shape_type == 'ellipse':
        return f'(["{label}"])'
    if shape_type == 'diamond':
        return f'{{"{label}"}}'
    if shape_type == 'rounded':
        return f'("{label}")'
    if shape_type == 'database' or shape_type == 'cylinder':
        return f'[("{label}")]'
    return f'["{label}"]'


def _path_endpoints(d: str) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Extract start and end points from an SVG path d attribute."""
    numbers = re.findall(r'[-+]?\d*\.?\d+', d)
    if len(numbers) < 4:
        return None
    try:
        start = (float(numbers[0]), float(numbers[1]))
        end = (float(numbers[-2]), float(numbers[-1]))
        return (start, end)
    except (ValueError, IndexError):
        return None


def _has_arrowhead(elem: ET.Element) -> bool:
    """Check if a line/path has a marker (arrowhead)."""
    marker = elem.get('marker-end', '') or elem.get('marker-start', '')
    if marker:
        return True
    style = _parse_style(elem.get('style', ''))
    return bool(style.get('marker-end') or style.get('marker-start'))


def convert_svg_to_mermaid(svg_content: str) -> Optional[str]:
    """
    Convert SVG XML to Mermaid flowchart syntax.
    Returns None if the SVG cannot be meaningfully parsed.
    """
    if is_embedded_raster(svg_content):
        return None

    try:
        root = ET.fromstring(svg_content)
    except ET.ParseError:
        return None

    ns = _get_namespaces(root)

    shapes = []
    texts_with_pos = []
    lines = []

    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

        if tag in ('rect', 'circle', 'ellipse'):
            bb = _bbox(elem)
            if bb and bb[2] > 5 and bb[3] > 5:
                fill = _get_fill(elem)
                stroke = _get_stroke(elem)
                if fill in ('#ffffff', '#FFFFFF', 'white', None) and not stroke:
                    continue
                shape_type = _detect_shape_type(elem)
                shapes.append({
                    'elem': elem,
                    'bbox': bb,
                    'center': _center(bb),
                    'fill': fill,
                    'stroke': stroke,
                    'type': shape_type,
                    'label': None,
                    'id': None,
                })

        elif tag in ('text', 'tspan'):
            text = (elem.text or '').strip()
            if text:
                x = float(elem.get('x', 0) or 0)
                y = float(elem.get('y', 0) or 0)
                texts_with_pos.append({'text': text, 'x': x, 'y': y})

        elif tag in ('line', 'path', 'polyline'):
            if tag == 'line':
                try:
                    start = (float(elem.get('x1', 0)), float(elem.get('y1', 0)))
                    end = (float(elem.get('x2', 0)), float(elem.get('y2', 0)))
                except (ValueError, TypeError):
                    continue
            elif tag == 'path':
                d = elem.get('d', '')
                if not d:
                    continue
                endpoints = _path_endpoints(d)
                if not endpoints:
                    continue
                start, end = endpoints
            else:
                points_str = elem.get('points', '')
                coords = re.findall(r'[-+]?\d*\.?\d+', points_str)
                if len(coords) < 4:
                    continue
                try:
                    start = (float(coords[0]), float(coords[1]))
                    end = (float(coords[-2]), float(coords[-1]))
                except (ValueError, IndexError):
                    continue

            dist = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
            if dist < 10:
                continue

            dashed = _get_stroke_dash(elem)
            width = _get_stroke_width(elem)
            lines.append({
                'start': start,
                'end': end,
                'dashed': dashed,
                'thick': width > 2.5,
                'has_arrow': _has_arrowhead(elem),
                'label': None,
            })

    if not shapes:
        return None

    for txt in texts_with_pos:
        best_shape = None
        best_dist = float('inf')
        for shape in shapes:
            bb = shape['bbox']
            cx, cy = _center(bb)
            if (bb[0] <= txt['x'] <= bb[0] + bb[2] and
                    bb[1] - 10 <= txt['y'] <= bb[1] + bb[3] + 10):
                d = math.sqrt((txt['x'] - cx) ** 2 + (txt['y'] - cy) ** 2)
                if d < best_dist:
                    best_dist = d
                    best_shape = shape

        if best_shape:
            if best_shape['label']:
                best_shape['label'] += ' ' + txt['text']
            else:
                best_shape['label'] = txt['text']

    labeled_shapes = [s for s in shapes if s.get('label')]
    if not labeled_shapes:
        for i, s in enumerate(shapes):
            s['label'] = f"Node {i + 1}"
        labeled_shapes = shapes

    used_ids = set()
    for s in labeled_shapes:
        base_id = _sanitize_id(s['label'])
        uid = base_id
        counter = 1
        while uid in used_ids:
            uid = f"{base_id}_{counter}"
            counter += 1
        s['id'] = uid
        used_ids.add(uid)

    all_y = [s['center'][1] for s in labeled_shapes]
    all_x = [s['center'][0] for s in labeled_shapes]
    y_spread = max(all_y) - min(all_y) if len(all_y) > 1 else 0
    x_spread = max(all_x) - min(all_x) if len(all_x) > 1 else 0
    direction = 'TB' if y_spread >= x_spread else 'LR'

    edges = []
    for line in lines:
        src_shape = None
        dst_shape = None
        src_dist = float('inf')
        dst_dist = float('inf')

        for s in labeled_shapes:
            bb = s['bbox']
            if _point_near_shape(line['start'][0], line['start'][1], bb):
                d = math.sqrt((line['start'][0] - s['center'][0]) ** 2 +
                              (line['start'][1] - s['center'][1]) ** 2)
                if d < src_dist:
                    src_dist = d
                    src_shape = s
            if _point_near_shape(line['end'][0], line['end'][1], bb):
                d = math.sqrt((line['end'][0] - s['center'][0]) ** 2 +
                              (line['end'][1] - s['center'][1]) ** 2)
                if d < dst_dist:
                    dst_dist = d
                    dst_shape = s

        if src_shape and dst_shape and src_shape['id'] != dst_shape['id']:
            if line['thick']:
                arrow = '==>'
            elif line['dashed']:
                arrow = '-.->'
            else:
                arrow = '-->'
            edges.append({
                'from': src_shape['id'],
                'to': dst_shape['id'],
                'arrow': arrow,
                'label': line.get('label'),
            })

    colors = {}
    for s in labeled_shapes:
        fill = s.get('fill')
        if fill and fill.lower() not in ('#ffffff', '#fff', 'white', 'none', 'transparent'):
            if fill not in colors:
                colors[fill] = f"color_{len(colors)}"

    mermaid_lines = [f'flowchart {direction}']

    if colors:
        for hex_color, class_name in colors.items():
            mermaid_lines.append(f'    classDef {class_name} fill:{hex_color},stroke:#333,color:#fff')
        mermaid_lines.append('')

    for s in labeled_shapes:
        node_def = f'    {s["id"]}{_shape_syntax(s["type"], s["label"])}'
        fill = s.get('fill')
        if fill and fill in colors:
            node_def += f':::{colors[fill]}'
        mermaid_lines.append(node_def)

    if edges:
        mermaid_lines.append('')
        seen = set()
        for e in edges:
            key = (e['from'], e['to'])
            if key in seen:
                continue
            seen.add(key)
            if e.get('label'):
                mermaid_lines.append(f'    {e["from"]} {e["arrow"]}|"{e["label"]}"| {e["to"]}')
            else:
                mermaid_lines.append(f'    {e["from"]} {e["arrow"]} {e["to"]}')

    if colors:
        mermaid_lines.append('')
        mermaid_lines.append('    %% Visual Legend:')
        mermaid_lines.append('    %% Colors:')
        for hex_color, class_name in colors.items():
            mermaid_lines.append(f'    %%   {hex_color} = {class_name}')

    mermaid_text = '\n'.join(mermaid_lines)
    return f'```mermaid\n{mermaid_text}\n```'


def main():
    parser = argparse.ArgumentParser(description='Convert SVG diagrams to Mermaid syntax')
    parser.add_argument('--input', '-i', required=True, help='Input SVG file path')
    parser.add_argument('--check-raster', action='store_true',
                        help='Only check if SVG contains embedded raster (exit 0=vector, 1=raster)')
    args = parser.parse_args()

    svg_path = Path(args.input)
    if not svg_path.exists():
        print(f"Error: File not found: {svg_path}", file=sys.stderr)
        return 1

    svg_content = svg_path.read_text(encoding='utf-8', errors='ignore')

    if args.check_raster:
        if is_embedded_raster(svg_content):
            print("RASTER", file=sys.stderr)
            return 1
        else:
            print("VECTOR", file=sys.stderr)
            return 0

    result = convert_svg_to_mermaid(svg_content)
    if result is None:
        print("Error: Could not convert SVG to Mermaid (embedded raster or no parseable shapes)",
              file=sys.stderr)
        return 1

    print(result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
