"""Built-in functions (SPEC section 9).

One registry, one argument checker, one AST node class. Each entry is
  name: (min_args, max_args, [type specs], implementation)
where a type spec is a concrete type name or one of the groups
'NUM' (INTEGER/REAL), 'TEXT' (STRING/CHAR), 'ANY'. Extra variadic
arguments (max_args=None) are unchecked. Implementations receive the node
(for error positions) and the evaluated argument pairs, and return a
(value, type) pair or None for EXIT.
"""
import random

from .data import *
from ..AST_Base import *
from ..global_var import *
from .. import values
from ..quit import quit

_GROUPS = {
    'NUM': ('INTEGER', 'REAL'),
    'TEXT': ('STRING', 'CHAR'),
}


def _fail(node, message):
    add_error_message(message, node)


def _type_ok(spec, type_name):
    if spec == 'ANY' or type_name in values.ANY_TYPES:
        return True
    if spec in _GROUPS:
        return type_name in _GROUPS[spec]
    return type_name == spec


class Builtin(AST_Node):
    def __init__(self, name, parameters, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'BUILTIN'
        self.name = name
        self.parameters = parameters

    def get_tree(self, level=0):
        result = LEVEL_STR * level + self.name
        if self.parameters:
            result += '\n' + self.parameters.get_tree(level+1)
        return result

    def exe(self, pre_params=None):
        min_args, max_args, specs, impl = BUILTINS[self.name]
        if pre_params is not None:
            args = pre_params
        else:
            args = self.parameters.exe() if self.parameters else []
        if len(args) < min_args or (max_args is not None and len(args) > max_args):
            expected = str(min_args) if min_args == max_args else f'{min_args} to {max_args or "more"}'
            _fail(self, f'`{self.name}` expects {expected} parameter(s), but found {len(args)}')
        for i, arg in enumerate(args):
            spec = specs[i] if i < len(specs) else 'ANY'
            if arg is None:
                _fail(self, f'parameter {i+1} of `{self.name}` has no value')
            if not _type_ok(spec, arg[1]):
                _fail(self, f'parameter {i+1} of `{self.name}` expects `{spec}`, found `{arg[1]}`')
        return impl(self, *args)


# --- conversions -------------------------------------------------------------

def _to_int(node, v):
    try:
        # Truncation toward zero, also for numeric text (SPEC section 9).
        return (int(float(v[0])), 'INTEGER')
    except (ValueError, TypeError):
        _fail(node, f'cannot convert `{v[0]}` into `INTEGER`')

def _to_real(node, v):
    try:
        return (float(v[0]), 'REAL')
    except (ValueError, TypeError):
        _fail(node, f'cannot convert `{v[0]}` into `REAL`')

def _to_string(node, v):
    return (values.to_text(v, node), 'STRING')

def _to_char(node, v):
    text = str(v[0])
    if len(text) != 1:
        _fail(node, f'cannot convert `{text}` into `CHAR` (need exactly one character)')
    return (text, 'CHAR')

def _to_boolean(node, v):
    if v[1] == 'BOOLEAN':
        return (v[0], 'BOOLEAN')
    text = str(v[0]).strip().upper()
    if text in ('TRUE', 'FALSE'):
        return (text == 'TRUE', 'BOOLEAN')
    _fail(node, f'cannot convert `{v[0]}` into `BOOLEAN`')


# --- strings -----------------------------------------------------------------

def _left(node, s, n):
    if not 0 <= n[0] <= len(s[0]):
        _fail(node, f'LEFT length {n[0]} is outside 0..{len(s[0])}')
    return (s[0][:n[0]], 'STRING')

def _right(node, s, n):
    if not 0 <= n[0] <= len(s[0]):
        _fail(node, f'RIGHT length {n[0]} is outside 0..{len(s[0])}')
    return (s[0][len(s[0]) - n[0]:], 'STRING')

def _mid(node, s, start, length):
    if start[0] < 1 or length[0] < 0 or start[0] + length[0] - 1 > len(s[0]):
        _fail(node, f'MID({start[0]}, {length[0]}) is outside a string of length {len(s[0])}')
    return (s[0][start[0] - 1:start[0] - 1 + length[0]], 'STRING')

def _length(node, v):
    if v[1] in ('STRING', 'CHAR'):
        return (len(str(v[0])), 'INTEGER')
    if v[1] == 'ARRAY':
        return (len(v[0]) - 2, 'INTEGER')  # minus the 'left'/'right' entries
    _fail(node, f'LENGTH expects `STRING` or `ARRAY`, found `{v[1]}`')

def _case_impl(upper):
    def impl(node, v):
        text = str(v[0])
        return (text.upper() if upper else text.lower(), v[1])
    return impl


# --- numbers -----------------------------------------------------------------

def _rand(node, n):
    if n[0] <= 0:
        _fail(node, f'RAND expects a positive INTEGER, found {n[0]}')
    # SPEC section 9: continuous uniform in [0, n).
    return (random.random() * n[0], 'REAL')

def _pow(node, x, y):
    try:
        return (float(x[0] ** y[0]), 'REAL')
    except (OverflowError, ZeroDivisionError, ValueError):
        _fail(node, f'cannot raise {x[0]} to the power {y[0]}')

def _round(node, x, places=None):
    digits = places[0] if places is not None else 0
    return (float(round(x[0], digits)), 'REAL')

def _div(node, a, b):
    return values.binary('DIV', a, b, node)

def _mod(node, a, b):
    return values.binary('MOD', a, b, node)


# --- dates (SPEC 4.7) --------------------------------------------------------

def _day(node, d):
    return (d[0].day, 'INTEGER')

def _month(node, d):
    return (d[0].month, 'INTEGER')

def _year(node, d):
    return (d[0].year, 'INTEGER')

def _dayindex(node, d):
    # Sunday = 1 ... Saturday = 7.
    return ((d[0].weekday() + 1) % 7 + 1, 'INTEGER')

def _setdate(node, day, month, year):
    return (values.make_date(day[0], month[0], year[0], node), 'DATE')

def _today(node):
    import datetime
    return (datetime.date.today(), 'DATE')


# --- interpreter interface ---------------------------------------------------

def _eof(node, path):
    f = stack.get_file(path[0])
    eof = stack.get_eof(path[0])
    return (f.tell() >= eof, 'BOOLEAN')

def _exit(node, code=None):
    quit(int(code[0]) if code is not None else 0)

def _vartype(node, v):
    return (v[1] if v[1] is not None else 'ANY', 'STRING')


class _PythonBridge(Builtin):
    """PYTHON(code, *vars): run python code; extra variables are passed under
    the NAME they have at the call site, so this needs the AST nodes."""

    def exe(self, pre_params=None):
        if not self.parameters:
            _fail(self, '`PYTHON` expects at least the code string')
        args = self.parameters.exe()
        if args[0][1] != 'STRING':
            _fail(self, 'the first parameter of `PYTHON` must be the code STRING')
        namespace = {}
        for i in range(1, len(args)):
            node = self.parameters.parameters[i]
            name = getattr(node, 'id', None)
            if name is None:
                _fail(self, '`PYTHON` extra parameters must be plain variables')
            namespace[name] = args[i][0]
        namespace['_result'] = None
        try:
            exec(args[0][0], namespace)
        except Exception as e:
            _fail(self, f'PYTHON code failed: {e}')
        return (namespace['_result'], None)


BUILTINS = {
    'INT':      (1, 1, ['ANY'], _to_int),
    'INTEGER':  (1, 1, ['ANY'], _to_int),
    'REAL':     (1, 1, ['ANY'], _to_real),
    'STRING':   (1, 1, ['ANY'], _to_string),
    'CHAR':     (1, 1, ['ANY'], _to_char),
    'BOOLEAN':  (1, 1, ['ANY'], _to_boolean),
    'LEFT':     (2, 2, ['STRING', 'INTEGER'], _left),
    'RIGHT':    (2, 2, ['STRING', 'INTEGER'], _right),
    'MID':      (3, 3, ['STRING', 'INTEGER', 'INTEGER'], _mid),
    'LENGTH':   (1, 1, ['ANY'], _length),
    'LCASE':    (1, 1, ['TEXT'], _case_impl(False)),
    'UCASE':    (1, 1, ['TEXT'], _case_impl(True)),
    'TO_LOWER': (1, 1, ['TEXT'], _case_impl(False)),
    'TO_UPPER': (1, 1, ['TEXT'], _case_impl(True)),
    'RAND':     (1, 1, ['INTEGER'], _rand),
    'POW':      (2, 2, ['NUM', 'NUM'], _pow),
    'ROUND':    (1, 2, ['NUM', 'INTEGER'], _round),
    'DIV':      (2, 2, ['INTEGER', 'INTEGER'], _div),
    'MOD':      (2, 2, ['INTEGER', 'INTEGER'], _mod),
    'DAY':      (1, 1, ['DATE'], _day),
    'MONTH':    (1, 1, ['DATE'], _month),
    'YEAR':     (1, 1, ['DATE'], _year),
    'DAYINDEX': (1, 1, ['DATE'], _dayindex),
    'SETDATE':  (3, 3, ['INTEGER', 'INTEGER', 'INTEGER'], _setdate),
    'TODAY':    (0, 0, [], _today),
    'EOF':      (1, 1, ['STRING'], _eof),
    'EXIT':     (0, 1, ['INTEGER'], _exit),
    'VARTYPE':  (1, 1, ['ANY'], _vartype),
    'PYTHON':   (1, None, ['STRING'], None),  # dispatched to _PythonBridge
}


def make_builtin(name, parameters, p=None):
    node_class = _PythonBridge if name == 'PYTHON' else Builtin
    return node_class(name, parameters, p=p)


# The set of built-in names, as the parser consumes it.
insert_functions = BUILTINS
