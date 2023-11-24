import copy

from enum import Enum
from intbase import InterpreterBase


# Enumerated type for our different language data types
class Type(Enum):
    INT = 1
    BOOL = 2
    STRING = 3
    CLOSURE = 4
    OBJECT = 5
    NIL = 6


class Closure:
    def __init__(self, func_ast, env):
        self.captured_env = copy.deepcopy(env)
        self.func_ast = func_ast
        self.type = Type.CLOSURE

class Object:
    def __init__(self, env):
        self.env = env
        self.fields = {}
        self.methods = {}
        self.proto = InterpreterBase.NIL_DEF
        self.type = Type.OBJECT

    def get_field(self, field_name):
        if field_name in self.fields:
            return self.fields[field_name]
        return None
    
    def set_field(self, field_name, value):
        self.fields[field_name] = value

    def get_method(self, method_name, num_args):
        if method_name in self.methods:
            if num_args in self.methods[method_name]:
                return self.methods[method_name][num_args]
            else:
                return None
        return None


# Represents a value, which has a type and its value
class Value:
    def __init__(self, t, v=None):
        self.t = t
        self.v = v

    def value(self):
        return self.v

    def type(self):
        return self.t

    def set(self, other):
        self.t = other.t
        self.v = other.v


def create_value(val):
    if val == InterpreterBase.TRUE_DEF:
        return Value(Type.BOOL, True)
    elif val == InterpreterBase.FALSE_DEF:
        return Value(Type.BOOL, False)
    elif isinstance(val, str):
        return Value(Type.STRING, val)
    elif isinstance(val, int):
        return Value(Type.INT, val)
    elif val == InterpreterBase.NIL_DEF:
        return Value(Type.NIL, None)
    else:
        raise ValueError("Unknown value type")


def get_printable(val):
    if val.type() == Type.INT:
        return str(val.value())
    if val.type() == Type.STRING:
        return val.value()
    if val.type() == Type.BOOL:
        if val.value() is True:
            return "true"
        return "false"
    return None