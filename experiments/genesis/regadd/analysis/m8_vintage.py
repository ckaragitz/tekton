"""M8 -- per-class ElemTable VINTAGE + OWNERSHIP for the classes the XR probes
touch, measured per specimen across all six samples (+K1), split into
project-scoped (not owned / m_famId -1) vs family-owned specimens."""
import os, sys, collections, json
ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
from rvt.mutate import Document

CLASSES = ["PenWidthTableElem", "KeynoteTable", "KeynotingSystem", "AllProjectPhases",
           "DBViewProject", "UnitsElem", "ProjectInfo", "StructSettingsElem",
           "ElectricalSetting", "ConstructionSetProject", "ReconcileBrowserSettingsElem",
           "BrowserOrganization", "AutoJoinTracker", "WallJoinDefaultSetting",
           "InitialViewSettings", "RbsDbViewSystemNavigator", "AllProjectRevisions",
           "RevisionNumberingSequence", "TrueNorth", "BasePoint", "TextNoteAttributes",
           "FontElem", "CategoryElem", "GStyleElem", "FillPatternElem", "LinePatternElem",
           "MaterialElem", "Viewer", "Viewport", "DBDrawing", "AssemblyCodeTable"]
INVALID = 0xFFFFFFFFFFFFFFFF

targets = [("K1", os.path.join(ROOT, "experiments/genesis/triage/K1.rvt"), True)] + [
    (s, s, False) for s in ["rstbasicsampleproject", "rmebasicsampleproject",
                            "racbasicsampleproject", "racadvancedsampleproject",
                            "rstadvancedsampleproject", "dach-sample-project"]]

agg = collections.defaultdict(lambda: collections.defaultdict(list))
for name, ref, is_file in targets:
    doc = Document.from_file(ref) if is_file else Document.load(ref)
    ce_max = max(int(r.modified_ep) for r in doc.et.records)
    for cls in CLASSES:
        for eid in doc.ids_of_class(cls):
            er = doc.et_by_id.get(eid)
            if er is None:
                continue
            v = doc.value(eid) or {}
            fam = v.get("m_famId", -1)
            owner_own = int(v.get("m_ownerId", -1)) if isinstance(v.get("m_ownerId"), int) else -1
            owner = er.owner_id if er.owner_id not in (INVALID, -1) else None
            owner_cls = doc.class_of(owner) if owner is not None else None
            cohort = "project" if (fam in (-1, None, INVALID) and owner_cls != "Family") else "scoped"
            # for GStyle / Category: builtin vs sub
            if cls == "GStyleElem":
                cat = v.get("m_categoryId")
                cohort = ("builtin" if isinstance(cat, int) and cat < 0 and fam in (-1, INVALID)
                          else "sub/other")
            agg[(cls, cohort)][name].append({
                "id": int(eid), "ce": int(er.creation_ep), "me": int(er.modified_ep),
                "ue": (None if er.user_modified_ep == 0xFFFFFFFF else int(er.user_modified_ep)),
                "owner_cls": owner_cls, "renum": bool(er.original_id != er.id),
                "part": int(er.partition_id), "max_ep": ce_max})
    print(f"loaded {name}: {len(doc.et.records)} rows, max_ep {ce_max}", flush=True)

# summarize
def band(i):
    n = abs(int(i))
    for thr, nm in ((5_000, "<5k"), (50_000, "<50k"), (500_000, "<500k"), (5_000_000, "<5M")):
        if n < thr:
            return nm
    return ">=5M"

out = {}
for (cls, coh), per_file in sorted(agg.items()):
    n = sum(len(v) for v in per_file.values())
    rows = [r for v in per_file.values() for r in v]
    ce0 = sum(1 for r in rows if r["ce"] == 0)
    bands = collections.Counter(band(r["id"]) for r in rows)
    owners = collections.Counter(r["owner_cls"] for r in rows)
    ue_never = sum(1 for r in rows if r["ue"] is None)
    ce_eq_me = sum(1 for r in rows if r["ce"] == r["me"])
    renum = sum(1 for r in rows if r["renum"])
    files = len(per_file)
    key = f"{cls}|{coh}"
    out[key] = {"n": n, "files": files, "creation_ep0": ce0, "bands": dict(bands),
                "owners": dict(owners), "usermod_never": ue_never, "ce_eq_me": ce_eq_me,
                "renumbered": renum,
                "sample": rows[:4]}
    print(f"{cls:28s} {coh:9s} n={n:>6} files={files} ce==0: {ce0:>6}/{n} "
          f"ce==me: {ce_eq_me:>6} usermod-never: {ue_never:>6} renum {renum} "
          f"bands {dict(bands)} owners {dict(list(owners.items())[:3])}")

with open(os.path.join(os.path.dirname(__file__), "m8_vintage.json"), "w") as fh:
    json.dump(out, fh, indent=1, default=str)
print("\nwritten m8_vintage.json")
