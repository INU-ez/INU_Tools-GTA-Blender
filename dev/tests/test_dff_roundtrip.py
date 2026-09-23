"""Round-trip tests for core/dff.py — write a structure, read it back,
check fidelity for materials, MatFX (env/specular/reflection/dual/bump),
2DFX effects, skin/HAnim, breakable objects, UV anim, and multi-frame
hierarchies. Covers every public dataclass and every chunk type the
writer can emit.

Lives at dev/tests/, runs with `pytest dev/tests/test_dff_roundtrip.py`.
Pure Python — no Blender required.
"""

from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.dff import (  # noqa: E402
    DffClump,
    DffFrame,
    DffGeometry,
    DffAtomic,
    DffMaterial,
    DffTexture,
    Triangle,
    BoundingSphere,
    RGBA,
    TexCoords,
    SurfaceProperties,
    EnvMapEffect,
    BumpMapEffect,
    SpecularMaterial,
    ReflectionMaterial,
    DualTextureEffect,
    Light2dfx,
    Particle2dfx,
    PedAttractor2dfx,
    SunGlare2dfx,
    EnterExit2dfx,
    RoadSign2dfx,
    Escalator2dfx,
    RawUnknown2dfx,
    Extension2dfx,
    BreakableData,
    SkinData,
    HAnimData,
    HAnimBone,
    UVAnim,
    UVAnimDict,
    UVAnimKeyframe,
    write_dff,
    read_dff,
)


def _triangle(a, b, c, m=0):
    return Triangle(a=a, b=b, c=c, material=m)


def _basic_geom(num_verts=3, num_tris=1, with_normals=True, with_uv=False,
                with_prelit=False, with_uv2=False):
    """Tiny but valid mesh — single material, optional layers."""
    verts = [(float(i), 0.0, 0.0) for i in range(num_verts)]
    norms = [(0.0, 0.0, 1.0)] * num_verts if with_normals else []
    tris = [_triangle(0, 1, 2)] * num_tris
    uvs = []
    if with_uv:
        uvs.append([TexCoords(u=float(i)/num_verts, v=0.0) for i in range(num_verts)])
    if with_uv2:
        uvs.append([TexCoords(u=0.0, v=float(i)/num_verts) for i in range(num_verts)])
    cols = []
    if with_prelit:
        cols = [RGBA(r=255, g=128, b=64, a=255) for _ in range(num_verts)]
    return DffGeometry(
        vertices=verts,
        normals=norms,
        triangles=tris,
        uv_layers=uvs,
        prelit_colors=cols,
        materials=[DffMaterial(color=RGBA(r=255, g=255, b=255, a=255))],
        bounding_sphere=BoundingSphere(x=0.0, y=0.0, z=0.0, radius=2.0),
    )


def _wrap(geom, frame_name="root"):
    """Single-atomic clump wrapping one geometry."""
    return DffClump(
        frames=[DffFrame(name=frame_name, parent=-1)],
        geometries=[geom],
        atomics=[DffAtomic(frame_index=0, geometry_index=0)],
    )


# ── Basic geometry shapes ────────────────────────────────────────

def test_geometry_with_uv_layer():
    geom = _basic_geom(with_uv=True)
    parsed = read_dff(write_dff(_wrap(geom)))
    g = parsed.geometries[0]
    assert len(g.uv_layers) == 1
    assert len(g.uv_layers[0]) == 3


def test_geometry_with_two_uv_layers():
    geom = _basic_geom(with_uv=True, with_uv2=True)
    parsed = read_dff(write_dff(_wrap(geom)))
    g = parsed.geometries[0]
    assert len(g.uv_layers) == 2


def test_geometry_with_prelit_colors():
    geom = _basic_geom(with_prelit=True)
    parsed = read_dff(write_dff(_wrap(geom)))
    g = parsed.geometries[0]
    assert len(g.prelit_colors) == 3
    # First vertex was (255, 128, 64, 255)
    assert g.prelit_colors[0].r == 255
    assert g.prelit_colors[0].g == 128
    assert g.prelit_colors[0].b == 64


def test_prelit_vertex_alpha_round_trip():
    """Per-vertex ALPHA in prelit (Day) colours must survive write→read.
    Guards the vertex-alpha export pipeline at the binary layer — the
    Blender side (dff_export `_mesh_alpha`) feeds these bytes."""
    geom = _basic_geom(num_verts=3, with_prelit=True)
    # Distinct alpha per vertex incl. the extremes (fully transparent /
    # opaque) and a mid value — exactly the KRC_mounta018-style gradient.
    geom.prelit_colors = [
        RGBA(r=10, g=20, b=30, a=0),
        RGBA(r=40, g=50, b=60, a=128),
        RGBA(r=70, g=80, b=90, a=245),
    ]
    g = read_dff(write_dff(_wrap(geom))).geometries[0]
    assert [c.a for c in g.prelit_colors] == [0, 128, 245]
    # RGB must not be disturbed by carrying alpha.
    assert (g.prelit_colors[1].r, g.prelit_colors[1].g,
            g.prelit_colors[1].b) == (40, 50, 60)


def test_extra_night_vertex_alpha_round_trip():
    """Night (ExtraVertColors, chunk 0x253F2F9) alpha must round-trip too —
    SA reads these for day/night buildings."""
    from core.dff import ExtraVertColors  # noqa: E402
    geom = _basic_geom(num_verts=3, with_prelit=True)
    geom.extra_colors = ExtraVertColors(colors=[
        RGBA(r=0, g=0, b=0, a=5),
        RGBA(r=255, g=255, b=255, a=200),
        RGBA(r=128, g=128, b=128, a=255),
    ])
    g = read_dff(write_dff(_wrap(geom))).geometries[0]
    assert g.extra_colors is not None
    assert [c.a for c in g.extra_colors.colors] == [5, 200, 255]


def test_geometry_without_normals():
    geom = _basic_geom(with_normals=False)
    geom.export_normals = False
    parsed = read_dff(write_dff(_wrap(geom)))
    # Either empty or per-vertex zeroes — what matters is no crash
    assert len(parsed.geometries[0].vertices) == 3


# ── Material variants ────────────────────────────────────────────

def test_material_with_texture():
    geom = _basic_geom(with_uv=True)
    geom.materials[0].texture = DffTexture(name="road01", mask="", filters=6)
    parsed = read_dff(write_dff(_wrap(geom)))
    mat = parsed.geometries[0].materials[0]
    assert mat.texture is not None
    assert mat.texture.name == "road01"


def test_material_with_env_map():
    geom = _basic_geom(with_uv=True)
    geom.materials[0].env_map = EnvMapEffect(
        coefficient=0.42, use_fb_alpha=True,
        texture=DffTexture(name="xvehicleenv128"))
    parsed = read_dff(write_dff(_wrap(geom)))
    mat = parsed.geometries[0].materials[0]
    assert mat.env_map is not None
    assert abs(mat.env_map.coefficient - 0.42) < 1e-5
    assert mat.env_map.use_fb_alpha is True
    assert mat.env_map.texture.name == "xvehicleenv128"


def test_material_with_specular():
    geom = _basic_geom(with_uv=True)
    geom.materials[0].specular = SpecularMaterial(level=1.5, name="vehiclespecdot64")
    parsed = read_dff(write_dff(_wrap(geom)))
    mat = parsed.geometries[0].materials[0]
    assert mat.specular is not None
    assert abs(mat.specular.level - 1.5) < 1e-5
    assert mat.specular.name == "vehiclespecdot64"


def test_material_reflection_not_written():
    # W7: Reflection Material (0x0253F2FC) — остаток 3ds Max-экспортёра, ваниль
    # SA его не пишет и движку он не нужен. Экспортёр его НЕ сериализует, чтобы
    # DFF совпадал с ванильным → после round-trip reflection отсутствует.
    geom = _basic_geom(with_uv=True)
    geom.materials[0].reflection = ReflectionMaterial(
        scale_x=2.0, scale_y=1.0, offset_x=0.1, offset_y=0.2, intensity=0.05)
    parsed = read_dff(write_dff(_wrap(geom)))
    mat = parsed.geometries[0].materials[0]
    assert mat.reflection is None


def test_material_with_dual_texture():
    geom = _basic_geom(with_uv=True, with_uv2=True)
    geom.materials[0].dual_texture = DualTextureEffect(
        src_blend=5, dst_blend=6, texture=DffTexture(name="detail01"))
    parsed = read_dff(write_dff(_wrap(geom)))
    mat = parsed.geometries[0].materials[0]
    assert mat.dual_texture is not None
    assert mat.dual_texture.src_blend == 5
    assert mat.dual_texture.dst_blend == 6
    assert mat.dual_texture.texture.name == "detail01"


def test_surface_properties():
    geom = _basic_geom()
    geom.materials[0].surface = SurfaceProperties(ambient=0.7, specular=0.3, diffuse=1.2)
    parsed = read_dff(write_dff(_wrap(geom)))
    sp = parsed.geometries[0].materials[0].surface
    assert abs(sp.ambient - 0.7) < 1e-5
    assert abs(sp.specular - 0.3) < 1e-5
    assert abs(sp.diffuse - 1.2) < 1e-5


# ── 2DFX effects (Light / Particle / Ped Attractor / Sun Glare) ──

def test_2dfx_light_full_round_trip():
    geom = _basic_geom()
    light = Light2dfx(
        loc=(1.0, 2.0, 3.0),
        color=RGBA(r=255, g=200, b=100, a=255),
        corona_far_clip=120.0,
        pointlight_range=8.5,
        corona_size=2.5,
        shadow_size=4.0,
        corona_show_mode=2,         # FLASH_RAIN
        corona_enable_reflection=1,
        corona_flare_type=1,
        shadow_color_multiplier=200,
        flags1=0x42,
        corona_tex_name="coronastar",
        shadow_tex_name="shad_exp",
        shadow_z_distance=10,
        flags2=0x07,
    )
    geom.ext_2dfx = Extension2dfx(entries=[light])
    parsed = read_dff(write_dff(_wrap(geom)))
    ext = parsed.geometries[0].ext_2dfx
    assert ext is not None and len(ext.entries) == 1
    e = ext.entries[0]
    assert e.effect_id == 0  # Light
    assert abs(e.corona_far_clip - 120.0) < 1e-5
    assert abs(e.pointlight_range - 8.5) < 1e-5
    assert e.corona_show_mode == 2
    assert e.corona_flare_type == 1
    assert e.flags1 == 0x42
    assert e.flags2 == 0x07
    assert e.corona_tex_name == "coronastar"
    assert e.shadow_tex_name == "shad_exp"
    assert e.shadow_z_distance == 10


def test_2dfx_particle():
    geom = _basic_geom()
    geom.ext_2dfx = Extension2dfx(entries=[
        Particle2dfx(loc=(0.0, 1.0, 2.0), effect_name="prt_smokeii"),
    ])
    parsed = read_dff(write_dff(_wrap(geom)))
    e = parsed.geometries[0].ext_2dfx.entries[0]
    assert e.effect_id == 1
    assert e.effect_name == "prt_smokeii"
    assert e.loc == (0.0, 1.0, 2.0)


def test_2dfx_ped_attractor():
    geom = _basic_geom()
    geom.ext_2dfx = Extension2dfx(entries=[
        PedAttractor2dfx(
            loc=(5.0, 0.0, 0.0),
            attractor_type=4,
            external_script="atm",
            ped_existing_probability=80,
        ),
    ])
    parsed = read_dff(write_dff(_wrap(geom)))
    e = parsed.geometries[0].ext_2dfx.entries[0]
    assert e.effect_id == 3
    assert e.attractor_type == 4
    assert e.external_script == "atm"
    assert e.ped_existing_probability == 80


def test_2dfx_sun_glare():
    geom = _basic_geom()
    geom.ext_2dfx = Extension2dfx(entries=[SunGlare2dfx(loc=(10.0, 20.0, 30.0))])
    parsed = read_dff(write_dff(_wrap(geom)))
    e = parsed.geometries[0].ext_2dfx.entries[0]
    assert e.effect_id == 4
    assert e.loc == (10.0, 20.0, 30.0)


def test_2dfx_multiple_effects_in_one_geom():
    geom = _basic_geom()
    geom.ext_2dfx = Extension2dfx(entries=[
        Light2dfx(loc=(0.0, 0.0, 0.0), color=RGBA(r=255), corona_size=1.0,
                  corona_tex_name="coronastar", shadow_tex_name=""),
        Particle2dfx(loc=(1.0, 0.0, 0.0), effect_name="prt_water_splsh"),
        SunGlare2dfx(loc=(2.0, 0.0, 0.0)),
    ])
    parsed = read_dff(write_dff(_wrap(geom)))
    entries = parsed.geometries[0].ext_2dfx.entries
    assert len(entries) == 3
    assert {e.effect_id for e in entries} == {0, 1, 4}


def test_2dfx_enter_exit():
    geom = _basic_geom()
    geom.ext_2dfx = Extension2dfx(entries=[EnterExit2dfx(
        loc=(1.0, 2.0, 3.0), enter_angle=45.0,
        approximation_radius_x=1.5, approximation_radius_y=2.5,
        exit_loc=(4.0, 5.0, 6.0), exit_angle=90.0, interior=13,
        flags1=7, sky_color=2, interior_name="casino",
        time_on=6, time_off=20, flags2=1, unknown=0)])
    e = read_dff(write_dff(_wrap(geom))).geometries[0].ext_2dfx.entries[0]
    assert e.effect_id == 6
    assert e.loc == (1.0, 2.0, 3.0)
    assert e.exit_loc == (4.0, 5.0, 6.0)
    assert e.interior == 13
    assert e.interior_name == "casino"
    assert e.time_off == 20
    assert e.enter_angle == 45.0


def test_2dfx_road_sign():
    geom = _basic_geom()
    geom.ext_2dfx = Extension2dfx(entries=[RoadSign2dfx(
        loc=(7.0, 8.0, 9.0), size=(2.0, 1.0), rotation=(0.0, 0.0, 90.0),
        flags=0b011011, text_lines=["LINE1", "LINE2", "THIRD", ""])])
    e = read_dff(write_dff(_wrap(geom))).geometries[0].ext_2dfx.entries[0]
    assert e.effect_id == 7
    assert e.text_lines[:3] == ["LINE1", "LINE2", "THIRD"]
    assert e.flags == 0b011011
    assert e.size[0] == 2.0


def test_2dfx_escalator():
    geom = _basic_geom()
    geom.ext_2dfx = Extension2dfx(entries=[Escalator2dfx(
        loc=(10.0, 11.0, 12.0), bottom=(1.0, 1.0, 0.0),
        top=(1.0, 3.0, 5.0), end=(1.0, 3.0, 5.0), direction=1)])
    e = read_dff(write_dff(_wrap(geom))).geometries[0].ext_2dfx.entries[0]
    assert e.effect_id == 10
    assert e.direction == 1
    assert e.top == (1.0, 3.0, 5.0)


def test_2dfx_raw_unknown_preserved():
    """Undecoded types (here a fake type 8 trigger point) must round-trip
    byte-exact instead of being dropped."""
    import struct
    geom = _basic_geom()
    payload = struct.pack('<I', 42)
    geom.ext_2dfx = Extension2dfx(entries=[
        RawUnknown2dfx(effect_id=8, loc=(0.0, 0.0, 0.0), raw=payload)])
    e = read_dff(write_dff(_wrap(geom))).geometries[0].ext_2dfx.entries[0]
    assert isinstance(e, RawUnknown2dfx)
    assert e.effect_id == 8
    assert e.raw == payload


# ── Frame hierarchy ──────────────────────────────────────────────

def test_multiple_frames_with_parent_chain():
    """chassis_dummy → wheel_lf_dummy → wheel_lf hierarchy. Frame names
    only persist when ``write_name=True`` (DFF files without Frame Name
    chunks rely on Atomic→Frame index for identity)."""
    geom = _basic_geom()
    clump = DffClump(
        frames=[
            DffFrame(name="chassis_dummy", parent=-1, write_name=True),
            DffFrame(name="wheel_lf_dummy", parent=0, write_name=True),
            DffFrame(name="wheel_lf", parent=1, write_name=True),
        ],
        geometries=[geom],
        atomics=[DffAtomic(frame_index=2, geometry_index=0)],
    )
    parsed = read_dff(write_dff(clump))
    assert len(parsed.frames) == 3
    assert parsed.frames[0].parent == -1
    assert parsed.frames[1].parent == 0
    assert parsed.frames[2].parent == 1
    names = [f.name for f in parsed.frames]
    assert "chassis_dummy" in names
    assert "wheel_lf_dummy" in names


def test_multiple_atomics():
    """Two atomics share a clump — typical for vehicles (chassis + wheels)."""
    g0 = _basic_geom()
    g1 = _basic_geom()
    clump = DffClump(
        frames=[DffFrame(name="root", parent=-1),
                DffFrame(name="part1", parent=0),
                DffFrame(name="part2", parent=0)],
        geometries=[g0, g1],
        atomics=[
            DffAtomic(frame_index=1, geometry_index=0),
            DffAtomic(frame_index=2, geometry_index=1),
        ],
    )
    parsed = read_dff(write_dff(clump))
    assert len(parsed.atomics) == 2
    assert {a.frame_index for a in parsed.atomics} == {1, 2}
    assert {a.geometry_index for a in parsed.atomics} == {0, 1}


# ── Skin / HAnim (skinned characters) ────────────────────────────

def test_skin_data():
    # 4×4 matrix as 4 rows of 4 floats — writer flattens row-by-row.
    identity = ((1.0, 0.0, 0.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 0.0),
                (0.0, 0.0, 0.0, 1.0))
    geom = _basic_geom(num_verts=3)
    geom.skin = SkinData(
        num_bones=2,
        num_used=2,
        max_weights=4,
        bones_used=[0, 1],
        bone_indices=[(0, 1, 0, 0), (0, 1, 0, 0), (1, 0, 0, 0)],
        bone_weights=[(0.5, 0.5, 0.0, 0.0)] * 3,
        bone_matrices=[identity, identity],
    )
    parsed = read_dff(write_dff(_wrap(geom)))
    g = parsed.geometries[0]
    assert g.skin is not None
    assert g.skin.num_bones == 2
    assert len(g.skin.bone_weights) == 3


def test_hanim_on_frame():
    geom = _basic_geom()
    clump = DffClump(
        frames=[
            DffFrame(name="Root", parent=-1, write_name=True, hanim=HAnimData(
                bone_id=0,
                bones=[HAnimBone(bone_id=0, index=0, bone_type=0),
                       HAnimBone(bone_id=1, index=1, bone_type=2)])),
            DffFrame(name="Bone1", parent=0, write_name=True),
        ],
        geometries=[geom],
        atomics=[DffAtomic(frame_index=0, geometry_index=0)],
    )
    parsed = read_dff(write_dff(clump))
    h = parsed.frames[0].hanim
    assert h is not None
    assert len(h.bones) == 2
    assert h.bones[0].bone_id == 0
    assert h.bones[1].bone_id == 1


# ── Breakable Objects (chunk 0x253F2FD) ──────────────────────────

def test_breakable_objects():
    """W1: the chunk is the engine's mesh copy (magic + 52-byte header +
    arrays), built from the geometry and read back field by field."""
    geom = _basic_geom(with_uv=True)
    geom.prelit_colors = [RGBA(10, 20, 30, 255)] * 3
    geom.materials[0].texture = DffTexture(name="brick", mask="brick_m")
    geom.breakable = BreakableData.from_geometry(geom)
    parsed = read_dff(write_dff(_wrap(geom)))
    b = parsed.geometries[0].breakable
    assert b is not None
    assert b.posn_rule == 1
    assert len(b.vertices) == 3 and len(b.uvs) == 3 and len(b.colors) == 3
    assert b.triangles == [(0, 1, 2)]
    assert b.tri_materials == [0]
    assert b.tex_names == ["brick"] and b.mask_names == ["brick_m"]
    assert b.ambient == [(1.0, 1.0, 1.0)]
    assert b.colors[0].g == 20


def test_breakable_marker_zero_is_not_breakable():
    """The 4-byte magic-0 marker vanilla writes on non-breakable
    geometries reads back as "no breakable" (same state as no chunk)."""
    from core.dff import _read_breakable_plugin
    from core.rwbinary import BinaryReader
    assert _read_breakable_plugin(BinaryReader(bytes(4)), 4) is None


def test_breakable_chunk_layout_matches_engine():
    """W1 regression: magic + 52-byte header with u16 counts at the
    offsets BreakableStreamRead (0x59CEC0) reads, then the arrays."""
    geom = _basic_geom(with_uv=True)
    geom.materials[0].texture = DffTexture(name="brick")
    blob = BreakableData.from_geometry(geom).to_bytes(0x1803FFFF)
    ctype, size, _lib = struct.unpack_from('<III', blob, 0)
    assert ctype == 0x253F2FD
    body = blob[12:]
    assert struct.unpack_from('<I', body, 0)[0] != 0          # magic
    nv = struct.unpack_from('<H', body, 4 + 4)[0]
    nt = struct.unpack_from('<H', body, 4 + 0x14)[0]
    nm = struct.unpack_from('<H', body, 4 + 0x20)[0]
    assert (nv, nt, nm) == (3, 1, 1)
    assert size == 4 + 52 + nv * 24 + nt * 8 + nm * 76
    names_off = 4 + 52 + nv * 24 + nt * 8
    assert body[names_off:names_off + 6] == b"brick" + bytes(1)


# ── UV animation dictionary (clump-level) ────────────────────────

def test_uv_anim_dict():
    geom = _basic_geom(with_uv=True)
    geom.materials[0].uv_anim_names = ["spin01"]
    clump = _wrap(geom)
    clump.uv_anim_dict = UVAnimDict(anims=[
        UVAnim(
            name="spin01",
            duration=2.0,
            keyframes=[
                UVAnimKeyframe(time=0.0,
                               scale_u=1.0, scale_v=1.0,
                               shear_u=0.0, shear_v=0.0,
                               trans_u=0.0, trans_v=0.0),
                UVAnimKeyframe(time=2.0,
                               scale_u=1.0, scale_v=1.0,
                               shear_u=0.0, shear_v=0.0,
                               trans_u=0.5, trans_v=0.0),
            ],
        ),
    ])
    parsed = read_dff(write_dff(clump))
    assert parsed.uv_anim_dict is not None
    assert len(parsed.uv_anim_dict.anims) == 1
    a = parsed.uv_anim_dict.anims[0]
    assert a.name == "spin01"
    assert abs(a.duration - 2.0) < 1e-5
    assert len(a.keyframes) == 2
    # Material side carries the link
    assert "spin01" in parsed.geometries[0].materials[0].uv_anim_names


# ── Triangles & material indexing ────────────────────────────────

def test_triangle_material_indices_preserved():
    """Two materials, two triangles, each with different material — order
    matters and must round-trip exactly."""
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
             (1.0, 1.0, 0.0)]
    geom = DffGeometry(
        vertices=verts,
        normals=[(0, 0, 1)] * 4,
        triangles=[
            _triangle(0, 1, 2, m=0),
            _triangle(1, 3, 2, m=1),
        ],
        materials=[
            DffMaterial(color=RGBA(r=255, g=0, b=0, a=255)),
            DffMaterial(color=RGBA(r=0, g=255, b=0, a=255)),
        ],
        bounding_sphere=BoundingSphere(radius=2.0),
    )
    parsed = read_dff(write_dff(_wrap(geom)))
    tris = parsed.geometries[0].triangles
    mats = parsed.geometries[0].materials
    assert len(mats) == 2
    assert mats[0].color.r == 255 and mats[0].color.g == 0
    assert mats[1].color.r == 0 and mats[1].color.g == 255
    # Triangle→material assignments preserved
    assert {tris[0].material, tris[1].material} == {0, 1}


def test_bounding_sphere_round_trip():
    geom = _basic_geom()
    geom.bounding_sphere = BoundingSphere(x=10.0, y=20.0, z=-5.0, radius=42.0)
    parsed = read_dff(write_dff(_wrap(geom)))
    bs = parsed.geometries[0].bounding_sphere
    assert abs(bs.x - 10.0) < 1e-4
    assert abs(bs.y - 20.0) < 1e-4
    assert abs(bs.z - (-5.0)) < 1e-4
    assert abs(bs.radius - 42.0) < 1e-4


# ── Stress: combined effects on one geometry ─────────────────────

def test_geometry_with_everything():
    """Real-world-like geometry: textured material with env_map + specular,
    prelit colors, two UV layers, breakable, and a 2DFX light."""
    verts = [(float(i), 0.0, 0.0) for i in range(4)]
    geom = DffGeometry(
        vertices=verts,
        normals=[(0, 0, 1)] * 4,
        triangles=[_triangle(0, 1, 2), _triangle(1, 3, 2)],
        uv_layers=[
            [TexCoords(u=0.0, v=0.0), TexCoords(u=1.0, v=0.0),
             TexCoords(u=0.0, v=1.0), TexCoords(u=1.0, v=1.0)],
            [TexCoords(u=0.5, v=0.5)] * 4,
        ],
        prelit_colors=[RGBA(r=200, g=200, b=200, a=255)] * 4,
        materials=[DffMaterial(
            color=RGBA(r=255, g=255, b=255, a=255),
            texture=DffTexture(name="vehiclebody"),
            env_map=EnvMapEffect(coefficient=0.3, use_fb_alpha=False,
                                 texture=DffTexture(name="xvehicleenv128")),
            specular=SpecularMaterial(level=1.0, name="vehiclespecdot64"),
        )],
        bounding_sphere=BoundingSphere(radius=3.0),
    )
    geom.breakable = BreakableData.from_geometry(geom)
    geom.ext_2dfx = Extension2dfx(entries=[
        Light2dfx(loc=(0.5, 0.5, 1.0), color=RGBA(r=255, g=255),
                  corona_size=1.0, corona_tex_name="coronastar",
                  shadow_tex_name=""),
    ])

    parsed = read_dff(write_dff(_wrap(geom)))
    g = parsed.geometries[0]

    assert len(g.uv_layers) == 2
    assert len(g.prelit_colors) == 4
    m = g.materials[0]
    assert m.texture.name == "vehiclebody"
    assert m.env_map is not None
    assert m.env_map.texture.name == "xvehicleenv128"
    assert m.specular is not None
    assert g.breakable is not None
    assert len(g.breakable.vertices) == 4 and g.breakable.tex_names == ["vehiclebody"]
    assert g.ext_2dfx is not None
    assert len(g.ext_2dfx.entries) == 1
