"""Guard: the shipped plugin must never drift from the source of truth.

If this fails, run `python tools/sync_plugin.py` (which also re-validates the
manifest and rebuilds tekton-plugin.zip). See tools/sync_plugin.py for the map.
"""
import hashlib
import importlib
import json
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")


def _sync_plugin():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        return importlib.reload(importlib.import_module("sync_plugin"))
    finally:
        sys.path.pop(0)


def test_plugin_is_in_sync_with_source():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sync_plugin.py"),
                        "--check"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, (
        "plugin/ has drifted from source — run `python tools/sync_plugin.py`\n"
        + r.stdout + r.stderr)
    # the content audit is part of --check and prints its table (issue #193)
    assert "IDENTITY SCAN" in r.stdout and " 0 mismatch(es) against the allowlist" in r.stdout, r.stdout


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
    leaks = _sync_plugin().audit_deny(PLUGIN)
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


# ---------------------------------------------------------------------------
# identity scan (issue #193): the BYTES we ship carry no Autodesk employee
# username and no C:\Users\ path beyond the frozen, #19-tracked residue of the
# three genesis bases -- and that allowlist can only ever shrink.
# ---------------------------------------------------------------------------
def test_identity_scan_matches_allowlist():
    sp = _sync_plugin()
    res = sp.check_identity_strings(PLUGIN)          # + tekton-plugin.zip when built
    assert res["mismatch"] == [], (
        "shipped bytes and tools/plugin_identity_allowlist.json disagree -- UNEXPECTED: "
        "remove the string from the file (never extend the allowlist); VANISHED: delete "
        "the row so the allowlist shrinks with #19:\n"
        + "\n".join(sp.format_identity_report(res)))
    assert res["files"] >= 80 and len(res["hits"]) > 0
    # the allowlist itself: only the three bundled bases, every row owned by #19,
    # no duplicate keys (a duplicate would silently shadow a count)
    doc = json.load(open(sp.IDENTITY_ALLOWLIST, encoding="utf-8"))
    keys = [(e["file"], e["member"], e["token"]) for e in doc["entries"]]
    assert len(keys) == len(set(keys))
    assert {e["file"] for e in doc["entries"]} == {
        "assets/genesis/G_ABPD.rvt", "assets/genesis/G_ABPD_2025.rvt",
        "assets/genesis/G_ABPD_2024.rvt"}
    assert all(e["tracked_by"] == "#19" and e["count"] > 0 for e in doc["entries"])
    tokens = {e["token"] for e in doc["entries"]}
    assert tokens <= set(sp.identity_tokens()) and "hansonje" in tokens


def _leaky_plugin(root):
    """A tiny plugin tree + zip with one injected identity string per vector."""
    (root / "skills" / "x" / "references").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "skills" / "x" / "SKILL.md").write_text(
        "---\nname: x\ndescription: y\n---\nclean text\n", encoding="utf-8")
    # ASCII, mixed case (the scan is case-insensitive)
    (root / "skills" / "x" / "references" / "NOTES.md").write_text(
        "last saved by HansonJe on the sample\n", encoding="utf-8")
    # UTF-16LE, the way Revit stores strings
    (root / "assets" / "info.txt").write_bytes(
        b"\x01\x02" + "C:\\Users\\someone\\Documents\\a.rvt".encode("utf-16-le") + b"\x00")
    # a .rfa that is not a CFB container: falls back to a raw scan, still caught
    (root / "assets" / "fake.rfa").write_bytes(b"MZ..not-ole.." + b"okapaw" * 3)
    # .py is not a shipped-content extension: the engine's own deny constants live there
    (root / "deny.py").write_text("NAMES = {'hansonje', 'zhangg'}\n", encoding="utf-8")
    zpath = root.parent / "leaky-plugin.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.write(root / "assets" / "fake.rfa", "assets/fake.rfa")     # verbatim tree file
        zf.writestr("skills/x/references/NOTES.md", "mirror of the tree: hansonje\n")
        zf.writestr("examples/job.json", json.dumps({"path": "c:\\users\\me\\job"}))  # JSON-escaped
    return zpath


def test_identity_scan_catches_injected_strings(tmp_path):
    sp = _sync_plugin()
    root = tmp_path / "plugin"
    zpath = _leaky_plugin(root)
    res = sp.audit_identity_strings(str(root), zip_path=str(zpath))
    injected = {
        ("plugin", "skills/x/references/NOTES.md", "", "hansonje"): 1,
        ("plugin", "assets/info.txt", "", "C:\\Users\\"): 1,
        ("plugin", "assets/fake.rfa", sp.RAW_MEMBER, "okapaw"): 3,
        ("zip", "assets/fake.rfa", sp.RAW_MEMBER, "okapaw"): 3,
        ("zip", "skills/x/references/NOTES.md", "", "hansonje"): 1,
        ("zip", "examples/job.json", "", "C:\\Users\\"): 1,
    }
    assert res["hits"] == injected
    assert res["files"] == 4 and res["zip_members"] == 3      # deny.py not scanned

    # against the real allowlist: every injected hit is UNEXPECTED (tree AND zip),
    # every frozen base row is VANISHED once, against the tree (this tree ships
    # no bases) -- either kind fails --check
    chk = sp.check_identity_strings(str(root), zip_path=str(zpath))
    unexpected = [x for x in chk["mismatch"] if x[5] is None]
    vanished = [x for x in chk["mismatch"] if x[4] == 0]
    assert {x[:4] for x in unexpected} == set(injected)
    assert len(vanished) == len(sp.load_identity_allowlist()) and all(
        v[0] == "plugin" and v[1].startswith("assets/genesis/") for v in vanished)
    assert len(chk["mismatch"]) == len(unexpected) + len(vanished)
    report = "\n".join(sp.format_identity_report(chk))
    assert "UNEXPECTED skills/x/references/NOTES.md carries 'hansonje' x1" in report
    assert "UNEXPECTED zip:examples/job.json carries 'C:\\\\Users\\\\' x1" in report
    assert "VANISHED   assets/genesis/G_ABPD.rvt :: BasicFileInfo 'hansonje' x2" in report

    # an allowlist naming exactly the tree's hits passes; a stale count does not
    allow = tmp_path / "allow.json"
    entries = [{"file": f, "member": m, "token": t, "count": n, "tracked_by": "#19"}
               for (o, f, m, t), n in injected.items() if o == "plugin"]
    allow.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    chk = sp.check_identity_strings(str(root), zip_path=None, allowlist_path=str(allow))
    assert chk["mismatch"] == []
    entries[0]["count"] += 1
    allow.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    chk = sp.check_identity_strings(str(root), zip_path=None, allowlist_path=str(allow))
    assert [(x[4], x[5]) for x in chk["mismatch"]] == [(entries[0]["count"] - 1, entries[0]["count"])]

    # and the plugin's own validator runs the same scan: red on this tree, same wording
    r = subprocess.run([sys.executable, os.path.join(PLUGIN, "scripts", "validate_plugin.py"),
                        str(root)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 1, r.stdout
    assert ("identity scan: UNEXPECTED skills/x/references/NOTES.md carries 'hansonje' x1"
            in r.stdout), r.stdout
