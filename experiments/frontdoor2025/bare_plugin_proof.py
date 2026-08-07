#!/usr/bin/env python
"""bare_plugin_proof.py -- THE PLUGIN-BUNDLE VARIANT of the 2025 finish line
(build-2025 stream).

Acceptance-test pattern (tests/test_frontdoor_standalone.py): a BARE temp
directory containing NOTHING but the unzipped ``tekton-plugin.zip`` -- no
repo, no experiments/, no samples/, no vendor/.  In a subprocess whose
python path is ONLY the plugin's ``lib/src``:

  1. ``rvt.frontdoor.base.resolve_base(target_release=2025)`` must resolve
     the BUNDLED ``assets/genesis/G_ABPD_2025.rvt`` (sha256-pin verified);
  2. ``rvt.frontdoor.standalone.author_standalone(prompt=..., target_version
     =2025, no_handoff=True)`` must produce a native file whose
     ``detect_release`` is 2025, manifest ``target_version.status ==
     'match'``, validator self-checks green.

Writes the machine report to ``bare_plugin_proof.json`` beside this script.
Exit 0 = both proofs hold.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ZIP = os.path.join(ROOT, "tekton-plugin.zip")

CODE = r"""
import json, os
import rvt.versions as V
from rvt.frontdoor.base import resolve_base
from rvt.frontdoor.standalone import author_standalone

out = {}
rb = resolve_base(target_release=2025)
out["resolved_base"] = {"path": os.path.abspath(rb.path), "source": rb.source,
                        "certified": rb.certified, "pinned": rb.pinned,
                        "detect": V.detect_release(rb.path)}
r = author_standalone(prompt="a 400 A distribution panel", target_version=2025,
                      no_handoff=True, out="out-2025")
f = r.files.get("combined") or r.files.get("equipment") or r.files.get("shell")
tv = (r.manifest.get("target_version") or {})
val = ((r.manifest.get("build") or {}).get("validation") or {})
roles = {role: bool((g or {}).get("self_checks_ok")) for role, g in val.items()}
out["author"] = {"ok": r.ok, "errors": r.errors, "output": os.path.abspath(f or ""),
                 "detect_release": (V.detect_release(f) if f else None),
                 "schema_sha256": (V.schema_of(f).stats()["sha256"] if f else None),
                 "target_version": {k: tv.get(k) for k in ("status", "requested",
                                                            "output_release", "line")},
                 "self_checks": roles}
print("PROOF-JSON:" + json.dumps(out))
"""


def main() -> int:
    if not os.path.isfile(ZIP):
        print(f"tekton-plugin.zip not found at {ZIP}")
        return 2
    bare = tempfile.mkdtemp(prefix="tekton-bare-plugin-")
    try:
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(bare)
        env = {k: v for k, v in os.environ.items()
               if k not in ("RVT_GENESIS_BASE", "RVT_PLUGIN_ROOT", "PYTHONPATH")}
        env["TEKTON_ROOT"] = bare
        env["PYTHONPATH"] = os.path.join(bare, "lib", "src")
        p = subprocess.run([sys.executable, "-c", CODE], cwd=bare, env=env,
                           capture_output=True, text=True, timeout=1200)
        line = next((l for l in p.stdout.splitlines()
                     if l.startswith("PROOF-JSON:")), None)
        rep = {"zip": os.path.relpath(ZIP, ROOT), "bare_dir": bare,
               "returncode": p.returncode,
               "stderr_tail": p.stderr[-1500:] if p.returncode else ""}
        ok = False
        if line:
            data = json.loads(line[len("PROOF-JSON:"):])
            rep.update(data)
            base_ok = (data["resolved_base"]["detect"] == 2025
                       and data["resolved_base"]["certified"]
                       and data["resolved_base"]["path"].startswith(bare)
                       and data["resolved_base"]["path"].endswith(
                           os.path.join("assets", "genesis", "G_ABPD_2025.rvt")))
            a = data["author"]
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_vers", os.path.join(ROOT, "src", "rvt", "versions", "__init__.py"))
            pin = None
            try:
                sys.path.insert(0, os.path.join(ROOT, "src"))
                import rvt.versions as V
                pin = V.KNOWN_RELEASES[2025].schema_sha256
            except Exception:
                pass
            author_ok = (a["ok"] and not a["errors"]
                         and a["detect_release"] == 2025
                         and a["target_version"]["status"] == "match"
                         and not a["target_version"]["line"]
                         and all(a["self_checks"].values())
                         and (pin is None or a["schema_sha256"] == pin))
            rep["base_resolution_proof"] = base_ok
            rep["author_proof"] = author_ok
            ok = bool(base_ok and author_ok and p.returncode == 0)
        rep["pass"] = ok
        outp = os.path.join(HERE, "bare_plugin_proof.json")
        rep_out = {k: v for k, v in rep.items() if k != "bare_dir"}
        with open(outp, "w") as fh:
            json.dump(rep_out, fh, indent=1)
        print(json.dumps(rep_out, indent=1)[:2400])
        print(f"[bare-plugin] {'PASS' if ok else 'FAIL'} (report: {outp})")
        return 0 if ok else 1
    finally:
        shutil.rmtree(bare, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
