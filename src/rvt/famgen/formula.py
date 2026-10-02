"""formula -- a family parameter FORMULA as the expression tree Revit stores (#850).

WHERE A FORMULA LIVES.  Revit does not store formula text.  Each ``FamilyParamValue``
entry (the self-Family's ``m_familyParams`` AND every ``FamilyTypeTable`` row) carries
``m_oExpression``: a pointer to a parsed tree of the schema's ``Expression`` classes,
with the evaluated result in the entry's ``m_value`` / ``m_int``.  Every type row
repeats the same tree (2,052 / 2,052 formula entries in the owner's 421-family
reference pack); the ``ParamElemFamily`` carries no formula flag; and the family's
``FamDimConstrMgr.m_paramExprs`` is the linear dimension-constraint table, not the
formulas (39 of the sampled families have formulas and no ``m_paramExprs``).
"No formula" is a null pointer (or an empty ``StringConstantExpression``).

THE NODE CODES are pinned NUMERICALLY, never guessed: every formula entry of every type
row in the reference pack (24,320 evaluations) was re-evaluated under candidate
meanings and compared with the value Revit stored for that type (issue #850 has the
table).  Only pinned codes are emitted; a formula needing an unpinned one ('^', a
size_lookup, 'sqrt' ...) is REFUSED with the reason, never approximated.

UNITS follow Revit's own rule, read from the same pack: a literal written with a unit
('1\\'', '300 mm', '6"') is a LENGTH constant (``m_value`` in feet, the internal unit);
a bare literal is a NUMBER; '+', '-' and the comparisons need the same spec on both
sides, and '*' / '/' by a number keep the other side's spec -- so 'Width + 1' is
refused exactly as Revit's formula editor refuses "inconsistent units".

TEXT (#870) is a value, never an operand: a ``"quoted"`` literal is a
``StringConstantExpression`` holding only ``m_value`` (no spec), a text parameter
may be named, and ``if()`` may choose between texts -- the shapes the owner's
reference library uses (4,002 text formulas: 3,278 bare constants, the rest
``if()`` chains over Yes/No conditions; every result stored in the row's
``m_str`` with ``m_value`` 0.0, ``m_int`` 0, ``m_elemId`` -1).  No operator
takes text ('+' joining, '=' comparing): none is pinned, so each is refused.

This module is FORMAT, not content: the node classes and field names are our own
Revit-2026 ``Formats/Latest`` schema's; no value, name or tree from a reference
family is carried (hard rule 3).
"""
from __future__ import annotations

import functools
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

SPEC_LENGTH = "autodesk.spec.aec:length-1.0.0"
SPEC_NUMBER = "autodesk.spec.aec:number-1.0.0"
SPEC_YESNO = "autodesk.spec:spec.bool-1.0.0"
SPEC_ANGLE = "autodesk.spec.aec:angle-1.0.0"
SPEC_TEXT = "autodesk.spec:spec.string-1.0.0"
#: deepest tree the writer emits: far beyond a formula anyone writes by hand, and well
#: inside Python's own recursion limit, so no formula string can crash a build (hard
#: rule 1); deeper is refused with the reason
MAX_DEPTH = 60

#: ``BinaryOperatorExpression.m_binaryOperator`` -- pinned (#850; the independent
#: re-verification's single-code counts, Integer results read rounded from m_int):
#: 1 '+' 842/842, 2 '-' 901/901, 3 '*' 603/603, 4 '/' 942/942, 6 '=' 722/722,
#: 7 '>' 476/476, 8 '<' 1,022/1,022.  Code 5 is NOT pinned (8 uses, none evaluable).
BINARY_OP = {"+": 1, "-": 2, "*": 3, "/": 4, "=": 6, ">": 7, "<": 8}
#: ``UnaryOperatorExpression.m_unaryOperator`` 1 = negation
UNARY_NEG = 1
#: ``FunctionExpression.m_function`` -- pinned (#850): 10 if (3 args), 12 and / 11 or
#: (variadic, 6,955/6,955), 13 not, 18 round (88/88), 3 tan (30/30).
FUNCTION = {"if": 10, "and": 12, "or": 11, "not": 13, "round": 18, "tan": 3}
_ARITY = {"if": (3, 3), "and": (2, 64), "or": (2, 64), "not": (1, 1), "round": (1, 1),
          "tan": (1, 1)}
#: known functions whose codes are NOT pinned yet -- refused by name
_UNPINNED = {"sin", "cos", "asin", "acos", "atan", "exp", "ln", "log", "sqrt", "abs",
             "roundup", "rounddown", "size_lookup", "pi"}

#: length units a literal may carry -> feet (Revit's internal length unit)
_UNIT_FT = {"mm": 1 / 304.8, "cm": 10 / 304.8, "m": 1000 / 304.8, "in": 1 / 12, '"': 1 / 12,
            "ft": 1.0, "'": 1.0}


class FormulaError(ValueError):
    """The formula cannot be represented faithfully (syntax, units, unpinned code)."""


def _ptr(cls: str, value: dict) -> dict:
    return {"ptr_class": cls, "pid": -1, "value": value}


@dataclass(frozen=True)
class ParamRef:
    """A parameter a formula may name: its element id and spec."""
    param_id: int
    spec: str


_NUMBER = re.compile(r"\s*(?P<num>\d+(?:\.\d*)?|\.\d+)\s*"
                     r"(?P<unit>mm|cm|m(?![A-Za-z])|in(?![A-Za-z])|ft|'|\")?")
_CALL = re.compile(r"([A-Za-z_]+)\s*\(")
#: specs a formula may NOT read or produce: integer, material and other storage kinds
#: (their stored form -- a rounded m_int, an element id -- is not what this writer
#: emits).  Measurable doubles, Yes/No and text (#870) are read and produced.
_UNSUPPORTED = ("autodesk.spec:spec.int64", "tekton.storage:")


def is_text(spec: str) -> bool:
    """True for a text spec (any version)."""
    return str(spec).startswith("autodesk.spec:spec.string")


class NameTable:
    """The parameter names a formula may use, indexed ONCE per family: by first
    character, then by LENGTH, longest first (names may hold spaces; the longest
    match wins).  A lookup tests one slice per distinct name length -- never every
    name sharing a first letter, which made a family of thousands of ``P…``
    parameters quadratic (measured: a 4x longer chain cost 11.5x) -- so a family
    with thousands of parameters parses each formula in time independent of how
    many there are."""

    def __init__(self, params: Mapping[str, ParamRef]):
        self.params = dict(params)
        grouped: Dict[str, Dict[int, set]] = {}
        for name in self.params:
            if name:
                grouped.setdefault(name[0], {}).setdefault(len(name), set()).add(name)
        self.by_first: Dict[str, List[Tuple[int, set]]] = {
            c: sorted(by_len.items(), reverse=True) for c, by_len in grouped.items()}


class _Parser:
    def __init__(self, text: str, table: NameTable):
        self.text = text
        self.params = table.params
        self.table = table
        self.pos = 0

    # --- lexing -----------------------------------------------------------
    def _skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _peek(self) -> Optional[str]:
        self._skip()
        if self.pos >= len(self.text):
            return None
        for op in ("<>", "<=", ">="):
            if self.text.startswith(op, self.pos):
                return op
        return self.text[self.pos]

    def _eat(self, s: str) -> None:
        self._skip()
        if not self.text.startswith(s, self.pos):
            raise FormulaError(f"expected {s!r} at column {self.pos + 1} of {self.text!r}")
        self.pos += len(s)

    # --- grammar: comparison < additive < multiplicative < unary < primary --
    def parse(self) -> Tuple[dict, str]:
        node = self._comparison()
        self._skip()
        if self.pos != len(self.text):
            raise FormulaError(f"unexpected {self.text[self.pos:]!r} in {self.text!r}")
        return node

    def _comparison(self) -> Tuple[dict, str]:
        left = self._additive()
        op = self._peek()
        if op in ("<>", "<=", ">="):
            raise FormulaError(f"operator {op!r} has no pinned code (#850)")
        if op in ("=", "<", ">"):
            self._eat(op)
            right = self._additive()
            _no_text(op, left, right)
            _no_yesno(op, left, right)
            _same_spec(left, right, op)
            return _binary(op, left, right), SPEC_YESNO
        return left

    def _additive(self) -> Tuple[dict, str]:
        node = self._multiplicative()
        while self._peek() in ("+", "-"):
            op = self._peek(); self._eat(op)
            right = self._multiplicative()
            _no_text(op, node, right)
            _no_yesno(op, node, right)
            _same_spec(node, right, op)
            node = (_binary(op, node, right), node[1])
        return node

    def _multiplicative(self) -> Tuple[dict, str]:
        node = self._unary()
        while self._peek() in ("*", "/", "^"):
            op = self._peek()
            if op == "^":
                raise FormulaError("operator '^' has no pinned code (#850)")
            self._eat(op)
            right = self._unary()
            _no_text(op, node, right)
            _no_yesno(op, node, right)
            node = (_binary(op, node, right), _product_spec(node[1], right[1], op))
        return node

    def _unary(self) -> Tuple[dict, str]:
        if self._peek() == "-":
            self._eat("-")
            inner = self._unary()
            _no_text("-", inner)
            if inner[1] == SPEC_YESNO:
                raise FormulaError("cannot negate a Yes/No value (use not(...))")
            return _ptr("UnaryOperatorExpression", {"m_unaryOperator": UNARY_NEG,
                                                     "m_pSubexpression": inner[0]}), inner[1]
        return self._primary()

    def _primary(self) -> Tuple[dict, str]:
        self._skip()
        if self._peek() == "(":
            self._eat("(")
            inner = self._comparison()
            self._eat(")")
            return _ptr("ParenExpression", {"m_pSubexpression": inner[0]}), inner[1]
        if self.pos >= len(self.text):
            raise FormulaError(f"formula ends where a value is expected: {self.text!r}")
        if self.text[self.pos] == '"':
            end = self.text.find('"', self.pos + 1)
            if end < 0:
                raise FormulaError(f"text constant at column {self.pos + 1} of {self.text!r} "
                                   f"has no closing quote")
            value = self.text[self.pos + 1:end]
            self.pos = end + 1
            return _ptr("StringConstantExpression", {"m_value": value}), SPEC_TEXT
        if self.text[self.pos] in "+*/^=<>),":
            raise FormulaError(f"a value is expected at column {self.pos + 1} of {self.text!r}, "
                               f"not {self.text[self.pos]!r}")
        m = _NUMBER.match(self.text, self.pos)
        if m:
            self.pos = m.end()
            val = float(m.group("num"))
            if not math.isfinite(val):
                raise FormulaError(f"constant {m.group('num')[:20]}... is too large to store")
            unit = (m.group("unit") or "").lower()
            if unit:
                return _number(val * _UNIT_FT[unit], SPEC_LENGTH), SPEC_LENGTH
            return _number(val, SPEC_NUMBER), SPEC_NUMBER
        # a function CALL first (a name followed by '(' -- a parameter named like a
        # function never shadows it), then a parameter name: exact case, as Revit
        # matches, longest known name first (names may hold spaces)
        fm = _CALL.match(self.text, self.pos)
        if fm and fm.group(1).lower() in set(FUNCTION) | _UNPINNED:
            return self._call(fm)
        for length, names in self.table.by_first.get(self.text[self.pos], ()):
            end = self.pos + length
            name = self.text[self.pos:end]
            if name in names and not \
                    (end < len(self.text) and (self.text[end].isalnum() or self.text[end] == "_")):
                self.pos = end
                ref = self.params[name]
                if ref.spec.startswith(_UNSUPPORTED):
                    raise FormulaError(f"parameter {name!r} is {_short(ref.spec)}: only measurable, "
                                       f"Yes/No and text parameters are supported in formulas")
                return _ptr("ParameterExpression", {"m_paramId": int(ref.param_id)}), ref.spec
        if fm:
            return self._call(fm)
        word = re.compile(r"[A-Za-z_][\w .\-]*").match(self.text, self.pos)
        raise FormulaError(f"unknown name {word.group(0).strip() if word else self.text[self.pos:]!r}"
                           f" in {self.text!r}")

    def _call(self, fm: "re.Match") -> Tuple[dict, str]:
        fname = fm.group(1).lower()
        if fname in _UNPINNED:
            raise FormulaError(f"function {fname!r} has no pinned code (#850)")
        if fname not in FUNCTION:
            raise FormulaError(f"unknown function {fname!r}")
        self.pos = fm.end()
        args: List[Tuple[dict, str]] = []
        if self._peek() != ")":
            args.append(self._comparison())
            while self._peek() == ",":
                self._eat(",")
                args.append(self._comparison())
        self._eat(")")
        lo, hi = _ARITY[fname]
        if not lo <= len(args) <= hi:
            raise FormulaError(f"{fname}() takes {lo}..{hi} arguments, got {len(args)}")
        spec = _function_spec(fname, args)
        return _ptr("FunctionExpression", {"m_function": FUNCTION[fname],
                                           "m_subexpressions": [a[0] for a in args]}), spec


def _number(value: float, spec: str) -> dict:
    return _ptr("NumberConstantExpression", {"m_value": float(value),
                                             "m_specTypeId": {"m_typeId": spec}})


def _binary(op: str, left: Tuple[dict, str], right: Tuple[dict, str]) -> dict:
    return _ptr("BinaryOperatorExpression", {"m_binaryOperator": BINARY_OP[op],
                                             "m_pLeftSubexpression": left[0],
                                             "m_pRightSubexpression": right[0]})


def _no_yesno(op: str, *operands: Tuple[dict, str]) -> None:
    """Yes/No is never a number: no arithmetic, ordering or '=' on it (use and / or /
    not / if) -- Revit's editor never writes such a tree."""
    if any(o[1] == SPEC_YESNO for o in operands):
        raise FormulaError(f"a Yes/No value cannot take {op!r} (use and / or / not / if)")


def _no_text(op: str, *operands: Tuple[dict, str]) -> None:
    """Text is a value only: no operator takes it -- joining ('+') and comparing ('=')
    text have no pinned code, so neither is guessed (#870)."""
    if any(is_text(o[1]) for o in operands):
        raise FormulaError(f"a text value cannot take {op!r} (text can only be a value or an "
                           f"if() result)")


def _same_spec(a: Tuple[dict, str], b: Tuple[dict, str], op: str) -> None:
    if is_text(a[1]) != is_text(b[1]):
        raise FormulaError(f"{op} mixes text and {_short(b[1] if is_text(a[1]) else a[1])}: "
                           f"both sides must be text")
    if a[1] != b[1]:
        raise FormulaError(f"inconsistent units: {_short(a[1])} {op} {_short(b[1])} "
                           f"(write the constant with its unit, e.g. 1' or 300 mm)")


def _product_spec(a: str, b: str, op: str) -> str:
    if b == SPEC_NUMBER:
        return a
    if a == SPEC_NUMBER and op == "*":
        return b
    if op == "/" and a == b:
        return SPEC_NUMBER
    raise FormulaError(f"unsupported units: {_short(a)} {op} {_short(b)}")


def _function_spec(fname: str, args: List[Tuple[dict, str]]) -> str:
    if fname == "if":
        if args[0][1] != SPEC_YESNO:
            raise FormulaError(f"if() condition must be Yes/No, not {_short(args[0][1])}")
        _same_spec(args[1], args[2], "if(...)")
        return args[1][1]
    if fname in ("and", "or", "not"):
        bad = [_short(a[1]) for a in args if a[1] != SPEC_YESNO]
        if bad:
            raise FormulaError(f"{fname}() takes Yes/No arguments, not {', '.join(bad)}")
        return SPEC_YESNO
    if args[0][1] == SPEC_YESNO or is_text(args[0][1]):
        raise FormulaError(f"{fname}() takes a measurable value, not {_short(args[0][1])}")
    if fname == "round":
        # pinned on NUMBERS only (88/88): rounding a length would round its internal
        # feet, and negative halves are unpinned -- refused until pinned
        if args[0][1] != SPEC_NUMBER:
            raise FormulaError(f"round() takes a number, not {_short(args[0][1])}")
        return args[0][1]
    if args[0][1] not in (SPEC_NUMBER, SPEC_ANGLE):       # tan
        raise FormulaError(f"tan() takes an angle or a number, not {_short(args[0][1])}")
    return SPEC_NUMBER


def _short(spec: str) -> str:
    return spec.split(":")[-1].split("-")[0]


def parse_formula(text: str, params: "Mapping[str, ParamRef] | NameTable") -> Tuple[dict, str]:
    """``text`` -> (the ``m_oExpression`` tree, its result spec).  ``params`` maps each
    parameter name the formula may use to its :class:`ParamRef` (or is a prebuilt
    :class:`NameTable`, for many formulas of one family).  Raises
    :class:`FormulaError` for anything that cannot be stored faithfully."""
    if not str(text).strip():
        raise FormulaError("empty formula")
    table = params if isinstance(params, NameTable) else NameTable(params)
    try:
        tree, spec = _Parser(str(text), table).parse()
    except RecursionError:
        raise FormulaError(f"formula has more than {MAX_DEPTH} levels or terms") from None
    if _depth(tree) > MAX_DEPTH:
        raise FormulaError(f"formula has more than {MAX_DEPTH} levels or terms")
    inner = tree
    while isinstance(inner, dict) and inner.get("ptr_class") == "ParenExpression":
        inner = (inner.get("value") or {}).get("m_pSubexpression")
    if is_no_formula(inner):
        # bracketed or not: a formula whose whole value is "" is Revit's NO formula
        raise FormulaError('an empty text formula ("") is how Revit stores NO formula: '
                           'leave the value blank instead')
    return tree, spec


def _depth(tree: Any) -> int:
    """Nesting depth of a tree, iteratively (never recursion-limited)."""
    best, stack = 0, [(tree, 1)]
    while stack:
        n, d = stack.pop()
        if isinstance(n, dict):
            if "ptr_class" in n:
                best = max(best, d)
                d += 1
            stack.extend((x, d) for x in n.values())
        elif isinstance(n, list):
            stack.extend((x, d) for x in n)
    return best


_BIN_EVAL: Dict[int, Callable[[Any, Any], Any]] = {
    1: lambda a, b: a + b, 2: lambda a, b: a - b, 3: lambda a, b: a * b,
    4: lambda a, b: a / b, 6: lambda a, b: abs(a - b) < 1e-9,
    7: lambda a, b: a > b, 8: lambda a, b: a < b}


def evaluate(tree: dict, values: Mapping[int, Any]) -> Any:
    """The value Revit computes for ``tree`` given parameter ``values`` (by param id,
    internal units; Yes/No as 0/1).  Comparisons and and/or/not give bools."""
    c = tree.get("ptr_class"); v = tree.get("value") or {}
    if c == "NumberConstantExpression":
        return float(v["m_value"])
    if c == "StringConstantExpression":
        return str(v.get("m_value") or "")
    if c == "ParameterExpression":
        pid = int(v["m_paramId"])
        if pid not in values:
            raise FormulaError(f"no value for parameter id {pid}")
        return values[pid]
    if c == "ParenExpression":
        return evaluate(v["m_pSubexpression"], values)
    if c == "UnaryOperatorExpression":
        return -evaluate(v["m_pSubexpression"], values)
    if c == "BinaryOperatorExpression":
        return _BIN_EVAL[int(v["m_binaryOperator"])](evaluate(v["m_pLeftSubexpression"], values),
                                                     evaluate(v["m_pRightSubexpression"], values))
    if c == "FunctionExpression":
        f = int(v["m_function"]); subs = v["m_subexpressions"]
        if f == FUNCTION["if"]:
            return evaluate(subs[1] if evaluate(subs[0], values) else subs[2], values)
        if f == FUNCTION["and"]:
            return all(evaluate(s, values) for s in subs)
        if f == FUNCTION["or"]:
            return any(evaluate(s, values) for s in subs)
        if f == FUNCTION["not"]:
            return not evaluate(subs[0], values)
        if f == FUNCTION["round"]:
            x = evaluate(subs[0], values)
            if x < 0 and float(x + 0.5).is_integer():
                # only non-negative halves are pinned (half up); Revit rounds a
                # negative half away from zero -- refused until pinned, never guessed
                raise FormulaError(f"round() of a negative half ({x}) is not pinned")
            return float(math.floor(x + 0.5))
        if f == FUNCTION["tan"]:
            return math.tan(evaluate(subs[0], values))
    raise FormulaError(f"cannot evaluate node {c}")


_OP_TEXT = {v: k for k, v in BINARY_OP.items()}
_FN_TEXT = {v: k for k, v in FUNCTION.items()}


def _num_text(v: float) -> str:
    """A constant as the parser reads it back to the SAME float: the shortest
    round-trip digits (``repr``) in fixed-point, never an exponent -- a rounded
    spelling can flip a comparison against a value stored a few ulps away."""
    from decimal import Decimal
    t = format(Decimal(repr(abs(float(v)))), "f")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t or "0"


def is_spellable(name: str) -> bool:
    """True when a formula can name the parameter ``name`` (see :func:`_spellable`)."""
    return _spellable(str(name))


@functools.lru_cache(maxsize=4096)
def _spellable(name: str) -> bool:
    """True when the parser reads ``name`` back as that parameter: a caption that
    starts like a number ('3 Phase'), carries a quote, or begins with an operator is not
    -- such a formula is reported unread rather than spelled wrong."""
    try:
        tree, _ = parse_formula(name, {name: ParamRef(0, SPEC_NUMBER)})
    except (FormulaError, ValueError, KeyError, IndexError):
        return False
    return tree.get("ptr_class") == "ParameterExpression"


#: binding strength of each spelled node, as :class:`_Parser` reads it back:
#: comparison < additive < multiplicative < unary minus < atom
_P_CMP, _P_ADD, _P_MUL, _P_UNARY, _P_ATOM = 1, 2, 3, 4, 5
_OP_PREC = {"=": _P_CMP, ">": _P_CMP, "<": _P_CMP, "+": _P_ADD, "-": _P_ADD,
            "*": _P_MUL, "/": _P_MUL}


def is_no_formula(tree: Any) -> bool:
    """True when ``m_oExpression`` means "no formula": a null pointer or an empty
    ``StringConstantExpression`` (both are how Revit stores an absent formula)."""
    if not tree:
        return True
    return (isinstance(tree, dict) and tree.get("ptr_class") == "StringConstantExpression"
            and not ((tree.get("value") or {}).get("m_value")))


def unparse(tree: Any, names: Mapping[int, str]) -> Optional[str]:
    """The Revit formula text of a stored expression tree -- the inverse of
    :func:`parse_formula` for everything it pins: + - * / = > <, unary minus,
    parentheses, if / and / or / not / round / tan, parameter references by
    ``names`` (param id -> caption), number constants (a length in feet, written
    ``1.5'``), and string constants (``"..."``, written as text formulas since
    #870).  Anything else -- an unpinned operator
    or function, an angle constant, a parameter not in ``names`` -- gives None:
    never a guessed spelling.  Precedence is spelled from the TREE, not from any
    stored parentheses: an operand that binds more loosely than its operator is
    bracketed, so a Revit-born tree with no ``ParenExpression`` nodes reads back
    to the same tree's value."""
    try:
        got = _unparse(tree, names)
    except RecursionError:                            # a tree deeper than any written by hand
        return None
    return None if got is None else got[0]


def _subs(v: Mapping[str, Any]) -> Optional[list]:
    """A ``FunctionExpression``'s argument trees, however the record holds them."""
    subs = v.get("m_subexpressions") or []
    if isinstance(subs, dict):
        subs = subs.get("value") or subs.get("m_items") or []
    return subs if isinstance(subs, list) else None


def _constant_value(n: Any) -> Optional[float]:
    """The value of ``n`` when it is a number constant -- through parentheses and
    leading minus signs, so ``-(2)``, ``-2.0`` and a stored ``-2`` read alike --
    else None.  -0.0 is 0.0 (the two compute alike)."""
    sign = 1.0
    while isinstance(n, dict):
        cls, v = n.get("ptr_class"), n.get("value") or {}
        if cls == "ParenExpression":
            n = v.get("m_pSubexpression")
        elif cls == "UnaryOperatorExpression" and v.get("m_unaryOperator") == UNARY_NEG:
            sign, n = -sign, v.get("m_pSubexpression")
        elif cls == "NumberConstantExpression":
            try:
                return sign * float(v.get("m_value")) + 0.0
            except (TypeError, ValueError):
                return None
        else:
            return None
    return None


def _shape(tree: Any) -> list:
    """``tree`` as a preorder list of (class, operator / function / parameter /
    constant), parentheses skipped -- two trees with one shape compute alike.  A
    number constant compares by value (an int and a float, -0.0 and 0.0 alike), a
    negated constant as the negative number, a parameter by its integer id.  A
    constant's unit spec is not compared: ``unparse`` spells the unit (``2'`` vs ``2``)
    and the parser reads it back, so a spelling never changes a constant's unit."""
    out: list = []
    stack = [tree]
    while stack:
        n = stack.pop()
        if not isinstance(n, dict):
            out.append(("?", repr(n)))
            continue
        cls, v = n.get("ptr_class"), n.get("value") or {}
        num = _constant_value(n)
        if num is not None:
            out.append(("NumberConstantExpression", num))
        elif cls == "ParenExpression":
            stack.append(v.get("m_pSubexpression"))
        elif cls == "BinaryOperatorExpression":
            out.append((cls, v.get("m_binaryOperator")))
            stack += [v.get("m_pRightSubexpression"), v.get("m_pLeftSubexpression")]
        elif cls == "UnaryOperatorExpression":
            out.append((cls, v.get("m_unaryOperator")))
            stack.append(v.get("m_pSubexpression"))
        elif cls == "FunctionExpression":
            subs = _subs(v) or []
            out.append((cls, v.get("m_function"), len(subs)))
            stack += list(reversed(subs))
        elif cls == "ParameterExpression":
            try:
                out.append((cls, int(v.get("m_paramId"))))
            except (TypeError, ValueError):
                out.append((cls, repr(v.get("m_paramId"))))
        else:
            out.append((cls, repr(v.get("m_value"))))
    return out


def unparse_checked(tree: Any, names: Mapping[int, str], table: "NameTable") -> Optional[str]:
    """:func:`unparse`, and the text parsed back against the family's OWN names
    (``table``) must give the same tree -- a caption that holds another one plus an
    operator ('A - B' beside 'A' and 'B') would otherwise read back as a different
    parameter.  A text that cannot be parsed back cannot be checked here and is
    returned as is -- the parser refusing it (its unit rules, or a tree deeper than
    ``MAX_DEPTH``) or Python's recursion limit: the writer parses with the same parser
    and limits, so it refuses such a text rather than writing another tree.  None when
    the tree cannot be spelled at all, or reads back as a different one."""
    text = unparse(tree, names)
    if text is None:
        return None
    try:
        back, _spec = parse_formula(text, table)
    except (FormulaError, RecursionError):
        return text
    return text if _shape(back) == _shape(tree) else None


def _wrap(child: Tuple[str, int], need: int) -> str:
    text, prec = child
    return f"({text})" if prec < need else text


def _unparse(tree: Any, names: Mapping[int, str]) -> Optional[Tuple[str, int]]:
    if not isinstance(tree, dict):
        return None
    cls, v = tree.get("ptr_class"), tree.get("value") or {}
    try:
        if cls == "ParameterExpression":
            name = names.get(int(v.get("m_paramId")))
            return None if name is None or not _spellable(name) else (name, _P_ATOM)
        if cls == "NumberConstantExpression":
            val = v.get("m_value")
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                return None
            spec = str(((v.get("m_specTypeId") or {}).get("m_typeId")) or "")
            if spec.startswith("autodesk.spec.aec:length"):
                body = _num_text(val) + "'"
            elif spec.startswith("autodesk.spec.aec:number") or not spec:
                body = _num_text(val)
            else:
                return None                                   # angle / other units: not pinned
            return (f"(-{body})" if val < 0 else body), _P_ATOM
        if cls == "StringConstantExpression":
            text = v.get("m_value")
            return None if not isinstance(text, str) or '"' in text else (f'"{text}"', _P_ATOM)
        if cls == "ParenExpression":
            inner = _unparse(v.get("m_pSubexpression"), names)
            return None if inner is None else (f"({inner[0]})", _P_ATOM)
        if cls == "UnaryOperatorExpression":
            if v.get("m_unaryOperator") != UNARY_NEG:
                return None
            inner = _unparse(v.get("m_pSubexpression"), names)
            return None if inner is None else (f"-{_wrap(inner, _P_UNARY)}", _P_UNARY)
        if cls == "BinaryOperatorExpression":
            op = _OP_TEXT.get(v.get("m_binaryOperator"))
            left = _unparse(v.get("m_pLeftSubexpression"), names)
            right = _unparse(v.get("m_pRightSubexpression"), names)
            if None in (op, left, right):
                return None
            p = _OP_PREC[op]
            # left-associative: an equal-precedence RIGHT operand is bracketed
            # ('A - (B - C)'); comparisons do not chain, so both sides need more
            lneed = p + 1 if p == _P_CMP else p
            return f"{_wrap(left, lneed)} {op} {_wrap(right, p + 1)}", p
        if cls == "FunctionExpression":
            fn = _FN_TEXT.get(v.get("m_function"))
            subs = _subs(v)
            args = [_unparse(a, names) for a in subs] if subs is not None else [None]
            if fn is None or None in args:
                return None
            return f"{fn}({', '.join(a[0] for a in args)})", _P_ATOM
    except (TypeError, ValueError):
        return None
    return None


def referenced_params(tree: dict) -> List[int]:
    """Every parameter id a tree reads (for dependency order)."""
    out: List[int] = []
    stack: List[Any] = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, dict):
            if n.get("ptr_class") == "ParameterExpression":
                out.append(int(n["value"]["m_paramId"]))
            stack.extend(n.values())
        elif isinstance(n, list):
            stack.extend(n)
    return out
