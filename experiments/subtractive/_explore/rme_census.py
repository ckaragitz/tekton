import sys, os, collections
ROOT = '/Users/ck/dev/things/tekton'
sys.path.insert(0, os.path.join(ROOT,'src')); sys.path.insert(0, os.path.join(ROOT,'tools'))
import famdoc_bisect as FB
FB._install_schema()
try:
    els, adoc, idx = FB.load_unit_elements(FB.RME, FB.RME_PANELBOARD_UNIT)
    cen = collections.Counter(e.class_name for e in els)
    print('RME panelboard unit', FB.RME_PANELBOARD_UNIT, 'elements:', len(els))
    for c, n in sorted(cen.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f'{n:4d}  {c}')
except Exception as e:
    print('load failed:', type(e).__name__, e)
    # fall back: raw record census without rep check
    from rvt.families import FamilyIndex
    idx = FamilyIndex(FB.RME)
    recs = idx.unit_records(FB.RME_PANELBOARD_UNIT)
    cen = collections.Counter(idx.class_name(r.class_id) for r in recs.get(102, {}).values())
    print('raw census:', len(recs.get(102, {})))
    for c, n in sorted(cen.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f'{n:4d}  {c}')
