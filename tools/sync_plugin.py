#!/usr/bin/env python3
"""sync_plugin.py — rebuild the shippable tekton plugin from source. ONE command,
run after ANY change to the engine, generators, skills, examples or assets:

    python tools/sync_plugin.py            # sync + validate + rebuild the zip
    python tools/sync_plugin.py --check    # exit non-zero if the plugin has drifted

(The product's display name is TEKTON; the plugin folder, manifest name and
python packages keep the working name ``tekton`` / ``rvt`` until the
scripted trademark-clearance rename sweep — see the plugin README.)

The plugin (plugin/) BUNDLES copies of source-of-truth files; this script is
the only sanctioned way to update those copies, so the plugin can never
silently fall behind the framework:

    src/rvt/**                     -> plugin/lib/src/rvt/**       (the engine; incl.
                                      rvt.render / rvt.ifc / rvt.genesis /
                                      rvt.frontdoor when present, reduce_law,
                                      regadd, regdiff, objlint, residue modules)
    skills/tekton-ifc/**         -> plugin/skills/tekton-ifc/**   (IFC skill)
    tools/<engine scripts>         -> plugin/skills/<skill>/scripts/  (see mappings())
    experiments/genesis/.../G_ABPD.rvt (+ manifest) -> plugin/assets/genesis/ (CERTIFIED
                                      genesis base ASSET; the ONLY .rvt shipped,
                                      opt-in by exact path, sha256-verified
                                      against the front door's pin)
    inputs/ifc/*.ifc               -> plugin/skills/tekton-author/examples/
    spec/building.schema.json      -> plugin/skills/tekton-native/examples/
    usecases/<job>/*  (non-binary) -> plugin/examples/<job>/*

Guards enforced on every run (and by tests/test_plugin_sync.py):
  * DENY list  — quarantined / third-party-extracted reference data NEVER
    enters the plugin tree, and the whole tree is audited for leaks (an ASSET
    is refused if its path matches the deny list).
  * IDENTITY scan — the BYTES we ship (plugin/**/*.{rvt,rfa,json,md,txt,ifc,
    tksc} and every such member of the built zip; .rvt/.rfa opened and every
    stream inflated) are searched, ASCII + UTF-16LE, case-insensitively, for
    Autodesk employee usernames and `C:\\Users\\` paths. The only tolerated
    hits are the ones measured in the three genesis bases and frozen in
    tools/plugin_identity_allowlist.json (tracked by #19): a hit outside the
    allowlist fails the build, and so does an allowlisted hit that vanished
    (the allowlist must shrink with the scrub, never lag behind it).
  * ASSET pin  — a bundled .rvt asset must equal its source byte-for-byte
    and, when rvt.frontdoor ships its genesis-base pin, must match that pin's
    sha256 (the plugin can never ship a base the front door would refuse).
  * OPTIONAL sources — a script another stream is still building (e.g. the
    unified front door) is copied when present and skipped WITHOUT drift
    otherwise, so --check stays green before, during and after its landing.

Then: `claude plugin validate plugin/` and rebuild tekton-plugin.zip (plugin
contents at the archive root, loadable via `claude --plugin-dir tekton-plugin.zip`).
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
ZIP = os.path.join(ROOT, "tekton-plugin.zip")
IDENTITY_ALLOWLIST = os.path.join(ROOT, "tools", "plugin_identity_allowlist.json")

SKIP_DIR_NAMES = {"__pycache__", "node_modules", ".pytest_cache", ".DS_Store"}
BINARY_EXT = {".rvt", ".rfa", ".mp4", ".mov"}          # never bundled by tree/file syncs
EXAMPLE_KEEP_EXT = {".ifc", ".json", ".md", ".txt", ".js"}
# Never ship third-party extracted reference data (see experiments/genesis/reference/README.md)
DENY_PATH_PARTS = ("autodesk-extracted", "quarantine", "/reference/", os.sep + "reference" + os.sep)

# ---------------------------------------------------------------------------
# the certified genesis base ASSET (the ONLY .rvt the plugin ships) — an
# opt-in exact path, exempt from BINARY_EXT, sha256-verified.
# ---------------------------------------------------------------------------
GENESIS_BASE_SRC = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
GENESIS_MANIFEST_SRC = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                                    "G_ABPD.manifest.json")
GENESIS_BASE_2025_SRC = os.path.join(ROOT, "experiments", "genesis",
                                     "subst_k4_2025", "compose", "G_ABPD_2025.rvt")
GENESIS_MANIFEST_2025_SRC = os.path.join(ROOT, "experiments", "genesis",
                                         "subst_k4_2025", "compose",
                                         "G_ABPD_2025.manifest.json")
GENESIS_BASE_2024_SRC = os.path.join(ROOT, "experiments", "genesis",
                                     "subst_k4_2024", "compose", "G_ABPD_2024.rvt")
GENESIS_MANIFEST_2024_SRC = os.path.join(ROOT, "experiments", "genesis",
                                         "subst_k4_2024", "compose",
                                         "G_ABPD_2024.manifest.json")
GENESIS_DST_DIR = "assets/genesis"
# the front door's pin (its resolver refuses a base whose sha256 != the pin)
FRONTDOOR_PIN = os.path.join(ROOT, "src", "rvt", "frontdoor", "assets", "genesis_base.json")


def _hash(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _denied(path: str) -> bool:
    rel_full = path.replace("\\", "/").lower()
    return any(part in rel_full for part in DENY_PATH_PARTS)


def _walk(src_dir: str, keep_ext=None):
    for base, dirs, files in os.walk(src_dir):
        # never mirror packaging junk (pip metadata / build dirs / node modules / caches)
        dirs[:] = [d for d in dirs if not (d.endswith(".egg-info") or d in ("build", "__pycache__", "node_modules", ".pytest_cache"))]
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
        for f in files:
            if f in SKIP_DIR_NAMES or f.endswith((".pyc",)):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in BINARY_EXT:
                continue
            if keep_ext is not None and ext not in keep_ext:
                continue
            if _denied(os.path.join(base, f)):
                continue
            yield os.path.relpath(os.path.join(base, f), src_dir)


# ---------------------------------------------------------------------------
# the mapping tables
# ---------------------------------------------------------------------------
def _tool(name: str) -> str:
    return os.path.join(ROOT, "tools", name)


# tekton-author (THE FRONT DOOR, prompt / IFC / .rvt in -> gated .rvt out):
# every engine script the front door composes sits SIDE BY SIDE with it —
# rvt_job.py / seed_audit.py load their siblings by path from their own dir.
AUTHOR_SCRIPTS = ("frontdoor.py",            # OPTIONAL: the unified router (frontdoor stream)
                  "rvt_job.py", "spec_to_rvt.py", "ifc_to_spec.py", "ifc_intent.py",
                  "seed_audit.py", "panel_schedule.py", "genesis_compose.py",
                  "probe_batch.py", "rvt_validate.py")
# tekton-edit (manipulate an existing .rvt) — rvt_job.py for the batch/ops door
EDIT_SCRIPTS = ("rvt_edit.py", "rvt_validate.py", "rvt_job.py")
# tekton-inspect (validate / seed audit / schedules / LOAD-vs-RENDER)
INSPECT_SCRIPTS = ("rvt_validate.py", "seed_audit.py", "spec_to_rvt.py", "panel_schedule.py")
# scripts another stream is still building: copied when present, never drift
OPTIONAL_SOURCES = {_tool("frontdoor.py")}
# THE ENGINE-SIDE TOOLS SHIM: rvt.frontdoor.build/.edit locate the reused
# build code at `<repo_root>/tools/<name>.py`; with the bundled-source
# install repo_root() resolves to <plugin-root>/lib (its src/rvt marker), so
# the same scripts must ALSO sit at plugin/lib/tools/. Remove this shim once
# the front door looks beside the running script (docs/inbox/plugin-packaging.md).
LIB_TOOLS_SHIM = ("frontdoor.py", "ifc_intent.py", "rvt_job.py", "probe_batch.py",
                  "spec_to_rvt.py", "ifc_to_spec.py", "seed_audit.py",
                  "panel_schedule.py", "genesis_compose.py", "rvt_validate.py",
                  "rvt_edit.py",
                  # loaded by path from rvt.famgen.famdoc_adoc._ga(): the
                  # audited ADocument purge machinery + its reducer import.
                  # OUR OWN engine code -- without them stage F dies in the
                  # field with FileNotFoundError (docs/inbox/standalone.md par.1)
                  "genesis_assemble.py", "rvt_reduce.py")


# (source, destination-inside-plugin, keep_ext filter, mirror-deletes?)
def mappings():
    m = [
        (os.path.join(ROOT, "src", "rvt"), "lib/src/rvt", None, True),
        (os.path.join(ROOT, "skills", "tekton-ifc"), "skills/tekton-ifc", None, True),
    ]
    files = [
        (_tool("spec_to_rvt.py"), "skills/tekton-native/scripts/spec_to_rvt.py"),
        (_tool("ifc_to_spec.py"), "skills/tekton-native/scripts/ifc_to_spec.py"),
        (_tool("rvt_validate.py"), "skills/tekton-native/scripts/rvt_validate.py"),
        (_tool("rvt_edit.py"), "skills/tekton-native/scripts/rvt_edit.py"),
        (_tool("seed_audit.py"), "skills/tekton-native/scripts/seed_audit.py"),
        (_tool("panel_schedule.py"), "skills/tekton-native/scripts/panel_schedule.py"),
        # rvt.frontdoor's --rvt route imports the job runner from HERE when
        # RVT_PLUGIN_ROOT is set (its documented plugin lookup path):
        (_tool("rvt_job.py"), "skills/tekton-native/scripts/rvt_job.py"),
        (os.path.join(ROOT, "spec", "building.schema.json"), "skills/tekton-native/examples/building.schema.json"),
        (os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room", "room-spec.json"),
         "skills/tekton-native/examples/room-spec.json"),
    ]
    # --- tekton skills: colocate the engine scripts beside each skill --------
    for s in AUTHOR_SCRIPTS:
        files.append((_tool(s), f"skills/tekton-author/scripts/{s}"))
    for s in EDIT_SCRIPTS:
        files.append((_tool(s), f"skills/tekton-edit/scripts/{s}"))
    for s in INSPECT_SCRIPTS:
        files.append((_tool(s), f"skills/tekton-inspect/scripts/{s}"))
    for s in LIB_TOOLS_SHIM:
        files.append((_tool(s), f"lib/tools/{s}"))
    # --- worked-example inputs for the flagship skill (OUR IFC authoring) ----
    for ifc in ("electrical-room-2500a.ifc", "chicago-plenum-downlight.ifc"):
        files.append((os.path.join(ROOT, "inputs", "ifc", ifc),
                      f"skills/tekton-author/examples/{ifc}"))
    files.append((os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room", "room-spec.json"),
                  "skills/tekton-author/examples/room-spec.json"))
    files.append((os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room", "electrical-job.json"),
                  "skills/tekton-author/examples/electrical-job.json"))
    # tekton-inspect worked inputs (seed audit + panel schedules)
    for f in ("room-spec.json", "electrical-job.json"):
        files.append((os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room", f),
                      f"skills/tekton-inspect/examples/{f}"))
    for job in ("chicago-plenum-electrical-room", "eaton-panelboard"):
        sd = os.path.join(ROOT, "usecases", job)
        if os.path.isdir(sd):
            m.append((sd, f"examples/{job}", EXAMPLE_KEEP_EXT, False))
    return m, files


def asset_mappings():
    """Binary/opt-in ASSETS: (source, destination) — exempt from BINARY_EXT,
    still DENY-audited, byte-verified. Missing manifest is tolerated (the .rvt
    is the load-bearing artefact)."""
    return [
        (GENESIS_BASE_SRC, f"{GENESIS_DST_DIR}/G_ABPD.rvt", True),
        (GENESIS_MANIFEST_SRC, f"{GENESIS_DST_DIR}/G_ABPD.compose.json", False),
    (GENESIS_BASE_2025_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2025.rvt", True),
    (GENESIS_MANIFEST_2025_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2025.compose.json", False),
    (GENESIS_BASE_2024_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2024.rvt", True),
    (GENESIS_MANIFEST_2024_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2024.compose.json", False),
    ]


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------
def sync(check_only: bool = False) -> list[str]:
    """Copy source-of-truth into the plugin. Returns the list of drift paths."""
    drift: list[str] = []
    dir_maps, file_maps = mappings()
    for src_dir, dst_rel, keep, mirror in dir_maps:
        dst_dir = os.path.join(PLUGIN, dst_rel)
        for rel in _walk(src_dir, keep):
            s, d = os.path.join(src_dir, rel), os.path.join(dst_dir, rel)
            if not (os.path.exists(d) and filecmp.cmp(s, d, shallow=False)):
                drift.append(os.path.join(dst_rel, rel))
                if not check_only:
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)
        if mirror and not check_only and os.path.isdir(dst_dir):
            # remove files that no longer exist in the source
            for rel in _walk(dst_dir, None):
                if not os.path.exists(os.path.join(src_dir, rel)):
                    os.remove(os.path.join(dst_dir, rel))
    for s, dst_rel in file_maps:
        d = os.path.join(PLUGIN, dst_rel)
        if not os.path.exists(s):
            if s in OPTIONAL_SOURCES:
                # another stream's in-flight deliverable: skip WITHOUT drift
                if not check_only:
                    print(f"  (optional source not built yet, skipped: "
                          f"{os.path.relpath(s, ROOT)})")
                continue
            print(f"  WARNING missing source (skipped): {os.path.relpath(s, ROOT)}")
            continue
        if not (os.path.exists(d) and filecmp.cmp(s, d, shallow=False)):
            drift.append(dst_rel)
            if not check_only:
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
    # --- marketplace convenience copy (must stay identical by construction:
    #     plugin/marketplace.json == plugin/.claude-plugin/marketplace.json) ---
    m_src = os.path.join(PLUGIN, ".claude-plugin", "marketplace.json")
    m_dst = os.path.join(PLUGIN, "marketplace.json")
    if os.path.exists(m_src) and not (os.path.exists(m_dst) and filecmp.cmp(m_src, m_dst, shallow=False)):
        drift.append("marketplace.json")
        if not check_only:
            shutil.copy2(m_src, m_dst)
    # --- assets (binary, opt-in, verified) --------------------------------
    for s, dst_rel, required in asset_mappings():
        d = os.path.join(PLUGIN, dst_rel)
        if _denied(s) or _denied(dst_rel):
            raise SystemExit(f"REFUSING asset from a denied path: {s} -> {dst_rel}")
        if not os.path.exists(s):
            if required:
                print(f"  WARNING required asset source missing: {os.path.relpath(s, ROOT)}")
            continue
        if not (os.path.exists(d) and _hash(s) == _hash(d)):
            drift.append(dst_rel)
            if not check_only:
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
    return drift


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------
def audit_deny(root: str = PLUGIN) -> list[str]:
    """Every file under the plugin tree; return any that match the DENY list
    (quarantined third-party data). MUST be empty."""
    leaks = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
        for f in files:
            p = os.path.join(base, f)
            if _denied(p):
                leaks.append(os.path.relpath(p, root))
    return leaks


def verify_assets() -> list[str]:
    """Bundled assets equal their source byte-for-byte; the genesis base
    matches the front door's pin when that pin ships. Returns problems."""
    problems: list[str] = []
    for s, dst_rel, required in asset_mappings():
        d = os.path.join(PLUGIN, dst_rel)
        if not os.path.exists(d):
            if required:
                problems.append(f"missing asset: {dst_rel}")
            continue
        if os.path.exists(s) and _hash(s) != _hash(d):
            problems.append(f"asset differs from source: {dst_rel}")
    # cross-check the shipped genesis base against the front door's pin
    base_dst = os.path.join(PLUGIN, GENESIS_DST_DIR, "G_ABPD.rvt")
    if os.path.exists(base_dst) and os.path.exists(FRONTDOOR_PIN):
        try:
            with open(FRONTDOOR_PIN) as fh:
                pin = json.load(fh)
            want = str(pin["default"]["sha256"]).lower()
            got = _hash(base_dst)
            if got != want:
                problems.append(
                    f"genesis base asset sha256 {got[:16]}.. != rvt.frontdoor pin "
                    f"{want[:16]}.. — the front door would REFUSE the bundled base")
        except (KeyError, ValueError, OSError) as e:      # pragma: no cover - malformed pin
            problems.append(f"cannot read frontdoor pin {FRONTDOOR_PIN}: {e}")
    return problems


# ---------------------------------------------------------------------------
# identity strings — a CONTENT audit of the bytes we ship (issue #193)
# ---------------------------------------------------------------------------
# The deny-audit above is path-based; this one reads the bytes. Tokens: the
# Autodesk employee usernames rvt.provenance already refuses in a generated
# file, plus a Windows profile path prefix. Both are searched ASCII and
# UTF-16LE (the interleaved-NUL encoding Revit stores strings in), case-
# insensitively, in one regex pass over each file's lowered bytes.
IDENTITY_SCAN_EXT = {".rvt", ".rfa", ".json", ".md", ".txt", ".ifc", ".tksc"}
CONTAINER_EXT = {".rvt", ".rfa"}
USER_PROFILE_TOKEN = "C:\\Users\\"
RAW_MEMBER = "<raw>"            # member label for a container we could not open


def _engine():
    """(tokens, open_rvt) from OUR engine copy under src/. Imported up front so a
    missing `olefile` fails loudly instead of degrading containers to a raw
    skim that sees nothing inside their gzip streams."""
    src = os.path.join(ROOT, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from rvt.container import open_rvt
    from rvt.provenance import AUTODESK_EMPLOYEE_USERNAMES
    return sorted(AUTODESK_EMPLOYEE_USERNAMES) + [USER_PROFILE_TOKEN], open_rvt


def _identity_matcher(tokens: list[str]):
    """-> scan(data) -> Counter{token: hits}, ASCII + UTF-16LE, case-insensitive;
    a backslashed token also matches its JSON/markdown-escaped spelling (C:\\\\Users\\\\)."""
    back: dict[bytes, str] = {}
    for tok in tokens:
        for spelling in {tok.lower(), tok.lower().replace("\\", "\\\\")}:
            for enc in ("ascii", "utf-16-le"):
                back[spelling.encode(enc)] = tok
    rx = re.compile(b"|".join(re.escape(b) for b in sorted(back, key=len, reverse=True)))

    def scan(data: bytes) -> Counter:
        return Counter(back[m] for m in rx.findall(data.lower()))
    return scan


def _scan_container(path: str, scan, open_rvt) -> dict[str, Counter]:
    """Per-stream hits of a .rvt/.rfa: each stream's de-paged bytes plus every
    gzip member inflated (what Revit reads, not the compressed envelope)."""
    out: dict[str, Counter] = {}
    with open_rvt(path) as doc:
        for s in doc.streams():
            hits = scan(doc.logical(s.name))
            try:
                hits += scan(doc.concat(s.name))
            except Exception:                       # a member we cannot inflate:
                pass                                # its envelope was scanned above
            if hits:
                out[s.name] = hits
    return out


def _scan_blob(name: str, data: bytes, scan, open_rvt, path: str | None = None
               ) -> dict[str, Counter]:
    """{member: Counter} for one shipped file. Containers are walked stream by
    stream; anything else (or a container that will not open) is one blob."""
    if os.path.splitext(name)[1].lower() in CONTAINER_EXT:
        try:
            with tempfile.TemporaryDirectory() as td:
                if path is None:                    # zip member: olefile wants a path
                    path = os.path.join(td, os.path.basename(name))
                    with open(path, "wb") as fh:
                        fh.write(data)
                return _scan_container(path, scan, open_rvt)
        except Exception:
            hits = scan(data)
            return {RAW_MEMBER: hits} if hits else {}
    hits = scan(data)
    return {"": hits} if hits else {}


def audit_identity_strings(root: str = PLUGIN, zip_path: str | None = ZIP) -> dict:
    """Scan every IDENTITY_SCAN_EXT file under ``root`` and (when it exists)
    every such member of ``zip_path``. Returns
    {"hits": [(origin, file, member, token, count)], "files": n, "zip_members": n,
     "seconds": t} with origin in {"plugin", "zip"}; byte-identical blobs are
    scanned once (the zip normally repeats the tree verbatim)."""
    t0 = time.perf_counter()
    tokens, open_rvt = _engine()
    scan = _identity_matcher(tokens)
    cache: dict[str, dict[str, Counter]] = {}           # sha256 -> {member: Counter}
    hits: list[tuple[str, str, str, str, int]] = []
    counts = {"plugin": 0, "zip": 0}

    def record(origin: str, rel: str, data: bytes, path: str | None = None) -> None:
        key = hashlib.sha256(data).hexdigest()
        if key not in cache:
            cache[key] = _scan_blob(rel, data, scan, open_rvt, path=path)
        for member, cnt in cache[key].items():
            for tok, n in cnt.items():
                hits.append((origin, rel, member, tok, n))
        counts[origin] += 1

    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIR_NAMES)
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() not in IDENTITY_SCAN_EXT:
                continue
            p = os.path.join(base, f)
            with open(p, "rb") as fh:
                record("plugin", os.path.relpath(p, root).replace(os.sep, "/"), fh.read(), p)
    if zip_path and os.path.isfile(zip_path):
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                name = info.filename
                if info.is_dir() or os.path.splitext(name)[1].lower() not in IDENTITY_SCAN_EXT:
                    continue
                record("zip", name[2:] if name.startswith("./") else name, zf.read(info))
    return {"hits": sorted(hits), "files": counts["plugin"], "zip_members": counts["zip"],
            "seconds": time.perf_counter() - t0}


def load_identity_allowlist(path: str = IDENTITY_ALLOWLIST) -> dict[tuple[str, str, str], int]:
    """{(file, member, token): count} — the frozen, #19-tracked leak set."""
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    out: dict[tuple[str, str, str], int] = {}
    for e in doc["entries"]:
        out[(e["file"], e.get("member", ""), e["token"])] = int(e["count"])
    return out


def check_identity_strings(root: str = PLUGIN, zip_path: str | None = ZIP,
                           allowlist_path: str = IDENTITY_ALLOWLIST) -> dict:
    """Run the scan and diff it against the allowlist, per origin. Adds
    "unexpected" (hit not allowlisted, or count differs) and "vanished"
    (allowlisted, no longer hit) — both must be empty."""
    res = audit_identity_strings(root, zip_path)
    allow = load_identity_allowlist(allowlist_path)
    origins = ["plugin"] + (["zip"] if res["zip_members"] else [])
    got = {(o, f, m, t): n for o, f, m, t, n in res["hits"]}
    unexpected, vanished = [], []
    for (o, f, m, t), n in sorted(got.items()):
        want = allow.get((f, m, t))
        if want != n:
            unexpected.append((o, f, m, t, n, want))
    for o in origins:
        for (f, m, t), want in sorted(allow.items()):
            if (o, f, m, t) not in got:
                vanished.append((o, f, m, t, want))
    res.update(unexpected=unexpected, vanished=vanished, allowlisted=len(got) - len(unexpected),
               allowlist=os.path.relpath(allowlist_path, ROOT))
    return res


def format_identity_report(res: dict) -> list[str]:
    """The table --check prints: one row per (origin, file, member)."""
    lines = [f"IDENTITY SCAN (Autodesk usernames + {USER_PROFILE_TOKEN} in shipped bytes; "
             f"allowlist {res['allowlist']}, tracked by #19):"]
    rows: dict[tuple[str, str, str], list[str]] = {}
    for o, f, m, t, n in res["hits"]:
        rows.setdefault((o, f, m), []).append(f"{t}={n}")
    bad = {(o, f, m) for o, f, m, _t, _n, _w in res["unexpected"]}
    for (o, f, m), toks in rows.items():
        where = ("zip:" if o == "zip" else "") + f + (f" :: {m}" if m else "")
        flag = "UNEXPECTED " if (o, f, m) in bad else "allowlisted"
        lines.append(f"  {flag} {where:<66} {' '.join(toks)}")
    for o, f, m, t, n, want in res["unexpected"]:
        exp = "not allowlisted" if want is None else f"allowlist says {want}"
        lines.append(f"  UNEXPECTED {o}:{f}{' :: ' + m if m else ''} {t}={n} ({exp})")
    for o, f, m, t, want in res["vanished"]:
        lines.append(f"  VANISHED   {o}:{f}{' :: ' + m if m else ''} {t}={want} "
                     f"— gone from the bytes: delete it from {res['allowlist']}")
    lines.append(f"  {res['files']} file(s) + {res['zip_members']} zip member(s) scanned in "
                 f"{res['seconds']:.2f} s: {res['allowlisted']} allowlisted hit(s), "
                 f"{len(res['unexpected'])} unexpected, {len(res['vanished'])} vanished")
    return lines


# ---------------------------------------------------------------------------
# zip + validate
# ---------------------------------------------------------------------------
def rebuild_zip() -> int:
    if os.path.exists(ZIP):
        os.remove(ZIP)
    # plugin contents at the archive root; example/proof .rvt outputs are
    # excluded (they are large research proofs), then the certified genesis
    # base ASSETS are added back explicitly.
    subprocess.check_call(
        ["zip", "-qr", ZIP, ".", "-x", "*/node_modules/*", "-x", "*/__pycache__/*",
         "-x", "*.rvt", "-x", "*.DS_Store", "-x", ".DS_Store"], cwd=PLUGIN)
    if os.path.isdir(os.path.join(PLUGIN, "assets")):
        subprocess.check_call(
            ["zip", "-qr", ZIP, "assets", "-x", "*.DS_Store"], cwd=PLUGIN)
    return os.path.getsize(ZIP)


def validate() -> bool:
    if shutil.which("claude") is None:
        print("  (claude CLI not on PATH — skipping `claude plugin validate`)")
        return True
    r = subprocess.run(["claude", "plugin", "validate", PLUGIN],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip().splitlines()
    print("  " + (out[-1] if out else "(no output)"))
    return r.returncode == 0


def sync_schema_cache(check_only: bool = False) -> list[str]:
    """BUILD-TIME SCHEMA CACHE (perf-coldstart): parse each bundled release
    schema once and emit the compact runtime cache into
    ``plugin/assets/schema_cache/`` (see ``src/rvt/schema_cache.py``).
    Deterministic files -> ordinary drift accounting; a broken engine copy
    fails the sync loudly rather than silently shipping no cache."""
    src = os.path.join(ROOT, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from rvt import schema_cache as SC
    return SC.sync_assets(PLUGIN, check_only=check_only)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="sync source -> plugin, validate, re-zip")
    ap.add_argument("--check", action="store_true", help="report drift only; exit 1 if any")
    ap.add_argument("--no-zip", action="store_true")
    a = ap.parse_args(argv)
    drift = sync(check_only=a.check)
    drift += sync_schema_cache(check_only=a.check)
    leaks = audit_deny()
    problems = [] if a.check else verify_assets()
    if a.check:
        rc = 0
        if drift:
            print(f"PLUGIN DRIFT: {len(drift)} file(s) differ from source:")
            for p in drift[:40]:
                print(f"  {p}")
            print("run: python tools/sync_plugin.py")
            rc = 1
        if leaks:
            print(f"DENY-LIST LEAK: {len(leaks)} quarantined file(s) inside plugin/: {leaks[:5]}")
            rc = 1
        for pr in verify_assets():
            print(f"ASSET PROBLEM: {pr}")
            rc = 1
        ident = check_identity_strings()
        print("\n".join(format_identity_report(ident)))
        if ident["unexpected"] or ident["vanished"]:
            rc = 1
        if rc == 0:
            print("plugin in sync with source (deny-audit clean, identity scan == allowlist, "
                  "assets verified)")
        return rc
    print(f"synced {len(drift)} file(s) into plugin/")
    if leaks:
        print(f"DENY-LIST LEAK: {leaks}")
        return 3
    if problems:
        for pr in problems:
            print(f"ASSET PROBLEM: {pr}")
        return 4
    print("  deny-audit clean; assets verified"
          + (" (genesis base == frontdoor pin)" if os.path.exists(FRONTDOOR_PIN) else ""))
    ok = validate()
    if not a.no_zip:
        size = rebuild_zip()
        print(f"rebuilt {os.path.relpath(ZIP, ROOT)} ({size / 1024:.0f} KB)")
    # content audit last, so the freshly built zip is scanned too
    ident = check_identity_strings(zip_path=None if a.no_zip else ZIP)
    if ident["unexpected"] or ident["vanished"]:
        print("\n".join(format_identity_report(ident)))
        return 5
    print(f"  identity scan == allowlist ({ident['allowlisted']} tracked hit(s), "
          f"{ident['files']} files + {ident['zip_members']} zip members, {ident['seconds']:.2f} s)")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
