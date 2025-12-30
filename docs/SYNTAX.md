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
- Structs are declarations only for now (no generated layout or field access).
- Arrays are heap-allocated int arrays via `Array(len)`; index with `arr[i]` and get length with `Length(arr)`. Indexing is null/bounds-checked and aborts on violation.

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

### If/Else/Elif Statement
```vyl
if (condition) {
    // Code to execute if true
} elif (other_condition) {
    // Checked if the first condition was false
} else {
    // Fallback branch
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
- `ReadFilesize(path: string) -> int`: File size in bytes.
- `Remove(path: string) -> int`: Remove a file.
- `MkdirP(path: string) -> int`: Create directories recursively (mkdir -p).
- `RemoveAll(path: string) -> int`: Recursively delete path (rm -rf).
- `CopyFile(src: string, dst: string) -> int`: Copy a file.
- `SHA256(data: string) -> string`: Compute SHA256 hash.
- `Sys(command: string) -> int`: Execute a system command.
- `GetArg(index: int) -> string`: Get command line argument.
- `Argc() -> int`: Get number of command line arguments.
- `Exit(code: int)`: Terminate process.
- `Input() -> string`: Read a line from stdin.
- `GC()`: Trigger the garbage collector.
- `Sleep(ms: int) -> int`: Sleep for milliseconds.
- `Clock() -> int`: Monotonic clock ticks.
- `Now() -> int`: Unix timestamp.
- `RandInt() -> int`: Random 64-bit int.

### Networking
- `TcpConnect(host: string, port: int) -> int`
- `TcpSend(fd: int, data: string) -> int`
- `TcpRecv(fd: int, max_bytes: int) -> string`
- `TcpClose(fd: int) -> int`
- `TcpResolve(host: string) -> string`
- `TlsConnect(host: string, port: int) -> int`
- `TlsSend(fd: int, data: string) -> int`
- `TlsRecv(fd: int, max_bytes: int) -> string`
- `TlsClose(fd: int) -> int`
- `HttpGet(host: string, path: string, use_tls: int) -> string`
- `HttpDownload(host: string, path: string, use_tls: int, dest: string) -> int`

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
Function Main(argc, argv) {
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

// Simple HTTP GET
Function Fetch() {
    var string body = HttpGet("example.com", "/", 0);
    Print(body);
}
```

## Language Limitations (v0.2.5)

- Structs are declarations only (no layout or field access in codegen yet).
- Arrays are int-only; indexing is null/bounds-checked and aborts on violation.
- Includes inline files; no modules/packages yet.
- Networking is blocking and IPv4-focused.
- No exception handling or operator overloading.

## Style Guide

- Use camelCase for variable names
- Use PascalCase for function names
- Indent with 4 spaces
- Use meaningful variable names
- Comment complex logic
