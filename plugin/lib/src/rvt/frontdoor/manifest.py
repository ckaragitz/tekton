"""rvt.frontdoor.manifest -- the DELIVERABLE MANIFEST every route emits.

Whatever the input (prompt / IFC / .rvt+edit), the output is the ``.rvt``
file(s) PLUS this manifest: the route taken, the intent summary, the
elements created, the families generated, the base + its certification
citation + hash pin, the validator summary, the PROOF-ONLY stamps, and the
CRUD affordances (exactly how to modify / move / retype / delete what was
just created, in the ONE ops vocabulary the edit route speaks).  Written as
``manifest.json`` (machine) + ``MANIFEST.md`` (human) beside the outputs.

Nothing in here overclaims: self-checks (validator / registries /
identity) are reported as SELF-CHECKS, viewer acceptance is a separate tier
this run does not claim, LOAD vs RENDER is stated, and every degradation the
build recorded is listed.

Territory: ``src/rvt/frontdoor/`` (front-door stream).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Sequence

from .base import GenesisPin, ResolvedBase, PIN, repo_root
from .. import _jsonsafe
from .._clause import clip

__all__ = ["TOOL", "TOOL_VERSION", "file_facts", "crud_affordances",
           "coverage_cross_reference", "census_gaps", "authorship_census_note",
           "plan_note_degradations",
           "status_gate_lines", "resolved_pin", "build_manifest", "edit_manifest",
           "write_manifest", "created_counts", "report_block", "REPORT_DEGRADATIONS_CAP"]

TOOL = "tekton frontdoor (rvt.frontdoor)"
TOOL_VERSION = "1.0.0"

#: the coverage.py CRUD-matrix cells a room build exercises (28 categories x
#: 6 verbs; docs/coverage/matrix.json).  create = this build; the other verbs
#: are the edit route's affordances over the created elements.
_CATEGORY_FOR = {
    "wall": "walls",
    "equipment-instance": "electrical_equipment",
    "fixture-instance": "electrical_devices",
    "family(.rfa)": "families",
    "loaded-family": "families",
    "circuit": "circuits_systems",
}


def _relp(p: Optional[str]) -> Optional[str]:
    if not p:
        return None
    try:
        r = os.path.relpath(p, repo_root())
        return r if not r.startswith("..") else os.path.abspath(p)
    except ValueError:
        return os.path.abspath(p)


def file_facts(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"path": os.path.abspath(path), "relpath": _relp(path),
            "bytes": os.path.getsize(path), "sha256": h.hexdigest()}


# ---------------------------------------------------------------------------
# CRUD affordances (the CRUD mandate: creatable, editable AND deletable)
# ---------------------------------------------------------------------------

def crud_affordances(files: Dict[str, Optional[str]], created: List[Dict[str, Any]],
                     *, out_dir: Optional[str] = None) -> Dict[str, Any]:
    """For every created element: the exact commands that modify / move /
    retype / delete it (front door text edits + the rvt_edit.py CLI + the
    job runner's ops.json), plus whole-layer operations."""
    target = files.get("combined") or files.get("equipment") or files.get("shell")
    target_rel = _relp(target) if target else "<output.rvt>"
    rows: List[Dict[str, Any]] = []
    for c in created:
        eid = c.get("elem_id")
        kind = c.get("kind")
        tag = c.get("tag")
        if kind in ("family(.rfa)", "loaded-family") or eid is None:
            continue
        r: Dict[str, Any] = {"tag": tag, "elem_id": eid, "kind": kind,
                             "file": _relp(_file_for(files, c))}
        f = _relp(_file_for(files, c)) or target_rel
        if kind == "wall":
            r["modify"] = {
                "note": ("a wall's geometry is its location line + type + level; move / "
                         "delete are supported; length / type changes are the walls "
                         "stream's modify path"),
                "delete": {"text_edit": f"delete {eid}",
                           "cli": f"python tools/rvt_edit.py {f} delete --id {eid} -o edited.rvt",
                           "op": {"op": "delete", "id": eid, "cascade": True}},
            }
        else:  # equipment instance
            r["modify"] = {
                "move": {"text_edit": f"move {tag or eid} to X,Y,Z ft",
                         "cli": f"python tools/rvt_edit.py {f} move --id {eid} --to X Y Z "
                                f"[--rotation-deg N] -o edited.rvt",
                         "op": {"op": "move", "id": eid, "to": ["X", "Y", "Z"], "rotation_deg": 0}},
                "retype": {"text_edit": f"retype {tag or eid} to <symbol id>",
                           "cli": f"python tools/rvt_edit.py {f} retype --id {eid} --symbol S "
                                  "-o edited.rvt",
                           "op": {"op": "retype", "id": eid, "symbol": "<symbol id>"}},
                "delete": {"text_edit": f"delete {tag or eid} with cascade",
                           "cli": f"python tools/rvt_edit.py {f} delete --id {eid} --cascade "
                                  "-o edited.rvt",
                           "op": {"op": "delete", "id": eid, "cascade": True}},
            }
            r["not_available"] = {
                "rename / set-mark": ("front-door instances are specimen-scaffolded clones "
                                      "with NO instance parameter rows (the tag/PanelName rides "
                                      "on each board's own generated family + type; wiring "
                                      "devices share ONE family, their R-n tag is the manifest's "
                                      "label only) -- rename = regenerate with a new tag; "
                                      "`rename`/`set-mark` DO work on native instances in a "
                                      "user's file (--rvt route)"),
            }
        rows.append(r)
    return {
        "entrypoint": f"python tools/frontdoor.py author --rvt {target_rel} --edit \"<sentence | ops.json | inline JSON>\" --out <dir>",
        "note": ("every element the front door created is EDITABLE and DELETABLE through the "
                 "same front door (--rvt --edit) or the underlying rvt_edit.py / rvt_job.py "
                 "ops -- one ops vocabulary for all of them"),
        "elements": rows,
        "layer_operations": {
            "recreate": "re-run the same `frontdoor author` command (deterministic for the "
                        "same inputs) -- outputs are regenerated from the intent",
            "start_over": "the base is untouched; delete the output directory to discard the "
                          "whole created layer",
            "circuits": ("feeder circuits are NOT authored on this base yet (named blocker in "
                         "the manifest); the resolved circuit plan is in the intent's "
                         "feederTree.circuitPlan -- rvt.mep add_circuit / a Revit-side add-in "
                         "consume it"),
        },
    }


def _file_for(files: Dict[str, Optional[str]], row: Dict[str, Any]) -> Optional[str]:
    role = str(row.get("file_role") or "")
    if "shell" in role and files.get("shell"):
        return files["shell"]
    if "equipment" in role and files.get("equipment"):
        return files["equipment"]
    return files.get("combined") or files.get("equipment") or files.get("shell")


def coverage_cross_reference(created: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Which docs/coverage/matrix.json cells this run exercised."""
    cells = set()
    for c in created:
        cat = _CATEGORY_FOR.get(c.get("kind"))
        if cat:
            cells.add((cat, "create"))
    return {
        "matrix": "docs/coverage/matrix.json (28 categories x 6 verbs; tools/coverage.py)",
        "cells_exercised": [{"category": a, "verb": b} for a, b in sorted(cells)],
        "affordances": ("modify / move / retype / delete over every created element are the "
                        "manipulate stream's certified cells (M2/M3/M4); the front door's "
                        "--rvt route drives them"),
    }


# ---------------------------------------------------------------------------
# the honesty box
# ---------------------------------------------------------------------------

#: honesty.load_vs_render, keyed by the seq-103 rep the created walls actually
#: carry (``elements_created[].rep``); no wall created -> the 'dummy'
#: (historical) wording.  The ONE home of the certification-state sentence.
LOAD_VS_RENDER = {
    "solid": ("created walls carry authored solids: each SWall's seq-103 rep is a six-face "
              "GElement B-rep (rvt.render.brep, the W1_gabpd_wall_solid / "
              "RSOLID_walls_A_solid recipe -- RENDER-certified as a SHAPE on the composed "
              "base); THIS exact output is uncertified until its own viewer batch passes, "
              "and every other certification behind these shapes is a LOAD pass; our loaded "
              "symbols carry real solids; RVT_WALL_REP=dummy restores the SerializedDummy rep"),
    "dummy": ("every certification behind these shapes is a LOAD pass; created "
              "walls carry a SerializedDummy rep (desktop Revit regenerates; "
              "the cloud viewer does NOT) and our loaded symbols carry real "
              "solids -- RENDER (baked geometry) is the render stream's "
              "second gate"),
}


def _wall_rep_of(build: Optional[Dict[str, Any]]) -> str:
    """The seq-103 rep kind the created walls carry ('solid' / 'dummy')."""
    created = (build or {}).get("created") or []
    solid = any(c.get("kind") == "wall" and c.get("rep") == "solid" for c in created)
    return "solid" if solid else "dummy"


def _honesty(build: Optional[Dict[str, Any]], verdict: Optional[Dict[str, Any]],
             version: Optional[Dict[str, Any]] = None, *,
             status_gate: Optional[Dict[str, Any]] = None,
             extra_stamps: Sequence[str] = (),
             release_line: Optional[str] = None) -> Dict[str, Any]:
    """The honesty box.  ``status_gate`` is the job runner's P0 gate for the
    delivered file (create: ``build.status_gate``; edit: the job's
    ``base_provenance`` gate): its PROOF-ONLY label is a STAMP wherever a
    reader looks (hard rule 1) -- ONE rule for every route."""
    stamps: List[str] = []
    if verdict and verdict.get("stamp"):
        stamps.append(str(verdict["stamp"]))
    label = str((status_gate or {}).get("status") or "")
    if "PROOF-ONLY" in label:
        stamps.append(label)
    stamps += list(extra_stamps)
    return {
        "tiers": {
            "self_checks": ("rvt.validate (0 errors), four-registry coherence, identity gate -- "
                            "prove OUR OWN invariants; reported per file below"),
            "autodesk_acceptance": ("NOT claimed by this run: only the Autodesk Viewer / Revit "
                                    "prove acceptance (upload -> 'translated' -> open the {3D} "
                                    "view). Report both tiers separately, never conflated."),
            "load_vs_render": LOAD_VS_RENDER[_wall_rep_of(build)],
        },
        "proof_only_stamps": stamps,
        "release": release_line or _release_line(version),
    }


def _release_line(version: Optional[Dict[str, Any]] = None) -> str:
    if version and version.get("status") == "fallback" and version.get("line"):
        return str(version["line"])
    out = version.get("output_release") if version else None
    rel = out or PIN.revit_release
    return (f"Revit {rel} target (the base and the schema are {rel}); Revit cannot open a "
            "newer file -- confirm the customer's Revit version before promising a .rvt "
            "(`--target-version N` makes the front door check, and degrade honestly, for you)")


# ---------------------------------------------------------------------------
# the IFC census: what the input held that did NOT reach the .rvt (issue #153)
# ---------------------------------------------------------------------------

def census_gaps(census: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The part of an intent census a QA engineer must see: dropped product
    classes, unreadable body-item types, products left without any body, and
    the relationship classes not read.  ``show`` is True whenever anything
    was dropped or unreadable -- the trigger for the MANIFEST.md section and
    the one build degradation line (a LABEL: delivery is unchanged)."""
    c = census or {}
    by_class = c.get("by_class") or {}
    body = c.get("body_items") or {}
    dropped = [{"class": cls, "count": int(row.get("dropped") or 0), "of": int(row.get("read") or 0),
                "reason": row.get("reason")}
               for cls, row in by_class.items() if int(row.get("dropped") or 0) > 0]
    n_dropped = sum(d["count"] for d in dropped)
    n_unreadable = int(body.get("unreadable") or 0)
    return {
        "show": bool(n_dropped or n_unreadable),
        "products_total": int(c.get("products_total") or 0),
        "schema": c.get("schema"),
        "dropped": dropped, "n_dropped": n_dropped,
        "unreadable_by_type": dict(body.get("unreadable_by_type") or {}),
        "n_unreadable": n_unreadable,
        "body_items_total": int(body.get("total") or 0),
        "readable_kinds": list(body.get("readable_kinds") or []),
        "bodiless": list(body.get("products_left_bodiless") or []),
        "relationships_ignored": list(c.get("relationships_ignored") or []),
    }


def _census_degradation(g: Dict[str, Any]) -> str:
    """The ONE build degradation line the census adds (only when g['show'])."""
    parts = []
    if g["n_dropped"]:
        parts.append(f"{g['n_dropped']} of {g['products_total']} products dropped ("
                     + ", ".join(f"{d['class']}×{d['count']}" for d in g["dropped"]) + ")")
    if g["n_unreadable"]:
        parts.append(f"{g['n_unreadable']} of {g['body_items_total']} body items unreadable ("
                     + ", ".join(f"{t}×{n}" for t, n in g["unreadable_by_type"].items()) + ")")
    return ("IFC census: " + "; ".join(parts) + " -- that content does not reach the .rvt; "
            "delivery unchanged (a label, hard rule 1); itemised under 'Not converted from the "
            "IFC' / manifest.json intent.summary.census")


# ---------------------------------------------------------------------------
# the status gate's AUTHORSHIP census note (issue #143 / #303): the gate says
# `census: STALE …` when the pinned bytes have no census entry and `census:
# UNAVAILABLE (…)` when the lookup could not even import -- either way the
# ledger fell back to the conservative reading and the manifest must SAY so
# (never a silent "user-supplied base" for our own pin)
# ---------------------------------------------------------------------------

def authorship_census_note(status_gate: Optional[Dict[str, Any]]) -> Optional[str]:
    """The one line a STALE / UNAVAILABLE authorship census adds to
    build.degradations and MANIFEST.md, or None when the census applied (a
    ``residue`` block is present) or the base simply has none (a sample, a
    user's ``--base``)."""
    note = (status_gate or {}).get("census")
    if not note:
        return None
    return (f"status-gate authorship census {note} -- the ledger fell back to the conservative "
            "reading (everything inherited from the base counted as the base's, nothing presumed "
            "ours), so the blocker count over-states, never under-states; the label and the "
            "delivered file are unaffected (hard rule 1)")


# ---------------------------------------------------------------------------
# plan notes (issue #465): every family plan's notes ride in intent.summary.
# family_plans[].notes and under MANIFEST.md's family-plans row; a note saying
# a schedule cell was DROPPED / DEFAULTED is also a build degradation (the panel
# silently rated from another cell or a default), a coerced label is not
# ---------------------------------------------------------------------------

#: the wording rvt.ifc.intent.parse_schedule_scalar gives every dropped / defaulted cell
DROPPED_CELL_MARK = " is not a usable "


def plan_note_degradations(intent_summary: Optional[Dict[str, Any]]) -> List[str]:
    """One degradation line per family plan whose notes say a schedule cell
    was dropped or defaulted (``'LP-1: PanelSchedule.MainsRating '4OO A' is
    not a usable current rating (not a number) -> ...'``), plus every plan's own
    ``degradations`` (built, but not as the input asked: a declared maker whose
    record is not held or refused the member, #692); ``[]`` when no plan carries
    either.  Plans saying the very same thing share one line."""
    by_text: Dict[str, List[str]] = {}
    for p in (intent_summary or {}).get("family_plans") or []:
        said = ([n for n in p.get("notes") or [] if DROPPED_CELL_MARK in n]
                + list(p.get("degradations") or []))
        if said:
            by_text.setdefault("; ".join(said), []).append(str(p.get("tag")))
    return [f"{', '.join(tags)}: {text}" for text, tags in by_text.items()]


#: the keys of each job-runner gate the EDIT route's manifest echoes under
#: edit.gates.<name> (the full dicts stay one hop away in edit.job_manifest):
#: the structural / validation / identity summaries, and for base_provenance
#: what the create routes' build.status_gate shows -- what the base IS (kind,
#: census block or why there is none, the pin a descendant was ledgered
#: against) and the ledger totals, so an edit of our own output reads
#: descends-from-pinned-genesis at the front door itself (#406)
_EDIT_GATE_KEYS = ("status", "errors", "warnings", "verdict", "issues", "kind", "report",
                   "identity", "reason", "deliverable", "base_is_autodesk_sample",
                   "base_kind", "residue", "census", "ledgered_against", "provenance_totals")


def status_gate_lines(sg: Optional[Dict[str, Any]], *, ledger_of: str = "this build") -> List[str]:
    """The MANIFEST.md lines of a P0 status gate -- ONE wording for the create
    routes' ``build.status_gate`` and the edit route's
    ``edit.gates.base_provenance``: the deliverability label + reason, then
    'base authorship (issue #143 census)': the pin (or the pin a descendant
    descends from + the descent evidence + the file it was ledgered against),
    the census numbers, the ledger totals; or the no-residue line (sample /
    user base, or our pin with a STALE / UNAVAILABLE census -- said, never
    silent, #303).  No authorship line when the gate recorded no base kind
    (skipped / crashed before classifying); ``[]`` for no gate at all."""
    sg = sg or {}
    if not sg:
        return []
    lines = [f"- deliverability (P0 gate): {sg.get('status')}"
             + (f" — {sg['reason']}" if sg.get("reason") else "")]
    res = sg.get("residue")
    if not res:
        if sg.get("base_kind"):
            why = f"census **{sg['census']}**" if sg.get("census") else "no census"
            lines.append(f"- base authorship: **{sg['base_kind']}** ({why}: everything inherited "
                         "from the base is ledgered as the base's)")
        return lines
    if res.get("descends_from"):                    # #284: NOT the pin's bytes, but grown on it
        d = res.get("descent") or {}
        pin = os.path.basename(str(sg.get("ledgered_against") or "")) or "the pin"
        head = (f"**{sg['base_kind']}** — descends from {res['descends_from']} "
                f"(Revit {res['revit_release']}; {d.get('probed_identical', 0):,} of "
                f"{d.get('pin_slots_probed', 0):,} {d.get('probed', 'composed slots')} "
                f"byte-identical, share {d.get('share')} ≥ {d.get('min_share')}), ledgered "
                f"against the pin `{pin}` and its census")
    else:
        head = f"**{sg['base_kind']}** {res['base_id']} (Revit {res['revit_release']})"
    disp = f"; recorded dispositions {res['by_disposition']}" if res.get("by_disposition") else ""
    tot = sg.get("provenance_totals") or {}
    lines.append(f"- base authorship (issue #143 census): {head} — {res['ours_by_composition']:,} "
                 f"of {res['host_elements']:,} base elements ours by composition; residue "
                 f"{res['identical_to_ancestor']:,} still byte-identical to the Autodesk ancestor "
                 f"({res['never_authored']} never authored, {res['landed_but_identical']} "
                 f"re-emitted identically by our constructors{disp})")
    lines.append(f"- {ledger_of}: {tot.get('ours-created', 0)} created elements ours, "
                 f"{tot.get('transitive-cloned', 0)} created with lineage into the residue"
                 + (f", {tot['ours-modified']} residue slot(s) edited and still derived"
                    if tot.get("ours-modified") else ""))
    return lines


def _honesty_lines(hon: Dict[str, Any]) -> List[str]:
    """The MANIFEST.md 'Honesty' section (stamps, tiers, release), every route."""
    lines = ["", "## Honesty"]
    lines += [f"- **{s}** (a label, never a refusal)" for s in hon.get("proof_only_stamps") or []]
    lines += [f"- {k}: {t}" for k, t in (hon.get("tiers") or {}).items()]
    lines.append(f"- release: {hon.get('release')}")
    return lines


# ---------------------------------------------------------------------------
# the pin block: the registry slot the resolved base answers to (issue #264)
# ---------------------------------------------------------------------------

def resolved_pin(base: ResolvedBase, release: Optional[int] = None, *,
                 pin: GenesisPin = PIN) -> Dict[str, Any]:
    """The registry pin the run's base was checked against, as ``base.pin``.

    A ``--target-version 2025`` (or 2024) run resolves THAT release's slot
    (``G_ABPD_2025``), so the pin block must name that slot's relpath / sha256 /
    certification entry -- never the default (2026) pin beside a 2025 base.
    The slot is the one whose pinned sha256 IS the resolved base's digest (any
    pinned resolution, and a ``--base`` copy that happens to be the certified
    bytes); failing that, ``release`` (the run's output release, or the target
    a refused run was resolved against); failing that, the registry default,
    which yields ``pin.as_json()`` unchanged."""
    digest = str(base.sha256 or "").lower()
    year = next((y for y in pin.release_years()
                 if digest and str((pin.release_slot(y) or {}).get("sha256") or "").lower() == digest),
                release)
    out = pin.as_json()
    if year is None or int(year) == int(pin.revit_release):
        return out                          # the default slot IS the default record
    slot = pin.release_slot(int(year)) or {}
    if not slot.get("sha256"):              # unknown / unpinned year: the default stands
        return out
    out.update({k: slot[k] for k in ("id", "relpath", "sha256", "bytes", "lineage") if k in slot},
               revit_release=str(int(year)), certification=dict(slot.get("certification") or {}))
    return out


def _version_release(version: Optional[Dict[str, Any]]) -> Optional[int]:
    """The release a version block names: what was produced, else what was
    requested (a refused run produced nothing), else None."""
    v = version or {}
    return next((int(v[k]) for k in ("output_release", "requested")
                 if str(v.get(k) or "").isdigit()), None)


# ---------------------------------------------------------------------------
# create routes (prompt / ifc)
# ---------------------------------------------------------------------------

def build_manifest(*, route: str, inputs: Dict[str, Any], base: ResolvedBase,
                   out_dir: str, intent_summary: Optional[Dict[str, Any]],
                   intent_json: Optional[str], build: Optional[Dict[str, Any]],
                   coverage: Optional[Dict[str, Any]] = None,
                   handoff: Optional[Dict[str, Any]] = None,
                   errors: Optional[List[str]] = None,
                   version: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The manifest for the two CREATE routes (prompt / ifc)."""
    build = build or {}
    verdict = build.get("verdict") or {}
    files = build.get("files") or {}
    created = build.get("created") or []
    m: Dict[str, Any] = {
        "tool": TOOL, "tool_version": TOOL_VERSION,
        "product": "tekton (multi-surface front door)",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "route": route,
        "inputs": inputs,
        "out_dir": _relp(out_dir),
    }
    if version:
        m["target_version"] = dict(version)
        ifc_add = version.get("ifc_addition")
        if ifc_add:
            ff = file_facts(os.path.join(repo_root(), str(ifc_add))
                            if not os.path.isabs(str(ifc_add)) else str(ifc_add))
            if ff:
                m["target_version"]["ifc_addition_facts"] = ff
    if handoff:
        m["prompt_handoff"] = handoff
    if coverage:
        m["prompt_coverage"] = coverage
    m["base"] = {
        **base.as_json(),
        "pin": resolved_pin(base, _version_release(version)),
        "policy": ("the front door authors ONLY on the certified genesis base (our composed "
                   "project, no Autodesk-authored base content) or a user-supplied non-sample "
                   "base; NEVER an Autodesk sample"),
    }
    m["intent"] = {"summary": intent_summary, "json": _relp(intent_json)}
    m["build"] = {
        "combination_verdict": verdict,
        "files": {role: file_facts(p) for role, p in files.items()
                  if p and os.path.isfile(str(p))},
        "families_dir": _relp(files.get("families_dir")),
        "stages": build.get("stages"),
        "load": build.get("load"),
        "families": {k: v for k, v in (build.get("families") or {}).items() if k != "families"},
        "family_files": [{"tag": f.get("tag"), "path": f.get("path"), "ok": f.get("ok"),
                          "catalog": f.get("catalog"), "variant": f.get("variant"),
                          "reason": f.get("reason") or f.get("error")}
                         for f in ((build.get("families") or {}).get("families") or [])],
        "elements_created": created,
        "project_info": build.get("project_info") or {},
        "levels": build.get("levels") or {},
        "degradations": list(build.get("degradations") or []),
        "circuits": build.get("circuits") or {},
        "validation": build.get("validation") or {},
        "status_gate": build.get("status_gate") or {},
        "seconds": build.get("seconds"),
        "log": _relp(build.get("build_log")),          # the quiet stage log (issue #312)
        "errors": (build.get("errors") or []) + list(errors or []),
    }
    gaps = census_gaps((intent_summary or {}).get("census"))
    m["intent"]["census_gaps"] = gaps
    if gaps["show"]:                       # a LABEL on the delivered file(s), never a refusal
        m["build"]["degradations"].append(_census_degradation(gaps))
    m["build"]["degradations"] += plan_note_degradations(intent_summary)   # dropped cells: said
    note = authorship_census_note(m["build"]["status_gate"])
    if note:                               # STALE / UNAVAILABLE base census: said, never silent
        m["build"]["degradations"].append(note)
    m["crud"] = crud_affordances(files, created, out_dir=out_dir)
    m["coverage_matrix"] = coverage_cross_reference(created)
    m["honesty"] = _honesty(build, verdict, version, status_gate=m["build"]["status_gate"])
    m["report"] = report_block(
        degradations=m["build"]["degradations"],
        validation=_build_validation_summary(m["build"]["validation"]),
        counts={**created_counts(created), "elements_created": len(created),
                "circuits": int((build.get("circuits") or {}).get("circuits_built") or 0)})
    m["status"] = _rollup_status(m)
    return m


# ---------------------------------------------------------------------------
# shared: the one-line status reason (create + edit routes)
# ---------------------------------------------------------------------------

_STATUS_REASON_MAX = 160        # errors[0] rides whole in `FAILED (...)` up to this


def _status_reason(error: Any) -> str:
    """One line of ``error`` for the status sentence a skill relays verbatim:
    whole when it fits :data:`_STATUS_REASON_MAX`, else cut at a word
    boundary with ``...`` (``rvt._clause.clip`` -- the one rule)."""
    return clip(str(error), _STATUS_REASON_MAX)


def _rollup_status(m: Dict[str, Any]) -> str:
    b = m.get("build") or {}
    if b.get("errors"):
        return "FAILED (" + _status_reason(b["errors"][0]) + ")"
    files = b.get("files") or {}
    if not files:
        return "NO-OUTPUT (see build.degradations / errors)"
    val = b.get("validation") or {}
    if val and not _self_checks_ok(val):
        bad = [r for r, g in val.items() if not (g or {}).get("self_checks_ok")]
        return "SELF-CHECKS FAILED (" + ", ".join(bad) + ")"
    sg = b.get("status_gate") or {}
    stamps = (m.get("honesty") or {}).get("proof_only_stamps") or []
    if sg.get("deliverable") and not stamps:
        return "DELIVERABLE (all gates passed; genesis base)"
    if stamps or sg.get("status"):
        return "PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)"
    return "BUILT (self-checks PASS)"


# ---------------------------------------------------------------------------
# the compact `report` block: manifest["report"] == the ONE --json result's
# `report` (issue #185)
# ---------------------------------------------------------------------------

REPORT_DEGRADATIONS_CAP = 10           # degradations relayed before the "+N more" tail
_REPORT_DEGRADATION_MAX = 500          # one degradation rides whole up to this (clip's rule); longest seen: 401
_CREATED_KINDS = {"families": "family(.rfa)", "walls": "wall",
                  "equipment_instances": "equipment-instance",
                  "wiring_devices": "fixture-instance", "loaded_families": "loaded-family"}
_COUNT_KEYS = (*_CREATED_KINDS, "elements_created", "circuits", "edited", "deleted")
_NO_VALIDATION = {"verdict": "NOT-RUN", "errors": 0, "warnings": 0, "self_checks_ok": False, "files": 0}


def created_counts(rows: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, int]:
    """ONE tally of ``build.elements_created`` rows by kind -- MANIFEST.md's
    "created:" line and the ``report`` block count the same way."""
    kinds = [r.get("kind") for r in rows or []]
    return {name: kinds.count(kind) for name, kind in _CREATED_KINDS.items()}


def _self_checks_ok(validation: Optional[Dict[str, Any]]) -> bool:
    """Every emitted file's V-stage gates passed (and at least one file was gated)."""
    return bool(validation) and all((g or {}).get("self_checks_ok") for g in validation.values())


def _build_validation_summary(validation: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll ``build.validation[role].validate`` up over every emitted file: any
    non-VALID verdict wins, errors / warnings are summed."""
    validation = validation or {}
    gates = [((g or {}).get("validate") or {}) for g in validation.values()]
    verdicts = [str(g.get("verdict") or "NOT-RUN") for g in gates]
    return {"verdict": next((v for v in verdicts if v != "VALID"), "VALID" if gates else "NOT-RUN"),
            "errors": sum(int(g.get("n_errors") or 0) for g in gates),
            "warnings": sum(int(g.get("n_warnings") or 0) for g in gates),
            "self_checks_ok": _self_checks_ok(validation), "files": len(gates)}


def _edit_validation_summary(gate: Optional[Dict[str, Any]], *, hard_gates_passed: Any,
                             has_output: bool) -> Dict[str, Any]:
    """The edit route's one file is judged by the job runner's validation gate
    (PASS / FAIL / SKIPPED + counts), said in the create routes' words."""
    gate = gate or {}
    status = gate.get("status")
    return {"verdict": {"PASS": "VALID", "FAIL": "INVALID"}.get(status, status or "NOT-RUN"),
            "errors": int(gate.get("errors") or 0), "warnings": int(gate.get("warnings") or 0),
            "self_checks_ok": bool(hard_gates_passed), "files": int(bool(has_output))}


def _budgeted(lines: Sequence[Any]) -> List[str]:
    """Order kept, duplicates dropped, each line whole up to
    :data:`_REPORT_DEGRADATION_MAX` (``clip``'s rule), the list capped at
    :data:`REPORT_DEGRADATIONS_CAP` with a '+N more' tail naming the long form."""
    out = [clip(s, _REPORT_DEGRADATION_MAX) for s in dict.fromkeys(str(x) for x in lines)]
    if len(out) > REPORT_DEGRADATIONS_CAP:
        more = len(out) - REPORT_DEGRADATIONS_CAP
        out = out[:REPORT_DEGRADATIONS_CAP] + [
            f"... +{more} more degradation(s), see MANIFEST.md (the manifest's degradations list)"]
    return out


def report_block(*, degradations: Sequence[Any] = (), validation: Optional[Dict[str, Any]] = None,
                 counts: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """The compact ``report`` block (issue #185): every degradation (budgeted),
    the validator summary {verdict, errors, warnings, self_checks_ok, files}
    and the counts, assembled by each manifest builder from what it natively
    holds and stored as ``manifest["report"]`` -- so ``AuthorResult.as_json()``
    relays it in the ONE ``--json`` result and a skill never opens
    ``manifest.json`` (45-225 KB) in a second tool call to say them.  Called
    with no arguments it is the empty-but-present block of a result that has
    no manifest (same keys, zero counts, verdict NOT-RUN).  The PROOF-ONLY
    stamps and the target-version line keep their #24 homes (``stamps``,
    ``release.line``) and are not repeated here."""
    counts = counts or {}
    return {"degradations": _budgeted(degradations),
            "validation": dict(validation or _NO_VALIDATION),
            "counts": {k: int(counts.get(k) or 0) for k in _COUNT_KEYS}}


# ---------------------------------------------------------------------------
# the --rvt (edit) route
# ---------------------------------------------------------------------------

def edit_manifest(*, inputs: Dict[str, Any], base_note: str, out_dir: str,
                  edit_spec: Dict[str, Any], run: Dict[str, Any],
                  editables_before: Optional[Dict[str, Any]] = None,
                  errors: Optional[List[str]] = None,
                  version: Optional[Dict[str, Any]] = None,
                  input_release: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    job = run.get("job_manifest") or {}
    out_rvt = run.get("out_rvt")
    gates = {k: {kk: vv for kk, vv in (g or {}).items() if kk in _EDIT_GATE_KEYS}
             for k, g in (job.get("gates") or {}).items()}
    bp = gates.get("base_provenance") or {}       # the P0 gate: stamped + rendered like build's
    degradations = list(run.get("degradations") or [])
    note = authorship_census_note(bp)             # STALE / UNAVAILABLE census: said (#303)
    if note:
        degradations.append(note)
    # the INPUT's era / release, classified before anything opened it (#176):
    # a refused input's one line IS the status and the release story; an
    # unverified release stamps the honesty box and the status; known just rides
    ir = input_release or {}
    refused_line = str(ir["line"]) if ir.get("status") == "refused" else None
    unverified = ir.get("status") == "unverified"
    status = job.get("status") or ("FAILED (no job manifest)" if run.get("rc") else "UNKNOWN")
    if errors and run.get("rc") is None:
        # the job never started (cannot open/plan, edit not understood, the
        # run raised): the reason IS the status, like the create routes'
        # `FAILED (<errors[0]>)` -- never "rc None" with the cause elsewhere
        status = "FAILED (" + _status_reason(errors[0]) + ")"
    elif errors or (run.get("rc") not in (0, None) and not job):
        status = "FAILED (edit did not complete: rc %s)" % (run.get("rc"),)
    if refused_line:
        status = refused_line
    elif unverified:
        from .input_release import UNVERIFIED_TAG
        status = f"{status}; {UNVERIFIED_TAG} (input Revit {ir.get('year')})"
    m: Dict[str, Any] = {
        "tool": TOOL, "tool_version": TOOL_VERSION,
        "product": "tekton (multi-surface front door)",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "route": "rvt",
        "inputs": inputs,
        "out_dir": _relp(out_dir),
        "base": {"note": base_note,
                 "input_file": inputs.get("rvt"),
                 "input_is_autodesk_sample": (job.get("base") or {}).get("is_autodesk_sample")},
        "edit": {
            "spec": edit_spec,
            "delegated_to": "tools/rvt_job.py edit (rvt.manipulate ONE commit + rvt.mutate adds "
                            "+ structural / validation / identity / provenance gates)",
            "ops_json": _relp(run.get("ops_json")),
            "job_manifest": _relp(run.get("job_manifest_json")),
            "job_validation_report": _relp(run.get("validation_json")),
            "job_status": job.get("status"),
            "hard_gates_passed": job.get("hard_gates_passed"),
            "gates": gates,
            "log": _relp(run.get("log_path")),           # the quiet edit's job log: a PATH, like
            "degradations": degradations,                # build.log (issue #373)
            "rc": run.get("rc"),
        },
        "output": file_facts(out_rvt),
        "elements": {"edited": (job.get("edit") or {}).get("edited_ids"),
                     "deleted": (job.get("edit") or {}).get("deleted_ids"),
                     "created": (job.get("edit") or {}).get("created_ids"),
                     "created_detail": (job.get("elements") or {}).get("created")},
        "crud": {
            "note": ("the SAME file remains fully editable: run --rvt --edit again on the "
                     "output; `info`/`deps` reads what is there"),
            "inspect": f"python tools/rvt_edit.py {_relp(out_rvt) or '<out.rvt>'} info",
            "entrypoint": (f"python tools/frontdoor.py author --rvt {_relp(out_rvt) or '<out.rvt>'} "
                           "--edit \"<sentence | ops.json | inline JSON>\" --out <dir>"),
            "editables_before": editables_before,
        },
        "honesty": _honesty(None, None, version, status_gate=bp,
                            extra_stamps=([ir["stamp"]] if unverified else ()),
                            release_line=refused_line),
        "status": status,
        "errors": list(errors or []),
    }
    m["report"] = report_block(
        degradations=degradations,
        validation=_edit_validation_summary(gates.get("validation"),
                                            hard_gates_passed=job.get("hard_gates_passed"),
                                            has_output=bool(m["output"])),
        counts={"elements_created": len(m["elements"]["created"] or []),
                "edited": len(m["elements"]["edited"] or []),
                "deleted": len(m["elements"]["deleted"] or [])})
    if version:
        m["target_version"] = dict(version)
    if ir:
        m["input_release"] = dict(ir)
    return m


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------

def write_manifest(manifest: Dict[str, Any], out_dir: str) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, "manifest.json")
    with open(jp, "w") as fh:
        _jsonsafe.dump(manifest, fh, indent=1)
    mp = os.path.join(out_dir, "MANIFEST.md")
    with open(mp, "w") as fh:
        fh.write(_render_md(manifest))
    paths = {"json": jp, "md": mp}
    for block in ("build", "edit"):                  # the quiet stage log that opened (#312 /
        log = (manifest.get(block) or {}).get("log") # #373): named beside them by its own file
        if log:                                      # name, never a deliverable in `files`
            name = os.path.basename(str(log))
            paths[name] = os.path.join(out_dir, name)
    return paths


def _render_md(m: Dict[str, Any]) -> str:
    L: List[str] = []
    ap = L.append
    ap(f"# Deliverable manifest — route `{m.get('route')}`")
    ap("")
    ap(f"**Status:** {m.get('status')}")
    ap(f"**Tool:** {m.get('tool')} v{m.get('tool_version')} · {m.get('generated_at')}")
    tv = m.get("target_version") or {}
    if tv:
        ap("")
        ap("## Target Revit version")
        ap(f"- requested: {tv.get('requested')} · output release: {tv.get('output_release')} "
           f"· status: **{tv.get('status')}**")
        if tv.get("line"):
            ap(f"- **{tv.get('line')}**")
        if tv.get("ifc_addition"):
            ap(f"- IFC addition (version-agnostic): `{tv.get('ifc_addition')}` — "
               f"{tv.get('ifc_addition_source')}")
        bs = tv.get("base_status") or {}
        if bs and not bs.get("certified"):
            ap(f"- the Revit {tv.get('requested')} genesis base: {bs.get('status')} "
               f"(lineage {bs.get('id')}; docs/writer/genesis-2025-plan.md)")
        if tv.get("note"):
            ap(f"- {tv.get('note')}")
    ir = m.get("input_release")
    if ir:
        ap("")
        ap("## Input release")
        ap(f"- Revit {ir.get('year')} · BasicFileInfo era {ir.get('era')} · **{ir.get('status')}**")
        for key in ("line", "stamp"):
            if ir.get(key):
                ap(f"- **{ir[key]}**")
        if ir.get("note"):
            ap(f"- {ir['note']}")
    ap("")
    inp = m.get("inputs") or {}
    ap("## Input")
    for k, v in inp.items():
        if v not in (None, "", [], {}):
            ap(f"- **{k}**: `{v}`" if not isinstance(v, (dict, list)) else f"- **{k}**: `{json.dumps(v)[:200]}`")
    if m.get("route") == "rvt":
        e = m.get("edit") or {}
        ap("")
        ap("## Edit")
        ap(f"- delegated to: {e.get('delegated_to')}")
        for u in (e.get("spec") or {}).get("understood") or []:
            ap(f"- understood: `{json.dumps(u)[:200]}`")
        for u in (e.get("spec") or {}).get("unparsed") or []:
            ap(f"- **unparsed**: {u}")
        ap(f"- job status: {e.get('job_status')} (hard gates passed: {e.get('hard_gates_passed')})")
        gates = e.get("gates") or {}
        for gk, gv in gates.items():
            ap(f"  - gate `{gk}`: {gv.get('status')}"
               + (f" (errors {gv.get('errors')}, warnings {gv.get('warnings')})" if 'errors' in gv else ""))
        L.extend(status_gate_lines(gates.get("base_provenance"),
                                   ledger_of="this file's ledger (everything the chain created)"))
        o = m.get("output") or {}
        if o:
            ap(f"- output: `{o.get('relpath')}` ({o.get('bytes')} bytes, sha256 `{str(o.get('sha256'))[:16]}…`)")
        el = m.get("elements") or {}
        ap(f"- edited {el.get('edited')} · deleted {el.get('deleted')} · created {el.get('created')}")
        for d in e.get("degradations") or []:
            ap(f"- **degradation**: {d}")
        if e.get("log"):
            ap(f"- job log (plan / commit / gate progress): `{e['log']}`")
        L.extend(_honesty_lines(m.get("honesty") or {}))
        ap("")
        ap("## CRUD (the result stays editable)")
        c = m.get("crud") or {}
        ap(f"- inspect: `{c.get('inspect')}`")
        ap(f"- next edit: `{c.get('entrypoint')}`")
        return "\n".join(L) + "\n"

    b = m.get("base") or {}
    ap("")
    ap("## Base (certified genesis base — never an Autodesk sample)")
    ap(f"- file: `{b.get('path')}` (source: {b.get('source')}, sha256 `{str(b.get('sha256'))[:16]}…`)")
    ap(f"- pinned: {b.get('pinned')} · certified genesis base: {b.get('certified_genesis_base')} · "
       f"Autodesk sample: {b.get('is_autodesk_sample')}")
    cert = (b.get('certification') or {})
    if cert.get("proves") or cert.get("verdict"):
        ap(f"- certification: {cert.get('proves', '')}")
        ap(f"  - verdict: {cert.get('verdict', '')}")
    elif cert:                                  # a per-release slot cites its ledger entry
        ap(f"- certification: `{cert.get('ledger')}` entry `{cert.get('entry')}`"
           + (f" — {cert['required']}" if cert.get("required") else ""))
    for w in b.get("warnings") or []:
        ap(f"- **base warning**: {w}")
    it = (m.get("intent") or {}).get("summary") or {}
    ap("")
    ap("## Intent")
    if it:
        ap(f"- project: {it.get('project')}")
        rm = it.get("room")
        if rm:
            ap(f"- room `{rm.get('name')}`: {rm.get('walls')} walls "
               f"({rm.get('walls_synthesized')} synthesized), {rm.get('doors')} doors")
        ap(f"- equipment ({it.get('equipment_total')}): "
           + ", ".join(f"{k}×{v}" for k, v in (it.get('equipment_by_kind') or {}).items()))
        fps = it.get("family_plans_by_status") or {}
        ap("- family plans: " + ", ".join(f"{k} {v}" for k, v in fps.items()))
        for p in it.get("family_plans") or []:      # each plan's notes (#465); nothing when none
            for n in p.get("notes") or []:
                ap(f"  - note: `{p.get('tag')}` — {n}")
            for n in p.get("degradations") or []:  # built, not as asked (#692) -- also up top
                ap(f"  - **said**: `{p.get('tag')}` — {n}")
        ap(f"- feeder edges: {len(it.get('feeder_edges') or [])}")
        ops = it.get("other_products") or []
        if ops:                                # prompt-route entries carry no ifcClass: kind only
            ap(f"- recorded, not modelled ({len(ops)}): "
               + ", ".join(f"{o.get('name') or o.get('tag')} ("
                           + (f"{o['ifcClass']} → " if o.get("ifcClass") else "") + f"{o.get('kind')})"
                           for o in ops[:24]))
    gaps = (m.get("intent") or {}).get("census_gaps") or census_gaps(it.get("census"))
    cs = it.get("census") or {}
    if cs.get("error"):                        # the observer failed; the delivery did not (rule 1)
        ap(f"- IFC census: **unavailable** ({cs['error']}) — the file is delivered regardless; "
           "what did not convert is not enumerated for this run")
    elif cs:
        tot = cs.get("totals") or {}
        bi = cs.get("body_items") or {}
        ap(f"- IFC census ({cs.get('schema')}): {cs.get('products_total')} products read — "
           f"{tot.get('mapped', 0)} mapped, {tot.get('recorded', 0)} recorded only, "
           f"{gaps['n_dropped']} dropped; body items {bi.get('read', 0)}/{bi.get('total', 0)} read, "
           f"{gaps['n_unreadable']} unreadable — "
           + ("see **Not converted from the IFC** below" if gaps["show"] else "nothing dropped or unreadable"))
    ap(f"- intent JSON: `{(m.get('intent') or {}).get('json')}`")
    if gaps["show"]:
        ap("")
        ap("## Not converted from the IFC")
        ap(f"- the input held {gaps['products_total']} products ({gaps['schema']}); the content below "
           "did NOT reach the delivered .rvt — the file is delivered all the same (a label, never a "
           "refusal); full per-class census in `manifest.json` → intent.summary.census / `intent.json` → census")
        for d in gaps["dropped"]:
            ap(f"- **dropped** {d['class']} ×{d['count']}"
               + (f" of {d['of']}" if d["of"] != d["count"] else "") + f" — {d.get('reason') or 'not read'}")
        if gaps["n_unreadable"]:
            ap(f"- **unreadable body items** ({gaps['n_unreadable']} of {gaps['body_items_total']}): "
               + ", ".join(f"{t} ×{n}" for t, n in gaps["unreadable_by_type"].items())
               + f" — the resolver reads {', '.join(gaps['readable_kinds'])}; anything else loses its geometry")
        for b in gaps["bodiless"][:24]:
            ap(f"- **left without any body**: '{b.get('tag') or b.get('name')}' ({b.get('ifcClass')}, "
               f"{b.get('unreadable')}/{b.get('body_items')} body items unreadable) — recorded at its "
               "placement with no extents")
        for r in gaps["relationships_ignored"]:
            ap(f"- relationship not read: {r.get('class')} ×{r.get('count')} — {r.get('effect')}")
    cov = m.get("prompt_coverage")
    if cov:
        ap("")
        ap("## Prompt coverage (what the fallback parser understood)")
        for u in (cov.get("understood") or [])[:16]:
            ap(f"- understood: “{u.get('clause')}” → {u.get('as')}")
        if cov.get("not_built"):
            ap("- **recognised, NOT modelled**: " + ", ".join(f"{n.get('text')} ({n.get('kind')})"
                                                           for n in cov["not_built"]))
            for n in cov["not_built"][:16]:      # the MEP taxonomy's line per kind (#692 DONE 3)
                if n.get("label"):               # the reason leads with 'Label: Revit category'
                    ap(f"  - “{n.get('text')}” → {n.get('reason')}")
        if cov.get("ignored_words"):
            ap("- **ignored words**: " + ", ".join(cov["ignored_words"][:24]))
        for d in (cov.get("defaults_applied") or [])[:24]:
            ap(f"- default: {d}")
        for w in (cov.get("warnings") or []):
            ap(f"- **warning**: {w}")
    ho = m.get("prompt_handoff")
    if ho:
        ap("")
        ap("## Primary prompt path — the AI-surface handoff")
        for k, v in ho.items():
            ap(f"- {k}: `{v}`")
    build = m.get("build") or {}
    ap("")
    ap("## Build")
    v = build.get("combination_verdict") or {}
    if v:
        ap(f"- degrade mode: **{v.get('mode')}** — {v.get('reason')}")
        if v.get("stamp"):
            ap(f"- **STAMP: {v.get('stamp')}** (a label: the file below is delivered)")
        if v.get("open_bug_text"):
            ap(f"- open cell: {v.get('open_bug_text')}")
    files = build.get("files") or {}
    for role, f in files.items():
        ap(f"- file **{role}**: `{f.get('relpath')}` ({f.get('bytes')} bytes, sha256 `{str(f.get('sha256'))[:16]}…`)")
    for c in (build.get("elements_created") or []):
        if c.get("kind") == "family(.rfa)":
            src = (f"{c.get('catalog')} {c.get('variant')}" if c.get("catalog")
                   else "house family (our own modeled extents; no catalog line covers the rating)")
            ap(f"- family: `{c.get('name')}` ({c.get('tag')}; {src}; ok={c.get('ok')})")
    created_rows = build.get("elements_created") or []
    n = created_counts(created_rows)
    devices = [c for c in created_rows if c.get("kind") == "fixture-instance"]
    ap(f"- created: {n['walls']} walls, {n['equipment_instances']} equipment instances, "
       + (f"{n['wiring_devices']} wiring devices, " if devices else "")
       + f"{n['loaded_families']} loaded families")
    if devices:
        ap("- device schedule (one Electrical Fixtures instance per row, all on ONE shared "
           "generated family; free-standing upright at the wall face, PROOF-ONLY like the boards):")
        ap("")
        ap("| tag | id | device | V | VA | height AFF | at (ft) | level |")
        ap("|---|---|---|---|---|---|---|---|")
        for c in devices:
            s = c.get("schedule") or {}
            pos = ", ".join(f"{float(x):g}" for x in (c.get("position_ft") or []))
            ap(f"| {c.get('tag')} | {c.get('elem_id')} | {s.get('DeviceType') or c.get('equip_kind')} "
               f"| {s.get('Voltage', '')} | {s.get('Load', '')} | {s.get('MountingHeight', '')} in "
               f"| {pos} | {c.get('level') or ''} |")
        ap("")
    pi = build.get("project_info") or {}
    if pi.get("ok"):
        ident = pi.get("after") or {}
        ap(f"- project information (ProjectInfo {pi.get('elem_id')}): "
           + ", ".join(f"{k}='{v}'" for k, v in ident.items() if v)
           + " (the element's other fields blank)")
    lv = build.get("levels") or {}
    if lv.get("levels"):
        ap("- levels (the base's building-story datums, "
           + ("renamed / re-elevated" if lv.get("written") else "unchanged") + "): "
           + ", ".join(f"{b.get('id')} → '{b.get('name')}' @ {b.get('elevation_ft'):g} ft "
                       f"(Level {b.get('base_id')}, was '{b.get('base_name')}' @ "
                       f"{b.get('base_elevation_ft'):g} ft)" for b in lv["levels"]))
        for nb in lv.get("not_built") or []:
            ap(f"- **level NOT created**: {nb.get('reason')}")
    for role, g in (build.get("validation") or {}).items():
        val = (g or {}).get("validate") or {}
        idg = (g or {}).get("identity") or {}
        cen = (g or {}).get("census") or {}
        ap(f"- self-checks **{role}**: validator {val.get('verdict')} "
           f"({val.get('n_errors')} errors, {val.get('n_warnings')} warnings); "
           f"registries coherent={cen.get('coherent')}; identity {idg.get('status')}")
    L.extend(status_gate_lines(build.get("status_gate")))
    for d in (build.get("degradations") or []):
        ap(f"- **degradation**: {d}")
    for e in (build.get("errors") or []):
        ap(f"- **error**: {str(e)[:300]}")
    if build.get("log"):
        ap(f"- stage log (per-family / per-stage progress): `{build['log']}`")
    L.extend(_honesty_lines(m.get("honesty") or {}))
    crud = m.get("crud") or {}
    ap("")
    ap("## CRUD — everything created is editable / deletable")
    ap(f"- entrypoint: `{crud.get('entrypoint')}`")
    for r in (crud.get("elements") or [])[:24]:
        mods = r.get("modify") or {}
        ap(f"- `{r.get('tag')}` (id {r.get('elem_id')}, {r.get('kind')}): "
           + "; ".join(f"{k}: `{(mv or {}).get('text_edit')}`" for k, mv in mods.items()
                       if isinstance(mv, dict) and mv.get('text_edit')))
    na = next((r.get("not_available") for r in (crud.get("elements") or [])
               if r.get("not_available")), None)
    if na:
        for k, why in na.items():
            ap(f"- not available on created instances — **{k}**: {why}")
    lo = crud.get("layer_operations") or {}
    for k, t in lo.items():
        ap(f"- {k}: {t}")
    cm = m.get("coverage_matrix") or {}
    if cm.get("cells_exercised"):
        ap("- coverage-matrix cells exercised: " + ", ".join(
            f"{c['category']}:{c['verb']}" for c in cm["cells_exercised"]))
    return "\n".join(L) + "\n"
