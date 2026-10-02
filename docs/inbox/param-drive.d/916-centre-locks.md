# 916 — circle centre locks to the origin planes: census says no rule (no code change)

Stream: **param-drive** (fragment; index `../param-drive.md`). Issue **#916**, the gap both
earlier fragments left open (`916-run-arc.md`, `916-plan-arc.md`): born families lock some
circle centres to reference planes, and our non-follower circles (cylinder parts centred on
the origin planes, conduit runs, the downlight's can / trim / lens, the fan units' round
parts) carry no centre lock. Base `276a5a8`. No probe families were made and nothing was
sent to the owner. No Revit claim is made here (hard rule 4).

**Decision: no code change.** The census does not support "a circle whose centre lies on
an origin centre plane is locked to it" — born families leave about 93 % of such circles
unlocked. A born centre lock goes to a plane that MOVES (a labelled or EQ-held plane),
which is the follow drive (#904 P4) this engine already authors. Every product's bytes are
unchanged because nothing was changed.

## Census (421-family private reference corpus — development instrument, counts only)

Scripts in the session scratchpad (`centre916/census*.py`, `cdim.py`, `driven.py`, never
committed). Population: every `ExtrusionElem` whose sketch holds ONE full arc (a single
circle): **235 plan** (horizontal sketch) and **147 run** (vertical sketch) circles — the
same populations as the two earlier fragments. A circle "sits on" a plane when its world
centre (`GArc.m_center`, a world point in both lanes) is within 1e-6 ft of the plane
(`constraint_law.plane_of_any`); only planes whose normal lies in the sketch plane count
(a lockable direction). "Origin plane" = `m_definesOrigin`; counted once per axis.

### Which circles sit on an origin plane, and which are locked to it

| lane | axis of the origin plane | circles on it | `Alignment` to it | to another plane | flags-28 centre dim | nothing |
|---|---|---:|---:|---:|---:|---:|
| plan | X (Center Left/Right) | 74 | **8** | 1 | 50 | 15 |
| plan | Y (Center Front/Back) | 104 | **2** | 0 | 89 | 13 |
| run | X | 28 | **3** | 0 | 14 | 11 |
| run | Y | 72 | **5** | 0 | 53 | 14 |
| run | Z (origin elevation plane) | 76 | **6** | 0 | 2 | 68 |

- **Plan:** 137 / 235 circles sit on at least one origin plane (both 41, X only 33, Y only
  63); **9 / 137** are centre-locked to an origin plane (10 locks); 10 / 178 circle-axis
  pairs (5.6 %).
- **Runs:** 14 locks to an origin plane over 176 circle-axis pairs (8.0 %); the 10 / 151
  runs that lock both directions of the earlier fragment are these plus the instance locks.
- **Off the origin planes:** plan 98 circles — 10 centre-locked (to other planes), 75 with
  a flags-28 centre dim only, 13 nothing; runs 33 — 0 locked, 16 dim, 17 nothing.

### What born centre locks go to

- **Per circle (plan, 235):** no centre lock 212; two locks to two non-origin planes 11;
  origin X + plane Y 5; one plane X 3; one origin X 2; origin X + origin Y 1; origin Y +
  plane X 1 — **41 locks: 10 to origin planes, 31 to other planes**.
  **Runs (147):** none 137; origin Y + origin Z 5; origin X + plane Z 2; origin X +
  origin Z 1; two nested-instance locks 1; instance + plane Z 1 — **20 locks: 14 origin,
  3 other planes, 3 nested instance** (the earlier fragment's numbers, reproduced).
- **The target planes are driven:** every non-origin plane a centre is locked to is held
  by a dimension — plan 31 / 31 (EQ 21, labelled 8, labelled + locked 2), run 3 / 3
  (labelled). Origin targets: plan 10 / 10 witnessed by an EQ and/or labelled dim (as
  every origin centre plane is); run 8 / 14, the 6 others undriven.
  **Reading:** a born centre lock ties a circle to a plane that moves — the follow
  pattern (#904 P4, the trapeze rods' centre locks). A centre on a fixed origin plane is
  almost never locked: the plane does not move, so a lock holds nothing a born author
  needed.

### The born centre lock's fields (41 plan + 20 run `Alignment`s, witness geomTag 1)

- `m_flags` 30 (61 / 61); header category −2000262 (61 / 61); **header owner view −1
  (61 / 61)**; a sketch member of the circle's own sketch, listed in its `m_dimIds`
  (61 / 61), `m_dimData` second 0 / 1 (plan 23 / 18, run 10 / 10); regenOnly
  [SketchPlane] 58 (3 instance locks: Level, SketchPlane, FamilySymbol);
  `m_dimLockedForLabeling` False, `m_orientType` 0 (61 / 61).
- Witnesses: the plane first (geomTag 0, subTag −1, constrFlags 4), then the arc (geomTag
  1, subTag −1, constrFlags 2, `m_refLength` 0), both `m_oldRefSegEndIdx` 0 — 58 / 58
  plane locks; witness ids (plane 0, arc 1) with segment id2 1 on 36 (plan 26, 2 of them
  with `m_lastDimSegInfoId` id2 1; run 10), (plane 1, arc 0) with id2 −1 on 25.
- Segment: flags 1, `m_paramId` −1 (61 / 61); segment origin = the centre and on the plane
  (58 / 58 plane locks).
- `m_constrDir` parallel to the plane normal (58 / 58); `m_pDimLine` direction square to
  it (61 / 61); `m_refPnts` both on the plane, the second at the centre and the first not
  (58 / 58); `m_oldOrigin` on the plane (58 / 58) but **never the centre (0 / 61)**.

### The flags-28 centre dimensions (the commonest relation, not a lock)

539 `LinearDimString`s witness a single circle's centre (geomTag 1) and one other
reference: 534 are `m_flags` 28 in the internal dimension-style category −2000261 (the
"secret internal style" #948 found pinning the hexagon corner), unlabelled, segment flags
0 (not locked), sketch members (534 / 534). They are **not centre-on-plane pins**: 361
are zero-length (the centre on the plane — origin planes 208, other planes 111, a Level
42) and 173 are not (the centre off the plane it witnesses). 5 more are ordinary labelled
dimensions (flags 12, category −2000260) from a centre to an origin plane. Authoring the
internal style constellation was declined in #948 (it is only ever seen inside Autodesk-
born files) and nothing here shows it constrains anything, so it is out of scope.

## Observation on our own centre-lock author (no change made)

`drive_law.align_arc_centre` (the #904 P4 follow lock, the one desktop-verified on the
owner's Revit with the rest of the Follow ladder) matches the born lock above on flags,
category, witness order / constrFlags / geomTags / refLength, segment, constrDir, dim-line
direction and refPnts, with two differences: it writes the header owner view and
`m_ownerDBViewId` = the plan view (born −1, 61 / 61), and `m_oldOrigin` = the centre (born
never, 0 / 61, though on the plane 58 / 58). It also uses the (plane 1, arc 0) id form
(born 25 / 61, the minority). These are recorded, not changed: the form as written is the
one the #904 desktop round accepted, and changing a verified lock is a single-variable
round of its own, not a side effect of this one (filed as #986).

## What a future rule would need

If a future steer wants a centre held on an origin plane anyway (for instance so a
diameter edit cannot drift the centre), the author is `align_arc_centre(doc, arc, sk,
drive_law.origin_centre_plane(doc, axis), axis)` and `constraint_law` CG7 already judges it
(a `GArc` with geomTag 1 has `m_center` on the plane). A run's lock in z would need the
Ref. Level / origin elevation plane as the target, which no lane here authors. Neither is
born practice by the counts above, so neither is built.

## BRANCH STATE

**Files written:** this fragment only. No source, test or plugin file changed, so every
product (cylinder parts, trapeze, downlight, fan units, conduit runs, panelboard,
transformer, LCP, cable tray, wireway, junction box, strut channel, prism, rotated
`cylinder_x`, the flagship 6-panel go author) is byte-identical to `276a5a8` by
construction; no byte-delta table is needed and none was measured.

**Gates:** `tools/dev/check_portable_paths.py` ok (3,476 tracked paths, this fragment
included); `tools/sync_plugin.py --check` clean (plugin in sync,
deny-audit clean); `tests/test_records_layout.py` 5 passed. No test was added and no product suite was re-run: there is no
behaviour to pin and no byte that could move.

**Shipped vs staged:** nothing shipped beyond the record; nothing staged for a viewer or
desktop round.
