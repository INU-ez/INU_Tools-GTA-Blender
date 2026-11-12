"""
Live particle simulation for 2DFX Particle empties.

Runs via bpy.app.timers when the scene-level toggle is on. For each
PARTICLE 2DFX empty, maintains a pool of quads in a child mesh
`{empty}_psim`, with per-particle position, size and color.

State is held in module-level dicts (ephemeral — not saved with the file).
"""

import math
import random
import bpy
from dataclasses import dataclass, field
from typing import Dict, List
from mathutils import Vector
from ..tools import compat


MAX_PARTICLES_PER_EMITTER = 64
TICK_INTERVAL = 1.0 / 30.0  # ~30 Hz


@dataclass
class _Particle:
    pos: Vector = field(default_factory=lambda: Vector((0.0, 0.0, 0.0)))
    vel: Vector = field(default_factory=lambda: Vector((0.0, 0.0, 0.0)))
    age: float = 0.0
    life: float = 1.0


# {empty_name: [_Particle, ...]}
_sim_state: Dict[str, List[_Particle]] = {}
# {empty_name: float} — leftover emit fraction so rate stays accurate below 1/tick
_emit_accum: Dict[str, float] = {}

_sim_timer_running = False


# --------------------------------------------------------------------------- #
# View basis — quads face the active 3D viewport
# --------------------------------------------------------------------------- #

def _current_view_basis():
    """Return (right, up) world-space unit vectors for the active VIEW_3D."""
    try:
        wm = bpy.context.window_manager
        if wm is None:
            return Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0))
        for window in wm.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                for space in area.spaces:
                    if space.type == 'VIEW_3D' and space.region_3d is not None:
                        quat = space.region_3d.view_rotation
                        right = quat @ Vector((1.0, 0.0, 0.0))
                        up = quat @ Vector((0.0, 1.0, 0.0))
                        return right, up
    except Exception:
        pass
    return Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0))


# --------------------------------------------------------------------------- #
# Mesh pool — one quad per particle slot, shared mesh per emitter
# --------------------------------------------------------------------------- #

def _get_or_create_sim_mesh(empty):
    """Return the child mesh object for this empty's particle pool, creating
    it with `MAX_PARTICLES_PER_EMITTER` collapsed quads on first use."""
    mesh_name = f"{empty.name}_psim"

    # Find existing child by suffix
    for child in empty.children:
        if child.type == 'MESH' and child.name.startswith(empty.name) and '_psim' in child.name:
            return child

    n = MAX_PARTICLES_PER_EMITTER
    mesh = bpy.data.meshes.new(mesh_name)
    verts = [(0.0, 0.0, 0.0)] * (n * 4)
    faces = [(i * 4, i * 4 + 1, i * 4 + 2, i * 4 + 3) for i in range(n)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    # UV map (each quad 0..1)
    uv = mesh.uv_layers.new(name='UVMap')
    uv_data = uv.data
    for i in range(n):
        uv_data[i * 4 + 0].uv = (0.0, 0.0)
        uv_data[i * 4 + 1].uv = (1.0, 0.0)
        uv_data[i * 4 + 2].uv = (1.0, 1.0)
        uv_data[i * 4 + 3].uv = (0.0, 1.0)

    # Vertex color layer (per-loop RGBA). На 2.80-3.1 будет BYTE_COLOR.
    compat.vcol_new(mesh, 'Col', dtype='FLOAT_COLOR')

    obj = bpy.data.objects.new(mesh_name, mesh)
    obj.parent = empty
    collection = empty.users_collection[0] if empty.users_collection else bpy.context.collection
    collection.objects.link(obj)

    # Non-exportable, non-selectable
    if hasattr(obj, 'inu'):
        obj.inu.type = 'NON'
    obj.hide_select = True
    obj['inu_2dfx_owned_preview'] = 1
    from .fx_preview import apply_preview_visibility
    apply_preview_visibility(obj)
    obj.lock_location = (True, True, True)
    obj.lock_rotation = (True, True, True)
    obj.lock_scale = (True, True, True)

    # Material
    tex_name = (empty.inu.particle_texture or '').strip() if hasattr(empty, 'inu') else ''
    mat = _create_sim_material(empty.name, tex_name or None)
    mesh.materials.append(mat)

    return obj


def _create_sim_material(name: str, tex_name):
    """Transparent + Emission shader driven by per-loop vertex color.
    Texture colour (if loaded) is multiplied with vertex colour; texture
    alpha is multiplied with vertex alpha to drive the mix factor."""
    mat_name = f"2dfx_psim_{name}"
    if mat_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[mat_name], do_unlink=True)

    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    if hasattr(mat, 'blend_method'):
        mat.blend_method = 'BLEND'
    mat.use_backface_culling = False

    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (700, 0)

    transparent = nodes.new('ShaderNodeBsdfTransparent')
    transparent.location = (300, 100)

    emission = nodes.new('ShaderNodeEmission')
    emission.location = (300, -100)
    emission.inputs['Strength'].default_value = 1.0

    mix_shader = nodes.new('ShaderNodeMixShader')
    mix_shader.location = (500, 0)
    links.new(transparent.outputs['BSDF'], mix_shader.inputs[1])
    links.new(emission.outputs['Emission'], mix_shader.inputs[2])
    links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])

    vcol = nodes.new('ShaderNodeVertexColor')
    vcol.layer_name = 'Col'
    vcol.location = (-300, -100)

    from .fx_preview import _find_particle_image
    img = _find_particle_image(tex_name) if tex_name else None

    if img is not None:
        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.image = img
        tex_node.location = (-300, 200)

        mul_rgb = nodes.new('ShaderNodeMixRGB')
        mul_rgb.blend_type = 'MULTIPLY'
        mul_rgb.inputs['Fac'].default_value = 1.0
        mul_rgb.location = (0, 50)
        links.new(tex_node.outputs['Color'], mul_rgb.inputs['Color1'])
        links.new(vcol.outputs['Color'], mul_rgb.inputs['Color2'])
        links.new(mul_rgb.outputs['Color'], emission.inputs['Color'])

        mul_a = nodes.new('ShaderNodeMath')
        mul_a.operation = 'MULTIPLY'
        mul_a.location = (0, -150)
        links.new(tex_node.outputs['Alpha'], mul_a.inputs[0])
        links.new(vcol.outputs['Alpha'], mul_a.inputs[1])
        links.new(mul_a.outputs['Value'], mix_shader.inputs[0])
    else:
        links.new(vcol.outputs['Color'], emission.inputs['Color'])
        links.new(vcol.outputs['Alpha'], mix_shader.inputs[0])

    return mat


def _remove_sim_mesh(empty):
    """Remove the psim child mesh for an empty (on stop / cleanup)."""
    for child in list(empty.children):
        if child.type == 'MESH' and '_psim' in child.name:
            mesh = child.data
            bpy.data.objects.remove(child, do_unlink=True)
            if mesh and mesh.users == 0:
                bpy.data.meshes.remove(mesh)


# --------------------------------------------------------------------------- #
# Simulation tick
# --------------------------------------------------------------------------- #

def _orthonormal_basis(forward: Vector):
    """Build a right-handed basis (right, up, fwd) from a unit forward vector."""
    f = forward.copy()
    if f.length_squared < 1e-8:
        f = Vector((0.0, 0.0, 1.0))
    f.normalize()
    # Pick a temp up that isn't parallel to f
    tmp = Vector((0.0, 0.0, 1.0))
    if abs(f.dot(tmp)) > 0.99:
        tmp = Vector((0.0, 1.0, 0.0))
    r = f.cross(tmp)
    r.normalize()
    u = r.cross(f)
    u.normalize()
    return r, u, f


def _emit(empty, state: List[_Particle], dt: float):
    inu = empty.inu
    rate = max(inu.particle_rate, 0.0)
    if rate <= 0.0:
        return

    accum = _emit_accum.get(empty.name, 0.0) + rate * dt
    n = int(accum)
    _emit_accum[empty.name] = accum - n

    life_base = max(inu.particle_life, 0.05)
    life_bias = max(inu.particle_life_bias, 0.0)
    speed_base = max(inu.particle_speed, 0.0)
    speed_bias = max(inu.particle_speed_bias, 0.0)

    d = Vector(inu.particle_direction)
    if d.length_squared > 1e-8:
        d.normalize()
    else:
        d = Vector((0.0, 0.0, 1.0))

    # Cone around direction (EMANGLE MIN/MAX in degrees)
    angle_min = max(float(inu.particle_angle_min), 0.0)
    angle_max = max(float(inu.particle_angle_max), angle_min)
    right, up, fwd = _orthonormal_basis(d)

    # Box as symmetric half-extent around emitter — matches FXP save which
    # writes SIZEMIN=-v SIZEMAX=+v per axis.
    vol_half = Vector(inu.particle_volume)
    offset = Vector(inu.particle_offset)

    world_mat = empty.matrix_world
    emission_centre = world_mat @ offset
    rot3 = world_mat.to_3x3()

    box_has_range = vol_half.x > 1e-6 or vol_half.y > 1e-6 or vol_half.z > 1e-6

    for _ in range(n):
        if len(state) >= MAX_PARTICLES_PER_EMITTER:
            break

        if box_has_range:
            local_offset = Vector((
                random.uniform(-vol_half.x, vol_half.x),
                random.uniform(-vol_half.y, vol_half.y),
                random.uniform(-vol_half.z, vol_half.z),
            ))
        else:
            local_offset = Vector((0.0, 0.0, 0.0))

        spawn_pos = emission_centre + rot3 @ local_offset

        # Random direction inside the cone
        if angle_max > 0.001:
            theta_deg = random.uniform(angle_min, angle_max)
            phi = random.uniform(0.0, 2.0 * math.pi)
            theta = math.radians(theta_deg)
            # Direction = fwd * cos(theta) + (right*cos(phi)+up*sin(phi)) * sin(theta)
            radial = right * math.cos(phi) + up * math.sin(phi)
            dir_vec = fwd * math.cos(theta) + radial * math.sin(theta)
        else:
            dir_vec = fwd.copy()

        speed = speed_base + random.uniform(-speed_bias, speed_bias)
        vel = dir_vec * max(speed, 0.0)

        life = life_base + random.uniform(-life_bias, life_bias)
        life = max(life, 0.05)

        state.append(_Particle(
            pos=spawn_pos,
            vel=vel,
            age=0.0,
            life=life,
        ))


def _update(empty, state: List[_Particle], dt: float):
    inu = empty.inu
    force = Vector(inu.particle_force)
    friction = max(float(inu.particle_friction), 0.0)
    bounce = max(float(inu.particle_ground_bounce), 0.0)
    speedmult = max(float(inu.particle_ground_speedmult), 0.0)
    ground_z = empty.matrix_world.translation.z - 10.0  # a metre or two below; FXP has no explicit ground in MVP

    # Convert friction to an exponential decay factor per tick for stable damping.
    friction_decay = math.exp(-friction * dt) if friction > 0.0 else 1.0

    i = 0
    while i < len(state):
        p = state[i]
        p.age += dt
        if p.age >= p.life:
            state.pop(i)
            continue
        p.vel += force * dt
        if friction_decay != 1.0:
            p.vel *= friction_decay
        p.pos += p.vel * dt

        # Ground bounce — only if GROUNDCOLLIDE was configured
        if (bounce > 0.0 or speedmult < 1.0) and p.pos.z < ground_z and p.vel.z < 0.0:
            p.pos.z = ground_z
            p.vel.z = -p.vel.z * bounce
            p.vel.x *= speedmult
            p.vel.y *= speedmult

        i += 1


def _render(empty, mesh_obj, state: List[_Particle], right: Vector, up: Vector):
    inu = empty.inu
    mesh = mesh_obj.data
    n = MAX_PARTICLES_PER_EMITTER

    # World → mesh-local transform (mesh_obj is a child of empty)
    inv = mesh_obj.matrix_world.inverted()

    size_a = float(inu.particle_size_start)
    size_b = float(inu.particle_size_end)
    c0 = inu.particle_color_start
    c1 = inu.particle_color_end
    mid_on = bool(inu.particle_color_mid_enabled)
    cm = inu.particle_color_mid if mid_on else None
    mt = float(inu.particle_color_mid_time) if mid_on else 0.5

    vco = [0.0] * (n * 4 * 3)
    loop_col = [0.0] * (n * 4 * 4)

    for i in range(n):
        base_v = i * 4 * 3
        base_c = i * 4 * 4
        if i >= len(state):
            # collapse dead slot to origin, fully transparent
            for k in range(12):
                vco[base_v + k] = 0.0
            for k in range(16):
                loop_col[base_c + k] = 0.0
            continue

        p = state[i]
        t = p.age / p.life if p.life > 0.0 else 0.0
        sz = size_a + (size_b - size_a) * t
        half = sz * 0.5

        # Build quad corners in WORLD space (camera-facing), then bring each
        # point into the mesh-local frame. Mixing spaces breaks alignment
        # whenever the parent empty is rotated.
        r = right * half
        u = up * half
        w0 = p.pos - r - u
        w1 = p.pos + r - u
        w2 = p.pos + r + u
        w3 = p.pos - r + u
        v0 = inv @ w0
        v1 = inv @ w1
        v2 = inv @ w2
        v3 = inv @ w3

        vco[base_v + 0] = v0.x
        vco[base_v + 1] = v0.y
        vco[base_v + 2] = v0.z
        vco[base_v + 3] = v1.x
        vco[base_v + 4] = v1.y
        vco[base_v + 5] = v1.z
        vco[base_v + 6] = v2.x
        vco[base_v + 7] = v2.y
        vco[base_v + 8] = v2.z
        vco[base_v + 9] = v3.x
        vco[base_v + 10] = v3.y
        vco[base_v + 11] = v3.z

        if mid_on:
            if t <= mt:
                k = t / mt if mt > 0.0 else 0.0
                r_ = c0[0] + (cm[0] - c0[0]) * k
                g_ = c0[1] + (cm[1] - c0[1]) * k
                b_ = c0[2] + (cm[2] - c0[2]) * k
                a_ = c0[3] + (cm[3] - c0[3]) * k
            else:
                span = 1.0 - mt
                k = (t - mt) / span if span > 0.0 else 0.0
                r_ = cm[0] + (c1[0] - cm[0]) * k
                g_ = cm[1] + (c1[1] - cm[1]) * k
                b_ = cm[2] + (c1[2] - cm[2]) * k
                a_ = cm[3] + (c1[3] - cm[3]) * k
        else:
            r_ = c0[0] + (c1[0] - c0[0]) * t
            g_ = c0[1] + (c1[1] - c0[1]) * t
            b_ = c0[2] + (c1[2] - c0[2]) * t
            a_ = c0[3] + (c1[3] - c0[3]) * t
        for k in range(4):
            loop_col[base_c + k * 4 + 0] = r_
            loop_col[base_c + k * 4 + 1] = g_
            loop_col[base_c + k * 4 + 2] = b_
            loop_col[base_c + k * 4 + 3] = a_

    mesh.vertices.foreach_set('co', vco)

    # Write vertex color attribute через compat — на 2.80-3.1 это
    # mesh.vertex_colors, на 3.2+ это mesh.color_attributes.
    attr = compat.vcol_get(mesh, 'Col')
    if attr is not None:
        attr.data.foreach_set('color', loop_col)

    mesh.update()


def _tick():
    """bpy.app.timer callback — runs while simulation is enabled."""
    global _sim_timer_running
    try:
        scene = bpy.context.scene
        if scene is None or not getattr(scene.inu_settings, 'gtatools_particle_sim', False):
            _sim_timer_running = False
            return None  # unregister

        wm = bpy.context.window_manager
        if wm is not None and wm.is_interface_locked:
            return TICK_INTERVAL
        if getattr(scene.inu_settings, 'gtatools_fx_preview_hidden', False):
            return TICK_INTERVAL

        dt = TICK_INTERVAL
        right, up = _current_view_basis()

        active_names = set()
        # Creating the pool changes bpy.data.objects: never mutate the
        # collection being iterated (including the first tick with 5 emitters).
        for obj in [obj for obj in scene.objects if obj.type == 'EMPTY']:
            inu = getattr(obj, 'inu', None)
            if inu is None or inu.type != '2DFX' or inu.effect_2dfx != 'PARTICLE':
                continue
            active_names.add(obj.name)

            state = _sim_state.setdefault(obj.name, [])
            _emit(obj, state, dt)
            _update(obj, state, dt)

            try:
                mesh_obj = _get_or_create_sim_mesh(obj)
                _render(obj, mesh_obj, state, right, up)
            except Exception as e:
                print(f"[2DFX PSim] render error for {obj.name}: {e}")

        # Drop state for emitters that no longer exist
        for dead in list(_sim_state.keys()):
            if dead not in active_names:
                del _sim_state[dead]
                _emit_accum.pop(dead, None)

        # Force the viewport to show THIS tick. Writing the mesh from a timer
        # doesn't reliably schedule a redraw, so without this the sim only
        # refreshes whenever the viewport happens to redraw (playback at the
        # scene's fps — 24 by default — or mouse movement), making it look
        # like it runs at 24 fps. Tagging here locks the visible rate to our
        # 30 Hz tick regardless of scene fps.
        if active_names:
            wm = bpy.context.window_manager
            for window in (wm.windows if wm else ()):
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

    except Exception as e:
        print(f"[2DFX PSim] tick error: {e}")

    return TICK_INTERVAL


# --------------------------------------------------------------------------- #
# Public start/stop API
# --------------------------------------------------------------------------- #

def start_simulation():
    """Register the tick timer if not already running."""
    global _sim_timer_running
    if _sim_timer_running and bpy.app.timers.is_registered(_tick):
        return
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    bpy.app.timers.register(_tick, first_interval=TICK_INTERVAL)
    _sim_timer_running = True
    print("[2DFX PSim] started")


def stop_simulation(clear_meshes: bool = True):
    """Unregister timer and optionally clear per-emitter mesh pools."""
    global _sim_timer_running
    if bpy.app.timers.is_registered(_tick):
        try:
            bpy.app.timers.unregister(_tick)
        except Exception:
            pass
    _sim_timer_running = False
    _sim_state.clear()
    _emit_accum.clear()

    if clear_meshes:
        for obj in [obj for obj in bpy.data.objects if obj.type == 'EMPTY']:
            inu = getattr(obj, 'inu', None)
            if inu is None or inu.type != '2DFX' or inu.effect_2dfx != 'PARTICLE':
                continue
            try:
                _remove_sim_mesh(obj)
            except Exception as e:
                print(f"[2DFX PSim] cleanup error: {e}")
    print("[2DFX PSim] stopped")
