#!/usr/bin/env python3
"""Zip constraint scan (target-2024 stream) — the shipping-zip gate re-run
after the 2024 registry-slot changes.  HARD constraints:

  1. deny-listed member PATHS (samples/, extracted/, quarantine, /reference/,
     autodesk-extracted) must be 0;
  2. banned RAW-BYTE strings in any member must be 0 (old working name
     'rev-revit' + internal identifiers);
  3. quarantined-content sha256 matches must be 0 (every member hashed
     against every quarantined Autodesk sample file);
  4. .rvt/.rfa members limited to the allow-list;  nested zips 0;
  5. the genesis asset sha256 == the front door's pin;
  6. SKILL.md frontmatter: keys exactly {name, description}, name == folder,
     description non-empty, <= 1024 chars, and NO '<' or '>' characters;
  7. plugin.json description <= 500 chars.

HYGIENE (report-only, pre-existing per docs/inbox/target-2025.md §3.1):
  raw-byte '/Users/ck' personal-path hits.
"""
import glob
import hashlib
import io
import json
import os
import sys
import zipfile

ROOT = "/Users/ck/dev/things/tekton"
BANNED = [b"rev-revit", b"anthropic", b"claude-cli-internal"]
HYGIENE = [b"/Users/ck"]
DENY_PARTS = ("samples/", "extracted/", "quarantine", "/reference/", "autodesk-extracted")


def quarantined_hashes():
    out = {}
    for pat in ("samples/*.rvt", "samples/*.rfa", "samples/*/*.rvt", "samples/*/*.rfa",
                "samples/*/*/*.rvt", "samples/*/*/*.rfa"):
        for p in glob.glob(os.path.join(ROOT, pat)):
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            out[h] = os.path.relpath(p, ROOT)
    return out


def frontmatter(text):
    if not text.startswith("---"):
        return None
    body = text.split("---", 2)
    if len(body) < 3:
        return None
    fm = {}
    key = None
    for line in body[1].splitlines():
        if not line.strip():
            continue
        if line[:1] not in (" ", "\t") and ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            fm[key] = val.strip()
        elif key:
            fm[key] += " " + line.strip()
    return fm


def scan(zpath, rvt_allow):
    q = quarantined_hashes()
    z = zipfile.ZipFile(zpath)
    names = z.namelist()
    res = {"zip": os.path.relpath(zpath, ROOT), "members": len(names),
           "deny_paths": [], "banned": {}, "hygiene": {}, "quarantine_hash": [],
           "rvt_members": [], "rvt_unexpected": [], "nested_zips": [],
           "frontmatter": [], "plugin_json": None, "genesis_pin": None}
    for c in BANNED:
        res["banned"][c.decode()] = []
    for c in HYGIENE:
        res["hygiene"][c.decode()] = []
    for n in names:
        low = n.lower()
        if any(p in ("/" + low) for p in DENY_PARTS):
            res["deny_paths"].append(n)
        b = z.read(n)
        for c in BANNED:
            if c in b:
                res["banned"][c.decode()].append(n)
        for c in HYGIENE:
            if c in b:
                res["hygiene"][c.decode()].append(n)
        h = hashlib.sha256(b).hexdigest()
        if h in q:
            res["quarantine_hash"].append((n, q[h]))
        if low.endswith((".rvt", ".rfa")):
            res["rvt_members"].append(n)
            if n not in rvt_allow:
                res["rvt_unexpected"].append(n)
        if low.endswith(".zip"):
            res["nested_zips"].append(n)
        # SKILL.md frontmatter constraints
        parts = n.split("/")
        if len(parts) >= 2 and parts[-1] == "SKILL.md" and "skills" in parts:
            fm = frontmatter(b.decode("utf-8", "replace"))
            folder = parts[parts.index("skills") + 1] if parts.index("skills") + 1 < len(parts) else "?"
            desc = (fm or {}).get("description", "")
            ok = (fm is not None and set(fm) == {"name", "description"}
                  and fm.get("name") == folder and bool(desc)
                  and len(desc) <= 1024 and "<" not in desc and ">" not in desc
                  and "<" not in fm.get("name", "") and ">" not in fm.get("name", ""))
            res["frontmatter"].append(
                {"member": n, "name": (fm or {}).get("name"), "folder": folder,
                 "keys": sorted(fm) if fm else None, "desc_len": len(desc),
                 "desc_angle_brackets": ("<" in desc or ">" in desc), "ok": ok})
        if n.endswith(".claude-plugin/plugin.json"):
            d = json.loads(b)
            dl = len(d.get("description", ""))
            res["plugin_json"] = {"member": n, "desc_len": dl, "ok": dl <= 500,
                                  "name": d.get("name")}
        if n.endswith("assets/genesis/G_ABPD.rvt"):
            pin = json.load(open(os.path.join(
                ROOT, "src", "rvt", "frontdoor", "assets", "genesis_base.json")))
            want = pin["default"]["sha256"].lower()
            res["genesis_pin"] = {"member": n, "sha256_matches_pin": h == want}
    return res


def report(res):
    hard_fail = []
    print(f"== {res['zip']} — {res['members']} members ==")
    print(f"  deny-listed member paths: {len(res['deny_paths'])} {res['deny_paths'][:4]}")
    if res["deny_paths"]:
        hard_fail.append("deny paths")
    for s, hits in res["banned"].items():
        print(f"  banned raw-byte {s!r}: {len(hits)} {hits[:4]}")
        if hits:
            hard_fail.append(f"banned {s}")
    print(f"  quarantined-content sha256 matches: {len(res['quarantine_hash'])} "
          f"{res['quarantine_hash'][:2]}")
    if res["quarantine_hash"]:
        hard_fail.append("quarantine hash")
    print(f"  .rvt/.rfa members: {len(res['rvt_members'])} {res['rvt_members']} "
          f"(unexpected: {len(res['rvt_unexpected'])} {res['rvt_unexpected'][:4]})")
    if res["rvt_unexpected"]:
        hard_fail.append("unexpected rvt")
    print(f"  nested zips: {len(res['nested_zips'])} {res['nested_zips'][:4]}")
    if res["nested_zips"]:
        hard_fail.append("nested zip")
    if res["genesis_pin"] is not None:
        print(f"  genesis asset sha256 == frontdoor pin: {res['genesis_pin']['sha256_matches_pin']}")
        if not res["genesis_pin"]["sha256_matches_pin"]:
            hard_fail.append("genesis pin")
    fm_ok = all(f["ok"] for f in res["frontmatter"])
    print(f"  SKILL.md frontmatter clean {sum(f['ok'] for f in res['frontmatter'])}/"
          f"{len(res['frontmatter'])} (keys exactly {{name,description}}, name==folder, "
          f"desc non-empty <=1024, no '<'/'>')")
    for f in res["frontmatter"]:
        flag = "ok" if f["ok"] else "FAIL"
        print(f"    [{flag}] {f['member']} name={f['name']} desc_len={f['desc_len']}")
        if not f["ok"]:
            hard_fail.append(f"frontmatter {f['member']}")
    if res["plugin_json"]:
        pj = res["plugin_json"]
        print(f"  plugin.json: name={pj['name']!r} desc_len={pj['desc_len']} <=500: {pj['ok']}")
        if not pj["ok"]:
            hard_fail.append("plugin.json desc")
    for s, hits in res["hygiene"].items():
        print(f"  HYGIENE (report-only) raw-byte {s!r}: {len(hits)} hit(s) "
              f"{'(pre-existing, target-2025 record §3.1)' if hits else ''}")
        for hmem in hits:
            print(f"    - {hmem}")
    print(f"  HARD constraints: {'PASS' if not hard_fail else 'FAIL: ' + ', '.join(hard_fail)}")
    return not hard_fail


ok = True
ok &= report(scan(os.path.join(ROOT, "tekton-plugin.zip"),
                  rvt_allow={"assets/genesis/G_ABPD.rvt"}))
kit = os.path.join(ROOT, "tekton-eval-kit.zip")
if os.path.exists(kit):
    z = zipfile.ZipFile(kit)
    kit_allow = {n for n in z.namelist()
                 if n.lower().endswith((".rvt", ".rfa"))
                 and ("TEST-KIT" in n or n.endswith("tekton-plugin/assets/genesis/G_ABPD.rvt"))}
    ok &= report(scan(kit, rvt_allow=kit_allow))
print("\nOVERALL:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
