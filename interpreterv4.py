import copy
from enum import Enum

from brewparse import parse_program
from env_v4 import EnvironmentManager
from intbase import InterpreterBase, ErrorType
from type_valuev4 import Object, Closure, Type, Value, create_value, get_printable


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
        self.__setup_ops() #dict of lambdas for each type

    # run a program that's provided in a string
    # usese the provided Parser found in brewparse.py to parse the program
    # into an abstract syntax tree (ast)
    def run(self, program):
        ast = parse_program(program) #AST nodes list
        self.__set_up_function_table(ast) #dict of function names to asts
        self.env = EnvironmentManager() #EnvironmentManager object that holds list of dicts
        main_func = self.__get_func_by_name("main", 0) #Closure object
        if main_func is None:
            super().error(ErrorType.NAME_ERROR, f"Function main not found")
        self.__run_statements(main_func.func_ast.get("statements")) #returns (status, return_val) of (Continue and NIL)

    def __set_up_function_table(self, ast):
        self.func_name_to_ast = {}
        empty_env = EnvironmentManager()
        for func_def in ast.get("functions"):
            func_name = func_def.get("name") #string
            num_params = len(func_def.get("args")) #int
            if func_name not in self.func_name_to_ast:
                self.func_name_to_ast[func_name] = {}
            self.func_name_to_ast[func_name][num_params] = Closure(func_def, empty_env)

    def __get_func_by_name(self, name, num_params):
        #NOT A PREDEFINED FUNCTION
        if name not in self.func_name_to_ast: 
            closure_val_obj = self.env.get(name) #Value object of (Type.CLOSURE, Closure object)
            if closure_val_obj is None:
                return None
                # super().error(ErrorType.NAME_ERROR, f"Function {name} not found")
            if closure_val_obj.type() != Type.CLOSURE:
                super().error(
                    ErrorType.TYPE_ERROR, "Trying to call function with non-closure"
                )
            closure = closure_val_obj.value() #Closure object
            num_formal_params = len(closure.func_ast.get("args")) #int
            if num_formal_params != num_params:
                super().error(ErrorType.TYPE_ERROR, "Invalid # of args to lambda")
            return closure_val_obj.value() #Closure object

        #PREDEFINED FUNCTION
        candidate_funcs = self.func_name_to_ast[name]
        if num_params is None:
            # case where we want assign variable to func_name and we don't have
            # a way to specify the # of arguments for the function, so we generate
            # an error if there's more than one function with that name
            if len(candidate_funcs) > 1:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Function {name} has multiple overloaded versions",
                )
            num_args = next(iter(candidate_funcs)) #int, first key of candidate_funcs
            closure = candidate_funcs[num_args] #Closure object
            return closure

        if num_params not in candidate_funcs:
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {name} taking {num_params} params not found",
            )
        return candidate_funcs[num_params] #Closure object

    def __run_statements(self, statements):
        self.env.push() #add empty dict to list of dicts
        for statement in statements:
            if self.trace_output:
                print(statement)
            status = ExecStatus.CONTINUE
            if statement.elem_type == InterpreterBase.FCALL_DEF:
                self.__call_func(statement) #returns Value object
            elif statement.elem_type == "=":
                self.__assign(statement) #returns Value object
            elif statement.elem_type == InterpreterBase.RETURN_DEF:
                status, return_val = self.__do_return(statement) #returns (status, return_val) of (Return and Value object)
            elif statement.elem_type == Interpreter.IF_DEF:
                status, return_val = self.__do_if(statement) #returns (status, return_val) of (Continue and NIL)
            elif statement.elem_type == Interpreter.WHILE_DEF:
                status, return_val = self.__do_while(statement) #returns (status, return_val) of (Continue and NIL)
            elif statement.elem_type == Interpreter.MCALL_DEF:
                self.__call_func(statement) #returns Value object
            if status == ExecStatus.RETURN:
                self.env.pop() #remove dict from list of dicts
                return (status, return_val)

        self.env.pop() #remove dict from list of dicts
        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)


    def __call_func(self, call_ast):
        is_method = (call_ast.elem_type == Interpreter.MCALL_DEF)
        if call_ast.elem_type == Interpreter.MCALL_DEF:
            print("hit")
            print(call_ast)
            object = call_ast.get("objref") #NEEDS TO RETURN A VALUE OBJECT
            print(object)
            obj = self.env.get(object) #Value object of (Type.OBJECT, Object object)
            print(obj)
            if obj is None:
                super().error(ErrorType.NAME_ERROR, f"Object {object} not found")
            
            if obj.type() != Type.OBJECT:
                super().error(
                    ErrorType.TYPE_ERROR, "Trying to call method on non-object"
                )
            obj = obj.value() #Object object
            print(obj)
            print(obj.methods)
            target_closure = obj.get_method(call_ast.get("name"), len(call_ast.get("args"))) #Closure object
            if target_closure is None:
                super().error(ErrorType.NAME_ERROR, f"Method {call_ast.get('name')} not found")
            
            print(type(target_closure))
        
        if not is_method:
            func_name = call_ast.get("name")
            if func_name == "print":
                return self.__call_print(call_ast) #returns Value object
            if func_name == "inputi":
                return self.__call_input(call_ast) #returns Value object
            if func_name == "inputs":
                return self.__call_input(call_ast) #returns Value object

        actual_args = call_ast.get("args") #list of arg or refarg nodes
        
        if not is_method:
            target_closure = self.__get_func_by_name(func_name, len(actual_args)) #Closure object
        
        if target_closure == None:
            super().error(ErrorType.NAME_ERROR, f"Function {func_name} not found")
        if target_closure.type != Type.CLOSURE:
            super().error(ErrorType.TYPE_ERROR, f"Function {func_name} is changed to non-function type.")
        
        
        target_ast = target_closure.func_ast #AST node of function definition

        new_env = {}
        self.__prepare_env_with_closed_variables(target_closure, new_env) #add closed variables to new_env
        self.__prepare_params(target_ast,call_ast, new_env)  #add parameters to new_env  
        self.env.push(new_env) #add new_env to list of dicts
        _, return_val = self.__run_statements(target_ast.get("statements")) #returns (status, return_val) of (Continue and NIL)
        self.env.pop() #remove new_env from list of dicts
        return return_val #Value object

    def __prepare_env_with_closed_variables(self, target_closure, temp_env): #NO RETURN VALUE
        for var_name, value in target_closure.captured_env:
            # Updated here - ignore updates to the scope if we
            #   altered a parameter, or if the argument is a similarly named variable
            temp_env[var_name] = value


    def __prepare_params(self, target_ast, call_ast, temp_env): #NO RETURN VALUE
        actual_args = call_ast.get("args")
        formal_args = target_ast.get("args")
        if len(actual_args) != len(formal_args):
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {target_ast.get('name')} with {len(actual_args)} args not found",
            )

        for formal_ast, actual_ast in zip(formal_args, actual_args):
            if formal_ast.elem_type == InterpreterBase.REFARG_DEF:
                result = self.__eval_expr(actual_ast)
            else:
                result = copy.deepcopy(self.__eval_expr(actual_ast))
            arg_name = formal_ast.get("name")
            temp_env[arg_name] = result

    def __call_print(self, call_ast): #returns NIL_VALUE
        output = ""
        for arg in call_ast.get("args"):
            result = self.__eval_expr(arg)  # result is a Value object
            output = output + get_printable(result) #get_printable returns a string
        super().output(output) #output is a string
        return Interpreter.NIL_VALUE

    def __call_input(self, call_ast): #returns Value object
        args = call_ast.get("args")
        if args is not None and len(args) == 1:
            result = self.__eval_expr(args[0]) #result is a Value object
            super().output(get_printable(result)) #get_printable returns a string
        elif args is not None and len(args) > 1:
            super().error(
                ErrorType.NAME_ERROR, "No inputi() function that takes > 1 parameter"
            )
        inp = super().get_input() #inp is a string
        if call_ast.get("name") == "inputi":
            return Value(Type.INT, int(inp))
        if call_ast.get("name") == "inputs":
            return Value(Type.STRING, inp)

    def __assign(self, assign_ast):
        var_name = assign_ast.get("name")
        if var_name.find(".") != -1:
            #THIS IS AN OBJECT
            obj_name = var_name.split(".")[0]
            field_name = var_name.split(".")[1]
            #print(obj_name, field_name)
            self.env.set("this", obj_name)
            object = self.env.get(obj_name) #Value object of (Type.OBJECT, Object object)
            print(object)
            if object is None:
                super().error(ErrorType.NAME_ERROR, f"Object {obj_name} not found")
            object = object.value() #Object object
            
            if self.__eval_expr(assign_ast.get("expression")).type() is Type.CLOSURE: #is a function
                closure = self.__eval_expr(assign_ast.get("expression")) #Value object of (Type.CLOSURE, Closure object)
                closure = closure.value() #Closure object
                function_ast = closure.func_ast #AST node of function definition
                num_args = len(function_ast.get("args")) #int
                print("SETTING METHOD")
                object.set_method(field_name, num_args, closure) #set appropriate method
            else:
                if field_name == "proto":
                    if self.__eval_expr(assign_ast.get("expression")).type() is not Type.OBJECT:
                        super().error(ErrorType.TYPE_ERROR, f"Object {obj_name} proto being set to non-object type.")
                    object.set_proto(self.__eval_expr(assign_ast.get("expression")))
                else:
                    object.set_field(field_name, self.__eval_expr(assign_ast.get("expression"))) #set appropriate field
        
        src_value_obj = copy.copy(self.__eval_expr(assign_ast.get("expression")))
        target_value_obj = self.env.get(var_name)
        if target_value_obj is None:
                self.env.set(var_name, src_value_obj)
        else:
                # if a close is changed to another type such as int, we cannot make function calls on it any more 
                if target_value_obj.t == Type.CLOSURE and src_value_obj.t != Type.CLOSURE:
                    target_value_obj.v.type = src_value_obj.t
                target_value_obj.set(src_value_obj)

    def __eval_expr(self, expr_ast): #returns Value object  or NIL_VALUE 
        if expr_ast.elem_type == InterpreterBase.NIL_DEF:
            return Interpreter.NIL_VALUE
        if expr_ast.elem_type == InterpreterBase.INT_DEF:
            return Value(Type.INT, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.STRING_DEF:
            return Value(Type.STRING, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.BOOL_DEF:
            return Value(Type.BOOL, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.VAR_DEF:
            return self.__eval_name(expr_ast)
        if expr_ast.elem_type == InterpreterBase.FCALL_DEF:
            return self.__call_func(expr_ast)
        if expr_ast.elem_type in Interpreter.BIN_OPS:
            return self.__eval_op(expr_ast)
        if expr_ast.elem_type == Interpreter.NEG_DEF:
            return self.__eval_unary(expr_ast, Type.INT, lambda x: -1 * x)
        if expr_ast.elem_type == Interpreter.NOT_DEF:
            return self.__eval_unary(expr_ast, Type.BOOL, lambda x: not x)
        if expr_ast.elem_type == Interpreter.LAMBDA_DEF:
            return Value(Type.CLOSURE, Closure(expr_ast, self.env))
        if expr_ast.elem_type == Interpreter.OBJ_DEF:
            return Value(Type.OBJECT, Object(self.env))
        if expr_ast.elem_type == Interpreter.MCALL_DEF:
            return self.__call_func(expr_ast)

    def __eval_name(self, name_ast):
        var_name = name_ast.get("name")
        print(var_name)
        if var_name.find(".") != -1:
            #IS AN OBJECT
            obj_name = var_name.split(".")[0]
            field_name = var_name.split(".")[1]
            print(obj_name, field_name)
            object = self.env.get(obj_name).value() #Object object
            print(object)
            if object is None:
                super().error(ErrorType.NAME_ERROR, f"Object {obj_name} not found")
            field = object.get_field(field_name) #Value object
            print(field)
            if field is None:
                super().error(ErrorType.NAME_ERROR, f"Field {field_name} not found")
            return field
        val = self.env.get(var_name)
        if val is not None:
            return val
        closure = self.__get_func_by_name(var_name, None)
        if closure is None:
            super().error(
                ErrorType.NAME_ERROR, f"Variable/function {var_name} not found"
            )
        return Value(Type.CLOSURE, closure)

    

    def __eval_op(self, arith_ast):
        left_value_obj = self.__eval_expr(arith_ast.get("op1")) #Value object
        right_value_obj = self.__eval_expr(arith_ast.get("op2")) #Value object


        left_value_obj, right_value_obj = self.__bin_op_promotion(
            arith_ast.elem_type, left_value_obj, right_value_obj
        ) #Value object, Value object

        if not self.__compatible_types(
            arith_ast.elem_type, left_value_obj, right_value_obj
        ):
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible types for {arith_ast.elem_type} operation",
            )
        if arith_ast.elem_type not in self.op_to_lambda[left_value_obj.type()]:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible operator {arith_ast.elem_type} for type {left_value_obj.type()}",
            )
        f = self.op_to_lambda[left_value_obj.type()][arith_ast.elem_type] #lambda function
        return f(left_value_obj, right_value_obj) #Value object

    # bool and int, int and bool for and/or/==/!= -> coerce int to bool
    # bool and int, int and bool for arithmetic ops, coerce true to 1, false to 0
    def __bin_op_promotion(self, operation, op1, op2): #returns Value object, Value object tuple
        if operation in self.op_to_lambda[Type.BOOL]:  # && or ||
            
            # If this operation is still allowed in the ints, then continue
            if operation in self.op_to_lambda[Type.INT] and op1.type() == Type.INT \
                and op2.type() == Type.INT:
                pass
            else:
                if op1.type() == Type.INT:
                    op1 = Interpreter.__int_to_bool(op1)
                if op2.type() == Type.INT:
                    op2 = Interpreter.__int_to_bool(op2)
        if operation in self.op_to_lambda[Type.INT]:  # +, -, *, /
            if op1.type() == Type.BOOL:
                op1 = Interpreter.__bool_to_int(op1)
            if op2.type() == Type.BOOL:
                op2 = Interpreter.__bool_to_int(op2)
        return (op1, op2) 

    def __unary_op_promotion(self, operation, op1): #returns Value object
        if operation == "!" and op1.type() == Type.INT:
            op1 = Interpreter.__int_to_bool(op1)
        return op1

    @staticmethod
    def __int_to_bool(value): #returns Value object
        return Value(Type.BOOL, value.value() != 0)

    @staticmethod
    def __bool_to_int(value): #returns Value object
        return Value(Type.INT, 1 if value.value() else 0)

    def __compatible_types(self, oper, obj1, obj2): #returns boolean
        # DOCUMENT: allow comparisons ==/!= of anything against anything
        if oper in ["==", "!="]:
            return True
        return obj1.type() == obj2.type()

    def __eval_unary(self, arith_ast, t, f): #returns Value object
        value_obj = self.__eval_expr(arith_ast.get("op1"))
        value_obj = self.__unary_op_promotion(arith_ast.elem_type, value_obj)

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
            x.type(), x.value() + y.value()
        )
        self.op_to_lambda[Type.INT]["-"] = lambda x, y: Value(
            x.type(), x.value() - y.value()
        )
        self.op_to_lambda[Type.INT]["*"] = lambda x, y: Value(
            x.type(), x.value() * y.value()
        )
        self.op_to_lambda[Type.INT]["/"] = lambda x, y: Value(
            x.type(), x.value() // y.value()
        )
        self.op_to_lambda[Type.INT]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.INT]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
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
            x.type(), x.value() and y.value()
        )
        self.op_to_lambda[Type.BOOL]["||"] = lambda x, y: Value(
            x.type(), x.value() or y.value()
        )
        self.op_to_lambda[Type.BOOL]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.BOOL]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )

        #  set up operations on nil
        self.op_to_lambda[Type.NIL] = {}
        self.op_to_lambda[Type.NIL]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.NIL]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )

        #  set up operations on closures
        self.op_to_lambda[Type.CLOSURE] = {}
        self.op_to_lambda[Type.CLOSURE]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.CLOSURE]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )

    def __do_if(self, if_ast): #returns (status, return_val) of (Continue and NIL)
        cond_ast = if_ast.get("condition")
        result = self.__eval_expr(cond_ast)
        if result.type() == Type.INT:
            result = Interpreter.__int_to_bool(result)
        if result.type() != Type.BOOL:
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

    def __do_while(self, while_ast): #returns (status, return_val) of (Continue/Return and NIL)
        cond_ast = while_ast.get("condition")
        run_while = Interpreter.TRUE_VALUE
        while run_while.value():
            run_while = self.__eval_expr(cond_ast)
            if run_while.type() == Type.INT:
                run_while = Interpreter.__int_to_bool(run_while)
            if run_while.type() != Type.BOOL:
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

    def __do_return(self, return_ast): #returns (status, return_val) of (Return and Value object)
        expr_ast = return_ast.get("expression")
        if expr_ast is None:
            return (ExecStatus.RETURN, Interpreter.NIL_VALUE)
        value_obj = copy.deepcopy(self.__eval_expr(expr_ast))
        return (ExecStatus.RETURN, value_obj)