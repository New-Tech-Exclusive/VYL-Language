# VYL Modules Registry

This is the official package registry for VYL.

## Available Packages

- **hello** - A simple hello world module
- **http** - HTTP download utilities  
- **strings** - String manipulation utilities

## Installing Packages

```bash
vpm install <package-name>
```

## Using Packages

```vyl
import "hello"

Function Main() -> int {
    SayHello();
    return 0;
}
```

## Contributing

To add a package:
1. Fork this repository
2. Create a folder with your package name
3. Add `mod.vyl` (code) and `mod.vinfo` (metadata)
4. Submit a pull request
