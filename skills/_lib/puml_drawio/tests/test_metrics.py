"""Tests for the draw.io geometry quality metrics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from puml_drawio.metrics import (
    Box,
    Segment,
    Metrics,
    _seg_intersects_box,
    _segments_cross,
    _overlap_area,
    measure,
)


class TestSegmentBoxIntersection:
    BOX = Box(id="n", x=100, y=100, w=100, h=50)   # 100..200 x 100..150

    def test_horizontal_segment_through_box(self):
        assert _seg_intersects_box(Segment(50, 125, 250, 125), self.BOX)

    def test_vertical_segment_through_box(self):
        assert _seg_intersects_box(Segment(150, 50, 150, 200), self.BOX)

    def test_segment_clear_above(self):
        assert not _seg_intersects_box(Segment(50, 20, 250, 20), self.BOX)

    def test_segment_clear_to_the_left(self):
        assert not _seg_intersects_box(Segment(20, 50, 20, 200), self.BOX)

    def test_segment_touching_edge_does_not_count(self):
        """An edge that lands on the boundary is attaching, not crossing."""
        assert not _seg_intersects_box(Segment(50, 100, 250, 100), self.BOX)

    def test_segment_ending_inside_counts(self):
        assert _seg_intersects_box(Segment(50, 125, 150, 125), self.BOX)

    def test_diagonal_through_corner(self):
        assert _seg_intersects_box(Segment(90, 90, 210, 160), self.BOX)


class TestSegmentCrossing:
    def test_perpendicular_cross(self):
        assert _segments_cross(Segment(0, 50, 100, 50), Segment(50, 0, 50, 100))

    def test_parallel_no_cross(self):
        assert not _segments_cross(Segment(0, 50, 100, 50), Segment(0, 80, 100, 80))

    def test_shared_endpoint_is_not_a_crossing(self):
        """Edges meeting at a node port must not be counted as crossings."""
        assert not _segments_cross(Segment(0, 0, 50, 50), Segment(50, 50, 100, 0))

    def test_disjoint(self):
        assert not _segments_cross(Segment(0, 0, 10, 10), Segment(90, 90, 100, 100))


class TestOverlapArea:
    def test_full_overlap(self):
        a = Box(id="a", x=0, y=0, w=10, h=10)
        assert _overlap_area(a, a) == 100

    def test_partial(self):
        a = Box(id="a", x=0, y=0, w=10, h=10)
        b = Box(id="b", x=5, y=5, w=10, h=10)
        assert _overlap_area(a, b) == 25

    def test_disjoint(self):
        a = Box(id="a", x=0, y=0, w=10, h=10)
        b = Box(id="b", x=50, y=50, w=10, h=10)
        assert _overlap_area(a, b) == 0


class TestMeasureDrawio:
    """measure() reads a .drawio and scores it."""

    def _xml(self, cells: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<mxfile><diagram name="d"><mxGraphModel><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>'
            f'{cells}'
            '</root></mxGraphModel></diagram></mxfile>'
        )

    def _node(self, i, x, y, w=100, h=50, parent="1"):
        return (f'<mxCell id="c_{i}" value="{i}" style="rounded=1;" vertex="1" parent="{parent}">'
                f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

    def test_counts_nodes(self):
        m = measure(self._xml(self._node("a", 0, 0) + self._node("b", 0, 200)))
        assert m.node_count == 2

    def test_straight_edge_through_a_node_is_a_crossing(self):
        """a at y0..50, b at y200..250, c sits between them; the edge cuts through c."""
        cells = (
            self._node("a", 0, 0) + self._node("b", 0, 200) + self._node("c", 0, 100)
            + '<mxCell id="e0" style="edgeStyle=orthogonalEdgeStyle;" edge="1" parent="1"'
              ' source="c_a" target="c_b"><mxGeometry relative="1" as="geometry"/></mxCell>'
        )
        m = measure(self._xml(cells))
        assert m.edge_node_crossings >= 1

    def test_waypoints_routing_around_avoids_the_crossing(self):
        cells = (
            self._node("a", 0, 0) + self._node("b", 0, 200) + self._node("c", 0, 100)
            + '<mxCell id="e0" style="edgeStyle=orthogonalEdgeStyle;" edge="1" parent="1"'
              ' source="c_a" target="c_b"><mxGeometry relative="1" as="geometry">'
              '<Array as="points"><mxPoint x="300" y="75"/><mxPoint x="300" y="175"/></Array>'
              '</mxGeometry></mxCell>'
        )
        m = measure(self._xml(cells))
        assert m.edge_node_crossings == 0

    def test_child_coordinates_are_resolved_to_absolute(self):
        """A child of a boundary is positioned relative to it; metrics must use absolute coords."""
        cells = (
            self._node("bound", 500, 500, 300, 200)
            + self._node("kid", 10, 40, 100, 50, parent="c_bound")
        )
        m = measure(self._xml(cells))
        kid = [b for b in m.boxes if b.id == "c_kid"][0]
        assert (kid.x, kid.y) == (510, 540)

    def test_score_is_zero_for_a_clean_diagram(self):
        cells = self._node("a", 0, 0) + self._node("b", 0, 200)
        m = measure(self._xml(cells))
        assert m.edge_node_crossings == 0
        assert m.edge_edge_crossings == 0
        assert m.label_overlap_area == 0

    def test_label_overlapping_a_node_is_measured(self):
        cells = (
            self._node("a", 0, 0)
            + '<mxCell id="e0" value="lbl" style="edgeStyle=orthogonalEdgeStyle;" edge="1"'
              ' parent="1"><mxGeometry relative="1" as="geometry">'
              '<Array as="points"><mxPoint x="10" y="10"/><mxPoint x="90" y="10"/></Array>'
              '</mxGeometry></mxCell>'
        )
        m = measure(self._xml(cells))
        assert m.label_overlap_area > 0

    def test_is_comparable_and_reports_a_summary(self):
        m = measure(self._xml(self._node("a", 0, 0) + self._node("b", 300, 0)))
        assert isinstance(m.summary(), str)
        assert "crossings" in m.summary()


class TestEdgeAttachPoints:
    """When exit/entry ports are set, the metric must trace the real path.

    Otherwise a straight perimeter-to-perimeter route gets approximated as
    centre-to-centre, which can clip a third node that the true path misses,
    producing phantom crossings.
    """

    def _xml(self, edge_style):
        def node(i, x, y):
            return (f'<mxCell id="c_{i}" value="{i}" style="rounded=1;" vertex="1" parent="1">'
                    f'<mxGeometry x="{x}" y="{y}" width="100" height="50" as="geometry"/></mxCell>')
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<mxfile><diagram name="d"><mxGraphModel><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>'
            + node("a", 0, 0) + node("b", 0, 200) + node("c", 40, 100)
            + f'<mxCell id="e0" style="{edge_style}" edge="1" parent="1" source="c_a"'
              ' target="c_b"><mxGeometry relative="1" as="geometry"/></mxCell>'
            '</root></mxGraphModel></diagram></mxfile>'
        )

    def test_centre_to_centre_clips_the_middle_node(self):
        m = measure(self._xml("edgeStyle=orthogonalEdgeStyle;"))
        assert m.edge_node_crossings >= 1

    def test_ports_on_the_far_left_avoid_it(self):
        """Exit/entry at x=0 runs down the left edge, clear of c at x=40."""
        style = "edgeStyle=orthogonalEdgeStyle;exitX=0;exitY=1;entryX=0;entryY=0;"
        m = measure(self._xml(style))
        assert m.edge_node_crossings == 0
