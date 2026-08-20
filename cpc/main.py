# Dependency check must run before the third-party imports below.
from .requirements import test_requirements
test_requirements()

import signal
# colorama makes \033 escape codes work on legacy Windows terminals.
import colorama
colorama.init()

from . import global_var
from . import options
from . import runner
from .history import PACKAGE_DIR
from .quit import quit
from .line_commands import run_command
from .error import print_err

import os
import sys

SCRIPTS_PATH = os.path.join(PACKAGE_DIR, 'scripts')

preline = '>'
multi_preline = '.'


def signal_handler(_signal, _frame):
    quit(130)


def wrong_argument(msg):
    print_err(f'Unknown argument: {msg}')
    print_err('Use `cpc -h` to get detailed information about how to use')
    quit(2)


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
            runner.parser.parse(text, lexer=runner.lexer, tracking=True)
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


# Interactive session (SPEC 8.6).
def with_line():
    global_var.set_running_mod('line')
    global_var.set_running_path('')
    if sys.stdin.isatty():
        options.standard_output()
    while 1:
        text = multi_input()
        runner.lexer.lineno = 1
        if run_command(text):
            continue
        if not text:
            continue
        global_var.set_running_mod('line')
        runner.execute_text(text, '')


def main(input_=None, output_=None, addition_file_name=None):
    if input_: global_var.set_std_in(input_)
    if output_: global_var.set_std_out(output_)

    # SPEC 8.10: files run in the order given, duplicates included.
    argv = sys.argv
    file_paths = []
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
                file_paths.append(arg)
        i += 1

    if addition_file_name:
        file_paths.append(addition_file_name)

    # SPEC 8.8: a plain run performs no update check, no network access and
    # no interactive prompt. Updating is the explicit `cpc -u` command.

    if not file_paths:
        runner.preload_scripts(SCRIPTS_PATH)
        with_line()
        return runner.RUN_OK

    worst = runner.RUN_OK
    for index, file_path in enumerate(file_paths):
        if not os.path.exists(file_path):
            wrong_argument(f'File `{file_path}` does not exist')
        if not os.path.isfile(file_path):
            wrong_argument(f'`{file_path}` is not a file')
        # SPEC 8.10: each file starts from a fresh interpreter state.
        if index > 0:
            runner.reset_interpreter(SCRIPTS_PATH)
        else:
            runner.preload_scripts(SCRIPTS_PATH)
        # The top-level file counts as imported (SPEC 8.11).
        runner.imported_paths.add(os.path.abspath(file_path))
        worst = max(worst, runner.run_file(file_path))
    return worst


def cli():
    """Console entry point (`cpc`) and shim target (`python main.py`)."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    global_var.__init__()
    try:
        quit(main())
    except EOFError:
        # End of input in the interactive session is a normal exit.
        quit(0)
    except KeyboardInterrupt:
        quit(130)


if __name__ == '__main__':
    cli()
