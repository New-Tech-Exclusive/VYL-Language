# VYL Compiler

A complete Python-based compiler for the VYL programming language that generates x86-64 assembly code.

## Features

### Language Features
- **Variables**: `var x = 10`, `var name = "John"`
- **Types**: `int`, `dec`, `string`, `bool`
- **Arithmetic**: `+`, `-`, `*`, `/`
- **Comparison**: `==`, `!=`, `<`, `>`, `<=`, `>=`
- **Control Flow**: `if/else`, `while`, `for`
- **Functions**: `Main() { ... }`, user-defined functions
- **Built-ins**: `Print()`, `Clock()`
- **Includes**: `include "other.vyl"` (or `import "other.vyl"`) to inline local files

### Compiler Features
- **Lexer**: Tokenizes source code with full error reporting
- **Parser**: Builds AST with proper operator precedence
- **Validator**: Semantic checks (entrypoint, identifiers, duplicates) before codegen
- **Include Preprocessor**: Recursively inlines local `.vyl` files (cycle-safe)
- **Codegen**: Generates x86-64 assembly with symbol tables and better diagnostics
- **CLI**: Command-line interface with multiple output options and targets

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

### Basic Compilation
```bash
python3 -m vyl.main program.vyl
```

### Generate Assembly Only
```bash
python3 -m vyl.main program.vyl -S
```
This path avoids invoking the system linker/assembler and is the most portable.

### Targeting Other Formats
- **Default ELF64 (Linux)**: `python3 -m vyl.main program.vyl`
- **Mach-O object (macOS)**: `python3 -m vyl.main program.vyl -cm` (requires `clang` with macOS target)
- **PE/COFF object (Windows)**: `python3 -m vyl.main program.vyl -cpe` (requires `x86_64-w64-mingw32-gcc` or a PE-capable `clang`)
- **Flat binary via Keystone**: `python3 -m vyl.main program.vyl -S -k` (writes `program.bin` if Keystone is installed)

For non-ELF targets the compiler emits assembly then assembles to an object file; linking against system libs should be done with a platform-appropriate toolchain.

### Specify Output File
```bash
python3 -m vyl.main program.vyl -o myprogram
```

## Example Program

```vyl
// Hello World in VYL
Main() {
    Print("Hello, World!");
}

// Variables and arithmetic
Main() {
    var x = 10;
    var y = 5;
    var result = x + y;
    Print(result);  // Prints: 15
}

// Control flow
Main() {
    var counter = 0;
    while (counter < 3) {
        Print(counter);
        counter = counter + 1;
    }
    
    for i in 1..5 {
        Print(i);
    }
}
```

**Important:** VYL requires semicolons at the end of statements (except for control flow blocks).

### Includes
Inline other local files with:
```vyl
include "utils.vyl";
```
Paths are resolved relative to the including file. Cyclic includes are rejected.

## Implementation Details

### Lexer
- Handles whitespace and comments
- Supports escape sequences in strings
- Distinguishes between integers and decimals
- Recognizes keywords and identifiers
- Tokenizes operators and punctuation

### Parser
- Recursive descent parser
- Operator precedence: comparisons > addition/subtraction > multiplication/division
- Handles all VYL language constructs
- Detailed error reporting with line/column info

### Code Generator
- Symbol table management (global/local scopes)
- Stack frame allocation for local variables
- Control flow with labels
- Built-in function implementations
- String literal management

### Built-in Functions
- `Print(val)`: Prints integers or strings (handles `GetArg`, `Read`, `SHA256` outputs as strings)
- `Clock()`: Placeholder timing function
- `Exists(path)`: Returns non-zero if file/folder exists
- `CreateFolder(path)`: Creates a directory (0755)
- `Open(path, mode)`: Opens a file (mode like `"r"`, `"rb"`, `"w"`, `"wb"`), returns FILE* handle
- `Read(file)`: Reads entire file into a null-terminated buffer
- `Write(file, data)`: Writes a null-terminated buffer to a file
- `Close(file)`: Closes an opened file
- `SHA256(data)`: Returns hex string of SHA-256 digest (uses OpenSSL libcrypto)
- `Argc()`: Returns process argc
- `GetArg(i)`: Returns argv[i] string pointer

## Testing

The compiler has been tested with:
- ✅ Basic "Hello, World!" program
- ✅ Variable declarations and assignments
- ✅ Arithmetic operations
- ✅ Comparison operators
- ✅ If/else statements
- ✅ While loops
- ✅ For loops
- ✅ Mixed control flow

## Compilation Pipeline

1. **Lexical Analysis**: Source → Tokens
2. **Parsing**: Tokens → AST
3. **Validation**: AST → Checked AST (fails fast on semantic issues)
4. **Code Generation**: AST → Assembly
5. **Assembly/Linking**: Assembly → Executable/Object (via platform toolchain)

## Requirements

- Keystone (optional) for generating flat binaries with `-k`

## Error Handling

The compiler provides clear error messages:
- Syntax errors with line/column information
- Validation errors for missing `Main`, duplicate symbols, or undefined identifiers
- Codegen errors (with line/column) for issues encountered during emission
- Tokenization errors for invalid characters

## Future Enhancements

- [ ] Function parameters
- [ ] Return values
- [ ] Arrays and structs
- [ ] Import system
- [ ] Optimization passes
- [ ] Debug information generation
- [ ] Multiple file compilation

## License

This is a demonstration compiler for educational purposes.
