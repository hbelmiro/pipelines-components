#!/usr/bin/env python3
"""Validate that all components and pipelines compile successfully."""

import ast
import sys
from pathlib import Path


def find_decorated_functions(file_path: Path, decorators: set[str]) -> list[str]:
    """Find functions decorated with specific decorators in a Python file."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"  Warning: Could not parse {file_path}: {e}")
        return []

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                decorator_name = None
                if isinstance(decorator, ast.Name):
                    decorator_name = decorator.id
                elif isinstance(decorator, ast.Attribute):
                    decorator_name = decorator.attr
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        decorator_name = decorator.func.id
                    elif isinstance(decorator.func, ast.Attribute):
                        decorator_name = decorator.func.attr

                if decorator_name in decorators:
                    functions.append(node.name)
                    break

    return functions


def validate_imports() -> bool:
    """Validate that package structure imports correctly."""
    print("Validating package imports...")
    success = True

    packages = [
        ("components", ["training", "evaluation", "data_processing", "deployment"]),
        ("pipelines", ["training", "evaluation", "data_processing", "deployment"]),
    ]

    for package, submodules in packages:
        for submodule in submodules:
            module_path = f"{package}.{submodule}"
            try:
                __import__(module_path)
                print(f"  ✓ {module_path}")
            except ImportError as e:
                print(f"  ✗ {module_path}: {e}")
                success = False

    return success


def validate_compilation() -> bool:
    """Find and compile all components and pipelines."""
    print("\nValidating component/pipeline compilation...")

    try:
        from kfp import compiler, dsl
    except ImportError:
        print("  Error: kfp not installed")
        return False

    decorators = {"component", "pipeline", "container_component"}
    success = True
    found_any = False

    for directory in ["components", "pipelines"]:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            functions = find_decorated_functions(py_file, decorators)
            if not functions:
                continue

            found_any = True
            module_path = str(py_file.with_suffix("")).replace("/", ".")

            for func_name in functions:
                try:
                    module = __import__(module_path, fromlist=[func_name])
                    func = getattr(module, func_name)

                    compiler.Compiler().compile(func, f"/tmp/{func_name}.yaml")
                    print(f"  ✓ {module_path}.{func_name}")
                except Exception as e:
                    print(f"  ✗ {module_path}.{func_name}: {e}")
                    success = False

    if not found_any:
        print("  No components or pipelines found to compile")

    return success


def main() -> int:
    sys.path.insert(0, ".")

    imports_ok = validate_imports()
    compilation_ok = validate_compilation()

    print()
    if imports_ok and compilation_ok:
        print("✓ All validations passed")
        return 0
    else:
        print("✗ Some validations failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

