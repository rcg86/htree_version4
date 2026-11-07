"""-if expression parser, e.g. {.name == IA && .pitch_x > 0.2}.

Grammar (lowest to highest precedence):
    or   := and ('||' and)*
    and  := not ('&&' not)*
    not  := '!' not | atom
    atom := '(' or ')' | operand [cmp operand]
    cmp  := == != < > <= >=
Operands are attributes (.name) or literals (bare words or "quoted strings").
== and != glob-match when the right side has * ? or [ and is not a number.
Comparison is numeric when both sides are numbers, string otherwise.
"""

import re
from fnmatch import fnmatchcase

from core.messages import HtreeError

BAD_EXPR = 24

_TOKEN_RE = re.compile(r'\s*(&&|\|\||==|!=|<=|>=|<|>|!|\(|\)|"[^"]*"|[^\s()!<>=&|"]+)')
_CMP = {"==", "!=", "<", ">", "<=", ">="}


def _tokenize(text: str):
    tokens, pos = [], 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise HtreeError(BAD_EXPR, f"-if: cannot parse '{text[pos:]}'")
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _compare(left: str, op: str, right: str) -> bool:
    ln, rn = _num(left), _num(right)
    if ln is not None and rn is not None:
        return {"==": ln == rn, "!=": ln != rn, "<": ln < rn, ">": ln > rn,
                "<=": ln <= rn, ">=": ln >= rn}[op]
    if op in ("==", "!=") and any(c in right for c in "*?["):
        match = fnmatchcase(left, right)
        return match if op == "==" else not match
    return {"==": left == right, "!=": left != right, "<": left < right, ">": left > right,
            "<=": left <= right, ">=": left >= right}[op]


class Expr:
    """Compiled -if expression. evaluate(getter) where getter(attr) -> str."""

    def __init__(self, text: str):
        self.text = text
        self.toks = _tokenize(text)
        self.pos = 0
        if not self.toks:
            raise HtreeError(BAD_EXPR, "-if: empty expression")
        self.tree = self._or()
        if self.pos != len(self.toks):
            raise HtreeError(BAD_EXPR, f"-if: unexpected '{self.toks[self.pos]}' in '{text}'")

    def attrs(self):
        """Attribute names the expression reads."""
        return [t[1:] for t in self.toks if t.startswith(".")]

    def evaluate(self, getter) -> bool:
        return self._eval(self.tree, getter)

    # -- parser --------------------------------------------------------------
    def _peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _take(self):
        tok = self._peek()
        if tok is None:
            raise HtreeError(BAD_EXPR, f"-if: expression ends early: '{self.text}'")
        self.pos += 1
        return tok

    def _or(self):
        node = self._and()
        while self._peek() == "||":
            self._take()
            node = ("or", node, self._and())
        return node

    def _and(self):
        node = self._not()
        while self._peek() == "&&":
            self._take()
            node = ("and", node, self._not())
        return node

    def _not(self):
        if self._peek() == "!":
            self._take()
            return ("not", self._not())
        return self._atom()

    def _atom(self):
        if self._peek() == "(":
            self._take()
            node = self._or()
            if self._take() != ")":
                raise HtreeError(BAD_EXPR, f"-if: missing ')' in '{self.text}'")
            return node
        left = self._operand()
        if self._peek() in _CMP:
            op = self._take()
            return ("cmp", left, op, self._operand())
        return ("truth", left)

    def _operand(self):
        tok = self._take()
        if tok in _CMP or tok in ("&&", "||", "!", "(", ")"):
            raise HtreeError(BAD_EXPR, f"-if: expected a value, got '{tok}' in '{self.text}'")
        if tok.startswith("."):
            return ("attr", tok[1:])
        if tok.startswith('"'):
            return ("lit", tok[1:-1])
        return ("lit", tok)

    # -- evaluation ----------------------------------------------------------
    def _value(self, operand, getter) -> str:
        kind, val = operand
        return getter(val) if kind == "attr" else val

    def _eval(self, node, getter) -> bool:
        op = node[0]
        if op == "or":
            return self._eval(node[1], getter) or self._eval(node[2], getter)
        if op == "and":
            return self._eval(node[1], getter) and self._eval(node[2], getter)
        if op == "not":
            return not self._eval(node[1], getter)
        if op == "truth":
            value = self._value(node[1], getter)
            return value not in ("", "0", "false")
        return _compare(self._value(node[1], getter), node[2], self._value(node[3], getter))
