# Philosophy

## The Problem with C

C has been the language of systems programming for 50 years. It's fast, portable, and close to the metal. But it's also dangerous: buffer overflows, null pointer dereferences, use-after-free bugs, and memory leaks have caused billions of dollars in security vulnerabilities.

Rust solves these problems but introduces significant complexity. Zig offers a middle ground but still has a steep learning curve. C++ bolts modern features onto an ancient foundation, creating a sprawling specification that no one fully understands.

## What VYL Offers

**VYL is C's successor for people who want safety without ceremony.**

We keep what makes C great:
- Direct compilation to native code (x86-64)
- Predictable performance with no hidden allocations
- Simple mental model: structs, functions, pointers
- Small language surface area

We add what C lacks:
- **Memory safety** without a garbage collector (planned: Option/Result types, null safety)
- **Modern syntax** that's readable and concise
- **Methods on structs** with a proper `self` keyword
- **Enums with values** for type-safe constants
- **Real strings** instead of null-terminated char arrays
- **Built-in networking** (TCP, TLS, HTTP) without linking nightmares
- **Package management** via VPM

## Design Principles

### 1. Simplicity Over Cleverness
If a feature requires a PhD to understand, it doesn't belong in VYL. The language should be learnable in a weekend. Code should be readable by anyone who knows basic programming.

### 2. Safety by Default
Null references are the "billion dollar mistake." VYL aims to eliminate entire classes of bugs at compile time:
- Non-nullable types by default
- Bounds-checked arrays
- Result types instead of error codes
- Explicit memory management without footguns

### 3. One Way to Do Things
Python says "there should be one obvious way to do it." VYL agrees. We don't provide five syntaxes for the same operation. This makes code consistent across projects and reduces cognitive load.

### 4. Batteries Included
The standard library should cover common needs:
- File I/O, processes, environment
- Networking (TCP, TLS, HTTP)
- Cryptography (SHA-256, hashing)
- VINFO, CSV, strings
- Date/time handling

You shouldn't need external dependencies for basic tasks.

### 5. Fast Compilation
The compiler should be fast enough that you never wait. Incremental compilation, parallel builds, and simple semantics keep compile times low.

### 6. Honest Abstractions
Every abstraction in VYL maps directly to machine concepts. There's no hidden virtual dispatch, no surprise heap allocations, no implicit copies. What you write is what runs.

## What VYL is Not

- **Not a research language** — We implement proven ideas, not experiments
- **Not maximally safe** — We trust programmers more than Rust does, we're the net, but you have the parachute.
- **Not garbage collected** — You manage memory, we help you do it safely
- **Not object-oriented** — Structs with methods, not class hierarchies
- **Not functional** — Imperative at heart, with functional conveniences

## Target Audience

VYL is for programmers who:
- Currently use C or Python but want safety and speed improvements
- Find Rust's learning curve too steep for their needs
- Want a simple language for CLI tools, systems utilities, and embedded work, and general purpose programming
- Value readable code over clever abstractions
- Need predictable performance

## The Path Forward

VYL is evolving toward these goals:

**Near-term:**
- Multiple return values and tuple unpacking
- Defer statements for resource cleanup
- For-each loops and iterators
- Match expressions with pattern matching

**Medium-term:**
- Generics for type-safe containers
- Interfaces/traits for polymorphism
- Closures and higher-order functions
- Async/await for concurrent I/O

**Long-term:**
- Borrow checking (optional, for maximum safety)
- WebAssembly target
- Full language server (LSP) for IDE support
- Self-hosted compiler

## Community

VYL is community-driven and versioned as a single language, not a fragmented ecosystem. There's one canonical toolchain that favors clarity, speed, and portability over ceremony.

We welcome contributions that align with these principles. If you're unsure whether a feature fits, ask: "Would this make VYL simpler and safer, or more complex and clever?"

Choose simple. Choose safe. Choose VYL.