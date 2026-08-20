from .error import CpcError, SyntaxIssue
from . import options
from .history import Cmd
from .config import Config
import sys

running_mod = 'file'  # file / line
running_path = ''  # path of the file currently executed
console = Cmd()
config = Config()
std_in = sys.stdin
std_out = sys.stdout

# Static errors collected during lexing/parsing of the current text (SPEC 8.2).
syntax_errors = []


# Python stack frames consumed per pseudocode call. Measured 5 for a plain
# call chain (frame counting via PYTHON(), 2026-08); doubled with margin for
# expression-heavy bodies, which hold extra evaluation frames while calling.
PY_FRAMES_PER_CALL = 12


def __init__():
    global running_mod
    running_mod = 'file'
    console.preloop()
    # 'rl' counts PSEUDOCODE calls (SPEC 5.5); scale it to Python's limit.
    sys.setrecursionlimit(config.get_config('rl') * PY_FRAMES_PER_CALL + 300)


def set_std_in(new_in):
    global std_in
    std_in = new_in


def set_std_out(new_out):
    global std_out
    std_out = new_out


def get_std_in():
    return std_in


def get_std_out():
    return std_out


def set_config(opt_name, value):
    config.update_config(opt_name, value)


# --- runtime errors: these raise and thereby stop execution (SPEC 8.3) ---

def add_error_message(msg, obj):
    raise CpcError(msg, getattr(obj, 'lineno', None) or None)


def add_stack_error_message(msg):
    raise CpcError(msg)


def add_python_error_message(msg, obj):
    raise CpcError(str(msg), getattr(obj, 'lineno', None) or None)


# --- static errors: collected, reported before execution (SPEC 8.2) ---

def add_parse_error_message(msg, obj):
    syntax_errors.append(SyntaxIssue(
        msg, getattr(obj, 'lineno', None), 'parse', getattr(obj, 'lexpos', None)))


def add_eof_error_message(obj):
    syntax_errors.append(SyntaxIssue('unexpected end of input', getattr(obj, 'lineno', None), 'eof'))


def add_lexer_error_message(msg, obj):
    syntax_errors.append(SyntaxIssue(
        msg, getattr(obj, 'lineno', None), 'lex', getattr(obj, 'lexpos', None)))


def get_syntax_errors():
    return syntax_errors


def clear_syntax_errors():
    syntax_errors.clear()


def is_error_messages_empty():
    return not syntax_errors


def set_running_mod(mod):
    global running_mod
    running_mod = mod


def get_running_mod():
    return running_mod


def set_running_path(p):
    global running_path
    running_path = p


def get_running_path():
    return running_path


def print_(t, end='\n', need_output=True):
    if not need_output:
        return
    get_std_out().write(str(t) + end)
    get_std_out().flush()


def input_():
    get_std_out().flush()
    return get_std_in().readline().strip()
