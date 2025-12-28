# VYL Language Syntax Reference

## Basic Syntax

### Comments
```vyl
// This is a single-line comment
```

### Variables
```vyl
var x = 10;                 // Integer (inferred)
var int count = 5;          // Explicitly typed integer
var dec price = 19.99;      // Decimal
var string name = "John";   // String
var bool isActive = true;   // Boolean
```

Semicolons are required at the end of statements. Control-flow headers and block openings (e.g., `if (...) {`, `while (...) {`, `for ... {`, `Function MyFunction() {`, `struct MyStruct {`) do not end with semicolons.

### Types
- Primitive kinds: `int`, `dec`, `string`, `bool`.
- Variable declarations use `var` with optional type annotation.
- Structs allow grouping data.

### Structs
```vyl
struct Point {
    var int x;
    var int y;
}
```
Structs are currently used for data organization and are handled by the parser and validator.

## Operators

### Arithmetic
- `+` Addition
- `-` Subtraction
- `*` Multiplication
- `/` Division

### Comparison
- `==` Equal to
- `!=` Not equal to
- `<` Less than
- `>` Greater than
- `<=` Less than or equal
- `>=` Greater than or equal

## Control Flow

### If/Else Statement
```vyl
if (condition) {
    // Code to execute if true
} else {
    // Code to execute if false
} elif {
    // Code to exectute if false, then check if something else is true
}
```

### While Loop
```vyl
while (condition) {
    // Loop body
}
```

### For Loop
```vyl
for i in 1..5 {
    // Loop body
    // i goes from 1 to 5 (inclusive)
}
```

**Note:** Control-flow blocks use braces. Statements inside blocks must end with semicolons.

## Functions

### Function Definition
```vyl
Function MyFunction(a: int, b: int) -> int {
    return a + b;
}
```
Functions can have typed parameters and return types.

### Function Call
```vyl
var result = MyFunction(10, 20);
```

### Main Function
Every VYL program needs a `Main` function as the entry point:
```vyl
Function Main(argc, argv) {
    // Program starts here
}
```
`Main` can optionally take `argc` and `argv`.

## Built-in Functions

### Print
Prints values to stdout:
```vyl
Print("Hello, World!");
Print(42);
var x = 10;
Print(x);
```

### File and System
- `Exists(path: string) -> bool`: Check if file exists.
- `CreateFolder(path: string) -> int`: Create a directory.
- `Open(path: string, mode: string) -> int`: Open a file (returns file descriptor).
- `Close(fd: int) -> int`: Close a file descriptor.
- `Read(path: string) -> string`: Read entire file content.
- `Write(fd: int, data: string) -> int`: Write string to file descriptor.
- `SHA256(data: string) -> string`: Compute SHA256 hash.
- `Sys(command: string) -> int`: Execute a system command.
- `GetArg(index: int) -> string`: Get command line argument.
- `Argc() -> int`: Get number of command line arguments.

### Complex Conditions
```vyl
if (x > 5) {
    // Nested conditions
    if (y < 10) {
        Print("Both conditions true");
    }
}
```

## Complete Example

```vyl
// Calculate factorial
Main() {
    var n = 5;
    var result = 1;
    var i = 1;
    
    while (i <= n) {
        result = result * i;
        i = i + 1;
    }
    
    Print("Factorial of");
    Print(n);
    Print("is");
    Print(result);
}
```

## Language Limitations (Current Version)

- No function parameters
- No return values
- No arrays or structs
- No import system
- No operator overloading
- No exception handling

## Style Guide

- Use camelCase for variable names
- Use PascalCase for function names
- Indent with 4 spaces
- Use meaningful variable names
- Comment complex logic
