import json, collections, re
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
roles = g['frame_roles']; SF = roles['self_family']
frame = set(roles.values())
all_ids = set(cls)

def norm(p): return re.sub(r'\[\d+\]', '[]', p)
FAMILY_IDS = {i for i, c in cls.items() if c == 'Family'}
REG_TOP = {'m_familyIds','m_familyParams','m_pFamilyTypes',
           'm_lockedParameterIdsForDirectManipulation','m_cellList',
           'm_oFamDimConstrMgr','m_deletableElements','m_refs','m_fsdos'}
def is_registry(s, p):
    np = norm(p)
    if np.startswith('hdr.m_parents.'): return True
    if s in FAMILY_IDS:
        if np.startswith('obj.') and np.split('.')[1].split('[')[0] in REG_TOP: return True
    if cls[s] == 'VarSketch':
        if np.startswith('obj.') and np.split('.')[1].split('[')[0] in ('m_dimIds','m_dimData'): return True
    return False
hard_in = collections.defaultdict(set)   # target -> {sources}
hard_out = collections.defaultdict(set)
for s, p, t in edges:
    if is_registry(s, p): continue
    hard_out[s].add(t); hard_in[t].add(s)

# nested cluster
NF = 1411054
import sys, os
sys.path.insert(0, os.path.join(ROOT,'src')); sys.path.insert(0, os.path.join(ROOT,'tools'))
nested_members = json.load(open(ROOT + '/experiments/subtractive/_explore/nested_members.json')) if os.path.exists(ROOT + '/experiments/subtractive/_explore/nested_members.json') else None
if nested_members is None:
    import famdoc_bisect as FB
    FB._install_schema()
    els, _a, _i = FB.load_unit_elements(FB.RST, FB.DONOR_UNIT)
    by = {e.elem_id: e for e in els}
    fi = ((by[NF].obj.get('m_familyIds') or {}).get('value') or {}).get('m_data') or []
    nested_members = sorted(int(d['m_elementId']) for d in fi)
    json.dump(nested_members, open(ROOT + '/experiments/subtractive/_explore/nested_members.json','w'))
S6 = set(nested_members) | {NF, 1411142, 1411143, 1411144}

# ownership-root attr for cat/gstyle/font
def root_attr(i):
    j = i
    while j in own and cls[own[j]] in ('CategoryElem','GStyleElem'):
        j = own[j]
    return own.get(j)  # the attr that owns the top cat (or None)

CLASS_GROUP = {
 'S1': {'ExtrusionElem','VarSketch','CurveElem','SketchPlane'},
 'S2': {'LinearDimString','RadialDim','Alignment'},
 'S3': {'RefPlane','Level','LevelAttributes','BaseLevelTracker','TrueNorth'},
 'S4': {'DBViewPlan','DBViewSection','DBView3d','DBViewDrafting','Viewer','Viewer3d',
        'DBDrawing','Viewport','DBViewType','ExtentElem','SketchGrid','ModelClipBox',
        'CalloutTag','SectionAttributes','InteriorElevAttributes'},
 'S5': {'DimensionStyle','LeaderStyle','SpotElevationStyle','TextNoteAttributes',
        'TagNoteAttributes','FilledRegionAttributes','Text3dAttrSymbol',
        'RevisionCloudAttr','ReferenceViewerAttributes','FilledRegion','TagNote'},
 'S7': {'LoadNatureElem','LoadCaseElem','StructConnectionType','AnalyticalLinkType',
        'StructSettingsElem','AreaSettingsElem','AutoJoinTracker',
        'CoordinateSystemDisplayElem','DefaultDivideSettings','DrawOrder3dElem',
        'Dwg2dExportUserSettingsData','STEPExportSettings','DaylightSourceIdSet',
        'PenWidthTableElem','CoverType','PropertyAttr','RevealAttr','CorniceAttr',
        'ComponentRepeaterSlotSpecialType','RvtLinkInstanceAppearanceParentElem',
        'SketchGridAppearanceParentElem','ParamElemFamily','AutoCamSettingsElem'},
}
grp = {}
for i in sorted(all_ids):
    if i in frame: grp[i] = 'FRAME'; continue
    if i in S6: grp[i] = 'S6'; continue
    c = cls[i]
    if c in ('CategoryElem','GStyleElem','FontElem'):
        ra = root_attr(i)
        if ra is not None and ra not in frame:
            tgt = grp.get(ra)
            if tgt is None:
                rc = cls[ra]
                for k, v in CLASS_GROUP.items():
                    if rc in v: tgt = k; break
            grp[i] = tgt or 'S5'
        else:
            grp[i] = 'S5'
        continue
    assigned = None
    for k, v in CLASS_GROUP.items():
        if c in v: assigned = k; break
    grp[i] = assigned or 'UNASSIGNED'
un = [i for i, k in grp.items() if k == 'UNASSIGNED']
print('unassigned:', [(i, cls[i]) for i in un])
sizes = collections.Counter(grp.values())
print('sizes:', dict(sorted(sizes.items())))

# per-group cascade closure (frame protected)
def cascade(seed):
    S = set(seed)
    changed = True
    refused = []
    while changed:
        changed = False
        for i in sorted(all_ids - S):
            pulls = (own.get(i) in S) or any(t in S for t in hard_out.get(i, ()))
            if pulls:
                if i in frame:
                    refused.append(i); continue
                S.add(i); changed = True
    return S, refused

for k in ('S1','S2','S3','S4','S5','S6','S7'):
    seed = {i for i, gk in grp.items() if gk == k}
    S, refused = cascade(seed)
    extra = S - seed
    ec = collections.Counter(f'{grp[i]}:{cls[i]}' for i in extra)
    print(f'\n{k}: seed {len(seed)} -> closure {len(S)} (pulled {len(extra)}) refused={refused}')
    for kk, n in sorted(ec.items(), key=lambda kv: -kv[1])[:12]:
        print(f'    +{n:3d} {kk}')
json.dump({str(i): grp[i] for i in grp}, open(ROOT + '/experiments/subtractive/_explore/groups.json','w'))
