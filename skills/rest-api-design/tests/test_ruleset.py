"""Regression tests for the rest-api-design Spectral ruleset.

These assert the *rule codes* that fire on each fixture, not their messages. Messages are
meant to be edited freely as the guidance improves; which rule catches which defect is the
contract.

The `good.yaml` case is the important one. A ruleset that cannot be satisfied trains people
to ignore it, so a document that conforms to the example style profile must produce zero
findings from this skill's rules.

Requires Node and network access on first run (npx fetches the Spectral CLI). Run with:

    python3 -m pytest skills/rest-api-design/tests -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent
FIXTURES = SKILL / "tests" / "fixtures"
PROFILE = SKILL / "style" / "api-style.example.yaml"
LINT = SKILL / "lint-api.sh"
OVERLAY = SKILL / "spectral" / "profile-overlay.mjs"

pytestmark = pytest.mark.skipif(
    shutil.which("npx") is None or shutil.which("node") is None,
    reason="Node and npx are required to run Spectral",
)


def _lint(document: str, *, profile: Path | None = PROFILE) -> list[dict]:
    """Run lint-api.sh over a fixture and return the parsed findings."""
    cmd = [str(LINT), "--format", "json"]
    if profile is not None:
        cmd += ["--profile", str(profile)]
    cmd.append(str(FIXTURES / document))

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, f"lint-api.sh failed:\n{proc.stderr}"
    if not proc.stdout.strip():
        return []
    return json.loads(proc.stdout)


def _rad_codes(results: list[dict]) -> Counter:
    """Only this skill's rules; spectral:oas findings are not our contract."""
    return Counter(r["code"] for r in results if str(r["code"]).startswith("rad-"))


@pytest.fixture(scope="module")
def bad():
    return _lint("bad.yaml", profile=None)


@pytest.fixture(scope="module")
def good():
    return _lint("good.yaml")


@pytest.fixture(scope="module")
def aggregate():
    return _lint("aggregate.yaml")


# ── The clean document must stay clean ───────────────────────────────────────

def test_conforming_document_produces_no_findings(good):
    codes = _rad_codes(good)
    assert codes == Counter(), (
        "A document conforming to the example profile produced findings. Either the rule "
        f"is wrong or the fixture is: {dict(codes)}"
    )


# ── Structural defects ───────────────────────────────────────────────────────

def test_schema_defects_are_all_caught(bad):
    """type: '', invented type names, placeholder enums, arrays without items,
    empty objects, null-in-enum, and a JSON Schema pasted into a type field."""
    assert _rad_codes(bad)["rad-schema-defects"] == 11


def test_missing_response_contract_is_caught(bad):
    messages = [r["message"] for r in bad if r["code"] == "rad-response-contract"]
    assert any("declares no `content`" in m for m in messages)
    assert any("no 4xx or 5xx response" in m for m in messages)
    assert any("empty description" in m for m in messages)


def test_duplicate_operation_id_is_caught(bad):
    messages = [r["message"] for r in bad if r["code"] == "rad-operation-identity"]
    assert any("already used by" in m for m in messages)


def test_contradictory_summary_and_description_is_caught(bad):
    messages = [r["message"] for r in bad if r["code"] == "rad-operation-identity"]
    assert any("describe different lookups" in m for m in messages)


def test_orphaned_component_is_caught(bad):
    messages = [r["message"] for r in bad if r["code"] == "rad-orphan-components"]
    assert any("OrphanedResponse" in m for m in messages)


def test_whitespace_in_path_is_caught(bad):
    messages = [r["message"] for r in bad if r["code"] == "rad-path-hygiene"]
    assert any("contains whitespace" in m for m in messages)


def test_base_rules_need_no_profile(bad):
    """Structural rules must fire with no style profile at all — an estate that has
    recorded no decisions still deserves the defects it can act on."""
    assert _rad_codes(bad)["rad-schema-defects"] > 0


# ── Decomposition smells ─────────────────────────────────────────────────────

def test_all_three_decomposition_smells_fire(aggregate):
    messages = [r["message"] for r in aggregate if r["code"] == "rad-decomposition-smell"]
    assert any("object levels deep" in m for m in messages), "depth smell did not fire"
    assert any("leaf properties" in m for m in messages), "breadth smell did not fire"
    assert any("nullable" in m for m in messages), "nullability smell did not fire"


def test_decomposition_smells_are_advisory(aggregate):
    """Severity 4 is `hint`. These signals point the procedure at a representation;
    they do not assert that anything is wrong."""
    smells = [r for r in aggregate if r["code"] == "rad-decomposition-smell"]
    assert smells and all(r["severity"] == 3 for r in smells)


def test_decomposition_smells_silent_on_a_small_representation(good):
    assert _rad_codes(good)["rad-decomposition-smell"] == 0


# ── Security and privacy ─────────────────────────────────────────────────────

def test_third_party_pii_in_self_scoped_response_is_caught(aggregate):
    messages = [r["message"] for r in aggregate if r["code"] == "rad-security"]
    hits = [m for m in messages if "belonging to other parties" in m]
    assert hits, "third-party PII in a /me response was not caught"
    assert "coBorrowers[].nationalId" in hits[0]


def test_unmasked_personal_identifiers_are_caught(aggregate):
    messages = [r["message"] for r in aggregate if r["code"] == "rad-security"]
    assert any("no indication of masking" in m for m in messages)


# ── Profile overlay ──────────────────────────────────────────────────────────

def test_overlay_emits_rules_for_recorded_decisions(tmp_path):
    out = tmp_path / "derived.yaml"
    subprocess.run(
        ["node", str(OVERLAY), "--profile", str(PROFILE), "--out", str(out)],
        check=True, capture_output=True, text=True, timeout=60,
    )
    text = out.read_text()
    for expected in [
        "rad-path-style", "rad-error-model", "rad-required-statuses",
        "rad-pagination-style", "rad-security", "rad-cross-cutting",
        "rad-webhooks", "rad-decomposition-smell",
    ]:
        assert expected in text, f"{expected} missing from the derived ruleset"


def test_overlay_without_a_profile_emits_base_rules_only(tmp_path):
    """No recorded decisions means no style findings. Silence is the correct output."""
    out = tmp_path / "derived.yaml"
    subprocess.run(
        ["node", str(OVERLAY), "--out", str(out)],
        check=True, capture_output=True, text=True, timeout=60,
    )
    text = out.read_text()
    assert "extends:" in text
    assert "rules:" not in text


def test_overlay_derives_thresholds_from_the_profile(tmp_path):
    profile = tmp_path / "api-style.yaml"
    profile.write_text(
        "version: 1\n"
        "naming:\n  paths: kebab-case\n"
        "errors:\n  model: problem-details\n"
        "smells:\n"
        "  max-response-depth: 7\n"
        "  max-response-properties: 99\n"
    )
    out = tmp_path / "derived.yaml"
    subprocess.run(
        ["node", str(OVERLAY), "--profile", str(profile), "--out", str(out)],
        check=True, capture_output=True, text=True, timeout=60,
    )
    text = out.read_text()
    assert "maxDepth: 7" in text
    assert "maxProperties: 99" in text


def test_raised_thresholds_silence_the_smells(tmp_path):
    """A team that has justified a larger representation should stop being told about it."""
    profile = tmp_path / "api-style.yaml"
    profile.write_text(
        "version: 1\n"
        "naming:\n  paths: kebab-case\n"
        "errors:\n  model: problem-details\n"
        "smells:\n"
        "  max-response-depth: 20\n"
        "  max-response-properties: 500\n"
        "  max-nullable-ratio: 0.99\n"
    )
    results = _lint("aggregate.yaml", profile=profile)
    assert _rad_codes(results)["rad-decomposition-smell"] == 0


# ── Reporting posture ────────────────────────────────────────────────────────

def test_report_mode_exits_zero_despite_errors():
    """The default posture is recommendation, not gate."""
    proc = subprocess.run(
        [str(LINT), str(FIXTURES / "bad.yaml")],
        capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0


def test_gate_mode_exits_non_zero_on_errors():
    proc = subprocess.run(
        [str(LINT), "--gate", str(FIXTURES / "bad.yaml")],
        capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode != 0
