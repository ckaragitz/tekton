"""rvt.frontdoor.target_status -- the HONEST per-release status, in one place.

The skills ask the recipient's Revit YEAR before anything is built (Revit
cannot open a file saved by a newer release) and must state, with every
result and without a follow-up call, what that year honestly gets:

* ``certified-base``      -- a composed genesis base for that release is
                             certified by Autodesk's reader (ledger:
                             docs/coverage/viewer-certified.json) and pinned;
                             files are BUILT on it.  The individual output is
                             still only *validated* by our own gate.
* ``known-not-certified`` -- the release's format is known to the version
                             model (files of that release read / edit), but no
                             certified creation base exists yet, so a CREATE
                             request falls back (delivered + one clear line +
                             a version-agnostic IFC addition).
* ``not-supported``       -- unknown to the version model; same fallback.

and for THE FILE that was delivered: ``validated-not-certified`` (our
validator: 0 errors -- Autodesk acceptance is only ever proven by the
recipient's Revit / the Autodesk Viewer) or ``self-checks-failed`` /
``not-built``.  The classification is DERIVED from
``rvt.versions.creation_status`` (one classifier, no year literal here).

:func:`release_view` condenses the manifest's ``target_version`` block +
validation summary into the compact ``release`` block the front door's
``--json`` result carries (issue #24: one call, no manifest re-read).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["support_status", "supported_targets", "nearest_supported",
           "opens_in", "release_view"]


def _V():
    from .. import versions
    return versions


def supported_targets() -> List[int]:
    """Releases a file can be CREATED for today (certified genesis base)."""
    return sorted(_V().SUPPORTED_CREATION_RELEASES)


def support_status(year: Optional[int]) -> str:
    if year is None:
        return "not-supported"
    st = _V().creation_status(int(year))
    if st["supported"]:
        return "certified-base"
    return "known-not-certified" if st.get("have_schema") else "not-supported"


def nearest_supported(year: int) -> Optional[int]:
    """The supported target closest to ``year`` -- preferring one the
    recipient can OPEN (<= year); only when none exists, the oldest we have
    (which their Revit cannot open: say so)."""
    sup = supported_targets()
    if not sup:
        return None
    older = [y for y in sup if y <= int(year)]
    return max(older) if older else min(sup)


def opens_in(release: Optional[int]) -> Optional[str]:
    if release is None:
        return None
    return f"Revit {int(release)} and newer -- never an older Revit"


def _this_file(manifest: Dict[str, Any], files: Optional[Dict[str, str]]) -> str:
    if not any(str(p).lower().endswith((".rvt", ".rfa")) for p in (files or {}).values()):
        return "not-built"
    if str(manifest.get("status") or "").upper().startswith("SELF-CHECKS FAILED"):
        return "self-checks-failed (delivered WITH the failed report -- say so plainly)"
    if "SKIPPED" in str((manifest.get("report") or {}).get("validation", {}).get("verdict")):
        return ("self-checks-skipped (no validator verdict for this file -- NOT a shippable run; "
                "Autodesk acceptance only when the recipient's Revit / the Autodesk Viewer opens it)")
    parts = [f"{role}: {v.get('verdict')} {v.get('n_errors', '?')} errors / "
             f"{v.get('n_warnings', '?')} warnings"
             for role, g in ((manifest.get("build") or {}).get("validation") or {}).items()
             for v in [(g or {}).get("validate") or {}] if v]
    ed = manifest.get("edit") or {}
    if not parts and ed:
        parts = [f"edit job: {ed.get('job_status')} (hard gates passed: "
                 f"{ed.get('hard_gates_passed')})"]
    return ("validated-not-certified (our gate: " + ("; ".join(parts) or "see manifest")
            + "; Autodesk acceptance only when the recipient's Revit / the Autodesk "
            "Viewer opens it)")


def release_view(manifest: Dict[str, Any], *, files: Optional[Dict[str, str]] = None
                 ) -> Dict[str, Any]:
    """The compact, relay-as-is ``release`` block for a front-door result."""
    tv = manifest.get("target_version") or {}
    req, out_rel = tv.get("requested"), tv.get("output_release")
    view: Dict[str, Any] = {
        "requested": req,
        "output": out_rel,
        "resolution": tv.get("status") or "unspecified",
        "opens_in": opens_in(out_rel),
        "target_support": tv.get("target_support") or support_status(out_rel if req is None else req),
        "this_file": _this_file(manifest, files),
        "supported_targets": tv.get("supported_targets") or supported_targets(),
    }
    for key in ("input_release", "line", "nearest_supported", "ifc_addition"):
        if tv.get(key) is not None:
            view[key] = tv[key]                       # `line` is relayed VERBATIM
    if req is None and tv.get("input_release") is None and tv.get("note"):
        view["ask"] = tv["note"]                      # "no --target-version given: ... ask"
    return view
