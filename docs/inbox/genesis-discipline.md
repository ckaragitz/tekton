# genesis-discipline — STANDING CONTROLS DISCIPLINE + CAMPAIGN LEDGER HYGIENE (workstream record, 2026-08-04)

Charter (ORCHESTRATOR VERDICTS #15, the K1 retraction): tonight lost five
hours because (a) a base — K1 — was ASSUMED sound instead of certified, and
(b) four consecutive rounds carried ZERO known-PASS controls, so a broken base
masqueraded as forty findings. Make both **mechanically impossible**, then
apply the same test **retroactively** to every recorded verdict so the ledger
tells the truth about which of the 40+ verdicts still constitute evidence.

**Deliverables (this stream's territory only):** `tools/probe_batch.py` (the
batch gate + control generator + verdict interpreter + history replayer),
`tests/test_probe_batch.py` (34 pass), `docs/writer/verdict-integrity-audit.md`
(the honest map — every recorded FAIL classified), the annotate-only pass over
`docs/coverage/viewer-certified.json` (`cause_status` on all 34 `failed`
entries + an `integrity_audit` pointer; nothing deleted, `certified`
untouched), one appended section `## VERDICT INTEGRITY LEDGER` in
`docs/inbox/genesis-audit.md`, and this record. No existing `src/`, tool,
test or `.rvt` was edited; no browser used.

## Result in one screen

* **The gate exists and works on every corpus manifest convention.**
  `tools/probe_batch.py stage FILES…` resolves each probe's declared BASE
  from its `probes.json` (11 heterogeneous formats: `derived_from` /
  `derives_from` / `base` / addpath `template`→`reference_files` /
  `parent_rung` / `passing_sibling` / `known_sibling` / manifest-level
  `base`/`start_base`, the latest-probes symbolic `bases` map, absolute
  paths, and — as a WEAK fallback — unique bare filenames), **REFUSES** the
  batch unless every base is *itself* in the ledger's `certified` (a
  recorded-FAIL base is refused with the failure's own text; a probe with NO
  declared base is refused; the manifest's own "(viewer PASS)" prose is
  ignored), auto-generates the round's **certified CONTROL**
  (`CTRL_<newest-certified>_b<n>.rvt`, byte-identity asserted), stages into
  `experiments/acceptance/`, and writes `batch_<n>.json` = per entry `{file,
  md5, base, base_certification, kind}` with the **control first** in the
  reading order. A file uploaded *to be certified* is a `--candidate-base`.
* **`read_batch_verdicts()`** is the only sanctioned way to read a round:
  control FAILED ⇒ `VOID_ROUND` (every other verdict void; pause; re-upload
  a fresh control alone); control pending ⇒ interpret nothing; a probe whose
  base is uncertified ⇒ refuse it and demand the base be uploaded first; only
  then attribute a FAIL to the probe's ONE change — and emit paste-ready
  ledger `certified`/`failed` snippets.
* **The retro audit is done and machine-reproducible**
  (`tools/probe_batch.py retro` → `docs/writer/verdict-integrity-audit.md`
  §3): **46 verdicts; 35 FAILs = 31 VOID + 3 UNGUARDED + exactly 1 SOUND
  (R9b→KD1); 11 PASSes survive.** ONE round of fourteen (#12) carried a
  deliberate control; eight of twelve FAIL-bearing rounds carried no passing
  file. Bug A ("settings singletons required" / "catalog required", verdict
  #6) is VOID — K5/K6 rest on K1. What survives: dangling-tolerance (R5/R9),
  the four-registry law + Bug-B fix (R9b→KD1), K4, K3, L1a, T_conduit_types,
  V30–V32, the death signatures, the P4/P6 live-id rule (unguarded but
  consistent), every corpus fact the linter/fixer mined, and K1's own FAIL
  (base R5 certified; robust under either oracle branch) — the campaign's
  real product.

## Evidence log

### E1. The base-declaration surface of the corpus — measured before design
Enumerated all 11 `probes.json`/`manifest.json` under `experiments/`
(`genesis_addpath_probes`, `genesis_controls`, `regadd`, `triage` ×2,
`subst`, `subst_v2`, `addback`, `singletons`, `loader`, `families/genesis2`,
plus the latest-probes `manifest.json`). Base declarations use eight
different keys and three path styles (repo-relative, absolute, bare name);
several embed the false prose "(viewer PASS)" about K1. **25 probe entries (across six manifests) declare
K1 as base; K1 was never in `certified` and is in `failed` (crash
-1073741831).** The resolver was built to that surface, then verified:
`resolve` on X0 → K1 (failed), P_ep_only → K1 via `template`, P_ep → X0
(failed), X3 → X2 (unknown), X_pen → K1 via bare "K1.rvt", S3 → K5c
(unknown), KD1 → R9 (**certified**), L1a → the rst sample (certified
source), P4_ids_null → the rst sample via the symbolic `bases.rst`, B3 → R9,
and staged copies under `experiments/acceptance/` back to their source
manifests. `subst_v2/X1` declares only "K1 (its passing parent rung)" — no
resolvable file — and is refused as *undeclared* (the discipline: declare
`base` as a full repo path).

### E2. The gate refuses tonight's batches — demonstrated
`probe_batch.py check` on {P_ep_only, XR0, X3, subst_v2/X1, S2} → **BATCH
REFUSED, 5 violations**, each naming the exact base, the manifest field that
declared it, and the ledger fact: K1 "is a RECORDED VIEWER FAILURE (crash
-1073741831, ~02:40)"; X2/K5b "NOT in 'certified' — 'derived from a
certified file' does not count and the manifest's own '(viewer PASS)' prose
is not evidence"; subst_v2/X1 "NO DECLARED BASE — undeclared lineage is
refused (that is how the K1 base slipped through)". Against yesterday's
ledger (K1 merely *absent*), the same gate refuses the ~19:12 K5/K6 upload —
that refusal is the five hours.

### E3. An admissible batch stages correctly
`stage K4b KD1a --candidate-base K2` (K4b's base K3 and KD1a's base R9 are
certified), into a scratch out-dir: manifest `batch_<n>.json` (numbering
floors at 15 — the campaign consumed rounds 1–14) written with the control
`CTRL_R9_recheck_b<n>.rvt` first (md5 == R9's md5 == the certified copy's
md5 — asserted), then the candidate-base (K2, with the printed ADVISORY that
its declared lineage K1 is a recorded failure), then the two probes, each
carrying `base` + `base_certification` (the ledger's `proves` text). All
three `read_batch_verdicts` branches exercised: control FAIL ⇒
`VOID_ROUND` + "do NOT enter any of this round's verdicts into the ledger";
control pending ⇒ `INCOMPLETE`; control PASS ⇒ K4b's FAIL "ATTRIBUTED …
convicts the probe's ONE stated change", KD1a's PASS certifiable, K2's FAIL
"candidate BASE fails on its own; nothing may be built on it".

### E4. The retro replay = the audit's table
`HISTORY_ROUNDS` (14 rounds, transcribed from verdicts #1–#15 + the ledger's
`when` fields) run through `classify_history()` — the same
control→base→attribution order applied to history. Key mechanical outcomes
(each pinned by a test): every FAIL whose base is K1 classifies **VOID**
(≥12 rows); K5/K6/K5a/K5d/S-set/R1/R2/R3/X-set/G1-set VOID; R9b the single
SOUND FAIL ("CONFIRMED" by KD1); G0 VOID with its dangling-id suspect
REFUTED; **K1's own FAIL reads UNGUARDED with base R5 certified** (audit §6
argues why it is nevertheless decisive); rounds with a deliberate control =
[12]; FAIL rounds with no pass = [4, 7, 8, 9, 10, 11, 13, 14].

### E5. Ledger discrepancies (surfaced, not silently fixed — see audit §8)
R4s + R0_identity ARE ledger-certified while genesis-status E5 / audit §B6
say "no R-rung viewer pass" (the acceptance log stopped at batch 10; the
LEDGER is the authority — a `CTRL_R4s` control in a future round re-proves
both cheaply); XR_null's #15 FAIL is absent from `failed`; 18 genesis-era files sit in
`experiments/acceptance/` with no recorded verdict (queue-as-directory loses
"never uploaded" vs "read forgotten" — the batch manifests keep it); the six
samples are certified in fact (every lineage builds on them) but not listed
— the gate admits `samples/*.rvt` by rule; listing them removes the rule.

## New laws / method findings (for KNOWLEDGE.md)

1. **A base is certified before anything is built on it, and "certified"
   means listed in the ledger's `certified` — nothing else.** Derivation
   from a certified file is not certification (K1 = "R5 minus placed model"
   crashed on its own while R5 loads); manifest prose ("(viewer PASS)") is
   not certification. `[verified: 25 probe entries across six manifests carried false certification
   prose about K1]`
2. **Every viewer round carries ≥ 1 CONTROL = a byte-identical, renamed
   (CTRL_ prefix + batch tag) copy of a CERTIFIED file, generated
   automatically, read FIRST.** A co-uploaded candidate that happens to pass
   guards a round only by luck; a copy of an uncertified file (round 13's
   XR_null) is not a control. `[the two CTRL_* files at ~01:55 are the
   proven pattern: md5-identical copies passed]`
3. **A round is read in exactly one order:** control FAIL ⇒ the whole round
   is VOID (oracle/environment), never a finding; control PASS but a
   probe's base uncertified ⇒ refuse that probe, upload the base first;
   only then attribute a FAIL to the probe's one change. Implemented as
   `read_batch_verdicts()`; a round with no control is refused outright.
4. **A viewer FAIL is evidence only on the two-axis test** (base itself
   certified at verdict time ∧ round carried a known-PASS control).
   Applied to the campaign: 35 FAILs → 31 VOID / 3 UNGUARDED / 1 SOUND. The
   corpus-mined FACTS (scale-key sets, per-category flag profiles, ownership
   webs, vintage bands, record-order law) never depended on a verdict and
   are unaffected. `[audit §3, §5]`
5. **The K1 retraction is robust under both oracle branches** (healthy ⇒
   K1 broken; sick ⇒ rounds 8–14 unread anyway) — there is no branch on
   which verdicts #9–#14 stand. K1's own FAIL is attributable (base R5
   certified, byte-identical XR_null corroborates, ~01:55 controls guard the
   window). `[audit §6]`

## Gotchas found

1. The reduction ladder's `R9b`/`R10b` are built on `R9`/`R10` respectively;
   R10 was never uploaded, so R10b's verdict was void-by-base from the start
   — the round-2 conclusion happened to be right (R9b re-proved it) but was
   not entitled to be.
2. `experiments/genesis/latest/probes/manifest.json` keeps build details under
   `probes` (keyed by filename, no base) and the base under `viewer_queue`
   (`"base": "rst"` → top-level `bases`); a resolver that stops at `probes`
   sees no base. The gate reads both blocks.
3. Basename collisions are real: `subst/X1.rvt` vs `subst_v2/X1.rvt`; the
   viewer and the acceptance folder key on the *name*. The gate refuses a
   batch whose basenames collide (rename first) and refuses to overwrite a
   *different* file already staged under a name.
4. `experiments/acceptance/` doubles as upload queue and archive: 16 staged
   files have no recorded verdict. Only the `batch_<n>.json` manifests
   disambiguate "staged, never uploaded" from "uploaded, verdict forgotten".

## How to use (orchestrator)

```
# a normal round: probes on certified bases (the control is added for you)
.venv/bin/python tools/probe_batch.py stage <probe.rvt>... [--note "..."]
#   -> refuses (exit 2) on any uncertified/undeclared base, printing why;
#   -> else copies CTRL_<stem>_b<n>.rvt + the probes into experiments/acceptance/
#      and writes experiments/acceptance/batch_<n>.json (control first).
# upload every file listed in batch_<n>.json, CONTROL FIRST; then:
.venv/bin/python tools/probe_batch.py verdicts experiments/acceptance/batch_<n>.json \
    --verdict CTRL_..._b<n>.rvt=PASS --verdict <probe>=FAIL ...
#   -> VOID_ROUND / INCOMPLETE / REFUSED_UNCERTIFIED_BASE / INTERPRETED,
#      per-file readings, and paste-ready 'certified'/'failed' ledger snippets.
# certifying a NEW BASE (so future probes may build on it):
.venv/bin/python tools/probe_batch.py stage --candidate-base <base.rvt>
# dry-run / inspection / history:
.venv/bin/python tools/probe_batch.py check <files>      # gate only
.venv/bin/python tools/probe_batch.py resolve <files>    # base + ledger status
.venv/bin/python tools/probe_batch.py retro              # regenerate the audit table
```
The next K-round, concretely: `stage --candidate-base experiments/genesis/
triage/K1_step1_neutralised.rvt` (the pre-staged K1 split file) plus the
first rung of the ladder **rebased on the certified K4** — the gate will
admit the K4-rebased rung, refuse anything still declaring K1, and attach
the control.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **Every probe-building tool** (`tools/genesis_*`, `tools/latest_probes.py`,
  reduce ladder, famgen): emit `probes.json` entries with a `"base"` field =
  the FULL repo-relative path of the file the probe's one change was made
  to (not prose, not a symbol, not a bare name); the gate accepts the legacy
  forms only for backward compatibility.
* **Orchestrator / ledger owner:** (a) add explicit `certified` entries for
  the six `samples/*.rvt` (kind: sample source); (b) add XR_null to `failed`
  (verdict #15); (c) settle R4s/R0_identity with a `CTRL_R4s_b<n>` control;
  (d) record verdicts (or "never uploaded") for the 16 unread files in
  `experiments/acceptance/`; (e) enter future verdicts ONLY from a
  `read_batch_verdicts` interpretation.
* **KNOWLEDGE.md owner:** merge laws 1–5 above; strike the "no R-rung viewer
  pass" claim (genesis-status E5 / genesis-audit §B6) or annotate it as
  superseded by the ledger.
* **`tools/sync_plugin.py`:** this stream adds no `src/` module (a tool +
  tests + docs only) — no plugin-drift change.

## Verification

* `.venv/bin/python -m pytest tests/test_probe_batch.py -q` → **34 passed**
  (hermetic tmp-ledger gate/staging/verdict tests + the retro classification
  + resolution against the real corpus manifests + a real byte-identical
  control build).
* `.venv/bin/python tools/probe_batch.py retro` regenerates audit §3
  byte-for-byte-equivalent (46 rows; summary in the audit's totals line).
* Ledger consumers re-read the annotated `viewer-certified.json` unchanged in
  behaviour: `tools/coverage.py load_ledger` (33 entries), `rvt.census`,
  `probe_batch.Ledger` (33 certified / 34 failed).
* Full suite: see BRANCH STATE.

## Open questions (need the viewer / a decision)

* R4s / R0_identity — ledger says certified, campaign prose says never
  viewer-passed. A CTRL_R4s copy in the next round decides for one file's
  cost.
* Whether the reader's dedupe keys on filename or content — the CTRL_ naming
  assumes name; if content, a same-round re-upload of an identical file may
  be read from cache (the b<n> tag makes each round's control name unique;
  the bytes are necessarily identical to a certified file's — watch for a
  suspiciously instant control PASS and, if in doubt, alternate the control
  source among certified files).
* P4/P6 (UNGUARDED): re-run `P4_ids_null.rvt` in a properly controlled
  round to promote the live-registry-id rule from consistent-lead to fact.

## BRANCH STATE

* No VCS (plain directory). NEW files, this stream's territory only:
  `tools/probe_batch.py`, `tests/test_probe_batch.py`,
  `docs/writer/verdict-integrity-audit.md`, `docs/inbox/genesis-discipline.md`
  (this file). EDITED (annotate-only): `docs/coverage/viewer-certified.json`
  (added `integrity_audit` key + `cause_status` on all 34 `failed` entries;
  the 33 `certified` entries untouched). APPENDED: one section (`## VERDICT
  INTEGRITY LEDGER`) to `docs/inbox/genesis-audit.md`. NO existing `src/`
  module, tool, test or `.rvt` touched; no browser / viewer use.
* DONE per charter: the gate tool (base-certification refusal + auto
  certified control + staging manifest + `read_batch_verdicts`), its tests,
  and the integrity audit classifying every recorded verdict.
* Full suite this session (`.venv/bin/python -m pytest tests/ -q
  --ignore=tests/oracle`): **923 passed, 2 failed** (925 tests, 969.7 s).
  This stream's 34 tests are among the 923. The 2 failures are the
  pre-existing, other-stream stale assertions every recent record lists —
  `tests/test_provenance.py::test_G0_resource_refs_are_counted` and
  `::test_G0_identity_dit_usernames_still_leak` (they pin the pre-genesis-2
  G0 leaks that the rebuilt G0 no longer has; owner: the provenance
  stream). The previously-recorded `test_plugin_sync` failure is no longer
  present. Neither failure touches this stream's files.
* STOPPED AT READY — the gate is live for the orchestrator's next batch;
  the audit is the honest evidence map for planning genesis-7.
