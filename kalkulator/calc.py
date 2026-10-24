"""A small, safe calculator: + − × ÷ and parentheses. Parses with `ast`, never `eval`."""

import ast
import operator
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext

from .numfmt import MAX_INPUT, NumberError, parse_number
from .sprak import _, english

MAX_LENGTH = 200

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


class CalcError(ValueError):
    pass


def _normalize(expression: str) -> str:
    text = expression.replace("×", "*").replace("÷", "/").replace("−", "-").replace(":", "/")
    # Decimal comma → dot. Commas are never separators in this calculator.
    return text.replace(",", ".").replace(" ", "")


def calculate(expression: str) -> Decimal:
    if not expression.strip():
        raise CalcError(_("Skriv inn et regnestykke."))
    if len(expression) > MAX_LENGTH:
        raise CalcError(_("Regnestykket er for langt."))
    if english() and "," in expression:
        # "1,500" means 1500 in English and 1.5 in Norwegian: refuse rather than guess.
        raise CalcError(_("Bruk punktum som desimaltegn, for eksempel 1.5. Komma er ikke tillatt."))
    source = _normalize(expression)
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError:
        raise CalcError(_("Regnestykket er ikke fullstendig.")) from None

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            # Re-read the literal from the text so 0.1 stays exactly 0.1, not a float.
            try:
                return parse_number(ast.get_source_segment(source, node))
            except NumberError as e:
                raise CalcError(str(e)) from None
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = evaluate(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        raise CalcError(_("Bare tall, + − × ÷ og parenteser er tillatt."))

    with localcontext() as ctx:
        ctx.prec = 34
        ctx.traps[DivisionByZero] = True
        ctx.traps[InvalidOperation] = True
        try:
            result = evaluate(tree)
        except (DivisionByZero, InvalidOperation):
            raise CalcError(_("Kan ikke dele på null.")) from None
    if abs(result) >= MAX_INPUT:
        raise CalcError(_("Svaret er for stort."))
    return result
