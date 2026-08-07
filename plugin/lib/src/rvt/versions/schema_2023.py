"""rvt.versions.schema_2023 -- the Revit 2023 ``Formats/Latest`` handle.

RESULT (2026-08-04, genesis-2023-reduce stream): the 2023 schema STREAM
parses AT PARITY with 2024/2025/2026 using the UNCHANGED ``rvt.schema``
grammar -- zero parse errors, zero unresolved refs, the same trailing
8-byte zero sentinel.  ``PARSER_DELTAS`` is empty on purpose: 2023 is the
FOURTH consecutive release with no schema-parser delta.

What DOES differ at 2023 is one layer below the schema: the RECORD LAYER.
The 2023 schema itself declares it -- class ``Identifier`` is **v1 with
field ``m_id`` (i32)** where 2024+ is v2 with ``m_id64`` (i64) -- so every
serialized element id (record framing headers, in-body ElementId values,
the ElemTable rows/footer) is 32-bit.  That layer lives in
``rvt.versions.records32`` (activate with ``records32.ids32()`` or the
composed ``records32.reading32(path)``); this module only pins the schema:

* ``EXPECTED_SIZE`` = 462,765 inflated bytes, ``EXPECTED_SHA256`` =
  bce7907b..., ``CLASS_COUNT`` = 4,418 (2024 has 4,492; 2025 4,600;
  2026 4,690).  Byte-identical in every 2023 file we hold (all six
  Autodesk 2023 sample projects).
* The 2023 partition-framing ordinals live in
  ``rvt.versions.KNOWN_RELEASES[2023].framing`` and are ALWAYS
  re-derivable by name from this schema (SegmentMarker 0x0e4e,
  SegmentCheckback 0x0e47, SignatureMarker 0x0e61, ContentMarker 0x0365,
  ContentKey 0x0364, PartitionTable 0x0bc0).

The samples that carry this schema are DEV-ONLY quarantined reference data
(``samples/2023/SOURCES.md``); nothing here reads them at import time.
"""
from __future__ import annotations

from typing import Optional

from . import KNOWN_RELEASES
from ._release_schema import (SchemaMismatch, default_source, load_release_schema,
                              verify_schema)

YEAR = 2023
RELEASE = KNOWN_RELEASES[YEAR]

EXPECTED_SIZE = RELEASE.schema_size          # 462,765
EXPECTED_SHA256 = RELEASE.schema_sha256      # bce7907bbb970c0e...
CLASS_COUNT = RELEASE.class_count            # 4,418

#: What had to change in the schema PARSER for 2023: nothing.  Kept explicit
#: so the question "where are the 2023 parser deltas?" has a checkable
#: answer (tests/test_genesis_2023.py asserts it stays empty while parity
#: holds).  The 2023 delta is the RECORD layer (32-bit element ids), which
#: is below the schema grammar: see ``rvt.versions.records32``.
PARSER_DELTAS: tuple = ()

#: The record layer this release's files use: element ids are 32-bit
#: (``Identifier`` v1).  The checkable authority is the schema's own
#: declaration -- ``records32.is_ids32(load())`` is True.
ELEMENT_ID_BITS = 32

#: The 2023 framing ordinals (by-name resolvable from the schema).
FRAMING = dict(RELEASE.framing)

__all__ = ["YEAR", "RELEASE", "EXPECTED_SIZE", "EXPECTED_SHA256", "CLASS_COUNT",
           "PARSER_DELTAS", "ELEMENT_ID_BITS", "FRAMING", "load", "verify",
           "default_source", "SchemaMismatch"]


def load(source: Optional[str] = None):
    """Parse the 2023 schema (from ``source`` or the local dev sample) and
    verify it against the pin.  Raises FileNotFoundError off the dev
    machine unless a 2023 file is supplied -- by design (samples are never
    shipped)."""
    return load_release_schema(RELEASE, source=source)


def verify(schema) -> bool:
    """True (or SchemaMismatch) that ``schema`` IS the pinned 2023 schema."""
    return verify_schema(RELEASE, schema)[0]


def source_path() -> Optional[str]:
    """A quarantined dev sample that carries the 2023 schema, if present."""
    return default_source(RELEASE)


if __name__ == "__main__":  # pragma: no cover
    s = load()
    st = s.stats()
    print(f"Revit {YEAR} schema: {st['stream_size']:,} B, {st['class_count']:,} classes, "
          f"{st['field_count']:,} fields, unresolved={st['unresolved_refs']} "
          f"sha256={st['sha256'][:16]}..  PARSER_DELTAS={PARSER_DELTAS}")
    print(f"framing: {{{', '.join(f'{k}={v:#x}' for k, v in FRAMING.items())}}}")
    from .records32 import is_ids32
    print(f"element ids 32-bit (Identifier v1): {is_ids32(s)}")
