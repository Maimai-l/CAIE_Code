from .global_var import *
from .data_types import *
from .history import HOME_PATH


# A Space holds names for one scope. kind is one of:
#   'global' - the single global frame
#   'frame'  - locals + parameters of one active subroutine call
#   'object' - the member space of a record/class instance
class Space:
    def __init__(self, name: str, variables: dict, functions: dict, kind='frame', parent=None):
        self.name = name
        self.variables = variables
        self.functions = functions
        self.kind = kind
        # For 'object' spaces of a class with INHERITS: the parent
        # instance's space, searched after this one (SPEC 6.2).
        self.parent = parent

    def __getitem__(self, index):
        if index == 0:
            return self.name
        elif index == 1:
            return self.variables
        elif index == 2:
            return self.functions
        else:
            raise IndexError(f'Invalid index `{index}` for space `{self.name}`')

    def new_variable(self, id, value, is_const):
        self.variables[id] = (value, is_const)

    def set_variable(self, id, value, type):
        if self.variables[id][1]:
            add_stack_error_message(f'cannot assign a value to constant `{id}`')
        self.variables[id][0].set_value(value)

    def force_set_variable(self, id, value, type):
        if self.variables[id][1]:
            add_stack_error_message(f'cannot assign a value to constant `{id}`')
        if self.variables[id][0][1] == type:
            self.variables[id] = (value, False)
        else:
            add_stack_error_message(f'cannot assign `{type}` pointer to `{self.variables[id][0][1]}`')

    def set_function(self, id, func):
        self.functions[id] = func


class Stack:
    def __init__(self) -> None:
        self.spaces = [Space('GLOBAL', {}, {}, kind='global')]
        self.files = {}  # {path: (file object, eof position, seek position)}
        self.structs = {
            'INTEGER': INTEGER,
            'REAL': REAL,
            'STRING': STRING,
            'CHAR': CHAR,
            'BOOLEAN': BOOLEAN,
            'DATE': DATE,
            'ARRAY': ARRAY,
            'ANY': ANY,
        }
        self.return_variables = None
        self.return_request = False
        self.call_depth = 0  # pseudocode calls currently active (SPEC 5.5)
        self._visible_cache = None  # invalidated on every push/pop
        home = STRING(HOME_PATH, name='__HOME__')
        home.is_const = True
        self.spaces[0].new_variable('__HOME__', home, True)

    def global_space(self):
        return self.spaces[-1]

    def current_space(self):
        return self.spaces[0]

    def visible_spaces(self):
        """Lexical visibility (SPEC 5.1). Caller frames are never visible.
        The result is cached until the space list changes.

        Two shapes occur at the top of the space list:
        - plain member access pushes object spaces: they see themselves
          (plus nested object spaces) and the global frame only;
        - a subroutine call pushes one frame; a method call pushes it on
          top of its object space: [frame, object, ...]. The frame sees
          itself, those object spaces, and the global frame.
        """
        if self._visible_cache is not None:
            return self._visible_cache

        def with_parents(space):
            chain = []
            while space is not None and space not in chain:
                chain.append(space)
                space = space.parent
            return chain

        visible = []
        i = 0
        while i < len(self.spaces) and self.spaces[i].kind == 'object':
            visible.extend(with_parents(self.spaces[i]))
            i += 1
        if not visible and i < len(self.spaces) and self.spaces[i].kind == 'frame':
            visible.append(self.spaces[i])
            i += 1
            while i < len(self.spaces) and self.spaces[i].kind == 'object':
                visible.extend(with_parents(self.spaces[i]))
                i += 1
        globe = self.global_space()
        if globe not in visible:
            visible.append(globe)
        self._visible_cache = visible
        return visible

    def _private_accessible(self, owner_space):
        # A private member is reachable from methods of its object or of a
        # subclass (SPEC 6.2), and always at global scope.
        if owner_space.kind == 'global':
            return True
        if self.spaces[0].kind != 'frame':
            return False
        for space in self.spaces:
            probe = space
            while probe is not None:
                if probe is owner_space:
                    return True
                probe = getattr(probe, 'parent', None)
        return False

    def get_variable(self, id):
        for space in self.visible_spaces():
            if id in space.variables:
                v = space.variables[id][0]
                if v.current_space is None or self._private_accessible(v.current_space):
                    return v
                add_stack_error_message(f'private variable `{id}` is not accessible')
        add_stack_error_message(f'no variable or constant named `{id}`')

    def new_variable(self, id, type, value=None):
        if type not in self.structs:
            add_stack_error_message(f'unknown type `{type}`')
        self.declare_check(id)
        if value is not None:
            self.spaces[0].new_variable(id, self.structs[type](name=id, value=value), False)
        else:
            self.spaces[0].new_variable(id, self.structs[type](name=id), False)

    def declare_check(self, id):
        # SPEC 4.4: re-declaring a name in the same scope is an error;
        # the interactive session may re-declare freely.
        if id in self.spaces[0].variables and get_running_mod() != 'line':
            add_stack_error_message(f'`{id}` is already declared')

    def ensure_loop_variable(self, id):
        """FOR creates its counter on first use and reuses it afterwards."""
        for space in self.visible_spaces():
            if id in space.variables:
                v = space.variables[id]
                if v[1]:
                    add_stack_error_message(f'cannot use constant `{id}` as a loop counter')
                if v[0][1] != 'INTEGER':
                    add_stack_error_message(f'loop counter `{id}` must be INTEGER, found `{v[0][1]}`')
                return
        self.spaces[0].new_variable(id, self.structs['INTEGER'](name=id), False)

    def new_constant(self, id, value):
        self.declare_check(id)
        if isinstance(value, tuple):
            clone = self.structs[value[1]](value[0]) if value[1] in self.structs else ANY(value[0])
        else:
            from copy import copy
            clone = copy(value)
        clone.is_const = True
        self.spaces[0].new_variable(id, clone, True)

    def set_variable(self, id, value, type):
        for space in self.visible_spaces():
            if id in space.variables:
                space.set_variable(id, value, type)
                return
        add_stack_error_message(f'no variable or constant named `{id}`')

    def force_set_variable(self, id, value, type):
        for space in self.visible_spaces():
            if id in space.variables:
                space.force_set_variable(id, value, type)
                return
        add_stack_error_message(f'no variable or constant named `{id}`')

    def remove_variable(self, id):
        for space in self.visible_spaces():
            if id in space.variables:
                del space.variables[id]
                return
        add_stack_error_message(f'no variable or constant named `{id}`')

    def pop_space(self):
        self.spaces.pop(0)
        self.return_request = False
        self._visible_cache = None

    def new_space(self, space_name, var_dict, func_dict):
        self.spaces.insert(0, Space(space_name, var_dict, func_dict, kind='frame'))
        self._visible_cache = None

    def set_return_variables(self, variables):
        self.return_variables = variables

    def get_return_variables(self):
        v = self.return_variables
        self.return_variables = None
        return v

    def add_function(self, function):
        self.current_space().set_function(function.id, function)

    def get_function(self, id):
        for space in self.visible_spaces():
            if id in space.functions:
                f = space.functions[id]
                if f.current_space is None or self._private_accessible(f.current_space):
                    return f
                add_stack_error_message(f'private function `{id}` is not accessible')
        add_stack_error_message(f'no procedure or function named `{id}`')

    def add_file(self, path, open_file):
        if path in self.files:
            add_stack_error_message(f'file `{path}` is already open')
        self.files[path] = open_file

    def get_file(self, path):
        if path in self.files:
            return self.files[path]
        add_stack_error_message(f'file `{path}` is not open')

    def forget_file(self, path):
        self.files.pop(path, None)

    def close_all_files(self):
        from .error import print_err
        # Only files the program left open warn here (SPEC 7.4).
        for path, entry in self.files.items():
            print_err(f'warning: program ended before closing file `{path}`')
            entry.close()
        self.files.clear()

    def add_struct(self, id, obj):
        self.structs[id] = obj

    def pop_subspace(self):
        self.spaces.pop(0)
        self._visible_cache = None

    def push_subspace(self, space):
        self.spaces.insert(0, space)
        self._visible_cache = None
