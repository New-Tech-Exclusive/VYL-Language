# Vyl Implementation Roadmap

This document outlines the current status and future direction of the Vyl programming language.

## 1. Milestones Achieved [DONE]

### Phase 1: Core Architecture
- [x] **Lexer/Parser**: Robust tokenization and AST generation for VYL syntax.
- [x] **Native CodeGen**: Direct emission of x86_64 assembly (Intel syntax).
- [x] **Type System**: Support for `int`, `dec`, `string`, and **`bool`** with **implicit typing**.

### Phase 2: Control Flow & Built-ins
- [x] **Logic**: `if`, `else`, and `while` loop implementation.
- [x] **Arithmetic**: Full support for signed integers and floating-point math (XMM).
- [x] **Built-ins**: `Print()` and `Clock()` for high-precision timing.

### Phase 3: Performance & Safety
- [x] **Optimization**:
  - [x] **Register Promotion**: Local variables promoted to CPU registers (v0.1.5).
  - [x] **Constant Folding**: Compile-time arithmetic evaluation.
  - [x] **Peephole optimization** and streamlined loop structures.
- [x] **Memory Safety**:
  - [x] Integrated AddressSanitizer (ASAN) and LeakSanitizer.
  - [x] Comprehensive AST and Token cleanup logic.
- [x] **Benchmarking**: **2x faster** than unoptimized native C (0.19s vs 0.39s for 1B count).

### Phase 4: Ecosystem
- [x] **VS Code Support**: Syntax highlighting via `.vsix` extension.
- [x] **Documentation**: Comprehensive README, Cheatsheet, and Walkthroughs.

---

## 2. In Progress [CURRENT]

### Phase 5: Enhanced Control Flow
- [ ] **For Loops**: Implement C-style and range-based `for` loops.
- [ ] **Switch/Case**: Add pattern matching or basic switch statements.

### Phase 6: Standard Library Expansion
- [ ] **File I/O**: `Open()`, `Read()`, `Write()` wrappers for syscalls.
- [ ] **String Manipulation**: `Len()`, `Concat()`, `Split()`.
- [ ] **Math Library**: `Sin`, `Cos`, `Sqrt`, etc.

---

## 3. Future Goals [PLANNED]

### Phase 7: Systems Programming
- [ ] **Structs/Classes**: Custom data types and basic OOP.
- [ ] **Pointers/References**: Explicit memory control for low-level tasks.
- [ ] **Inline Assembly**: Allow direct assembly injection for micro-optimizations.

### Phase 8: Advanced Tooling
- [ ] **vylpkg**: A simple package manager for community libraries.
- [ ] **LSP Support**: Language Server Protocol for completions and hover info.
- [ ] **vyld**: Dedicated linker to simplify the build process (removing GCC dependency).

### Phase 9: Language Evolution
- [ ] **OSdev integration**: Templates for writing bootloaders and kernels.
- [ ] **Cross-compilation**: ARM and RISC-V backends.
- [ ] **Concurrency**: Go-like routines or lightweight threading model.

---

## Long‑Term Vision
VYL aims to be the language C should have evolved into: predictable, fast, and readable. Our goal is to provide a viable alternative for kernel development, driver writing, and high-performance backend services without the syntax baggage of the 1970s.
