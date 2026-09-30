"""scene_settings.py: ленивые прокси update=/items= находят свои функции.

Прокси делают `from . import X` / `from .tools.col_light import X` в момент
вызова; имени нет в модуле — ImportError в каждом update-колбэке (так было с
_col_light_invalidate_preview: __init__ его не импортирует, Night Min/Max,
Edge, Threshold, Contrast, Font Size сыпали трейсбеком без tag_redraw).
Проверка по AST: каждое такое имя определено или импортировано на верхнем
уровне целевого модуля."""

import ast
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "INU_tools"
SETTINGS = PKG / "scene_settings.py"


def _top_names(path):
    names = set()
    for node in ast.parse(io.open(path, encoding="utf-8").read()).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


def _lazy_imports():
    tree = ast.parse(io.open(SETTINGS, encoding="utf-8").read())
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                yield fn.name, node.module, [a.name for a in node.names]


def test_every_lazy_proxy_import_resolves():
    seen, missing = 0, []
    for fn, module, names in _lazy_imports():
        if module is None:
            target = PKG / "__init__.py"
        else:
            base = PKG.joinpath(*module.split("."))
            target = base / "__init__.py" if base.is_dir() else base.with_suffix(".py")
        top = _top_names(target)
        subpkg = {p.stem for p in target.parent.iterdir()} if target.name == "__init__.py" else set()
        for name in names:
            seen += 1
            if name not in top and name not in subpkg:
                missing.append(f"{fn}: from .{module or ''} import {name}")
    assert seen > 10
    assert not missing, missing


def test_col_light_proxy_targets_col_light():
    got = [(m, n) for fn, m, n in _lazy_imports()
           if fn == "_col_light_invalidate_preview_proxy"]
    assert got == [("tools.col_light", ["_col_light_invalidate_preview"])]
