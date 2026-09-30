# INU_tools.tools.vehicle_scale — vehicle hierarchy tools.
#
# GTA SA vehicles are stored as a tree of Empties (chassis_dummy,
# wheel_*_dummy, bump_front_dummy, door_*_dummy, …) with meshes as
# children — and each visible body part has both an `_ok` and a `_dam`
# variant that the engine swaps when the vehicle takes damage.
#
# This module ships:
#   • Vehicle Scale — uniform rescale of the whole hierarchy (positions,
#     mesh data, empty display sizes), so the DFF exporter sees a clean
#     scale=(1,1,1) tree.
#   • Damage variants — paired _ok / _dam atomic management. The game
#     auto-detects the suffix at load time, so all the addon needs to
#     do is help the user create matching pairs and toggle viewport
#     visibility between OK and damaged state for preview.

import bpy
from mathutils import Matrix

from .. import T
from typing import Dict, List, Optional, Tuple


# ── Damage-variant naming ────────────────────────────────────────────

_OK_SUFFIX = "_ok"
_DAM_SUFFIX = "_dam"


def _strip_damage_suffix(name: str) -> Tuple[str, str]:
    """Return (base, suffix) where suffix is _ok / _dam / ''."""
    if name.endswith(_OK_SUFFIX):
        return name[:-len(_OK_SUFFIX)], _OK_SUFFIX
    if name.endswith(_DAM_SUFFIX):
        return name[:-len(_DAM_SUFFIX)], _DAM_SUFFIX
    return name, ""


def collect_vehicle_root(obj: "Optional[bpy.types.Object]") -> "Optional[bpy.types.Object]":
    """Walk parents up to the topmost ancestor for hierarchy ops."""
    if obj is None:
        return None
    root = obj
    while root.parent is not None:
        root = root.parent
    return root


def find_damage_pairs(objects) -> List[Tuple["bpy.types.Object", "bpy.types.Object"]]:
    """Return [(ok_obj, dam_obj)] for matched suffix pairs in *objects*."""
    by_base: Dict[str, Dict[str, bpy.types.Object]] = {}
    for obj in objects:
        if obj.type != 'MESH':
            continue
        base, suffix = _strip_damage_suffix(obj.name)
        if not suffix:
            continue
        by_base.setdefault(base, {})[suffix] = obj
    pairs = []
    for base, parts in by_base.items():
        ok = parts.get(_OK_SUFFIX)
        dam = parts.get(_DAM_SUFFIX)
        if ok and dam:
            pairs.append((ok, dam))
    return pairs


def _walk(obj, out: list):
    out.append(obj)
    for ch in obj.children:
        _walk(ch, out)


def _scaled_local(local, factor: float):
    """Parent-relative 4×4 *local* with its offset scaled by *factor*,
    rotation untouched. Plain indexing — runs on numpy too (tests)."""
    out = local.copy()
    for i in range(3):
        out[i][3] *= factor
    return out


def _rescale_hierarchy(root, factor: float, *, dummies_only: bool):
    """Return (scaled_meshes, scaled_empties) count after walking the tree."""
    if factor <= 0.0:
        return 0, 0

    tree: List[bpy.types.Object] = []
    _walk(root, tree)

    scaled_meshes = 0
    scaled_empties = 0
    scale_mat = Matrix.Scale(factor, 4)

    for i, obj in enumerate(tree):
        # Rescale position offset from parent. The walked root stays put —
        # the tree scales about it. The parent inverse is folded into the
        # new basis before it is reset, so a child parented with Keep
        # Transform keeps its place instead of jumping.
        if i:
            local = _scaled_local(
                obj.matrix_parent_inverse @ obj.matrix_basis, factor)
            try:
                obj.matrix_parent_inverse.identity()
            except Exception:
                pass
            obj.matrix_basis = local

        if obj.type == 'MESH' and not dummies_only:
            # Transform the mesh data itself so vertex positions shrink/grow
            if obj.data.users == 1:
                obj.data.transform(scale_mat)
            else:
                # Shared mesh — copy so we don't touch other users
                obj.data = obj.data.copy()
                obj.data.transform(scale_mat)
            obj.scale = (1.0, 1.0, 1.0)
            scaled_meshes += 1

        elif obj.type == 'EMPTY':
            obj.empty_display_size *= factor
            obj.scale = (1.0, 1.0, 1.0)
            scaled_empties += 1

        elif obj.type == 'ARMATURE':
            # For skinned vehicles — transform the armature data too
            if obj.data.users == 1:
                obj.data.transform(scale_mat)
            obj.scale = (1.0, 1.0, 1.0)

    return scaled_meshes, scaled_empties


class GTATOOLS_OT_vehicle_scale(bpy.types.Operator):
    """Пропорционально масштабировать всю иерархию машины (Empty-корень + меши + дамми), сохраняя структуру. Применяет масштаб к данным меша чтобы DFF-экспорт остался чистым"""
    bl_idname = "gtatools.vehicle_scale"
    bl_label = "INU: Vehicle Scale"
    bl_options = {'REGISTER', 'UNDO'}

    factor: bpy.props.FloatProperty(
        name="Factor", default=1.0, min=0.01, max=100.0,
        description=T("Множитель равномерного масштаба — применяется к позициям и вершинам"),
    )
    dummies_only: bpy.props.BoolProperty(
        name="Dummies Only",
        description=T("Двигать только дамми-Empty, меши не трогать"),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        root = context.active_object
        meshes, empties = _rescale_hierarchy(
            root, self.factor, dummies_only=self.dummies_only)
        self.report(
            {'INFO'},
            f"×{self.factor:g}: {meshes} mesh(es), {empties} empty(s)")
        return {'FINISHED'}


# ── Damage Variant operators ─────────────────────────────────────────

class GTATOOLS_OT_vehicle_add_damage_variant(bpy.types.Operator):
    """Создать поврежденный (_dam) дубликат активного меша. Если у источника нет суффикса, ему присваивается _ok. Поврежденный вариант ставится в ту же иерархию и скрывается во viewport (но остаётся видим для DFF-экспорта)"""
    bl_idname = "gtatools.vehicle_add_damage_variant"
    bl_label = "Добавить _dam вариант"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None
                and context.active_object.type == 'MESH')

    def execute(self, context):
        src = context.active_object
        base, suffix = _strip_damage_suffix(src.name)
        if suffix == _DAM_SUFFIX:
            self.report({'WARNING'},
                        f"{src.name}{T(' уже _dam — выбери _ok вариант')}")
            return {'CANCELLED'}
        if suffix == "":
            try:
                src.name = base + _OK_SUFFIX
            except Exception:
                pass

        new_name = base + _DAM_SUFFIX
        # Avoid name collision — Blender appends .001 itself, but we
        # want to fail loudly when the pair already exists.
        for obj in bpy.data.objects:
            if obj.name == new_name:
                self.report({'WARNING'},
                            f"{new_name}{T(' уже есть в сцене — связана пара')}")
                return {'CANCELLED'}

        new_mesh = src.data.copy()
        new_mesh.name = new_name
        new_obj = bpy.data.objects.new(new_name, new_mesh)
        new_obj.matrix_world = src.matrix_world.copy()
        new_obj.parent = src.parent
        try:
            new_obj.matrix_parent_inverse = src.matrix_parent_inverse.copy()
        except Exception:
            pass

        for coll in src.users_collection:
            try:
                coll.objects.link(new_obj)
            except RuntimeError:
                # Already linked (rare race)
                pass
        if not src.users_collection:
            context.scene.collection.objects.link(new_obj)

        # Hide _dam from viewport so the user previews OK state by default.
        # DFF exporter walks all hierarchy children regardless of viewport
        # hide flag, so the variant still ships into the .dff.
        new_obj.hide_viewport = True

        self.report({'INFO'}, f"{T('Создан')}: {new_name}")
        return {'FINISHED'}


class GTATOOLS_OT_vehicle_show_damage(bpy.types.Operator):
    """Переключить отображение OK / Damaged частей машины во viewport. Сканирует иерархию активной машины (или всю сцену, если активного объекта нет) и скрывает _ok или _dam меши в зависимости от выбранного состояния. Не влияет на DFF-экспорт"""
    bl_idname = "gtatools.vehicle_show_damage"
    bl_label = "Состояние повреждений"
    bl_options = {'REGISTER', 'UNDO'}

    state: bpy.props.EnumProperty(
        name=T("Состояние"),
        items=[
            ('OK', T("OK"), T("Показать целые меши, скрыть _dam")),
            ('DAM', T("Damaged"), T("Показать повреждённые _dam меши, скрыть _ok")),
            ('BOTH', T("Оба"), T("Показать оба варианта одновременно")),
        ],
        default='OK',
    )

    def execute(self, context):
        # Limit scan to active object's hierarchy when possible — keeps
        # operator harmless when there are multiple vehicles in scene.
        root = collect_vehicle_root(context.active_object)
        if root is not None:
            tree: List[bpy.types.Object] = []
            stack = [root]
            while stack:
                cur = stack.pop()
                tree.append(cur)
                stack.extend(cur.children)
            scope = tree
        else:
            scope = list(bpy.data.objects)

        ok_count = dam_count = 0
        for obj in scope:
            if obj.type != 'MESH':
                continue
            _base, suffix = _strip_damage_suffix(obj.name)
            if suffix == _OK_SUFFIX:
                obj.hide_viewport = (self.state == 'DAM')
                ok_count += 1
            elif suffix == _DAM_SUFFIX:
                obj.hide_viewport = (self.state == 'OK')
                dam_count += 1

        self.report(
            {'INFO'},
            f"{self.state}: {T('OK')}={ok_count} {T('Damaged')}={dam_count}",
        )
        return {'FINISHED'}


class GTATOOLS_OT_vehicle_pair_report(bpy.types.Operator):
    """Найти и отчитаться о парах _ok / _dam в активной иерархии. Предупреждает если у меша есть _ok без _dam (или наоборот) — такой меш пропускается движком при повреждениях"""
    bl_idname = "gtatools.vehicle_pair_report"
    bl_label = "Проверить _ok/_dam пары"
    bl_options = {'REGISTER'}

    def execute(self, context):
        root = collect_vehicle_root(context.active_object)
        if root is None:
            scope = list(bpy.data.objects)
        else:
            scope = []
            stack = [root]
            while stack:
                cur = stack.pop()
                scope.append(cur)
                stack.extend(cur.children)

        oks: Dict[str, bpy.types.Object] = {}
        dams: Dict[str, bpy.types.Object] = {}
        for obj in scope:
            if obj.type != 'MESH':
                continue
            base, suffix = _strip_damage_suffix(obj.name)
            if suffix == _OK_SUFFIX:
                oks[base] = obj
            elif suffix == _DAM_SUFFIX:
                dams[base] = obj

        paired = sorted(set(oks) & set(dams))
        ok_only = sorted(set(oks) - set(dams))
        dam_only = sorted(set(dams) - set(oks))

        print("[vehicle_pair_report] paired _ok+_dam:")
        for base in paired:
            print(f"  {base}: {oks[base].name} ↔ {dams[base].name}")
        print("[vehicle_pair_report] _ok без пары:")
        for base in ok_only:
            print(f"  {oks[base].name}")
        print("[vehicle_pair_report] _dam без пары:")
        for base in dam_only:
            print(f"  {dams[base].name}")

        msg = (f"{T('Пар')}: {len(paired)} | "
               f"{T('одиночные _ok')}: {len(ok_only)} | "
               f"{T('одиночные _dam')}: {len(dam_only)} "
               f"({T('детали в системной консоли')})")
        level = 'WARNING' if (ok_only or dam_only) else 'INFO'
        self.report({level}, msg)
        return {'FINISHED'}


