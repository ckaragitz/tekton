import json, collections
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
SF = g['frame_roles']['self_family']

# field-ref matrix by (src class, dst class), excluding self-family regs
mat = collections.Counter()
sf_paths = collections.Counter()
for s, p, t in edges:
    if s == SF:
        # bucket self-family paths by top key
        key = p.split('.')[1] if '.' in p else p
        key = key.split('[')[0]
        sf_paths[key] += 1
        continue
    mat[(cls[s], cls[t])] += 1
print('SELF-FAMILY outgoing ref paths (top-key histogram):')
for k, n in sorted(sf_paths.items(), key=lambda kv: -kv[1]):
    print(f'  {n:5d}  {k}')
print()
print('NON-SF field-ref matrix (src class -> dst class, count):')
for (sc, tc), n in sorted(mat.items(), key=lambda kv: -kv[1]):
    print(f'  {n:4d}  {sc} -> {tc}')
