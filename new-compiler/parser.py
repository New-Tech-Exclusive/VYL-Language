"""
VYL Parser - Builds an Abstract Syntax Tree (AST) from token stream

This module parses tokens from the lexer and constructs an AST that represents
the program structure. The AST is then used by the code generator to produce
assembly code.

AST Node Types:
    - Program: Root node containing all statements
    - VarDecl: Variable declarations
    - Assignment: Variable assignments
    - FunctionCall: Function calls (including Print and Clock)
    - FunctionDef: Function definitions with parameters
    - ReturnStmt: Return statements
    - Block: Code blocks ( {...} )
    - IfStmt: Conditional statements
    - WhileStmt: While loops
    - ForStmt: For loops
    - BinaryExpr: Binary expressions (a + b, a * b, etc.)
    - UnaryExpr: Unary expressions (-a, +a)
    - Literal: Integer, decimal, string, boolean literals
    - Identifier: Variable references
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
try:
    from .lexer import Token
except ImportError:
    from lexer import Token


@dataclass
class ASTNode:
    """Base class for all AST nodes"""
    line: int = 0
    column: int = 0


@dataclass
class Program(ASTNode):
    """Root node containing all program statements"""
    statements: List[ASTNode] = field(default_factory=list)


@dataclass
class VarDecl(ASTNode):
    """Variable declaration: var name [type] [= value]"""
    name: str = ""
    var_type: Optional[str] = None  # 'int', 'dec', 'string', 'bool'
    value: Optional[ASTNode] = None
    is_mutable: bool = True


@dataclass
class Assignment(ASTNode):
    """Variable assignment: name = value"""
    name: str = ""  # for simple identifier assignments
    value: ASTNode = None
    target: Optional[ASTNode] = None  # can be FieldAccess when assigning to a field


@dataclass
class FunctionCall(ASTNode):
    """Function call: name(args)"""
    name: str = ""
    arguments: List[ASTNode] = field(default_factory=list)


@dataclass
class FunctionDef(ASTNode):
    """Function definition: name(params) [-> return_type] { ... }"""
    name: str = ""
    params: List[tuple[str, Optional[str], Optional[ASTNode]]] = field(default_factory=list)  # (name, type, default)
    return_type: Optional[str] = None
    body: Optional['Block'] = None
    type_params: List[str] = field(default_factory=list)  # Generic type parameters like [T, K]


@dataclass
class StructDef(ASTNode):
    """Struct definition: struct Name { fields, methods }"""
    name: str = ""
    fields: List['VarDecl'] = field(default_factory=list)
    methods: List['MethodDef'] = field(default_factory=list)
    type_params: List[str] = field(default_factory=list)  # Generic type parameters


@dataclass
class ReturnStmt(ASTNode):
    """Return statement: return [expr]"""
    value: Optional[ASTNode] = None


@dataclass
class DeferStmt(ASTNode):
    """Defer statement: defer { block } or defer statement;
    
    Deferred code runs when the enclosing function returns.
    """
    body: 'Block' = None


@dataclass
class Block(ASTNode):
    """Code block: { statements }"""
    statements: List[ASTNode] = field(default_factory=list)
    deferred: List['DeferStmt'] = field(default_factory=list)  # Deferred statements


@dataclass
class IfStmt(ASTNode):
    """If statement: if (condition) { then_block } [else { else_block }]"""
    condition: ASTNode = None
    then_block: Block = None
    else_block: Optional[Block] = None


@dataclass
class WhileStmt(ASTNode):
    """While loop: while (condition) { body }"""
    condition: ASTNode = None
    body: Block = None


@dataclass
class ForStmt(ASTNode):
    """For loop: for var in start..end { body }"""
    var_name: str = ""
    start: ASTNode = None
    end: ASTNode = None
    body: Block = None


@dataclass
class BinaryExpr(ASTNode):
    """Binary expression: left op right"""
    left: ASTNode = None
    operator: str = ""
    right: ASTNode = None


@dataclass
class UnaryExpr(ASTNode):
    """Unary expression: op operand"""
    operator: str = ""
    operand: ASTNode = None


@dataclass
class Literal(ASTNode):
    """Literal value: integer, decimal, string, or boolean"""
    value: Any = None
    literal_type: str = ""  # 'int', 'dec', 'string', 'bool'


@dataclass
class InterpString(ASTNode):
    """Interpolated string: "Hello {name}!"
    
    The parts list contains tuples of (is_expr, value):
    - (False, "Hello ") - literal string part
    - (True, "name") - expression part (as string, to be parsed)
    """
    parts: List[tuple] = field(default_factory=list)  # [(is_expr, value), ...]


@dataclass
class Identifier(ASTNode):
    """Variable reference"""
    name: str = ""


@dataclass
class FieldAccess(ASTNode):
    """Field access: expr.field"""
    receiver: ASTNode = None
    field: str = ""


@dataclass
class IndexExpr(ASTNode):
    """Index access: expr[index]"""
    receiver: ASTNode = None
    index: ASTNode = None


@dataclass
class NewExpr(ASTNode):
    """New struct expression: new StructName or StructName{field: value, ...}"""
    struct_name: str = ""
    initializers: List[tuple[str, ASTNode]] = field(default_factory=list)  # list of (field_name, value) pairs


@dataclass
class ArrayLiteral(ASTNode):
    """Array literal: [expr1, expr2, ...]"""
    elements: List[ASTNode] = field(default_factory=list)
    element_type: Optional[str] = None  # inferred or explicit type


@dataclass
class EnumDef(ASTNode):
    """Enum definition: Enum Name { VALUE1, VALUE2 = 10, ... }"""
    name: str = ""
    variants: List[tuple[str, Optional[int]]] = field(default_factory=list)  # (name, optional_value)


@dataclass
class InterfaceDef(ASTNode):
    """Interface definition: Interface Name { method signatures }"""
    name: str = ""
    methods: List['InterfaceMethod'] = field(default_factory=list)


@dataclass
class InterfaceMethod(ASTNode):
    """Method signature in an interface"""
    name: str = ""
    params: List[tuple[str, Optional[str]]] = field(default_factory=list)
    return_type: Optional[str] = None


@dataclass
class EnumAccess(ASTNode):
    """Enum value access: EnumName.VARIANT"""
    enum_name: str = ""
    variant: str = ""


@dataclass
class MethodDef(ASTNode):
    """Method definition inside a struct"""
    name: str = ""
    params: List[tuple[str, Optional[str]]] = field(default_factory=list)
    return_type: Optional[str] = None
    body: Optional['Block'] = None


@dataclass
class MethodCall(ASTNode):
    """Method call: expr.method(args)"""
    receiver: ASTNode = None
    method_name: str = ""
    arguments: List[ASTNode] = field(default_factory=list)


@dataclass
class SelfExpr(ASTNode):
    """Self reference in methods"""
    pass


@dataclass
class AddressOf(ASTNode):
    """Address-of expression: &expr"""
    operand: ASTNode = None


@dataclass
class Dereference(ASTNode):
    """Dereference expression: *expr"""
    operand: ASTNode = None


@dataclass
class NullLiteral(ASTNode):
    """Null pointer literal"""
    pass


@dataclass
class TryExpr(ASTNode):
    """Error propagation expression: expr?
    
    If expr evaluates to < 0, return early with that value.
    Otherwise, continue with the value.
    """
    operand: ASTNode = None


@dataclass
class TupleLiteral(ASTNode):
    """Tuple literal: (expr1, expr2, ...)"""
    elements: List[ASTNode] = field(default_factory=list)


@dataclass
class TupleUnpack(ASTNode):
    """Tuple unpacking declaration: var x, y = expr"""
    names: List[str] = field(default_factory=list)
    types: List[Optional[str]] = field(default_factory=list)
    value: ASTNode = None
    is_mutable: bool = True
    pass


class Parser:
    """
    Parser for VYL source code
    
    Converts a stream of tokens into an AST.
    Uses recursive descent parsing with operator precedence.
    """
    
    def __init__(self, tokens: List[Token]):
        """
        Initialize the parser with tokens
        
        Args:
            tokens: List of tokens from the lexer
        """
        self.tokens = tokens
        self.position = 0
        self.current_token = tokens[0] if tokens else None
    
    def peek(self, offset: int = 0) -> Optional[Token]:
        """Look ahead at token without consuming it"""
        pos = self.position + offset
        return self.tokens[pos] if pos < len(self.tokens) else None
    
    def advance(self):
        """Move to the next token"""
        self.position += 1
        if self.position < len(self.tokens):
            self.current_token = self.tokens[self.position]
        else:
            self.current_token = None
    
    def consume(self, expected_type: str) -> Token:
        """
        Consume a token of expected type
        
        Args:
            expected_type: Expected token type
            
        Returns:
            The consumed token
            
        Raises:
            SyntaxError: If current token doesn't match expected type
        """
        if self.current_token is None:
            raise SyntaxError(f"Expected {expected_type}, got EOF")
        
        if self.current_token.type != expected_type:
            raise SyntaxError(
                f"Expected {expected_type}, got {self.current_token.type} "
                f"at line {self.current_token.line}"
            )
        
        token = self.current_token
        self.advance()
        return token
    
    def skip_newlines(self):
        """Skip optional newlines"""
        while self.current_token and self.current_token.type == 'NEWLINE':
            self.advance()
    
    def parse(self) -> Program:
        """Parse the entire program"""
        program = Program()
        self.skip_newlines()
        
        while self.current_token and self.current_token.type != 'EOF':
            stmt = self.parse_statement()
            if stmt:
                program.statements.append(stmt)
            self.skip_newlines()
        
        return program
    
    def parse_statement(self) -> Optional[ASTNode]:
        """Parse a single statement"""
        if not self.current_token:
            return None
        
        token_type = self.current_token.type
        
        # Skip empty statements
        if token_type == 'SEMICOLON':
            self.advance()
            return None
        
        # Parse the statement
        stmt = None
        if token_type == 'VAR':
            stmt = self.parse_var_decl()
        elif token_type == 'LET':
            stmt = self.parse_let_decl()
        elif token_type == 'FUNCTION':
            stmt = self.parse_function_decl()
        elif token_type == 'STRUCT':
            stmt = self.parse_struct_decl()
        elif token_type == 'ENUM':
            stmt = self.parse_enum_decl()
        elif token_type == 'INTERFACE':
            stmt = self.parse_interface_decl()
        elif token_type == 'RETURN':
            stmt = self.parse_return()
        elif token_type == 'IDENTIFIER':
            # Check if this is a shorthand function definition: Name() { ... }
            if self.peek(1) and self.peek(1).type == 'LPAREN':
                # Lookahead to find matching ) and check for {
                save_pos = self.position
                self.advance()  # consume identifier
                self.consume('LPAREN')
                # Skip to matching RPAREN
                depth = 1
                while self.current_token and depth > 0:
                    if self.current_token.type == 'LPAREN':
                        depth += 1
                    elif self.current_token.type == 'RPAREN':
                        depth -= 1
                    if depth > 0:
                        self.advance()
                if self.current_token and self.current_token.type == 'RPAREN':
                    self.advance()  # consume RPAREN
                # Check for ARROW or LBRACE after params
                is_func_def = False
                if self.current_token:
                    if self.current_token.type == 'LBRACE':
                        is_func_def = True
                    elif self.current_token.type == 'ARROW':
                        is_func_def = True
                # Restore position and parse appropriately
                self.position = save_pos
                self.current_token = self.tokens[self.position] if self.position < len(self.tokens) else None
                if is_func_def:
                    stmt = self.parse_shorthand_function_decl()
                else:
                    stmt = self.parse_assignment_or_call()
            else:
                stmt = self.parse_assignment_or_call()
        elif token_type == 'SELF':
            # self.field = value or self.method(args)
            stmt = self.parse_self_expression_statement()
        elif token_type == 'STAR':
            # *ptr = value (dereference assignment)
            stmt = self.parse_dereference_assignment()
        elif token_type == 'IF':
            stmt = self.parse_if()
        elif token_type == 'WHILE':
            stmt = self.parse_while()
        elif token_type == 'FOR':
            stmt = self.parse_for()
        elif token_type == 'DEFER':
            stmt = self.parse_defer()
        else:
            raise SyntaxError(
                f"Unexpected token {token_type} at line {self.current_token.line}"
            )
        
        # Require semicolon after statement
        if stmt and not isinstance(stmt, (IfStmt, WhileStmt, ForStmt, FunctionDef, Block, StructDef, EnumDef, InterfaceDef, DeferStmt)):
            if not self.current_token or self.current_token.type != 'SEMICOLON':
                raise SyntaxError(
                    f"Expected ';' after statement at line {stmt.line}"
                )
            self.consume('SEMICOLON')
        
        return stmt

    def parse_function_decl(self) -> FunctionDef:
        """Parse: Function name(params) [-> type] { ... }"""
        fn_token = self.consume('FUNCTION')
        name_tok = self.consume('IDENTIFIER')
        self.consume('LPAREN')
        params: List[tuple[str, Optional[str]]] = []
        if self.current_token and self.current_token.type != 'RPAREN':
            params.append(self.parse_param())
            while self.current_token and self.current_token.type == 'COMMA':
                self.consume('COMMA')
                params.append(self.parse_param())
        self.consume('RPAREN')

        return_type: Optional[str] = None
        if self.current_token and self.current_token.type == 'ARROW':
            self.consume('ARROW')
            return_type = self.parse_type_annotation()

        body = self.parse_block()
        return FunctionDef(name=name_tok.value, params=params, return_type=return_type, body=body, line=fn_token.line, column=fn_token.column)

    def parse_shorthand_function_decl(self) -> FunctionDef:
        """Parse shorthand function: name(params) [-> type] { ... } (without 'Function' keyword)"""
        name_tok = self.consume('IDENTIFIER')
        self.consume('LPAREN')
        params: List[tuple[str, Optional[str]]] = []
        if self.current_token and self.current_token.type != 'RPAREN':
            params.append(self.parse_param())
            while self.current_token and self.current_token.type == 'COMMA':
                self.consume('COMMA')
                params.append(self.parse_param())
        self.consume('RPAREN')

        return_type: Optional[str] = None
        if self.current_token and self.current_token.type == 'ARROW':
            self.consume('ARROW')
            return_type = self.parse_type_annotation()

        body = self.parse_block()
        return FunctionDef(name=name_tok.value, params=params, return_type=return_type, body=body, line=name_tok.line, column=name_tok.column)

    def parse_param(self) -> tuple[str, Optional[str], Optional[ASTNode]]:
        """Parse a function parameter: name: type [= default]"""
        name_tok = self.consume('IDENTIFIER')
        param_type: Optional[str] = None
        default_value: Optional[ASTNode] = None
        
        if self.current_token and self.current_token.type == 'COLON':
            self.consume('COLON')
            param_type = self.parse_type_annotation()
        
        # Check for default value
        if self.current_token and self.current_token.type == 'ASSIGN':
            self.consume('ASSIGN')
            default_value = self.parse_expression()
        
        return (name_tok.value, param_type, default_value)


    def parse_struct_decl(self) -> StructDef:
        """Parse: struct Name<T> { fields and methods }"""
        struct_tok = self.consume('STRUCT')
        struct_name_tok = self.consume('IDENTIFIER')
        struct_name = struct_name_tok.value
        
        # Parse generic type parameters: <T, K, V>
        type_params: List[str] = []
        if self.current_token and self.current_token.type == 'LT':
            self.consume('LT')
            type_params.append(self.consume('IDENTIFIER').value)
            while self.current_token and self.current_token.type == 'COMMA':
                self.consume('COMMA')
                type_params.append(self.consume('IDENTIFIER').value)
            self.consume('GT')
        
        self.consume('LBRACE')
        self.skip_newlines()

        fields: List[VarDecl] = []
        methods: List[MethodDef] = []
        while self.current_token and self.current_token.type != 'RBRACE':
            if self.current_token.type == 'VAR':
                # Parse a field: var <type-or-identifier> <name>;
                self.consume('VAR')
                field_type = self.parse_type_annotation() if self.current_token else None

                field_name_tok = self.consume('IDENTIFIER')
                field_decl = VarDecl(name=field_name_tok.value, var_type=field_type, value=None, is_mutable=True,
                                     line=field_name_tok.line, column=field_name_tok.column)

                if not self.current_token or self.current_token.type != 'SEMICOLON':
                    raise SyntaxError(
                        f"Expected ';' after field in struct at line {field_decl.line}"
                    )
                self.consume('SEMICOLON')
                fields.append(field_decl)
            elif self.current_token.type == 'FUNCTION':
                # Parse a method
                method = self.parse_method_decl()
                methods.append(method)
            else:
                raise SyntaxError(
                    f"Expected field or method declaration in struct at line {self.current_token.line}"
                )
            self.skip_newlines()

        self.consume('RBRACE')
        return StructDef(name=struct_name, fields=fields, methods=methods, type_params=type_params, line=struct_tok.line, column=struct_tok.column)

    def parse_method_decl(self) -> MethodDef:
        """Parse: Function name(params) [-> type] { ... } inside a struct"""
        fn_token = self.consume('FUNCTION')
        name_tok = self.consume('IDENTIFIER')
        self.consume('LPAREN')
        params: List[tuple[str, Optional[str]]] = []
        if self.current_token and self.current_token.type != 'RPAREN':
            params.append(self.parse_param())
            while self.current_token and self.current_token.type == 'COMMA':
                self.consume('COMMA')
                params.append(self.parse_param())
        self.consume('RPAREN')

        return_type: Optional[str] = None
        if self.current_token and self.current_token.type == 'ARROW':
            self.consume('ARROW')
            return_type = self.parse_type_annotation()

        body = self.parse_block()
        return MethodDef(name=name_tok.value, params=params, return_type=return_type, body=body, line=fn_token.line, column=fn_token.column)

    def parse_enum_decl(self) -> EnumDef:
        """Parse: Enum Name { VARIANT1, VARIANT2 = 10, ... }"""
        enum_tok = self.consume('ENUM')
        name_tok = self.consume('IDENTIFIER')
        self.consume('LBRACE')
        self.skip_newlines()

        variants: List[tuple[str, Optional[int]]] = []
        current_value = 0
        while self.current_token and self.current_token.type != 'RBRACE':
            variant_tok = self.consume('IDENTIFIER')
            variant_value = None
            
            if self.current_token and self.current_token.type == 'ASSIGN':
                self.consume('ASSIGN')
                value_tok = self.consume('INTEGER')
                variant_value = value_tok.int_value
                current_value = variant_value
            else:
                variant_value = current_value
            
            variants.append((variant_tok.value, variant_value))
            current_value += 1
            
            if self.current_token and self.current_token.type == 'COMMA':
                self.consume('COMMA')
            self.skip_newlines()

        self.consume('RBRACE')
        return EnumDef(name=name_tok.value, variants=variants, line=enum_tok.line, column=enum_tok.column)

    def parse_interface_decl(self) -> InterfaceDef:
        """Parse: Interface Name { method signatures }"""
        interface_tok = self.consume('INTERFACE')
        name_tok = self.consume('IDENTIFIER')
        self.consume('LBRACE')
        self.skip_newlines()

        methods: List[InterfaceMethod] = []
        while self.current_token and self.current_token.type != 'RBRACE':
            # Parse: Function methodName(params) -> returnType;
            self.consume('FUNCTION')
            method_name = self.consume('IDENTIFIER')
            self.consume('LPAREN')
            
            params: List[tuple[str, Optional[str]]] = []
            if self.current_token and self.current_token.type != 'RPAREN':
                param_name = self.consume('IDENTIFIER')
                self.consume('COLON')
                param_type = self.parse_type_annotation()
                params.append((param_name.value, param_type))
                
                while self.current_token and self.current_token.type == 'COMMA':
                    self.consume('COMMA')
                    param_name = self.consume('IDENTIFIER')
                    self.consume('COLON')
                    param_type = self.parse_type_annotation()
                    params.append((param_name.value, param_type))
            
            self.consume('RPAREN')
            
            return_type = None
            if self.current_token and self.current_token.type == 'ARROW':
                self.consume('ARROW')
                return_type = self.parse_type_annotation()
            
            self.consume('SEMICOLON')
            methods.append(InterfaceMethod(name=method_name.value, params=params, return_type=return_type))
            self.skip_newlines()

        self.consume('RBRACE')
        return InterfaceDef(name=name_tok.value, methods=methods, line=interface_tok.line, column=interface_tok.column)

    def parse_type_annotation(self) -> str:
        if not self.current_token:
            raise SyntaxError("Expected type annotation")
        
        # Handle tuple types: (int, string), (int, int, int)
        if self.current_token.type == 'LPAREN':
            self.consume('LPAREN')
            types = []
            if self.current_token and self.current_token.type != 'RPAREN':
                types.append(self.parse_type_annotation())
                while self.current_token and self.current_token.type == 'COMMA':
                    self.consume('COMMA')
                    types.append(self.parse_type_annotation())
            self.consume('RPAREN')
            return '(' + ', '.join(types) + ')'
        
        # Handle pointer types: *int, *string, etc.
        if self.current_token.type == 'STAR':
            self.advance()
            inner_type = self.parse_type_annotation()
            return '*' + inner_type
        
        tok = self.current_token
        if tok.type in ['INT_TYPE', 'DEC_TYPE', 'STRING_TYPE', 'BOOL_TYPE', 'INF_TYPE', 'ARRAY_TYPE']:
            self.advance()
            return tok.value
        if tok.type == 'IDENTIFIER':
            # Struct type or enum type
            self.advance()
            return tok.value
        raise SyntaxError(f"Expected type, got {tok.type}")

    def parse_return(self) -> ReturnStmt:
        """Parse: return [expr]"""
        tok = self.consume('RETURN')
        if self.current_token and self.current_token.type not in ('SEMICOLON', 'NEWLINE', 'RBRACE'):
            value = self.parse_expression()
        else:
            value = None
        return ReturnStmt(value=value, line=tok.line, column=tok.column)
    
    def parse_var_decl(self) -> ASTNode:
        """Parse: var [type] name [= value] OR var x, y = tuple_expr"""
        var_tok = self.consume('VAR')

        # Check for tuple unpacking: var x, y = ... or var int x, int y = ...
        # Look ahead to detect comma pattern
        save_pos = self.position
        
        # Try to parse first variable (possibly with type)
        var_type = None
        if self.current_token and self.current_token.type == 'STAR':
            # Pointer type
            self.advance()
            inner_type = self.parse_type_annotation()
            var_type = '*' + inner_type
        elif self.current_token and self.current_token.type in ['INT_TYPE', 'DEC_TYPE', 'STRING_TYPE', 'BOOL_TYPE', 'INF_TYPE', 'ARRAY_TYPE']:
            var_type = self.current_token.value
            self.advance()
            if self.current_token and self.current_token.type == 'LBRACKET':
                self.advance()
                self.consume('RBRACKET')
                var_type = var_type + '[]'
        elif self.current_token and self.current_token.type == 'IDENTIFIER':
            next_tok = self.peek(1)
            if next_tok and next_tok.type == 'IDENTIFIER':
                var_type = self.current_token.value
                self.advance()
            elif next_tok and next_tok.type == 'LBRACKET':
                var_type = self.current_token.value
                self.advance()
                self.advance()
                self.consume('RBRACKET')
                var_type = var_type + '[]'

        if not self.current_token or self.current_token.type != 'IDENTIFIER':
            raise SyntaxError(f"Expected variable name at line {var_tok.line}")
        
        first_name = self.consume('IDENTIFIER')
        
        # Check if this is tuple unpacking (comma after first name)
        if self.current_token and self.current_token.type == 'COMMA':
            # This is tuple unpacking: var x, y = ...
            names = [first_name.value]
            types = [var_type]
            
            while self.current_token and self.current_token.type == 'COMMA':
                self.consume('COMMA')
                # Parse optional type for next variable
                next_type = None
                if self.current_token and self.current_token.type in ['INT_TYPE', 'DEC_TYPE', 'STRING_TYPE', 'BOOL_TYPE', 'INF_TYPE', 'ARRAY_TYPE']:
                    next_type = self.current_token.value
                    self.advance()
                elif self.current_token and self.current_token.type == 'IDENTIFIER':
                    # Could be type or name - lookahead
                    lookahead = self.peek(1)
                    if lookahead and lookahead.type == 'IDENTIFIER':
                        next_type = self.current_token.value
                        self.advance()
                
                name_tok = self.consume('IDENTIFIER')
                names.append(name_tok.value)
                types.append(next_type)
            
            if not self.current_token or self.current_token.type != 'ASSIGN':
                raise SyntaxError(f"Tuple unpacking requires initialization at line {var_tok.line}")
            self.consume('ASSIGN')
            value = self.parse_expression()
            
            return TupleUnpack(names=names, types=types, value=value, is_mutable=True,
                               line=var_tok.line, column=var_tok.column)
        
        # Regular variable declaration
        value = None
        if self.current_token and self.current_token.type == 'ASSIGN':
            self.consume('ASSIGN')
            value = self.parse_expression()

        return VarDecl(name=first_name.value, var_type=var_type, value=value, is_mutable=True,
                      line=first_name.line, column=first_name.column)

    def parse_let_decl(self) -> VarDecl:
        """Parse: let [mut] name [: type] [= value] (immutable by default)"""
        self.consume('LET')
        is_mutable = False
        if self.current_token and self.current_token.type == 'MUT':
            self.consume('MUT')
            is_mutable = True

        name_token = self.consume('IDENTIFIER')
        name = name_token.value

        var_type = None
        if self.current_token and self.current_token.type == 'COLON':
            self.consume('COLON')
            var_type = self.parse_type_annotation()

        value = None
        if self.current_token and self.current_token.type == 'ASSIGN':
            self.consume('ASSIGN')
            value = self.parse_expression()

        return VarDecl(name=name, var_type=var_type, value=value, is_mutable=is_mutable,
                      line=name_token.line, column=name_token.column)
    
    def parse_dereference_assignment(self) -> Assignment:
        """Parse *ptr = value (assignment through dereference)"""
        star_tok = self.consume('STAR')
        operand = self.parse_unary()  # Parse the operand being dereferenced
        deref = Dereference(operand=operand, line=star_tok.line, column=star_tok.column)
        
        if not self.current_token or self.current_token.type != 'ASSIGN':
            raise SyntaxError(f"Expected '=' after dereference at line {star_tok.line}")
        self.consume('ASSIGN')
        value = self.parse_expression()
        return Assignment(name="", value=value, target=deref,
                          line=star_tok.line, column=star_tok.column)
    
    def parse_self_expression_statement(self) -> ASTNode:
        """Parse self.field = value or self.method(args)"""
        self_tok = self.consume('SELF')
        node: ASTNode = SelfExpr(line=self_tok.line, column=self_tok.column)
        
        # Must have field access after self
        if not self.current_token or self.current_token.type != 'DOT':
            raise SyntaxError(f"Expected '.' after 'self' at line {self_tok.line}")
        
        # Parse field/method chain
        while self.current_token and self.current_token.type in ('DOT', 'LBRACKET'):
            if self.current_token.type == 'DOT':
                self.consume('DOT')
                field_tok = self.consume('IDENTIFIER')
                # Check if this is a method call: self.method(args)
                if self.current_token and self.current_token.type == 'LPAREN':
                    self.consume('LPAREN')
                    args = []
                    if self.current_token and self.current_token.type != 'RPAREN':
                        args.append(self.parse_expression())
                        while self.current_token and self.current_token.type == 'COMMA':
                            self.consume('COMMA')
                            args.append(self.parse_expression())
                    self.consume('RPAREN')
                    node = MethodCall(receiver=node, method_name=field_tok.value, arguments=args,
                                      line=field_tok.line, column=field_tok.column)
                else:
                    node = FieldAccess(receiver=node, field=field_tok.value,
                                        line=field_tok.line, column=field_tok.column)
            else:
                lbr = self.consume('LBRACKET')
                idx_expr = self.parse_expression()
                self.consume('RBRACKET')
                node = IndexExpr(receiver=node, index=idx_expr,
                                 line=lbr.line, column=lbr.column)
        
        # Method call is a statement by itself
        if isinstance(node, MethodCall):
            return node
        
        # Expect assignment for field access
        if not self.current_token or self.current_token.type != 'ASSIGN':
            raise SyntaxError(f"Expected '=' after self field access at line {node.line}")
        self.consume('ASSIGN')
        value = self.parse_expression()
        return Assignment(name="", value=value, target=node,
                          line=node.line, column=node.column)
    
    def parse_assignment_or_call(self) -> ASTNode:
        """Parse assignment or function call (supports field lvalues)."""
        lhs = self.parse_postfix_identifier()

        # Function call or method call already produced by postfix
        if isinstance(lhs, (FunctionCall, MethodCall)):
            return lhs

        # Expect assignment
        if not self.current_token or self.current_token.type != 'ASSIGN':
            raise SyntaxError(f"Expected ASSIGN, got {self.current_token.type if self.current_token else 'EOF'} at line {lhs.line}")
        self.consume('ASSIGN')
        value = self.parse_expression()

        if isinstance(lhs, Identifier):
            return Assignment(name=lhs.name, value=value, target=None,
                              line=lhs.line, column=lhs.column)
        if isinstance(lhs, (FieldAccess, IndexExpr)):
            return Assignment(name="", value=value, target=lhs,
                              line=lhs.line, column=lhs.column)
        raise SyntaxError("Invalid assignment target")

    def parse_postfix_identifier(self) -> ASTNode:
        """Parse identifier with optional call, indexing, field access, method calls, or error propagation."""
        name_token = self.consume('IDENTIFIER')
        node: ASTNode = Identifier(name=name_token.value, line=name_token.line, column=name_token.column)

        # Function call suffix
        if self.current_token and self.current_token.type == 'LPAREN':
            self.consume('LPAREN')
            arguments = []
            if self.current_token and self.current_token.type != 'RPAREN':
                arguments.append(self.parse_expression())
                while self.current_token and self.current_token.type == 'COMMA':
                    self.consume('COMMA')
                    arguments.append(self.parse_expression())
            self.consume('RPAREN')
            node = FunctionCall(name=name_token.value, arguments=arguments,
                                line=name_token.line, column=name_token.column)

        # Field/index/method/error-propagation chain (left-to-right)
        while self.current_token and self.current_token.type in ('DOT', 'LBRACKET', 'QUESTION'):
            if self.current_token.type == 'QUESTION':
                # Error propagation: expr?
                q_tok = self.consume('QUESTION')
                node = TryExpr(operand=node, line=q_tok.line, column=q_tok.column)
            elif self.current_token.type == 'DOT':
                self.consume('DOT')
                field_tok = self.consume('IDENTIFIER')
                # Check if this is a method call: expr.method(args)
                if self.current_token and self.current_token.type == 'LPAREN':
                    self.consume('LPAREN')
                    args = []
                    if self.current_token and self.current_token.type != 'RPAREN':
                        args.append(self.parse_expression())
                        while self.current_token and self.current_token.type == 'COMMA':
                            self.consume('COMMA')
                            args.append(self.parse_expression())
                    self.consume('RPAREN')
                    node = MethodCall(receiver=node, method_name=field_tok.value, arguments=args,
                                      line=field_tok.line, column=field_tok.column)
                else:
                    node = FieldAccess(receiver=node, field=field_tok.value,
                                        line=field_tok.line, column=field_tok.column)
            else:
                lbr = self.consume('LBRACKET')
                idx_expr = self.parse_expression()
                self.consume('RBRACKET')
                node = IndexExpr(receiver=node, index=idx_expr,
                                 line=lbr.line, column=lbr.column)
        return node
    
    def parse_block(self) -> Block:
        """Parse a code block: { statements }"""
        self.consume('LBRACE')
        self.skip_newlines()
        
        block = Block()
        while self.current_token and self.current_token.type != 'RBRACE':
            stmt = self.parse_statement()
            if stmt:
                block.statements.append(stmt)
            self.skip_newlines()
        
        self.consume('RBRACE')
        return block
    
    def parse_if(self) -> IfStmt:
        """Parse if statement"""
        if_token = self.consume('IF')
        self.consume('LPAREN')
        condition = self.parse_expression()
        self.consume('RPAREN')
        then_block = self.parse_block()

        root = IfStmt(condition=condition, then_block=then_block, else_block=None, line=if_token.line, column=if_token.column)
        current = root

        # Handle zero or more elif clauses by chaining nested IfStmt in else_block
        self.skip_newlines()
        while self.current_token and self.current_token.type == 'ELIF':
            elif_token = self.consume('ELIF')
            self.consume('LPAREN')
            elif_cond = self.parse_expression()
            self.consume('RPAREN')
            elif_block = self.parse_block()
            new_if = IfStmt(condition=elif_cond, then_block=elif_block, else_block=None, line=elif_token.line, column=elif_token.column)
            current.else_block = new_if
            current = new_if
            self.skip_newlines()

        # Optional final else
        if self.current_token and self.current_token.type == 'ELSE':
            self.consume('ELSE')
            current.else_block = self.parse_block()

        return root
    
    def parse_while(self) -> WhileStmt:
        """Parse while loop"""
        while_token = self.consume('WHILE')
        self.consume('LPAREN')
        condition = self.parse_expression()
        self.consume('RPAREN')
        body = self.parse_block()
        
        return WhileStmt(condition=condition, body=body,
                        line=while_token.line, column=while_token.column)
    
    def parse_for(self) -> ForStmt:
        """Parse for loop: for var in start..end { body }"""
        for_token = self.consume('FOR')
        var_name = self.consume('IDENTIFIER').value
        self.consume('IN')
        start = self.parse_expression()
        if self.current_token and self.current_token.type == 'RANGE':
            self.consume('RANGE')
        else:
            raise SyntaxError("Expected '..' in for loop range")
        
        end = self.parse_expression()
        body = self.parse_block()
        
        return ForStmt(var_name=var_name, start=start, end=end, body=body,
                      line=for_token.line, column=for_token.column)
    
    def parse_defer(self) -> DeferStmt:
        """Parse defer statement: defer { ... } or defer expr;
        
        Deferred statements are executed when the enclosing function returns.
        """
        defer_token = self.consume('DEFER')
        
        if self.current_token and self.current_token.type == 'LBRACE':
            # defer { block }
            body = self.parse_block()
        else:
            # defer single_statement;
            stmt = self.parse_statement()  # This will handle semicolon
            body = Block(statements=[stmt], line=stmt.line, column=stmt.column)
        
        return DeferStmt(body=body, line=defer_token.line, column=defer_token.column)
    
    def parse_expression(self) -> ASTNode:
        """Parse a full expression with precedence."""
        return self.parse_comparison()
    def parse_comparison(self) -> ASTNode:
        """Parse comparison operators"""
        node = self.parse_term()
        
        while self.current_token and self.current_token.type in ['LT', 'GT', 'LE', 'GE', 'EQ', 'NE']:
            op = self.current_token.value
            self.advance()
            right = self.parse_term()
            node = BinaryExpr(left=node, operator=op, right=right,
                            line=node.line, column=node.column)
        
        return node
    
    def parse_term(self) -> ASTNode:
        """Parse addition/subtraction"""
        node = self.parse_factor()
        
        while self.current_token and self.current_token.type in ['PLUS', 'MINUS']:
            op = self.current_token.value
            self.advance()
            right = self.parse_factor()
            node = BinaryExpr(left=node, operator=op, right=right,
                            line=node.line, column=node.column)
        
        return node
    
    def parse_factor(self) -> ASTNode:
        """Parse multiplication/division"""
        node = self.parse_unary()
        
        while self.current_token and self.current_token.type in ['STAR', 'SLASH']:
            op = self.current_token.value
            self.advance()
            right = self.parse_unary()
            node = BinaryExpr(left=node, operator=op, right=right,
                            line=node.line, column=node.column)
        
        return node
    
    def parse_unary(self) -> ASTNode:
        """Parse unary operators"""
        if self.current_token and self.current_token.type in ['PLUS', 'MINUS', 'NOT']:
            op = self.current_token.value
            self.advance()
            operand = self.parse_unary()
            return UnaryExpr(operator=op, operand=operand,
                           line=operand.line, column=operand.column)
        
        # Address-of operator: &expr
        if self.current_token and self.current_token.type == 'AMPERSAND':
            tok = self.current_token
            self.advance()
            operand = self.parse_unary()
            return AddressOf(operand=operand, line=tok.line, column=tok.column)
        
        # Dereference operator: *expr
        if self.current_token and self.current_token.type == 'STAR':
            tok = self.current_token
            self.advance()
            operand = self.parse_unary()
            return Dereference(operand=operand, line=tok.line, column=tok.column)
        
        return self.parse_primary()
    
    def parse_primary(self) -> ASTNode:
        """Parse primary expressions"""
        if not self.current_token:
            raise SyntaxError("Unexpected end of expression")

        token = self.current_token

        # Parenthesized expression or tuple literal
        if token.type == 'LPAREN':
            self.consume('LPAREN')
            # Check for empty tuple ()
            if self.current_token and self.current_token.type == 'RPAREN':
                self.consume('RPAREN')
                return TupleLiteral(elements=[], line=token.line, column=token.column)
            
            first_expr = self.parse_expression()
            
            # If comma follows, this is a tuple
            if self.current_token and self.current_token.type == 'COMMA':
                elements = [first_expr]
                while self.current_token and self.current_token.type == 'COMMA':
                    self.consume('COMMA')
                    if self.current_token and self.current_token.type == 'RPAREN':
                        break  # Allow trailing comma
                    elements.append(self.parse_expression())
                self.consume('RPAREN')
                return TupleLiteral(elements=elements, line=token.line, column=token.column)
            
            # Otherwise it's a parenthesized expression
            self.consume('RPAREN')
            return first_expr

        # Array literal: [expr1, expr2, ...]
        if token.type == 'LBRACKET':
            return self.parse_array_literal()

        # New expression: new StructName
        if token.type == 'NEW':
            return self.parse_new_expr()

        # Self reference in methods
        if token.type == 'SELF':
            self.advance()
            node = SelfExpr(line=token.line, column=token.column)
            # Handle self.field or self.method()
            while self.current_token and self.current_token.type in ('DOT', 'LBRACKET'):
                if self.current_token.type == 'DOT':
                    self.consume('DOT')
                    field_tok = self.consume('IDENTIFIER')
                    # Check for method call
                    if self.current_token and self.current_token.type == 'LPAREN':
                        self.consume('LPAREN')
                        args = []
                        if self.current_token and self.current_token.type != 'RPAREN':
                            args.append(self.parse_expression())
                            while self.current_token and self.current_token.type == 'COMMA':
                                self.consume('COMMA')
                                args.append(self.parse_expression())
                        self.consume('RPAREN')
                        node = MethodCall(receiver=node, method_name=field_tok.value, arguments=args,
                                          line=field_tok.line, column=field_tok.column)
                    else:
                        node = FieldAccess(receiver=node, field=field_tok.value,
                                           line=field_tok.line, column=field_tok.column)
                else:
                    lbr = self.consume('LBRACKET')
                    idx_expr = self.parse_expression()
                    self.consume('RBRACKET')
                    node = IndexExpr(receiver=node, index=idx_expr,
                                     line=lbr.line, column=lbr.column)
            return node

        # Null literal
        if token.type == 'NULL':
            self.advance()
            return NullLiteral(line=token.line, column=token.column)

        # Boolean literals
        if token.type == 'TRUE':
            self.advance()
            return Literal(value=True, literal_type='bool',
                          line=token.line, column=token.column)

        if token.type == 'FALSE':
            self.advance()
            return Literal(value=False, literal_type='bool',
                          line=token.line, column=token.column)

        # Literals
        if token.type == 'INTEGER':
            self.advance()
            return Literal(value=token.int_value, literal_type='int',
                          line=token.line, column=token.column)

        if token.type == 'DECIMAL':
            self.advance()
            return Literal(value=token.dec_value, literal_type='dec',
                          line=token.line, column=token.column)

        if token.type == 'STRING':
            self.advance()
            return Literal(value=token.value, literal_type='string',
                          line=token.line, column=token.column)

        if token.type == 'INTERP_STRING':
            self.advance()
            # token.value is a list of (is_expr, value) tuples
            return InterpString(parts=token.value, line=token.line, column=token.column)

        if token.type == 'BOOL':
            self.advance()
            return Literal(value=token.value, literal_type='bool',
                          line=token.line, column=token.column)

        if token.type == 'IDENTIFIER':
            return self.parse_postfix_identifier()

        raise SyntaxError(f"Unexpected token {token.type} at line {token.line}")

    def parse_new_expr(self) -> NewExpr:
        """Parse: new StructName or new StructName{field: value, ...}"""
        new_tok = self.consume('NEW')
        name_tok = self.consume('IDENTIFIER')
        
        initializers: List[tuple[str, ASTNode]] = []
        
        # Check for struct literal syntax: new StructName{field: value, ...}
        if self.current_token and self.current_token.type == 'LBRACE':
            self.consume('LBRACE')
            self.skip_newlines()
            
            while self.current_token and self.current_token.type != 'RBRACE':
                field_tok = self.consume('IDENTIFIER')
                self.consume('COLON')
                value = self.parse_expression()
                initializers.append((field_tok.value, value))
                
                if self.current_token and self.current_token.type == 'COMMA':
                    self.consume('COMMA')
                    self.skip_newlines()
                else:
                    break
                self.skip_newlines()
            
            self.consume('RBRACE')
        
        return NewExpr(struct_name=name_tok.value, initializers=initializers,
                       line=new_tok.line, column=new_tok.column)

    def parse_array_literal(self) -> ArrayLiteral:
        """Parse: [expr1, expr2, ...]"""
        lbr = self.consume('LBRACKET')
        elements: List[ASTNode] = []
        
        if self.current_token and self.current_token.type != 'RBRACKET':
            elements.append(self.parse_expression())
            while self.current_token and self.current_token.type == 'COMMA':
                self.consume('COMMA')
                elements.append(self.parse_expression())
        
        self.consume('RBRACKET')
        return ArrayLiteral(elements=elements, line=lbr.line, column=lbr.column)


def parse(tokens: List[Token]) -> Program:
    """
    Convenience function to parse tokens into an AST
    
    Args:
        tokens: List of tokens from the lexer
        
    Returns:
        AST Program node
    """
    parser = Parser(tokens)
    return parser.parse()
