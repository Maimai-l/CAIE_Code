# Remediation Plan

Status: DRAFT for review. No implementation starts before this plan and `docs/SPEC.md`
are approved. Findings referenced as A1–E7 are from the review report (2026-08-20).

---

## 0. Rules that hold for every step

- **R1 — Spec is law.** A step implements only clauses of SPEC.md. If a step needs behavior
  the spec doesn't define, the spec is amended and re-reviewed BEFORE code is written.
- **R2 — Tests are append-only.** A step MUST NOT modify tests added by earlier steps.
  This is enforceable because baseline tests (step 0) cover only behavior the spec KEEPS
  (see 1.4). If a step would need to change an existing test, the plan is wrong — stop.
- **R3 — Size budget.** Each step has a net line budget (code added minus code deleted,
  tests excluded). Exceeding a budget by more than 50% means stop and re-design, not push.
  Expected total across all steps: `src/` shrinks by roughly 300 lines.
- **R4 — Comment discipline.** All code comments in English. A comment states an invariant,
  a spec clause number, or a non-obvious reason. No comments narrating what the next line does.
- **R5 — One step, one commit** (large steps list their internal commits). Message format
  `step N: <goal>`. All tests green before the next step starts.
- **R6 — No new dependencies.** The test runner uses the Python standard library only.

---

## 1. Test infrastructure design (step 0, before touching the interpreter)

### 1.1 The test form

Every test is an *expected-output test*: a pseudocode program plus files stating exactly
what the interpreter must produce. No unit-test framework; the interpreter is exercised
only through its public interface (the command line), which is what students use.

```
tests/
  run_tests.py              # the runner, stdlib only, ~150 lines
  cases/<area>/<name>.cpc   # program under test
  cases/<area>/<name>.out   # expected stdout  (required; may be empty)
  cases/<area>/<name>.err   # expected stderr, exact match (optional)
  cases/<area>/<name>.err.contains  # expected stderr, one required substring per line
                            # (optional; at most one of .err / .err.contains; used where
                            # the message format is expected to improve in a later step)
  cases/<area>/<name>.in    # stdin to feed    (optional; default: empty)
  cases/<area>/<name>.exit  # expected exit code (optional; default 0)
  cases/<area>/<name>.argv  # custom argv tokens; the token CASE stands for the absolute
                            # path of the .cpc file (optional; enables CLI-flag tests)
  cases/<area>/<name>.files/  # fixture files copied to the working dir (optional)
  cases/<area>/<name>.repl  # marker: run with no file argument, .cpc becomes stdin
```
When neither `.err` nor `.err.contains` exists, stderr must be empty.

### 1.2 Runner algorithm (normative)

For each `cases/**/<name>.cpc`, in sorted path order:

1. Create a fresh temporary directory D. Copy `<name>.files/*` into D if present.
2. Run `python main.py <abs path to name.cpc>` with working directory D
   (REPL cases: no file argument; `.cpc` content piped to stdin), stdin from `.in`,
   environment: current env plus `CODESPACES=1` (suppresses the updater today; replaced by
   `CPC_HOME=D` + hermetic default in step 9 — a one-line runner change, the only planned
   runner change), timeout 10 seconds.
3. Normalize each captured stream: CRLF→LF, strip ANSI escape sequences
   (regex `\x1b\[[0-9;]*m`), drop one trailing LF if present. Apply the same to expected files.
4. The case passes iff stdout == `.out` AND stderr == `.err` AND exit code == `.exit`.
   (Until step 1 lands, stderr is empty and exit codes are always 0, so baseline cases
   simply omit `.err`/`.exit`.)
5. Print one line per case (`PASS`/`FAIL name` + first differing line on failure) and a
   summary; exit 1 if any case failed. `--filter SUBSTRING` runs a subset.

A timeout or crash of the interpreter process is a FAIL with the reason printed.

### 1.3 Worked examples (these exact files will exist)

`tests/cases/gram/and_or_precedence.cpc` (added in step 3):
```
OUTPUT TRUE OR FALSE AND FALSE
```
`tests/cases/gram/and_or_precedence.out`:
```
TRUE
```

`tests/cases/err/undeclared_variable.cpc` (added in step 1):
```
OUTPUT x
```
`.out` empty; `.exit` = `1`; `.err`:
```
FILE:1: error: no variable or constant named `x`
```
(The runner substitutes the literal token `FILE` for the case's absolute path before
comparing, so expected files stay machine-independent.)

### 1.4 Baseline suite (step 0): pin what already works

Rule: baseline cases cover ONLY behavior SPEC keeps unchanged, so they never need editing
later (R2). They therefore avoid: error messages, exit codes, multi-value `OUTPUT`
separators, REAL formatting, file round-trips, REPL, enums, OOP inheritance.

24 cases, all MUST pass against the current interpreter before any fix — that gate reviews
the harness itself:

| Case | Asserts |
|------|---------|
| basics/declare_assign_output | `<-` and OUTPUT of INTEGER |
| basics/integer_arithmetic | `+ - * DIV MOD` on INTEGER literals |
| basics/if_else, basics/nested_if | both IF forms |
| basics/constant_read | CONSTANT then OUTPUT |
| loops/for_basic, loops/for_step_down | FOR 1..5; FOR 10..1 STEP -2 |
| loops/while_do, loops/while_no_do, loops/repeat_until | three loop forms |
| arrays/one_dim_set_get, arrays/two_dim, arrays/negative_bounds | element write/read |
| arrays/literal_one_based | `a <- [6,7,8]` into `ARRAY[1:3]` |
| case/int_labels_semicolon, case/otherwise_semicolon | current CASE syntax (with `;` — stays legal per SPEC 2.3) |
| proc/call_with_args, proc/byref_integer | parameter passing that already works |
| func/return_value, func/recursion_depth_50 | function calls; shallow recursion |
| strings/left_right_mid_length, strings/concat_ampersand | happy-path built-ins |
| io/input_string, io/input_integer | INPUT with `.in` files |
| types/record_field_set_get | `TYPE/ENDTYPE`, standalone `b.a` access |
| dates/setdate_day_month_year | SETDATE + accessors (current output format kept) |

### 1.5 Continuous integration (part of step 0)

`.github/workflows/tests.yml`: on push and pull request, CPython 3.11 and PyPy 3.10,
`pip install -r requirements.txt`, `python tests/run_tests.py`. Green CI is the merge gate
for every later step.

---

## 2. Fix sequence

Ordering principle: (a) safety net first; (b) error *reporting* before error *sites*, so
every later fix lands with its final user-visible message; (c) syntax before semantics,
because the grammar decides what programs exist at all; (d) the value/type core before
everything that consumes it; (e) feature completion (OOP/enums) last, on a stable core.
Each step lists: spec clauses, files, method, tests added, net size budget.

### Step 0 — Test harness + baseline + CI
- Spec: none (no interpreter change). Findings: E1.
- Files: `tests/`, `.github/workflows/tests.yml`.
- Method: exactly section 1 of this plan.
- Tests: the 24 baseline cases; all green on the unmodified interpreter.
- Budget: +120 lines runner (tests/data excluded from budgets).

### Step 1 — One error channel, correct exit codes
- Spec: 8.1–8.5, 8.7. Findings: D1, D2 (partially: batching removed), D4, A11 (stop-on-error policy).
- Files: `src/error.py`, `src/global_var.py`, `src/AST/program.py` (Statements.exe),
  `main.py`, `src/quit.py`.
- Method: introduce ONE exception type `CpcError(message, lineno)`. The existing
  `add_*_error_message()` helpers RAISE it instead of appending to the `errors` dict —
  call sites all over the AST stay untouched, which is what keeps this step small.
  Lex/parse errors keep collecting into a list; after parsing, if the list is non-empty,
  print all to stderr and exit 1 without executing. Runtime: first `CpcError` propagates to
  the per-file driver, printed to stderr as `FILE:LINE: error: ...`, exit 1. Any other
  Python exception prints the internal-error banner + traceback, exit 70. Delete the two
  bare `except: pass` in `main.py`, the `try/except` in `Statements.exe`, the error-dict
  sort/dedup machinery, and the "Python Error" class. Color only per 8.7.
  REPL: catch `CpcError` per line, print, continue.
- Tests: err/undeclared_variable, err/divide_by_zero_stops (nothing after the error runs),
  err/assign_to_constant, err/syntax_error_exit_1, err/success_exit_0.
- Budget: net −40.

### Step 2 — Lexer per SPEC §1
- Spec: 1.2–1.8. Findings: A13, A14, A15①②③④, E7⑧.
- Files: `src/lex.py`, `main.py` (delete `remove_comment`), `src/AST/data_types.py`
  (String node: delete escape decoding).
- Method: comment rule `//[^\n]*` ignored in the lexer; `t_ignore = " \t\r"`;
  `TRUE|FALSE` and DATE rules get word boundaries; `t_ASSIGN = r"<-|←"`; CHAR regex
  requires exactly one character; STRING regex forbids raw LF (unterminated string =
  static error); fix the "fount" typo. `remove_comment` deleted from both file and REPL
  paths — line numbers now come from real source lines.
- Tests: lex/url_in_string ("http://x" prints intact), lex/backslash_verbatim
  (`C:\new` prints intact), lex/true_prefix_identifier (TRUEVALUE is a variable),
  lex/tab_between_tokens, lex/char_two_chars_error, lex/string_unterminated_error.
- Budget: net ±0 (about −25 in main.py, +20 in lex.py).

### Step 3 — Grammar rebuild: lines, precedence, headers
- Spec: 2.1–2.5, 3.1, 4.10, 8.2 (caret messages), 8.6. Findings: A1, A2, A3, A4, C1, C2,
  B5, D3, D5, E7② (stop committing parser.out), Pass-node label (E7④).
- Files: `src/parse.py`, `src/lex.py` (NEWLINE emitted as a token), `main.py` (REPL loop),
  `.gitignore` (+`parser.out`, `parsetab.py`; delete both from git).
- Method, in three commits:
  1. `NEWLINE` becomes a real token; grammar becomes line-oriented
     (`statements : statements NEWLINE statement | ...`); blocks consume interior
     newlines. Acceptance: `yacc.yacc()` reports ZERO conflicts (SPEC 2.5) — enforced by
     the runner: it rebuilds the parser with a capturing PLY errorlog and fails the whole
     suite if any conflict is reported.
  2. Precedence table exactly SPEC 3.1, comparisons nonassoc, `DOT`/index/call/deref as a
     postfix `primary` chain (this removes the need for precedence hacks on DOT).
     Bare-comparison statements become the static error of SPEC 4.10.
  3. Optional-parenthesis subroutine headers and calls (SPEC 2.4); CASE branches per
     SPEC 2.3 (`;` optional); delete the empty `SET`/`DEFINE` rules and reserved words;
     `p_error` gains source-line + caret formatting (uses the real source kept by step 2).
     REPL: continue only on end-of-input errors (SPEC 8.6); banner/prompts to stderr,
     suppressed when stdin is not a TTY.
- Tests: gram/and_or_precedence, gram/not_binds_before_and, gram/comparison_nonassoc_error,
  gram/one_statement_per_line_error (the old `a <- 5` / `- 3` gluing now a syntax error
  naming line 2), gram/dot_in_arithmetic (`p.x + p.y` = 7), gram/no_paren_procedure,
  gram/no_paren_function, gram/case_without_semicolon, gram/eq_statement_hint,
  repl/echo_expression, repl/error_reports_immediately.
- Budget: net +40 on parse.py (new forms) − removed dead rules; main.py −30.
- Risk note: this is the largest step; the three commits are independently green.

### Step 4 — One value model, one type-rule table
- Spec: 3.2–3.3, 4.1–4.2, 4.5–4.9, 5.4 (procedure-in-expression check lands here with the
  call-result model). Findings: A7, A8, A9, A11 (typed compare), A15⑤⑥ partly (STEP 0 check),
  C3, C4, C5, D8②③④, E2, E7⑤⑥.
- Files: new `src/values.py`; `src/AST/calc.py`, `cmp.py`, `logic.py` collapse into thin
  nodes; `src/data_types.py` (DATE holds `datetime.date`; set_value delegates to the
  assignment rule); `src/AST/io.py` (OUTPUT concatenation, REAL text form, INPUT parsing);
  `src/AST/program.py` (For/Range/A_case: STEP≠0 check, range compare by endpoints,
  IF/WHILE/REPEAT/CASE conditions must be BOOLEAN); `src/AST/array.py` (INTEGER-only
  index with bounds error).
- Method: `values.py` defines `Value(type, value)`, one operator table
  `binary(op, a, b) -> Value`, `unary(op, a)`, `check_assign(target_type, v)`,
  `parse_input(type, text)`, `to_text(v)`. Every arithmetic/comparison/logic node body
  becomes two evaluations plus one table call — the three files shrink from ~290 lines of
  copied classes to ~90. CASE range branches compare `lo <= v <= hi` (endpoints only).
  `Logic_or` gains the same short-circuit shape as `Logic_and`.
- Tests: types/real_plus_real_is_real (`5.0`), types/slash_always_real (`4.0`),
  types/div_mod_negative (`-3`, `-1` per SPEC 3.2), types/bool_arithmetic_error,
  types/narrowing_assign_error (REAL→INTEGER), types/input_boolean_false,
  types/input_integer_reject_text, types/date_chronological_compare,
  types/case_range_endpoints_fast (2000 iterations; the 10 s runner timeout is the
  performance assertion), types/output_no_separator, types/if_condition_must_be_boolean,
  loops/step_zero_error, arrays/real_index_error, arrays/out_of_bounds_message.
- Budget: net −120 (values.py +180; calc+cmp+logic −200; scattered −100).

### Step 5 — Scope, parameters, declaration rules
- Spec: 5.1–5.4, 4.3–4.4. Findings: A5, A6, B7, D7, D8①.
- Files: `src/stack.py`, `src/AST/function.py`, `src/AST/var.py`.
- Method: `get_variable`/`set_variable` search current frame → object space (only when
  executing a method) → global frame; nothing in between. BYVAL deep-copies ARRAY/record
  values (one `deep_copy` in values.py); BYREF arguments must be assignable targets, else
  runtime error; argument count/type mismatches produce the SPEC 5.2 message and stop
  before creating the frame (removes the `parameters`-unbound crash). Function fall-off →
  SPEC 5.3 error. Re-DECLARE / re-CONSTANT in same frame → error (REPL exempt per 4.4).
- Tests: scope/callee_cannot_read_caller_local, scope/callee_cannot_write_caller_local,
  scope/global_read_write, params/byval_array_isolated, params/byval_2d_isolated,
  params/byref_requires_variable_error, func/missing_return_error,
  func/procedure_in_expression_error, func/wrong_arg_count_message,
  vars/redeclare_error, vars/reconstant_error.
- Budget: net ±30.

### Step 6 — Built-ins: one registry, repaired functions
- Spec: §9. Findings: B1, B2, B3, B4 (RANDOM alias removed), B8, A15⑥.
- Files: `src/AST/insert_func.py` (rewritten), `src/parse.py` (only if the builtin-call
  hook needs adjusting).
- Method: one table `BUILTINS = {name: (arity_range, param_types, impl)}` and ONE generic
  argument checker; each impl is a plain function over `Value`s. This deletes ~25
  copy-pasted classes. TODAY/DAYINDEX return proper Values; RAND uses `random() * n`;
  SETDATE validates via the date type; LEFT/RIGHT/MID enforce SPEC §9 bounds; DIV/MOD
  functions reuse the step-4 operator table. User FUNCTION with a builtin name → static error.
- Tests: builtins/today_runs (asserts `DAY(TODAY()) >= 1` prints `TRUE`),
  builtins/dayindex_known_date, builtins/mid_bounds_error, builtins/left_negative_error,
  builtins/rand_in_range (comparisons print TRUE), builtins/setdate_invalid_error,
  builtins/user_function_shadow_error.
- Budget: net −300 (insert_func 660 → ~300, checker included).

### Step 7 — File I/O
- Spec: §7. Findings: A12, D6.
- Files: `src/AST/file.py`, `src/stack.py`.
- Method: WRITEFILE appends LF; READFILE reads one line into STRING targets only;
  RANDOM opens `r+b`/creates, SEEK honored by PUTRECORD/GETRECORD; OPENFILE failures are
  runtime errors; CLOSEFILE removes the table entry; end-of-run warning only for files
  still open.
- Tests: files/write_then_read_lines, files/append_mode, files/eof_loop,
  files/random_seek_put_get, files/open_missing_error, files/close_then_exit_silent.
- Budget: net ±25.

### Step 8 — Recursion depth
- Spec: 5.5. Findings: C6.
- Files: `src/AST/function.py`, `src/global_var.py`.
- Method: count pseudocode call depth in the interpreter (one integer on the stack object);
  entering a call past `recursion-limit` raises the SPEC 5.5 error. Set Python's own limit
  to `pseudocode_limit * measured_frames_per_call + margin` at startup (the factor is
  measured once during this step and recorded as a named constant with the measurement in
  a comment). RecursionError, if it still occurs, reports as an internal error (8.4).
- Tests: func/recursion_depth_1000_ok, func/recursion_limit_exceeded_message.
- Budget: net +25.

### Step 9 — Hermetic CLI and startup
- Spec: 8.8–8.11. Findings: E3, E4, E5, E6, E7①③⑦, A15 leftover (none), D2 leftover
  (message ordering is gone with batching).
- Files: `main.py`, `src/options.py`, `src/config.py`, `src/update.py`,
  `src/requirements.py`, `src/history.py`, `src/AST/program.py` (Import), `src/main.rs`
  (search order note only).
- Method: plain runs never touch the network, never prompt, never pip-install
  (`test_requirements` prints install instructions and exits 3 instead of running pip);
  update + integrity check move behind `cpc update` (integrity reset requires an explicit
  `--force` confirmation); state directory `$CPC_HOME` default `~/.cpc`, one-time
  migration from the install dir; config values keep case except enum-like keys;
  files run in argv order, each in fresh state (8.10); IMPORT keeps a per-run
  set of resolved paths — repeats are no-ops (8.11); `--migrate` uses `os.path.splitext`.
  Runner switches its env line from `CODESPACES=1` to `CPC_HOME=<tempdir>` (the planned
  one-line change from 1.2).
- Tests: cli/two_files_argv_order, cli/import_repeated_noop, cli/import_cycle_terminates,
  cli/fresh_state_between_files, cli/config_preserves_case, cli/no_files_written_to_cwd.
- Budget: net −60 (auto-update wiring leaves the hot path).

### Step 11 — Standalone packaging (added after plan approval, at the owner's request)
- Spec: 8.12–8.14 (added alongside this step). Problem: the interpreter can only run out
  of a git checkout of the whole project; installation means cloning the repository and
  putting `bin/` on PATH.
- Files: `src/` renamed to package `cpc/` (with root `main.py` kept as a thin
  backward-compatible shim so the existing `bin/` launchers keep working), new
  `pyproject.toml` with console entry point `cpc`, `README.md` installation section,
  `.github/workflows/tests.yml` (adds an install-and-run smoke job).
- Method: standard `pip`/`pipx` installation (`pipx install cpc-interpreter` from a git
  URL or sdist). Bundled scripts and version metadata become package data. PLY parser
  tables are never written into the installation directory: the parser is built at start
  and cached under the state directory (measured; rebuild cost is acceptable if caching
  proves unnecessary). Network-dependent packages (GitPython, requests) become an
  optional extra needed only by `cpc update`; `cpc update` detects a pip-managed install
  and prints the `pip install --upgrade` command instead of using git.
- Tests: existing suite runs against the shim (unchanged); CI gains one job that does
  `pip install .` and runs a smoke program via the installed `cpc` command.
- Budget: net +80 (pyproject + shim + path plumbing), mechanical rename excluded.
- Placed last: the rename touches every import line, so it lands after all behavioral
  work is complete and protected by the full suite.

### Step 10 — Feature completion on the stable core
Three independent sub-steps, each with its own commit and tests; explicitly last because
they are feature work, not repair.
- **10a Enums** (SPEC 4.8; finding A10): enum items as ordered constants; compare/assign/
  OUTPUT. Tests: enum/assign_compare_output, enum/cross_type_compare_error.
- **10b Inheritance** (SPEC 6.2; finding B6): `SUPER.NEW/Method` grammar + parent-chain
  method lookup. Tests: oop/super_new, oop/inherited_method_call, oop/private_from_outside_error.
- **10c Record value semantics** (SPEC 6.1): record assignment deep-copies.
  Tests: records/assign_copies_not_aliases.
- Budget: net +120 total.

---

## 3. Finding → step map (completeness check)

| Findings | Step |
|----------|------|
| E1 (no tests/CI) | 0 |
| D1 D2 D4 A11(policy) | 1 |
| A13 A14 A15①②③④ E7⑧ | 2 |
| A1 A2 A3 A4 C1 C2 B5 D3 D5 E7②④ | 3 |
| A7 A8 A9 A15⑤⑥ C3 C4 C5 D8②③④ E2 E7⑤⑥ A11(typed compare) | 4 |
| A5 A6 B7 D7 D8① | 5 |
| B1 B2 B3 B4 B8 | 6 |
| A12 D6 | 7 |
| C6 | 8 |
| E3 E4 E5 E6 E7①③⑦ | 9 |
| A10 B6 (+record semantics) | 10 |

Every finding from the review appears exactly once. C-group compliance gaps that are
*documentation* only (DIV/MOD negatives) are closed by SPEC 3.2 plus the step-4 tests.

## 4. Why this order cannot contradict itself

1. All steps implement one frozen document (R1); disagreements are resolved in the spec,
   not in code.
2. Baseline tests pin only kept behavior (1.4), and tests are append-only (R2), so a green
   suite at step N proves steps 0..N−1 still hold — the "no regression, no rework" proof
   is mechanical, not narrative.
3. Dependencies only point backwards: 1 (error channel) is used by every later error site;
   3 (grammar) decides which programs exist before 4–6 give them meaning; 4 (values) is
   consumed by 5–7; 10 builds on all of it. No step changes a decision an earlier step
   shipped.
