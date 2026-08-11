# INTERVIEW — when a prompt is too broad to build from (issue #684)

**The prompt is the interface.** Most requests need no interview at all: read
the prompt, build, hand the file over. Questions exist for exactly one job —
what a descriptive prompt genuinely leaves undetermined. *"lines of questions
are just for use if the prompt is not descriptive enough"* / *"if its broad ask
questions"* (owner, steers #685 / #687).

So do not open with a questionnaire. Ask the engine what is actually missing.

```bash
python scripts/_bootstrap.py run interview.py ask "a transformer" --json
```

Exit code **0** = it has enough to build a specific product; **2** = something
decisive is still open; **3** = there is no question set for this (say the
tool's sentence, do not improvise one).

## The rule that outranks the interview

**Never withhold the file to finish the questions.** Hard rule 1 — the
deliverable always ships. The user may stop at any point, answer nothing, or
contradict themselves, and they still get a `.rfa`:

```bash
python scripts/_bootstrap.py run interview.py build "a transformer" -o out/x --json
```

That command works with zero answers. Its report's `interview.assumed_answers`
names every answer that was assumed rather than given, and `conflicts` names any
answer that could not be honoured with the rest (with what was built instead).
**Say those out loud after you hand over the file** — never instead of it, and
never as a reason to ask one more question first.

## Asking, if the engine says something decisive is open

`ask` returns the ordered residue, most decisive first: what to build, whose it
is, which line, then the rating that identifies the member, then dimensions,
then the parameters an engineer schedules it by. Ask **a few at a time** (the
`-n` flag, default 3), in the order given, in your own words — and offer the
`choices` verbatim, because they are the only values the engine can actually
deliver.

```bash
python scripts/_bootstrap.py run interview.py ask "a transformer" -a vendor=hps -n 3
```

Each question carries what you need to ask it well:

| field | what it is for |
|---|---|
| `ask` | the question, already worded |
| `choices` | the only values this engine can build — offer these, not a guess |
| `withheld` | values a registry holds that it cannot build **with the answers so far**, each with the engine's own reason. Mention one only if the user asks for it by name |
| `default` / `default_tier` / `default_basis` | what happens if they skip it, and why that value |
| `affects` | what the answer changes — a family parameter, or the geometry |
| `decisive` | `true` = it changes *which* product gets built |

When `enough_to_build` is `true`, stop asking and build. Everything still open
at that point only refines a product that is already decided; offering to build
now and refine later is almost always the better move.

## What you must not say

* Do not offer a value that is not in `choices`. A rating the catalog holds but
  publishes no dimensions for (Eaton's 500 kVA row) is deliberately absent.
* Do not present a `nominal` value as a manufacturer's figure. The tiers are
  `fact` (read from a catalog record), `given` (they said so), `nominal`
  (standard practice / the constructor's documented default) and `blank`
  (nobody supplied it — an empty standard parameter is the honest state).
  `interview.values.<key>.tier` says which, per value.
* Do not claim a source answered. `interview.sources` lists which registries
  were available on this build; some are only present once their PRs land.
* If `covered` is `false`, read the `note` as written. It says why there is no
  question set (a kind whose geometry the caller supplies has no series of
  questions that ends in a file) and what the engine *can* build.

## The whole question set of one kind, without asking anything

```bash
python scripts/_bootstrap.py run interview.py describe transformer --json
python scripts/_bootstrap.py run interview.py kinds        # what has question sets
python scripts/_bootstrap.py run interview.py sources      # which registries answered
```

## Where the questions come from

Nothing in the engine knows what a transformer *is*. The questions are derived:
the catalog supplies vendors, lines and the published rating rows; the archetype
registry supplies generated products with their nominals and standard sizes; the
category standards table supplies the parameters an engineer schedules by. A new
vendor, line or rating row grows its own questions with no code change — which
is why the choice lists are worth trusting and worth quoting exactly.
