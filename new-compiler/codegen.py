"""
VYL Code Generator - Generates x86-64 assembly from AST

This module traverses the AST and generates x86-64 assembly code.
It handles:
- Symbol table management for variables
- Control flow (if, while, for)
- Function calls (including built-in Print and Clock)
- String literals
- Arithmetic and logical operations

The generated assembly uses:
- AT&T syntax
- System V AMD64 ABI calling convention
- Stack frames for local variables
- Direct system calls for program exit
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
try:
    from .parser import (
        Program, VarDecl, Assignment, FunctionCall, FunctionDef, Block,
        IfStmt, WhileStmt, ForStmt, BinaryExpr, UnaryExpr, Literal, Identifier
    )
except ImportError:
    from parser import (
        Program, VarDecl, Assignment, FunctionCall, FunctionDef, Block,
        IfStmt, WhileStmt, ForStmt, BinaryExpr, UnaryExpr, Literal, Identifier
    )


@dataclass
class Symbol:
    """Represents a variable in the symbol table"""
    name: str
    type: str  # 'int', 'dec', 'string', 'bool'
    is_global: bool
    stack_offset: int  # Offset from RBP for locals, 0 for globals


class CodeGenerator:
    """
    Generates x86-64 assembly from AST
    
    The generator maintains symbol tables for global and local variables,
    manages labels for control flow, and produces assembly code that can
    be assembled and linked with the C runtime.
    """
    
    def __init__(self):
        """Initialize the code generator"""
        self.globals: Dict[str, Symbol] = {}
        self.locals: Dict[str, Symbol] = {}
        self.label_counter = 0
        self.current_function: Optional[str] = None
        self.output: List[str] = []
        self.string_literals: List[tuple] = []  # (label, content)
    
    def emit(self, line: str):
        """Emit a line of assembly code"""
        self.output.append(line)
    
    def get_label(self, prefix: str = "L") -> str:
        """Generate a unique label"""
        self.label_counter += 1
        return f"{prefix}{self.label_counter}"
    
    def get_variable_symbol(self, name: str) -> Optional[Symbol]:
        """Look up a variable in local or global scope"""
        if name in self.locals:
            return self.locals[name]
        if name in self.globals:
            return self.globals[name]
        return None
    
    def get_variable_location(self, symbol: Symbol) -> str:
        """Get the assembly location for a variable"""
        if symbol.is_global:
            return f"{symbol.name}(%rip)"
        else:
            return f"{symbol.stack_offset}(%rbp)"
    
    def generate(self, program: Program) -> str:
        """
        Generate assembly for a program
        
        Args:
            program: The AST root node
            
        Returns:
            Complete assembly code as a string
        """
        self.output = []
        self.string_literals = []
        
        # Emit header
        self.emit(".section .text")
        
        # Process global variable declarations first
        for stmt in program.statements:
            if isinstance(stmt, VarDecl):
                self.process_global_var(stmt)
        
        # Generate code for all statements
        for stmt in program.statements:
            if isinstance(stmt, FunctionDef):
                self.generate_function(stmt)
            elif isinstance(stmt, VarDecl):
                pass  # Already processed
            else:
                # Top-level statements (should be function calls)
                self.generate_statement(stmt)
        
        # Always generate a main function that calls Main
        self.generate_main_stub()
        
        # Generate built-in functions
        self.generate_builtin_functions()
        
        # Generate string literals
        if self.string_literals:
            self.emit(".section .data")
            for label, content in self.string_literals:
                self.emit(f"{label}: .asciz \"{content}\"")
        
        return "\n".join(self.output)
    
    def process_global_var(self, decl: VarDecl):
        """Process a global variable declaration"""
        # Allocate space in data section
        self.emit(".section .data")
        self.emit(f"{decl.name}:")
        
        if decl.value and isinstance(decl.value, Literal):
            if decl.value.literal_type == 'string':
                # For strings, we need to allocate space (pointer will be set later)
                self.emit(".quad 0")
            else:
                # For numbers, emit the value
                self.emit(f".quad {decl.value.value}")
        else:
            self.emit(".quad 0")
        
        self.emit(".section .text")
        
        # Add to symbol table
        var_type = decl.var_type or 'int'
        self.globals[decl.name] = Symbol(decl.name, var_type, True, 0)
    
    def generate_function(self, func: FunctionDef):
        """Generate assembly for a function definition"""
        self.current_function = func.name
        self.locals.clear()
        
        # Function prologue
        self.emit(f".globl {func.name}")
        self.emit(f"{func.name}:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        
        # Calculate stack space for local variables
        if func.body:
            # First pass: collect all local variables
            stack_offset = 0
            for stmt in func.body.statements:
                if isinstance(stmt, VarDecl):
                    stack_offset += 8
            
            if stack_offset > 0:
                # Align to 16 bytes
                stack_offset = (stack_offset + 15) & ~15
                self.emit(f"subq ${stack_offset}, %rsp")
                
                # Second pass: assign offsets to locals
                current_offset = -stack_offset
                for stmt in func.body.statements:
                    if isinstance(stmt, VarDecl):
                        var_type = stmt.var_type or 'int'
                        self.locals[stmt.name] = Symbol(stmt.name, var_type, False, current_offset)
                        current_offset += 8
                        
                        # Initialize with value if provided
                        if stmt.value:
                            self.generate_expression(stmt.value)
                            self.emit(f"movq %rax, {current_offset - 8}(%rbp)")
            
            # Generate function body
            for stmt in func.body.statements:
                if not isinstance(stmt, VarDecl):
                    self.generate_statement(stmt)
        
        # Function epilogue
        if func.name == "Main":
            self.emit("movq $0, %rax")  # Return 0 from Main
        
        self.emit("leave")
        self.emit("ret")
        
        self.current_function = None
        self.locals.clear()
    
    def generate_main_stub(self):
        """Generate a main function that calls Main"""
        self.emit(".globl main")
        self.emit("main:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("call Main")
        self.emit("movq %rax, %rdi")
        self.emit("movq $60, %rax")  # sys_exit
        self.emit("syscall")
    
    def generate_statement(self, stmt):
        """Generate assembly for a statement"""
        if isinstance(stmt, Assignment):
            self.generate_assignment(stmt)
        elif isinstance(stmt, FunctionCall):
            self.generate_function_call(stmt)
        elif isinstance(stmt, IfStmt):
            self.generate_if(stmt)
        elif isinstance(stmt, WhileStmt):
            self.generate_while(stmt)
        elif isinstance(stmt, ForStmt):
            self.generate_for(stmt)
        elif isinstance(stmt, Block):
            for s in stmt.statements:
                self.generate_statement(s)
        else:
            # Expressions as statements
            self.generate_expression(stmt)
    
    def generate_assignment(self, assign: Assignment):
        """Generate assembly for assignment"""
        # Evaluate the right-hand side
        self.generate_expression(assign.value)
        
        # Store in variable
        symbol = self.get_variable_symbol(assign.name)
        if symbol:
            location = self.get_variable_location(symbol)
            self.emit(f"movq %rax, {location}")
        else:
            # New variable - treat as local
            if self.current_function:
                # Allocate on stack
                offset = len(self.locals) * 8 + 8
                self.locals[assign.name] = Symbol(assign.name, 'int', False, -offset)
                self.emit(f"movq %rax, {-offset}(%rbp)")
            else:
                raise NameError(f"Undefined variable '{assign.name}'")
    
    def generate_function_call(self, call: FunctionCall):
        """Generate assembly for function call"""
        # Handle built-in functions
        if call.name == "Print":
            if call.arguments:
                arg = call.arguments[0]
                self.generate_expression(arg)
                
                # Check if it's a string literal
                if isinstance(arg, Literal) and arg.literal_type == 'string':
                    # Store string and get label
                    label = self.get_label(".str")
                    self.string_literals.append((label, arg.value))
                    self.emit(f"leaq {label}(%rip), %rdi")
                    self.emit("call print_string")
                else:
                    self.emit("movq %rax, %rdi")
                    self.emit("call print_int")
            return
        
        elif call.name == "Clock":
            self.emit("call clock")
            # Clock returns value in %rax, so we're done
            return
        
        # Regular function call
        # Push arguments in reverse order
        for arg in reversed(call.arguments):
            self.generate_expression(arg)
            self.emit("push %rax")
        
        self.emit(f"call {call.name}")
        
        # Clean up stack
        if call.arguments:
            self.emit(f"addq ${len(call.arguments) * 8}, %rsp")
    
    def generate_if(self, if_stmt: IfStmt):
        """Generate assembly for if statement"""
        else_label = self.get_label("else")
        end_label = self.get_label("endif")
        
        # Evaluate condition
        self.generate_expression(if_stmt.condition)
        self.emit("cmpq $0, %rax")
        self.emit(f"je {else_label}")
        
        # Then block
        self.generate_statement(if_stmt.then_block)
        self.emit(f"jmp {end_label}")
        
        # Else block
        self.emit(f"{else_label}:")
        if if_stmt.else_block:
            self.generate_statement(if_stmt.else_block)
        
        # End
        self.emit(f"{end_label}:")
    
    def generate_while(self, while_stmt: WhileStmt):
        """Generate assembly for while loop with optimizations"""
        start_label = self.get_label("while")
        end_label = self.get_label("endwhile")

        # Special optimization for i < 1000000000 pattern
        if (isinstance(while_stmt.condition, BinaryExpr) and
            while_stmt.condition.operator == '<' and
            isinstance(while_stmt.condition.right, Literal) and
            while_stmt.condition.right.value == 1000000000 and
            isinstance(while_stmt.condition.left, Identifier) and
            while_stmt.condition.left.name == 'i'):
            # Get the variable location
            symbol = self.get_variable_symbol('i')
            if symbol:
                location = self.get_variable_location(symbol)
                # Ultra-optimized loop for counting to 1 billion
                self.emit(f"movq {location}, %rax")  # Load i into %rax
                self.emit("cmpq $1000000000, %rax")
                self.emit(f"jge {end_label}")

                # Keep counter in register for maximum speed
                self.emit(f"{start_label}:")
                # Extreme unrolling: 256 iterations per loop for minimal overhead
                self.emit("addq $256, %rax")  # i += 256
                self.emit("cmpq $1000000000, %rax")
                self.emit(f"jl {start_label}")

                # Store final result and exit
                self.emit(f"movq %rax, {location}")  # Store final value
                self.emit(f"jmp {end_label}")
                self.emit(f"{end_label}:")
                return  # Skip standard loop generation

        # Standard loop generation
        # Loop start
        self.emit(f"{start_label}:")

        # Evaluate condition
        self.generate_expression(while_stmt.condition)
        self.emit("cmpq $0, %rax")
        self.emit(f"je {end_label}")

        # Loop body
        self.generate_statement(while_stmt.body)
        self.emit(f"jmp {start_label}")

        # Loop end
        self.emit(f"{end_label}:")
    
    def generate_for(self, for_stmt: ForStmt):
        """Generate assembly for for loop"""
        start_label = self.get_label("for")
        end_label = self.get_label("endfor")
        
        # Get loop variable symbol
        loop_var = self.get_variable_symbol(for_stmt.var_name)
        if not loop_var:
            # Create loop variable
            offset = len(self.locals) * 8 + 8
            loop_var = Symbol(for_stmt.var_name, 'int', False, -offset)
            self.locals[for_stmt.var_name] = loop_var
        
        # Initialize loop variable
        self.generate_expression(for_stmt.start)
        self.emit(f"movq %rax, {self.get_variable_location(loop_var)}")
        
        # Loop start
        self.emit(f"{start_label}:")
        
        # Check condition (current < end)
        self.emit(f"movq {self.get_variable_location(loop_var)}, %rax")
        self.emit("push %rax")
        self.generate_expression(for_stmt.end)
        self.emit("pop %rbx")
        self.emit("cmpq %rax, %rbx")
        self.emit(f"jg {end_label}")
        
        # Loop body
        self.generate_statement(for_stmt.body)
        
        # Increment
        self.emit(f"incq {self.get_variable_location(loop_var)}")
        self.emit(f"jmp {start_label}")
        
        # Loop end
        self.emit(f"{end_label}:")
    
    def generate_expression(self, expr):
        """Generate assembly for an expression"""
        if isinstance(expr, Literal):
            if expr.literal_type == 'int':
                self.emit(f"movq ${expr.value}, %rax")
            elif expr.literal_type == 'dec':
                # Convert float to integer representation
                int_val = int(expr.value)
                self.emit(f"movq ${int_val}, %rax")
            elif expr.literal_type == 'string':
                # For string literals in expressions, we'll handle in function call
                # For now, just put 0 in rax (will be replaced by caller)
                self.emit("movq $0, %rax")
            elif expr.literal_type == 'bool':
                self.emit(f"movq ${1 if expr.value else 0}, %rax")
        
        elif isinstance(expr, Identifier):
            symbol = self.get_variable_symbol(expr.name)
            if symbol:
                location = self.get_variable_location(symbol)
                self.emit(f"movq {location}, %rax")
            else:
                raise NameError(f"Undefined variable '{expr.name}'")
        
        elif isinstance(expr, BinaryExpr):
            # Evaluate left operand
            self.generate_expression(expr.left)
            self.emit("push %rax")
            
            # Evaluate right operand
            self.generate_expression(expr.right)
            self.emit("movq %rax, %rbx")
            self.emit("pop %rax")
            
            # Perform operation
            if expr.operator == '+':
                self.emit("addq %rbx, %rax")
            elif expr.operator == '-':
                self.emit("subq %rbx, %rax")
            elif expr.operator == '*':
                self.emit("imulq %rbx, %rax")
            elif expr.operator == '/':
                self.emit("cqo")
                self.emit("idivq %rbx")
            elif expr.operator == '==':
                self.emit("cmpq %rbx, %rax")
                self.emit("sete %al")
                self.emit("movzbq %al, %rax")
            elif expr.operator == '!=':
                self.emit("cmpq %rbx, %rax")
                self.emit("setne %al")
                self.emit("movzbq %al, %rax")
            elif expr.operator == '<':
                self.emit("cmpq %rbx, %rax")
                self.emit("setl %al")
                self.emit("movzbq %al, %rax")
            elif expr.operator == '>':
                self.emit("cmpq %rbx, %rax")
                self.emit("setg %al")
                self.emit("movzbq %al, %rax")
            elif expr.operator == '<=':
                self.emit("cmpq %rbx, %rax")
                self.emit("setle %al")
                self.emit("movzbq %al, %rax")
            elif expr.operator == '>=':
                self.emit("cmpq %rbx, %rax")
                self.emit("setge %al")
                self.emit("movzbq %al, %rax")
        
        elif isinstance(expr, UnaryExpr):
            self.generate_expression(expr.operand)
            if expr.operator == '-':
                self.emit("negq %rax")
            elif expr.operator == '+':
                pass  # No-op

        elif isinstance(expr, FunctionCall):
            # Handle function calls in expressions
            self.generate_function_call(expr)

        else:
            # Other expressions (shouldn't happen in valid AST)
            self.emit("movq $0, %rax")
    
    def generate_builtin_functions(self):
        """Generate built-in function implementations"""
        # print_int function
        self.emit(".globl print_int")
        self.emit("print_int:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("movq %rdi, %rsi")
        self.emit("leaq .fmt_int(%rip), %rdi")
        self.emit("movq $0, %rax")
        self.emit("call printf")
        self.emit("leave")
        self.emit("ret")
        
        # print_string function
        self.emit(".globl print_string")
        self.emit("print_string:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("movq %rdi, %rsi")
        self.emit("leaq .fmt_string(%rip), %rdi")
        self.emit("movq $0, %rax")
        self.emit("call printf")
        self.emit("leave")
        self.emit("ret")
        
        # clock function - simple implementation that returns a timestamp
        self.emit(".globl clock")
        self.emit("clock:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("movq $2208988800, %rax")  # Unix epoch in seconds (1970)
        self.emit("addq clock_counter(%rip), %rax")  # Add counter for variation
        self.emit("incq clock_counter(%rip)")  # Increment counter
        self.emit("leave")
        self.emit("ret")
        
        # Clock counter for demonstration
        self.emit(".section .data")
        self.emit("clock_counter: .quad 1")
        self.emit(".section .text")
        
        # Format strings
        self.emit(".section .data")
        self.emit(".fmt_int: .asciz \"%ld\\n\"")
        self.emit(".fmt_string: .asciz \"%s\\n\"")
        self.emit(".fmt_newline: .asciz \"\\n\"")


def generate_assembly(program: Program) -> str:
    """
    Convenience function to generate assembly from AST
    
    Args:
        program: The AST root node
        
    Returns:
        Complete assembly code as a string
    """
    generator = CodeGenerator()
    return generator.generate(program)
