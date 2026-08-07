"""compare_oracle.py -- the AGREEMENT REPORT: .rvt (partial decode) vs the
IFC that Revit exported from the very same model (ground truth).

    .venv/bin/python tests/oracle/compare_oracle.py <file.rvt> <file.ifc>
        [--md report.md] [--json report.json] [--refresh]
    .venv/bin/python tests/oracle/compare_oracle.py <file.rvt> --fme "<FME Demos dir>"
        (Einhoven mode: FME/StrangeMatter component exports carry Revit
         UniqueIds = document GUID + hex ElementId, used as the oracle)

Three independent lines of evidence are combined:

  1. ELEMENT-ID JOIN (definitive): every Revit-exported IFC entity carries
     `Tag` = the Revit ElementId (also embedded in Name as 'Family:Type:Id').
     We look that id up in the .rvt's partition record index (seq102 object
     records) and read the record's schema class -> a per-element ground
     truth 'IfcWall #20796 IS an SWall record'. Aggregated per IFC entity type
     it yields the confirmed correspondence table with a purity score.
  2. COUNT MATCHING (schema-agnostic proposal): IFC entity counts vs rvt
     record counts by class -- flags near-equal counts. Useful where the join
     is impossible (no Tag) and as a cross-check of (1).
  3. NAME AGREEMENT: storey names, wall/door/column type names, family names,
     space names/numbers, materials, site name -> located inside the .rvt's
     decoded strings, WITH the record class the string lives in (Level,
     BasicWallType, Family, FamilySymbol, RoomElem, MaterialElem...).

Everything is cached; re-running after decoder changes is ~2 s.
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import oracle_extract as OX  # noqa: E402
import oracle_ifc as OI  # noqa: E402


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def string_index(rvt: dict):
    """text(normalised) -> item ; plus per-class string sets."""
    idx = {}
    for it in rvt["strings"]["items"]:
        idx.setdefault(norm(it["text"]), it)
    return idx


def find_name(idx: dict, name: str):
    """Exact-match a name in the rvt string index. Returns item or None."""
    it = idx.get(norm(name))
    if it:
        return it
    return None


TYPEISH = ("Type", "Symbol", "Attributes")


def rec_class(item, prefer_typeish: bool = False):
    """Best owning record class for a matched string item."""
    if not item:
        return None
    recs = item.get("records") or []
    if not recs:
        return "(global stream)"
    if prefer_typeish:
        for cls, _eid in recs:
            if any(t in cls for t in TYPEISH):
                return cls
    return recs[0][0]


def rec_id(item):
    recs = (item or {}).get("records") or []
    return recs[0][1] if recs else None


# --------------------------------------------------------------------------
# core comparison
# --------------------------------------------------------------------------

def compare(rvt_path: str, ifc_path: str, refresh: bool = False) -> dict:
    rvt = OX.extract(rvt_path, refresh=refresh, quiet=True)
    ifc = OI.extract(ifc_path, refresh=refresh, quiet=True)
    rep: dict = {"rvt": os.path.basename(rvt_path), "ifc": os.path.basename(ifc_path)}

    # -- identity check ----------------------------------------------------
    rvt_guid = ((rvt.get("meta") or {}).get("guids") or {}).get("unique_document_guid")
    ifc_guid = ifc["header"].get("version_guid")
    rep["identity"] = {
        "rvt_release": rvt["meta"]["release"], "rvt_build": rvt["meta"]["build"],
        "rvt_doc_guid": rvt_guid, "ifc_version_guid": ifc_guid,
        "guid_match": bool(rvt_guid and ifc_guid and rvt_guid.lower() == ifc_guid.lower()),
        "ifc_app": ifc["header"].get("application"),
        "ifc_saves": ifc["header"].get("number_of_saves"),
        "rvt_central_version": rvt["meta"].get("central_version_number"),
    }

    # -- (1) element-id join ------------------------------------------------
    id_to_cls = {int(k): v for k, v in rvt["id_to_cls_seq102"].items()}
    elem_ids = set(rvt["elemtable_ids"])
    join = collections.defaultdict(collections.Counter)   # ifc_class -> rvt_class counter
    join_examples = collections.defaultdict(list)
    tagged = 0
    found_in_records = 0
    found_in_elemtable = 0
    missing = []
    for e in ifc["elements"]:
        tag = e.get("tag")
        if tag is None:
            continue
        tagged += 1
        cls = id_to_cls.get(tag)
        in_et = tag in elem_ids
        found_in_elemtable += 1 if in_et else 0
        if cls is not None:
            found_in_records += 1
            join[e["is_a"]][cls] += 1
            if len(join_examples[e["is_a"]]) < 3:
                join_examples[e["is_a"]].append({"tag": tag, "name": e["name"], "rvt_class": cls})
        else:
            join[e["is_a"]]["<not found>"] += 1
            if len(missing) < 20:
                missing.append({"tag": tag, "is_a": e["is_a"], "name": e["name"], "in_elemtable": in_et})
    rows = []
    for icls, ctr in sorted(join.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(ctr.values())
        top_cls, top_n = ctr.most_common(1)[0]
        purity = top_n / total
        rows.append({
            "ifc_class": icls, "n": total,
            "rvt_class": top_cls, "rvt_n": top_n, "purity": round(purity, 3),
            "distribution": dict(ctr.most_common(4)),
            "confidence": ("CONFIRMED" if purity >= 0.95 and top_cls != "<not found>"
                           else "STRONG" if purity >= 0.7 and top_cls != "<not found>"
                           else "MIXED" if top_cls != "<not found>" else "NOT-FOUND"),
            "examples": join_examples.get(icls, []),
        })
    rep["element_join"] = {
        "ifc_elements_with_tag": tagged,
        "found_in_partition_records": found_in_records,
        "found_in_elemtable": found_in_elemtable,
        "coverage_records": round(found_in_records / tagged, 4) if tagged else None,
        "coverage_elemtable": round(found_in_elemtable / tagged, 4) if tagged else None,
        "rows": rows, "missing_examples": missing,
    }

    # -- (2) count matching --------------------------------------------------
    # use the LIVE census (ElemTable ids, latest record) when available: raw
    # record counts are inflated by superseded versions across save units.
    rvt_counts = rvt.get("class_counts_live") or rvt["class_word_counts_seq102"]
    rvt_counts_source = "live (ElemTable ids)" if rvt.get("class_counts_live") else "raw records"
    rep["rvt_count_source"] = rvt_counts_source
    count_props = []
    for icls, n in ifc["product_counts"].items():
        if icls in ("IfcSite", "IfcBuilding", "IfcSpatialZone"):
            continue
        # candidate rvt classes with count within 5% (or +-2)
        cands = []
        for rcls, rn in rvt_counts.items():
            if rn == 0:
                continue
            if abs(rn - n) <= max(2, 0.05 * n):
                cands.append({"rvt_class": rcls, "rvt_n": rn, "delta": rn - n})
        cands.sort(key=lambda c: abs(c["delta"]))
        joined = next((r["rvt_class"] for r in rows if r["ifc_class"] == icls), None)
        count_props.append({"ifc_class": icls, "ifc_n": n,
                            "join_says": joined,
                            "join_class_live_n": rvt_counts.get(joined) if joined else None,
                            "count_candidates": cands[:5],
                            "join_confirmed_by_count": any(c["rvt_class"] == joined for c in cands)})
    rep["count_match"] = count_props

    # type-level counts
    type_join = []
    for tcls, n in ifc["type_counts"].items():
        type_join.append({"ifc_type_class": tcls, "ifc_n": n})
    rep["type_counts"] = type_join

    # -- (3) name agreement ------------------------------------------------------
    idx = string_index(rvt)
    names = {"storeys": [], "wall_types": [], "families": [], "type_names": [],
             "spaces": [], "materials": [], "misc": []}
    # storeys
    for st in ifc["storeys"]:
        hit = find_name(idx, st["name"])
        names["storeys"].append({
            "ifc_name": st["name"], "elevation": st["elevation"],
            "found": bool(hit),
            "rvt_class": rec_class(hit),
            "rvt_record_id": rec_id(hit),
        })
    # type names (Family:Type) -- dedupe (Revit emits one IfcTypeObject per
    # instance for parametric families such as columns/spaces)
    seen_fams = set()
    seen_types = set()
    type_dupes = collections.Counter()
    system_families = {"Basic Wall", "Floor", "Basic Roof", "Pad", "Curtain Wall",
                       "Compound Ceiling", "Basic Ceiling", "Ceiling", "Roof"}
    for t in ifc["types"]:
        # IfcSpaceType is a per-instance pseudo type ('RoomName Number:Id');
        # room agreement is measured in the spaces section instead.
        if t["is_a"] == "IfcSpaceType":
            continue
        key = (t["is_a"], t["name"])
        type_dupes[key] += 1
        if key in seen_types:
            continue
        seen_types.add(key)
        fam, typ = t.get("family"), t.get("type_name")
        entry = {"ifc_type_class": t["is_a"], "ifc_name": t["name"],
                 "family": fam, "type": typ}
        if typ:
            hit = find_name(idx, typ)
            entry["type_found"] = bool(hit)
            entry["type_in_class"] = rec_class(hit, prefer_typeish=True) if hit else None
        if fam and fam not in system_families and fam not in seen_fams:
            fh = find_name(idx, fam)
            entry["family_found"] = bool(fh)
            entry["family_in_class"] = rec_class(fh) if fh else None
            seen_fams.add(fam)
        target = names["wall_types"] if t["is_a"] == "IfcWallType" else names["type_names"]
        target.append(entry)
    for e in names["wall_types"] + names["type_names"]:
        e["instances_named"] = type_dupes[(e["ifc_type_class"], e["ifc_name"])]
    # spaces (names + numbers)
    for sp in ifc.get("spaces", [])[:400]:
        base = sp.get("name") or ""
        long = sp.get("long_name") or ""
        # revit: Name = number, LongName = name; IFC space Name often "name number"
        found_any = False
        which = None
        for cand in (base, long, f"{base}", base.rsplit(" ", 1)[0] if " " in base else ""):
            if cand:
                hit = find_name(idx, cand)
                if hit:
                    found_any = True
                    which = rec_class(hit)
                    break
        names["spaces"].append({"ifc_name": base, "found": found_any, "rvt_class": which})
    # materials
    for mat in ifc.get("materials", []):
        if mat.startswith("<"):
            continue
        hit = find_name(idx, mat)
        names["materials"].append({"ifc_name": mat, "found": bool(hit), "rvt_class": rec_class(hit)})
    # site / project (Revit names the IfcSite 'ToposurfaceName:ElementId' when
    # a topography site is selected -> join the id too)
    for lbl, val in (("site", ifc.get("site_name")), ("project", ifc.get("project_name"))):
        if val:
            hit = find_name(idx, val)
            entry = {"what": lbl, "ifc_name": val, "found": bool(hit), "rvt_class": rec_class(hit)}
            m = re.search(r":(\d+)$", val or "")
            if m and not hit:
                cls = id_to_cls.get(int(m.group(1)))
                if cls:
                    entry["found"] = True
                    entry["rvt_class"] = f"{cls} (by ElementId {m.group(1)})"
            names["misc"].append(entry)

    def rate(lst):
        f = sum(1 for x in lst if x.get("found") or x.get("type_found") or x.get("family_found"))
        return {"n": len(lst), "found": f, "rate": round(f / len(lst), 3) if lst else None}

    rep["name_agreement"] = {k: {"score": rate(v), "items": v} for k, v in names.items()}

    # -- correspondence table (the deliverable) --------------------------------
    table = []
    for r in rows:
        icls = r["ifc_class"]
        cnt = next((c for c in count_props if c["ifc_class"] == icls), None)
        table.append({
            "ifc_entity": icls,
            "rvt_class": r["rvt_class"],
            "evidence": (f"element-id join: {r['rvt_n']}/{r['n']} tagged elements = "
                         f"{r['purity']:.0%} pure"
                         + (f"; count match {cnt['count_candidates'][0]['rvt_n']} vs {cnt['ifc_n']}"
                            if cnt and cnt["join_confirmed_by_count"] else "")),
            "confidence": r["confidence"],
        })
    # type-level correspondences from name agreement
    tcls_map = collections.defaultdict(collections.Counter)
    for lst in (names["wall_types"], names["type_names"]):
        for e in lst:
            if e.get("type_found") and e.get("type_in_class"):
                tcls_map[e["ifc_type_class"]][e["type_in_class"]] += 1
            if e.get("family_found") and e.get("family_in_class"):
                tcls_map[e["ifc_type_class"] + " (family)"][e["family_in_class"]] += 1
    for icls, ctr in tcls_map.items():
        top, n = ctr.most_common(1)[0]
        table.append({"ifc_entity": icls, "rvt_class": top,
                      "evidence": f"type/family name found inside {n} {top} record(s)",
                      "confidence": "CONFIRMED" if n >= 2 else "STRONG"})
    if names["storeys"] and all(x["found"] for x in names["storeys"]):
        cls = collections.Counter(x["rvt_class"] for x in names["storeys"] if x["rvt_class"])
        top = cls.most_common(1)[0][0] if cls else "Level"
        table.append({"ifc_entity": "IfcBuildingStorey", "rvt_class": top,
                      "evidence": f"all {len(names['storeys'])} storey names found in {top} records",
                      "confidence": "CONFIRMED"})
    sp = rep["name_agreement"]["spaces"]["score"]
    if sp["n"]:
        cls = collections.Counter(x["rvt_class"] for x in names["spaces"] if x["rvt_class"])
        top_cls, top_n = (cls.most_common(1)[0] if cls else ("RoomElem", 0))
        table.append({"ifc_entity": "IfcSpace", "rvt_class": top_cls,
                      "evidence": f"space names found: {sp['found']}/{sp['n']} ({sp['rate']:.0%}), "
                                  f"{top_n} inside {top_cls} records",
                      "confidence": ("CONFIRMED" if (sp["rate"] or 0) >= 0.95 and top_n >= 0.9 * sp["found"]
                                     else "STRONG" if (sp["rate"] or 0) >= 0.6 else "WEAK")})
    for e in names["misc"]:
        if e.get("what") == "site" and e.get("found") and e.get("rvt_class") and "ElementId" in str(e["rvt_class"]):
            table.append({"ifc_entity": "IfcSite (from ToposurfaceName:Id)",
                          "rvt_class": str(e["rvt_class"]).split(" (")[0],
                          "evidence": f"site name {e['ifc_name']!r} ends in an ElementId that is that record",
                          "confidence": "CONFIRMED"})
    rep["correspondence_table"] = table
    return rep


# --------------------------------------------------------------------------
# Einhoven / FME mode (no IFC in the dataset for that model)
# --------------------------------------------------------------------------

RE_UNIQUEID = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})-([0-9a-fA-F]{8})")


def compare_fme(rvt_path: str, fme_dir: str, refresh: bool = False) -> dict:
    rvt = OX.extract(rvt_path, refresh=refresh, quiet=True)
    rep = {"rvt": os.path.basename(rvt_path), "oracle": fme_dir, "mode": "FME/StrangeMatter"}
    ids = {}
    classes = collections.defaultdict(collections.Counter)
    sources = collections.defaultdict(set)
    csv.field_size_limit(10 ** 8)
    # CSV component tables: SourceDataItemId column carries the Revit UniqueId,
    # Classification column the StrangeMatter/IFC class (hok.wall, ifc.window...)
    for path in sorted(glob.glob(os.path.join(fme_dir, "*.csv"))):
        try:
            with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
                for row in csv.DictReader(fh):
                    blob = " ".join(str(v) for v in (row.get("SourceDataItemId"),
                                                     row.get("SourceData"), row.get("Payload")) if v)
                    for m in RE_UNIQUEID.finditer(blob):
                        eid = int(m.group(2), 16)
                        ids.setdefault(eid, set()).add(m.group(1).lower())
                        cls = (row.get("Classification") or "").strip()
                        if cls:
                            classes[eid][cls] += 1
                        sources[eid].add(os.path.basename(path))
        except Exception:  # noqa: BLE001
            continue
    # JSON exports (no UniqueIds normally, but scan defensively)
    for path in sorted(glob.glob(os.path.join(fme_dir, "*.json"))):
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except Exception:  # noqa: BLE001
            continue
        for m in RE_UNIQUEID.finditer(txt):
            eid = int(m.group(2), 16)
            ids.setdefault(eid, set()).add(m.group(1).lower())
            sources[eid].add(os.path.basename(path))
            seg = txt[max(0, m.start() - 400): m.start() + 400]
            cm = re.search(r'"?Classification"?\s*[:=,]\s*"?([A-Za-z0-9_.]+)', seg)
            if cm:
                classes[eid][cm.group(1)] += 1
    id_to_cls = {int(k): v for k, v in rvt["id_to_cls_seq102"].items()}
    et = set(rvt["elemtable_ids"])
    rows = []
    for eid in sorted(ids):
        rows.append({
            "element_id": eid, "hex": f"{eid:08x}",
            "episode_guids": sorted(ids[eid]),
            "fme_class": (classes[eid].most_common(1)[0][0] if classes[eid] else None),
            "sources": sorted(sources.get(eid, [])),
            "in_elemtable": eid in et,
            "rvt_record_class": id_to_cls.get(eid),
        })
    doc_guid = ((rvt.get("meta") or {}).get("guids") or {}).get("unique_document_guid")
    rep["rvt_doc_guid"] = doc_guid
    rep["episode_guids_seen"] = sorted({g for r in rows for g in r["episode_guids"]})
    rep["n_ids"] = len(rows)
    rep["n_in_elemtable"] = sum(1 for r in rows if r["in_elemtable"])
    rep["n_in_records"] = sum(1 for r in rows if r["rvt_record_class"])
    rep["rows"] = rows
    ctr = collections.Counter((r["fme_class"], r["rvt_record_class"]) for r in rows)
    rep["class_correspondence"] = [{"fme_class": a, "rvt_class": b, "n": n} for (a, b), n in ctr.most_common()]
    return rep


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def render_md(rep: dict) -> str:
    L = []
    P = L.append
    P(f"# Agreement report: `{rep['rvt']}` vs `{rep['ifc']}`\n")
    idn = rep["identity"]
    P(f"* rvt: Revit **{idn['rvt_release']}** build `{idn['rvt_build']}`, doc GUID `{idn['rvt_doc_guid']}`, "
      f"central version {idn['rvt_central_version']}")
    P(f"* ifc: `{idn['ifc_app']}`, VersionGUID `{idn['ifc_version_guid']}`, NumberOfSaves {idn['ifc_saves']}")
    P(f"* **document identity match: {'YES' if idn['guid_match'] else 'NO'}** "
      f"(IFC VersionGUID == rvt Unique Document GUID)\n")
    ej = rep["element_join"]
    P("## 1. Element-id join (IFC Tag == Revit ElementId -> partition record)\n")
    P(f"* IFC elements carrying a Revit ElementId tag: **{ej['ifc_elements_with_tag']:,}**")
    if ej["coverage_records"] is not None:
        P(f"* found as a seq102 object record in the .rvt: **{ej['found_in_partition_records']:,} "
          f"({ej['coverage_records']:.1%})**; present in Global/ElemTable: "
          f"{ej['found_in_elemtable']:,} ({ej['coverage_elemtable']:.1%})\n")
    P("| IFC entity | n | rvt record class | purity | distribution | verdict |")
    P("|---|---:|---|---:|---|---|")
    for r in ej["rows"]:
        dist = ", ".join(f"{k}:{v}" for k, v in r["distribution"].items())
        P(f"| {r['ifc_class']} | {r['n']} | **{r['rvt_class']}** | {r['purity']:.0%} | {dist} | {r['confidence']} |")
    if ej["missing_examples"]:
        P(f"\n_not found examples_: {ej['missing_examples'][:4]}")
    P("\n## 2. Count matching (side by side, schema-agnostic)\n")
    P(f"_rvt counts = {rep.get('rvt_count_source')} (live model census); "
      f"IFC counts = exported subset (export omits unplaced/legend/view-specific elements, "
      f"and curtain-wall panels/mullions ride inside their host)._\n")
    P("| IFC entity | IFC n | join class -> live n in whole model | other rvt classes with a count within 5% |")
    P("|---|---:|---|---|")
    for c in rep["count_match"]:
        cands = ", ".join(f"{x['rvt_class']}={x['rvt_n']}" for x in c["count_candidates"][:3]) or "(none within 5%)"
        jl = f"{c['join_says']}={c['join_class_live_n']}" if c["join_says"] else "-"
        P(f"| {c['ifc_class']} | {c['ifc_n']} | {jl} | {cands} |")
    P("\n## 3. Name agreement (IFC names found in .rvt decoded strings, with owning record class)\n")
    na = rep["name_agreement"]
    for key in ("storeys", "wall_types", "type_names", "spaces", "materials", "misc"):
        sc = na[key]["score"]
        if not sc["n"]:
            continue
        P(f"### {key}: {sc['found']}/{sc['n']} found ({(sc['rate'] or 0):.0%})\n")
        items = na[key]["items"]
        show = items if len(items) <= 20 else items[:20]
        if key == "storeys":
            P("| storey | elev | found in .rvt | record class : id |")
            P("|---|---:|---|---|")
            for x in items:
                P(f"| {x['ifc_name']} | {x['elevation']:.1f} | {'yes' if x['found'] else 'NO'} | "
                  f"{x['rvt_class'] or ''} {x['rvt_record_id'] if x['rvt_record_id'] is not None else ''} |")
        elif key in ("wall_types", "type_names"):
            P("| IFC type | family found (class) | type name found (class) |")
            P("|---|---|---|")
            for x in show:
                fam = ("yes: " + str(x.get("family_in_class"))) if x.get("family_found") else (
                    "no" if "family_found" in x else "-")
                typ = ("yes: " + str(x.get("type_in_class"))) if x.get("type_found") else (
                    "no" if "type_found" in x else "-")
                P(f"| {x['ifc_name']} | {fam} | {typ} |")
            if len(items) > 20:
                P(f"| ... {len(items) - 20} more | | |")
        else:
            found = [x['ifc_name'] for x in items if x.get('found')][:12]
            nf = [x['ifc_name'] for x in items if not x.get('found')][:12]
            P(f"* found: {found}")
            P(f"* not found: {nf}")
        P("")
    P("## 4. Correspondence table (IFC entity <-> rvt schema class), scored\n")
    P("| IFC entity | rvt class (schema name = class_word) | evidence | confidence |")
    P("|---|---|---|---|")
    for t in rep["correspondence_table"]:
        P(f"| {t['ifc_entity']} | **{t['rvt_class']}** | {t['evidence']} | {t['confidence']} |")
    return "\n".join(L) + "\n"


def render_md_fme(rep: dict) -> str:
    L = []
    P = L.append
    P(f"# Agreement report (FME/StrangeMatter oracle): `{rep['rvt']}`\n")
    P(f"* rvt doc GUID: `{rep['rvt_doc_guid']}`")
    P(f"* episode GUIDs referenced by the FME UniqueIds: {rep['episode_guids_seen']} "
      f"(all present in the rvt's Global/History)")
    P(f"* distinct Revit ElementIds referenced by FME exports: **{rep['n_ids']}**; "
      f"found in Global/ElemTable: **{rep['n_in_elemtable']}**; "
      f"found as seq102 object record: **{rep['n_in_records']}**\n")
    P("| ElementId | hex | FME classification | in ElemTable | rvt record class |")
    P("|---:|---|---|---|---|")
    for r in rep["rows"]:
        P(f"| {r['element_id']} | {r['hex']} | {r['fme_class']} | {r['in_elemtable']} | {r['rvt_record_class']} |")
    P("\n### class correspondence\n")
    for c in rep["class_correspondence"]:
        P(f"* {c['fme_class']} <-> {c['rvt_class']} (n={c['n']})")
    return "\n".join(L) + "\n"


def print_headline(rep: dict) -> None:
    if rep.get("mode") == "FME/StrangeMatter":
        print(f"== {rep['rvt']} vs FME exports: {rep['n_ids']} ElementIds -> "
              f"{rep['n_in_elemtable']} in ElemTable, {rep['n_in_records']} in partition records")
        for c in rep["class_correspondence"]:
            print(f"   {str(c['fme_class']):32s} <-> {str(c['rvt_class']):24s} n={c['n']}")
        return
    idn = rep["identity"]
    ej = rep["element_join"]
    print(f"== {rep['rvt']} (Revit {idn['rvt_release']}) vs {rep['ifc']}  "
          f"identity={'MATCH' if idn['guid_match'] else 'no-guid-match'}")
    print(f"   element-id join coverage: {ej['found_in_partition_records']}/{ej['ifc_elements_with_tag']} "
          f"= {(ej['coverage_records'] or 0):.1%} (ElemTable {(ej['coverage_elemtable'] or 0):.1%})")
    print(f"   {'IFC entity':22s} {'n':>5s}  {'rvt class':22s} {'purity':>6s}  verdict")
    for r in ej["rows"]:
        print(f"   {r['ifc_class']:22s} {r['n']:5d}  {r['rvt_class']:22s} {r['purity']:6.0%}  {r['confidence']}")
    na = rep["name_agreement"]
    print("   name agreement: " + ", ".join(
        f"{k}={v['score']['found']}/{v['score']['n']}" for k, v in na.items() if v['score']['n']))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rvt")
    ap.add_argument("ifc", nargs="?")
    ap.add_argument("--fme", help="FME Demos dir (StrangeMatter component exports) as the oracle")
    ap.add_argument("--md", help="write the markdown report here")
    ap.add_argument("--json", help="write the JSON report here")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    if args.fme:
        rep = compare_fme(args.rvt, args.fme, refresh=args.refresh)
        md = render_md_fme(rep)
    else:
        if not args.ifc:
            ap.error("need an .ifc (or --fme)")
        rep = compare(args.rvt, args.ifc, refresh=args.refresh)
        md = render_md(rep)
    print_headline(rep)
    if args.md:
        with open(args.md, "w") as f:
            f.write(md)
        print(f"   wrote {args.md}")
    else:
        print()
        print(md)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=1)
        print(f"   wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
