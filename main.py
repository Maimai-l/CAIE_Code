# Dependency check must run before the third-party imports below.
from src.requirements import test_requirements
test_requirements()

from ply import lex
from chardet import detect
import signal
# colorama makes \033 escape codes work on legacy Windows terminals.
import colorama
colorama.init()

import src.global_var as global_var

from src.lex import *
from src.parse import *
import src.options as options
from src.history import HOME_PATH
from src.quit import quit
from src.line_commands import run_command
from src.update import update
from src.update import update_expired
from src.update import integrity_protection
from src.error import (
    CpcError,
    format_runtime_error,
    format_syntax_issue,
    print_err,
    print_internal_error,
)

import sys
import os
from time import time

# Result states of running one file (drives the process exit code, SPEC 8.5).
RUN_OK = 0
RUN_ERROR = 1
RUN_INTERNAL = 70

preline = '>'
multi_preline = '.'
home_path = HOME_PATH


def signal_handler(_signal, _frame):
    quit(130)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def wrong_argument(msg):
    print_err(f'Unknown argument: {msg}')
    print_err('Use `cpc -h` to get detailed information about how to use')
    quit(2)


def report_syntax_errors(path, source=None):
    if options.get_value('show_error'):
        for issue in global_var.get_syntax_errors()[:20]:
            print_err(format_syntax_issue(path, issue, source))
    global_var.clear_syntax_errors()


def preload_scripts():
    scripts_path = os.path.join(home_path, 'scripts')
    for p, _dir_list, file_list in os.walk(scripts_path):
        for i in file_list:
            path = os.path.join(p, i)
            _, n = os.path.splitext(path)
            if n == '.cpc':
                with_file(path, True)


def _read_line(prompt_text):
    # SPEC 8.6: prompts appear only on a terminal.
    if sys.stdin.isatty():
        return input(prompt_text)
    return input()


def multi_input():
    text = _read_line(f'{preline} ')
    if not text.strip():
        return ''
    while True:
        global_var.clear_syntax_errors()
        try:
            parser.parse(text, tracking=True)
        except Exception:
            pass
        issues = global_var.get_syntax_errors()
        # Only "the input ended mid-construct" asks for a continuation line;
        # a complete-but-invalid line is reported at once (SPEC 8.6).
        if issues and all(i.kind == 'eof' for i in issues):
            text += '\n' + _read_line(f'{multi_preline} ')
            continue
        global_var.clear_syntax_errors()
        return text


def run_AST(ast, preload=False):
    if options.get_value('show_tree') and not preload:
        print(ast.get_tree())

    if options.get_value('show_time') and not preload:
        t = time()

    ast.exe()

    if options.get_value('show_time') and not preload:
        t = time() - t
        print(f'\033[4mDuration: {t}s\033[0m')


def execute_text(text, path, preload=False):
    """Parse and run one chunk of source. Returns a RUN_* state."""
    global_var.clear_syntax_errors()
    try:
        ast = parser.parse(text, debug=options.get_value('show_parse'), tracking=True)
    except Exception as e:
        print_internal_error(e)
        return RUN_INTERNAL

    if global_var.get_syntax_errors():
        report_syntax_errors(path, text)
        return RUN_ERROR
    if ast is None:
        return RUN_OK

    try:
        run_AST(ast, preload=preload)
    except CpcError as e:
        if options.get_value('show_error'):
            print_err(format_runtime_error(path, e))
        return RUN_ERROR
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as e:
        print_internal_error(e)
        return RUN_INTERNAL
    return RUN_OK


# Interactive session (SPEC 8.6).
def with_line():
    global_var.set_running_mod('line')
    global_var.set_running_path('')
    if sys.stdin.isatty():
        options.standard_output()
    while 1:
        text = multi_input()
        lexer.lineno = 1
        if run_command(text):
            continue
        if not text:
            continue
        execute_text(text, '')


# Run a whole file. Returns a RUN_* state.
def with_file(path, preload=False):
    global_var.set_running_mod('file')
    global_var.set_running_path(path)
    lexer.lineno = 1
    with open(path, 'rb') as f:
        encode = detect(f.read())['encoding']
    with open(path, 'r', encoding=encode) as f:
        text = f.read()
    if not text.strip():
        return RUN_OK

    return execute_text(text, path, preload=preload)


def main(input_=None, output_=None, addition_file_name=None):
    if input_: global_var.set_std_in(input_)
    if output_: global_var.set_std_out(output_)

    argv = sys.argv
    file_paths = set()
    i = 1
    while i < len(argv):
        arg = argv[i]
        for opt in options.arguments:
            if opt.check(arg):
                opt.run(argv[i:])
                i += opt.value_num
                break
        else:
            if arg[0] == '-':
                wrong_argument(f'Unknown option `{arg}`')
            else:
                file_paths.add(arg)
        i += 1

    if addition_file_name:
        file_paths.add(addition_file_name)

    if not config.get_config('dev') and config.get_config('integrity-protection'):
        integrity_protection()

    if config.get_config('dev.simulate-update') or (config.get_config('auto-update') and not config.get_config('dev') and update_expired()):
        update()
        config.update_config('last-auto-update', str(time()))

    preload_scripts()

    if not file_paths:
        with_line()
        return RUN_OK

    worst = RUN_OK
    for file_path in file_paths:
        lexer.lineno = 1
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                worst = max(worst, with_file(file_path))
            else:
                wrong_argument(f'`{file_path}` is not a file')
        else:
            wrong_argument(f'File `{file_path}` does not exist')
    return worst


global_var.__init__()

lexer = lex.lex()
parser = build_parser()

if __name__ == '__main__':
    try:
        quit(main())
    except EOFError:
        # End of input in the interactive session is a normal exit.
        quit(0)
    except KeyboardInterrupt:
        quit(130)
