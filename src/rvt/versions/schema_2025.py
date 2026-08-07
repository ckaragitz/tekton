"""rvt.versions.schema_2025 -- the Revit 2025 ``Formats/Latest`` handle.

RESULT (2026-08-04, phase A): the 2025 schema stream parses AT PARITY with
2026 using the UNCHANGED ``rvt.schema`` grammar -- there are NO parser
deltas to carry.  This module therefore wraps ``rvt.schema.parse`` (it does
not fork or subclass the grammar; ``PARSER_DELTAS`` is empty on purpose)
and pins what makes a schema "the 2025 schema":

* ``EXPECTED_SIZE`` = 484,585 inflated bytes, ``EXPECTED_SHA256`` =
  c964f9aa..., ``CLASS_COUNT`` = 4,600 (2026 has 4,690; 2024 has 4,492).
  Byte-identical in every 2025 file we hold: the six Autodesk 2025 sample
  projects AND the 2025 basic sample family (.rfa).
* The 2025 partition-framing ordinals live in
  ``rvt.versions.KNOWN_RELEASES[2025].framing`` and are ALWAYS re-derivable
  by name from this schema (SegmentMarker 0x0ed9, SegmentCheckback 0x0ed2,
  SignatureMarker 0x0eee, ContentMarker 0x0391, ContentKey 0x0390,
  PartitionTable 0x0c40).

The samples that carry this schema are DEV-ONLY quarantined reference data
(``samples/2025/SOURCES.md``); nothing here reads them at import time.
"""
from __future__ import annotations

from typing import Optional

from . import KNOWN_RELEASES
from ._release_schema import (SchemaMismatch, default_source, load_release_schema,
                              verify_schema)

YEAR = 2025
RELEASE = KNOWN_RELEASES[YEAR]

EXPECTED_SIZE = RELEASE.schema_size          # 484,585
EXPECTED_SHA256 = RELEASE.schema_sha256      # c964f9aa2a5f674e...
CLASS_COUNT = RELEASE.class_count            # 4,600

#: What had to change in the schema PARSER for 2025: nothing.  Kept explicit
#: so the question "where are the 2025 parser deltas?" has a checkable
#: answer (tests/test_versions.py asserts it stays empty while parity holds).
PARSER_DELTAS: tuple = ()

#: The 2025 framing ordinals (by-name resolvable from the schema).
FRAMING = dict(RELEASE.framing)

__all__ = ["YEAR", "RELEASE", "EXPECTED_SIZE", "EXPECTED_SHA256", "CLASS_COUNT",
           "PARSER_DELTAS", "FRAMING", "load", "verify", "default_source",
           "SchemaMismatch"]


def load(source: Optional[str] = None):
    """Parse the 2025 schema (from ``source`` or the local dev sample) and
    verify it against the pin.  Raises FileNotFoundError off the dev
    machine unless a 2025 file is supplied -- by design (samples are never
    shipped)."""
    return load_release_schema(RELEASE, source=source)


def verify(schema) -> bool:
    """True (or SchemaMismatch) that ``schema`` IS the pinned 2025 schema."""
    return verify_schema(RELEASE, schema)[0]


def source_path() -> Optional[str]:
    """A quarantined dev sample that carries the 2025 schema, if present."""
    return default_source(RELEASE)


if __name__ == "__main__":  # pragma: no cover
    s = load()
    st = s.stats()
    print(f"Revit {YEAR} schema: {st['stream_size']:,} B, {st['class_count']:,} classes, "
          f"{st['field_count']:,} fields, unresolved={st['unresolved_refs']} "
          f"sha256={st['sha256'][:16]}..  PARSER_DELTAS={PARSER_DELTAS}")
    print(f"framing: {{{', '.join(f'{k}={v:#x}' for k, v in FRAMING.items())}}}")
