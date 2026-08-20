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
    """One collected static error (SPEC 8.2). kind is 'lex', 'parse' or 'eof'.

    'eof' means the input ended in the middle of a construct — the interactive
    session uses this to ask for a continuation line instead of reporting.
    """

    def __init__(self, message, lineno, kind='parse', lexpos=None):
        self.message = message
        self.lineno = lineno
        self.kind = kind
        self.lexpos = lexpos


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


def format_syntax_issue(path, issue, source=None):
    label = 'syntax error'
    if _use_color(sys.stderr):
        label = '\033[1;31msyntax error\033[0m'
    parts = [f'{_prefix(path, issue.lineno)}{label}: {issue.message}']
    # SPEC 8.2: show the offending source line with a caret marker.
    if source is not None and issue.lineno and issue.lexpos is not None:
        lines = source.split('\n')
        if 0 < issue.lineno <= len(lines):
            line = lines[issue.lineno - 1]
            line_start = sum(len(l) + 1 for l in lines[:issue.lineno - 1])
            col = max(0, min(issue.lexpos - line_start, len(line)))
            parts.append('    ' + line)
            parts.append('    ' + ' ' * col + '^')
    return '\n'.join(parts)


def print_err(text):
    sys.stderr.write(text + '\n')
    sys.stderr.flush()


def print_internal_error(exc):
    """SPEC 8.4: interpreter defects are never presented as the user's fault."""
    import traceback
    print_err('internal error, please report to the cpc issue tracker:')
    print_err(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())
