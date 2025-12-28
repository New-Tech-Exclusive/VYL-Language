# VYL Compiler

A Python-based compiler for the VYL language that emits x86-64 assembly and produces runnable ELF binaries by default.

## Highlights

- **Language**: variables with optional types, functions with typed params/returns, `if/elif/else`, `while`, `for`, arithmetic/comparison ops, string concatenation, and includes (`include/import "file.vyl"`).
- **Struct declarations**: `struct Point { var int x; var int y; }` are parsed/validated; runtime layout/codegen is currently a no-op (used as declarations only).
- **Built-ins**: `Print`, `Clock`, `Exists`, `CreateFolder`, `Open`, `Read`, `Write`, `Close`, `SHA256`, `Sys`, `Argc`, `GetArg`, `ReadFilesize`, `Input`, `GC`.
- **CLI**: `vyl -c file.vyl` builds an executable (`file.vylo` by default), `-S` for assembly-only, `-k` for flat `.bin` via Keystone, `-cm` Mach-O object, `-cpe` PE/COFF object.
- **Include preprocessor**: recursively inlines local `.vyl` files with cycle detection.

## Requirements

- Python 3.10+
- `gcc` (Linux) or `clang` for assembling/linking; `x86_64-w64-mingw32-gcc` or a PE-capable `clang` for `-cpe`
- OpenSSL libcrypto (for `SHA256` built-in)
- Optional: `keystone-engine` (`pip install keystone-engine`) when using `-k` to emit flat binaries

## Architecture

```
vyl/
├── __init__.py      # Package initialization
├── lexer.py         # Tokenization and lexical analysis
├── parser.py        # AST construction
├── codegen.py       # Assembly generation
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

- `Print(any)`
- `Clock()` → `int`
- `Exists(path: string)` → `bool`
- `CreateFolder(path: string)` → `int`
- `Open(path: string, mode: string)` → `int`
- `Read(path: string)` → `string`
- `Write(fd: int, data: string)` → `int`
- `Close(fd: int)` → `int`
- `ReadFilesize(path: string)` → `int`
- `SHA256(data: string)` → `string`
- `Sys(cmd: string)` → `int`
- `Argc()` → `int`, `GetArg(i: int)` → `string`
- `Input()` → `string`
- `GC()`

## Pipeline

1. Preprocess includes (cycle detection)
2. Tokenize
3. Parse (recursive descent)
4. Resolve and validate symbols
5. Type check
6. Generate assembly
7. Assemble/link (or flat binary with Keystone)

## Limitations / Notes

- Structs are accepted syntactically but have no generated layout or field access yet.
- No arrays, slices, or user-defined modules; includes inline files instead.
- Linking uses `-lcrypto` for SHA256 on ELF; ensure OpenSSL is present.

## License

MIT License
