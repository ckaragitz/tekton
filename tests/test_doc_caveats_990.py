"""#990 -- every shipped skill doc and product doc that names a registered
certified evidence file carries that file's caveat where it names it.

#981 / #984 guard the machine matrix's rows and two rendered docs
(PERMUTATION-MATRIX.md table rows, HONEST-STATUS.md table rows).  #990 found
the same files named, uncaveated, in a shipped skill reference
(plugin/skills/tekton-author/references/GENESIS-BASE.md) and in
docs/product/REQUIREMENTS.md.  This module widens the net to every file a
user or a skill session reads:

    plugin/skills/**/SKILL.md, plugin/skills/**/references/*.md,
    plugin/docs/*.md, docs/product/*.md

For every registered path (``EVIDENCE_FORMS`` / ``EVIDENCE_MECHANISMS``,
found by its ``doc_names`` regexes) the *unit* naming it must carry the
caveat's issue tag (``#981`` for the downlight, ``#984`` for the rest) and
its kind phrase (``earlier form`` / ``mechanism only``, case-insensitive).
A unit is: a table row (a line starting ``|``); a line inside a fenced code
block (the dated measurement logs are one long line per finding); otherwise
one prose paragraph or list item (consecutive non-blank lines, split where a
new list item starts) -- prose wraps, so a line is too small a unit there.

Exclusions: none.  The only dated logs in scope are REQUIREMENTS.md's
"Measurements behind this section" blocks, and #990 caveats them in place
(an appended ``[#990 note: ...]``) rather than exempting them, so a reader
of any of these files never meets an uncaveated certification claim.  An
exclusion added later must be listed in ``EXCLUDED`` with its reason.

What this can NOT prove (hard rule 4): a caveat in prose says what the
ledger certifies; it never makes a file open in Revit.
"""
from __future__ import annotations

import glob
import os
import re

import pytest

from rvt.frontdoor import matrix as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: (plugin/docs/*.md is spelled as a join: tests/test_ci_fresh.py's docs-reference
#: scanner reads a "plugin/docs/*" literal as the repo's own docs/ directory)
GLOBS = ("plugin/skills/**/SKILL.md", "plugin/skills/**/references/*.md",
         "/".join(("plugin", "docs", "*.md")), "docs/product/*.md")
#: repo-relative path -> reason; empty on purpose (see the module docstring)
EXCLUDED: dict = {}
DOWNLIGHT = "experiments/families/ifc/L_downlight_loaded.rvt"
_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s")


def _scoped_files():
    out = set()
    for g in GLOBS:
        out.update(os.path.relpath(p, ROOT).replace(os.sep, "/")
                   for p in glob.glob(os.path.join(ROOT, g), recursive=True))
    return sorted(p for p in out if p not in EXCLUDED)


def units(text):
    """``[(first line number, unit text)]`` as the module docstring defines."""
    out, buf, start, fence = [], [], 0, False

    def flush():
        nonlocal buf
        if buf:
            out.append((start, "\n".join(buf)))
        buf = []

    for i, ln in enumerate(text.splitlines(), 1):
        if ln.lstrip().startswith("```"):
            flush()
            fence = not fence
            continue
        if fence or ln.startswith("|"):
            flush()
            if ln.strip():
                out.append((i, ln))
            continue
        if not ln.strip():
            flush()
            continue
        if buf and _ITEM.match(ln):
            flush()
        if not buf:
            start = i
        buf.append(ln)
    flush()
    return out


def _registry():
    reg = []
    for path in sorted(set(M.EVIDENCE_FORMS) | set(M.EVIDENCE_MECHANISMS)):
        ent = M.EVIDENCE_FORMS.get(path) or M.EVIDENCE_MECHANISMS[path]
        phrase = "earlier form" if path in M.EVIDENCE_FORMS else "mechanism only"
        tag = "#981" if path == DOWNLIGHT else "#984"
        reg.append((path, [re.compile(p) for p in ent["doc_names"]], tag, phrase))
    return reg


def missing_caveats(text, reg=None):
    """``[(line, path)]`` for every unit of ``text`` naming a registered file
    without its caveat."""
    bad = []
    for start, u in units(text):
        for path, pats, tag, phrase in (reg or _registry()):
            if any(p.search(u) for p in pats) and not (tag in u and phrase in u.lower()):
                bad.append((start, path))
    return bad


def test_the_scope_is_what_990_names():
    files = _scoped_files()
    for must in ("plugin/skills/tekton-author/references/GENESIS-BASE.md",
                 "plugin/skills/tekton-author/SKILL.md", "plugin/docs/HONEST-STATUS.md",
                 "docs/product/REQUIREMENTS.md", "docs/product/PERMUTATION-MATRIX.md"):
        assert must in files, must
    assert not set(EXCLUDED) - {p for g in GLOBS for p in
                                (os.path.relpath(x, ROOT).replace(os.sep, "/")
                                 for x in glob.glob(os.path.join(ROOT, g), recursive=True))}


@pytest.mark.parametrize("rel", _scoped_files())
def test_every_unit_naming_a_registered_file_carries_its_caveat(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        bad = missing_caveats(fh.read())
    assert bad == [], [(f"{rel}:{ln}", os.path.basename(p)) for ln, p in bad]


def test_the_guard_finds_every_registered_file_somewhere():
    """Each registered file is named by at least one scoped doc -- else its
    doc_names regexes have drifted from how the docs spell it."""
    reg = _registry()
    named = set()
    for rel in _scoped_files():
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            for _, u in units(fh.read()):
                named.update(path for path, pats, _, _ in reg if any(p.search(u) for p in pats))
    assert named == {path for path, _, _, _ in reg}, sorted({p for p, *_ in reg} - named)


def test_the_guard_fires_on_the_shapes_990_found():
    # the old GENESIS-BASE.md item 3: prose, wrapped, two files, no caveat
    prose = ("3. **THE OPEN BUG.** walls alone\n   PASS -- `electrical_room_2500a_walls_only.rvt`"
             " certified; families\n   alone PASS -- `stage_L8_lp4.rvt` certified).\n")
    assert {os.path.basename(p) for _, p in missing_caveats(prose)} == {
        "electrical_room_2500a_walls_only.rvt", "stage_L8_lp4.rvt"}
    # the old REQUIREMENTS.md:98: one fenced log line
    fenced = "```text\n(8) certified on 2026 (electrical_room_2500a_walls_only, W1_gabpd).\n```\n"
    assert len(missing_caveats(fenced)) == 2
    # a table row without its caveat
    assert missing_caveats("| a | certified `ROOM2025_walls.rvt` |\n")
    # the caveat in the NEXT list item does not cover this one
    split = ("- `stage_L8_lp4.rvt` certified\n"
             "- an earlier form (#984) of something else\n")
    assert missing_caveats(split) == [(1, "experiments/ifc_room/stage_L8_lp4.rvt")]
    # and the caveated forms pass
    assert not missing_caveats("- `stage_L8_lp4.rvt` is an **earlier form** (#984)\n")
    assert not missing_caveats("| `W1_gabpd` (MECHANISM ONLY, #984) |\n")


def test_the_genesis_base_reference_states_the_open_cell_as_the_matrix_does():
    with open(os.path.join(ROOT, "plugin/skills/tekton-author/references/GENESIS-BASE.md"),
              encoding="utf-8") as fh:
        flat = " ".join(fh.read().split())
    from rvt.frontdoor.intent import OPEN_CELL_STAMP
    assert OPEN_CELL_STAMP in flat
    assert "walls+families combination unverified" not in flat      # the stale stamp
    assert "WF_fix" in flat and "PLACED INSTANCES" in flat
    assert "verdicts #24/#25" in flat


def test_the_placing_chain_row_carries_the_chain_notes_clauses():
    with open(os.path.join(ROOT, "docs/product/PERMUTATION-MATRIX.md"), encoding="utf-8") as fh:
        row = next(ln for ln in fh if ln.startswith("| prompt → rfa → loaded-rvt |"))
    from rvt.frontdoor.intent import OPEN_CELL_STAMP
    assert OPEN_CELL_STAMP in row and "THE OPEN CELL" in row
    assert "tests/test_frontdoor_standalone.py" in row
    ch = M.CHAINS["prompt->rfa->loaded-rvt"]
    assert OPEN_CELL_STAMP in ch["note"]
    assert "test:tests/test_frontdoor_standalone.py" in ch["evidence"]
