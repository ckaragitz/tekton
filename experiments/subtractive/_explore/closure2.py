import json, collections, re
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
roles = g['frame_roles']; SF = roles['self_family']

def norm(p): return re.sub(r'\[\d+\]', '[]', p)
FAMILY_IDS = {i for i, c in cls.items() if c == 'Family'}
REG_TOP = {'m_familyIds','m_familyParams','m_pFamilyTypes',
           'm_lockedParameterIdsForDirectManipulation','m_cellList',
           'm_oFamDimConstrMgr','m_deletableElements','m_refs','m_fsdos'}
def is_registry(s, p):
    np = norm(p)
    if np.startswith('hdr.m_parents.'): return True
    if s in FAMILY_IDS:
        top = np.split('.')[1] if np.startswith('obj.') else None
        if top and top.split('[')[0] in REG_TOP: return True
    if cls[s] == 'VarSketch':
        top = np.split('.')[1] if np.startswith('obj.') else None
        if top and top.split('[')[0] in ('m_dimIds','m_dimData'): return True
    return False

hard = [(s, p, t) for s, p, t in edges if not is_registry(s, p)]
hard_out = collections.defaultdict(set)
for s, p, t in hard: hard_out[s].add(t)

kept = set(roles.values())
frontier = list(kept); why = {}
while frontier:
    nxt = []
    for s in frontier:
        for t in hard_out.get(s, ()):
            if t not in kept: kept.add(t); why[t]=('hardref',s); nxt.append(t)
        o = own.get(s)
        if o and o not in kept: kept.add(o); why[o]=('owner',s); nxt.append(o)
    frontier = nxt
print('frame-only closure:', len(kept))
for i in sorted(kept - set(roles.values())):
    print(f'  pulled {i} {cls[i]} <- {why[i]}')

# what hard refs does each frame element make (any target)?
for r, i in roles.items():
    outs = sorted(hard_out.get(i, ()))
    print(f'{r} {i} hard-> {[(t, cls[t]) for t in outs]}')
