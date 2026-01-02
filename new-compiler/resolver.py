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
except ImportError:  # pragma: no cover - fallback for direct execution
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
    "OpenDir",
    "ReadDir",
    "CloseDir",
    "Alloc",
    "Free",
    "StrConcat",
    "StrLen",
    "StrFind",
    "Substring",
    "GetEnv",
    "Sys",
    "Len",
}


def resolve_program(program: Program) -> tuple[Dict[str, tuple[str, bool]], Dict[str, FunctionDef]]:
    globals_table: Dict[str, tuple[str, bool]] = {}
    functions: Dict[str, FunctionDef] = {}
    structs: Dict[str, StructDef] = {}
    enums: Dict[str, EnumDef] = {}
    interfaces: Dict[str, InterfaceDef] = {}

    for stmt in program.statements:
        if isinstance(stmt, VarDecl):
            _register_global(stmt, globals_table)
        elif isinstance(stmt, FunctionDef):
            _register_function(stmt, functions)
        elif isinstance(stmt, StructDef):
            if stmt.name in structs:
                raise ValidationError(f"Duplicate struct '{stmt.name}'", stmt.line, stmt.column)
            structs[stmt.name] = stmt
        elif isinstance(stmt, EnumDef):
            if stmt.name in enums:
                raise ValidationError(f"Duplicate enum '{stmt.name}'", stmt.line, stmt.column)
            enums[stmt.name] = stmt
        elif isinstance(stmt, InterfaceDef):
            if stmt.name in interfaces:
                raise ValidationError(f"Duplicate interface '{stmt.name}'", stmt.line, stmt.column)
            interfaces[stmt.name] = stmt

    if "Main" not in functions:
        raise ValidationError("Missing Main function entrypoint", program.line, program.column)

    for stmt in program.statements:
        if isinstance(stmt, FunctionDef):
            _resolve_function(stmt, globals_table, functions, structs, enums)
        elif isinstance(stmt, VarDecl):
            if stmt.value:
                _resolve_expression(stmt.value, globals_table, {}, functions, structs, enums)
        elif isinstance(stmt, StructDef):
            # Resolve method bodies
            for method in stmt.methods:
                _resolve_method(method, stmt, globals_table, functions, structs, enums)
        elif isinstance(stmt, EnumDef):
            continue
        elif isinstance(stmt, InterfaceDef):
            continue
        else:
            _resolve_statement(stmt, globals_table, {}, functions, structs, enums, in_function=False)

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


def _resolve_function(func: FunctionDef, globals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef]) -> None:
    locals_table: Dict[str, tuple[str, bool]] = {}
    for pname, ptype, pdefault in func.params:
        if pname in locals_table:
            raise ValidationError(f"Duplicate parameter '{pname}'", func.line, func.column)
        locals_table[pname] = (ptype or "int", True)

    for stmt in func.body.statements if func.body else []:
        _resolve_statement(stmt, globals_table, locals_table, functions, structs, enums, in_function=True)


def _resolve_method(method: MethodDef, struct: StructDef, globals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef]) -> None:
    """Resolve a method body with 'self' in scope."""
    locals_table: Dict[str, tuple[str, bool]] = {}
    # Add 'self' as implicit first parameter with the struct type
    locals_table["self"] = (struct.name, False)
    for pname, ptype, pdefault in method.params:
        if pname in locals_table:
            raise ValidationError(f"Duplicate parameter '{pname}'", method.line, method.column)
        locals_table[pname] = (ptype or "int", True)

    for stmt in method.body.statements if method.body else []:
        _resolve_statement(stmt, globals_table, locals_table, functions, structs, enums, in_function=True, in_method=True, current_struct=struct)


def _resolve_statement(stmt, globals_table: Dict[str, tuple[str, bool]], locals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef], in_function: bool, in_method: bool = False, current_struct: StructDef = None) -> None:
    if isinstance(stmt, VarDecl):
        if stmt.name in locals_table:
            raise ValidationError(f"Duplicate local variable '{stmt.name}'", stmt.line, stmt.column)
        locals_table[stmt.name] = (stmt.var_type or "int", stmt.is_mutable)
        if stmt.value:
            _resolve_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(stmt, TupleUnpack):
        # Register all tuple variables
        for i, name in enumerate(stmt.names):
            if name in locals_table:
                raise ValidationError(f"Duplicate local variable '{name}'", stmt.line, stmt.column)
            var_type = stmt.types[i] if i < len(stmt.types) else None
            locals_table[name] = (var_type or "int", stmt.is_mutable)
        _resolve_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(stmt, Assignment):
        if stmt.target:
            _resolve_expression(stmt.target, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        else:
            if not in_function and stmt.name not in globals_table:
                raise ValidationError(f"Assignment to undefined global '{stmt.name}'", stmt.line, stmt.column)
            if in_function and stmt.name not in locals_table and stmt.name not in globals_table:
                raise ValidationError(f"Assignment to undefined identifier '{stmt.name}'", stmt.line, stmt.column)
        _resolve_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(stmt, FunctionCall):
        _resolve_expression(stmt, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(stmt, MethodCall):
        _resolve_expression(stmt, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(stmt, IfStmt):
        _resolve_expression(stmt.condition, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _resolve_statement(stmt.then_block, globals_table, dict(locals_table), functions, structs, enums, in_function, in_method, current_struct)
        if stmt.else_block:
            _resolve_statement(stmt.else_block, globals_table, dict(locals_table), functions, structs, enums, in_function, in_method, current_struct)
    elif isinstance(stmt, WhileStmt):
        _resolve_expression(stmt.condition, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _resolve_statement(stmt.body, globals_table, dict(locals_table), functions, structs, enums, in_function, in_method, current_struct)
    elif isinstance(stmt, ForStmt):
        _resolve_expression(stmt.start, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _resolve_expression(stmt.end, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        loop_locals = dict(locals_table)
        loop_locals[stmt.var_name] = ("int", True)
        _resolve_statement(stmt.body, globals_table, loop_locals, functions, structs, enums, in_function, in_method, current_struct)
    elif isinstance(stmt, DeferStmt):
        # Defer body is resolved in the current scope
        _resolve_statement(stmt.body, globals_table, dict(locals_table), functions, structs, enums, in_function, in_method, current_struct)
    elif isinstance(stmt, Block):
        scope_locals = dict(locals_table)
        for inner in stmt.statements:
            _resolve_statement(inner, globals_table, scope_locals, functions, structs, enums, in_function, in_method, current_struct)
    elif isinstance(stmt, ReturnStmt):
        if not in_function and not in_method:
            raise ValidationError("Return outside of function", stmt.line, stmt.column)
        if stmt.value:
            _resolve_expression(stmt.value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(stmt, StructDef):
        return
    elif isinstance(stmt, EnumDef):
        return
    else:
        if hasattr(stmt, "condition") or hasattr(stmt, "body"):
            return
        _resolve_expression(stmt, globals_table, locals_table, functions, structs, enums, in_method, current_struct)


def _resolve_expression(expr, globals_table: Dict[str, tuple[str, bool]], locals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef], structs: Dict[str, StructDef], enums: Dict[str, EnumDef], in_method: bool = False, current_struct: StructDef = None) -> None:
    if isinstance(expr, Identifier):
        if expr.name in ("argc", "argv"):
            return
        if expr.name not in locals_table and expr.name not in globals_table:
            # Check if it's an enum name (will be resolved as EnumAccess via FieldAccess)
            if expr.name not in enums:
                raise ValidationError(f"Undefined identifier '{expr.name}'", expr.line, expr.column)
    elif isinstance(expr, SelfExpr):
        if not in_method:
            raise ValidationError("'self' used outside of method", expr.line, expr.column)
    elif isinstance(expr, BinaryExpr):
        _resolve_expression(expr.left, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _resolve_expression(expr.right, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, UnaryExpr):
        _resolve_expression(expr.operand, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, AddressOf):
        _resolve_expression(expr.operand, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, Dereference):
        _resolve_expression(expr.operand, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, NullLiteral):
        return
    elif isinstance(expr, FunctionCall):
        if expr.name not in BUILTIN_FUNCTIONS and expr.name not in functions:
            raise ValidationError(f"Unknown function '{expr.name}'", expr.line, expr.column)
        for arg in expr.arguments:
            _resolve_expression(arg, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, MethodCall):
        _resolve_expression(expr.receiver, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        for arg in expr.arguments:
            _resolve_expression(arg, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, NewExpr):
        if expr.struct_name not in structs:
            raise ValidationError(f"Unknown struct type '{expr.struct_name}'", expr.line, expr.column)
        for field_name, value in expr.initializers:
            _resolve_expression(value, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, ArrayLiteral):
        for elem in expr.elements:
            _resolve_expression(elem, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, TupleLiteral):
        for elem in expr.elements:
            _resolve_expression(elem, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, InterpString):
        # Interpolated strings have embedded expression strings
        # They get parsed and resolved at codegen time
        return
    elif isinstance(expr, TryExpr):
        # Error propagation expression
        _resolve_expression(expr.operand, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, FieldAccess):
        _resolve_expression(expr.receiver, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        # Check if receiver is an enum (e.g., Status.OK)
        if isinstance(expr.receiver, Identifier) and expr.receiver.name in enums:
            # This is enum variant access
            enum_def = enums[expr.receiver.name]
            variant_names = [v[0] for v in enum_def.variants]
            if expr.field not in variant_names:
                raise ValidationError(f"Unknown variant '{expr.field}' in enum '{expr.receiver.name}'", expr.line, expr.column)
            return
        recv_type = None
        if isinstance(expr.receiver, Identifier):
            if expr.receiver.name in locals_table:
                recv_type = locals_table[expr.receiver.name][0]
            elif expr.receiver.name in globals_table:
                recv_type = globals_table[expr.receiver.name][0]
        if recv_type and recv_type not in structs and recv_type not in enums:
            raise ValidationError(f"Unknown struct type '{recv_type}' for field access", expr.line, expr.column)
    elif hasattr(expr, "receiver") and hasattr(expr, "index"):
        _resolve_expression(expr.receiver, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
        _resolve_expression(expr.index, globals_table, locals_table, functions, structs, enums, in_method, current_struct)
    elif isinstance(expr, (Literal,)):
        return
    elif isinstance(expr, Block):
        for inner in expr.statements:
            _resolve_statement(inner, globals_table, dict(locals_table), functions, structs, enums, in_function=True, in_method=in_method, current_struct=current_struct)
    else:
        raise ValidationError("Unsupported expression encountered", expr.line if hasattr(expr, "line") else 0, getattr(expr, "column", 0))
