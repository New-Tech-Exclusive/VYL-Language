#!/usr/bin/env python3

"""
VYL Compiler - Command Line Interface

This module provides the command-line interface for the VYL compiler.
It handles:
- Command-line argument parsing
- File I/O
- Compilation pipeline orchestration
- Error reporting
- Assembly generation and linking

Usage:
    python -m vyl.main input.vyl -o output
    python -m vyl.main input.vyl -S          # Generate assembly only
    python -m vyl.main input.vyl             # Compile to a.out
"""

import sys
import os
import subprocess
import argparse
import shutil
import re
from pathlib import Path

# Handle both module and standalone execution
try:
    from .lexer import tokenize
    from .parser import parse
    from .resolver import resolve_program
    from .type_checker import type_check
    from .validator import validate_program, ValidationError
    from .codegen import generate_assembly, CodegenError
except ImportError:
    # Running as standalone script
    if __name__ == '__main__' and __package__ is None:
        import sys
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from lexer import tokenize
        from parser import parse
        from resolver import resolve_program
        from type_checker import type_check
        from validator import validate_program, ValidationError
        from codegen import generate_assembly, CodegenError
    else:
        raise


INCLUDE_PATTERN = re.compile(r'^\s*(include|import)\s+"([^"]+)"\s*;?\s*$')


def preprocess_includes(source_code: str, base_dir: Path, seen: set[Path]) -> str:
    """Recursively inline local .vyl files referenced by include/import directives."""
    result = []
    for line in source_code.splitlines():
        match = INCLUDE_PATTERN.match(line)
        if match:
            rel_path = match.group(2)
            include_path = (base_dir / rel_path).resolve()
            if include_path in seen:
                raise SyntaxError(f"Cyclic include detected at {include_path}")
            if not include_path.exists():
                raise FileNotFoundError(f"Include not found: {include_path}")
            seen.add(include_path)
            included_text = include_path.read_text()
            result.append(f"// begin include {rel_path}")
            result.append(preprocess_includes(included_text, include_path.parent, seen))
            result.append(f"// end include {rel_path}")
            continue
        result.append(line)
    return "\n".join(result) + "\n"


def assemble_with_keystone(assembly: str):
    """Assemble AT&T x86_64 assembly to machine code using Keystone."""
    try:
        from keystone import Ks, KS_ARCH_X86, KS_MODE_64, KS_OPT_SYNTAX_ATT
    except ImportError:
        raise ImportError("keystone-engine not installed; install with 'pip install keystone-engine'")

    ks = Ks(KS_ARCH_X86, KS_MODE_64)
    ks.syntax = KS_OPT_SYNTAX_ATT
    encoding, _ = ks.asm(assembly)
    return bytes(encoding)


def compile_vyl(source_code: str, output_file: str, generate_assembly_only: bool = False, target: str = "elf", source_path: str | None = None, use_keystone: bool = False) -> bool:
    """
    Compile VYL source code to assembly, object, executable, or flat binary.
    
    Args:
        source_code: VYL source code as string (may contain include/import directives)
        output_file: Output file path (base name; .s/.o/.obj/.bin appended as needed)
        generate_assembly_only: If True, stop after writing assembly
        target: 'elf' (default executable), 'mach' (Mach-O object), or 'pe' (PE/COFF object)
        source_path: Optional path of the source file to resolve relative includes
        use_keystone: If True, assemble to a flat .bin using Keystone in addition to normal outputs
    
    Returns:
        True if compilation succeeded, False otherwise
    """
    try:
        # Step 0: Resolve includes
        base_dir = Path(source_path).resolve().parent if source_path else Path.cwd()
        print("Step 0: Resolving includes...")
        source_code_expanded = preprocess_includes(source_code, base_dir, set())

        # Step 1: Lexical analysis
        print("Step 1: Tokenizing...")
        tokens = tokenize(source_code_expanded)
        print(f"  Generated {len(tokens)} tokens")
        
        # Step 2: Parsing
        print("Step 2: Parsing...")
        ast = parse(tokens)
        print("  AST generated successfully")
        
        # Step 2.5: Resolve symbols / basic semantics
        print("Step 2a: Resolving symbols...")
        resolve_program(ast)
        print("  Resolution passed")

        # Step 2.6: Type checking
        print("Step 2b: Type checking...")
        type_check(ast)
        print("  Type checking passed")

        # Step 2.7: Additional validation (legacy checks)
        print("Step 2c: Validating AST...")
        validate_program(ast)
        print("  Validation passed")

        # Step 3: Code generation
        print("Step 3: Generating assembly...")
        assembly = generate_assembly(ast)
        
        # Determine output paths
        if generate_assembly_only:
            asm_file = output_file
            executable_file = None
        else:
            asm_file = output_file + ".s"
            executable_file = output_file
        
        # Write assembly to file
        with open(asm_file, 'w') as f:
            f.write(assembly)
        print(f"  Assembly written to {asm_file}")

        # Optional: assemble to flat machine code using Keystone
        if use_keystone:
            try:
                machine_code = assemble_with_keystone(assembly)
                bin_file = output_file + ".bin"
                with open(bin_file, 'wb') as bf:
                    bf.write(machine_code)
                print(f"  Machine code written to {bin_file} (flat binary)")
            except Exception as ke:
                print(f"  Keystone assembly failed: {ke}")
                return False
        
        if generate_assembly_only:
            return True

        # Step 4: Assemble and link per target
        print("Step 4: Assembling and linking...")
        try:
            if target == "elf":
                tool = shutil.which('gcc')
                if not tool:
                    print("  Error: gcc not found. Please install gcc.")
                    return False
                result = subprocess.run([tool, '-no-pie', asm_file, '-o', executable_file, '-lcrypto'], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"  Error: {result.stderr}")
                    return False
                print(f"  Executable written to {executable_file}")
                os.remove(asm_file)
                return True

            if target == "mach":
                # Produce Mach-O object; linking requires macOS SDK
                tool = shutil.which('clang')
                if not tool:
                    print("  Error: clang not found. Install clang to build Mach-O.")
                    return False
                object_file = executable_file if executable_file.endswith('.o') else executable_file + '.o'
                result = subprocess.run([tool, '-target', 'x86_64-apple-darwin', '-c', asm_file, '-o', object_file], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"  Error: {result.stderr}")
                    return False
                print(f"  Mach-O object written to {object_file}")
                return True

            if target == "pe":
                tool = shutil.which('x86_64-w64-mingw32-gcc') or shutil.which('clang')
                if not tool:
                    print("  Error: mingw-w64 gcc/clang not found. Install a PE-capable toolchain.")
                    return False
                object_file = executable_file if executable_file.endswith('.obj') else executable_file + '.obj'
                cmd = [tool, '-c', asm_file, '-o', object_file]
                if os.path.basename(tool).startswith('clang'):
                    cmd = [tool, '-target', 'x86_64-w64-windows-gnu', '-c', asm_file, '-o', object_file]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"  Error: {result.stderr}")
                    return False
                print(f"  PE object written to {object_file}")
                return True

            print(f"  Error: Unknown target '{target}'")
            return False

        except Exception as e:
            print(f"  Error during assembly/linking: {e}")
            return False
            
    except ValidationError as e:
        print(f"Validation Error: {e}")
        return False
    except FileNotFoundError as e:
        print(f"File Error: {e}")
        return False
    except SyntaxError as e:
        print(f"Syntax Error: {e}")
        return False
    except CodegenError as e:
        print(f"Codegen Error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="VYL Compiler - Compile VYL source code to x86-64 assembly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vyl -c program.vyl              # Compile to a.out
  vyl -c program.vyl -o myapp     # Compile to myapp
  vyl -c program.vyl -S           # Generate program.s only
  vyl -c program.vyl -S -o out.s  # Generate out.s
        """
    )
    
    parser.add_argument('-c', '--compile', dest='input', help='Input VYL source file to compile')
    parser.add_argument('-o', '--output', help='Output file name')
    parser.add_argument('-S', '--assembly', action='store_true',
                       help='Generate assembly only (don\'t assemble/link)')
    parser.add_argument('-cm', '--mach', action='store_true',
                       help='Generate Mach-O object (macOS)')
    parser.add_argument('-cpe', '--pe', action='store_true',
                       help='Generate PE/COFF object (Windows)')
    parser.add_argument('-k', '--keystone', action='store_true',
                       help='Also assemble with Keystone and emit a flat .bin')
    
    # Also support direct file argument for convenience
    parser.add_argument('input_file', nargs='?', help='Input VYL source file (alternative to -c)')
    
    args = parser.parse_args()
    
    # Determine input file (support both -c and direct file argument)
    input_file = args.input or args.input_file
    
    if not input_file:
        print("Error: No input file specified. Use -c <file> or provide file as argument")
        sys.exit(1)
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    # Read source code
    try:
        with open(input_file, 'r') as f:
            source_code = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        sys.exit(1)
    
    # Determine output file name
    if args.output:
        output_file = args.output
    else:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        if args.assembly:
            output_file = base_name + ".s"
        else:
            # Default compiled output uses .vylo extension when no explicit output is given.
            output_file = base_name + ".vylo"
    
    # Target selection
    target = 'elf'
    if args.mach:
        target = 'mach'
    elif args.pe:
        target = 'pe'

    # Compile
    print(f"Compiling {input_file} (target={target})...")
    print("-" * 50)
    
    success = compile_vyl(source_code, output_file, args.assembly, target, input_file, args.keystone)
    
    print("-" * 50)
    if success:
        print("✓ Compilation successful!")
        if args.assembly:
            print(f"  Assembly: {output_file}")
        else:
            if target == 'elf':
                print(f"  Executable: {output_file}")
                print(f"  Run with: ./{output_file}")
            elif target == 'mach':
                print(f"  Object: {output_file if output_file.endswith('.o') else output_file + '.o'}")
            elif target == 'pe':
                print(f"  Object: {output_file if output_file.endswith('.obj') else output_file + '.obj'}")
        if args.keystone:
            print(f"  Flat binary: {output_file}.bin")
    else:
        print("✗ Compilation failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
