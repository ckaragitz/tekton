# interview — the question engine (#684)

Stream record. Issue #684 (steer S-2026-08-11-b, `docs/PROGRAM.md` O12), read
together with the steers that moved its emphasis before a line was written:
**#685 / #687 — the prompt is the interface.**

## What #684 asked for, and what #685 / #687 changed about it

#684 was filed while the interview still looked like *the* flow: *"if i ask for
a tansformer in a simple prompt, i need series of questions to get to the
specific detail that the family would be generated. even the vendor etc
everything and anything"*, derived from the registries rather than written per
product — *"this needs to be a universal database engine"*.

#685 and #687 then said the questions are the exception, not the interface:
*"lines of questions are just for use if the prompt is not descriptive enough"*
and *"if its broad ask questions"*. So the subject of this module is the
**residue** — what a prompt, read as far as it can be read, still leaves
undetermined — and a form-first design would have been the wrong answer.

That inversion is visible in the entry point and in the tests: `plan()` takes
the prompt FIRST and the answers second, there is no call that asks a question
the prompt already settled, and a descriptive prompt returns **zero** questions.

> Sources note: this session could not read issues #684 / #685 / #687 directly.
> The GitHub API is closed to it (`403 "GitHub access is not enabled for this
> session"` on every `/repos/ckaragitz/tekton/...` path; only `/user` and the
> git transport are served). #684's substance was recovered from the unmerged
> branch `cam/684-steering-row`, which carries the steering row S-2026-08-11-b
> and PROGRAM objective O12 verbatim; #685 / #687 from the owner's words as
> quoted in this session's charter. Anything in those issues that is not in the
> steering row or the quoted words has NOT been read. See *Not done* below.

## What was built

`src/rvt/famgen/interview.py` (new module, famgen territory — reads registries
and constructor signatures, writes no family, edits no writer path).

**The pluggable source list.** `SOURCES` is five rows loaded **by name at call
time** — never imported at module level, so a checkout without them costs
nothing:

| source | module | on this branch |
|---|---|---|
| `catalog` | `rvt.famgen.catalog` | present |
| `archetypes` | `rvt.famgen.archetypes` | **absent** (PR #674 unmerged) |
| `standards` | `rvt.famgen.standards` | present |
| `taxonomy` | `rvt.famgen.taxonomy` | **absent** (#692 in flight) |
| `vendors` | `rvt.famgen.vendors` | **absent** (#692 in flight) |

`source_status()` reports availability, every `Plan` and `Resolution` carries it,
and `tools/interview.py sources` prints it. Only `ImportError` is swallowed: a
source that exists and is *broken* must not be silently reported absent.

**Where each question comes from.** Nothing in the module knows what a
transformer is:

* **vendor / line** — the catalog's own vendors and lines, via the factory's own
  selector maps read by attribute name (`_XFMR_LINES`, `_PANEL_LINES`,
  `_LUM_KINDS`, `DEVICE_KINDS`), so the factory stays the single source of truth
  and a rename degrades to "no choices offered", never to a wrong list.
* **the identifying rating** — a ratings key with the same name as a constructor
  argument carries one value per variant (a transformer's `kva`).
* **published option lists** — `mains_ratings_available_a`, `mains_ratings_a`,
  `branch_pole_space_options` (the module's only key→key alias table, two rows).
* **everything else the constructor takes** — from `inspect.signature`, with the
  signature's own default as the question's default. Plumbing arguments
  (`start_id`, `solid`, `shared_params`, …) are never asked.
* **the schedule parameters** — `standards.authored_params(category)`, minus any
  the constructor already fills, matched by `standards.meaning_key` (#622's one
  meaning / one entry law). They rank last and default to **blank**.
* **archetypes** — one question per `Param`: its nominal as the default, its
  standard sizes as the choices, its `basis` as what the answer affects.

**Ordering.** Rank bands, most decisive first: kind (0) · vendor (10) · line
(20) · the identifying rating (30) · a dimension with published sizes (40) · any
other constructor argument (50) · a schedule parameter (60). Within a band, by
how many deliverable outcomes the answer eliminates. `Plan.enough` is true when
nothing at rank ≤ 30 is left — i.e. *which* product is settled and everything
open only refines it.

**Tiers fall out of who supplied the value**, not out of the key: `fact` (read
back from a catalog record) · `given` (the user answered, typed or picked) ·
`nominal` (nobody answered; an archetype nominal or the constructor's documented
default) · `blank` (nobody answered and nothing standard applies — an empty
standard parameter is the honest state).

**`tools/interview.py`** — `ask` / `describe` / `kinds` / `sources` / `build`.
`ask` exits 0 when the engine has enough, 2 when something decisive is open, 3
when there is no question set. It ships in the plugin bundle
(`AUTHOR_SCRIPTS`), so the skill flow is a flow the bundle can actually run.

**`plugin/skills/tekton-author/references/INTERVIEW.md`** — the conversational
flow: ask the engine what is missing, offer `choices` verbatim, ask a few at a
time in rank order, stop asking when `enough_to_build`, and say the assumptions
*after* the file.

## Evidence

Stream-local, `.venv/bin/python -m pytest`, this branch:

| gate | result |
|---|---|
| `tests/test_famgen_interview_684.py` | **65 passed, 2 skipped** (the 2 skips are the archetype-source tests: `rvt.famgen.archetypes` is not on `main`) |
| the same module on `main` + PR #674 merged (throwaway worktree) | **67 passed, 0 skipped** — both archetype tests run and pass |
| `tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py` | 32 passed |
| the whole CI shard (`tools/dev/shard_list.py --print`, 119 files) | **2519 passed, 130 skipped, 3 xfailed** in 481 s |
| `tools/sync_plugin.py --check` | in sync, deny-audit clean, identity scan == allowlist |
| `plugin/scripts/validate_plugin.py` | PASS — 25 assertions, 86 referenced paths resolve |
| `tools/dev/check_portable_paths.py` | ok: 3064 tracked paths portable |
| `interview.check_registry()` | `[]` |

Bare-surface run (unzipped `tekton-plugin.zip`, system `python3`, no repo on the
path — the product as a user meets it):

```
$ python3 skills/tekton-author/scripts/_bootstrap.py run interview.py ask "a transformer" -n 2
15 thing(s) the prompt leaves open for this transformer (these change which product gets built) …
$ python3 skills/tekton-author/scripts/_bootstrap.py run interview.py build "a transformer" -o out/bare
wrote out/bare.rfa
Building the transformer now. 4 answer(s) were ASSUMED, not given: vendor='eaton', kva=75, …
```

The derived question sets on this branch (sources: catalog + standards):

| kind | questions | decisive | filled without asking |
|---|---|---|---|
| transformer | 15 | 2 (`vendor`, `kva`) | 0 |
| panelboard | 17 | 0 | 2 (`vendor`, `line` — one deliverable each) |
| luminaire | 22 | 1 (`fixture`) | 0 |
| device | 16 | 1 (`device`) | 0 |

Prompt-first, measured:

| prompt | kind read | decisive left | read from the prompt |
|---|---|---|---|
| `a 75 kVA eaton transformer` | transformer | **0** | `kva=75`, `vendor=eaton` |
| `a transformer` | transformer | 2 | — |
| `a 30 kVA hps transformer` | transformer | **0** | `kva=30`, `vendor=hps` |
| `make me a duplex receptacle` | device | 0 | `device=duplex-receptacle` |
| `a 24 inch cable tray 20 ft long` (with #674) | cable_tray | **0** | `width_in=24`, `length_ft=20` |

## The three failure classes this was written against

Sibling PR #674 took six review rounds and twenty-six findings, all after CI was
green. The three classes were written into the suite before the code:

**(b) a question loop that withholds the file.** `resolve()` is total: it never
asks, never raises for an unanswered question, and returns a famspec the
contract accepts at any stage. Tested by answering the first *k* questions for
every *k* of every kind and validating each result; by writing a real `.rfa`
from a plan nobody answered; and by the contradiction case below.

**(c) offering a choice the engine cannot build.** Every catalog-derived choice
is probed through the kind's own facts resolver before it is offered — the probe
authors no geometry, so a whole choice list costs milliseconds. Eaton's 500 kVA
row is in the catalog, publishes no dimensions, and is never on the kVA list.
Nothing is dropped silently either: `Question.withheld` carries what a source
named and the engine cannot build **with the answers so far**, each with the
constructor's own refusal quoted.

**(a) text claiming behaviour the code does not have.** Absent sources are named
absent and no question ever carries an absent source. Every default that gets
used carries a basis. A question's sentence lists exactly the choices it offers
and never a withheld one. A kind with no question set says so plainly and
`resolve()` refuses to invent a famspec for it.

## Findings

1. **Answers can be individually deliverable and jointly impossible.** HPS
   publishes 30 and 75 kVA; `vendor=hps` and `kva=225` are each fine and
   together are a `FactoryError`. The first version crashed — a hard-rule-1
   hole found by the module's own CLI, not by a test. Now the **least decisive**
   answer yields (the vendor identifies the product, the rating refines it), the
   nearest deliverable value is used, and what was asked / why it could not be
   honoured / what was built instead ride on `Plan.conflicts` and are said
   *after* the file.
2. **Square D panelboards are catalogued but not buildable at the default
   voltage.** `resolve_panelboard_facts(vendor="square-d", …)` refuses at
   480Y/277 — *"NF: no circuits->height sizing table on record and no
   shared-family table to borrow"* — and succeeds at 240 V (56 combinations
   tried). So the vendor question is answer-sensitive: at the default it has one
   deliverable choice and is filled rather than asked (with Square D named on
   the fill's basis line); answer `voltage=240` first and Square D appears as a
   choice. This is worth an issue against the facts store, not against this
   module: the record holds facts the constructor cannot use.
3. **One measurement was answering eight questions.** Trialling the engine
   against the unmerged #674 branch showed a bare `"24 inch"` bound to every
   question whose key ends in `_in` — so a ladder tray came out 24 in wide, 24
   in deep, with 24 in rungs 24 in thick, and the report quoted three of the
   caller's words back at eight dimensions they never gave. Fixed twice over: a
   measurement is consumed when used, a number binds to a question only when one
   of *that* question's own words sits beside it, an unanchored measurement goes
   to the single most decisive question of its unit, and — the real fix — an
   archetype now reads its own prompt through
   `archetypes.resolve_prompt`, which already knows a tray's bare width. One
   reader per product family; running the generic one afterwards was what spent
   the same words twice.
4. **A measurement is one because of its key, not its default.** Requiring a
   numeric default made every *optional* dimension unreadable: a device's
   `mounting_height_in` defaults to `None` (the record's convention fills it), so
   `"at 18 in"` was dropped and then reported as an assumption — a quiet lie
   about what the user said.
5. **`kVA Rating` is not in the Electrical Equipment standards table.**
   `make_transformer` authors it itself. So `affects` honestly names the
   constructor argument there, and names the standard parameter (with its spec
   and group) only where the table really has one — `voltage` → `Voltage`,
   `cct` → `Initial Color Temperature`. A test pins both directions, because the
   first draft of that test asserted the parameter existed and was wrong.
6. **Three spellings of one record is not a question.** `_PANEL_LINES` maps
   `pow-r-line` / `prl` / `pow-r-line-panelboards` onto one catalog file;
   choices now collapse to one per deliverable outcome, while an answer given in
   any spelling still survives (membership of the offer list is not the test —
   deliverability is).
7. **A whole new *kind* still needs its constructor.** Adding a vendor, a line
   or a rating row grows its questions with no code change here, which is what
   *"universal database engine"* asks for. A new *category* cannot: an engine
   cannot offer to build what it has no constructor for.
   `unbuildable_categories()` reports any catalog category in that state (empty
   today) rather than pretending to interview for it.

## Not done / open questions

* **The issue text itself was never read** (API 403, above). If #684's DONE list
  or #685 / #687 carry a requirement that is not in steering row S-2026-08-11-b
  or in the owner's quoted words, it is not implemented. A reviewer with API
  access should diff the six DONE items against this record.
* **Not claimed, and not claimable from this session:** the issue is **not
  assigned** and carries **no 🔒 comment** from this session, and **no PR is
  open** — all three need the GitHub API. The branch is pushed; the head SHA is
  below. A tech-lead session must claim/assign and open the PR with
  `Closes #684`.
* **`taxonomy` / `vendors` (#692) contribute nothing yet** beyond being reported
  absent. The hooks are duck-typed and guarded (`kinds()` widens the kind list
  from `taxonomy.kinds()` when that callable exists), but they have never run
  against a real module — that is a claim about a shape, not about behaviour, and
  is written that way in the code.
* **`generic_model` and `downlight` have no question set.** `generic_model` is
  the standing example in the tests: its geometry is supplied by the caller, so
  no derived series of questions ends in a file. `downlight` needs the research
  corpus. Both are reported plainly.
* **No viewer round.** This module writes no bytes; the families it resolves to
  are the ones the factory already builds, so nothing new goes to Autodesk's
  reader. Hard rule 4 is untouched, and no certification is claimed.
* **`Plan.next()` is a plain head-of-list slice.** Whether the skill should ask
  strictly in rank order or group a vendor+line pair into one turn is a UX
  question worth a real session's judgement, not a code change here.

## Patch owed to a hot file (`plugin/skills/tekton-author/SKILL.md`)

`plugin/skills/*/SKILL.md` is a hot file (CLAUDE.md §4: an issue labelled
`hot-file`, a tiny dedicated PR, merged the same day), so this stream did not
edit it. The reference doc and the shipped script stand alone and work today;
the wiring below is what a `hot-file` PR should add. **Until it is applied, the
skill does not route broad prompts through the interview by itself** — this is
stated so nothing here claims otherwise.

In `## Step 1 — the job`, before the front-door command:

```markdown
**If the prompt is broad, ask the engine what is missing — do not guess and do
not open a questionnaire.** `python scripts/_bootstrap.py run interview.py ask
"<their words>" --json`: exit 0 = build now, 2 = something decisive is open (ask
its first few `choices` verbatim, a few at a time), 3 = no question set, say the
tool's own sentence. The user may stop at any point: `run interview.py build …`
delivers the file whether or not anything was answered, and its
`interview.assumed_answers` / `conflicts` are what you say *after* handing it
over. Detail: `references/INTERVIEW.md`.
```

In the `## Reference` table:

```markdown
| `scripts/interview.py` · `references/INTERVIEW.md` | the question engine (`ask` / `build`) · when to ask and what not to claim |
```

---

## BRANCH STATE

**Branch** `eng/684-interview`, cut from `main` at `e55bd9b`.
**Head at the time of writing:** see the PR / `git rev-parse HEAD` — the last
commit is the one adding this record.

**Files written**

| path | state |
|---|---|
| `src/rvt/famgen/interview.py` | new, 1634 lines — the engine |
| `tools/interview.py` | new, 221 lines — the CLI a skill session drives |
| `tests/test_famgen_interview_684.py` | new, 696 lines — 65 tests + 2 archetype-gated |
| `tests/ci_shard.d/684-interview.txt` | new drop-in (`tests/ci_shard.txt` untouched, #328) |
| `plugin/skills/tekton-author/references/INTERVIEW.md` | new, hand-authored |
| `tools/sync_plugin.py` | +6 lines: `interview.py` into `AUTHOR_SCRIPTS` |
| `docs/inbox/interview.md` | this record |
| `plugin/skills/tekton-author/scripts/interview.py`, `plugin/lib/src/rvt/famgen/interview.py`, `tekton-plugin.zip` | generated by `tools/sync_plugin.py` (zip is git-ignored) |

**Not touched:** `plugin/skills/*/SKILL.md` (hot — patch above),
`tests/ci_shard.txt`, `TRACKER.md`, `KNOWLEDGE.md`, `src/rvt/frontdoor/**`,
`src/rvt/famgen/factory.py`, any writer path.

**Gates run on this branch:** stream-local 65 passed / 2 skipped; full CI shard
2519 passed / 130 skipped / 3 xfailed (481 s); `sync_plugin.py --check` clean;
`validate_plugin.py` PASS; `check_portable_paths.py` ok (3064 paths); bare-unzip
`ask` and `build` both work under system Python.

**Staged, not shipped:** nothing. No viewer batch was reserved or staged — this
stream writes no new bytes for Autodesk's reader to judge.

**Blocked, needs a session with GitHub API access:** assign #684 + 🔒 comment;
open the PR ready with `Closes #684`. Everything else is done.
