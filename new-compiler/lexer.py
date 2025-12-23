"""
VYL Lexer - Tokenizes VYL source code into a stream of tokens

This module handles lexical analysis of VYL source code, converting the raw
text into tokens that the parser can work with.

Token Types:
    Keywords: var, if, else, while, for, in, struct, new, import
    Types: int, dec, string, bool
    Literals: INTEGER, DECIMAL, STRING, TRUE, FALSE
    Identifiers: variable/function names
    Operators: +, -, *, /, =, ==, !=, <, >, <=, >=
    Punctuation: (, ), {, }, [, ], ;, ,, ., :
    Special: NEWLINE, COMMENT, EOF
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Token:
    """Represents a single token in the source code"""
    type: str  # Token type (e.g., 'INTEGER', 'PLUS', 'IDENTIFIER')
    value: Optional[str] = None  # The actual text of the token
    int_value: Optional[int] = None  # For integer literals
    dec_value: Optional[float] = None  # For decimal literals
    line: int = 0  # Line number where token appears
    column: int = 0  # Column number where token starts
    
    def __repr__(self):
        if self.value:
            return f"Token({self.type}, '{self.value}', line={self.line})"
        return f"Token({self.type}, line={self.line})"


# Keyword mapping
KEYWORDS = {
    'var': 'VAR',
    'if': 'IF',
    'else': 'ELSE',
    'while': 'WHILE',
    'for': 'FOR',
    'in': 'IN',
    'struct': 'STRUCT',
    'new': 'NEW',
    'import': 'IMPORT',
    'int': 'INT_TYPE',
    'dec': 'DEC_TYPE',
    'string': 'STRING_TYPE',
    'bool': 'BOOL_TYPE',
    'true': 'TRUE',
    'false': 'FALSE',
}


class Lexer:
    """
    Lexical analyzer for VYL source code
    
    The lexer converts raw source text into a stream of tokens.
    It handles:
    - Whitespace skipping
    - Comment removal
    - String literal parsing with escape sequences
    - Number parsing (integers and decimals)
    - Identifier and keyword recognition
    - Operator and punctuation tokenization
    """
    
    def __init__(self, source: str):
        """
        Initialize the lexer with source code
        
        Args:
            source: The VYL source code as a string
        """
        self.source = source
        self.position = 0
        self.line = 1
        self.column = 1
        self.length = len(source)
    
    def peek(self, offset: int = 0) -> str:
        """
        Look ahead at a character without consuming it
        
        Args:
            offset: Number of characters to look ahead (0 = current char)
            
        Returns:
            The character at the specified position, or '' if out of bounds
        """
        pos = self.position + offset
        return self.source[pos] if pos < self.length else ''
    
    def advance(self, count: int = 1):
        """
        Move forward in the source code
        
        Args:
            count: Number of characters to advance
        """
        for _ in range(count):
            if self.position >= self.length:
                break
            char = self.source[self.position]
            if char == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.position += 1
    
    def skip_whitespace(self):
        """Skip spaces, tabs, and carriage returns"""
        while self.position < self.length:
            char = self.peek()
            if char in ' \t\r':
                self.advance()
            else:
                break
    
    def skip_comment(self):
        """Skip single-line comments (// to end of line)"""
        if self.peek() == '/' and self.peek(1) == '/':
            self.advance(2)
            while self.position < self.length and self.peek() != '\n':
                self.advance()
    
    def scan_string(self) -> str:
        """
        Scan a string literal with escape sequence support
        
        Returns:
            The decoded string content
        """
        self.advance()  # Skip opening quote
        result = []
        
        while self.position < self.length:
            char = self.peek()
            
            if char == '"':
                self.advance()  # Skip closing quote
                break
            
            if char == '\\':
                # Handle escape sequences
                self.advance()
                escape_char = self.peek()
                if escape_char == 'n':
                    result.append('\n')
                elif escape_char == 't':
                    result.append('\t')
                elif escape_char == 'r':
                    result.append('\r')
                elif escape_char == '"':
                    result.append('"')
                else:
                    result.append(escape_char)
                self.advance()
            else:
                result.append(char)
                self.advance()
        
        return ''.join(result)
    
    def scan_number(self) -> tuple:
        """
        Scan a number (integer or decimal)
        
        Returns:
            Tuple of (is_decimal, value) where value is the numeric value
        """
        start_pos = self.position
        has_dot = False
        
        while self.position < self.length:
            char = self.peek()
            if char == '.':
                # Check if next character is also a dot (range operator)
                if self.position + 1 < self.length and self.peek(1) == '.':
                    # This is a range operator '..', not part of a number
                    break
                if has_dot:
                    break
                has_dot = True
                self.advance()
            elif not char.isdigit():
                break
            else:
                self.advance()
        
        num_str = self.source[start_pos:self.position]
        
        if has_dot:
            return True, float(num_str)
        else:
            return False, int(num_str)
    
    def scan_identifier(self) -> str:
        """
        Scan an identifier (variable/function names)
        
        Returns:
            The identifier string
        """
        start_pos = self.position
        
        while self.position < self.length:
            char = self.peek()
            if not (char.isalnum() or char == '_'):
                break
            self.advance()
        
        return self.source[start_pos:self.position]
    
    def next_token(self) -> Token:
        """
        Get the next token from the source
        
        Returns:
            The next Token object
        """
        # Skip whitespace and comments
        self.skip_whitespace()
        self.skip_comment()
        self.skip_whitespace()
        
        # Check for end of file
        if self.position >= self.length:
            return Token('EOF', line=self.line, column=self.column)
        
        # Get current character
        char = self.peek()
        line = self.line
        column = self.column
        
        # Handle newlines
        if char == '\n':
            self.advance()
            return Token('NEWLINE', line=line, column=column)
        
        # Handle string literals
        if char == '"':
            string_value = self.scan_string()
            return Token('STRING', string_value, line=line, column=column)
        
        # Handle numbers
        if char.isdigit():
            is_decimal, value = self.scan_number()
            if is_decimal:
                return Token('DECIMAL', str(value), dec_value=value, line=line, column=column)
            else:
                return Token('INTEGER', str(value), int_value=value, line=line, column=column)
        
        # Handle identifiers and keywords
        if char.isalpha() or char == '_':
            ident = self.scan_identifier()
            token_type = KEYWORDS.get(ident, 'IDENTIFIER')
            return Token(token_type, ident, line=line, column=column)
        
        # Handle two-character operators
        two_char = char + self.peek(1)
        if two_char in ['==', '!=', '<=', '>=', '..']:
            self.advance(2)
            return Token(two_char, two_char, line=line, column=column)
        
        # Handle single-character tokens
        self.advance()
        
        if char == '+': return Token('PLUS', '+', line=line, column=column)
        if char == '-': return Token('MINUS', '-', line=line, column=column)
        if char == '*': return Token('STAR', '*', line=line, column=column)
        if char == '/': return Token('SLASH', '/', line=line, column=column)
        if char == '=': return Token('ASSIGN', '=', line=line, column=column)
        if char == '<': return Token('LT', '<', line=line, column=column)
        if char == '>': return Token('GT', '>', line=line, column=column)
        if char == '(': return Token('LPAREN', '(', line=line, column=column)
        if char == ')': return Token('RPAREN', ')', line=line, column=column)
        if char == '{': return Token('LBRACE', '{', line=line, column=column)
        if char == '}': return Token('RBRACE', '}', line=line, column=column)
        if char == '[': return Token('LBRACKET', '[', line=line, column=column)
        if char == ']': return Token('RBRACKET', ']', line=line, column=column)
        if char == ';': return Token('SEMICOLON', ';', line=line, column=column)
        if char == ',': return Token('COMMA', ',', line=line, column=column)
        if char == '.': return Token('DOT', '.', line=line, column=column)
        if char == ':': return Token('COLON', ':', line=line, column=column)
        
        # Unknown character
        raise SyntaxError(f"Unexpected character '{char}' at line {line}, column {column}")
    
    def tokenize(self) -> List[Token]:
        """
        Tokenize the entire source code
        
        Returns:
            List of all tokens in the source
        """
        tokens = []
        while True:
            token = self.next_token()
            tokens.append(token)
            if token.type == 'EOF':
                break
        return tokens


def tokenize(source: str) -> List[Token]:
    """
    Convenience function to tokenize source code
    
    Args:
        source: VYL source code
        
    Returns:
        List of tokens
    """
    lexer = Lexer(source)
    return lexer.tokenize()
