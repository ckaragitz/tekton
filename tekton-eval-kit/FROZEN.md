# This kit is a frozen snapshot, not the current plugin

`tekton-eval-kit/` was assembled for evaluators and committed on 2026-08-11
(commit `6f33fb7`). Nothing in it has been updated since. Its
`tekton-plugin/` folder is a copy of the plugin **as it was then** (manifest
version 0.2.0). The `TEST-KIT/` files are the exact files evaluators were
sent. The repo's tests read some of them as fixtures, so they are kept
byte-for-byte rather than refreshed.

**For current behaviour, use `plugin/`** (built by `tools/sync_plugin.py`
into `tekton-plugin.zip`), not this copy.

## Known-stale claims inside the snapshot

These are wrong today. They were superseded after the kit was cut:

- **The open cell.** The snapshot describes the open cell as created walls +
  placed families in ONE file, with the stamp
  `PROOF-ONLY: walls+families combination unverified`. The open cell is
  PLACED INSTANCES of our generated families on our composed genesis base
  (genesis-audit #48, issue #16), and the stamp is
  `rvt.frontdoor.intent.OPEN_CELL_STAMP`. Walls + one loaded family in one
  file is certified (WF_fix / WF_nofix). Whether more families in one file
  pass is open (verdict #27). The fixes are #999 and #1002.
- **Everything else** that changed in `plugin/` after 2026-08-11 is also
  missing here: family drives, the family-edit lane, the certified-evidence
  caveats (#981 / #984 / #990), and more. Diff `plugin/` against this folder
  for the full list.

`tests/test_open_cell_996.py` keeps this note honest. It fails if the
snapshot stops carrying the dead stamp (it was refreshed, so delete this
note) or if this note goes missing while the stamp is still there.
