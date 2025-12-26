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
    )


class CodegenError(Exception):
    """Raised when code generation fails."""


@dataclass
class Symbol:
    name: str
    typ: str
    is_global: bool
    offset: int  # stack offset for locals, unused for globals


class CodeGenerator:
    def __init__(self):
        self.output: List[str] = []
        self.label_counter = 0
        self.current_function: Optional[str] = None
        self.locals: Dict[str, Symbol] = {}
        self.globals: Dict[str, Symbol] = {}
        self.string_literals: List[Tuple[str, str]] = []

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
        return self.globals.get(name)

    def get_variable_location(self, symbol: Symbol) -> str:
        if symbol.is_global:
            return f"{symbol.name}(%rip)"
        return f"{symbol.offset}(%rbp)"

    # ---------- entry ----------
    def generate(self, program: Program) -> str:
        self.output = []
        self.string_literals = []
        self.locals = {}
        self.globals = {}
        self.label_counter = 0

        self.emit(".section .text")

        for stmt in program.statements:
            if isinstance(stmt, VarDecl):
                self.process_global_var(stmt)

        for stmt in program.statements:
            if isinstance(stmt, FunctionDef):
                self.generate_function(stmt)
            elif isinstance(stmt, VarDecl):
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

        return "\n".join(self.output)

    # ---------- globals ----------
    def process_global_var(self, decl: VarDecl):
        self.emit(".section .data")
        self.emit(f"{decl.name}:")
        if decl.value and isinstance(decl.value, Literal) and decl.value.literal_type != "string":
            self.emit(f".quad {decl.value.value}")
        else:
            self.emit(".quad 0")
        self.emit(".section .text")
        var_type = decl.var_type or "int"
        self.globals[decl.name] = Symbol(decl.name, var_type, True, 0)

    # ---------- functions ----------
    def generate_function(self, func: FunctionDef):
        self.current_function = func.name
        self.locals = {}

        self.emit(f".globl {func.name}")
        self.emit(f"{func.name}:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")

        decls = self.collect_var_decls(func.body) if func.body else []
        stack_bytes = len(decls) * 8
        if stack_bytes:
            stack_bytes = (stack_bytes + 15) & ~15
            self.emit(f"subq ${stack_bytes}, %rsp")
            offset = -stack_bytes
            for d in decls:
                var_type = d.var_type or "int"
                self.locals[d.name] = Symbol(d.name, var_type, False, offset)
                offset += 8

        if func.body:
            for stmt in func.body.statements:
                self.generate_statement(stmt)

        if func.name == "Main":
            self.emit("movq $0, %rax")
        self.emit("leave")
        self.emit("ret")
        self.current_function = None
        self.locals = {}

    def generate_main_stub(self):
        self.emit(".globl main")
        self.emit("main:")
        self.emit("push %rbp")
        self.emit("movq %rsp, %rbp")
        self.emit("movq %rdi, argc_store(%rip)")
        self.emit("movq %rsi, argv_store(%rip)")
        self.emit("movq %rbp, stack_base(%rip)")
        self.emit("call Main")
        self.emit("movq %rax, %rdi")
        self.emit("movq $60, %rax")
        self.emit("syscall")

    # ---------- statements ----------
    def generate_statement(self, stmt):
        if isinstance(stmt, Assignment):
            self.generate_assignment(stmt)
        elif isinstance(stmt, VarDecl):
            sym = self.get_variable_symbol(stmt.name)
            if not sym:
                raise CodegenError(f"Undefined local declaration for '{stmt.name}'")
            if stmt.value:
                self.generate_expression(stmt.value)
                self.emit(f"movq %rax, {self.get_variable_location(sym)}")
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
            self.generate_expression(stmt)

    def collect_var_decls(self, block: Block) -> List[VarDecl]:
        decls: List[VarDecl] = []
        for stmt in block.statements if block else []:
            if isinstance(stmt, VarDecl):
                decls.append(stmt)
            elif isinstance(stmt, Block):
                decls.extend(self.collect_var_decls(stmt))
            elif isinstance(stmt, IfStmt):
                decls.extend(self.collect_from_if(stmt))
            elif isinstance(stmt, WhileStmt):
                decls.extend(self.collect_var_decls(stmt.body))
            elif isinstance(stmt, ForStmt):
                if isinstance(stmt.init, VarDecl):
                    decls.append(stmt.init)
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

        if isinstance(expr, FunctionCall):
            self.generate_function_call(expr)
            return

        if isinstance(expr, UnaryExpr):
            self.generate_expression(expr.operand)
            if expr.operator == "-":
                self.emit("negq %rax")
            elif expr.operator in ("!", "NOT"):
                self.emit("cmpq $0, %rax")
                self.emit("sete %al")
                self.emit("movzbq %al, %rax")
            else:
                raise CodegenError(f"Unsupported unary operator '{expr.operator}'")
            return

        if isinstance(expr, BinaryExpr):
            def _is_stringish(node):
                if isinstance(node, Literal) and node.literal_type == "string":
                    return True
                if isinstance(node, FunctionCall) and node.name in ("GetArg", "Read", "SHA256"):
                    return True
                return False

            stringy = _is_stringish(expr.left) or _is_stringish(expr.right)

            if expr.operator == "+" and stringy:
                # string concatenation: malloc(len(a)+len(b)+1), strcpy, strcat
                self.generate_expression(expr.left)
                self.emit("push %rax")  # save left ptr
                self.generate_expression(expr.right)
                self.emit("movq %rax, %rbx")  # right ptr
                self.emit("pop %rdi")  # left ptr into rdi
                self.emit("push %rdi")  # save left for later
                self.emit("push %rbx")  # save right while strlen(left)
                self.emit("call strlen")
                self.emit("movq %rax, %r12")  # len_left
                self.emit("pop %rbx")  # restore right ptr
                self.emit("movq %rbx, %rdi")
                self.emit("call strlen")
                self.emit("addq %r12, %rax")
                self.emit("incq %rax")
                self.emit("movq %rax, %rdi")
                self.emit("call vyl_alloc")
                self.emit("movq %rax, %r13")  # dest
                # strcpy(dest, left)
                self.emit("movq %r13, %rdi")
                self.emit("pop %rsi")  # left ptr
                self.emit("call strcpy")
                # strcat(dest, right)
                self.emit("movq %r13, %rdi")
                self.emit("movq %rbx, %rsi")
                self.emit("call strcat")
                self.emit("movq %r13, %rax")
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
            elif op == "&&":
                self.emit("andq %rbx, %rax")
            elif op == "||":
                self.emit("orq %rbx, %rax")
            else:
                raise CodegenError(f"Unsupported binary operator '{op}'")
            return

        raise CodegenError(f"Unsupported expression type: {type(expr).__name__}")

    # ---------- assignments ----------
    def generate_assignment(self, assign: Assignment):
        self.generate_expression(assign.value)
        sym = self.get_variable_symbol(assign.name)
        if sym:
            self.emit(f"movq %rax, {self.get_variable_location(sym)}")
        elif self.current_function:
            offset = len(self.locals) * 8 + 8
            sym = Symbol(assign.name, "int", False, -offset)
            self.locals[assign.name] = sym
            self.emit(f"movq %rax, {-offset}(%rbp)")
        else:
            raise CodegenError(f"Undefined variable '{assign.name}'")

    # ---------- calls ----------
    def generate_function_call(self, call: FunctionCall):
        name = call.name
        if name == "Print":
            if call.arguments:
                arg = call.arguments[0]
                self.generate_expression(arg)
                stringy = isinstance(arg, Literal) and arg.literal_type == "string"
                if isinstance(arg, FunctionCall) and arg.name in ("GetArg", "Read", "SHA256"):
                    stringy = True
                self.emit("movq %rax, %rdi")
                self.emit("call print_string" if stringy else "call print_int")
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

        if name == "CreateFolder":
            if len(call.arguments) != 1:
                raise CodegenError("CreateFolder expects (path)")
            self.generate_expression(call.arguments[0])
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

        # generic call
        for arg in reversed(call.arguments):
            self.generate_expression(arg)
            self.emit("push %rax")
        self.emit(f"call {name}")
        if call.arguments:
            self.emit(f"addq ${len(call.arguments) * 8}, %rsp")

    # ---------- control flow ----------
    def generate_if(self, node: IfStmt):
        else_lbl = self.get_label("else")
        end_lbl = self.get_label("endif")
        self.generate_expression(node.condition)
        self.emit("cmpq $0, %rax")
        self.emit(f"je {else_lbl}")
        self.generate_statement(node.then_block)
        self.emit(f"jmp {end_lbl}")
        self.emit(f"{else_lbl}:")
        if node.else_block:
            self.generate_statement(node.else_block)
        self.emit(f"{end_lbl}:")

    def generate_while(self, node: WhileStmt):
        start_lbl = self.get_label("while")
        end_lbl = self.get_label("endwhile")
        self.emit(f"{start_lbl}:")
        self.generate_expression(node.condition)
        self.emit("cmpq $0, %rax")
        self.emit(f"je {end_lbl}")
        self.generate_statement(node.body)
        self.emit(f"jmp {start_lbl}")
        self.emit(f"{end_lbl}:")

    def generate_for(self, node: ForStmt):
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
        self.generate_statement(node.body)
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
        self.emit(".fmt_string: .asciz \"%s\\n\"")
        self.emit(".fmt_newline: .asciz \"\\n\"")
        self.emit("argc_store: .quad 0")
        self.emit("argv_store: .quad 0")
        self.emit(".mode_rb: .asciz \"rb\"")
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


def generate_assembly(program: Program) -> str:
    generator = CodeGenerator()
    return generator.generate(program)
