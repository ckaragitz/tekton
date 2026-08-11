"""test_clause_relays.py -- the three error relays that adopted ``rvt._clause``
last (issue #596; the rule itself is pinned by test_edit_status.py /
test_release_ctx_refusal.py, #587):

* ``rvt.frontdoor.manifest._rollup_status`` -- the CREATE routes' ``FAILED
  (<errors[0]>)`` status: whole when it fits, else cut at a word boundary
  with ``...`` by the same ``_status_reason`` the edit route uses (was a raw
  ``[:160]`` mid-word slice);
* ``rvt.frontdoor.input_release`` -- the refused-input line of a 2019+ file
  outside the roster whose own ``Formats/Latest`` does not parse names the
  parser's error as a clause (``cause_clause``: the words, never its
  ``@0x…: hex | hex`` context dump);
* ``rvt.manipulate.verify_manipulated`` -- the ``own schema unreadable (…)``
  decode fallback note on a schema-damaged host: the same clause its sibling
  framing rung (``global_framing.enter_own_release``) already carries.

The damaged inputs are our own certified 2025 pin re-emitted by our CFB writer
(``conftest.rewrite_stream`` / ``zero_schema_bytes``); no samples.  Fresh-clone
runnable (tests/ci_shard.d/596-clause-relays.txt).

Run: .venv/bin/python -m pytest tests/test_clause_relays.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import FOREIGN, pinned_base, rewrite_stream, zero_schema_bytes   # noqa: E402
from rvt import _clause                                                       # noqa: E402
from rvt import versions as V                                                 # noqa: E402
from rvt.frontdoor import input_release as IR                                 # noqa: E402
from rvt.frontdoor import manifest as MF                                      # noqa: E402


# ---------------------------------------------------------------------------
# site 1: the create routes' FAILED status
# ---------------------------------------------------------------------------

def _rollup(*errors: str) -> str:
    return MF._rollup_status({"build": {"errors": list(errors)}})


def test_create_status_carries_a_fitting_reason_whole():
    reason = ("IFC intent failed: the --ifc route needs numpy, not installed on this interpreter -- "
              "one-time fix: python -m pip install numpy (--prompt / --rvt run without it)")
    assert len(reason) <= MF._STATUS_REASON_MAX
    assert _rollup(reason, "a second error never rides in the status") == f"FAILED ({reason})"


def test_create_status_cuts_a_long_reason_at_a_word_boundary():
    words = ("IFC intent failed: ValueError: the storey carries fourteen flow segment runs whose "
             "local placement chains never reach the site placement so no room-relative coordinates "
             "can be derived for any of them at all")
    assert len(words) > MF._STATUS_REASON_MAX
    reason = _clause.clip(words, MF._STATUS_REASON_MAX)          # the edit route's rule (manifest._status_reason)
    assert _rollup(words) == f"FAILED ({reason})" != f"FAILED ({words[:MF._STATUS_REASON_MAX]})"
    assert reason.endswith("...") and words[len(reason) - 3] == " "             # cut AT a boundary, not mid-word


def test_create_status_is_one_line():
    assert _rollup("a\nb  c") == "FAILED (a b c)"


# ---------------------------------------------------------------------------
# sites 2 + 3: a REAL ParseError (with its byte dump) from a schema-damaged pin
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def schema_dmg(tmp_path_factory):
    """The first certified foreign pin with 64 B of ``Formats/Latest`` zeroed:
    container and stream survive, the class schema no longer parses."""
    if not FOREIGN:
        pytest.skip("no certified foreign-release pin")
    return rewrite_stream(pinned_base(FOREIGN[0]), tmp_path_factory.mktemp("clause596") / "schema_dmg.rvt",
                          "Formats/Latest", zero_schema_bytes)


def _parse_error(path: str) -> BaseException:
    with pytest.raises(Exception) as ei:
        V.ordinals_from_schema(V.schema_of(path))
    assert " @0x" in str(ei.value) and " | " in str(ei.value)       # the parser's dump IS on the exception
    return ei.value


def test_refused_input_names_the_parse_error_as_a_clause(schema_dmg, tmp_path):
    """The damaged pin redated (by OUR BasicFileInfo encoder) to a year tekton
    never read: refused because its own schema does not parse -- the reason
    carries ``ParseError: <words>``, not the dump and not a mid-word cut."""
    from rvt.stream_encoders import decode_basic_file_info, encode_basic_file_info
    unread_year = max(V.KNOWN_RELEASES) + 1
    unread = rewrite_stream(schema_dmg, tmp_path / "unread_schema_dmg.rvt", "BasicFileInfo",
                            lambda raw: encode_basic_file_info({**decode_basic_file_info(raw),
                                                                "format": str(unread_year)}))
    blk = IR.input_release_block(unread)
    assert (blk["status"], blk["year"]) == ("refused", unread_year), blk
    cause = _clause.cause_clause(_parse_error(unread))
    assert cause.startswith("ParseError: ") and "@0x" not in cause and "..." not in cause
    assert blk["reason"] == f"its own Formats/Latest schema does not parse ({cause})"
    line = blk["line"]
    assert line.startswith(f"{IR.REFUSED_PREFIX}: unread_schema_dmg.rvt is a Revit {unread_year} file ({blk['reason']}); ")
    assert "@0x" not in line and " | " not in line and "\n" not in line


def test_verify_manipulated_names_the_unreadable_schema_as_a_clause(schema_dmg):
    """The decode rung of ``verify_manipulated`` on the damaged host says ``own
    schema unreadable (<clause>)`` with the very clause its framing rung
    (``global_framing.enter_own_release``, pinned by test_release_ctx_refusal)
    carries -- and neither carries the dump."""
    from rvt import manipulate as M
    cause = _clause.cause_clause(_parse_error(schema_dmg))
    v = M.verify_manipulated(schema_dmg, edited_ids=[])
    assert len(v["fallbacks"]) == 2, v["fallbacks"]
    framing, decode = v["fallbacks"]
    assert decode == (f"own schema unreadable ({cause}); edited records decoded against the "
                      "built-in latest-release schema")
    assert framing.startswith(f"own schema unreadable ({cause}); ")               # one clause, both rungs
    assert all("@0x" not in f and " | " not in f and "..." not in f for f in v["fallbacks"])
