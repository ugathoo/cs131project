import copy

from enum import Enum
from intbase import InterpreterBase
from env_v4 import EnvironmentManager


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
        self.captured_env = EnvironmentManager()
        for environm in env.environment:
            enviro = {}
            for var_name, value in environm.items():
                if value.type() == Type.CLOSURE or value.type() == Type.OBJECT:
                    enviro[var_name] = value
                else:
                    enviro[var_name] = copy.deepcopy(value)
            self.captured_env.push(enviro)
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
        if self == None or self == InterpreterBase.NIL_DEF:
            return None
        
        print(self.fields.keys())
        print(field_name)
        if field_name in self.fields.keys():
            print("field name in fields")
            print(self.fields[field_name])
            return self.fields[field_name]
        else:
            if self.proto == InterpreterBase.NIL_DEF:
                return None
                
            return self.check_proto_field(field_name)
    
    def set_field(self, field_name, value):
        self.fields[field_name] = value

    def get_method(self, method_name, num_args):
        if self == None:
            return None
        if method_name in self.methods:
            if num_args in self.methods[method_name]:
                return self.methods[method_name][num_args] # returns a closure
            elif method_name in self.fields:
                return None
            else:
                return self.check_proto_method(method_name, num_args, self.proto)
        elif method_name in self.fields:
                return None
        return self.check_proto_method(method_name, num_args, self.proto)
    
    def set_method(self, method_name, num_args, value):
        if method_name not in self.methods:
            self.methods[method_name] = {}
        self.methods[method_name][num_args] = value    

    def get_proto(self):
        return self.proto
    
    def set_proto(self, proto):
        self.proto = proto

    def check_proto_method(self, method_name, num_args, proto):
        if proto == InterpreterBase.NIL_DEF:
            return None
        proto = proto.value()
        return proto.get_method(method_name, num_args)
    
    def check_proto_field(self, field_name):
        proto = self.get_proto()
        print("check proto field")
        print(proto)
        if proto == InterpreterBase.NIL_DEF:
            return None
    
        proto = proto.value()
        print("proto value")
        print(proto)
        if proto == InterpreterBase.NIL_DEF:
            return None

        print("proto get field")
        print(proto.get_field(field_name))
        thing = proto.get_field(field_name)
        if thing == None:
            print("thing is none")
            return None
        else:
            print("thing is not none")
            return thing

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