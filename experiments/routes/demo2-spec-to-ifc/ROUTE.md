# route: spec -> ifc

* ok: **True** -- OK (deterministic IFC4 from the building spec)
* matrix cell: status **works**, route `spec_to_ifc`, stages: spec->ifc
* delivered:
  * `ifc` -> `experiments/routes/demo2-spec-to-ifc/room-spec.ifc`
* caveats (after delivery, per the deliverable rule):
  * deterministic: identical spec -> byte-identical IFC
* evidence cited by the matrix: worked:usecases/chicago-plenum-electrical-room/generated.ifc; worked:skills/tekton-ifc/tests
* seconds: 0.3
