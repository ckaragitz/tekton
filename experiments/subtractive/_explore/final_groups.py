import json, collections, re
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
edges = [(int(s), p, int(t)) for s, p, t in g['edges']]
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
roles = g['frame_roles']; SF = roles['self_family']
frame = set(roles.values()); all_ids = set(cls)
nested = set(json.load(open(ROOT + '/experiments/subtractive/_explore/nested_members.json')))
NF = 1411054
S6 = nested | {NF, 1411142, 1411143, 1411144}

def norm(p): return re.sub(r'\[\d+\]', '[]', p)
FAMILY_IDS = {i for i, c in cls.items() if c == 'Family'}
REG_TOP = {'m_familyIds','m_familyParams','m_pFamilyTypes','m_lockedParameterIdsForDirectManipulation',
           'm_cellList','m_oFamDimConstrMgr','m_deletableElements','m_refs','m_fsdos'}
def is_registry(s, p):
    np = norm(p)
    if np.startswith('hdr.m_parents.'): return True
    if s in FAMILY_IDS and np.startswith('obj.') and np.split('.')[1].split('[')[0] in REG_TOP: return True
    if cls[s] == 'VarSketch' and np.startswith('obj.') and np.split('.')[1].split('[')[0] in ('m_dimIds','m_dimData'): return True
    return False
hard_out = collections.defaultdict(set)
for s, p, t in edges:
    if not is_registry(s, p): hard_out[s].add(t)

# structural sketchplane / stray-sketch roles need obj data: load
import sys, os
sys.path.insert(0, os.path.join(ROOT,'src')); sys.path.insert(0, os.path.join(ROOT,'tools'))
import famdoc_bisect as FB
FB._install_schema()
els, _a, _i = FB.load_unit_elements(FB.RST, FB.DONOR_UNIT)
by = {e.elem_id: e for e in els}
EXT = 1410972
ext_sketch = by[EXT].obj.get('m_sketchId')  # ? check key
# find extrusion's sketch: VarSketch owned by EXT
ext_sk = next(e.elem_id for e in els if e.class_name=='VarSketch' and e.owner_id==EXT)

BASE = {
 'S1': {'ExtrusionElem','VarSketch','CurveElem'},
 'S2': {'LinearDimString','RadialDim','Alignment'},
 'S3': {'RefPlane','Level','LevelAttributes','BaseLevelTracker','TrueNorth'},
 'S4': {'DBViewPlan','DBViewSection','DBView3d','DBViewDrafting','Viewer','Viewer3d',
        'DBDrawing','Viewport','DBViewType','ExtentElem','SketchGrid','ModelClipBox',
        'CalloutTag','SectionAttributes','InteriorElevAttributes','SunAndShadowSettings',
        'BrowserOrganization'},
 'S5': {'DimensionStyle','LeaderStyle','SpotElevationStyle','TextNoteAttributes',
        'TagNoteAttributes','FilledRegionAttributes','Text3dAttrSymbol',
        'RevisionCloudAttr','ReferenceViewerAttributes','FilledRegion','TagNote'},
 'S7': {'LoadNatureElem','LoadCaseElem','StructConnectionType','AnalyticalLinkType',
        'StructSettingsElem','AreaSettingsElem','AutoJoinTracker','CoordinateSystemDisplayElem',
        'DefaultDivideSettings','DrawOrder3dElem','Dwg2dExportUserSettingsData','STEPExportSettings',
        'DaylightSourceIdSet','PenWidthTableElem','CoverType','PropertyAttr','RevealAttr',
        'CorniceAttr','ComponentRepeaterSlotSpecialType','RvtLinkInstanceAppearanceParentElem',
        'SketchGridAppearanceParentElem','ParamElemFamily','AutoCamSettingsElem'},
}
def root_attr(i):
    j = i
    while j in own and cls[own[j]] in ('CategoryElem','GStyleElem'):
        j = own[j]
    return own.get(j)
grp = {}
for i in sorted(all_ids):
    if i in frame: grp[i]='FRAME'; continue
    if i in S6: grp[i]='S6'; continue
    c = cls[i]
    if c == 'SketchPlane':
        e = by[i]
        if (e.obj.get('m_ownerDBViewId') or -1) > 0 or (e.header.get('m_ownerViewId') or -1) > 0:
            grp[i]='S4'
        elif (e.obj.get('m_userId') or -1) > 0:
            grp[i]='S1'
        else:
            grp[i]='S3'          # datum-hosted plane
        continue
    if c in ('CategoryElem','GStyleElem','FontElem'):
        ra = root_attr(i)
        if ra is not None and ra not in frame and ra not in S6:
            rc = cls[ra]
            t = None
            for k, v in BASE.items():
                if rc in v: t = k; break
            grp[i] = t or 'S5'
        else:
            grp[i] = 'S5'
        continue
    t = None
    for k, v in BASE.items():
        if c in v: t = k; break
    grp[i] = t or 'UNASSIGNED'
un = [(i, cls[i]) for i,k in grp.items() if k=='UNASSIGNED']
print('unassigned:', un)
sizes = collections.Counter(grp.values())
print('sizes:', dict(sorted(sizes.items())), 'sum:', sum(v for k,v in sizes.items() if k not in ('FRAME',)))

DETACH = {('LevelAttributes','m_familyTagId')}
def cascade(seed, detach=True):
    S = set(seed); refused=[]; detached=[]
    changed=True
    while changed:
        changed=False
        for i in sorted(all_ids - S):
            pulls=set()
            if own.get(i) in S: pulls.add(('own', own[i]))
            for t in hard_out.get(i,()):
                if t in S: pulls.add(('ref', t))
            if not pulls: continue
            # detach rule: LevelAttributes -> FamilySymbol via m_familyTagId
            if detach and cls[i]=='LevelAttributes':
                only_sym = all(cls[t]=='FamilySymbol' for k,t in pulls if k=='ref') and own.get(i) not in S
                if only_sym:
                    detached.append(i); continue
            if i in frame: refused.append((i, sorted(pulls))); continue
            S.add(i); changed=True
    return S, refused, detached

rows = {}
for k in ('S1','S2','S3','S4','S5','S6','S7'):
    seed = {i for i,gk in grp.items() if gk==k}
    S, refused, det = cascade(seed)
    extra = S - seed
    ec = collections.Counter(f'{grp[i]}:{cls[i]}' for i in extra)
    print(f'\n{k}: seed {len(seed)} -> closure {len(S)} (+{len(extra)}) refused={refused} detach={det}')
    for kk,n in sorted(ec.items(), key=lambda kv:-kv[1])[:14]: print(f'    +{n:3d} {kk}')
    rows[k] = {'seed': sorted(seed), 'closure': sorted(S), 'detached': det}
# halves of S5 by constellation root
A_ROOTS = {'DimensionStyle','LeaderStyle','SpotElevationStyle'}
s5 = {i for i,gk in grp.items() if gk=='S5'}
def s5_root(i):
    j=i
    while j in own and cls[j] in ('CategoryElem','GStyleElem','FontElem'):
        j=own[j]
    return j
s5a = {i for i in s5 if cls[s5_root(i)] in A_ROOTS}
s5b = s5 - s5a
Sa,_ ,da = cascade(s5a); Sb,_,db = cascade(s5b)
print(f'\nS5A(dim-flavored styles): seed {len(s5a)} closure {len(Sa)}; S5B(text/region): seed {len(s5b)} closure {len(Sb)}')
print('S5A pulls:', collections.Counter(f'{grp[i]}:{cls[i]}' for i in Sa-s5a))
print('S5B pulls:', collections.Counter(f'{grp[i]}:{cls[i]}' for i in Sb-s5b))
json.dump({'groups': {str(i): grp[i] for i in grp}, 'closures': {k: v for k,v in rows.items()},
           's5a': sorted(s5a), 's5b': sorted(s5b)},
          open(ROOT + '/experiments/subtractive/_explore/final_groups.json','w'))
