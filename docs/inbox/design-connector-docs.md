# inbox — design-connector-docs (2026-08-03)

Notes from writing plugin/docs/ (playbooks, job templates, HONEST-STATUS).

For the packager agent:
- plugin/docs/ references three slash commands `/revit-validate`,
  `/revit-harden`, `/revit-job` as thin wrappers over
  `skills/revit-bridge/scripts/{validate_ifc,harden_ifc,report}.py` and the
  JOB-TEMPLATES. Docs state the equivalent script line if the command isn't
  installed. Please wire the commands to exactly those scripts.
- Docs reference an `rvt-native` skill for `.rvt` audit/edit (read-only
  audit today, via `rvt.mutate.Document`). If it ships under another name,
  update PLAYBOOK-cowork-and-chat.md Job B + model-audit template.

Gaps / propose:
- `report.py` expects `validation_json` (+ `--compare harden.json`); SKILL.md
  §5.4 shows `report.py out/hardened.ifc --before ... -o ...` (older
  signature). Docs use the current `report.py` CLI (checked with --help).
  SKILL.md should be reconciled.
- Cowork wheel pre-staging (TRACKER F8) is the one un-tested link in the
  chat path; playbooks tell users to report a `pip` failure, never fake a
  score. Suggest packager bundles `wheels/` (ifcopenshell 0.8.5 manylinux +
  numpy) proactively.
- Electrical unit conversion for `.rvt` audit: Revit stores V/VA/W in
  internal ft-based units; SI = internal / 10.7639104 (208 V verified from
  m_dVoltage 2238.89 on rme sample). Worth a helper in the engine
  (e.g. `rvt.units.volts()`), currently inlined in the audit template.
- Open (blocks .rvt promises): brothers' Revit version still unconfirmed.
