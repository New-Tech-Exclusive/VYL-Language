"""
Generic instantiation pass for VYL.

This module implements monomorphization - converting generic types like List<int>
into concrete types like List_int.

Strategy:
1. Scan all type usages to find concrete instantiations (e.g., List<int>, Map<string, int>)
2. Generate concrete struct definitions for each instantiation
3. Substitute type parameters in fields, methods, and expressions
"""

from typing import Dict, Set, List, Optional, Tuple
from copy import deepcopy

try:
    from .parser import (
        Program, StructDef, VarDecl, FunctionDef, MethodDef,
        Block, Assignment, FunctionCall, MethodCall, NewExpr,
        BinaryExpr, UnaryExpr, Identifier, Literal, FieldAccess,
        IndexExpr, IfStmt, WhileStmt, ForStmt, ReturnStmt,
        ArrayLiteral, AddressOf, Dereference, SelfExpr,
        TupleLiteral, TupleUnpack, EnumDef, InterfaceDef
    )
except ImportError:
    from parser import (
        Program, StructDef, VarDecl, FunctionDef, MethodDef,
        Block, Assignment, FunctionCall, MethodCall, NewExpr,
        BinaryExpr, UnaryExpr, Identifier, Literal, FieldAccess,
        IndexExpr, IfStmt, WhileStmt, ForStmt, ReturnStmt,
        ArrayLiteral, AddressOf, Dereference, SelfExpr,
        TupleLiteral, TupleUnpack, EnumDef, InterfaceDef
    )


def mangle_generic_name(base_name: str, type_args: List[str]) -> str:
    """Generate mangled name for generic instantiation.
    
    Example: List<int> -> List_int
             Map<string, int> -> Map_string_int
    """
    sanitized_args = []
    for arg in type_args:
        # Handle pointer types
        if arg.startswith('*'):
            sanitized_args.append('ptr_' + arg[1:])
        else:
            sanitized_args.append(arg)
    return base_name + '_' + '_'.join(sanitized_args)


def parse_generic_type(type_str: str) -> Tuple[str, List[str]]:
    """Parse a generic type string into base name and type arguments.
    
    Example: "List<int>" -> ("List", ["int"])
             "Map<string, int>" -> ("Map", ["string", "int"])
             "int" -> ("int", [])
    """
    if '<' not in type_str:
        return (type_str, [])
    
    lt_pos = type_str.index('<')
    base_name = type_str[:lt_pos]
    
    # Find matching >
    depth = 0
    args_str = ""
    for i, ch in enumerate(type_str[lt_pos:]):
        if ch == '<':
            depth += 1
            if depth > 1:
                args_str += ch
        elif ch == '>':
            depth -= 1
            if depth == 0:
                break
            args_str += ch
        elif depth >= 1:
            args_str += ch
    
    # Split by comma (but not nested commas)
    args = []
    current_arg = ""
    depth = 0
    for ch in args_str:
        if ch == '<':
            depth += 1
            current_arg += ch
        elif ch == '>':
            depth -= 1
            current_arg += ch
        elif ch == ',' and depth == 0:
            args.append(current_arg.strip())
            current_arg = ""
        else:
            current_arg += ch
    if current_arg.strip():
        args.append(current_arg.strip())
    
    return (base_name, args)


def substitute_type(type_str: str, substitutions: Dict[str, str]) -> str:
    """Substitute type parameters with concrete types.
    
    Example: substitute_type("T", {"T": "int"}) -> "int"
             substitute_type("*T", {"T": "int"}) -> "*int"
             substitute_type("List<T>", {"T": "int"}) -> "List<int>"
    """
    if not type_str:
        return type_str
    
    # Handle pointer types
    if type_str.startswith('*'):
        inner = substitute_type(type_str[1:], substitutions)
        return '*' + inner
    
    # Handle generic types
    base, args = parse_generic_type(type_str)
    
    # Substitute base if it's a type parameter
    if base in substitutions:
        base = substitutions[base]
    
    # Substitute type arguments
    if args:
        new_args = [substitute_type(arg, substitutions) for arg in args]
        return base + '<' + ', '.join(new_args) + '>'
    
    return base


def find_generic_usages(program: Program, generic_structs: Dict[str, StructDef]) -> Set[str]:
    """Find all concrete instantiations of generic types in the program.
    
    Returns a set of type strings like "List<int>", "Map<string, int>"
    """
    usages: Set[str] = set()
    
    def scan_type(type_str: str):
        if not type_str:
            return
        
        # Strip pointer
        base_type = type_str.lstrip('*')
        base_name, args = parse_generic_type(base_type)
        
        if base_name in generic_structs and args:
            usages.add(base_type)
            # Recursively scan type arguments for nested generics
            for arg in args:
                scan_type(arg)
    
    def scan_expr(expr):
        if expr is None:
            return
        
        if isinstance(expr, NewExpr):
            scan_type(expr.struct_type)
        elif isinstance(expr, VarDecl):
            scan_type(expr.var_type)
        elif isinstance(expr, FunctionCall):
            for arg in expr.arguments:
                scan_expr(arg)
        elif isinstance(expr, MethodCall):
            scan_expr(expr.receiver)
            for arg in expr.arguments:
                scan_expr(arg)
        elif isinstance(expr, BinaryExpr):
            scan_expr(expr.left)
            scan_expr(expr.right)
        elif isinstance(expr, UnaryExpr):
            scan_expr(expr.operand)
        elif isinstance(expr, FieldAccess):
            scan_expr(expr.object)
        elif isinstance(expr, IndexExpr):
            scan_expr(expr.array)
            scan_expr(expr.index)
        elif isinstance(expr, ArrayLiteral):
            for elem in expr.elements:
                scan_expr(elem)
        elif isinstance(expr, AddressOf):
            scan_expr(expr.operand)
        elif isinstance(expr, Dereference):
            scan_expr(expr.operand)
        elif isinstance(expr, TupleLiteral):
            for elem in expr.elements:
                scan_expr(elem)
    
    def scan_stmt(stmt):
        if stmt is None:
            return
        
        if isinstance(stmt, VarDecl):
            scan_type(stmt.var_type)
            scan_expr(stmt.value)
        elif isinstance(stmt, Assignment):
            scan_expr(stmt.value)
            if stmt.target:
                scan_expr(stmt.target)
        elif isinstance(stmt, FunctionCall):
            scan_expr(stmt)
        elif isinstance(stmt, MethodCall):
            scan_expr(stmt)
        elif isinstance(stmt, Block):
            for s in stmt.statements:
                scan_stmt(s)
        elif isinstance(stmt, IfStmt):
            scan_expr(stmt.condition)
            scan_stmt(stmt.then_block)
            if stmt.else_block:
                scan_stmt(stmt.else_block)
        elif isinstance(stmt, WhileStmt):
            scan_expr(stmt.condition)
            scan_stmt(stmt.body)
        elif isinstance(stmt, ForStmt):
            scan_stmt(stmt.init)
            scan_expr(stmt.condition)
            scan_stmt(stmt.update)
            scan_stmt(stmt.body)
        elif isinstance(stmt, ReturnStmt):
            scan_expr(stmt.value)
        elif isinstance(stmt, TupleUnpack):
            scan_expr(stmt.value)
    
    def scan_function(func: FunctionDef):
        for param_name, param_type, param_default in func.params:
            scan_type(param_type)
        scan_type(func.return_type)
        if func.body:
            scan_stmt(func.body)
    
    def scan_method(method: MethodDef):
        for param_name, param_type, param_default in method.params:
            scan_type(param_type)
        scan_type(method.return_type)
        if method.body:
            scan_stmt(method.body)
    
    # Scan all program statements
    for stmt in program.statements:
        if isinstance(stmt, FunctionDef):
            scan_function(stmt)
        elif isinstance(stmt, StructDef):
            for field in stmt.fields:
                scan_type(field.var_type)
            for method in stmt.methods:
                scan_method(method)
        elif isinstance(stmt, VarDecl):
            scan_type(stmt.var_type)
            scan_expr(stmt.value)
    
    return usages


def instantiate_generic(generic_struct: StructDef, type_args: List[str]) -> StructDef:
    """Create a concrete instantiation of a generic struct.
    
    Example: instantiate_generic(List<T>, ["int"]) -> List_int
    """
    # Build substitution map
    substitutions = {}
    for i, param in enumerate(generic_struct.type_params):
        if i < len(type_args):
            substitutions[param] = type_args[i]
    
    # Create mangled name
    mangled_name = mangle_generic_name(generic_struct.name, type_args)
    
    # Deep copy and substitute
    new_struct = StructDef(
        name=mangled_name,
        type_params=[],  # Concrete struct has no type params
        line=generic_struct.line,
        column=generic_struct.column
    )
    
    # Substitute field types
    for field in generic_struct.fields:
        new_field = VarDecl(
            name=field.name,
            var_type=substitute_type(field.var_type, substitutions),
            value=deepcopy(field.value),
            is_mutable=field.is_mutable,
            line=field.line,
            column=field.column
        )
        new_struct.fields.append(new_field)
    
    # Substitute method types
    for method in generic_struct.methods:
        new_params = []
        for param_name, param_type, param_default in method.params:
            new_params.append((param_name, substitute_type(param_type, substitutions), param_default))
        
        new_method = MethodDef(
            name=method.name,
            params=new_params,
            return_type=substitute_type(method.return_type, substitutions),
            body=deepcopy(method.body),  # TODO: substitute types in body
            line=method.line,
            column=method.column
        )
        new_struct.methods.append(new_method)
    
    return new_struct


def instantiate_generics(program: Program) -> Program:
    """Main entry point: instantiate all generics in the program.
    
    This function:
    1. Identifies all generic struct definitions
    2. Finds all concrete usages (List<int>, Map<string, int>, etc.)
    3. Generates concrete struct definitions
    4. Updates all type references to use mangled names
    """
    # Find generic structs
    generic_structs: Dict[str, StructDef] = {}
    for stmt in program.statements:
        if isinstance(stmt, StructDef) and stmt.type_params:
            generic_structs[stmt.name] = stmt
    
    if not generic_structs:
        return program  # No generics to instantiate
    
    # Find all usages
    usages = find_generic_usages(program, generic_structs)
    
    if not usages:
        return program  # No instantiations needed
    
    # Generate concrete structs
    concrete_structs: List[StructDef] = []
    type_mappings: Dict[str, str] = {}  # Original type -> mangled name
    
    for usage in usages:
        base_name, type_args = parse_generic_type(usage)
        if base_name in generic_structs:
            concrete = instantiate_generic(generic_structs[base_name], type_args)
            concrete_structs.append(concrete)
            type_mappings[usage] = concrete.name
    
    # Create new program with concrete structs added and generics removed
    new_statements = []
    for stmt in program.statements:
        if isinstance(stmt, StructDef) and stmt.type_params:
            continue  # Skip generic definitions
        new_statements.append(stmt)
    
    # Add concrete structs at the beginning (after any globals)
    insert_pos = 0
    for i, stmt in enumerate(new_statements):
        if isinstance(stmt, (FunctionDef, StructDef)):
            insert_pos = i
            break
    
    for concrete in concrete_structs:
        new_statements.insert(insert_pos, concrete)
        insert_pos += 1
    
    # TODO: Update all type references in the program to use mangled names
    # This requires walking the entire AST and substituting types
    
    new_program = Program(statements=new_statements)
    return new_program


# Convenience function for testing
def print_generic_info(program: Program):
    """Print information about generics in the program."""
    for stmt in program.statements:
        if isinstance(stmt, StructDef) and stmt.type_params:
            print(f"Generic struct: {stmt.name}<{', '.join(stmt.type_params)}>")
            for field in stmt.fields:
                print(f"  Field: {field.name}: {field.var_type}")
