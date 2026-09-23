"""
Полная очистка следов тайм-цикла (INU Tools) из текущей сцены Blender.

Что убирает:
  • материалы: ноды Prelight_* (превью прилайта, игровой вид, туман),
    инстанс группы Day↔Night, восстанавливает Base Color/текстуру,
    чистит служебные пропсы (inu_tc_*, prelight_preview_active);
  • мир «INU Timecyc» (возвращает прежний, если он был запомнен), солнце
    INU_Timecyc_Sun, коллекцию «INU Timecyc», нод-группу INU_Timecyc_DayNight;
  • композитор сцены: ноды INU_TC_*;
  • пропсы сцены inu_tc_* и флаги gtatools_timecyc (enabled/game_look/…).

Как запустить: Blender → вкладка Scripting → Open → этот файл → Run Script
(или вставить в текстовый редактор и нажать ▶). Идемпотентно: можно гонять
повторно, лишнего не сломает. Работает и без загруженного тайм-цикла.
"""

import bpy

# ── Имена, которые ставит тайм-цикл (из исходников аддона) ──────────────
WORLD_NAME       = "INU Timecyc"
SUN_NAME         = "INU_Timecyc_Sun"
COLLECTION_NAME  = "INU Timecyc"
DAYNIGHT_GROUP   = "INU_Timecyc_DayNight"
PRELIGHT_PREFIX  = "Prelight_"          # все ноды превью прилайта/игрового вида
COMP_PREFIX      = "INU_TC_"            # ноды композитора (туман/PostFX)
MAT_PROPS  = ("inu_tc_game_look", "inu_tc_prev_emit", "inu_tc_prev_base",
             "inu_tc_ambient", "inu_tc_night_balance", "prelight_preview_active",
             "prelight_alpha_mode")
SCENE_PROPS = ("inu_tc_comp_version", "inu_tc_fog_attempts", "inu_tc_fog_wired",
               "inu_tc_prev_view", "inu_tc_prev_world")

stats = {"materials": 0, "nodes": 0, "props": 0, "datablocks": 0}


def _principled(nodes):
    for n in nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None


def _first_texture_socket(nodes):
    """Первый вывод Color у ноды-картинки — чтобы вернуть текстуру на Base Color."""
    for n in nodes:
        if n.type == 'TEX_IMAGE':
            out = n.outputs.get('Color')
            if out is not None:
                return out
    return None


def clean_material(mat):
    if not mat or not getattr(mat, 'use_nodes', False) or mat.node_tree is None:
        return
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    touched = False

    principled = _principled(nodes)

    # 1) Снять игровой вид: вернуть Base Color, погасить Emission.
    if principled is not None:
        bc = principled.inputs.get('Base Color')
        emit = (principled.inputs.get('Emission Color')
                or principled.inputs.get('Emission'))
        tex = _first_texture_socket(nodes)
        if bc is not None:
            for l in list(bc.links):
                links.remove(l)
            if tex is not None:
                links.new(tex, bc)                 # вернуть текстуру
            else:
                prev = mat.get('inu_tc_prev_base')
                bc.default_value = (tuple(prev) if prev is not None
                                    else (0.8, 0.8, 0.8, 1.0))
            touched = True
        if emit is not None:
            for l in list(emit.links):
                links.remove(l)
            try:
                emit.default_value = (0.0, 0.0, 0.0, 1.0)
            except Exception:
                pass
            strength = principled.inputs.get('Emission Strength')
            if strength is not None and not strength.is_linked:
                strength.default_value = float(mat.get('inu_tc_prev_emit', 1.0))

    # 2) Удалить все ноды прелайта/тайм-цикла (Prelight_* + инстанс группы).
    for n in list(nodes):
        nm = getattr(n, 'name', '')
        is_group = (n.type == 'GROUP'
                    and getattr(n, 'node_tree', None) is not None
                    and n.node_tree.name == DAYNIGHT_GROUP)
        if nm.startswith(PRELIGHT_PREFIX) or is_group:
            nodes.remove(n)
            stats["nodes"] += 1
            touched = True

    # 3) Служебные пропсы материала.
    for k in MAT_PROPS:
        if k in mat.keys():
            del mat[k]
            stats["props"] += 1
            touched = True

    if touched:
        stats["materials"] += 1


def clean_scene_world(scene):
    # Вернуть прежний мир, если тайм-цикл его запоминал.
    prev = scene.get('inu_tc_prev_world')
    if prev is not None:
        scene.world = bpy.data.worlds.get(prev) if prev else None
    elif scene.world is not None and scene.world.name == WORLD_NAME:
        scene.world = None
    # Снять игровую цветокоррекцию (view transform), если стоит Standard-заглушка.
    view = getattr(scene, 'view_settings', None)
    pv = scene.get('inu_tc_prev_view')
    if view is not None and pv:
        try:
            view.view_transform, view.look = pv[0], pv[1]
            view.exposure, view.gamma = float(pv[2]), float(pv[3])
        except Exception:
            pass


def clean_compositor(scene):
    nt = getattr(scene, 'node_tree', None)
    if nt is None:
        return
    for n in list(nt.nodes):
        if getattr(n, 'name', '').startswith(COMP_PREFIX):
            nt.nodes.remove(n)
            stats["nodes"] += 1
    # Восстановить простую цепочку Render Layers → Composite, если тайм-цикл
    # был вставлен в неё и после удаления вход Composite повис.
    comp = next((n for n in nt.nodes if n.type == 'COMPOSITE'), None)
    rl = next((n for n in nt.nodes if n.type == 'R_LAYERS'), None)
    if comp is not None and rl is not None:
        img_in = comp.inputs.get('Image')
        img_out = rl.outputs.get('Image')
        if img_in is not None and img_out is not None and not img_in.is_linked:
            nt.links.new(img_out, img_in)


def remove_datablock(collection, name):
    db = collection.get(name)
    if db is not None:
        try:
            collection.remove(db)
            stats["datablocks"] += 1
        except Exception:
            pass


def main():
    scene = bpy.context.scene

    # Флаги тайм-цикла — в выкл (если аддон установлен).
    props = getattr(getattr(scene, 'inu_settings', None), 'gtatools_timecyc', None)
    if props is not None:
        for flag in ('enabled', 'live', 'game_look', 'prelight_daynight',
                     'use_fog', 'use_postfx'):
            try:
                setattr(props, flag, False)
            except Exception:
                pass

    # Материалы.
    for mat in bpy.data.materials:
        clean_material(mat)

    # Мир / цветокоррекция.
    clean_scene_world(scene)

    # Композитор.
    clean_compositor(scene)

    # Пропсы сцены.
    for k in SCENE_PROPS:
        if k in scene.keys():
            del scene[k]
            stats["props"] += 1

    # Датаблоки: солнце, коллекция, мир, нод-группа.
    remove_datablock(bpy.data.objects, SUN_NAME)
    remove_datablock(bpy.data.collections, COLLECTION_NAME)
    remove_datablock(bpy.data.worlds, WORLD_NAME)
    remove_datablock(bpy.data.node_groups, DAYNIGHT_GROUP)

    # Осиротевшие копии («INU_Timecyc_DayNight.001» и т.п.).
    for grp in list(bpy.data.node_groups):
        if grp.name.startswith(DAYNIGHT_GROUP) and grp.users == 0:
            bpy.data.node_groups.remove(grp)
            stats["datablocks"] += 1

    print("[INU] Тайм-цикл очищен из сцены: "
          "материалов %(materials)d, нод %(nodes)d, "
          "пропсов %(props)d, датаблоков %(datablocks)d" % stats)


if __name__ == "__main__":
    main()
