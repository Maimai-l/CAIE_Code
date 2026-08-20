from .data import *
from ..AST_Base import *
from ..global_var import *
from .array import *
from os import path as Path
from os import mkdir

class Statements(AST_Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'STATEMENTS'
        self.statements = []

    def add_statement(self, statement):
        self.statements.append(statement)

    def get_tree(self, level=0):
        result = []
        for statement in self.statements:
            result.append(str(statement.get_tree(level)))
        return '\n'.join(result)

    def exe(self):
        from ..error import CpcError
        for statement in self.statements:
            # A RETURN executed inside this block stops the whole block.
            if stack.return_request:
                break
            try:
                statement.exe()
            except CpcError as e:
                # Deep code may raise without position info; the innermost
                # statement wins, so an already-set lineno is kept.
                if e.lineno is None and statement.lineno:
                    e.lineno = statement.lineno
                raise

class If(AST_Node):
    def __init__(self, condition, true_statement, false_statement=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'IF'
        self.condition = condition
        self.true_statement = true_statement
        self.false_statement = false_statement

    def get_tree(self, level=0):
        result = LEVEL_STR * level
        result += 'IF\n' + self.condition.get_tree(level+1)
        result += '\n' + self.true_statement.get_tree(level+1)
        result += ( '\n' + LEVEL_STR * level + 'ELSE\n' + self.false_statement.get_tree(level+1) ) if self.false_statement else ''

        return result

    def exe(self):
        from .. import values
        if values.require_boolean(self.condition.exe(), self, 'IF condition'):
            self.true_statement.exe()
        elif self.false_statement:
            self.false_statement.exe()

class For(AST_Node):
    def __init__(self, id, left, right, step, body_statement, next_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'FOR'
        self.id = id
        self.left = left
        self.right = right
        self.step = step
        self.body_statement = body_statement
        self.next_id = next_id

    def get_tree(self, level=0):
        result = LEVEL_STR * level
        result += 'FOR ' + str(self.id)
        result += '\n' + self.left.get_tree(level+1) + '\n' + self.right.get_tree(level+1)
        result += '\n' + self.step.get_tree(level+1)
        result += '\n' + self.body_statement.get_tree(level+1)
        result += '\n' + LEVEL_STR * level + 'NEXT ' + str(self.next_id)

        return result

    def exe(self):
        left = self.left.exe()
        right = self.right.exe()
        step = self.step.exe()
        if left[1] == 'INTEGER' and right[1] == 'INTEGER' and step[1] == 'INTEGER':
            if step[0] == 0:
                add_error_message('FOR loop STEP must not be zero', self)
            if step[0] < 0:
                diff = -1
            else:
                diff = 1

            # 核对id是否相同
            if self.id != self.next_id:
                add_error_message(f'Expect `{self.id}` for next id, but found `{self.next_id}`', self)
                return

            # The counter is created on first use and reused when declared.
            stack.ensure_loop_variable(self.id)

            for i in range(left[0], right[0]+diff, step[0]):
                # 给 index 赋值
                stack.set_variable(self.id, i, 'INTEGER')
                # 执行内部操作
                self.body_statement.exe()

                # 检查是否有 return 需要退出
                if stack.return_request:
                    break

        else:
            add_error_message(f'FOR loop bounds and STEP must be INTEGER, found `{left[1]}`, `{right[1]}` and `{step[1]}`', self)

class Case(AST_Node):
    def __init__(self, id, cases, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CASE'
        self.id = id
        self.cases = cases

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + self.cases.get_tree(level+1)

    def exe(self):
        value = stack.get_variable(self.id)
        self.cases.exe(value)

class Case_array(AST_Node):
    def __init__(self, id, indexes, cases, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CASE_ARRAY'
        self.id = id
        self.indexes = indexes
        self.cases = cases

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + ' ' + str(self.id) + '\n' + self.indexes.get_tree(level+1) + '\n' + self.cases.get_tree(level+1)

    def exe(self):
        value = Array_get(self.id, self.indexes, lineno=self.lineno, lexpos=self.lexpos)
        self.cases.exe(value)

class NewCase(AST_Node):
    def __init__(self, expr, cases, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'NEW_CASE'
        self.expr = expr
        self.cases = cases

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.expr.get_tree(level+1) + '\n' + self.cases.get_tree(level+1)

    def exe(self):
        value = self.expr.exe()
        self.cases.exe(value)

class Cases(AST_Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'CASES'
        self.cases = []
        self.otherwise = None

    def get_tree(self, level=0):
        result = LEVEL_STR * level + self.type
        for i in self.cases:
            result += '\n' + i.get_tree(level+1)
        return result

    def add_case(self, case):
        if case.is_otherwise:
            self.otherwise = case
        else:
            self.cases.append(case)

    def exe(self, value):
        for case in self.cases:
            if case.check(value):
                case.exe()
                break
        else:
            if self.otherwise:
                self.otherwise.exe()

class A_case(AST_Node):
    def __init__(self, condition, true_statement, is_otherwise=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'A_CASE'
        self.condition = condition
        self.true_statement = true_statement
        self.is_otherwise = is_otherwise

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.condition.get_tree(level+1) + '\n' + self.true_statement.get_tree(level+1)

    def check(self, value):
        from .. import values
        if self.condition.type == 'RANGE':
            low, high = self.condition.bounds()
            return (values.binary('<=', low, value, self)[0]
                    and values.binary('<=', value, high, self)[0])
        return values.binary('=', value, self.condition.exe(), self)[0]

    def exe(self):
        self.true_statement.exe()

class Range(AST_Node):
    def __init__(self, start, end, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'RANGE'
        self.start = start
        self.end = end

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.start.get_tree(level+1) + '\n' + self.end.get_tree(level+1)

    def bounds(self):
        return self.start.exe(), self.end.exe()

class Repeat(AST_Node):
    def __init__(self, true_statement, condition, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'REPEAT'
        self.true_statement = true_statement
        self.condition = condition

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.true_statement.get_tree(level+1) + '\n' + self.condition.get_tree(level+1)

    def exe(self):
        from .. import values
        while 1:
            self.true_statement.exe()
            if stack.return_request:
                break
            if values.require_boolean(self.condition.exe(), self, 'UNTIL condition'):
                break

class While(AST_Node):
    def __init__(self, condition, true_statement, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'WHILE'
        self.condition = condition
        self.true_statement = true_statement

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.condition.get_tree(level+1) + '\n' + self.true_statement.get_tree(level+1)

    def exe(self):
        from .. import values
        while values.require_boolean(self.condition.exe(), self, 'WHILE condition'):
            self.true_statement.exe()
            if stack.return_request:
                break

class Pass(AST_Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'PASS'

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type

    def exe(self):
        return

class Import(AST_Node):
    def __init__(self, target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'IMPORT'
        self.target = target

    def get_tree(self, level=0):
        return LEVEL_STR * level + self.type + '\n' + self.target.get_tree(level+1)

    def exe(self):
        # 保存当前运行路径，以及类型
        last_file = get_running_path()
        last_mod = get_running_mod()
        # 获取要导入的路径
        default_package_path = config.get_config('default-package-path')
        if not Path.exists(default_package_path):
            mkdir(default_package_path)

        path = self.target.exe()[0]
        if Path.splitext(path)[1] != '.cpc':
            path += '.cpc'
        final_path = path
        # 尝试选择路径
        if Path.exists(Path.join(default_package_path, path)):
            final_path = Path.join(default_package_path, path)
        if Path.exists(path):
            final_path = path
        # 导入
        if Path.exists(final_path):
            # 运行导入程序
            from main import with_file
            with_file(final_path)
            # 修改回之前的路径，以及类型
            set_running_path(last_file)
            set_running_mod(last_mod)
        else:
            add_error_message(f'Cannot find `{final_path}` to import', self)
