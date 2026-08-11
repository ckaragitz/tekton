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
  note says what the file keeps); both catalog value shapes unwrap.

Bundled bases only (fresh-clone safe).
Run: .venv/bin/python -m pytest tests/test_estorage_catalog_2024.py -q
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import CERTIFIED_YEARS, pinned_base                # noqa: E402
from rvt import estorage as ES                                    # noqa: E402
from rvt import global_framing as GF                              # noqa: E402
from rvt.encode import ObjectEncoder                              # noqa: E402
from rvt.schema import Schema                                     # noqa: E402

OLD = [y for y in CERTIFIED_YEARS if y <= 2024]
NEW = [y for y in CERTIFIED_YEARS if y >= 2025]

# the two schemas every bundled base carries (inherited from the seed project)
AREX = "4c817959-0028-4a83-b3e7-cd1e832a459a"
DAYLIGHT = "5d9588ee-e6c7-4c96-87dc-df2a5fbe6613"
EXPECTED = {
    AREX: ("AREXContentGenerator", "", [("Identity", "TCHAR")], 6),
    DAYLIGHT: ("DaylightingAnalysisInfo", "ADSK", [("AnalysisId", "TCHAR"), ("ResultsInvalid", "int")], 1),
}
# 2025+/2026 catalogs as `main` read them: (schemas, map count, sha256[:16] of to_json() minus 'source')
MAIN_DIGEST = {2025: (2, 2, "43f8ad756ff22977"), 2026: (2, 2, "2d621ae50133432e")}


def _catalog(path: str) -> ES.ESSchemaCatalog:
    with GF.reading(path):
        return ES.schemas(path)


def _digest(cat: ES.ESSchemaCatalog) -> str:
    j = cat.to_json()
    j.pop("source")
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


@pytest.mark.parametrize("year", NEW)
def test_new_layout_pins_read_exactly_as_before(year):
    path = pinned_base(year)
    assert ES.catalog_layout(GF.schema_of(path)).member == "m_schemaUsageMap"
    cat = _catalog(path)
    assert (cat.note, cat.layout) == ("", "m_schemaUsageMap") and all(s.used_in_host is True for s in cat)
    assert (len(cat), cat.map_count, _digest(cat)) == MAIN_DIGEST[year], (
        f"the {year} pin's catalog no longer reads as main did -- if the pin was "
        f"re-composed on purpose, update MAIN_DIGEST from _digest(_catalog(path))")


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


def test_entry_value_shapes():
    sch = {"m_guid": AREX, "m_schemaName": "S", "m_vendorId": "V", "m_fields": []}
    wrapped = {"first": AREX, "second": {"m_contentDocsKeys": ["k"], "m_schema": sch, "m_usedInHost": True}}
    bare = {"first": AREX, "second": sch}
    assert ES._entry_schema(wrapped) == (sch, wrapped["second"]) and ES._entry_schema(bare) == (sch, None)
    w, b = ES._schema_from_pair(wrapped), ES._schema_from_pair(bare)
    assert (w.used_in_host, w.content_docs_keys) == (True, ["k"])
    assert (b.used_in_host, b.content_docs_keys, b.guid, b.name) == (None, [], AREX, "S")
