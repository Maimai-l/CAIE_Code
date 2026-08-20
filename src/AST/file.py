"""File statements (SPEC section 7). Text files are line-based: WRITEFILE
writes one line, READFILE reads one line, EOF looks one line ahead. RANDOM
mode is binary with an honest read/write handle, so SEEK really positions
PUTRECORD/GETRECORD."""
import os
import pickle

from .data import *
from ..AST_Base import *
from ..global_var import *
from .. import values


class OpenFile:
    """One open file: the OS handle, the cpc mode, and a one-line lookahead
    buffer that makes EOF() work on text files."""

    def __init__(self, handle, mode):
        self.handle = handle
        self.mode = mode  # READ / WRITE / APPEND / RANDOM
        self._peeked = None

    def read_line(self):
        if self._peeked is not None:
            line, self._peeked = self._peeked, None
        else:
            line = self.handle.readline()
        if line == '':
            return None  # past end of file
        return line.rstrip('\r\n')

    def at_eof(self):
        if self.mode == 'RANDOM':
            return self.handle.tell() >= os.fstat(self.handle.fileno()).st_size
        if self._peeked is not None:
            return False
        line = self.handle.readline()
        if line == '':
            return True
        self._peeked = line
        return False

    def close(self):
        self.handle.close()


def _path_of(node, expr):
    fp = expr.exe()
    if fp[1] != 'STRING':
        add_error_message(f'expect `STRING` for a file path, but found `{fp[1]}`', node)
    return fp[0]


class Open_file(AST_Node):
    def __init__(self, file_path, file_mode, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'OPENFILE'
        self.file_path = file_path
        self.file_mode = file_mode

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.file_path.get_tree(level+1) + '\n' + LEVEL_STR * (level+1) + str(self.file_mode)

    def exe(self):
        path = _path_of(self, self.file_path)
        try:
            if self.file_mode == 'READ':
                handle = open(path, 'r')
            elif self.file_mode == 'WRITE':
                handle = open(path, 'w')
            elif self.file_mode == 'APPEND':
                handle = open(path, 'a')
            else:  # RANDOM: read/write binary, created when missing (SPEC 7.1)
                handle = open(path, 'r+b') if os.path.exists(path) else open(path, 'w+b')
        except OSError as e:
            add_error_message(f'cannot open `{path}`: {e.strerror or e}', self)
        stack.add_file(path, OpenFile(handle, self.file_mode))


class Close_file(AST_Node):
    def __init__(self, file_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CLOSEFILE'
        self.file_path = file_path

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.file_path.get_tree(level+1)

    def exe(self):
        path = _path_of(self, self.file_path)
        stack.get_file(path).close()
        stack.forget_file(path)


class Read_file(AST_Node):
    def __init__(self, file_path, target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'READFILE'
        self.file_path = file_path
        self.target = target

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.file_path.get_tree(level+1) + '\n' + self.target.get_tree(level+1)

    def exe(self):
        path = _path_of(self, self.file_path)
        entry = stack.get_file(path)
        if entry.mode != 'READ':
            add_error_message(f'`{path}` is not open for READ', self)
        line = entry.read_line()
        if line is None:
            add_error_message(f'read past the end of `{path}`', self)
        target = self.target.exe()
        if target is None or isinstance(target, tuple):
            add_error_message('READFILE target must be a variable, array element or field', self)
        if target[1] != 'STRING':
            # SPEC 7.2: lines are text; parse them explicitly afterwards.
            add_error_message(f'READFILE target must be STRING, found `{target[1]}`', self)
        target.set_value(line)


class Write_file(AST_Node):
    def __init__(self, file_path, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'WRITEFILE'
        self.file_path = file_path
        self.value = value

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.file_path.get_tree(level+1) + '\n' + self.value.get_tree(level+1)

    def exe(self):
        path = _path_of(self, self.file_path)
        entry = stack.get_file(path)
        if entry.mode not in ('WRITE', 'APPEND'):
            add_error_message(f'`{path}` is not open for WRITE or APPEND', self)
        # SPEC 7.2: one value, one line.
        entry.handle.write(values.to_text(self.value.exe(), self) + '\n')


class Seek(AST_Node):
    def __init__(self, file_path, ad, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'SEEK'
        self.file_path = file_path
        self.ad = ad

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.file_path.get_tree(level+1) + '\n' + self.ad.get_tree(level+1)

    def exe(self):
        path = _path_of(self, self.file_path)
        ad = self.ad.exe()
        if ad[1] != 'INTEGER':
            add_error_message(f'expect `INTEGER` for an address, but found `{ad[1]}`', self)
        entry = stack.get_file(path)
        if entry.mode != 'RANDOM':
            add_error_message(f'SEEK needs `{path}` to be open FOR RANDOM', self)
        entry.handle.seek(ad[0])


class Get_record(AST_Node):
    def __init__(self, file_path, target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'GETRECORD'
        self.file_path = file_path
        self.target = target

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.file_path.get_tree(level+1) + '\n' + self.target.get_tree(level+1)

    def exe(self):
        path = _path_of(self, self.file_path)
        entry = stack.get_file(path)
        if entry.mode != 'RANDOM':
            add_error_message(f'GETRECORD needs `{path}` to be open FOR RANDOM', self)
        try:
            record = pickle.load(entry.handle)
        except (EOFError, pickle.UnpicklingError):
            add_error_message(f'no record at this position in `{path}`', self)
        target = self.target.exe()
        if target is None or isinstance(target, tuple):
            add_error_message('GETRECORD target must be a variable, array element or field', self)
        values.assign_to(target, record, self)


class Put_record(AST_Node):
    def __init__(self, file_path, record, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'PUTRECORD'
        self.file_path = file_path
        self.record = record

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.file_path.get_tree(level+1) + '\n' + self.record.get_tree(level+1)

    def exe(self):
        path = _path_of(self, self.file_path)
        entry = stack.get_file(path)
        if entry.mode != 'RANDOM':
            add_error_message(f'PUTRECORD needs `{path}` to be open FOR RANDOM', self)
        record = self.record.exe()
        if record is None:
            add_error_message('PUTRECORD needs a value', self)
        try:
            pickle.dump((record[0], record[1]), entry.handle)
            entry.handle.flush()
        except (pickle.PicklingError, TypeError):
            add_error_message('this value cannot be stored as a record', self)
