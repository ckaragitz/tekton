"""#996 -- what WF_fix / WF_nofix certify is stated ONE way everywhere.

Both ledger entries are walls + ONE loaded family; the walls+families file
that failed had 8, and verdict #27 (docs/inbox/genesis-audit.md) left the
attribution open -- no walls + N families ladder has run since.  So every
product surface quotes ``matrix.WALLS_FAMILY_SHAPE`` and none says "walls +
loaded families are certified" or that the old suspicion is "exonerated".

What this can NOT prove (hard rule 4): the wording follows the ledger; it
never makes a file open in Revit.
"""
from __future__ import annotations

import glob
import json
import os
import re

import pytest

from rvt.frontdoor import intent as FI
from rvt.frontdoor import matrix as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHAPE = M.WALLS_FAMILY_SHAPE
#: every hand-authored surface that states the shape -- each must quote it
QUOTING = ("plugin/skills/tekton-author/references/GENESIS-BASE.md",
           "docs/product/PERMUTATION-MATRIX.md", "/".join(("plugin", "docs", "HONEST-STATUS.md")),
           "src/rvt/frontdoor/SKILL.frontdoor.md", "plugin/skills/tekton-author/SKILL.md",
           "plugin/README.md", "plugin/agents/bim-job-orchestrator.md", "tools/frontdoor.py")
#: the sources an overclaim must never reappear in
SCANNED = ("src/rvt/frontdoor/*.py", "src/rvt/frontdoor/*.md", "plugin/skills/**/SKILL.md",
           "plugin/skills/**/references/*.md", "/".join(("plugin", "docs", "*.md")),
           "docs/product/*.md", "plugin/README.md", "plugin/agents/*.md",
           "plugin/commands/*.md", "src/rvt/convert/*.py", "tools/frontdoor.py", "tools/route.py",
           "tools/revit_kit.py")
#: dated measurement logs quote what a run printed then; never a claim of now
LOGS = {"docs/product/REQUIREMENTS.md"}
_OVERCLAIM = re.compile(
    r"walls \+ loaded famil(?:y|ies)(?: documents)?(?: (?:together|in (?:one|ONE) file))?"
    r"(?: are| is)? (?:certified|PASS)\b"
    r"|walls\s*\+\s*loaded families,? (?:the )?certified shape"
    r"|walls\+families combination['’]? suspicion is exonerated"
    r"|walls\+families in one file\)? [—-]+ \*\*exonerated"
    # #998: the old cell, the dead stamp, and a --strict pair called proven
    r"|walls\+families combination unverified"
    r"|created walls \**and\** our generated,? placed families"
    r"|walls\+families open[- ]bug"
    r"|(?:two |coordinated )+(?:proven|certified)(?:-shaped)? files"
    r"|walls \+ our placed families in one file"
    r"|walls\+families combination bug"
    r"|walls \+ loaded[- ]families combination is the open bug"
    r"|PROOF-ONLY: walls\+\s*\"?\s*\"?families combination", re.I)


def _flat(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return " ".join(fh.read().split())


def _scanned():
    out = set()
    for g in SCANNED:
        out.update(os.path.relpath(p, ROOT).replace(os.sep, "/")
                   for p in glob.glob(os.path.join(ROOT, g), recursive=True))
    return sorted(out - LOGS)


def test_the_shape_says_one_family_and_names_the_open_question():
    assert "one loaded family" in SHAPE and "WF_fix / WF_nofix" in SHAPE
    assert "open" in SHAPE and "#27" in SHAPE


def test_the_ledger_still_says_what_the_shape_says():
    with open(os.path.join(ROOT, "docs/coverage/viewer-certified.json"), encoding="utf-8") as fh:
        led = json.load(fh)
    ents = led if isinstance(led, list) else next(v for v in led.values() if isinstance(v, list))
    wf = {os.path.basename(e["file"]): e for e in ents
          if isinstance(e, dict) and str(e.get("file", "")).endswith(("WF_fix.rvt", "WF_nofix.rvt"))}
    assert set(wf) == {"WF_fix.rvt", "WF_nofix.rvt"}
    assert "one family" in wf["WF_fix.rvt"]["proves"]
    assert "8 families" in wf["WF_nofix.rvt"]["proves"]      # the attribution is open


def test_the_engine_texts_quote_the_shape():
    for text in (M._OPEN_BUG, FI.OPEN_BUG_TEXT, FI._CELL_WHY):
        assert SHAPE in text, text[:120]


@pytest.mark.parametrize("rel", QUOTING)
def test_each_surface_quotes_the_shape(rel):
    assert SHAPE in _flat(rel), rel


@pytest.mark.parametrize("rel", _scanned())
def test_no_surface_overclaims_walls_plus_families(rel):
    hits = [m.group(0) for m in _OVERCLAIM.finditer(_flat(rel))]
    assert hits == [], (rel, hits)


def test_the_overclaim_pattern_fires_on_the_old_texts():
    for old in ("walls + loaded families in one file are certified -- WF_fix",
                "walls + loaded families in ONE file PASS (WF_fix / WF_nofix",
                "walls + loaded families together PASS",
                "shell (walls + loaded families, certified shape)",
                "the old 'walls+families combination' suspicion is exonerated",
                "**Open bug r2** (walls+families in one file) — **exonerated**",
                "stamped `PROOF-ONLY: walls+families combination unverified`",
                "Created walls AND our generated, placed families in ONE file",
                "help=\"walls+families open bug -> two coordinated files\"",
                "`--strict` = TWO coordinated proven files",
                "wants two proven-shaped files instead of the stamped combo",
                "caveats: walls + our placed families in one file is the open cell",
                "research residuals (RENDER gate, walls+families combination bug",
                "and the walls + loaded-families COMBINATION is the open bug the",
                "the stamped product shape (PROOF-ONLY: walls+families combination)"):
        assert _OVERCLAIM.search(old), old
    assert not _OVERCLAIM.search(SHAPE)


@pytest.mark.parametrize("n_fam,one", [(1, True), (2, False), (8, False)])
def test_the_shell_reason_scales_with_the_family_count(n_fam, one):
    text = FI._wf_shape(n_fam)
    if one:
        assert "certified shape" in text and "one loaded family" in text
    else:
        assert text.startswith("certified only as " + SHAPE)
        assert f"with {n_fam} families no viewer verdict" in text
