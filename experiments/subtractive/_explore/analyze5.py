import json, collections
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
SF = g['frame_roles']['self_family']

def normpath(p):
    # collapse indices
    import re
    return re.sub(r'\[\d+\]', '[]', p)

# path histogram per (srccls,dstcls)
ph = collections.defaultdict(collections.Counter)
for s, p, t in edges:
    if s == SF: continue
    ph[(cls[s], cls[t])][normpath(p)] += 1

interesting = [
    ('CategoryElem','Family'), ('GStyleElem','Family'), ('CategoryElem','GStyleElem'),
    ('GStyleElem','CategoryElem'), ('CategoryElem','DimensionStyle'), ('DimensionStyle','CategoryElem'),
    ('LinearDimString','RefPlane'), ('LinearDimString','DimensionStyle'), ('LinearDimString','ParamElemFamily'),
    ('ExtentElem','RefPlane'), ('DBViewType','CalloutTag'), ('DBViewType','SectionAttributes'),
    ('Viewer','DBViewType'), ('SketchPlane','DBViewSection'), ('RefPlane','DBViewPlan'),
    ('Family','CategoryElem'), ('Family','CurveElem'), ('Family','DBViewType'), ('Family','LinearDimString'),
    ('Level','LevelAttributes'), ('LevelAttributes','CategoryElem'), ('VarSketch','LinearDimString'),
    ('VarSketch','CurveElem'), ('FamilySymbol','CurveElem'), ('FamilySymbol','TagNoteAttributes'),
    ('DimensionStyle','FontElem'), ('Alignment','RefPlane'), ('Alignment','ExtrusionElem'),
    ('DBViewPlan','Level'), ('SketchPlane','Level'), ('Level','UnitsElem'), ('LinearDimString','UnitsElem'),
    ('TagNote','TagNoteAttributes'), ('FilledRegion','FilledRegionAttributes'), ('SketchGrid','SketchGridAppearanceParentElem'),
]
for key in interesting:
    c = ph.get(key)
    if not c: print(f'{key}: NONE'); continue
    print(f'{key[0]} -> {key[1]}  (total {sum(c.values())})')
    for p, n in c.most_common(4):
        print(f'    {n:4d}  {p}')
