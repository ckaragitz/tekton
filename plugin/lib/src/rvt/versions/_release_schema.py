"""Shared machinery for the per-release schema handles
(``rvt.versions.schema_2025``, ``schema_2024``, ...).

THE FINDING THESE MODULES EXIST TO RECORD: the ``Formats/Latest`` STREAM
GRAMMAR IS RELEASE-INDEPENDENT.  ``rvt.schema.parse`` (written against
Revit 2026) reads the 2025 and 2024 schemas to EOF -- zero parse errors,
zero unresolved refs, the same 8-byte zero sentinel -- so a per-release
handle is NOT a forked parser.  It is:

* a WRAPPER around ``rvt.schema.parse`` (never a modified copy),
* the release's pinned expectations (size, sha256, class count) so a wrong
  or corrupt schema is caught the way ``rvt.schema.EXPECTED_SIZE`` /
  ``EXPECTED_SHA256`` catch it for 2026,
* an explicit, empty ``PARSER_DELTAS`` -- the documented answer to "what
  had to change in the schema PARSER for this release": nothing.

What DOES differ per release lives in ``rvt.versions`` (the six framing
ordinals) -- it is a property of the CLASS TABLE, not of the grammar that
serializes it.
"""
from __future__ import annotations

import glob
import os
from typing import Optional, Tuple

from . import KNOWN_RELEASES, Release, VersionError


class SchemaMismatch(VersionError):
    """The parsed schema does not match the release's pinned signature."""


def repo_root() -> str:
    """Repo root (env ``TEKTON_ROOT`` overrides), mirroring rvt.schema.ROOT."""
    return os.environ.get("TEKTON_ROOT") or os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def default_source(release: Release) -> Optional[str]:
    """A quarantined DEV sample of this release to load the schema from
    (any file works -- the schema is byte-identical within a release).
    Returns None when the samples are not on this machine (they are
    dev-only and never shipped)."""
    d = os.path.join(repo_root(), release.samples_dir)
    for stem in ("rstbasicsampleproject.rvt", "racbasicsampleproject.rvt"):
        p = os.path.join(d, stem)
        if os.path.isfile(p):
            return p
    hits = sorted(glob.glob(os.path.join(d, "*.rvt")))
    return hits[0] if hits else None


def load_release_schema(release: Release, source: Optional[str] = None):
    """Parse this release's ``Formats/Latest`` with the (release-independent)
    ``rvt.schema`` grammar and verify it against the pinned signature."""
    src = source or default_source(release)
    if src is None:
        # no dev sample on this machine (fresh clone / cloud session): the
        # plugin bundles a parsed-schema cache keyed by this release's pinned
        # sha256 (assets/schema_cache/<sha>.tksc) -- reconstruct from it and
        # hold it to the same pin
        from ..schema_cache import load_cached
        s = load_cached(release.schema_sha256,
                        source=f"schema_cache:{release.schema_sha256[:16]}")
        if s is not None:
            verify_schema(release, s)
            return s
        raise FileNotFoundError(
            f"no {release.label} sample under {release.samples_dir}/ to load the "
            f"schema from and no bundled schema cache for "
            f"{release.schema_sha256[:16]}..; supply source=<any {release.year} "
            ".rvt/.rfa> (the schema is byte-identical across a release's files)")
    from ..versions import schema_of
    s = schema_of(src)
    verify_schema(release, s)
    return s


def verify_schema(release: Release, schema) -> Tuple[bool, str]:
    """Raise :class:`SchemaMismatch` unless ``schema`` carries this
    release's pinned size / sha256 / class count."""
    st = schema.stats()
    probs = []
    if st["stream_size"] != release.schema_size:
        probs.append(f"size {st['stream_size']} != {release.schema_size}")
    if st["sha256"] != release.schema_sha256:
        probs.append(f"sha256 {st['sha256'][:16]}.. != {release.schema_sha256[:16]}..")
    if st["class_count"] != release.class_count:
        probs.append(f"class_count {st['class_count']} != {release.class_count}")
    if st["unresolved_refs"]:
        probs.append(f"{st['unresolved_refs']} unresolved class refs")
    if probs:
        raise SchemaMismatch(
            f"not the pinned {release.label} Formats/Latest schema: " + "; ".join(probs))
    return True, "ok"


def release(year: int) -> Release:
    return KNOWN_RELEASES[year]
