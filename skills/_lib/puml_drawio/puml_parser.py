"""Parse PlantUML C4 diagrams into a structured data model."""
from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class TagStyle:
    name: str
    bg_color: str = "#438DD5"
    font_color: str = "#FFFFFF"
    legend_text: str = ""


@dataclass
class Component:
    id: str
    name: str
    comp_type: str
    technology: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    sprite: str = ""
    parent_boundary: str | None = None


@dataclass
class Boundary:
    id: str
    label: str
    parent_boundary: str | None = None


@dataclass
class Relationship:
    source_id: str
    target_id: str
    label: str = ""
    technology: str = ""
    direction: str | None = None


@dataclass
class LayoutHint:
    hint_type: str
    source_id: str
    target_id: str


@dataclass
class Diagram:
    title: str = ""
    layout_direction: str = "TOP_DOWN"
    components: list[Component] = field(default_factory=list)
    boundaries: list[Boundary] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    layout_hints: list[LayoutHint] = field(default_factory=list)
    tag_styles: dict[str, TagStyle] = field(default_factory=dict)


def _split_args(text: str) -> list[str]:
    """Split macro arguments, respecting quoted strings and nested parens."""
    args: list[str] = []
    buf: list[str] = []
    in_q = False
    depth = 0
    for ch in text:
        if ch == '"' and depth == 0:
            in_q = not in_q
            buf.append(ch)
        elif ch == '(' and not in_q:
            depth += 1
            buf.append(ch)
        elif ch == ')' and not in_q and depth > 0:
            depth -= 1
            buf.append(ch)
        elif ch == ',' and not in_q and depth == 0:
            args.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = ''.join(buf).strip()
    if tail:
        args.append(tail)
    return args


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _named_args(args: list[str]) -> tuple[list[str], dict[str, str]]:
    """Separate positional and $key=value arguments."""
    pos: list[str] = []
    named: dict[str, str] = {}
    for a in args:
        a = a.strip()
        m = re.match(r'\$(\w+)\s*=\s*"?([^"]*)"?', a)
        if m:
            named[m.group(1)] = m.group(2)
        else:
            pos.append(a)
    return pos, named


def _clean_desc(desc: str) -> tuple[str, str]:
    """Strip PlantUML-specific markup from description.

    Returns (cleaned_description, first_inline_sprite_name).
    """
    sprite = ""
    m = re.search(r'<\$(\w+)', desc)
    if m:
        sprite = m.group(1)
    cleaned = re.sub(r'<\$\w+[^>]*>', '', desc)
    cleaned = re.sub(r'</?b>', '', cleaned)
    cleaned = re.sub(r'<size:\d+>', '', cleaned)
    cleaned = re.sub(r'</size>', '', cleaned)
    cleaned = re.sub(r'</?i>', '', cleaned)
    cleaned = cleaned.strip()
    return cleaned, sprite


_RE_COMP = re.compile(
    r'^(Person|System_Ext|System|Container)\((.+)\)\s*$'
)
_RE_BOUNDARY = re.compile(
    r'^System_Boundary\((\w+),\s*"([^"]+)"\)\s*\{'
)
_RE_TAG = re.compile(r'^AddElementTag\((.+)\)\s*$')
_RE_LAY = re.compile(r'^Lay_(R|D|L|U)\((\w+),\s*(\w+)\)')
_RE_REL = re.compile(r'^Rel(?:_(D|U|L|R))?\((.+)\)\s*$')
_RE_ARROW = re.compile(
    r'^(\w+)\s*(<)?-+>\s*(\w+)\s*:\s*(.*?)\s*$'
)
_RE_BIARROW = re.compile(
    r'^(\w+)\s*<-+>\s*(\w+)\s*:\s*(.*?)\s*$'
)


def parse(puml_text: str) -> Diagram:
    """Parse PlantUML C4 source into a Diagram model."""
    diag = Diagram()
    block_stack: list[tuple[str, str | None]] = []

    def _cur_boundary() -> str | None:
        for btype, bid in reversed(block_stack):
            if btype == 'boundary':
                return bid
        return None

    for raw_line in puml_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("'") or line.startswith('!'):
            continue
        if line.startswith('@') or line.startswith('skinparam'):
            continue
        if line in ('SHOW_LEGEND()', 'SHOW_LEGEND()'):
            continue

        tm = re.match(r'^title\s+(.*)', line)
        if tm:
            raw = tm.group(1)
            clean = re.sub(r'<[^>]+>', '', raw)
            parts = [p.strip() for p in clean.split('\\n') if p.strip()]
            diag.title = ' // '.join(parts)
            continue

        if 'LAYOUT_TOP_DOWN()' in line:
            diag.layout_direction = 'TOP_DOWN'
            continue
        if 'LAYOUT_LEFT_RIGHT()' in line:
            diag.layout_direction = 'LEFT_RIGHT'
            continue

        tm = _RE_TAG.match(line)
        if tm:
            args = _split_args(tm.group(1))
            pos, named = _named_args(args)
            tag_name = _unquote(pos[0]) if pos else ''
            diag.tag_styles[tag_name] = TagStyle(
                name=tag_name,
                bg_color=named.get('bgColor', '#438DD5'),
                font_color=named.get('fontColor', '#FFFFFF'),
                legend_text=named.get('legendText', ''),
            )
            continue

        bm = _RE_BOUNDARY.match(line)
        if bm:
            bid, label = bm.group(1), bm.group(2)
            parent = _cur_boundary()
            diag.boundaries.append(Boundary(id=bid, label=label, parent_boundary=parent))
            block_stack.append(('boundary', bid))
            continue

        if line.startswith('together') and '{' in line:
            block_stack.append(('together', None))
            continue

        if line == '}':
            if block_stack:
                block_stack.pop()
            continue

        cm = _RE_COMP.match(line)
        if cm:
            ctype = cm.group(1)
            args = _split_args(cm.group(2))
            pos, named = _named_args(args)
            cid = _unquote(pos[0]) if pos else ''

            if ctype == 'Container':
                name = _unquote(pos[1]) if len(pos) > 1 else ''
                tech = _unquote(pos[2]) if len(pos) > 2 else ''
                desc_raw = _unquote(pos[3]) if len(pos) > 3 else ''
            elif ctype == 'Person':
                name = _unquote(pos[1]) if len(pos) > 1 else ''
                tech = ''
                desc_raw = _unquote(pos[2]) if len(pos) > 2 else ''
            else:
                name = _unquote(pos[1]) if len(pos) > 1 else ''
                tech = ''
                desc_raw = _unquote(pos[2]) if len(pos) > 2 else ''

            desc_clean, inline_sprite = _clean_desc(desc_raw)
            sprite = named.get('sprite', '') or inline_sprite

            tags_str = named.get('tags', '')
            tags = [t.strip() for t in tags_str.split('+') if t.strip()]

            diag.components.append(Component(
                id=cid,
                name=name,
                comp_type=ctype,
                technology=tech,
                description=desc_clean,
                tags=tags,
                sprite=sprite,
                parent_boundary=_cur_boundary(),
            ))
            continue

        lm = _RE_LAY.match(line)
        if lm:
            diag.layout_hints.append(LayoutHint(
                hint_type=lm.group(1),
                source_id=lm.group(2),
                target_id=lm.group(3),
            ))
            continue

        rm = _RE_REL.match(line)
        if rm:
            direction = rm.group(1)
            args = _split_args(rm.group(2))
            pos, _ = _named_args(args)
            diag.relationships.append(Relationship(
                source_id=_unquote(pos[0]) if pos else '',
                target_id=_unquote(pos[1]) if len(pos) > 1 else '',
                label=_unquote(pos[2]) if len(pos) > 2 else '',
                technology=_unquote(pos[3]) if len(pos) > 3 else '',
                direction=direction,
            ))
            continue

        bam = _RE_BIARROW.match(line)
        if bam:
            label = re.sub(r'<[^>]+>', '', bam.group(3)).strip()
            diag.relationships.append(Relationship(
                source_id=bam.group(1),
                target_id=bam.group(2),
                label=label,
            ))
            continue

        am = _RE_ARROW.match(line)
        if am:
            label = re.sub(r'<[^>]+>', '', am.group(4)).strip()
            diag.relationships.append(Relationship(
                source_id=am.group(1),
                target_id=am.group(3),
                label=label,
            ))
            continue

    return diag
