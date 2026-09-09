"""Tests for the c4drawio command line interface.

The CLI is the primary interface, so it gets the same rigour as the library:
exit codes, output shape, and the quality gate are all contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from puml_drawio import cli, elk_layout

SAMPLE = """@startuml
!include _style.puml
Person(user, "User", "someone")
System_Boundary(zone, "A Zone") {
    Container(api, "API", ".NET", "front door", $tags="ey")
    Container(svc, "Service", ".NET", "the work")
}
System(db, "Database", "master")
Rel(user, api, "calls")
Rel(api, svc, "delegates")
Rel(svc, db, "reads and writes")
Rel(user, db, "long edge that skips a rank")
@enduml"""

STYLE = 'AddElementTag("ey", $bgColor="#2E6DB4", $legendText="EY-built")'


@pytest.fixture
def project(tmp_path):
    (tmp_path / "plantuml").mkdir()
    (tmp_path / "plantuml" / "_style.puml").write_text(STYLE)
    (tmp_path / "plantuml" / "arch.puml").write_text(SAMPLE)
    return tmp_path


def run(args, capsys):
    code = cli.main([str(a) for a in args])
    out, err = capsys.readouterr()
    return code, out, err


needs_elk = pytest.mark.skipif(
    not elk_layout.available(), reason="java/plantuml.jar not available"
)


class TestUsage:
    def test_no_args_shows_usage_and_fails(self, capsys):
        code, out, err = run([], capsys)
        assert code != 0
        assert "convert" in (out + err)

    def test_help_lists_every_subcommand(self, capsys):
        with pytest.raises(SystemExit):
            run(["--help"], capsys)
        out = capsys.readouterr().out
        for sub in ("convert", "render", "score", "build", "doctor"):
            assert sub in out

    def test_unknown_subcommand_fails(self, capsys):
        with pytest.raises(SystemExit):
            run(["frobnicate"], capsys)


class TestDoctor:
    def test_reports_each_dependency(self, capsys):
        code, out, _ = run(["doctor"], capsys)
        for tool in ("java", "javac", "plantuml.jar", "draw.io"):
            assert tool in out

    def test_json_output(self, capsys):
        code, out, _ = run(["doctor", "--json"], capsys)
        data = json.loads(out)
        assert "java" in data and "ok" in data


@needs_elk
class TestConvert:
    def test_writes_a_drawio_beside_the_default_location(self, project, capsys):
        src = project / "plantuml" / "arch.puml"
        code, out, _ = run(["convert", src], capsys)
        assert code == 0
        assert (project / "drawio" / "arch.drawio").is_file()

    def test_explicit_output_path(self, project, capsys, tmp_path):
        dst = tmp_path / "custom" / "out.drawio"
        code, _, _ = run(["convert", project / "plantuml" / "arch.puml", "-o", dst], capsys)
        assert code == 0 and dst.is_file()

    def test_resolves_includes_so_tag_colours_survive(self, project, capsys):
        run(["convert", project / "plantuml" / "arch.puml"], capsys)
        xml = (project / "drawio" / "arch.drawio").read_text()
        assert "EY-built" in xml, "legend from _style.puml missing: include not resolved"

    def test_refuses_to_clobber_without_force(self, project, capsys):
        src = project / "plantuml" / "arch.puml"
        run(["convert", src], capsys)
        (project / "drawio" / "arch.drawio").write_text("HAND POLISHED")
        code, out, _ = run(["convert", src], capsys)
        assert code == 0
        assert "skip" in out.lower()
        assert (project / "drawio" / "arch.drawio").read_text() == "HAND POLISHED"

    def test_force_overwrites(self, project, capsys):
        src = project / "plantuml" / "arch.puml"
        run(["convert", src], capsys)
        (project / "drawio" / "arch.drawio").write_text("HAND POLISHED")
        code, _, _ = run(["convert", src, "--force"], capsys)
        assert code == 0
        assert "mxfile" in (project / "drawio" / "arch.drawio").read_text()

    def test_picks_up_the_overrides_sidecar(self, project, capsys):
        (project / "plantuml" / "arch.overrides.json").write_text(
            json.dumps({"nodes": {"db": {"x": 4242}}})
        )
        run(["convert", project / "plantuml" / "arch.puml"], capsys)
        assert "4242" in (project / "drawio" / "arch.drawio").read_text()

    def test_missing_input_is_a_clean_error(self, project, capsys):
        code, out, err = run(["convert", project / "nope.puml"], capsys)
        assert code != 0
        assert "not found" in (out + err).lower()

    def test_reports_the_score_after_converting(self, project, capsys):
        code, out, _ = run(["convert", project / "plantuml" / "arch.puml"], capsys)
        assert "crossings" in out


@needs_elk
class TestScore:
    def test_reports_metrics(self, project, capsys):
        run(["convert", project / "plantuml" / "arch.puml"], capsys)
        code, out, _ = run(["score", project / "drawio" / "arch.drawio"], capsys)
        assert code == 0
        assert "crossings" in out

    def test_json_shape(self, project, capsys):
        run(["convert", project / "plantuml" / "arch.puml"], capsys)
        code, out, _ = run(["score", project / "drawio" / "arch.drawio", "--json"], capsys)
        data = json.loads(out)
        entry = data[0]
        for k in ("file", "nodes", "edges", "edge_node_crossings",
                  "edge_edge_crossings", "label_overlap_area", "aspect_ratio"):
            assert k in entry

    def test_gate_passes_when_clean(self, project, capsys):
        run(["convert", project / "plantuml" / "arch.puml"], capsys)
        code, _, _ = run(["score", project / "drawio" / "arch.drawio",
                          "--max-crossings", "0"], capsys)
        assert code == 0

    def test_gate_fails_with_exit_code_2(self, project, capsys, tmp_path):
        """A dirty diagram must fail the gate distinguishably from an error."""
        bad = tmp_path / "bad.drawio"
        bad.write_text(
            '<mxfile><diagram><mxGraphModel><root><mxCell id="0"/>'
            '<mxCell id="1" parent="0"/>'
            '<mxCell id="c_a" vertex="1" parent="1" style="rounded=1;">'
            '<mxGeometry x="0" y="0" width="100" height="50" as="geometry"/></mxCell>'
            '<mxCell id="c_b" vertex="1" parent="1" style="rounded=1;">'
            '<mxGeometry x="0" y="200" width="100" height="50" as="geometry"/></mxCell>'
            '<mxCell id="c_c" vertex="1" parent="1" style="rounded=1;">'
            '<mxGeometry x="0" y="100" width="100" height="50" as="geometry"/></mxCell>'
            '<mxCell id="e0" edge="1" parent="1" source="c_a" target="c_b">'
            '<mxGeometry relative="1" as="geometry"/></mxCell>'
            '</root></mxGraphModel></diagram></mxfile>'
        )
        code, out, _ = run(["score", bad, "--max-crossings", "0"], capsys)
        assert code == 2, "quality failure must be exit 2, not 1"

    def test_accepts_a_directory(self, project, capsys):
        run(["convert", project / "plantuml" / "arch.puml"], capsys)
        code, out, _ = run(["score", project / "drawio"], capsys)
        assert code == 0 and "arch.drawio" in out

    def test_scores_a_puml_by_converting_in_memory(self, project, capsys):
        """Lets you check a source before committing to an output file."""
        code, out, _ = run(["score", project / "plantuml" / "arch.puml"], capsys)
        assert code == 0 and "crossings" in out
