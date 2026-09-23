# Диагностика краша Blender 5.1.2 в `_weld_custom` → bm.to_mesh()
# (EXCEPTION_ILLEGAL_INSTRUCTION в bm_face_loop_table_build).
#
# Запуск из Blender (Text Editor → Run Script) или:
#   blender --python dev/diag_weld_custom.py -- model.dff [ещё.dff ...]
#   blender --python dev/diag_weld_custom.py -- archive.img
#
# Что делает: импортирует DFF БЕЗ автосварки (monkeypatch), потом повторяет
# шаги `_weld_custom` по одному и после КАЖДОГО шага пишет состояние bmesh в
# лог с fsync — если Blender упадёт, в логе останется последний живой шаг.
# Режим IMG: все .dff архива подряд, имя модели пишется ДО обработки —
# после краша последняя строка лога = виновник.
# Лог: <dff|img>.weld_diag.txt рядом с файлом.

import math
import os
import sys
import tempfile
from collections import defaultdict

import bpy
import bmesh


def _addon():
    for name in ("INU_tools", "bl_ext.blender_org.inu_tools_gta_sa",
                 "bl_ext.user_default.inu_tools_gta_sa"):
        mod = sys.modules.get(name)
        if mod is not None:
            return mod
    for name in list(sys.modules):
        if name.endswith("inu_tools_gta_sa") or name == "INU_tools":
            return sys.modules[name]
    raise RuntimeError("INU Tools не загружен")


def _sync(log):
    log.flush()
    os.fsync(log.fileno())


def _stats(bm, tag, log):
    n_bad_len = sum(1 for f in bm.faces if len(f.verts) < 3)
    loop_sum = sum(len(f.verts) for f in bm.faces)
    # цикл лупов: обход по l.link_loop_next должен вернуться в первый луп
    # ровно через len(f.verts) шагов
    cyc_mismatch = 0
    for f in bm.faces:
        n_exp = len(f.verts)
        first = f.loops[0]
        l, n = first, 0
        while True:
            l = l.link_loop_next
            n += 1
            if l == first or n > n_exp + 1:
                break
        if n != n_exp:
            cyc_mismatch += 1
    dead = sum(1 for v in bm.verts if not v.is_valid)
    log.write(f"[{tag}] verts={len(bm.verts)} edges={len(bm.edges)} "
              f"faces={len(bm.faces)} "
              f"sum(face.len)={loop_sum} faces.len<3={n_bad_len} "
              f"loop-cycle-mismatch={cyc_mismatch} invalid-verts={dead} "
              f"is_valid={bm.is_valid}\n")
    _sync(log)


def diag_weld(obj, log, sharp_angle):
    me = obj.data
    log.write(f"mesh '{me.name}': verts={len(me.vertices)} "
              f"polys={len(me.polygons)} loops={len(me.loops)} "
              f"uv={[u.name for u in me.uv_layers]} "
              f"attrs={[(a.name, a.domain, a.data_type) for a in me.attributes]}\n")
    _sync(log)
    bm = bmesh.new()
    bm.from_mesh(me)
    _stats(bm, "from_mesh", log)

    by_pos = defaultdict(list)
    for f in bm.faces:
        by_pos[frozenset((round(v.co.x, 4), round(v.co.y, 4),
                          round(v.co.z, 4)) for v in f.verts)].append(f)
    protected = set()
    for faces in by_pos.values():
        if len(faces) >= 2:
            for f in faces:
                protected.update(f.verts)
    weld_verts = ([v for v in bm.verts if v not in protected]
                  if protected else bm.verts)
    log.write(f"protected verts={len(protected)} weld_verts="
              f"{len(weld_verts)} double-groups="
              f"{sum(1 for fs in by_pos.values() if len(fs) >= 2)}\n")
    _sync(log)

    bmesh.ops.remove_doubles(bm, verts=weld_verts, dist=0.00001)
    _stats(bm, "remove_doubles", log)

    n_val = 0
    for edge in bm.edges:
        if len(edge.link_faces) == 2:
            try:
                edge.smooth = edge.calc_face_angle() <= sharp_angle
            except ValueError:
                n_val += 1
                edge.smooth = True
    log.write(f"edge.smooth pass done, ValueError={n_val}\n")
    _stats(bm, "edge_smooth", log)

    # Шаг 1: to_mesh в СВЕЖИЙ пустой меш (изолирует «bmesh vs целевой меш»).
    tmp = bpy.data.meshes.new(me.name + "_diag_tmp")
    log.write("to_mesh(NEW mesh) ...\n")
    _sync(log)
    bm.to_mesh(tmp)
    log.write("to_mesh(NEW mesh) OK\n")
    _sync(log)
    bpy.data.meshes.remove(tmp)

    # Шаг 2: как в аддоне — в исходный меш.
    log.write("to_mesh(ORIGINAL mesh) ...\n")
    _sync(log)
    bm.to_mesh(me)
    log.write("to_mesh(ORIGINAL mesh) OK\n")
    _sync(log)
    bm.free()
    me.update()
    log.write("me.update OK\n")
    _sync(log)


def _no_weld(di):
    """Контекст-менеджер: отключить автосварку импорта (повторим её сами)."""
    class _Ctx:
        def __enter__(self):
            self.orig = di._weld_custom, di._weld_and_sharpen
            di._weld_custom = di._weld_and_sharpen = lambda obj: None

        def __exit__(self, *exc):
            di._weld_custom, di._weld_and_sharpen = self.orig
    return _Ctx()


def _cleanup(objs):
    for o in objs:
        try:
            me = o.data if o.type == "MESH" else None
            bpy.data.objects.remove(o)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        except Exception:                                 # noqa: BLE001
            pass


def run(dff_path):
    addon = _addon()
    di = sys.modules[addon.__name__ + ".ops.dff_import"]
    log_path = dff_path + ".weld_diag.txt"
    angle = getattr(di, "_CUSTOM_SHARP_ANGLE", math.radians(30))
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"Blender {bpy.app.version_string}\nDFF: {dff_path}\n")
        _sync(log)
        with _no_weld(di):
            objs = di.import_dff(dff_path, bpy.context, weld_sharpen=False)
        meshes = [o for o in (objs or []) if getattr(o, "type", "") == "MESH"]
        log.write(f"imported {len(meshes)} mesh object(s)\n")
        _sync(log)
        for o in meshes:
            log.write(f"\n=== {o.name} ===\n")
            diag_weld(o, log, angle)
        log.write("\nALL DONE — краша нет\n")
    print(f"[diag] лог: {log_path}")


def run_img(img_path):
    """Все .dff из IMG подряд. Объекты каждой модели удаляются сразу, чтобы
    сцена не разбухала на тысячах моделей."""
    addon = _addon()
    core_img = sys.modules[addon.__name__ + ".core.img"]
    di = sys.modules[addon.__name__ + ".ops.dff_import"]
    names = sorted(n for n in core_img.list_files(img_path)
                   if n.lower().endswith(".dff"))
    log_path = img_path + ".weld_diag.txt"
    angle = getattr(di, "_CUSTOM_SHARP_ANGLE", math.radians(30))
    with open(log_path, "w", encoding="utf-8") as log, \
            tempfile.TemporaryDirectory() as tmp, _no_weld(di):
        log.write(f"Blender {bpy.app.version_string}\nIMG: {img_path} "
                  f"({len(names)} dff)\n")
        for i, name in enumerate(names):
            log.write(f"\n=== [{i + 1}/{len(names)}] {name} ===\n")
            _sync(log)
            data = core_img.extract_file(img_path, name)
            if not data:
                log.write("extract failed\n")
                continue
            path = os.path.join(tmp, name)
            with open(path, "wb") as f:
                f.write(data)
            try:
                objs = di.import_dff(path, bpy.context, weld_sharpen=False,
                                     skip_2dfx=True)
            except Exception as e:                        # noqa: BLE001
                log.write(f"import error: {e}\n")
                continue
            objs = list(objs or [])
            for o in objs:
                if getattr(o, "type", "") == "MESH":
                    diag_weld(o, log, angle)
            _cleanup(objs)
            log.write("model OK\n")
        log.write("\nALL DONE — краша нет\n")
    print(f"[diag] лог: {log_path}")


def run_folder(folder):
    """Все .dff из папки подряд (loose-файлы модлоадера) — как run_img."""
    addon = _addon()
    di = sys.modules[addon.__name__ + ".ops.dff_import"]
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith(".dff"))
    log_path = os.path.join(folder, "weld_diag.txt")
    angle = getattr(di, "_CUSTOM_SHARP_ANGLE", math.radians(30))
    with open(log_path, "w", encoding="utf-8") as log, _no_weld(di):
        log.write(f"Blender {bpy.app.version_string}\nFOLDER: {folder} "
                  f"({len(names)} dff)\n")
        for i, name in enumerate(names):
            log.write(f"\n=== [{i + 1}/{len(names)}] {name} ===\n")
            _sync(log)
            try:
                objs = di.import_dff(os.path.join(folder, name), bpy.context,
                                     weld_sharpen=False, skip_2dfx=True)
            except Exception as e:                        # noqa: BLE001
                log.write(f"import error: {e}\n")
                continue
            objs = list(objs or [])
            for o in objs:
                if getattr(o, "type", "") == "MESH":
                    diag_weld(o, log, angle)
            _cleanup(objs)
            log.write("model OK\n")
        log.write("\nALL DONE — краша нет\n")
    print(f"[diag] лог: {log_path}")


def install_trace(log_path):
    """Режим --trace: подменить `_weld_custom` аддона логирующей версией и
    оставить Blender открытым. Дальше пользователь руками запускает любой
    импорт (IDE/IPL/IMG, Import Map, одиночный DFF) — каждая сварка пишет
    имя объекта и шаги в лог с fsync. После краша хвост лога = виновник."""
    addon = _addon()
    di = sys.modules[addon.__name__ + ".ops.dff_import"]
    angle = getattr(di, "_CUSTOM_SHARP_ANGLE", math.radians(30))
    log = open(log_path, "a", encoding="utf-8")
    log.write(f"\n##### trace start, Blender {bpy.app.version_string}\n")
    _sync(log)
    counter = [0]

    def _traced(obj):
        counter[0] += 1
        log.write(f"\n=== #{counter[0]} {obj.name} (mesh users="
                  f"{obj.data.users}, materials={len(obj.data.materials)}) ===\n")
        _sync(log)
        diag_weld(obj, log, angle)
        # хвост оригинала (auto_smooth на <4.1 + update) — diag_weld это делает
        log.write("weld OK\n")
        _sync(log)

    di._weld_custom = _traced

    # Пакет IDE/IPL/IMG в старых сборках импортирует один и тот же TXD на
    # каждый инстанс (часы на большой карте) — здесь тот же TXD грузим раз.
    ti = sys.modules[addon.__name__ + ".ops.txd_import"]
    _orig_import_txd = ti.import_txd
    _txd_seen = set()

    def _import_txd_once(filepath, *a, **kw):
        key = os.path.basename(filepath).lower()
        if key in _txd_seen:
            return []
        _txd_seen.add(key)
        return _orig_import_txd(filepath, *a, **kw)

    ti.import_txd = _import_txd_once
    print(f"[diag] trace installed → {log_path}")
    print("[diag] теперь делай импорт руками (IDE/IPL/IMG → Import)")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        print("usage: blender --python dev/diag_weld_custom.py -- "
              "model.dff | archive.img | folder | --trace [log.txt]")
    if argv and argv[0] == "--trace":
        install_trace(os.path.abspath(argv[1]) if len(argv) > 1
                      else os.path.join(tempfile.gettempdir(), "inu_weld_trace.txt"))
    else:
        for p in argv:
            p = os.path.abspath(p)
            if os.path.isdir(p):
                run_folder(p)
            elif p.lower().endswith(".img"):
                run_img(p)
            else:
                run(p)
