import json, sys, os
ROOT = '/Users/ck/dev/things/tekton'
sys.path.insert(0, os.path.join(ROOT,'src')); sys.path.insert(0, os.path.join(ROOT,'tools'))
import famdoc_bisect as FB
FB._install_schema()
prod = FB.our_product(2_000_000)
la = next(e for e in prod.doc.elements if e.class_name=='LevelAttributes')
print('OUR LevelAttributes m_familyTagId:', la.obj.get('m_familyTagId'))
don_els, _a, _i = FB.load_unit_elements(FB.RST, FB.DONOR_UNIT)
by = {e.elem_id: e for e in don_els}
print('DONOR LevelAttributes m_familyTagId:', by[1410873].obj.get('m_familyTagId'))
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
cls = {int(k): v for k, v in g['classes'].items()}
nested = set(json.load(open(ROOT + '/experiments/subtractive/_explore/nested_members.json')))
print('\nnon-nested SketchPlanes:')
for e in don_els:
    if e.class_name != 'SketchPlane' or e.elem_id in nested: continue
    o = e.obj
    print(f'  {e.elem_id}: ownerDBView={o.get("m_ownerDBViewId")} hdrOwnerView={e.header.get("m_ownerViewId")} userId={o.get("m_userId")} datumPlane={(((o.get("m_oPlaneRef") or {}).get("value")) or {}).get("m_datumPlaneId")}')
# also our own LevelAttributes m_attrId level chain and our Sun/BrowserOrg absence
print('\nOur classes:', sorted({e.class_name for e in prod.doc.elements}))
