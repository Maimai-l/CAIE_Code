"""Grammar for cpc pseudocode (docs/SPEC.md sections 2-4).

Shape of the grammar:
- The program is line-oriented: NEWLINE is a real token and the only statement
  separator (SPEC 2.1). Consecutive newlines arrive as one token, so blank
  lines need no special rules.
- Binary/unary operators use the precedence table below, which mirrors the
  table in SPEC 3.1 exactly.
- Member access, indexing, calls and pointer dereference are a postfix chain
  (SPEC 3.1 level 9), not precedence hacks, so `p.x + p.y` parses as
  `(p.x) + (p.y)`.
- The parser must build with zero conflicts; build_parser(strict=True) turns
  any conflict into a build failure and is run by the test suite (SPEC 2.5).
"""
import sys

from ply import yacc

from . import AST
from .AST.insert_func import *
from .global_var import *
from .error import *
from .AST_Base import *
from .lex import tokens

start = 'program'

# SPEC 3.1, lowest to highest. UMINUS/UPLUS are the unary +- pseudo-tokens.
precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('right', 'NOT'),
    ('nonassoc', 'LESS', 'GREATER', 'LESS_EQUAL', 'GREATER_EQUAL', 'EQUAL', 'NOT_EQUAL'),
    ('left', 'CONNECT'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'MUL', 'N_DIV', 'MOD', 'DIV'),
    ('right', 'UMINUS', 'UPLUS'),
)


def p_error(p):
    if p:
        add_parse_error_message(f'unexpected `{p.value}`', AST_Node(lineno=p.lineno, lexpos=p.lexpos))
    else:
        add_eof_error_message(AST_Node())


# --- program frame -----------------------------------------------------------

def p_program(p):
    """program : opt_nl
            | opt_nl statements opt_nl"""
    p[0] = p[2] if len(p) == 4 else None

def p_opt_nl(p):
    """opt_nl : NEWLINE
            | empty"""

def p_empty(p):
    """empty :"""

def p_statements(p):
    """statements : statements NEWLINE statement
            | statement"""
    if len(p) == 2:
        p[0] = AST.Statements(p=p)
        p[0].add_statement(p[1])
    else:
        p[1].add_statement(p[3])
        p[0] = p[1]

def p_statement(p):
    """statement : simple_statement
            | block_statement"""
    p[0] = p[1]

# Error recovery: an unparsable line is consumed up to its NEWLINE so several
# syntax errors can be reported in one run (SPEC 8.2). The Pass placeholder is
# never executed because collected syntax errors block execution.
def p_statement_error(p):
    """statement : error"""
    p[0] = AST.Pass(p=p)


# --- simple statements (one per line; also legal as a CASE branch body) ------

def p_delete_statement(p):
    """simple_statement : DELETE ID"""
    p[0] = AST.Delete(p[2], p=p)

def p_declare_statement(p):
    """simple_statement : DECLARE ids COLON ID
            | PUBLIC ids COLON ID"""
    p[0] = AST.MultiVariables(p[2], p[4], p=p)

def p_private_declare_statement(p):
    """simple_statement : PRIVATE ids COLON ID"""
    p[0] = AST.MultiVariables(p[2], p[4], private=True, p=p)

def p_multi_id_expression(p):
    """ids : ids COMMA ID
        | ID"""
    if len(p) == 2:
        p[0] = AST.Ids(p=p)
        p[0].add_id(p[1])
    else:
        p[1].add_id(p[3])
        p[0] = p[1]

def _array_declares(ids_node, dimensions, elem_type, private, p):
    """One Array node per declared name; several names share one line."""
    if len(ids_node.ids) == 1:
        return AST.Array(ids_node.ids[0], dimensions, elem_type, private=private, p=p)
    block = AST.Statements(p=p)
    for name in ids_node.ids:
        block.add_statement(AST.Array(name, dimensions, elem_type, private=private, p=p))
    return block

def p_array_declare_statement(p):
    """simple_statement : DECLARE ids COLON ARRAY LEFT_SQUARE dimensions RIGHT_SQUARE OF ID
            | PUBLIC ids COLON ARRAY LEFT_SQUARE dimensions RIGHT_SQUARE OF ID"""
    p[0] = _array_declares(p[2], p[6], p[9], False, p)

def p_private_array_declare_statement(p):
    """simple_statement : PRIVATE ids COLON ARRAY LEFT_SQUARE dimensions RIGHT_SQUARE OF ID"""
    p[0] = _array_declares(p[2], p[6], p[9], True, p)

def p_dimensions_expression(p):
    """dimensions : dimensions COMMA dimension
        | dimension"""
    if len(p) == 2:
        p[0] = AST.Dimensions(p=p)
        p[0].add_dimension(p[1])
    else:
        p[1].add_dimension(p[3])
        p[0] = p[1]

def p_dimension_expression(p):
    """dimension : expression COLON expression"""
    p[0] = AST.Dimension(p[1], p[3], p=p)

def p_const_declare_statement(p):
    """simple_statement : CONSTANT ID EQUAL expression
            | CONSTANT ID ASSIGN expression"""
    p[0] = AST.Constant(p[2], p[4], p=p)

def p_assign_statement(p):
    """simple_statement : postfix ASSIGN expression"""
    p[0] = AST.NewAssign(p[1], p[3], p=p)

def p_output_statement(p):
    """simple_statement : OUTPUT output_expression"""
    p[0] = AST.Output(p[2], p=p)

def p_no_end_output_statement(p):
    """simple_statement : _OUTPUT output_expression"""
    p[0] = AST.Output(p[2], end="", p=p)

def p_output_expression(p):
    """output_expression : output_expression COMMA expression
            | expression"""
    if len(p) == 2:
        p[0] = AST.Output_expression(p=p)
        p[0].add_expression(p[1])
    else:
        p[1].add_expression(p[3])
        p[0] = p[1]

def p_input_statement(p):
    """simple_statement : INPUT postfix"""
    p[0] = AST.NewInput(p[2], p=p)

def p_call_statement(p):
    """simple_statement : CALL postfix"""
    p[0] = AST.CallStatement(p[2], p=p)

def p_return_statement(p):
    """simple_statement : RETURN expression"""
    p[0] = AST.Return(p[2], p=p)

def p_pass_statement(p):
    """simple_statement : PASS"""
    p[0] = AST.Pass(p=p)

def p_import_statement(p):
    """simple_statement : IMPORT expression"""
    p[0] = AST.Import(p[2], p=p)

def _is_call(node):
    if isinstance(node, AST.Call_function) or type(node) in _builtin_classes:
        return True
    return (isinstance(node, AST.Composite_type_expression) and _is_call(node.exp2))

_builtin_classes = set(insert_functions.values())

def p_expression_statement(p):
    """simple_statement : expression"""
    # SPEC 4.10: in file mode a bare expression must be a call; in the
    # interactive session everything is legal and echoed.
    node = p[1]
    if get_running_mod() == 'file' and not _is_call(node):
        if isinstance(node, AST.BinOp) and node.op == '=':
            msg = 'statement has no effect (use <- for assignment)'
        else:
            msg = 'statement has no effect'
        add_parse_error_message(msg, node)
    p[0] = AST.Raw_output(node, p=p)


# --- file statements ---------------------------------------------------------

def p_openfile_statement(p):
    """simple_statement : OPENFILE expression FOR READ
            | OPENFILE expression FOR WRITE
            | OPENFILE expression FOR APPEND
            | OPENFILE expression FOR RANDOM"""
    p[0] = AST.Open_file(p[2], p[4], p=p)

def p_readfile_statement(p):
    """simple_statement : READFILE expression COMMA postfix"""
    p[0] = AST.Read_file(p[2], p[4], p=p)

def p_writefile_statement(p):
    """simple_statement : WRITEFILE expression COMMA expression"""
    p[0] = AST.Write_file(p[2], p[4], p=p)

def p_closefile_statement(p):
    """simple_statement : CLOSEFILE expression"""
    p[0] = AST.Close_file(p[2], p=p)

def p_seek_statement(p):
    """simple_statement : SEEK expression COMMA expression"""
    p[0] = AST.Seek(p[2], p[4], p=p)

def p_get_record_statement(p):
    """simple_statement : GETRECORD expression COMMA postfix"""
    p[0] = AST.Get_record(p[2], p[4], p=p)

def p_put_record_statement(p):
    """simple_statement : PUTRECORD expression COMMA expression"""
    p[0] = AST.Put_record(p[2], p[4], p=p)


# --- type definitions --------------------------------------------------------

def p_composite_type_statement(p):
    """block_statement : TYPE ID NEWLINE statements NEWLINE ENDTYPE"""
    p[0] = AST.Composite_type(p[2], p[4], p=p)

def p_enumerate_type_statement(p):
    """simple_statement : TYPE ID EQUAL LEFT_PAREN enumerate_items RIGHT_PAREN"""
    p[0] = AST.Enumerate_type(p[2], p[5], p=p)

def p_enumerate_items(p):
    """enumerate_items : enumerate_items COMMA ID
            | ID"""
    if len(p) == 2:
        p[0] = AST.Enumerate_items(p=p)
        p[0].add_item(p[1])
    else:
        p[1].add_item(p[3])
        p[0] = p[1]

def p_pointer_type_statement(p):
    """simple_statement : TYPE ID EQUAL POINTER ID"""
    p[0] = AST.TypePointerStatement(p[2], p[5], p=p)

def p_class_statement(p):
    """block_statement : CLASS ID NEWLINE statements NEWLINE ENDCLASS
            | CLASS ID INHERITS ID NEWLINE statements NEWLINE ENDCLASS"""
    if len(p) == 7:
        p[0] = AST.Class(p[2], p[4], p=p)
    else:
        p[0] = AST.Class(p[2], p[6], p[4], p=p)


# --- control-flow blocks -----------------------------------------------------

def p_if_statement(p):
    """block_statement : IF expression THEN NEWLINE statements NEWLINE ENDIF
            | IF expression THEN NEWLINE statements NEWLINE ELSE NEWLINE statements NEWLINE ENDIF"""
    if len(p) == 8:
        p[0] = AST.If(p[2], p[5], p=p)
    else:
        p[0] = AST.If(p[2], p[5], p[9], p=p)

def p_case_statement(p):
    """block_statement : CASE OF expression NEWLINE case_branches NEWLINE ENDCASE"""
    p[0] = AST.NewCase(p[3], p[5], p=p)

def p_case_branches(p):
    """case_branches : case_branches NEWLINE case_branch
            | case_branch"""
    if len(p) == 2:
        p[0] = AST.Cases(p=p)
        p[0].add_case(p[1])
    else:
        if p[1].otherwise is not None:
            # SPEC 2.3: OTHERWISE must be the last branch.
            add_parse_error_message('OTHERWISE must be the last CASE branch', p[3])
        p[1].add_case(p[3])
        p[0] = p[1]

def p_case_branch(p):
    """case_branch : case_label COLON simple_statement opt_semi
            | OTHERWISE COLON simple_statement opt_semi"""
    if p[1] == 'OTHERWISE':
        p[0] = AST.A_case(None, p[3], True, p=p)
    else:
        p[0] = AST.A_case(p[1], p[3], p=p)

def p_case_label(p):
    """case_label : expression TO expression
            | expression"""
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = AST.Range(p[1], p[3], p=p)

def p_opt_semi(p):
    """opt_semi : SEMICOLON
            | empty"""

def p_for_statement(p):
    """block_statement : FOR ID ASSIGN expression TO expression NEWLINE statements NEWLINE NEXT ID
            | FOR ID ASSIGN expression TO expression STEP expression NEWLINE statements NEWLINE NEXT ID"""
    if len(p) == 12:
        p[0] = AST.For(p[2], p[4], p[6], AST.Integer(1, p=p), p[8], p[11], p=p)
    else:
        p[0] = AST.For(p[2], p[4], p[6], p[8], p[10], p[13], p=p)

def p_while_statement(p):
    """block_statement : WHILE expression NEWLINE statements NEWLINE ENDWHILE
            | WHILE expression DO NEWLINE statements NEWLINE ENDWHILE"""
    if len(p) == 7:
        p[0] = AST.While(p[2], p[4], p=p)
    else:
        p[0] = AST.While(p[2], p[5], p=p)

def p_repeat_statement(p):
    """block_statement : REPEAT NEWLINE statements NEWLINE UNTIL expression"""
    p[0] = AST.Repeat(p[3], p[6], p=p)


# --- subroutine definitions --------------------------------------------------

def p_visibility(p):
    """visibility : PUBLIC
            | PRIVATE
            | empty"""
    p[0] = (p[1] == 'PRIVATE')

def p_subroutine_params(p):
    """subroutine_params : LEFT_PAREN declare_parameters RIGHT_PAREN
            | LEFT_PAREN RIGHT_PAREN
            | empty"""
    p[0] = p[2] if len(p) == 4 else None

def p_procedure_statement(p):
    """block_statement : visibility PROCEDURE ID subroutine_params NEWLINE statements NEWLINE ENDPROCEDURE
            | visibility PROCEDURE NEW subroutine_params NEWLINE statements NEWLINE ENDPROCEDURE"""
    p[0] = AST.Function(p[3], p[4], p[6], private=p[1], p=p)

def p_function_statement(p):
    """block_statement : visibility FUNCTION ID subroutine_params RETURNS ret_type NEWLINE statements NEWLINE ENDFUNCTION"""
    kind, type_name = p[6]
    if kind == 'ARR_OF':
        p[0] = AST.ArrFunction(p[3], p[4], type_name, p[8], private=p[1], p=p)
    else:
        p[0] = AST.Function(p[3], p[4], p[8], type_name, private=p[1], p=p)

def p_ret_type(p):
    """ret_type : ID
            | ARRAY
            | ARRAY OF ID"""
    if len(p) == 4:
        p[0] = ('ARR_OF', p[3])
    else:
        p[0] = ('PLAIN', p[1])

def p_declare_parameters(p):
    """declare_parameters : declare_parameters COMMA declare_parameter
            | declare_parameter"""
    if len(p) == 2:
        p[0] = AST.Declare_parameters(p=p)
        p[0].add_parameter(p[1])
    else:
        p[1].add_parameter(p[3])
        p[0] = p[1]

def p_declare_parameter(p):
    """declare_parameter : ID COLON ID
            | ID COLON ARRAY
            | BYREF ID COLON ID
            | BYREF ID COLON ARRAY
            | BYVAL ID COLON ID
            | BYVAL ID COLON ARRAY"""
    if len(p) == 4:
        p[0] = AST.Declare_parameter(p[1], p[3], p=p)
    elif p[1] == 'BYREF':
        p[0] = AST.Declare_parameter(p[2], p[4], True, p=p)
    else:
        p[0] = AST.Declare_parameter(p[2], p[4], False, p=p)

def p_declare_array_parameter(p):
    """declare_parameter : ID COLON ARRAY OF ID
            | BYREF ID COLON ARRAY OF ID
            | BYVAL ID COLON ARRAY OF ID"""
    if len(p) == 6:
        p[0] = AST.Declare_arr_parameter(p[1], p[5], p=p)
    elif p[1] == 'BYREF':
        p[0] = AST.Declare_arr_parameter(p[2], p[6], True, p=p)
    else:
        p[0] = AST.Declare_arr_parameter(p[2], p[6], False, p=p)

def p_new_declare_array_parameter(p):
    """declare_parameter : ID LEFT_SQUARE RIGHT_SQUARE COLON ID
            | BYREF ID LEFT_SQUARE RIGHT_SQUARE COLON ID
            | BYVAL ID LEFT_SQUARE RIGHT_SQUARE COLON ID"""
    if len(p) == 6:
        p[0] = AST.Declare_arr_parameter(p[1], p[5], p=p)
    elif p[1] == 'BYREF':
        p[0] = AST.Declare_arr_parameter(p[2], p[6], True, p=p)
    else:
        p[0] = AST.Declare_arr_parameter(p[2], p[6], False, p=p)

def p_parameters(p):
    """parameters : parameters COMMA expression
            | expression"""
    if len(p) == 2:
        p[0] = AST.Parameters(p=p)
        p[0].add_parameter(p[1])
    else:
        p[1].add_parameter(p[3])
        p[0] = p[1]


# --- expressions -------------------------------------------------------------

def p_binary_expression(p):
    """expression : expression OR expression
            | expression AND expression
            | expression EQUAL expression
            | expression NOT_EQUAL expression
            | expression LESS expression
            | expression GREATER expression
            | expression LESS_EQUAL expression
            | expression GREATER_EQUAL expression
            | expression CONNECT expression
            | expression PLUS expression
            | expression MINUS expression
            | expression MUL expression
            | expression N_DIV expression
            | expression MOD expression
            | expression DIV expression"""
    if p[2] == 'OR':
        p[0] = AST.Logic_or(p[1], p[3], p=p)
    elif p[2] == 'AND':
        p[0] = AST.Logic_and(p[1], p[3], p=p)
    else:
        p[0] = AST.BinOp(p[2], p[1], p[3], p=p)

def p_not_expression(p):
    """expression : NOT expression"""
    p[0] = AST.Logic_not(p[2], p=p)

def p_uminus_expression(p):
    """expression : MINUS expression %prec UMINUS"""
    p[0] = AST.BinOp('-', AST.Integer(0, p=p), p[2], p=p)

def p_uplus_expression(p):
    """expression : PLUS expression %prec UPLUS"""
    p[0] = AST.BinOp('+', AST.Integer(0, p=p), p[2], p=p)

def p_expression_postfix(p):
    """expression : postfix"""
    p[0] = p[1]


# --- postfix chain and primaries (SPEC 3.1 level 9) --------------------------

def p_postfix(p):
    """postfix : primary
            | postfix DOT member_ref
            | postfix POINTER"""
    if len(p) == 2:
        p[0] = p[1]
    elif p[2] == '.':
        p[0] = AST.Composite_type_expression(p[1], p[3], p=p)
    else:
        p[0] = AST.SolvePointer(p[1], p=p)

def _call_node(name, parameters, p):
    """A name used with (): a built-in when registered, else a user call."""
    if name in insert_functions:
        return insert_functions[name](parameters, p=p)
    return AST.Call_function(name, parameters, p=p) if parameters else AST.Call_function(name, p=p)

def p_member_ref(p):
    """member_ref : ID
            | ID LEFT_PAREN parameters RIGHT_PAREN
            | ID LEFT_PAREN RIGHT_PAREN
            | ID LEFT_SQUARE indexes RIGHT_SQUARE"""
    if len(p) == 2:
        p[0] = AST.Get(p[1], p=p)
    elif p[2] == '(':
        p[0] = _call_node(p[1], p[3] if len(p) == 5 else None, p)
    else:
        p[0] = AST.Array_get(p[1], p[3], p=p)

def p_indexes(p):
    """indexes : indexes COMMA expression
            | expression"""
    if len(p) == 2:
        p[0] = AST.Indexes(p=p)
        p[0].add_index(p[1])
    else:
        p[1].add_index(p[3])
        p[0] = p[1]

def p_primary_literal(p):
    """primary : INTEGER
            | REAL
            | CHAR
            | STRING
            | BOOLEAN
            | DATE"""
    if isinstance(p[1], bool):
        p[0] = AST.Boolean(p[1], p=p)
    elif isinstance(p[1], int):
        p[0] = AST.Integer(p[1], p=p)
    elif isinstance(p[1], float):
        p[0] = AST.Real(p[1], p=p)
    else:
        # Strings: the lexer token type distinguishes CHAR/STRING/DATE.
        kind = p.slice[1].type
        if kind == 'CHAR':
            p[0] = AST.Char(p[1], p=p)
        elif kind == 'DATE':
            p[0] = AST.Date(p[1], p=p)
        else:
            p[0] = AST.String(p[1], p=p)

def p_primary_id(p):
    """primary : ID"""
    p[0] = AST.Get(p[1], p=p)

def p_primary_call(p):
    """primary : ID LEFT_PAREN parameters RIGHT_PAREN
            | ID LEFT_PAREN RIGHT_PAREN
            | MOD LEFT_PAREN parameters RIGHT_PAREN
            | DIV LEFT_PAREN parameters RIGHT_PAREN"""
    p[0] = _call_node(p[1], p[3] if len(p) == 5 else None, p)

def p_primary_index(p):
    """primary : ID LEFT_SQUARE indexes RIGHT_SQUARE"""
    p[0] = AST.Array_get(p[1], p[3], p=p)

def p_primary_paren(p):
    """primary : LEFT_PAREN expression RIGHT_PAREN"""
    p[0] = p[2]

def p_primary_array_literal(p):
    """primary : LEFT_SQUARE array_items RIGHT_SQUARE
            | LEFT_SQUARE RIGHT_SQUARE"""
    if len(p) == 4:
        p[0] = AST.Array_expression(p[2], p=p)
    else:
        p[0] = AST.Array_expression(AST.Array_items(p=p), p=p)

def p_array_items(p):
    """array_items : array_items COMMA expression
            | expression"""
    if len(p) == 2:
        p[0] = AST.Array_items(p=p)
        p[0].add_item(p[1])
    else:
        p[1].add_item(p[3])
        p[0] = p[1]

def p_primary_new(p):
    """primary : NEW ID
            | NEW ID LEFT_PAREN parameters RIGHT_PAREN"""
    if len(p) == 3:
        p[0] = AST.Class_expression(p[2], None, p=p)
    else:
        p[0] = AST.Class_expression(p[2], p[4], p=p)

def p_primary_pointer(p):
    """primary : POINTER primary"""
    p[0] = AST.Pointer(p[2], p=p)


# --- parser construction -----------------------------------------------------

class _CollectingLogger:
    """Captures PLY grammar diagnostics so conflicts can be turned into errors."""

    def __init__(self):
        self.messages = []

    def _log(self, msg, *args):
        self.messages.append((msg % args) if args else str(msg))

    warning = _log
    error = _log
    info = _log
    debug = _log
    critical = _log


def build_parser(strict=False):
    """Build the parser without writing table files (SPEC 8.13).

    strict=True fails on any grammar conflict or error; the test suite runs
    this so the zero-conflict rule of SPEC 2.5 is enforced mechanically.
    """
    log = _CollectingLogger()
    # debug=True is required for PLY to report conflicts at all; NullLogger
    # keeps it from writing a parser.out file (SPEC 8.13).
    parser = yacc.yacc(
        module=sys.modules[__name__],
        debug=True,
        debuglog=yacc.NullLogger(),
        write_tables=False,
        errorlog=log,
    )
    problems = [m for m in log.messages if 'conflict' in m or 'error' in m.lower()]
    if strict and problems:
        raise RuntimeError('grammar is not clean:\n' + '\n'.join(problems))
    return parser
