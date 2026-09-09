"""Generate draw.io XML from a parsed PlantUML C4 diagram model."""
from __future__ import annotations

import html
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from . import icons as _icons
from . import elk_layout as _elk
from .puml_parser import (
    _C4_ELEMENTS,
    Boundary,
    Component,
    Diagram,
    LayoutHint,
    Relationship,
)

# Default icon map ships empty; projects supply their own via icons.json sidecar
ICON_MAP: dict[str, str] = {}

FALLBACK_ICONS: dict[str, str] = {
    "System_Ext": "img/lib/azure2/general/Module.svg",
    "System": "img/lib/azure2/general/Module.svg",
    "Container": "img/lib/azure2/general/Module.svg",
    "Component": "img/lib/azure2/general/Module.svg",
    "Person": "img/lib/azure2/identity/Groups.svg",
}

COMP_W = 155
COMP_H = 92
H_GAP = 28
V_GAP = 36
BOUND_PAD = 20
BOUND_HEADER = 30
ICON_SIZE = 56
MAX_DESC_LINES = 3

# Component IDs treated as secondary (monitoring/observability) edges
_MONITORING_IDS: set[str] = set()


def load_icon_map(json_path: str | Path) -> None:
    """Load sprite-to-icon mappings from a JSON sidecar file.

    The JSON file should be a flat dict mapping sprite names to draw.io
    image paths, e.g.: {"AzureAPIManagement": "img/lib/azure2/integration/API_Management_Services.svg"}
    """
    global ICON_MAP
    p = Path(json_path)
    if p.exists():
        with p.open() as f:
            data = json.load(f)
        if isinstance(data, dict):
            ICON_MAP.update(data)


def configure(
    *,
    monitoring_ids: set[str] | None = None,
    icon_map: dict[str, str] | None = None,
    fallback_icons: dict[str, str] | None = None,
) -> None:
    """Configure generator globals for project-specific needs."""
    global _MONITORING_IDS, ICON_MAP, FALLBACK_ICONS
    if monitoring_ids is not None:
        _MONITORING_IDS = monitoring_ids
    if icon_map is not None:
        ICON_MAP.update(icon_map)
    if fallback_icons is not None:
        FALLBACK_ICONS.update(fallback_icons)


def _html_value(comp: Component, tag_styles: dict | None = None) -> str:
    name = html.escape(comp.name.replace("\\n", " ").strip())
    has_tag_color = bool(comp.tags and tag_styles and comp.tags[0] in tag_styles)
    tech_color = "#FFFFFF" if has_tag_color else "#666666"
    parts: list[str] = []
    parts.append(f'<font style="font-size:12px"><b>{name}</b></font>')
    if comp.technology:
        tech = html.escape(comp.technology)
        parts.append(f'<font style="font-size:9px" color="{tech_color}"><i>[{tech}]</i></font>')
    if MAX_DESC_LINES > 0 and comp.description:
        desc = comp.description.replace("\\n", "\n")
        lines = [l.strip() for l in desc.split("\n") if l.strip() and not all(c in "-─=" for c in l.strip())]
        lines = lines[:MAX_DESC_LINES]
        if lines:
            desc_color = "#E0E0E0" if has_tag_color else "#888888"
            desc_text = html.escape(" | ".join(lines))
            parts.append(f'<font style="font-size:8px" color="{desc_color}">{desc_text}</font>')
    return "<br/>".join(parts)


def _icon_path(comp: Component) -> str:
    # Central curated MS icons first: embeds the official SVG when the sprite or
    # component id matches ms_icons/catalog.tsv (no-op if there is no match).
    embedded = _icons.resolve(sprite=comp.sprite, comp_id=getattr(comp, "id", None))
    if embedded:
        return embedded
    if comp.sprite and comp.sprite in ICON_MAP:
        return ICON_MAP[comp.sprite]
    if comp.comp_type in FALLBACK_ICONS:
        return FALLBACK_ICONS[comp.comp_type]
    # Fall back on the C4 base kind so Component/*Db/*Queue/_Ext variants
    # (e.g. ComponentQueue_Ext) still get an icon.
    base = _C4_ELEMENTS.get(comp.comp_type)
    return FALLBACK_ICONS.get(base, "") if base else ""


def _wrapped_line_count(text: str, width_px: float, font_px: float) -> int:
    """Estimate how many rendered lines `text` needs at `font_px` in `width_px`.

    draw.io wraps on width, so counting explicit newlines alone badly
    under-estimates height for long single-line descriptions.
    """
    if not text:
        return 0
    usable = max(width_px - 16, 40)
    # ~0.55em average glyph advance for the sans stack draw.io uses.
    chars_per_line = max(int(usable / (font_px * 0.55)), 8)
    total = 0
    for line in text.replace("\\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        total += max(1, -(-len(line) // chars_per_line))
    return total


def _comp_height(comp: Component) -> int:
    has_icon = bool(_icon_path(comp))
    width = _comp_width(comp)

    name_h = _wrapped_line_count(comp.name, width, 12) * 15
    tech_h = 12 if comp.technology else 0

    desc_h = 0
    if MAX_DESC_LINES > 0 and comp.description:
        raw = comp.description.replace("\\n", "\n")
        lines = [l.strip() for l in raw.split("\n") if l.strip() and not all(c in "-─=" for c in l.strip())]
        lines = lines[:MAX_DESC_LINES]
        if lines:
            desc_text = " | ".join(lines)
            wrapped = _wrapped_line_count(desc_text, width, 8)
            # Honour the cap on rendered lines, not just on source lines.
            desc_h = min(wrapped, MAX_DESC_LINES * 2) * 10

    if has_icon:
        # icon occupies y=4 .. 4+ICON_SIZE; text stacks beneath it
        return max(COMP_H, 4 + ICON_SIZE + 6 + name_h + tech_h + desc_h + 8)
    return max(52, 8 + name_h + tech_h + desc_h + 8)


MAX_COMP_W = 230


def _comp_width(comp: Component) -> int:
    name = comp.name.replace("\\n", "\n")
    lines = name.split("\n")
    max_chars = max(len(line.strip()) for line in lines)
    if comp.technology:
        max_chars = max(max_chars, len(comp.technology) + 2)
    needed = max_chars * 8 + 24
    return min(max(COMP_W, needed), MAX_COMP_W)


def _comp_style(
    has_icon: bool,
    bg_color: str = "#FFFFFF",
    font_color: str = "#333333",
    border_color: str = "",
    border_thickness: str = "",
    border_style: str = "",
) -> str:
    if border_color:
        stroke_color = border_color
    elif bg_color != "#FFFFFF":
        stroke_color = bg_color
    else:
        stroke_color = "#CCCCCC"
    parts = [
        "rounded=1",
        "whiteSpace=wrap",
        "html=1",
        f"fillColor={bg_color}",
        f"fontColor={font_color}",
        f"strokeColor={stroke_color}",
        f"verticalAlign={'bottom' if has_icon else 'middle'}",
        "align=center",
        "spacing=4",
        f"spacingBottom={'8' if has_icon else '4'}",
        "arcSize=6",
        "fontSize=10",
        "shadow=0",
        "glass=0",
        "gradientColor=none",
    ]
    if border_thickness:
        parts.append(f"strokeWidth={border_thickness}")
    if border_style == "dashed":
        parts.append("dashed=1")
    elif border_style == "dotted":
        parts.extend(["dashed=1", "dashPattern=1 3"])
    return ";".join(parts) + ";"


def _boundary_style(depth: int = 0) -> str:
    fills = ["#D0E8F2", "#E8F4F8", "#F0F9FC"]
    strokes = ["#0070C0", "#3399CC", "#66AACC"]
    stroke_widths = ["1.5", "1", "0.75"]
    fill = fills[min(depth, len(fills) - 1)]
    stroke = strokes[min(depth, len(strokes) - 1)]
    sw = stroke_widths[min(depth, len(stroke_widths) - 1)]
    return (
        "swimlane;rounded=1;whiteSpace=wrap;html=1;"
        f"fillColor={fill};fontColor=#000000;strokeColor={stroke};"
        f"fontSize=13;fontStyle=1;startSize=30;container=1;"
        f"collapsible=0;swimlaneLine=0;strokeWidth={sw};"
        "shadow=0;arcSize=5;labelBackgroundColor=none;"
        "dashed=1;dashPattern=5 3;spacingLeft=8;"
    )


def _edge_style(
    is_bidirectional: bool = False,
    is_secondary: bool = False,
    exit_x: float | None = None,
    exit_y: float | None = None,
    entry_x: float | None = None,
    entry_y: float | None = None,
) -> str:
    stroke_color = "#666666" if is_secondary else "#000000"
    stroke_width = "0.75" if is_secondary else "1.5"
    font_color = "#666666" if is_secondary else "#000000"
    base = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
        f"jettySize=auto;html=1;strokeColor={stroke_color};fontColor={font_color};"
        f"fontSize=9;strokeWidth={stroke_width};"
        "labelBackgroundColor=none;labelBorderColor=none;"
        "spacingTop=1;spacingBottom=1;spacingLeft=2;spacingRight=2;"
        "sourcePerimeterSpacing=8;targetPerimeterSpacing=8;"
    )
    if exit_x is not None and exit_y is not None:
        base += f"exitX={exit_x};exitY={exit_y};exitDx=0;exitDy=0;"
    if entry_x is not None and entry_y is not None:
        base += f"entryX={entry_x};entryY={entry_y};entryDx=0;entryDy=0;"
    if is_bidirectional:
        base += "startArrow=classic;startFill=1;endArrow=classic;endFill=1;"
    return base


def _edge_label(rel: Relationship) -> str:
    text = ""
    if rel.label:
        first_line = rel.label.split("\\n")[0]
        text = first_line.strip().rstrip("+").strip()
    elif rel.technology:
        text = rel.technology.strip()

    if not text:
        return ""

    # No truncation: ELK reserves space for the label's real size, so it no
    # longer has to be clipped to avoid collisions.
    return html.escape(text)


@dataclass
class _Rect:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


def _path_midpoint(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Point at half the arc length — where draw.io anchors an edge label."""
    if not pts:
        return (0.0, 0.0)
    if len(pts) == 1:
        return pts[0]
    seg_len = [
        ((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
        for i in range(len(pts) - 1)
    ]
    total = sum(seg_len)
    if total <= 0:
        return pts[0]
    half = total / 2
    run = 0.0
    for i, ln in enumerate(seg_len):
        if run + ln >= half:
            t = (half - run) / ln if ln else 0.0
            return (
                pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
                pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t,
            )
        run += ln
    return pts[-1]


def _elk_label_size(rel: Relationship) -> tuple[float, float]:
    """Reserve space for the label's true size so ELK routes clear of it."""
    text = _edge_label(rel)
    if not text:
        return (0.0, 0.0)
    w = len(text) * 5.0
    if w <= 190.0:
        return (w, 12.0)
    return (190.0, 12.0 * (-(-w // 190.0)))


class _ElkLayout:
    """Adapter presenting an ElkResult through the interface generate() expects.

    Node geometry stays parent-relative (draw.io's cell model); centres and
    routes are exposed in absolute coordinates.
    """

    def __init__(self, diagram: Diagram, overrides: dict | None = None):
        self.diagram = diagram
        self._result = _elk.layout(
            diagram,
            overrides=overrides,
            size_of=lambda c: (float(_comp_width(c)), float(_comp_height(c))),
            label_size_of=_elk_label_size,
            boundary_header=float(BOUND_HEADER),
            boundary_pad=float(BOUND_PAD),
        )
        self.rects: dict[str, _Rect] = {
            nid: _Rect(x=x, y=y, w=w, h=h)
            for nid, (x, y, w, h) in self._result.nodes.items()
        }
        seen = {(r.source_id, r.target_id) for r in diagram.relationships}
        self._bidi = {(s, t) for s, t in seen if (t, s) in seen}

    def is_bidirectional(self, src: str, tgt: str) -> bool:
        return (src, tgt) in self._bidi or (tgt, src) in self._bidi

    def route(self, src: str, tgt: str):
        return self._result.edges.get(f"{src}->{tgt}")

    def _abs_center(self, node_id: str) -> tuple[float, float]:
        if node_id not in self._result.nodes:
            return (0.0, 0.0)
        x, y, w, h = self._result.abs_rect(node_id)
        return (x + w / 2, y + h / 2)

    def abs_rect(self, node_id: str):
        return self._result.abs_rect(node_id)

    def compute(self):     # call-site compatibility
        return


def generate(diagram: Diagram, overrides: dict | None = None) -> str:
    """Generate draw.io XML from a parsed Diagram.

    `overrides` is the optional hand-polish sidecar (see
    elk_layout.load_overrides); anything it does not mention keeps the
    computed layout.
    """
    layout = _ElkLayout(diagram, overrides)
    layout.compute()

    mxfile = ET.Element("mxfile")
    mxfile.set("host", "puml-drawio-converter")
    mxfile.set("type", "device")

    dia = ET.SubElement(mxfile, "diagram")
    dia.set("id", "page1")
    dia.set("name", diagram.title or "Architecture")

    model = ET.SubElement(dia, "mxGraphModel")
    model.set("dx", "1600")
    model.set("dy", "900")
    model.set("grid", "1")
    model.set("gridSize", "10")
    model.set("guides", "1")
    model.set("tooltips", "1")
    model.set("connect", "1")
    model.set("arrows", "1")
    model.set("fold", "1")
    model.set("page", "0")
    model.set("pageScale", "1")
    model.set("pageWidth", "2339")
    model.set("pageHeight", "1654")
    model.set("math", "0")
    model.set("shadow", "0")

    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell").set("id", "0")
    layer = ET.SubElement(root, "mxCell")
    layer.set("id", "1")
    layer.set("parent", "0")

    cell_id_map: dict[str, str] = {}
    bound_map = {b.id: b for b in diagram.boundaries}

    def _boundary_depth(bid: str) -> int:
        depth = 0
        cur = bid
        while cur and cur in bound_map:
            p = bound_map[cur].parent_boundary
            if p:
                depth += 1
            cur = p
        return depth

    # Boundaries
    for b in diagram.boundaries:
        cell_id = f"b_{b.id}"
        cell_id_map[b.id] = cell_id
        r = layout.rects.get(b.id, _Rect(w=400, h=300))

        cell = ET.SubElement(root, "mxCell")
        cell.set("id", cell_id)
        cell.set("value", f'<b>{html.escape(b.label)}</b>')
        cell.set("style", _boundary_style(_boundary_depth(b.id)))
        cell.set("vertex", "1")
        parent_id = f"b_{b.parent_boundary}" if b.parent_boundary else "1"
        cell.set("parent", parent_id)

        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("x", str(r.x))
        geo.set("y", str(r.y))
        geo.set("width", str(r.w))
        geo.set("height", str(r.h))
        geo.set("as", "geometry")

    # Components
    tag_styles = diagram.tag_styles
    for comp in diagram.components:
        cell_id = f"c_{comp.id}"
        cell_id_map[comp.id] = cell_id
        r = layout.rects.get(comp.id, _Rect(w=COMP_W, h=COMP_H))
        icon_path = _icon_path(comp)

        bg_color = "#FFFFFF"
        font_color = "#333333"
        border_color = border_thickness = border_style = ""
        if comp.tags and tag_styles:
            # Merge per property, first tag that sets one wins. This lets a
            # border-only overlay tag (build state) sit in front of a fill tag
            # (ownership) — e.g. $tags="gap+ey" — without masking the fill.
            for tag in comp.tags:
                ts = tag_styles.get(tag)
                if ts is None:
                    continue
                if ts.bg_color and bg_color == "#FFFFFF":
                    bg_color = ts.bg_color
                if ts.font_color and font_color == "#333333":
                    font_color = ts.font_color if ts.font_color != "white" else "#FFFFFF"
                if ts.border_color and not border_color:
                    border_color = ts.border_color
                if ts.border_thickness and not border_thickness:
                    border_thickness = ts.border_thickness
                if ts.border_style and not border_style:
                    border_style = ts.border_style
            # C4 semantics: a tagged element with no explicit $bgColor still
            # takes the default C4 element fill, not the untagged white.
            if bg_color == "#FFFFFF" and any(t in tag_styles for t in comp.tags):
                bg_color = "#438DD5"
                if font_color == "#333333":
                    font_color = "#FFFFFF"

        cell = ET.SubElement(root, "mxCell")
        cell.set("id", cell_id)
        cell.set("value", _html_value(comp, tag_styles))
        cell.set("style", _comp_style(
            bool(icon_path), bg_color, font_color,
            border_color, border_thickness, border_style,
        ))
        cell.set("vertex", "1")
        parent_id = f"b_{comp.parent_boundary}" if comp.parent_boundary else "1"
        cell.set("parent", parent_id)

        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("x", str(r.x))
        geo.set("y", str(r.y))
        geo.set("width", str(r.w))
        geo.set("height", str(r.h))
        geo.set("as", "geometry")

        if icon_path:
            icon_cell = ET.SubElement(root, "mxCell")
            icon_cell.set("id", f"i_{comp.id}")
            icon_cell.set("value", "")
            icon_cell.set(
                "style",
                f"shape=image;imageAspect=0;aspect=fixed;image={icon_path};"
                "noLabel=1;movable=0;resizable=0;deletable=0;",
            )
            icon_cell.set("vertex", "1")
            icon_cell.set("parent", cell_id)
            icon_cell.set("connectable", "0")

            icon_x = (r.w - ICON_SIZE) / 2.0
            ig = ET.SubElement(icon_cell, "mxGeometry")
            ig.set("x", str(round(icon_x, 1)))
            ig.set("y", "4")
            ig.set("width", str(ICON_SIZE))
            ig.set("height", str(ICON_SIZE))
            ig.set("as", "geometry")

    # Title
    if diagram.title:
        title_cell = ET.SubElement(root, "mxCell")
        title_cell.set("id", "title")
        title_parts = diagram.title.split(" // ")
        title_html = f'<font style="font-size:16px"><b>{html.escape(title_parts[0])}</b></font>'
        if len(title_parts) > 1:
            title_html += f'<br/><font style="font-size:11px" color="#777777">{html.escape(" | ".join(title_parts[1:]))}</font>'
        title_cell.set("value", title_html)
        title_cell.set(
            "style",
            "text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;"
            "fontColor=#000000;fontSize=14;fillColor=none;strokeColor=none;",
        )
        title_cell.set("vertex", "1")
        title_cell.set("parent", "1")
        tg = ET.SubElement(title_cell, "mxGeometry")
        tg.set("x", "30")
        tg.set("y", "8")
        tg.set("width", "1200")
        tg.set("height", "42")
        tg.set("as", "geometry")

    # Legend
    if tag_styles:
        used_tags = set()
        for c in diagram.components:
            for t in c.tags:
                if t in tag_styles:
                    used_tags.add(t)
        if used_tags:
            max_bottom = 0.0
            all_ids = [c.id for c in diagram.components] + [b.id for b in diagram.boundaries]
            for nid in all_ids:
                r = layout.rects.get(nid)
                if not r:
                    continue
                _, cy = layout._abs_center(nid)
                abs_bottom = cy + r.h / 2
                max_bottom = max(max_bottom, abs_bottom)

            legend_y = max_bottom + 40
            legend_x = 30.0
            swatch_w, swatch_h = 14, 14
            row_h = 22

            ordered_tags = [t for t in tag_styles if t in used_tags]

            # Legend labels never wrap, so size the column to the longest text
            # and drop the column count until the whole row stays reasonable.
            longest = max(
                (len(tag_styles[t].legend_text or t) for t in ordered_tags),
                default=0,
            )
            entry_w = max(180.0, longest * 9 * 0.55 + swatch_w + 20)
            cols = max(1, min(4, int(1400 / entry_w)))

            for i, tag_name in enumerate(ordered_tags):
                ts = tag_styles[tag_name]
                col = i % cols
                row = i // cols
                x = legend_x + col * entry_w
                y = legend_y + row * row_h

                swatch = ET.SubElement(root, "mxCell")
                swatch.set("id", f"legend_sw_{i}")
                swatch.set("value", "")
                # Mirror the node encoding: fill = ownership, border = state.
                # A border-only tag gets a neutral fill so its border reads.
                sw_fill = ts.bg_color or ("#FFFFFF" if ts.border_color else "#CCCCCC")
                sw_stroke = ts.border_color or ts.bg_color or "#CCCCCC"
                sw_style = (
                    f"rounded=1;whiteSpace=wrap;html=1;fillColor={sw_fill};"
                    f"strokeColor={sw_stroke};arcSize=20;"
                )
                if ts.border_thickness:
                    sw_style += f"strokeWidth={ts.border_thickness};"
                if ts.border_style == "dashed":
                    sw_style += "dashed=1;"
                elif ts.border_style == "dotted":
                    sw_style += "dashed=1;dashPattern=1 3;"
                swatch.set("style", sw_style)
                swatch.set("vertex", "1")
                swatch.set("parent", "1")
                sg = ET.SubElement(swatch, "mxGeometry")
                sg.set("x", str(x))
                sg.set("y", str(y))
                sg.set("width", str(swatch_w))
                sg.set("height", str(swatch_h))
                sg.set("as", "geometry")

                label = ET.SubElement(root, "mxCell")
                label.set("id", f"legend_lb_{i}")
                label.set("value", html.escape(ts.legend_text or tag_name))
                label.set(
                    "style",
                    "text;html=1;align=left;verticalAlign=middle;"
                    "fontColor=#333333;fontSize=9;fillColor=none;strokeColor=none;",
                )
                label.set("vertex", "1")
                label.set("parent", "1")
                lg = ET.SubElement(label, "mxGeometry")
                lg.set("x", str(x + swatch_w + 4))
                lg.set("y", str(y - 1))
                lg.set("width", str(entry_w - swatch_w - 8))
                lg.set("height", str(swatch_h + 2))
                lg.set("as", "geometry")

    # Edge classification helpers
    comp_parent: dict[str, str | None] = {}
    for c in diagram.components:
        comp_parent[c.id] = c.parent_boundary
    for b in diagram.boundaries:
        comp_parent[b.id] = b.parent_boundary

    def _is_secondary_edge(src_id: str, tgt_id: str) -> bool:
        if src_id in _MONITORING_IDS or tgt_id in _MONITORING_IDS:
            return True
        src_p = comp_parent.get(src_id)
        tgt_p = comp_parent.get(tgt_id)
        return src_p is not None and src_p == tgt_p

    def _abs_center(node_id: str) -> tuple[float, float]:
        r = layout.rects.get(node_id)
        if not r:
            return 0.0, 0.0
        cx, cy = r.x + r.w / 2, r.y + r.h / 2
        pid = comp_parent.get(node_id)
        while pid:
            pr = layout.rects.get(pid)
            if pr:
                cx += pr.x
                cy += pr.y
            pid = comp_parent.get(pid)
        return cx, cy

    def _boundary_depth_edge(node_id: str) -> int:
        depth = 0
        pid = comp_parent.get(node_id)
        while pid:
            depth += 1
            pid = comp_parent.get(pid)
        return depth

    def _share_boundary(a: str, b: str) -> bool:
        pa = comp_parent.get(a)
        pb = comp_parent.get(b)
        if pa == pb:
            return True
        if pa == b or pb == a:
            return True
        return False

    _target_fanin: dict[str, list[str]] = {}
    _source_fanout: dict[str, list[str]] = {}
    for rel in diagram.relationships:
        _target_fanin.setdefault(rel.target_id, []).append(rel.source_id)
        _source_fanout.setdefault(rel.source_id, []).append(rel.target_id)

    merged_edges: list[tuple[str, str, str, bool]] = []
    seen_pairs: set[tuple[str, str]] = set()
    rel_by_pair: dict[tuple[str, str], list[Relationship]] = {}
    for rel in diagram.relationships:
        pair = (rel.source_id, rel.target_id)
        rel_by_pair.setdefault(pair, []).append(rel)

    for rel in diagram.relationships:
        src_cell = cell_id_map.get(rel.source_id)
        tgt_cell = cell_id_map.get(rel.target_id)
        if not src_cell or not tgt_cell:
            continue

        pair = (rel.source_id, rel.target_id)
        rev = (rel.target_id, rel.source_id)

        if pair in seen_pairs:
            continue

        is_bidi = layout.is_bidirectional(rel.source_id, rel.target_id)
        if is_bidi and rev not in seen_pairs:
            fwd_label = _edge_label(rel)
            merged_edges.append((rel.source_id, rel.target_id, fwd_label, True))
            seen_pairs.add(pair)
            seen_pairs.add(rev)
        else:
            merged_edges.append((rel.source_id, rel.target_id, _edge_label(rel), False))
            seen_pairs.add(pair)

    for idx, (src_id, tgt_id, label, is_bidi) in enumerate(merged_edges):
        src_cell = cell_id_map[src_id]
        tgt_cell = cell_id_map[tgt_id]
        secondary = _is_secondary_edge(src_id, tgt_id)

        route = layout.route(src_id, tgt_id) or layout.route(tgt_id, src_id)

        # Anchor the edge where ELK attached it, so draw.io reproduces the
        # routed path exactly instead of re-deriving its own perimeter points.
        ex = ey = nx = ny = None
        if route and len(route.points) >= 2:
            sx, sy, sw, sh = layout.abs_rect(src_id)
            tx, ty, tw, th = layout.abs_rect(tgt_id)
            p0, pN = route.points[0], route.points[-1]
            if sw and sh:
                ex = round(min(max((p0[0] - sx) / sw, 0.0), 1.0), 3)
                ey = round(min(max((p0[1] - sy) / sh, 0.0), 1.0), 3)
            if tw and th:
                nx = round(min(max((pN[0] - tx) / tw, 0.0), 1.0), 3)
                ny = round(min(max((pN[1] - ty) / th, 0.0), 1.0), 3)

        edge = ET.SubElement(root, "mxCell")
        edge.set("id", f"e_{idx}")
        edge.set("value", label)
        edge.set("style", _edge_style(is_bidi, secondary, ex, ey, nx, ny))
        edge.set("edge", "1")
        edge.set("parent", "1")
        edge.set("source", src_cell)
        edge.set("target", tgt_cell)

        eg = ET.SubElement(edge, "mxGeometry")
        eg.set("relative", "1")
        eg.set("as", "geometry")

        # Explicit waypoints: this is what stops draw.io re-routing through
        # whatever happens to be in the way.
        if route and len(route.points) > 2:
            arr = ET.SubElement(eg, "Array")
            arr.set("as", "points")
            for px, py in route.points[1:-1]:
                mp = ET.SubElement(arr, "mxPoint")
                mp.set("x", str(round(px, 2)))
                mp.set("y", str(round(py, 2)))

        if label:
            pt = ET.SubElement(eg, "mxPoint")
            pt.set("as", "offset")
            if route and route.label and len(route.points) >= 2:
                # draw.io positions the label relative to the path midpoint;
                # offset it to land exactly where ELK reserved room for it.
                mx_, my_ = _path_midpoint(route.points)
                lx, ly, lw, lh = route.label
                pt.set("x", str(round(lx + lw / 2 - mx_, 1)))
                pt.set("y", str(round(ly + lh / 2 - my_, 1)))
            else:
                pt.set("x", "0")
                pt.set("y", "0")

    ET.indent(mxfile, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        mxfile, encoding="unicode"
    )
