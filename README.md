# VYL Compiler

A Python-based compiler for the VYL language that emits x86-64 assembly and produces runnable ELF binaries by default.

## Highlights

- **Language**: variables with optional types, typed function params/returns, `if/elif/else`, `while`, `for`, arithmetic/comparison ops, string concatenation, includes (`include/import "file.vyl"`).
- **Struct declarations**: `struct Point { var int x; var int y; }` are parsed/validated; field layout and access remain declarative-only for now.
- **Built-ins**: filesystem/process primitives, timing/randomness, and a full networking stack: TCP, TLS, `HttpGet`, `HttpDownload` (streaming to disk).
- **CLI**: `vyl -c file.vyl` builds an executable (`file.vylo` by default), `-S` for assembly-only, `-k` for flat `.bin` via Keystone, `-cm` Mach-O object, `-cpe` PE/COFF object.
- **Include preprocessor**: recursively inlines local `.vyl` files with cycle detection.

## Requirements

- Python 3.10+
- `gcc` (Linux) or `clang` for assembling/linking; `x86_64-w64-mingw32-gcc` or a PE-capable `clang` for `-cpe`
- OpenSSL libssl/libcrypto (for TLS/HTTP download and `SHA256` built-ins)
- Optional: `keystone-engine` (`pip install keystone-engine`) when using `-k` to emit flat binaries

## Architecture

```
new-compiler/
├── lexer.py         # Tokenization and lexical analysis
├── parser.py        # AST construction
├── resolver.py      # Declaration-before-use and scopes
├── validator.py     # Semantic checks for identifiers
├── type_checker.py  # Minimal static typing for expressions/returns
├── codegen.py       # x86-64 assembly generation + runtime intrinsics
└── main.py          # CLI interface
```

## Usage

### Basic
```bash
vyl -c program.vyl
# emits program.vylo (ELF)
```

### Assembly only
```bash
vyl -c program.vyl -S
# emits program.s
```

### Other targets
- Mach-O object (macOS): `vyl -c program.vyl -cm`
- PE/COFF object (Windows): `vyl -c program.vyl -cpe`
- Flat binary via Keystone: `vyl -c program.vyl -S -k` (writes `program.bin`)

### Output naming
- Without `-o`, ELF builds emit `<base>.vylo` (so `main.vyl` → `main.vylo`).
- With `-S` and no `-o`, emits `<base>.s`.
- Use `-o name` to override.

### Includes
```vyl
include "utils.vyl";
```
Includes are resolved relative to the including file; cycles are rejected.

## Language Quick Reference

```vyl
Function add(a: int, b: int) -> int {
    return a + b;
}

struct BlobHeader {
    var string id;
    var string kind; // "blob" | "tree" | "commit" | "changeset"
}

Function Main(argc, argv) {
    var string msg = "Hello, VYL";
    Print(msg);
}
```

- Variables: `var x = 10;`, `var int n = 5;`
- Types: `int`, `dec`, `string`, `bool`; structs are declarations only
- Control flow: `if / elif / else`, `while`, `for i in 1..N`
- Semicolons: required after statements; not after block headers
- Strings: use `+` for concatenation; built-ins return strings where noted

## Built-in Functions

**IO & filesystem**
- `Print(any)`
- `Exists(path: string)` → `bool`
- `CreateFolder(path: string)` → `int`
- `Open(path: string, mode: string)` → `int`
- `Close(fd: int)` → `int`
- `Read(path: string)` → `string`
- `Write(fd: int, data: string)` → `int`
- `ReadFilesize(path: string)` → `int`
- `Remove(path: string)` → `int`

**Process & environment**
- `Argc()` → `int`
- `GetArg(i: int)` → `string`
- `Sys(cmd: string)` → `int`
- `Exit(code: int)`
- `Input()` → `string`
- `GC()`

**Time & randomness**
- `Clock()` → `int`
- `Sleep(ms: int)` → `int`
- `Now()` → `int` (Unix timestamp)
- `RandInt()` → `int`

**Crypto**
- `SHA256(data: string)` → `string`

**Arrays & math**
- `Array(len: int)` → `array` (int elements, length stored)
- `Length(arr: array)` → `int`
- `Sqrt(n: int)` → `int` (integer floor sqrt)

**Networking**
- `TcpConnect(host: string, port: int)` → `int`
- `TcpSend(fd: int, data: string)` → `int`
- `TcpRecv(fd: int, max_bytes: int)` → `string`
- `TcpClose(fd: int)` → `int`
- `TcpResolve(host: string)` → `string` (IPv4 dotted quad)
- `TlsConnect(host: string, port: int)` → `int`
- `TlsSend(fd: int, data: string)` → `int`
- `TlsRecv(fd: int, max_bytes: int)` → `string`
- `TlsClose(fd: int)` → `int`
- `HttpGet(host: string, path: string, use_tls: int)` → `string`
- `HttpDownload(host: string, path: string, use_tls: int, dest_path: string)` → `int`

## Pipeline

1. Preprocess includes (cycle detection)
2. Tokenize
3. Parse (recursive descent)
4. Resolve and validate symbols
5. Type check
6. Generate assembly
7. Assemble/link (or flat binary with Keystone)

## Limitations / Notes

- Structs are declarations only; no field storage or access in codegen yet.
- Arrays are int-only and bounds are unchecked.
- No slices or user-defined modules; includes inline files instead.
- Networking built-ins are blocking and assume IPv4 today.
- TLS/HTTP depend on OpenSSL (`libssl`/`libcrypto`).

## License

MIT License
