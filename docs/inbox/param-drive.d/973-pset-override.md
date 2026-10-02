# #973: a type-level pset value never blocks the occurrence's drive

Stream: param-drive. Issue #973 (follow-up to #972's re-review). Base `main` 5d6621a.

## What changed (`src/rvt/ifc/pset_params.py`)
- **IFC's override rule.** A repeat of a label from a pset that no
  `IfcRelDefinesByProperties` links to a product (a type-level set reached through
  `HasPropertySets` has that shape here) never records a conflict against an
  occurrence's value. If it differs, `skipped` says "type-level value X overridden
  by the occurrence value Y". Order-free: when the unattached set comes first, the
  occurrence's value and owners replace it.
- **One tolerance.** Two carried lengths are the same statement when their converted
  values are within `SAME_LENGTH_FT` = 1e-6 ft, which is `pset_drive.SPAN_TOL` (pinned
  equal by a test). Non-lengths compare with `_same_value` (1e-9 relative).
- **One test for "different".** The `skipped` note and the conflict record now use
  the same equality, so float noise or a sub-tolerance repeat is neither.
- Refactor: `_typed()` (kind and converted value) and `_source()` (the source record)
  replace the inline copies.

*Review of #974 (2026-10-02), 🛑 then fixed:*
- A length and a plain number of one value (`IFCLENGTHMEASURE(1574.8)` and
  `IFCREAL(1574.8)` on one product) compared feet against file units, so a correctly
  driven `BodyWidth` became value-only. Mixed kinds now compare the RAW values;
  only two lengths compare converted.
- Two unattached values with no occurrence were worded as "overridden by the
  occurrence value". They now say "the first unattached value … is kept".
- `IfcRelDefinesByType` is not resolved, so the note no longer claims an occurrence
  overrode *its* type: "unattached value X not carried; the occurrence value Y wins".
- An unreadable repeat (for example `IFCLENGTHMEASURE('abc')`) is dropped with a
  `skipped` row saying so; it is not a statement.

## Evidence
- `tests/test_pset_override_973.py`: 6 tests. 3 fail against `5d6621a`'s module (the
  real-conflict guard passes on both); the 2 #974-review tests fail against the PR's
  first head `71b5e3e`.
- The #714 fixture's 7 drives and every `test_review_nits_967_970` case are unchanged.

## BRANCH STATE
- Files: `src/rvt/ifc/pset_params.py` (+ `plugin/lib` mirror),
  `tests/test_pset_override_973.py` (new), `tests/ci_shard.d/973-pset-override.txt`
  (new), this fragment. Nothing staged; no Revit claim (hard rule 4).

## Correction (#975), 2026-10-02
Appended by the #975 fix; the text above is left as merged.
- "What changed" quotes the `skipped` wording as "type-level value X overridden by
  the occurrence value Y". That is the first head's wording. What #974 merged says
  "unattached value X not carried; the occurrence value Y wins", as the #974-review
  bullets above record.
- The #974-review bullet "An unreadable repeat ... is dropped" was incomplete. The
  drop also lost that statement's product as an owner of the label, so a value on
  another product no longer made the label "attached to 2 products". #975 restores
  this, along with three other edge cases: `975-pset-edges.md`.
- The unattached-vs-unattached wording "the first unattached value ... is kept" could
  become false once a later occurrence value replaced it. #975 rewords it.
