import sys


class CpcError(Exception):
    """A pseudocode-level runtime error (SPEC 8.3). Stops execution of the program.

    lineno may be None when raised from code that has no AST node at hand; the
    statement dispatcher fills it in with the current statement's line.
    """

    def __init__(self, message, lineno=None):
        super().__init__(message)
        self.message = message
        self.lineno = lineno


class SyntaxIssue:
    """One collected static error (SPEC 8.2). kind is 'lex', 'parse' or 'eof'."""

    def __init__(self, message, lineno, kind='parse'):
        self.message = message
        self.lineno = lineno
        self.kind = kind


def _use_color(stream):
    # SPEC 8.7: color only on a terminal and only when NO_COLOR is unset.
    import os
    return stream.isatty() and not os.environ.get('NO_COLOR')


def _prefix(path, lineno):
    where = path if path else '<stdin>'
    return f'{where}:{lineno}: ' if lineno else f'{where}: '


def format_runtime_error(path, err):
    label = 'error'
    if _use_color(sys.stderr):
        label = '\033[1;31merror\033[0m'
    return f'{_prefix(path, err.lineno)}{label}: {err.message}'


def format_syntax_issue(path, issue):
    label = 'syntax error'
    if _use_color(sys.stderr):
        label = '\033[1;31msyntax error\033[0m'
    return f'{_prefix(path, issue.lineno)}{label}: {issue.message}'


def print_err(text):
    sys.stderr.write(text + '\n')
    sys.stderr.flush()


def print_internal_error(exc):
    """SPEC 8.4: interpreter defects are never presented as the user's fault."""
    import traceback
    print_err('internal error, please report to the cpc issue tracker:')
    print_err(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())
