"""The family anatomy profiler: content-free, complete, and honest (#837).

Steer #836 makes the owner's reference families the bar for generation.
``tools/family_anatomy.py`` turns a family into counts and kinds so a
reference and ours can be compared gap by gap.  These tests run on families
we generate ourselves -- no reference family is, or may be, in the repo.

What is worth breaking here:

1. **Content-free.**  The profile of a third-party family must be safe to
   quote in a public record, so it may never carry the family's text.
2. **Nothing guessed.**  Every aspect says how it was read; a record that
   fails to decode is counted, not skipped.
3. **The comparison is honest both ways**: ours-vs-ours has no gaps, and a
   richer family shows up as richer.
4. **The quarantine holds**: reference families are git-ignored and the
   plugin deny-audit refuses them.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import family_anatomy as FA   # noqa: E402

PROMPTS = {
    "lighting_control_panel": "a lighting control panel",
    "cable_tray": "a 24 in wide cable tray",
    "strut_channel": "a strut channel",
    "wireway": "a wireway",
    "junction_box": "a junction box",
    "conduit": "a conduit",
}


@pytest.fixture(scope="module")
def families(tmp_path_factory):
    from rvt.frontdoor import router as R
    out = {}
    for key, prompt in PROMPTS.items():
        d = tmp_path_factory.mktemp(key)
        res = R.route({"prompt": prompt}, "rfa", out=str(d), quiet=True)
        assert res.ok, (key, res.status)
        out[key] = res.files["rfa"]
    return out


@pytest.fixture(scope="module")
def profiles(families):
    return {k: FA.profile(p) for k, p in families.items()}


def _strings_in(path):
    """Every string the family itself carries that a profile must never
    repeat: parameter captions, type names, the family name."""
    from rvt.families import FamilyIndex
    fi = FamilyIndex(path)
    found = set()

    def walk(v, key=""):
        # schema identifiers (a ptr_class, a spec/group type id) are not the
        # family's text -- the profile uses ParamDef class names on purpose
        if isinstance(v, dict):
            for k, x in v.items():
                if k != "ptr_class" and not k.lower().endswith("typeid"):
                    walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str) and len(v) >= 3:
            found.add(v)

    for eid, r in fi.unit_records(0).get(102, {}).items():
        if fi.class_name(r.class_id) in ("ParamElemFamily", "Family"):
            walk(fi.value(0, int(eid), 102))
    return found


# ---------------------------------------------------------------------------
# 1. content-free
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(PROMPTS))
def test_a_profile_never_repeats_the_familys_own_text(families, profiles, key):
    text = json.dumps(profiles[key])
    strings = _strings_in(families[key])
    assert strings, "the family carries no strings -- the check would be vacuous"
    leaked = sorted(s for s in strings if s in text and not re.fullmatch(r"[a-z_]+", s))
    assert not leaked, f"{key}: the profile repeats the family's text: {leaked[:5]}"


def _keys(v, out):
    if isinstance(v, dict):
        for k, x in v.items():
            out.add(k)
            _keys(x, out)
    return out


@pytest.mark.parametrize("key", sorted(PROMPTS))
def test_every_key_is_from_our_vocabulary_or_a_schema_identifier(profiles, key):
    """Keys are this module's words, a ParamDef class name, or the short
    form of a parameter-group type id -- never a name the family chose."""
    for k in _keys(profiles[key], set()):
        assert re.fullmatch(r"[A-Za-z_0-9]+", k), (key, k)
    for k in profiles[key]["parameters"]["value"]["by_storage"]:
        assert k.startswith("ParamDef") or k == "unknown", k


# ---------------------------------------------------------------------------
# 2. nothing guessed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(PROMPTS))
def test_every_aspect_says_how_it_was_read_and_nothing_failed_to_decode(profiles, key):
    prof = profiles[key]
    assert {a["how"] for a in prof.values()} <= {"decoded", "class-count", "not-yet-readable"}
    assert prof["undecoded"]["value"] == {}, prof["undecoded"]
    assert prof["visibility_parameter_bindings"]["how"] == "not-yet-readable"


def test_the_lighting_control_panel_is_seven_extrusions_and_its_parameters(profiles):
    """Pinned to what the #816 builder authors: back, four walls, door, latch."""
    lcp = profiles["lighting_control_panel"]["forms"]["value"]
    assert lcp["by_kind"] == {"extrusion": 7} and lcp["solids"] == 7 and lcp["voids"] == 0
    params = profiles["lighting_control_panel"]["parameters"]["value"]
    assert params["total"] >= 3 and params["by_group"].get("dimensions", 0) >= 3
    assert profiles["lighting_control_panel"]["types"]["value"]["total"] == 1


# ---------------------------------------------------------------------------
# 3. the comparison
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(PROMPTS))
def test_a_family_compared_with_itself_has_no_gaps(profiles, key):
    assert FA.compare(profiles[key], profiles[key]) == []


def test_a_richer_family_shows_up_as_richer_and_missing_features_rank_first(profiles):
    tray, lcp = profiles["cable_tray"], profiles["lighting_control_panel"]
    assert tray["forms"]["value"]["total"] > lcp["forms"]["value"]["total"]
    gaps = FA.compare(tray, lcp)
    measures = {(g["aspect"], g["measure"]) for g in gaps}
    assert ("forms", "total") in measures
    missing = [g["missing"] for g in gaps]
    assert missing == sorted(missing, reverse=True), "a missing feature must rank first"
    for g in gaps:
        assert g["reference"] > g["ours"]


def test_the_cli_writes_the_report_and_refuses_a_non_family_in_one_line(families, tmp_path):
    out = tmp_path / "cmp.json"
    rc = FA.main(["compare", families["cable_tray"], families["lighting_control_panel"],
                  "--json", str(out)])
    assert rc == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert set(rep) == {"reference", "ours", "gaps"}
    junk = tmp_path / "junk.rfa"
    junk.write_bytes(b"not a family")
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "family_anatomy.py"),
                           "profile", str(junk)], capture_output=True, text=True)
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr and proc.stderr.count("\n") == 1, proc.stderr


# ---------------------------------------------------------------------------
# 4. the quarantine
# ---------------------------------------------------------------------------

def test_reference_families_are_git_ignored():
    proc = subprocess.run(["git", "check-ignore", "-q", "samples/reference-families/any.rfa"],
                          cwd=ROOT, capture_output=True)
    assert proc.returncode == 0, "samples/reference-families/ must be git-ignored (public repo)"


@pytest.mark.parametrize("path", ["/w/samples/reference-families/x.rfa", "/w/plugin/lib/samples/x.rfa",
                                  "/w/any/reference-families/x.rfa", "/w/plugin/vendor/x.rfa",
                                  "/w/plugin/extracted/x.json"])
def test_the_plugin_deny_audit_refuses_quarantined_paths(path):
    import sync_plugin
    assert sync_plugin._denied(path), path


def test_the_deny_audit_still_lets_the_real_plugin_through():
    import sync_plugin
    assert not sync_plugin._denied("/w/plugin/skills/tekton-author/SKILL.md")
    assert sync_plugin.audit_deny() == []


def test_a_record_that_fails_to_decode_is_counted_not_skipped(families, monkeypatch):
    """Nothing guessed: when the decoder cannot read a record, the profile
    says so under ``undecoded`` instead of silently reporting fewer forms."""
    from rvt.families import FamilyIndex
    real = FamilyIndex.value

    def flaky(self, unit, eid, seq=102):
        v = real(self, unit, eid, seq)
        if isinstance(v, dict) and "m_cutting" in v:      # every form record
            raise ValueError("simulated decode failure")
        return v

    monkeypatch.setattr(FamilyIndex, "value", flaky)
    prof = FA.profile(families["lighting_control_panel"])
    assert prof["undecoded"]["value"] == {"ExtrusionElem": 7}
    assert prof["forms"]["value"]["total"] == 0
