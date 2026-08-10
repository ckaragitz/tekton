"""#548: ``rvt.estorage`` walks seq-102 records with the walker IN FORCE.

``records32.ids32()`` (the Revit <= 2023 32-bit-id era) rebinds
``iter_records`` BY NAME on the modules its ``_patch_table`` lists.
``estorage`` is not listed, and until #548 it held its own module-level
``from .objects import iter_records`` -- a by-value copy the context could
not reach, so the Extensible-Storage entity walk of a 2023 file ran the
64-bit walker (wrong offsets: entities missed or mis-read).  It now reads
``O.iter_records`` through ``rvt.objects`` at CALL time.

Doors (all SYNTHETIC, packed here from docs/writer/format-2023.md; no
Autodesk bytes -- fresh-clone safe):
  1. binding: no ``iter_records`` value lives in ``vars(rvt.estorage)``; the
     name estorage calls resolves to ``iter_records32`` inside ``ids32()`` and
     to the 64-bit walker before and after;
  2. behaviour: a 32-bit segment walked through the estorage entry point
     ``harvest_token_guids`` under ``ids32()`` visits exactly the records
     ``iter_records32`` yields -- and outside the context it does NOT (the
     matched fail half: the fixture discriminates the two eras);
  3. import order (the #455 shape, fresh interpreter): a process whose FIRST
     ``import rvt.estorage`` happens inside ``ids32()`` still walks 64-bit
     records correctly after the context exits -- the old by-value copy taken
     at that moment would have frozen ``iter_records32`` for the process.
"""
import json
import os
import struct
import subprocess
import sys
import textwrap
import zlib
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import estorage as ES                                      # noqa: E402
from rvt.versions import records32 as R32                           # noqa: E402


EXPECTED = [(0x0576, b"\x01\x02\x03"), (0x0819, b"")]   # (class_id, body) of the two elements


def _rec(id_fmt: str, eid: int, cls: int, body: bytes) -> bytes:
    """One seq-102 record: <id> u32 stamp u32 psize + u16 class + body + u32 psize."""
    payload = struct.pack("<H", cls) + body
    stamp = zlib.adler32(payload) & 0xFFFFFFFF
    return struct.pack(id_fmt + "II", eid, stamp, len(payload)) + payload + struct.pack("<I", len(payload))


def seg(id_fmt: str) -> bytes:
    """The two EXPECTED elements (ids 4096, 4097) + a save-unit sentinel, ids packed as ``id_fmt``."""
    recs = b"".join(_rec(id_fmt, 4096 + i, cls, body) for i, (cls, body) in enumerate(EXPECTED))
    return recs + struct.pack(id_fmt + "II", -1, 1, 0) + struct.pack("<I", 0)


SEG32, SEG64 = seg("<i"), seg("<q")           # the 2023 era / the 2024+ era


class RecordingDecoder:
    """Stands in for the ObjectDecoder: records what the walk hands it and
    reports every record clean, so harvest_token_guids just moves on."""
    def __init__(self):
        self.seen = []

    def decode_record(self, class_id, payload):
        self.seen.append((class_id, bytes(payload)))
        return SimpleNamespace(clean=True, stub=False, errors=[])


def _walk_through_estorage(seg: bytes):
    dec = RecordingDecoder()
    assert ES.harvest_token_guids(seg, dec) == {}       # all "clean": no GUIDs harvested
    return dec.seen


def test_estorage_holds_no_by_value_copy_and_resolves_the_walker_in_force():
    assert "iter_records" not in vars(ES)
    assert ES.O.iter_records is not R32.iter_records32     # the name estorage calls, at rest
    with R32.ids32():
        assert ES.O.iter_records is R32.iter_records32     # ... inside the 32-bit era
    assert ES.O.iter_records is not R32.iter_records32     # ... and restored after it


def test_estorage_walks_a_32bit_segment_like_iter_records32_under_ids32():
    want = [(r.class_id, r.payload) for r in R32.iter_records32(SEG32, 102) if r.elem_id >= 0]
    assert want == EXPECTED                             # the sentinel is skipped
    with R32.ids32():
        assert _walk_through_estorage(SEG32) == want
    # matched fail half: the same bytes through the 64-bit walker are NOT those records
    assert _walk_through_estorage(SEG32) != want
    # and the 64-bit era is untouched at rest
    assert _walk_through_estorage(SEG64) == EXPECTED


def test_first_import_inside_ids32_does_not_freeze_the_32bit_walker():
    """Fresh interpreter: ``rvt.estorage`` is first imported INSIDE ``ids32()``;
    after the context exits a 64-bit segment must walk exactly as it does in
    this process (import outside any context), and a 32-bit one must not."""
    code = textwrap.dedent(f"""
        import json, sys
        sys.path.insert(0, {os.path.join(ROOT, "src")!r})
        sys.path.insert(0, {os.path.join(ROOT, "tests")!r})
        from rvt.versions import records32 as R32
        with R32.ids32():
            assert "rvt.estorage" not in sys.modules, "imported before the door"
            import rvt.estorage                      # FIRST import, inside the 32-bit era
            import test_estorage_ids32 as T
            inside = T._walk_through_estorage(T.SEG32)
        after64 = T._walk_through_estorage(T.SEG64)
        after32 = T._walk_through_estorage(T.SEG32)
        enc = lambda seen: [[c, p.hex()] for c, p in seen]
        print(json.dumps({{"inside": enc(inside), "after64": enc(after64), "after32": enc(after32)}}))
    """)
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=ROOT, timeout=120)
    assert res.returncode == 0, res.stderr
    got = json.loads(res.stdout.strip().splitlines()[-1])
    expected = [[c, p.hex()] for c, p in EXPECTED]
    assert got["inside"] == expected                     # 32-bit walk inside the context
    assert got["after64"] == expected                    # 64-bit walk restored after it (== in-process, door 2)
    assert got["after32"] != expected                    # ... and really the 64-bit walker
