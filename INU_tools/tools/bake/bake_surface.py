"""Live scalar mask operations, directional dirt and colour transitions."""
import math

SURFACE_DEFAULTS = dict(direction_mode='TOP', direction=(0., 0., 1.),
    direction_threshold=.5, direction_softness=.5, streak_length=12.,
    ramp_low=0., ramp_high=1., ramp_smooth=False)


def math_node(nt, operation, a=None, b=None, clamp=False):
    node = nt.nodes.new('ShaderNodeMath')
    node.operation = operation
    node.use_clamp = clamp
    for index, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            nt.links.new(value, node.inputs[index])
    return node.outputs[0]


def levels(nt, value, low, high, smooth=False):
    if low == 0. and high == 1. and not smooth:
        return value
    value = math_node(nt, 'SUBTRACT', value, float(low))
    value = math_node(nt, 'DIVIDE', value, max(float(high)-float(low), 1e-5), True)
    if smooth:
        square = math_node(nt, 'MULTIPLY', value, value)
        value = math_node(nt, 'MULTIPLY', square,
            math_node(nt, 'SUBTRACT', 3., math_node(nt, 'MULTIPLY', value, 2.)))
    return value


def directional_mask(nt, settings):
    direction = settings.get('direction', (0., 0., 1.))
    length = math.sqrt(sum(v*v for v in direction))
    direction = tuple(v / length for v in direction) if length > 1e-8 else (0., 0., 1.)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    def vector(op, a, b):
        n = nt.nodes.new('ShaderNodeVectorMath')
        n.operation = op
        nt.links.new(a, n.inputs[0])
        if isinstance(b, tuple):
            n.inputs[1].default_value = b
        else:
            nt.links.new(b, n.inputs[1])
        return n.outputs['Value' if op == 'DOT_PRODUCT' else 'Vector']
    mode = settings.get('direction_mode', 'TOP')
    if mode in {'TOP', 'SLOPE'}:
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        transform = nt.nodes.new('ShaderNodeVectorTransform')
        transform.vector_type = 'NORMAL'
        transform.convert_from, transform.convert_to = 'WORLD', 'OBJECT'
        nt.links.new(geo.outputs['True Normal'], transform.inputs['Vector'])
        normal = vector('NORMALIZE', transform.outputs['Vector'], (0., 0., 0.))
        value = vector('DOT_PRODUCT', normal, direction)
        if mode == 'SLOPE':
            value = math_node(nt, 'SUBTRACT', 1., math_node(nt, 'ABSOLUTE', value))
    else:
        # Generated coordinates give a normalized height independent of mesh size.
        value = vector('DOT_PRODUCT', tc.outputs['Generated'], direction)
        low = sum(min(0., v) for v in direction)
        span = max(sum(abs(v) for v in direction), 1e-5)
        value = math_node(nt, 'DIVIDE', math_node(nt, 'SUBTRACT', value, low), span)
        value = math_node(nt, 'SUBTRACT', 1., value)
        if mode == 'STREAK':
            coords = tc.outputs['Generated']
            projection = vector('DOT_PRODUCT', coords, direction)
            combine = nt.nodes.new('ShaderNodeCombineXYZ')
            for name in ('X', 'Y', 'Z'):
                nt.links.new(projection, combine.inputs[name])
            axis = vector('MULTIPLY', combine.outputs['Vector'], direction)
            axis = vector('MULTIPLY', axis, (1.-1./max(settings.get('streak_length', 12.), 1.),)*3)
            coords = vector('SUBTRACT', coords, axis)
            noise = nt.nodes.new('ShaderNodeTexNoise')
            noise.noise_dimensions = '4D'
            noise.inputs['Scale'].default_value = settings.get('pattern_scale', 8.)
            noise.inputs['Detail'].default_value = settings.get('pattern_detail', 2.)
            noise.inputs['W'].default_value = settings.get('pattern_seed', 0)
            nt.links.new(coords, noise.inputs['Vector'])
            value = math_node(nt, 'MULTIPLY', value, noise.outputs['Fac'])
    threshold = settings.get('direction_threshold', .5)
    softness = max(settings.get('direction_softness', .5), 1e-5)
    return levels(nt, value, threshold-softness*.5, threshold+softness*.5, True)


def combine_masks(nt, color, layer, source):
    masks = [mask for mask in layer.get('masks', ()) if mask.get('enabled', True)]
    if not masks:
        return color
    neutral = 1. if layer['map_id'] in {'DIRT', 'GRUNGE'} else (.5 if layer['map_id'] == 'CURVATURE' else 0.)
    delta = math_node(nt, 'SUBTRACT', color, neutral)
    if neutral == 1.:
        value = math_node(nt, 'MULTIPLY', delta, -1.)
    elif neutral == .5:
        value = math_node(nt, 'MULTIPLY', math_node(nt, 'ABSOLUTE', delta), 2.)
    else:
        value = delta
    for mask in masks:
        fac = source(mask['basis'])
        if mask.get('invert'):
            fac = math_node(nt, 'SUBTRACT', 1., fac, True)
        amount = mask.get('strength', 1.)
        fac = math_node(nt, 'MULTIPLY', fac, amount)
        operation = mask.get('operation', 'MULTIPLY')
        if operation == 'MULTIPLY':
            fac = math_node(nt, 'ADD', fac, 1.-amount)
        value = math_node(nt, operation, value, fac, True)
    if neutral == 1.:
        return math_node(nt, 'SUBTRACT', 1., value, True)
    if neutral == .5:
        sign = math_node(nt, 'SUBTRACT', math_node(nt, 'GREATER_THAN', delta, 0.),
                         math_node(nt, 'LESS_THAN', delta, 0.))
        # At flat (delta=0) additive masks should still be able to add convex wear.
        sign = math_node(nt, 'ADD', sign,
            math_node(nt, 'LESS_THAN', math_node(nt, 'ABSOLUTE', delta), 1e-8))
        return math_node(nt, 'ADD', math_node(nt, 'MULTIPLY', value,
            math_node(nt, 'MULTIPLY', sign, .5)), .5, True)
    return value
