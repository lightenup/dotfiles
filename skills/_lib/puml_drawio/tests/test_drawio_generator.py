"""Tests for the draw.io XML generator."""
from __future__ import annotations

import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from puml_drawio.puml_parser import (
    Boundary,
    Component,
    Diagram,
    LayoutHint,
    Relationship,
    TagStyle,
    parse,
)
from puml_drawio.drawio_generator import (
    FALLBACK_ICONS,
    ICON_MAP,
    generate,
    load_icon_map,
    configure,
    _html_value,
    _comp_width,
    _comp_height,
    _comp_style,
    _boundary_style,
    _edge_style,
    _edge_label,
)


class TestHtmlValue:
    def test_name_only(self):
        comp = Component(id="c1", name="Service", comp_type="Container")
        val = _html_value(comp)
        assert "<b>Service</b>" in val

    def test_with_technology(self):
        comp = Component(id="c1", name="Service", comp_type="Container", technology="Go")
        val = _html_value(comp)
        assert "[Go]" in val

    def test_with_description(self):
        comp = Component(id="c1", name="Svc", comp_type="Container", description="Line one\nLine two")
        val = _html_value(comp)
        assert "Line one" in val

    def test_tag_colors(self):
        comp = Component(id="c1", name="Svc", comp_type="Container", technology="Go", tags=["SaaS"])
        styles = {"SaaS": TagStyle(name="SaaS", bg_color="#4A90D9")}
        val = _html_value(comp, styles)
        assert "#FFFFFF" in val  # white tech color for tagged component


class TestCompDimensions:
    def test_default_width(self):
        comp = Component(id="c1", name="Svc", comp_type="Container")
        w = _comp_width(comp)
        assert w >= 155

    def test_long_name_width(self):
        comp = Component(id="c1", name="A Very Long Service Name Indeed", comp_type="Container")
        w = _comp_width(comp)
        assert w > 155

    def test_max_width_cap(self):
        comp = Component(id="c1", name="X" * 100, comp_type="Container")
        w = _comp_width(comp)
        assert w <= 230

    def test_default_height(self):
        comp = Component(id="c1", name="Svc", comp_type="Container")
        h = _comp_height(comp)
        assert h >= 52

    def test_height_with_description(self):
        comp = Component(id="c1", name="Svc", comp_type="Container", description="Line1\nLine2\nLine3")
        h = _comp_height(comp)
        assert h > 52


class TestStyles:
    def test_comp_style_default(self):
        s = _comp_style(has_icon=False)
        assert "fillColor=#FFFFFF" in s
        assert "strokeColor=#CCCCCC" in s

    def test_comp_style_colored(self):
        s = _comp_style(has_icon=False, bg_color="#4A90D9", font_color="#FFFFFF")
        assert "fillColor=#4A90D9" in s
        assert "strokeColor=#4A90D9" in s

    def test_comp_style_icon(self):
        s = _comp_style(has_icon=True)
        assert "verticalAlign=bottom" in s

    def test_boundary_style_depth0(self):
        s = _boundary_style(depth=0)
        assert "fillColor=#D0E8F2" in s
        assert "strokeColor=#0070C0" in s
        assert "strokeWidth=1.5" in s

    def test_boundary_style_depth1(self):
        s = _boundary_style(depth=1)
        assert "fillColor=#E8F4F8" in s

    def test_edge_style_default(self):
        s = _edge_style()
        assert "strokeColor=#000000" in s
        assert "strokeWidth=1.5" in s

    def test_edge_style_secondary(self):
        s = _edge_style(is_secondary=True)
        assert "strokeColor=#666666" in s

    def test_edge_style_bidi(self):
        s = _edge_style(is_bidirectional=True)
        assert "startArrow=classic" in s

    def test_edge_style_ports(self):
        s = _edge_style(exit_x=0.5, exit_y=1.0, entry_x=0.5, entry_y=0.0)
        assert "exitX=0.5" in s
        assert "entryY=0.0" in s


class TestEdgeLabel:
    def test_simple_label(self):
        r = Relationship(source_id="a", target_id="b", label="Uses")
        assert _edge_label(r) == "Uses"

    def test_multiline_label(self):
        r = Relationship(source_id="a", target_id="b", label="First line\\nSecond line")
        assert _edge_label(r) == "First line"

    def test_long_label_is_not_truncated(self):
        """ELK reserves space for the label's true size, so clipping is obsolete."""
        long = "an edge label comfortably longer than twenty-eight characters"
        rel = Relationship(source_id='a', target_id='b', label=long)
        assert _edge_label(rel) == long

    def test_technology_fallback(self):
        r = Relationship(source_id="a", target_id="b", technology="HTTPS")
        assert _edge_label(r) == "HTTPS"

    def test_no_label(self):
        r = Relationship(source_id="a", target_id="b")
        assert _edge_label(r) == ""


class TestLoadIconMap:
    def test_load_from_json(self):
        original = dict(ICON_MAP)
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({"testSprite": "img/test.svg"}, f)
                f.flush()
                load_icon_map(f.name)
            assert ICON_MAP["testSprite"] == "img/test.svg"
        finally:
            ICON_MAP.clear()
            ICON_MAP.update(original)
            Path(f.name).unlink()

    def test_nonexistent_file(self):
        load_icon_map("/nonexistent/path.json")  # should not raise


class TestConfigure:
    def test_configure_monitoring(self):
        configure(monitoring_ids={"grafana", "prometheus"})

    def test_configure_icons(self):
        original = dict(ICON_MAP)
        try:
            configure(icon_map={"custom": "img/custom.svg"})
            assert ICON_MAP["custom"] == "img/custom.svg"
        finally:
            ICON_MAP.clear()
            ICON_MAP.update(original)


class TestGenerateMinimal:
    def test_empty_diagram(self):
        d = Diagram()
        xml = generate(d)
        assert '<?xml version="1.0"' in xml
        assert '<mxfile' in xml
        assert 'host="puml-drawio-converter"' in xml

    def test_single_component(self):
        d = Diagram(components=[
            Component(id="c1", name="Service", comp_type="Container", technology="Go"),
        ])
        xml = generate(d)
        root = ET.fromstring(xml)
        cells = root.findall('.//mxCell[@vertex="1"]')
        comp_cells = [c for c in cells if c.get('id', '').startswith('c_')]
        assert len(comp_cells) == 1
        assert 'Service' in comp_cells[0].get('value', '')

    def test_boundary_with_component(self):
        d = Diagram(
            boundaries=[Boundary(id="b1", label="Platform")],
            components=[
                Component(id="c1", name="Svc", comp_type="Container", parent_boundary="b1"),
            ],
        )
        xml = generate(d)
        root = ET.fromstring(xml)
        boundary_cells = [c for c in root.findall('.//mxCell') if c.get('id', '') == 'b_b1']
        assert len(boundary_cells) == 1
        assert 'Platform' in boundary_cells[0].get('value', '')

    def test_relationship_edge(self):
        d = Diagram(
            components=[
                Component(id="a", name="A", comp_type="Container"),
                Component(id="b", name="B", comp_type="Container"),
            ],
            relationships=[
                Relationship(source_id="a", target_id="b", label="Calls"),
            ],
        )
        xml = generate(d)
        root = ET.fromstring(xml)
        edges = root.findall('.//mxCell[@edge="1"]')
        assert len(edges) == 1
        assert edges[0].get('source') == 'c_a'
        assert edges[0].get('target') == 'c_b'

    def test_title(self):
        d = Diagram(title="My Architecture")
        xml = generate(d)
        assert 'My Architecture' in xml

    def test_tag_legend(self):
        d = Diagram(
            tag_styles={"SaaS": TagStyle(name="SaaS", bg_color="#4A90D9", legend_text="SaaS Service")},
            components=[
                Component(id="c1", name="Svc", comp_type="Container", tags=["SaaS"]),
            ],
        )
        xml = generate(d)
        assert 'SaaS Service' in xml


class TestGenerateFromPuml:
    SAMPLE = '''@startuml
title Test Diagram

System_Boundary(platform, "Platform") {
    Container(gw, "Gateway", "Kong", "Routes requests")
    Container(svc, "Backend", "Go", "Business logic")
}

Rel(gw, svc, "Routes to")
Lay_R(gw, svc)

@enduml'''

    def test_roundtrip(self):
        d = parse(self.SAMPLE)
        xml = generate(d)
        root = ET.fromstring(xml)

        # Verify structure
        assert root.tag == 'mxfile'
        diagrams = root.findall('diagram')
        assert len(diagrams) == 1

        cells = root.findall('.//mxCell')
        assert len(cells) > 2  # at least root cells + content

        # Verify components exist
        comp_ids = {c.get('id') for c in cells if c.get('id', '').startswith('c_')}
        assert 'c_gw' in comp_ids
        assert 'c_svc' in comp_ids

        # Verify boundary exists
        bound_ids = {c.get('id') for c in cells if c.get('id', '').startswith('b_')}
        assert 'b_platform' in bound_ids

        # Verify edge exists
        edges = [c for c in cells if c.get('edge') == '1']
        assert len(edges) == 1

    def test_layout_positions(self):
        d = parse(self.SAMPLE)
        xml = generate(d)
        root = ET.fromstring(xml)

        gw_cell = root.find('.//mxCell[@id="c_gw"]')
        svc_cell = root.find('.//mxCell[@id="c_svc"]')
        assert gw_cell is not None
        assert svc_cell is not None

        gw_geo = gw_cell.find('mxGeometry')
        svc_geo = svc_cell.find('mxGeometry')
        gw_y = float(gw_geo.get('y'))
        svc_y = float(svc_geo.get('y'))
        # Rel(gw, svc) exists, so a layered layout MUST rank svc below gw.
        # Lay_R cannot also apply here: an edge defines the rank order, and a
        # node cannot be both below and beside its predecessor. Lay_R/Lay_L are
        # honoured between same-layer siblings instead - see
        # TestLayHintsOrderSameLayerSiblings.
        assert svc_y > gw_y


class TestGenerateNestedBoundaries:
    def test_nested(self):
        d = Diagram(
            boundaries=[
                Boundary(id="outer", label="Outer"),
                Boundary(id="inner", label="Inner", parent_boundary="outer"),
            ],
            components=[
                Component(id="c1", name="Svc", comp_type="Container", parent_boundary="inner"),
            ],
        )
        xml = generate(d)
        root = ET.fromstring(xml)

        inner_cell = root.find('.//mxCell[@id="b_inner"]')
        assert inner_cell is not None
        assert inner_cell.get('parent') == 'b_outer'


class TestGenerateBidirectional:
    def test_bidi_merged(self):
        d = Diagram(
            components=[
                Component(id="a", name="A", comp_type="Container"),
                Component(id="b", name="B", comp_type="Container"),
            ],
            relationships=[
                Relationship(source_id="a", target_id="b", label="Send"),
                Relationship(source_id="b", target_id="a", label="Reply"),
            ],
        )
        xml = generate(d)
        root = ET.fromstring(xml)
        edges = root.findall('.//mxCell[@edge="1"]')
        # Bidirectional pair should be merged into one edge
        assert len(edges) == 1
        style = edges[0].get('style', '')
        assert 'startArrow=classic' in style


class TestFallbackIconsForC4Levels:
    """Component()/*Db/*Queue/_Ext variants must still get a fallback icon."""

    def test_component_gets_fallback(self):
        from puml_drawio.drawio_generator import _icon_path
        from puml_drawio.puml_parser import Component
        assert _icon_path(Component(id='zz1', name='X', comp_type='Component'))

    def test_variants_get_fallback(self):
        from puml_drawio.drawio_generator import _icon_path
        from puml_drawio.puml_parser import Component
        for t in ('ComponentDb', 'ComponentQueue', 'Component_Ext',
                  'ContainerDb', 'ContainerQueue', 'Container_Ext',
                  'SystemDb', 'SystemQueue', 'Person_Ext'):
            assert _icon_path(Component(id='zz_' + t, name='X', comp_type=t)), t

    def test_person_ext_uses_person_icon(self):
        from puml_drawio.drawio_generator import _icon_path, FALLBACK_ICONS
        from puml_drawio.puml_parser import Component
        assert _icon_path(Component(id='zz2', name='X', comp_type='Person_Ext')) == \
            FALLBACK_ICONS['Person']


class TestTagBorderOverlay:
    """fill = ownership, border = build state; $tags="new+ey" must merge per property."""

    SRC = '''@startuml
AddElementTag("ey",  $bgColor="#2E6DB4", $fontColor="#FFFFFF")
AddElementTag("new", $borderColor="#69DB7C", $borderThickness="4")
AddElementTag("gap", $borderColor="#E8590C", $borderThickness="3", $borderStyle="dashed")
Component(a, "Built", ".NET", "d", $tags="ey")
Component(b, "New", ".NET", "d", $tags="new+ey")
Component(c, "Gap", ".NET", "d", $tags="gap+ey")
@enduml'''

    def _style_of(self, cid):
        from puml_drawio import parse, generate
        import re
        xml = generate(parse(self.SRC))
        m = re.search(r'id="c_%s"[^>]*style="([^"]*)"' % cid, xml)
        assert m, f'cell c_{cid} not found'
        return m.group(1)

    def test_plain_tag_keeps_fill_and_matching_stroke(self):
        s = self._style_of('a')
        assert 'fillColor=#2E6DB4' in s
        assert 'strokeColor=#2E6DB4' in s

    def test_overlay_keeps_ownership_fill(self):
        s = self._style_of('b')
        assert 'fillColor=#2E6DB4' in s, 'border-only tag must not blank the fill'

    def test_overlay_border_colour_wins(self):
        s = self._style_of('b')
        assert 'strokeColor=#69DB7C' in s
        assert 'strokeWidth=4' in s

    def test_dashed_border_style(self):
        s = self._style_of('c')
        assert 'strokeColor=#E8590C' in s
        assert 'strokeWidth=3' in s
        assert 'dashed=1' in s

    def test_no_dash_when_not_requested(self):
        assert 'dashed=1' not in self._style_of('b')


class TestC4DefaultFillAppliedByGenerator:
    """A tag that declares no $bgColor still renders with the C4 default fill."""

    def _style_of(self, src, cid):
        from puml_drawio import parse, generate
        import re
        m = re.search(r'id="c_%s"[^>]*style="([^"]*)"' % cid, generate(parse(src)))
        assert m
        return m.group(1)

    def test_bare_tag_gets_c4_default(self):
        src = ('@startuml\nAddElementTag("basic")\n'
               'Component(a, "A", ".NET", "d", $tags="basic")\n@enduml')
        assert 'fillColor=#438DD5' in self._style_of(src, 'a')

    def test_untagged_component_stays_white(self):
        src = '@startuml\nComponent(a, "A", ".NET", "d")\n@enduml'
        assert 'fillColor=#FFFFFF' in self._style_of(src, 'a')

    def test_border_only_tag_gets_c4_default_fill(self):
        src = ('@startuml\nAddElementTag("gap", $borderColor="#E8590C")\n'
               'Component(a, "A", ".NET", "d", $tags="gap")\n@enduml')
        s = self._style_of(src, 'a')
        assert 'fillColor=#438DD5' in s
        assert 'strokeColor=#E8590C' in s


class TestLegendSwatchBorders:
    """Legend swatches must reproduce the same fill+border encoding as the nodes."""

    SRC = '''@startuml
AddElementTag("ey",  $bgColor="#2E6DB4", $legendText="EY-built")
AddElementTag("gap", $borderColor="#E8590C", $borderThickness="3", $borderStyle="dashed", $legendText="Interface undefined")
Component(a, "A", ".NET", "d", $tags="ey")
Component(b, "B", ".NET", "d", $tags="gap+ey")
@enduml'''

    def _swatches(self):
        from puml_drawio import parse, generate
        import re
        xml = generate(parse(self.SRC))
        return dict(re.findall(r'id="legend_sw_(\d+)"[^>]*style="([^"]*)"', xml))

    def test_fill_tag_swatch(self):
        s = self._swatches()['0']
        assert 'fillColor=#2E6DB4' in s and 'strokeColor=#2E6DB4' in s

    def test_border_only_tag_swatch_shows_border(self):
        s = self._swatches()['1']
        assert 'strokeColor=#E8590C' in s
        assert 'strokeWidth=3' in s
        assert 'dashed=1' in s
        assert 'fillColor=#2E6DB4' not in s


class TestHeightAccountsForWrapping:
    """Node height must budget for text WRAPPING, not just explicit newlines.

    Regression: descriptions are single-line strings, so the old estimate always
    counted 1 line. Long descriptions then grew upwards (verticalAlign=bottom)
    and rendered on top of the icon.
    """

    def _comp(self, **kw):
        from puml_drawio.puml_parser import Component
        base = dict(id='x', name='X', comp_type='Container', technology='.NET 8', description='')
        base.update(kw)
        return Component(**base)

    def test_long_description_is_taller_than_short(self):
        from puml_drawio.drawio_generator import _comp_height
        short = self._comp(description='Short.')
        long = self._comp(description=(
            'Scores applicants and ranks a shortlist; credit-checks only the '
            'finalists; stores the score, never the credit data'))
        assert _comp_height(long) > _comp_height(short) + 15

    def test_icon_node_leaves_room_below_the_icon(self):
        from puml_drawio.drawio_generator import _comp_height, _comp_width, ICON_SIZE
        c = self._comp(
            name='Rating & selection service',
            description=('Scores applicants and ranks a shortlist; credit-checks only the '
                         'finalists; stores the score, never the credit data'),
            sprite='AzureFunctions')
        h, w = _comp_height(c), _comp_width(c)
        # icon occupies y=4 .. 4+ICON_SIZE; the text block must fit under it
        chars_per_line = max(int((w - 16) / (8 * 0.55)), 8)
        est_desc_lines = -(-len(c.description) // chars_per_line)
        needed = 4 + ICON_SIZE + 15 + 12 + est_desc_lines * 10
        assert h >= needed, f'height {h} < needed {needed}'

    def test_wrapping_name_adds_height(self):
        from puml_drawio.drawio_generator import _comp_height
        one = self._comp(name='API Gateway')
        two = self._comp(name='A very long container name that must wrap onto lines')
        assert _comp_height(two) > _comp_height(one)

    def test_description_capped_at_max_desc_lines(self):
        from puml_drawio.drawio_generator import _comp_height
        capped = self._comp(description='\n'.join(['line'] * 50))
        assert _comp_height(capped) < 220


class TestLegendDoesNotOverlap:
    """Legend columns must be wide enough for the longest legend text."""

    SRC = '''@startuml
AddElementTag("a", $bgColor="#111111", $legendText="Short")
AddElementTag("b", $bgColor="#222222", $legendText="Interface NOT yet defined / scope open - see backlog")
AddElementTag("c", $bgColor="#333333", $legendText="Existing legacy - being replaced or strangled")
AddElementTag("d", $bgColor="#444444", $legendText="In Phase 1 build - designed, being built")
Component(p, "P", ".NET", "d", $tags="a")
Component(q, "Q", ".NET", "d", $tags="b")
Component(r, "R", ".NET", "d", $tags="c")
Component(s, "S", ".NET", "d", $tags="d")
@enduml'''

    def _entries(self):
        from puml_drawio import parse, generate
        import re
        xml = generate(self.SRC and parse(self.SRC))
        out = {}
        for kind in ('sw', 'lb'):
            for m in re.finditer(
                r'id="legend_%s_(\d+)".*?<mxGeometry x="([\d.]+)" y="([\d.]+)" width="([\d.]+)"' % kind,
                xml, re.S):
                out[(kind, int(m.group(1)))] = (float(m.group(2)), float(m.group(3)), float(m.group(4)))
        return out

    def test_label_box_fits_its_text(self):
        """Legend labels don't wrap, so the box must be wide enough for the text."""
        from puml_drawio import parse
        e = self._entries()
        assert e, 'no legend rendered'
        texts = [ts.legend_text for ts in parse(self.SRC).tag_styles.values()]
        longest = max(len(t) for t in texts)
        needed = longest * 9 * 0.55
        widths = [w for (kind, _), (_, _, w) in e.items() if kind == 'lb']
        assert min(widths) >= needed, (
            f'legend label box {min(widths):.0f}px too narrow for {longest} chars '
            f'(needs ~{needed:.0f}px) — text will overflow into the next column')

    def test_labels_do_not_overlap_next_swatch(self):
        e = self._entries()
        assert e, 'no legend rendered'
        for (kind, i), (x, y, w) in e.items():
            if kind != 'lb':
                continue
            nxt = e.get(('sw', i + 1))
            if not nxt or nxt[1] != y:   # different row is fine
                continue
            assert x + w <= nxt[0] + 0.5, f'legend label {i} runs into swatch {i+1}'


class TestElkWaypointEmission:
    """generate() must emit ELK's routes as explicit draw.io waypoints.

    Without <Array as="points"> draw.io re-routes with its own local router,
    which does not avoid obstacles — that was the root cause of edges crossing
    boxes.
    """
    import pytest as _pytest

    SRC = '''@startuml
Container(top, "Top", ".NET", "d")
Container(mid, "Mid", ".NET", "d")
Container(bot, "Bot", ".NET", "d")
Rel(top, mid, "one")
Rel(mid, bot, "two")
Rel(top, bot, "skips a rank")
@enduml'''

    def _xml(self):
        from puml_drawio import parse, generate
        return generate(parse(self.SRC))

    def test_rank_skipping_edge_has_waypoints(self):
        import re
        xml = self._xml()
        edges = re.findall(r'<mxCell id="e_\d+".*?</mxCell>', xml, re.S)
        assert any('<Array as="points">' in e for e in edges), \
            "no edge carries explicit waypoints"

    def test_no_edge_crosses_a_node(self):
        from puml_drawio.metrics import measure
        m = measure(self._xml())
        assert m.edge_node_crossings == 0, m.crossing_detail

    def test_nodes_do_not_overlap(self):
        from puml_drawio.metrics import measure
        assert measure(self._xml()).node_overlap_area == 0

    def test_edge_labels_are_not_truncated(self):
        """Space is reserved for labels now, so the 28-char clamp is obsolete."""
        from puml_drawio import parse, generate
        src = ('@startuml\nContainer(a, "A", ".NET", "d")\nContainer(b, "B", ".NET", "d")\n'
               'Rel(a, b, "an edge label comfortably longer than twenty-eight characters")\n@enduml')
        xml = generate(parse(src))
        assert "twenty-eight characters" in xml
        assert "..." not in xml

    def test_boundary_contains_its_children(self):
        from puml_drawio import parse, generate
        from puml_drawio.metrics import measure
        src = ('@startuml\nSystem_Boundary(z, "Zone") {\n'
               'Container(a, "A", ".NET", "d")\nContainer(b, "B", ".NET", "d")\n}\n'
               'Rel(a, b, "x")\n@enduml')
        m = measure(generate(parse(src)))
        zone = [x for x in m.boxes if x.id == "b_z"][0]
        for cid in ("c_a", "c_b"):
            kid = [x for x in m.boxes if x.id == cid][0]
            assert zone.x <= kid.x and kid.x + kid.w <= zone.x2 + 0.5
            assert zone.y <= kid.y and kid.y + kid.h <= zone.y2 + 0.5


class TestLayHintsOrderSameLayerSiblings:
    """Lay_R / Lay_L survive the move to ELK as an in-layer ordering constraint."""

    SRC = """@startuml
Container(r, "R", ".NET", "d")
Container(b, "B", ".NET", "d")
Container(a, "A", ".NET", "d")
Rel(r, a, "x")
Rel(r, b, "y")
Lay_R(a, b)
@enduml"""

    def _x(self, xml, cid):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
        return float(root.find(f'.//mxCell[@id="c_{cid}"]/mxGeometry').get("x"))

    def test_lay_r_puts_a_left_of_b_despite_source_order(self):
        from puml_drawio import parse, generate
        xml = generate(parse(self.SRC))
        assert self._x(xml, "a") < self._x(xml, "b")

    def test_lay_l_reverses_it(self):
        from puml_drawio import parse, generate
        xml = generate(parse(self.SRC.replace("Lay_R(a, b)", "Lay_L(a, b)")))
        assert self._x(xml, "b") < self._x(xml, "a")

    def test_contradictory_hints_do_not_crash(self):
        from puml_drawio import parse, generate
        src = self.SRC.replace("Lay_R(a, b)", "Lay_R(a, b)\nLay_R(b, a)")
        assert generate(parse(src))
