# VYL Language Syntax Reference

## Basic Syntax

### Comments
```vyl
// This is a single-line comment
```

### Variables
```vyl
var x = 10;                   // Integer
var price = 19.99;            // Decimal
var name = "John";            // String
var isActive = true;          // Boolean
```

Semicolons are required after statements except for control-flow block headers.

### Types
- `int` - Integer numbers
- `dec` - Decimal numbers
- `string` - String literals
- `bool` - Boolean values (true/false)

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

**Note:** Control flow statements (if, while, for) do not require semicolons after the closing brace, but statements inside the blocks do.

## Functions

### Function Definition
```vyl
MyFunction() {
    // Function body
}
```

### Function Call
```vyl
MyFunction();
```

### Main Function
Every VYL program needs a Main function as the entry point (validated before codegen):
```vyl
Main() {
    // Program starts here
}
```

## Built-in Functions

### Print
Prints values to stdout:
```vyl
Print("Hello, World!");
Print(42);
Print(x);
```

### Clock
Placeholder for timing functions:
```vyl
var time = Clock();
```

## Expression Examples

### Arithmetic Expressions
```vyl
var result = (10 + 5) * 2 - 3;
```

### Comparison Expressions
```vyl
if (x > 5) {
    Print("x is greater than 5");
}
```

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
