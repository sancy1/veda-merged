# filename: scripts/inspect_module.py
# title: Python Module Inspection Utility
# layer: Test-recovery tooling
# status: Phase 1-6 test recovery support
# description:
#     Reads and parses a Python source module so the developer can
#     identify its public contract, models, functions, imports, and
#     likely side effects before writing tests.
#
#     This utility does not execute application business logic. It uses
#     the ast module to parse the source file and print a structured
#     summary.
#
# source:
#     AUTHORED - no such utility existed before test recovery began.
#
# notes:
#     - Prints imports, classes (with fields and methods), top-level
#       functions, and side-effect signals (network, timestamps,
#       randomness).
#     - Never imports the target module. Never runs application code.
#     - Usage: python scripts/inspect_module.py <python-file>

from __future__ import annotations

import ast
import sys
from pathlib import Path


def annotation_text(node: ast.AST | None) -> str:
    """Return a readable string for an annotation node, or empty string."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def inspect_module(path: Path) -> None:
    """Print a structured summary of one Python source file."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    print(f"MODULE: {path}")
    print("=" * 72)

    # --- imports ---
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.extend(f"{module}.{alias.name}" for alias in node.names)

    print("IMPORTS:")
    for item in imports:
        print(f"  - {item}")

    # --- classes ---
    print("CLASSES:")
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        bases = ", ".join(annotation_text(base) for base in node.bases)
        print(f"  - {node.name}({bases})")

        fields: list[str] = []
        methods: list[str] = []

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [
                    annotation_text(arg.annotation)
                    for arg in child.args.args
                ]
                methods.append(f"{child.name}({', '.join(args)})")
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                fields.append(
                    f"{child.target.id}: {annotation_text(child.annotation)}"
                )

        for field in fields:
            print(f"      field: {field}")
        for method in methods:
            print(f"      method: {method}")

    # --- top-level functions ---
    print("TOP-LEVEL FUNCTIONS:")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [
                annotation_text(arg.annotation)
                for arg in node.args.args
            ]
            returns = annotation_text(node.returns)
            print(f"  - {node.name}({', '.join(args)}) -> {returns}")

    # --- side-effect signals ---
    lowered = source.lower()
    signals = {
        "network": any(
            token in lowered
            for token in ["httpx", "requests", "urllib", "client.get", "client.post"]
        ),
        "timestamps": any(
            token in lowered
            for token in ["datetime.now", "datetime.utcnow", "time.time"]
        ),
        "randomness": any(
            token in lowered
            for token in ["random.", "uuid.uuid4", "secrets."]
        ),
    }

    print("SIDE-EFFECT SIGNALS:")
    for name, present in signals.items():
        print(f"  - {name}: {present}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/inspect_module.py <python-file>")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        return 2

    inspect_module(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())