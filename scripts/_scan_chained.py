"""
Static scanner for syntactically-chained assignments that break under
pandas copy-on-write (Pandas 4).

Reports (file, line):
  * obj[idx1][idx2] = val         -> chained subscript assignment
  * obj[idx].attr = val           -> chained subscript.attribute assignment
These are the patterns that either raise ChainedAssignmentError or silently
fail under CoW. They are the real "chained-assignment" cleanup targets.

Safe patterns (NOT reported):
  * obj.loc[...] = val            (single .loc subscript is fine)
  * obj.iloc[...] = val

Usage (repo root, any python with stdlib):
    python scripts/_scan_chained.py
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP = {"scripts/_scan_chained.py", "scripts/_probe_warn.py", "scripts/_probe_warn_b.py", "conftest.py"}


class ChainedFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.hits: list[tuple[int, str]] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._check_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.target is not None:
            self._check_target(node.target)
        self.generic_visit(node)

    def _check_target(self, target: ast.AST) -> None:
        # obj[idx1][idx2] = val  -> target is Subscript of a Subscript
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Subscript):
            self.hits.append((target.lineno, "chained subscript: obj[a][b] = val"))
        # obj[idx].attr = val    -> target is Attribute of a Subscript
        elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Subscript):
            self.hits.append((target.lineno, "chained subscript.attr: obj[a].attr = val"))


def main() -> int:
    results: list[tuple[str, int, str]] = []
    py_files = sorted(p for p in REPO.rglob("*.py") if str(p.relative_to(REPO)) not in SKIP)
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        finder = ChainedFinder()
        finder.visit(tree)
        for ln, kind in finder.hits:
            results.append((str(path.relative_to(REPO)), ln, kind))

    results.sort()
    print(f"=== {len(results)} syntactically-chained assignment sites ===\n")
    cur = None
    for rel, ln, kind in results:
        if rel != cur:
            print(f"\n## {rel}")
            cur = rel
        print(f"  L{ln}: {kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
