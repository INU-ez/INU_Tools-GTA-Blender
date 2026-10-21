"""Deterministic UV rasterization of selected-edge masks, without Blender.

Overlapping and tiled faces contribute their maximum mask value. A black
face cannot erase an edge from a different copy of the same UV island.
"""
import math
import numpy as np

from .bake_composite import linear_to_srgb


def _box_max(values, radius):
    """Separable maximum filter in O(log(radius)) array passes."""
    result = values
    span = 2 * radius + 1
    for axis in (0, 1):
        padding = [(0, 0), (0, 0)]
        padding[axis] = (radius, radius)
        result = np.pad(result, padding)
        size = 1
        while size < span:
            shift = min(size, span - size)
            left, right = [slice(None)] * 2, [slice(None)] * 2
            left[axis], right[axis] = slice(None, -shift), slice(shift, None)
            result = np.maximum(result[tuple(left)], result[tuple(right)])
            size += shift
    return result


def rasterize_bevel_uv(uv, triangles, distances, radius, width, height, margin=0):
    """Interpolate CORNER distance fields and union all face contributions.

    Pixel centres and row order match Blender image buffers. Coordinates
    outside 0..1 repeat into the same tile, matching Image Texture Repeat.
    Large triangles are processed in row strips to bound temporary memory.
    """
    uv = np.asarray(uv, dtype=np.float64)
    distances = np.asarray(distances, dtype=np.float32)
    mask = np.zeros((height, width), dtype=np.float32)
    coverage = np.zeros((height, width), dtype=bool)
    safe_radius = max(float(radius), 1e-8)
    for triangle in triangles:
        indices = np.asarray(triangle, dtype=np.intp)
        points = uv[indices]
        if not np.isfinite(points).all():
            continue
        fields = distances[:, indices]
        lo, hi = np.floor(points.min(axis=0)).astype(int), np.ceil(points.max(axis=0)).astype(int)
        for tile_y in range(lo[1], hi[1]):
            for tile_x in range(lo[0], hi[0]):
                p = (points - (tile_x, tile_y)) * (width, height)
                a, b, c = p
                denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(denominator) < 1e-12:
                    continue
                x0, y0 = np.maximum(np.floor(p.min(axis=0)), (0, 0)).astype(int)
                x1, y1 = np.minimum(np.ceil(p.max(axis=0)), (width, height)).astype(int)
                if x1 <= x0 or y1 <= y0:
                    continue
                xs = np.arange(x0, x1, dtype=np.float64)[None, :] + 0.5
                row_step = max(1, min(128, 131072 // (x1 - x0)))
                for start in range(y0, y1, row_step):
                    stop = min(y1, start + row_step)
                    ys = np.arange(start, stop, dtype=np.float64)[:, None] + 0.5
                    wa = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / denominator
                    wb = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / denominator
                    wc = 1.0 - wa - wb
                    inside = (wa >= -1e-8) & (wb >= -1e-8) & (wc >= -1e-8)
                    coverage[start:stop, x0:x1] |= inside
                    if radius <= 0:
                        continue
                    closest = np.full(inside.shape, safe_radius, dtype=np.float32)
                    for field in fields:
                        value = wa * field[0] + wb * field[1] + wc * field[2]
                        np.minimum(closest, value, out=closest)
                    strength = np.clip(1.0 - closest / safe_radius, 0.0, 1.0)
                    strength[~inside] = 0.0
                    target = mask[start:stop, x0:x1]
                    np.maximum(target, strength, out=target)
    padding = max(0, min(int(margin), max(width, height)))
    if padding and np.any(mask):
        extended = _box_max(mask, padding)
        # Padding can never overwrite the interiors of other UV faces.
        mask = np.where(coverage, mask, extended)
        coverage |= mask > 0
    out = np.empty((height, width, 4), dtype=np.float32)
    out[..., :3] = linear_to_srgb(mask)[..., None]
    out[..., 3] = coverage
    return out
