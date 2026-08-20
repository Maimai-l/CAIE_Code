"""Operator AST nodes. All typing rules live in src/values.py; these nodes
only evaluate operands and delegate (SPEC 3.2)."""
from .data import *
from ..AST_Base import *
from ..global_var import *
from .. import values


class BinOp(AST_Node):
    """Any binary operator except the short-circuiting AND/OR."""

    def __init__(self, op, left, right, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'BINOP'
        self.op = op
        self.left = left
        self.right = right

    def get_tree(self, level=0):
        return (LEVEL_STR * level + self.op + '\n'
                + self.left.get_tree(level+1) + '\n' + self.right.get_tree(level+1))

    def exe(self):
        return values.binary(self.op, self.left.exe(), self.right.exe(), self)


class Logic_and(AST_Node):
    def __init__(self, left, right, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'AND'
        self.left = left
        self.right = right

    def get_tree(self, level=0):
        return (LEVEL_STR * level + self.type + '\n'
                + self.left.get_tree(level+1) + '\n' + self.right.get_tree(level+1))

    def exe(self):
        # SPEC 3.2: AND short-circuits left to right.
        if not values.require_boolean(self.left.exe(), self, 'AND operand'):
            return (False, 'BOOLEAN')
        return (values.require_boolean(self.right.exe(), self, 'AND operand'), 'BOOLEAN')


class Logic_or(AST_Node):
    def __init__(self, left, right, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'OR'
        self.left = left
        self.right = right

    def get_tree(self, level=0):
        return (LEVEL_STR * level + self.type + '\n'
                + self.left.get_tree(level+1) + '\n' + self.right.get_tree(level+1))

    def exe(self):
        # SPEC 3.2: OR short-circuits left to right.
        if values.require_boolean(self.left.exe(), self, 'OR operand'):
            return (True, 'BOOLEAN')
        return (values.require_boolean(self.right.exe(), self, 'OR operand'), 'BOOLEAN')


class Logic_not(AST_Node):
    def __init__(self, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'NOT'
        self.value = value

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.value.get_tree(level+1)

    def exe(self):
        return (not values.require_boolean(self.value.exe(), self, 'NOT operand'), 'BOOLEAN')
