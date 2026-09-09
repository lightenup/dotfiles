"""Tests for the PlantUML C4 parser."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from puml_drawio.puml_parser import (
    Boundary,
    Component,
    Diagram,
    LayoutHint,
    Relationship,
    TagStyle,
    _split_args,
    _unquote,
    _named_args,
    _clean_desc,
    parse,
)


class TestSplitArgs:
    def test_simple(self):
        assert _split_args('a, b, c') == ['a', 'b', 'c']

    def test_quoted(self):
        assert _split_args('"hello, world", b') == ['"hello, world"', 'b']

    def test_nested_parens(self):
        assert _split_args('a, f(x, y), c') == ['a', 'f(x, y)', 'c']

    def test_empty(self):
        assert _split_args('') == []

    def test_single(self):
        assert _split_args('abc') == ['abc']


class TestUnquote:
    def test_quoted(self):
        assert _unquote('"hello"') == 'hello'

    def test_unquoted(self):
        assert _unquote('hello') == 'hello'

    def test_whitespace(self):
        assert _unquote('  "test"  ') == 'test'

    def test_empty_quoted(self):
        assert _unquote('""') == ''


class TestNamedArgs:
    def test_mixed(self):
        pos, named = _named_args(['a', '$key="val"', 'b'])
        assert pos == ['a', 'b']
        assert named == {'key': 'val'}

    def test_no_named(self):
        pos, named = _named_args(['a', 'b'])
        assert pos == ['a', 'b']
        assert named == {}

    def test_named_no_quotes(self):
        pos, named = _named_args(['$bgColor=#FF0000'])
        assert pos == []
        assert named == {'bgColor': '#FF0000'}


class TestCleanDesc:
    def test_strips_sprite(self):
        desc, sprite = _clean_desc('<$myIcon> Some description')
        assert sprite == 'myIcon'
        assert 'myIcon' not in desc
        assert 'Some description' in desc

    def test_strips_html(self):
        desc, _ = _clean_desc('<b>Bold</b> and <i>italic</i>')
        assert desc == 'Bold and italic'

    def test_strips_size(self):
        desc, _ = _clean_desc('<size:14>Big text</size>')
        assert desc == 'Big text'

    def test_no_markup(self):
        desc, sprite = _clean_desc('Plain text')
        assert desc == 'Plain text'
        assert sprite == ''


class TestParseMinimal:
    def test_empty(self):
        d = parse('')
        assert d.title == ''
        assert d.components == []
        assert d.boundaries == []
        assert d.relationships == []

    def test_title(self):
        d = parse('title My Diagram')
        assert d.title == 'My Diagram'

    def test_title_with_newline(self):
        d = parse('title Line One\\nLine Two')
        assert d.title == 'Line One // Line Two'

    def test_title_with_html(self):
        d = parse('title <b>Bold Title</b>')
        assert d.title == 'Bold Title'


class TestParseLayoutDirection:
    def test_top_down(self):
        d = parse('LAYOUT_TOP_DOWN()')
        assert d.layout_direction == 'TOP_DOWN'

    def test_left_right(self):
        d = parse('LAYOUT_LEFT_RIGHT()')
        assert d.layout_direction == 'LEFT_RIGHT'


class TestParseTags:
    def test_tag(self):
        d = parse('AddElementTag("SaaS", $bgColor="#4A90D9", $fontColor="#FFFFFF", $legendText="SaaS Service")')
        assert 'SaaS' in d.tag_styles
        ts = d.tag_styles['SaaS']
        assert ts.bg_color == '#4A90D9'
        assert ts.font_color == '#FFFFFF'
        assert ts.legend_text == 'SaaS Service'

    def test_tag_defaults(self):
        """The parser records only what the source declared; unset means ''.

        Applying the C4 default fill is the generator's job — see
        TestTagBorderOverlay. Keeping 'unset' distinguishable is what makes a
        border-only overlay tag (e.g. $tags="gap+ey") possible.
        """
        d = parse('AddElementTag("basic")')
        ts = d.tag_styles['basic']
        assert ts.bg_color == ''
        assert ts.font_color == ''


class TestParseComponents:
    def test_system_ext(self):
        d = parse('System_Ext(ext1, "External System", "Some description")')
        assert len(d.components) == 1
        c = d.components[0]
        assert c.id == 'ext1'
        assert c.name == 'External System'
        assert c.comp_type == 'System_Ext'
        assert c.description == 'Some description'

    def test_container(self):
        d = parse('Container(c1, "My Container", "Java", "Does things")')
        c = d.components[0]
        assert c.id == 'c1'
        assert c.name == 'My Container'
        assert c.technology == 'Java'
        assert c.description == 'Does things'

    def test_person(self):
        d = parse('Person(user, "End User", "Uses the system")')
        c = d.components[0]
        assert c.id == 'user'
        assert c.name == 'End User'
        assert c.comp_type == 'Person'
        assert c.technology == ''
        assert c.description == 'Uses the system'

    def test_system(self):
        d = parse('System(s1, "My System")')
        c = d.components[0]
        assert c.id == 's1'
        assert c.name == 'My System'
        assert c.comp_type == 'System'

    def test_tags(self):
        d = parse('Container(c1, "Svc", "Go", "desc", $tags="SaaS+Gateway")')
        c = d.components[0]
        assert c.tags == ['SaaS', 'Gateway']

    def test_sprite(self):
        d = parse('Container(c1, "Svc", "Go", "desc", $sprite="myIcon")')
        c = d.components[0]
        assert c.sprite == 'myIcon'


class TestParseBoundaries:
    def test_single_boundary(self):
        puml = '''System_Boundary(platform, "My Platform") {
    Container(c1, "Service A", "Go")
}'''
        d = parse(puml)
        assert len(d.boundaries) == 1
        assert d.boundaries[0].id == 'platform'
        assert d.boundaries[0].label == 'My Platform'
        assert d.boundaries[0].parent_boundary is None
        assert d.components[0].parent_boundary == 'platform'

    def test_nested_boundaries(self):
        puml = '''System_Boundary(outer, "Outer") {
    System_Boundary(inner, "Inner") {
        Container(c1, "Service", "Go")
    }
}'''
        d = parse(puml)
        assert len(d.boundaries) == 2
        inner = [b for b in d.boundaries if b.id == 'inner'][0]
        assert inner.parent_boundary == 'outer'
        assert d.components[0].parent_boundary == 'inner'


class TestParseRelationships:
    def test_rel(self):
        d = parse('Rel(a, b, "Uses", "HTTPS")')
        assert len(d.relationships) == 1
        r = d.relationships[0]
        assert r.source_id == 'a'
        assert r.target_id == 'b'
        assert r.label == 'Uses'
        assert r.technology == 'HTTPS'

    def test_rel_d(self):
        d = parse('Rel_D(a, b, "Sends data")')
        r = d.relationships[0]
        assert r.direction == 'D'
        assert r.label == 'Sends data'

    def test_rel_r(self):
        d = parse('Rel_R(a, b, "Calls")')
        r = d.relationships[0]
        assert r.direction == 'R'

    def test_freeform_arrow(self):
        d = parse('a --> b : some label')
        assert len(d.relationships) == 1
        r = d.relationships[0]
        assert r.source_id == 'a'
        assert r.target_id == 'b'
        assert r.label == 'some label'

    def test_bidirectional_arrow(self):
        d = parse('a <--> b : sync data')
        assert len(d.relationships) == 1
        r = d.relationships[0]
        assert r.source_id == 'a'
        assert r.target_id == 'b'
        assert r.label == 'sync data'


class TestParseLayoutHints:
    def test_lay_r(self):
        d = parse('Lay_R(a, b)')
        assert len(d.layout_hints) == 1
        h = d.layout_hints[0]
        assert h.hint_type == 'R'
        assert h.source_id == 'a'
        assert h.target_id == 'b'

    def test_lay_d(self):
        d = parse('Lay_D(x, y)')
        h = d.layout_hints[0]
        assert h.hint_type == 'D'


class TestParseSkips:
    def test_skips_comments(self):
        d = parse("' This is a comment\nSystem(s1, \"Sys\")")
        assert len(d.components) == 1

    def test_skips_includes(self):
        d = parse("!include foo.puml\nSystem(s1, \"Sys\")")
        assert len(d.components) == 1

    def test_skips_startuml(self):
        d = parse("@startuml\nSystem(s1, \"Sys\")\n@enduml")
        assert len(d.components) == 1

    def test_skips_skinparam(self):
        d = parse("skinparam linetype ortho\nSystem(s1, \"Sys\")")
        assert len(d.components) == 1

    def test_skips_show_legend(self):
        d = parse("SHOW_LEGEND()\nSystem(s1, \"Sys\")")
        assert len(d.components) == 1


class TestParseFullDiagram:
    SAMPLE = '''@startuml Sample Architecture
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml

LAYOUT_TOP_DOWN()

title Sample Architecture\\nLevel 2

AddElementTag("SaaS", $bgColor="#4A90D9", $fontColor="#FFFFFF", $legendText="SaaS")

Person(user, "End User")
System_Ext(ext, "External API", "Third-party service")

System_Boundary(platform, "Platform") {
    Container(gw, "API Gateway", "Kong", "Routes requests", $tags="SaaS")
    Container(svc, "Backend", "Go", "Business logic")

    System_Boundary(data, "Data Layer") {
        Container(db, "Database", "PostgreSQL", "Stores state")
    }
}

Rel(user, gw, "Calls", "HTTPS")
Rel(gw, svc, "Routes to")
Rel(svc, db, "Reads/writes")
Rel(svc, ext, "Fetches data", "REST")

Lay_R(gw, svc)
Lay_D(svc, db)

@enduml'''

    def test_full_parse(self):
        d = parse(self.SAMPLE)
        assert d.title == 'Sample Architecture // Level 2'
        assert d.layout_direction == 'TOP_DOWN'
        assert len(d.components) == 5
        assert len(d.boundaries) == 2
        assert len(d.relationships) == 4
        assert len(d.layout_hints) == 2
        assert 'SaaS' in d.tag_styles

        gw = [c for c in d.components if c.id == 'gw'][0]
        assert gw.tags == ['SaaS']
        assert gw.parent_boundary == 'platform'

        db = [c for c in d.components if c.id == 'db'][0]
        assert db.parent_boundary == 'data'

        data_boundary = [b for b in d.boundaries if b.id == 'data'][0]
        assert data_boundary.parent_boundary == 'platform'


class TestParseC4ComponentLevel:
    """C4 L3 macros: Component(), Container_Boundary(), and the Db/Queue variants.

    Regression: the parser previously only matched Person|System_Ext|System|Container
    and System_Boundary, so every Component()/Container_Boundary() in an L3 diagram was
    silently dropped, leaving empty boundaries and dangling relationships.
    """

    def test_component(self):
        d = parse('@startuml\nComponent(gate, "Gate check", ".NET 8", "Eligibility")\n@enduml')
        assert len(d.components) == 1
        c = d.components[0]
        assert c.id == 'gate'
        assert c.name == 'Gate check'
        assert c.technology == '.NET 8'
        assert c.description == 'Eligibility'
        assert c.comp_type == 'Component'

    def test_component_ext(self):
        d = parse('@startuml\nComponent_Ext(x, "Ext comp", "Java", "Desc")\n@enduml')
        assert d.components[0].comp_type == 'Component_Ext'
        assert d.components[0].technology == 'Java'

    def test_component_with_tags(self):
        d = parse('@startuml\nComponent(sb, "Bus", "Azure", "Topics", $tags="async")\n@enduml')
        assert d.components[0].tags == ['async']

    def test_container_boundary(self):
        src = '''@startuml
Container_Boundary(app, "func-willhem-public") {
    Component(a, "A", ".NET", "desc")
}
@enduml'''
        d = parse(src)
        assert [b.id for b in d.boundaries] == ['app']
        assert d.boundaries[0].label == 'func-willhem-public'
        assert d.components[0].parent_boundary == 'app'

    def test_container_boundary_nested_in_system_boundary(self):
        src = '''@startuml
System_Boundary(zone, "Zone A") {
    Container_Boundary(app, "func-public") {
        Component(a, "A", ".NET", "desc")
    }
}
@enduml'''
        d = parse(src)
        ids = {b.id: b for b in d.boundaries}
        assert ids['zone'].parent_boundary is None
        assert ids['app'].parent_boundary == 'zone'
        assert d.components[0].parent_boundary == 'app'

    def test_generic_and_enterprise_boundary(self):
        src = '''@startuml
Enterprise_Boundary(ent, "Willhem") {
    Boundary(grp, "Group") {
        Component(a, "A", ".NET", "desc")
    }
}
@enduml'''
        d = parse(src)
        ids = {b.id: b for b in d.boundaries}
        assert set(ids) == {'ent', 'grp'}
        assert ids['grp'].parent_boundary == 'ent'
        assert d.components[0].parent_boundary == 'grp'

    def test_boundary_with_type_argument(self):
        """Boundary(id, label, type) — the optional 3rd positional arg."""
        d = parse('@startuml\nBoundary(b, "Group", "zone") {\n}\n@enduml')
        assert d.boundaries[0].label == 'Group'

    def test_db_and_queue_variants(self):
        src = '''@startuml
ContainerDb(db, "Store", "SQL", "State")
ContainerQueue(q, "Queue", "SB", "Msgs")
ComponentDb(cdb, "Cache", "Redis", "Hot")
ComponentQueue(cq, "Topic", "SB", "Events")
SystemDb(sdb, "Warehouse", "Analytics")
SystemQueue(sq, "Broker", "Events")
@enduml'''
        d = parse(src)
        by_id = {c.id: c for c in d.components}
        assert set(by_id) == {'db', 'q', 'cdb', 'cq', 'sdb', 'sq'}
        # 4-arg forms keep technology
        assert by_id['db'].technology == 'SQL'
        assert by_id['cq'].technology == 'SB'
        # 3-arg System* forms put the 2nd string in description, not technology
        assert by_id['sdb'].technology == ''
        assert by_id['sdb'].description == 'Analytics'

    def test_ext_container_and_person_variants(self):
        src = '''@startuml
Container_Ext(c, "Ext container", "Node", "Desc")
Person_Ext(p, "Ext person", "Desc")
ContainerDb_Ext(d, "Ext db", "SQL", "Desc")
@enduml'''
        d = parse(src)
        by_id = {c.id: c for c in d.components}
        assert by_id['c'].technology == 'Node'
        assert by_id['p'].technology == ''
        assert by_id['p'].description == 'Desc'
        assert by_id['d'].technology == 'SQL'

    def test_l3_zone_diagram_keeps_everything(self):
        """End-to-end shape of the Willhem target diagram."""
        src = '''@startuml
Person(applicant, "Applicant", "Housing seeker")
System_Ext(web, "My Pages", "Optimizely")

System_Boundary(zoneA, "Zone A") {
    Component(apim, "APIM", "Azure", "Gateway", $tags="ey")
    Container_Boundary(pubfa, "func-willhem-public") {
        Component(leasing, "Leasing API", ".NET 8", "Submit", $tags="ey")
        Component(gate, "Gate check", ".NET 8", "Eligibility", $tags="ey")
    }
}

Rel(applicant, web, "Uses")
Rel(web, apim, "Calls")
Rel(apim, leasing, "Routes")
Rel(leasing, gate, "Evaluates")
@enduml'''
        d = parse(src)
        assert len(d.components) == 5
        assert len(d.boundaries) == 2
        assert len(d.relationships) == 4
        ids = {c.id for c in d.components}
        assert ids == {'applicant', 'web', 'apim', 'leasing', 'gate'}
        by_id = {c.id: c for c in d.components}
        assert by_id['apim'].parent_boundary == 'zoneA'
        assert by_id['gate'].parent_boundary == 'pubfa'


class TestParseTagBorders:
    """AddElementTag border properties must survive parsing so build-state
    overlays (e.g. $tags="gap+ey") can be rendered in draw.io, not just PlantUML."""

    def test_border_color(self):
        d = parse('@startuml\nAddElementTag("gap", $borderColor="#E8590C")\n@enduml')
        assert d.tag_styles['gap'].border_color == '#E8590C'

    def test_border_thickness_and_style(self):
        d = parse('@startuml\n'
                  'AddElementTag("new", $borderColor="#69DB7C", $borderThickness="4")\n'
                  'AddElementTag("dep", $bgColor="#9E9E9E", $borderStyle="dashed")\n'
                  '@enduml')
        assert d.tag_styles['new'].border_thickness == '4'
        assert d.tag_styles['new'].bg_color == ''
        assert d.tag_styles['dep'].border_style == 'dashed'
        assert d.tag_styles['dep'].bg_color == '#9E9E9E'

    def test_bg_color_absent_is_empty_not_default(self):
        """A border-only overlay tag must not claim a background colour,
        otherwise it would mask the ownership fill it is overlaid on."""
        d = parse('@startuml\nAddElementTag("new", $borderColor="#69DB7C")\n@enduml')
        assert d.tag_styles['new'].bg_color == ''


class TestParseIncludes:
    """`!include _style.puml` must be resolved, or every shared AddElementTag
    (the ownership colour palette) is silently invisible to the converter."""

    def _write(self, tmp_path, name, text):
        p = tmp_path / name
        p.write_text(text, encoding='utf-8')
        return p

    def test_local_include_brings_in_tags(self, tmp_path):
        self._write(tmp_path, '_style.puml',
                    'AddElementTag("ey", $bgColor="#2E6DB4", $legendText="EY-built")')
        main = self._write(tmp_path, 'd.puml',
                           '@startuml\n!include _style.puml\n'
                           'Component(a, "A", ".NET", "d", $tags="ey")\n@enduml')
        d = parse(main.read_text(), base_dir=tmp_path)
        assert 'ey' in d.tag_styles
        assert d.tag_styles['ey'].bg_color == '#2E6DB4'

    def test_stdlib_include_is_ignored(self, tmp_path):
        d = parse('@startuml\n!include <C4/C4_Component>\nComponent(a, "A", ".NET", "d")\n@enduml',
                  base_dir=tmp_path)
        assert len(d.components) == 1

    def test_missing_include_is_ignored_not_fatal(self, tmp_path):
        d = parse('@startuml\n!include nope.puml\nComponent(a, "A", ".NET", "d")\n@enduml',
                  base_dir=tmp_path)
        assert len(d.components) == 1

    def test_nested_include(self, tmp_path):
        self._write(tmp_path, 'inner.puml', 'AddElementTag("x", $bgColor="#111111")')
        self._write(tmp_path, 'outer.puml', '!include inner.puml\nAddElementTag("y", $bgColor="#222222")')
        main = self._write(tmp_path, 'd.puml', '@startuml\n!include outer.puml\n@enduml')
        d = parse(main.read_text(), base_dir=tmp_path)
        assert d.tag_styles['x'].bg_color == '#111111'
        assert d.tag_styles['y'].bg_color == '#222222'

    def test_circular_include_terminates(self, tmp_path):
        self._write(tmp_path, 'a.puml', '!include b.puml\nAddElementTag("a", $bgColor="#111111")')
        self._write(tmp_path, 'b.puml', '!include a.puml\nAddElementTag("b", $bgColor="#222222")')
        main = self._write(tmp_path, 'd.puml', '@startuml\n!include a.puml\n@enduml')
        d = parse(main.read_text(), base_dir=tmp_path)
        assert set(d.tag_styles) == {'a', 'b'}

    def test_quoted_and_relative_include(self, tmp_path):
        sub = tmp_path / 'sub'
        sub.mkdir()
        (sub / 's.puml').write_text('AddElementTag("q", $bgColor="#333333")', encoding='utf-8')
        d = parse('@startuml\n!include "sub/s.puml"\n@enduml', base_dir=tmp_path)
        assert d.tag_styles['q'].bg_color == '#333333'

    def test_include_defaults_to_no_resolution_without_base_dir(self):
        d = parse('@startuml\n!include _style.puml\nComponent(a, "A", ".NET", "d")\n@enduml')
        assert len(d.components) == 1
        assert d.tag_styles == {}

    def test_parse_file_helper_resolves_relative_to_the_file(self, tmp_path):
        from puml_drawio.puml_parser import parse_file
        self._write(tmp_path, '_style.puml', 'AddElementTag("ey", $bgColor="#2E6DB4")')
        main = self._write(tmp_path, 'd.puml',
                           '@startuml\n!include _style.puml\n'
                           'Component(a, "A", ".NET", "d", $tags="ey")\n@enduml')
        d = parse_file(main)
        assert d.tag_styles['ey'].bg_color == '#2E6DB4'
