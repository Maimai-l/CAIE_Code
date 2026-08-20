from .data import *
from ..AST_Base import *
from ..global_var import *
from ..error import CpcError

class Function(AST_Node):
    def __init__(self, id, parameters, statements, returns=None, private=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'FUNCTION'
        self.id = id
        self.private = private
        self.parameters = parameters
        self.statements = statements
        self.returns = returns
        self.arr_type = None
        self.current_space = None

    def get_tree(self, level=0):
        if self.parameters:
            return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + self.parameters.get_tree(level+1) + '\n' + LEVEL_STR * (level+1) + 'RETURNS ' + self.returns + '\n' + self.statements.get_tree(level+1) + '\n' + LEVEL_STR * (level+1) + str(self.private)
        else:
            return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + LEVEL_STR * (level+1) + 'RETURNS ' + self.returns + '\n' + self.statements.get_tree(level+1) + '\n' + LEVEL_STR * (level+1) + str(self.private)

    def exe(self):
        if self.private: self.current_space = stack.current_space()
        stack.add_function(self)

class ArrFunction(AST_Node):
    def __init__(self, id, parameters, arr_type, statements, private=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'FUNCTION'
        self.id = id
        self.private = private
        self.parameters = parameters
        self.statements = statements
        self.returns = 'ARRAY'
        self.arr_type = arr_type
        self.current_space = None

    def get_tree(self, level=0):
        if self.parameters:
            return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + self.parameters.get_tree(level+1) + '\n' + self.statements.get_tree(level+1) + '\n' + LEVEL_STR * (level+1) + str(self.private)
        else:
            return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + self.statements.get_tree(level+1) + '\n' + LEVEL_STR * (level+1) + str(self.private)

    def exe(self):
        if self.private: self.current_space = stack.current_space()
        stack.add_function(self)

class Call_function(AST_Node):
    def __init__(self, id, parameters=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CALL_FUNCTION'
        self.id = id
        self.parameters = parameters

    def get_tree(self, level=0):
        if self.parameters:
            return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + self.parameters.get_tree(level+1)
        else:
            return LEVEL_STR * level + self.type + ' ' + str(self.id)

    def _bind_parameter(self, name, ptype, byref, elem_type, arg):
        """Build the storage slot for one parameter (SPEC 5.2)."""
        from .. import values
        from ..data_types import clone_wrapper, ARRAY
        if byref:
            if arg is None or isinstance(arg, tuple):
                add_error_message(
                    f'BYREF parameter `{name}` needs a variable, array or field as argument', self)
            if ptype not in ('ANY',) and arg[1] != ptype:
                add_error_message(
                    f'BYREF parameter `{name}` expects `{ptype}`, found `{arg[1]}`', self)
            return arg
        if ptype == 'ARRAY':
            if arg is None or arg[1] != 'ARRAY':
                found = 'nothing' if arg is None else f'`{arg[1]}`'
                add_error_message(f'parameter `{name}` expects `ARRAY`, found {found}', self)
            cp = clone_wrapper(arg) if not isinstance(arg, tuple) else ARRAY(arg[0])
            if elem_type:
                cp.to_target(elem_type)
            return cp
        value = values.check_assign(ptype, arg, self)
        if ptype in ('INTEGER', 'REAL', 'STRING', 'CHAR', 'BOOLEAN', 'DATE', 'ANY'):
            return stack.structs[ptype](value)
        if ptype not in stack.structs:
            add_error_message(f'unknown parameter type `{ptype}`', self)
        # User-defined type: pass the instance (records copy in plan step 10c).
        if isinstance(arg, tuple):
            add_error_message(f'parameter `{name}` expects a `{ptype}` value', self)
        return arg

    def exe(self, pre_params=None):
        from .. import values
        function_obj = stack.get_function(self.id)
        if pre_params is not None:
            args = pre_params
        else:
            args = self.parameters.exe() if self.parameters else []
        target = function_obj.parameters.exe() if function_obj.parameters else []
        if len(args) != len(target):
            add_error_message(
                f'`{self.id}` expects {len(target)} parameter(s), but found {len(args)}', self)

        new_dict = {}
        for (name, ptype, byref, elem_type), arg in zip(target, args):
            try:
                new_dict[name] = (self._bind_parameter(name, ptype, byref, elem_type, arg), False)
            except CpcError as e:
                # Point the message at the call site.
                if e.lineno is None:
                    e.lineno = self.lineno or None
                raise

        stack.new_space(self.id, new_dict, {})
        stack.call_depth += 1
        try:
            function_obj.statements.exe()
            returns = stack.get_return_variables()
        finally:
            stack.call_depth -= 1
            stack.pop_space()

        if function_obj.returns:
            if returns is None:
                # SPEC 5.3: a FUNCTION must RETURN before its body ends.
                add_error_message(f'function `{self.id}` ended without RETURN', self)
            if function_obj.returns == 'ARRAY':
                if returns[1] != 'ARRAY':
                    add_error_message(
                        f'function `{self.id}` must return `ARRAY`, found `{returns[1]}`', self)
                if function_obj.arr_type:
                    returns.to_target(function_obj.arr_type)
                return returns
            if returns[1] == function_obj.returns:
                return returns
            value = values.check_assign(function_obj.returns, returns, self)
            return (value, function_obj.returns)
        if returns is not None:
            add_error_message(f'`{self.id}` is a procedure and cannot RETURN a value', self)
        return None

class CallStatement(AST_Node):
    """CALL <target>: target may be a call, a method call, or a bare name
    (SPEC 2.4 allows `CALL P` without parentheses)."""

    def __init__(self, target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CALL'
        self.target = target

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.target.get_tree(level+1)

    def exe(self):
        from .var import Get
        from .types import Composite_type_expression
        target = self.target
        if isinstance(target, Get):
            # Parenthesis-free procedure call (SPEC 2.4).
            Call_function(target.id, lineno=self.lineno, lexpos=self.lexpos).exe()
        elif isinstance(target, Composite_type_expression) or not isinstance(target, (Get,)) and hasattr(target, 'parameters'):
            # A direct call (user function or built-in) or a method call.
            target.exe()
        else:
            add_error_message('CALL expects a procedure name or call', self)


class Declare_parameter(AST_Node):
    def __init__(self, id, type, by_ref=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'DECLARE_PARAMETER'
        self.id = id
        self.var_type = type
        self.by_ref = by_ref

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + LEVEL_STR * (level+1) + str(self.var_type)

    def exe(self):
        return (self.id, self.var_type, self.by_ref, None)

class Declare_arr_parameter(AST_Node):
    def __init__(self, id, arr_type, by_ref=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'DECLARE_ARR_PARAMETER'
        self.id = id
        self.var_type = 'ARRAY'
        self.arr_type = arr_type
        self.by_ref = by_ref

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + LEVEL_STR * (level + 1) + str(self.var_type) + ' ' + str(self.arr_type)

    def exe(self):
        return (self.id, self.var_type, self.by_ref, self.arr_type)

class Declare_parameters(AST_Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'DECLARE_PARAMETERS'
        self.parameters = []

    def get_tree(self, level=0):
        result = LEVEL_STR * level + self.type + '\n'
        for i in self.parameters:
            result += i.get_tree(level+1) + '\n'
        return result[:-1]

    def add_parameter(self, parameter):
        self.parameters.append(parameter)

    def __len__(self):
        return len(self.parameters)

    def exe(self):
        result = []
        for i in self.parameters:
            v = i.exe()
            if v[2] == None:
                if len(result):
                    v = (v[0], v[1], result[-1][2], v[3])
                else:
                    v = (v[0], v[1], False, v[3])
            result.append(v)
        return result

class Parameters(AST_Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'PARAMETERS'
        self.parameters = []

    def get_tree(self, level=0):
        result = LEVEL_STR * level + self.type + '\n'
        for i in self.parameters:
            result += i.get_tree(level+1) + '\n'
        return result[:-1]

    def add_parameter(self, parameter):
        self.parameters.append(parameter)

    def __len__(self):
        return len(self.parameters)

    def exe(self):
        result = []
        for i in self.parameters:
            result.append(i.exe())
        return result

class Return(AST_Node):
    def __init__(self, expression, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'RETURN'
        self.expression = expression

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.expression.get_tree(level+1)

    def exe(self):
        if stack.call_depth == 0:
            add_error_message('RETURN outside a function or procedure', self)
        stack.set_return_variables(self.expression.exe())
        stack.return_request = True
