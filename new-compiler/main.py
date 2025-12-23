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
from pathlib import Path

# Handle both module and standalone execution
try:
    from .lexer import tokenize
    from .parser import parse
    from .codegen import generate_assembly
except ImportError:
    # Running as standalone script
    if __name__ == '__main__' and __package__ is None:
        import sys
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from lexer import tokenize
        from parser import parse
        from codegen import generate_assembly
    else:
        raise


def compile_vyl(source_code: str, output_file: str, generate_assembly_only: bool = False) -> bool:
    """
    Compile VYL source code to assembly or executable
    
    Args:
        source_code: VYL source code as string
        output_file: Output file path
        generate_assembly_only: If True, only generate assembly file
    
    Returns:
        True if compilation succeeded, False otherwise
    """
    try:
        # Step 1: Lexical analysis
        print("Step 1: Tokenizing...")
        tokens = tokenize(source_code)
        print(f"  Generated {len(tokens)} tokens")
        
        # Step 2: Parsing
        print("Step 2: Parsing...")
        ast = parse(tokens)
        print("  AST generated successfully")
        
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
        
        if generate_assembly_only:
            return True
        
        # Step 4: Assemble and link
        print("Step 4: Assembling and linking...")
        try:
            # Use gcc to assemble and link with C runtime
            result = subprocess.run([
                'gcc', '-no-pie', asm_file, '-o', executable_file
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"  Error: {result.stderr}")
                return False
            
            print(f"  Executable written to {executable_file}")
            
            # Clean up assembly file
            os.remove(asm_file)
            
            return True
            
        except FileNotFoundError:
            print("  Error: gcc not found. Please install gcc.")
            return False
        except Exception as e:
            print(f"  Error during assembly/linking: {e}")
            return False
            
    except SyntaxError as e:
        print(f"Syntax Error: {e}")
        return False
    except NameError as e:
        print(f"Name Error: {e}")
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
            output_file = base_name
    
    # Compile
    print(f"Compiling {input_file}...")
    print("-" * 50)
    
    success = compile_vyl(source_code, output_file, args.assembly)
    
    print("-" * 50)
    if success:
        print("✓ Compilation successful!")
        if not args.assembly:
            print(f"  Executable: {output_file}")
            print(f"  Run with: ./{output_file}")
        else:
            print(f"  Assembly: {output_file}")
    else:
        print("✗ Compilation failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
