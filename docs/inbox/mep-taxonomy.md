# mep-taxonomy — the data tables that make one prompt resolve anything (#692, child of #685)

Charter: issue #692. Two tables, not code: an **MEP taxonomy** (kind → Revit category →
standard-parameter table → which lane can build it: catalog = `fact`, archetype = `nominal`,
none = say so) and a **vendor directory** (manufacturer → product lines → kinds → whether sourced
facts are held), both gated by `--check` so no claim outlives its evidence. The standing line
(steer #685 / S-2026-08-11-c): model knowledge may supply taxonomy, vendor and line *names* and
standard practice — never a manufacturer's dimensions as a `fact`; #688 (spec sheets) is how member
data legitimately arrives.

Fragments (one per PR, `docs/inbox/README.md`):

- `692-tables.md` — slice 1: `src/rvt/famgen/taxonomy.py` + `vendors.py`, the `make_family.py
  taxonomy|vendors` verbs, the `--check` gates (DONE 1, 2, 4 and the honest line of DONE 3 as an
  API); slice 2 (DONE 3/5: the prompt resolver and the #684 interview read the tables) follows.
- `692-wiring.md` — slice 2: the tables are what the prompt grammar and the family-plan resolver
  READ (DONE 3 relay + DONE 5): a phrase scanner over both tables, generic words (`refine`),
  makers carried as declared identity with the directory's one sentence, review nits 1-3 of #735.
- `739-maker-adjacency.md` — #739 (third review of #736): a maker that does not make the noun's
  kind rides it only when adjacent; a maker's name used as a place / client / existing gear names
  no maker; wider whole-job cues (hard vs soft); `Square D` and acronyms are real names; Price /
  Titus grilles; a cell naming two makers declares neither.
