"""
VYL Compiler - A Python-based compiler for the VYL programming language

This compiler translates VYL source code to x86-64 assembly language.
It consists of several modules:
- lexer: Tokenizes VYL source code
- parser: Builds an Abstract Syntax Tree (AST)
- codegen: Generates x86-64 assembly from AST
- main: Command-line interface and orchestration

Usage:
    python -m vyl.main input.vyl -o output
"""

__version__ = "0.2.2"
__author__ = "VYL Language Organization"
