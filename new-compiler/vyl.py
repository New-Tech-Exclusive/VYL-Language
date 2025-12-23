#!/usr/bin/env python3

"""
VYL Compiler - Standalone CLI

This script provides a simple command-line interface for the VYL compiler.
Usage: vylc.py -c program.vyl
"""

import sys
import os

# Add the current directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import tokenize
from parser import parse
from codegen import generate_assembly
import subprocess
import argparse


def compile_vyl(source_code: str, output_file: str, generate_assembly_only: bool = False) -> bool:
    """Compile VYL source code to assembly or executable"""
    try:
        # Step 1: Lexical analysis
        print("Tokenizing...")
        tokens = tokenize(source_code)
        print(f"  Generated {len(tokens)} tokens")
        
        # Step 2: Parsing
        print("Parsing...")
        ast = parse(tokens)
        print("  AST generated successfully")
        
        # Step 3: Code generation
        print("Generating assembly...")
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
            result = subprocess.run([
                'gcc', '-no-pie', asm_file, '-o', executable_file, '-lc'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"  Error: {result.stderr}")
                return False
            
            print(f"  Executable written to {executable_file}")
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
        return False


def main():
    parser = argparse.ArgumentParser(
        description="VYL Compiler - Compile VYL source code to x86-64 assembly",
        epilog="Examples:\n  vylc.py -c program.vyl\n  vylc.py -c program.vyl -o myapp\n  vylc.py -c program.vyl -S",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-c', '--compile', dest='input', required=True, help='Input VYL source file')
    parser.add_argument('-o', '--output', help='Output file name')
    parser.add_argument('-S', '--assembly', action='store_true', help='Generate assembly only')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        sys.exit(1)
    
    try:
        with open(args.input, 'r') as f:
            source_code = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        sys.exit(1)
    
    output_file = args.output or (os.path.splitext(os.path.basename(args.input))[0] + (".s" if args.assembly else ""))
    
    print(f"Compiling {args.input}...")
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
