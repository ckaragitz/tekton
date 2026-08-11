# param-drive — making a family parameter actually MOVE the geometry

A generated family whose Width/Height parameters flex needs a chain: reference planes,
alignments binding the solid's sketch to them, a labelled dimension carrying the
parameter id, and the driver tables that say the parameter *drives* that dimension.
`param_drive` (#372) authored the first three; #689 found the fourth was empty in every
family this engine writes, which is why nothing flexed.

## Fragments

- `689-parametric-spine.md` — the `FamDimConstrMgr` driver tables (rung ladder D0–D4),
  and the declarative spine that derives the whole chain from what a product is
  parametric in, bound to its category's Revit template.

## Standing summary

- The driver-table STRUCTURE is schema fact; the VALUES are a hypothesis ladder.
  Default rung is D0 — the control, which must not flex.
- Revit's default `.rft` templates cannot settle the rungs: their driver tables are
  empty too (no user geometry, no recorded flex). A Revit-born parametric `.rfa` would
  settle all four unknowns by direct reading.
- Nothing in this stream claims a family flexes in Revit (hard rule 4).
