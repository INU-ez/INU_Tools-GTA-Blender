# INU_tools.ops.paintjob_ops
# Vehicle paintjob validator — checks that every material with paintjob
# alt textures (mat.inu.paintjob_alt_1 / _alt_2) has both alts set and
# a usable main image to derive the <base>_paintjob1/_paintjob2 names
# from. Surfaces problems via Operator.report so the user sees them in
# Blender's status bar and Info editor.

import bpy

from .. import T


def _material_main_image_name(mat):
    """Return the basename of the first connected TEX_IMAGE in this
    material, or None if there is no usable main texture. Mirrors the
    pass-1 logic in tools.txd_export.collect_textures."""
    if not mat.use_nodes or not mat.node_tree:
        return None
    for node in mat.node_tree.nodes:
        if node.type != 'TEX_IMAGE' or not node.image:
            continue
        if node.name in ("LM_Texture", "Lightmap_Texture"):
            continue
        # Reuse the addon's connectivity check so we agree with the
        # exporter on what counts as "the body texture".
        try:
            from ..tools.txd_export import is_node_connected
            if not is_node_connected(node):
                continue
        except Exception:
            pass
        from ..core.tex_name import clean_texture_name
        return clean_texture_name(node.image.name)
    return None


class GTATOOLS_OT_validate_paintjobs(bpy.types.Operator):
    """Проверить все материалы со слотами Paintjob:
    оба слота должны быть заполнены, и у материала должна быть основная
    текстура — иначе игра не подхватит paintjob в Pay'n'Spray."""
    bl_idname = "gtatools.validate_paintjobs"
    bl_label = "INU: Validate Paintjobs"
    bl_options = {'REGISTER'}

    def execute(self, context):
        problems = []
        ok_count = 0

        for mat in bpy.data.materials:
            inu = getattr(mat, 'inu', None)
            if inu is None:
                continue
            alt1 = getattr(inu, 'paintjob_alt_1', None)
            alt2 = getattr(inu, 'paintjob_alt_2', None)
            if not (alt1 or alt2):
                continue

            base = _material_main_image_name(mat)

            if not alt1:
                problems.append(
                    f"{mat.name}: " + T("заполнен только Paintjob 2 — нужны оба"))
            elif not alt2:
                problems.append(
                    f"{mat.name}: " + T("заполнен только Paintjob 1 — нужны оба"))
            elif not base:
                problems.append(
                    f"{mat.name}: " + T(
                        "нет основной текстуры — paintjob не к чему привязать"))
            else:
                ok_count += 1

        if not problems and ok_count == 0:
            self.report({'INFO'}, T("Paintjob'ов в сцене нет"))
            return {'FINISHED'}

        # Always log to console — easier to copy-paste full reports.
        print(f"[paintjob validator] OK: {ok_count}, problems: {len(problems)}")
        for p in problems:
            print(f"  ! {p}")

        if problems:
            self.report({'WARNING'},
                        f"{T('Paintjob проблем')}: {len(problems)}, "
                        f"{T('OK')}: {ok_count} " + T("(см. System Console)"))
        else:
            self.report({'INFO'},
                        f"{T('Все paintjob материалы OK')}: {ok_count}")
        return {'FINISHED'}


