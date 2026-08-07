"""identity.py — the writer OWNS the file's identity block (BasicFileInfo).

A generated file must never inherit its template's identity. Cloning the
Autodesk sample project carries forward, verbatim, an Autodesk employee's
local file path, the sample's document GUIDs and the Revit build string —
"live contamination" per docs/product/content-strategy.md, and (per the
research critic) the analog of DWG's TrustedDWG false-designation hook.

Policy implemented here (see TRACKER P0 gate G2):
  * ALWAYS scrubbed (unambiguous — a new document is a new identity):
      last_save_path  -> the output filename (no directories) or "";
      username        -> "" (or the caller's product identity);
      unique_document_guid / central_episode_guid -> fresh UUIDs;
      central_model_identity / model_identity -> nil GUID;
      unique_document_increments -> unchanged (History coherence).
  * COUNSEL DECISION C1 (parameterised, default = keep for compatibility):
      author ("Autodesk Revit"), client_app_name ("RevitApplication"), and
      the version marker (format "2026" + build). Revit reads the version
      marker on open, so it stays until proven changeable; whether the
      AUTHORING string may/must be changed is a legal question informed by
      the compatibility experiments (V30/V31), not decided here.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from . import stream_encoders as se

PRODUCT_AUTHOR_PLACEHOLDER = "rvt-writer"          # product-name placeholder (counsel C1)
# V31 (2026-08-03, Autodesk viewer PASS) proved the reader does NOT gatekeep on
# the author/client strings, so the honest default is to declare OUR authorship
# rather than falsely assert "Autodesk Revit" -- never claim an origin we don't
# have. Exact wording pending counsel decision C1; the version marker stays.
DEFAULT_AUTHOR = PRODUCT_AUTHOR_PLACEHOLDER
DEFAULT_CLIENT_APP = PRODUCT_AUTHOR_PLACEHOLDER


def own_identity_model(model: dict, *, out_path: str = "",
                       username: str = "",
                       document_guid: Optional[str] = None,
                       author: Optional[str] = None,
                       client_app_name: Optional[str] = None,
                       keep_version_marker: bool = True) -> dict:
    """Return a copy of a decoded BasicFileInfo model with OUR identity.

    ``author``/``client_app_name`` None => keep the template's value (the
    compatibility default until counsel decides); pass strings to assert our
    own. The Revit version marker (format/build) is preserved unless
    keep_version_marker=False (untested; Revit reads it to open the file).
    """
    m = dict(model)
    guid = document_guid or str(uuid.uuid4())
    m["last_save_path"] = os.path.basename(out_path) if out_path else ""
    m["username"] = username
    m["unique_document_guid"] = guid
    m["central_episode_guid"] = guid
    m["central_model_identity"] = "00000000-0000-0000-0000-000000000000"
    m["model_identity"] = "00000000-0000-0000-0000-000000000000"
    m["central_model_path"] = ""
    m["author"] = author if author is not None else DEFAULT_AUTHOR
    m["client_app_name"] = client_app_name if client_app_name is not None else DEFAULT_CLIENT_APP
    if not keep_version_marker:
        m["build"] = ""
    return m


def own_basic_file_info(raw_bfi: bytes, *, out_path: str = "", **kw) -> bytes:
    """Decode a template's BasicFileInfo, replace its identity with ours,
    re-encode (mirror text regenerated so the human-readable block agrees
    with the fields)."""
    model = se.decode_basic_file_info(raw_bfi)
    ours = own_identity_model(model, out_path=out_path, **kw)
    return se.encode_basic_file_info(ours, regenerate_mirror=True)


def identity_report(raw_bfi: bytes) -> dict:
    """What identity does this file assert? (for audits / the validator)."""
    m = se.decode_basic_file_info(raw_bfi)
    keys = ("author", "client_app_name", "format", "build", "username",
            "last_save_path", "unique_document_guid", "central_episode_guid",
            "locale", "unique_document_increments")
    return {k: m.get(k) for k in keys}


# ---------------------------------------------------------------------------
# Global/DocumentIncrementTable — one row per save episode, each carrying the
# USERNAME of who saved it. Cloning a sample inherits Autodesk employees'
# usernames (audit finding 2026-08-03: zhangg, hansonje, campbes, loboarch,
# okapaw, youyi, xuew, gbs_subsuser6). The writer owns this field too.
# ---------------------------------------------------------------------------
def own_increment_table_payload(payload: bytes, *, username: str = "") -> bytes:
    """Rewrite every save-episode username in an inflated
    Global/DocumentIncrementTable payload; returns the new inflated payload."""
    m = se.decode_increment_table(payload)
    for key in ("records", "records2"):
        for row in m.get(key) or []:
            if isinstance(row, dict) and "username" in row:
                row["username"] = username
    return se.encode_increment_table(m)


def own_increment_table_stream(framed_raw: bytes, prefix: bytes, inflated: bytes, *,
                               username: str = "", level: int = 3) -> bytes:
    """Given the stream's global prefix + inflated payload, return the fully
    re-framed raw stream (prefix + gzip member + ECC page framing)."""
    from .writer import gzip_member
    from . import ecc
    new_payload = own_increment_table_payload(inflated, username=username)
    logical = prefix + gzip_member(new_payload, level=level, sync_flush=True)
    return ecc.frame_stream(logical)
