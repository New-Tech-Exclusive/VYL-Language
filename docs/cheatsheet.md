# VYL Language Cheatsheet

A quick reference guide for the VYL programming language.

## NOTICE

Not *Fully* up to date, This WILL change

## Types

| Type | Keyword | Description | Example |
| :--- | :--- | :--- | :--- |
| **Integer** | `int` | 64-bit signed integer | `var int x = 10` |
| **Decimal** | `dec` | 64-bit floating point | `var dec pi = 3.14` |
| **String** | `string` | Null-terminated string | `var string s = "Hello"` |
| **Boolean** | `bool` | True or false value | `var bool active = true` |
| **Implicit** | (none) | Type inferred, defaults to `int` | `var count = 0` |

## Variable Declarations

```vyl
var <type> <name> = <expression>
```
Example:
```vyl
var int score = 100
var dec price = 19.99
var string user = "Bentley"
```

## Control Flow

### If/Else
```vyl
if (condition) {
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

## Built-in Functions

| Function | Return Type | Description |
| :--- | :--- | :--- |
| `Print(val)` | `void` | Prints value to standard output. |
| `Clock()` | `dec` | Returns current CPU time in seconds. |

## Program Structure

VYL programs start at `Main()`. Omit it and the compiler will fail validation.

```vyl
import stdio

Main() {
    Print("Live from VYL")
    
    var dec start = Clock()
    // Process...
    var dec end = Clock()
    
    Print("Elapsed: ")
    Print(end - start)
}
```

## Special Syntax

- **Newlines**: Use `/n` inside strings for a literal newline character.
- **Comments**: Use `//` for single-line comments.
- **Semicolons**: Required after statements; omit them for blocks (`if/while/for` bodies).

## Optimization Tips
- VYL uses **Peephole Optimization** for `i = i + 1` (converted to a single `inc` instruction).
- Binary operations with integer literals (e.g., `x + 5`) avoid stack traffic.
- Loop structures are optimized to minimize branch overhead.
