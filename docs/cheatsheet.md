# VYL Language Cheatsheet

A quick reference guide for the VYL programming language.

## NOTICE

Not *Fully* up to date, This WILL change

## Types

| Type | Description | Example |
| :--- | :--- | :--- |
| **Integer** | 64-bit signed integer | `var int x = 10;` |
| **Decimal** | 64-bit floating point | `var dec pi = 3.14;` |
| **String** | Null-terminated string | `var string s = "Hello";` |
| **Boolean** | True or false value | `var bool active = true;` |
| **Struct** | User-defined data structure | `struct Point { var int x; }` |
| **Implicit** | Type inferred from expression | `var count = 0;` |

## Variable Declarations

```vyl
var [type] <name> = <expression>;
```
Example:
```vyl
var int score = 100;
var dec price = 19.99;
var string user = "Bentley";
var is_valid = true; // inferred as bool
```

## Structs

```vyl
struct <Name> {
    var <type> <field>;
    ...
}
```

## Control Flow

### If/Else/Elif
```vyl
if (condition) {
    // code
} elif (other_condition) {
    // code
} else {
    // code
}
```

### While Loop
```vyl
while (condition) {
    // code
}
```

### For Loop
```vyl
for i in 1..10 {
    // code
}
```

## Functions

```vyl
Function <name>(<params>) [-> <return_type>] {
    // code
    return <expression>;
}
```

## Built-in Functions

| Function | Return Type | Description |
| :--- | :--- | :--- |
| `Print(val)` | `void` | Prints value to standard output. |
| `Clock()` | `dec` | Returns current CPU time in seconds. |
| `SHA256(s)` | `string` | Returns SHA256 hash of string. |
| `Exists(p)` | `bool` | Returns true if path exists. |
| `Read(p)`   | `string` | Reads file content. |
| `Sys(cmd)` | `int` | Runs shell command. |

## Program Structure

VYL programs start at `Function Main(argc, argv)`.

```vyl
Function Main(argc, argv) {
    Print("Live from VYL");
    
    var start = Clock();
    // Process...
    var end = Clock();
    
    Print("Elapsed: ");
    Print(end - start);
}
```

## Special Syntax

- **Newlines**: Use `\n` inside strings for a literal newline character.
- **Comments**: Use `//` for single-line comments.
- **Semicolons**: Required after statements; omit for block headers.

## Optimization Tips
- VYL uses **Peephole Optimization** for `i = i + 1` (converted to a single `inc` instruction).
- Binary operations with integer literals (e.g., `x + 5`) avoid stack traffic.
- Loop structures are optimized to minimize branch overhead.
