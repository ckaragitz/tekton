import json, collections
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
names = {int(k): v for k, v in g['names'].items()}
frame = set(g['frame_roles'].values())
roles = g['frame_roles']

all_ids = set(cls)
top = sorted(i for i in all_ids if i not in own)
print('TOP-LEVEL (unowned):')
for i in top: print(f'  {i} {cls[i]} name={names.get(i)}')

# ownership tree: children per parent
kids = collections.defaultdict(list)
for c, p in own.items(): kids[p].append(c)

def subtree(i, depth=0, out=None):
    out = out if out is not None else []
    out.append((depth, i))
    for c in sorted(kids.get(i, [])): subtree(c, depth+1, out)
    return out

# who owns what: histogram of owner class -> child class
oc = collections.Counter((cls[p], cls[c]) for c, p in own.items())
print('\nOWNERSHIP (owner class -> child class, count):')
for (pc, cc), n in sorted(oc.items(), key=lambda kv: -kv[1])[:40]:
    print(f'  {n:4d}  {pc} -> {cc}')
