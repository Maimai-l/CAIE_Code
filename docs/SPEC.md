# cpc Language and Interpreter Specification

Status: DRAFT for review. Nothing is implemented from this document until it is approved.

This document is the single source of truth for observable behavior. Every fix step in
`docs/PLAN.md` implements clauses of this document and nothing else. If an implementation
needs to deviate, this document is amended and re-reviewed first.

Key words MUST, MUST NOT, MAY are used as in RFC 2119. "Static error" = detected before
execution (lexing/parsing); "runtime error" = detected during execution; "internal error" =
a defect of the interpreter itself, never the user's fault.

---

## 1. Source form

- **1.1 Encoding.** Source files MUST be UTF-8. If UTF-8 decoding fails, the interpreter MAY
  retry with a detected legacy encoding and MUST print a warning naming the encoding used.
- **1.2 Comments.** `//` starts a comment that runs to end of line. Comment recognition is
  performed by the lexer, so `//` inside a string or char literal is literal text.
- **1.3 Whitespace.** Space, tab, and CR separate tokens and are otherwise ignored.
  Line feed (LF) is significant: it terminates statements (3.1).
- **1.4 Identifiers.** `[A-Za-z_][A-Za-z0-9_]*`, case-sensitive. An identifier MUST NOT be a
  reserved word. Reserved words are recognized only as whole words: `TRUEX` is an identifier,
  not `TRUE` followed by `X`.
- **1.5 Removed reserved words.** `SET` and `DEFINE` are no longer reserved (the set-type
  feature is not implemented; see 10.4). `RANDOM` remains reserved (file mode only, 7.1);
  the random-number function is `RAND` only.

### 1.6 Literals

| Kind    | Form                                   | Notes |
|---------|----------------------------------------|-------|
| INTEGER | `[0-9]+`                               | |
| REAL    | `[0-9]*\.[0-9]+`                       | `.5` is legal and means `0.5` |
| CHAR    | `'x'` — exactly one character          | `''` and `'ab'` are static errors |
| STRING  | `"..."` on one line                    | MUST NOT contain a raw line feed |
| BOOLEAN | `TRUE` / `FALSE`                       | whole words only |
| DATE    | `dd/mm/yyyy` (2+2+4 digits)            | value MUST be a valid calendar date |

- **1.7 No escape sequences.** Backslash inside STRING/CHAR literals is a literal backslash.
  `"C:\new"` contains the characters `C : \ n e w`. There is no way to embed `"` in a string
  literal or `'` in a char literal in this version.
- **1.8 Assignment operator.** Exactly `<-` or `←`. `<--` is `<-` followed by unary minus
  applied to the right-hand side; `a <-- 5` therefore assigns `-5`.

---

## 2. Program structure

- **2.1 One statement per line.** A statement is terminated by end of line or end of file.
  A statement MUST NOT span multiple lines. Blank lines are ignored. Two statements MUST NOT
  share a line.
- **2.2 Block forms.** `IF/[ELSE]/ENDIF`, `CASE OF/ENDCASE`, `FOR/NEXT`, `WHILE [DO]/ENDWHILE`,
  `REPEAT/UNTIL`, `PROCEDURE/ENDPROCEDURE`, `FUNCTION/ENDFUNCTION`, `TYPE/ENDTYPE`,
  `CLASS/ENDCLASS`. Header and terminator each occupy their own line. `IF c THEN s ENDIF` on
  one line is NOT supported in v0.2 (compatibility break, accepted; the existing test files
  that use it are updated).
- **2.3 CASE branches.** One branch per line: `value : statement` where `value` is an
  expression or `lo TO hi`, plus at most one `OTHERWISE : statement`, which MUST be last.
  In v0.2 a branch holds exactly ONE statement (call a procedure when more is needed); this
  is what makes newline-terminated branches unambiguous. A trailing `;` after a branch is
  accepted and ignored (deprecated, kept so old cpc code still parses).
- **2.4 Subroutine headers.** Parentheses are OPTIONAL when there are no parameters, in both
  declaration and call: `PROCEDURE P`, `CALL P`, `FUNCTION F RETURNS INTEGER` are legal and
  equivalent to the `()` forms.
- **2.5 Grammar hygiene.** The generated parser MUST build with zero shift/reduce and zero
  reduce/reduce conflicts. This is a release gate, not advice.

---

## 3. Operators

### 3.1 Precedence, lowest to highest

| Level | Operators                            | Associativity |
|-------|--------------------------------------|---------------|
| 1     | `OR`                                 | left |
| 2     | `AND`                                | left |
| 3     | `NOT`                                | prefix |
| 4     | `= <> < <= > >=`                     | non-associative: `a < b < c` is a static error |
| 5     | `&`                                  | left |
| 6     | `+ -` (binary)                       | left |
| 7     | `* / DIV MOD`                        | left |
| 8     | unary `- +`                          | prefix |
| 9     | `.` member access, `[ ]` index, `( )` call, `^` deref | postfix, left |

### 3.2 Typing rules per operator

- `+ - *`: both operands numeric (INTEGER/REAL). Result INTEGER iff both operands INTEGER,
  else REAL. `2.5 + 2.5` is `5.0` (REAL). Any non-numeric operand: runtime error.
- `/`: both operands numeric; result is ALWAYS REAL (`8 / 2` is `4.0`).
- `DIV MOD`: both operands INTEGER only; divisor 0 is a runtime error. `DIV` truncates toward
  zero. `MOD` satisfies `a = (a DIV b) * b + (a MOD b)`, so its sign follows the dividend:
  `-7 DIV 2 = -3`, `-7 MOD 2 = -1`. (CAIE does not define negative operands; this definition
  is documented and deterministic.)
- `&`: both operands STRING or CHAR; result STRING.
- Comparisons `= <> < <= > >=`: legal operand pairs — both numeric (mixed INTEGER/REAL
  compares by value); both text (STRING/CHAR in any combination, code-point order — a CHAR
  compares against a one-character STRING, which exam code does constantly); both DATE
  (chronological); both BOOLEAN (`=` `<>` only); both the same enum type (declaration
  order). Result BOOLEAN. Any other pair: runtime error.
- `AND OR NOT`: BOOLEAN operands only; non-BOOLEAN operand is a runtime error. `AND` and `OR`
  MUST short-circuit left to right.
- **3.3 No implicit conversions** anywhere except INTEGER→REAL widening inside the numeric
  rules above and in assignment (4.2).

---

## 4. Types, variables, assignment

- **4.1 Base types and defaults.** `INTEGER 0`, `REAL 0.0`, `STRING ""`, `CHAR` the empty
  char `''` (prints as nothing), `BOOLEAN FALSE`, `DATE` the current date. A declared
  variable holds its default until assigned.
- **4.2 Assignment compatibility.** `target <- v` succeeds iff `v` has the target's type, or
  the target is REAL and `v` is INTEGER (widening). Everything else is a runtime error that
  names both types. In particular: REAL to INTEGER is an error (use `INT()` / `ROUND()`),
  STRING to CHAR is an error even for length 1, INTEGER to BOOLEAN is an error.
- **4.3 Assignable targets.** A variable, an array element, a record/class field, or a
  dereferenced pointer. Assigning to anything else (function call result, literal) is a
  static error where detectable, otherwise a runtime error.
- **4.4 DECLARE / CONSTANT.** Declaring a name that already exists in the same scope frame is
  a runtime error (both variable and constant). Assigning to a constant is a runtime error.
  Exception: in the interactive session (8.6) re-DECLARE replaces the variable.
- **4.5 INPUT.** Reads one line from standard input, trims trailing CR/LF, then parses by the
  target's declared type: INTEGER `[+-]?digits`; REAL a decimal number; BOOLEAN exactly
  `TRUE` or `FALSE` (case-insensitive); CHAR exactly one character; STRING the raw line.
  A parse failure is a runtime error naming the expected type and the offending text.
- **4.6 Arrays.** `ARRAY[l1:u1, ...] OF T` with INTEGER bounds, `l <= u` (else runtime error).
  Every index MUST be INTEGER (a REAL index is a runtime error, not silently dropped) and
  within bounds, else runtime error naming index, dimension, and bounds. An array literal
  `[a, b, c]` has homogeneous element type; it may be assigned to a one-dimensional array
  with the same element count; values fill from the target's lower bound.
- **4.7 DATE.** Internally a calendar date. `SETDATE(d, m, y)` validates and errors on
  impossible dates. Comparisons are chronological. Printing format is `dd/mm/yyyy`.
- **4.8 Enumerated types.** `TYPE Name = (A, B, C)` defines constants `Name.A` ... of type
  `Name` with ordinals 1, 2, 3. Enum values compare within their own type by ordinal,
  assign type-checked, and print as their item name.
- **4.9 OUTPUT.** `OUTPUT e1, e2, ...` converts each value to text and concatenates with NO
  separator, then one LF. `_OUTPUT` is identical without the LF. Text forms: INTEGER decimal;
  REAL decimal with at least one fraction digit (`4.0`, `0.25`), no exponent for magnitudes
  below 1e16; STRING/CHAR their characters (no quotes); BOOLEAN `TRUE`/`FALSE`; DATE 4.7;
  ARRAY `[v1, v2, ...]`; enum item name.
- **4.10 Bare expression statements.** In file mode, a statement consisting of a bare
  expression is legal ONLY when the expression is a call (function call or method call);
  the result is discarded. Any other bare expression is a static error: "statement has no
  effect" — with the hint "use <- for assignment" when its top operator is `=`. In the
  interactive session every bare expression is legal and its value is echoed in literal
  form (strings quoted).

---

## 5. Subroutines and scope

- **5.1 Lexical scope, two levels.** Name lookup inside a subroutine body searches, in
  order: (1) the subroutine's own parameters and locals, (2) — inside a method only — the
  owning object's fields and methods, (3) the global frame. Frames of the CALLING subroutine
  are NEVER searched, for reading or for writing. Using an undeclared name is a runtime
  error.
- **5.2 Parameter passing.** Default is BYVAL. BYVAL: the callee receives a copy; for ARRAY
  and record values a deep copy — mutations inside the callee are invisible to the caller.
  BYREF: the argument MUST be an assignable target (4.3), else runtime error; callee and
  caller share the variable. Argument count and each argument's type are checked at call
  time (4.2 rules); mismatch is a runtime error naming the subroutine, expected, and found.
- **5.3 FUNCTION return.** A FUNCTION MUST execute RETURN before its body ends; falling off
  the end is a runtime error "function F ended without RETURN". The returned value is
  checked against the declared RETURNS type by rule 4.2.
- **5.4 PROCEDURE has no value.** Using `CALL` on a FUNCTION discards its result and is
  legal. Using a PROCEDURE call inside an expression is a runtime error.
- **5.5 Recursion.** Supported to at least depth 1000 by default; the limit counts
  pseudocode calls and is configurable (`recursion-limit`). Exceeding it is a runtime error
  "recursion limit (N) exceeded", never a raw Python traceback.

---

## 6. Records, classes, pointers

- **6.1 Records** (`TYPE ... ENDTYPE`): composite values. Assignment between record
  variables copies the whole record (deep copy) — CAIE semantics. Field access via `.`.
- **6.2 Classes**: reference semantics. `NEW C(args)` runs constructor `NEW`; a class
  without a constructor cannot be instantiated with arguments. Method lookup searches the
  object's class, then its parent chain (INHERITS). `SUPER.NEW(args)` and
  `SUPER.Method(args)` are legal inside methods and bind to the parent class.
  PRIVATE members are accessible only from methods of the class (and subclasses).
- **6.3 Pointers**: `TYPE P = ^T` declares a pointer type; `^x` takes a reference to
  variable `x`; `p^` dereferences. A pointer variable holds a reference or is unset;
  dereferencing an unset pointer is a runtime error. (Kept minimal; full review in a later
  version.)

---

## 7. Files

- **7.1 Modes.** `READ` (file must exist), `WRITE` (create/truncate), `APPEND`,
  `RANDOM` (binary read/write, created if missing). Opening an already-open path, or using
  an unopened path, is a runtime error. Open failures (missing file, permission) are
  runtime errors naming the path.
- **7.2 Line I/O.** `WRITEFILE p, v` writes the text form of `v` (4.9) followed by one LF.
  `READFILE p, x` reads one line into `x`, which MUST be of type STRING. `EOF(p)` is TRUE
  iff no line remains.
- **7.3 Random access.** In RANDOM mode, `SEEK p, n` sets the position; `PUTRECORD` /
  `GETRECORD` write/read one record at the current position (record format is
  interpreter-specific and documented as such).
- **7.4 Close.** `CLOSEFILE p` closes and forgets the file; the same path may be reopened.
  Files still open at program end are closed with a warning on stderr (not an error).

---

## 8. Errors, exit codes, CLI

- **8.1 Streams.** Program `OUTPUT` goes to stdout and nothing else does. All diagnostics
  (errors, warnings, banner) go to stderr.
- **8.2 Static errors.** All are reported (capped at 20) before execution; the program is
  then NOT executed. Format: `FILE:LINE: syntax error: unexpected TOKEN` plus the source
  line and a `^` marker. Exit code 1.
- **8.3 Runtime errors.** Execution stops at the first one. Format:
  `FILE:LINE: error: MESSAGE`. Exit code 1.
- **8.4 Internal errors.** Any unexpected Python exception is reported as
  `internal error, please report: ...` with traceback, exit code 70. It is never presented
  as if the user's program were at fault.
- **8.5 Exit codes.** 0 success; 1 static or runtime error; 2 command-line usage error;
  70 internal error; 130 interrupted. `EXIT(n)` exits with code n.
- **8.6 Interactive session (REPL).** When stdin is not a terminal, the banner and prompts
  are suppressed. A line that parses executes immediately; continuation is requested only
  when the parser reports the input ended mid-construct; a complete-but-invalid line
  reports its syntax error immediately. A runtime error prints and the session continues.
- **8.7 Color.** ANSI color only when the stream is a terminal and `NO_COLOR` is unset.
- **8.8 Plain runs are hermetic.** `cpc file.cpc` performs no network access, no update
  check, no package installation, no interactive prompt, and writes nothing outside the
  user state directory. Updating and dependency install are explicit commands only.
- **8.9 User state.** Config, history, and packages live under `$CPC_HOME`
  (default `~/.cpc`), never in the installation directory. Config string values keep their
  case; only enum-like config values are case-normalized.
- **8.10 Multiple files.** `cpc a.cpc b.cpc` runs the files in argv order, each in a fresh
  interpreter state.
- **8.11 IMPORT.** Paths resolve relative to the importing file's directory, then the
  package directory. Each file is imported at most once per run; a repeated or circular
  import is a no-op. Imported files share the global frame (documented limitation).
- **8.12 Installation.** The interpreter is an installable Python package with a `cpc`
  console command; `pip install` / `pipx install` from a git URL or release archive is
  the supported path. Running from a git checkout (via the repository's `main.py`)
  remains supported for development.
- **8.13 No writes to the installation.** The interpreter MUST NOT write to its own
  installation directory at runtime (parser caches go to the state directory, 8.9).
- **8.14 Update under pip.** `cpc update` on a pip-managed installation prints the
  appropriate `pip install --upgrade` command instead of performing a git update; the
  git-based updater applies only to git checkouts. Network-using dependencies are
  optional and only required by `cpc update`.

---

## 9. Built-in functions

All argument counts and types are checked; violations are runtime errors via one shared
mechanism (no per-function ad-hoc messages). `s` STRING, `c` CHAR, `n x y` numeric.

| Function | Rule |
|----------|------|
| `LEFT(s, n)` / `RIGHT(s, n)` | `0 <= n <= LENGTH(s)`, else runtime error |
| `MID(s, start, len)` | `1 <= start`, `0 <= len`, `start+len-1 <= LENGTH(s)` |
| `LENGTH(s)` / `LENGTH(array)` | STRING length / element count of first dimension |
| `UCASE LCASE TO_UPPER TO_LOWER` | CHAR→CHAR, STRING→STRING |
| `INT(x)` | truncation toward zero, REAL→INTEGER (INTEGER passes through) |
| `REAL(x) STRING(x) CHAR(x) BOOLEAN(x)` | explicit conversions; failure = runtime error |
| `ROUND(x, places)` | REAL result; `ROUND(x)` = 0 places |
| `POW(x, y)` | numeric; result REAL |
| `RAND(n)` | `n` INTEGER > 0; uniform REAL in [0, n) — continuous, endpoint excluded |
| `DIV(a,b) MOD(a,b)` | function forms of the operators, identical semantics (3.2) |
| `SETDATE DAY MONTH YEAR DAYINDEX TODAY` | per 4.7; DAYINDEX: Sunday=1 |
| `EOF(path)` | per 7.2 |
| `EXIT(n)` | per 8.5 |
| `VARTYPE(v)` | type name as STRING (interpreter extension) |
| `PYTHON(code, ...)` | kept as documented extension; failures are runtime errors |

- **9.1** The name `RANDOM` is NOT a function (1.5). Built-in names cannot be redefined by
  user code; a user FUNCTION with a built-in's name is a static error.
- **9.2 Explicitly unsupported** (clean syntax error, listed in README): set types
  (`DEFINE`), one-line IF, multi-line statements.
