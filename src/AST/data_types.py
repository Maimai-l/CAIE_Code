from .data import *
from ..AST_Base import *
from ..global_var import *
from ..data_types import DATE

class Integer(AST_Node):
    def __init__(self, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'INTEGER'
        self.value = value

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + str(self.value)

    def exe(self):
        return (self.value, self.type)

class Real(AST_Node):
    def __init__(self, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'REAL'
        self.value = value

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + str(self.value)

    def exe(self):
        return (self.value, self.type)

class Char(AST_Node):
    def __init__(self, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CHAR'
        self.value = str(value)

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + "'" + str(self.value) + "'"

    def exe(self):
        return (self.value, self.type)

class String(AST_Node):
    def __init__(self, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'STRING'
        # SPEC 1.7: no escape sequences; a backslash is a literal character.
        self.value = str(value)

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + '"' + str(self.value) + '"'

    def exe(self):
        return (self.value, self.type)

class Boolean(AST_Node):
    def __init__(self, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'BOOLEAN'
        self.value = value

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + str(self.value)

    def exe(self):
        return (self.value, self.type)

class Date(AST_Node):
    def __init__(self, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'DATE'
        self.value = value

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + self.value

    def exe(self):
        from .. import values
        # SPEC 1.6: a DATE literal must be a valid calendar date.
        return (values.parse_date(self.value, self), 'DATE')
