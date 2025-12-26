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
    - FunctionDef: Function definitions
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


@dataclass
class Assignment(ASTNode):
    """Variable assignment: name = value"""
    name: str = ""
    value: ASTNode = None


@dataclass
class FunctionCall(ASTNode):
    """Function call: name(args)"""
    name: str = ""
    arguments: List[ASTNode] = field(default_factory=list)


@dataclass
class FunctionDef(ASTNode):
    """Function definition: name() { ... }"""
    name: str = ""
    body: Optional['Block'] = None


@dataclass
class Block(ASTNode):
    """Code block: { statements }"""
    statements: List[ASTNode] = field(default_factory=list)


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
class Identifier(ASTNode):
    """Variable reference"""
    name: str = ""


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
        elif token_type == 'FUNCTION':
            stmt = self.parse_function_decl()
        elif token_type == 'IDENTIFIER':
            stmt = self.parse_assignment_or_call()
        elif token_type == 'IF':
            stmt = self.parse_if()
        elif token_type == 'WHILE':
            stmt = self.parse_while()
        elif token_type == 'FOR':
            stmt = self.parse_for()
        else:
            raise SyntaxError(
                f"Unexpected token {token_type} at line {self.current_token.line}"
            )
        
        # Require semicolon after statement
        if stmt and not isinstance(stmt, (IfStmt, WhileStmt, ForStmt, FunctionDef)):
            if not self.current_token or self.current_token.type != 'SEMICOLON':
                raise SyntaxError(
                    f"Expected ';' after statement at line {stmt.line}"
                )
            self.consume('SEMICOLON')
        
        return stmt

    def parse_function_decl(self) -> FunctionDef:
        """Parse: Function name() { ... }"""
        fn_token = self.consume('FUNCTION')
        name_tok = self.consume('IDENTIFIER')
        self.consume('LPAREN')
        # no parameters supported yet
        self.consume('RPAREN')
        body = self.parse_block()
        return FunctionDef(name=name_tok.value, body=body, line=fn_token.line, column=fn_token.column)
    
    def parse_var_decl(self) -> VarDecl:
        """Parse: var [type] name [= value]"""
        self.consume('VAR')

        # Optional type annotation
        var_type = None
        if self.current_token and self.current_token.type in ['INT_TYPE', 'DEC_TYPE', 'STRING_TYPE', 'BOOL_TYPE']:
            var_type = self.current_token.value
            self.advance()

        # Get variable name
        name_token = self.consume('IDENTIFIER')
        name = name_token.value

        # Optional initialization
        value = None
        if self.current_token and self.current_token.type == 'ASSIGN':
            self.consume('ASSIGN')
            value = self.parse_expression()

        return VarDecl(name=name, var_type=var_type, value=value, 
                      line=name_token.line, column=name_token.column)
    
    def parse_assignment_or_call(self) -> ASTNode:
        """Parse assignment or function call"""
        name_token = self.consume('IDENTIFIER')
        name = name_token.value
        
        # Check if it's a function call
        if self.current_token and self.current_token.type == 'LPAREN':
            self.consume('LPAREN')
            arguments = []
            
            if self.current_token and self.current_token.type != 'RPAREN':
                arguments.append(self.parse_expression())
                while self.current_token and self.current_token.type == 'COMMA':
                    self.consume('COMMA')
                    arguments.append(self.parse_expression())
            
            self.consume('RPAREN')
            
            # Check if this is actually a function definition
            if self.current_token and self.current_token.type == 'LBRACE':
                body = self.parse_block()
                return FunctionDef(name=name, body=body, 
                                 line=name_token.line, column=name_token.column)
            
            return FunctionCall(name=name, arguments=arguments,
                              line=name_token.line, column=name_token.column)
        
        # Otherwise it's an assignment
        self.consume('ASSIGN')
        value = self.parse_expression()
        return Assignment(name=name, value=value,
                         line=name_token.line, column=name_token.column)
    
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
        # Handle both '..' and separate DOT tokens
        if self.current_token and self.current_token.type == 'DOT':
            self.consume('DOT')
            if self.current_token and self.current_token.type == 'DOT':
                self.consume('DOT')
            else:
                raise SyntaxError("Expected '..' in for loop range")
        elif self.current_token and self.current_token.value == '..':
            self.consume('..')  # This will work if we add '..' as a token type
        else:
            raise SyntaxError("Expected '..' in for loop range")
        
        end = self.parse_expression()
        body = self.parse_block()
        
        return ForStmt(var_name=var_name, start=start, end=end, body=body,
                      line=for_token.line, column=for_token.column)
    
    def parse_expression(self) -> ASTNode:
        """Parse expression with operator precedence"""
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
        
        return self.parse_primary()
    
    def parse_primary(self) -> ASTNode:
        """Parse primary expressions"""
        if not self.current_token:
            raise SyntaxError("Unexpected end of expression")
        
        token = self.current_token
        
        # Parenthesized expression
        if token.type == 'LPAREN':
            self.consume('LPAREN')
            expr = self.parse_expression()
            self.consume('RPAREN')
            return expr
        
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
        
        if token.type == 'TRUE':
            self.advance()
            return Literal(value=True, literal_type='bool',
                          line=token.line, column=token.column)
        
        if token.type == 'FALSE':
            self.advance()
            return Literal(value=False, literal_type='bool',
                          line=token.line, column=token.column)
        
        # Identifier (variable reference or function call)
        if token.type == 'IDENTIFIER':
            name = token.value
            line = token.line
            column = token.column
            self.advance()
            
            # Check if this is a function call
            if self.current_token and self.current_token.type == 'LPAREN':
                self.consume('LPAREN')
                arguments = []
                
                if self.current_token and self.current_token.type != 'RPAREN':
                    arguments.append(self.parse_expression())
                    while self.current_token and self.current_token.type == 'COMMA':
                        self.consume('COMMA')
                        arguments.append(self.parse_expression())
                
                self.consume('RPAREN')
                return FunctionCall(name=name, arguments=arguments, line=line, column=column)
            
            # Otherwise it's a variable reference
            return Identifier(name=name, line=line, column=column)

        raise SyntaxError(f"Unexpected token {token.type} at line {token.line}")


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
