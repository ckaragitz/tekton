import json, collections
ROOT = '/Users/ck/dev/things/tekton'
g = json.load(open(ROOT + '/experiments/subtractive/_explore/graph.json'))
own = {int(k): int(v) for k, v in g['own'].items()}
cls = {int(k): v for k, v in g['classes'].items()}
oc = collections.Counter((cls[p], cls[c]) for c, p in own.items())
rows = sorted(oc.items(), key=lambda kv: -kv[1])
print('OWNERSHIP rows 41..end:')
for (pc, cc), n in rows[40:]:
    print(f'  {n:4d}  {pc} -> {cc}')
print()
# owners of each class instance where the class matters
for k in ('CategoryElem','GStyleElem','FontElem','SketchPlane','Viewer','Viewport','DBDrawing','ExtentElem','VarSketch','CurveElem','RefPlane','ParamElemFamily','FamilySymbol','Family','FamilySurrogate','FamSymSurrogate','BrowserOrganization','SunAndShadowSettings','UnitsElem','Level','DBViewType','SketchGrid','Alignment','LinearDimString','RadialDim','ModelClipBox','TrueNorth','BaseLevelTracker','FilledRegion','TagNote','CalloutTag','Text3dAttrSymbol','DaylightSourceIdSet','PenWidthTableElem','CoverType','PropertyAttr','RevealAttr','CorniceAttr','ComponentRepeaterSlotSpecialType','AutoJoinTracker','AutoCamSettingsElem','Dwg2dExportUserSettingsData','AnalyticalLinkType','ExtrusionElem'):
    ids = [i for i, c in cls.items() if c == k]
    owners = collections.Counter(cls.get(own.get(i), 'TOP') for i in ids)
    print(f'{k:38s} n={len(ids):3d} owners={dict(owners)}')
