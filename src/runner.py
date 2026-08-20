"""Parsing and execution of source text. This module owns the lexer/parser
instances and the run-one-file logic, so both the CLI (main.py) and the
IMPORT statement use the same path without importing the entry script."""
import os
import sys

from ply import lex as plylex
from chardet import detect

from . import global_var
from . import lex as lex_rules
from . import options
from .parse import build_parser
from .error import (
    CpcError,
    format_runtime_error,
    format_syntax_issue,
    print_err,
    print_internal_error,
)

# Result states of running one chunk of source (exit codes, SPEC 8.5).
RUN_OK = 0
RUN_ERROR = 1
RUN_INTERNAL = 70

lexer = plylex.lex(module=lex_rules)
parser = build_parser()

# Absolute paths already imported in this run (SPEC 8.11).
imported_paths = set()


def reset_imports():
    imported_paths.clear()


def report_syntax_errors(path, source=None):
    if options.get_value('show_error'):
        for issue in global_var.get_syntax_errors()[:20]:
            print_err(format_syntax_issue(path, issue, source))
    global_var.clear_syntax_errors()


def run_ast(ast, preload=False):
    if options.get_value('show_tree') and not preload:
        print(ast.get_tree())

    if options.get_value('show_time') and not preload:
        from time import time
        t = time()

    ast.exe()

    if options.get_value('show_time') and not preload:
        from time import time
        print(f'\033[4mDuration: {time() - t}s\033[0m')


def execute_text(text, path, preload=False):
    """Parse and run one chunk of source. Returns a RUN_* state."""
    global_var.clear_syntax_errors()
    try:
        ast = parser.parse(text, lexer=lexer, debug=options.get_value('show_parse'), tracking=True)
    except Exception as e:
        print_internal_error(e)
        return RUN_INTERNAL

    if global_var.get_syntax_errors():
        report_syntax_errors(path, text)
        return RUN_ERROR
    if ast is None:
        return RUN_OK

    try:
        run_ast(ast, preload=preload)
    except CpcError as e:
        if options.get_value('show_error'):
            print_err(format_runtime_error(path, e))
        return RUN_ERROR
    except (SystemExit, KeyboardInterrupt):
        raise
    except RecursionError:
        # Deep expression nesting can exhaust Python's stack before the
        # pseudocode call limit is reached; still report it cleanly.
        if options.get_value('show_error'):
            print_err(format_runtime_error(path, CpcError('the program nests too deeply for the interpreter')))
        return RUN_ERROR
    except Exception as e:
        print_internal_error(e)
        return RUN_INTERNAL
    return RUN_OK


def run_file(path, preload=False):
    """Run a whole file. Returns a RUN_* state."""
    global_var.set_running_mod('file')
    global_var.set_running_path(path)
    lexer.lineno = 1
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        # SPEC 1.1: UTF-8 is required; legacy encodings work with a warning.
        encoding = detect(raw)['encoding'] or 'utf-8'
        print_err(f'warning: `{path}` is not UTF-8; read as {encoding}')
        text = raw.decode(encoding, errors='replace')
    if not text.strip():
        return RUN_OK

    return execute_text(text, path, preload=preload)


def preload_scripts(scripts_path):
    """Run every bundled .cpc script to define the standard helpers."""
    for parent, _dirs, files in os.walk(scripts_path):
        for name in files:
            if os.path.splitext(name)[1] == '.cpc':
                run_file(os.path.join(parent, name), preload=True)


def reset_interpreter(scripts_path):
    """Fresh state for the next file of a multi-file run (SPEC 8.10)."""
    from .AST.data import stack
    stack.__init__()
    reset_imports()
    preload_scripts(scripts_path)
