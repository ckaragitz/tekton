# rft-mining — laws mined from Revit's default `.rft` family templates

The owner supplied Revit's complete default family-template set (2026). The files are
third-party material and live ONLY in the git-ignored quarantine (`samples/rft/`,
`vendor/rft/`); nothing here copies template content. What we take is **laws** — the
integers and shapes Autodesk's own family documents declare — and we author our own
equivalents (hard rule 3). `tools/rft_facts.py` re-mines everything the records below
claim, and `check` proves the shipped tables still match the templates on any machine
that has them.

Why this material matters: a `.rft` is an Autodesk-BORN family document. It answers,
from the format itself, several questions that were previously gated on a human with
desktop Revit.

## Fragments

- `516-category-facts.md` — family category ids + part types per category, mined from
  108 templates; seven shipped ids were wrong and silently built the wrong kind of
  family. Removed the `needs-revit-desktop` gate from #516.

## Standing summary

- **108 templates decode clean** through our codec (`load_rft_elements`), 1686–2194
  elements each.
- **Category id per family kind: settled.** `src/rvt/famgen/category_facts.py`.
- **Part types: mostly −1 or 0.** The exceptions are Electrical Equipment 14, Data
  Panel 17, and the duct fittings, which enumerate by fitting kind (elbow 5, tee 6,
  transition 7, cross 8).
- **Templates do NOT carry per-category standard parameters.** Almost every template
  carries exactly `Radius` / `Width` / `Length`; only genuinely parametric kinds add
  more (Door: `Frame Width`, `Frame Projection Int./Ext.`; Window: `Default Sill
  Height`; the duct fittings: `Angle`, `Center Radius`, `Insulation Thickness`,
  `Lining Thickness`, …). This **confirms** the `ORIGIN_BUILTIN` design in
  `standards.py`: a category's standard parameters are supplied by Revit's binary at
  runtime, not stored in the family document, so they are listed and never authored.
- **Templates do NOT carry populated driver tables.** Every `Family` element's
  `FamDimConstrMgr` is empty and `m_constrInfo` is `[]` on every dimension — a
  template has no user geometry, so it has recorded no flex. The templates therefore
  do **not** answer #689; a real `.rfa` with a working flex still would.
