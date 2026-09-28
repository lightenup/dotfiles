"""Tests for the drawiovsdx command line interface.

The wrapper's whole job is to be a trustworthy boundary between the Python
pipeline and the Node converter: resolve paths the way the rest of the
pipeline does, pass the right flags, and report the converter's verdict
faithfully. None of these tests need Node or the network — the subprocess is
stubbed, because what is under test is the boundary, not the converter (which
has its own suite on the other side).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from drawio_vsdx import bootstrap, cli


class FakeCompleted:
    """Stands in for subprocess.CompletedProcess."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def report(**overrides):
    base = {
        "ok": True,
        "output": "out.vsdx",
        "bytes": 1234,
        "pages": ["Page-1"],
        "warnings": [],
        "degraded": 0,
        "degradation": None,
        "strict": True,
    }
    base.update(overrides)
    return json.dumps(base)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "diagrams" / "drawio").mkdir(parents=True)
    src = tmp_path / "diagrams" / "drawio" / "arch.drawio"
    src.write_text("<mxfile></mxfile>")
    return tmp_path


@pytest.fixture
def installed(tmp_path, monkeypatch):
    """Pretends the converter is bootstrapped, so tests skip cloning."""
    home = tmp_path / "converter"
    (home / "src").mkdir(parents=True)
    (home / "src" / "cli.js").write_text("// stub")
    (home / "package.json").write_text('{"name":"drawio-vsdx"}')
    (home / "node_modules").mkdir()
    monkeypatch.setenv("DRAWIO_VSDX_HOME", str(home))
    return home


# ---------------------------------------------------------------- paths


def test_default_output_mirrors_the_drawio_convention(project):
    """diagrams/drawio/arch.drawio -> diagrams/vsdx/arch.vsdx"""
    src = project / "diagrams" / "drawio" / "arch.drawio"
    assert cli.default_output(src) == project / "diagrams" / "vsdx" / "arch.vsdx"


def test_default_output_falls_back_to_a_sibling_directory(tmp_path):
    """A file outside a diagrams/ tree still gets a vsdx/ directory beside it."""
    src = tmp_path / "scratch" / "arch.drawio"
    src.parent.mkdir()
    src.write_text("<mxfile/>")
    assert cli.default_output(src) == tmp_path / "scratch" / "vsdx" / "arch.vsdx"


def test_explicit_output_wins(project, installed, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run_converter", lambda argv, **kw: (calls.append(argv), FakeCompleted(0, report()))[1])
    src = project / "diagrams" / "drawio" / "arch.drawio"
    rc = cli.main(["convert", str(src), "-o", str(project / "custom.vsdx")])
    assert rc == cli.EXIT_OK
    assert str(project / "custom.vsdx") in calls[0]


# ---------------------------------------------------------------- exit codes


def test_clean_conversion_exits_zero(project, installed, monkeypatch):
    monkeypatch.setattr(cli, "_run_converter", lambda argv, **kw: FakeCompleted(0, report()))
    rc = cli.main(["convert", str(project / "diagrams" / "drawio" / "arch.drawio")])
    assert rc == cli.EXIT_OK


def test_fidelity_loss_propagates_as_exit_three(project, installed, monkeypatch):
    """The converter's exit 3 must not be flattened into success or failure."""
    monkeypatch.setattr(
        cli,
        "_run_converter",
        lambda argv, **kw: FakeCompleted(
            3, report(degraded=2, degradation="2 image(s) dropped [image-not-found]")
        ),
    )
    rc = cli.main(["convert", str(project / "diagrams" / "drawio" / "arch.drawio")])
    assert rc == cli.EXIT_DEGRADED


def test_converter_failure_is_an_error(project, installed, monkeypatch):
    monkeypatch.setattr(
        cli,
        "_run_converter",
        lambda argv, **kw: FakeCompleted(1, json.dumps({"ok": False, "error": "boom"})),
    )
    rc = cli.main(["convert", str(project / "diagrams" / "drawio" / "arch.drawio")])
    assert rc == cli.EXIT_ERROR


def test_missing_input_is_an_error(tmp_path, installed):
    assert cli.main(["convert", str(tmp_path / "nope.drawio")]) == cli.EXIT_ERROR


# ---------------------------------------------------------------- flags


def test_strict_is_the_default(project, installed, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run_converter", lambda argv, **kw: (calls.append(argv), FakeCompleted(0, report()))[1])
    cli.main(["convert", str(project / "diagrams" / "drawio" / "arch.drawio")])
    assert "--no-strict" not in calls[0], "strict must not be disabled by default"


def test_no_strict_is_forwarded(project, installed, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run_converter", lambda argv, **kw: (calls.append(argv), FakeCompleted(0, report()))[1])
    cli.main(["convert", str(project / "diagrams" / "drawio" / "arch.drawio"), "--no-strict"])
    assert "--no-strict" in calls[0]


def test_image_root_is_passed_through(project, installed, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run_converter", lambda argv, **kw: (calls.append(argv), FakeCompleted(0, report()))[1])
    cli.main([
        "convert", str(project / "diagrams" / "drawio" / "arch.drawio"),
        "--image-root", "/somewhere/app.asar",
    ])
    assert "--image-root" in calls[0]
    assert "/somewhere/app.asar" in calls[0]


def test_drawio_desktop_supplies_a_default_image_root(project, installed, monkeypatch, tmp_path):
    """The Azure icons only resolve if we point the converter at draw.io's webapp."""
    asar = tmp_path / "app.asar"
    asar.write_text("stub")
    monkeypatch.setattr(cli, "discover_image_roots", lambda: [str(asar)])
    calls = []
    monkeypatch.setattr(cli, "_run_converter", lambda argv, **kw: (calls.append(argv), FakeCompleted(0, report()))[1])
    cli.main(["convert", str(project / "diagrams" / "drawio" / "arch.drawio")])
    assert str(asar) in calls[0], "a discovered image root should be forwarded"


# ---------------------------------------------------------------- output


def test_json_mode_emits_the_converter_report(project, installed, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "_run_converter",
        lambda argv, **kw: FakeCompleted(3, report(degraded=1, degradation="1 image(s) dropped")),
    )
    rc = cli.main(["convert", str(project / "diagrams" / "drawio" / "arch.drawio"), "--json"])
    assert rc == cli.EXIT_DEGRADED
    payload = json.loads(capsys.readouterr().out)
    assert payload["degraded"] == 1


def test_human_output_names_the_degradation(project, installed, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "_run_converter",
        lambda argv, **kw: FakeCompleted(3, report(degraded=1, degradation="1 image(s) dropped [remote]")),
    )
    cli.main(["convert", str(project / "diagrams" / "drawio" / "arch.drawio")])
    captured = capsys.readouterr()
    assert "dropped" in (captured.out + captured.err)


# ---------------------------------------------------------------- bootstrap


def test_pinned_ref_is_a_tag_or_full_sha():
    ref = bootstrap.PINNED_REF
    assert ref, "a pin is required; tracking a moving branch is not allowed"
    assert ref.startswith("v") or len(ref) == 40, f"unexpected pin format: {ref}"


def test_clone_uses_gh_and_checks_out_the_pin(tmp_path, monkeypatch):
    """gh handles auth for the private repo; the pin is fetched explicitly so
    the same command works whether it names a tag or a commit."""
    commands = []

    def fake_run(argv, **kwargs):
        commands.append(argv)
        return FakeCompleted(0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "/usr/bin/" + name)
    bootstrap.install(tmp_path / "home")

    flat = [" ".join(c) for c in commands]
    assert any(c.startswith("gh repo clone") for c in flat), flat
    assert any(bootstrap.PINNED_REF in c for c in flat), "the pin must be checked out"
    assert any("npm" in c for c in flat), "dependencies must be installed"


def test_bootstrap_without_gh_explains_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: None)
    with pytest.raises(bootstrap.BootstrapError) as excinfo:
        bootstrap.install(tmp_path / "home")
    assert "gh" in str(excinfo.value)


def test_home_honours_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAWIO_VSDX_HOME", str(tmp_path / "elsewhere"))
    assert bootstrap.converter_home() == tmp_path / "elsewhere"


def test_home_defaults_under_local_share(monkeypatch):
    monkeypatch.delenv("DRAWIO_VSDX_HOME", raising=False)
    home = bootstrap.converter_home()
    assert ".local/share" in str(home)
    assert bootstrap.PINNED_REF in str(home), "installs are keyed by pin so bumps are clean"


# ---------------------------------------------------------------- doctor


def test_doctor_reports_each_tool(installed, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_node_version", lambda: "v22.0.0")
    monkeypatch.setattr(cli, "discover_image_roots", lambda: [])
    rc = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "node" in out
    assert "converter" in out
    assert rc in (cli.EXIT_OK, cli.EXIT_ERROR)


def test_doctor_json_is_machine_readable(installed, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_node_version", lambda: "v22.0.0")
    monkeypatch.setattr(cli, "discover_image_roots", lambda: ["/Applications/draw.io.app"])
    cli.main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert "node" in payload
    assert "image_roots" in payload
    assert "ok" in payload


def test_doctor_fails_when_node_is_missing(installed, monkeypatch):
    monkeypatch.setattr(cli, "_node_version", lambda: None)
    monkeypatch.setattr(cli, "discover_image_roots", lambda: [])
    assert cli.main(["doctor"]) == cli.EXIT_ERROR


def test_doctor_flags_a_missing_image_root(installed, monkeypatch, capsys):
    """Without one, every Azure and bundled icon silently vanishes -- doctor
    has to say so even though conversion still 'works'."""
    monkeypatch.setattr(cli, "_node_version", lambda: "v22.0.0")
    monkeypatch.setattr(cli, "discover_image_roots", lambda: [])
    cli.main(["doctor"])
    out = capsys.readouterr().out.lower()
    assert "image root" in out
