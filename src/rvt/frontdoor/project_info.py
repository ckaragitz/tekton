"""rvt.frontdoor.project_info -- stage P: write THE JOB's identity into the
base's ``ProjectInfo`` element (issue #148).

Every front-door output grows on a pinned genesis base whose singleton
``ProjectInfo`` (class 0xd13, our own constructor's element --
``rvt.genesis.skeleton.new_project_info``) still carries the BASE's
placeholders ('Genesis Base', 'GEN-0000', the pre-rename organisation
string ...).  Manage > Project Information -- and the GEN-101 title block --
is the first thing the receiving engineer reads, so a job must say what it
is: the intent's project name, PROOF-ONLY as the project status while the
deliverability gates are open (the label mirrors the manifest stamp; hard
rule 1: a label, never refusal logic), the build date as the issue date,
and :data:`rvt.identity.PRODUCT_AUTHOR_PLACEHOLDER` as the author (hard
rule 6: never an Autodesk or template identity as OUR author string).

The write is the certified MODIFY shape (matrix cell M3): ten AString
``set-param`` edits on ONE existing element through
:func:`rvt.manipulate.set_param`, one seq-102 record replaced, one commit,
nothing added or removed -- no new verbs, no new format work.  It runs
FIRST in the build (base -> ``_stages/stage_P_identity.rvt``) so every
downstream file (loaded chain, walls, equipment, shell/combined) inherits
the identity from one edit, and the P0 provenance gate still ledgers the
output against the untouched pinned base.

Determinism: the stage is a pure function of (base bytes, identity); the
only day-varying input is the issue date, which honours
``SOURCE_DATE_EPOCH`` (the reproducible-builds convention) when set.

Territory: ``src/rvt/frontdoor/`` (front-door stream).
"""
from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Optional

from ..genesis import skeleton as GSK
from ..identity import PRODUCT_AUTHOR_PLACEHOLDER

__all__ = ["PROJECT_STATUS_PROOF_ONLY", "FIELD_PARAMS", "ProjectIdentity",
           "build_date", "identity_from_intent", "read_project_info",
           "stage_project_info"]

#: Project Status while the P0 deliverability gates (G2 identity / G3
#: counsel / G4 content, TRACKER.md) are open -- the same word the manifest
#: stamps on every output today.  The day ``status_gate`` reports
#: ``deliverable`` this default must follow it (build.py records both).
PROJECT_STATUS_PROOF_ONLY = "PROOF-ONLY"

#: identity field -> (BuiltInParameter id on ProjectInfo, Revit's UI label).
#: The ten AString parameters :func:`rvt.genesis.skeleton.new_project_info`
#: authors, keyed by the constructor's own keyword names.
FIELD_PARAMS: Dict[str, tuple] = {
    "project_name": (GSK.BIP_PROJECT_NAME, "Project Name"),
    "project_number": (GSK.BIP_PROJECT_NUMBER, "Project Number"),
    "address": (GSK.BIP_PROJECT_ADDRESS, "Project Address"),
    "client_name": (GSK.BIP_CLIENT_NAME, "Client Name"),
    "project_status": (GSK.BIP_PROJECT_STATUS, "Project Status"),
    "issue_date": (GSK.BIP_PROJECT_ISSUE_DATE, "Project Issue Date"),
    "organization_name": (GSK.BIP_PROJECT_ORG_NAME, "Organization Name"),
    "organization_description": (GSK.BIP_PROJECT_ORG_DESCRIPTION, "Organization Description"),
    "building_name": (GSK.BIP_PROJECT_BUILDING_NAME, "Building Name"),
    "author": (GSK.BIP_PROJECT_AUTHOR, "Author"),
}


@dataclass(frozen=True)
class ProjectIdentity:
    """The ten Project Information strings a job writes.  Empty means
    'not known for this job' (Revit shows a blank field) -- never a base
    placeholder carried over."""
    project_name: str
    project_number: str = ""
    address: str = ""
    client_name: str = ""
    project_status: str = PROJECT_STATUS_PROOF_ONLY
    issue_date: str = ""
    organization_name: str = ""
    organization_description: str = ""
    building_name: str = ""
    author: str = PRODUCT_AUTHOR_PLACEHOLDER

    def params(self) -> Dict[int, str]:
        """``{BuiltInParameter id: value}`` for :func:`rvt.manipulate.set_param`."""
        return {FIELD_PARAMS[f.name][0]: str(getattr(self, f.name)) for f in fields(self)}

    def as_json(self) -> Dict[str, str]:
        return asdict(self)


def build_date(now: Optional[float] = None) -> str:
    """The job's issue date, ISO ``YYYY-MM-DD`` in UTC.  ``SOURCE_DATE_EPOCH``
    (seconds since the epoch) pins it for reproducible builds; otherwise the
    wall clock (``now`` overrides both, for tests)."""
    if now is None:
        sde = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
        now = float(sde) if sde.isdigit() else time.time()
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def identity_from_intent(model: Any, *, issue_date: Optional[str] = None,
                         **known: str) -> ProjectIdentity:
    """Resolve a job's :class:`ProjectIdentity` from its intent model.

    The intent (``rvt.ifc.intent.IntentModel``, spec v2) carries the project
    NAME on every route (prompt: the room's name; IFC: ``IfcProject.Name``);
    number / client / building / address / organisation ride in ``known``
    when a caller has them (empty otherwise -- the spec's ``project`` block
    and ``IfcProject.LongName/Phase`` are not threaded through the intent
    model yet).  Status and author are the product's, not the caller's."""
    unknown = set(known) - set(FIELD_PARAMS)
    if unknown:
        raise ValueError(f"unknown ProjectInfo field(s): {sorted(unknown)} "
                         f"(known: {sorted(FIELD_PARAMS)})")
    name = str(getattr(model, "project_name", "") or "").strip()
    return ProjectIdentity(project_name=name,
                           issue_date=issue_date or build_date(),
                           **{k: str(v) for k, v in known.items()})


def read_project_info(doc: Any) -> Dict[str, Any]:
    """Decode the host document's singleton ``ProjectInfo``:
    ``{"elem_id", "params": {param_id: value}, "fields": {field: value}}``."""
    ids = doc.ids_of_class("ProjectInfo")
    if len(ids) != 1:
        raise ValueError(f"expected exactly one host ProjectInfo element, found {ids}")
    eid = int(ids[0])
    pset = (((doc.value(eid).get("m_pParamValueSetAString") or {}).get("value") or {})
            .get("m_paramSet") or [])
    params = {int(p["m_paramId"]): p.get("m_value") for p in pset if isinstance(p, dict)}
    by_pid = {pid: name for name, (pid, _label) in FIELD_PARAMS.items()}
    return {"elem_id": eid, "params": params,
            "fields": {by_pid[pid]: v for pid, v in params.items() if pid in by_pid}}


def stage_project_info(src_rvt: str, out_path: str, ident: ProjectIdentity) -> Dict[str, Any]:
    """Stage P: write ``ident`` into ``src_rvt``'s ProjectInfo -> ``out_path``.

    One :func:`rvt.manipulate.set_param` per field on the singleton element
    and ONE commit (:func:`rvt.manipulate.commit_plans` -- unit 0 re-emitted,
    everything else copied); the written file is then re-opened and its
    ProjectInfo decoded again, proving the replaced record reads back with
    every value landed.  The whole-file structural proof is NOT repeated
    here: every downstream stage verifies the file it writes
    (``verify_written``) and the V gates validate the deliverable, all of
    which descend from this one -- a second CRC/ECC/stamp sweep would only
    cost the job ~0.3 s.  Returns the stage record (``ok`` False +
    ``blocker`` on any failure; the caller degrades to the unedited base --
    a missing identity never costs the user the file)."""
    from .. import manipulate as M
    from ..mutate import Document

    rec: Dict[str, Any] = {"stage": "P", "what": "job identity -> ProjectInfo",
                           "in": src_rvt, "out": out_path, "ok": False,
                           "identity": ident.as_json()}
    t0 = time.perf_counter()
    try:
        doc = Document.from_file(src_rvt)
        before = read_project_info(doc)
        eid = before["elem_id"]
        rec["elem_id"] = eid
        rec["before"] = before["fields"]
        plans = [M.set_param(doc, eid, pid, value) for pid, value in ident.params().items()]
        crep = M.commit_plans(src_rvt, out_path, plans)
        rec["commit"] = {"replaced": [list(r) for r in crep.replaced],
                         "removed_ids": list(crep.removed_ids),
                         "elemtable_count_before": crep.elemtable_count_before,
                         "elemtable_count_after": crep.elemtable_count_after,
                         "watermark": crep.watermark}
        after = read_project_info(Document.from_file(out_path))
        rec["after"] = after["fields"]
        rec["mismatch"] = {k: {"wanted": v, "got": after["fields"].get(k)}
                           for k, v in ident.as_json().items() if after["fields"].get(k) != v}
        rec["ok"] = bool(list(crep.replaced) == [(102, eid)] and not crep.removed_ids
                         and crep.elemtable_count_before == crep.elemtable_count_after
                         and after["elem_id"] == eid and not rec["mismatch"])
        if not rec["ok"]:
            rec["blocker"] = "ProjectInfo edit did not land cleanly (see commit / mismatch)"
    except Exception as e:                                               # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["blocker"] = rec["error"]
    rec["elapsed_s"] = round(time.perf_counter() - t0, 2)
    return rec
