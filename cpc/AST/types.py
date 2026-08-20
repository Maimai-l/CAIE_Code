from .data import *
from ..AST_Base import *
from ..global_var import *
from .var import *
from .array import *
from ..stack import Space
from ..data_types import base, POINTER
from .function import Call_function

class Enumerate_type(AST_Node):
    def __init__(self, id, enumerate_items, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = "ENUMERATE_TYPE"
        self.id = id
        self.items = enumerate_items

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + LEVEL_STR * (level+1) + str(self.id) + '\n' + self.items.get_tree(level+1)

    def exe(self):
        from .. import values as values_mod
        enum_name = self.id
        items = self.items.exe()
        values_mod.register_enum(enum_name, items)

        class e(base):
            """A variable of this enum type. Its value is the item ordinal,
            starting at 1 (SPEC 4.8); the default is the first item."""

            def __init__(self, value=1, name=enum_name, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.name = name
                self.type = enum_name
                self.items = items
                self.is_enum = True
                self.value = value if isinstance(value, int) else 1

            def set_value(self, value):
                if isinstance(value, int) and 1 <= value <= len(self.items):
                    self.value = value
                else:
                    add_error_message(f'invalid value `{value}` for enum `{self.type}`', self)

            def __str__(self):
                return self.items[self.value - 1]

        stack.add_struct(enum_name, e)
        # The type name itself resolves to an accessor object so that
        # `Season.Spring` works as member access.
        accessor = e(name=enum_name)
        accessor.is_const = True
        stack.current_space().new_variable(enum_name, accessor, True)

class Enumerate_items(AST_Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'ENUMERATE_ITEMS'
        self.items = []

    def add_item(self, id):
        self.items.append(id)

    def get_tree(self, level=0):
        result = LEVEL_STR * level + self.type
        for i in self.items:
            result += '\n' + LEVEL_STR * (level+1) + str(i)
        return result

    def exe(self):
        return self.items

class Composite_type(AST_Node):
    def __init__(self, id, body_expression, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'COMPOSITE_TYPE'
        self.id = id
        self.body = body_expression

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + LEVEL_STR * (level + 1) + str(self.id) + '\n' + self.body.get_tree(level+1)

    def exe(self):
        that = self

        class t(base):
            def __init__(self, name=that.id, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.name = name
                self.type = that.id
                self.body = that.body
                self.is_struct = True
                self.is_record = True
                self.space = Space(self.type, {}, {}, kind='object')
                stack.push_subspace(self.space)
                try:
                    self.body.exe()
                finally:
                    stack.pop_subspace()

            def clone_record(self):
                from ..data_types import clone_wrapper
                new = object.__new__(type(self))
                base.__init__(new, name=self.name)
                new.type = self.type
                new.body = self.body
                new.is_struct = True
                new.is_record = True
                new.space = Space(
                    self.type,
                    {key: (clone_wrapper(entry[0]), entry[1])
                     for key, entry in self.space.variables.items()},
                    self.space.functions,
                    kind='object')
                return new

            def __getitem__(self, i):
                if i == 1:
                    return self.type
                else:
                    return self

            def __str__(self):
                space = self.space
                s = self.type
                if space.variables:
                    str_variables = {}
                    for key, value in space.variables.items():
                        str_variables[str(key)] = str(value[0])
                    s += f' {str_variables}'
                if space.functions:
                    str_functions = {}
                    for key, value in space.functions.items():
                        str_functions[str(key)] = str(value)
                    s += f' {str_functions}'
                return s

            def set_value(self, value):
                # SPEC 6.1: record assignment copies the whole record.
                if getattr(value, 'type', None) == self.type:
                    self.space = value.clone_record().space
                else:
                    add_stack_error_message(
                        f'cannot assign `{getattr(value, "type", type(value).__name__)}` to `{self.type}`')

        stack.add_struct(self.id, t)

class Class(AST_Node):
    def __init__(self, id, body, inherit_id='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CLASS'
        self.id = id
        self.body = body
        self.inherit_id = inherit_id

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + self.id + '\n' + self.body.get_tree(level+1)

    def exe(self):
        that = self

        class c(base):
            def __init__(self, name=that.id, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.name = name
                self.type = that.id
                self.body = that.body
                self.is_struct = True
                if that.inherit_id:
                    if that.inherit_id in stack.structs:
                        inherit_obj = stack.structs[that.inherit_id]()
                    else:
                        add_stack_error_message(f'Cannot inherit from an unknown class: `{that.inherit_id}`')
                        return
                    self.space = Space(self.type, {'SELF': (self, False), 'SUPER': (inherit_obj, False)}, {}, kind='object', parent=inherit_obj.space)
                else:
                    self.space = Space(self.type, {'SELF': (self, False)}, {}, kind='object')
                stack.push_subspace(self.space)
                try:
                    self.body.exe()
                finally:
                    stack.pop_subspace()

            def _has_constructor(self):
                probe = self.space
                while probe is not None:
                    if 'NEW' in probe.functions:
                        return True
                    probe = probe.parent
                return False

            def load_init(self, param):
                # Constructor arguments are evaluated in the caller's scope
                # before the object space is pushed (SPEC 5.1).
                args = param.exe() if param else []
                if not self._has_constructor():
                    if args:
                        add_stack_error_message(
                            f'class `{self.type}` has no constructor NEW')
                    return
                stack.push_subspace(self.space)
                try:
                    Call_function('NEW', param).exe(pre_params=args)
                finally:
                    stack.pop_subspace()

            def __getitem__(self, key):
                if key == 1:
                    return self.type
                else:
                    return self

            def __str__(self):
                space = self.space
                s = self.type
                if space.variables:
                    str_variables = {}
                    for key, value in space.variables.items():
                        if key == 'SELF':
                            str_variables[str(key)] = 'SELF'
                        else:
                            str_variables[str(key)] = str(value[0])
                    s += f' {str_variables}'
                if space.functions:
                    str_functions = {}
                    for key, value in space.functions.items():
                        str_functions[str(key)] = str(value)
                    s += f' {str_functions}'
                return s

            def set_value(self, value):
                # 将对方的 subspace 设置为自己的
                if value.type == self.type:
                    self.space = value.space
                else:
                    add_stack_error_message(f'Cannot assign `{value.type}` to `{self.type}`')

        stack.add_struct(self.id, c)

class Class_expression(AST_Node):
    def __init__(self, id, param, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CLASS_EXPRESSION'
        self.id = id
        self.param = param

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + self.id + '\n' + self.param.get_tree(level+1)

    def exe(self):
        if self.id not in stack.structs:
            add_error_message(f'unknown class or type `{self.id}`', self)
        s = stack.structs[self.id](None)
        if not hasattr(s, 'load_init'):
            add_error_message(f'`{self.id}` is not a class', self)
        s.load_init(self.param)
        return s

class Composite_type_expression(AST_Node):
    def __init__(self, exp1, exp2, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'COMPOSITE_TYPE_EXPRESSION'
        self.exp1 = exp1
        self.exp2 = exp2

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.exp1.get_tree(level+1) + '\n' + self.exp2.get_tree(level+2)

    def exe(self):
        left = self.exp1.exe()
        if left is None:
            add_error_message('expression has no value (a procedure returns nothing)', self)
        # Variables arrive as storage wrappers, computed results as pairs.
        obj = left if not isinstance(left, tuple) else left[0]
        if not hasattr(obj, 'is_enum'):
            add_error_message(f'a `{left[1]}` value has no members', self)
        # Enum member access yields (ordinal, enum type) per SPEC 4.8.
        if obj.is_enum:
            item = getattr(self.exp2, 'id', None)
            if item in obj.items:
                return (obj.items.index(item) + 1, obj.type)
            add_error_message(f'`{item}` is not an item of enum `{obj.type}`', self)
        # Member access runs exp2 inside the object's space. Arguments and
        # indexes are evaluated FIRST, in the caller's scope, so that
        # obj.m(localVar) still sees the caller's locals (SPEC 5.1).
        from .function import Call_function
        pre = None
        if isinstance(self.exp2, Call_function) and self.exp2.parameters:
            pre = self.exp2.parameters.exe()
        elif isinstance(self.exp2, Array_get):
            pre = self.exp2.indexes.exe()
        stack.push_subspace(obj.space)
        try:
            if isinstance(self.exp2, Call_function):
                v = self.exp2.exe(pre_params=pre if pre is not None else [])
            elif isinstance(self.exp2, Array_get):
                v = self.exp2.exe(pre_indexes=pre)
            else:
                v = self.exp2.exe()
        finally:
            stack.pop_subspace()
        return v

class Composite_type_statement(AST_Node):
    def __init__(self, exp, statement, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'COMPOSITE_TYPE_STATEMENT'
        self.exp = exp
        self.statement = statement

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.exp.get_tree(level+1) + '\n' + self.statement.get_tree(level+2)

    def exe(self):
        obj = self.exp.exe()
        # 判断一下是不是枚举类型
        if obj[1] == 'ENUM':
            return (obj[0].__members__[self.id], 'ENUM')
        # 否则，按照正常自定义类型的操作运行
        # 将此对象的空间放入主空间列表
        stack.push_subspace(obj.space)
        # 获取变量的值
        self.statement.exe()
        # 将空间放回子空间列表
        stack.pop_subspace()

class TypePointerStatement(AST_Node):
    def __init__(self, new_id, old_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'TYPE_POINTER_STATEMENT'
        self.new_id = new_id
        self.old_id = old_id

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + LEVEL_STR * (level+1) + str(self.old_id) + ' ' + str(self.new_id)

    def exe(self):
        stack.add_struct(self.new_id, stack.structs[self.old_id])

class PointerStatement(AST_Node):
    def __init__(self, new_id, id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'POINTER_STATEMENT'
        self.id = id
        self.new_id = new_id

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + LEVEL_STR * (level+1) + str(self.id) + ' ' + str(self.new_id)

    def exe(self):
        v = stack.get_variable(self.id)
        stack.force_set_variable(self.new_id, v, v[1])

class Pointer(AST_Node):
    def __init__(self, item, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'POINTER'
        self.item = item

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.item.get_tree(level+1)

    def exe(self):
        try:
            return POINTER(self.item.exe())
        except:
            add_error_message(f'Cannot create pointer for `{self.item}`', self)

class SolvePointer(AST_Node):
    def __init__(self, pointer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'SOLVE_POINTER'
        self.pointer = pointer

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.pointer.get_tree(level+1)

    def exe(self):
        try:
            return self.pointer.solve_value()
        except:
            add_error_message(f'Cannot solve pointer `{self.item}`', self)
