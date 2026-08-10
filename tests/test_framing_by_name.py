"""#467 (Refs #455): no module under ``src/rvt`` keeps a BY-VALUE copy of a
name a release context rebinds BY NAME.

Block framing (``BLOCK_TAG`` / ``TRAILER_TAG``) lives in ``rvt.partitions``;
``rvt.versions.reading()`` rebinds it there per release and every project-side
block emitter -- ``reduce.NewBlock.frame``, ``writer.regzip_partition_logical``,
``commit``, ``manipulate._emit_block``, ``families._rebuild_partition_logical``,
``mep.conduit`` -- reads it at CALL time.  Before #467 ``reduce`` / ``writer``
held 2026 literals (``BLOCK_TAG = 0x0F28``, ``BLOCK_TRL_TAG = 0x0F21``) and
``commit`` / ``families`` / ``conduit`` from-imported the latter; only the
front door's ``release_ctx`` and the owner-machine genesis drivers knew to swap
each copy, so the engine's OWN release ladder (``validate.enter_own_release``
== ``versions.reading`` + ``global_framing.bound``) re-blocked a 2025/2024 file
with 2026 tags: ``reduce.delete_elements`` died on its post-emit walk
(``walker errors after re-block: unexpected tag 0x0f28``) and
``writer.build_variant`` silently wrote ``0x0f21`` trailers into a 2025 file.

The 32-bit-id era is the same class one layer down: ``records32.ids32()``
rebinds ``encode_record`` / ``record_bytes`` / ``decode_elemtable`` /
``_assert_sentinel_tail`` / ... by name on the modules its patch table lists,
so a module-level ``from .encode import encode_record`` in a module the table
does NOT list keeps the 64-bit variant under it.

Fresh-clone safe: needs only ``plugin/assets/genesis``.
"""
from __future__ import annotations

import ast
import functools
import json
import os
import struct
import subprocess
import sys
import textwrap

import pytest
from conftest import ROOT, pinned_base          # the certified pinned base of a year, or a clean skip

from rvt import partitions as P
from rvt import versions as V

SRC = os.path.join(ROOT, "src", "rvt")
LEVEL_ID = 1351691                     # "GEN B1 - Basement", present in every G_ABPD base


def _tags(raw: bytes) -> tuple:
    """(header tag, trailer tag) of ONE framed block."""
    return struct.unpack_from("<H", raw)[0], struct.unpack_from("<H", raw, len(raw) - 6)[0]


def _stream_tags(logical: bytes) -> tuple[set, set, list]:
    """({header tags}, {trailer tags}, walker errors) of a partition stream,
    walked with whatever framing is in force NOW."""
    w = P.StreamWalker(logical, inflate=False, keep_data=False)
    hdr = {struct.unpack_from("<H", logical, b.hdr_offset)[0] for b in w.blocks}
    trl = {struct.unpack_from("<H", logical, b.member_offset + b.member_len)[0] for b in w.blocks}
    return hdr, trl, list(w.errors)


# ---------------------------------------------------------------------------
# 1. unit law: every emitter follows a bare versions.reading() -- no swap list
# ---------------------------------------------------------------------------
def test_newblock_frame_follows_the_reading_context_for_every_release():
    from rvt import reduce as R
    blk = R.NewBlock(seq=102, flags=4, A=1, C=12, payload=b"\x00" * 32)
    for year in sorted(V.KNOWN_RELEASES):
        t = V.framing_table(year)
        with V.reading(year=year):
            assert _tags(blk.frame()) == (t["BLOCK_TAG"], t["TRAILER_TAG"]) \
                == (P.BLOCK_TAG, P.TRAILER_TAG), year
    t26 = V.framing_table(V.LATEST_RELEASE)
    assert _tags(blk.frame()) == (t26["BLOCK_TAG"], t26["TRAILER_TAG"]) == (P.BLOCK_TAG, P.TRAILER_TAG)


def test_writer_trailer_tag_is_an_access_time_alias_not_a_copy():
    """``writer.BLOCK_TRL_TAG`` still resolves (famgen.geometry's call-time
    import spells it) but holds no value: it IS rvt.partitions.TRAILER_TAG."""
    from rvt import writer as W
    assert "BLOCK_TRL_TAG" not in vars(W), "writer took a by-value copy again"
    for year in sorted(V.KNOWN_RELEASES):
        with V.reading(year=year):
            from rvt.writer import BLOCK_TRL_TAG          # what a call-time import sees
            assert BLOCK_TRL_TAG == W.BLOCK_TRL_TAG == P.TRAILER_TAG \
                == V.framing_table(year)["TRAILER_TAG"], year
    assert W.BLOCK_TRL_TAG == V.framing_table(V.LATEST_RELEASE)["TRAILER_TAG"]
    with pytest.raises(AttributeError):
        W.NO_SUCH_NAME                                    # the alias is exact, not a catch-all


def test_no_module_keeps_the_retired_tag_handles():
    from rvt import commit, families, manipulate, reduce
    from rvt.mep import conduit
    for mod in (reduce, manipulate, commit, families, conduit):
        for name in ("BLOCK_TAG", "TRAILER_TAG", "BLOCK_TRL_TAG", "FOOTER_TAG"):
            assert name not in vars(mod), f"{mod.__name__}.{name} is a by-value copy"


@pytest.mark.parametrize("year", [2025, 2024])
def test_regzip_and_rebuild_follow_the_files_own_release(year):
    """writer.regzip_partition_logical + families._rebuild_partition_logical
    on a 2025/2024 base under a BARE versions.reading(base): the re-emitted
    stream walks clean under that release and carries only its tags."""
    from rvt import families as F
    from rvt import writer as W
    from rvt.container import open_rvt
    base = pinned_base(year)
    t = V.framing_table(year)
    with V.reading(base), open_rvt(base) as d:
        name = d.partition_streams()[0]
        logical = d.logical(name)
        out_w = W.regzip_partition_logical(d, name)
        walker = P.StreamWalker(logical, inflate=True, keep_data=True)
        assert not walker.errors
        out_f = F._rebuild_partition_logical(logical, walker, {}, 3)
        for out in (out_w, out_f):
            hdr, trl, errs = _stream_tags(out)
            assert errs == [] and hdr == {t["BLOCK_TAG"]} and trl == {t["TRAILER_TAG"]}
        # payloads untouched: inflating the re-emitted stream gives the base's data
        w2 = P.StreamWalker(out_w, inflate=True, keep_data=True)
        assert [b.data for b in w2.blocks] == [b.data for b in walker.blocks]


# ---------------------------------------------------------------------------
# 2. fresh interpreters: import order can neither freeze nor rescue a tag
# ---------------------------------------------------------------------------
PRELUDE = """
import json, os, struct, sys
from contextlib import ExitStack
sys.path.insert(0, os.path.join(ROOT, "src"))
from rvt import partitions as P, versions as V
for m in ("rvt.reduce", "rvt.writer", "rvt.commit", "rvt.families", "rvt.manipulate"):
    assert m not in sys.modules, m + " imported before the door"

def tags_of(path):
    from rvt.container import open_rvt
    from rvt.validate import enter_own_release
    with ExitStack() as st:
        enter_own_release(st, path)
        with open_rvt(path) as d:
            raw = d.logical(d.partition_streams()[0])
            w = P.StreamWalker(raw, inflate=False, keep_data=False)
            return {"hdr": sorted({struct.unpack_from("<H", raw, b.hdr_offset)[0] for b in w.blocks}),
                    "trl": sorted({struct.unpack_from("<H", raw, b.member_offset + b.member_len)[0] for b in w.blocks}),
                    "errors": list(w.errors), "in_force": [P.BLOCK_TAG, P.TRAILER_TAG]}
"""

DOORS = {
    # the #455 shape: FIRST import of every emitter inside a 2024 context,
    # then a 2026 reduce after the context closed -> 2026 tags, byte-identical
    # to the same reduce made by a process that imported them at rest
    "first-import-inside-2024-then-reduce-2026": """
        with V.reading(BASE_2024):
            import rvt.reduce, rvt.writer, rvt.commit, rvt.families, rvt.manipulate
            inside = [P.BLOCK_TAG, P.TRAILER_TAG]
        from rvt import reduce as R
        rep = R.delete_elements(BASE_2026, OUT, [LEVEL_ID])
        print(json.dumps({"inside": inside, "deleted": rep.deleted, "on_disk": tags_of(OUT),
                          "at_rest": [P.BLOCK_TAG, P.TRAILER_TAG]}))
    """,
    # the user-visible shape #467 fixes: emitters imported AT REST (2026),
    # then a 2024 file reduced under the engine's own release ladder -> must
    # frame with 2024's tags (main @ fdcbf12: RuntimeError 'walker errors
    # after re-block: unexpected tag 0x0f28')
    "import-at-rest-then-reduce-2024-under-own-release": """
        import rvt.reduce, rvt.writer, rvt.commit, rvt.families, rvt.manipulate
        from rvt import reduce as R
        from rvt.validate import enter_own_release
        with ExitStack() as st:
            note = enter_own_release(st, BASE_2024)
            inside = [P.BLOCK_TAG, P.TRAILER_TAG]
            rep = R.delete_elements(BASE_2024, OUT, [LEVEL_ID])
        print(json.dumps({"inside": inside, "note": note, "deleted": rep.deleted,
                          "on_disk": tags_of(OUT), "at_rest": [P.BLOCK_TAG, P.TRAILER_TAG]}))
    """,
}


def _run_fresh(door: str, out: str) -> dict:
    consts = dict(ROOT=ROOT, BASE_2026=pinned_base(2026), BASE_2024=pinned_base(2024),
                  LEVEL_ID=LEVEL_ID, OUT=out)
    src = ("".join(f"{k} = {v!r}\n" for k, v in consts.items())
           + PRELUDE + textwrap.dedent(DOORS[door]))
    cp = subprocess.run([sys.executable, "-c", src], cwd=ROOT,
                        capture_output=True, text=True, timeout=600)
    assert cp.returncode == 0, f"fresh interpreter failed ({door}):\n{cp.stderr[-4000:]}"
    return json.loads(cp.stdout.strip().splitlines()[-1])


def test_first_import_inside_2024_then_a_2026_reduce_frames_2026(tmp_path):
    from rvt import reduce as R
    t24, t26 = V.framing_table(2024), V.framing_table(2026)
    out = str(tmp_path / "fresh.rvt")
    r = _run_fresh("first-import-inside-2024-then-reduce-2026", out)
    assert r["inside"] == [t24["BLOCK_TAG"], t24["TRAILER_TAG"]]
    assert r["at_rest"] == [t26["BLOCK_TAG"], t26["TRAILER_TAG"]]
    assert r["deleted"] == 1
    assert r["on_disk"] == {"hdr": [t26["BLOCK_TAG"]], "trl": [t26["TRAILER_TAG"]],
                            "errors": [], "in_force": [t26["BLOCK_TAG"], t26["TRAILER_TAG"]]}
    # byte-identical to the same reduce made by THIS process (imports at rest)
    ref = str(tmp_path / "ref.rvt")
    R.delete_elements(pinned_base(2026), ref, [LEVEL_ID])
    with open(out, "rb") as a, open(ref, "rb") as b:
        assert a.read() == b.read()


def test_a_2024_file_reduced_under_its_own_release_frames_2024(tmp_path):
    t24, t26 = V.framing_table(2024), V.framing_table(2026)
    r = _run_fresh("import-at-rest-then-reduce-2024-under-own-release", str(tmp_path / "r24.rvt"))
    assert r["note"] is None                       # the schema rung resolved the release
    assert r["inside"] == [t24["BLOCK_TAG"], t24["TRAILER_TAG"]]
    assert r["deleted"] == 1
    assert r["on_disk"] == {"hdr": [t24["BLOCK_TAG"]], "trl": [t24["TRAILER_TAG"]],
                            "errors": [], "in_force": [t24["BLOCK_TAG"], t24["TRAILER_TAG"]]}
    assert r["at_rest"] == [t26["BLOCK_TAG"], t26["TRAILER_TAG"]]


# ---------------------------------------------------------------------------
# 3. source laws: the class cannot come back unnoticed
# ---------------------------------------------------------------------------
#: famgen is fenced this wave (its literals + release_ctx's FSK swap rows stay
#: until #547, the famgen follow-up of #467); nothing else may hold a copy
FENCED_DIRS = ("famgen",)
FRAMING_NAMES = {"BLOCK_TAG", "TRAILER_TAG", "FOOTER_TAG", "BLOCK_TRL_TAG"}
FRAMING_VALUES = {v for y in V.KNOWN_RELEASES for k, v in V.framing_table(y).items()
                  if k in ("BLOCK_TAG", "TRAILER_TAG", "FOOTER_TAG")}


@functools.lru_cache(maxsize=None)
def _modules() -> tuple:
    """((repo-relative path, parsed module), ...) for src/rvt minus the fence
    -- parsed once for both source laws."""
    out = []
    for dirpath, _dirs, files in os.walk(SRC):
        rel = os.path.relpath(dirpath, SRC)
        if rel.split(os.sep)[0] in FENCED_DIRS or "__pycache__" in rel:
            continue
        for f in sorted(files):
            if f.endswith(".py"):
                path = os.path.join(dirpath, f)
                with open(path, encoding="utf-8") as fh:
                    out.append((os.path.relpath(path, ROOT), ast.parse(fh.read())))
    return tuple(out)


def test_no_by_value_copy_of_a_block_framing_name_outside_partitions():
    """No ``from .partitions/.writer import <TAG>`` (any depth) and no
    module-level ``<NAME>_TAG = <a framing ordinal>`` literal anywhere but
    rvt/partitions.py itself (the versions tables are dict literals, fine).
    Deliberately the two shapes this class has taken so far, not every way to
    bake an ordinal (an inline ``struct.pack("<H", 0x0F28)`` would pass here);
    the behavioural doors above are what catch a wrong byte."""
    offenders = []
    for rel, tree in _modules():
        if rel.replace(os.sep, "/") == "src/rvt/partitions.py":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] in ("partitions", "writer"):
                for a in node.names:
                    if a.name in FRAMING_NAMES:
                        offenders.append(f"{rel}:{node.lineno} from {node.module} import {a.name}")
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                    and node.value.value in FRAMING_VALUES:
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id.endswith("_TAG"):
                        offenders.append(f"{rel}:{node.lineno} {tgt.id} = {node.value.value:#06x}")
    assert offenders == [], "by-value block-framing copies:\n" + "\n".join(offenders)


#: (rel_path, name) pairs knowingly exempt from the law below -- none
KNOWN_RESIDUAL_IDS32: set = set()


def test_every_module_level_copy_of_an_ids32_patched_name_is_a_listed_holder():
    """``records32._patch_table`` rebinds names per HOLDING module; a
    module-level from-import of such a name in a module the table does not
    list is a by-value copy the 32-bit era cannot reach.  Computed against
    the live table, so a new holder or a new patched name is judged too."""
    from rvt.versions import records32
    patched: dict[str, set[str]] = {}           # attr -> {holder module names}
    for holder, attr, _repl in records32._patch_table():
        if isinstance(holder, type(os)):        # module holders only (classes patch methods)
            patched.setdefault(attr, set()).add(holder.__name__)
    offenders = []
    for rel, tree in _modules():
        mod = "rvt." + rel.replace(os.sep, "/")[len("src/rvt/"):-3].replace("/", ".")
        mod = mod[:-len(".__init__")] if mod.endswith(".__init__") else mod
        for node in tree.body:                  # module level only: call-time imports see the live binding
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                for a in node.names:
                    name = a.asname or a.name
                    if a.name in patched and mod not in patched[a.name] \
                            and (rel.replace(os.sep, "/"), a.name) not in KNOWN_RESIDUAL_IDS32:
                        offenders.append(f"{rel}:{node.lineno} from {'.' * node.level}{node.module or ''} "
                                         f"import {a.name}{' as ' + name if a.asname else ''} "
                                         f"(holders: {sorted(patched[a.name])})")
    assert offenders == [], "unlisted by-value copies of ids32-patched names:\n" + "\n".join(offenders)


def test_electrical_data_and_regadd_read_the_ids32_names_through_their_modules():
    """The two modules #467 names: no copies at rest, and under ids32() the
    functions they will call ARE the 32-bit variants."""
    from rvt import commit, encode, reduce, regadd, stream_encoders
    from rvt.mep import electrical_data as ED
    from rvt.versions import records32
    for name in ("decode_elemtable", "encode_elemtable", "_assert_sentinel_tail"):
        assert name not in vars(ED), f"electrical_data.{name} is a by-value copy"
    for name in ("encode_record", "record_bytes", "verify_reduced"):
        assert name not in vars(regadd), f"regadd.{name} is a by-value copy"
    assert ED.SE is stream_encoders and ED._commit is commit
    assert regadd.E is encode and regadd._reduce is reduce
    at_rest = (stream_encoders.decode_elemtable, encode.encode_record, encode.record_bytes,
               reduce.verify_reduced, commit._assert_sentinel_tail)
    with records32.ids32():
        inside = (ED.SE.decode_elemtable, regadd.E.encode_record, regadd.E.record_bytes,
                  regadd._reduce.verify_reduced, ED._commit._assert_sentinel_tail)
        assert all(a is not b for a, b in zip(inside, at_rest)), "ids32 did not reach a name"
    assert (stream_encoders.decode_elemtable, encode.encode_record, encode.record_bytes,
            reduce.verify_reduced, commit._assert_sentinel_tail) == at_rest
