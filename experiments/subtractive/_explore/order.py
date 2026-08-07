import sys, os, json, collections
ROOT = '/Users/ck/dev/things/tekton'
sys.path.insert(0, os.path.join(ROOT, 'src')); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import famdoc_bisect as FB
FB._install_schema()
els, _a, _i = FB.load_unit_elements(FB.RST, FB.DONOR_UNIT)
print('DONOR ascending-id order (first 60):')
for e in sorted(els, key=lambda e: e.elem_id)[:60]:
    print(f'  {e.elem_id} {e.class_name}')
print('...')
prod = FB.our_product(2_000_000)
print('\nOURS ascending-id order (all 41):')
for e in sorted(prod.doc.elements, key=lambda e: e.elem_id):
    print(f'  {e.elem_id} {e.class_name} kind={e.kind}')
print('self_family id:', prod.doc.self_family.elem_id)
