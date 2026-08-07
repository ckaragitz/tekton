"""Guard: the shipped plugin must never drift from the source of truth.

If this fails, run `python tools/sync_plugin.py` (which also re-validates the
manifest and rebuilds tekton-plugin.zip). See tools/sync_plugin.py for the map.
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")


def test_plugin_is_in_sync_with_source():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sync_plugin.py"),
                        "--check"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, (
        "plugin/ has drifted from source — run `python tools/sync_plugin.py`\n"
        + r.stdout + r.stderr)


def test_plugin_manifest_layout():
    # per the Claude Code plugin spec: manifest lives ONLY in .claude-plugin/,
    # component dirs live at the plugin root
    p = PLUGIN
    assert os.path.isfile(os.path.join(p, ".claude-plugin", "plugin.json"))
    assert os.path.isfile(os.path.join(p, ".claude-plugin", "marketplace.json"))
    for d in ("skills", "agents", "commands"):
        assert os.path.isdir(os.path.join(p, d)), f"{d}/ must be at the plugin root"
        assert not os.path.exists(os.path.join(p, ".claude-plugin", d)), \
            f"{d}/ must NOT be inside .claude-plugin/"


# ---------------------------------------------------------------------------
# tekton packaging: the three skills, their bundled scripts / references,
# the certified genesis-base ASSET, and the deny-list.
# ---------------------------------------------------------------------------
TEKTON_SKILLS = {
    "tekton-author": {
        "scripts": ("frontdoor.py", "rvt_job.py", "ifc_intent.py", "ifc_to_spec.py",
                    "spec_to_rvt.py", "seed_audit.py", "panel_schedule.py",
                    "genesis_compose.py", "probe_batch.py", "rvt_validate.py",
                    "_bootstrap.py"),
        "references": ("TAGGING-CONTRACT.md", "CATALOG-FACTS.md", "PROMPT-TO-IFC.md",
                       "GENESIS-BASE.md", "CRUD-COVERAGE.md"),
        "examples": ("electrical-room-2500a.ifc", "chicago-plenum-downlight.ifc",
                     "room-spec.json", "electrical-job.json"),
    },
    "tekton-edit": {
        "scripts": ("rvt_edit.py", "rvt_validate.py", "rvt_job.py", "_bootstrap.py"),
        "references": (),
        "examples": (),
    },
    "tekton-inspect": {
        "scripts": ("rvt_validate.py", "render_inspect.py", "seed_audit.py",
                    "spec_to_rvt.py", "panel_schedule.py", "_bootstrap.py"),
        "references": (),
        "examples": ("room-spec.json", "electrical-job.json"),
    },
}


def test_tekton_skills_present_with_contents():
    for skill, want in TEKTON_SKILLS.items():
        sd = os.path.join(PLUGIN, "skills", skill)
        assert os.path.isfile(os.path.join(sd, "SKILL.md")), f"{skill}: SKILL.md missing"
        text = open(os.path.join(sd, "SKILL.md"), encoding="utf-8").read()
        assert text.startswith("---") and f"name: {skill}" in text.split("---", 2)[1], \
            f"{skill}: frontmatter name mismatch"
        for sub, files in want.items():
            for f in files:
                p = os.path.join(sd, sub, f)
                assert os.path.isfile(p), f"{skill}: {sub}/{f} missing (run tools/sync_plugin.py)"


def test_synced_scripts_are_byte_identical_to_source():
    """Every engine script bundled into a tekton skill (or the lib/tools shim)
    is a byte-identical copy of tools/<name>.py — skills never fork the engine."""
    def h(p):
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    checked = 0
    for skill, want in TEKTON_SKILLS.items():
        for f in want["scripts"]:
            if f.startswith("_") or f == "render_inspect.py":     # skill-native helpers
                continue
            src = os.path.join(ROOT, "tools", f)
            if not os.path.isfile(src):        # optional in-flight source (e.g. frontdoor.py)
                continue
            dst = os.path.join(PLUGIN, "skills", skill, "scripts", f)
            assert h(src) == h(dst), f"{skill}/scripts/{f} differs from tools/{f}"
            checked += 1
    assert checked >= 8
    shim = os.path.join(PLUGIN, "lib", "tools")
    if os.path.isdir(shim):
        for f in os.listdir(shim):
            if f.endswith(".py"):
                assert h(os.path.join(ROOT, "tools", f)) == h(os.path.join(shim, f)), \
                    f"lib/tools/{f} differs from tools/{f}"


def test_genesis_base_asset_present_and_pinned():
    """The ONLY .rvt the plugin ships is the certified genesis base, byte-
    identical to its source and (when the front door ships its pin) equal to
    the pinned sha256 — the plugin never bundles a base the front door refuses."""
    asset = os.path.join(PLUGIN, "assets", "genesis", "G_ABPD.rvt")
    src = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
    assert os.path.isfile(asset), "assets/genesis/G_ABPD.rvt missing (run tools/sync_plugin.py)"
    assert os.path.isfile(os.path.join(PLUGIN, "assets", "genesis", "G_ABPD.compose.json"))
    got = hashlib.sha256(open(asset, "rb").read()).hexdigest()
    if os.path.isfile(src):
        assert got == hashlib.sha256(open(src, "rb").read()).hexdigest(), \
            "genesis base asset differs from its source file"
    pin = os.path.join(ROOT, "src", "rvt", "frontdoor", "assets", "genesis_base.json")
    if os.path.isfile(pin):
        want = json.load(open(pin))["default"]["sha256"].lower()
        assert got == want, "genesis base asset does not match rvt.frontdoor's pin"


def test_no_denylisted_data_in_plugin():
    """Quarantined / third-party-extracted reference data must never enter
    the shipping tree (the sync's own audit, re-asserted here)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import importlib
        sp = importlib.import_module("sync_plugin")
        importlib.reload(sp)
        leaks = sp.audit_deny(PLUGIN)
    finally:
        sys.path.pop(0)
    assert leaks == [], f"deny-listed files inside plugin/: {leaks[:5]}"
    # and the plugin ships exactly the sanctioned .rvt asset(s), nothing else:
    # the default genesis base plus every CERTIFIED per-release slot of the
    # registry (genesis_base.json "releases" -- certified + sha256-pinned;
    # the G25-5 flip bundles G_ABPD_2025.rvt beside G_ABPD.rvt, so the
    # allow-list is registry-driven rather than a stale literal)
    rvts = []
    for base, _dirs, files in os.walk(PLUGIN):
        for f in files:
            if f.lower().endswith((".rvt", ".rfa")):
                rvts.append(os.path.relpath(os.path.join(base, f), PLUGIN))
    reg = json.load(open(os.path.join(
        ROOT, "src", "rvt", "frontdoor", "assets", "genesis_base.json")))
    allowed = {os.path.join("assets", "genesis",
                            os.path.basename(reg["default"]["relpath"]))}
    for year, slot in (reg.get("releases") or {}).items():
        if not isinstance(slot, dict):
            continue
        if slot.get("status") == "certified" and slot.get("sha256") \
                and slot.get("relpath"):
            allowed.add(os.path.join("assets", "genesis",
                                     os.path.basename(slot["relpath"])))
    # (large example proof .rvt files may exist on disk under examples/ but
    #  are excluded from tekton-plugin.zip; the asset dir must hold only ours)
    in_assets = {r for r in rvts if r.startswith("assets" + os.sep)}
    assert in_assets <= allowed, f"unexpected binaries in assets/: {sorted(in_assets - allowed)}"
    assert os.path.join("assets", "genesis", "G_ABPD.rvt") in in_assets


def test_plugin_manifest_says_tekton():
    d = json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))
    assert d["name"] == "tekton", "manifest name stays rev-revit until the rename sweep"
    assert "tekton" in d.get("description", "").lower(), "plugin description must name tekton"
