"""rvt._clause -- how tekton says an error INSIDE a sentence.

Every door relays a failure as ONE sentence a skill session repeats verbatim
-- a status line, a refusal note, a tool's ``warning:`` -- naming the file,
the reason in words, and a layer's own error as a short clause: never a
traceback, never a byte dump, never an absolute upload path in front of the
reason (#559, #573, #574, #587).  The two rules that make such a sentence
live here, once, in a stdlib-only leaf, so the engine's read-side ladder
(``rvt.global_framing``), the front door (``rvt.frontdoor.release_ctx`` /
``manifest``) and the tools all say it the same way without importing one
another:

* :func:`clip` -- text as one line, whole when it fits a budget, else cut at
  a word boundary with ``...`` (the status sentence's rule);
* :func:`cause_clause` -- ``Type: message`` of an exception for use inside
  a sentence: the schema parser's trailing context dump dropped by shape,
  the words clipped to :data:`CAUSE_MAX`.  The exception itself is never
  touched -- callers keep it chained (``__cause__``) or listed whole next
  to the sentence, so nothing a layer said is lost.
"""
from __future__ import annotations

import re

__all__ = ["CAUSE_MAX", "clip", "cause_clause"]

#: a layer's error rides in a sentence as a clause of at most this many
#: characters of WORDS: room for the engine's longest worded one-sentence
#: error (the empty/truncated-schema ``ParseError``, 103 chars, #569); in
#: front of the reason anything longer pushes the reason out of a status cut
CAUSE_MAX = 120

#: the schema parser's trailing context dump, ``@0x603b: 14 1e .. | 3c 40 ..``
#: (``rvt.schema``'s ``_Parser.ctx``): bytes for a forensic log, noise in a
#: sentence -- dropped by shape so the words before it ride whole; a dump of
#: any other shape still meets the length cap
_CTX_DUMP = re.compile(r"\s*@0x[0-9a-f]+: [0-9a-f ]*\|[0-9a-f ]*$")


def clip(text: str, limit: int) -> str:
    """``text`` as one line (whitespace collapsed): whole when it fits
    ``limit``, else cut at the last word boundary that keeps at least a third
    of it (never mid-word unless one token is that long), trailing clause
    punctuation dropped, ``...`` marking the cut -- the result is <= ``limit``."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    keep = limit - len("...")
    cut = text.rfind(" ", 0, keep + 1)                # a boundary at or before `keep`
    return text[:cut if cut >= limit // 3 else keep].rstrip(" ,;:-(") + "..."


def cause_clause(e: BaseException) -> str:
    """``Type: message`` of ``e`` for a sentence -- the parser's context dump
    dropped, the words clipped to :data:`CAUSE_MAX`; the bare type name when
    there is no message."""
    text = clip(_CTX_DUMP.sub("", str(e)), CAUSE_MAX)
    return f"{type(e).__name__}: {text}" if text else type(e).__name__
