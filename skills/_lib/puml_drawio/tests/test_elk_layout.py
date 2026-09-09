"""Tests for the ELK layout backend.

These are integration tests: they compile and run the real ELK from
plantuml.jar. If the toolchain is missing the whole module skips, so the suite
still runs on a machine without Java.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from puml_drawio import elk_layout
from puml_drawio.puml_parser import parse

pytestmark = pytest.mark.skipif(
    not elk_layout.available(), reason="java/plantuml.jar not available"
)


def _layout(src: str, **opts):
    return elk_layout.layout(parse(src), **opts)


class TestBasicLayout:
    SRC = '''@startuml
Container(a, "A", ".NET", "d")
Container(b, "B", ".NET", "d")
Rel(a, b, "calls")
@enduml'''

    def test_returns_a_rect_per_component(self):
        r = _layout(self.SRC)
        assert set(r.nodes) == {"a", "b"}

    def test_nodes_do_not_overlap(self):
        r = _layout(self.SRC)
        a, b = r.abs_rect("a"), r.abs_rect("b")
        assert a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1] or \
               a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]

    def test_edge_has_a_route(self):
        r = _layout(self.SRC)
        assert len(r.edges) == 1
        route = next(iter(r.edges.values()))
        assert len(route.points) >= 2

    def test_direction_down_puts_target_below_source(self):
        r = _layout(self.SRC)
        assert r.abs_rect("a")[1] < r.abs_rect("b")[1]

    def test_reports_drawing_size(self):
        r = _layout(self.SRC)
        assert r.width > 0 and r.height > 0


class TestHierarchy:
    SRC = '''@startuml
System_Boundary(zone, "Zone") {
    Container(a, "A", ".NET", "d")
    Container(b, "B", ".NET", "d")
}
Container(out, "Out", ".NET", "d")
Rel(a, b, "in-zone")
Rel(out, a, "into zone")
@enduml'''

    def test_boundary_is_laid_out(self):
        r = _layout(self.SRC)
        assert "zone" in r.nodes

    def test_boundary_is_big_enough_for_its_children(self):
        r = _layout(self.SRC)
        _, _, zw, zh = r.nodes["zone"]
        for cid in ("a", "b"):
            cx, cy, cw, ch = r.nodes[cid]
            assert cx >= 0 and cy >= 0
            assert cx + cw <= zw + 0.5, f"{cid} overflows boundary width"
            assert cy + ch <= zh + 0.5, f"{cid} overflows boundary height"

    def test_child_coords_are_parent_relative(self):
        """draw.io positions child cells relative to their parent swimlane."""
        r = _layout(self.SRC)
        zx, zy, _, _ = r.nodes["zone"]
        ax, ay, _, _ = r.nodes["a"]
        assert r.abs_rect("a")[0] == pytest.approx(zx + ax)
        assert r.abs_rect("a")[1] == pytest.approx(zy + ay)

    def test_boundary_reserves_header_room(self):
        r = _layout(self.SRC, boundary_header=30)
        _, _, _, _ = r.nodes["zone"]
        topmost = min(r.nodes[c][1] for c in ("a", "b"))
        assert topmost >= 30, "children must clear the boundary title bar"

    def test_edge_points_are_absolute(self):
        """Edges are parented to the graph root in draw.io, so routes must be
        converted out of their ELK container's coordinate space."""
        r = _layout(self.SRC)
        route = r.edges["a->b"] if "a->b" in r.edges else None
        assert route is not None
        zx, zy, _, _ = r.nodes["zone"]
        # the a->b edge lives inside the zone; absolute points must be shifted
        assert all(p[0] >= zx - 1 for p in route.points)


class TestObstacleAvoidance:
    """The whole point of the exercise."""

    SRC = '''@startuml
Container(top, "Top", ".NET", "d")
Container(mid, "Mid", ".NET", "d")
Container(bot, "Bot", ".NET", "d")
Rel(top, mid, "1")
Rel(mid, bot, "2")
Rel(top, bot, "skips a rank")
@enduml'''

    def test_rank_skipping_edge_does_not_cross_the_middle_node(self):
        from puml_drawio.metrics import Box, Segment, _seg_intersects_box
        r = _layout(self.SRC)
        mx, my, mw, mh = r.abs_rect("mid")
        mid_box = Box(id="mid", x=mx, y=my, w=mw, h=mh)
        route = r.edges["top->bot"]
        pts = route.points
        for i in range(len(pts) - 1):
            seg = Segment(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            assert not _seg_intersects_box(seg, mid_box), \
                "ELK routed the rank-skipping edge straight through 'mid'"


class TestEdgeLabels:
    SRC = '''@startuml
Container(a, "A", ".NET", "d")
Container(b, "B", ".NET", "d")
Rel(a, b, "a fairly long edge label that needs room")
@enduml'''

    def test_label_gets_geometry(self):
        r = _layout(self.SRC)
        route = next(iter(r.edges.values()))
        assert route.label is not None
        assert route.label[2] > 0 and route.label[3] > 0

    def test_label_does_not_sit_on_a_node(self):
        from puml_drawio.metrics import Box, _overlap_area
        r = _layout(self.SRC)
        route = next(iter(r.edges.values()))
        lx, ly, lw, lh = route.label
        lbl = Box(id="l", x=lx, y=ly, w=lw, h=lh)
        for nid in ("a", "b"):
            nx, ny, nw, nh = r.abs_rect(nid)
            assert _overlap_area(lbl, Box(id=nid, x=nx, y=ny, w=nw, h=nh)) == 0


class TestToolchain:
    def test_available_reports_true_here(self):
        assert elk_layout.available()

    def test_driver_is_cached_after_first_use(self):
        elk_layout.ensure_compiled()
        assert (elk_layout.cache_dir() / "ElkDriver.class").exists()

    def test_empty_diagram_does_not_explode(self):
        r = _layout('@startuml\n@enduml')
        assert r.nodes == {}


class TestSidecarOverrides:
    """Hand-polish lives in a sidecar, not in the generated .drawio.

    That keeps regeneration non-destructive and keeps the polish reviewable in
    version control.
    """

    SRC = '''@startuml
Container(a, "A", ".NET", "d")
Container(b, "B", ".NET", "d")
Rel(a, b, "calls")
@enduml'''

    def test_node_position_override(self):
        r = _layout(self.SRC, overrides={"nodes": {"a": {"x": 999, "y": 888}}})
        x, y, _, _ = r.nodes["a"]
        assert (x, y) == (999, 888)

    def test_node_size_override(self):
        r = _layout(self.SRC, overrides={"nodes": {"a": {"w": 300, "h": 120}}})
        _, _, w, h = r.nodes["a"]
        assert (w, h) == (300, 120)

    def test_partial_override_leaves_other_axes_alone(self):
        base = _layout(self.SRC)
        r = _layout(self.SRC, overrides={"nodes": {"a": {"x": 500}}})
        assert r.nodes["a"][0] == 500
        assert r.nodes["a"][1] == base.nodes["a"][1]

    def test_edge_waypoint_override(self):
        r = _layout(self.SRC, overrides={"edges": {"a->b": {"points": [[10, 20], [30, 40]]}}})
        assert r.edges["a->b"].points == [(10.0, 20.0), (30.0, 40.0)]

    def test_edge_label_override(self):
        r = _layout(self.SRC, overrides={"edges": {"a->b": {"label": [1, 2, 3, 4]}}})
        assert r.edges["a->b"].label == (1.0, 2.0, 3.0, 4.0)

    def test_unknown_ids_are_ignored(self):
        r = _layout(self.SRC, overrides={"nodes": {"nope": {"x": 1}},
                                         "edges": {"x->y": {"points": [[0, 0]]}}})
        assert "nope" not in r.nodes

    def test_no_overrides_is_a_no_op(self):
        assert _layout(self.SRC, overrides={}).nodes == _layout(self.SRC).nodes


class TestLoadOverrides:
    def test_reads_sidecar_next_to_the_puml(self, tmp_path):
        (tmp_path / "d.overrides.json").write_text('{"nodes": {"a": {"x": 7}}}')
        got = elk_layout.load_overrides(tmp_path / "d.puml")
        assert got["nodes"]["a"]["x"] == 7

    def test_missing_sidecar_gives_empty(self, tmp_path):
        assert elk_layout.load_overrides(tmp_path / "nothing.puml") == {}

    def test_malformed_sidecar_raises_with_the_path(self, tmp_path):
        (tmp_path / "d.overrides.json").write_text("{not json")
        with pytest.raises(ValueError, match="overrides"):
            elk_layout.load_overrides(tmp_path / "d.puml")


class TestBoundaryMinimumWidth:
    """A boundary must be at least as wide as its own title bar.

    Trap worth a regression test: ELK transposes NODE_SIZE_MINIMUM for vertical
    layout directions, so a naive (w, h) sets the *height*, silently doing
    nothing about a title that wraps down over the nodes inside.
    """

    SRC = '''@startuml
System_Boundary(z, "A deliberately long boundary title that would otherwise wrap") {
    Container(a, "A", ".NET", "d")
    Container(b, "B", ".NET", "d")
}
Rel(a, b, "x")
@enduml'''

    def test_boundary_is_wide_enough_for_its_title(self):
        r = _layout(self.SRC)
        _, _, w, _ = r.nodes["z"]
        title = "A deliberately long boundary title that would otherwise wrap"
        assert w >= len(title) * 7.0, f"boundary {w}px too narrow for its title"

    def test_min_width_is_not_applied_to_height(self):
        """The transposition bug showed up as an absurdly tall boundary."""
        r = _layout(self.SRC)
        _, _, w, h = r.nodes["z"]
        assert h < w, f"boundary {w}x{h} — minimum size landed on the wrong axis"
