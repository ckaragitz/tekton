"""#455: ``rvt.manipulate`` frames re-emitted blocks with the tags in force in
``rvt.partitions`` at CALL time -- not with by-value copies taken at import.

The bug: ``from .partitions import BLOCK_TAG, TRAILER_TAG`` froze whatever
release context the process's FIRST ``import rvt.manipulate`` happened to sit
in.  ``rvt.versions.records32.reading32`` on a <= 2023 file imports it inside
one (``ids32() -> _patch_table``), and so does a validator/context that holds
``enter_own_release`` on a 2024 base while something imports the edit layer;
after that every 2026 ``commit_plans`` / ``commit_session`` in the process
wrote 2024/2023 block tags and died on its own re-walk (``walker errors after
re-emit: unexpected tag 0x0e7c``).  Only import ORDER hid it (in the suite:
``tests/test_objects_plans.py`` before ``tests/test_manipulate.py``).

Each case runs in a FRESH interpreter (subprocess) so the import inside the
context really is the process's first; then a set-level edit of the bundled
2026 base must re-emit clean, validate with 0 errors, carry 2026 tags on
disk, and be byte-identical to the same edit made by a process that imported
``rvt.manipulate`` outside any context (this pytest process).  Fresh-clone
safe: needs only ``plugin/assets/genesis`` (no samples/).
"""
import json
import os
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASE_2026 = os.path.join(GEN, "G_ABPD.rvt")
BASE_2024 = os.path.join(GEN, "G_ABPD_2024.rvt")
LEVEL_ID = 1351691                     # "GEN B1 - Basement", present in every G_ABPD base
ELEVATION_FT = 12.0

needs_bases = pytest.mark.skipif(
    not (os.path.isfile(BASE_2026) and os.path.isfile(BASE_2024)),
    reason="bundled genesis bases missing")

#: how the non-2026 context is entered before the first import -- the three
#: doors real code and the suite go through
CONTEXTS = {
    # rvt.versions.reading(<2024 file>): the plain by-name framing context
    "reading-2024": """
        from rvt import versions as V
        with V.reading(BASE_2024):
            import rvt.manipulate                       # FIRST import, 2024 tags in force
            inside = P.BLOCK_TAG
    """,
    # the validator's own-release ladder (what test_objects_plans' corpus
    # fixture holds while the ids32 walk imports the edit layer)
    "enter_own_release-2024": """
        from contextlib import ExitStack
        from rvt.validate import enter_own_release
        with ExitStack() as st:
            enter_own_release(st, BASE_2024)
            import rvt.manipulate
            inside = P.BLOCK_TAG
    """,
    # reading32 on a 2023 file == reading(2023 framing) + ids32(), whose
    # _patch_table imports rvt.manipulate itself -- no explicit import here
    "reading-2023+ids32": """
        from rvt import versions as V
        from rvt.versions import records32
        with V.reading(year=2023):
            with records32.ids32():
                inside = P.BLOCK_TAG
            assert "rvt.manipulate" in sys.modules, "ids32() no longer imports rvt.manipulate?"
    """,
}

SCRIPT = """
import json, os, struct, sys
sys.path.insert(0, os.path.join(ROOT, "src"))
from rvt import partitions as P
assert "rvt.manipulate" not in sys.modules, "rvt.manipulate imported before the context"
{enter}
from rvt import manipulate as M, versions as V
from rvt.container import open_rvt
from rvt.mutate import Document
from rvt.partitions import StreamWalker
from rvt.validate import validate_file

t26 = V.framing_table(V.LATEST_RELEASE)
assert inside != t26["BLOCK_TAG"], "the context was not in force around the first import"
at_rest = {{"P": [P.BLOCK_TAG, P.TRAILER_TAG], "M": [M.BLOCK_TAG, M.TRAILER_TAG]}}

doc = Document.from_file(BASE_2026)
plan = M.set_level_elevation(doc, LEVEL_ID, ELEVATION_FT)
M.commit_plans(BASE_2026, OUT, [plan])          # raised 'unexpected tag 0x0e7c' before #455
v = M.verify_manipulated(OUT, edited_ids=[LEVEL_ID])
rep = validate_file(OUT).to_json()
with open_rvt(OUT) as d:
    w = StreamWalker(d.logical(d.partition_streams()[0]), inflate=False, keep_data=False)
    tags = sorted({{struct.unpack_from("<H", w.raw, b.hdr_offset)[0] for b in w.blocks}})
print(json.dumps({{
    "inside": inside, "at_rest": at_rest, "t26": t26,
    "walker_errors": v["walker_errors"], "crc_failures": v["crc_failures"],
    "ecc_mismatches": v["ecc_mismatches"], "stamps_ok": v["stamps_ok"],
    "edited_clean": all(x["clean"] for x in v["edited"][str(LEVEL_ID)].values()),
    "rewalk_errors": w.errors[:3], "block_tags_on_disk": tags,
    "validation_errors": [f for f in rep["findings"] if f.get("severity") == "error"][:5],
}}))
"""


def _run_fresh(context: str, out: str) -> dict:
    consts = dict(ROOT=ROOT, BASE_2026=BASE_2026, BASE_2024=BASE_2024,
                  LEVEL_ID=LEVEL_ID, ELEVATION_FT=ELEVATION_FT, OUT=out)
    head = "".join(f"{k} = {v!r}\n" for k, v in consts.items())
    src = head + SCRIPT.format(enter=textwrap.dedent(CONTEXTS[context]))
    cp = subprocess.run([sys.executable, "-c", src], cwd=ROOT,
                        capture_output=True, text=True, timeout=600)
    assert cp.returncode == 0, f"fresh interpreter failed ({context}):\n{cp.stderr[-4000:]}"
    return json.loads(cp.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def in_process_edit(tmp_path_factory):
    """The same edit made by THIS process, whose rvt.manipulate import sits
    outside any release context -- the certified lineage's byte reference."""
    from rvt import manipulate as M
    from rvt.mutate import Document
    out = str(tmp_path_factory.mktemp("i455") / "ref.rvt")
    doc = Document.from_file(BASE_2026)
    M.commit_plans(BASE_2026, out, [M.set_level_elevation(doc, LEVEL_ID, ELEVATION_FT)])
    with open(out, "rb") as fh:
        return fh.read()


@needs_bases
@pytest.mark.parametrize("context", sorted(CONTEXTS))
def test_first_import_inside_a_foreign_context_still_emits_2026_tags(context, tmp_path,
                                                                     in_process_edit):
    out = str(tmp_path / "edit2026.rvt")
    r = _run_fresh(context, out)
    t26 = r["t26"]
    # the context restored rvt.partitions, and manipulate's at-rest handles
    # are the 2026 table whatever context its import sat in
    assert r["at_rest"]["P"] == [t26["BLOCK_TAG"], t26["TRAILER_TAG"]]
    assert r["at_rest"]["M"] == [t26["BLOCK_TAG"], t26["TRAILER_TAG"]]
    # the 2026 edit re-emitted clean and carries 2026 block tags on disk
    assert r["walker_errors"] == 0 and not r["rewalk_errors"]
    assert r["crc_failures"] == 0 and r["ecc_mismatches"] == 0 and r["stamps_ok"]
    assert r["edited_clean"]
    assert r["block_tags_on_disk"] == [t26["BLOCK_TAG"]]
    assert r["validation_errors"] == []
    # and not one written byte differs from the import-outside-a-context lineage
    with open(out, "rb") as fh:
        assert fh.read() == in_process_edit


def test_emit_block_reads_partitions_at_call_time():
    """The unit-level law: whatever rvt.partitions says NOW is what a block
    is framed with (and restored tags frame 2026 again)."""
    import struct

    from rvt import manipulate as M
    from rvt import partitions as P
    from rvt import versions as V
    blk = {"payload": b"\x00" * 32, "flags": 4, "A": 1, "C": 12}
    for year in sorted(V.KNOWN_RELEASES):
        t = V.framing_table(year)
        with V.reading(year=year):
            raw = M._emit_block(blk, 102)
            assert struct.unpack_from("<H", raw, 0)[0] == t["BLOCK_TAG"] == P.BLOCK_TAG
            assert struct.unpack_from("<H", raw, len(raw) - 6)[0] == t["TRAILER_TAG"]
    t26 = V.framing_table(V.LATEST_RELEASE)
    raw = M._emit_block(blk, 102)
    assert struct.unpack_from("<H", raw, 0)[0] == t26["BLOCK_TAG"] == M.BLOCK_TAG
    assert struct.unpack_from("<H", raw, len(raw) - 6)[0] == t26["TRAILER_TAG"] == M.TRAILER_TAG
