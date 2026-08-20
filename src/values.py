"""Runtime value and type rules (SPEC sections 3-4).

A value travels the interpreter as a pair (python_value, type_name); stored
variables are wrapper objects that expose the same pair through indexing
([0] -> value, [1] -> type name). Every rule about which values may combine,
convert, print or be assigned lives in this module, so the AST nodes stay
thin and the rules cannot drift apart.

The PYTHON() interface returns values with type None; they are treated like
ANY: allowed anywhere, checked nowhere. That is the single escape hatch.
"""
import datetime

from .error import CpcError

NUMERIC = ('INTEGER', 'REAL')
TEXT = ('STRING', 'CHAR')
ANY_TYPES = (None, 'ANY')

_COMPARE_OPS = ('=', '<>', '<', '<=', '>', '>=')


def _raise(message, node=None):
    raise CpcError(message, getattr(node, 'lineno', None) or None)


def parts(v, node=None):
    """Split a value carrier into (python_value, type_name)."""
    if v is None:
        _raise('expression has no value (a procedure returns nothing)', node)
    return v[0], v[1]


# --- operators (SPEC 3.2) ----------------------------------------------------

def binary(op, left, right, node=None):
    a, at = parts(left, node)
    b, bt = parts(right, node)

    if at in ANY_TYPES or bt in ANY_TYPES:
        return _binary_any(op, a, b, node)

    if op in ('+', '-', '*'):
        if at in NUMERIC and bt in NUMERIC:
            result_type = 'REAL' if 'REAL' in (at, bt) else 'INTEGER'
            value = {'+': a + b, '-': a - b, '*': a * b}[op]
            return (float(value) if result_type == 'REAL' else value, result_type)
        _raise(f'cannot apply `{op}` to `{at}` and `{bt}`', node)

    if op == '/':
        if at in NUMERIC and bt in NUMERIC:
            if b == 0:
                _raise('cannot divide by zero', node)
            return (a / b, 'REAL')
        _raise(f'cannot apply `/` to `{at}` and `{bt}`', node)

    if op in ('DIV', 'MOD'):
        if at == 'INTEGER' and bt == 'INTEGER':
            if b == 0:
                _raise('cannot divide by zero', node)
            # DIV truncates toward zero; MOD keeps a = (a DIV b)*b + a MOD b.
            q = abs(a) // abs(b)
            if (a < 0) != (b < 0):
                q = -q
            return (q, 'INTEGER') if op == 'DIV' else (a - q * b, 'INTEGER')
        _raise(f'`{op}` needs INTEGER operands, found `{at}` and `{bt}`', node)

    if op == '&':
        if at in TEXT and bt in TEXT:
            return (a + b, 'STRING')
        _raise(f'cannot concatenate `{at}` and `{bt}`', node)

    if op in _COMPARE_OPS:
        return _compare(op, a, at, b, bt, node)

    _raise(f'unknown operator `{op}`', node)


def _binary_any(op, a, b, node):
    """One operand came from PYTHON()/ANY: fall back to Python semantics."""
    try:
        if op in _COMPARE_OPS:
            return (_PY_COMPARE[op](a, b), 'BOOLEAN')
        if op == '&':
            return (str(a) + str(b), 'STRING')
        value = _PY_ARITH[op](a, b)
    except Exception:
        _raise(f'cannot apply `{op}` to these values', node)
    if isinstance(value, float):
        return (value, 'REAL')
    return (value, 'INTEGER')


_PY_COMPARE = {
    '=': lambda a, b: a == b, '<>': lambda a, b: a != b,
    '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
    '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
}
_PY_ARITH = {
    '+': lambda a, b: a + b, '-': lambda a, b: a - b,
    '*': lambda a, b: a * b, '/': lambda a, b: a / b,
    'DIV': lambda a, b: a // b, 'MOD': lambda a, b: a % b,
}


def _compare(op, a, at, b, bt, node):
    comparable = (
        (at in NUMERIC and bt in NUMERIC)
        or (at in TEXT and bt in TEXT)
        or (at == 'DATE' and bt == 'DATE')
        or (at == bt)
    )
    if not comparable:
        _raise(f'cannot compare `{at}` with `{bt}`', node)
    if at == 'BOOLEAN' and op not in ('=', '<>'):
        _raise('BOOLEAN values support only `=` and `<>`', node)
    try:
        return (_PY_COMPARE[op](a, b), 'BOOLEAN')
    except Exception:
        _raise(f'cannot compare `{at}` with `{bt}`', node)


def require_boolean(v, node=None, what='condition'):
    value, type_name = parts(v, node)
    if type_name in ANY_TYPES:
        return bool(value)
    if type_name != 'BOOLEAN':
        _raise(f'{what} must be BOOLEAN, found `{type_name}`', node)
    return value


# --- assignment (SPEC 4.2) ---------------------------------------------------

def check_assign(target_type, v, node=None):
    """Return the python value to store, or raise. Widening INTEGER->REAL is
    the only implicit conversion."""
    value, type_name = parts(v, node)
    if type_name in ANY_TYPES or target_type == 'ANY':
        return value
    if type_name == target_type:
        return value
    if target_type == 'REAL' and type_name == 'INTEGER':
        return float(value)
    _raise(f'cannot assign `{type_name}` to `{target_type}`', node)


def assign_to(target, v, node=None):
    """Assign an evaluated value to an evaluated target object (SPEC 4.2/4.3)."""
    if v is None:
        _raise('expression has no value (a procedure returns nothing)', node)
    if target is None:
        _raise('assignment target does not exist', node)
    if isinstance(target, tuple):
        _raise('assignment target must be a variable, array element or field', node)
    if getattr(target, 'is_const', False):
        _raise('cannot assign a value to a constant', node)
    if getattr(target, 'is_enum', False):
        # Enum variables validate membership themselves (SPEC 4.8).
        target.set_value(v[0])
        return
    if getattr(target, 'is_struct', False):
        # Records/class instances take the whole object, not a raw value.
        target.set_value(v[0])
        return
    stored = check_assign(target[1], v, node)
    target.set_value(stored)


# --- INPUT parsing (SPEC 4.5) ------------------------------------------------

def parse_input(target_type, text, node=None):
    text = text.strip()
    if target_type == 'STRING' or target_type == 'ANY':
        return text
    if target_type == 'INTEGER':
        stripped = text[1:] if text[:1] in '+-' else text
        if stripped.isdigit():
            return int(text)
        _raise(f'expected INTEGER input, got `{text}`', node)
    if target_type == 'REAL':
        try:
            return float(text)
        except ValueError:
            _raise(f'expected REAL input, got `{text}`', node)
    if target_type == 'BOOLEAN':
        upper = text.upper()
        if upper in ('TRUE', 'FALSE'):
            return upper == 'TRUE'
        _raise(f'expected TRUE or FALSE, got `{text}`', node)
    if target_type == 'CHAR':
        if len(text) == 1:
            return text
        _raise(f'expected a single character, got `{text}`', node)
    if target_type == 'DATE':
        return parse_date(text, node)
    _raise(f'cannot INPUT a value of type `{target_type}`', node)


# --- dates (SPEC 4.7) --------------------------------------------------------

def parse_date(text, node=None):
    try:
        day, month, year = (int(x) for x in str(text).split('/'))
        return datetime.date(year, month, day)
    except (ValueError, TypeError):
        _raise(f'`{text}` is not a valid date (dd/mm/yyyy)', node)


def make_date(day, month, year, node=None):
    try:
        return datetime.date(year, month, day)
    except (ValueError, TypeError):
        _raise(f'{day:02}/{month:02}/{year:04} is not a valid calendar date', node)


def date_text(d):
    return f'{d.day:02}/{d.month:02}/{d.year:04}'


# --- text forms (SPEC 4.9) ---------------------------------------------------

def real_text(x):
    if x != x or x in (float('inf'), float('-inf')):
        return str(x)
    if abs(x) < 1e16 and x == int(x):
        return f'{int(x)}.0'
    return repr(x)


def array_text(value_dict):
    items = []
    for key, entry in value_dict.items():
        if key in ('left', 'right'):
            continue
        if entry[1] == 'ARRAY':
            inner = entry[0]
            # The element is an ARRAY wrapper or a raw bounds dict.
            inner_dict = inner if isinstance(inner, dict) else inner.value
            items.append(array_text(inner_dict))
        else:
            items.append(to_text(entry))
    return '[' + ', '.join(items) + ']'


def to_text(v, node=None):
    value, type_name = parts(v, node)
    if type_name == 'REAL':
        return real_text(value)
    if type_name == 'BOOLEAN':
        return 'TRUE' if value else 'FALSE'
    if type_name == 'DATE':
        return date_text(value)
    if type_name == 'ARRAY':
        return array_text(value)
    return str(value)


def echo_text(v):
    """Literal form for the interactive echo: strings and chars keep quotes."""
    if v is None:
        return None
    value, type_name = v[0], v[1]
    if type_name == 'STRING':
        return '"' + str(value) + '"'
    if type_name == 'CHAR':
        return "'" + str(value) + "'"
    return to_text(v)
