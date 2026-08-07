"""Re-run the fixdemo gates against the STAGED batch-39 bytes (restored into
experiments/hostpair/) so fix_accounting.json + probes.json describe the
exact staged files."""
import json, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "tools"))
import hostpair_probe as HP
import famdoc_bisect as FDB
FDB._install_schema()
B = HP._bisect()
from rvt import famload_hostfix as HF
from rvt.mutate import Document

def md5(p):
    h = hashlib.md5(); h.update(open(p, "rb").read()); return h.hexdigest()

with open(os.path.join(HP.OUT_DIR, "fix_accounting.json")) as fh:
    out = json.load(fh)
for name in HP.FIX_LADDER:
    info = out["built"][name]
    child = os.path.join(ROOT, info["file"])
    info["md5"] = md5(child)
    doc = Document.from_file(child)
    forms = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        fam = doc.value(v.get("m_familyId") or -1) or {}
        if "PP-" in str(fam.get("m_name") or ""):
            forms[sid] = HF.assert_symbol_form(child, sid)
    info["symbol_form"] = {str(k): {"ok": f["ok"], "counts": f["counts"]} for k, f in forms.items()}
    bad = [k for k, f in forms.items() if not f["ok"]]
    assert forms and not bad, (name, bad)
    # instance ids from the staged bytes (instances of our symbols)
    insts = []
    for iid in doc.ids_of_class("FamilyInstance"):
        v = doc.value(iid) or {}
        if v.get("m_masterSymbolId") in forms:
            insts.append(iid)
    info["instance_ids"] = sorted(insts)
    rep = B.account(name, child, HP.G_ABPD, declared_base=HP.G_ABPD,
                    instance_ids=info["instance_ids"], with_regdiff=False)
    out["accounting"][name] = rep
    va = rep["validator"]
    print(name, "validator", va["n_errors"], "unexpected", len(va["unexpected_errors"]),
          "coherent", rep["census"]["coherent"], "survivor", rep["survivor_law_ok"],
          "forms", len(forms), "instances", len(insts), "md5", info["md5"][:8])
out["note"] = ("gates re-run against the STAGED batch-39 bytes (restored from "
               "experiments/acceptance/); fresh GUIDs are minted per fixdemo "
               "rebuild -- the staged bytes are canonical")
with open(os.path.join(HP.OUT_DIR, "fix_accounting.json"), "w") as fh:
    json.dump(out, fh, indent=1, default=str)
HP.write_probes_json_all()
print("done")
