"""User-facing bake diagnostics, stack reuse and final texture inspection."""
import json
import uuid

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .. import T
from ..tools.bake.bake_workflow import (diagnose_uv, selection_uv_conflicts,
    stack_data, validate_stack, bake_stamp, stamp_status)
from . import bake_ops as ops


def _mesh_object(context):
    obj = context.active_object
    return obj if obj and obj.type == 'MESH' else None


def _layer(context):
    obj = _mesh_object(context)
    layers = obj.inu.gtatools_bake_layers if obj else ()
    index = obj.inu.gtatools_bake_layers_index if obj else -1
    return layers[index] if 0 <= index < len(layers) else None


def _apply_rows(obj, data, replace=False):
    """Validate first, append transactionally, then optionally remove old rows."""
    from ..tools.bake.bake_maps import get_map
    rows = validate_stack(data)
    if any(get_map(row['map_id']) is None for row in rows):
        raise ValueError(T('Неизвестная карта в пресете'))
    layers = obj.inu.gtatools_bake_layers
    old_count = len(layers)
    obj['_inu_bake_editing_stack'] = True
    try:
        for row in rows:
            layer = layers.add()
            layer.uid = uuid.uuid4().hex[:16]
            for key, value in row.items():
                if key in {'paint_mask_index', 'masks', 'uid', 'paint_mask_uid'}:
                    continue
                prop = layer.bl_rna.properties.get(key)
                if prop is not None and not prop.is_readonly:
                    setattr(layer, key, value)
            for mask_row in row.get('masks', ()):
                mask = layer.masks.add()
                for key, value in mask_row.items():
                    if key in {'basis', 'operation', 'strength', 'invert', 'enabled'}:
                        setattr(mask, key, value)
        for index, row in enumerate(rows):
            mask_index = row.get('paint_mask_index', -1)
            if mask_index >= 0:
                layers[old_count+index].paint_mask_uid = layers[old_count+mask_index].uid
        if replace:
            for _ in range(old_count):
                layers.remove(0)
        obj.inu.gtatools_bake_layers_index = 0
    except Exception:
        while len(layers) > old_count:
            layers.remove(len(layers)-1)
        raise
    finally:
        obj.pop('_inu_bake_editing_stack', None)
    ops.rebuild_live_composite(obj)


class GTATOOLS_OT_bake_mask_edit(bpy.types.Operator):
    bl_idname = 'gtatools.bake_mask_edit'
    bl_label = 'Изменить маски эффекта'
    bl_options = {'REGISTER', 'UNDO'}
    uid: StringProperty()
    index: IntProperty(default=-1)

    def execute(self, context):
        obj = _mesh_object(context)
        layer = next((l for l in obj.inu.gtatools_bake_layers if ops._lkey(l) == self.uid), None) if obj else None
        if layer is None:
            return {'CANCELLED'}
        if self.index < 0:
            if len(layer.masks) >= 32:
                return {'CANCELLED'}
            layer.masks.add()
        elif self.index < len(layer.masks):
            layer.masks.remove(self.index)
        ops.rebuild_live_composite(obj)
        return {'FINISHED'}


class GTATOOLS_OT_bake_diagnose(bpy.types.Operator):
    bl_idname = 'gtatools.bake_diagnose'
    bl_label = 'Проверить запекание'
    bl_description = 'Проверить UV и конфликты выделения без изменения развёртки'
    bl_options = {'REGISTER'}

    def execute(self, context):
        obj = _mesh_object(context)
        if obj is None:
            return {'CANCELLED'}
        obj.update_from_editmode()
        uv = obj.data.uv_layers.active
        if uv is None:
            self.report({'ERROR'}, T('Нет активной UV-карты'))
            return {'CANCELLED'}
        me = obj.data
        faces = {p.index: [tuple(uv.data[i].uv) for i in p.loop_indices] for p in me.polygons}
        me.calc_loop_triangles()
        triangles = [(t.polygon_index, [tuple(uv.data[i].uv) for i in t.loops]) for t in me.loop_triangles]
        report = diagnose_uv(faces, triangles)
        layer = _layer(context)
        s = context.scene.inu_settings
        domain = (layer.normal_bevel_selection if layer and layer.map_id == 'NORMAL'
                  and layer.normal_bevel else ('FACE' if s.gtatools_bake_selected_faces else 'EDGE'))
        use_selection = bool(layer and ((layer.map_id == 'NORMAL' and layer.normal_bevel)
            or (ops.uses_bevel_mask(layer.map_id, layer.effect_basis, layer.masks)
                and (s.gtatools_bake_selected_edges or s.gtatools_bake_selected_faces))))
        report['conflict'] = selection_uv_conflicts(faces, {
            p.index: [i for i, loop_index in enumerate(p.loop_indices)
                      if (p.select if domain == 'FACE' else me.edges[me.loops[loop_index].edge_index].select)]
            for p in me.polygons}) if use_selection else []
        report['uv'] = uv.name
        from ..tools.bake.bake_workflow import mesh_digest
        report['mesh'] = mesh_digest(obj, uv.name)
        report['normal_pixels'] = []
        if layer and layer.map_id == 'NORMAL':
            from ..tools import bake as B
            image = bpy.data.images.get(f"{obj.get('inu_bake_base', '')}_{ops._lkey(layer)}")
            if image:
                import numpy as np
                pixels = B.read_image_to_numpy(image)
                h, w = pixels.shape[:2]
                for index, points in faces.items():
                    if index in report['degenerate']:
                        continue
                    centre = np.mean(points, axis=0)
                    samples = [centre] + [centre*.15 + np.asarray(p)*.85 for p in points]
                    for u, v in samples:
                        rgb = pixels[min(h-1, max(0, int(v*h))), min(w-1, max(0, int(u*w))), :3]
                        length = np.linalg.norm(rgb*2.-1.)
                        if not np.isfinite(length) or length < .65 or length > 1.35:
                            report['normal_pixels'].append(index)
                            break
        obj['inu_bake_diagnostics'] = json.dumps(report)
        self.report({'INFO'}, T('Проверка UV завершена'))
        return {'FINISHED'}


class GTATOOLS_OT_bake_diagnostic_select(bpy.types.Operator):
    bl_idname = 'gtatools.bake_diagnostic_select'
    bl_label = 'Выделить проблемные грани'
    bl_options = {'REGISTER', 'UNDO'}
    category: StringProperty()

    def execute(self, context):
        obj = _mesh_object(context)
        if obj is None:
            return {'CANCELLED'}
        data = json.loads(obj.get('inu_bake_diagnostics', '{}'))
        # Never apply stored face indices after topology/UV changes.
        from ..tools.bake.bake_workflow import mesh_digest
        if data.get('mesh') and data['mesh'] != mesh_digest(obj, data.get('uv', '')):
            self.report({'WARNING'}, T('Повторите проверку после изменения модели'))
            return {'CANCELLED'}
        chosen = set(data.get(self.category, ()))
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        for vert in bm.verts:
            vert.select_set(False)
        for edge in bm.edges:
            edge.select_set(False)
        for face in bm.faces:
            face.select_set(face.index in chosen)
        bm.select_mode = {'FACE'}
        bm.select_flush_mode()
        context.tool_settings.mesh_select_mode = (False, False, True)
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        return {'FINISHED'}


class GTATOOLS_OT_bake_preset_save(bpy.types.Operator, ExportHelper):
    bl_idname = 'gtatools.bake_preset_save'
    bl_label = 'Сохранить пресет слоёв'
    filename_ext = '.json'
    filter_glob: StringProperty(default='*.json', options={'HIDDEN'})

    def invoke(self, context, event):
        self.filepath = 'BakeStack.json'
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        obj = _mesh_object(context)
        if not obj or not obj.inu.gtatools_bake_layers:
            return {'CANCELLED'}
        try:
            self.filepath = bpy.path.ensure_ext(self.filepath, '.json')
            with open(self.filepath, 'w', encoding='utf8') as out:
                json.dump(stack_data(obj.inu.gtatools_bake_layers), out, ensure_ascii=False, indent=2)
        except (OSError, ValueError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class GTATOOLS_OT_bake_preset_load(bpy.types.Operator, ImportHelper):
    bl_idname = 'gtatools.bake_preset_load'
    bl_label = 'Загрузить пресет слоёв'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = '.json'
    filter_glob: StringProperty(default='*.json', options={'HIDDEN'})
    replace: BoolProperty(name=T('Заменить текущие слои'), default=False)

    def execute(self, context):
        obj = _mesh_object(context)
        if obj is None:
            return {'CANCELLED'}
        try:
            with open(self.filepath, encoding='utf8') as source:
                data = json.load(source)
            _apply_rows(obj, data, self.replace)
        except (OSError, ValueError, TypeError, AttributeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class GTATOOLS_OT_bake_stack_copy(bpy.types.Operator):
    bl_idname = 'gtatools.bake_stack_copy'
    bl_label = 'Скопировать слои на выделенные'
    bl_description = 'Перенести настройки и связи масок; запечённые изображения и области не копируются'
    bl_options = {'REGISTER', 'UNDO'}
    replace: BoolProperty(name=T('Заменить текущие слои'), default=False)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _mesh_object(context)
        if obj is None or not obj.inu.gtatools_bake_layers:
            return {'CANCELLED'}
        data = stack_data(obj.inu.gtatools_bake_layers)
        targets = [other for other in context.selected_objects if other != obj and other.type == 'MESH']
        for other in targets:
            _apply_rows(other, data, self.replace)
        self.report({'INFO'}, T('Настройки перенесены: {0}').format(len(targets)))
        return {'FINISHED'}


class GTATOOLS_OT_bake_batch(ops.BakeJobDriver, bpy.types.Operator):
    bl_idname = 'gtatools.bake_batch'
    bl_label = 'Запечь выделенные модели'
    bl_description = 'Последовательно запечь стеки выделенных моделей; Esc останавливает очередь'
    bl_options = {'REGISTER', 'UNDO'}
    only_uid = ''
    only_map_id = ''
    _gen = None
    _timer = None

    @classmethod
    def poll(cls, context):
        return _mesh_object(context) is not None

    only_stale: BoolProperty(name=T('Только устаревшие слои'), default=True)

    def _bake_iter(self, context):
        from ..tools.bake.bake_maps import find_hilow_pair, HI_SUFFIX, LOW_SUFFIX
        targets, seen = [], set()
        original = context.view_layer.objects.active
        selected = list(context.selected_objects)
        if context.mode != 'OBJECT':
            self.report({'ERROR'}, T('Для очереди перейдите в объектный режим'))
            return {'CANCELLED'}
        s = context.scene.inu_settings
        if s.gtatools_bake_mode == 'CAMERA':
            self.report({'ERROR'}, T('Очередь поддерживает UV → UV и Hi → Low'))
            return {'CANCELLED'}
        for obj in selected:
            if obj.type != 'MESH':
                continue
            if s.gtatools_bake_mode == 'HILOW':
                high, low = find_hilow_pair(obj, HI_SUFFIX, LOW_SUFFIX)
                if high is None or low is None:
                    self.report({'ERROR'}, T('Не найдена пара Hi/Low: {0}').format(obj.name))
                    return {'CANCELLED'}
                obj = low
            if obj.as_pointer() not in seen:
                seen.add(obj.as_pointer())
                targets.append(obj)
        total = sum(sum(l.enabled and l.map_id != 'PAINT' for l in o.inu.gtatools_bake_layers) for o in targets)
        done = 0
        try:
            for obj in targets:
                context.view_layer.objects.active = obj
                edge_selection = [e.select for e in obj.data.edges]
                face_selection = [p.select for p in obj.data.polygons]
                try:
                    for layer in obj.inu.gtatools_bake_layers:
                        if not layer.enabled or layer.map_id == 'PAINT':
                            continue
                        uv = obj.data.uv_layers.active
                        image = bpy.data.images.get(f"{obj.get('inu_bake_base', '')}_{ops._lkey(layer)}")
                        # A queued layer uses its remembered area, independently of other layers.
                        if ops._has_bevel_selection(obj, ops._lkey(layer), 'EDGE'):
                            indices = set(ops._stored_bevel_indices(obj, ops._lkey(layer), 'EDGE'))
                            for edge in obj.data.edges:
                                edge.select = edge.index in indices
                        if ops._has_bevel_selection(obj, ops._lkey(layer), 'FACE'):
                            indices = set(ops._stored_bevel_indices(obj, ops._lkey(layer), 'FACE'))
                            for face in obj.data.polygons:
                                face.select = face.index in indices
                        status = stamp_status(image, bake_stamp(obj, s, layer, uv.name if uv else ''))
                        if self.only_stale and status == 'READY':
                            done += 1
                            continue
                        self.only_uid, self.only_map_id = ops._lkey(layer), ''
                        gen = ops.GTATOOLS_OT_bake_run._bake_iter(self, context)
                        try:
                            while True:
                                next(gen)
                                yield done, max(total, 1), obj.name + ': ' + layer.map_id
                        except StopIteration as result:
                            if result.value != {'FINISHED'}:
                                return {'CANCELLED'}
                        finally:
                            gen.close()
                        done += 1
                        yield done, max(total, 1), obj.name
                finally:
                    for edge, value in zip(obj.data.edges, edge_selection):
                        edge.select = value
                    for face, value in zip(obj.data.polygons, face_selection):
                        face.select = value
        finally:
            self.only_uid = ''
            for obj in context.view_layer.objects:
                obj.select_set(obj in selected)
            context.view_layer.objects.active = original
        return {'FINISHED'}


class GTATOOLS_OT_bake_game_preview(bpy.types.Operator):
    bl_idname = 'gtatools.bake_game_preview'
    bl_label = 'Проверить игровую текстуру'
    bl_description = 'Показать сведённый RGB и альфу в выбранном размере, не меняя исходные карты'
    bl_options = {'REGISTER'}
    original: BoolProperty(name=T('Показать исходные материалы'), default=False)

    def execute(self, context):
        obj = _mesh_object(context)
        if obj is None:
            return {'CANCELLED'}
        if self.original:
            if obj.get('inu_bake_preview_on'):
                ops._restore_materials(obj)
            return {'FINISHED'}
        base = obj.get('inu_bake_base', '')
        # Procedural export must see original materials, never its own preview.
        image = ops._composite_stack_image(obj.inu, base, ops._preview_material_name(obj, 'GameImage'))
        if image is None:
            self.report({'ERROR'}, T('Нет запечённых карт'))
            return {'CANCELLED'}
        settings = context.scene.inu_settings
        target = int(settings.gtatools_bake_game_size)
        if target:
            w, h = image.size
            ratio = min(1., target/max(w, h))
            image.scale(max(1, round(w*ratio)), max(1, round(h*ratio)))
        mip = int(settings.gtatools_bake_game_mip)
        if mip:
            w, h = image.size
            image.scale(max(1, w//(2**mip)), max(1, h//(2**mip)))
        image.pack()
        ops._snapshot_materials(obj)
        mat = ops._build_single_image_mat(image, obj.get('inu_bake_uv', ''), None,
                                         ops._preview_material_name(obj, 'Game'))
        tex = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
        emit = next(n for n in mat.node_tree.nodes if n.type == 'EMISSION')
        if settings.gtatools_bake_game_alpha:
            mat.node_tree.links.new(tex.outputs['Alpha'], emit.inputs['Color'])
        else:
            from ..tools import compat
            nt = mat.node_tree
            trans = nt.nodes.new('ShaderNodeBsdfTransparent')
            mix = nt.nodes.new('ShaderNodeMixShader')
            out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
            nt.links.new(tex.outputs['Alpha'], mix.inputs[0])
            nt.links.new(trans.outputs[0], mix.inputs[1])
            nt.links.new(emit.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs['Surface'])
            compat.make_material_alpha(mat)
        ops._assign_material(obj, mat, obj.get('inu_bake_uv', ''))
        # Freeze the inspected image until the user explicitly refreshes it.
        obj['inu_bake_mode_live'] = 0
        obj['inu_bake_preview_kind'] = 'game'
        ops._show_image(context, image)
        return {'FINISHED'}


CLASSES = (GTATOOLS_OT_bake_mask_edit, GTATOOLS_OT_bake_diagnose,
    GTATOOLS_OT_bake_diagnostic_select, GTATOOLS_OT_bake_preset_save,
    GTATOOLS_OT_bake_preset_load, GTATOOLS_OT_bake_stack_copy,
    GTATOOLS_OT_bake_batch, GTATOOLS_OT_bake_game_preview)
