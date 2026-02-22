#!/usr/bin/env python3
"""
PlantUML to Mermaid Converter

Converts PlantUML diagram blocks to Mermaid syntax with:
- Sequence diagram support (participants, messages, notes, loops, alt)
- Component/deployment diagram support (packages, components, connections)
- Class diagram support (classes, interfaces, inheritance, composition)
- Color preservation (inline #hex, skinparam, named colors)
- Line style preservation (solid, dashed, dotted, thick, bidirectional)

Usage:
    python plantuml_to_mermaid.py --input file.puml
    python plantuml_to_mermaid.py --input file.puml --output file.mmd
    echo "@startuml ... @enduml" | python plantuml_to_mermaid.py --stdin
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from diagram_ast import (
    DiagramAST, DiagramNode, DiagramEdge, DiagramGroup,
    generate_mermaid as ast_generate_mermaid, save_ast,
)


# ─── Named color mapping ───────────────────────────────────────────

NAMED_COLORS = {
    'red': '#FF0000', 'blue': '#0000FF', 'green': '#008000',
    'orange': '#FFA500', 'yellow': '#FFFF00', 'purple': '#800080',
    'pink': '#FFC0CB', 'black': '#000000', 'white': '#FFFFFF',
    'gray': '#808080', 'grey': '#808080',
    'lightblue': '#ADD8E6', 'darkblue': '#00008B',
    'lightgreen': '#90EE90', 'darkgreen': '#006400',
    'lightgray': '#D3D3D3', 'lightgrey': '#D3D3D3',
    'darkgray': '#A9A9A9', 'darkgrey': '#A9A9A9',
    'cyan': '#00FFFF', 'magenta': '#FF00FF',
    'brown': '#A52A2A', 'navy': '#000080',
    'teal': '#008080', 'maroon': '#800000',
    'olive': '#808000', 'aqua': '#00FFFF',
    'coral': '#FF7F50', 'salmon': '#FA8072',
    'gold': '#FFD700', 'silver': '#C0C0C0',
    'skyblue': '#87CEEB', 'tomato': '#FF6347',
    'wheat': '#F5DEB3', 'beige': '#F5F5DC',
    'ivory': '#FFFFF0', 'linen': '#FAF0E6',
    'crimson': '#DC143C', 'indigo': '#4B0082',
}


def resolve_color(color_str: str) -> Optional[str]:
    """Resolve a PlantUML color to hex. Handles #hex, #NamedColor, and bare names."""
    if not color_str:
        return None
    color_str = color_str.strip().lstrip('#')
    # Already hex?
    if re.match(r'^[0-9a-fA-F]{3,8}$', color_str):
        return f'#{color_str}'
    # Named color?
    return NAMED_COLORS.get(color_str.lower())


# ─── Data structures ───────────────────────────────────────────────

@dataclass
class PumlParticipant:
    alias: str
    label: str
    color: Optional[str] = None


@dataclass
class PumlMessage:
    src: str
    dst: str
    label: str = ""
    line_style: str = "solid"   # solid, dashed, dotted
    arrow_end: bool = True
    arrow_start: bool = False


@dataclass
class PumlNode:
    id: str
    label: str
    shape: str = "rectangle"   # rectangle, database, cloud, actor, component, interface
    color: Optional[str] = None
    parent_group: Optional[str] = None


@dataclass
class PumlEdge:
    src: str
    dst: str
    label: str = ""
    line_style: str = "solid"
    arrow_end: bool = True
    arrow_start: bool = False


@dataclass
class PumlGroup:
    id: str
    label: str
    children: List[str] = field(default_factory=list)


@dataclass
class PumlClass:
    name: str
    stereotype: str = ""        # interface, abstract, enum
    members: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)


@dataclass
class PumlRelation:
    src: str
    dst: str
    rel_type: str = "association"  # extends, implements, association, composition, aggregation, dependency
    label: str = ""


# ─── Diagram type detection ───────────────────────────────────────

def detect_diagram_type(content: str) -> str:
    """Detect PlantUML diagram type from content."""
    lines = content.strip().split('\n')
    text = content.lower()

    # Sequence indicators
    seq_patterns = [r'participant\s', r'actor\s+\w+\s', r'\w+\s*-+>+\s*\w+\s*:']
    if any(re.search(p, content, re.IGNORECASE) for p in seq_patterns):
        # But if it also has class/package, might be something else
        if 'class ' not in text and 'package ' not in text:
            return 'sequence'

    # Class indicators
    if re.search(r'\bclass\s+\w+', content, re.IGNORECASE) or re.search(r'\binterface\s+\w+', content, re.IGNORECASE):
        return 'class'

    # State indicators
    if '[*] -->' in content or 'state ' in text:
        return 'state'

    # Component/deployment (default for structured diagrams)
    if any(kw in text for kw in ['package ', 'component ', 'node ', 'folder ', 'cloud ', 'database ']):
        return 'component'

    # Activity
    if re.search(r':[\w\s]+;', content) or ('start' in text and 'stop' in text):
        return 'activity'

    return 'component'  # default


# ─── Arrow parsing ────────────────────────────────────────────────

@dataclass
class ParsedArrow:
    style: str = "solid"        # solid, dashed, dotted, thick
    has_start: bool = False     # < on the left
    has_end: bool = True        # > on the right
    color: Optional[str] = None # extracted from -[#color]>
    lost: bool = False          # ->x lost message
    activate: int = 0           # +1 = activate, -1 = deactivate (from ++/--)


def parse_arrow(arrow: str) -> ParsedArrow:
    """
    Parse a PlantUML arrow string comprehensively.
    
    PlantUML arrow syntax (all forms):
      ->    solid forward            <->   solid bidirectional
      -->   dashed forward           <-->  dashed bidirectional
      ..>   dotted forward           <..>  dotted bidirectional
      ==>   thick forward            <==>  thick bidirectional
      --    dashed no arrow           ..   dotted no arrow
      -     solid no arrow
      -[#red]>  colored arrow
      ->++  activate target          -->-- deactivate target
      ->x   lost message             ->o   endpoint
    """
    arrow = arrow.strip()
    result = ParsedArrow()

    # Extract color: -[#red]> or -[#FF0000]>
    color_match = re.search(r'\[#([^\]]+)\]', arrow)
    if color_match:
        result.color = resolve_color(color_match.group(1))
        # Remove color from arrow for further parsing
        arrow = re.sub(r'\[#[^\]]+\]', '', arrow)

    # Check for activation markers at the end: ++, --
    # But only if the arrow has a head (> or x) before the ++/--
    # Otherwise bare '--' would be misdetected as deactivation
    if re.search(r'[>x]\+\+$', arrow):
        result.activate = 1
        arrow = arrow[:-2]
    elif re.search(r'[>x]--$', arrow):
        result.activate = -1
        arrow = arrow[:-2]

    # Check for lost message: ->x, -->x, ->>x
    if arrow.endswith('x') and re.search(r'[-.>=]x$', arrow):
        result.lost = True
        result.has_end = False
        arrow = arrow[:-1]

    # Check for endpoint: ->o, -->o
    if arrow.endswith('o') and re.search(r'[-.>=]o$', arrow):
        arrow = arrow[:-1]  # strip it, treat as normal arrow

    # Arrow heads
    result.has_start = arrow.startswith('<')
    if not result.lost:
        result.has_end = arrow.endswith('>')

    # Remove arrow heads for style detection
    core = arrow.lstrip('<').rstrip('>')

    # Detect style from the core shaft
    if '==' in core:
        result.style = 'thick'
    elif '..' in core:
        result.style = 'dotted'
    elif len(core) >= 2 and re.match(r'^-+$', core):
        # Two or more dashes = dashed (e.g. -- or ---)
        result.style = 'dashed'
    elif '-' in core:
        result.style = 'solid'
    else:
        result.style = 'solid'

    return result


def arrow_to_mermaid_flowchart(parsed: ParsedArrow) -> str:
    """Convert parsed arrow to Mermaid flowchart arrow syntax."""
    style = parsed.style
    if style in ('dashed', 'dotted'):
        if parsed.has_start and parsed.has_end:
            return '<-.->'
        elif parsed.has_start:
            return '<-.-'
        elif parsed.has_end:
            return '-.->'
        else:
            return '-.-'
    elif style == 'thick':
        if parsed.has_start and parsed.has_end:
            return '<==>'
        elif parsed.has_start:
            return '<=='
        elif parsed.has_end:
            return '==>'
        else:
            return '==='
    else:  # solid
        if parsed.has_start and parsed.has_end:
            return '<-->'
        elif parsed.has_start:
            return '<--'
        elif parsed.has_end:
            return '-->'
        else:
            return '---'


def arrow_to_mermaid_sequence(parsed: ParsedArrow) -> str:
    """
    Convert parsed arrow to Mermaid sequence diagram arrow syntax.
    
    Mermaid sequence arrows:
      ->>   solid with arrowhead (synchronous request)
      -->>  dashed with arrowhead (async/return)
      ->>+  activate target
      -->>- deactivate target
      ->    solid without arrowhead (open arrow)
      -->   dashed without arrowhead
      -x    cross (lost/destroy)
      --x   dashed cross
    """
    # Base arrow
    if parsed.lost:
        return '--x' if parsed.style == 'dashed' else '-x'

    if parsed.style in ('dashed', 'dotted'):
        base = '-->>' if parsed.has_end else '-->'
    else:
        base = '->>' if parsed.has_end else '->'

    # Activation suffix
    if parsed.activate == 1:
        base += '+'
    elif parsed.activate == -1:
        base += '-'

    return base


# ─── Sequence diagram conversion ─────────────────────────────────

# Regex for PlantUML sequence message arrows:
# Matches arrows like: ->, -->, ..>, ==>, <->, -[#red]>, ->++, ->x, etc.
_SEQ_ARROW_RE = re.compile(
    r'[<]?'                     # optional left head
    r'(?:-+|\.\.|==)'           # shaft
    r'(?:\[#[^\]]+\])?'         # optional color [#hex]
    r'(?:-+|\.\.|==)?'          # optional continued shaft
    r'[>]?[>]?'                 # optional right head (one or two >)
    r'[xo]?'                    # optional lost/endpoint marker
    r'(?:\+\+|--)?'             # optional activation ++/--
)


def convert_sequence(content: str) -> str:
    """
    Convert PlantUML sequence diagram to Mermaid.
    
    Handles:
    - participant / actor declarations with colors
    - All message arrow styles (solid, dashed, dotted, thick)
    - Activation bars: activate/deactivate, ++/-- on arrows
    - Colored arrows: -[#red]>
    - All fragment types: alt/else, opt, loop, break, critical, par, group, ref
    - Multi-line notes: note left/right/over ... end note
    - Single-line notes
    - Return keyword
    - Create / destroy participant
    - Box grouping: box "Label" ... end box
    - Title
    - Dividers: == Section ==
    - Autonumber
    - skinparam color extraction (for legend)
    """
    lines_out = ['sequenceDiagram']
    participants: Dict[str, str] = {}   # alias -> label
    color_legend: Dict[str, str] = {}
    arrow_color_legend: Dict[str, str] = {}
    in_multiline_note = False
    note_buffer: List[str] = []
    note_header = ''
    in_skinparam = False
    skinparam_depth = 0

    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        i += 1

        # Skip empty lines, comments, @startuml/@enduml
        if not line or line.startswith('@'):
            continue

        # PlantUML single-line comment
        if line.startswith("'"):
            continue

        # PlantUML block comment /' ... '/
        if line.startswith("/'"):
            while i < len(lines) and "'/" not in lines[i - 1]:
                i += 1
            continue

        # ─── Multi-line note handling ────────────────────
        if in_multiline_note:
            if re.match(r'end\s*note', line, re.IGNORECASE):
                # Emit the accumulated note
                note_text = '<br/>'.join(note_buffer)
                lines_out.append(f'    {note_header}{note_text}')
                in_multiline_note = False
                note_buffer = []
                note_header = ''
            else:
                note_buffer.append(line)
            continue

        # ─── skinparam block (extract colors for legend, skip the rest) ──
        if in_skinparam:
            if '{' in line:
                skinparam_depth += 1
            if '}' in line:
                skinparam_depth -= 1
                if skinparam_depth <= 0:
                    in_skinparam = False
            # Extract color info for legend
            m = re.match(r'(\w+)\s+(#\w+)', line)
            if m:
                prop, color = m.group(1), m.group(2)
                hex_c = resolve_color(color)
                if hex_c:
                    color_legend[hex_c] = f'skinparam {prop}'
            continue

        if re.match(r'skinparam\s+', line, re.IGNORECASE):
            if '{' in line:
                in_skinparam = True
                skinparam_depth = 1
            # Extract inline skinparam color
            m = re.match(r'skinparam\s+\w+\s+(#\w+)', line, re.IGNORECASE)
            if m:
                hex_c = resolve_color(m.group(1))
                if hex_c:
                    color_legend[hex_c] = 'skinparam'
            continue

        # ─── Title ───────────────────────────────────────
        m = re.match(r'title\s+(.*)', line, re.IGNORECASE)
        if m:
            # Mermaid doesn't have sequence title; emit as comment
            lines_out.insert(1, f'    %% Title: {m.group(1).strip()}')
            continue

        # ─── Autonumber ─────────────────────────────────
        if re.match(r'autonumber', line, re.IGNORECASE):
            lines_out.append('    autonumber')
            continue

        # ─── Divider: == Section == ──────────────────────
        m = re.match(r'==\s*(.*?)\s*==', line)
        if m:
            # Mermaid uses rect blocks or notes for dividers; use a note-style break
            divider_text = m.group(1).strip() or 'Section'
            lines_out.append(f'    Note over {_first_participant(participants)}: --- {divider_text} ---')
            continue

        # ─── Box grouping: box "Label" #color ... end box ──
        m = re.match(r'box\s+"?([^"]*?)"?\s*(?:#(\w+))?\s*$', line, re.IGNORECASE)
        if m:
            box_label, box_color = m.group(1).strip(), m.group(2)
            lines_out.append(f'    box {box_label}')
            if box_color:
                hex_c = resolve_color(box_color)
                if hex_c:
                    color_legend[hex_c] = f'Box: {box_label}'
            continue

        if re.match(r'end\s*box', line, re.IGNORECASE):
            lines_out.append('    end')
            continue

        # ─── Create participant ──────────────────────────
        m = re.match(r'create\s+(?:participant|actor|entity|boundary|control|database|collections|queue)?\s*"?([^"]*?)"?\s*(?:as\s+(\w+))?\s*$', line, re.IGNORECASE)
        if m:
            label = m.group(1).strip()
            alias = m.group(2) or re.sub(r'[^a-zA-Z0-9]', '', label)
            if alias not in participants:
                participants[alias] = label or alias
                lines_out.append(f'    create participant {alias} as {label or alias}')
            continue

        # ─── Destroy participant ─────────────────────────
        m = re.match(r'destroy\s+(\w+)', line, re.IGNORECASE)
        if m:
            target = m.group(1)
            lines_out.append(f'    destroy {target}')
            continue

        # ─── Participant / actor / entity / boundary / control / database / collections / queue ──
        m = re.match(
            r'(?:participant|actor|entity|boundary|control|database|collections|queue)\s+'
            r'"([^"]+)"\s+as\s+(\w+)(?:\s+(?:<<[^>]+>>))?\s*(?:#(\w+))?\s*$',
            line, re.IGNORECASE
        )
        if m:
            label, alias, color = m.group(1), m.group(2), m.group(3)
            participants[alias] = label
            # Mermaid: actor uses different keyword
            keyword = 'actor' if line.strip().lower().startswith('actor') else 'participant'
            lines_out.append(f'    {keyword} {alias} as {label}')
            if color:
                hex_color = resolve_color(color)
                if hex_color:
                    color_legend[hex_color] = f'{label} ({alias})'
            continue

        # Participant without "as" alias
        m = re.match(
            r'(?:participant|actor|entity|boundary|control|database|collections|queue)\s+'
            r'"?([^"#]+?)"?\s*(?:#(\w+))?\s*$',
            line, re.IGNORECASE
        )
        if m:
            name = m.group(1).strip()
            color = m.group(2)
            alias = re.sub(r'[^a-zA-Z0-9]', '', name)
            participants[alias] = name
            participants[name] = name
            keyword = 'actor' if line.strip().lower().startswith('actor') else 'participant'
            lines_out.append(f'    {keyword} {alias} as {name}')
            if color:
                hex_color = resolve_color(color)
                if hex_color:
                    color_legend[hex_color] = name
            continue

        # ─── Activate / deactivate standalone ────────────
        m = re.match(r'activate\s+(\w+)(?:\s+#(\w+))?', line, re.IGNORECASE)
        if m:
            target, color = m.group(1), m.group(2)
            lines_out.append(f'    activate {target}')
            if color:
                hex_c = resolve_color(color)
                if hex_c:
                    color_legend[hex_c] = f'{target} activation'
            continue

        m = re.match(r'deactivate\s+(\w+)', line, re.IGNORECASE)
        if m:
            lines_out.append(f'    deactivate {m.group(1)}')
            continue

        # ─── Return keyword ──────────────────────────────
        m = re.match(r'return\s+(.*)', line, re.IGNORECASE)
        if m:
            # Mermaid doesn't have 'return'; emit as a dashed reply
            # We need to know the last caller, but we can't always track that
            # Emit as a comment with note
            lines_out.append(f'    %% return {m.group(1).strip()}')
            continue

        # ─── Multi-line note start ───────────────────────
        m = re.match(
            r'note\s+(left|right|over)\s+(?:of\s+)?(\w+(?:\s*,\s*\w+)?)\s*$',
            line, re.IGNORECASE
        )
        if m:
            pos, targets = m.group(1), m.group(2)
            pos_map = {'left': 'left of', 'right': 'right of', 'over': 'over'}
            mm_pos = pos_map.get(pos.lower(), 'right of')
            note_header = f'Note {mm_pos} {targets}: '
            in_multiline_note = True
            note_buffer = []
            continue

        # ─── Single-line note ────────────────────────────
        m = re.match(
            r'note\s+(left|right|over)\s+(?:of\s+)?(\w+(?:\s*,\s*\w+)?)\s*:\s*(.*)',
            line, re.IGNORECASE
        )
        if m:
            pos, targets, text = m.group(1), m.group(2), m.group(3).strip()
            pos_map = {'left': 'left of', 'right': 'right of', 'over': 'over'}
            mm_pos = pos_map.get(pos.lower(), 'right of')
            # Convert PlantUML \n to Mermaid <br/>
            text = text.replace('\\n', '<br/>')
            lines_out.append(f'    Note {mm_pos} {targets}: {text}')
            continue

        # ─── hnote / rnote (hexagonal/rectangle note) ───
        m = re.match(
            r'[hr]note\s+(?:over\s+)?(\w+(?:\s*,\s*\w+)?)\s*:\s*(.*)',
            line, re.IGNORECASE
        )
        if m:
            targets, text = m.group(1), m.group(2).strip()
            lines_out.append(f'    Note over {targets}: {text}')
            continue

        # ─── Ref over (standalone single-line) ────────────
        # Must check BEFORE generic fragment handler since "ref" is also a fragment keyword
        m = re.match(r'ref\s+over\s+(\w+(?:\s*,\s*\w+)*)\s*:\s*(.*)', line, re.IGNORECASE)
        if m:
            targets, text = m.group(1), m.group(2).strip()
            lines_out.append(f'    rect rgb(240, 240, 240)')
            lines_out.append(f'        Note over {targets}: ref: {text}')
            lines_out.append(f'    end')
            continue

        # ─── Fragment blocks: alt, else, opt, loop, break, critical, par, group, ref ──
        m = re.match(r'(alt|opt|loop|break|critical|par|group|ref)\s+(.*)', line, re.IGNORECASE)
        if m:
            keyword, label = m.group(1).lower(), m.group(2).strip()
            # Mermaid supports: alt, else, opt, loop, critical, break, par, rect
            mm_keyword_map = {
                'alt': 'alt',
                'opt': 'opt',
                'loop': 'loop',
                'break': 'break',
                'critical': 'critical',
                'par': 'par',
                'group': 'rect',   # Mermaid uses rect for generic grouping
                'ref': 'rect',     # ref block → rect with label
            }
            mm_kw = mm_keyword_map.get(keyword, 'rect')
            if keyword == 'ref':
                lines_out.append(f'    rect rgb(240, 240, 240)')
                lines_out.append(f'        Note over {_first_participant(participants)}: ref: {label}')
            else:
                lines_out.append(f'    {mm_kw} {label}')
            continue

        m = re.match(r'else\s*(.*)', line, re.IGNORECASE)
        if m:
            label = m.group(1).strip()
            lines_out.append(f'    else {label}')
            continue

        # ─── "and" in par fragment ──
        m = re.match(r'and\s*(.*)', line, re.IGNORECASE)
        if m:
            # Mermaid par uses "and" as well
            lines_out.append(f'    and {m.group(1).strip()}')
            continue

        if re.match(r'^end\s*$', line, re.IGNORECASE):
            lines_out.append('    end')
            continue

        # ─── Message: A -> B : label (comprehensive arrow parsing) ──
        # PlantUML message arrows can be:
        #   A -> B      A --> B      A ..> B      A ==> B
        #   A ->> B     A -[#red]> B
        #   A ->++ B    A -->-- B    (activate/deactivate)
        #   A <-> B     A <--> B    (bidirectional)
        #   A ->x B     (lost message)
        #   A ->o B     (endpoint)
        m = re.match(
            r'^(\w+)\s+'                              # source
            r'(<?'                                    # optional left head
            r'(?:-+|\.\.|==)'                         # shaft: dashes, dots, or equals
            r'(?:\[#[^\]]+\])?'                       # optional color [#hex]
            r'(?:-+|\.\.|==)?'                        # optional continued shaft
            r'(?:[>])?'                               # optional > head
            r'(?:[>])?'                               # optional second > (for ->>)
            r'(?:[xo])?'                              # optional lost/endpoint marker
            r'(?:\+\+|--)?'                           # optional activation ++/--
            r')\s+'                                   # end of arrow
            r'(\w+)'                                  # destination
            r'(?:\s*:\s*(.*))?$',                     # optional label
            line
        )
        if m:
            src, arrow_str, dst, label = m.group(1), m.group(2), m.group(3), (m.group(4) or '').strip()

            # Auto-register participants
            for p in (src, dst):
                if p not in participants:
                    participants[p] = p

            parsed = parse_arrow(arrow_str)
            mm_arrow = arrow_to_mermaid_sequence(parsed)

            # Colored arrow → add to legend
            if parsed.color:
                arrow_color_legend[parsed.color] = label or f'{src} → {dst}'

            # Bidirectional: emit request + return
            if parsed.has_start and parsed.has_end:
                lines_out.append(f'    {src}->>+{dst}: {label}')
                lines_out.append(f'    {dst}-->>-{src}: (return)')
                continue

            label_part = f': {label}' if label else ':'
            lines_out.append(f'    {src}{mm_arrow}{dst}{label_part}')
            continue


        # ─── Delay: ... or ...text... ────────────────────
        m = re.match(r'\.\.\.(.*)\.\.\.', line)
        if m:
            delay_text = m.group(1).strip()
            lines_out.append(f'    Note over {_first_participant(participants)}: ⏳ {delay_text or "delay"}')
            continue

        if line == '...':
            lines_out.append(f'    Note over {_first_participant(participants)}: ⏳ delay')
            continue

    # ─── Color / style legend ────────────────────────────
    has_legend = color_legend or arrow_color_legend
    if has_legend:
        lines_out.append('')
        lines_out.append('    %% Visual Legend:')

    if color_legend:
        lines_out.append('    %% Participant Colors (from PlantUML):')
        for hex_c, meaning in color_legend.items():
            lines_out.append(f'    %%   {hex_c} = {meaning}')
        lines_out.append('    %% Note: Mermaid sequenceDiagram has limited color support.')
        lines_out.append('    %% Colors documented here for downstream rules-extraction agents.')

    if arrow_color_legend:
        lines_out.append('    %% Arrow Colors (from PlantUML):')
        for hex_c, meaning in arrow_color_legend.items():
            lines_out.append(f'    %%   {hex_c} arrow = {meaning}')

    return '\n'.join(lines_out)


def _first_participant(participants: Dict[str, str]) -> str:
    """Get the first participant alias, or a fallback."""
    if participants:
        return next(iter(participants.keys()))
    return 'A'


# ─── Component / deployment diagram conversion ───────────────────

def convert_component(content: str) -> str:
    """Convert PlantUML component/deployment diagram to Mermaid flowchart."""
    nodes: Dict[str, PumlNode] = {}
    edges: List[PumlEdge] = []
    groups: Dict[str, PumlGroup] = {}
    color_legend: Dict[str, str] = {}
    current_group: Optional[str] = None
    group_stack: List[Optional[str]] = []

    def safe_id(name: str) -> str:
        sid = re.sub(r'[^a-zA-Z0-9_]', '_', name).strip('_')[:25]
        if not sid or sid[0].isdigit():
            sid = f'n_{sid}'
        return sid

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        # Group start: package, node, folder, cloud, rectangle
        m = re.match(r'(package|node|folder|cloud|rectangle|frame)\s+"?([^"{]*)"?\s*(?:as\s+(\w+))?\s*(?:#(\w+))?\s*\{', line, re.IGNORECASE)
        if m:
            kind, label, alias, color = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
            gid = alias or safe_id(label)
            groups[gid] = PumlGroup(id=gid, label=label)
            group_stack.append(current_group)
            current_group = gid
            if color:
                hex_c = resolve_color(color)
                if hex_c:
                    color_legend[hex_c] = f'{label} ({kind})'
            continue

        # Group end
        if line == '}':
            if group_stack:
                current_group = group_stack.pop()
            continue

        # Component: [Name] or component "Name" as alias
        # Must end at line boundary to avoid matching edge lines like [A] --> [B]
        m = re.match(r'\[([^\]]+)\]\s*(?:as\s+(\w+))?\s*(?:#(\w+))?\s*$', line)
        if m:
            label, alias, color = m.group(1).strip(), m.group(2), m.group(3)
            nid = alias or safe_id(label)
            node = PumlNode(id=nid, label=label, shape='rectangle', parent_group=current_group)
            if color:
                node.color = resolve_color(color)
                if node.color:
                    color_legend[node.color] = label
            nodes[nid] = node
            if current_group and current_group in groups:
                groups[current_group].children.append(nid)
            continue

        m = re.match(r'(?:component|database|cloud|actor|interface)\s+"?([^"]*?)"?\s*(?:as\s+(\w+))?\s*(?:#(\w+))?$', line, re.IGNORECASE)
        if m:
            kind_match = re.match(r'(\w+)', line, re.IGNORECASE)
            kind = kind_match.group(1).lower() if kind_match else 'rectangle'
            label, alias, color = m.group(1).strip(), m.group(2), m.group(3)
            nid = alias or safe_id(label)
            shape_map = {'database': 'database', 'actor': 'circle', 'interface': 'circle'}
            node = PumlNode(id=nid, label=label, shape=shape_map.get(kind, 'rectangle'), parent_group=current_group)
            if color:
                node.color = resolve_color(color)
                if node.color:
                    color_legend[node.color] = label
            nodes[nid] = node
            if current_group and current_group in groups:
                groups[current_group].children.append(nid)
            continue

        # Edge: A --> B : label  or  [A] --> [B] : label
        m = re.match(r'(?:\[([^\]]+)\]|(\w+))\s*([<]?[-=.]+[>]?)\s*(?:\[([^\]]+)\]|(\w+))(?:\s*:\s*(.*))?', line)
        if m:
            src_bracket, src_word = m.group(1), m.group(2)
            dst_bracket, dst_word = m.group(4), m.group(5)
            arrow_str = m.group(3)
            label = (m.group(6) or '').strip()

            src_name = src_bracket or src_word
            dst_name = dst_bracket or dst_word

            if not src_name or not dst_name:
                continue

            src_id = safe_id(src_name)
            dst_id = safe_id(dst_name)

            # Auto-create nodes if they don't exist
            if src_id not in nodes:
                nodes[src_id] = PumlNode(id=src_id, label=src_name)
            if dst_id not in nodes:
                nodes[dst_id] = PumlNode(id=dst_id, label=dst_name)

            parsed = parse_arrow(arrow_str)
            edges.append(PumlEdge(
                src=src_id, dst=dst_id, label=label,
                line_style=parsed.style, arrow_start=parsed.has_start, arrow_end=parsed.has_end
            ))
            continue

    # Generate Mermaid
    lines_out = ['flowchart TB']

    # classDef for colors
    color_classes: Dict[str, str] = {}
    for node in nodes.values():
        if node.color and node.color not in color_classes:
            cls_name = f'color{len(color_classes)}'
            color_classes[node.color] = cls_name

    for hex_c, cls_name in color_classes.items():
        lines_out.append(f'    classDef {cls_name} fill:{hex_c},stroke:{hex_c},color:#FFFFFF')

    # Subgraphs
    grouped_ids = set()
    for gid, group in groups.items():
        if group.children:
            safe_label = re.sub(r'[^a-zA-Z0-9_]', '_', group.label)
            lines_out.append(f'    subgraph {safe_label}["{group.label}"]')
            for child_id in group.children:
                if child_id in nodes:
                    node = nodes[child_id]
                    node_str = _format_node(node)
                    cls = color_classes.get(node.color, '')
                    if cls:
                        node_str += f':::{cls}'
                    lines_out.append(f'        {node_str}')
                    grouped_ids.add(child_id)
            lines_out.append('    end')

    # Ungrouped nodes
    for nid, node in nodes.items():
        if nid not in grouped_ids:
            node_str = _format_node(node)
            cls = color_classes.get(node.color, '')
            if cls:
                node_str += f':::{cls}'
            lines_out.append(f'    {node_str}')

    # Edges
    for edge in edges:
        mm_arrow = arrow_to_mermaid_flowchart(ParsedArrow(
            style=edge.line_style, has_start=edge.arrow_start, has_end=edge.arrow_end
        ))
        if edge.label:
            lines_out.append(f'    {edge.src} {mm_arrow}|"{edge.label}"| {edge.dst}')
        else:
            lines_out.append(f'    {edge.src} {mm_arrow} {edge.dst}')

    # Color legend
    if color_legend:
        lines_out.append('')
        lines_out.append('    %% Visual Legend:')
        lines_out.append('    %% Colors:')
        for hex_c, meaning in color_legend.items():
            lines_out.append(f'    %%   {hex_c} = {meaning}')

    # Line style legend
    styles_used = set(e.line_style for e in edges)
    bidir_used = any(e.arrow_start and e.arrow_end for e in edges)
    if len(styles_used) > 1 or bidir_used:
        lines_out.append('    %% Line Styles:')
        if 'solid' in styles_used:
            lines_out.append('    %%   Solid (-->) = Synchronous / confirmed dependency')
        if 'dashed' in styles_used:
            lines_out.append('    %%   Dashed (-.->) = Async / optional / return')
        if 'thick' in styles_used:
            lines_out.append('    %%   Thick (==>) = Critical / primary path')
        if bidir_used:
            lines_out.append('    %%   Bidirectional (<-->) = Mutual dependency')

    return '\n'.join(lines_out)


def _format_node(node: PumlNode) -> str:
    """Format a node with the correct Mermaid shape."""
    nid = node.id
    label = node.label
    shape_map = {
        'rectangle': f'{nid}["{label}"]',
        'database': f'{nid}[("{label}")]',
        'circle': f'{nid}(("{label}"))',
        'stadium': f'{nid}(["{label}"])',
    }
    return shape_map.get(node.shape, f'{nid}["{label}"]')


# ─── Class diagram conversion ────────────────────────────────────

def convert_class(content: str) -> str:
    """Convert PlantUML class diagram to Mermaid classDiagram."""
    classes: Dict[str, PumlClass] = {}
    relations: List[PumlRelation] = []
    current_class: Optional[str] = None

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        # Class/interface/enum/abstract declaration with body start
        m = re.match(r'(?:(abstract)\s+)?(?:class|interface|enum)\s+"?(\w+)"?\s*(?:<<(\w+)>>)?\s*\{', line, re.IGNORECASE)
        if m:
            abstract, name, stereo = m.group(1), m.group(2), m.group(3)
            kind = 'interface' if 'interface' in line.lower() else ('enum' if 'enum' in line.lower() else '')
            if abstract:
                kind = 'abstract'
            if stereo:
                kind = stereo.lower()
            classes[name] = PumlClass(name=name, stereotype=kind)
            current_class = name
            continue

        # Class declaration without body
        m = re.match(r'(?:(abstract)\s+)?(?:class|interface|enum)\s+"?(\w+)"?\s*(?:<<(\w+)>>)?$', line, re.IGNORECASE)
        if m:
            abstract, name, stereo = m.group(1), m.group(2), m.group(3)
            kind = 'interface' if 'interface' in line.lower() else ('enum' if 'enum' in line.lower() else '')
            if abstract:
                kind = 'abstract'
            if stereo:
                kind = stereo.lower()
            classes[name] = PumlClass(name=name, stereotype=kind)
            continue

        # End of class body
        if line == '}':
            current_class = None
            continue

        # Class member (inside { })
        if current_class and current_class in classes:
            if '(' in line and ')' in line:
                classes[current_class].methods.append(line)
            elif line not in ('{', '}', '--', '==', '..'):
                classes[current_class].members.append(line)
            continue

        # Relations: A --|> B, A ..> B, A *-- B, etc.
        m = re.match(r'(\w+)\s+([<>|.*o#x+\-]+)\s+(\w+)(?:\s*:\s*(.*))?', line)
        if m:
            src, arrow, dst, label = m.group(1), m.group(2), m.group(3), (m.group(4) or '').strip()
            rel = _classify_class_relation(arrow)
            relations.append(PumlRelation(src=src, dst=dst, rel_type=rel, label=label))

            # Auto-create classes
            if src not in classes:
                classes[src] = PumlClass(name=src)
            if dst not in classes:
                classes[dst] = PumlClass(name=dst)
            continue

    # Generate Mermaid
    lines_out = ['classDiagram']

    for cls in classes.values():
        lines_out.append(f'    class {cls.name} {{')
        if cls.stereotype:
            lines_out.append(f'        <<{cls.stereotype}>>')
        for member in cls.members:
            lines_out.append(f'        {member}')
        for method in cls.methods:
            lines_out.append(f'        {method}')
        lines_out.append('    }')
        lines_out.append('')

    for rel in relations:
        mm_rel = _relation_to_mermaid(rel.rel_type)
        label_part = f' : {rel.label}' if rel.label else ''
        lines_out.append(f'    {rel.src} {mm_rel} {rel.dst}{label_part}')

    return '\n'.join(lines_out)


def _classify_class_relation(arrow: str) -> str:
    """Classify a PlantUML class relation arrow."""
    if '|>' in arrow or '<|' in arrow:
        if '..' in arrow:
            return 'implements'
        return 'extends'
    if '*' in arrow:
        return 'composition'
    if 'o' in arrow:
        return 'aggregation'
    if '..' in arrow:
        return 'dependency'
    return 'association'


def _relation_to_mermaid(rel_type: str) -> str:
    """Convert relation type to Mermaid class diagram arrow."""
    return {
        'extends': '<|--',
        'implements': '<|..',
        'composition': '*--',
        'aggregation': 'o--',
        'dependency': '<..',
        'association': '<--',
    }.get(rel_type, '<--')


# ─── State diagram conversion ────────────────────────────────────

def convert_state(content: str) -> str:
    """Convert PlantUML state diagram to Mermaid stateDiagram-v2."""
    lines_out = ['stateDiagram-v2']

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        # State declaration
        m = re.match(r'state\s+"?([^"]+?)"?\s+as\s+(\w+)', line, re.IGNORECASE)
        if m:
            label, alias = m.group(1), m.group(2)
            lines_out.append(f'    {alias} : {label}')
            continue

        # Transition: A --> B : label
        m = re.match(r'(\[?\*?\]?|\w+)\s*-+>\s*(\[?\*?\]?|\w+)(?:\s*:\s*(.*))?', line)
        if m:
            src, dst, label = m.group(1), m.group(2), (m.group(3) or '').strip()
            # [*] maps to [*] in Mermaid too
            label_part = f' : {label}' if label else ''
            lines_out.append(f'    {src} --> {dst}{label_part}')
            continue

    return '\n'.join(lines_out)


# ─── AST conversion helpers ───────────────────────────────────────

def _parse_component_data(content: str) -> Tuple[Dict[str, PumlNode], List[PumlEdge], Dict[str, PumlGroup]]:
    """Parse component/deployment PlantUML into intermediate structures."""
    nodes: Dict[str, PumlNode] = {}
    edges: List[PumlEdge] = []
    groups: Dict[str, PumlGroup] = {}
    current_group: Optional[str] = None
    group_stack: List[Optional[str]] = []

    def safe_id(name: str) -> str:
        sid = re.sub(r'[^a-zA-Z0-9_]', '_', name).strip('_')[:25]
        if not sid or sid[0].isdigit():
            sid = f'n_{sid}'
        return sid

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        m = re.match(r'(package|node|folder|cloud|rectangle|frame)\s+"?([^"{]*)"?\s*(?:as\s+(\w+))?\s*(?:#(\w+))?\s*\{', line, re.IGNORECASE)
        if m:
            kind, label, alias, color = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
            gid = alias or safe_id(label)
            groups[gid] = PumlGroup(id=gid, label=label)
            group_stack.append(current_group)
            current_group = gid
            continue

        if line == '}':
            if group_stack:
                current_group = group_stack.pop()
            continue

        m = re.match(r'\[([^\]]+)\]\s*(?:as\s+(\w+))?\s*(?:#(\w+))?\s*$', line)
        if m:
            label, alias, color = m.group(1).strip(), m.group(2), m.group(3)
            nid = alias or safe_id(label)
            node = PumlNode(id=nid, label=label, shape='rectangle', parent_group=current_group)
            if color:
                node.color = resolve_color(color)
            nodes[nid] = node
            if current_group and current_group in groups:
                groups[current_group].children.append(nid)
            continue

        m = re.match(r'(?:component|database|cloud|actor|interface)\s+"?([^"]*?)"?\s*(?:as\s+(\w+))?\s*(?:#(\w+))?$', line, re.IGNORECASE)
        if m:
            kind_match = re.match(r'(\w+)', line, re.IGNORECASE)
            kind = kind_match.group(1).lower() if kind_match else 'rectangle'
            label, alias, color = m.group(1).strip(), m.group(2), m.group(3)
            nid = alias or safe_id(label)
            shape_map = {'database': 'database', 'actor': 'circle', 'interface': 'circle'}
            node = PumlNode(id=nid, label=label, shape=shape_map.get(kind, 'rectangle'), parent_group=current_group)
            if color:
                node.color = resolve_color(color)
            nodes[nid] = node
            if current_group and current_group in groups:
                groups[current_group].children.append(nid)
            continue

        m = re.match(r'(?:\[([^\]]+)\]|(\w+))\s*([<]?[-=.]+[>]?)\s*(?:\[([^\]]+)\]|(\w+))(?:\s*:\s*(.*))?', line)
        if m:
            src_name = m.group(1) or m.group(2)
            dst_name = m.group(4) or m.group(5)
            arrow_str = m.group(3)
            label = (m.group(6) or '').strip()
            if not src_name or not dst_name:
                continue
            src_id = safe_id(src_name)
            dst_id = safe_id(dst_name)
            if src_id not in nodes:
                nodes[src_id] = PumlNode(id=src_id, label=src_name)
            if dst_id not in nodes:
                nodes[dst_id] = PumlNode(id=dst_id, label=dst_name)
            parsed = parse_arrow(arrow_str)
            edges.append(PumlEdge(
                src=src_id, dst=dst_id, label=label,
                line_style=parsed.style, arrow_start=parsed.has_start, arrow_end=parsed.has_end
            ))
            continue

    return nodes, edges, groups


def _parse_class_data(content: str) -> Tuple[Dict[str, PumlClass], List[PumlRelation]]:
    """Parse class-diagram PlantUML into intermediate structures."""
    classes: Dict[str, PumlClass] = {}
    relations: List[PumlRelation] = []
    current_class: Optional[str] = None

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        m = re.match(r'(?:(abstract)\s+)?(?:class|interface|enum)\s+"?(\w+)"?\s*(?:<<(\w+)>>)?\s*\{', line, re.IGNORECASE)
        if m:
            abstract, name, stereo = m.group(1), m.group(2), m.group(3)
            kind = 'interface' if 'interface' in line.lower() else ('enum' if 'enum' in line.lower() else '')
            if abstract:
                kind = 'abstract'
            if stereo:
                kind = stereo.lower()
            classes[name] = PumlClass(name=name, stereotype=kind)
            current_class = name
            continue

        m = re.match(r'(?:(abstract)\s+)?(?:class|interface|enum)\s+"?(\w+)"?\s*(?:<<(\w+)>>)?$', line, re.IGNORECASE)
        if m:
            abstract, name, stereo = m.group(1), m.group(2), m.group(3)
            kind = 'interface' if 'interface' in line.lower() else ('enum' if 'enum' in line.lower() else '')
            if abstract:
                kind = 'abstract'
            if stereo:
                kind = stereo.lower()
            classes[name] = PumlClass(name=name, stereotype=kind)
            continue

        if line == '}':
            current_class = None
            continue

        if current_class and current_class in classes:
            if '(' in line and ')' in line:
                classes[current_class].methods.append(line)
            elif line not in ('{', '}', '--', '==', '..'):
                classes[current_class].members.append(line)
            continue

        m = re.match(r'(\w+)\s+([<>|.*o#x+\-]+)\s+(\w+)(?:\s*:\s*(.*))?', line)
        if m:
            src, arrow, dst, label = m.group(1), m.group(2), m.group(3), (m.group(4) or '').strip()
            rel = _classify_class_relation(arrow)
            relations.append(PumlRelation(src=src, dst=dst, rel_type=rel, label=label))
            if src not in classes:
                classes[src] = PumlClass(name=src)
            if dst not in classes:
                classes[dst] = PumlClass(name=dst)
            continue

    return classes, relations


def _parse_sequence_data(content: str) -> Tuple[Dict[str, str], List[dict]]:
    """Parse sequence-diagram PlantUML into participants and messages."""
    participants: Dict[str, str] = {}
    messages: List[dict] = []

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        m = re.match(
            r'(?:participant|actor|entity|boundary|control|database|collections|queue)\s+'
            r'"([^"]+)"\s+as\s+(\w+)', line, re.IGNORECASE)
        if m:
            participants[m.group(2)] = m.group(1)
            continue

        m = re.match(
            r'(?:participant|actor|entity|boundary|control|database|collections|queue)\s+'
            r'"?([^"#]+?)"?\s*(?:#\w+)?\s*$', line, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            alias = re.sub(r'[^a-zA-Z0-9]', '', name)
            participants[alias] = name
            participants[name] = name
            continue

        m = re.match(
            r'^(\w+)\s+'
            r'(<?(?:-+|\.\.|==)(?:\[#[^\]]+\])?(?:-+|\.\.|==)?(?:[>])?(?:[>])?(?:[xo])?(?:\+\+|--)?)\s+'
            r'(\w+)(?:\s*:\s*(.*))?$', line)
        if m:
            src, arrow_str, dst, label = m.group(1), m.group(2), m.group(3), (m.group(4) or '').strip()
            for p in (src, dst):
                if p not in participants:
                    participants[p] = p
            parsed = parse_arrow(arrow_str)
            messages.append({
                'src': src, 'dst': dst, 'label': label,
                'style': parsed.style,
                'arrow_start': parsed.has_start, 'arrow_end': parsed.has_end,
            })

    return participants, messages


def _parse_state_data(content: str) -> Tuple[Dict[str, str], List[dict]]:
    """Parse state-diagram PlantUML into states and transitions."""
    states: Dict[str, str] = {}
    transitions: List[dict] = []

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('@'):
            continue

        m = re.match(r'state\s+"?([^"]+?)"?\s+as\s+(\w+)', line, re.IGNORECASE)
        if m:
            states[m.group(2)] = m.group(1)
            continue

        m = re.match(r'(\[?\*?\]?|\w+)\s*-+>\s*(\[?\*?\]?|\w+)(?:\s*:\s*(.*))?', line)
        if m:
            src, dst, label = m.group(1), m.group(2), (m.group(3) or '').strip()
            transitions.append({'src': src, 'dst': dst, 'label': label})
            if src not in states and src != '[*]':
                states[src] = src
            if dst not in states and dst != '[*]':
                states[dst] = dst

    return states, transitions


def _component_data_to_ast(nodes: Dict[str, PumlNode], edges: List[PumlEdge],
                           groups: Dict[str, PumlGroup]) -> DiagramAST:
    """Map parsed component data to DiagramAST."""
    ast_nodes = [
        DiagramNode(
            id=n.id, label=n.label, shape=n.shape,
            fill_color=n.color, parent_group=n.parent_group,
        )
        for n in nodes.values()
    ]
    ast_edges = [
        DiagramEdge(
            id=f"edge_{i+1}", source=e.src, target=e.dst,
            label=e.label, style=e.line_style,
            arrow_start=e.arrow_start, arrow_end=e.arrow_end,
        )
        for i, e in enumerate(edges)
    ]
    ast_groups = [
        DiagramGroup(id=g.id, label=g.label, children=list(g.children))
        for g in groups.values()
    ]
    return DiagramAST(
        nodes=ast_nodes, edges=ast_edges, groups=ast_groups,
        diagram_type='flowchart', direction='TB',
        metadata={'source_format': 'plantuml', 'plantuml_type': 'component'},
    )


def _class_data_to_ast(classes: Dict[str, PumlClass],
                       relations: List[PumlRelation]) -> DiagramAST:
    """Map parsed class data to DiagramAST."""
    ast_nodes = [
        DiagramNode(
            id=c.name, label=c.name, shape='rectangle',
            metadata={
                'stereotype': c.stereotype,
                'members': list(c.members),
                'methods': list(c.methods),
            },
        )
        for c in classes.values()
    ]
    ast_edges = [
        DiagramEdge(
            id=f"rel_{i+1}", source=r.src, target=r.dst,
            label=r.label,
            metadata={'rel_type': r.rel_type},
        )
        for i, r in enumerate(relations)
    ]
    return DiagramAST(
        nodes=ast_nodes, edges=ast_edges, groups=[],
        diagram_type='class',
        metadata={'source_format': 'plantuml', 'plantuml_type': 'class'},
    )


def _sequence_data_to_ast(participants: Dict[str, str],
                          messages: List[dict]) -> DiagramAST:
    """Map parsed sequence data to DiagramAST."""
    seen = set()
    ast_nodes: List[DiagramNode] = []
    for alias, label in participants.items():
        if alias in seen:
            continue
        seen.add(alias)
        ast_nodes.append(DiagramNode(
            id=alias, label=label, shape='rectangle',
            metadata={'role': 'participant'},
        ))
    ast_edges = [
        DiagramEdge(
            id=f"msg_{i+1}", source=msg['src'], target=msg['dst'],
            label=msg.get('label', ''), style=msg.get('style', 'solid'),
            arrow_start=msg.get('arrow_start', False),
            arrow_end=msg.get('arrow_end', True),
        )
        for i, msg in enumerate(messages)
    ]
    return DiagramAST(
        nodes=ast_nodes, edges=ast_edges, groups=[],
        diagram_type='sequence',
        metadata={'source_format': 'plantuml', 'plantuml_type': 'sequence'},
    )


def _state_data_to_ast(states: Dict[str, str],
                       transitions: List[dict]) -> DiagramAST:
    """Map parsed state data to DiagramAST."""
    ast_nodes = [
        DiagramNode(id=sid, label=label, shape='rectangle')
        for sid, label in states.items()
    ]
    ast_edges = [
        DiagramEdge(
            id=f"trans_{i+1}", source=t['src'], target=t['dst'],
            label=t.get('label', ''),
        )
        for i, t in enumerate(transitions)
    ]
    return DiagramAST(
        nodes=ast_nodes, edges=ast_edges, groups=[],
        diagram_type='state',
        metadata={'source_format': 'plantuml', 'plantuml_type': 'state'},
    )


def convert_plantuml_to_ast(puml_content: str) -> DiagramAST:
    """Parse a PlantUML block and return a DiagramAST."""
    dtype = detect_diagram_type(puml_content)

    if dtype == 'component' or dtype == 'activity':
        nodes, edges, groups = _parse_component_data(puml_content)
        return _component_data_to_ast(nodes, edges, groups)
    elif dtype == 'class':
        classes, relations = _parse_class_data(puml_content)
        return _class_data_to_ast(classes, relations)
    elif dtype == 'sequence':
        participants, messages = _parse_sequence_data(puml_content)
        return _sequence_data_to_ast(participants, messages)
    elif dtype == 'state':
        states, transitions = _parse_state_data(puml_content)
        return _state_data_to_ast(states, transitions)
    else:
        nodes, edges, groups = _parse_component_data(puml_content)
        return _component_data_to_ast(nodes, edges, groups)


# ─── Main conversion entry point ─────────────────────────────────

def extract_plantuml_blocks(text: str) -> List[str]:
    """Extract PlantUML blocks from text (both @startuml and fenced code blocks)."""
    blocks = []

    # @startuml ... @enduml
    for m in re.finditer(r'@startuml\b.*?\n(.*?)@enduml', text, re.DOTALL | re.IGNORECASE):
        blocks.append(m.group(1))

    # ```plantuml ... ``` or ```puml ... ```
    for m in re.finditer(r'```(?:plantuml|puml)\s*\n(.*?)```', text, re.DOTALL | re.IGNORECASE):
        blocks.append(m.group(1))

    return blocks


def convert_plantuml_to_mermaid(puml_content: str) -> str:
    """
    Convert a single PlantUML diagram block to Mermaid.
    
    Returns Mermaid code wrapped in ```mermaid ... ``` fences.
    """
    diagram_type = detect_diagram_type(puml_content)

    converters = {
        'sequence': convert_sequence,
        'class': convert_class,
        'state': convert_state,
        'component': convert_component,
        'activity': convert_component,  # activity uses flowchart too
    }

    converter = converters.get(diagram_type, convert_component)
    mermaid_body = converter(puml_content)

    return f'```mermaid\n{mermaid_body}\n```'


def convert_file(input_path: Path) -> str:
    """Convert a PlantUML file or a Markdown file containing PlantUML blocks."""
    content = input_path.read_text(encoding='utf-8', errors='ignore')

    # If it's a pure .puml file
    if input_path.suffix.lower() in ('.puml', '.plantuml', '.pu', '.wsd'):
        # Strip @startuml/@enduml wrapper
        inner = re.sub(r'@startuml\b[^\n]*\n?', '', content, flags=re.IGNORECASE)
        inner = re.sub(r'@enduml\b[^\n]*', '', inner, flags=re.IGNORECASE)
        return convert_plantuml_to_mermaid(inner.strip())

    # If it's a Markdown file, replace blocks in-place
    blocks = extract_plantuml_blocks(content)
    if not blocks:
        print("  ⚠ No PlantUML blocks found", file=sys.stderr)
        return content

    result = content
    count = 0

    # FIRST: Replace ```plantuml...``` and ```puml...``` fenced blocks
    # (these may contain @startuml/@enduml inside, which we strip)
    def _replace_fenced(m):
        nonlocal count
        inner = m.group(1).strip()
        # Strip @startuml/@enduml wrapper if present inside the fence
        inner = re.sub(r'@startuml\b[^\n]*\n?', '', inner, flags=re.IGNORECASE)
        inner = re.sub(r'@enduml\b[^\n]*', '', inner, flags=re.IGNORECASE)
        inner = inner.strip()
        if not inner:
            return m.group(0)  # empty block, leave as-is
        count += 1
        return convert_plantuml_to_mermaid(inner)

    result = re.sub(
        r'```(?:plantuml|puml)\s*\n(.*?)```',
        _replace_fenced,
        result,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # SECOND: Replace any remaining bare @startuml...@enduml blocks
    # (not inside a fenced code block)
    def _replace_bare(m):
        nonlocal count
        inner = m.group(1).strip()
        if not inner:
            return m.group(0)
        count += 1
        return convert_plantuml_to_mermaid(inner)

    result = re.sub(
        r'@startuml\b[^\n]*\n(.*?)@enduml',
        _replace_bare,
        result,
        flags=re.DOTALL | re.IGNORECASE,
    )

    print(f"  📊 Converted {count} PlantUML block(s) to Mermaid", file=sys.stderr)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Convert PlantUML diagrams to Mermaid (via AST IR)",
    )
    parser.add_argument("--input", "-i", help="Input .puml or .md file")
    parser.add_argument("--output", "-o", help="Output file (optional, prints to stdout if omitted)")
    parser.add_argument("--ast-output", help="Write AST IR to this .ast.json path")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    args = parser.parse_args()

    if args.stdin:
        content = sys.stdin.read()
        blocks = extract_plantuml_blocks(content)
        if blocks:
            for block in blocks:
                print(convert_plantuml_to_mermaid(block))
        else:
            inner = re.sub(r'@startuml\b[^\n]*\n?', '', content, flags=re.IGNORECASE)
            inner = re.sub(r'@enduml\b[^\n]*', '', inner, flags=re.IGNORECASE)
            print(convert_plantuml_to_mermaid(inner.strip()))
        return

    if not args.input:
        parser.error("Either --input or --stdin is required")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if args.ast_output and input_path.suffix.lower() in ('.puml', '.plantuml', '.pu', '.wsd'):
        content = input_path.read_text(encoding='utf-8', errors='ignore')
        inner = re.sub(r'@startuml\b[^\n]*\n?', '', content, flags=re.IGNORECASE)
        inner = re.sub(r'@enduml\b[^\n]*', '', inner, flags=re.IGNORECASE)
        ast = convert_plantuml_to_ast(inner.strip())
        save_ast(ast, args.ast_output)
        print(f"  AST written to {args.ast_output}", file=sys.stderr)

    result = convert_file(input_path)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result, encoding='utf-8')
        print(f"  Output written to {output_path}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
