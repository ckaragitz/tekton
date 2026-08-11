"""test_estorage_catalog_2024.py -- the Extensible-Storage catalog reader
knows the Revit <= 2024 layout (issue #576, Refs #566 / #548).

The bundled 2024 base's own ``Formats/Latest`` has no ``SchemaUsageInfo``
class; its ``ESSchemaStorage`` keeps the catalog in ``m_storedSchemas :
container< std::pair< GUIDvalue, ESSchema > >`` (the value IS the schema)
where 2025+ files keep ``m_schemaUsageMap : container< std::pair< GUIDvalue,
SchemaUsageInfo > >``.  ``rvt.estorage`` reads which one off the file's own
``ESSchemaStorage`` (``catalog_layout``) and decodes either against the
file's own schema.  Rows:

* the 2024 pin: layout ``m_storedSchemas``; ``schemas()`` = the two schemas
  the 2025/2026 pins also carry (GUIDs, names, fields), ``note == ""``,
  ``used_in_host is None`` (that layout does not record it), tracking 6 / 1
  elements -- and the CLI lists them (main: an honest ``0 schemas (...)``);
* the 2025/2026 pins: layout ``m_schemaUsageMap``; catalog byte-for-byte
  what ``main`` read (entry count + a digest of ``to_json()``);
* GUID-free location and backward chaining on the OLDER layout, on bytes
  re-encoded by our own encoder around junk (no seed / a seed on the LAST
  entry only must recover the whole map and its count offset);
* synthetic schemas: the layout is the one the file's ``ESSchemaStorage``
  holds (both pair classes may exist), none without it (and the empty-catalog
  note says what the file keeps); both catalog value shapes unwrap;
* the ``EStorageTracking`` table (issue #595): on the 2024 pin it is 7 items
  led by 5 GUIDs that are in no catalog -- ``locate_tracking`` walks back
  over them and VERIFIES the table by its leading count (offset = the count
  u32, ``tracking_count == 7``), the five are exposed as
  ``tracking_uncatalogued`` with their ids and named by the CLI, the generic
  decoder reading the file's own ``EStorageTracking`` class over the same
  bytes agrees item for item; the 2025/2026 pins' tracking reads exactly as
  on ``main`` (2 items, nothing uncatalogued, header unchanged); synthetic
  tables: leading/trailing uncatalogued items, a false backward tiling that
  even meets the count, a wrong count (the unverified fallback), are each
  read for what they are.

Bundled bases only (fresh-clone safe).
Run: .venv/bin/python -m pytest tests/test_estorage_catalog_2024.py -q
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import CERTIFIED_YEARS, ladder_constants, pinned_base   # noqa: E402
from rvt import estorage as ES                                    # noqa: E402
from rvt import global_framing as GF                              # noqa: E402
from rvt.encode import ObjectEncoder                              # noqa: E402
from rvt.schema import Schema                                     # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")           # every catalog is read under GF.reading in-process


@pytest.fixture
def release_leak_extra():
    """``GF.reading`` climbs the instrument ladder: watch what it swaps, too."""
    return ladder_constants


OLD = [y for y in CERTIFIED_YEARS if y <= 2024]
NEW = [y for y in CERTIFIED_YEARS if y >= 2025]

# the two schemas every bundled base carries (inherited from the seed project)
AREX = "4c817959-0028-4a83-b3e7-cd1e832a459a"
DAYLIGHT = "5d9588ee-e6c7-4c96-87dc-df2a5fbe6613"
EXPECTED = {
    AREX: ("AREXContentGenerator", "", [("Identity", "TCHAR")], 6),
    DAYLIGHT: ("DaylightingAnalysisInfo", "ADSK", [("AnalysisId", "TCHAR"), ("ResultsInvalid", "int")], 1),
}
# 2025+/2026 catalogs as `main` read them: (schemas, map count, sha256[:16] of to_json() minus 'source').
# #595 added two keys to to_json() ('tracking_count', 'tracking_uncatalogued'); PRE_595 is the digest with
# those two keys removed and must stay what #599 pinned -- everything main read, it still reads byte for byte
MAIN_DIGEST = {2025: (2, 2, "787646f8f1bbe113"), 2026: (2, 2, "786987e13fdb4bd7")}
PRE_595_DIGEST = {2025: "43f8ad756ff22977", 2026: "2d621ae50133432e"}
NEW_IN_595 = ("tracking_count", "tracking_uncatalogued")
# the 2024 pin's EStorageTracking table (#595): count u32 @0xff92e in Global/Latest, 7 items -- these
# five (in no catalog, nowhere else in the file; 49504 = the ProjectInfo element) lead the two catalogued ones
TRACKING_2024 = (0xff92e, 7)
UNCATALOGUED_2024 = [
    ("30000001-6e79-430c-adf9-634f716c5f5d", []),
    ("30000001-62e6-416d-a34a-bb3064350b62", [49504]),
    ("20000002-6e79-430c-adf9-634f716c5f5d", []),
    ("20000002-62e6-416d-a34a-bb3064350b62", [49504]),
    ("10000005-db1a-45fc-9eed-810262792b5b", []),
]


def _catalog(path: str) -> ES.ESSchemaCatalog:
    with GF.reading(path):
        return ES.schemas(path)


def _digest(cat: ES.ESSchemaCatalog, drop=()) -> str:
    j = cat.to_json()
    for k in ("source", *drop):
        j.pop(k)
    return hashlib.sha256(json.dumps(j, sort_keys=True).encode()).hexdigest()[:16]


@pytest.mark.parametrize("year", OLD)
def test_old_layout_pin_lists_its_schemas(year):
    path = pinned_base(year)
    lay = ES.catalog_layout(GF.schema_of(path))
    assert (lay.member, lay.pair_class, lay.tail) == ("m_storedSchemas", "std::pair< GUIDvalue, ESSchema >", 8)
    cat = _catalog(path)
    assert (cat.note, cat.layout) == ("", "m_storedSchemas") and cat.map_count == len(cat) == 2 and cat.map_offset > 0
    assert cat.order == [AREX, DAYLIGHT]
    for s in cat:
        name, vendor, fields, tracked = EXPECTED[s.guid]
        assert (s.name, s.vendor_id) == (name, vendor)
        assert [(f.name, f.type_name) for f in s.fields] == fields
        assert s.used_in_host is None and s.content_docs_keys == []      # not recorded by this layout: absent, not invented
        assert len(cat.tracking[s.guid]) == tracked
    assert cat.tracking[DAYLIGHT] == [1382860]


@pytest.mark.parametrize("year", OLD)
def test_old_layout_pin_cli_lists_its_schemas(year, capsys):
    path = pinned_base(year)
    assert ES.main([path, "--report"]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert "\nES schema catalog: 2 schemas (map count 2 @0x" in out and "0 schemas" not in out
    assert f"  {AREX}  'AREXContentGenerator' vendor='' usage-unrecorded fields=1 read=Public write=Public tracked_elements=6\n" in out
    assert f"  {DAYLIGHT}  'DaylightingAnalysisInfo' vendor='ADSK' usage-unrecorded fields=2 read=Public write=Vendor tracked_elements=1\n" in out
    assert "\nES report: 2 schemas\n" in out
    # the tracking table is verified, and what leads it is named -- once (#595)
    off, n = TRACKING_2024
    assert f" in Global/Latest; tracking @{off:#x}, {n} items, {len(UNCATALOGUED_2024)} uncatalogued)\n" in out
    assert "\n  uncatalogued schema GUIDs tracked by EStorageTracking (no catalog entry; name and fields unknown):\n" in out
    for g, ids in UNCATALOGUED_2024:
        assert f"\n    {g}  tracked_elements={len(ids)}" + (f" {ids}\n" if ids else "\n") in out
        assert out.count(g) == 1


def _tracking_object(path: str, cat: ES.ESSchemaCatalog):
    """The whole ``EStorageTracking`` AppInfo read by the GENERIC decoder against
    the file's own class: it begins one u32 (``AppInfo.m_pADoc``, a weak ref)
    before the item count.  -> (decoded object, its end offset in Global/Latest)."""
    gl, _ = ES._global_latest_bytes(path)
    dec = ES._decoder_for(path)
    start = cat.tracking_offset - 4
    o = dec.decode_record(dec.schema.by_name["EStorageTracking"].type_id, gl[start:])
    assert not o.errors, o.errors
    return o.value, start + o.consumed


def _table_end(cat: ES.ESSchemaCatalog) -> int:
    """Where the byte walk says the table ends: count u32 + items of 20 + 8*ids bytes."""
    items = list(cat.tracking.values()) + list(cat.tracking_uncatalogued.values())
    return cat.tracking_offset + 4 + sum(20 + 8 * len(ids) for ids in items)


@pytest.mark.parametrize("year", OLD)
def test_old_layout_pin_tracking_table_is_verified_not_guessed(year):
    """7 items @0xff92e: the five uncatalogued items are walked back over and
    kept (GUIDs + ids, table order), the count in front verifies the table,
    and the file's own ``EStorageTracking`` class decodes the same bytes to
    the same seven ``EStorageTrackingItem``s, ending where the walk ends."""
    path = pinned_base(year)
    cat = _catalog(path)
    gl, _ = ES._global_latest_bytes(path)
    assert (cat.tracking_offset, cat.tracking_count) == TRACKING_2024, (
        "the 2024 pin's tracking table moved -- if the pin was re-composed on purpose, update TRACKING_2024")
    assert struct.unpack_from("<I", gl, cat.tracking_offset)[0] == cat.tracking_count \
        == len(cat.tracking) + len(cat.tracking_uncatalogued) == 7
    assert list(cat.tracking_uncatalogued.items()) == UNCATALOGUED_2024
    assert {g: len(v) for g, v in cat.tracking.items()} == {AREX: 6, DAYLIGHT: 1} and cat.tracking[DAYLIGHT] == [1382860]
    for g, _ids in UNCATALOGUED_2024:                     # what the bytes say: once each in the whole stream, in no catalog
        assert gl.count(ES.guid_bytes(g)) == 1 and cat.get(g) is None
    # classified against the file's own schema: EStorageTracking{AppInfo.m_pADoc, m_trackingItems[7]}
    obj, end = _tracking_object(path, cat)
    items = [(it["m_schemaGuid"], it["m_elemIdSet"]) for it in obj["m_trackingItems"]]
    assert items == UNCATALOGUED_2024 + list(cat.tracking.items())
    assert end == _table_end(cat) == 0xffa06
    j = cat.to_json()
    assert (j["tracking_uncatalogued"], j["tracking"], j["tracking_count"]) == ({g: len(i) for g, i in UNCATALOGUED_2024}, {AREX: 6, DAYLIGHT: 1}, 7)


@pytest.mark.parametrize("year", NEW)
def test_new_layout_pins_tracking_reads_exactly_as_before(year):
    """2 catalogued items, verified by the count as on main; nothing
    uncatalogued, so header, JSON and report carry no new token."""
    path = pinned_base(year)
    cat = _catalog(path)
    gl, _ = ES._global_latest_bytes(path)
    assert cat.tracking_count == struct.unpack_from("<I", gl, cat.tracking_offset)[0] == len(cat.tracking) == 2
    assert (cat.tracking_uncatalogued, cat.tracking_note) == ({}, "")
    obj, end = _tracking_object(path, cat)
    assert [(it["m_schemaGuid"], it["m_elemIdSet"]) for it in obj["m_trackingItems"]] == list(cat.tracking.items())
    assert end == _table_end(cat)
    buf = io.StringIO()
    ES.print_catalog(cat, buf)
    assert buf.getvalue().startswith(f"ES schema catalog: 2 schemas (map count 2 @{cat.map_offset:#x} "
                                     f"in Global/Latest; tracking @{cat.tracking_offset:#x})\n")
    assert "uncatalogued" not in buf.getvalue() and "unverified" not in buf.getvalue()


def _item(guid: str, ids: list[int]) -> bytes:
    return ES.guid_bytes(guid) + struct.pack(f"<I{len(ids)}q", len(ids), *ids)


U1, U2, U3 = "9d1c2b3a-4e5f-4a6b-8c7d-0e1f2a3b4c5d", "0a9b8c7d-6e5f-4d3c-9b1a-2f3e4d5c6b7a", "77665544-3322-4100-8fee-ddccbbaa9988"
HEAD = b"\x07junk-before-the-table" * 3
GARBAGE = bytes(range(0x40, 0x50)) + b"\x00\x00\x00\x00" + b"\x03trailing"   # reads as one more 0-id "item", then junk


def _locate(count: int, *items: bytes, skip=(0, 0)):
    gl = HEAD + struct.pack("<I", count) + b"".join(items) + GARBAGE
    return ES.locate_tracking(gl, [AREX, DAYLIGHT], skip=skip)


def test_tracking_walk_reads_synthetic_tables_for_what_they_are():
    C1, C2 = _item(AREX, [10, 11, 12]), _item(DAYLIGHT, [13])
    table = {U1: [7], U2: [], AREX: [10, 11, 12], DAYLIGHT: [13]}
    # (a) two uncatalogued items lead: walked back over, verified by the count, kept in table order;
    #     the garbage "item" that chains after the last real one is cut off by the count
    got = _locate(4, _item(U1, [7]), _item(U2, []), C1, C2)
    assert got == (len(HEAD), 4, table) and list(got[2]) == list(table)
    # (b) the false backward tiling: U1's own tail (guid[8:16] + count 1 + low id word) reads as a 0-id
    #     item ending where U2 starts, and here the u32 in front of it (guid[4:8]) is forged to EQUAL the
    #     count that tiling would need -- the real, longer tiling of the same level still wins
    forged = ES.guid_str(ES.guid_bytes(U1)[:4] + struct.pack("<I", 4) + ES.guid_bytes(U1)[8:])
    got = _locate(4, _item(forged, [7]), _item(U2, []), C1, C2)
    assert got == (len(HEAD), 4, {forged: [7], U2: [], AREX: [10, 11, 12], DAYLIGHT: [13]})
    # (c) a trailing uncatalogued item is in the table iff the count says so
    assert _locate(3, C1, C2, _item(U3, [21, 22])) == (len(HEAD), 3, {AREX: [10, 11, 12], DAYLIGHT: [13], U3: [21, 22]})
    assert _locate(2, C1, C2, _item(U3, [21, 22])) == (len(HEAD), 2, {AREX: [10, 11, 12], DAYLIGHT: [13]})
    # (d) a count no tiling meets: nothing verified -> the longest catalogued run, offset = its start - 4, count 0
    lead = _item(U1, [7]) + _item(U2, [])
    assert _locate(9, lead, C1, C2) == (len(HEAD) + 4 + len(lead) - 4, 0, {AREX: [10, 11, 12], DAYLIGHT: [13]})
    # (e) an anchor inside `skip` is no anchor; no anchor at all is the documented triple
    assert _locate(4, lead, C1, C2, skip=(0, 1 << 30)) == (-1, 0, {})
    assert ES.locate_tracking(HEAD + GARBAGE, [AREX, DAYLIGHT]) == (-1, 0, {})
    # (f) an anchor at the very start of the stream has no count in front: unverifiable, never a wrapped read
    assert ES.locate_tracking(C1 + C2 + GARBAGE, [AREX, DAYLIGHT])[1:] == (0, {AREX: [10, 11, 12], DAYLIGHT: [13]})


def test_tracking_walk_never_verifies_a_tail_carved_pseudo_item(monkeypatch):
    """#614: only the LONGEST self-checking item ending at a node is walked to,
    so a pseudo-item carved from a real item's tail cannot count-verify on a
    shallower level than that item; the backward id scan is charged to
    ``_TRACKING_BUDGET`` and a walk that spends it verifies nothing."""
    known = {AREX: [10, 11, 12], DAYLIGHT: [13]}
    C1, C2 = (_item(g, ids) for g, ids in known.items())

    def unverified(lead: bytes):                                    # the labelled fallback: C1's start - 4, count 0
        return len(HEAD) + len(lead), 0, known
    # (g) the issue's repro: U2's last 20 bytes read as a 0-id pseudo-item ending where C1 starts and the u32 in
    #     front of THAT is the low dword of U2's third-from-last id -- 3 = exactly the count the pseudo-tiling
    #     [pseudo, C1, C2] needs, one level before the walk through U2 itself reaches U1 and the real count 4.
    #     main read (118, 3, {<phantom 00000000-... GUID>: [], AREX, DAYLIGHT}); any other small id there (40)
    #     always read right
    for third in (3, 40):
        table = {U1: [7], U2: [third, 1372292, 1372482], **known}
        got = _locate(4, *(_item(g, ids) for g, ids in table.items()))
        assert got == (len(HEAD), 4, table) and list(got[2]) == list(table)
    #     and when the real chain does NOT verify (count 9), the pseudo-tiling still must not: labelled fallback
    lead = _item(U1, [7]) + _item(U2, [3, 1372292, 1372482])
    assert _locate(9, lead, C1, C2) == unverified(lead)
    # (h) the k scan is charged to the budget: U2 with 100 ids fronts C1; its tail again reads as a pseudo-item
    #     whose leading u32 (3) would verify [pseudo, C1, C2].  Full budget: U2 is the longest candidate, the
    #     real 3-item table verifies.  A budget smaller than U2's id run: the scan stops before reaching U2's
    #     start and names NO predecessor -- the labelled unverified fallback, never the shorter "verified" table
    many = list(range(500, 597)) + [3, 1372292, 1372482]
    big = _item(U2, many)
    assert _locate(3, big, C1, C2) == (len(HEAD), 3, {U2: many, **known})
    for budget, expected in ((40, unverified(big)), (400, (len(HEAD), 3, {U2: many, **known}))):   # 400: 100 id words + slack
        monkeypatch.setattr(ES, "_TRACKING_BUDGET", budget)
        assert _locate(3, big, C1, C2) == expected


@pytest.mark.parametrize("year", NEW)
def test_new_layout_pins_read_exactly_as_before(year):
    path = pinned_base(year)
    assert ES.catalog_layout(GF.schema_of(path)).member == "m_schemaUsageMap"
    cat = _catalog(path)
    assert (cat.note, cat.layout) == ("", "m_schemaUsageMap") and all(s.used_in_host is True for s in cat)
    assert (len(cat), cat.map_count, _digest(cat)) == MAIN_DIGEST[year], (
        f"the {year} pin's catalog no longer reads as main did -- if the pin was "
        f"re-composed on purpose, update MAIN_DIGEST from _digest(_catalog(path))")
    assert _digest(cat, drop=NEW_IN_595) == PRE_595_DIGEST[year]         # minus #595's two keys: exactly what #599 pinned


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_map_located_without_seeds_and_chained_backwards(year):
    """The map re-encoded by our encoder between junk, either layout: the
    GUID-free tail scan finds it; a seed on the LAST entry alone chains back
    to the first (entry tail 8 bytes on the older layout, 9 on the newer --
    and on the older one the u32 before an inner entry is the previous
    entry's write level 1, which must not pass for "count 1") and the count
    offset is exact."""
    path = pinned_base(year)
    dec = ES._decoder_for(path)
    lay = ES.catalog_layout(dec.schema)
    cat = _catalog(path)
    enc = ObjectEncoder(decoder=dec)
    entries = b"".join(enc.encode_object(lay.pair_id, s.raw) for s in cat)
    head, tail = b"\x07junk-before" * 3, b"\x00\x00\x00\x00\x01junk-after"
    gl = head + len(cat).to_bytes(4, "little") + entries + tail
    for seeds in (None, [DAYLIGHT]):
        off, count, found = ES.locate_schema_map(gl, dec, seed_guids=seeds)
        assert (off, count) == (len(head), 2), seeds
        assert sorted(found) == [len(head) + 4, len(head) + 4 + cat.by_guid[DAYLIGHT].offset - cat.by_guid[AREX].offset]
        assert [ES._entry_schema(v)[0]["m_guid"] for _e, v in (found[k] for k in sorted(found))] == [AREX, DAYLIGHT]
    assert ES.locate_schema_map(head + tail, dec) == (-1, 0, {})           # nothing there: the documented triple


def _schema(**classes) -> Schema:
    """A stand-in archive schema: class name -> [(member, type_name), ...]."""
    s = Schema()
    for i, (name, members) in enumerate(classes.items()):
        s.by_name[name] = SimpleNamespace(
            type_id=0x500 + i, fields=[SimpleNamespace(name=m, type_name=t) for m, t in members])
    return s


USAGE, BARE = "std::pair< GUIDvalue, SchemaUsageInfo >", "std::pair< GUIDvalue, ESSchema >"


def test_layout_is_read_off_the_files_own_ESSchemaStorage():
    # 2025 shape: both pair classes exist, ESSchemaStorage holds the usage map -> the usage layout
    new = ES.catalog_layout(_schema(ESSchemaStorage=[("m_schemaUsageMap", USAGE), ("m_dirty", None)], **{USAGE: [], BARE: []}))
    assert (new.member, new.tail) == ("m_schemaUsageMap", 9)
    # 2024 shape
    old = _schema(ESSchemaStorage=[("m_storedSchemas", BARE), ("m_dirty", None)], **{BARE: []})
    lay = ES.catalog_layout(old)
    assert (lay.member, lay.pair_id, lay.tail) == ("m_storedSchemas", 0x501, 8)
    assert ES._no_map_reason(old) == "no ESSchemaStorage.m_storedSchemas entry could be located in Global/Latest"
    # a pair class the file's ESSchemaStorage does not hold is not a catalog
    stray = _schema(ESSchemaStorage=[("m_other", "std::pair< GUIDvalue, Mystery >")], **{BARE: []})
    assert ES.catalog_layout(stray) is None
    assert ES._no_map_reason(stray).endswith("-- its ESSchemaStorage keeps no ESSchema map at all")
    # a pair class with no ESSchemaStorage to hold it is not a catalog either
    assert ES.catalog_layout(_schema(**{BARE: []})) is None and ES.catalog_layout(_schema(Unrelated=[])) is None


def test_tracking_item_layout_is_read_off_the_files_own_schema():
    """The three pins declare the EStorageTrackingItem the walk reads; a file
    that does not gets no walk and a header that says why (never ``@-0x1``)."""
    for year in CERTIFIED_YEARS:
        assert ES.tracking_layout_known(GF.schema_of(pinned_base(year)))
    assert ES.tracking_layout_known(_schema(EStorageTrackingItem=list(ES.TRACKING_ITEM)))
    assert not ES.tracking_layout_known(_schema(EStorageTrackingItem=[("m_schemaGuid", "GUIDvalue"), ("m_elemIds", "int")]))
    assert not ES.tracking_layout_known(_schema(Unrelated=[]))
    cat = ES.ESSchemaCatalog()
    cat.add(ES._schema_from_pair({"first": AREX, "second": {"m_guid": AREX, "m_schemaName": "S", "m_vendorId": "", "m_fields": []}}))
    cat.map_offset, cat.map_count, cat.tracking_note = 36, 1, "this file's EStorageTrackingItem is not ..."
    buf = io.StringIO()
    ES.print_catalog(cat, buf)
    assert buf.getvalue().startswith("ES schema catalog: 1 schemas (map count 1 @0x24 in Global/Latest; "
                                     "tracking not read (this file's EStorageTrackingItem is not ...))\n")
    cat.tracking_offset, cat.tracking = 100, {AREX: [5]}                # located but count 0: the labelled fallback
    buf = io.StringIO()
    ES.print_catalog(cat, buf)
    assert "; tracking @0x64 (count unverified))\n" in buf.getvalue()


def test_entry_value_shapes():
    sch = {"m_guid": AREX, "m_schemaName": "S", "m_vendorId": "V", "m_fields": []}
    wrapped = {"first": AREX, "second": {"m_contentDocsKeys": ["k"], "m_schema": sch, "m_usedInHost": True}}
    bare = {"first": AREX, "second": sch}
    assert ES._entry_schema(wrapped) == (sch, wrapped["second"]) and ES._entry_schema(bare) == (sch, None)
    w, b = ES._schema_from_pair(wrapped), ES._schema_from_pair(bare)
    assert (w.used_in_host, w.content_docs_keys) == (True, ["k"])
    assert (b.used_in_host, b.content_docs_keys, b.guid, b.name) == (None, [], AREX, "S")
