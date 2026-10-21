"""Pixel-based Hi -> Low projection through alpha cards. No mesh edits.

Native bake projection stops at geometry before evaluating its shader. This
path follows each ray through transparent pixels and composites the surfaces
behind them. It samples the image/colour nodes used by GTA albedo materials.
"""
import math
import numpy as np


def _projection_error(message, *args):
    from ... import T
    return RuntimeError(T(message).format(*args))


def sample_image(pixels, uv, extension='REPEAT', nearest=False):
    h, w = pixels.shape[:2]
    u, v = float(uv[0]), float(uv[1])
    if extension == 'CLIP' and not (0. <= u <= 1. and 0. <= v <= 1.):
        return np.zeros(4)
    def address(i, size):
        if extension == 'REPEAT':
            return i % size
        if extension == 'MIRROR':
            i %= 2*size
            return min(i, 2*size-1-i)
        return min(max(i, 0), size-1)
    if nearest:
        return pixels[address(math.floor(v*h), h), address(math.floor(u*w), w)]
    x, y = u*w-.5, v*h-.5
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x-ix, y-iy
    a, b = pixels[address(iy, h), address(ix, w)], pixels[address(iy, h), address(ix+1, w)]
    c, d = pixels[address(iy+1, h), address(ix, w)], pixels[address(iy+1, h), address(ix+1, w)]
    return (a*(1.-fx)+b*fx)*(1.-fy)+(c*(1.-fx)+d*fx)*fy


def sample_image_batch(pixels, uv, extension='REPEAT', nearest=False):
    h, w = pixels.shape[:2]
    uv = np.asarray(uv)[:, :2]
    def address(indices, size):
        if extension == 'REPEAT':
            return indices % size
        if extension == 'MIRROR':
            indices %= 2*size
            return np.minimum(indices, 2*size-1-indices)
        return np.clip(indices, 0, size-1)
    if nearest:
        xy = np.floor(uv*(w, h)).astype(np.intp)
        result = pixels[address(xy[:,1], h), address(xy[:,0], w)].copy()
    else:
        xy = uv*(w, h)-.5
        ij = np.floor(xy).astype(np.intp)
        fx, fy = (xy-ij).T
        fx, fy = fx[:,None], fy[:,None]
        a = pixels[address(ij[:,1], h), address(ij[:,0], w)]
        b = pixels[address(ij[:,1], h), address(ij[:,0]+1, w)]
        c = pixels[address(ij[:,1]+1, h), address(ij[:,0], w)]
        d = pixels[address(ij[:,1]+1, h), address(ij[:,0]+1, w)]
        result = (a*(1.-fx)+b*fx)*(1.-fy)+(c*(1.-fx)+d*fx)*fy
    if extension == 'CLIP':
        result[np.any((uv < 0.) | (uv > 1.), axis=1)] = 0.
    return result


def over_sample(accumulator, colour, alpha):
    """Front-to-back premultiplied accumulation, including partial opacity."""
    weight = (1.-accumulator[...,3:4])*np.clip(alpha, 0., 1.)
    accumulator[...,:3] += np.asarray(colour)[...,:3]*weight
    accumulator[...,3:4] += weight
    return accumulator


def straight_sample(accumulator):
    out = accumulator.copy()
    out[...,:3] /= np.maximum(out[...,3:4], 1e-8)
    return out


def uv_fragments(points, width, height):
    """Bounded row chunks of target pixel indices and barycentric weights."""
    p = np.asarray(points, dtype=np.float64)*(width, height)
    a, b, c = p
    denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(denominator) < 1e-12:
        return
    x0, y0 = np.maximum(np.floor(p.min(axis=0)), (0, 0)).astype(int)
    x1, y1 = np.minimum(np.ceil(p.max(axis=0)), (width, height)).astype(int)
    if x1 <= x0 or y1 <= y0:
        return
    xs = np.arange(x0, x1)[None, :]+.5
    for start in range(y0, y1, 32):
        ys = np.arange(start, min(start+32, y1))[:, None]+.5
        wa = ((b[1]-c[1])*(xs-c[0])+(c[0]-b[0])*(ys-c[1]))/denominator
        wb = ((c[1]-a[1])*(xs-c[0])+(a[0]-c[0])*(ys-c[1]))/denominator
        wc = 1.-wa-wb
        inside = (wa >= -1e-8) & (wb >= -1e-8) & (wc >= -1e-8)
        rows, cols = np.nonzero(inside)
        yield rows+start, cols+x0, np.column_stack((wa[inside], wb[inside], wc[inside]))


def extend_margin(pixels, coverage, margin):
    """Extend only beyond Low UV faces; never fill transparent holes inside."""
    filled = coverage.copy()
    h, w = coverage.shape
    for _ in range(min(int(margin), max(w, h))):
        old = filled.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            dst = (slice(max(0, dy), min(h, h+dy)), slice(max(0, dx), min(w, w+dx)))
            src = (slice(max(0, -dy), min(h, h-dy)), slice(max(0, -dx), min(w, w-dx)))
            take = ~filled[dst] & old[src]
            pixels[dst][take] = pixels[src][take]
            filled[dst][take] = True
        if np.array_equal(old, filled):
            break
    return pixels


class MaterialReader:
    def __init__(self):
        self.images = {}

    def pixels(self, image):
        key = image.as_pointer()
        if key not in self.images:
            from .bake_core import read_image_to_numpy
            self.images[key] = read_image_to_numpy(image)
        return self.images[key]

    def surface(self, material):
        tree = material.node_tree if material and getattr(material, 'use_nodes', False) else None
        if tree is None:
            return None
        outputs = [n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL']
        output = next((n for n in outputs if n.is_active_output), outputs[0] if outputs else None)
        if output and output.inputs['Surface'].is_linked:
            return output.inputs['Surface'].links[0].from_socket
        return None

    def needs_projection(self, materials):
        for material in materials:
            tree = material.node_tree if material and getattr(material, 'use_nodes', False) else None
            if tree:
                for node in tree.nodes:
                    if node.type in {'BSDF_TRANSPARENT', 'MIX_SHADER'}:
                        return True
                    if node.type == 'BSDF_PRINCIPLED':
                        alpha = node.inputs.get('Alpha')
                        if alpha and (alpha.is_linked or float(alpha.default_value) < 1.-1e-6):
                            return True
        return False

    def shade(self, material, hit, alpha_only=False):
        socket = self.surface(material)
        if socket is None:
            colour = tuple(material.diffuse_color) if material else (1., 1., 1., 1.)
            return np.asarray(colour[:3]), colour[3]
        cache = {}
        def value(sock):
            if not sock.is_linked:
                default = sock.default_value
                return np.asarray(default, dtype=float) if hasattr(default, '__len__') else float(default)
            return output(sock.links[0].from_socket)
        def scalar(v):
            a = np.asarray(v)
            if a.ndim == 0:
                return float(a)
            if a.ndim == 2:
                return a if a.shape[1] == 1 else (a[:,:3] @ (.2126, .7152, .0722))[:,None]
            return float(np.dot(a[:3], (.2126, .7152, .0722)))
        def colour(v):
            a = np.asarray(v)
            if a.ndim == 2:
                return np.repeat(a, 3, axis=1) if a.shape[1] == 1 else a[:,:3]
            return np.full(3, a) if a.ndim == 0 else a[:3]
        def blend(node, a, b, factor):
            from .bake_composite import _BLEND
            operation = node.blend_type
            if operation == 'MIX':
                mixed = b
            else:
                fn = _BLEND.get(operation)
                if fn is None:
                    raise _projection_error('Неподдерживаемый режим смешивания альбедо: {0}', operation)
                mixed = fn(a, b)
            result = a*(1.-factor)+mixed*factor
            return np.clip(result, 0., 1.) if getattr(node, 'use_clamp', False) else result
        def output(sock):
            key = sock.as_pointer()
            if key in cache:
                return cache[key]
            node, name = sock.node, sock.name
            kind = node.type
            if kind == 'TEX_IMAGE':
                if node.projection != 'FLAT':
                    raise _projection_error('Для альфа-проекции нужна плоская проекция изображения')
                coords = value(node.inputs['Vector']) if node.inputs['Vector'].is_linked else hit.uv('')
                if node.image is None:
                    result = 1. if name == 'Alpha' else np.zeros(3)
                else:
                    sample = sample_image_batch if np.ndim(coords) == 2 else sample_image
                    rgba = sample(self.pixels(node.image), coords, node.extension,
                                  node.interpolation == 'Closest')
                    if name == 'Alpha':
                        result = 1. if node.image.alpha_mode == 'NONE' else rgba[...,3:] if rgba.ndim == 2 else float(rgba[3])
                    else:
                        from .bake_composite import srgb_to_linear
                        result = rgba[...,:3]
                        if not node.image.is_float and node.image.colorspace_settings.name == 'sRGB':
                            result = srgb_to_linear(result)
            elif kind == 'UVMAP':
                result = hit.uv(node.uv_map)
            elif kind == 'TEX_COORD' and name == 'UV':
                result = hit.uv('')
            elif kind == 'MAPPING':
                from mathutils import Euler
                coordinates = value(node.inputs['Vector'])
                location, rotation, scale = (value(node.inputs[k]) for k in ('Location', 'Rotation', 'Scale'))
                if np.ndim(rotation) != 1 or node.vector_type not in {'POINT', 'VECTOR'}:
                    raise _projection_error('Неподдерживаемое преобразование координат изображения')
                matrix = np.asarray(Euler(rotation).to_matrix())
                result = np.asarray(coordinates)*scale @ matrix.T
                if node.vector_type == 'POINT':
                    result += location
            elif kind == 'VECT_MATH':
                a, b = value(node.inputs[0]), value(node.inputs[1])
                if node.operation == 'ADD': result = np.asarray(a)+b
                elif node.operation == 'SUBTRACT': result = np.asarray(a)-b
                elif node.operation == 'MULTIPLY': result = np.asarray(a)*b
                elif node.operation == 'SCALE': result = np.asarray(a)*scalar(value(node.inputs['Scale']))
                else: raise _projection_error('Неподдерживаемая векторная операция изображения: {0}', node.operation)
            elif kind in {'VERTEX_COLOR', 'COLOR_ATTRIBUTE', 'ATTRIBUTE'}:
                attribute = getattr(node, 'layer_name', '') or getattr(node, 'attribute_name', '')
                rgba = hit.attribute(attribute)
                result = (rgba[...,3:] if rgba.ndim == 2 else float(rgba[3])) if name == 'Alpha' else scalar(rgba) if name == 'Fac' else rgba[...,:3]
            elif kind in {'RGB', 'VALUE'}:
                result = np.asarray(sock.default_value) if kind == 'RGB' else float(sock.default_value)
            elif kind == 'REROUTE':
                result = value(node.inputs[0])
            elif kind == 'MIX_RGB':
                result = blend(node, colour(value(node.inputs[1])), colour(value(node.inputs[2])),
                               np.clip(scalar(value(node.inputs[0])), 0., 1.))
            elif kind == 'MIX' and node.data_type == 'RGBA':
                result = blend(node, colour(value(node.inputs[6])), colour(value(node.inputs[7])),
                               np.clip(scalar(value(node.inputs[0])), 0., 1.))
            elif kind == 'RGBTOBW':
                result = scalar(value(node.inputs[0]))
            elif kind == 'GAMMA':
                result = np.maximum(colour(value(node.inputs['Color'])), 0.)**scalar(value(node.inputs['Gamma']))
            elif kind == 'HUE_SAT':
                from .bake_composite import _rgb_to_hsv, _hsv_to_rgb
                c = colour(value(node.inputs['Color']))
                h, s, v = _rgb_to_hsv(c)
                hue, sat, val = (np.asarray(scalar(value(node.inputs[k]))).squeeze()
                                 for k in ('Hue', 'Saturation', 'Value'))
                factor = np.clip(scalar(value(node.inputs['Fac'])), 0., 1.)
                result = c*(1.-factor)+_hsv_to_rgb((h+hue-.5) % 1.,
                    np.clip(s*sat, 0., 1.), v*val)*factor
            elif kind == 'VALTORGB':
                fac = scalar(value(node.inputs['Fac']))
                if np.ndim(fac):
                    rgba = np.asarray([node.color_ramp.evaluate(float(v)) for v in np.ravel(fac)])
                    result = rgba[:,3:] if name == 'Alpha' else rgba[:,:3]
                else:
                    rgba = node.color_ramp.evaluate(fac)
                    result = rgba[3] if name == 'Alpha' else np.asarray(rgba[:3])
            elif kind == 'MATH':
                a, b = scalar(value(node.inputs[0])), scalar(value(node.inputs[1]))
                operations = {'MULTIPLY': lambda: a*b, 'ADD': lambda: a+b, 'SUBTRACT': lambda: a-b,
                    'DIVIDE': lambda: np.divide(a, b, out=np.zeros(np.broadcast_shapes(np.shape(a), np.shape(b))), where=np.asarray(b) != 0),
                    'MINIMUM': lambda: np.minimum(a, b),
                    'MAXIMUM': lambda: np.maximum(a, b), 'GREATER_THAN': lambda: np.asarray(a > b, dtype=float),
                    'LESS_THAN': lambda: np.asarray(a < b, dtype=float), 'POWER': lambda: np.maximum(a, 0.)**b,
                    'MULTIPLY_ADD': lambda: a*b+scalar(value(node.inputs[2])),
                    'ABSOLUTE': lambda: abs(a)}
                if node.operation not in operations:
                    raise _projection_error('Неподдерживаемая математическая операция альфы: {0}', node.operation)
                result = operations[node.operation]()
                if node.use_clamp:
                    result = np.clip(result, 0., 1.)
            elif kind == 'BRIGHTCONTRAST':
                c = colour(value(node.inputs['Color']))
                bright, contrast = scalar(value(node.inputs['Bright'])), scalar(value(node.inputs['Contrast']))
                if np.any(np.abs(bright)+np.abs(contrast) > 1e-8):
                    raise _projection_error('Примените яркость и контраст альбедо после проекции')
                result = c
            else:
                raise _projection_error('Неподдерживаемая нода материала для альфа-проекции: {0}', node.bl_idname)
            cache[key] = result
            return result
        def shader(sock):
            node = sock.node
            if node.type == 'REROUTE' and node.inputs[0].is_linked:
                return shader(node.inputs[0].links[0].from_socket)
            if node.type == 'BSDF_TRANSPARENT':
                return np.zeros(3), 0.
            if node.type == 'BSDF_PRINCIPLED':
                alpha = np.clip(scalar(value(node.inputs['Alpha'])), 0., 1.)
                rgb = np.zeros(3) if alpha_only or np.all(alpha <= 1e-8) else colour(value(node.inputs['Base Color']))
                return rgb, alpha
            if node.type == 'MIX_SHADER':
                factor = np.clip(scalar(value(node.inputs[0])), 0., 1.)
                a, aa = shader(node.inputs[1].links[0].from_socket) if node.inputs[1].is_linked else (np.zeros(3), 0.)
                b, ab = shader(node.inputs[2].links[0].from_socket) if node.inputs[2].is_linked else (np.zeros(3), 0.)
                alpha = aa*(1.-factor)+ab*factor
                return (a*aa*(1.-factor)+b*ab*factor)/np.maximum(alpha, 1e-8), alpha
            if node.type in {'EMISSION', 'BSDF_DIFFUSE'}:
                return np.zeros(3) if alpha_only else colour(value(node.inputs['Color'])), 1.
            raise _projection_error('Неподдерживаемый шейдер для альфа-проекции: {0}', node.bl_idname)
        return shader(socket)


class HitBatch:
    def __init__(self, source, triangles, bary, vertices=None):
        self.source, self.bary = source, bary
        self.loops = np.asarray([t.loops[:] for t in triangles], np.intp) if vertices is None else triangles
        self.vertices = np.asarray([t.vertices[:] for t in triangles], np.intp) if vertices is None else vertices

    def uv(self, name):
        name = name or self.source['uv_default']
        if name not in self.source['uvs']:
            raise _projection_error('Не найдена UV-карта Hi: {0}', name)
        xy = np.einsum('ij,ijk->ik', self.bary, self.source['uvs'][name][self.loops])
        return np.column_stack((xy, np.zeros(len(xy))))

    def attribute(self, name):
        name = name or self.source['colour_default']
        if name not in self.source['colours']:
            raise _projection_error('Не найден цветовой атрибут Hi: {0}', name)
        domain, values = self.source['colours'][name]
        return np.einsum('ij,ijk->ik', self.bary, values[self.vertices if domain == 'POINT' else self.loops])


def bake_alpha_projection(context, low, image, *, sources, map_id, target_uv,
                          cage_extrusion, max_ray, margin):
    """Return False for ordinary opaque bakes; otherwise write the pixel result."""
    reader = MaterialReader()
    sources = tuple(o for o in (sources or context.selected_objects) if o is not low and o.type == 'MESH')
    if not reader.needs_projection([s.material for o in sources for s in o.material_slots]):
        return False
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from .bake_core import write_numpy_to_image
    from .bake_composite import linear_to_srgb
    evaluated, visibility = [], []
    modifiers = []
    try:
        cage_obj = context.scene.render.bake.cage_object
        for obj in dict.fromkeys((*sources, low, cage_obj)):
            if obj is None:
                continue
            for modifier in obj.modifiers:
                modifiers.append((modifier, modifier.show_viewport))
                modifier.show_viewport = modifier.show_render
        for obj in sources:
            visibility.append((obj, obj.hide_get(), obj.hide_viewport))
            obj.hide_viewport = False
            obj.hide_set(False)
        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()
        def snapshot(obj):
            ev = obj.evaluated_get(depsgraph)
            me = ev.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            evaluated.append(ev)
            me.calc_loop_triangles()
            return me
        mesh = snapshot(low)
        # BVH/mathutils use float32. Applying a large world translation before
        # stepping through alpha can round the step to zero. Transform in double
        # precision around the Low centre, then give only nearby values to BVH.
        low_matrix = np.asarray(low.matrix_world, dtype=np.float64)
        low_coords = np.asarray([v.co[:] for v in mesh.vertices], dtype=np.float64)
        centre = (low_coords.min(axis=0)+low_coords.max(axis=0))*.5 if len(low_coords) else np.zeros(3)
        reference = low_matrix[:3,:3] @ centre+low_matrix[:3,3]

        vertices, triangles, records = [], [], []
        for obj in sources:
            me = snapshot(obj)
            offset = len(vertices)
            matrix = np.asarray(obj.matrix_world, dtype=np.float64)
            coords = np.asarray([v.co[:] for v in me.vertices], dtype=np.float64).reshape(-1, 3)
            transformed = coords @ matrix[:3,:3].T+(matrix[:3,3]-reference)
            vertices.extend(Vector(point) for point in transformed)
            uvs = {}
            for uv in me.uv_layers:
                values = np.empty(len(me.loops)*2, np.float32)
                uv.data.foreach_get('uv', values)
                uvs[uv.name] = values.reshape(-1, 2)
            colours = {}
            for attr in me.color_attributes:
                values = np.empty(len(attr.data)*4, np.float32)
                attr.data.foreach_get('color', values)
                colours[attr.name] = attr.domain, values.reshape(-1, 4)
            src = dict(uvs=uvs, colours=colours,
                uv_default=next((u.name for u in me.uv_layers if u.active_render),
                                me.uv_layers.active.name if me.uv_layers.active else ''),
                colour_default=me.color_attributes.active_color.name if me.color_attributes.active_color else '')
            for tri in me.loop_triangles:
                triangles.append(tuple(v+offset for v in tri.vertices))
                material = obj.material_slots[tri.material_index].material if tri.material_index < len(obj.material_slots) else None
                records.append((src, tri, material))
        tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
        triangle_points = np.asarray(vertices)[np.asarray(triangles, dtype=np.intp).reshape(-1, 3)]
        anchors = triangle_points[:,0]
        edge_b, edge_c = triangle_points[:,1]-anchors, triangle_points[:,2]-anchors
        bb = np.einsum('ij,ij->i', edge_b, edge_b)
        bc = np.einsum('ij,ij->i', edge_b, edge_c)
        cc = np.einsum('ij,ij->i', edge_c, edge_c)
        determinant = bb*cc-bc*bc
        inverse = np.divide(1., determinant, out=np.zeros_like(determinant), where=determinant != 0.)
        bary_b = (cc[:,None]*edge_b-bc[:,None]*edge_c)*inverse[:,None]
        bary_c = (bb[:,None]*edge_c-bc[:,None]*edge_b)*inverse[:,None]
        triangle_loops = np.asarray([t.loops[:] for _, t, _ in records], np.intp)
        triangle_vertices = np.asarray([t.vertices[:] for _, t, _ in records], np.intp)
        group_keys = [(id(src), material.as_pointer() if material else 0) for src, _, material in records]
        uv = mesh.uv_layers.get(target_uv) if target_uv else mesh.uv_layers.active
        if uv is None:
            raise _projection_error('Не найдена UV-карта Low')
        w, h = image.size
        pixels = np.zeros((h, w, 4), np.float32)
        coverage = np.zeros((h, w), bool)
        normals = np.asarray(low.matrix_world.inverted_safe().transposed().to_3x3())
        cage_mesh = snapshot(cage_obj) if cage_obj and context.scene.render.bake.use_cage else None
        if cage_mesh and len(cage_mesh.loop_triangles) != len(mesh.loop_triangles):
            raise _projection_error('Топология Low и клетки проекции различается')
        extent = max((max(v[i] for v in vertices)-min(v[i] for v in vertices) for i in range(3)), default=1.) if vertices else 1.
        epsilon = max(1e-7, extent*1e-7)
        def trace(origins, directions):
            count = len(origins)
            accumulator = np.zeros((count, 4), np.float64)
            travelled = np.zeros(count)
            active = np.ones(count, bool)
            cursors = list(origins)
            for _ in range(128):
                groups = {}
                locations = np.empty((count, 3))
                hits = np.full(count, -1, np.intp)
                for i in np.flatnonzero(active):
                    remaining = max_ray-travelled[i] if max_ray > 0. else 1e30
                    if remaining <= 0.:
                        continue
                    location, _, index, distance = tree.ray_cast(cursors[i], directions[i], remaining)
                    if index is None:
                        continue
                    locations[i] = location
                    hits[i] = index
                    groups.setdefault(group_keys[index], []).append(i)
                    travelled[i] += distance+epsilon
                    cursors[i] = location+directions[i]*epsilon
                active[:] = False
                for indices in groups.values():
                    indices = np.asarray(indices, np.intp)
                    selected = hits[indices]
                    src, _, material = records[selected[0]]
                    delta = locations[indices]-anchors[selected]
                    wb = np.einsum('ij,ij->i', delta, bary_b[selected])
                    wc = np.einsum('ij,ij->i', delta, bary_c[selected])
                    weights = np.column_stack((1.-wb-wc, wb, wc))
                    batch = HitBatch(src, triangle_loops[selected], weights, triangle_vertices[selected])
                    rgb, alpha = reader.shade(material, batch, map_id == 'ALPHA')
                    alpha = np.broadcast_to(np.asarray(alpha).reshape(-1, 1), (len(indices), 1))
                    accumulator[indices] = over_sample(accumulator[indices], rgb, alpha)
                    active[indices] = accumulator[indices,3] < 1.-1e-6
                if not active.any():
                    break
            else:
                raise _projection_error('На пути луча запекания больше 128 прозрачных поверхностей')
            if map_id == 'ALPHA':
                return np.repeat(accumulator[:,3:4], 4, axis=1)
            accumulator = straight_sample(accumulator)
            if not image.is_float and image.colorspace_settings.name == 'sRGB':
                accumulator[:,:3] = linear_to_srgb(accumulator[:,:3])
            return accumulator
        for tri in mesh.loop_triangles:
            uv_points = [uv.data[i].uv[:] for i in tri.loops]
            coords = np.asarray([mesh.vertices[i].co[:] for i in tri.vertices])
            smooth = mesh.polygons[tri.polygon_index].use_smooth or context.scene.render.bake.use_cage
            vn = np.asarray([mesh.vertices[i].normal[:] if smooth else tri.normal[:] for i in tri.vertices])
            for rows, cols, weights in uv_fragments(uv_points, w, h):
                coverage[rows, cols] = True
                positions, directions = weights @ coords, weights @ vn
                if cage_mesh:
                    ct = cage_mesh.loop_triangles[tri.index]
                    cage_positions = weights @ np.asarray([cage_mesh.vertices[i].co[:] for i in ct.vertices])
                directions /= np.maximum(np.linalg.norm(directions, axis=1, keepdims=True), 1e-30)
                origins = (positions+directions*cage_extrusion) @ low_matrix[:3,:3].T+(low_matrix[:3,3]-reference)
                ray_directions = -directions @ normals.T
                if cage_mesh:
                    cage_matrix = np.asarray(cage_obj.matrix_world, dtype=np.float64)
                    origins = cage_positions @ cage_matrix[:3,:3].T+(cage_matrix[:3,3]-reference)
                    ray_directions = positions @ low_matrix[:3,:3].T+(low_matrix[:3,3]-reference)-origins
                ray_directions /= np.maximum(np.linalg.norm(ray_directions, axis=1, keepdims=True), 1e-30)
                origins = [Vector(point) for point in origins]
                ray_directions = [Vector(direction) for direction in ray_directions]
                pixels[rows, cols] = trace(origins, ray_directions)
        write_numpy_to_image(image, extend_margin(pixels, coverage, margin), pack=False)
        return True
    finally:
        for ev in reversed(evaluated):
            ev.to_mesh_clear()
        for modifier, viewport in reversed(modifiers):
            modifier.show_viewport = viewport
        for obj, hidden, viewport in reversed(visibility):
            obj.hide_set(hidden)
            obj.hide_viewport = viewport
