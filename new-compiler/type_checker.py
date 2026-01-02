"""
Minimal type checking pass for VYL.
- Ensures assignments and returns match declared types.
- Enforces operator compatibility.
- Short-circuit logical operators are assumed by codegen when operator is &&/||.
"""
from typing import Dict, Optional, Tuple, List
try:
    from .parser import (
        Program,
        VarDecl,
        Assignment,
        FunctionCall,
        FunctionDef,
        ReturnStmt,
        DeferStmt,
        Block,
        IfStmt,
        WhileStmt,
        ForStmt,
        BinaryExpr,
        UnaryExpr,
        Literal,
        Identifier,
        StructDef,
        FieldAccess,
        IndexExpr,
        NewExpr,
        ArrayLiteral,
        EnumDef,
        EnumAccess,
        MethodDef,
        MethodCall,
        SelfExpr,
        AddressOf,
        Dereference,
        NullLiteral,
        TupleLiteral,
        TupleUnpack,
        InterfaceDef,
        InterpString,
        TryExpr,
    )
    from .validator import ValidationError
except ImportError:  # pragma: no cover
    from parser import (  # type: ignore
        Program,
        VarDecl,
        Assignment,
        FunctionCall,
        FunctionDef,
        ReturnStmt,
        DeferStmt,
        Block,
        IfStmt,
        WhileStmt,
        ForStmt,
        BinaryExpr,
        UnaryExpr,
        Literal,
        Identifier,
        StructDef,
        FieldAccess,
        IndexExpr,
        NewExpr,
        ArrayLiteral,
        EnumDef,
        EnumAccess,
        MethodDef,
        MethodCall,
        SelfExpr,
        AddressOf,
        Dereference,
        NullLiteral,
        TupleLiteral,
        TupleUnpack,
        InterfaceDef,
        InterpString,
        TryExpr,
    )
    from validator import ValidationError  # type: ignore

TypeEnv = Dict[str, tuple[str, bool]]

NUMERIC = {"int", "dec"}
BOOL = "bool"
STRING = "string"

# Builtin signatures: name -> (param_types, return_type)
# param_types can be None to mean "any" for that slot.
BUILTINS: Dict[str, Tuple[List[Optional[str]], Optional[str]]] = {
    "Print": ([None], None),
    "Clock": ([], "int"),
    "Exists": ([STRING], BOOL),
    "CreateFolder": ([STRING], "int"),
    "Open": ([STRING, STRING], "int"),
    "Close": (["int"], "int"),
    "Read": (["int"], STRING),
    "Write": (["int", STRING], "int"),
    "SHA256": ([STRING], STRING),
    "Argc": ([], "int"),
    "GetArg": (["int"], STRING),
    "ReadFilesize": ([STRING], "int"),
    "GC": ([], None),
    "Sys": ([STRING], "int"),
    "Input": ([], STRING),
    "Exit": (["int"], None),
    "Sleep": (["int"], "int"),
    "Now": ([], "int"),
    "RandInt": ([], "int"),
    "Remove": ([STRING], "int"),
    "MkdirP": ([STRING], "int"),
    "RemoveAll": ([STRING], "int"),
    "CopyFile": ([STRING, STRING], "int"),
    "Unzip": ([STRING, STRING], "int"),
    "OpenDir": ([STRING], "int"),
    "ReadDir": (["int"], STRING),
    "CloseDir": (["int"], "int"),
    "Alloc": (["int"], "int"),
    "StrConcat": ([STRING, STRING], STRING),
    "StrLen": ([STRING], "int"),
    "StrFind": ([STRING, STRING], "int"),
    "Substring": ([STRING, "int", "int"], STRING),
    "GetEnv": ([STRING], STRING),
    "Sys": ([STRING], "int"),
    "TcpConnect": ([STRING, "int"], "int"),
    "TcpSend": (["int", STRING], "int"),
    "TcpRecv": (["int", "int"], STRING),
    "TcpClose": (["int"], "int"),
    "TcpResolve": ([STRING], STRING),
    "TlsConnect": ([STRING, "int"], "int"),
    "TlsSend": (["int", STRING], "int"),
    "TlsRecv": (["int", "int"], STRING),
    "TlsClose": (["int"], "int"),
    "HttpGet": ([STRING, STRING, "int"], STRING),
    "HttpDownload": ([STRING, STRING, "int", STRING], "int"),
    "Array": (["int"], "array"),
    "Length": (["array"], "int"),
    "Len": ([None], "int"),  # Works on any array type
    "Sqrt": (["int"], "int"),
    "Malloc": (["int"], "int"),
    "Free": (["int"], "int"),
    "Memcpy": (["int", "int", "int"], "int"),
    "Memset": (["int", "int", "int"], "int"),
}


def type_check(program: Program) -> None:
    globals_table: TypeEnv = {}
    functions: Dict[str, FunctionDef] = {}
    structs: Dict[str, StructDef] = {s.name: s for s in program.statements if isinstance(s, StructDef)}
    enums: Dict[str, EnumDef] = {e.name: e for e in program.statements if isinstance(e, EnumDef)}

    for stmt in program.statements:
        if isinstance(stmt, VarDecl):
            _define_var(globals_table, stmt)
        elif isinstance(stmt, FunctionDef):
            _register_function(functions, stmt)
        elif isinstance(stmt, StructDef):
            pass
        elif isinstance(stmt, EnumDef):
            pass

    if "Main" not in functions:
        raise ValidationError("Missing Main function entrypoint", program.line, program.column)

    for stmt in program.statements:
        if isinstance(stmt, FunctionDef):
            _type_check_function(stmt, globals_table, functions, structs, enums)
        elif isinstance(stmt, VarDecl):
            if stmt.value:
                val_type = _type_of_expression(stmt.value, globals_table, {}, functions, structs, enums)
                if stmt.name in globals_table:
                    cur_t, cur_mut = globals_table[stmt.name]
                    if cur_t == "int" and stmt.var_type in (None, "inf"):
                        globals_table[stmt.name] = (val_type, cur_mut)
        elif isinstance(stmt, StructDef):
            # Type check method bodies
            for method in stmt.methods:
                _type_check_method(method, stmt, globals_table, functions, structs, enums)
        elif isinstance(stmt, EnumDef):
            continue
        elif isinstance(stmt, InterfaceDef):
            continue
        else:
            _type_check_statement(stmt, globals_table, {}, functions, structs, enums, func_ret=None)


def _define_var(env: TypeEnv, decl: VarDecl) -> None:
    if decl.name in env:
        raise ValidationError(f"Duplicate global variable '{decl.name}'", decl.line, decl.column)
    if decl.var_type in (None, "inf"):
        lit_type = decl.value.literal_type if isinstance(decl.value, Literal) else None
        inferred = lit_type or "int"
    else:
        inferred = decl.var_type
    env[decl.name] = (inferred, decl.is_mutable)


def _register_function(funcs: Dict[str, FunctionDef], func: FunctionDef) -> None:
    if func.name in funcs:
        raise ValidationError(f"Duplicate function '{func.name}'", func.line, func.column)
    funcs[func.name] = func


def _type_check_function(func: FunctionDef, globals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef]) -> None:
    locals_table: TypeEnv = {}
    for pname, ptype, pdefault in func.params:
        if pname in locals_table:
            raise ValidationError(f"Duplicate parameter '{pname}'", func.line, func.column)
        locals_table[pname] = (ptype or "int", True)

    for stmt in func.body.statements if func.body else []:
        _type_check_statement(stmt, globals_table, locals_table, functions, structs, enums, func_ret=func.return_type or None)


def _type_check_method(method: MethodDef, struct: StructDef, globals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef]) -> None:
    """Type check a method body with 'self' in scope."""
    locals_table: TypeEnv = {}
    locals_table["self"] = (struct.name, False)
    for pname, ptype, pdefault in method.params:
        if pname in locals_table:
            raise ValidationError(f"Duplicate parameter '{pname}'", method.line, method.column)
        locals_table[pname] = (ptype or "int", True)

    for stmt in method.body.statements if method.body else []:
        _type_check_statement(stmt, globals_table, locals_table, functions, structs, enums, func_ret=method.return_type or None, in_method=True, current_struct=struct)


def _type_check_statement(stmt, globals_table: TypeEnv, locals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef], func_ret: Optional[str], in_method: bool = False, current_struct: StructDef = None) -> None:
    if isinstance(stmt, VarDecl):
        if stmt.name in locals_table:
            raise ValidationError(f"Duplicate local variable '{stmt.name}'", stmt.line, stmt.column)
        if stmt.value:
            val_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
            decl_type_hint = None if stmt.var_type in (None, "inf") else stmt.var_type
            decl_type = decl_type_hint or val_type or "int"
        else:
            decl_type = None if stmt.var_type in (None, "inf") else stmt.var_type
            if decl_type is None:
                decl_type = "int"
        locals_table[stmt.name] = (decl_type, stmt.is_mutable)
    elif isinstance(stmt, TupleUnpack):
        # Type-check the value being unpacked
        val_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        # Parse the tuple type: "(type1, type2, ...)"
        if not (val_type.startswith("(") and val_type.endswith(")")):
            raise ValidationError(f"Cannot unpack non-tuple type '{val_type}'", stmt.line, stmt.column)
        inner = val_type[1:-1]
        # Parse tuple element types (handling nested tuples)
        elem_types = []
        depth = 0
        current = ""
        for ch in inner:
            if ch == "(":
                depth += 1
                current += ch
            elif ch == ")":
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                elem_types.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            elem_types.append(current.strip())
        
        if len(elem_types) != len(stmt.names):
            raise ValidationError(f"Tuple unpacking: expected {len(elem_types)} values, got {len(stmt.names)} names", stmt.line, stmt.column)
        
        # Register each variable with its type
        for i, name in enumerate(stmt.names):
            if name in locals_table:
                raise ValidationError(f"Duplicate local variable '{name}'", stmt.line, stmt.column)
            # Use explicit type if provided, otherwise inferred type
            var_type = stmt.types[i] if stmt.types[i] else elem_types[i]
            locals_table[name] = (var_type, True)  # Tuple unpacking creates mutable bindings
    elif isinstance(stmt, Assignment):
        if stmt.target:
            target_type = _type_of_expression(stmt.target, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
            val_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
            _ensure_assignable(target_type, val_type, stmt.line, stmt.column)
        else:
            if stmt.name in locals_table:
                target_type, is_mut = locals_table[stmt.name]
            elif stmt.name in globals_table:
                target_type, is_mut = globals_table[stmt.name]
            else:
                raise ValidationError(f"Assignment to undefined identifier '{stmt.name}'", stmt.line, stmt.column)
            if not is_mut:
                raise ValidationError(f"Cannot assign to immutable binding '{stmt.name}'", stmt.line, stmt.column)
            val_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
            _ensure_assignable(target_type, val_type, stmt.line, stmt.column)
    elif isinstance(stmt, FunctionCall):
        _type_of_expression(stmt, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(stmt, MethodCall):
        _type_of_expression(stmt, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(stmt, IfStmt):
        cond_t = _type_of_expression(stmt.condition, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _require_bool(cond_t, stmt.condition.line, stmt.condition.column)
        _type_check_statement(stmt.then_block, globals_table, dict(locals_table), functions, structs, enums, func_ret, in_method, current_struct)
        if stmt.else_block:
            _type_check_statement(stmt.else_block, globals_table, dict(locals_table), functions, structs, enums, func_ret, in_method, current_struct)
    elif isinstance(stmt, WhileStmt):
        cond_t = _type_of_expression(stmt.condition, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _require_bool(cond_t, stmt.condition.line, stmt.condition.column)
        _type_check_statement(stmt.body, globals_table, dict(locals_table), functions, structs, enums, func_ret, in_method, current_struct)
    elif isinstance(stmt, ForStmt):
        start_t = _type_of_expression(stmt.start, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        end_t = _type_of_expression(stmt.end, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _require_numeric(start_t, stmt.start.line, stmt.start.column)
        _require_numeric(end_t, stmt.end.line, stmt.end.column)
        loop_locals = dict(locals_table)
        loop_locals[stmt.var_name] = ("int", True)
        _type_check_statement(stmt.body, globals_table, loop_locals, functions, structs, enums, func_ret, in_method, current_struct)
    elif isinstance(stmt, DeferStmt):
        # Type-check the deferred body in the current scope
        _type_check_statement(stmt.body, globals_table, dict(locals_table), functions, structs, enums, func_ret, in_method, current_struct)
    elif isinstance(stmt, Block):
        scope_locals = dict(locals_table)
        for inner in stmt.statements:
            _type_check_statement(inner, globals_table, scope_locals, functions, structs, enums, func_ret, in_method, current_struct)
    elif isinstance(stmt, ReturnStmt):
        ret_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct) if stmt.value else None
        if func_ret:
            _ensure_assignable(func_ret, ret_type or "void", stmt.line, stmt.column)
    elif isinstance(stmt, StructDef):
        return
    elif isinstance(stmt, EnumDef):
        return
    else:
        _type_of_expression(stmt, globals_table, locals_table, functions, structs, enums, in_method, current_struct)


def _type_of_expression(expr, globals_table: TypeEnv, locals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef], in_method: bool = False, current_struct: StructDef = None) -> str:
    if isinstance(expr, Literal):
        return expr.literal_type
    if isinstance(expr, NullLiteral):
        return "*void"  # null pointer type
    if isinstance(expr, SelfExpr):
        if not in_method or not current_struct:
            raise ValidationError("'self' used outside of method", expr.line, expr.column)
        return current_struct.name
    if isinstance(expr, Identifier):
        if expr.name in locals_table:
            return locals_table[expr.name][0]
        if expr.name in globals_table:
            return globals_table[expr.name][0]
        if expr.name in ("argc", "argv"):
            return "int"
        # Check if it's an enum name
        if expr.name in enums:
            return expr.name
        raise ValidationError(f"Undefined identifier '{expr.name}'", expr.line, expr.column)
    if isinstance(expr, AddressOf):
        t = _type_of_expression(expr.operand, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        return "*" + t  # pointer to type
    if isinstance(expr, Dereference):
        t = _type_of_expression(expr.operand, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        if not t.startswith("*"):
            raise ValidationError(f"Cannot dereference non-pointer type '{t}'", expr.line, expr.column)
        return t[1:]  # remove leading *
    if isinstance(expr, UnaryExpr):
        t = _type_of_expression(expr.operand, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        if expr.operator in ('-', '+'):
            _require_numeric(t, expr.line, expr.column)
            return t
        if expr.operator in ('!', 'NOT'):
            _require_bool(t, expr.line, expr.column)
            return BOOL
        raise ValidationError(f"Unsupported unary operator '{expr.operator}'", expr.line, expr.column)
    if isinstance(expr, BinaryExpr):
        left_t = _type_of_expression(expr.left, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        right_t = _type_of_expression(expr.right, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        op = expr.operator
        if op == '+':
            # String concatenation: string + anything or anything + string
            if left_t == STRING or right_t == STRING:
                return STRING
            _require_numeric(left_t, expr.left.line, expr.left.column)
            _require_numeric(right_t, expr.right.line, expr.right.column)
            return 'dec' if 'dec' in (left_t, right_t) else 'int'
        if op in ('-', '*', '/', '%'):
            _require_numeric(left_t, expr.left.line, expr.left.column)
            _require_numeric(right_t, expr.right.line, expr.right.column)
            return 'dec' if 'dec' in (left_t, right_t) else 'int'
        if op in ('==', '!='):
            _ensure_same(left_t, right_t, expr.line, expr.column)
            return BOOL
        if op in ('<', '>', '<=', '>='):
            _require_numeric(left_t, expr.left.line, expr.left.column)
            _require_numeric(right_t, expr.right.line, expr.right.column)
            return BOOL
        if op in ('&&', '||'):
            _require_bool(left_t, expr.left.line, expr.left.column)
            _require_bool(right_t, expr.right.line, expr.right.column)
            return BOOL
        raise ValidationError(f"Unsupported binary operator '{op}'", expr.line, expr.column)
    if isinstance(expr, MethodCall):
        recv_type = _type_of_expression(expr.receiver, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        if recv_type not in structs:
            raise ValidationError(f"Method call on non-struct type '{recv_type}'", expr.line, expr.column)
        struct_def = structs[recv_type]
        for method in struct_def.methods:
            if method.name == expr.method_name:
                # Count required params (those without defaults)
                required_params = sum(1 for _, _, pdefault in method.params if pdefault is None)
                if len(expr.arguments) < required_params or len(expr.arguments) > len(method.params):
                    raise ValidationError(f"Method '{expr.method_name}' expects {required_params} to {len(method.params)} args, got {len(expr.arguments)}", expr.line, expr.column)
                for (pname, ptype, pdefault), arg in zip(method.params, expr.arguments):
                    arg_t = _type_of_expression(arg, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
                    expected = ptype or "int"
                    _ensure_assignable(expected, arg_t, arg.line, arg.column)
                return method.return_type or "int"
        raise ValidationError(f"Unknown method '{expr.method_name}' on struct '{recv_type}'", expr.line, expr.column)
    if isinstance(expr, FunctionCall):
        # Builtins
        if expr.name == "CreateFolder":
            if not expr.arguments:
                raise ValidationError("Function 'CreateFolder' expects at least 1 arg", expr.line, expr.column)
            for arg in expr.arguments:
                arg_t = _type_of_expression(arg, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
                _ensure_assignable(STRING, arg_t, arg.line, arg.column)
            return "int"
        if expr.name in BUILTINS:
            sig_params, sig_ret = BUILTINS[expr.name]
            if len(sig_params) == 1 and sig_params[0] is None:
                pass
            elif len(sig_params) != len(expr.arguments):
                raise ValidationError(f"Function '{expr.name}' expects {len(sig_params)} args, got {len(expr.arguments)}", expr.line, expr.column)
            for idx, arg in enumerate(expr.arguments):
                arg_t = _type_of_expression(arg, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
                if idx < len(sig_params) and sig_params[idx] is not None:
                    _ensure_assignable(sig_params[idx], arg_t, arg.line, arg.column)
            return sig_ret or "int"
        if expr.name not in functions:
            raise ValidationError(f"Unknown function '{expr.name}'", expr.line, expr.column)
        fn = functions[expr.name]
        # Count required params (those without defaults)
        required_params = sum(1 for _, _, pdefault in fn.params if pdefault is None)
        if len(expr.arguments) < required_params or len(expr.arguments) > len(fn.params):
            raise ValidationError(f"Function '{expr.name}' expects {required_params} to {len(fn.params)} args, got {len(expr.arguments)}", expr.line, expr.column)
        for (pname, ptype, pdefault), arg in zip(fn.params, expr.arguments):
            arg_t = _type_of_expression(arg, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
            expected = ptype or "int"
            _ensure_assignable(expected, arg_t, arg.line, arg.column)
        return fn.return_type or "int"
    if isinstance(expr, FieldAccess):
        # Check if receiver is an enum (e.g., Status.OK)
        if isinstance(expr.receiver, Identifier) and expr.receiver.name in enums:
            return expr.receiver.name  # Return enum type
        recv_type = _type_of_expression(expr.receiver, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        if recv_type not in structs:
            raise ValidationError(f"Field access on non-struct type '{recv_type}'", expr.line, expr.column)
        struct_def = structs[recv_type]
        for fld in struct_def.fields:
            if fld.name == expr.field:
                return fld.var_type or "int"
        raise ValidationError(f"Unknown field '{expr.field}' on struct '{recv_type}'", expr.line, expr.column)
    if isinstance(expr, NewExpr):
        if expr.struct_name not in structs:
            raise ValidationError(f"Unknown struct type '{expr.struct_name}'", expr.line, expr.column)
        struct_def = structs[expr.struct_name]
        field_names = {fld.name for fld in struct_def.fields}
        for field_name, value in expr.initializers:
            if field_name not in field_names:
                raise ValidationError(f"Unknown field '{field_name}' on struct '{expr.struct_name}'", expr.line, expr.column)
            _type_of_expression(value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        return expr.struct_name
    if isinstance(expr, ArrayLiteral):
        elem_type = "int"  # default
        for elem in expr.elements:
            elem_type = _type_of_expression(elem, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        return elem_type + "[]"  # Return typed array like "int[]" or "string[]"
    if isinstance(expr, TupleLiteral):
        elem_types = []
        for elem in expr.elements:
            elem_types.append(_type_of_expression(elem, globals_table, locals_table, functions, structs, enums, in_method, current_struct))
        return "(" + ", ".join(elem_types) + ")"  # e.g., "(int, string)"
    if isinstance(expr, IndexExpr):
        arr_t = _type_of_expression(expr.receiver, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        # Check for array or typed array (ends with [])
        if arr_t != "array" and not arr_t.endswith("[]"):
            raise ValidationError(f"Indexing requires array, got '{arr_t}'", expr.line, expr.column)
        idx_t = _type_of_expression(expr.index, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _require_numeric(idx_t, expr.index.line, expr.index.column)
        # Return element type for typed arrays
        if arr_t.endswith("[]"):
            return arr_t[:-2]  # e.g., "int[]" -> "int"
        return "int"
    if isinstance(expr, Block):
        scope_locals = dict(locals_table)
        last_type = "void"
        for inner in expr.statements:
            last_type = _type_check_statement_expr(inner, globals_table, scope_locals, functions, structs, enums)
        return last_type
    if isinstance(expr, InterpString):
        # Interpolated strings are always strings
        return STRING
    if isinstance(expr, TryExpr):
        # Error propagation returns the type of its operand
        return _type_of_expression(expr.operand, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    raise ValidationError("Unsupported expression encountered", expr.line if hasattr(expr, "line") else 0, getattr(expr, "column", 0))


def _type_check_statement_expr(stmt, globals_table: TypeEnv, locals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef]) -> str:
    # Helper to type-check a statement used as expression; return last expression type or void.
    _type_check_statement(stmt, globals_table, locals_table, functions, structs, enums, func_ret=None)
    return "void"


def _ensure_assignable(expected: str, actual: str, line: int, col: int) -> None:
    if expected == actual:
        return
    # simple numeric widening
    if expected == 'dec' and actual == 'int':
        return
    # null can be assigned to any pointer type
    if expected.startswith('*') and actual == '*void':
        return
    # enum comparison
    if expected == actual:
        return
    raise ValidationError(f"Type mismatch: expected {expected}, got {actual}", line, col)


def _ensure_same(t1: str, t2: str, line: int, col: int) -> None:
    if t1 != t2:
        # Allow null comparison with pointers
        if (t1.startswith('*') and t2 == '*void') or (t2.startswith('*') and t1 == '*void'):
            return
        raise ValidationError(f"Type mismatch: {t1} vs {t2}", line, col)


def _require_numeric(t: str, line: int, col: int) -> None:
    if t not in NUMERIC:
        raise ValidationError(f"Numeric type required, got {t}", line, col)


def _require_bool(t: str, line: int, col: int) -> None:
    if t != BOOL:
        raise ValidationError(f"Boolean type required, got {t}", line, col)
