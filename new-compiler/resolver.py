"""
Resolver pass: builds symbol tables and enforces declaration-before-use.
This is a syntax-level semantic check (no types yet).
"""
from typing import Dict, Set
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
    )
    from .validator import ValidationError
except ImportError:  # pragma: no cover - fallback for direct execution
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
    )
    from validator import ValidationError  # type: ignore

BUILTIN_FUNCTIONS: Set[str] = {
    "Print",
    "Clock",
    "Exists",
    "CreateFolder",
    "Open",
    "Close",
    "Read",
    "Write",
    "SHA256",
    "Argc",
    "GetArg",
    "ReadFilesize",
    "GC",
    "Sys",
    "Input",
    "Exit",
    "Sleep",
    "Now",
    "RandInt",
    "Remove",
    "TcpConnect",
    "TcpSend",
    "TcpRecv",
    "TcpClose",
    "TcpResolve",
    "TlsConnect",
    "TlsSend",
    "TlsRecv",
    "TlsClose",
    "HttpGet",
    "HttpDownload",
    "Array",
    "Length",
    "Sqrt",
    "MkdirP",
    "RemoveAll",
    "CopyFile",
    "Unzip",
    "StrConcat",
    "StrLen",
    "StrFind",
    "Substring",
    "GetEnv",
    "Sys",
}


def resolve_program(program: Program) -> tuple[Dict[str, tuple[str, bool]], Dict[str, FunctionDef]]:
    globals_table: Dict[str, tuple[str, bool]] = {}
    functions: Dict[str, FunctionDef] = {}
    structs: Dict[str, StructDef] = {}

    for stmt in program.statements:
        if isinstance(stmt, VarDecl):
            _register_global(stmt, globals_table)
        elif isinstance(stmt, FunctionDef):
            _register_function(stmt, functions)
        elif isinstance(stmt, StructDef):
            if stmt.name in structs:
                raise ValidationError(f"Duplicate struct '{stmt.name}'", stmt.line, stmt.column)
            structs[stmt.name] = stmt

    if "Main" not in functions:
        raise ValidationError("Missing Main function entrypoint", program.line, program.column)

    for stmt in program.statements:
        if isinstance(stmt, FunctionDef):
            _resolve_function(stmt, globals_table, functions, structs)
        elif isinstance(stmt, VarDecl):
            if stmt.value:
                _resolve_expression(stmt.value, globals_table, {}, functions, structs)
        elif isinstance(stmt, StructDef):
            continue
        else:
            _resolve_statement(stmt, globals_table, {}, functions, structs, in_function=False)

    return globals_table, functions


def _register_global(decl: VarDecl, globals_table: Dict[str, tuple[str, bool]]) -> None:
    if decl.name in globals_table:
        raise ValidationError(f"Duplicate global variable '{decl.name}'", decl.line, decl.column)
    inferred = decl.var_type or "int"
    globals_table[decl.name] = (inferred, decl.is_mutable)


def _register_function(func: FunctionDef, functions: Dict[str, FunctionDef]) -> None:
    if func.name in functions:
        raise ValidationError(f"Duplicate function '{func.name}'", func.line, func.column)
    functions[func.name] = func


def _resolve_function(func: FunctionDef, globals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef], structs: Dict[str, StructDef]) -> None:
    locals_table: Dict[str, tuple[str, bool]] = {}
    for pname, ptype in func.params:
        if pname in locals_table:
            raise ValidationError(f"Duplicate parameter '{pname}'", func.line, func.column)
        locals_table[pname] = (ptype or "int", True)

    for stmt in func.body.statements if func.body else []:
        _resolve_statement(stmt, globals_table, locals_table, functions, structs, in_function=True)


def _resolve_statement(stmt, globals_table: Dict[str, tuple[str, bool]], locals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], in_function: bool) -> None:
    if isinstance(stmt, VarDecl):
        if stmt.name in locals_table:
            raise ValidationError(f"Duplicate local variable '{stmt.name}'", stmt.line, stmt.column)
        locals_table[stmt.name] = (stmt.var_type or "int", stmt.is_mutable)
        if stmt.value:
            _resolve_expression(stmt.value, globals_table, locals_table, functions, structs)
    elif isinstance(stmt, Assignment):
        if stmt.target:
            _resolve_expression(stmt.target, globals_table, locals_table, functions, structs)
        else:
            if not in_function and stmt.name not in globals_table:
                raise ValidationError(f"Assignment to undefined global '{stmt.name}'", stmt.line, stmt.column)
            if in_function and stmt.name not in locals_table and stmt.name not in globals_table:
                raise ValidationError(f"Assignment to undefined identifier '{stmt.name}'", stmt.line, stmt.column)
        _resolve_expression(stmt.value, globals_table, locals_table, functions, structs)
    elif isinstance(stmt, FunctionCall):
        _resolve_expression(stmt, globals_table, locals_table, functions, structs)
    elif isinstance(stmt, IfStmt):
        _resolve_expression(stmt.condition, globals_table, locals_table, functions, structs)
        _resolve_statement(stmt.then_block, globals_table, dict(locals_table), functions, structs, in_function)
        if stmt.else_block:
            _resolve_statement(stmt.else_block, globals_table, dict(locals_table), functions, structs, in_function)
    elif isinstance(stmt, WhileStmt):
        _resolve_expression(stmt.condition, globals_table, locals_table, functions, structs)
        _resolve_statement(stmt.body, globals_table, dict(locals_table), functions, structs, in_function)
    elif isinstance(stmt, ForStmt):
        _resolve_expression(stmt.start, globals_table, locals_table, functions, structs)
        _resolve_expression(stmt.end, globals_table, locals_table, functions, structs)
        loop_locals = dict(locals_table)
        loop_locals[stmt.var_name] = ("int", True)
        _resolve_statement(stmt.body, globals_table, loop_locals, functions, structs, in_function)
    elif isinstance(stmt, Block):
        scope_locals = dict(locals_table)
        for inner in stmt.statements:
            _resolve_statement(inner, globals_table, scope_locals, functions, structs, in_function)
    elif isinstance(stmt, ReturnStmt):
        if not in_function:
            raise ValidationError("Return outside of function", stmt.line, stmt.column)
        if stmt.value:
            _resolve_expression(stmt.value, globals_table, locals_table, functions, structs)
    elif isinstance(stmt, StructDef):
        return
    else:
        if hasattr(stmt, "condition") or hasattr(stmt, "body"):
            return
        _resolve_expression(stmt, globals_table, locals_table, functions, structs)


def _resolve_expression(expr, globals_table: Dict[str, tuple[str, bool]], locals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef], structs: Dict[str, StructDef]) -> None:
    if isinstance(expr, Identifier):
        if expr.name in ("argc", "argv"):
            return
        if expr.name not in locals_table and expr.name not in globals_table:
            raise ValidationError(f"Undefined identifier '{expr.name}'", expr.line, expr.column)
    elif isinstance(expr, BinaryExpr):
        _resolve_expression(expr.left, globals_table, locals_table, functions, structs)
        _resolve_expression(expr.right, globals_table, locals_table, functions, structs)
    elif isinstance(expr, UnaryExpr):
        _resolve_expression(expr.operand, globals_table, locals_table, functions, structs)
    elif isinstance(expr, FunctionCall):
        if expr.name not in BUILTIN_FUNCTIONS and expr.name not in functions:
            raise ValidationError(f"Unknown function '{expr.name}'", expr.line, expr.column)
        for arg in expr.arguments:
            _resolve_expression(arg, globals_table, locals_table, functions, structs)
    elif isinstance(expr, FieldAccess):
        _resolve_expression(expr.receiver, globals_table, locals_table, functions, structs)
        recv_type = None
        if isinstance(expr.receiver, Identifier):
            if expr.receiver.name in locals_table:
                recv_type = locals_table[expr.receiver.name][0]
            elif expr.receiver.name in globals_table:
                recv_type = globals_table[expr.receiver.name][0]
        if recv_type and recv_type not in structs:
            raise ValidationError(f"Unknown struct type '{recv_type}' for field access", expr.line, expr.column)
    elif hasattr(expr, "receiver") and hasattr(expr, "index"):
        _resolve_expression(expr.receiver, globals_table, locals_table, functions, structs)
        _resolve_expression(expr.index, globals_table, locals_table, functions, structs)
    elif isinstance(expr, (Literal,)):
        return
    elif isinstance(expr, Block):
        for inner in expr.statements:
            _resolve_statement(inner, globals_table, dict(locals_table), functions, structs, in_function=True)
    else:
        raise ValidationError("Unsupported expression encountered", expr.line if hasattr(expr, "line") else 0, getattr(expr, "column", 0))
