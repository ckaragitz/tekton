"""Guard: tools/dev/coord.py — the token-free coordination helpers behind coord.yml.

The fixture is the real issue list from the repo's first night (2026-08-07/08),
when two contributors' sessions filed and fixed the same three bugs twice
(#26/#34, #29/#32, #27+#37/#33). `similar` must flag each later filing against
the earlier one and stay quiet on the unrelated seeded queue; `refs`/`rivals`
must read PR bodies the way GitHub's issue linker does, including the
"does not close #N" trap that closes #N anyway.
"""
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORD = os.path.join(ROOT, "tools", "dev", "coord.py")
_spec = importlib.util.spec_from_file_location("coord", COORD)
coord = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(coord)

TITLES = {
    1: 'Front door: restore wall derivation from room prompts + add rating-class voltage vocabulary ("250V")',
    2: "CI v1: GitHub Actions running plugin drift/validation + a fast no-samples test shard",
    3: "pyproject: declare test / geometry / IFC extras and align README setup",
    4: "Docs: refresh README / AGENT_BRIEF / SHARE-README to match tekton + CLAUDE.md (kill stale rev-revit-era text)",
    5: "Permutation matrix: register the convert-a/b implementations, add the certified .rfa-load and extract→place depths, apply the frontdoor patch",
    6: "Perf: make the ifcopenshell import lazy in rvt.ifc.intent (P1 patch) — stop taxing prompt-only jobs",
    7: "Validator: promote the 0x0f3f unit-footer-blob presence law to a rule (ERROR when the unit is instanced)",
    8: "probe_batch: campaign-global batch numbering + native multi-control batches",
    9: "famgen determinism: replace uuid4 in skeleton.new_geo_site with a deterministic uuid5 default",
    10: "famgen/famload: never emit blank-named host symbol pairs (promote the birthright v3 hostsym one-liners to product code)",
    11: "manipulate: bind the FILE'S OWN schema in verify_manipulated (latent 2024/2025 verification bug)",
    12: "famdoc_adoc: fix the donor-id byte-scan false positive (tree-corroborate at the raise site)",
    13: "Encoders: GraveyardRec ElemTable codec gap (unblocks full RFA→RFA on foreign families)",
    14: "2025 famload/instance lane: port family loading + placement to native 2025 framing (gap B)",
    15: "rft_probe hygiene: remap seq-103 rep id slots in the schema-typed rebase (T-lane gap)",
    16: "THE OPEN CELL: run the desktop-Revit check kit and record the exact error dialogs",
    17: "2023: run the substitution ladder + compose G_ABPD_2023 on the certified B2023_K4, stage the round, prep the flip",
    18: "Re-emit and re-certify the pre-fix acceptance/convert artifacts through the current writer (blob + D1–D5 fixes)",
    19: "Genesis identity: scrub the inherited Autodesk username from G_ABPD (BFI / DIT / ProjectInformation / TransmissionData) and re-certify",
    20: "Compose-side style repair (HR1): real appearance assets + cellLists on substituted style/material rows; close deleted-style holes",
    21: "Genesis residue: author the curtain constellation + remaining residue groups (586 elements / 45 classes after RC_2024)",
    22: "test_genesis_assemble::test_ladder_end_to_end is red (G0a four-registry incoherence)",
    23: "Counsel gates (C1 author string, C4 schema corpora, C5 footer token, trademark) — tracking",
    24: "Skills UX: target-version FIRST (ask the year for prompt/IFC inputs; auto-detect for .rvt inputs) with per-release honest status",
    25: "START HERE — how to pick work in this repo (read before claiming anything)",
    26: "validate_plugin: check_skills treats non-skill dirs (_shared, __pycache__) as skills and always fails",
    27: "Windows: autocrlf corrupts a tracked PDF, and schema_cache/index.json generates non-deterministically (sync_plugin --check permanently red)",
    29: "Windows: text I/O without encoding= crashes on non-ASCII output (cp1252) — 222 write sites",
    32: "Windows: front-door manifest/handoff writers crash with cp1252 UnicodeEncodeError (write UTF-8 explicitly)",
    33: "Windows: sync_plugin re-zip subprocess FileNotFoundError + schema_cache index.json backslash churn breaks --check",
    34: "validate_plugin: skills/_shared fails 'SKILL.md missing' (23/24 assertions pass)",
    37: "sync_plugin.rebuild_zip shells out to the 'zip' CLI, which does not exist on Windows",
}
# (later issue, the earlier issue it duplicated) — what actually happened that night.
DUPLICATES = [(34, 26), (32, 29), (33, 27), (37, 33)]

PR_BODY = """<!-- One issue = one branch = one PR. Closes #999 in a template comment does not count -->
Closes #37
Refs #29 (stage 1 of 3 — does **not** close #29)
Also fixes: #12 and resolved #7; see #40 for the gates, and the pre-fix #18 artifacts.
&#39;quoted&#39; entity is not issue 39.
"""


def _filed_before(n):
    return [{"number": k, "title": t, "state": "open", "assignees": []}
            for k, t in TITLES.items() if k < n]


def test_similar_flags_each_real_duplicate_against_what_was_already_filed():
    for later, earlier in DUPLICATES:
        hits = coord.similar(TITLES[later], _filed_before(later), self_number=later)
        numbers = [h[1]["number"] for h in hits]
        assert earlier in numbers, (later, earlier, hits)
        # top hit is the real duplicate; #37 may rank the closely related #27 next to #33
        assert numbers[0] == earlier or (later, numbers[0]) == (37, 27), hits


def test_similar_stays_quiet_on_the_unrelated_seeded_queue():
    noisy = {n: [(h[0], h[1]["number"]) for h in coord.similar(TITLES[n], _filed_before(n), n)]
             for n in TITLES if n <= 25}
    assert {n: h for n, h in noisy.items() if h} == {}


def test_similar_excludes_self_and_ranks_rare_identifiers_above_common_words():
    everything = [{"number": k, "title": t, "state": "open"} for k, t in TITLES.items()]
    hits = coord.similar(TITLES[34], everything, self_number=34)
    assert 34 not in [h[1]["number"] for h in hits]
    shared = hits[0][2]
    assert {"validate_plugin", "shared", "plugin"} <= set(shared), shared
    assert shared.index("validate_plugin") < shared.index("plugin"), shared   # rarer token first


def test_tokens_keep_identifiers_whole_and_split():
    t = coord.tokens("Windows: schema_cache/index.json backslash churn breaks sync_plugin --check")
    assert {"schema_cache", "index.json", "sync_plugin", "schema", "cache", "json", "check", "window"} <= t
    assert coord.tokens("the a of and") == set()


def test_refs_reads_bodies_like_githubs_linker():
    r = coord.refs(PR_BODY)
    assert r["closing"] == [7, 12, 29, 37], r      # GitHub WILL close #29 here — hence 'negated'
    assert r["negated"] == [29], r
    assert r["refs"] == [18, 40], r
    assert coord.refs("")["closing"] == [] and coord.refs(None)["refs"] == []


def test_rivals_uses_the_same_parser():
    prs = [{"number": 40, "author": {"login": "Ckaragitz12"}, "body": "Closes #37\nRefs #29"},
           {"number": 47, "author": {"login": "cam-karagitz"}, "body": "Closes #46"},
           {"number": 50, "author": {"login": "clkaragitz"}, "body": PR_BODY}]
    assert coord.rivals(37, prs, self_number=50) == [(40, "Ckaragitz12")]
    assert coord.rivals(29, prs) == [(50, "clkaragitz")]           # negated wording still closes
    assert coord.rivals(999, prs) == []                              # template comment ignored


def test_cli(tmp_path):
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps(_filed_before(34)), encoding="utf-8")
    out = subprocess.run([sys.executable, COORD, "similar", "--title", TITLES[34], "--self", "34",
                          "--issues", str(issues)], capture_output=True, text=True, check=True).stdout
    assert out.startswith("- #26 (open, unassigned) validate_plugin:"), out
    out = subprocess.run([sys.executable, COORD, "refs"], input="Part of #44.\n",
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {"closing": [], "refs": [44], "negated": []}
    prs = tmp_path / "prs.json"
    prs.write_text(json.dumps([{"number": 40, "author": {"login": "x"}, "body": "fixes #37"}]), encoding="utf-8")
    out = subprocess.run([sys.executable, COORD, "rivals", "--issue", "37", "--self", "50", "--prs", str(prs)],
                         capture_output=True, text=True, check=True).stdout
    assert out == "40 x\n"


def test_reqfile_front_matter_wins_and_labels_split():
    text = ("---\n"
            "title: famgen: blank-named host symbol pairs never emitted\n"
            "labels: area:famgen, P1 , good-first-pick\n"
            "auto: Claude\n"
            "---\n"
            "# A heading that must NOT become the title\n\nBody text.\n")
    r = coord.reqfile(text, "docs/requirements/famgen-hostsym.md")
    assert r["title"] == "famgen: blank-named host symbol pairs never emitted"
    assert r["labels"] == ["area:famgen", "P1", "good-first-pick"]
    assert r["auto"] == "claude"
    assert r["body"].startswith("# A heading")


def test_reqfile_falls_back_to_heading_then_filename():
    r = coord.reqfile("# The checkable DONE\n\ndetails\n", "docs/requirements/x.md")
    assert (r["title"], r["labels"], r["auto"]) == ("The checkable DONE", [], "")
    r = coord.reqfile("no heading at all\n", "docs/requirements/route-ifc-out-gap.md")
    assert r["title"] == "Route ifc out gap"


def test_reqfile_malformed_front_matter_is_body_not_error():
    text = "---\nthis line is prose, not key: value pairs precede it? no\n---\n# T\n"
    r = coord.reqfile(text, "docs/requirements/y.md")
    assert r["title"] == "T"                       # heading still found
    assert r["body"].startswith("---")             # the pseudo-front-matter stayed in the body
    # a --- horizontal rule mid-document never eats the text above it
    r2 = coord.reqfile("# T2\n\nintro\n\n---\n\nafter the rule\n", "docs/requirements/z.md")
    assert r2["title"] == "T2" and "after the rule" in r2["body"]


def test_reqfile_cli(tmp_path):
    f = tmp_path / "req.md"
    f.write_text("---\nlabels: P2\n---\n# From CLI\nbody\n", encoding="utf-8")
    out = subprocess.run([sys.executable, COORD, "reqfile", "--path", str(f)],
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {"title": "From CLI", "labels": ["P2"], "auto": "", "body": "# From CLI\nbody"}
