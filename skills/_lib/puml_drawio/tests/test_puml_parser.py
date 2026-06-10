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
        d = parse('AddElementTag("basic")')
        ts = d.tag_styles['basic']
        assert ts.bg_color == '#438DD5'
        assert ts.font_color == '#FFFFFF'


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
