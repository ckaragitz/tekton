import json, collections, re, sys, os
ROOT = '/Users/ck/dev/things/tekton'
sys.path.insert(0, os.path.join(ROOT,'src')); sys.path.insert(0, os.path.join(ROOT,'tools'))
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
cls = {int(k): v for k, v in g['classes'].items()}
# LevelAttributes -> FamilySymbol path:
for s,p,t in edges:
    if s == 1410873 and t == 1411143: print('LevelAttributes->FamilySymbol:', p)
    if s == 1410875 and t == 1410873: print('Level->LevelAttributes:', p)
# stray sketches
for i in (1410910, 1410991, 1410993, 1410909, 1411228, 1410981):
    outs = [(p,t,cls[t]) for s,p,t in edges if s==i and not p.startswith('hdr.m_parents')]
    ins  = [(s,cls[s],p) for s,p,t in edges if t==i and not p.startswith('hdr.m_parents') and s != 1410872]
    print(f'\n{i} {cls[i]}:')
    print('  out:', outs[:8])
    print('  in :', ins[:8])
import famdoc_bisect as FB
FB._install_schema()
prod = FB.our_product(2_000_000)
la = next(e for e in prod.doc.elements if e.class_name=='LevelAttributes')
print('\nOUR LevelAttributes obj keys sample:')
print(json.dumps({k: la.obj[k] for k in la.obj if 'sym' in k.lower() or 'Sym' in k}, default=str))
don_els, _a, _i = FB.load_unit_elements(FB.RST, FB.DONOR_UNIT)
dla = next(e for e in don_els if e.elem_id == 1410873)
print('DONOR LevelAttributes symbol-ish keys:')
print(json.dumps({k: dla.obj[k] for k in dla.obj if 'sym' in k.lower() or 'Sym' in k}, default=str))
