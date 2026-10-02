"""#981 -- a certified family the matrix cites must still be the form its
generator emits, or every row citing it must say it is an EARLIER form.

``src/rvt/frontdoor/matrix.py`` cited ``certified:experiments/families/ifc/
L_downlight_loaded.rvt`` for ``famfrom_ifc:make_downlight`` while the
downlight's bytes moved twice under it (the drive law #950; one full plan arc
per circle #980).  Nothing failed, because the evidence audit only checks that
a citation is in the ledger -- not that the cited file still describes what a
user gets.  This module is the guard:

* ``EVIDENCE_FORMS`` records, per certified file a generator in this repo still
  emits, the generator's output fingerprint at certification (``None`` when it
  was never recorded) and the fingerprint the matrix WORDING was last reviewed
  against;
* :func:`verify_evidence` (static, no build) fails any row that cites an
  earlier-form file without the entry's caveat;
* the rebuild tests below regenerate through the cited generator at 2026 and
  2025 and fail when the output drifts from the reviewed fingerprint -- so the
  next byte change to the downlight re-opens the matrix wording in the same PR.

What this can NOT prove (hard rule 4): a matching fingerprint says the bytes
are the ones the wording was reviewed against, never that Revit opens them.
The certified ``.rvt`` itself is git-ignored and was built with the owner
machine's family container, so its own generator fingerprint is unknowable --
which is exactly why the entry says ``certified: None`` and the caveat is
mandatory today.
"""
from __future__ import annotations

import os

import pytest

from rvt.frontdoor import matrix as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLIGHT = "experiments/families/ifc/L_downlight_loaded.rvt"
BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
DOC = os.path.join(ROOT, "docs", "product", "PERMUTATION-MATRIX.md")


def _citers(path):
    """Every (where, text) row of the machine matrix that cites ``path``."""
    ref = "certified:" + path
    out = []
    for s in M.STAGES.values():
        if ref in s.evidence:
            out.append((f"stage {s.id}", s.does))
    for c in M.all_cells():
        if ref in c.evidence:
            out.append((f"cell {'+'.join(c.inputs)}->{c.output}", "\n".join(c.caveats)))
    for name, ch in M.CHAINS.items():
        if ref in ch.get("evidence", ()):
            out.append((f"chain {name}", str(ch.get("note") or "")))
    return out


# ---------------------------------------------------------------------------
# static: the registry, the wording, the audit hook
# ---------------------------------------------------------------------------

def test_every_registered_form_is_a_certified_ledger_entry():
    import json
    with open(os.path.join(ROOT, M.LEDGER_RELPATH), encoding="utf-8") as fh:
        certified = {e.get("file") for e in json.load(fh).get("certified", [])}
    for path, ent in M.EVIDENCE_FORMS.items():
        assert path in certified, path
        assert ent["generator"] and ent["build"] and ent["caveat"]
        assert set(ent["reviewed"]) >= {2026, 2025}, path


def test_the_downlight_is_registered_and_is_an_earlier_form():
    assert DOWNLIGHT in M.EVIDENCE_FORMS
    assert M.EVIDENCE_FORMS[DOWNLIGHT]["certified"] is None
    assert M.evidence_form_is_earlier(DOWNLIGHT)


def test_every_row_citing_the_downlight_says_earlier_form():
    rows = _citers(DOWNLIGHT)
    # the five places #981 named: facts->rfa, rfa-load, ifc->rfa, rfa->rvt,
    # rfa+rvt->rvt, and the ifc->rfa->loaded-rvt chain
    wheres = {w for w, _ in rows}
    assert {"stage facts->rfa", "stage rfa-load", "cell ifc->rfa", "cell rfa->rvt",
            "cell rfa+rvt->rvt", "chain ifc->rfa->loaded-rvt"} <= wheres, wheres
    for where, text in rows:
        assert M.DOWNLIGHT_EARLIER_FORM in text, where


def test_the_caveat_names_what_changed_and_the_current_status():
    c = M.DOWNLIGHT_EARLIER_FORM
    for must in ("EARLIER FORM", "#950", "#980", "full arc", "drive",
                 "VALID", "NO viewer or desktop-Revit verdict"):
        assert must in c, must


def test_verify_evidence_is_clean():
    assert [p for p in M.verify_evidence() if M.ABSENT_BINARY_MARK not in p] == []


def test_verify_evidence_fails_a_row_that_drops_the_caveat(monkeypatch):
    s = M.STAGES["facts->rfa"]
    bare = M.Stage(s.id, s.impl, s.does.replace(M.DOWNLIGHT_EARLIER_FORM, ""), s.evidence)
    monkeypatch.setitem(M.STAGES, "facts->rfa", bare)
    probs = [p for p in M.verify_evidence() if "EARLIER form" in p]
    assert probs and probs[0].startswith("stage facts->rfa"), probs


def test_a_matching_fingerprint_needs_no_caveat(monkeypatch):
    ent = dict(M.EVIDENCE_FORMS[DOWNLIGHT])
    ent["certified"] = ent["reviewed"]
    monkeypatch.setitem(M.EVIDENCE_FORMS, DOWNLIGHT, ent)
    assert not M.evidence_form_is_earlier(DOWNLIGHT)


def test_the_rendered_doc_says_earlier_form_wherever_it_names_the_file():
    with open(DOC, encoding="utf-8") as fh:
        rows = [ln for ln in fh if ln.startswith("|") and "L_downlight" in ln]
    assert len(rows) == 4, len(rows)
    for ln in rows:
        assert "an earlier form" in ln and "#981" in ln, ln[:80]
        # never presented as the complete list of changes (#985 review)
        assert "not complete" in ln and "#601" in ln, ln[:80]


def test_the_plugin_honest_status_says_earlier_form_too():
    """The shipped plugin's own status page cites the same ledger file (#985 review)."""
    path = os.path.join(ROOT, "plugin", "docs", "HONEST-STATUS.md")
    with open(path, encoding="utf-8") as fh:
        rows = [ln for ln in fh if "L_downlight_loaded" in ln]
    assert rows and all("an earlier form" in ln and "#981" in ln for ln in rows), rows


# ---------------------------------------------------------------------------
# dynamic: rebuild through the cited generator and compare fingerprints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("release", [2026, 2025])
def test_generator_output_is_the_reviewed_form(release):
    """Fails when make_downlight's bytes move.  The fix is NOT to paste the new
    hash: re-read every row citing L_downlight_loaded.rvt, name the change in
    ``DOWNLIGHT_EARLIER_FORM`` (and the rendered doc), THEN record the new
    ``reviewed`` fingerprint -- or stage a viewer batch and, once a verdict
    lands, cite the new certified file instead."""
    if not os.path.isfile(BASE):
        pytest.skip("bundled genesis base not in this clone")
    ent = M.EVIDENCE_FORMS[DOWNLIGHT]
    got = M.generator_fingerprint(DOWNLIGHT, release)
    assert got == ent["reviewed"][release], (
        f"{ent['generator']} output at {release} drifted from the fingerprint the "
        f"matrix wording was reviewed against ({ent['reviewed'][release][:8]} -> "
        f"{got[:8]}): update DOWNLIGHT_EARLIER_FORM + PERMUTATION-MATRIX.md to name "
        "what changed, then record the new reviewed fingerprint (#981)")


def test_the_fingerprint_is_deterministic_across_directories(tmp_path):
    if not os.path.isfile(BASE):
        pytest.skip("bundled genesis base not in this clone")
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert (M.generator_fingerprint(DOWNLIGHT, 2026, out_dir=str(a))
            == M.generator_fingerprint(DOWNLIGHT, 2026, out_dir=str(b)))
