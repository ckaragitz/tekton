"""Global/Latest = the serialized ADocument object graph (rvt.adocument).

Targets (all six corpus samples):
  * FULL structured decode: consumed == payload length minus the constant
    trailing u32 0, zero decode errors (100.0000 % byte coverage).
  * decode -> encode is BYTE-EXACT (the ADocument codec is the symmetric
    ObjectDecoder/ObjectEncoder pair, needing only the document pid seed
    and a lifted container cap).
  * the top-level field map and the 241-slot AppInfo registry are stable.
  * an ADocument value tree we AUTHOR from scratch encodes and re-decodes.
"""
from __future__ import annotations

import os
import struct

import pytest

from rvt import adocument as ad
from rvt import objects as O

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, "extracted")
SAMPLES = [
    "racbasicsampleproject",
    "rstbasicsampleproject",
    "racadvancedsampleproject",
    "rstadvancedsampleproject",
    "rmebasicsampleproject",
    "dach-sample-project",
]
LARGE = {"rmebasicsampleproject", "dach-sample-project"}


def _payload(sample: str) -> bytes:
    p = os.path.join(EXTRACTED, sample, "Global__Latest.gz", "000.bin")
    if not os.path.exists(p):
        pytest.skip(f"no extracted Global/Latest for {sample}")
    with open(p, "rb") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def docs():
    """Decode every sample once (module-scoped cache)."""
    out = {}
    for s in SAMPLES:
        if s in LARGE and os.environ.get("RVT_SKIP_LARGE"):
            continue
        pay = _payload(s)
        out[s] = (pay, ad.decode_latest(pay))
    return out


# ---------------------------------------------------------------- framing
def test_root_class_is_adocument():
    s = ad.get_decoder().schema
    assert s.by_id[ad.ROOT_CLASS_ID].name == "ADocument"


def test_payload_starts_with_u16_adocument_class():
    for s in SAMPLES[:2]:
        pay = _payload(s)
        assert struct.unpack_from("<H", pay, 0)[0] == ad.ROOT_CLASS_ID


def test_stream_prefix_is_u64_five():
    from rvt.stream_encoders import global_prefix
    assert global_prefix("Global/Latest") == struct.pack("<Q", ad.LATEST_PREFIX_VALUE)


# ---------------------------------------------------------------- coverage
def test_full_decode_coverage_all_samples(docs):
    assert docs, "no samples decoded"
    for s, (pay, adoc) in docs.items():
        assert adoc.errors == [], f"{s}: {adoc.errors[:1]}"
        assert adoc.clean, f"{s}: not a clean full decode"
        # structured decode consumes everything except the trailing u32 0
        assert adoc.consumed + 2 + len(adoc.trailer) == len(pay), s
        assert adoc.trailer == ad.TRAILER, f"{s}: trailer {adoc.trailer.hex()}"
        cov = adoc.coverage
        assert cov["errors"] == 0 and cov["fraction"] >= 0.99999, s


def test_document_shape_constants(docs):
    for s, (_pay, adoc) in docs.items():
        v = adoc.value
        # externalized members are null / empty here
        assert v["m_elemTable"] is None, s            # -> Global/ElemTable
        assert v["m_pHistory"] is None, s             # -> Global/History
        assert v["m_pPartitionTable"] is None, s      # -> Global/PartitionTable
        assert v["m_appInfoArr"] == [], s             # app-infos hang off the manager
        # the document is archive object 1
        assert v["m_pHostDocument"] == {"weakref": ad.DOCUMENT_PID}, s
        # inline value class DevBranchInfo carries the schema version
        assert v["m_devBranchInfo"]["m_syncVersion"] == 2662, s
        assert v["m_ownerFamilyId"] == -1 and v["m_ownerFamilyContainingGroupId"] == -1, s
        assert v["m_groupFile"] is False and v["m_corruptDocument"] is False, s
        # 'saved by' build history is a real string list
        builds = adoc.summary()["stored_by_revit_build"]
        assert 4 <= len(builds) <= 20 and "Revit" in builds[-1], s


def test_appinfo_registry_is_the_fixed_241_slot_table(docs):
    assert len(ad.APPINFO_SLOTS) == ad.APPINFO_SLOT_COUNT == 241
    for s, (_pay, adoc) in docs.items():
        slots = adoc.appinfo_slots()
        assert len(slots) == 241, s
        # every populated slot carries the canonical class for that index
        assert adoc.slot_deviations() == [], f"{s}: {adoc.slot_deviations()[:3]}"
        assert 160 <= sum(1 for x in slots if x) <= 190, s
        # first indexed object is FamilyMgr with archive pid 2 (document = 1)
        arr = adoc.appinfo_array()
        assert arr[0]["ptr_class"] == "FamilyMgr" and arr[0]["pid"] == 2, s


def test_forge_corpus_lives_in_esschemastorage(docs):
    for s, (_pay, adoc) in docs.items():
        fc = adoc.forge_schema_corpus()
        if s == "dach-sample-project":
            continue          # dach stores no forge unit corpus
        assert fc["forge_unit_schema_pairs"] > 0 or fc["parameter_schema_pairs"] > 0, s
    # racbasic pins the wave-1 landmark: the declared 893-entry dictionary
    if "racbasicsampleproject" in docs:
        fc = docs["racbasicsampleproject"][1].forge_schema_corpus()
        assert fc["forge_unit_schema_pairs"] == 893
        assert fc["parameter_schema_pairs"] == 422


# ---------------------------------------------------------------- codec
def test_roundtrip_byte_exact(docs):
    """decode -> encode reproduces the payload byte-for-byte."""
    for s in ("racbasicsampleproject", "rstbasicsampleproject"):
        if s not in docs:
            continue
        pay, adoc = docs[s]
        assert ad.encode_latest(adoc) == pay, s


@pytest.mark.slow
def test_roundtrip_byte_exact_large(docs):
    if os.environ.get("RVT_SKIP_LARGE"):
        pytest.skip("RVT_SKIP_LARGE")
    for s in ("rmebasicsampleproject", "dach-sample-project"):
        if s not in docs:
            continue
        pay, adoc = docs[s]
        assert ad.encode_latest(adoc) == pay, s


def test_field_map_matches_schema_order():
    s = ad.get_decoder().schema
    names = [f.name for f in s.by_id[ad.ROOT_CLASS_ID].fields]
    assert [row["field"] for row in ad.FIELD_MAP] == names
    assert len(ad.FIELD_MAP) == 19


def test_field_holdings_annotated(docs):
    _pay, adoc = docs.get("rstbasicsampleproject") or next(iter(docs.values()))
    rows = adoc.field_holdings()
    assert [r["field"] for r in rows] == [f["field"] for f in ad.FIELD_MAP]
    mgr = next(r for r in rows if r["field"] == "m_pAppInfoManager")
    assert mgr["deferred_bytes"] > 0 and mgr["element_id_refs_distinct"] > 100


def test_minimal_authored_document_roundtrip():
    """An ADocument WE build from scratch encodes and decodes back."""
    value = {
        "m_elemTable": None,
        "m_appInfoArr": [],
        "m_oContentTable": None,
        "m_pHostDocument": {"weakref": ad.DOCUMENT_PID},
        "m_pAppInfoManager": None,
        "m_pStyleSettings": None,
        "m_pHistory": None,
        "m_pSteelModelInfo": None,
        "m_pPartitionTable": None,
        "m_oNobleSecondaryData": None,
        "m_ownerFamilyId": -1,
        "m_ownerFamilyContainingGroupId": -1,
        "m_devBranchInfo": {"m_devBranchId": 1, "m_syncVersion": 2662},
        "m_groupFile": False,
        "m_corruptDocument": False,
        "m_bIsCoreDocument": False,
        "m_executedUpgrades": [],
        "m_storedByRevitBuild": [{"m_str": "rev-revit genesis writer"}],
        "m_oExServicesUsed": None,
    }
    payload = ad.encode_latest(value)
    assert struct.unpack_from("<H", payload, 0)[0] == ad.ROOT_CLASS_ID
    assert payload.endswith(ad.TRAILER)
    back = ad.decode_latest(payload)
    assert back.clean and back.errors == []
    assert back.value == value


def test_transforms_keep_the_graph_decodable(docs):
    """The A2/A3 authoring transforms produce cleanly re-decodable documents."""
    _pay, adoc = docs.get("rstbasicsampleproject") or next(iter(docs.values()))
    v2 = ad.transform_drop_forge_corpus(ad.transform_build_list(adoc.value, ["ours"]))
    v3 = ad.transform_empty_content_table(ad.transform_scrub_sample_names(v2))
    p = ad.encode_latest(v3)
    back = ad.decode_latest(p)
    assert back.clean and back.value == v3
    fc = back.forge_schema_corpus()
    assert fc["forge_unit_schema_pairs"] == 0 and fc["parameter_schema_pairs"] == 0
    assert back.value["m_storedByRevitBuild"] == [{"m_str": "ours"}]
    assert len(p) < len(_pay)


def test_element_decoder_defaults_untouched():
    """The document decoder subclasses; it must NOT mutate rvt.objects."""
    assert O.MAX_CONTAINER == 2_000_000
    # a fresh element decoder still pre-seeds pids {1, 2} (element framing)
    # -- exercised implicitly by tests/test_objects.py; here just import path
    assert issubclass(ad.ADocumentDecoder, O.ObjectDecoder)
    assert issubclass(ad.ADocReader, O.Reader)
