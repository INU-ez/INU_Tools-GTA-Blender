"""Static lighting from baked RGB normals, flattened into GTA colour textures."""
import math


NORMAL_DEFAULTS = {
    'normal_lighting': True,
    'normal_light_mode': 'DIRECTIONAL',
    'normal_light_azimuth': -45.0,
    'normal_light_elevation': 50.0,
    'normal_ambient': .65,
    'normal_diffuse': .45,
    'normal_specular': .15,
    'normal_shininess': 32.0,
    'desaturate': False,
}

NORMAL_BEVEL_DEFAULTS = {
    'normal_bevel': False,
    'normal_bevel_selection': 'EDGE',
    'normal_bevel_width': .02,
    'normal_bevel_segments': 8,
    'normal_bevel_profile': .5,
}


def normal_bevel_area(obj, settings):
    mesh = obj.data
    if settings.get('normal_bevel_selection', 'EDGE') == 'FACE':
        faces = [face.index for face in mesh.polygons if face.select]
        edges = sorted({mesh.loops[i].edge_index for face in mesh.polygons if face.select
                        for i in face.loop_indices})
        return faces, edges
    return None, [edge.index for edge in mesh.edges if edge.select]


def normal_bevel_cage(obj, settings):
    """Keep generated-source rays near the selected edge neighbourhood.

    The Bevel modifier clamps oversized widths to the local geometry. Using
    the requested width as a cage offset can instead hit a neighbouring part.
    """
    mesh = obj.data
    _, selected = normal_bevel_area(obj, settings)
    chosen = set(selected)
    neighbourhood = set(chosen)
    for face in mesh.polygons:
        edges = {mesh.loops[i].edge_index for i in face.loop_indices}
        if edges & chosen:
            neighbourhood.update(edges)
    lengths = [(mesh.vertices[mesh.edges[i].vertices[0]].co
                - mesh.vertices[mesh.edges[i].vertices[1]].co).length
               for i in neighbourhood]
    shortest = min((length for length in lengths if length > 1e-8), default=0.)
    requested = settings.get('normal_bevel_width', .02) * 2
    return max(1e-5, min(requested, shortest * .25))


def make_normal_bevel_source(context, obj, settings):
    """Temporary high source from selected low edges; original mesh stays intact."""
    import bpy
    from ... import T
    _, edges = normal_bevel_area(obj, settings)
    if not edges:
        raise RuntimeError(T("Выделите рёбра или грани для скругления Normal Map"))
    source = obj.copy()
    source.data = obj.data.copy()
    source.name = obj.name + '__normal_source'
    context.scene.collection.objects.link(source)
    source.hide_render = False
    source.hide_set(False)
    try:
        weights = source.data.attributes.get('bevel_weight_edge')
        if weights is not None:
            source.data.attributes.remove(weights)
        weights = source.data.attributes.new('bevel_weight_edge', 'FLOAT', 'EDGE')
        chosen = set(edges)
        weights.data.foreach_set('value', [float(i in chosen) for i in range(len(weights.data))])
        for face in source.data.polygons:
            face.use_smooth = True
        # Keep untouched corners hard. Otherwise weighted smooth normals still
        # bend entire flat faces when only a subset of edges is bevelled.
        for edge in source.data.edges:
            edge.use_edge_sharp = True
        bevel = source.modifiers.new('INU Normal rounding', 'BEVEL')
        bevel.limit_method = 'WEIGHT'
        bevel.width = settings.get('normal_bevel_width', .02)
        bevel.segments = settings.get('normal_bevel_segments', 8)
        bevel.profile = settings.get('normal_bevel_profile', .5)
        bevel.harden_normals = True
        bevel.face_strength_mode = 'FSTR_ALL'
        weighted = source.modifiers.new('INU Normal planes', 'WEIGHTED_NORMAL')
        weighted.keep_sharp = True
        weighted.use_face_influence = True
    except Exception:
        mesh = source.data
        bpy.data.objects.remove(source, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        raise
    return source


def normal_light_directions(settings):
    azimuth = math.radians(settings.get('normal_light_azimuth', -45.0))
    elevation = math.radians(settings.get('normal_light_elevation', 50.0))
    light = (math.cos(elevation) * math.cos(azimuth),
             math.cos(elevation) * math.sin(azimuth), math.sin(elevation))
    # Fixed illustrative view: highlights become part of the exported colour.
    half = (light[0], light[1] - math.sqrt(.5), light[2] + math.sqrt(.5))
    length = max(math.sqrt(sum(value * value for value in half)), 1e-8)
    return light, tuple(value / length for value in half)


def normal_lighting_nodes(nt, color, settings):
    """Return scalar diffuse shading and white highlight sockets."""
    from .bake_maps import _math_node

    def vector(operation, source=None, other=None):
        node = nt.nodes.new('ShaderNodeVectorMath')
        node.operation = operation
        if source is not None:
            nt.links.new(source, node.inputs[0])
        if other is not None:
            node.inputs[1].default_value = other
        return node

    if settings.get('normal_space', 'OBJECT') == 'TANGENT':
        decode = nt.nodes.new('ShaderNodeNormalMap')
        decode.space = 'TANGENT'
        decode.uv_map = settings.get('normal_uv', '')
        nt.links.new(color, decode.inputs['Color'])
        transform = nt.nodes.new('ShaderNodeVectorTransform')
        transform.vector_type = 'NORMAL'
        transform.convert_from, transform.convert_to = 'WORLD', 'OBJECT'
        nt.links.new(decode.outputs['Normal'], transform.inputs['Vector'])
        normal = vector('NORMALIZE', transform.outputs['Vector']).outputs['Vector']
    else:
        # Compatibility for previously baked object-space maps.
        decode = vector('MULTIPLY_ADD', color, (2.0, 2.0, 2.0))
        decode.inputs[2].default_value = (-1.0, -1.0, -1.0)
        normal = vector('NORMALIZE', decode.outputs['Vector']).outputs['Vector']
    mode = settings.get('normal_light_mode', 'DIRECTIONAL')
    if mode != 'DIRECTIONAL':
        geometry = nt.nodes.new('ShaderNodeNewGeometry')
        reference = nt.nodes.new('ShaderNodeVectorTransform')
        reference.vector_type = 'NORMAL'
        reference.convert_from, reference.convert_to = 'WORLD', 'OBJECT'
        nt.links.new(geometry.outputs['True Normal'], reference.inputs['Vector'])
        ref = vector('NORMALIZE', reference.outputs['Vector']).outputs['Vector']
        dot = vector('DOT_PRODUCT', normal)
        nt.links.new(ref, dot.inputs[1])
        difference = _math_node(nt, 'SUBTRACT', a=1.0)
        nt.links.new(dot.outputs['Value'], difference.inputs[1])
        edge = _math_node(nt, 'MULTIPLY', b=4.0, clamp=True)
        nt.links.new(difference.outputs['Value'], edge.inputs[0])
        if mode == 'EDGES':
            scale = _math_node(nt, 'MULTIPLY', b=-.35 * settings.get('normal_diffuse', .45))
            nt.links.new(edge.outputs['Value'], scale.inputs[0])
            shading = _math_node(nt, 'ADD', b=1.0)
        else:
            scale = _math_node(nt, 'MULTIPLY', b=.5 * settings.get('normal_diffuse', .45))
            nt.links.new(edge.outputs['Value'], scale.inputs[0])
            shading = _math_node(nt, 'ADD', b=settings.get('normal_ambient', .65)
                                 + .5 * settings.get('normal_diffuse', .45))
        nt.links.new(scale.outputs['Value'], shading.inputs[0])
        power = _math_node(nt, 'POWER', b=settings.get('normal_shininess', 32.) / 32.)
        nt.links.new(edge.outputs['Value'], power.inputs[0])
        highlight = _math_node(nt, 'MULTIPLY', b=settings.get('normal_specular', .15))
        nt.links.new(power.outputs['Value'], highlight.inputs[0])
        return shading.outputs['Value'], highlight.outputs['Value']
    light, half = normal_light_directions(settings)

    def lobe(direction):
        dot = vector('DOT_PRODUCT', normal, direction)
        positive = _math_node(nt, 'MAXIMUM', b=0.0)
        nt.links.new(dot.outputs['Value'], positive.inputs[0])
        return positive.outputs['Value']

    diffuse = _math_node(nt, 'MULTIPLY', b=settings.get('normal_diffuse', .45))
    nt.links.new(lobe(light), diffuse.inputs[0])
    shading = _math_node(nt, 'ADD', b=settings.get('normal_ambient', .65))
    nt.links.new(diffuse.outputs['Value'], shading.inputs[0])
    power = _math_node(nt, 'POWER', b=settings.get('normal_shininess', 32.0))
    nt.links.new(lobe(half), power.inputs[0])
    highlight = _math_node(nt, 'MULTIPLY', b=settings.get('normal_specular', .15))
    nt.links.new(power.outputs['Value'], highlight.inputs[0])
    return shading.outputs['Value'], highlight.outputs['Value']
