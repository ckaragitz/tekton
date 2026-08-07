"""M6 -- where do the settings singletons / catalog rows SIT in the unit-0
record stream of accepted files?  Position (index, %) per class, all six
samples + K1.  Also: are the K1 singletons contiguous with related classes
(neighbours)?"""
import os, sys, collections, statistics
ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
from rvt.container import open_rvt
from rvt.partitions import StreamWalker
from rvt.objects import iter_records, ObjectDecoder

DEC = ObjectDecoder()
CLASSES = ["PenWidthTableElem", "KeynoteTable", "KeynotingSystem", "StructSettingsElem",
           "UnitsElem", "DBViewProject", "AllProjectPhases", "ElectricalSetting",
           "BrowserOrganization", "ReconcileBrowserSettingsElem", "ConstructionSetProject",
           "AutoJoinTracker", "WallJoinDefaultSetting", "InitialViewSettings", "ProjectInfo",
           "BasePoint", "TrueNorth", "SunAndShadowSettings", "RbsDbViewSystemNavigator",
           "AllProjectRevisions", "RevisionNumberingSequence", "TextNoteAttributes", "FontElem",
           "CategoryElem", "GStyleElem", "FillPatternElem", "LinePatternElem", "MaterialElem",
           "Level", "DBViewType", "AssemblyCodeTable", "PostedWarningElem"]


def order(path):
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        seg = b"".join(b.data for b in u0 if b.seq == 102)
    recs = [r for r in iter_records(seg, 102) if r.elem_id >= 0]
    return recs


targets = [("K1", os.path.join(ROOT, "experiments/genesis/triage/K1.rvt"))] + [
    (s, os.path.join(ROOT, "samples", s + ".rvt")) for s in
    ["rstbasicsampleproject", "rmebasicsampleproject", "racbasicsampleproject",
     "racadvancedsampleproject", "rstadvancedsampleproject", "dach-sample-project"]]

for name, path in targets:
    if not os.path.exists(path):
        continue
    recs = order(path)
    n = len(recs)
    pos_by_class = collections.defaultdict(list)
    for i, r in enumerate(recs):
        cls = DEC.class_name(r.class_id)
        if cls in CLASSES:
            pos_by_class[cls].append((i, r.elem_id))
    print(f"\n=== {name} ({n} records)")
    for cls in CLASSES:
        ps = pos_by_class.get(cls, [])
        if not ps:
            continue
        idxs = [p[0] for p in ps]
        if len(ps) <= 3:
            desc = ", ".join(f"pos {i} ({100*i/n:.1f}%) id {e}" for i, e in ps)
        else:
            desc = (f"{len(ps)} rows: pos min {min(idxs)} ({100*min(idxs)/n:.1f}%) "
                    f"median {int(statistics.median(idxs))} max {max(idxs)} "
                    f"({100*max(idxs)/n:.1f}%)")
        print(f"  {cls:32s} {desc}")
    # neighbours of the pen table (id 2 / the m_famId -1 one) in K1-family files
    for i, r in enumerate(recs):
        if DEC.class_name(r.class_id) == "PenWidthTableElem":
            o = DEC.decode_record(r.class_id, r.payload)
            if int(o.value.get("m_famId", -1)) == -1:
                lo, hi = max(0, i - 4), min(n, i + 5)
                nb = [(recs[j].elem_id, DEC.class_name(recs[j].class_id)) for j in range(lo, hi)]
                print(f"  project pen table id {r.elem_id} at pos {i} ({100*i/n:.2f}%); "
                      f"neighbours: {nb}")
            break
