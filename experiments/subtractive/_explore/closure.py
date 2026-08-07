import json, collections, re
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
names = {int(k): v for k, v in g['names'].items()}
roles = g['frame_roles']
SF = roles['self_family']
all_ids = set(cls)

def norm(p): return re.sub(r'\[\d+\]', '[]', p)

REG_SF = True  # all SF outgoing = registry
def is_registry(s, p):
    if s == SF: return True
    np = norm(p)
    if np.startswith('hdr.m_parents.'): return True
    return False

hard = [(s, p, t) for s, p, t in edges if not is_registry(s, p)]
hard_out = collections.defaultdict(set)
for s, p, t in hard: hard_out[s].add(t)

kids = collections.defaultdict(set)
for c, pa in own.items(): kids[pa].add(c)

# ---- FLOOR: frame + pins + params ----
LEVEL, PLAN, EXT = 1410875, 1410877, 1410972
params = sorted(i for i, c in cls.items() if c == 'ParamElemFamily')
floor = set(roles.values()) | {LEVEL, PLAN, EXT} | set(params)
# sun (1), LevelAttributes (1) are class-unique matches of our roster
for c1 in ('SunAndShadowSettings', 'LevelAttributes'):
    floor |= {i for i, c in cls.items() if c == c1}

# hard-ref closure + ownership-ancestor closure
kept = set(floor)
frontier = list(kept)
why = {}
while frontier:
    nxt = []
    for s in frontier:
        for t in hard_out.get(s, ()):  # hard refs
            if t not in kept:
                kept.add(t); why[t] = ('hardref', s); nxt.append(t)
        o = own.get(s)
        if o and o not in kept:  # ownership ancestors
            kept.add(o); why[o] = ('owner_of', s); nxt.append(o)
    frontier = nxt

print(f'floor={len(floor)} kept-closure={len(kept)}')
cc = collections.Counter(cls[i] for i in kept)
print('kept census:', dict(sorted(cc.items())))
print()
print('pulled beyond floor (why):')
for i in sorted(kept - floor):
    w = why.get(i)
    print(f'  {i} {cls[i]:22s} <- {w[0]} {w[1]} ({cls.get(w[1])})' + (f' name={names.get(i)!r}' if names.get(i) else ''))
