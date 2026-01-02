"""
VYL Code Generator - Generates x86-64 assembly from AST
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

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
        ReturnStmt,
        DeferStmt,
        StructDef,
        FieldAccess,
        IndexExpr,
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
except ImportError:  # pragma: no cover - fallback for direct execution
    from parser import (
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
        ReturnStmt,
        DeferStmt,
        StructDef,
        FieldAccess,
        IndexExpr,
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


class CodegenError(Exception):
    """Raised when code generation fails."""


@dataclass
class Symbol:
    name: str
    typ: str
    is_global: bool
    offset: int  # stack offset for locals, unused for globals
    is_param: bool = False
    reg: Optional[str] = None
    size: int = 8


class CodeGenerator:
    def __init__(self):
        self.output: List[str] = []
        self.label_counter = 0
        self.current_function: Optional[str] = None
        self.current_struct: Optional[StructDef] = None
        self.current_function_end_label: Optional[str] = None  # For early returns (e.g., ? operator)
        self.locals: Dict[str, Symbol] = {}
        self.params: Dict[str, Symbol] = {}
        self.globals: Dict[str, Symbol] = {}
        self.function_defs: Dict[str, FunctionDef] = {}  # Store function definitions for default params
        self.string_literals: List[Tuple[str, str]] = []
        self.struct_layouts: Dict[str, dict] = {}
        self.enum_values: Dict[str, Dict[str, int]] = {}
        self.defer_stack: List[DeferStmt] = []  # Stack of deferred statements

    # ---------- helpers ----------
    def emit(self, line: str):
        self.output.append(line)

    def get_label(self, prefix: str = ".L") -> str:
        lbl = f"{prefix}{self.label_counter}"
        self.label_counter += 1
        return lbl

    def escape_string(self, content: str) -> str:
        return (
            content.replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace("\r", "\\r")
        )

    def get_variable_symbol(self, name: str) -> Optional[Symbol]:
        if name in self.locals:
            return self.locals[name]
        if name in self.params:
            return self.params[name]
        return self.globals.get(name)

    def get_variable_location(self, symbol: Symbol) -> str:
        if symbol.reg:
            return symbol.reg
        if symbol.is_global:
            return f"{symbol.name}(%rip)"
        return f"{symbol.offset}(%rbp)"

    def _infer_type_from_expr(self, expr) -> str:
        """Infer the type of an expression for variable declarations."""
        if isinstance(expr, Literal):
            return expr.literal_type  # 'int', 'string', 'bool', 'dec'
        if isinstance(expr, FunctionCall):
            if expr.name in ("GetArg", "Read", "SHA256", "Input", "GetEnv", "StrConcat", "Substring"):
                return "string"
            return "int"  # Default for function calls
        if isinstance(expr, BinaryExpr):
            if expr.operator == "+":
                left_t = self._infer_type_from_expr(expr.left)
                right_t = self._infer_type_from_expr(expr.right)
                if left_t == "string" or right_t == "string":
                    return "string"
                if left_t == "dec" or right_t == "dec":
                    return "dec"
                return "int"
            if expr.operator in ("==", "!=", "<", ">", "<=", ">=", "&&", "||"):
                return "bool"
            return "int"
        return "int"  # Default fallback

    def _expr_is_stringish(self, node) -> bool:
        """Check if an expression evaluates to a string type."""
        if isinstance(node, Literal) and node.literal_type == "string":
            return True
        if isinstance(node, FunctionCall) and node.name in ("GetArg", "Read", "SHA256", "Input", "GetEnv", "StrConcat", "Substring"):
            return True
        if isinstance(node, Identifier):
            sym = self.get_variable_symbol(node.name)
            if sym and sym.typ == "string":
                return True
        if isinstance(node, BinaryExpr) and node.operator == "+":
            # If either side is stringish, the result is stringish
            return self._expr_is_stringish(node.left) or self._expr_is_stringish(node.right)
        return False

    # ---------- entry ----------
    def generate(self, program: Program) -> str:
        self.output = []
        self.string_literals = []
        self.locals = {}
        self.params = {}
        self.globals = {}
        self.function_defs = {}
        self.label_counter = 0

        self.struct_layouts = self.build_struct_layouts(program)
        self.enum_values = self.build_enum_values(program)
        self.method_table: Dict[str, Dict[str, MethodDef]] = self.build_method_table(program)

        # Build function lookup table for default parameters
        for stmt in program.statements:
            if isinstance(stmt, FunctionDef):
                self.function_defs[stmt.name] = stmt

        self.emit(".section .text")

        for stmt in program.statements:
            if isinstance(stmt, VarDecl):
                self.process_global_var(stmt)
            elif isinstance(stmt, StructDef):
                continue
            elif isinstance(stmt, EnumDef):
                continue
            elif isinstance(stmt, InterfaceDef):
                continue

        for stmt in program.statements:
            if isinstance(stmt, FunctionDef):
                self.generate_function(stmt)
            elif isinstance(stmt, VarDecl):
                continue
            elif isinstance(stmt, StructDef):
                # Generate methods for the struct
                for method in stmt.methods:
                    self.generate_method(method, stmt)
            elif isinstance(stmt, EnumDef):
                continue
            elif isinstance(stmt, InterfaceDef):
                continue
            else:
                self.generate_statement(stmt)

        self.generate_main_stub()
        self.generate_builtin_functions()

        if self.string_literals:
            self.emit(".section .data")
            for label, content in self.string_literals:
                escaped = self.escape_string(content)
                self.emit(f"{label}: .asciz \"{escaped}\"")

        # Add format string for int-to-string conversion
        self.emit(".section .data")
        self.emit(".int_fmt: .asciz \"%ld\"")

        return "\n".join(self.output)

    # ---------- globals ----------
    def process_global_var(self, decl: VarDecl):
        var_type = decl.var_type or "int"
        self.emit(".section .data")
        if var_type in self.struct_layouts:
            data_label = f"{decl.name}_data"
            size = self.struct_layouts[var_type]["size"]
            self.emit(f"{data_label}:")
            self.emit(f".zero {size}")
            self.emit(f"{decl.name}:")
            self.emit(f".quad {data_label}")
        else:
            self.emit(f"{decl.name}:")
            if decl.value and isinstance(decl.value, Literal) and decl.value.literal_type != "string":
                self.emit(f".quad {decl.value.value}")
            else:
                self.emit(".quad 0")
        self.emit(".section .text")
        self.globals[decl.name] = Symbol(decl.name, var_type, True, 0, size=8)

    # ---------- functions ----------
    def generate_function(self, func: FunctionDef):
        self.current_function = func.name
        self.locals = {}
        self.params = {}
        self.defer_stack = []  # Clear defer stack for new function

        # Collect locals
        decls = self.collect_var_decls(func.body) if func.body else []

        arg_regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        param_reg_pool = ["%r14", "%r15"]  # callee-saved to survive calls
        reg_param_count = min(len(func.params), len(param_reg_pool))
        saved_regs = param_reg_pool[:reg_param_count]

        # Stack slots for non-register params + locals
        total_slots = (len(func.params) - reg_param_count)
        locals_size = sum(self.var_size(d.var_type or "int") for d in decls)
        stack_bytes = total_slots * 8 + locals_size
        
        # Account for stack alignment: after push rbp + saved_regs pushes
        # push rbp: rsp aligned (16)
        # each saved_reg push: toggles alignment
        # We need total frame to maintain 16-byte alignment before calls
        # saved_regs_bytes + stack_bytes must be multiple of 16
        saved_regs_bytes = len(saved_regs) * 8
        total_frame = saved_regs_bytes + stack_bytes
        if total_frame % 16 != 0:
            stack_bytes += 8  # add padding to align
        
        offset = -stack_bytes if stack_bytes else 0

        self.emit(f".globl {func.name}")
        self.emit(f"{func.name}:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")

        for reg in saved_regs:
            self.emit(f"push {reg}")

        if stack_bytes:
            self.emit(f"subq ${stack_bytes}, %rsp")

        # Assign parameters (register-backed first, then stack-backed)
        offset_cursor = offset
        for idx, (pname, ptype, pdefault) in enumerate(func.params):
            if idx < reg_param_count:
                sym = Symbol(pname, ptype or "int", False, 0, is_param=True, reg=param_reg_pool[idx])
                self.locals[pname] = sym
                self.params[pname] = sym
            else:
                sym = Symbol(pname, ptype or "int", False, offset_cursor, is_param=True)
                self.locals[pname] = sym
                self.params[pname] = sym
                offset_cursor += 8

        # Move incoming parameter values to their homes
        for idx, (pname, _, pdefault) in enumerate(func.params):
            sym = self.params[pname]
            if sym.reg:
                if idx < len(arg_regs):
                    self.emit(f"movq {arg_regs[idx]}, {sym.reg}")
                else:
                    src_offset = 16 + (idx - len(arg_regs)) * 8
                    self.emit(f"movq {src_offset}(%rbp), {sym.reg}")
            else:
                if idx < len(arg_regs):
                    self.emit(f"movq {arg_regs[idx]}, {self.get_variable_location(sym)}")
                else:
                    src_offset = 16 + (idx - len(arg_regs)) * 8
                    self.emit(f"movq {src_offset}(%rbp), %rax")
                    self.emit(f"movq %rax, {self.get_variable_location(sym)}")

        # Assign locals after params
        for d in decls:
            # Infer type from initializer if not explicitly specified
            if d.var_type:
                var_type = d.var_type
            elif d.value:
                var_type = self._infer_type_from_expr(d.value)
            else:
                var_type = "int"
            size = self.var_size(var_type)
            sym = Symbol(d.name, var_type, False, offset_cursor, size=size)
            self.locals[d.name] = sym
            offset_cursor += size

        end_lbl = self.get_label("ret")
        self.current_function_end_label = end_lbl

        # Initialize struct locals so field access has storage
        for d in decls:
            var_type = d.var_type or "int"
            if var_type in self.struct_layouts:
                size = self.struct_layouts[var_type]["size"]
                loc = self.get_variable_location(self.locals[d.name])
                self.emit(f"movq ${size}, %rdi")
                self.emit("call vyl_alloc")
                self.emit(f"movq %rax, {loc}")

        if func.body:
            for stmt in func.body.statements:
                self.generate_statement(stmt, end_label=end_lbl)

        if func.name == "Main":
            self.emit("movq $0, %rax")
        # Execute any remaining deferred statements for implicit return
        self._emit_deferred_statements()
        self.emit(f"{end_lbl}:")
        if stack_bytes:
            self.emit(f"addq ${stack_bytes}, %rsp")
        for reg in reversed(saved_regs):
            self.emit(f"pop {reg}")
        self.emit("leave")
        self.emit("ret")
        self.current_function = None

    def generate_method(self, method: MethodDef, struct: StructDef):
        """Generate code for a struct method. 'self' is passed as implicit first argument."""
        method_name = f"{struct.name}_{method.name}"
        self.current_function = method_name
        self.current_struct = struct
        self.locals = {}
        self.params = {}
        self.defer_stack = []  # Clear defer stack for new method

        # Collect locals
        decls = self.collect_var_decls(method.body) if method.body else []

        # 'self' is the first argument (pointer to struct), then explicit params
        all_params = [("self", struct.name)] + list(method.params)

        arg_regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        param_reg_pool = ["%r14", "%r15", "%r13"]  # callee-saved to survive calls
        reg_param_count = min(len(all_params), len(param_reg_pool))
        saved_regs = param_reg_pool[:reg_param_count]

        # Stack slots for non-register params + locals
        total_slots = (len(all_params) - reg_param_count)
        locals_size = sum(self.var_size(d.var_type or "int") for d in decls)
        stack_bytes = total_slots * 8 + locals_size

        saved_regs_bytes = len(saved_regs) * 8
        total_frame = saved_regs_bytes + stack_bytes
        if total_frame % 16 != 0:
            stack_bytes += 8

        offset = -stack_bytes if stack_bytes else 0

        self.emit(f".globl {method_name}")
        self.emit(f"{method_name}:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")

        for reg in saved_regs:
            self.emit(f"push {reg}")

        if stack_bytes:
            self.emit(f"subq ${stack_bytes}, %rsp")

        # Assign parameters (register-backed first, then stack-backed)
        offset_cursor = offset
        for idx, (pname, ptype) in enumerate(all_params):
            if idx < reg_param_count:
                sym = Symbol(pname, ptype or "int", False, 0, is_param=True, reg=param_reg_pool[idx])
                self.locals[pname] = sym
                self.params[pname] = sym
            else:
                sym = Symbol(pname, ptype or "int", False, offset_cursor, is_param=True)
                self.locals[pname] = sym
                self.params[pname] = sym
                offset_cursor += 8

        # Move incoming parameter values to their homes
        for idx, (pname, _) in enumerate(all_params):
            sym = self.params[pname]
            if sym.reg:
                if idx < len(arg_regs):
                    self.emit(f"movq {arg_regs[idx]}, {sym.reg}")
                else:
                    src_offset = 16 + (idx - len(arg_regs)) * 8
                    self.emit(f"movq {src_offset}(%rbp), {sym.reg}")
            else:
                if idx < len(arg_regs):
                    self.emit(f"movq {arg_regs[idx]}, {self.get_variable_location(sym)}")
                else:
                    src_offset = 16 + (idx - len(arg_regs)) * 8
                    self.emit(f"movq {src_offset}(%rbp), %rax")
                    self.emit(f"movq %rax, {self.get_variable_location(sym)}")

        # Assign locals after params
        for d in decls:
            # Infer type from initializer if not explicitly specified
            if d.var_type:
                var_type = d.var_type
            elif d.value:
                var_type = self._infer_type_from_expr(d.value)
            else:
                var_type = "int"
            size = self.var_size(var_type)
            sym = Symbol(d.name, var_type, False, offset_cursor, size=size)
            self.locals[d.name] = sym
            offset_cursor += size

        end_lbl = self.get_label("ret")
        self.current_function_end_label = end_lbl

        # Initialize struct locals
        for d in decls:
            var_type = d.var_type or "int"
            if var_type in self.struct_layouts:
                size = self.struct_layouts[var_type]["size"]
                loc = self.get_variable_location(self.locals[d.name])
                self.emit(f"movq ${size}, %rdi")
                self.emit("call vyl_alloc")
                self.emit(f"movq %rax, {loc}")

        if method.body:
            for stmt in method.body.statements:
                self.generate_statement(stmt, end_label=end_lbl)

        self.emit(f"{end_lbl}:")
        if stack_bytes:
            self.emit(f"addq ${stack_bytes}, %rsp")
        for reg in reversed(saved_regs):
            self.emit(f"pop {reg}")
        self.emit("leave")
        self.emit("ret")
        self.current_function = None
        self.current_struct = None
        self.locals = {}
        self.params = {}

    def generate_main_stub(self):
        self.emit(".globl main")
        self.emit("main:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("movq %rdi, argc_store(%rip)")
        self.emit("movq %rsi, argv_store(%rip)")
        self.emit("movq %rbp, stack_base(%rip)")
        # After push rbp, rsp % 16 == 0. Keep aligned for calls.
        self.emit("subq $16, %rsp")
        # seed rand()
        self.emit("movq $0, %rdi")
        self.emit("call time")
        self.emit("movq %rax, %rdi")
        self.emit("call srand")
        self.emit("call Main")
        self.emit("movq %rax, %rdi")
        self.emit("movq $60, %rax")
        self.emit("syscall")

    def generate_statement(self, stmt, end_label: Optional[str] = None):
        if isinstance(stmt, Assignment):
            self.generate_assignment(stmt)
        elif isinstance(stmt, VarDecl):
            sym = self.get_variable_symbol(stmt.name)
            if not sym:
                raise CodegenError(f"Undefined local declaration for '{stmt.name}'")
            if stmt.value:
                self.generate_expression(stmt.value)
                self.emit(f"movq %rax, {self.get_variable_location(sym)}")
        elif isinstance(stmt, TupleUnpack):
            # Generate the tuple expression - tuple values are laid out on stack
            self.generate_expression(stmt.value)
            # %rax now points to the tuple base address
            # Unpack each element into its corresponding variable
            for i, name in enumerate(stmt.names):
                sym = self.get_variable_symbol(name)
                if not sym:
                    raise CodegenError(f"Undefined local declaration for '{name}'")
                # Each tuple element is 8 bytes
                offset = i * 8
                self.emit(f"movq {offset}(%rax), %rcx")
                self.emit(f"movq %rcx, {self.get_variable_location(sym)}")
        elif isinstance(stmt, FunctionCall):
            self.generate_function_call(stmt)
        elif isinstance(stmt, IfStmt):
            self.generate_if(stmt, end_label=end_label)
        elif isinstance(stmt, WhileStmt):
            self.generate_while(stmt, end_label=end_label)
        elif isinstance(stmt, ForStmt):
            self.generate_for(stmt, end_label=end_label)
        elif isinstance(stmt, DeferStmt):
            # Add defer to stack - will be executed when function returns
            self.defer_stack.append(stmt)
        elif isinstance(stmt, Block):
            for s in stmt.statements:
                self.generate_statement(s, end_label=end_label)
        elif isinstance(stmt, ReturnStmt):
            if stmt.value:
                self.generate_expression(stmt.value)
            else:
                self.emit("movq $0, %rax")
            # Execute all deferred statements in LIFO order
            self._emit_deferred_statements()
            if end_label:
                self.emit(f"jmp {end_label}")
            else:
                self.emit("leave")
                self.emit("ret")
        elif isinstance(stmt, StructDef):
            return
        else:
            self.generate_expression(stmt)

    def _emit_deferred_statements(self):
        """Emit all deferred statements in LIFO order, preserving return value."""
        if not self.defer_stack:
            return
        # Save return value
        self.emit("pushq %rax")
        # Execute deferred statements in reverse order
        for defer_stmt in reversed(self.defer_stack):
            for stmt in defer_stmt.body.statements:
                self.generate_statement(stmt)
        # Restore return value
        self.emit("popq %rax")

    def collect_var_decls(self, block: Block) -> List[VarDecl]:
        """Collect VarDecl nodes and synthesize VarDecl for TupleUnpack names."""
        decls: List[VarDecl] = []
        for stmt in block.statements if block else []:
            if isinstance(stmt, VarDecl):
                decls.append(stmt)
            elif isinstance(stmt, TupleUnpack):
                # Create synthetic VarDecl for each unpacked variable
                for i, name in enumerate(stmt.names):
                    var_type = stmt.types[i] if stmt.types[i] else "int"
                    synthetic = VarDecl(name=name, var_type=var_type, is_mutable=True, value=None, 
                                       line=stmt.line, column=stmt.column)
                    decls.append(synthetic)
            elif isinstance(stmt, Block):
                decls.extend(self.collect_var_decls(stmt))
            elif isinstance(stmt, IfStmt):
                decls.extend(self.collect_from_if(stmt))
            elif isinstance(stmt, WhileStmt):
                decls.extend(self.collect_var_decls(stmt.body))
            elif isinstance(stmt, ForStmt):
                decls.extend(self.collect_var_decls(stmt.body))
        return decls

    def collect_from_if(self, node: IfStmt) -> List[VarDecl]:
        decls: List[VarDecl] = []
        decls.extend(self.collect_var_decls(node.then_block))
        if node.else_block:
            if isinstance(node.else_block, Block):
                decls.extend(self.collect_var_decls(node.else_block))
            elif isinstance(node.else_block, IfStmt):
                decls.extend(self.collect_from_if(node.else_block))
        return decls

    # ---------- expressions ----------
    def generate_expression(self, expr):
        if isinstance(expr, Literal):
            if expr.literal_type == "int":
                self.emit(f"movq ${expr.value}, %rax")
            elif expr.literal_type == "dec":
                self.emit(f"movq ${int(expr.value)}, %rax")
            elif expr.literal_type == "string":
                label = self.get_label(".str")
                self.string_literals.append((label, expr.value))
                self.emit(f"leaq {label}(%rip), %rax")
            elif expr.literal_type == "bool":
                self.emit(f"movq ${1 if expr.value else 0}, %rax")
            return

        if isinstance(expr, Identifier):
            if expr.name == "argc":
                self.emit("movq argc_store(%rip), %rax")
            elif expr.name == "argv":
                self.emit("movq argv_store(%rip), %rax")
            else:
                sym = self.get_variable_symbol(expr.name)
                if not sym:
                    raise CodegenError(f"Undefined variable '{expr.name}'")
                self.emit(f"movq {self.get_variable_location(sym)}, %rax")
            return

        if isinstance(expr, FieldAccess):
            # Check if this is an enum access (receiver is an identifier that names an enum)
            if isinstance(expr.receiver, Identifier):
                enum_name = expr.receiver.name
                if enum_name in self.enum_values:
                    variant = expr.field
                    if variant not in self.enum_values[enum_name]:
                        raise CodegenError(f"Unknown enum variant '{enum_name}.{variant}'")
                    val = self.enum_values[enum_name][variant]
                    self.emit(f"movq ${val}, %rax")
                    return
            self.generate_address(expr, dest="%rax")
            self.emit("movq (%rax), %rax")
            return

        if isinstance(expr, IndexExpr):
            # Save base while computing index; index expression may call functions
            self.generate_expression(expr.receiver)
            self.emit("push %rax")
            self.generate_expression(expr.index)
            self.emit("movq %rax, %rcx")
            self.emit("pop %rbx")
            bounds_fail = self.get_label("oob")
            self.emit("cmpq $0, %rbx")
            self.emit(f"je {bounds_fail}")
            self.emit("cmpq $0, %rcx")
            self.emit(f"jl {bounds_fail}")
            self.emit("movq -8(%rbx), %rdx")
            self.emit("cmpq %rdx, %rcx")
            self.emit(f"jae {bounds_fail}")
            self.emit("imulq $8, %rcx")
            self.emit("addq %rcx, %rbx")
            self.emit("movq (%rbx), %rax")
            self.emit(f"jmp {bounds_fail}_done")
            self.emit(f"{bounds_fail}:")
            self.emit("call vyl_bounds_fail")
            self.emit(f"{bounds_fail}_done:")
            return

        if isinstance(expr, FunctionCall):
            self.generate_function_call(expr)
            return

        if isinstance(expr, NewExpr):
            self.generate_new_expr(expr)
            return

        if isinstance(expr, ArrayLiteral):
            self.generate_array_literal(expr)
            return

        if isinstance(expr, TupleLiteral):
            self.generate_tuple_literal(expr)
            return

        if isinstance(expr, InterpString):
            self.generate_interp_string(expr)
            return

        if isinstance(expr, TryExpr):
            self.generate_try_expr(expr)
            return

        if isinstance(expr, UnaryExpr):
            self.generate_expression(expr.operand)
            if expr.operator == "-":
                self.emit("negq %rax")
            elif expr.operator in ("!", "NOT"):
                self.emit("cmpq $0, %rax")
                self.emit("sete %al")
                self.emit("movzbq %al, %rax")
            return

        if isinstance(expr, BinaryExpr):
            # Short-circuit logical ops
            if expr.operator in ("&&", "||"):
                end_lbl = self.get_label("bool_end")
                false_lbl = self.get_label("bool_false")
                true_lbl = self.get_label("bool_true") if expr.operator == "||" else None
                # Evaluate left
                self.generate_expression(expr.left)
                self.emit("cmpq $0, %rax")
                if expr.operator == "&&":
                    self.emit(f"je {false_lbl}")
                    self.generate_expression(expr.right)
                    self.emit("cmpq $0, %rax")
                    self.emit(f"je {false_lbl}")
                    self.emit("movq $1, %rax")
                    self.emit(f"jmp {end_lbl}")
                    self.emit(f"{false_lbl}:")
                    self.emit("movq $0, %rax")
                    self.emit(f"{end_lbl}:")
                else:  # ||
                    self.emit(f"jne {true_lbl}")
                    self.generate_expression(expr.right)
                    self.emit("cmpq $0, %rax")
                    self.emit(f"jne {true_lbl}")
                    self.emit("movq $0, %rax")
                    self.emit(f"jmp {end_lbl}")
                    self.emit(f"{true_lbl}:")
                    self.emit("movq $1, %rax")
                    self.emit(f"{end_lbl}:")
                return

            def _is_stringish(node):
                if isinstance(node, Literal) and node.literal_type == "string":
                    return True
                if isinstance(node, FunctionCall) and node.name in ("GetArg", "Read", "SHA256"):
                    return True
                if isinstance(node, Identifier):
                    sym = self.get_variable_symbol(node.name)
                    if sym and sym.typ == "string":
                        return True
                if isinstance(node, BinaryExpr) and node.operator == "+":
                    # Recursive check - if either side is stringish, result is stringish
                    return _is_stringish(node.left) or _is_stringish(node.right)
                return False

            left_stringy = _is_stringish(expr.left)
            right_stringy = _is_stringish(expr.right)
            stringy = left_stringy or right_stringy

            if expr.operator == "+" and stringy:
                # String concatenation with automatic int-to-string conversion
                # Use callee-saved registers to preserve values across function calls
                
                # Helper to convert int in %rax to string, result in %rax
                def emit_int_to_string():
                    self.emit("movq %rax, %r14")  # save int value in callee-saved reg
                    self.emit("movq $24, %rdi")
                    self.emit("call vyl_alloc")
                    self.emit("movq %rax, %r12")  # buffer in r12
                    self.emit("movq %r12, %rdi")  # 1st arg: buffer
                    self.emit("leaq .int_fmt(%rip), %rsi")  # 2nd arg: format
                    self.emit("movq %r14, %rdx")  # 3rd arg: value
                    self.emit("movq $0, %rax")  # no vector registers for sprintf
                    self.emit("call sprintf")
                    self.emit("movq %r12, %rax")  # result is buffer
                
                # Generate left, convert if needed
                self.generate_expression(expr.left)
                if not left_stringy:
                    emit_int_to_string()
                self.emit("movq %rax, %r15")  # save left string in r15 (callee-saved)
                
                # Generate right, convert if needed
                self.generate_expression(expr.right)
                if not right_stringy:
                    emit_int_to_string()
                self.emit("movq %rax, %rbx")  # right string in rbx
                
                # Now concatenate: left in r15, right in rbx
                # Get strlen of left
                self.emit("movq %r15, %rdi")
                self.emit("call strlen")
                self.emit("movq %rax, %r14")  # len_left in r14
                
                # Get strlen of right
                self.emit("movq %rbx, %rdi")
                self.emit("call strlen")
                self.emit("addq %r14, %rax")  # total length
                self.emit("incq %rax")  # +1 for null terminator
                
                # Allocate destination buffer
                self.emit("movq %rax, %rdi")
                self.emit("call vyl_alloc")
                self.emit("movq %rax, %r13")  # dest buffer in r13
                
                # strcpy(dest, left)
                self.emit("movq %r13, %rdi")
                self.emit("movq %r15, %rsi")
                self.emit("call strcpy")
                
                # strcat(dest, right)
                self.emit("movq %r13, %rdi")
                self.emit("movq %rbx, %rsi")
                self.emit("call strcat")
                
                self.emit("movq %r13, %rax")  # return concatenated string
                return

            if expr.operator in ("==", "!=") and stringy:
                self.generate_expression(expr.left)
                self.emit("push %rax")
                self.generate_expression(expr.right)
                self.emit("movq %rax, %rsi")
                self.emit("pop %rdi")
                self.emit("call strcmp")
                self.emit("cmpq $0, %rax")
                self.emit("sete %al" if expr.operator == "==" else "setne %al")
                self.emit("movzbq %al, %rax")
                return

            self.generate_expression(expr.left)
            self.emit("push %rax")
            self.generate_expression(expr.right)
            self.emit("movq %rax, %rbx")
            self.emit("pop %rax")

            op = expr.operator
            if op == "+":
                self.emit("addq %rbx, %rax")
            elif op == "-":
                self.emit("subq %rbx, %rax")
            elif op == "*":
                self.emit("imulq %rbx, %rax")
            elif op == "/":
                self.emit("cqto")
                self.emit("idivq %rbx")
            elif op == "%":
                self.emit("cqto")
                self.emit("idivq %rbx")
                self.emit("movq %rdx, %rax")
            elif op in ("==", "!=", "<", ">", "<=", ">="):
                self.emit("cmpq %rbx, %rax")
                table = {
                    "==": "sete",
                    "!=": "setne",
                    "<": "setl",
                    ">": "setg",
                    "<=": "setle",
                    ">=": "setge",
                }
                self.emit(f"{table[op]} %al")
                self.emit("movzbq %al, %rax")
            else:
                raise CodegenError(f"Unsupported binary operator '{op}'")
            return

        if isinstance(expr, SelfExpr):
            # 'self' is a pointer to the current struct, stored in locals
            sym = self.get_variable_symbol("self")
            if not sym:
                raise CodegenError("'self' used outside of a method")
            self.emit(f"movq {self.get_variable_location(sym)}, %rax")
            return

        if isinstance(expr, NullLiteral):
            self.emit("movq $0, %rax")
            return

        if isinstance(expr, AddressOf):
            # Get address of the operand
            self.generate_address(expr.operand, dest="%rax")
            return

        if isinstance(expr, Dereference):
            # Load value at pointer
            self.generate_expression(expr.operand)
            self.emit("movq (%rax), %rax")
            return

        if isinstance(expr, EnumAccess):
            # Enums are compile-time constants
            if expr.enum_name not in self.enum_values:
                raise CodegenError(f"Unknown enum '{expr.enum_name}'")
            if expr.variant not in self.enum_values[expr.enum_name]:
                raise CodegenError(f"Unknown enum variant '{expr.enum_name}.{expr.variant}'")
            val = self.enum_values[expr.enum_name][expr.variant]
            self.emit(f"movq ${val}, %rax")
            return

        if isinstance(expr, MethodCall):
            self.generate_method_call(expr)
            return

        raise CodegenError(f"Unsupported expression type: {type(expr).__name__}")

    # ---------- address helpers ----------
    def generate_address(self, expr, dest: str = "%rax", want_struct_data: bool = False) -> str:
        if isinstance(expr, Identifier):
            sym = self.get_variable_symbol(expr.name)
            if not sym:
                raise CodegenError(f"Undefined variable '{expr.name}'")
            if sym.typ in self.struct_layouts:
                # load pointer to struct storage
                self.emit(f"movq {self.get_variable_location(sym)}, {dest}")
                return sym.typ
            self.emit(f"leaq {self.get_variable_location(sym)}, {dest}")
            return sym.typ
        if isinstance(expr, SelfExpr):
            # 'self' is a pointer to the current struct
            sym = self.get_variable_symbol("self")
            if not sym:
                raise CodegenError("'self' used outside of a method")
            self.emit(f"movq {self.get_variable_location(sym)}, {dest}")
            return sym.typ
        if isinstance(expr, Dereference):
            # *ptr - evaluate pointer, the result is the address we want
            self.generate_expression(expr.operand)
            if dest != "%rax":
                self.emit(f"movq %rax, {dest}")
            # Return type without the leading *
            # We'd need type info here, for now just return "int"
            return "int"
        if isinstance(expr, FieldAccess):
            recv_type = self.generate_address(expr.receiver, dest=dest, want_struct_data=True)
            layout = self.struct_layouts.get(recv_type)
            if not layout:
                raise CodegenError(f"Field access on non-struct type '{recv_type}'")
            field_info = layout["fields"].get(expr.field)
            if not field_info:
                raise CodegenError(f"Unknown field '{expr.field}' on struct '{recv_type}'")
            field_type, offset = field_info
            if offset:
                self.emit(f"addq ${offset}, {dest}")
            if want_struct_data and field_type in self.struct_layouts:
                self.emit(f"movq ({dest}), {dest}")
            return field_type
        if isinstance(expr, IndexExpr):
            # dest receives address of element
            self.generate_expression(expr.receiver)
            self.emit("push %rax")
            self.generate_expression(expr.index)
            self.emit("movq %rax, %rcx")
            self.emit("pop %rbx")
            bounds_fail = self.get_label("oob")
            self.emit("cmpq $0, %rbx")
            self.emit(f"je {bounds_fail}")
            self.emit("cmpq $0, %rcx")
            self.emit(f"jl {bounds_fail}")
            self.emit("movq -8(%rbx), %rdx")
            self.emit("cmpq %rdx, %rcx")
            self.emit(f"jae {bounds_fail}")
            self.emit("imulq $8, %rcx")
            self.emit("addq %rcx, %rbx")
            self.emit(f"movq %rbx, {dest}")
            self.emit(f"jmp {bounds_fail}_done")
            self.emit(f"{bounds_fail}:")
            self.emit("call vyl_bounds_fail")
            self.emit(f"{bounds_fail}_done:")
            return "int"
        raise CodegenError("Unsupported lvalue expression")

    def var_size(self, var_type: str) -> int:
        if var_type in self.struct_layouts:
            return 8  # struct variables hold pointers
        return 8

    def build_struct_layouts(self, program: Program) -> Dict[str, dict]:
        layouts: Dict[str, dict] = {}
        for stmt in program.statements:
            if not isinstance(stmt, StructDef):
                continue
            offset = 0
            fields: Dict[str, tuple[str, int]] = {}
            for fld in stmt.fields:
                ftype = fld.var_type or "int"
                fields[fld.name] = (ftype, offset)
                offset += 8
            size = offset or 8
            layouts[stmt.name] = {"size": size, "fields": fields}
        return layouts

    def build_enum_values(self, program: Program) -> Dict[str, Dict[str, int]]:
        """Build a mapping of EnumName -> {VARIANT: value}"""
        enums: Dict[str, Dict[str, int]] = {}
        for stmt in program.statements:
            if not isinstance(stmt, EnumDef):
                continue
            variants: Dict[str, int] = {}
            for name, value in stmt.variants:
                variants[name] = value
            enums[stmt.name] = variants
        return enums

    def build_method_table(self, program: Program) -> Dict[str, Dict[str, MethodDef]]:
        """Build a mapping of StructName -> {method_name: MethodDef}"""
        methods: Dict[str, Dict[str, MethodDef]] = {}
        for stmt in program.statements:
            if not isinstance(stmt, StructDef):
                continue
            methods[stmt.name] = {}
            for method in stmt.methods:
                methods[stmt.name][method.name] = method
        return methods

    # ---------- assignments ----------
    def generate_assignment(self, assign: Assignment):
        self.generate_expression(assign.value)
        if assign.target:
            self.emit("push %rax")
            self.generate_address(assign.target, dest="%rcx")
            self.emit("pop %rax")
            self.emit("movq %rax, (%rcx)")
            return
        sym = self.get_variable_symbol(assign.name)
        if sym:
            self.emit(f"movq %rax, {self.get_variable_location(sym)}")
        else:
            raise CodegenError(f"Undefined variable '{assign.name}'")

    # ---------- struct instantiation ----------
    def generate_new_expr(self, expr: NewExpr):
        """Generate code for new StructName or new StructName{field: value, ...}"""
        layout = self.struct_layouts.get(expr.struct_name)
        if not layout:
            raise CodegenError(f"Unknown struct type '{expr.struct_name}'")
        size = layout["size"]
        
        # Allocate memory for struct
        self.emit(f"movq ${size}, %rdi")
        self.emit("call vyl_alloc")
        self.emit("movq %rax, %r12")  # save struct pointer
        
        # Zero-initialize all fields
        for i in range(size // 8):
            self.emit(f"movq $0, {i * 8}(%r12)")
        
        # Apply initializers
        for field_name, value in expr.initializers:
            field_info = layout["fields"].get(field_name)
            if not field_info:
                raise CodegenError(f"Unknown field '{field_name}' on struct '{expr.struct_name}'")
            field_type, offset = field_info
            
            self.emit("push %r12")  # save struct pointer
            self.generate_expression(value)
            self.emit("pop %r12")  # restore struct pointer
            self.emit(f"movq %rax, {offset}(%r12)")
        
        self.emit("movq %r12, %rax")  # return struct pointer

    # ---------- array literals ----------
    def generate_array_literal(self, expr: ArrayLiteral):
        """Generate code for [expr1, expr2, ...]"""
        num_elements = len(expr.elements)
        
        # Allocate: 8 bytes for length + 8 bytes per element
        total_size = 8 + (num_elements * 8)
        self.emit(f"movq ${total_size}, %rdi")
        self.emit("call vyl_alloc")
        self.emit("movq %rax, %r12")  # save array pointer
        
        # Store length at offset 0
        self.emit(f"movq ${num_elements}, (%r12)")
        
        # Evaluate and store each element
        for i, elem in enumerate(expr.elements):
            self.emit("push %r12")  # save array pointer
            self.generate_expression(elem)
            self.emit("pop %r12")  # restore array pointer
            offset = 8 + (i * 8)  # skip length field
            self.emit(f"movq %rax, {offset}(%r12)")
        
        # Return pointer to first element (skip length)
        self.emit("addq $8, %r12")
        self.emit("movq %r12, %rax")

    def generate_tuple_literal(self, expr: TupleLiteral):
        """Generate code for (expr1, expr2, ...)"""
        num_elements = len(expr.elements)
        
        # Allocate: 8 bytes per element
        total_size = num_elements * 8
        self.emit(f"movq ${total_size}, %rdi")
        self.emit("call vyl_alloc")
        self.emit("movq %rax, %r12")  # save tuple pointer
        
        # Evaluate and store each element
        for i, elem in enumerate(expr.elements):
            self.emit("push %r12")  # save tuple pointer
            self.generate_expression(elem)
            self.emit("pop %r12")  # restore tuple pointer
            offset = i * 8
            self.emit(f"movq %rax, {offset}(%r12)")
        
        # Return pointer to tuple
        self.emit("movq %r12, %rax")

    def generate_interp_string(self, expr: InterpString):
        """Generate code for interpolated string: "Hello {name}!"
        
        The approach is to build the string by:
        1. For each part, generate either a string literal or convert expression to string
        2. Concatenate all parts together using vyl_strconcat
        """
        # Import lexer and parser for parsing embedded expressions
        try:
            from .lexer import tokenize
            from .parser import Parser
        except ImportError:
            from lexer import tokenize
            from parser import Parser
        
        parts = expr.parts
        
        if not parts:
            # Empty string
            label = self.get_label(".str")
            self.string_literals.append((label, ""))
            self.emit(f"leaq {label}(%rip), %rax")
            return
        
        # Helper to convert int in %rax to string, result in %rax
        # Uses rbx (callee-saved) to preserve values across calls
        def emit_int_to_string():
            self.emit("push %rbx")  # save rbx
            self.emit("movq %rax, %rbx")  # save int value
            self.emit("subq $8, %rsp")  # align stack to 16 bytes
            self.emit("movq $24, %rdi")
            self.emit("call vyl_alloc")
            self.emit("push %rax")  # save buffer pointer
            self.emit("movq %rax, %rdi")  # 1st arg: buffer
            self.emit("leaq .int_fmt(%rip), %rsi")  # 2nd arg: format
            self.emit("movq %rbx, %rdx")  # 3rd arg: value
            self.emit("movq $0, %rax")  # no vector registers for sprintf
            self.emit("call sprintf")
            self.emit("pop %rax")  # result is buffer
            self.emit("addq $8, %rsp")  # remove alignment padding
            self.emit("pop %rbx")  # restore rbx
        
        def is_stringish_expr(node):
            """Check if expression result is a string."""
            if isinstance(node, Literal) and node.literal_type == "string":
                return True
            if isinstance(node, FunctionCall) and node.name in ("GetArg", "Read", "SHA256", "Input", "GetEnv", "StrConcat", "Substring"):
                return True
            if isinstance(node, Identifier):
                sym = self.get_variable_symbol(node.name)
                if sym and sym.typ == "string":
                    return True
            if isinstance(node, InterpString):
                return True
            return False
        
        # Generate first part
        is_expr, value = parts[0]
        if is_expr:
            # Parse and generate the expression
            tokens = tokenize(value)
            parser = Parser(tokens)
            ast_expr = parser.parse_expression()
            self.generate_expression(ast_expr)
            if not is_stringish_expr(ast_expr):
                emit_int_to_string()
        else:
            # String literal
            label = self.get_label(".str")
            self.string_literals.append((label, value))
            self.emit(f"leaq {label}(%rip), %rax")
        
        # If only one part, we're done
        if len(parts) == 1:
            return
        
        # Save result and concatenate with remaining parts
        self.emit("push %rax")  # Save accumulated string
        
        for is_expr, value in parts[1:]:
            # Generate next part
            if is_expr:
                tokens = tokenize(value)
                parser = Parser(tokens)
                ast_expr = parser.parse_expression()
                self.generate_expression(ast_expr)
                if not is_stringish_expr(ast_expr):
                    emit_int_to_string()
            else:
                label = self.get_label(".str")
                self.string_literals.append((label, value))
                self.emit(f"leaq {label}(%rip), %rax")
            
            # Concatenate: pop left, right is in rax
            self.emit("movq %rax, %rsi")  # right
            self.emit("pop %rdi")  # left
            self.emit("call vyl_strconcat")
            self.emit("push %rax")  # Save result for next iteration
        
        # Final result is on stack
        self.emit("pop %rax")

    def generate_try_expr(self, expr: TryExpr):
        """Generate code for error propagation: expr?
        
        If the operand evaluates to < 0, return early with that value.
        Otherwise, continue with the value.
        """
        # Evaluate the operand
        self.generate_expression(expr.operand)
        
        # Check if result is < 0 (error condition)
        ok_label = self.get_label("try_ok")
        self.emit("cmpq $0, %rax")
        self.emit(f"jge {ok_label}")  # Jump if >= 0 (success)
        
        # Error path: execute deferred statements and jump to function epilogue
        self._emit_deferred_statements()
        
        # Jump to the function's return label which handles proper stack cleanup
        if self.current_function_end_label:
            self.emit(f"jmp {self.current_function_end_label}")
        else:
            # Fallback: direct return (shouldn't happen in practice)
            self.emit("leave")
            self.emit("ret")
        
        # Success path: continue with the value
        self.emit(f"{ok_label}:")
        # Value is already in %rax

    # ---------- calls ----------
    def generate_function_call(self, call: FunctionCall):
        name = call.name
        if name == "Print":
            if call.arguments:
                arg = call.arguments[0]
                self.generate_expression(arg)
                stringy = isinstance(arg, Literal) and arg.literal_type == "string"
                if isinstance(arg, InterpString):
                    stringy = True
                if isinstance(arg, FunctionCall) and arg.name in ("GetArg", "Read", "SHA256", "Input", "GetEnv", "StrConcat", "Substring"):
                    stringy = True
                # Check if it's a variable reference of type string
                if isinstance(arg, Identifier):
                    sym = self.get_variable_symbol(arg.name)
                    if sym and sym.typ == "string":
                        stringy = True
                # Check if it's indexing a string array
                if isinstance(arg, IndexExpr):
                    if isinstance(arg.receiver, Identifier):
                        sym = self.get_variable_symbol(arg.receiver.name)
                        if sym and sym.typ in ("string[]", "array"):
                            # Check if it's a string array by inspecting element type
                            if sym.typ == "string[]":
                                stringy = True
                # Check if it's a string concatenation expression
                if isinstance(arg, BinaryExpr) and arg.operator == "+":
                    stringy = self._expr_is_stringish(arg)
                self.emit("movq %rax, %rdi")
                self.emit("call print_string" if stringy else "call print_int")
            return

        if name == "Len":
            if len(call.arguments) != 1:
                raise CodegenError("Len expects (array)")
            self.generate_expression(call.arguments[0])
            # Array pointer points to first element, length is at -8
            self.emit("movq -8(%rax), %rax")
            return

        if name == "Exists":
            if len(call.arguments) != 1:
                raise CodegenError("Exists expects (path)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("movq $0, %rsi")
            self.emit("call access")
            self.emit("cmpq $0, %rax")
            self.emit("sete %al")
            self.emit("movzbq %al, %rax")
            return
            self.emit("subq $8, %rax")          # reserve length slot before data
            self.emit("movq %rbx, (%rax)")      # store length
            self.emit("addq $8, %rax")          # return data pointer
            if len(call.arguments) != 1:
                raise CodegenError("Sys expects (command)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call system")
            return

        if name == "Input":
            if len(call.arguments) != 0:
                raise CodegenError("Input expects ()")
            self.emit("call vyl_input")
            return

        if name == "CreateFolder":
            if not call.arguments:
                raise CodegenError("CreateFolder expects at least one path")
            for arg in call.arguments:
                self.generate_expression(arg)
                self.emit("movq %rax, %rdi")
                self.emit("movq $493, %rsi")
                self.emit("call mkdir")
            return

        if name == "Open":
            if len(call.arguments) != 2:
                raise CodegenError("Open expects (path, mode)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call fopen")
            return

        if name == "Close":
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call fclose")
            return

        if name == "Read":
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_read_all")
            return

        if name == "Write":
            if len(call.arguments) != 2:
                raise CodegenError("Write expects (file, data)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_write_all")
            return

        if name == "SHA256":
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_sha256")
            return

        if name == "GC":
            self.emit("call vyl_collect")
            return

        if name == "ReadFilesize":
            if len(call.arguments) != 1:
                raise CodegenError("ReadFilesize expects (path)")
            fail_lbl = self.get_label("rfs_fail")
            done_lbl = self.get_label("rfs_done")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("leaq .mode_rb(%rip), %rsi")
            self.emit("call fopen")
            self.emit("movq %rax, %rbx")
            self.emit(f"cmpq $0, %rbx")
            self.emit(f"je {fail_lbl}")
            self.emit("movq %rbx, %rdi")
            self.emit("movq $0, %rsi")
            self.emit("movq $2, %rdx")
            self.emit("call fseek")
            self.emit("movq %rbx, %rdi")
            self.emit("call ftell")
            self.emit("movq %rax, %r12")
            self.emit("movq %rbx, %rdi")
            self.emit("call rewind")
            self.emit("movq %rbx, %rdi")
            self.emit("call fclose")
            self.emit("movq %r12, %rax")
            self.emit(f"jmp {done_lbl}")
            self.emit(f"{fail_lbl}:")
            self.emit("movq $0, %rax")
            self.emit(f"{done_lbl}:")
            return

        if name == "Argc":
            self.emit("movq argc_store(%rip), %rax")
            return

        if name == "GetArg":
            if len(call.arguments) == 1:
                self.generate_expression(call.arguments[0])
                self.emit("movq argv_store(%rip), %rbx")
                self.emit("movq %rax, %rcx")
                self.emit("movq (%rbx,%rcx,8), %rax")
                return
            if len(call.arguments) == 2:
                self.generate_expression(call.arguments[1])
                self.emit("movq %rax, %rcx")
                self.generate_expression(call.arguments[0])
                self.emit("movq %rax, %rbx")
                self.emit("movq (%rbx,%rcx,8), %rax")
                return
            raise CodegenError("GetArg expects 1 or 2 arguments")

        if name == "Exit":
            if len(call.arguments) != 1:
                raise CodegenError("Exit expects (code)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call exit")
            self.emit("movq $0, %rax")
            return

        if name == "Sleep":
            if len(call.arguments) != 1:
                raise CodegenError("Sleep expects (ms)")
            self.generate_expression(call.arguments[0])
            self.emit("push %rbp")
            self.emit("movq %rsp, %rbp")
            self.emit("push %rbx")
            self.emit("push %r12")
            # 208 bytes keeps rsp%16==8 after two pushes
            self.emit("subq $208, %rsp")
            self.emit("movq $1000, %rcx")
            self.emit("xorq %rdx, %rdx")
            self.emit("movq %rbx, %rax")
            self.emit("divq %rcx")          # rax=sec, rdx=ms
            self.emit("subq $16, %rsp")
            self.emit("movq %rax, (%rsp)")  # tv_sec
            self.emit("movq %rdx, %rax")
            self.emit("movq $1000000, %rcx")
            self.emit("imulq %rcx, %rax")   # ms->ns
            self.emit("movq %rax, 8(%rsp)") # tv_nsec
            self.emit("leaq (%rsp), %rdi")
            self.emit("movq $0, %rsi")
            self.emit("call nanosleep")
            self.emit("addq $16, %rsp")
            self.emit("pop %rdx")
            self.emit("pop %rcx")
            self.emit("pop %rbx")
            self.emit("movq $0, %rax")
            return

        if name == "Now":
            if len(call.arguments) != 0:
                raise CodegenError("Now expects ()")
            self.emit("subq $16, %rsp")
            self.emit("movq $1, %rdi")        # CLOCK_MONOTONIC
            self.emit("leaq (%rsp), %rsi")
            self.emit("call clock_gettime")
            self.emit("movq (%rsp), %rax")    # sec
            self.emit("imulq $1000, %rax")    # sec -> ms
            self.emit("movq %rax, %rbx")      # sec_ms
            self.emit("movq 8(%rsp), %rcx")   # nsec
            self.emit("movq $1000000, %r8")
            self.emit("xorq %rdx, %rdx")
            self.emit("movq %rcx, %rax")
            self.emit("divq %r8")             # (nsec / 1e6) quotient in rax
            self.emit("addq %rax, %rbx")      # total ms
            self.emit("movq %rbx, %rax")
            self.emit("addq $16, %rsp")
            return

        if name == "RandInt":
            if call.arguments:
                raise CodegenError("RandInt expects ()")
            self.emit("call rand")
            self.emit("movslq %eax, %rax")
            return

        if name == "Remove":
            if len(call.arguments) != 1:
                raise CodegenError("Remove expects (path)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call remove")
            return

        if name == "MkdirP":
            if len(call.arguments) != 1:
                raise CodegenError("MkdirP expects (path)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_mkdir_p")
            return

        if name == "RemoveAll":
            if len(call.arguments) != 1:
                raise CodegenError("RemoveAll expects (path)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_remove_all")
            return

        if name == "OpenDir":
            if len(call.arguments) != 1:
                raise CodegenError("OpenDir expects (path)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call opendir")
            return

        if name == "ReadDir":
            if len(call.arguments) != 1:
                raise CodegenError("ReadDir expects (dirHandle)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_readdir")
            return

        if name == "CloseDir":
            if len(call.arguments) != 1:
                raise CodegenError("CloseDir expects (dirHandle)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call closedir")
            return

        if name == "CopyFile":
            if len(call.arguments) != 2:
                raise CodegenError("CopyFile expects (src, dst)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_copy_file")
            return

        if name == "Unzip":
            if len(call.arguments) != 2:
                raise CodegenError("Unzip expects (zipPath, destDir)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_unzip")
            return

        if name == "Array":
            if len(call.arguments) != 1:
                raise CodegenError("Array expects (length)")
            fail_lbl = self.get_label("array_fail")
            done_lbl = self.get_label("array_done")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rbx")        # length
            self.emit("movq %rax, %rdi")
            self.emit("imulq $8, %rdi")         # bytes for elements
            self.emit("addq $8, %rdi")          # + header for length
            self.emit("call vyl_alloc")
            self.emit("cmpq $0, %rax")
            self.emit(f"je {fail_lbl}")
            self.emit("movq %rbx, (%rax)")      # store length at header
            self.emit("addq $8, %rax")          # return data pointer
            self.emit(f"jmp {done_lbl}")
            self.emit(f"{fail_lbl}:")
            self.emit("movq $0, %rax")
            self.emit(f"{done_lbl}:")
            return

        if name == "Length":
            if len(call.arguments) != 1:
                raise CodegenError("Length expects (array)")
            self.generate_expression(call.arguments[0])
            self.emit("movq -8(%rax), %rax")
            return

        if name == "Sqrt":
            if len(call.arguments) != 1:
                raise CodegenError("Sqrt expects (int)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_isqrt")
            return

        if name == "Malloc":
            if len(call.arguments) != 1:
                raise CodegenError("Malloc expects (size)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call malloc")
            return

        if name == "Alloc":
            if len(call.arguments) != 1:
                raise CodegenError("Alloc expects (size)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_alloc")
            return

        if name == "Free":
            if len(call.arguments) != 1:
                raise CodegenError("Free expects (ptr)")
            self.generate_expression(call.arguments[0])
            # vyl_alloc returns ptr+24, so we need to subtract 24 to get original malloc ptr
            self.emit("subq $24, %rax")
            self.emit("movq %rax, %rdi")
            self.emit("call free")
            self.emit("movq $0, %rax")
            return

        if name == "Memcpy":
            if len(call.arguments) != 3:
                raise CodegenError("Memcpy expects (dst, src, n)")
            self.generate_expression(call.arguments[2])
            self.emit("push %rax")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("pop %rdx")
            self.emit("call memcpy")
            return

        if name == "Memset":
            if len(call.arguments) != 3:
                raise CodegenError("Memset expects (ptr, val, n)")
            self.generate_expression(call.arguments[2])
            self.emit("push %rax")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("pop %rdx")
            self.emit("call memset")
            return

        if name == "StrConcat":
            # StrConcat(a, b) -> new string that is a + b
            if len(call.arguments) != 2:
                raise CodegenError("StrConcat expects (str1, str2)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_strconcat")
            return

        if name == "StrLen":
            if len(call.arguments) != 1:
                raise CodegenError("StrLen expects (str)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call strlen")
            return

        if name == "StrFind":
            # StrFind(haystack, needle) -> index or -1
            if len(call.arguments) != 2:
                raise CodegenError("StrFind expects (haystack, needle)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_strfind")
            return

        if name == "Substring":
            # Substring(str, start, len) -> new string
            if len(call.arguments) != 3:
                raise CodegenError("Substring expects (str, start, len)")
            self.generate_expression(call.arguments[2])
            self.emit("push %rax")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("pop %rdx")
            self.emit("call vyl_substring")
            return

        if name == "GetEnv":
            # GetEnv("VAR") -> value or empty string
            if len(call.arguments) != 1:
                raise CodegenError("GetEnv expects (varname)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call getenv")
            # If NULL, return empty string
            self.emit("cmpq $0, %rax")
            lbl = self.get_label("getenv")
            self.emit(f"jne {lbl}")
            self.emit("leaq .empty_str(%rip), %rax")
            self.emit(f"{lbl}:")
            return

        if name == "Sys":
            # Sys("command") -> exit code
            if len(call.arguments) != 1:
                raise CodegenError("Sys expects (command)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call system")
            return

        if name == "TcpConnect":
            if len(call.arguments) != 2:
                raise CodegenError("TcpConnect expects (host, port)")
            self.generate_expression(call.arguments[0])
            self.emit("push %rax")
            self.generate_expression(call.arguments[1])
            self.emit("movq %rax, %rsi")
            self.emit("pop %rdi")
            self.emit("call vyl_tcp_connect")
            return

        if name == "TcpSend":
            if len(call.arguments) != 2:
                raise CodegenError("TcpSend expects (fd, data)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_tcp_send")
            return

        if name == "TcpRecv":
            if len(call.arguments) != 2:
                raise CodegenError("TcpRecv expects (fd, max)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_tcp_recv")
            return

        if name == "TcpClose":
            if len(call.arguments) != 1:
                raise CodegenError("TcpClose expects (fd)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call close")
            return

        if name == "TcpResolve":
            if len(call.arguments) != 1:
                raise CodegenError("TcpResolve expects (host)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_tcp_resolve")
            return

        if name == "TlsConnect":
            if len(call.arguments) != 2:
                raise CodegenError("TlsConnect expects (host, port)")
            self.generate_expression(call.arguments[0])
            self.emit("push %rax")
            self.generate_expression(call.arguments[1])
            self.emit("movq %rax, %rsi")
            self.emit("pop %rdi")
            self.emit("call vyl_tls_connect")
            return

        if name == "TlsSend":
            if len(call.arguments) != 2:
                raise CodegenError("TlsSend expects (handle, data)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_tls_send")
            return

        if name == "TlsRecv":
            if len(call.arguments) != 2:
                raise CodegenError("TlsRecv expects (handle, max)")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("pop %rsi")
            self.emit("call vyl_tls_recv")
            return

        if name == "TlsClose":
            if len(call.arguments) != 1:
                raise CodegenError("TlsClose expects (handle)")
            self.generate_expression(call.arguments[0])
            self.emit("movq %rax, %rdi")
            self.emit("call vyl_tls_close")
            return

        if name == "HttpGet":
            if len(call.arguments) != 3:
                raise CodegenError("HttpGet expects (host, path, use_tls)")
            self.generate_expression(call.arguments[0])
            self.emit("push %rax")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[2])
            self.emit("movq %rax, %rdx")
            self.emit("pop %rsi")
            self.emit("pop %rdi")
            self.emit("call vyl_http_get")
            return

        if name == "HttpDownload":
            if len(call.arguments) != 4:
                raise CodegenError("HttpDownload expects (host, path, use_tls, dest)")
            self.generate_expression(call.arguments[0])
            self.emit("push %rax")
            self.generate_expression(call.arguments[1])
            self.emit("push %rax")
            self.generate_expression(call.arguments[2])
            self.emit("push %rax")
            self.generate_expression(call.arguments[3])
            self.emit("movq %rax, %rcx")
            self.emit("pop %rdx")
            self.emit("pop %rsi")
            self.emit("pop %rdi")
            self.emit("call vyl_http_download")
            return

        # generic call using SysV registers for first 6 args
        arg_regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        
        # Build full argument list with defaults filled in
        full_args: List = list(call.arguments)
        if name in self.function_defs:
            func_def = self.function_defs[name]
            # Fill in missing arguments with defaults
            for i in range(len(call.arguments), len(func_def.params)):
                _, _, default = func_def.params[i]
                if default is not None:
                    full_args.append(default)
        
        arg_count = len(full_args)
        # Evaluate args right-to-left, push on stack
        for arg in reversed(full_args):
            self.generate_expression(arg)
            self.emit("push %rax")
        # Pop into registers in order
        for idx in range(min(arg_count, len(arg_regs))):
            self.emit(f"pop {arg_regs[idx]}")
        # Remove any remaining stack args beyond 6 (not currently emitted separately)
        if arg_count > len(arg_regs):
            excess = arg_count - len(arg_regs)
            self.emit(f"addq ${excess * 8}, %rsp")
        self.emit(f"call {name}")

    def generate_method_call(self, call: MethodCall):
        """Generate code for a method call: receiver.method(args)
        The receiver becomes the implicit 'self' first argument."""
        # Determine struct name from receiver
        receiver = call.receiver
        struct_name = None
        if isinstance(receiver, Identifier):
            sym = self.get_variable_symbol(receiver.name)
            if sym:
                struct_name = sym.typ
        elif isinstance(receiver, SelfExpr):
            if self.current_struct:
                struct_name = self.current_struct.name
        elif isinstance(receiver, FieldAccess):
            # Need to figure out type from field access - for now just try looking up method
            pass

        method_name = f"{struct_name}_{call.method_name}" if struct_name else call.method_name

        # SysV calling convention: rdi, rsi, rdx, rcx, r8, r9
        arg_regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]

        # Total args = self + explicit args
        all_args = [receiver] + list(call.arguments)
        arg_count = len(all_args)

        # Evaluate args right-to-left, push on stack
        for arg in reversed(all_args):
            self.generate_expression(arg)
            self.emit("push %rax")

        # Pop into registers in order
        for idx in range(min(arg_count, len(arg_regs))):
            self.emit(f"pop {arg_regs[idx]}")

        # Remove any remaining stack args beyond 6
        if arg_count > len(arg_regs):
            excess = arg_count - len(arg_regs)
            self.emit(f"addq ${excess * 8}, %rsp")

        self.emit(f"call {method_name}")

    # ---------- control flow ----------
    def generate_if(self, node: IfStmt, end_label: Optional[str] = None):
        else_lbl = self.get_label("else")
        end_lbl = self.get_label("endif")
        self.generate_expression(node.condition)
        self.emit("cmpq $0, %rax")
        self.emit(f"je {else_lbl}")
        self.generate_statement(node.then_block, end_label=end_label)
        self.emit(f"jmp {end_lbl}")
        self.emit(f"{else_lbl}:")
        if node.else_block:
            self.generate_statement(node.else_block, end_label=end_label)
        self.emit(f"{end_lbl}:")

    def generate_while(self, node: WhileStmt, end_label: Optional[str] = None):
        # Fast path: detect a simple counter loop of the form:
        #   while (i < N) { i = i + 1; }
        # or with <=/>/>= and step +/- literal. Keeps the counter in a
        # register to avoid load/store on every iteration.
        if self._try_generate_counter_while(node, end_label=end_label):
            return

        start_lbl = self.get_label("while")
        end_lbl = self.get_label("endwhile")
        self.emit(f"{start_lbl}:")
        self.generate_expression(node.condition)
        self.emit("cmpq $0, %rax")
        self.emit(f"je {end_lbl}")
        self.generate_statement(node.body, end_label=end_label)
        self.emit(f"jmp {start_lbl}")
        self.emit(f"{end_lbl}:")

    def _try_generate_counter_while(self, node: WhileStmt, end_label: Optional[str] = None) -> bool:
        """Recognize and emit a register-based counter loop for simple patterns.

        Pattern: while (<id> <op> <int>) { <id> = <id> (+|-) <int>; }
        Supported ops: <, <=, >, >=. Step must be a literal. The loop variable
        must resolve to a known symbol.
        """
        cond = node.condition
        if not isinstance(cond, BinaryExpr):
            return False

        # Expect identifier on the left and integer literal on the right
        if not (isinstance(cond.left, Identifier) and isinstance(cond.right, Literal)):
            return False
        if cond.right.literal_type != "int":
            return False

        var_name = cond.left.name
        limit_val = cond.right.value
        op = cond.operator
        if op not in ("<", "<=", ">", ">="):
            return False

        # Body must be a block with a single assignment to the same var
        if not isinstance(node.body, Block):
            return False
        if len(node.body.statements) != 1:
            return False
        body_stmt = node.body.statements[0]
        if not isinstance(body_stmt, Assignment):
            return False
        if body_stmt.name != var_name:
            return False

        # Assignment value must be var +/- int
        if not isinstance(body_stmt.value, BinaryExpr):
            return False
        step_expr = body_stmt.value
        if step_expr.operator not in ("+", "-"):
            return False
        if not (isinstance(step_expr.left, Identifier) and step_expr.left.name == var_name):
            return False
        if not (isinstance(step_expr.right, Literal) and step_expr.right.literal_type == "int"):
            return False

        step_val = step_expr.right.value if step_expr.operator == "+" else -step_expr.right.value

        sym = self.get_variable_symbol(var_name)
        if not sym:
            return False

        start_lbl = self.get_label("while_fast")
        end_lbl = self.get_label("endwhile_fast")

        # Load counter and limit into registers
        self.emit(f"movq {self.get_variable_location(sym)}, %rax")  # counter
        self.emit(f"movq ${limit_val}, %rbx")                        # limit
        self.emit(f"{start_lbl}:")

        # Compare based on operator
        self.emit("cmpq %rbx, %rax")
        jmp_map = {
            "<": "jge",
            "<=": "jg",
            ">": "jle",
            ">=": "jl",
        }
        self.emit(f"{jmp_map[op]} {end_lbl}")

        # Increment/decrement in register
        if step_val == 1:
            self.emit("incq %rax")
        elif step_val == -1:
            self.emit("decq %rax")
        else:
            self.emit(f"addq ${step_val}, %rax")

        self.emit(f"jmp {start_lbl}")
        self.emit(f"{end_lbl}:")

        # Store the final counter back to its home slot
        self.emit(f"movq %rax, {self.get_variable_location(sym)}")
        return True

    def generate_for(self, node: ForStmt, end_label: Optional[str] = None):
        start_lbl = self.get_label("for")
        end_lbl = self.get_label("endfor")
        loop_var = self.get_variable_symbol(node.var_name)
        if not loop_var:
            offset = len(self.locals) * 8 + 8
            loop_var = Symbol(node.var_name, "int", False, -offset)
            self.locals[node.var_name] = loop_var
        self.generate_expression(node.start)
        self.emit(f"movq %rax, {self.get_variable_location(loop_var)}")
        self.emit(f"{start_lbl}:")
        self.emit(f"movq {self.get_variable_location(loop_var)}, %rax")
        self.emit("push %rax")
        self.generate_expression(node.end)
        self.emit("pop %rbx")
        self.emit("cmpq %rax, %rbx")
        self.emit(f"jg {end_lbl}")
        self.generate_statement(node.body, end_label=end_label)
        self.emit(f"incq {self.get_variable_location(loop_var)}")
        self.emit(f"jmp {start_lbl}")
        self.emit(f"{end_lbl}:")

    # ---------- built-ins ----------
    def generate_builtin_functions(self):
        # print_int
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

        # print_string
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

        # clock (stubbed)
        self.emit(".globl clock")
        self.emit("clock:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("movq $2208988800, %rax")
        self.emit("addq clock_counter(%rip), %rax")
        self.emit("incq clock_counter(%rip)")
        self.emit("leave")
        self.emit("ret")

        self.emit(".section .data")
        self.emit("clock_counter: .quad 1")
        self.emit(".fmt_int: .asciz \"%ld\\n\"")
        self.emit(".fmt_string: .asciz \"%s\"")
        self.emit(".fmt_newline: .asciz \"\\n\"")
        self.emit("argc_store: .quad 0")
        self.emit("argv_store: .quad 0")
        self.emit(".mode_rb: .asciz \"rb\"")
        self.emit(".mode_wb: .asciz \"wb\"")
        self.emit("vyl_head: .quad 0")
        self.emit("stack_base: .quad 0")
        self.emit(".section .text")

        # SHA256 helper
        self.emit(".globl vyl_sha256")
        self.emit("vyl_sha256:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        # 2 pushes, rsp % 16 == 0. Keep aligned.
        self.emit("subq $16, %rsp")
        self.emit("movq %rdi, %rbx")
        self.emit("movq %rbx, %rdi")
        self.emit("call strlen")
        self.emit("movq %rax, %r12")
        self.emit("leaq sha256_buf(%rip), %rdi")
        self.emit("movq %rdi, %rdx")
        self.emit("movq %rbx, %rdi")
        self.emit("movq %r12, %rsi")
        self.emit("call SHA256")
        self.emit("leaq sha256_buf(%rip), %rsi")
        self.emit("leaq sha256_hex(%rip), %rdi")
        self.emit("leaq hex_table(%rip), %r8")
        self.emit("movq $0, %rcx")
        self.emit("sha256_hex_loop:")
        self.emit("cmpq $32, %rcx")
        self.emit("jge sha256_hex_done")
        self.emit("movzbl (%rsi,%rcx,1), %eax")
        self.emit("movq %rax, %rbx")
        self.emit("shrq $4, %rbx")
        self.emit("andq $0xF, %rbx")
        self.emit("movzbl (%r8,%rbx,1), %ebx")
        self.emit("movb %bl, (%rdi,%rcx,2)")
        self.emit("movzbl %al, %ebx")
        self.emit("andq $0xF, %rbx")
        self.emit("movzbl (%r8,%rbx,1), %ebx")
        self.emit("movb %bl, 1(%rdi,%rcx,2)")
        self.emit("incq %rcx")
        self.emit("jmp sha256_hex_loop")
        self.emit("sha256_hex_done:")
        self.emit("movb $0, 64(%rdi)")
        self.emit("leaq sha256_hex(%rip), %rax")
        self.emit("addq $16, %rsp")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # input_line -> returns malloc'd string or 0 on EOF/error
        self.emit(".globl vyl_input")
        self.emit("vyl_input:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("movq $4096, %rdi")
        self.emit("call vyl_alloc")
        self.emit("movq %rax, %r12")
        self.emit("cmpq $0, %r12")
        self.emit("je vyl_input_fail")
        self.emit("movq %r12, %rdi")
        self.emit("movq $4096, %rsi")
        self.emit("movq stdin(%rip), %rdx")
        self.emit("call fgets")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_input_fail")
        # strip trailing newline if present
        self.emit("movq %r12, %rdi")
        self.emit("call strlen")
        self.emit("movq %rax, %rbx")
        self.emit("cmpq $0, %rbx")
        self.emit("je vyl_input_done")
        self.emit("decq %rbx")
        self.emit("cmpb $10, (%r12,%rbx,1)")
        self.emit("jne vyl_input_done")
        self.emit("movb $0, (%r12,%rbx,1)")
        self.emit("vyl_input_done:")
        self.emit("movq %r12, %rax")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")
        self.emit("vyl_input_fail:")
        self.emit("movq $0, %rax")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # read_all
        self.emit(".globl vyl_read_all")
        self.emit("vyl_read_all:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r13")
        self.emit("push %r12")
        self.emit("movq %rdi, %rbx")
        self.emit("movq %rbx, %rdi")
        self.emit("movq $0, %rsi")
        self.emit("movq $2, %rdx")
        self.emit("call fseek")
        self.emit("movq %rbx, %rdi")
        self.emit("call ftell")
        self.emit("movq %rax, %r12")
        self.emit("movq %rbx, %rdi")
        self.emit("call rewind")
        self.emit("cmpq $0, %r12")
        self.emit("jle vyl_read_all_zero")
        self.emit("movq %r12, %rdi")
        self.emit("incq %rdi")
        self.emit("call vyl_alloc")
        self.emit("movq %rax, %r13")
        self.emit("movq %r13, %rdi")
        self.emit("movq $1, %rsi")
        self.emit("movq %r12, %rdx")
        self.emit("movq %rbx, %rcx")
        self.emit("call fread")
        self.emit("movb $0, (%r13,%r12,1)")
        self.emit("movq %r13, %rax")
        self.emit("jmp vyl_read_all_done")
        self.emit("vyl_read_all_zero:")
        self.emit("movq $0, %rax")
        self.emit("vyl_read_all_done:")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # write_all
        self.emit(".globl vyl_write_all")
        self.emit("vyl_write_all:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("movq %rdi, %rbx")
        self.emit("movq %rsi, %r8")
        self.emit("movq %r8, %rdi")
        self.emit("call strlen")
        self.emit("movq %rax, %rdx")
        self.emit("movq %r8, %rdi")
        self.emit("movq $1, %rsi")
        self.emit("movq %rdx, %rdx")
        self.emit("movq %rbx, %rcx")
        self.emit("call fwrite")
        self.emit("movq %rax, %rax")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_isqrt (integer floor sqrt)
        self.emit(".globl vyl_isqrt")
        self.emit("vyl_isqrt:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("cmpq $0, %rdi")
        self.emit("jle vyl_isqrt_zero")
        self.emit("xorq %rbx, %rbx")
        self.emit("vyl_isqrt_loop:")
        self.emit("movq %rbx, %rax")
        self.emit("imulq %rbx, %rax")
        self.emit("cmpq %rax, %rdi")
        self.emit("jl vyl_isqrt_done")
        self.emit("incq %rbx")
        self.emit("jmp vyl_isqrt_loop")
        self.emit("vyl_isqrt_done:")
        self.emit("decq %rbx")
        self.emit("movq %rbx, %rax")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")
        self.emit("vyl_isqrt_zero:")
        self.emit("movq $0, %rax")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_alloc (tracked malloc)
        self.emit(".globl vyl_alloc")
        self.emit("vyl_alloc:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("movq %rdi, %rbx")  # size
        self.emit("addq $24, %rdi")
        self.emit("call malloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_alloc_fail")
        self.emit("movq vyl_head(%rip), %rcx")
        self.emit("movq %rcx, (%rax)")      # next
        self.emit("movq %rbx, 8(%rax)")      # size
        self.emit("movq $0, 16(%rax)")       # mark
        self.emit("movq %rax, vyl_head(%rip)")
        self.emit("addq $24, %rax")          # return data ptr
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_bounds_fail: abort on null/OO.B
        self.emit(".globl vyl_bounds_fail")
        self.emit("vyl_bounds_fail:")
        self.emit("movq $1, %rdi")
        self.emit("movq $60, %rax")
        self.emit("syscall")
        self.emit("vyl_alloc_fail:")
        self.emit("movq $0, %rax")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_mark_ptr(rdi=ptr)
        self.emit(".globl vyl_mark_ptr")
        self.emit("vyl_mark_ptr:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("cmpq $0, %rdi")
        self.emit("je vyl_mark_done")
        self.emit("movq vyl_head(%rip), %rbx")
        self.emit("vyl_mark_loop:")
        self.emit("cmpq $0, %rbx")
        self.emit("je vyl_mark_done")
        self.emit("leaq 24(%rbx), %rax")
        self.emit("cmpq %rax, %rdi")
        self.emit("jb vyl_mark_next")
        self.emit("movq 8(%rbx), %rcx")
        self.emit("leaq (%rax,%rcx,1), %rdx")
        self.emit("cmpq %rdi, %rdx")
        self.emit("jae vyl_mark_next")
        self.emit("movq $1, 16(%rbx)")
        self.emit("jmp vyl_mark_done")
        self.emit("vyl_mark_next:")
        self.emit("movq (%rbx), %rbx")
        self.emit("jmp vyl_mark_loop")
        self.emit("vyl_mark_done:")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_collect (mark-sweep)
        self.emit(".globl vyl_collect")
        self.emit("vyl_collect:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        self.emit("movq stack_base(%rip), %r12")
        self.emit("movq %rsp, %r13")
        self.emit("vyl_mark_scan:")
        self.emit("cmpq %r12, %r13")
        self.emit("jae vyl_mark_done_scan")
        self.emit("movq (%r13), %rdi")
        self.emit("call vyl_mark_ptr")
        self.emit("addq $8, %r13")
        self.emit("jmp vyl_mark_scan")
        self.emit("vyl_mark_done_scan:")
        self.emit("movq vyl_head(%rip), %rbx")
        self.emit("xor %rdi, %rdi")  # prev = 0
        self.emit("vyl_sweep_loop:")
        self.emit("cmpq $0, %rbx")
        self.emit("je vyl_sweep_done")
        self.emit("movq 16(%rbx), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("jne vyl_keep")
        self.emit("movq (%rbx), %rcx")   # next
        self.emit("cmpq $0, %rdi")
        self.emit("je vyl_sweep_update_head")
        self.emit("movq %rcx, (%rdi)")
        self.emit("jmp vyl_sweep_free")
        self.emit("vyl_sweep_update_head:")
        self.emit("movq %rcx, vyl_head(%rip)")
        self.emit("vyl_sweep_free:")
        self.emit("movq %rbx, %rdi")
        self.emit("call free")
        self.emit("movq %rcx, %rbx")
        self.emit("jmp vyl_sweep_loop")
        self.emit("vyl_keep:")
        self.emit("movq $0, 16(%rbx)")
        self.emit("movq %rbx, %rdi")
        self.emit("movq (%rbx), %rbx")
        self.emit("jmp vyl_sweep_loop")
        self.emit("vyl_sweep_done:")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # data
        self.emit(".section .data")
        self.emit("sha256_buf: .space 32")
        self.emit("sha256_hex: .space 65")
        self.emit("hex_table: .asciz \"0123456789abcdef\"")
        self.emit("tls_ctx: .quad 0")

        # File/dir helper strings
        self.emit(".fmt_mkdirp: .asciz \"mkdir -p %s\"")
        self.emit(".fmt_rmrf: .asciz \"rm -rf %s\"")
        self.emit(".fmt_unzip: .asciz \"unzip -o -q %s -d %s\"")

        # Switch back to text for networking helpers
        self.emit(".section .text")

        # Networking helpers
        self.emit(".globl vyl_tcp_connect")
        self.emit("vyl_tcp_connect:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        # 2 pushes = 16 bytes, rsp % 16 == 0 after these pushes
        # Need subq that keeps rsp % 16 == 0. 208 works (0 - 208 = -208, 208 % 16 = 0)
        self.emit("subq $208, %rsp")
        self.emit("movq %rdi, -24(%rbp)")  # host ptr
        self.emit("movq %rsi, -32(%rbp)")  # port int
        # build port string at -80..-65
        self.emit("leaq -80(%rbp), %rdi")
        self.emit("movq $16, %rsi")
        self.emit("leaq .fmt_port(%rip), %rdx")
        self.emit("movq -32(%rbp), %rcx")
        self.emit("movq $0, %rax")
        self.emit("call snprintf")
        # zero hints at -208..-96 (14 qwords)
        self.emit("leaq -216(%rbp), %rdi")
        self.emit("movq $0, %rax")
        self.emit("movq $0, %rcx")
        self.emit("movq $14, %rdx")
        self.emit("vyl_tcp_zero_hints:")
        self.emit("movq $0, (%rdi,%rcx,8)")
        self.emit("incq %rcx")
        self.emit("cmpq %rdx, %rcx")
        self.emit("jl vyl_tcp_zero_hints")
        # hints.ai_socktype = SOCK_STREAM(1)
        self.emit("movl $1, -208(%rbp)")
        # res pointer storage at -40
        self.emit("leaq -40(%rbp), %r9")
        self.emit("movq $0, -40(%rbp)")
        # call getaddrinfo(host, portstr, &hints, &res)
        self.emit("movq -24(%rbp), %rdi")
        self.emit("leaq -80(%rbp), %rsi")
        self.emit("leaq -216(%rbp), %rdx")
        self.emit("movq %r9, %rcx")
        self.emit("call getaddrinfo")
        self.emit("cmpq $0, %rax")
        self.emit("jne vyl_tcp_fail")
        self.emit("movq -40(%rbp), %rbx")
        self.emit("cmpq $0, %rbx")
        self.emit("je vyl_tcp_fail")
        # socket(res->ai_family, ai_socktype, ai_protocol)
        self.emit("movl 4(%rbx), %edi")
        self.emit("movl 8(%rbx), %esi")
        self.emit("movl 12(%rbx), %edx")
        self.emit("call socket")
        self.emit("movq %rax, %r12")
        self.emit("cmpq $0, %r12")
        self.emit("jl vyl_tcp_cleanup_fail")
        # connect(fd, res->ai_addr, res->ai_addrlen)
        self.emit("movq %r12, %rdi")
        self.emit("movq 24(%rbx), %rsi")
        self.emit("movl 16(%rbx), %edx")
        self.emit("call connect")
        self.emit("cmpq $0, %rax")
        self.emit("jne vyl_tcp_cleanup_fail")
        self.emit("movq -40(%rbp), %rdi")
        self.emit("call freeaddrinfo")
        self.emit("movq %r12, %rax")
        self.emit("addq $208, %rsp")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")
        self.emit("vyl_tcp_cleanup_fail:")
        self.emit("movq %r12, %rdi")
        self.emit("call close")
        self.emit("vyl_tcp_fail:")
        self.emit("movq -40(%rbp), %rdi")
        self.emit("cmpq $0, %rdi")
        self.emit("je vyl_tcp_fail_ret")
        self.emit("call freeaddrinfo")
        self.emit("vyl_tcp_fail_ret:")
        self.emit("movq $0, %rax")
        self.emit("addq $208, %rsp")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_tcp_send(fd, data)
        self.emit(".globl vyl_tcp_send")
        self.emit("vyl_tcp_send:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        # 2 pushes, rsp % 16 == 0. Need to keep aligned for calls.
        self.emit("subq $16, %rsp")
        self.emit("movq %rdi, %rbx")       # fd
        self.emit("movq %rsi, %r12")       # buf ptr
        self.emit("movq %rsi, %rdi")       # strlen(buf)
        self.emit("call strlen")
        self.emit("movq %rax, %rdx")       # length
        self.emit("movq %rbx, %rdi")       # send(fd, buf, len, 0)
        self.emit("movq %r12, %rsi")
        self.emit("movq $0, %rcx")
        self.emit("call send")
        self.emit("addq $16, %rsp")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_tcp_recv(fd, max)
        self.emit(".globl vyl_tcp_recv")
        self.emit("vyl_tcp_recv:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        self.emit("subq $8, %rsp")
        self.emit("movq %rdi, %rbx")       # fd
        self.emit("movq %rsi, %r12")       # max size
        self.emit("movq %r12, %rdi")
        self.emit("incq %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_tcp_recv_fail")
        self.emit("movq %rax, %r13")       # buf ptr
        self.emit("movq %rbx, %rdi")
        self.emit("movq %r13, %rsi")
        self.emit("movq %r12, %rdx")
        self.emit("movq $0, %rcx")
        self.emit("call recv")
        self.emit("cmpq $0, %rax")
        self.emit("jle vyl_tcp_recv_fail")
        self.emit("movq %rax, %rdx")
        self.emit("movb $0, (%r13,%rdx,1)")
        self.emit("movq %r13, %rax")
        self.emit("addq $8, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")
        self.emit("vyl_tcp_recv_fail:")
        self.emit("movq $0, %rax")
        self.emit("addq $8, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_tcp_resolve(host) -> string IPv4
        self.emit(".globl vyl_tcp_resolve")
        self.emit("vyl_tcp_resolve:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        # 2 pushes = 16 bytes, rsp % 16 == 0. Need subq that keeps aligned.
        # 112 works (0 - 112 = -112, 112 % 16 = 0)
        self.emit("subq $112, %rsp")
        self.emit("movq %rdi, -24(%rbp)")  # host
        # zero hints at -104..-24 (10 qwords)
        self.emit("leaq -104(%rbp), %rdi")
        self.emit("movq $0, %rax")
        self.emit("movq $10, %rcx")
        self.emit("vyl_tcp_resolve_zero:")
        self.emit("movq $0, (%rdi,%rax,8)")
        self.emit("incq %rax")
        self.emit("cmpq %rcx, %rax")
        self.emit("jl vyl_tcp_resolve_zero")
        # hints.family = AF_INET(2)
        self.emit("movl $2, -96(%rbp)")
        # res storage at -32
        self.emit("movq $0, -32(%rbp)")
        self.emit("movq -24(%rbp), %rdi")
        self.emit("movq $0, %rsi")
        self.emit("leaq -104(%rbp), %rdx")
        self.emit("leaq -32(%rbp), %rcx")
        self.emit("call getaddrinfo")
        self.emit("cmpq $0, %rax")
        self.emit("jne vyl_tcp_resolve_fail")
        self.emit("movq -32(%rbp), %rbx")
        self.emit("cmpq $0, %rbx")
        self.emit("je vyl_tcp_resolve_fail")
        # sockaddr_in starts at ai_addr
        self.emit("movq 24(%rbx), %rsi")
        self.emit("addq $4, %rsi")  # skip sin_family+port
        self.emit("movq $64, %rdx")
        self.emit("leaq -88(%rbp), %rdi")  # buffer for IP string
        self.emit("movl $2, %edi")         # AF_INET
        self.emit("call inet_ntop")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_tcp_resolve_fail")
        self.emit("movq %rax, %rdi")
        self.emit("call strlen")
        self.emit("incq %rax")
        self.emit("movq %rax, %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_tcp_resolve_fail")
        self.emit("movq %rax, %r12")
        self.emit("movq %r12, %rdi")
        self.emit("leaq -88(%rbp), %rsi")
        self.emit("call strcpy")
        self.emit("movq -32(%rbp), %rdi")
        self.emit("call freeaddrinfo")
        self.emit("movq %r12, %rax")
        self.emit("addq $112, %rsp")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")
        self.emit("vyl_tcp_resolve_fail:")
        self.emit("movq -32(%rbp), %rdi")
        self.emit("cmpq $0, %rdi")
        self.emit("je vyl_tcp_resolve_ret")
        self.emit("call freeaddrinfo")
        self.emit("vyl_tcp_resolve_ret:")
        self.emit("movq $0, %rax")
        self.emit("addq $112, %rsp")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        self.emit(".section .rodata")
        self.emit(".fmt_port: .asciz \"%d\"")
        self.emit(".empty_str: .asciz \"\"")
        self.emit(".section .text")

        # TLS helpers (OpenSSL)
        self.emit(".globl vyl_tls_ensure_ctx")
        self.emit("vyl_tls_ensure_ctx:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        # After push rbp, rsp % 16 == 0. Need to keep it that way for calls.
        # Subtracting 0 or 16 works. Use 16 for a bit of scratch.
        self.emit("subq $16, %rsp")
        self.emit("cmpq $0, tls_ctx(%rip)")
        self.emit("jne vyl_tls_ctx_done")
        self.emit("movq $0, %rdi")
        self.emit("movq $0, %rsi")
        self.emit("call OPENSSL_init_ssl")
        self.emit("call TLS_client_method")
        self.emit("movq %rax, %rdi")
        self.emit("call SSL_CTX_new")
        self.emit("movq %rax, tls_ctx(%rip)")
        self.emit("vyl_tls_ctx_done:")
        self.emit("addq $16, %rsp")
        self.emit("leave")
        self.emit("ret")

        self.emit(".globl vyl_tls_connect")
        self.emit("vyl_tls_connect:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        # 3 pushes = 24 bytes below rbp. rsp % 16 == 8.
        # Need subq $40 (24+40=64, still 8 mod 16) -> subq $40 gives 8-40%16=8-8=0 ✓
        self.emit("subq $40, %rsp")
        self.emit("movq %rdi, -32(%rbp)")   # host
        self.emit("movq %rsi, -40(%rbp)")   # port
        self.emit("call vyl_tls_ensure_ctx")
        self.emit("movq -32(%rbp), %rdi")
        self.emit("movq -40(%rbp), %rsi")
        self.emit("call vyl_tcp_connect")
        self.emit("movq %rax, %rbx")
        self.emit("cmpq $0, %rbx")
        self.emit("je vyl_tls_conn_fail")
        self.emit("movq tls_ctx(%rip), %rdi")
        self.emit("call SSL_new")
        self.emit("movq %rax, %r12")
        self.emit("cmpq $0, %r12")
        self.emit("je vyl_tls_conn_fail_close")
        self.emit("movq %r12, %rdi")
        self.emit("movq %rbx, %rsi")
        self.emit("call SSL_set_fd")
        self.emit("cmpq $0, %rax")
        self.emit("jle vyl_tls_conn_fail_ssl")
        # Set SNI hostname: SSL_ctrl(ssl, SSL_CTRL_SET_TLSEXT_HOSTNAME=55, TLSEXT_NAMETYPE_host_name=0, hostname)
        self.emit("movq %r12, %rdi")
        self.emit("movq $55, %rsi")         # SSL_CTRL_SET_TLSEXT_HOSTNAME
        self.emit("movq $0, %rdx")          # TLSEXT_NAMETYPE_host_name
        self.emit("movq -32(%rbp), %rcx")   # hostname
        self.emit("call SSL_ctrl")
        self.emit("movq %r12, %rdi")
        self.emit("call SSL_connect")
        self.emit("cmpq $0, %rax")
        self.emit("jle vyl_tls_conn_fail_ssl")
        self.emit("movq %r12, %rax")
        self.emit("addq $40, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")
        self.emit("vyl_tls_conn_fail_ssl:")
        self.emit("movq %r12, %rdi")
        self.emit("call SSL_free")
        self.emit("vyl_tls_conn_fail_close:")
        self.emit("movq %rbx, %rdi")
        self.emit("call close")
        self.emit("vyl_tls_conn_fail:")
        self.emit("movq $0, %rax")
        self.emit("addq $40, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        self.emit(".globl vyl_tls_send")
        self.emit("vyl_tls_send:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        # 2 pushes, rsp % 16 == 0. Keep aligned.
        self.emit("subq $16, %rsp")
        self.emit("movq %rdi, %rbx")       # ssl_ctx
        self.emit("movq %rsi, %r12")       # buf ptr
        self.emit("movq %rsi, %rdi")       # strlen(buf)
        self.emit("call strlen")
        self.emit("movq %rax, %rdx")       # length
        self.emit("movq %rbx, %rdi")       # SSL_write(ssl, buf, len)
        self.emit("movq %r12, %rsi")
        self.emit("call SSL_write")
        self.emit("addq $16, %rsp")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        self.emit(".globl vyl_tls_recv")
        self.emit("vyl_tls_recv:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        # 3 pushes, rsp % 16 == 8. Need subq $8 to align.
        self.emit("subq $8, %rsp")
        self.emit("movq %rdi, %rbx")
        self.emit("movq %rsi, %r12")
        self.emit("movq %r12, %rdi")
        self.emit("incq %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_tls_recv_fail")
        self.emit("movq %rax, %r13")
        self.emit("movq %rbx, %rdi")
        self.emit("movq %r13, %rsi")
        self.emit("movq %r12, %rdx")
        self.emit("call SSL_read")
        self.emit("cmpq $0, %rax")
        self.emit("jle vyl_tls_recv_fail")
        self.emit("movq %rax, %rdx")
        self.emit("movb $0, (%r13,%rdx,1)")
        self.emit("movq %r13, %rax")
        self.emit("addq $8, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")
        self.emit("vyl_tls_recv_fail:")
        self.emit("movq $0, %rax")
        self.emit("addq $8, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        self.emit(".globl vyl_tls_close")
        self.emit("vyl_tls_close:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("subq $8, %rsp")
        self.emit("movq %rdi, %rbx")       # save ssl ptr
        self.emit("movq %rbx, %rdi")
        self.emit("call SSL_get_fd")
        self.emit("movq %rax, %rdi")
        self.emit("call close")
        self.emit("movq %rbx, %rdi")
        self.emit("call SSL_free")
        self.emit("movq $0, %rax")
        self.emit("addq $8, %rsp")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_http_get(host, path, use_tls:int) -> string (body) or 0
        self.emit(".globl vyl_http_get")
        self.emit("vyl_http_get:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        # 3 pushes = 24 bytes. Locals at -32 and below. Need 128-byte buffer + 24 for vars + alignment
        self.emit("subq $168, %rsp")
        self.emit("movq %rdi, -32(%rbp)")   # host
        self.emit("movq %rsi, -40(%rbp)")   # path
        self.emit("movq %rdx, -48(%rbp)")   # use_tls

        # Build request into stack buffer (-176 to -49) and then heap copy
        self.emit("leaq -176(%rbp), %rdi")
        self.emit("movq $128, %rsi")
        self.emit("leaq .fmt_http_get(%rip), %rdx")
        self.emit("movq -40(%rbp), %rcx")
        self.emit("movq -32(%rbp), %r8")
        self.emit("movq $0, %rax")
        self.emit("call snprintf")
        self.emit("movq %rax, %r12")
        self.emit("incq %r12")
        self.emit("movq %r12, %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_fail")
        self.emit("movq %rax, %r13")
        self.emit("movq %r13, %rdi")
        self.emit("leaq -176(%rbp), %rsi")
        self.emit("call strcpy")

        # Connect
        self.emit("movq -32(%rbp), %rdi")
        self.emit("movq $80, %rsi")
        self.emit("movq -48(%rbp), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("jne vyl_http_tls_conn")
        self.emit("call vyl_tcp_connect")
        self.emit("jmp vyl_http_conn_done")
        self.emit("vyl_http_tls_conn:")
        self.emit("movq -32(%rbp), %rdi")   # host
        self.emit("movq $443, %rsi")        # port
        self.emit("call vyl_tls_connect")
        self.emit("vyl_http_conn_done:")
        self.emit("movq %rax, %rbx")
        self.emit("cmpq $0, %rbx")
        self.emit("je vyl_http_fail")

        # Send request
        self.emit("movq -48(%rbp), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_send_plain")
        self.emit("movq %rbx, %rdi")
        self.emit("movq %r13, %rsi")
        self.emit("call vyl_tls_send")
        self.emit("jmp vyl_http_after_send")
        self.emit("vyl_http_send_plain:")
        self.emit("movq %rbx, %rdi")
        self.emit("movq %r13, %rsi")
        self.emit("call vyl_tcp_send")
        self.emit("vyl_http_after_send:")

        # Receive (single chunk up to 65535)
        self.emit("movq $65535, %rsi")
        self.emit("movq -48(%rbp), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_recv_plain")
        self.emit("movq %rbx, %rdi")
        self.emit("call vyl_tls_recv")
        self.emit("jmp vyl_http_after_recv")
        self.emit("vyl_http_recv_plain:")
        self.emit("movq %rbx, %rdi")
        self.emit("call vyl_tcp_recv")
        self.emit("vyl_http_after_recv:")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_cleanup")
        self.emit("movq %rax, %r12")

        # Strip headers (


        self.emit("movq %r12, %rdi")
        self.emit("call strlen")
        self.emit("movq %rax, %rcx")
        self.emit("movq %r12, %rsi")
        self.emit("movq $0, %rdx")
        self.emit("vyl_http_scan:")
        self.emit("cmpq %rcx, %rdx")
        self.emit("jge vyl_http_no_headers")
        self.emit("movb (%rsi,%rdx,1), %al")
        self.emit("cmpb $13, %al")
        self.emit("jne vyl_http_next")
        self.emit("cmpq %rcx, %rdx")
        self.emit("addq $3, %rdx")
        self.emit("cmpq %rcx, %rdx")
        self.emit("jge vyl_http_next")
        self.emit("movb -3(%rsi,%rdx,1), %al")
        self.emit("cmpb $10, %al")
        self.emit("jne vyl_http_next")
        self.emit("movb -2(%rsi,%rdx,1), %al")
        self.emit("cmpb $13, %al")
        self.emit("jne vyl_http_next")
        self.emit("movb -1(%rsi,%rdx,1), %al")
        self.emit("cmpb $10, %al")
        self.emit("jne vyl_http_next")
        self.emit("addq $1, %rdx")
        self.emit("leaq (%rsi,%rdx,1), %rax")
        self.emit("movq %rax, %r12")
        self.emit("jmp vyl_http_done")
        self.emit("vyl_http_next:")
        self.emit("incq %rdx")
        self.emit("jmp vyl_http_scan")
        self.emit("vyl_http_no_headers:")
        self.emit("movq %rsi, %r12")
        self.emit("vyl_http_done:")
        self.emit("movq %r12, %rax")
        self.emit("jmp vyl_http_ret")

        self.emit("vyl_http_cleanup:")
        self.emit("movq $0, %rax")

        self.emit("vyl_http_ret:")
        self.emit("addq $168, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        self.emit("vyl_http_fail:")
        self.emit("movq $0, %rax")
        self.emit("addq $168, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        self.emit(".section .rodata")
        self.emit(".fmt_http_get: .asciz \"GET %s HTTP/1.0\\r\\nHost: %s\\r\\nUser-Agent: vyl/0.1\\r\\nConnection: close\\r\\n\\r\\n\"")
        self.emit(".http_loc: .asciz \"Location:\"")
        self.emit(".http_prefix: .asciz \"http://\"")
        self.emit(".https_prefix: .asciz \"https://\"")
        self.emit(".http_get_prefix: .asciz \"GET \"")
        self.emit(".http_get_mid: .asciz \" HTTP/1.0\\r\\nHost: \"")
        self.emit(".http_get_suffix: .asciz \"\\r\\nUser-Agent: vyl/0.1\\r\\nConnection: close\\r\\n\\r\\n\"")
        self.emit(".section .text")

        # vyl_http_download(host, path, use_tls, dest) -> int (0 fail, 1 success)
        self.emit(".globl vyl_http_download")
        self.emit("vyl_http_download:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        self.emit("push %r14")
        self.emit("push %r15")
        # 5 pushes = 40 bytes below rbp. After 5 pushes rsp % 16 == 8.
        # Need subq that makes rsp % 16 == 0 for proper call alignment.
        # 216 bytes: 8 + 216 = 224, 224 % 16 == 0
        self.emit("subq $216, %rsp")
        # Locals layout: -48(host), -56(path), -64(use_tls), -72(dest), -80(buf), -88(first_chunk), -96(redirect)
        self.emit("movq %rdi, -48(%rbp)")   # host
        self.emit("movq %rsi, -56(%rbp)")   # path
        self.emit("movq %rdx, -64(%rbp)")   # use_tls
        self.emit("movq %rcx, -72(%rbp)")   # dest path
        self.emit("movq $0, -96(%rbp)")     # redirect counter

        # Open dest file
        self.emit("movq -72(%rbp), %rdi")
        self.emit("leaq .mode_wb(%rip), %rsi")
        self.emit("call fopen")
        self.emit("movq %rax, %r14")
        self.emit("cmpq $0, %r14")
        self.emit("je vyl_http_dl_fail")

        self.emit("vyl_http_dl_start:")
        # limit redirects to 5
        self.emit("movq -96(%rbp), %rax")
        self.emit("cmpq $5, %rax")
        self.emit("jge vyl_http_dl_fail_close")

        # Build request string without varargs to avoid alignment issues
        self.emit("movq -48(%rbp), %rdi")   # host
        self.emit("call strlen")
        self.emit("movq %rax, %r12")       # len_host
        self.emit("movq -56(%rbp), %rdi")  # path
        self.emit("call strlen")
        self.emit("movq %rax, %r13")       # len_path
        self.emit("movq %r12, %rax")
        self.emit("addq %r13, %rax")
        self.emit("addq $66, %rax")        # constant parts + null
        self.emit("movq %rax, %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_fail_close")
        self.emit("movq %rax, %r13")       # req buffer
        # strcpy(req, "GET ")
        self.emit("movq %r13, %rdi")
        self.emit("leaq .http_get_prefix(%rip), %rsi")
        self.emit("call strcpy")
        # strcat(req, path)
        self.emit("movq %r13, %rdi")
        self.emit("movq -56(%rbp), %rsi")
        self.emit("call strcat")
        # strcat(req, " HTTP/1.0\\r\\nHost: ")
        self.emit("movq %r13, %rdi")
        self.emit("leaq .http_get_mid(%rip), %rsi")
        self.emit("call strcat")
        # strcat(req, host)
        self.emit("movq %r13, %rdi")
        self.emit("movq -48(%rbp), %rsi")
        self.emit("call strcat")
        # strcat(req, suffix)
        self.emit("movq %r13, %rdi")
        self.emit("leaq .http_get_suffix(%rip), %rsi")
        self.emit("call strcat")

        # Connect
        self.emit("movq -64(%rbp), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("jne vyl_http_dl_tls")
        self.emit("movq -48(%rbp), %rdi")
        self.emit("movq $80, %rsi")
        self.emit("call vyl_tcp_connect")
        self.emit("jmp vyl_http_dl_conn_done")
        self.emit("vyl_http_dl_tls:")
        self.emit("movq -48(%rbp), %rdi")
        self.emit("movq $443, %rsi")
        self.emit("call vyl_tls_connect")
        self.emit("vyl_http_dl_conn_done:")
        self.emit("movq %rax, %rbx")
        self.emit("cmpq $0, %rbx")
        self.emit("je vyl_http_dl_fail_close")

        # Send request
        self.emit("movq -64(%rbp), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_send_plain")
        self.emit("movq %rbx, %rdi")
        self.emit("movq %r13, %rsi")
        self.emit("call vyl_tls_send")
        self.emit("jmp vyl_http_dl_after_send")
        self.emit("vyl_http_dl_send_plain:")
        self.emit("movq %rbx, %rdi")
        self.emit("movq %r13, %rsi")
        self.emit("call vyl_tcp_send")
        self.emit("vyl_http_dl_after_send:")

        # recv loop - use 64KB buffer for faster downloads
        self.emit("movq $65536, %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_fail_conn")
        self.emit("movq %rax, -80(%rbp)")  # buf
        self.emit("movq $1, -88(%rbp)")     # first_chunk flag
        self.emit("vyl_http_dl_loop:")
        self.emit("movq -64(%rbp), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_plain_recv")
        self.emit("movq %rbx, %rdi")
        self.emit("movq -80(%rbp), %rsi")
        self.emit("movq $65535, %rdx")
        self.emit("call SSL_read")
        self.emit("jmp vyl_http_dl_after_recv")
        self.emit("vyl_http_dl_plain_recv:")
        self.emit("movq %rbx, %rdi")
        self.emit("movq -80(%rbp), %rsi")
        self.emit("movq $65535, %rdx")
        self.emit("movq $0, %rcx")
        self.emit("call recv")
        self.emit("vyl_http_dl_after_recv:")
        self.emit("cmpq $0, %rax")
        self.emit("jle vyl_http_dl_done")
        self.emit("movq %rax, %r12")
        # Null-terminate buffer at offset r12
        self.emit("movq -80(%rbp), %rdi")
        self.emit("movb $0, (%rdi,%r12,1)")

        # Load buffer pointer for write - needed for both first and subsequent chunks
        self.emit("movq -80(%rbp), %rsi")

        # handle redirects on first chunk (3xx with Location) or errors (4xx/5xx)
        self.emit("cmpq $0, -88(%rbp)")
        self.emit("je vyl_http_dl_write")
        self.emit("movq $0, -88(%rbp)")
        # %rsi already has buffer from above
        # Check HTTP status code at position 9 (after "HTTP/1.x ")
        # 2xx = success, 3xx = redirect, 4xx/5xx = error
        self.emit("movb 9(%rsi), %al")
        # Check for 4xx or 5xx errors
        self.emit("cmpb $'4', %al")
        self.emit("je vyl_http_dl_fail_conn")   # 4xx error
        self.emit("cmpb $'5', %al")
        self.emit("je vyl_http_dl_fail_conn")   # 5xx error
        # Check for 3xx redirect
        self.emit("cmpb $'3', %al")
        self.emit("jne vyl_http_dl_strip_headers")  # 2xx, go strip headers
        self.emit("movb 10(%rsi), %al")
        self.emit("cmpb $'0', %al")
        self.emit("jne vyl_http_dl_strip_headers")
        self.emit("movb 11(%rsi), %al")
        self.emit("cmpb $'1', %al")
        self.emit("je vyl_http_dl_redir")
        self.emit("cmpb $'2', %al")
        self.emit("je vyl_http_dl_redir")
        self.emit("cmpb $'7', %al")
        self.emit("je vyl_http_dl_redir")
        self.emit("cmpb $'8', %al")
        self.emit("jne vyl_http_dl_strip_headers")

        self.emit("vyl_http_dl_redir:")
        # find Location header
        self.emit("movq $0, %rdx")
        self.emit("movq %r12, %rcx")
        self.emit("vyl_http_dl_find_loc:")
        self.emit("cmpq %rcx, %rdx")
        self.emit("jge vyl_http_dl_strip_headers")
        self.emit("leaq (%rsi,%rdx,1), %rdi")
        self.emit("leaq .http_loc(%rip), %rsi")
        self.emit("movq $9, %rdx")
        self.emit("call strncmp")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_loc_found")
        self.emit("movq -80(%rbp), %rsi")
        self.emit("movq %rdx, %rax")
        self.emit("incq %rax")
        self.emit("movq %rax, %rdx")
        self.emit("jmp vyl_http_dl_find_loc")

        self.emit("vyl_http_dl_loc_found:")
        # rdi points to "Location:"; value starts at +10 (including space)
        self.emit("addq $10, %rdi")
        self.emit("movq %rdi, %r15")      # save location value ptr

        # detect scheme
        self.emit("movq %r15, %rdi")
        self.emit("leaq .https_prefix(%rip), %rsi")
        self.emit("movq $8, %rdx")
        self.emit("call strncmp")
        self.emit("cmpq $0, %rax")
        self.emit("jne vyl_http_dl_check_http")
        self.emit("movq $1, -64(%rbp)")    # use_tls=1
        self.emit("addq $8, %r15")         # skip https://
        self.emit("jmp vyl_http_dl_host_parsed")
        self.emit("vyl_http_dl_check_http:")
        self.emit("movq %r15, %rdi")
        self.emit("leaq .http_prefix(%rip), %rsi")
        self.emit("movq $7, %rdx")
        self.emit("call strncmp")
        self.emit("cmpq $0, %rax")
        self.emit("jne vyl_http_dl_relative")
        self.emit("movq $0, -64(%rbp)")    # use_tls=0
        self.emit("addq $7, %r15")         # skip http://
        self.emit("jmp vyl_http_dl_host_parsed")

        # relative redirect: host stays the same, path becomes location value
        self.emit("vyl_http_dl_relative:")
        self.emit("movq -48(%rbp), %rax")
        self.emit("movq %rax, %rdi")       # host stays
        self.emit("movq %r15, %rsi")       # path pointer
        self.emit("jmp vyl_http_dl_copy_host_path")

        # absolute redirect host parsed at r15 (start of host)
        self.emit("vyl_http_dl_host_parsed:")
        # find '/' separator to split host/path
        self.emit("movq %r15, %rdi")
        self.emit("movq $47, %rsi")
        self.emit("call strchr")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_strip_headers")
        self.emit("movq %rax, %rsi")       # rsi = path ptr
        self.emit("movb $0, (%rax)")       # null-terminate host in-place
        self.emit("movq %r15, %rdi")       # rdi = host ptr
        self.emit("movq %rsi, %r9")        # save path ptr

        self.emit("vyl_http_dl_copy_host_path:")
        # copy host
        self.emit("call strlen")
        self.emit("incq %rax")
        self.emit("movq %rax, %r12")
        self.emit("movq %rax, %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_strip_headers")
        self.emit("movq %rax, %r10")       # new host
        self.emit("movq %r10, %rdi")
        self.emit("movq %r15, %rsi")
        self.emit("call strcpy")
        # copy path
        self.emit("movq %r9, %rdi")
        self.emit("call strlen")
        self.emit("incq %rax")
        self.emit("movq %rax, %r12")
        self.emit("movq %rax, %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_strip_headers")
        self.emit("movq %rax, %r11")       # new path
        self.emit("movq %r11, %rdi")
        self.emit("movq %r9, %rsi")
        self.emit("call strcpy")

        # update host/path and restart request
        self.emit("movq %r10, -48(%rbp)")
        self.emit("movq %r11, -56(%rbp)")
        self.emit("incq -96(%rbp)")        # redirect++
        self.emit("movq %rbx, %rdi")
        self.emit("cmpq $0, -64(%rbp)")
        self.emit("jne vyl_http_dl_close_tls")
        self.emit("call close")
        self.emit("jmp vyl_http_dl_restart")
        self.emit("vyl_http_dl_close_tls:")
        self.emit("call vyl_tls_close")
        self.emit("vyl_http_dl_restart:")
        self.emit("movq $1, -88(%rbp)")
        self.emit("jmp vyl_http_dl_start")

        # strip headers on first chunk (fallback or non-redirect)
        # Look for \r\n\r\n sequence
        self.emit("vyl_http_dl_strip_headers:")
        self.emit("movq -80(%rbp), %rsi")
        self.emit("movq $0, %rdx")          # offset counter
        self.emit("movq %r12, %rcx")        # length
        self.emit("vyl_http_dl_scan:")
        self.emit("cmpq %rcx, %rdx")
        self.emit("jge vyl_http_dl_write")  # didn't find \r\n\r\n, write everything
        self.emit("movb (%rsi,%rdx,1), %al")
        self.emit("cmpb $13, %al")          # is it \r?
        self.emit("jne vyl_http_dl_scan_next")
        # Found \r at rdx. Check if next 3 bytes are \n\r\n
        self.emit("movq %rdx, %rax")
        self.emit("addq $3, %rax")
        self.emit("cmpq %rcx, %rax")
        self.emit("jge vyl_http_dl_scan_next")  # not enough bytes remaining
        self.emit("movb 1(%rsi,%rdx,1), %al")   # byte at rdx+1
        self.emit("cmpb $10, %al")              # == \n?
        self.emit("jne vyl_http_dl_scan_next")
        self.emit("movb 2(%rsi,%rdx,1), %al")   # byte at rdx+2
        self.emit("cmpb $13, %al")              # == \r?
        self.emit("jne vyl_http_dl_scan_next")
        self.emit("movb 3(%rsi,%rdx,1), %al")   # byte at rdx+3
        self.emit("cmpb $10, %al")              # == \n?
        self.emit("jne vyl_http_dl_scan_next")
        # Found \r\n\r\n! Body starts at rdx+4
        self.emit("addq $4, %rdx")
        self.emit("leaq (%rsi,%rdx,1), %rsi")  # rsi = body start
        self.emit("movq %rcx, %rax")
        self.emit("subq %rdx, %rax")
        self.emit("movq %rax, %r12")           # r12 = remaining body length
        self.emit("jmp vyl_http_dl_write")
        self.emit("vyl_http_dl_scan_next:")
        self.emit("incq %rdx")
        self.emit("jmp vyl_http_dl_scan")

        self.emit("vyl_http_dl_write:")
        self.emit("cmpq $0, %r12")
        self.emit("jle vyl_http_dl_loop")
        # fwrite(buf, 1, len, file)
        self.emit("movq %rsi, %rdi")
        self.emit("movq $1, %rsi")
        self.emit("movq %r12, %rdx")
        self.emit("movq %r14, %rcx")
        self.emit("call fwrite")
        self.emit("jmp vyl_http_dl_loop")

        self.emit("vyl_http_dl_done:")
        # Close the connection properly
        self.emit("movq -64(%rbp), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_done_plain")
        # TLS cleanup: call SSL_shutdown and SSL_free (rbx holds SSL*)
        self.emit("movq %rbx, %rdi")
        self.emit("call SSL_shutdown")
        self.emit("movq %rbx, %rdi")
        self.emit("call SSL_free")
        self.emit("jmp vyl_http_dl_done_fclose")
        self.emit("vyl_http_dl_done_plain:")
        # Plain socket: close fd (rbx holds socket fd)
        self.emit("movq %rbx, %rdi")
        self.emit("call close")
        self.emit("vyl_http_dl_done_fclose:")
        self.emit("movq %r14, %rdi")
        self.emit("call fclose")
        self.emit("movq $1, %rax")
        self.emit("jmp vyl_http_dl_ret")

        self.emit("vyl_http_dl_fail_conn:")
        # Check if TLS or plain
        self.emit("movq -64(%rbp), %rax")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_http_dl_fail_plain")
        # TLS cleanup
        self.emit("movq %rbx, %rdi")
        self.emit("call SSL_shutdown")
        self.emit("movq %rbx, %rdi")
        self.emit("call SSL_free")
        self.emit("jmp vyl_http_dl_fail_close")
        self.emit("vyl_http_dl_fail_plain:")
        self.emit("movq %rbx, %rdi")
        self.emit("call close")
        self.emit("vyl_http_dl_fail_close:")
        self.emit("cmpq $0, %r14")
        self.emit("je vyl_http_dl_fail")
        self.emit("movq %r14, %rdi")
        self.emit("call fclose")
        self.emit("vyl_http_dl_fail:")
        self.emit("movq $0, %rax")

        self.emit("vyl_http_dl_ret:")
        self.emit("addq $216, %rsp")
        self.emit("pop %r15")
        self.emit("pop %r14")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_mkdir_p(path) -> int (1 success, 0 fail)
        self.emit(".globl vyl_mkdir_p")
        self.emit("vyl_mkdir_p:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("subq $272, %rsp")  # 256-byte buffer + alignment (272 % 16 == 0)
        self.emit("movq %rdi, %rcx")               # rcx = path (format arg)
        self.emit("leaq -256(%rbp), %rdi")         # rdi = buffer
        self.emit("movq $256, %rsi")               # rsi = size
        self.emit("leaq .fmt_mkdirp(%rip), %rdx")  # rdx = format string
        self.emit("movq $0, %rax")
        self.emit("call snprintf")
        self.emit("leaq -256(%rbp), %rdi")
        self.emit("call system")
        self.emit("cmpq $0, %rax")
        self.emit("sete %al")
        self.emit("movzbq %al, %rax")
        self.emit("addq $272, %rsp")
        self.emit("leave")
        self.emit("ret")

        # vyl_remove_all(path) -> int (1 success, 0 fail)
        self.emit(".globl vyl_remove_all")
        self.emit("vyl_remove_all:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("subq $272, %rsp")               # 272 % 16 == 0, keeps alignment
        self.emit("movq %rdi, %rcx")               # rcx = path (format arg)
        self.emit("leaq -256(%rbp), %rdi")         # rdi = buffer
        self.emit("movq $256, %rsi")               # rsi = size
        self.emit("leaq .fmt_rmrf(%rip), %rdx")    # rdx = format string
        self.emit("movq $0, %rax")
        self.emit("call snprintf")
        self.emit("leaq -256(%rbp), %rdi")
        self.emit("call system")
        self.emit("cmpq $0, %rax")
        self.emit("sete %al")
        self.emit("movzbq %al, %rax")
        self.emit("addq $272, %rsp")
        self.emit("leave")
        self.emit("ret")

        # vyl_readdir(dir) -> string (entry name, or empty string if done)
        # Returns d_name field from struct dirent
        self.emit(".globl vyl_readdir")
        self.emit("vyl_readdir:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("subq $8, %rsp")  # Maintain 16-byte alignment (8 + 8 = 16)
        self.emit("movq %rdi, %rbx")  # Save dir handle
        self.emit("call readdir")     # Returns struct dirent*
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_readdir_done")
        # struct dirent has d_name at offset 19 (on x86-64 Linux)
        self.emit("addq $19, %rax")   # Point to d_name
        # Skip "." and ".." entries
        self.emit("movb (%rax), %cl")
        self.emit("cmpb $'.', %cl")
        self.emit("jne vyl_readdir_ret")
        self.emit("movb 1(%rax), %cl")
        self.emit("cmpb $0, %cl")
        self.emit("je vyl_readdir_next")  # "." entry
        self.emit("cmpb $'.', %cl")
        self.emit("jne vyl_readdir_ret")
        self.emit("movb 2(%rax), %cl")
        self.emit("cmpb $0, %cl")
        self.emit("jne vyl_readdir_ret")  # Not ".."
        self.emit("vyl_readdir_next:")
        self.emit("movq %rbx, %rdi")
        self.emit("call readdir")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_readdir_done")
        self.emit("addq $19, %rax")
        self.emit("jmp vyl_readdir_ret")
        self.emit("vyl_readdir_done:")
        self.emit("leaq .empty_str(%rip), %rax")
        self.emit("vyl_readdir_ret:")
        self.emit("addq $8, %rsp")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_unzip(zipPath, destDir) -> int (1 success, 0 fail)
        self.emit(".globl vyl_unzip")
        self.emit("vyl_unzip:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        # After 2 pushes, rsp = rbp - 16, rsp % 16 == 0
        # Need 512 byte buffer. 512 % 16 == 0, so just subq $512
        self.emit("subq $512, %rsp")
        self.emit("movq %rdi, %rbx")   # save zipPath
        self.emit("movq %rsi, %r12")   # save destDir
        # snprintf(buf, 512, "unzip -o -q %s -d %s", zipPath, destDir)
        # buffer is at rsp (which is rbp - 16 - 512 = rbp - 528)
        self.emit("movq %rsp, %rdi")
        self.emit("movq $512, %rsi")
        self.emit("leaq .fmt_unzip(%rip), %rdx")
        self.emit("movq %rbx, %rcx")   # zipPath
        self.emit("movq %r12, %r8")    # destDir
        self.emit("movq $0, %rax")
        self.emit("call snprintf")
        self.emit("movq %rsp, %rdi")
        self.emit("call system")
        self.emit("cmpq $0, %rax")
        self.emit("sete %al")
        self.emit("movzbq %al, %rax")
        self.emit("addq $512, %rsp")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_copy_file(src, dst) -> int (1 success, 0 fail)
        self.emit(".globl vyl_copy_file")
        self.emit("vyl_copy_file:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        self.emit("push %r14")
        self.emit("subq $4120, %rsp")  # 4096-byte buffer
        self.emit("movq %rdi, %r12")     # src path
        self.emit("movq %rsi, %r13")     # dst path
        # open src
        self.emit("movq %r12, %rdi")
        self.emit("leaq .mode_rb(%rip), %rsi")
        self.emit("call fopen")
        self.emit("movq %rax, %r12")     # src FILE*
        self.emit("cmpq $0, %r12")
        self.emit("je vyl_copy_fail")
        # open dst
        self.emit("movq %r13, %rdi")
        self.emit("leaq .mode_wb(%rip), %rsi")
        self.emit("call fopen")
        self.emit("movq %rax, %r13")     # dst FILE*
        self.emit("cmpq $0, %r13")
        self.emit("je vyl_copy_close_src")
        # buffer
        self.emit("leaq -4096(%rbp), %r14")
        self.emit("vyl_copy_loop:")
        self.emit("movq %r14, %rdi")
        self.emit("movq $1, %rsi")
        self.emit("movq $4096, %rdx")
        self.emit("movq %r12, %rcx")
        self.emit("call fread")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_copy_done")
        self.emit("movq %rax, %rbx")      # bytes read
        self.emit("movq %r14, %rdi")
        self.emit("movq $1, %rsi")
        self.emit("movq %rbx, %rdx")
        self.emit("movq %r13, %rcx")
        self.emit("call fwrite")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_copy_fail_close")
        self.emit("jmp vyl_copy_loop")
        self.emit("vyl_copy_done:")
        self.emit("movq %r12, %rdi")
        self.emit("call fclose")
        self.emit("movq %r13, %rdi")
        self.emit("call fclose")
        self.emit("movq $1, %rax")
        self.emit("jmp vyl_copy_ret")
        self.emit("vyl_copy_fail_close:")
        self.emit("movq %r13, %rdi")
        self.emit("call fclose")
        self.emit("vyl_copy_close_src:")
        self.emit("movq %r12, %rdi")
        self.emit("call fclose")
        self.emit("vyl_copy_fail:")
        self.emit("movq $0, %rax")
        self.emit("vyl_copy_ret:")
        self.emit("addq $4112, %rsp")
        self.emit("pop %r14")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_strconcat(s1, s2) -> new string s1+s2
        self.emit(".globl vyl_strconcat")
        self.emit("vyl_strconcat:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        self.emit("subq $8, %rsp")  # align to 16
        self.emit("movq %rdi, %r12")  # s1
        self.emit("movq %rsi, %r13")  # s2
        # len1 = strlen(s1)
        self.emit("call strlen")
        self.emit("movq %rax, %rbx")
        # len2 = strlen(s2)
        self.emit("movq %r13, %rdi")
        self.emit("call strlen")
        # allocate len1 + len2 + 1
        self.emit("addq %rbx, %rax")
        self.emit("addq $1, %rax")
        self.emit("movq %rax, %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_strconcat_fail")
        self.emit("movq %rax, %rbx")  # save result
        # strcpy(result, s1)
        self.emit("movq %rax, %rdi")
        self.emit("movq %r12, %rsi")
        self.emit("call strcpy")
        # strcat(result, s2)
        self.emit("movq %rbx, %rdi")
        self.emit("movq %r13, %rsi")
        self.emit("call strcat")
        self.emit("movq %rbx, %rax")
        self.emit("jmp vyl_strconcat_ret")
        self.emit("vyl_strconcat_fail:")
        self.emit("movq $0, %rax")
        self.emit("vyl_strconcat_ret:")
        self.emit("addq $8, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_strfind(haystack, needle) -> index or -1
        self.emit(".globl vyl_strfind")
        self.emit("vyl_strfind:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("subq $8, %rsp")
        self.emit("movq %rdi, %rbx")  # save haystack
        # strstr(haystack, needle)
        self.emit("call strstr")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_strfind_notfound")
        # found: return offset = result - haystack
        self.emit("subq %rbx, %rax")
        self.emit("jmp vyl_strfind_ret")
        self.emit("vyl_strfind_notfound:")
        self.emit("movq $-1, %rax")
        self.emit("vyl_strfind_ret:")
        self.emit("addq $8, %rsp")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

        # vyl_substring(str, start, len) -> new string
        self.emit(".globl vyl_substring")
        self.emit("vyl_substring:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("push %rbx")
        self.emit("push %r12")
        self.emit("push %r13")
        self.emit("subq $8, %rsp")
        self.emit("movq %rdi, %r12")  # str
        self.emit("movq %rsi, %r13")  # start
        self.emit("movq %rdx, %rbx")  # len
        # allocate len + 1
        self.emit("movq %rbx, %rdi")
        self.emit("addq $1, %rdi")
        self.emit("call vyl_alloc")
        self.emit("cmpq $0, %rax")
        self.emit("je vyl_substring_fail")
        self.emit("movq %rax, %rdi")  # dest
        # src = str + start
        self.emit("leaq (%r12,%r13,1), %rsi")
        self.emit("movq %rbx, %rdx")  # n
        self.emit("call memcpy")
        # null terminate
        self.emit("movb $0, (%rax,%rbx,1)")
        self.emit("jmp vyl_substring_ret")
        self.emit("vyl_substring_fail:")
        self.emit("movq $0, %rax")
        self.emit("vyl_substring_ret:")
        self.emit("addq $8, %rsp")
        self.emit("pop %r13")
        self.emit("pop %r12")
        self.emit("pop %rbx")
        self.emit("leave")
        self.emit("ret")

def generate_assembly(program: Program) -> str:
    generator = CodeGenerator()
    return generator.generate(program)
