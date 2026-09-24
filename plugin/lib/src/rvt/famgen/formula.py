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

This module is FORMAT, not content: the node classes and field names are our own
Revit-2026 ``Formats/Latest`` schema's; no value, name or tree from a reference
family is carried (hard rule 3).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

SPEC_LENGTH = "autodesk.spec.aec:length-1.0.0"
SPEC_NUMBER = "autodesk.spec.aec:number-1.0.0"
SPEC_YESNO = "autodesk.spec:spec.bool-1.0.0"

#: ``BinaryOperatorExpression.m_binaryOperator`` -- pinned (#850): 1 '+' 842/842,
#: 2 '-' 901/901, 3 '*' 603/603, 4 '/' 938/942, 6 '=' 722/722, 7 '>' 476/476,
#: 8 '<' 1,445/1,445.  Code 5 is NOT pinned (8 uses, none evaluable).
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


_TOKEN = re.compile(r"\s*(?:(?P<num>\d+(?:\.\d*)?|\.\d+)\s*(?P<unit>mm|cm|m(?![a-z])|in(?![a-z])|ft|'|\")?"
                    r"|(?P<op><>|<=|>=|[-+*/^=<>(),])"
                    r"|(?P<word>[A-Za-z_][A-Za-z0-9_ .\-]*))", re.I)


class _Parser:
    def __init__(self, text: str, params: Mapping[str, ParamRef]):
        self.text = text
        self.params = {k: v for k, v in params.items()}
        self.names = sorted(self.params, key=len, reverse=True)   # longest match first
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
        if op in ("<>", "<=", ">=", "^"):
            raise FormulaError(f"operator {op!r} has no pinned code (#850)")
        if op in ("=", "<", ">"):
            self._eat(op)
            right = self._additive()
            _same_spec(left, right, op)
            return _binary(op, left, right), SPEC_YESNO
        return left

    def _additive(self) -> Tuple[dict, str]:
        node = self._multiplicative()
        while self._peek() in ("+", "-"):
            op = self._peek(); self._eat(op)
            right = self._multiplicative()
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
            node = (_binary(op, node, right), _product_spec(node[1], right[1], op))
        return node

    def _unary(self) -> Tuple[dict, str]:
        if self._peek() == "-":
            self._eat("-")
            inner = self._unary()
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
        m = _TOKEN.match(self.text, self.pos)
        if m and m.group("num") is not None:
            self.pos = m.end()
            val = float(m.group("num"))
            unit = (m.group("unit") or "").lower()
            if unit:
                return _number(val * _UNIT_FT[unit], SPEC_LENGTH), SPEC_LENGTH
            return _number(val, SPEC_NUMBER), SPEC_NUMBER
        # a parameter name (longest known name wins: names may hold spaces) or a function
        for name in self.names:
            end = self.pos + len(name)
            if self.text[self.pos:end].lower() == name.lower() and not \
                    (end < len(self.text) and (self.text[end].isalnum() or self.text[end] == "_")):
                self.pos = end
                ref = self.params[name]
                return _ptr("ParameterExpression", {"m_paramId": int(ref.param_id)}), ref.spec
        fm = re.compile(r"([A-Za-z_]+)\s*\(").match(self.text, self.pos)
        if fm:
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
        word = re.compile(r"[A-Za-z_][\w .\-]*").match(self.text, self.pos)
        raise FormulaError(f"unknown name {word.group(0).strip() if word else self.text[self.pos:]!r}"
                           f" in {self.text!r}")


def _number(value: float, spec: str) -> dict:
    return _ptr("NumberConstantExpression", {"m_value": float(value),
                                             "m_specTypeId": {"m_typeId": spec}})


def _binary(op: str, left: Tuple[dict, str], right: Tuple[dict, str]) -> dict:
    return _ptr("BinaryOperatorExpression", {"m_binaryOperator": BINARY_OP[op],
                                             "m_pLeftSubexpression": left[0],
                                             "m_pRightSubexpression": right[0]})


def _same_spec(a: Tuple[dict, str], b: Tuple[dict, str], op: str) -> None:
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
        _same_spec(args[1], args[2], "if(...)")
        return args[1][1]
    if fname in ("and", "or", "not"):
        return SPEC_YESNO
    if fname == "round":
        return args[0][1]
    return SPEC_NUMBER                                    # tan


def _short(spec: str) -> str:
    return spec.split(":")[-1].split("-")[0]


def parse_formula(text: str, params: Mapping[str, ParamRef]) -> Tuple[dict, str]:
    """``text`` -> (the ``m_oExpression`` tree, its result spec).  ``params`` maps each
    parameter name the formula may use to its :class:`ParamRef`.  Raises
    :class:`FormulaError` for anything that cannot be stored faithfully."""
    if not str(text).strip():
        raise FormulaError("empty formula")
    return _Parser(str(text), params).parse()


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
            return float(math.floor(evaluate(subs[0], values) + 0.5))
        if f == FUNCTION["tan"]:
            return math.tan(evaluate(subs[0], values))
    raise FormulaError(f"cannot evaluate node {c}")


def referenced_params(tree: dict) -> List[int]:
    """Every parameter id a tree reads (for dependency order)."""
    out: List[int] = []

    def walk(n: Any) -> None:
        if isinstance(n, dict):
            if n.get("ptr_class") == "ParameterExpression":
                out.append(int(n["value"]["m_paramId"]))
            for x in n.values():
                walk(x)
        elif isinstance(n, list):
            for x in n:
                walk(x)
    walk(tree)
    return out
