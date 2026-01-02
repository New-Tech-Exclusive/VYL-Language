# VYL Standard Library

This directory contains the VYL standard library, a collection of reusable modules providing common functionality.

## Modules

### collections.vyl
Generic data structures:
- `List<T>` - Dynamic array with automatic growth
- `Map<K, V>` - Hash map using chaining

**Note:** Full generic support is still under development. Current implementations serve as templates and require type-specific instantiation.

### io.vyl
File I/O and filesystem operations:
- `File` - File handle wrapper with read/write operations
- `Directory` - Directory listing
- `readFile()`, `writeFile()` - Convenience functions
- `fileExists()`, `createDirectory()`, `removeFile()`, etc.

### strings.vyl
String manipulation utilities:
- `StringBuilder` - Efficient string concatenation
- `startsWith()`, `endsWith()`, `contains()`
- `trim()`, `split()`, `join()`, `replace()`

### math.vyl
Mathematical functions:
- `abs()`, `min()`, `max()`, `clamp()`
- `pow()`, `factorial()`, `gcd()`, `lcm()`
- `isPrime()`, `isqrt()` - Integer square root

## Usage

To use the standard library in your VYL programs:

```vyl
// Import specific modules (when import system is implemented)
// import std.io;
// import std.collections;

// For now, use the modules directly by including them in your project
```

## Implementation Status

✅ **Completed:**
- Basic file I/O wrappers
- String utilities
- Math functions
- Directory operations with native OpenDir/ReadDir/CloseDir

🔄 **In Progress:**
- Generic type system (parser support added)
- Interface system (parser support added)
- Type checking for generics

📋 **Planned:**
- Module import system
- Memory management with `defer`
- More efficient generic instantiation
- HTTP client utilities
- JSON parsing
- Date/time utilities

## Design Philosophy

The VYL standard library aims to provide:
1. **Zero external dependencies** - Pure VYL implementations using only compiler builtins
2. **C-level performance** - Direct syscalls and minimal overhead
3. **Modern ergonomics** - Generics, interfaces, and functional patterns
4. **Small binaries** - Link only what you use

## Contributing

When adding new standard library modules:
- Use only VYL language features and compiler builtins
- Provide comprehensive examples in comments
- Follow naming conventions: `camelCase` for functions, `PascalCase` for types
- Document all public APIs
