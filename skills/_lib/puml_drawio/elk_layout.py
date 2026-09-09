"""ELK layout backend.

Runs the Eclipse Layout Kernel over a parsed Diagram and returns node geometry
plus fully-routed orthogonal edges with bend points and edge-label positions.

Why ELK: draw.io's own orthogonal router is local — it routes around an edge's
endpoints, never around the nodes in between — so any edge spanning more than
adjacent ranks is drawn straight through whatever sits in its way. ELK does
global, hierarchy-aware, obstacle-avoiding orthogonal routing and hands back
exact bend points, which draw.io honours via <Array as="points">.

Why this JAR: ELK (plus its EMF and Guava dependencies) is bundled inside
plantuml.jar, which the diagram toolchain already downloads. No extra
dependency, works offline.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .puml_parser import Diagram

_DRIVER_SRC = Path(__file__).parent / "elk" / "ElkDriver.java"

# Defaults chosen for C4-style diagrams: top-down flow, orthogonal edges, and
# enough room between ranks for edge labels to sit without touching a node.
DEFAULT_OPTIONS: dict[str, str] = {
    "direction": "DOWN",
    "edgeRouting": "ORTHOGONAL",
    "spacing.nodeNode": "40",
    "spacing.edgeNode": "20",
    "spacing.edgeEdge": "14",
    "spacing.edgeLabel": "6",
    "layered.spacing.nodeNodeBetweenLayers": "60",
    "layered.thoroughness": "20",
    "layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
    "edgeLabels.placement": "CENTER",
    "layered.edgeLabels.sideSelection": "SMART_DOWN",
    # Respect declaration order within a layer, which is how Lay_R/Lay_L hints
    # are honoured (see _ordered_components).
    "layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    "separateConnectedComponents": "false",
}


def plantuml_jar() -> Path | None:
    env = os.environ.get("PLANTUML_JAR")
    if env and Path(env).is_file():
        return Path(env)
    default = Path.home() / ".local/share/plantuml/plantuml.jar"
    return default if default.is_file() else None


def cache_dir() -> Path:
    return Path.home() / ".cache" / "puml_drawio" / "elk"


def available() -> bool:
    return bool(
        shutil.which("java")
        and shutil.which("javac")
        and plantuml_jar()
        and _DRIVER_SRC.is_file()
    )


def ensure_compiled() -> Path:
    """Compile ElkDriver.java on first use; reuse the cached class thereafter."""
    out = cache_dir()
    cls = out / "ElkDriver.class"
    if cls.is_file() and cls.stat().st_mtime >= _DRIVER_SRC.stat().st_mtime:
        return out
    jar = plantuml_jar()
    if jar is None:
        raise RuntimeError("plantuml.jar not found; set PLANTUML_JAR")
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["javac", "-cp", str(jar), "-d", str(out), str(_DRIVER_SRC)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ElkDriver compile failed:\n{proc.stderr}")
    return out


@dataclass
class EdgeRoute:
    """Absolute polyline for one edge, plus its absolute label rect."""
    points: list[tuple[float, float]] = field(default_factory=list)
    label: tuple[float, float, float, float] | None = None
    container: str = "-"


@dataclass
class ElkResult:
    # id -> (x, y, w, h), PARENT-RELATIVE, which is what draw.io wants for cells
    nodes: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    edges: dict[str, EdgeRoute] = field(default_factory=dict)
    parent_of: dict[str, str | None] = field(default_factory=dict)
    width: float = 0.0
    height: float = 0.0

    def abs_origin(self, node_id: str) -> tuple[float, float]:
        x = y = 0.0
        cur: str | None = node_id
        seen: set[str] = set()
        while cur and cur in self.nodes and cur not in seen:
            seen.add(cur)
            nx, ny, _, _ = self.nodes[cur]
            x += nx
            y += ny
            cur = self.parent_of.get(cur)
        return x, y

    def abs_rect(self, node_id: str) -> tuple[float, float, float, float]:
        _, _, w, h = self.nodes[node_id]
        x, y = self.abs_origin(node_id)
        return x, y, w, h


def _edge_key(src: str, tgt: str) -> str:
    return f"{src}->{tgt}"


# Rough glyph advance for the 9px edge-label font draw.io renders.
_LABEL_CHAR_W = 5.0
_LABEL_LINE_H = 12.0
_LABEL_MAX_W = 190.0


def _default_label_size(rel) -> tuple[float, float]:
    """Size an edge label so ELK reserves real space for it.

    Reserving space is what stops labels landing on top of nodes, and it is why
    labels no longer have to be truncated to fit.
    """
    text = (rel.label or rel.technology or "").split("\\n")[0].strip()
    if not text:
        return (0.0, 0.0)
    w = len(text) * _LABEL_CHAR_W
    if w <= _LABEL_MAX_W:
        return (w, _LABEL_LINE_H)
    lines = -(-w // _LABEL_MAX_W)          # ceil: wrap onto N lines
    return (_LABEL_MAX_W, _LABEL_LINE_H * lines)


def _ordered_components(diagram: Diagram) -> list:
    """Order components so Lay_R / Lay_L hints are respected.

    ELK has no "place B to the right of A" constraint, but with
    considerModelOrder it preserves declaration order within a layer. So we
    translate the hints into an emission order via a topological sort:
    Lay_R(a, b) means a before b; Lay_L(a, b) means b before a.

    Cycles and hints referencing unknown ids are ignored rather than fatal —
    a contradictory hint should not stop the diagram rendering.
    """
    comps = list(diagram.components)
    index = {c.id: i for i, c in enumerate(comps)}
    if not comps:
        return comps

    succ: dict[str, set[str]] = {c.id: set() for c in comps}
    indeg: dict[str, int] = {c.id: 0 for c in comps}
    for h in getattr(diagram, "layout_hints", []):
        a, b = h.source_id, h.target_id
        if h.hint_type == "R":
            first, second = a, b
        elif h.hint_type == "L":
            first, second = b, a
        else:
            continue                       # D/U are handled by edge direction
        if first not in succ or second not in succ or second in succ[first]:
            continue
        succ[first].add(second)
        indeg[second] += 1

    import heapq
    ready = [index[c.id] for c in comps if indeg[c.id] == 0]
    heapq.heapify(ready)
    by_index = {index[c.id]: c for c in comps}
    out: list = []
    while ready:
        i = heapq.heappop(ready)
        c = by_index[i]
        out.append(c)
        for nxt in sorted(succ[c.id], key=lambda s: index[s]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(ready, index[nxt])
    if len(out) != len(comps):             # cycle: fall back to source order
        return comps
    return out


def layout(
    diagram: Diagram,
    *,
    size_of=None,
    label_size_of=None,
    boundary_header: float = 30.0,
    boundary_pad: float = 20.0,
    options: dict[str, str] | None = None,
    overrides: dict | None = None,
) -> ElkResult:
    """Lay out `diagram` with ELK.

    size_of(component)       -> (w, h)   defaults to a plain C4 box
    label_size_of(rel)       -> (w, h)   0,0 to suppress the label
    """
    opts = dict(DEFAULT_OPTIONS)
    if options:
        opts.update(options)

    if size_of is None:
        size_of = lambda c: (155.0, 92.0)          # noqa: E731
    if label_size_of is None:
        label_size_of = _default_label_size

    parent_of: dict[str, str | None] = {}
    lines: list[str] = [f"OPT {k} {v}" for k, v in opts.items()]

    # Boundaries first, outermost first, so parents always precede children.
    boundaries = list(diagram.boundaries)
    emitted: set[str] = set()
    progressed = True
    while progressed:
        progressed = False
        for b in boundaries:
            if b.id in emitted:
                continue
            if b.parent_boundary and b.parent_boundary not in emitted:
                continue
            lines.append(f"NODE {b.id} {b.parent_boundary or '-'} 0 0")
            lines.append(
                f"PAD {b.id} {boundary_header} {boundary_pad} {boundary_pad} {boundary_pad}"
            )
            # Keep the boundary at least as wide as its own title bar, so a long
            # heading cannot wrap down on top of the nodes inside it.
            title_w = len(b.label) * 7.0 + 2 * boundary_pad
            lines.append(f"MINSIZE {b.id} {title_w:.1f} {boundary_header + 20:.1f}")
            parent_of[b.id] = b.parent_boundary
            emitted.add(b.id)
            progressed = True

    for c in _ordered_components(diagram):
        w, h = size_of(c)
        lines.append(f"NODE {c.id} {c.parent_boundary or '-'} {w:.1f} {h:.1f}")
        parent_of[c.id] = c.parent_boundary

    known = set(parent_of)
    # considerModelOrder weighs edge declaration order as well as node order,
    # so edges must be emitted consistently with _ordered_components or the two
    # signals fight and the Lay_* hint loses.
    order_index = {c.id: i for i, c in enumerate(_ordered_components(diagram))}
    rels = sorted(
        diagram.relationships,
        key=lambda r: (
            order_index.get(r.source_id, 1 << 30),
            order_index.get(r.target_id, 1 << 30),
        ),
    )
    for rel in rels:
        if rel.source_id not in known or rel.target_id not in known:
            continue
        lw, lh = label_size_of(rel)
        lines.append(
            f"EDGE {_edge_key(rel.source_id, rel.target_id)} "
            f"{rel.source_id} {rel.target_id} {lw:.1f} {lh:.1f}"
        )

    if not diagram.components and not diagram.boundaries:
        return ElkResult()

    classes = ensure_compiled()
    jar = plantuml_jar()
    proc = subprocess.run(
        ["java", "-cp", f"{jar}:{classes}", "ElkDriver"],
        input="\n".join(lines),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ELK layout failed:\n{proc.stderr[:2000]}")

    raw = json.loads(proc.stdout)

    res = ElkResult(parent_of=parent_of)
    res.width = raw["root"]["w"]
    res.height = raw["root"]["h"]
    for nid, (x, y, w, h) in raw["nodes"].items():
        res.nodes[nid] = (x, y, w, h)

    for eid, e in raw.get("edges", {}).items():
        cid = e.get("container", "-")
        ox, oy = (0.0, 0.0) if cid == "-" else res.abs_origin(cid)
        pts = [tuple(e["start"])] + [tuple(b) for b in e["bends"]] + [tuple(e["end"])]
        route = EdgeRoute(
            points=[(p[0] + ox, p[1] + oy) for p in pts],
            container=cid,
        )
        if "label" in e:
            lx, ly, lw, lh = e["label"]
            route.label = (lx + ox, ly + oy, lw, lh)
        res.edges[eid] = route

    _apply_overrides(res, overrides)
    return res


def load_overrides(puml_path) -> dict:
    """Read `<name>.overrides.json` sitting beside the .puml, if present."""
    p = Path(puml_path).with_suffix("")
    sidecar = p.parent / f"{p.name}.overrides.json"
    if not sidecar.is_file():
        return {}
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed overrides file {sidecar}: {e}") from e


def _apply_overrides(res: ElkResult, overrides: dict | None) -> None:
    """Merge hand-polish nudges over the computed layout.

    Anything not mentioned keeps its computed value, and unknown ids are
    ignored so a stale sidecar never breaks a build.
    """
    if not overrides:
        return
    for nid, o in (overrides.get("nodes") or {}).items():
        if nid not in res.nodes:
            continue
        x, y, w, h = res.nodes[nid]
        res.nodes[nid] = (
            float(o.get("x", x)), float(o.get("y", y)),
            float(o.get("w", w)), float(o.get("h", h)),
        )
    for eid, o in (overrides.get("edges") or {}).items():
        route = res.edges.get(eid)
        if route is None:
            continue
        if "points" in o:
            route.points = [(float(a), float(b)) for a, b in o["points"]]
        if "label" in o:
            lx, ly, lw, lh = o["label"]
            route.label = (float(lx), float(ly), float(lw), float(lh))
