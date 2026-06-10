"""Generate draw.io XML from a parsed PlantUML C4 diagram model."""
from __future__ import annotations

import html
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .puml_parser import (
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
    if comp.sprite and comp.sprite in ICON_MAP:
        return ICON_MAP[comp.sprite]
    return FALLBACK_ICONS.get(comp.comp_type, "")


def _comp_height(comp: Component) -> int:
    has_icon = bool(_icon_path(comp))
    desc_lines = 0
    if MAX_DESC_LINES > 0 and comp.description:
        raw = comp.description.replace("\\n", "\n")
        lines = [l.strip() for l in raw.split("\n") if l.strip() and not all(c in "-─=" for c in l.strip())]
        desc_lines = min(len(lines), MAX_DESC_LINES)
    desc_h = desc_lines * 10 if desc_lines else 0
    if has_icon:
        base = 6 + ICON_SIZE + 4 + 14 + desc_h
        if comp.technology:
            base += 12
        return max(COMP_H, base)
    else:
        base = 14 + desc_h
        if comp.technology:
            base += 12
        return max(52, base)


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
) -> str:
    if bg_color != "#FFFFFF":
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

    if len(text) > 28:
        text = text[:26] + "..."
    return html.escape(text)


@dataclass
class _Rect:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


class _LayoutEngine:
    """Layered layout using Lay_D across nesting levels and Lay_R within rows."""

    def __init__(self, diagram: Diagram):
        self.d = diagram
        self.rects: dict[str, _Rect] = {}
        self._comp_map = {c.id: c for c in diagram.components}
        self._bound_map = {b.id: b for b in diagram.boundaries}
        self._children: dict[str | None, list[tuple[str, str]]] = {}
        self._processed: set[str] = set()

        for c in diagram.components:
            self._children.setdefault(c.parent_boundary, []).append(("comp", c.id))
        for b in diagram.boundaries:
            self._children.setdefault(b.parent_boundary, []).append(("bound", b.id))

        self._right_of: dict[str, list[str]] = {}
        self._below_of: dict[str, list[str]] = {}
        for h in diagram.layout_hints:
            if h.hint_type == "R":
                self._right_of.setdefault(h.source_id, []).append(h.target_id)
            elif h.hint_type == "D":
                self._below_of.setdefault(h.source_id, []).append(h.target_id)

        self._parent_of: dict[str, str | None] = {}
        for c in diagram.components:
            self._parent_of[c.id] = c.parent_boundary
        for b in diagram.boundaries:
            self._parent_of[b.id] = b.parent_boundary

        self._bidi_pairs: set[tuple[str, str]] = set()
        rel_pairs: dict[tuple[str, str], int] = {}
        for rel in diagram.relationships:
            pair = (rel.source_id, rel.target_id)
            rev = (rel.target_id, rel.source_id)
            rel_pairs[pair] = rel_pairs.get(pair, 0) + 1
            if rev in rel_pairs:
                self._bidi_pairs.add(pair)
                self._bidi_pairs.add(rev)

    def is_bidirectional(self, src: str, tgt: str) -> bool:
        return (src, tgt) in self._bidi_pairs

    def _all_descendants(self, bid: str) -> set[str]:
        result: set[str] = set()
        for ctype, cid in self._children.get(bid, []):
            result.add(cid)
            if ctype == "bound":
                result |= self._all_descendants(cid)
        return result

    def _resolve_hint_target(self, target_id: str, scope_ids: set[str]) -> str | None:
        if target_id in scope_ids:
            return target_id
        cur = target_id
        while cur in self._parent_of:
            p = self._parent_of[cur]
            if p in scope_ids:
                return p
            if p is None:
                break
            cur = p
        return None

    def _assign_rows(self, child_ids: set[str], parent_key: str | None = None) -> dict[int, list[str]]:
        descendant_of: dict[str, set[str]] = {}
        for cid in child_ids:
            if cid in self._bound_map:
                descendant_of[cid] = self._all_descendants(cid)
            else:
                descendant_of[cid] = set()

        row_of: dict[str, int] = {cid: 0 for cid in child_ids}

        effective_below: dict[str, set[str]] = {}
        all_relevant = child_ids.copy()
        for cid in child_ids:
            all_relevant |= descendant_of.get(cid, set())

        for src_id in all_relevant:
            for tgt_id in self._below_of.get(src_id, []):
                src_resolved = self._resolve_hint_target(src_id, child_ids)
                tgt_resolved = self._resolve_hint_target(tgt_id, child_ids)
                if src_resolved and tgt_resolved and src_resolved != tgt_resolved:
                    effective_below.setdefault(src_resolved, set()).add(tgt_resolved)

        if parent_key is None:
            def _can_reach(start: str, end: str) -> bool:
                visited: set[str] = set()
                stack = [start]
                while stack:
                    cur = stack.pop()
                    if cur == end:
                        return True
                    if cur in visited:
                        continue
                    visited.add(cur)
                    stack.extend(effective_below.get(cur, set()))
                return False

            for rel in self.d.relationships:
                if rel.direction in ("L", "R", "U"):
                    continue
                src_resolved = self._resolve_hint_target(rel.source_id, child_ids)
                tgt_resolved = self._resolve_hint_target(rel.target_id, child_ids)
                if (src_resolved and tgt_resolved
                        and src_resolved != tgt_resolved
                        and not _can_reach(tgt_resolved, src_resolved)):
                    effective_below.setdefault(src_resolved, set()).add(tgt_resolved)

        changed = True
        while changed:
            changed = False
            for src, targets in effective_below.items():
                for tgt in targets:
                    needed = row_of[src] + 1
                    if row_of[tgt] < needed:
                        row_of[tgt] = needed
                        changed = True

        rows: dict[int, list[str]] = {}
        for cid, rn in row_of.items():
            rows.setdefault(rn, []).append(cid)
        return rows

    def _order_row(self, ids: list[str]) -> list[str]:
        if len(ids) <= 1:
            return ids
        id_set = set(ids)

        effective_right: dict[str, list[str]] = {}
        for src in ids:
            for tgt in self._right_of.get(src, []):
                resolved = self._resolve_hint_target(tgt, id_set)
                if resolved and resolved != src:
                    effective_right.setdefault(src, []).append(resolved)
            if src in self._bound_map:
                for desc in self._all_descendants(src):
                    for tgt in self._right_of.get(desc, []):
                        resolved = self._resolve_hint_target(tgt, id_set)
                        if resolved and resolved != src:
                            effective_right.setdefault(src, []).append(resolved)

        chain_member: set[str] = set()
        for src in ids:
            for tgt in effective_right.get(src, []):
                if tgt in id_set:
                    chain_member.add(tgt)

        source_order = [c.id for c in self.d.components] + [b.id for b in self.d.boundaries]
        chain_starts = [s for s in source_order if s in id_set and s not in chain_member]

        if not chain_starts and effective_right:
            for sid in source_order:
                if sid in id_set:
                    chain_starts = [sid]
                    break
            if not chain_starts:
                chain_starts = [ids[0]]

        chains: list[list[str]] = []
        for start in chain_starts:
            chain = [start]
            cur = start
            while True:
                nxt = [t for t in effective_right.get(cur, []) if t in id_set and t not in set(chain)]
                if not nxt:
                    break
                chain.append(nxt[0])
                cur = nxt[0]
            chains.append(chain)

        used: set[str] = set()
        result: list[str] = []
        for chain in chains:
            for cid in chain:
                if cid not in used:
                    result.append(cid)
                    used.add(cid)
        remaining = [cid for cid in source_order if cid in id_set and cid not in used]
        result.extend(remaining)
        return result

    def _row_width(self, ordered: list[str]) -> float:
        if not ordered:
            return 0.0
        total = sum(self.rects[cid].w for cid in ordered)
        total += H_GAP * (len(ordered) - 1)
        return total

    def compute(self):
        for c in self.d.components:
            self.rects[c.id] = _Rect(w=_comp_width(c), h=_comp_height(c))
        for b in self.d.boundaries:
            self._layout_boundary(b.id)
        self._normalize_row_heights()
        self._processed.clear()
        for b in self.d.boundaries:
            self._layout_boundary(b.id)
        self._layout_root()

    def _normalize_row_heights(self):
        for parent_key in list(self._children.keys()):
            children = self._children.get(parent_key, [])
            if not children:
                continue
            child_ids = {cid for _, cid in children}
            child_map = {cid: ct for ct, cid in children}
            rows = self._assign_rows(child_ids, parent_key)
            for row_ids in rows.values():
                if len(row_ids) <= 1:
                    continue
                comps = [c for c in row_ids if child_map[c] == "comp"]
                bounds = [c for c in row_ids if child_map[c] == "bound"]
                for group in (comps, bounds):
                    if len(group) <= 1:
                        continue
                    heights = sorted(self.rects[cid].h for cid in group)
                    target_idx = min(len(heights) - 1, int(len(heights) * 0.75))
                    target_h = heights[target_idx]
                    for cid in group:
                        if self.rects[cid].h < target_h:
                            self.rects[cid].h = target_h

    def _layout_container(self, parent_key: str | None, start_y: float) -> tuple[float, float]:
        children = self._children.get(parent_key, [])
        if not children:
            return 0.0, 0.0

        child_ids = {cid for _, cid in children}
        rows = self._assign_rows(child_ids, parent_key)

        row_data: list[tuple[list[str], float]] = []
        max_row_w = 0.0
        for row_num in sorted(rows.keys()):
            ordered = self._order_row(rows[row_num])
            rw = self._row_width(ordered)
            row_data.append((ordered, rw))
            max_row_w = max(max_row_w, rw)

        y = start_y
        max_right = 0.0
        for ordered, rw in row_data:
            offset_x = BOUND_PAD + (max_row_w - rw) / 2.0
            x = offset_x
            row_h = 0.0
            for cid in ordered:
                r = self.rects[cid]
                r.x = x
                r.y = y
                x += r.w + H_GAP
                row_h = max(row_h, r.h)
            max_right = max(max_right, x - H_GAP + BOUND_PAD)
            y += row_h + V_GAP

        return max_right, y - start_y - V_GAP

    def _layout_boundary(self, bid: str):
        if bid in self._processed:
            return
        for ctype, cid in self._children.get(bid, []):
            if ctype == "bound":
                self._layout_boundary(cid)

        content_w, content_h = self._layout_container(bid, BOUND_HEADER + BOUND_PAD + 4)

        b = self._bound_map[bid]
        label_w = len(b.label) * 9 + 40
        total_w = max(content_w, 280, label_w)
        total_h = max(BOUND_HEADER + BOUND_PAD + content_h + BOUND_PAD, 110)
        self.rects[bid] = _Rect(w=total_w, h=total_h)
        self._processed.add(bid)

    def _abs_center(self, node_id: str) -> tuple[float, float]:
        r = self.rects.get(node_id)
        if not r:
            return 0.0, 0.0
        cx, cy = r.x + r.w / 2, r.y + r.h / 2
        pid = self._parent_of.get(node_id)
        while pid:
            pr = self.rects.get(pid)
            if pr:
                cx += pr.x
                cy += pr.y
            pid = self._parent_of.get(pid)
        return cx, cy

    def _barycenter_x(self, node_id: str) -> float | None:
        xs: list[float] = []
        descendants: set[str] = set()
        if node_id in self._bound_map:
            descendants = self._all_descendants(node_id)
        descendants.add(node_id)

        for rel in self.d.relationships:
            if rel.source_id in descendants:
                tx, _ = self._abs_center(rel.target_id)
                xs.append(tx)
            if rel.target_id in descendants:
                sx, _ = self._abs_center(rel.source_id)
                xs.append(sx)
        return sum(xs) / len(xs) if xs else None

    def _barycenter_sort(self, ids: list[str]) -> list[str]:
        with_bc: list[tuple[float, str]] = []
        without_bc: list[str] = []
        for cid in ids:
            bc = self._barycenter_x(cid)
            if bc is not None:
                with_bc.append((bc, cid))
            else:
                without_bc.append(cid)
        with_bc.sort(key=lambda t: t[0])
        return [cid for _, cid in with_bc] + without_bc

    def _target_depth(self, node_id: str) -> int:
        depth = 0
        pid = self._parent_of.get(node_id)
        while pid:
            depth += 1
            pid = self._parent_of.get(pid)
        return depth

    def _detect_satellites(self) -> dict[str, str]:
        root_comps = {
            cid for ctype, cid in self._children.get(None, [])
            if ctype == "comp"
        }
        if not root_comps:
            return {}

        max_y = 0.0
        for r in self.rects.values():
            max_y = max(max_y, r.y + r.h)
        if max_y < 600:
            return {}

        satellites: dict[str, str] = {}
        for cid in root_comps:
            neighbours: list[str] = []
            for rel in self.d.relationships:
                if rel.source_id == cid:
                    neighbours.append(rel.target_id)
                elif rel.target_id == cid:
                    neighbours.append(rel.source_id)
            if not neighbours:
                continue

            all_deep = all(self._target_depth(n) >= 1 for n in neighbours)
            if not all_deep:
                continue

            ys = [self._abs_center(n)[1] for n in neighbours]
            avg_y = sum(ys) / len(ys)
            min_y = min(ys)

            if min_y < max_y * 0.5:
                continue
            if avg_y < max_y * 0.6:
                continue

            boundary_counts: dict[str, int] = {}
            for n in neighbours:
                pid = self._parent_of.get(n)
                outermost = pid
                while pid:
                    outermost = pid
                    pid = self._parent_of.get(pid)
                if outermost:
                    boundary_counts[outermost] = boundary_counts.get(outermost, 0) + 1

            if boundary_counts:
                best_boundary = max(boundary_counts, key=lambda b: boundary_counts[b])
                satellites[cid] = best_boundary

        return satellites

    def _layout_root(self):
        children = self._children.get(None, [])
        if not children:
            return

        child_ids = {cid for _, cid in children}
        child_map = {cid: ct for ct, cid in children}

        satellites = self._detect_satellites()
        non_satellite_ids = child_ids - set(satellites.keys())

        rows = self._assign_rows(non_satellite_ids, None)

        root_v_gap = 44

        def _place_rows(row_orderer):
            sub_rows: list[tuple[list[str], float]] = []
            y = 60.0
            for row_num in sorted(rows.keys()):
                ids_in_row = rows[row_num]
                comps_in_row = [cid for cid in ids_in_row if child_map.get(cid) != "bound"]
                bounds_in_row = [cid for cid in ids_in_row if child_map.get(cid) == "bound"]

                if comps_in_row:
                    ordered = row_orderer(comps_in_row)
                    sub_rows.append((ordered, y))
                    row_h = max(self.rects[cid].h for cid in ordered)
                    y += row_h + root_v_gap

                if bounds_in_row:
                    if comps_in_row:
                        y += 10
                    ordered = row_orderer(bounds_in_row)
                    sub_rows.append((ordered, y))
                    row_h = max(self.rects[cid].h for cid in ordered)
                    y += row_h + root_v_gap

            max_rw = 0.0
            for ordered, _ in sub_rows:
                rw = self._row_width(ordered)
                max_rw = max(max_rw, rw)

            margin_x = 30.0
            for ordered, row_y in sub_rows:
                rw = self._row_width(ordered)
                offset_x = margin_x + (max_rw - rw) / 2.0
                x = offset_x
                for cid in ordered:
                    r = self.rects[cid]
                    r.x = x
                    r.y = row_y
                    x += r.w + H_GAP

        _place_rows(self._order_row)

        def _bc_order(ids: list[str]) -> list[str]:
            base = self._order_row(ids)
            return self._barycenter_sort(base)

        _place_rows(_bc_order)

        if satellites:
            self._place_satellites(satellites)

    def _place_satellites(self, satellites: dict[str, str]):
        by_boundary: dict[str, list[str]] = {}
        for sat_id, bound_id in satellites.items():
            by_boundary.setdefault(bound_id, []).append(sat_id)

        for bound_id, sat_ids in by_boundary.items():
            br = self.rects.get(bound_id)
            if not br:
                continue

            bound_right_x = br.x + br.w + H_GAP

            def _avg_target_y(sid: str) -> float:
                neighbours = []
                for rel in self.d.relationships:
                    if rel.source_id == sid:
                        neighbours.append(rel.target_id)
                    elif rel.target_id == sid:
                        neighbours.append(rel.source_id)
                if not neighbours:
                    return br.y + br.h / 2
                ys = [self._abs_center(n)[1] for n in neighbours]
                return sum(ys) / len(ys)

            sat_ids.sort(key=_avg_target_y)

            total_h = sum(self.rects[s].h for s in sat_ids) + V_GAP * (len(sat_ids) - 1)
            avg_y = sum(_avg_target_y(s) for s in sat_ids) / len(sat_ids)
            start_y = avg_y - total_h / 2

            x = bound_right_x
            y = start_y
            for sat_id in sat_ids:
                sr = self.rects[sat_id]
                sr.x = x
                sr.y = y
                y += sr.h + V_GAP


def generate(diagram: Diagram) -> str:
    """Generate draw.io XML string from a parsed Diagram model."""
    layout = _LayoutEngine(diagram)
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
        if comp.tags and tag_styles:
            for tag in comp.tags:
                if tag in tag_styles:
                    ts = tag_styles[tag]
                    if ts.bg_color:
                        bg_color = ts.bg_color
                    if ts.font_color:
                        font_color = ts.font_color if ts.font_color != "white" else "#FFFFFF"
                    break

        cell = ET.SubElement(root, "mxCell")
        cell.set("id", cell_id)
        cell.set("value", _html_value(comp, tag_styles))
        cell.set("style", _comp_style(bool(icon_path), bg_color, font_color))
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
            entry_w = 180
            cols = 4
            row_h = 22

            ordered_tags = [t for t in tag_styles if t in used_tags]

            for i, tag_name in enumerate(ordered_tags):
                ts = tag_styles[tag_name]
                col = i % cols
                row = i // cols
                x = legend_x + col * entry_w
                y = legend_y + row * row_h

                swatch = ET.SubElement(root, "mxCell")
                swatch.set("id", f"legend_sw_{i}")
                swatch.set("value", "")
                swatch.set(
                    "style",
                    f"rounded=1;whiteSpace=wrap;html=1;fillColor={ts.bg_color or '#CCCCCC'};"
                    f"strokeColor={ts.bg_color or '#CCCCCC'};arcSize=20;",
                )
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

    def _port_hints(
        src_id: str, tgt_id: str
    ) -> tuple[float | None, float | None, float | None, float | None]:
        if not _share_boundary(src_id, tgt_id):
            sd, td = _boundary_depth_edge(src_id), _boundary_depth_edge(tgt_id)
            if abs(sd - td) > 1:
                return None, None, None, None

        sx, sy = _abs_center(src_id)
        tx, ty = _abs_center(tgt_id)
        dx, dy = tx - sx, ty - sy
        adx, ady = abs(dx), abs(dy)
        if adx < 1 and ady < 1:
            return None, None, None, None

        exit_x_val: float | None = None
        exit_y_val: float | None = None
        entry_x_val: float | None = None
        entry_y_val: float | None = None

        targets_for_src = _source_fanout.get(src_id, [])
        if len(targets_for_src) >= 3:
            tgt_positions = sorted(
                [(_abs_center(t)[0], t) for t in targets_for_src],
                key=lambda p: p[0],
            )
            tgt_ids_sorted = [t for _, t in tgt_positions]
            if tgt_id in tgt_ids_sorted:
                idx = tgt_ids_sorted.index(tgt_id)
                n = len(tgt_ids_sorted)
                spread = 0.15 + 0.7 * (idx / max(n - 1, 1))
                if ady >= adx:
                    exit_x_val = round(spread, 2)
                    exit_y_val = 1.0 if dy > 0 else 0.0
                else:
                    exit_y_val = round(spread, 2)
                    exit_x_val = 1.0 if dx > 0 else 0.0

        sources_for_tgt = _target_fanin.get(tgt_id, [])
        if len(sources_for_tgt) >= 3:
            src_positions = sorted(
                [(_abs_center(s)[0], s) for s in sources_for_tgt],
                key=lambda p: p[0],
            )
            src_ids_sorted = [s for _, s in src_positions]
            if src_id in src_ids_sorted:
                idx = src_ids_sorted.index(src_id)
                n = len(src_ids_sorted)
                spread = 0.15 + 0.7 * (idx / max(n - 1, 1))
                if ady >= adx:
                    entry_x_val = round(spread, 2)
                    entry_y_val = 0.0 if dy > 0 else 1.0
                else:
                    entry_y_val = round(spread, 2)
                    entry_x_val = 0.0 if dx > 0 else 1.0

        if exit_x_val is None and exit_y_val is None:
            if ady >= adx:
                exit_x_val = 0.5
                exit_y_val = 1.0 if dy > 0 else 0.0
            else:
                exit_x_val = 1.0 if dx > 0 else 0.0
                exit_y_val = 0.5
        if entry_x_val is None and entry_y_val is None:
            if ady >= adx:
                entry_x_val = 0.5
                entry_y_val = 0.0 if dy > 0 else 1.0
            else:
                entry_x_val = 0.0 if dx > 0 else 1.0
                entry_y_val = 0.5

        return exit_x_val, exit_y_val, entry_x_val, entry_y_val

    # Build edges (merge bidirectional pairs)
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
        ex, ey, nx, ny = _port_hints(src_id, tgt_id)

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

        if label:
            pt = ET.SubElement(eg, "mxPoint")
            pt.set("as", "offset")
            pt.set("x", "0")
            pt.set("y", "0")

    ET.indent(mxfile, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        mxfile, encoding="unicode"
    )
