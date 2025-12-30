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

    for stmt in program.statements:
        if isinstance(stmt, VarDecl):
            _define_var(globals_table, stmt)
        elif isinstance(stmt, FunctionDef):
            _register_function(functions, stmt)
        elif isinstance(stmt, StructDef):
            pass

    if "Main" not in functions:
        raise ValidationError("Missing Main function entrypoint", program.line, program.column)

    for stmt in program.statements:
        if isinstance(stmt, FunctionDef):
            _type_check_function(stmt, globals_table, functions, structs)
        elif isinstance(stmt, VarDecl):
            if stmt.value:
                val_type = _type_of_expression(stmt.value, globals_table, {}, functions, structs)
                if stmt.name in globals_table:
                    cur_t, cur_mut = globals_table[stmt.name]
                    if cur_t == "int" and stmt.var_type in (None, "inf"):
                        globals_table[stmt.name] = (val_type, cur_mut)
        elif isinstance(stmt, StructDef):
            continue
        else:
            _type_check_statement(stmt, globals_table, {}, functions, structs, func_ret=None)


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


def _type_check_function(func: FunctionDef, globals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef]) -> None:
    locals_table: TypeEnv = {}
    for pname, ptype in func.params:
        if pname in locals_table:
            raise ValidationError(f"Duplicate parameter '{pname}'", func.line, func.column)
        locals_table[pname] = (ptype or "int", True)

    for stmt in func.body.statements if func.body else []:
        _type_check_statement(stmt, globals_table, locals_table, functions, structs, func_ret=func.return_type or None)


def _type_check_statement(stmt, globals_table: TypeEnv, locals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], func_ret: Optional[str]) -> None:
    if isinstance(stmt, VarDecl):
        if stmt.name in locals_table:
            raise ValidationError(f"Duplicate local variable '{stmt.name}'", stmt.line, stmt.column)
        if stmt.value:
            val_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs)
            decl_type_hint = None if stmt.var_type in (None, "inf") else stmt.var_type
            decl_type = decl_type_hint or val_type or "int"
        else:
            decl_type = None if stmt.var_type in (None, "inf") else stmt.var_type
            if decl_type is None:
                decl_type = "int"
        locals_table[stmt.name] = (decl_type, stmt.is_mutable)
    elif isinstance(stmt, Assignment):
        if stmt.target:
            target_type = _type_of_expression(stmt.target, globals_table, locals_table, functions, structs)
            val_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs)
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
            val_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs)
            _ensure_assignable(target_type, val_type, stmt.line, stmt.column)
    elif isinstance(stmt, FunctionCall):
        _type_of_expression(stmt, globals_table, locals_table, functions, structs)
    elif isinstance(stmt, IfStmt):
        cond_t = _type_of_expression(stmt.condition, globals_table, locals_table, functions, structs)
        _require_bool(cond_t, stmt.condition.line, stmt.condition.column)
        _type_check_statement(stmt.then_block, globals_table, dict(locals_table), functions, structs, func_ret)
        if stmt.else_block:
            _type_check_statement(stmt.else_block, globals_table, dict(locals_table), functions, structs, func_ret)
    elif isinstance(stmt, WhileStmt):
        cond_t = _type_of_expression(stmt.condition, globals_table, locals_table, functions, structs)
        _require_bool(cond_t, stmt.condition.line, stmt.condition.column)
        _type_check_statement(stmt.body, globals_table, dict(locals_table), functions, structs, func_ret)
    elif isinstance(stmt, ForStmt):
        start_t = _type_of_expression(stmt.start, globals_table, locals_table, functions, structs)
        end_t = _type_of_expression(stmt.end, globals_table, locals_table, functions, structs)
        _require_numeric(start_t, stmt.start.line, stmt.start.column)
        _require_numeric(end_t, stmt.end.line, stmt.end.column)
        loop_locals = dict(locals_table)
        loop_locals[stmt.var_name] = ("int", True)
        _type_check_statement(stmt.body, globals_table, loop_locals, functions, structs, func_ret)
    elif isinstance(stmt, Block):
        scope_locals = dict(locals_table)
        for inner in stmt.statements:
            _type_check_statement(inner, globals_table, scope_locals, functions, structs, func_ret)
    elif isinstance(stmt, ReturnStmt):
        ret_type = _type_of_expression(stmt.value, globals_table, locals_table, functions, structs) if stmt.value else None
        if func_ret:
            _ensure_assignable(func_ret, ret_type or "void", stmt.line, stmt.column)
    elif isinstance(stmt, StructDef):
        return
    else:
        _type_of_expression(stmt, globals_table, locals_table, functions, structs)


def _type_of_expression(expr, globals_table: TypeEnv, locals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef]) -> str:
    if isinstance(expr, Literal):
        return expr.literal_type
    if isinstance(expr, Identifier):
        if expr.name in locals_table:
            return locals_table[expr.name][0]
        if expr.name in globals_table:
            return globals_table[expr.name][0]
        if expr.name in ("argc", "argv"):
            return "int"
        raise ValidationError(f"Undefined identifier '{expr.name}'", expr.line, expr.column)
    if isinstance(expr, UnaryExpr):
        t = _type_of_expression(expr.operand, globals_table, locals_table, functions, structs)
        if expr.operator in ('-', '+'):
            _require_numeric(t, expr.line, expr.column)
            return t
        if expr.operator in ('!', 'NOT'):
            _require_bool(t, expr.line, expr.column)
            return BOOL
        raise ValidationError(f"Unsupported unary operator '{expr.operator}'", expr.line, expr.column)
    if isinstance(expr, BinaryExpr):
        left_t = _type_of_expression(expr.left, globals_table, locals_table, functions, structs)
        right_t = _type_of_expression(expr.right, globals_table, locals_table, functions, structs)
        op = expr.operator
        if op == '+':
            if left_t == STRING and right_t == STRING:
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
    if isinstance(expr, FunctionCall):
        # Builtins
        if expr.name == "CreateFolder":
            if not expr.arguments:
                raise ValidationError("Function 'CreateFolder' expects at least 1 arg", expr.line, expr.column)
            for arg in expr.arguments:
                arg_t = _type_of_expression(arg, globals_table, locals_table, functions, structs)
                _ensure_assignable(STRING, arg_t, arg.line, arg.column)
            return "int"
        if expr.name in BUILTINS:
            sig_params, sig_ret = BUILTINS[expr.name]
            if len(sig_params) == 1 and sig_params[0] is None:
                pass
            elif len(sig_params) != len(expr.arguments):
                raise ValidationError(f"Function '{expr.name}' expects {len(sig_params)} args, got {len(expr.arguments)}", expr.line, expr.column)
            for idx, arg in enumerate(expr.arguments):
                arg_t = _type_of_expression(arg, globals_table, locals_table, functions, structs)
                if idx < len(sig_params) and sig_params[idx] is not None:
                    _ensure_assignable(sig_params[idx], arg_t, arg.line, arg.column)
            return sig_ret or "int"
        if expr.name not in functions:
            raise ValidationError(f"Unknown function '{expr.name}'", expr.line, expr.column)
        fn = functions[expr.name]
        if len(fn.params) != len(expr.arguments):
            raise ValidationError(f"Function '{expr.name}' expects {len(fn.params)} args, got {len(expr.arguments)}", expr.line, expr.column)
        for (pname, ptype), arg in zip(fn.params, expr.arguments):
            arg_t = _type_of_expression(arg, globals_table, locals_table, functions, structs)
            expected = ptype or "int"
            _ensure_assignable(expected, arg_t, arg.line, arg.column)
        return fn.return_type or "int"
    if isinstance(expr, FieldAccess):
        recv_type = _type_of_expression(expr.receiver, globals_table, locals_table, functions, structs)
        if recv_type not in structs:
            raise ValidationError(f"Field access on non-struct type '{recv_type}'", expr.line, expr.column)
        struct_def = structs[recv_type]
        for fld in struct_def.fields:
            if fld.name == expr.field:
                return fld.var_type or "int"
        raise ValidationError(f"Unknown field '{expr.field}' on struct '{recv_type}'", expr.line, expr.column)
    if isinstance(expr, IndexExpr):
        arr_t = _type_of_expression(expr.receiver, globals_table, locals_table, functions, structs)
        if arr_t != "array":
            raise ValidationError(f"Indexing requires array, got '{arr_t}'", expr.line, expr.column)
        idx_t = _type_of_expression(expr.index, globals_table, locals_table, functions, structs)
        _require_numeric(idx_t, expr.index.line, expr.index.column)
        return "int"
    if isinstance(expr, Block):
        scope_locals = dict(locals_table)
        last_type = "void"
        for inner in expr.statements:
            last_type = _type_check_statement_expr(inner, globals_table, scope_locals, functions, structs)
        return last_type
    raise ValidationError("Unsupported expression encountered", expr.line if hasattr(expr, "line") else 0, getattr(expr, "column", 0))


def _type_check_statement_expr(stmt, globals_table: TypeEnv, locals_table: TypeEnv, functions: Dict[str, FunctionDef], structs: Dict[str, StructDef]) -> str:
    # Helper to type-check a statement used as expression; return last expression type or void.
    _type_check_statement(stmt, globals_table, locals_table, functions, structs, func_ret=None)
    return "void"


def _ensure_assignable(expected: str, actual: str, line: int, col: int) -> None:
    if expected == actual:
        return
    # simple numeric widening
    if expected == 'dec' and actual == 'int':
        return
    raise ValidationError(f"Type mismatch: expected {expected}, got {actual}", line, col)


def _ensure_same(t1: str, t2: str, line: int, col: int) -> None:
    if t1 != t2:
        raise ValidationError(f"Type mismatch: {t1} vs {t2}", line, col)


def _require_numeric(t: str, line: int, col: int) -> None:
    if t not in NUMERIC:
        raise ValidationError(f"Numeric type required, got {t}", line, col)


def _require_bool(t: str, line: int, col: int) -> None:
    if t != BOOL:
        raise ValidationError(f"Boolean type required, got {t}", line, col)
