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

    def test_long_label_truncated(self):
        r = Relationship(source_id="a", target_id="b", label="A" * 40)
        label = _edge_label(r)
        assert len(label) <= 29  # 26 + "..."

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
        gw_x = float(gw_geo.get('x'))
        svc_x = float(svc_geo.get('x'))
        # Lay_R(gw, svc) means svc should be to the right of gw
        assert svc_x > gw_x


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
