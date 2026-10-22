"""Route handlers must only pass keyword arguments that the service request dataclasses accept.

Several string-matching contract tests passed while POST /returns crashed with
``TypeError: ReturnRequest.__init__() got an unexpected keyword argument 'version'``. This AST check
catches that whole class of bug without needing a database.
"""
import ast
import dataclasses
import importlib
import inspect
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[1] / "app" / "api" / "routes"


def _service_dataclasses():
    found = {}
    for path in (ROUTES.parent.parent / "services").glob("*.py"):
        module = importlib.import_module(f"app.services.{path.stem}")
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if dataclasses.is_dataclass(obj) and obj.__module__ == module.__name__:
                found[name] = {f.name for f in dataclasses.fields(obj)}
    return found


def test_routes_pass_only_valid_keywords_to_service_dataclasses():
    classes = _service_dataclasses()
    assert "ReturnRequest" in classes
    problems = []
    for path in sorted(ROUTES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in classes:
                for kw in node.keywords:
                    if kw.arg is not None and kw.arg not in classes[node.func.id]:
                        problems.append(f"{path.name}:{node.lineno} {node.func.id}({kw.arg}=...)")
    assert not problems, problems
