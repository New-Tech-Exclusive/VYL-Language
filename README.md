# VYL Language

VYL is a high-performance, compiled language with Python-like readability and the raw speed of C. It is designed to be a modern, safe, and lightning-fast alternative to C for systems programming and computationally intensive tasks.

> "C is outdated and this could actually replace it. Please contribute."

## Key Features

- **Blazing Fast**: Advanced codegen and register promotion make VYL **2x faster** than unoptimized native C.
- **Smart Typing**: Supports explicit typing (`int`, `dec`, `string`, `bool`) and **implicit typing** (defaults to `int`).
- **Memory Safe**: Built-in protection against leaks and buffer overflows (ASAN integrated).
- **Clean Syntax**: No semi-colons*, no fluff. Python-inspired structure with `{}` blocks.
- **VS Code Support**: Semantic highlighting and custom file icons.

## Performance Benchmark

1,000,000,000 count loop:
- **VYL (v0.1.5)**: **0.19s** (**2x faster than C**)
- **C (unoptimized)**: 0.39s
- **Python**: 29.84s (VYL is ~150x faster)

## NOTICE

- VYL is *currently in development* and lacks many features, such as proper multi-file compilation, good error messages, and more.
- VYL is, and will always be, free and open source software. If you find VYL useful, please consider contributing to the project.
- Please don't do what every major company did to ASM and make a bunch of weird versions of it. VYL is language designed to be simple, fast, and easy to use.
- VYL is meant to be a direct replacement for C, I know languages like Rust, Zig, and C++ exist, but I find them hard to use, read, and learn.
- VYL is unstable*, don't expect it to just work. It's still in development and lacks many features. To make it stable, I need contributors.

## Syntax Overview

### Variables and Types
```vyl
var x = 10               // Implicit int
var int count = 1000      // Explicit int
var dec pi = 3.14159
var string s = "VYL"
var bool active = true
```

### Control Flow
```vyl
if (active) {
    Print("VYL is live")
}

while (count > 0) {
    count = count - 1
}
```

### Arrays
```vyl
var int[5] numbers
numbers[0] = 10
numbers[1] = 20
Print(numbers[0] + numbers[1]) // Prints 30
```

### Modules
```vyl
include "lib.vyl"      // Textual inclusion
import stdio          // Standard library, not always required
```

### Functions and Entry Point
```vyl
Main() {
    var dec start = Clock()
    // Code here...
    var dec end = Clock()
    Print("Time taken (seconds): ", end - start)
}
```

## Getting Started

### Prerequisites
- GCC (Possibly for linking, or VYL might be able to handle it, as the VYL linker is in progress, install it to build the compiler)
- Make (For compiling the compiler)

### Build the Compiler
```bash
#clone the repo
git clone https://github.com/New-Tech-Exclusive/VYL-Language.git
cd VYL-Language
cd vyl-compiler
make
```

### Use the Compiler
```bash
# Creating a symlink, I do this so its easier to run the latest compiler, I reccomend adding it to your PATH
mkdir -p ~/.local/bin
ln -s /full/path/to/VYL/executable ~/.local/bin/vyl

# Compile only (produces .vylo and .s)
vyl -c or --compile path/to/source.vyl
./path/to/source.vylo
```

## VS Code Extension
Install the pre-built [vyl-lang.vsix](file:///media/bentley/2TB/repos/vyl-lang/src/vyl-lang.vsix) located in the `src` directory to get full syntax highlighting.

## Contribute
VYL is a community-driven project. We aim to catch up to and eventually surpass C in features, safety, and ergonomics.

Please open an issue if you find a bug or have a feature request.

## License

GPL-2.0