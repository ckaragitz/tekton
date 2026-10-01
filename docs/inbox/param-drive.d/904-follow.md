# 904 — parts that follow a moving plane: the trapeze's rods, washers and nuts

Stream: **param-drive** (fragment; index `../param-drive.md`). Issue **#904**, steer
**#908** (*"the rest of the elements need to be constrained and move with it … fluent
and interchangeable"*). Branch `claude/pull-latest-main-1cmo56`. Follows PR #907
(`904-drive-law.md`).

## What the corpus showed

This is a census of the private reference corpus (#836 / #865, quarantined). It
records field and class facts only, posted on #904. The mechanisms born families use
to keep a part following a moving plane are:

1. a labelled offset dimension between two non-origin planes, chained (907 in 151
   files);
2. a locked unlabelled dimension, segment flags bit 0 (about 860);
3. EQ, dim flags 140, with three witnesses and two segments of flags 2 (1.2k);
4. a circle's centre aligned to a plane (the arc's geomTag 1, 579), and a labelled
   radial dimension (341);
5. a box held rigid about a plane by EQ plus a width;
6. nested families. Hardware is nested in practice, and the corpus's own trapeze
   nests its rods, nuts and washers, hanging each rod plane off its strut-end plane
   by a labelled offset.

## Desktop verdict: the "Follow" probe ladder (owner, 2026-10-01)

There were 9 rungs, staged for 2026 and 2025. Each one is a strut whose Strut Length
drive (verified in #907) is held symmetric about the centre (EQ), plus one follow
mechanism:

| Rung | Mechanism |
|---|---|
| P1 | chained labelled offset |
| P2 | locked unlabelled dimension |
| P2c | control for P2, lock bit cleared |
| P3 | EQ about a labelled offset plane |
| P4 | a circle's centres aligned to a plane |
| P5 | a labelled radius |
| P6 | in-sketch EQ |
| P0, P0n | controls |

**Owner:** *"all 9 worked"*. Reading: each rung behaved as described, the controls
included. The release used has not been stated.

## What was built

- **`drive_law` gains the ladder's mechanisms, ported field for field:**
  - `add_plane`
  - `dim3d` (labelled, or locked unlabelled)
  - `eq3d`
  - `align_arc_centre`
  - `lock_line`
  - `origin_centre_plane`
- **`wire_symmetric(doc, base)`:** EQ(lo | origin centre | hi), so a drive's ends move
  symmetrically. This is the ladder base, present on every rung that passed.
- **`wire_follow(doc, base, caption, offset, followers)`:**
  - plane R_lo = lo + `caption` (labelled);
  - R_hi mirrored by EQ(R_lo | centre | R_hi);
  - per follower, either a **circle** (its arc centres aligned to R) or a **rigid** part
    (its edges at R ± h locked to two planes held EQ about R by a locked width).
  - Every check runs before the first mutation: a length parameter whose value agrees,
    an offset inside the planes, edges or centres on their planes, and no curve already
    locked.
- **The factory.** A linear drive spec may carry `symmetric: True` and a `follow`
  block. Each is all-or-nothing, never undoes the drive it builds on, and is noted
  when refused.
- **The trapeze:**
  - Strut Length is symmetric.
  - Rod Inset carries the followers: both rods, and every washer and nut on every tier.
    At 2 tiers that is 18 followers and 36 locks.
  - The hex nut is rotated 30° so two flats sit square to the strut and can be locked.
  - `lod_note` says what is constrained. `limits` says the assembled trapeze has no
    verdict of its own, that the hex nut is the one unprobed shape, and that Rod
    Spacing, Tier Spacing and rod diameter are values only.

## Evidence

- The 2026 and 2025 trapeze, read back from the written file:
  - 56 sketch locks: 52 line locks, each line on its plane, and 4 arc-centre locks
    (geomTag 1), each centre on its plane;
  - 6 EQ, 2 labelled dims (Strut Length, Rod Inset) and 4 locked dims;
  - 0 `m_constrInfo` and 0 unclean records;
  - `rvt_validate` ok, family mode VALID with 0 errors, PROVENANCE-CLEAN.
- **Tests:**
  - `test_drive_follow_904.py`: 15 tests. The trapeze at 1, 2 and 3 tiers, with every
    lock checked against its plane; the hex nut's flats; a generic box plus circle; 8
    refusal cases, each SHA-identical to the build without the follow; symmetric
    needed; exactly one EQ.
  - The open nit from the #907 round-5 review: the value-mismatch test now compares
    SHA.

## Open

- **A desktop verdict on the assembled trapeze** (the owner): change Strut Length, then
  Rod Inset.
- **The hex nut's follow,** locked by two flats, is the one shape the ladder did not
  cover.
- **Rod diameter as a driver.** A labelled radius (P5) is verified, but "Rod Diameter"
  needs either a diameter-dimension marker (unread) or a formula radius = diameter / 2
  (formulas unverified, #862).
- **Tier Spacing** is the extrusion end (#787 Case B).
- **Nested hardware families,** the corpus's own way, need nested-family authoring.
- **The edit lane (#909)** and the back-edge law (#910) still apply.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/drive_law.py`: the follow mechanisms, `wire_symmetric` and
  `wire_follow`.
- `src/rvt/famgen/factory.py`: the `symmetric` / `follow` spec plumbing and the notes.
- `src/rvt/famgen/archetypes.py`: the hex nut orientation, `_trapeze_drives`
  followers, `lod_note` and `limits`.
- `src/rvt/famgen/taxonomy.py`: the trapeze note.
- `plugin/lib/…`: mirrors.
- `tests/test_drive_follow_904.py`: new.
- `tests/ci_shard.d/904-drive-follow.txt`: new.
- `tests/test_drive_law_904.py`: the SHA comparison.
- this fragment.

**Gates**
- the follow, drive-law and trapeze suites plus the #812 sweep, constraint_law,
  parametric, famgen, taxonomy, route, bootstrap and plugin suites:
  **1169 passed / 21 skipped / 5 xfailed**;
- `sync_plugin --check` in sync; `validate_plugin` PASS; portable paths ok.

**Shipped vs staged:** the mechanisms are desktop-verified one by one. The assembled
trapeze is staged for the owner's check.
