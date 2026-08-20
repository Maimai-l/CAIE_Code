#!/usr/bin/env python3
"""Expected-output test runner for the cpc interpreter.

Conventions (normative description in docs/PLAN.md, section 1):

  tests/cases/<area>/<name>.cpc           program under test
  tests/cases/<area>/<name>.out           expected stdout (required)
  tests/cases/<area>/<name>.err           expected stderr, exact match (optional)
  tests/cases/<area>/<name>.err.contains  expected stderr, one substring per line (optional)
  tests/cases/<area>/<name>.in            stdin to feed (optional, default empty)
  tests/cases/<area>/<name>.exit          expected exit code (optional, default 0)
  tests/cases/<area>/<name>.argv          custom argv tokens; the token CASE is replaced
                                          by the absolute path of the .cpc file (optional)
  tests/cases/<area>/<name>.repl          marker: run with no file argument and pipe the
                                          .cpc content to stdin (optional)
  tests/cases/<area>/<name>.files/        fixture files copied into the working dir (optional)

At most one of .err / .err.contains may exist. When neither exists, stderr must be empty.
Every case runs in a fresh temporary working directory with a 10 second timeout.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS_DIR)
CASES = os.path.join(TESTS_DIR, 'cases')
MAIN = os.path.join(REPO, 'main.py')
TIMEOUT_SECONDS = 10
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def read_text(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def normalize(text, case_path):
    """Make captured output machine-independent and newline-tolerant."""
    text = text.replace('\r\n', '\n')
    text = ANSI.sub('', text)
    text = text.replace(case_path, 'FILE')
    if text.endswith('\n'):
        text = text[:-1]
    return text


def build_env(workdir):
    env = dict(os.environ)
    # Suppresses the auto-updater on the pre-step-9 interpreter; harmless afterwards.
    env['CODESPACES'] = '1'
    # Keeps interpreter state out of the repository once step 9 introduces CPC_HOME.
    env['CPC_HOME'] = os.path.join(workdir, '.cpc-home')
    return env


def run_case(cpc_path):
    """Run one case. Returns (ok: bool, reason: str)."""
    base = cpc_path[:-len('.cpc')]
    expected_out = read_text(base + '.out')
    if expected_out is None:
        return False, 'missing required .out file'
    expected_err = read_text(base + '.err')
    err_contains = read_text(base + '.err.contains')
    if expected_err is not None and err_contains is not None:
        return False, 'both .err and .err.contains exist'
    stdin_text = read_text(base + '.in', '')
    expected_exit = int(read_text(base + '.exit', '0').strip())
    argv_spec = read_text(base + '.argv')
    is_repl = os.path.exists(base + '.repl')

    with tempfile.TemporaryDirectory() as workdir:
        fixtures = base + '.files'
        if os.path.isdir(fixtures):
            for name in os.listdir(fixtures):
                shutil.copy(os.path.join(fixtures, name), workdir)

        if is_repl:
            argv = []
            stdin_text = read_text(cpc_path, '')
        elif argv_spec is not None:
            argv = [cpc_path if tok == 'CASE' else tok for tok in argv_spec.split()]
        else:
            argv = [cpc_path]

        try:
            proc = subprocess.run(
                [sys.executable, MAIN] + argv,
                cwd=workdir,
                env=build_env(workdir),
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return False, f'timeout after {TIMEOUT_SECONDS}s'

    out = normalize(proc.stdout, cpc_path)
    err = normalize(proc.stderr, cpc_path)

    if out != normalize(expected_out, cpc_path):
        return False, first_diff('stdout', normalize(expected_out, cpc_path), out)
    if expected_err is not None:
        if err != normalize(expected_err, cpc_path):
            return False, first_diff('stderr', normalize(expected_err, cpc_path), err)
    elif err_contains is not None:
        for needle in err_contains.splitlines():
            if needle and needle not in err:
                return False, f'stderr does not contain {needle!r}; stderr was {err!r}'
    elif err != '':
        return False, f'expected empty stderr, got {err!r}'
    if proc.returncode != expected_exit:
        return False, f'exit code {proc.returncode}, expected {expected_exit} (stderr: {err!r})'
    return True, ''


def first_diff(stream, expected, actual):
    exp_lines, act_lines = expected.split('\n'), actual.split('\n')
    for i in range(max(len(exp_lines), len(act_lines))):
        e = exp_lines[i] if i < len(exp_lines) else '<missing>'
        a = act_lines[i] if i < len(act_lines) else '<missing>'
        if e != a:
            return f'{stream} line {i + 1}: expected {e!r}, got {a!r}'
    return f'{stream} differs'


def collect_cases(filter_text):
    result = []
    for root, dirs, files in os.walk(CASES):
        # Fixture directories may themselves contain .cpc files; they are data, not cases.
        dirs[:] = [d for d in dirs if not d.endswith('.files')]
        for name in sorted(files):
            if name.endswith('.cpc'):
                path = os.path.join(root, name)
                if filter_text in os.path.relpath(path, CASES):
                    result.append(path)
    return sorted(result)


def grammar_gate():
    """SPEC 2.5: the grammar must build with zero conflicts."""
    proc = subprocess.run(
        [sys.executable, '-c',
         'import sys; sys.path.insert(0, sys.argv[1]); '
         'from src.parse import build_parser; build_parser(strict=True)',
         REPO],
        capture_output=True, text=True)
    if proc.returncode != 0:
        print('FAIL grammar gate: parser does not build cleanly')
        print(proc.stderr.strip())
        return False
    print('PASS grammar gate (zero conflicts)')
    return True


def main():
    filter_text = ''
    args = sys.argv[1:]
    if args and args[0] == '--filter' and len(args) > 1:
        filter_text = args[1]
    if not grammar_gate():
        return 1
    cases = collect_cases(filter_text)
    if not cases:
        print('no test cases found')
        return 1
    failed = 0
    for path in cases:
        rel = os.path.relpath(path, CASES)
        ok, reason = run_case(path)
        if ok:
            print(f'PASS {rel}')
        else:
            failed += 1
            print(f'FAIL {rel}: {reason}')
    print(f'\n{len(cases) - failed}/{len(cases)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
