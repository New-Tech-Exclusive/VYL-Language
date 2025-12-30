"""
VYL AST Validator - performs lightweight semantic checks before code generation.

The validator ensures:
- No duplicate global variables or function names
- Assignments target declared globals when outside functions
- Identifiers reference declared symbols
- Function calls reference declared or built-in functions
- A user-defined Main function exists (the code generator always calls it)

The goal is to fail fast with clear diagnostics before code generation.
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
except ImportError:
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
class ValidationError(Exception):
    """Semantic validation failure with location metadata."""

    def __init__(self, message: str, line: int = 0, column: int = 0):
        super().__init__(message)
        self.line = line
        self.column = column

    def __str__(self) -> str:
        location = ""
        if self.line:
            location = f" (line {self.line}, col {self.column})"
        return f"{self.args[0]}{location}"


def validate_program(program: Program) -> None:
    """Validate the AST, raising ValidationError on the first problem."""
    globals_table: Dict[str, tuple[str, bool]] = {}
    functions: Dict[str, FunctionDef] = {}

    # Collect global identifier usage for warnings later
    global_refs: Set[str] = set()
    def _collect_identifiers(node) -> None:
        if isinstance(node, Identifier):
            global_refs.add(node.name)
        elif isinstance(node, FunctionCall):
            for arg in node.arguments:
                _collect_identifiers(arg)
        elif isinstance(node, BinaryExpr):
            _collect_identifiers(node.left)
            _collect_identifiers(node.right)
        elif isinstance(node, UnaryExpr):
            _collect_identifiers(node.operand)
        elif isinstance(node, (VarDecl, Assignment, ReturnStmt)) and getattr(node, 'value', None):
            _collect_identifiers(node.value)
        elif isinstance(node, IfStmt):
            _collect_identifiers(node.condition)
            for inner in (node.then_block.statements if node.then_block else []):
                _collect_identifiers(inner)
            if node.else_block:
                for inner in (node.else_block.statements if hasattr(node.else_block, 'statements') else []):
                    _collect_identifiers(inner)
        elif isinstance(node, WhileStmt):
            _collect_identifiers(node.condition)
            for inner in (node.body.statements if node.body else []):
                _collect_identifiers(inner)
        elif isinstance(node, ForStmt):
            _collect_identifiers(node.start)
            _collect_identifiers(node.end)
            for inner in (node.body.statements if node.body else []):
                _collect_identifiers(inner)
        elif isinstance(node, Block):
            for inner in node.statements:
                _collect_identifiers(inner)


    # First pass: globals and functions
    for stmt in program.statements:
        if isinstance(stmt, VarDecl):
            _register_global(stmt, globals_table)
        elif isinstance(stmt, FunctionDef):
            _register_function(stmt, functions)
        elif isinstance(stmt, StructDef):
            # Struct definitions are accepted but not yet validated semantically
            pass
        _collect_identifiers(stmt)

    # Ensure Main entrypoint exists
    if "Main" not in functions:
        raise ValidationError("Missing Main function entrypoint", program.line, program.column)

    # Second pass: validate statements
    for stmt in program.statements:
        if isinstance(stmt, FunctionDef):
            _validate_function(stmt, globals_table, functions)
        elif isinstance(stmt, VarDecl):
            # Validate initializer, if any, in global scope
            if stmt.value:
                _validate_expression(stmt.value, globals_table, {}, functions)
        elif isinstance(stmt, StructDef):
            continue
        else:
            _validate_statement(stmt, globals_table, {}, functions, in_function=False)

    # Warnings: unused globals
    for gname, (gtype, _) in globals_table.items():
        if gname not in global_refs:
            print(f"Warning: unused global '{gname}'")


def _register_global(decl: VarDecl, globals_table: Dict[str, tuple[str, bool]]) -> None:
    if decl.name in globals_table:
        raise ValidationError(f"Duplicate global variable '{decl.name}'", decl.line, decl.column)
    globals_table[decl.name] = (decl.var_type or "int", decl.is_mutable)


def _register_function(func: FunctionDef, functions: Dict[str, FunctionDef]) -> None:
    if func.name in functions:
        raise ValidationError(f"Duplicate function '{func.name}'", func.line, func.column)
    functions[func.name] = func


def _validate_function(func: FunctionDef, globals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef]) -> None:
    locals_table: Dict[str, tuple[str, bool]] = {}
    local_refs: Set[str] = set()

    # Register parameters as locals (mutable by default for now)
    for pname, ptype in func.params:
        if pname in locals_table:
            raise ValidationError(f"Duplicate parameter '{pname}'", func.line, func.column)
        locals_table[pname] = (ptype or "int", True)

    # Validate the body statements
    for stmt in func.body.statements if func.body else []:
        _validate_statement(stmt, globals_table, locals_table, functions, in_function=True)
        _collect_locals_refs(stmt, local_refs)

    # Warnings: unused locals/params
    for lname in locals_table.keys():
        if lname not in local_refs:
            print(f"Warning: unused local '{lname}' in function {func.name}")


def _collect_locals_refs(node, refs: Set[str]) -> None:
    if isinstance(node, Identifier):
        refs.add(node.name)
    elif isinstance(node, FunctionCall):
        for arg in node.arguments:
            _collect_locals_refs(arg, refs)
    elif isinstance(node, BinaryExpr):
        _collect_locals_refs(node.left, refs)
        _collect_locals_refs(node.right, refs)
    elif isinstance(node, UnaryExpr):
        _collect_locals_refs(node.operand, refs)
    elif hasattr(node, "receiver") and hasattr(node, "index"):
        _collect_locals_refs(node.receiver, refs)
        _collect_locals_refs(node.index, refs)
    elif isinstance(node, (VarDecl, Assignment, ReturnStmt)) and getattr(node, 'value', None):
        _collect_locals_refs(node.value, refs)
    elif isinstance(node, IfStmt):
        _collect_locals_refs(node.condition, refs)
        for inner in (node.then_block.statements if node.then_block else []):
            _collect_locals_refs(inner, refs)
        if node.else_block:
            for inner in (node.else_block.statements if hasattr(node.else_block, 'statements') else []):
                _collect_locals_refs(inner, refs)
    elif isinstance(node, WhileStmt):
        _collect_locals_refs(node.condition, refs)
        for inner in (node.body.statements if node.body else []):
            _collect_locals_refs(inner, refs)
    elif isinstance(node, ForStmt):
        _collect_locals_refs(node.start, refs)
        _collect_locals_refs(node.end, refs)
        for inner in (node.body.statements if node.body else []):
            _collect_locals_refs(inner, refs)
    elif isinstance(node, Block):
        for inner in node.statements:
            _collect_locals_refs(inner, refs)


def _validate_statement(stmt, globals_table: Dict[str, tuple[str, bool]], locals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef], in_function: bool) -> None:
    if isinstance(stmt, VarDecl):
        if stmt.name in locals_table:
            raise ValidationError(f"Duplicate local variable '{stmt.name}'", stmt.line, stmt.column)
        locals_table[stmt.name] = (stmt.var_type or "int", stmt.is_mutable)
        if stmt.value:
            _validate_expression(stmt.value, globals_table, locals_table, functions)
    elif isinstance(stmt, Assignment):
        if stmt.target:
            _validate_expression(stmt.target, globals_table, locals_table, functions)
        else:
            if not in_function and stmt.name not in globals_table:
                raise ValidationError(f"Assignment to undefined global '{stmt.name}'", stmt.line, stmt.column)
            if in_function and stmt.name not in locals_table and stmt.name not in globals_table:
                raise ValidationError(f"Assignment to undefined identifier '{stmt.name}'", stmt.line, stmt.column)
        _validate_expression(stmt.value, globals_table, locals_table, functions)
    elif isinstance(stmt, FunctionCall):
        _validate_expression(stmt, globals_table, locals_table, functions)
    elif isinstance(stmt, IfStmt):
        _validate_expression(stmt.condition, globals_table, locals_table, functions)
        _validate_statement(stmt.then_block, globals_table, dict(locals_table), functions, in_function)
        if stmt.else_block:
            _validate_statement(stmt.else_block, globals_table, dict(locals_table), functions, in_function)
    elif isinstance(stmt, WhileStmt):
        _validate_expression(stmt.condition, globals_table, locals_table, functions)
        _validate_statement(stmt.body, globals_table, dict(locals_table), functions, in_function)
    elif isinstance(stmt, ForStmt):
        _validate_expression(stmt.start, globals_table, locals_table, functions)
        _validate_expression(stmt.end, globals_table, locals_table, functions)
        loop_locals = dict(locals_table)
        loop_locals[stmt.var_name] = ("int", True)
        _validate_statement(stmt.body, globals_table, loop_locals, functions, in_function)
    elif isinstance(stmt, Block):
        scope_locals = dict(locals_table)
        saw_return = False
        for inner in stmt.statements:
            if saw_return:
                print(f"Warning: unreachable code after return at line {inner.line if hasattr(inner, 'line') else 0}")
            _validate_statement(inner, globals_table, scope_locals, functions, in_function)
            if isinstance(inner, ReturnStmt):
                saw_return = True
    elif isinstance(stmt, ReturnStmt):
        if not in_function:
            raise ValidationError("Return outside of function", stmt.line, stmt.column)
        if stmt.value:
            _validate_expression(stmt.value, globals_table, locals_table, functions)
    elif isinstance(stmt, StructDef):
        return
    # Other node types (e.g., expressions used as statements) fall through
    else:
        if hasattr(stmt, "condition") or hasattr(stmt, "body"):
            return  # Already handled structured nodes
        # Treat bare expressions conservatively
        _validate_expression(stmt, globals_table, locals_table, functions)


def _validate_expression(expr, globals_table: Dict[str, tuple[str, bool]], locals_table: Dict[str, tuple[str, bool]], functions: Dict[str, FunctionDef]) -> None:
    if isinstance(expr, Identifier):
        if expr.name in ("argc", "argv"):
            return
        if expr.name not in locals_table and expr.name not in globals_table:
            raise ValidationError(f"Undefined identifier '{expr.name}'", expr.line, expr.column)
    elif isinstance(expr, BinaryExpr):
        _validate_expression(expr.left, globals_table, locals_table, functions)
        _validate_expression(expr.right, globals_table, locals_table, functions)
    elif isinstance(expr, UnaryExpr):
        _validate_expression(expr.operand, globals_table, locals_table, functions)
    elif isinstance(expr, FunctionCall):
        if expr.name not in BUILTIN_FUNCTIONS and expr.name not in functions:
            raise ValidationError(f"Unknown function '{expr.name}'", expr.line, expr.column)
        for arg in expr.arguments:
            _validate_expression(arg, globals_table, locals_table, functions)
    elif isinstance(expr, FieldAccess):
        _validate_expression(expr.receiver, globals_table, locals_table, functions)
    elif hasattr(expr, "receiver") and hasattr(expr, "index"):
        _validate_expression(expr.receiver, globals_table, locals_table, functions)
        _validate_expression(expr.index, globals_table, locals_table, functions)
    elif isinstance(expr, (Literal,)):  # Literals are always valid
        return
    elif isinstance(expr, Block):
        # Validate nested block expressions if ever used
        for inner in expr.statements:
            _validate_statement(inner, globals_table, dict(locals_table), functions, in_function=True)
    else:
        # Catch-all to avoid silent acceptance of future node types
        raise ValidationError("Unsupported expression encountered", expr.line if hasattr(expr, "line") else 0, getattr(expr, "column", 0))
