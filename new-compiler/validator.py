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
        Block,
        IfStmt,
        WhileStmt,
        ForStmt,
        BinaryExpr,
        UnaryExpr,
        Literal,
        Identifier,
    )
except ImportError:
    from parser import (  # type: ignore
        Program,
        VarDecl,
        Assignment,
        FunctionCall,
        FunctionDef,
        Block,
        IfStmt,
        WhileStmt,
        ForStmt,
        BinaryExpr,
        UnaryExpr,
        Literal,
        Identifier,
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
    globals_table: Dict[str, str] = {}
    functions: Dict[str, FunctionDef] = {}

    # First pass: globals and functions
    for stmt in program.statements:
        if isinstance(stmt, VarDecl):
            _register_global(stmt, globals_table)
        elif isinstance(stmt, FunctionDef):
            _register_function(stmt, functions)

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
        else:
            _validate_statement(stmt, globals_table, {}, functions, in_function=False)


def _register_global(decl: VarDecl, globals_table: Dict[str, str]) -> None:
    if decl.name in globals_table:
        raise ValidationError(f"Duplicate global variable '{decl.name}'", decl.line, decl.column)
    globals_table[decl.name] = decl.var_type or "int"


def _register_function(func: FunctionDef, functions: Dict[str, FunctionDef]) -> None:
    if func.name in functions:
        raise ValidationError(f"Duplicate function '{func.name}'", func.line, func.column)
    functions[func.name] = func


def _validate_function(func: FunctionDef, globals_table: Dict[str, str], functions: Dict[str, FunctionDef]) -> None:
    locals_table: Dict[str, str] = {}

    # Validate the body statements
    for stmt in func.body.statements if func.body else []:
        _validate_statement(stmt, globals_table, locals_table, functions, in_function=True)


def _validate_statement(stmt, globals_table: Dict[str, str], locals_table: Dict[str, str], functions: Dict[str, FunctionDef], in_function: bool) -> None:
    if isinstance(stmt, VarDecl):
        if stmt.name in locals_table:
            raise ValidationError(f"Duplicate local variable '{stmt.name}'", stmt.line, stmt.column)
        locals_table[stmt.name] = stmt.var_type or "int"
        if stmt.value:
            _validate_expression(stmt.value, globals_table, locals_table, functions)
    elif isinstance(stmt, Assignment):
        if not in_function and stmt.name not in globals_table:
            raise ValidationError(f"Assignment to undefined global '{stmt.name}'", stmt.line, stmt.column)
        if in_function and stmt.name not in locals_table and stmt.name not in globals_table:
            # Implicit local to match codegen behavior
            locals_table[stmt.name] = "int"
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
        loop_locals[stmt.var_name] = "int"
        _validate_statement(stmt.body, globals_table, loop_locals, functions, in_function)
    elif isinstance(stmt, Block):
        scope_locals = dict(locals_table)
        for inner in stmt.statements:
            _validate_statement(inner, globals_table, scope_locals, functions, in_function)
    # Other node types (e.g., expressions used as statements) fall through
    else:
        if hasattr(stmt, "condition") or hasattr(stmt, "body"):
            return  # Already handled structured nodes
        # Treat bare expressions conservatively
        _validate_expression(stmt, globals_table, locals_table, functions)


def _validate_expression(expr, globals_table: Dict[str, str], locals_table: Dict[str, str], functions: Dict[str, FunctionDef]) -> None:
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
    elif isinstance(expr, (Literal,)):  # Literals are always valid
        return
    elif isinstance(expr, Block):
        # Validate nested block expressions if ever used
        for inner in expr.statements:
            _validate_statement(inner, globals_table, dict(locals_table), functions, in_function=True)
    else:
        # Catch-all to avoid silent acceptance of future node types
        raise ValidationError("Unsupported expression encountered", expr.line if hasattr(expr, "line") else 0, getattr(expr, "column", 0))
