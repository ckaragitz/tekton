"""rvt.versions.schema_2024 -- the Revit 2024 ``Formats/Latest`` handle.

RESULT (2026-08-04, phase A): the 2024 schema stream parses AT PARITY with
2026 using the UNCHANGED ``rvt.schema`` grammar -- NO parser deltas
(``PARSER_DELTAS`` is empty on purpose).  This module wraps
``rvt.schema.parse`` and pins what makes a schema "the 2024 schema":

* ``EXPECTED_SIZE`` = 470,502 inflated bytes, ``EXPECTED_SHA256`` =
  0bfb947b..., ``CLASS_COUNT`` = 4,492.  Byte-identical in every 2024 file
  we hold: the six Autodesk 2024 sample projects, the 2024 basic sample
  family (.rfa), AND an unrelated third-party 2024 model
  (magnetar 2024_Core_Interior.rvt) -- confirming the per-release-constant
  law beyond Autodesk's own content.
* The 2024 partition-framing ordinals live in
  ``rvt.versions.KNOWN_RELEASES[2024].framing`` and are ALWAYS
  re-derivable by name from this schema (SegmentMarker 0x0e7c,
  SegmentCheckback 0x0e75, SignatureMarker 0x0e8f, ContentMarker 0x037b,
  ContentKey 0x037a, PartitionTable 0x0bec).

The samples that carry this schema are DEV-ONLY quarantined reference data
(``samples/2024/SOURCES.md``); nothing here reads them at import time.
"""
from __future__ import annotations

from typing import Optional

from . import KNOWN_RELEASES
from ._release_schema import (SchemaMismatch, default_source, load_release_schema,
                              verify_schema)

YEAR = 2024
RELEASE = KNOWN_RELEASES[YEAR]

EXPECTED_SIZE = RELEASE.schema_size          # 470,502
EXPECTED_SHA256 = RELEASE.schema_sha256      # 0bfb947b3c9a0cec...
CLASS_COUNT = RELEASE.class_count            # 4,492

#: What had to change in the schema PARSER for 2024: nothing.
PARSER_DELTAS: tuple = ()

#: The 2024 framing ordinals (by-name resolvable from the schema).
FRAMING = dict(RELEASE.framing)

__all__ = ["YEAR", "RELEASE", "EXPECTED_SIZE", "EXPECTED_SHA256", "CLASS_COUNT",
           "PARSER_DELTAS", "FRAMING", "load", "verify", "default_source",
           "SchemaMismatch"]


def load(source: Optional[str] = None):
    """Parse the 2024 schema (from ``source`` or the local dev sample) and
    verify it against the pin."""
    return load_release_schema(RELEASE, source=source)


def verify(schema) -> bool:
    """True (or SchemaMismatch) that ``schema`` IS the pinned 2024 schema."""
    return verify_schema(RELEASE, schema)[0]


def source_path() -> Optional[str]:
    """A quarantined dev sample that carries the 2024 schema, if present."""
    return default_source(RELEASE)


if __name__ == "__main__":  # pragma: no cover
    s = load()
    st = s.stats()
    print(f"Revit {YEAR} schema: {st['stream_size']:,} B, {st['class_count']:,} classes, "
          f"{st['field_count']:,} fields, unresolved={st['unresolved_refs']} "
          f"sha256={st['sha256'][:16]}..  PARSER_DELTAS={PARSER_DELTAS}")
    print(f"framing: {{{', '.join(f'{k}={v:#x}' for k, v in FRAMING.items())}}}")
