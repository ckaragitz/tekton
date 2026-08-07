import json, collections, re, sys, os
ROOT = '/Users/ck/dev/things/tekton'
sys.path.insert(0, os.path.join(ROOT, 'src')); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import famdoc_bisect as FB
FB._install_schema()
els, adoc_value, idx = FB.load_unit_elements(FB.RST, FB.DONOR_UNIT)
by = {e.elem_id: e for e in els}
NF = 1411054
nf = by[NF]
fi = ((nf.obj.get('m_familyIds') or {}).get('value') or {}).get('m_data') or []
members = sorted(int(d.get('m_elementId')) for d in fi)
print('nested family m_familyIds members:', len(members))
cc = collections.Counter(by[m].class_name for m in members if m in by)
print(dict(sorted(cc.items())))
missing = [m for m in members if m not in by]
print('registered but not resident:', missing)
# what else does nested family reference in registries?
dele = ((nf.header.get('m_parents') or {}).get('value') or {}).get('m_deletion') or []
print('nested hdr m_deletion:', len(dele), 'same as members?', sorted(dele)==members)
fsdos = nf.obj.get('m_fsdos') or []
print('nested m_fsdos count:', len(fsdos))
# surrogates + symbol
for i in (1411142, 1411143, 1411144):
    e = by[i]
    print(i, e.class_name, 'owner=', e.owner_id, 'hdr.m_familyId=', e.header.get('m_familyId'))
# who owns the nested-registered members?
oc = collections.Counter(by[m].owner_id for m in members if m in by)
top_owners = {k: v for k, v in sorted(oc.items(), key=lambda kv: -kv[1])[:8]}
print('owners of nested members:', {f'{k}({by[k].class_name if k in by else k})': v for k,v in top_owners.items()})
# the 4 mystery VarSketches (owned by Family): which family, what content?
for e in els:
    if e.class_name == 'VarSketch':
        print('VarSketch', e.elem_id, 'owner', e.owner_id, by[e.owner_id].class_name if e.owner_id in by else '?', 'in_nested=', e.elem_id in set(members))
