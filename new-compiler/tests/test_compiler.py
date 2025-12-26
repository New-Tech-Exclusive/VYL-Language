import importlib.util
import sys
import tempfile
from pathlib import Path
import unittest

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "vylc"


def _load_compiler_modules():
    """Load compiler modules under a stable package name for testing."""
    if f"{PACKAGE_NAME}.main" in sys.modules:
        return (
            sys.modules[f"{PACKAGE_NAME}.main"],
            sys.modules[f"{PACKAGE_NAME}.lexer"],
            sys.modules[f"{PACKAGE_NAME}.parser"],
            sys.modules[f"{PACKAGE_NAME}.validator"],
        )

    package_spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    package = importlib.util.module_from_spec(package_spec)
    sys.modules[PACKAGE_NAME] = package
    package_spec.loader.exec_module(package)  # type: ignore

    modules = {}
    for name in ["lexer", "parser", "validator", "codegen", "main"]:
        spec = importlib.util.spec_from_file_location(
            f"{PACKAGE_NAME}.{name}",
            PACKAGE_DIR / f"{name}.py",
            submodule_search_locations=[str(PACKAGE_DIR)],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore
        modules[name] = module

    return modules["main"], modules["lexer"], modules["parser"], modules["validator"]


class CompilerPipelineTests(unittest.TestCase):
    def setUp(self):
        self.main_mod, self.lexer_mod, self.parser_mod, self.validator_mod = _load_compiler_modules()

    def test_pipeline_produces_assembly(self):
        source = (
            "var int x = 1;\n"
            "Main() {\n"
            "  var int y = 2;\n"
            "  Print(y);\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "program.s"
            success = self.main_mod.compile_vyl(source, str(out_path), generate_assembly_only=True)
            self.assertTrue(success, "Compilation pipeline should succeed")
            self.assertTrue(out_path.exists(), "Assembly output should be created")
            assembly = out_path.read_text()
            self.assertIn("Main:", assembly)
            self.assertIn(".globl main", assembly)

    def test_missing_main_fails_validation(self):
        source = "var int x = 1;\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "program.s"
            success = self.main_mod.compile_vyl(source, str(out_path), generate_assembly_only=True)
            self.assertFalse(success, "Validation should fail when Main is missing")
            self.assertFalse(out_path.exists(), "No assembly file should be produced on validation failure")

    def test_undefined_identifier_fails_validation(self):
        source = (
            "Main() {\n"
            "  Print(x);\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "program.s"
            success = self.main_mod.compile_vyl(source, str(out_path), generate_assembly_only=True)
            self.assertFalse(success, "Validation should reject undefined identifiers")
            self.assertFalse(out_path.exists())

    def test_mach_target_assembly_only(self):
        source = (
            "Main() {\n"
            "  Print(1);\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "program.s"
            success = self.main_mod.compile_vyl(source, str(out_path), generate_assembly_only=True, target="mach")
            self.assertTrue(success)
            self.assertTrue(out_path.exists())

    def test_pe_target_assembly_only(self):
        source = (
            "Main() {\n"
            "  Print(1);\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "program.s"
            success = self.main_mod.compile_vyl(source, str(out_path), generate_assembly_only=True, target="pe")
            self.assertTrue(success)
            self.assertTrue(out_path.exists())

    def test_if_elif_else(self):
        source = (
            "Main() {\n"
            "  var int x = 2;\n"
            "  if (x == 1) { Print(1); }\n"
            "  elif (x == 2) { Print(2); }\n"
            "  else { Print(3); }\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "program.s"
            success = self.main_mod.compile_vyl(source, str(out_path), generate_assembly_only=True)
            self.assertTrue(success)
            self.assertTrue(out_path.exists())

    def test_include_merges_local_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "main.vyl"
            lib_path = Path(tmpdir) / "lib.vyl"
            lib_path.write_text("var int z = 5;\n")
            base_path.write_text(
                'include "lib.vyl"\n'
                "Main() {\n"
                "  Print(z);\n"
                "}\n"
            )
            out_path = Path(tmpdir) / "program.s"
            success = self.main_mod.compile_vyl(
                base_path.read_text(),
                str(out_path),
                generate_assembly_only=True,
                target="elf",
                source_path=str(base_path),
            )
            self.assertTrue(success)
            self.assertTrue(out_path.exists())
            self.assertIn("z", out_path.read_text())

    def test_keystone_emits_bin_when_available(self):
        try:
            import keystone  # type: ignore  # noqa: F401
        except ImportError:
            self.skipTest("keystone not installed")

        source = (
            "Main() {\n"
            "  Print(1);\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_base = Path(tmpdir) / "program"
            success = self.main_mod.compile_vyl(
                source,
                str(out_base),
                generate_assembly_only=True,
                target="elf",
                use_keystone=True,
            )
            self.assertTrue(success)
            self.assertTrue(out_base.with_suffix(".bin").exists())


if __name__ == "__main__":
    unittest.main()
