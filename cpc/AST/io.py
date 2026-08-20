from .data import *
from ..AST_Base import *
from ..global_var import *
from .. import values
from .array import *
from .data_types import *

class Output(AST_Node):
    def __init__(self, value, end="\n", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'OUTPUT'
        self.value = value
        self.end = end

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.value.get_tree(level+1)

    def exe(self):
        v = self.value.exe()
        print_(v, end=self.end)

class Output_expression(AST_Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'OUTPUT_EXPRESSION'
        self.expressions = []

    def get_tree(self, level=0):
        r = LEVEL_STR * level + self.type
        for i in self.expressions:
            r += '\n' + i.get_tree(level+1)
        return r

    def add_expression(self, expression):
        self.expressions.append(expression)

    def exe(self):
        # SPEC 4.9: values are concatenated with no separator.
        return ''.join(values.to_text(i.exe(), i) for i in self.expressions)

# class Input(AST_Node):
#     def __init__(self, id, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.type = 'INPUT'
#         self.id = id

#     def get_tree(self, level=0):
#         return LEVEL_STR * level + self.type + ' ' + str(self.id)

#     def exe(self):
#         stack.set_variable(self.id, str(input_()), 'STRING')

# class Array_input(AST_Node):
#     def __init__(self, id, indexes, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.type = 'ARRAY_INPUT'
#         self.id = id
#         self.indexes = indexes

#     def get_tree(self, level=0):
#         return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + self.indexes.get_tree(level+1)

#     def exe(self):
#         inp = input()
#         Array_assign(
#             self.id,
#             self.indexes,
#             String(inp, lineno=self.lineno, lexpos=self.lexpos),
#             lineno=self.lineno,
#             lexpos=self.lexpos
#         ).exe()

class Raw_output(AST_Node):
    def __init__(self, expression, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'RAW_OUTPUT'
        self.expression = expression

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.expression.get_tree(level+1)

    def exe(self):
        t = self.expression.exe()
        # File mode reaches here only for calls (SPEC 4.10): evaluate, discard.
        if get_running_mod() != 'file':
            text = values.echo_text(t)
            if text is not None:
                print_(text)

class NewInput(AST_Node):
    def __init__(self, expr, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'NEW_INPUT'
        self.expr = expr

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + str(self.id)

    def exe(self):
        target = self.expr.exe()
        if target is None or isinstance(target, tuple):
            add_error_message('INPUT target must be a variable, array element or field', self)
        data = input_()
        # SPEC 4.5: parse the line by the target's declared type.
        target.set_value(values.parse_input(target[1], data, self))
