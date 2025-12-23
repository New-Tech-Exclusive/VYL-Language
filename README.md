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

### Compiler Features
- **Lexer**: Tokenizes source code with full error reporting
- **Parser**: Builds AST with proper operator precedence
- **Codegen**: Generates x86-64 assembly with symbol tables
- **CLI**: Command-line interface with multiple output options

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
- `print_int`: Prints integer values
- `print_string`: Prints string literals
- `clock`: Placeholder for timing functions

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
3. **Code Generation**: AST → Assembly
4. **Assembly/Linking**: Assembly → Executable (via gcc)

## Requirements

- Python 3.6+
- GCC (for assembling/linking)

## Error Handling

The compiler provides clear error messages:
- Syntax errors with line/column information
- Name errors for undefined variables
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
