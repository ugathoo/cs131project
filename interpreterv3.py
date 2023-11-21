import copy
from enum import Enum

from brewparse import parse_program
from env_v3 import EnvironmentManager
from intbase import InterpreterBase, ErrorType
from element import Element
from type_valuev3 import Type, Value, LambdaFunc, create_value, get_printable


class ExecStatus(Enum):
    CONTINUE = 1
    RETURN = 2


# Main interpreter class
class Interpreter(InterpreterBase):
    # constants
    NIL_VALUE = create_value(InterpreterBase.NIL_DEF)
    TRUE_VALUE = create_value(InterpreterBase.TRUE_DEF)
    BIN_OPS = {"+", "-", "*", "/", "==", "!=", ">", ">=", "<", "<=", "||", "&&"}

    # methods
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)
        self.trace_output = trace_output
        self.__setup_ops()

    # run a program that's provided in a string
    # usese the provided Parser found in brewparse.py to parse the program
    # into an abstract syntax tree (ast)
    def run(self, program):
        ast = parse_program(program)
        self.__set_up_function_table(ast)
        self.env = EnvironmentManager()
        main_func = self.__get_func_by_name("main", 0)
        self.__run_statements(main_func.get("statements"))

    def __set_up_function_table(self, ast):
        self.func_name_to_ast = {}
        for func_def in ast.get("functions"):
            func_name = func_def.get("name")
            num_params = len(func_def.get("args"))
            if func_name not in self.func_name_to_ast:
                self.func_name_to_ast[func_name] = {}
            self.func_name_to_ast[func_name][num_params] = func_def

    def __get_func_by_name(self, name, num_params):
        if name not in self.func_name_to_ast:
            for enviro in reversed(self.env.environment):
                if enviro.get(name) is not None:
                    #ITS A LAMBDA
                    return enviro.get("name")
            
            super().error(ErrorType.NAME_ERROR, f"Function {name} not found")
        candidate_funcs = self.func_name_to_ast[name]
        if num_params not in candidate_funcs:
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {name} taking {num_params} params not found",
            )
        return candidate_funcs[num_params]

    def __run_statements(self, statements):
        self.env.push()
        for statement in statements:
            if self.trace_output:
                print(statement)
            status = ExecStatus.CONTINUE
            if statement.elem_type == InterpreterBase.FCALL_DEF:
                self.__call_func(statement)
            elif statement.elem_type == "=":
                self.__assign(statement)
            elif statement.elem_type == InterpreterBase.RETURN_DEF:
                status, return_val = self.__do_return(statement)
            elif statement.elem_type == Interpreter.IF_DEF:
                status, return_val = self.__do_if(statement)
            elif statement.elem_type == Interpreter.WHILE_DEF:
                status, return_val = self.__do_while(statement)
            elif statement.elem_type == InterpreterBase.LAMBDA_DEF:
                status, return_val = self.__call_func(statement)
            if status == ExecStatus.RETURN:
                self.env.pop()
                return (status, return_val)

        self.env.pop()
        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __call_func(self, call_node):
        is_lambda = False
        func_name = call_node.get("name")
        
        if func_name == "print":
            return self.__call_print(call_node)
        if func_name == "inputi":
            return self.__call_input(call_node)
        if func_name == "inputs":
            return self.__call_input(call_node)

        actual_args = call_node.get("args")
        ###LAMBDA IMPLEMENTATION################
        for enviro in reversed(self.env.environment):
            if enviro.get(func_name) != None:
                value_of_obj = enviro.get(func_name)
                if isinstance(value_of_obj, Element) or value_of_obj.type() == Type.LAMBDA:
                   
                    #print(value_of_obj.value().lambda_ast)
                    is_lambda = True
            
        if not is_lambda:
            func_ast = self.__get_func_by_name(func_name, len(actual_args))
        else:
            for enviro in reversed(self.env.environment):
                if enviro.get(func_name) != None:
                    func_ast = enviro.get(func_name).value().lambda_ast
        ###LAMBDA IMPLEMENTATION################

        formal_args = func_ast.get("args")
        if len(actual_args) != len(formal_args):
            super().error(
                ErrorType.TYPE_ERROR,
                f"Function {func_ast.get('name')} with {len(actual_args)} args not found",
            )
        
        if is_lambda:
            ennv = (self.env.get(func_name).value()).lambda_env
            self.env.push(dict_append=ennv)
        else:
            self.env.push()
        all_refs_list = []
        ref_to_val = {}
        var_to_ref = {}
        for formal_ast, actual_ast in zip(formal_args, actual_args):
            arg_name = formal_ast.get("name") #name of arg 
            result = copy.deepcopy(self.__eval_expr(actual_ast))
            if formal_ast.elem_type == "refarg":
                var_to_ref[actual_ast.get("name")] = arg_name
                all_refs_list.append(arg_name)

            self.env.create(arg_name, result)
        _, return_val = self.__run_statements(func_ast.get("statements"))

        for refarg in all_refs_list:
            ref_to_val[refarg] = self.env.get(refarg)

        self.env.pop()
        for var in var_to_ref.keys():
            value = var_to_ref[var]
            self.env.set(var, ref_to_val[value])

        return return_val

    def __call_print(self, call_ast):
        output = ""
        for arg in call_ast.get("args"):
            result = self.__eval_expr(arg)  # result is a Value object
            output = output + get_printable(result)
        super().output(output)
        return Interpreter.NIL_VALUE

    def __call_input(self, call_ast):
        args = call_ast.get("args")
        if args is not None and len(args) == 1:
            result = self.__eval_expr(args[0])
            super().output(get_printable(result))
        elif args is not None and len(args) > 1:
            super().error(
                ErrorType.NAME_ERROR, "No inputi() function that takes > 1 parameter"
            )
        inp = super().get_input()
        if call_ast.get("name") == "inputi":
            return Value(Type.INT, int(inp))
        if call_ast.get("name") == "inputs":
            return Value(Type.STRING, inp)

    def __assign(self, assign_ast):
        var_name = assign_ast.get("name")
        value_obj = self.__eval_expr(assign_ast.get("expression"), assign=True)
        
        #check if val obj is dict
        if isinstance(value_obj, dict):
            key1 = (list(value_obj.keys()))[0]
            num_args = len(value_obj[key1].get("args"))
            if len(self.func_name_to_ast[value_obj[key1].get("name")]) != 1:
                    super().error(ErrorType.NAME_ERROR, "Overloaded function can't be assigned to a variable")

            #add var_name to func ast
            self.func_name_to_ast[var_name] = {}
            self.func_name_to_ast[var_name][num_args] = value_obj[key1]
        
        if isinstance(value_obj, LambdaFunc):
            self.func_name_to_ast[var_name] = {}
            num_args = len(value_obj.lambda_ast.get("args"))
            self.func_name_to_ast[var_name][num_args] = Element("lambda", value_obj.lambda_ast)
        
        self.env.set(var_name, value_obj)

    def __eval_expr(self, expr_ast, assign=False):
        if expr_ast.elem_type == InterpreterBase.NIL_DEF:
            return Interpreter.NIL_VALUE
        if expr_ast.elem_type == InterpreterBase.INT_DEF:
            return Value(Type.INT, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.STRING_DEF:
            return Value(Type.STRING, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.BOOL_DEF:
            return Value(Type.BOOL, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.VAR_DEF:
            var_name = expr_ast.get("name")
            val = self.env.get(var_name)
            if var_name in self.func_name_to_ast.keys():
                if len(self.func_name_to_ast[var_name]) != 1:
                    super().error(ErrorType.NAME_ERROR, "Overloaded function can't be assigned to a variable")

                val = self.func_name_to_ast[var_name] #function def of var_name
            
            if val is None:
                super().error(ErrorType.NAME_ERROR, f"Variable {var_name} not found")
            return val
        if expr_ast.elem_type == InterpreterBase.FCALL_DEF:
            if assign:
                return expr_ast
            return self.__call_func(expr_ast)
        if expr_ast.elem_type in Interpreter.BIN_OPS:
            return self.__eval_op(expr_ast)
        if expr_ast.elem_type == Interpreter.NEG_DEF:
            return self.__eval_unary(expr_ast, Type.INT, lambda x: -1 * x)
        if expr_ast.elem_type == Interpreter.NOT_DEF:
            return self.__eval_unary(expr_ast, Type.BOOL, lambda x: not x)
        
        if expr_ast.elem_type == InterpreterBase.LAMBDA_DEF:
            enviro = copy.deepcopy(self.env)
            #curr_env = self.__flatten(enviro.environment)
            #print(curr_env)
            if assign:
                return Value(Type.LAMBDA, LambdaFunc(enviro, expr_ast))
            return self.__run_statements(expr_ast)
            

    def __flatten(self, d, prefix=""):
        res = {}
        separator = "_"
        for dictionary in d:
            for key, value in dictionary.items():
                if isinstance(value, dict):
                    res.update(self.__flatten(value, key + separator))
                else:
                    res[prefix + key] = value
        return res

    def __eval_op(self, arith_ast):
        left_value_obj = self.__eval_expr(arith_ast.get("op1"))
        right_value_obj = self.__eval_expr(arith_ast.get("op2"))

        #check for functions
        if isinstance(left_value_obj, dict) and isinstance(right_value_obj, dict):
            if arith_ast.elem_type == "==":
                if (left_value_obj[0].get("name")) == (right_value_obj[0].get("name")) and len(left_value_obj[0].get("args")) == len(right_value_obj[0].get("args")):
                    return Value(Type.BOOL, True)
                else:
                    return Value(Type.BOOL, False)
            elif arith_ast.elem_type == "!=":
                if (left_value_obj[0].get("name")) == (right_value_obj[0].get("name")) and len(left_value_obj[0].get("args")) == len(right_value_obj[0].get("args")):
                    return Value(Type.BOOL, False)
                else:
                    return Value(Type.BOOL, True)
            else:
                super().error(ErrorType.TYPE_ERROR, f"Invalid function operation")
        
        elif (isinstance(left_value_obj, dict) and not isinstance(right_value_obj, dict)) or (not isinstance(left_value_obj, dict) and isinstance(right_value_obj, dict)):
            if arith_ast.elem_type == "==":
                return Value(Type.BOOL, False) 
            elif arith_ast.elem_type == "!=":
                return Value(Type.BOOL, True)
            else:
                super().error(ErrorType.TYPE_ERROR, f"Invalid function operation")
        
        if not self.__compatible_types(
            arith_ast.elem_type, left_value_obj, right_value_obj
        ):
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible types for {arith_ast.elem_type} operation",
            )
        

        if arith_ast.elem_type not in self.op_to_lambda[left_value_obj.type()]:
            if arith_ast.elem_type not in self.op_to_lambda[right_value_obj.type()]:
                super().error(
                    ErrorType.TYPE_ERROR,
                    f"Incompatible operator {arith_ast.elem_type} for type {left_value_obj.type()}",
                )
       
        if arith_ast.elem_type in self.op_to_lambda[left_value_obj.type()]:
            f = self.op_to_lambda[left_value_obj.type()][arith_ast.elem_type]
        else:
            f = self.op_to_lambda[right_value_obj.type()][arith_ast.elem_type]
        
        return f(left_value_obj, right_value_obj)

    def __compatible_types(self, oper, obj1, obj2):
        # DOCUMENT: allow comparisons ==/!= of anything against anything
        if oper in ["==", "!="]:
            return True
        elif (obj1.type() == Type.BOOL and obj2.type() == Type.INT) or (obj2.type() == Type.BOOL and obj1.type() == Type.INT):
            return True
        return obj1.type() == obj2.type()

    def __eval_unary(self, arith_ast, t, f):
        value_obj = self.__eval_expr(arith_ast.get("op1"))
        if arith_ast.elem_type == "!" and value_obj.type() == Type.INT:
            if value_obj.value() == 0:
                value_obj = Value(Type.BOOL, True)
            else:
                value_obj = Value(Type.BOOL, False)
        
        if value_obj.type() != t:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible type for {arith_ast.elem_type} operation",
            )
        return Value(t, f(value_obj.value()))

    def __setup_ops(self):
        self.op_to_lambda = {}
        # set up operations on integers
        self.op_to_lambda[Type.INT] = {}
        self.op_to_lambda[Type.INT]["+"] = lambda x, y: Value(
            self.__do_coerce_int(x).type(), self.__do_coerce_int(x).value() + self.__do_coerce_int(y).value()
        )
        self.op_to_lambda[Type.INT]["-"] = lambda x, y: Value(
            self.__do_coerce_int(x).type(), self.__do_coerce_int(x).value() - self.__do_coerce_int(y).value()
        )
        self.op_to_lambda[Type.INT]["*"] = lambda x, y: Value(
            self.__do_coerce_int(x).type(), self.__do_coerce_int(x).value() * self.__do_coerce_int(y).value()
        )
        self.op_to_lambda[Type.INT]["/"] = lambda x, y: Value(
            self.__do_coerce_int(x).type(), self.__do_coerce_int(x).value() // self.__do_coerce_int(y).value()
        )
        self.op_to_lambda[Type.INT]["=="] = lambda x, y: Value(
            Type.BOOL, self.__do_coerce_int_bool(y,x).type() == self.__do_coerce_int_bool(x,y).type() and self.__do_coerce_int_bool(y,x).value() == self.__do_coerce_int_bool(x,y).value()
        )
        self.op_to_lambda[Type.INT]["!="] = lambda x, y: Value(
            Type.BOOL, self.__do_coerce_int_bool(y,x).type() != self.__do_coerce_int_bool(x,y).type() or self.__do_coerce_int_bool(y,x).value() != self.__do_coerce_int_bool(x,y).value()
        )
        self.op_to_lambda[Type.INT]["<"] = lambda x, y: Value(
            Type.BOOL, x.value() < y.value()
        )
        self.op_to_lambda[Type.INT]["<="] = lambda x, y: Value(
            Type.BOOL, x.value() <= y.value()
        )
        self.op_to_lambda[Type.INT][">"] = lambda x, y: Value(
            Type.BOOL, x.value() > y.value()
        )
        self.op_to_lambda[Type.INT][">="] = lambda x, y: Value(
            Type.BOOL, x.value() >= y.value()
        )

        #  set up operations on strings
        self.op_to_lambda[Type.STRING] = {}
        self.op_to_lambda[Type.STRING]["+"] = lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
        self.op_to_lambda[Type.STRING]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.STRING]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )

        #  set up operations on bools
        self.op_to_lambda[Type.BOOL] = {}
        self.op_to_lambda[Type.BOOL]["&&"] = lambda x, y: Value(
            self.__do_coerce_bool(x).type(),self.__do_coerce_bool(x).value() and self.__do_coerce_bool(y).value()
        )
        self.op_to_lambda[Type.BOOL]["||"] = lambda x, y: Value(
            self.__do_coerce_bool(x).type(), self.__do_coerce_bool(x).value() or self.__do_coerce_bool(y).value()
        )
        self.op_to_lambda[Type.BOOL]["=="] = lambda x, y: Value(
            Type.BOOL, self.__do_coerce_bool(x).type() == self.__do_coerce_bool(y).type() and self.__do_coerce_bool(x).value() == self.__do_coerce_bool(y).value()
        )
        self.op_to_lambda[Type.BOOL]["!="] = lambda x, y: Value(
            Type.BOOL, self.__do_coerce_bool(x).type() != self.__do_coerce_bool(y).type() or self.__do_coerce_bool(x).value() != self.__do_coerce_bool(y).value()
        )
        self.op_to_lambda[Type.BOOL]["+"] = lambda x,y : Value(
            Type.INT, self.__add_bools(x,y)
        )
        self.op_to_lambda[Type.BOOL]["-"] = lambda x,y : Value(
            Type.INT, self.__sub_bools(x,y)
        )
        self.op_to_lambda[Type.BOOL]["*"] = lambda x,y : Value(
            Type.INT, self.__mult_bools(x,y)
        )
        self.op_to_lambda[Type.BOOL]["/"] = lambda x,y : Value(
            Type.INT, self.__div_bools(x,y)
        )
        #  set up operations on nil
        self.op_to_lambda[Type.NIL] = {}
        self.op_to_lambda[Type.NIL]["=="] = lambda x, y: Value(
            Type.BOOL, x.type() == y.type() and x.value() == y.value()
        )
        self.op_to_lambda[Type.NIL]["!="] = lambda x, y: Value(
            Type.BOOL, x.type() != y.type() or x.value() != y.value()
        )

        self.op_to_lambda[Type.LAMBDA] = {}
        self.op_to_lambda[Type.LAMBDA]["=="] = lambda x,y : Value(
            Type.BOOL, self.__check_eq_lambda(x,y)
        )
        self.op_to_lambda[Type.LAMBDA]["!="] = lambda x,y : Value(
            Type.BOOL, not self.__check_eq_lambda(x,y)
        )

    def __do_if(self, if_ast):
        cond_ast = if_ast.get("condition")
        result = self.__eval_expr(cond_ast)
        if result.type() != Type.BOOL:
            #Integer type coercion
            if result.type() == Type.INT:
                if result.value() == 0:
                    result = Value(Type.BOOL, False)
                else:
                    result = Value(Type.BOOL, True)
            else:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible type for if condition",
                )
        if result.value():
            statements = if_ast.get("statements")
            status, return_val = self.__run_statements(statements)
            return (status, return_val)
        else:
            else_statements = if_ast.get("else_statements")
            if else_statements is not None:
                status, return_val = self.__run_statements(else_statements)
                return (status, return_val)

        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __do_while(self, while_ast):
        cond_ast = while_ast.get("condition")
        run_while = Interpreter.TRUE_VALUE
        while run_while.value():
            run_while = self.__eval_expr(cond_ast)
            if run_while.type() != Type.BOOL:
                #integer type coercion
                if run_while.type() == Type.INT:
                    if run_while.value() == 0:
                        run_while = Value(Type.BOOL, False)
                    else:
                        run_while = Value(Type.BOOL, True)
                else:
                    super().error(
                        ErrorType.TYPE_ERROR,
                        "Incompatible type for while condition",
                    )
            if run_while.value():
                statements = while_ast.get("statements")
                status, return_val = self.__run_statements(statements)
                if status == ExecStatus.RETURN:
                    return status, return_val

        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __do_return(self, return_ast):
        expr_ast = return_ast.get("expression")
        if expr_ast is None:
            return (ExecStatus.RETURN, Interpreter.NIL_VALUE)
        value_obj = copy.deepcopy(self.__eval_expr(expr_ast))
        return (ExecStatus.RETURN, value_obj)

    def __do_coerce_bool(self, result):
        if result.type() == Type.BOOL:
            return result
        elif result.type() == Type.INT:
            if result.value() == 0:
                return Value(Type.BOOL, False)
            else:
                return Value(Type.BOOL, True)
        else:
            return result
        
    def __do_coerce_int(self, result):
        if result.type() == Type.INT:
            return result
        elif result.type() == Type.BOOL:
            if result.value() == True or result.value() == InterpreterBase.TRUE_DEF:
                return Value(Type.INT, 1)
            else:
                return Value(Type.INT, 0)
        else:
            return result

    def __do_coerce_int_bool(self, x, y):
        if y.type() == Type.BOOL:
            return self.__do_coerce_bool(x)
        else:
            return x

    def __add_bools(self, x, y):
        if x.type() == Type.BOOL and y.type() == Type.BOOL:
            sum = self.__do_coerce_int(x).value() + self.__do_coerce_bool(y).value()
            return sum
        elif x.type() == Type.BOOL and y.type() == Type.INT:
            sum = y.value() + self.__do_coerce_bool(x).value()
            return sum
        elif y.type() == Type.BOOL and x.type() == Type.INT:
            sum = x.value() + self.__do_coerce_bool(y).value()
            return sum
        else:
            super().error(ErrorType.TYPE_ERROR)
    
    def __sub_bools(self, x, y):
        if x.type() == Type.BOOL and y.type() == Type.BOOL:
            sum = self.__do_coerce_int(x).value() - self.__do_coerce_bool(y).value()
            return sum

        elif x.type() == Type.BOOL and y.type() == Type.INT:
            sum = self.__do_coerce_bool(x).value() - y.value()
            return sum
        elif y.type() == Type.BOOL and x.type() == Type.INT:
            sum = x.value() - self.__do_coerce_bool(y).value()
            return sum
        else:
            super().error(ErrorType.TYPE_ERROR)

    def __mult_bools(self, x, y):
        if x.type() == Type.BOOL and y.type() == Type.BOOL:
            sum = self.__do_coerce_int(x).value() * self.__do_coerce_bool(y).value()
            return sum
        elif x.type() == Type.BOOL and y.type() == Type.INT:
            sum = self.__do_coerce_bool(x).value() * y.value()
            return sum
        elif y.type() == Type.BOOL and x.type() == Type.INT:
            sum = x.value() * self.__do_coerce_bool(y).value()
            return sum
        else:
            super().error(ErrorType.TYPE_ERROR)

    def __div_bools(self, x, y):
        if x.type() == Type.BOOL and y.type() == Type.BOOL:
            sum = self.__do_coerce_int(x).value() // self.__do_coerce_bool(y).value()
            return sum
        elif x.type() == Type.BOOL and y.type() == Type.INT:
            sum = self.__do_coerce_bool(x).value() // y.value()
            return sum
        elif y.type() == Type.BOOL and x.type() == Type.INT:
            sum = x.value() // self.__do_coerce_bool(y).value()
            return sum
        else:
            super().error(ErrorType.TYPE_ERROR)

    def __check_eq_lambda(self, x, y):
        if x.type() == y.type():
            if len(x.get("args")) == len(y.get("args")):
                for statementx, statementy in zip(x.get("statements"), y.get("statements")):
                    if statementx.elem_type != statementy.elem_type or statementx.dict != statementy.dict:
                        return False
                return True
            else:
                return False
        else:
            return False