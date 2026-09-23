# «LightMap из папки»: файл <имя>_d — дневная карта, <имя>_n — ночная.
# Сопоставление идёт по имени объекта/меша, поэтому проверяем разбор папки и
# набор имён-кандидатов (Blender-суффикс .001 и хвосты _dff/_LOD/_dam/_ok).
#
# texture_ops импортирует bpy на уровне модуля — функции вытаскиваем по AST
# (тот же приём, что в test_material_color_export).

import ast
import io
import os
import re
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "INU_tools", "ops", "texture_ops.py")

WANTED = {"_lm_scan_folder", "_lm_name_candidates",
          "LM_IMAGE_EXT", "LM_DAY_SUFFIX", "LM_NIGHT_SUFFIX", "LM_NAME_TAIL"}


def _load():
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WANTED:
            keep.append(node)
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(t in WANTED for t in targets):
                keep.append(node)
    ns = {"os": os, "_re": re}
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns


NS = _load()
scan_folder = NS["_lm_scan_folder"]
name_candidates = NS["_lm_name_candidates"]


def _obj(name, mesh_name=None):
    return types.SimpleNamespace(
        name=name, data=types.SimpleNamespace(name=mesh_name or name))


def test_scan_folder_splits_day_and_night(tmp_path):
    for fn in ("house01_d.png", "house01_n.png", "shop_DAY.tga",
               "shop_night.tga", "readme.txt", "plain.png"):
        (tmp_path / fn).write_bytes(b"")
    found = scan_folder(str(tmp_path))
    assert set(found) == {"house01", "shop"}
    assert os.path.basename(found["house01"]["DAY"]) == "house01_d.png"
    assert os.path.basename(found["house01"]["NIGHT"]) == "house01_n.png"
    # Регистр суффикса не важен, длинная форма (_day/_night) тоже принимается.
    assert os.path.basename(found["shop"]["DAY"]) == "shop_DAY.tga"
    assert os.path.basename(found["shop"]["NIGHT"]) == "shop_night.tga"


def test_scan_folder_ignores_non_images(tmp_path):
    (tmp_path / "x_d.txt").write_bytes(b"")
    assert scan_folder(str(tmp_path)) == {}


def test_scan_folder_missing_dir():
    assert scan_folder(os.path.join(os.sep, "no", "such", "folder")) == {}


def test_name_candidates_strips_copy_and_tails():
    cands = name_candidates(_obj("house01_dff.001"))
    assert "house01_dff" in cands       # без .001
    assert "house01" in cands           # без хвоста _dff
    cands = name_candidates(_obj("tower_LOD"))
    assert "tower" in cands
    # Имя меша тоже кандидат — модели часто переименованы в объекте.
    cands = name_candidates(_obj("Cube.003", mesh_name="shop_ok"))
    assert "shop" in cands
