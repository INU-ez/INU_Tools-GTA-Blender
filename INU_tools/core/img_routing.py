# INU_tools.core.img_routing — в какой IMG писать модели при «Export to IMG».
#
# Игра берёт модель из ПЕРВОГО архива, где она записана: SA обходит
# gta3.img → gta_int.img → IMG из gta.dat (CStreaming::LoadCdDirectory,
# 0x5B82C0), III/VC — архивы CDIMAGE поверх gta3.img (re3 Streaming.cpp).
# Копия модели в другом архиве перекрыта — экспорт «ничего не делает».
# Поэтому модель со своим архивом (img_target_file) всегда пишется в него,
# а выбранный в окне архив получают только модели без своего (решение
# пользователя, как в Max).
#
# Без bpy: пути приходят уже абсолютными (bpy.path.abspath у вызывающего).

import os

from .fs_ci import path_key, resolve as _ci


def img_key(path):
    """Один архив в разном написании (регистр, «..», слэши) — один ключ."""
    return path_key(path)


def route_groups(own_by_base, default, isfile=os.path.isfile):
    """{base: свой архив или ''} + архив для моделей без своего →
    ({архив: [base]}, [base без архива]). Свой архив, которого нет на
    диске, — как без своего. Архив — путь в первом встреченном написании."""
    routes, paths, unresolved = {}, {}, []
    if default and not isfile(default):
        default = _ci(default)          # another letter case (Linux / macOS)
    for base, own in own_by_base.items():
        if own and not isfile(own):
            own = _ci(own)
        path = own if own and isfile(own) else default
        if not path or not isfile(path):
            unresolved.append(base)
            continue
        arch = paths.setdefault(img_key(path),
                                os.path.normpath(os.path.abspath(path)))
        routes.setdefault(arch, []).append(base)
    return routes, unresolved


def lod_routes(own_by_base, model_archives, isfile=os.path.isfile):
    """LOD → its own archive, or its model's. A missing explicit archive
    is an error; falling back would shadow the LOD the game already loads."""
    out, missing = {}, []
    paths = {img_key(a): a for a in model_archives.values() if a}
    for base, own in own_by_base.items():
        path = _ci(own) if own else model_archives.get(base, '')
        if not path or not isfile(path):
            missing.append(base)
            continue
        out[base] = paths.setdefault(img_key(path), os.path.normpath(os.path.abspath(path)))
    return out, missing


def shared_targets(archives, has_entry, required=()):
    """Куда писать запись, общую для моделей из разных архивов (TXD,
    library .col): в те их архивы, где она уже есть (там её читает игра);
    нет нигде — в архив первой модели. archives — по моделям, с повторами."""
    uniq = list(dict.fromkeys(archives))
    targets = [a for a in uniq if has_entry(a)] or uniq[:1]
    return list(dict.fromkeys(targets + list(required)))
