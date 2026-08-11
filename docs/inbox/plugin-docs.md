# plugin-docs -- the shipped plugin's prose (commands, SKILL.md caveats, README/docs) kept true to the engine and the ledger

Charter: whenever the engine's honest status moves (a route retired, a gate cleared, a caveat
falsified), the text a stranger reads inside `plugin/` and `docs/product/` moves with it -- never
claiming more than `tools/route.py matrix` + `docs/coverage/viewer-certified.json`, never less
than what ships. Index + fragments per `docs/inbox/README.md`; one fragment per PR below.

- `plugin-docs.d/511-donor-free-docs.md` -- the shipped plugin text stops offering a family donor; matrix rows say donor-free with their evidence (#511)
- `plugin-docs.d/653-tekton-env-donor-line.md` -- the bootstrap code follows: readiness line and doctor stop reporting `$RVT_FAMILY_DONOR`; preflight JSON loses `family_donor` (#653)
