"""rvt._quoted -- splitting edit text into clauses without cutting a quoted value.

Both edit doors read free text as clauses separated by ``;``, newlines and
``then`` (the family lane also by ``, set|rename``; the ``.rvt`` lane also by
``and then``).  A separator inside a quoted value is part of the value
(#1017: ``set Note = "a; b"``, #1019: ``mark DP-1 as "A; B"``).  The quote
rules live here, once, in a stdlib-only leaf, so the doors cannot drift:

* :func:`quoted_spans` -- the quote pairs that may hold a separator.  A pair
  opens at a word start onto a non-space (not ``;``/``,``); the NEXT copy of
  that quote must close it at a word end, not right after a digit (a unit
  mark, ``3'`` / ``5"``) or a space.  Any other quote is literal, so an
  apostrophe (``'90s``, ``Bob's``), a feet/inch mark, a glued ``"A"B`` or an
  unbalanced quote never pairs with a quote in a LATER clause and swallows it
  (PR #1018 review 1).
* :func:`split_clauses` -- split on a door's separators outside those spans.
  A span running across what reads as a further edit (the door's verbs) is
  refused, and each clause kept whole is reported in ``joined`` so the door
  refuses one its grammar cannot read instead of dropping it (PR #1018
  review 2): a refusal is recoverable, a swallowed edit is not.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Pattern, Set, Tuple

__all__ = ["quoted_spans", "split_clauses"]


def quoted_spans(s: str) -> List[Tuple[int, int]]:
    """(start, end) of each ``"..."`` / ``'...'`` pair that may hold a clause
    separator; every other quote is literal (see the module doc)."""
    spans: List[Tuple[int, int]] = []
    i = 0
    while i < len(s):
        q = s[i]
        if (q in "\"'" and (i == 0 or s[i - 1].isspace() or s[i - 1] in "=:,;(")
                and i + 1 < len(s) and not s[i + 1].isspace() and s[i + 1] not in ";,"):
            j = s.find(q, i + 1)
            if j > i and (j + 1 == len(s) or s[j + 1].isspace() or s[j + 1] in ".;,!?)") \
                    and not (s[j - 1].isdigit() or s[j - 1].isspace()):
                spans.append((i, j + 1))
                i = j + 1
                continue
        i += 1
    return spans


def split_clauses(s: str, sep: Pattern[str], further: Pattern[str],
                  refuse: Callable[[str], Exception],
                  joined: Optional[Set[str]] = None) -> List[str]:
    """Split ``s`` on ``sep`` outside :func:`quoted_spans`.  A span that runs
    across a separator followed by ``further`` (a door's edit verbs, matched
    at the text after the separator) raises ``refuse(message)``; each clause
    kept whole across a separator is added to ``joined``."""
    spans = quoted_spans(s)
    out: List[Tuple[str, bool]] = []
    start, kept = 0, False
    for m in sep.finditer(s):
        span = next(((a, b) for a, b in spans if a < m.start() < b), None)
        if span is None:
            out.append((s[start:m.start()], kept))
            start, kept = m.end(), False
            continue
        kept = True
        if further.match(s, m.end()):
            raise refuse(
                f"the quote in {s[span[0]:span[1]]} runs across a further edit: close the "
                "quote before the ';' / ',' / 'then' to make separate edits (to store that "
                "text itself, use a JSON op)")
    out.append((s[start:], kept))
    if joined is not None:
        joined.update(c.strip() for c, k in out if k)
    return [c.strip() for c, _ in out if c.strip()]
