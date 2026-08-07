"""Exploratory: donor unit-36 reference graph + ownership + roster-equivalence pins."""
import sys, os, json, collections
ROOT = '/Users/ck/dev/things/tekton'
sys.path.insert(0, os.path.join(ROOT, 'src')); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import famdoc_bisect as FB
FB._install_schema()

els, adoc_value, idx = FB.load_unit_elements(FB.RST, FB.DONOR_UNIT)
by_id = {e.elem_id: e for e in els}
don_ids = set(by_id)

# --- edges: int-walk with paths ---
edges = []  # (src, path, dst)
def walk(node, src, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, bool): continue
            if isinstance(v, int) and v in don_ids and v != src:
                edges.append((src, path + '.' + k, v))
            else:
                walk(v, src, path + '.' + k)
    elif isinstance(node, list):
        for j, v in enumerate(node):
            if isinstance(v, bool): continue
            if isinstance(v, int) and v in don_ids and v != src:
                edges.append((src, f'{path}[{j}]', v))
            else:
                walk(v, src, f'{path}[{j}]')

for e in els:
    walk(e.header, e.elem_id, 'hdr')
    walk(e.obj, e.elem_id, 'obj')
    if e.rep is not None:
        walk(e.rep, e.elem_id, 'rep')

print('edges:', len(edges))
own = {e.elem_id: e.owner_id for e in els if (e.owner_id or 0) > 0}
print('owned elements:', len(own))

# --- frame roles ---
dfr = FB.__dict__.get('donor_frame')
import famdoc_final as FF
dfr = FF.donor_frame(els)
frame_ids = set(dfr['roles'].values())
print('frame roles:', dfr['roles'], 'browser orgs:', dfr['browser_orgs'])

# --- our famdoc for matching ---
prod = FB.our_product(2_000_000)
ours = prod.doc
sets = FB.axis_sets(ours)
oby = {e.elem_id: e for e in ours.elements}
our_census = collections.Counter(e.class_name for e in ours.elements)
print('our census:', dict(our_census))

json.dump({'edges': edges, 'own': own,
           'classes': {str(e.elem_id): e.class_name for e in els},
           'names': {str(e.elem_id): (e.obj.get('m_name') if isinstance(e.obj.get('m_name'), str) else None) for e in els},
           'frame_roles': dfr['roles'], 'browser_orgs': dfr['browser_orgs']},
          open(os.path.join(ROOT, 'experiments/subtractive/_explore/graph.json'), 'w'))
print('saved graph.json')
