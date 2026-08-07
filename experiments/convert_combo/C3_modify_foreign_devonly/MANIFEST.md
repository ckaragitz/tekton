# prompt+rfa->rfa (rvt.convert.modify_family) -- deliverable manifest

## The deliverable(s)
* NO FILE PRODUCED -- see errors (nothing withheld)

## Stamps (labels, not refusals)
* PROOF-ONLY, NOT-DELIVERABLE (P0: identity/counsel gates G2-G3 open; every tekton output is an internal proof)
* QUARANTINED TARGET (dev-only proof): the target file is an Autodesk sample standing in for a user upload; this output exists to PROVE the route and is never shipped or redistributed

## Edits applied

## Errors
* apply failed: ValueError: ElemTable footer is 600 bytes / graveyard 18 — GraveyardRec wire layout not observed in corpus
* Traceback (most recent call last):
  File "/Users/ck/dev/things/tekton/src/rvt/convert/modify_family.py", line 549, in modify_family
    rec["apply"] = apply_family_edits(inv, parsed["ops"], out_path)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/ck/dev/things/tekton/src/rvt/convert/modify_family.py", line 462, in apply_family_edits
    crep = M.commit_plans(inv.path, out_path, [plan])
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/ck/dev/things/tekton/src/rvt/manipulate.py", line 1417, in commit_plans
    model = decode_elemtable(doc.inflate("Global/ElemTable"))
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/ck/dev/things/tekton/src/rvt/stream_encoders.py", line 179, in decode_elemtable
    raise ValueError(
ValueError: ElemTable footer is 600 bytes / graveyard 18 — GraveyardRec wire layout not observed in corpus

