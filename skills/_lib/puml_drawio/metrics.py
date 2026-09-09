"""Geometry quality metrics for generated draw.io diagrams.

The point of this module is to turn "the diagram looks bad" into numbers that a
test can gate on. Everything is measured from the emitted .drawio XML, so it
scores exactly what the renderer will draw — not what the layout engine
intended.

Metrics:
  edge_node_crossings  edges whose path cuts through a node box (the big one:
                       this is what "lines crossing boxes" actually is)
  edge_edge_crossings  pairs of edge segments that cross
  label_overlap_area   px^2 of edge-label area sitting on top of a node
  node_overlap_area    px^2 of node-on-node overlap (should always be 0)
  aspect_ratio         width/height of the drawing's bounding box

Edges without explicit waypoints are scored as the straight line between the
two node centres. That is deliberately pessimistic-but-honest: draw.io's
orthogonal router does not avoid obstacles, so an unrouted edge crossing a node
in the straight-line approximation will, in practice, cross something.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Box:
    id: str
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass(frozen=True)
class Segment:
    x1: float
    y1: float
    x2: float
    y2: float


_EPS = 1e-9


def _overlap_area(a: Box, b: Box) -> float:
    dx = min(a.x2, b.x2) - max(a.x, b.x)
    dy = min(a.y2, b.y2) - max(a.y, b.y)
    return dx * dy if dx > 0 and dy > 0 else 0.0


def _seg_intersects_box(s: Segment, b: Box) -> bool:
    """True if the segment passes through the box interior.

    Liang-Barsky clip. A segment that merely runs along an edge of the box, or
    touches a corner, is NOT counted — that is an edge attaching to a node, not
    cutting through it.
    """
    dx = s.x2 - s.x1
    dy = s.y2 - s.y1
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, s.x1 - b.x),
        (dx, b.x2 - s.x1),
        (-dy, s.y1 - b.y),
        (dy, b.y2 - s.y1),
    ):
        if abs(p) < _EPS:
            if q < 0:
                return False        # parallel and outside
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return False
            t0 = max(t0, r)
        else:
            if r < t0:
                return False
            t1 = min(t1, r)
    if t1 - t0 <= _EPS:
        return False
    # The clipped portion must have real extent inside the box, not just graze it.
    mx = s.x1 + dx * (t0 + t1) / 2
    my = s.y1 + dy * (t0 + t1) / 2
    return (b.x + _EPS < mx < b.x2 - _EPS) and (b.y + _EPS < my < b.y2 - _EPS)


def _orient(ax, ay, bx, by, cx, cy) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segments_cross(a: Segment, b: Segment) -> bool:
    """Proper crossing only: shared endpoints and collinear touching don't count."""
    pts_a = {(round(a.x1, 6), round(a.y1, 6)), (round(a.x2, 6), round(a.y2, 6))}
    pts_b = {(round(b.x1, 6), round(b.y1, 6)), (round(b.x2, 6), round(b.y2, 6))}
    if pts_a & pts_b:
        return False
    d1 = _orient(a.x1, a.y1, a.x2, a.y2, b.x1, b.y1)
    d2 = _orient(a.x1, a.y1, a.x2, a.y2, b.x2, b.y2)
    d3 = _orient(b.x1, b.y1, b.x2, b.y2, a.x1, a.y1)
    d4 = _orient(b.x1, b.y1, b.x2, b.y2, a.x2, a.y2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _style_ports(style: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in style.split(";"):
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        k = k.strip()
        if k in ("exitX", "exitY", "entryX", "entryY"):
            try:
                out[k] = float(v)
            except ValueError:
                pass
    return out


def _attach_point(box: Box, fx: float | None, fy: float | None) -> tuple[float, float]:
    """Resolve a draw.io exit/entry fraction to an absolute point on the box."""
    if fx is None or fy is None:
        return (box.cx, box.cy)
    return (box.x + box.w * fx, box.y + box.h * fy)


@dataclass
class Metrics:
    node_count: int = 0
    edge_count: int = 0
    edge_node_crossings: int = 0
    edge_edge_crossings: int = 0
    label_overlap_area: float = 0.0
    node_overlap_area: float = 0.0
    aspect_ratio: float = 0.0
    width: float = 0.0
    height: float = 0.0
    boxes: list[Box] = field(default_factory=list)
    crossing_detail: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.node_count} nodes, {self.edge_count} edges | "
            f"edge-node crossings: {self.edge_node_crossings} | "
            f"edge-edge crossings: {self.edge_edge_crossings} | "
            f"label overlap: {self.label_overlap_area:.0f}px2 | "
            f"node overlap: {self.node_overlap_area:.0f}px2 | "
            f"{self.width:.0f}x{self.height:.0f} (ar {self.aspect_ratio:.2f})"
        )

    def is_worse_than(self, other: "Metrics") -> bool:
        return (
            self.edge_node_crossings > other.edge_node_crossings
            or self.edge_edge_crossings > other.edge_edge_crossings
            or self.label_overlap_area > other.label_overlap_area * 1.05
        )


# Rough glyph advance for the 9px edge-label font draw.io uses.
_LABEL_CHAR_W = 5.0
_LABEL_H = 12.0


def measure(xml_text: str) -> Metrics:
    root = ET.fromstring(xml_text)

    cells = {}
    for cell in root.iter("mxCell"):
        cells[cell.get("id")] = cell

    # Resolve absolute positions: a child cell's geometry is relative to its parent.
    abs_pos: dict[str, tuple[float, float]] = {}

    def resolve(cid: str) -> tuple[float, float]:
        if cid in abs_pos:
            return abs_pos[cid]
        cell = cells.get(cid)
        if cell is None:
            return (0.0, 0.0)
        geo = cell.find("mxGeometry")
        x = float(geo.get("x", 0)) if geo is not None else 0.0
        y = float(geo.get("y", 0)) if geo is not None else 0.0
        parent = cell.get("parent")
        if parent and parent not in ("0", "1") and parent in cells:
            px, py = resolve(parent)
            x += px
            y += py
        abs_pos[cid] = (x, y)
        return (x, y)

    boxes: list[Box] = []
    box_by_id: dict[str, Box] = {}
    boundary_ids: set[str] = set()
    for cid, cell in cells.items():
        if cell.get("vertex") != "1" or cid in ("0", "1"):
            continue
        if cid.startswith("legend_") or cid == "title":
            continue
        geo = cell.find("mxGeometry")
        if geo is None:
            continue
        x, y = resolve(cid)
        w = float(geo.get("width", 0))
        h = float(geo.get("height", 0))
        style = cell.get("style") or ""
        b = Box(id=cid, x=x, y=y, w=w, h=h)
        if "swimlane" in style:
            boundary_ids.add(cid)
        # icon sub-cells are decoration, not obstacles
        if "shape=image" in style:
            continue
        boxes.append(b)
        box_by_id[cid] = b

    # Only leaf nodes are obstacles. A boundary legitimately contains its
    # children and edges legitimately enter it.
    obstacles = [b for b in boxes if b.id not in boundary_ids]

    m = Metrics()
    m.boxes = boxes
    m.node_count = len(obstacles)

    all_segments: list[tuple[str, Segment]] = []
    label_boxes: list[tuple[str, Box]] = []

    for cid, cell in cells.items():
        if cell.get("edge") != "1":
            continue
        m.edge_count += 1
        geo = cell.find("mxGeometry")
        pts: list[tuple[float, float]] = []

        src, tgt = cell.get("source"), cell.get("target")
        ports = _style_ports(cell.get("style") or "")
        if src in box_by_id:
            pts.append(_attach_point(box_by_id[src],
                                     ports.get("exitX"), ports.get("exitY")))
        arr = geo.find("Array[@as='points']") if geo is not None else None
        if arr is not None:
            for p in arr.findall("mxPoint"):
                pts.append((float(p.get("x", 0)), float(p.get("y", 0))))
        if tgt in box_by_id:
            pts.append(_attach_point(box_by_id[tgt],
                                     ports.get("entryX"), ports.get("entryY")))

        if len(pts) < 2:
            continue

        segs = [
            Segment(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            for i in range(len(pts) - 1)
        ]
        for s in segs:
            all_segments.append((cid, s))
            for b in obstacles:
                # the two endpoints' own nodes are not obstacles for this edge
                if b.id in (src, tgt):
                    continue
                if _seg_intersects_box(s, b):
                    m.edge_node_crossings += 1
                    m.crossing_detail.append((cid, b.id))

        value = cell.get("value") or ""
        if value:
            mid = segs[len(segs) // 2]
            lx = (mid.x1 + mid.x2) / 2
            ly = (mid.y1 + mid.y2) / 2
            lw = len(value) * _LABEL_CHAR_W
            label_boxes.append(
                (cid, Box(id=f"lbl_{cid}", x=lx - lw / 2, y=ly - _LABEL_H / 2,
                          w=lw, h=_LABEL_H))
            )

    for i in range(len(all_segments)):
        eid_a, sa = all_segments[i]
        for j in range(i + 1, len(all_segments)):
            eid_b, sb = all_segments[j]
            if eid_a == eid_b:
                continue
            if _segments_cross(sa, sb):
                m.edge_edge_crossings += 1

    for _, lb in label_boxes:
        for b in obstacles:
            m.label_overlap_area += _overlap_area(lb, b)

    for i in range(len(obstacles)):
        for j in range(i + 1, len(obstacles)):
            m.node_overlap_area += _overlap_area(obstacles[i], obstacles[j])

    if boxes:
        minx = min(b.x for b in boxes)
        miny = min(b.y for b in boxes)
        maxx = max(b.x2 for b in boxes)
        maxy = max(b.y2 for b in boxes)
        m.width = maxx - minx
        m.height = maxy - miny
        m.aspect_ratio = m.width / m.height if m.height else 0.0

    return m


def measure_file(path) -> Metrics:
    from pathlib import Path
    return measure(Path(path).read_text(encoding="utf-8"))
