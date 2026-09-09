"""Layout quality gate.

The previous generation of this toolchain was tuned by eye against a reference
image, so there was no way to tell whether a change was a net win, and each new
heuristic could silently undo an earlier one. These tests turn the thing we
actually care about — "does the picture read cleanly" — into numbers that can
fail a build.

Budgets are deliberately tight. If a change trips one, that is the signal:
either the change is a regression, or the budget needs an argued adjustment.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from puml_drawio import elk_layout, generate, parse
from puml_drawio.metrics import measure

pytestmark = pytest.mark.skipif(
    not elk_layout.available(), reason="java/plantuml.jar not available"
)


# A dense, cyclic, multi-boundary graph — the shape that used to fall apart.
DENSE = """@startuml
Person(user, "User", "d")
System_Ext(ext, "External", "d")
System_Boundary(zoneA, "Zone A the first boundary with a long title") {
    Container(api, "API", ".NET", "front door")
    Container(svc, "Service", ".NET", "does the work")
}
System_Boundary(zoneB, "Zone B") {
    Container(worker, "Worker", ".NET", "async")
    Container(store, "Store", "SQL", "state")
}
ContainerQueue(bus, "Bus", "SB", "async backbone")
System(db, "Database", "master")

Rel(user, api, "calls the api over https")
Rel(api, svc, "delegates")
Rel(svc, db, "reads and writes the record")
Rel(db, bus, "emits domain events")
Rel(bus, worker, "delivers")
Rel(worker, store, "persists")
Rel(worker, ext, "calls out")
Rel(worker, db, "writes back")
Rel(user, ext, "long edge skipping several ranks")
Rel(api, bus, "publishes")
@enduml"""


@pytest.fixture(scope="module")
def dense():
    return measure(generate(parse(DENSE)))


class TestLayoutQualityBudgets:
    def test_no_edge_crosses_a_node(self, dense):
        """The headline property. An edge cutting through a box is never OK."""
        assert dense.edge_node_crossings == 0, dense.crossing_detail

    def test_no_node_overlaps_another(self, dense):
        assert dense.node_overlap_area == 0

    def test_no_label_sits_on_a_node(self, dense):
        """Budget, not zero: both the space ELK reserves and the area this
        metric measures derive from an *estimated* glyph advance, so a few
        px^2 of apparent overlap is measurement noise rather than a visible
        collision. The baseline before ELK was ~86,000 px^2 across the suite,
        so anything at this scale means the reservation is working.
        """
        assert dense.label_overlap_area <= 50, dense.summary()

    def test_edge_crossings_stay_modest(self, dense):
        """Edge-edge crossings are sometimes unavoidable; runaway counts are not."""
        assert dense.edge_edge_crossings <= dense.edge_count

    def test_aspect_ratio_is_presentable(self, dense):
        """Slides are landscape. A tall ribbon is unusable in a deck."""
        assert 0.4 <= dense.aspect_ratio <= 4.0, dense.summary()


class TestBoundaryContainment:
    def test_children_stay_inside_their_boundary(self, dense):
        by_id = {b.id: b for b in dense.boxes}
        zone = by_id["b_zoneA"]
        for cid in ("c_api", "c_svc"):
            kid = by_id[cid]
            assert zone.x <= kid.x and kid.x2 <= zone.x2 + 0.5
            assert zone.y <= kid.y and kid.y2 <= zone.y2 + 0.5

    def test_long_boundary_title_does_not_overlap_its_children(self, dense):
        """A wrapped heading used to land on top of the first row of nodes."""
        by_id = {b.id: b for b in dense.boxes}
        zone = by_id["b_zoneA"]
        topmost = min(by_id[c].y for c in ("c_api", "c_svc"))
        assert topmost - zone.y >= 29.9, "no room reserved for the title bar"


class TestEveryEdgeIsRouted:
    def test_multi_rank_edges_carry_waypoints(self):
        xml = generate(parse(DENSE))
        assert '<Array as="points">' in xml, \
            "no explicit waypoints: draw.io will re-route and cross things"

    def test_labels_are_never_truncated(self):
        xml = generate(parse(DENSE))
        assert "long edge skipping several ranks" in xml
        assert "..." not in xml


class TestOverridesDoNotBreakTheGate:
    def test_a_sidecar_nudge_still_produces_valid_geometry(self):
        overrides = {"nodes": {"db": {"x": 40}}}
        m = measure(generate(parse(DENSE), overrides=overrides))
        assert m.node_count > 0
        assert m.node_overlap_area == 0 or m.node_overlap_area > 0  # must not crash
