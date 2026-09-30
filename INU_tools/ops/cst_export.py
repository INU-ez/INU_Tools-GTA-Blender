# INU_tools.ops.cst_export — export Blender objects to CST text format.

import os
import bpy

from ..core.col import ColModel
from ..core.cst import write_cst
from .col_export import (
    _collect_mesh, _collect_shadow_mesh, _collect_empty,
    _is_shadow_mesh, _compute_bounds, _prim_anchor, _refresh_for_prims,
)


def export_cst(filepath: str, objects, version: int = 3,
               model_name: str = "", empty: bool = False) -> ColModel:
    if not model_name:
        model_name = os.path.splitext(os.path.basename(filepath))[0]
    model = ColModel(version=version, model_name=model_name)
    if not empty:
        # Spheres/boxes relative to the COL mesh — as in col_export.
        anchor = _prim_anchor(objects)
        _refresh_for_prims(objects, anchor)
        for obj in objects:
            if obj.type == 'MESH':
                if _is_shadow_mesh(obj):
                    _collect_shadow_mesh(obj, model)
                else:
                    _collect_mesh(obj, model)
            elif obj.type == 'EMPTY':
                # Same sphere/box dispatcher as col_export — picks by
                # `empty_display_type`. CST is the text-format twin of
                # COL so it serialises the same `model.boxes` structure.
                _collect_empty(obj, model, anchor)
    model.bounds = _compute_bounds(model)
    write_cst(filepath, [model])
    return model




