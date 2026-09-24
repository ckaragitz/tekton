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

def _archetype_prompts():
    """Every archetype in the registry -- not a hand-kept list."""
    from rvt.famgen import archetypes as AR
    return {k: "a " + a.title.split(" - ")[0].lower() for k, a in AR.ARCHETYPES.items()}


PROMPTS = _archetype_prompts()

#: the catalog lane: families built from sourced manufacturer facts
CATALOG = {
    "panelboard": ["panelboard", "--types", "225,400"],
    "transformer": ["transformer"],
    "luminaire": ["luminaire"],
    "device": ["device"],
}


@pytest.fixture(scope="module")
def families(tmp_path_factory):
    from rvt.frontdoor import router as R
    from rvt.famgen import archetypes as AR
    out = {}
    for key, prompt in PROMPTS.items():
        assert AR.resolve_prompt(prompt).arch.key == key, (key, prompt)
        d = tmp_path_factory.mktemp(key)
        res = R.route({"prompt": prompt}, "rfa", out=str(d), quiet=True)
        assert res.ok, (key, res.status)
        out[key] = res.files["rfa"]
    for key, argv in CATALOG.items():
        d = tmp_path_factory.mktemp(key)
        path = str(d / f"{key}.rfa")
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), *argv,
                               "-o", path], capture_output=True, text=True, cwd=ROOT, timeout=300)
        assert proc.returncode == 0 and os.path.isfile(path), (key, proc.stdout[-400:], proc.stderr[-400:])
        out[key] = path
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


def _schema_ids_in(path):
    from rvt.families import FamilyIndex
    fi = FamilyIndex(path)
    ids = set()

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k == "m_typeId" and isinstance(x, str):
                    ids.add(x)
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for eid in fi.ids_of_class(0, "ParamElemFamily"):
        walk(fi.value(0, eid, 102))
    return ids


# ---------------------------------------------------------------------------
# 1. content-free
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(PROMPTS) + sorted(CATALOG))
def test_a_profile_never_repeats_the_familys_own_text(families, profiles, key):
    text = json.dumps(profiles[key])
    strings = _strings_in(families[key])
    assert strings, "the family carries no strings -- the check would be vacuous"
    ours = _keys(profiles[key], set())            # the words the profile is ALLOWED to use
    leaked = sorted(s for s in strings if s in text and s not in ours)
    assert not leaked, f"{key}: the profile repeats the family's text: {leaked[:5]}"


def _keys(v, out):
    if isinstance(v, dict):
        for k, x in v.items():
            out.add(k)
            _keys(x, out)
    return out


@pytest.mark.parametrize("key", sorted(PROMPTS) + sorted(CATALOG))
def test_every_key_is_from_our_vocabulary_or_a_schema_identifier(families, profiles, key):
    """Keys are this module's fixed VOCABULARY, a ParamDef class of the
    schema, a class name under `undecoded`, or the last token of a schema id
    the family itself carries -- never a word the family chose.  (Round 2: a
    caption like "Voltage" passed the old sanitiser as a group key.)"""
    from rvt import schema as S
    sch = S.load_schema()
    prof = profiles[key]
    tokens = {FA._group_key(x) for x in _schema_ids_in(families[key])} - {"other"}
    params = prof["parameters"]["value"]
    for k in params["by_storage"]:
        assert k == "other" or (k.startswith("ParamDef") and k in sch.by_name), k
    for k in list(params["by_group"]) + list(params["by_spec"]):
        assert k in ("other", "none") or k in tokens, k
    dynamic = set(params["by_storage"]) | set(params["by_group"]) | set(params["by_spec"]) \
        | set(prof["undecoded"]["value"])
    for k in _keys(prof, set()) - dynamic:
        assert k in FA.VOCABULARY, k


def test_a_caption_can_never_become_a_key():
    for text in ("Voltage", "Width", "Panel Name", "Eaton Pow-R-Line", "480Y/277"):
        assert FA._group_key(text) == "other", text


# ---------------------------------------------------------------------------
# 2. nothing guessed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(PROMPTS) + sorted(CATALOG))
def test_every_aspect_says_how_it_was_read_and_nothing_failed_to_decode(profiles, key):
    prof = profiles[key]
    assert {a["how"] for a in prof.values()} <= {"decoded", "inferred", "class-count", "not-yet-readable"}
    assert prof["undecoded"]["value"] == {}, prof["undecoded"]
    assert prof["visibility_parameter_bindings"]["how"] == "not-yet-readable"


def test_the_lighting_control_panel_is_pinned_aspect_by_aspect(profiles):
    """Pinned to what the #816 builder and our writer author: seven solid
    extrusions (back, four walls, door, latch), two named origin planes that
    are references, no subcategory / material / nested family, one type."""
    p = profiles["lighting_control_panel"]
    assert p["forms"]["value"] == {"by_kind": {"extrusion": 7}, "total": 7, "solids": 7, "voids": 0}
    assert p["reference_planes"]["value"] == {"total": 2, "named": 2, "define_origin": 2,
                                              "is_reference": 2, "strong": 0, "weak": 0}
    assert p["form_subcategories"]["value"] == {"forms_assigned": 0, "subcategories": 0}
    assert p["form_materials"]["value"] == {"forms_assigned": 0}
    assert p["nested_families"]["value"] == {"total": 0}
    assert p["dimensions"]["value"] == {"total": 0}
    assert p["dimension_constraints"]["value"] == {"eq_display_option": 0, "param_driven_segments": 0,
                                                   "driven_segments": 0, "anchored_refs": 0}
    assert p["dimension_constraints"]["how"] == "inferred"
    assert p["types"]["value"] == {"total": 1}
    params = p["parameters"]["value"]
    assert params["by_group"]["dimensions"] == 3 and params["by_spec"]["length"] >= 3
    assert p["view_specific_elements"]["how"] == "not-yet-readable"


# ---------------------------------------------------------------------------
# 3. the comparison
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(PROMPTS) + sorted(CATALOG))
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
    assert set(rep) == {"reference", "ours", "gaps", "undecoded_warning"}
    assert rep["undecoded_warning"] == {}
    junk = tmp_path / "junk.rfa"
    junk.write_bytes(b"not a family")
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "family_anatomy.py"),
                           "profile", str(junk)], capture_output=True, text=True)
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr and proc.stderr.count("\n") == 1, proc.stderr


# ---------------------------------------------------------------------------
# 4. the quarantine
# ---------------------------------------------------------------------------

def test_reference_families_are_git_ignored(tmp_path):
    """Checked with the repo's own .gitignore in a throwaway repository, so
    it also runs where the tree is an export without .git (session_ci.sh)."""
    import shutil
    shutil.copy(os.path.join(ROOT, ".gitignore"), tmp_path / ".gitignore")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    proc = subprocess.run(["git", "check-ignore", "-q", "samples/reference-families/any.rfa"],
                          cwd=tmp_path, capture_output=True)
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


def _patched_decode(monkeypatch, change):
    """Wrap FamilyIndex.decode; ``change(obj)`` may alter a COPY of a
    decoded form record -- the way the real decoder reports trouble is
    ``errors`` / ``clean``, never an exception."""
    import copy
    from rvt.families import FamilyIndex
    real = FamilyIndex.decode

    def fake(self, unit, eid, seq=102):
        o = real(self, unit, eid, seq)
        if o is not None and isinstance(o.value, dict) and "m_cutting" in o.value:
            o = copy.deepcopy(o)
            change(o)
        return o

    monkeypatch.setattr(FamilyIndex, "decode", fake)


def test_a_record_that_fails_to_decode_is_counted_not_skipped(families, monkeypatch):
    def fail(o):
        o.errors.append({"field": "m_cutting", "offset": 0, "error": "simulated"})
        o.value = {}
    _patched_decode(monkeypatch, fail)
    prof = FA.profile(families["lighting_control_panel"])
    assert prof["undecoded"]["value"] == {"ExtrusionElem": 7}
    assert prof["forms"]["value"]["total"] == 0


def test_compare_warns_when_a_side_did_not_fully_decode(families, monkeypatch, tmp_path, capsys):
    def fail(o):
        o.errors.append({"field": "x", "offset": 0, "error": "simulated"})
    _patched_decode(monkeypatch, fail)
    out = tmp_path / "c.json"
    assert FA.main(["compare", families["cable_tray"], families["lighting_control_panel"],
                    "--json", str(out)]) == 0
    assert "WARNING" in capsys.readouterr().out
    assert json.loads(out.read_text())["undecoded_warning"]


def test_a_void_is_read_from_the_forms_cutting_flag(families, monkeypatch):
    """Our writer authors no voids, so the reading is exercised on a record
    whose flag is set -- the field is GenSweep.m_cutting per the schema."""
    seen = []

    def one_void(o):
        if not seen:
            o.value["m_cutting"] = True
            seen.append(1)
    _patched_decode(monkeypatch, one_void)
    f = FA.profile(families["lighting_control_panel"])["forms"]["value"]
    assert (f["voids"], f["solids"], f["total"]) == (1, 6, 7)


@pytest.mark.parametrize("rel", ["plugin/assets/genesis/G_ABPD.rvt",
                                 # a project with SEVEN loaded families: the case where
                                 # "the first Family" is a random loaded one
                                 "tekton-eval-kit/TEST-KIT/04_electrical_room_equipment_families.rvt"])
def test_a_project_file_is_refused_not_profiled(rel):
    """A project carries loaded families; profiling 'the first Family' there
    reported a random loaded family as the file's anatomy."""
    rvt = os.path.join(ROOT, *rel.split("/"))
    with pytest.raises(FA.NotAFamily):
        FA.profile(rvt)
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "family_anatomy.py"),
                           "profile", rvt], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 1 and "NotAFamily" in proc.stderr and "Traceback" not in proc.stderr


def test_the_deny_audit_does_not_deny_a_clone_under_a_vendor_folder(monkeypatch):
    """Matched relative to the repo: a clone at /w/vendor/tekton must still
    build, while a samples/ path inside it is still refused."""
    import sync_plugin
    monkeypatch.setattr(sync_plugin, "ROOT", "/w/vendor/tekton")
    assert not sync_plugin._denied("/w/vendor/tekton/plugin/assets/genesis/G_ABPD.rvt")
    assert sync_plugin._denied("/w/vendor/tekton/plugin/lib/samples/x.rfa")
    assert sync_plugin._denied("/w/vendor/tekton/samples/reference-families/x.rfa")


def _patch_class(monkeypatch, cls_field, change):
    """Like _patched_decode, for records carrying ``cls_field``."""
    import copy
    from rvt.families import FamilyIndex
    real = FamilyIndex.decode

    def fake(self, unit, eid, seq=102):
        o = real(self, unit, eid, seq)
        if o is not None and isinstance(o.value, dict) and cls_field in o.value:
            o = copy.deepcopy(o)
            change(o.value)
        return o

    monkeypatch.setattr(FamilyIndex, "decode", fake)


def test_a_subcategory_is_a_category_under_the_familys_own(families, monkeypatch):
    """Our families carry no subcategory; one CategoryElem re-parented under
    the family's own category must count as exactly one."""
    from rvt.families import FamilyIndex, self_family_of_unit
    fam_cat = self_family_of_unit(FamilyIndex(families["lighting_control_panel"]), 0)["category"]
    done = []

    def reparent(v):
        if not done:
            v["m_pCategory"]["value"]["m_parentCategoryId"] = fam_cat
            done.append(1)
    _patch_class(monkeypatch, "m_pCategory", reparent)
    assert FA.profile(families["lighting_control_panel"])["form_subcategories"]["value"]["subcategories"] == 1


def test_a_plane_is_named_by_its_text_not_by_its_reference_setting(families, monkeypatch):
    """m_refName is the Is-Reference enum (Left = 0, Not a Reference = 12):
    a plane set to Left is still named and still a reference; a named plane
    set to Not a Reference is named but not a reference."""
    seen = []

    def edit(v):
        seen.append(1)
        v["m_refName"] = 0 if len(seen) == 1 else 12
    _patch_class(monkeypatch, "m_refName", edit)
    rp = FA.profile(families["lighting_control_panel"])["reference_planes"]["value"]
    assert (rp["named"], rp["is_reference"]) == (2, 1), rp


def test_a_plane_without_text_is_not_named(families, monkeypatch):
    def edit(v):
        v["m_text"] = ""
    _patch_class(monkeypatch, "m_refName", edit)
    rp = FA.profile(families["lighting_control_panel"])["reference_planes"]["value"]
    assert (rp["named"], rp["is_reference"]) == (0, 2), rp


def test_every_form_class_is_a_concrete_genSweep_subclass():
    """The form table names concrete classes -- SweepElem, not the GenSweep
    base, which no record ever carries -- and each one IS a GenSweep."""
    from rvt import schema as S
    sch = S.load_schema()
    assert "GenSweep" not in FA.FORM_CLASSES
    for cls in FA.FORM_CLASSES:
        c, chain = sch.by_name[cls], []
        while c is not None and len(chain) < 32:
            chain.append(c.name)
            c = sch.by_name.get(c.parent) if c.parent else None
        assert "GenSweep" in chain, (cls, chain)


@pytest.mark.parametrize("raw,want", [
    ("autodesk.parameter.group:dimensions-1.0.0", "dimensions"),
    ("autodesk.spec.aec:length-2.0.0", "length"),
    ("autodesk.parameter.group:Panel Name (Main)-1.0.0", "other"),
    ("Eaton Pow-R-Line", "other"),
    ("", "none"),
])
def test_a_key_built_from_file_data_can_never_carry_its_text(raw, want):
    assert FA._group_key(raw) == want


def test_a_relative_path_is_judged_as_is_whatever_the_current_directory(tmp_path, monkeypatch):
    """sync_plugin calls _denied(dst_rel) with a plugin-relative path; run
    from a directory under /vendor/ it must not deny the genesis asset."""
    import sync_plugin
    cwd = tmp_path / "vendor" / "work"
    cwd.mkdir(parents=True)
    monkeypatch.chdir(cwd)
    assert not sync_plugin._denied("assets/genesis/G_ABPD.rvt")
    assert sync_plugin._denied("lib/samples/x.rfa")


def test_the_tracked_eaton_family_is_pinned():
    """A stable tracked family: type-only parameters, and spec kinds told
    apart -- Text, Integer and length are not all 'other' (round 2)."""
    p = FA.profile(os.path.join(ROOT, "tekton-eval-kit", "TEST-KIT", "08_eaton_panelboard_family.rfa"))
    params = p["parameters"]["value"]
    assert (params["total"], params["instance"], params["type"]) == (14, 0, 14)
    assert params["by_spec"] == {"current": 2, "int64": 3, "length": 3, "number": 1,
                                 "potential": 1, "string": 4}
    assert p["types"]["value"] == {"total": 1}
    assert p["undecoded"]["value"] == {}


def test_the_two_type_catalog_panelboard(profiles):
    p = profiles["panelboard"]
    assert p["types"]["value"] == {"total": 2}
    params = p["parameters"]["value"]
    assert params["instance"] >= 1 and params["type"] > params["instance"]
    assert {"length", "current", "potential"} <= set(params["by_spec"])


@pytest.mark.parametrize("settings,want", [
    ((13, 13), (2, 0, 2)), ((14, 14), (0, 2, 2)), ((13, 14), (1, 1, 2)),
    ((12, 13), (1, 0, 1)), ((12, 12), (0, 0, 0))])
def test_strong_and_weak_references_are_told_apart(families, monkeypatch, settings, want):
    """The LCP's two planes re-set to each Is-Reference pairing; asymmetric
    pairs so a strong/weak swap cannot pass (round 2 mutant)."""
    seen = []

    def edit(v):
        v["m_refName"] = settings[len(seen) % 2]
        seen.append(1)
    _patch_class(monkeypatch, "m_refName", edit)
    rp = FA.profile(families["lighting_control_panel"])["reference_planes"]["value"]
    assert (rp["strong"], rp["weak"], rp["is_reference"]) == want, rp


@pytest.mark.parametrize("ptr_class", ["Lighting Control Panel", "ParamDefNotInTheSchema", ""])
def test_a_parameter_storage_class_is_named_only_when_the_schema_has_it(families, monkeypatch, ptr_class):
    """The storage key is a class name only if the file's own schema defines
    it as a ParamDef class; anything else -- a caption, an unknown name --
    counts as 'other' (round 2 mutant)."""
    def edit(v):
        v["m_pParamDef"] = dict(v.get("m_pParamDef") or {}, ptr_class=ptr_class)
    _patch_class(monkeypatch, "m_instanceParam", edit)
    params = FA.profile(families["lighting_control_panel"])["parameters"]["value"]
    assert params["by_storage"] == {"other": params["total"]}, params["by_storage"]


def test_a_form_with_its_own_visibility_is_counted(families, monkeypatch):
    seen = []

    def one_off(o):
        if not seen:
            o.value["m_famElemVisibility"] = {"m_flags": 1}
            seen.append(1)
    _patched_decode(monkeypatch, one_off)
    fv = FA.profile(families["lighting_control_panel"])["form_visibility"]["value"]
    assert fv == {"distinct_settings": 2, "forms_off_the_common_setting": 1}, fv


def test_an_undecodable_family_record_is_not_taken_for_the_self_family(monkeypatch):
    """A Family record that fails to decode used to read as a nil GUID --
    and a project whose Family records failed was profiled."""
    import copy
    from rvt.families import FamilyIndex
    real = FamilyIndex.decode

    def fake(self, unit, eid, seq=102):
        o = real(self, unit, eid, seq)
        if o is not None and isinstance(o.value, dict) and "m_famDocGUID" in o.value:
            o = copy.deepcopy(o)
            o.errors.append({"field": "m_famDocGUID", "offset": 0, "error": "simulated"})
            o.value = {}
        return o

    monkeypatch.setattr(FamilyIndex, "decode", fake)
    with pytest.raises(FA.NotAFamily):
        FA.profile(os.path.join(ROOT, "tekton-eval-kit", "TEST-KIT",
                                "04_electrical_room_equipment_families.rvt"))
