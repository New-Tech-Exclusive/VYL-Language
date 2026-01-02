# VYL Language TODO

## Completed ✅
- [x] Structs with field access
- [x] Struct initialization syntax (`new Point{x: 5, y: 10}`)
- [x] Array literals (`[1, 2, 3]`)
- [x] Typed arrays (`int[]`, `string[]`)
- [x] Enums with explicit values
- [x] Struct methods with `self`
- [x] Pointers and references (`&`, `*`, `*int`)
- [x] Multiple return values / tuples - `Function divmod(a, b) -> (int, int)` with `var q, r = divmod(17, 5)`

---

## High Priority - Beat C

### Memory Safety & Error Handling
- [ ] **Option type** - `Option<T>` with `Some(value)` and `None` (no null crashes)
- [ ] **Result type** - `Result<T, E>` with `Ok(value)` and `Err(error)` (no error codes)
- [ ] **Null safety** - Compile-time null checks, non-nullable by default
- [ ] **Bounds checking** - Already have runtime checks, add compile-time where possible

### Control Flow
- [ ] **Defer statement** - `defer Close(fd);` for guaranteed cleanup
- [ ] **Match expression** - Pattern matching with exhaustiveness checking
- [ ] **Guard clauses** - `if condition else return;` or similar

### Type System
- [ ] **Generics** - `Struct List<T>`, `Function map<T, U>(arr: T[], fn: T -> U) -> U[]`
- [ ] **Type inference** - Infer types from context, reduce annotations
- [ ] **Type aliases** - `type UserId = int;`
- [ ] **Union types** - `int | string` for flexible typing
- [ ] **Const generics** - `Array<int, 10>` for fixed-size arrays

### Iteration & Collections
- [ ] **For-each loops** - `for item in array { }` and `for i, item in array { }`
- [ ] **Range expressions** - `0..10`, `0..=10`, `0..<10`
- [ ] **Iterators** - Lazy evaluation with `.map()`, `.filter()`, `.reduce()`
- [ ] **Slices** - Views into arrays without copying
- [ ] **Maps/Dictionaries** - `Map<string, int>` built-in

---

## Medium Priority - Developer Experience

### Functions & Closures
- [ ] **Closures/Lambdas** - `(x) => x * 2` or `|x| x * 2`
- [ ] **Higher-order functions** - Functions as first-class values
- [ ] **Default parameters** - `Function greet(name: string = "World")`
- [ ] **Named parameters** - `greet(name: "Alice", times: 3)`
- [ ] **Variadic functions** - `Function printf(fmt: string, args: ...any)`

### OOP & Polymorphism
- [ ] **Interfaces/Traits** - `Interface Printable { Function toString() -> string; }`
- [ ] **Operator overloading** - `operator +(other: Vec2) -> Vec2`
- [ ] **Static methods** - `Point.origin()` without instance
- [ ] **Associated constants** - `Point.ZERO`
- [ ] **Extension methods** - Add methods to existing types

### String Handling
- [ ] **String interpolation** - `"Hello, {name}!"` or `f"Value: {x}"`
- [ ] **Raw strings** - `r"no\escape\needed"` for regex, paths
- [ ] **Multi-line strings** - Triple quotes or heredoc
- [ ] **String methods** - `.split()`, `.trim()`, `.replace()`, `.contains()`
- [ ] **Character type** - `char` distinct from `string`

### Error Handling
- [ ] **Try expression** - `var result = try riskyOperation();`
- [ ] **Error propagation** - `?` operator like Rust
- [ ] **Panic/recover** - For unrecoverable errors
- [ ] **Stack traces** - Useful error messages with line numbers

---

## Lower Priority - Production Ready

### Concurrency
- [ ] **Async/await** - `async Function fetch()`, `var data = await fetch();`
- [ ] **Spawn/goroutines** - `spawn doWork();` lightweight threads
- [ ] **Channels** - `chan<int>` for safe communication
- [ ] **Mutex/locks** - `sync.Mutex` for shared state
- [ ] **Atomics** - Lock-free primitives

### Module System
- [ ] **Packages** - Proper module organization
- [ ] **Public/private** - `pub Function` for visibility control
- [ ] **Imports** - `import std.io;` or `from std.io import read, write;`
- [ ] **Namespaces** - Avoid naming collisions
- [ ] **Dependency management** - Integrate with VPM properly

### Memory Management
- [ ] **RAII/destructors** - Automatic cleanup when scope ends
- [ ] **Move semantics** - Transfer ownership without copying
- [ ] **Borrow checker** - Compile-time memory safety (Rust-style)
- [ ] **Custom allocators** - Arena, pool allocators
- [ ] **Weak references** - Break reference cycles

### Compile-Time Features
- [ ] **Const evaluation** - Compute values at compile time
- [ ] **Comptime functions** - Functions that run at compile time
- [ ] **Macros** - Code generation/metaprogramming
- [ ] **Conditional compilation** - `#[cfg(target_os = "linux")]`
- [ ] **Static assertions** - `static_assert(sizeof(int) == 8)`

---

## Standard Library

### Core
- [ ] **fmt** - Formatting and printing
- [ ] **io** - File I/O, buffered readers/writers
- [ ] **os** - Environment, process, signals
- [ ] **math** - Trig, exp, log, random
- [ ] **time** - Duration, timestamps, formatting

### Collections
- [ ] **list** - Dynamic array
- [ ] **map** - Hash map
- [ ] **set** - Hash set
- [ ] **queue** - FIFO queue
- [ ] **heap** - Priority queue

### Text
- [ ] **strings** - Manipulation, builders
- [ ] **regex** - Regular expressions
- [ ] **unicode** - UTF-8 handling
- [ ] **json** - Parse and serialize
- [ ] **csv** - Parse and serialize

### Network
- [ ] **http** - Client and server
- [ ] **websocket** - Real-time communication
- [ ] **tcp/udp** - Raw sockets
- [ ] **dns** - Lookup and resolution

### Crypto
- [ ] **hash** - SHA, MD5, Blake
- [ ] **cipher** - AES, ChaCha
- [ ] **rand** - Cryptographic RNG
- [ ] **tls** - Already have basics

---

## Tooling

### Compiler
- [ ] **Better error messages** - Show context, suggest fixes
- [ ] **Warnings** - Unused variables, unreachable code
- [ ] **Optimization levels** - -O0, -O1, -O2, -O3
- [ ] **Debug info** - DWARF for GDB/LLDB
- [ ] **Cross-compilation** - Easy targeting of other platforms

### Developer Tools
- [ ] **Language server (LSP)** - Autocomplete, go-to-definition
- [ ] **Formatter** - `vyl fmt`
- [ ] **Linter** - `vyl lint`
- [ ] **Documentation generator** - `vyl doc`
- [ ] **REPL** - Interactive shell
- [ ] **Test framework** - `vyl test` with assertions
- [ ] **Benchmark framework** - `vyl bench`
- [ ] **Debugger integration** - Step through code

### Build System
- [ ] **Build scripts** - `vyl.toml` configuration
- [ ] **Caching** - Incremental compilation
- [ ] **Parallel compilation** - Use multiple cores
- [ ] **Hot reload** - For development

---

## Platform Support

### Targets
- [x] Linux x86-64 (ELF)
- [ ] macOS x86-64 (Mach-O) - assembly only currently
- [ ] Windows x86-64 (PE) - assembly only currently
- [ ] Linux ARM64
- [ ] macOS ARM64 (Apple Silicon)
- [ ] WebAssembly
- [ ] Embedded (no_std)

### FFI
- [ ] **C interop** - Call C functions, use C headers
- [ ] **Expose to C** - Generate C headers for VYL libs
- [ ] **Dynamic loading** - dlopen/LoadLibrary

---

## Immediate Next Steps

1. **Multiple return values** - Easy win, enables Result/Option
2. **Defer** - Simple, prevents resource leaks
3. **For-each loops** - Makes arrays usable
4. **Match expression** - Better than if/elif chains
5. **String interpolation** - Quality of life
6. **Generics** - Needed for proper containers