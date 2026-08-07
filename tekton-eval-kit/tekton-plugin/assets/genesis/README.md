# assets/genesis — the certified genesis project base (a bundled ASSET)

`G_ABPD.rvt` is the ONLY `.rvt` this plugin ships. It is OUR file — the
composed genesis project base (settings / style catalog / palette / datum /
views / residue layers all our constructors' output, composed by
`tools/genesis_compose.py` with no Autodesk-authored base content supplied)
that LOADS in Autodesk's reader as a browsable model. Full account, its
certification, and — as important — what it does NOT prove:
`skills/tekton-author/references/GENESIS-BASE.md`.

| file | what |
|---|---|
| `G_ABPD.rvt` | the base (581,632 bytes, sha256 `84173b8960b8cbba1b096a42ad4a97ed24deba9476ccb05eb8853d4c6d06df50`) |
| `G_ABPD.compose.json` | the composer's manifest for it (source `experiments/genesis/subst_k4/compose/G_ABPD.manifest.json`): the certified parent base, the in-place substitution phase and the lawful deletion phase with every asserted invariant. Its own top-level verdict field reads `NOT-CLEAN` — that is the composer's rung-byte-fidelity bookkeeping at the 19 deleted-by-design slots, NOT a load verdict; the load verdict is the viewer PASS recorded in the certification ledger (verdict #24). |
| `README.md` | this note |

Provenance guard: assets are synced by `tools/sync_plugin.py` from the
research repo with a sha256 check against the front door's pin
(`lib/src/rvt/frontdoor/assets/genesis_base.json` when present) and are
refused if they resolve under any quarantined / third-party-extracted path.
Never edit these by hand — re-certify, re-pin, then re-sync.
