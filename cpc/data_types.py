"""Storage wrappers for variables. A wrapper holds a python value plus its
cpc type name and exposes the runtime pair protocol ([0] -> value,
[1] -> type name). Conversion/compatibility rules live in src/values.py;
set_value here stores what it is given (the assignment path has already
validated it), keeping declaration defaults per SPEC 4.1."""
import datetime

from . import values


class base:
    def __init__(self, name=None):
        self.name = name
        self.is_struct = False
        self.current_space = None
        self.is_const = False
        self.value = None
        self.is_enum = False

    def __str__(self):
        return str(self.value)

    def __getitem__(self, key):
        if key == 1:
            return self.type
        else:
            return self.value

    def set_value(self, new_value):
        self.value = new_value


class INTEGER(base):
    def __init__(self, value=0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = int(value)
        self.type = 'INTEGER'

    def __bool__(self):
        return bool(self.value)


class REAL(base):
    def __init__(self, value=0.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = float(value)
        self.type = 'REAL'

    def set_value(self, new_value):
        self.value = float(new_value)


class STRING(base):
    def __init__(self, value='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = str(value)
        self.type = 'STRING'

    def __str__(self):
        return '"' + self.value + '"'


class CHAR(base):
    def __init__(self, value='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = str(value)
        self.type = 'CHAR'

    def __str__(self):
        return "'" + self.value + "'"


class BOOLEAN(base):
    def __init__(self, value=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = bool(value)
        self.type = 'BOOLEAN'

    def __str__(self):
        return 'TRUE' if self.value else 'FALSE'


class DATE(base):
    def __init__(self, value=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # SPEC 4.1: the default is the current date, taken at declaration time.
        if value is None:
            self.value = datetime.date.today()
        elif isinstance(value, datetime.date):
            self.value = value
        else:
            self.value = values.parse_date(value)
        self.type = 'DATE'

    def set_value(self, new_value):
        if isinstance(new_value, datetime.date):
            self.value = new_value
        else:
            self.value = values.parse_date(new_value)

    def __str__(self):
        return values.date_text(self.value)


class ARRAY(base):
    def __init__(self, value=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = {} if value is None else value
        self.type = 'ARRAY'

    def __str__(self):
        return values.array_text(self.value)

    def __len__(self):
        return len(self.value) - 2  # minus the 'left'/'right' bound entries

    def _is_one_dimensional(self, d):
        return all(entry[1] != 'ARRAY' for key, entry in d.items()
                   if key not in ('left', 'right'))

    def set_value(self, new):
        from .error import CpcError
        if isinstance(new, ARRAY):
            new = new.value
        if not isinstance(new, dict):
            raise CpcError('cannot assign a non-array value to an array')
        if new.get('left') == self.value.get('left') and new.get('right') == self.value.get('right'):
            self.value = new
            return
        # SPEC 4.6: a one-dimensional array (e.g. a literal, always 1-based)
        # fills a one-dimensional target of equal element count from the
        # target's lower bound.
        if self._is_one_dimensional(new) and self._is_one_dimensional(self.value):
            source = [entry for key, entry in new.items() if key not in ('left', 'right')]
            left, right = self.value['left'], self.value['right']
            if len(source) == right - left + 1:
                for offset, entry in enumerate(source):
                    slot = self.value[left + offset]
                    # entry[0] is a storage wrapper exposing (value, type).
                    slot[0].set_value(values.check_assign(slot[1], entry[0]))
                return
        s_left, s_right = self.value.get('left'), self.value.get('right')
        raise CpcError(
            f"cannot assign an array with bounds `{new.get('left')}:{new.get('right')}`"
            f" to an array with bounds `{s_left}:{s_right}`")

    def to_target(self, target, v=None):
        from .AST.data import stack
        from .error import CpcError
        if v is None:
            v = self.value
        for i in v.keys():
            if i in ('left', 'right'):
                continue
            if v[i][1] == 'ARRAY':
                self.to_target(target, v[i][0].value if isinstance(v[i][0], ARRAY) else v[i][0])
            elif v[i][1] != target:
                try:
                    v[i] = (stack.structs[target](v[i][0]), target)
                except Exception:
                    raise CpcError(f'cannot convert `{v[i][0]}` into `{target}`')


def clone_wrapper(w):
    """Deep copy of a storage wrapper, for BYVAL parameters (SPEC 5.2).
    Records copy (SPEC 6.1); class instances keep reference semantics
    (SPEC 6.2)."""
    if isinstance(w, ARRAY):
        return ARRAY(_clone_array_dict(w.value), name=w.name)
    if getattr(w, 'is_record', False):
        return w.clone_record()
    if getattr(w, 'is_struct', False):
        return w  # class instances keep reference semantics (SPEC 6.2)
    if getattr(w, 'is_enum', False):
        return type(w)(w.value, name=w.name)
    return type(w)(w.value, name=w.name)


def _clone_array_dict(d):
    result = {}
    for key, entry in d.items():
        if key in ('left', 'right'):
            result[key] = entry
        else:
            result[key] = (clone_wrapper(entry[0]), entry[1])
    return result


class POINTER(base):
    def __init__(self, value=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = value
        self.type = 'POINTER'

    def solve_value(self):
        return self.value


class ANY(base):
    def __init__(self, value=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = value
        self.type = 'ANY'
