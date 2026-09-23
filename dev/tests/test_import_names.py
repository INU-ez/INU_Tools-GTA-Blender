# Каждое имя, которое __init__.py тянет относительным импортом, должно
# существовать в своём модуле.
#
# Повод: класс оператора однажды попал в блок `from .ui.geo_panels import
# (...)` вместо блока ops, и аддон падал на включении с «cannot import
# name». Компиляция такое не ловит — импорт разрешается только в рантайме,
# а рантайм здесь требует Blender. Проверяем разбором AST, без bpy.

import ast
import io
import os

ADDON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "INU_tools")


def _parse(path):
    return ast.parse(io.open(path, encoding="utf-8").read())


def _toplevel_names(path):
    """Имена, определённые на верхнем уровне модуля.

    Классы внутри `if hasattr(bpy.types, 'FileHandler')` сюда не попадают,
    поэтому имена, которых нет, дополнительно проверяются как подмодули и
    как условные определения."""
    names = set()
    for node in _parse(path).body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets
                         if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target,
                                                            ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(a.asname or a.name.split(".")[0] for a in node.names)
    return names


def _nested_names(path):
    """Имена классов и функций на любой глубине — для определений под `if`."""
    return {n.name for n in ast.walk(_parse(path))
            if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef))}


def _module_file(module):
    parts = module.split(".")
    direct = os.path.join(ADDON, *parts) + ".py"
    if os.path.isfile(direct):
        return direct
    package = os.path.join(ADDON, *parts, "__init__.py")
    return package if os.path.isfile(package) else None


def _is_submodule(module, name):
    """`from .tools import compat` — имя не в __init__.py, а рядом файлом."""
    base = os.path.join(ADDON, *module.split("."))
    return (os.path.isfile(os.path.join(base, name + ".py"))
            or os.path.isfile(os.path.join(base, name, "__init__.py")))


def test_relative_imports_resolve():
    init = os.path.join(ADDON, "__init__.py")
    missing = []
    for node in ast.walk(_parse(init)):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 1 or not node.module:
            continue
        target = _module_file(node.module)
        if target is None:
            missing.append("нет модуля %s" % node.module)
            continue
        available = _toplevel_names(target)
        for alias in node.names:
            name = alias.name
            if name == "*" or name in available:
                continue
            if _is_submodule(node.module, name):
                continue
            if name in _nested_names(target):
                continue
            missing.append("%s не найдено в %s" % (name, node.module))
    assert not missing, "\n".join(missing)
