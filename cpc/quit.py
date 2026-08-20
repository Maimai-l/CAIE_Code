from .global_var import console
from .AST import stack
from sys import exit


def quit(code=0):
    stack.close_all_files()
    console.postloop()
    exit(code)
