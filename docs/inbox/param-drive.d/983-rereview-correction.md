# Correction to the #979 record after the #983 re-review

Stream: param-drive. Refs #979 #983. A separate fragment, because `979-pset-last.md` is PR #983's own and fragments have one writer (`docs/inbox/README.md`).


## Correction (2026-10-02)
As shipped (PR #983, merged as `a615735`): `tests/test_pset_last_979.py` holds **8**
tests, not 6 (the two #983-review tests added). Against base, "DRIVES lost" is **22**,
not 0 -- each one a contradiction base drove through: an attached
`IFCLABEL('inf'|'-inf'|'Infinity'|'1e400')`, or `IFCREAL(1.E400)`, next to the length
(base's `abs(inf - x) <= 1e-9 * inf` matched any number). The `_same_value` fix closes
that base bug too. The independent re-review's 5,116-case probe: contradicting
statements drive 22 times at base, 0 at head; 12 drives gained, all the intended
label → length upgrades. BRANCH STATE: pushed and merged as #983.
