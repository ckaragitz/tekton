"""test_conftest_scaffolding.py -- the own-release test scaffolding lives ONCE,
in ``tests/conftest.py`` (issue #579, Refs #566 / #533 / #518 / #451):

* the law, over EVERY ``tests/test_*.py`` (AST, so a copy cannot creep back
  anywhere): no module hand-rolls the container-rewrite PASS -- entries read out
  of a container (``read_entries``) and a container written (``write_cfb``) in
  one module is that pass whatever its helpers are called, and its one home is
  conftest's ``rewrite_stream(s)`` (= ``rvt.roundtrip.rewrite_entries``; #639);
  no module shadows a conftest scaffolding name at top level or binds one of the
  private spellings #579 / #617 retired (``FORBIDDEN``); the ``ADOPTERS``
  keep the leak guard on, and every module on the guard is an adopter (#605);
* the hoisted helpers behave as the copies did: ``FOREIGN_FIRST`` = the
  certified years with the native release last; ``native_constants`` /
  ``ladder_constants`` / ``context_constants`` snapshot the framing table /
  the ladder's swaps / the names the authoring context swaps (and a foreign
  context really moves the latter and puts them back, #605);
  ``rewrite_stream(s)`` re-emit a pin with the named stream(s) damaged or dropped,
  ready-made entries appended, and every other stream byte-identical (a missing
  name is a KeyError); ``twin_partition_entry`` is the primary partition under the
  next stream number; the damaged-copy recipes produce what their names say; the
  ``pin`` fixture is the first ``FOREIGN_FIRST`` pin and ``streams`` is the
  container's every stream, raw, by path (#670).

Fresh-clone safe: the pins are tracked assets; no pin -> the pin-backed rows skip.

Run: .venv/bin/python -m pytest tests/test_conftest_scaffolding.py -q
"""
from __future__ import annotations

import ast
import functools
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import conftest as C                                            # noqa: E402
from rvt import versions as V                                   # noqa: E402

#: the hand-rolled container-rewrite pass by SHAPE: a module calling both reads a container's entries and writes a
#: container -- "read the entries, replace some, write_cfb" under whatever names (#639).  A builder (``write_cfb`` on
#: entries it authored) or a reader (``read_entries`` for a census) alone is not the pass and stays green.
REWRITE_PASS = {"read_entries", "write_cfb"}
#: conftest's own-release scaffolding (+ #670's pinned-base ``pin`` fixture and ``streams`` reader): no test module
#: may shadow one of these at top level (checked below to still BE conftest names, so the list cannot outlive a rename);
#: a module that needs another pin axis takes another fixture name (``params=`` on a private ``pin`` is still a copy)
SHADOWS = {"FOREIGN_FIRST", "FOREIGN", "native_constants", "ladder_constants", "context_constants", "no_release_leak",
           "rewrite_streams", "rewrite_stream", "partition_of", "twin_partition_entry", "zero_partition_header",
           "zero_schema_bytes", "smash64", "flip_bit", "truncated_copy", "cfb_header_zeroed_copy", "pin", "streams"}
#: + the retired per-file spellings that actually existed and that the shape rule cannot see: the ``NATIVE_LAST`` axis
#: and #579's private copies, #617's bytes-damage / extra-entry recipe names (they write no container), and the
#: four-fold ``_streams`` census #670 hoisted (its ``pin`` twin is caught as a shadow)
FORBIDDEN = SHADOWS | {"NATIVE_LAST", "_native_constants", "_no_leak", "_rewrite_stream", "_partition_of",
                       "_zero16", "_smash64", "_flip_bit", "_twin_entry", "_streams"}
#: every module that keeps conftest's leak guard switched on module-wide -- the files #579 / #602 relieved of an autouse
#: guard of their own, the ones born on it since, and #605's in-process context callers: a hand list on purpose (the
#: ratchet: none of these may drop the guard again), kept complete by the law itself (a module that requests the guard,
#: or overrides ``release_leak_extra``, without standing here is red until it enlists -- so the list derives forward)
ADOPTERS = ["test_selfcheck_release", "test_inspect_release", "test_edit_text_release",
            "test_natively_framed", "test_estorage_cli_release", "test_edit_own_release",
            "test_rvt_edit_refusal", "test_release_ctx_refusal", "test_edit_status",
            "test_cfb_rewrite_entries", "test_rewrite_entries_646", "test_identity_helper_657",
            "test_reduce_v2_655", "test_reduce_v2_671", "test_rvt_job_scrub_656"]
TEST_FILES = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, "tests", "test_*.py")))


@functools.cache                     # three law rows walk every module: parse each once per session
def _tree(stem: str) -> ast.Module:
    path = os.path.join(ROOT, "tests", f"{stem}.py")
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


def _top_level_names(tree: ast.Module) -> set[str]:
    """Every name the module binds at top level by ``def`` / ``class`` / assignment (``tree.body`` only, where every
    copy ever lived: a copy nested inside a class or function slips past this ratchet -- widen it the day one does)."""
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for n in tree.body:
        targets = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, (ast.AnnAssign, ast.AugAssign)) else []
        names |= {t.id for t in targets if isinstance(t, ast.Name)}
    return names


def _called_names(tree: ast.Module) -> set[str]:
    """Every name the module CALLS anywhere, nested code included -- ``f(…)`` and ``mod.f(…)`` alike.  Calls, not
    references, on purpose: a seam that rebinds ``CW.write_cfb`` to count writes next to a ``read_entries`` census
    (test_famload_batch) is no rewrite pass; the price is that a call through an alias (``w = write_cfb; w(…)``) is
    not seen -- a ratchet against the habit, not against intent."""
    funcs = (n.func for n in ast.walk(tree) if isinstance(n, ast.Call))
    return {f.id if isinstance(f, ast.Name) else f.attr for f in funcs if isinstance(f, (ast.Name, ast.Attribute))}


def test_no_module_hand_rolls_the_container_rewrite_pass():
    offenders = [stem for stem in TEST_FILES if REWRITE_PASS <= _called_names(_tree(stem))]
    assert offenders == [], (f"{offenders} pair read_entries() with write_cfb() -- the hand-rolled 'read the entries, "
                             "replace some, write the container' pass: damage / drop / append streams through "
                             "conftest.rewrite_stream(s) (= rvt.roundtrip.rewrite_entries) instead; a module that "
                             "genuinely only BUILDS containers from entries it authored and separately censuses "
                             "another file splits the two, or is allow-listed here with its reason (#639)")


def test_no_module_carries_a_private_copy():
    clashes = {stem: sorted(_top_level_names(_tree(stem)) & FORBIDDEN) for stem in TEST_FILES}
    clashes = {stem: names for stem, names in clashes.items() if names}
    assert clashes == {}, f"{clashes} -- import the own-release scaffolding from conftest instead (#579)"
    stale = sorted(SHADOWS - set(vars(C)))
    assert stale == [], f"{stale} are no conftest names any more: drop them from SHADOWS"


def _requests_the_leak_guard(tree: ast.Module) -> bool:
    """The module's top-level ``pytestmark`` names the ``no_release_leak`` fixture (a bare mark or a list of marks)."""
    marks = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in n.targets)]
    return any(isinstance(c, ast.Constant) and c.value == "no_release_leak" for m in marks for c in ast.walk(m.value))


@pytest.mark.parametrize("stem", ADOPTERS)
def test_adopter_keeps_the_leak_guard_on(stem):
    assert _requests_the_leak_guard(_tree(stem)), f"tests/{stem}.py: pytestmark must request the no_release_leak fixture"


def test_every_module_on_the_leak_guard_is_an_adopter():
    """The other direction, so ``ADOPTERS`` cannot fall behind: a module that switches the guard on, or overrides
    ``release_leak_extra`` (an override the guard never calls is a watch that never runs), stands on the list."""
    guarded = {stem for stem in TEST_FILES
               if _requests_the_leak_guard(_tree(stem)) or "release_leak_extra" in _top_level_names(_tree(stem))}
    unlisted = sorted(guarded - set(ADOPTERS))
    assert unlisted == [], (f"{unlisted} request no_release_leak / override release_leak_extra but are not on ADOPTERS: "
                            "add the stem there, so dropping the guard later is red (#605)")


def test_foreign_first_puts_the_native_release_last():
    assert sorted(C.FOREIGN_FIRST) == sorted(C.CERTIFIED_YEARS)
    assert C.FOREIGN == [y for y in C.CERTIFIED_YEARS if y != V.LATEST_RELEASE]   # the order the per-file copies had
    if V.LATEST_RELEASE in C.CERTIFIED_YEARS:
        assert C.FOREIGN_FIRST[-1] == V.LATEST_RELEASE


def test_native_and_ladder_constants_snapshot_what_a_context_rebinds():
    plain, ladder = C.native_constants(), C.ladder_constants()
    table = V.framing_table(V.LATEST_RELEASE)
    assert plain == dict(table, active_release=None)
    assert set(ladder) == {"iter_records", "adoc_decoder", "family_end_record"} and not set(ladder) & set(plain)


def test_context_constants_snapshot_what_the_write_side_swaps(pin):
    from rvt.frontdoor import release_ctx as RC
    before = C.context_constants()                                # spelled out like the ladder row: a dropped watch is red HERE
    assert set(before) == {"RC._REFUSED", "MU.CLASS_ELEMENT_HEADER", "MU.CLASS_SWALL", "MU.CLASS_FAMILY_INSTANCE",
                           "GSK.minimal_history", "GSK.minimal_elemtable", "GSK._SCHEMA_CACHE",
                           "SA.bundled_base_path", "SA.family_instance_template", "SA._SCHEMA_STATE"}
    assert not set(before) & (set(C.native_constants()) | set(C.ladder_constants()))   # additive: nothing shadowed
    with RC.host_release_context(pin) as info:                    # a foreign pin swaps them; the native pin enters nothing
        inside = C.context_constants()
        swapped = {k for k in before if inside[k] != before[k]}
        if info is None:
            assert swapped == set()
        else:                                                     # every swapped NAME moves (the two registries need not)
            assert swapped >= set(before) - {"RC._REFUSED", "GSK._SCHEMA_CACHE"}, sorted(set(before) - swapped)
    assert C.context_constants() == before                        # and the LIFO restore puts every one back


def test_damage_recipes_are_what_their_names_say():
    raw = bytes(range(256)) * 16                                  # 4 KiB
    hz = C.zero_partition_header(raw)
    assert len(hz) == len(raw) and hz[:16] == bytes(16) and hz[16:] == raw[16:]
    sz = C.zero_schema_bytes(raw)
    assert len(sz) == len(raw) and sz[2000:2064] == bytes(64) and sz[:2000] + sz[2064:] == raw[:2000] + raw[2064:]


def test_offset_damage_recipes_are_what_their_names_say():
    raw = bytes(range(256)) * 16                                  # 4 KiB
    sm = C.smash64(raw, 280)
    assert len(sm) == len(raw) and sm[280:344] == b"\xff" * 64 and sm[:280] + sm[344:] == raw[:280] + raw[344:]
    assert C.smash64(raw, 218) != sm and C.smash64(raw, 218)[218:282] == b"\xff" * 64
    fl = C.flip_bit(raw, 280, 2)
    assert len(fl) == len(raw) and fl[280] == raw[280] ^ 0x04 and fl[:280] + fl[281:] == raw[:280] + raw[281:]
    assert C.flip_bit(raw, 7) == raw[:7] + bytes([raw[7] ^ 0x01]) + raw[8:]          # bit 0 by default
    assert C.flip_bit(raw, -1, 7) == raw[:-1] + bytes([raw[-1] ^ 0x80])              # indexes like raw[at]
    assert C.flip_bit(fl, 280, 2) == raw                                             # an involution
    with pytest.raises(IndexError):
        C.flip_bit(raw, len(raw))


def test_pin_is_the_first_foreign_first_pin_and_streams_is_its_every_stream_raw(pin):
    from rvt.container import open_rvt
    assert pin == C.pinned_base(C.FOREIGN_FIRST[0])                                   # what the four copies resolved
    got = C.streams(pin)
    with open_rvt(pin) as doc:                                                        # the container reader as oracle
        names = [s.name for s in doc.streams()]
        assert sorted(got) == sorted(names)                                           # every stream, no storage
        assert all(got[n] == doc.raw(n) for n in names)                               # raw = still paged


def test_rewrite_stream_damages_one_stream_and_keeps_the_rest_byte_identical(pin, tmp_path):
    pname = C.partition_of(pin)
    assert pname.startswith("Partitions/")
    out = C.rewrite_stream(pin, tmp_path / "hz.rvt", pname, C.zero_partition_header)
    assert out == str(tmp_path / "hz.rvt") and os.path.isfile(out)
    before, after = C.streams(pin), C.streams(out)
    assert set(after) == set(before)
    assert after[pname] == C.zero_partition_header(before[pname]) != before[pname]
    assert all(after[p] == before[p] for p in before if p != pname)
    dropped = set(C.streams(C.rewrite_stream(pin, tmp_path / "nolatest.rvt", "Formats/Latest", None)))
    assert "Formats/Latest" not in dropped and pname in dropped
    with pytest.raises(KeyError):
        C.rewrite_stream(pin, tmp_path / "never.rvt", "No/Such/Stream", C.zero_partition_header)
    assert not os.path.exists(tmp_path / "never.rvt")


def test_rewrite_streams_damages_drops_and_appends_in_one_pass(pin, tmp_path):
    pname = C.partition_of(pin)
    twin = C.twin_partition_entry(pin, C.zero_partition_header)
    head, n = pname.rsplit("/", 1)
    assert twin.path == "%s/%d" % (head, int(n) + 1) and twin.entry_type == "stream"
    before = C.streams(pin)
    assert twin.path not in before and twin.data == C.zero_partition_header(before[pname])
    assert C.twin_partition_entry(pin).data == before[pname]                          # no damage = verbatim
    out = C.rewrite_streams(pin, tmp_path / "multi.rvt",
                            {pname: lambda raw: C.smash64(raw, 280), "Formats/Latest": None}, extra=[twin])
    assert out == str(tmp_path / "multi.rvt")
    after = C.streams(out)
    assert set(after) == (set(before) - {"Formats/Latest"}) | {twin.path}
    assert after[pname] == C.smash64(before[pname], 280) and after[twin.path] == twin.data
    assert all(after[p] == before[p] for p in before if p not in (pname, "Formats/Latest"))
    with open(C.rewrite_streams(pin, tmp_path / "same.rvt", {}), "rb") as a, \
            open(C.rewrite_stream(pin, tmp_path / "same1.rvt", pname, lambda raw: raw), "rb") as b:
        assert a.read() == b.read()                                                   # ONE loop behind both
    with pytest.raises(KeyError):
        C.rewrite_streams(pin, tmp_path / "never.rvt", {pname: None, "No/Such/Stream": None})
    assert not os.path.exists(tmp_path / "never.rvt")


def test_truncated_and_header_zeroed_copies(pin, tmp_path):
    t = C.truncated_copy(pin, tmp_path / "t64k.rvt", 65536)
    with open(pin, "rb") as fh:
        head = fh.read(65536)
    with open(t, "rb") as fh:
        assert fh.read() == head
    z = C.cfb_header_zeroed_copy(pin, tmp_path / "cfb_zeroed.rvt")
    assert os.path.getsize(z) == os.path.getsize(pin)
    with open(z, "rb") as fh:
        assert fh.read(512) == bytes(512) and fh.read(65536 - 512) == head[512:]
