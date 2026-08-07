# rvt->rfa (rvt.convert.extract_family) -- deliverable manifest

## The deliverable(s)
* **rfa**: `experiments/convert/extract-family-foreign/rme_level_head_QUARANTINED.rfa` (319,488 bytes, sha256 afc722cab27f03f3...)

## Extracted family
* `M_Level Head - Circle` (host family 88459, unit 265, category -2006020, types ['M_Level Head - Circle'])
* source lineage: foreign (native Revit save lineage)

## Stamps (labels, not refusals)
* FOREIGN DESIGN CONTENT: the source model was not authored by tekton -- the extracted .rfa carries THAT model's family (their geometry, their parameters, their type values). Dev/interop artifact for the file's owner; never shipped as tekton content.
* QUARANTINED SOURCE (dev-only): research-corpus / third-party content; the extraction stays in experiments/.

## Gates (self-checks)
* family-mode validator: INVALID (1 errors, 0 warnings)
* records decode clean: True
* self-checks ok: **False**

## Caveats
* self-checks did not all pass -- the file is delivered with this label; see validation
* the family document references HOST-side resources (categories / styles / materials) that have no embedded twin in this unit (they are not in the host Family's big2SmallMap2 either) -- a project-hosted family is not fully self-contained. Standalone extraction of such a family needs HOST-RESOURCE REPATRIATION (copy those host records into the unit and remap the references): a named follow-up, not built in v1. Our own generated families are self-contained and extract clean.

