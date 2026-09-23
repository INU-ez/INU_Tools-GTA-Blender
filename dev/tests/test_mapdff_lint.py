"""core.mapdff_lint — pre-write audit of a map / object clump against what
gta_sa.exe dereferences when it streams it (DFF-03..DFF-70 in
E:\\RE\\addon_check\\mapdff_path.md), plus regressions for the DFF writer
fixes from the same engine read: W1 breakable chunk layout, W2 ped
attractor size, W8 texture-name limit, W12 unknown 2dfx types, W13 2dfx
name fields, W14 night-colour count.

Every rule gets a passing and a failing case built from synthetic core
structures. Pure Python — no Blender required.
"""

from pathlib import Path
from struct import pack, unpack_from
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.dff import (  # noqa: E402
    DffClump, DffFrame, DffGeometry, DffAtomic, DffMaterial, DffTexture,
    Triangle, BoundingSphere, RGBA, TexCoords, ExtraVertColors, BreakableData,
    Light2dfx, Particle2dfx, PedAttractor2dfx, SunGlare2dfx, RawUnknown2dfx,
    Extension2dfx, UVAnim, UVAnimDict, HAnimData, DffLimitError, SkinData,
    DFF_EXPORT_WARNINGS, TEXTURE_NAME_MAX, write_dff, read_dff,
    _read_2dfx_plugin, CHUNK_2DFXPLG, CHUNK_BREAKABLE, CHUNK_EXTRA_COLORS,
)
from core.rwbinary import BinaryReader  # noqa: E402
from core.mapdff_lint import check_map_clump  # noqa: E402


def _geom(nv=3, with_uv=True, prelit=False):
    g = DffGeometry(
        vertices=[(float(i), 0.0, 0.0) for i in range(nv)],
        normals=[(0.0, 0.0, 1.0)] * nv,
        triangles=[Triangle(a=0, b=1, c=2, material=0)],
        materials=[DffMaterial(texture=DffTexture(name="brick"))],
        bounding_sphere=BoundingSphere(1.0, 0.0, 0.0, 2.0),
    )
    if with_uv:
        g.uv_layers = [[TexCoords(0.0, 0.0)] * nv]
    if prelit:
        g.prelit_colors = [RGBA()] * nv
    return g


def _clump(geoms=None, frames=None, atomics=None):
    geoms = geoms if geoms is not None else [_geom()]
    if frames is None:
        frames = [DffFrame(name="root", parent=-1, write_name=True),
                  DffFrame(name="obj", parent=0, write_name=True)]
    if atomics is None:
        atomics = [DffAtomic(frame_index=1, geometry_index=i) for i in range(len(geoms))]
    return DffClump(frames=frames, geometries=geoms, atomics=atomics)


def _has(items, tag):
    return any(tag in s for s in items)


# ── baseline ─────────────────────────────────────────────────────

def test_clean_clump_passes():
    fatal, warn = check_map_clump(_clump())
    assert fatal == [] and warn == []


def test_skinned_clump_is_not_audited():
    g = _geom()
    g.skin = SkinData(num_bones=1)
    fatal, warn = check_map_clump(_clump([g]))
    assert fatal == [] and warn == []


# ── frames / atomics ─────────────────────────────────────────────

def test_no_frames_fatal():
    fatal, _ = check_map_clump(_clump(frames=[], atomics=[DffAtomic(0, 0)]))
    assert _has(fatal, "DFF-03")


def test_forward_parent_fatal():
    frames = [DffFrame(name="a", parent=1), DffFrame(name="b", parent=0)]
    fatal, _ = check_map_clump(_clump(frames=frames, atomics=[DffAtomic(1, 0)]))
    assert _has(fatal, "DFF-06")


def test_self_parent_fatal():
    frames = [DffFrame(name="a", parent=0)]
    fatal, _ = check_map_clump(_clump(frames=frames, atomics=[DffAtomic(0, 0)]))
    assert _has(fatal, "DFF-06")


def test_long_frame_name_fatal():
    frames = [DffFrame(name="x" * 24, parent=-1, write_name=True)]
    fatal, _ = check_map_clump(_clump(frames=frames, atomics=[DffAtomic(0, 0)]))
    assert _has(fatal, "24-байтовом") or _has(fatal, "24-byte")


def test_no_atomics_fatal():
    fatal, _ = check_map_clump(_clump(atomics=[]))
    assert _has(fatal, "DFF-03")


def test_atomic_frame_index_out_of_range_fatal():
    fatal, _ = check_map_clump(_clump(atomics=[DffAtomic(frame_index=7, geometry_index=0)]))
    assert _has(fatal, "DFF-05")


def test_atomic_geometry_index_out_of_range_fatal():
    fatal, _ = check_map_clump(_clump(atomics=[DffAtomic(frame_index=1, geometry_index=3)]))
    assert _has(fatal, "DFF-07")


def test_atomic_without_render_flag_warns():
    _, warn = check_map_clump(_clump(atomics=[DffAtomic(1, 0, flags=1)]))
    assert _has(warn, "DFF-41")


def test_multiple_plain_atomics_warn_but_not_for_hanim():
    frames = [DffFrame(name="root", parent=-1), DffFrame(name="a", parent=0),
              DffFrame(name="b", parent=0)]
    geoms = [_geom(), _geom()]
    atomics = [DffAtomic(1, 0), DffAtomic(2, 1)]
    _, warn = check_map_clump(_clump(geoms, frames, atomics))
    assert _has(warn, "DFF-27")
    frames[0].hanim = HAnimData(bone_id=0)
    _, warn = check_map_clump(_clump(geoms, frames, atomics))
    assert not _has(warn, "DFF-27")


def test_dam_atomic_warns_about_ide_flag():
    frames = [DffFrame(name="root", parent=-1), DffFrame(name="crate_dam", parent=0)]
    _, warn = check_map_clump(_clump(frames=frames))
    assert _has(warn, "DFF-28")


def test_transformed_single_atomic_frame_warns():
    # Чистое СМЕЩЕНИЕ — штатный round-trip INU (позицию в игре несёт IPL),
    # НЕ предупреждаем. Запечённый ПОВОРОТ/масштаб движок так же отбрасывает —
    # вот на него DFF-29 и ругается.
    frames = [DffFrame(name="root", parent=-1),
              DffFrame(name="obj", parent=0, position=(1.0, 2.0, 3.0))]
    _, warn = check_map_clump(_clump(frames=frames))
    assert not _has(warn, "DFF-29")

    frames[1].rotation = (0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)  # 90° Z
    _, warn = check_map_clump(_clump(frames=frames))
    assert _has(warn, "DFF-29")


def test_model_name_too_long_fatal():
    fatal, _ = check_map_clump(_clump(), model_name="a" * 24)
    assert _has(fatal, "DFF-70")
    fatal, _ = check_map_clump(_clump(), model_name="a" * 23)
    assert not _has(fatal, "DFF-70")


# ── geometry ─────────────────────────────────────────────────────

def test_too_many_vertices_fatal():
    g = _geom(nv=3)
    g.vertices = [(0.0, 0.0, 0.0)] * 65536
    g.normals = [(0.0, 0.0, 1.0)] * 65536
    g.uv_layers = [[TexCoords()] * 65536]
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-09")


def test_empty_geometry_warns():
    g = DffGeometry(materials=[DffMaterial()], bounding_sphere=BoundingSphere(0, 0, 0, 1))
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-26")


def test_texcoord_sets_rules():
    g = _geom()
    g.uv_layers = [[TexCoords()] * 3] * 3
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-11")
    g.uv_layers = [[TexCoords()] * 3] * 9
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-11")


def test_native_flag_fatal():
    g = _geom()
    g.is_native_ogl = True          # the writer then sets NATIVE (0x01000000)
    c = _clump([g])
    fatal, _ = check_map_clump(c)
    assert _has(fatal, "DFF-12")
    c.is_mobile = True              # mobile export: native data is expected
    fatal, _ = check_map_clump(c)
    assert not _has(fatal, "DFF-12")


def test_per_vertex_array_length_mismatch_fatal():
    g = _geom(prelit=True)
    g.prelit_colors = g.prelit_colors[:-1]
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-13")
    g = _geom()
    g.uv_layers[0] = g.uv_layers[0][:-1]
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-13")
    g = _geom()
    g.normals = g.normals[:-1]
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-13")


def test_no_materials_with_triangles_fatal():
    g = _geom()
    g.materials = []
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-14")


def test_triangle_vertex_index_out_of_range_fatal():
    g = _geom()
    g.triangles = [Triangle(0, 1, 3, 0)]
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-23")


def test_triangle_material_index_out_of_range_fatal():
    g = _geom()
    g.triangles = [Triangle(0, 1, 2, 1)]
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-20")


def test_bounding_sphere_rules():
    g = _geom()
    g.bounding_sphere = BoundingSphere(0.0, 0.0, 0.0, 0.0)
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-25")
    g.bounding_sphere = BoundingSphere(0.0, 0.0, 0.0, 1.0)   # vertex at x=2 outside
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-25")
    g.bounding_sphere = BoundingSphere(1.0, 0.0, 0.0, 1.0)   # exactly encloses
    _, warn = check_map_clump(_clump([g]))
    assert not _has(warn, "DFF-25")


def test_night_colours_rules():
    g = _geom()
    g.extra_colors = ExtraVertColors(colors=[RGBA()] * 3)
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-43")
    g = _geom(prelit=True)
    g.extra_colors = ExtraVertColors(colors=[RGBA()] * 2)
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-45") and not _has(warn, "DFF-43")
    g.extra_colors = ExtraVertColors(colors=[RGBA()] * 3)
    _, warn = check_map_clump(_clump([g]))
    assert not _has(warn, "DFF-45")


def test_unknown_pipeline_warns():
    g = _geom()
    g.pipeline = 0x12345678
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-08")
    g.pipeline = 0x53F2009C
    _, warn = check_map_clump(_clump([g]))
    assert not _has(warn, "DFF-08")


# ── materials ────────────────────────────────────────────────────

def test_texture_name_rules():
    g = _geom()
    g.materials[0].texture.name = "x" * 32
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-19")
    g.materials[0].texture.name = "x" * 31
    fatal, warn = check_map_clump(_clump([g]))
    assert not _has(fatal, "DFF-19")
    g.materials[0].texture.name = ""
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-19")
    g.materials[0].texture.name = "кирпич"
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-19")


def test_black_modulate_material_warns():
    g = _geom()
    g.original_flags = 0x40 | 0x2F
    g.export_mod_color = True
    g.materials[0].color = RGBA(0, 0, 0, 255)
    _, warn = check_map_clump(_clump([g]))
    assert _has(warn, "DFF-46")


def test_vehicle_clump_skips_objs_only_rules():
    # A vehicle / weapon keeps every atomic, owns the _dam slot, honours
    # frame transforms and paints black body colours through the car
    # pipeline — DFF-27/28/29/46 are objs/tobj rules only (vanilla
    # infernus.dff would otherwise collect 9 false warnings).
    frames = [DffFrame(name="chassis", parent=-1),
              DffFrame(name="wheel_lf_dummy", parent=0, position=(1.0, 2.0, 3.0)),
              DffFrame(name="door_lf_dam", parent=0),
              DffFrame(name="door_lf_ok", parent=0)]
    g1, g2, g3 = _geom(), _geom(), _geom()
    g1.original_flags = 0x40 | 0x2F
    g1.export_mod_color = True
    g1.materials[0].color = RGBA(0, 0, 0, 255)
    atomics = [DffAtomic(1, 0), DffAtomic(2, 1), DffAtomic(3, 2)]
    _, warn = check_map_clump(_clump([g1, g2, g3], frames, atomics))
    assert _has(warn, "DFF-27") and _has(warn, "DFF-28") and _has(warn, "DFF-46")
    fatal, warn = check_map_clump(_clump([g1, g2, g3], frames, atomics), is_vehicle=True)
    assert fatal == [] and warn == []
    # Single transformed atomic: DFF-29 for objs, nothing for a vehicle.
    _, warn = check_map_clump(_clump(frames=frames[:2]), is_vehicle=True)
    assert not _has(warn, "DFF-29")


def test_uv_anim_rules():
    g = _geom()
    g.materials[0].uv_anim_names = ["missing"]
    c = _clump([g])
    c.uv_anim_dict = UVAnimDict(anims=[UVAnim(name="present")])
    _, warn = check_map_clump(c)
    assert _has(warn, "DFF-51")
    g.materials[0].uv_anim_names = ["present"]
    _, warn = check_map_clump(c)
    assert not _has(warn, "DFF-51")
    g.materials[0].uv_anim_names = ["present"] * 9
    fatal, _ = check_map_clump(c)
    assert _has(fatal, "DFF-54")
    g.materials[0].uv_anim_names = ["n" * 32]
    fatal, _ = check_map_clump(c)
    assert _has(fatal, "DFF-54")


# ── 2dfx ─────────────────────────────────────────────────────────

def _fx(*entries):
    g = _geom()
    g.ext_2dfx = Extension2dfx(entries=list(entries))
    return _clump([g])


def test_2dfx_unknown_type_warns():
    _, warn = check_map_clump(_fx(RawUnknown2dfx(effect_id=2, raw=b"\0" * 4)))
    assert _has(warn, "DFF-32")
    _, warn = check_map_clump(_fx(RawUnknown2dfx(effect_id=8, raw=pack('<I', 1))))
    assert not _has(warn, "DFF-32")
    _, warn = check_map_clump(_fx(RawUnknown2dfx(effect_id=8, raw=b"\0" * 6)))
    assert _has(warn, "DFF-32")


def test_2dfx_light_rules():
    ok = Light2dfx(loc=(1.0, 0.0, 0.0), flags1=0x60, corona_size=1.0,
                   corona_tex_name="coronastar", shadow_size=1.0, shadow_tex_name="shad_exp")
    fatal, warn = check_map_clump(_fx(ok))
    assert fatal == [] and warn == []
    bad = Light2dfx(loc=(1.0, 0.0, 0.0), flags1=0x60, shadow_size=1.0, shadow_tex_name="")
    fatal, _ = check_map_clump(_fx(bad))
    assert _has(fatal, "DFF-34")
    _, warn = check_map_clump(_fx(Light2dfx(loc=(1, 0, 0), flags1=0, corona_size=1.0)))
    assert _has(warn, "DFF-35") and _has(warn, "DFF-34")
    _, warn = check_map_clump(_fx(Light2dfx(loc=(1, 0, 0), flags1=0x20, corona_show_mode=14)))
    assert _has(warn, "DFF-35")
    _, warn = check_map_clump(_fx(Light2dfx(loc=(1, 0, 0), flags1=0x20, corona_far_clip=-1.0)))
    assert _has(warn, "DFF-35")
    _, warn = check_map_clump(_fx(Light2dfx(loc=(1, 0, 0), flags1=0x20, corona_tex_name="x" * 24)))
    assert _has(warn, "W13")


def test_2dfx_particle_rules():
    _, warn = check_map_clump(_fx(Particle2dfx(loc=(1, 0, 0), effect_name="")))
    assert _has(warn, "DFF-36")
    _, warn = check_map_clump(_fx(Particle2dfx(loc=(1, 0, 0), effect_name="p" * 24)))
    assert _has(warn, "W13")
    _, warn = check_map_clump(_fx(Particle2dfx(loc=(1, 0, 0), effect_name="prt_smoke")))
    assert warn == []


def test_2dfx_position_far_from_model_warns():
    _, warn = check_map_clump(_fx(Particle2dfx(loc=(50.0, 0.0, 0.0), effect_name="fire")))
    assert _has(warn, "DFF-39")


def test_2dfx_count_over_255_warns():
    entries = [SunGlare2dfx(loc=(0, 0, 0)) for _ in range(256)]
    _, warn = check_map_clump(_fx(*entries))
    assert _has(warn, "DFF-33")


# ── breakable ────────────────────────────────────────────────────

def test_breakable_consistency():
    g = _geom()
    g.breakable = BreakableData.from_geometry(g)
    fatal, warn = check_map_clump(_clump([g]))
    assert fatal == []
    g.breakable.triangles = [(0, 1, 9)]
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-60")
    g.breakable = BreakableData.from_geometry(g)
    g.breakable.tri_materials = [4]
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-60")
    g.breakable = BreakableData.from_geometry(g)
    g.breakable.uvs = []
    fatal, _ = check_map_clump(_clump([g]))
    assert _has(fatal, "DFF-60")


# ── writer regressions ───────────────────────────────────────────

def _plugin(blob, chunk_type):
    """First plugin chunk body of ``chunk_type`` anywhere in ``blob``."""
    off = 0
    while off + 12 <= len(blob):
        t, sz, _ = unpack_from('<III', blob, off)
        if t == chunk_type and sz <= len(blob) - off - 12:
            return blob[off + 12:off + 12 + sz]
        off += 1
    return None


def test_w1_breakable_written_in_engine_layout():
    g = _geom(prelit=True)
    g.breakable = BreakableData.from_geometry(g)
    body = _plugin(write_dff(_clump([g])), CHUNK_BREAKABLE)
    assert body is not None
    nv = unpack_from('<H', body, 8)[0]
    nt = unpack_from('<H', body, 4 + 0x14)[0]
    nm = unpack_from('<H', body, 4 + 0x20)[0]
    assert (nv, nt, nm) == (3, 1, 1)
    assert len(body) == 4 + 52 + nv * 24 + nt * 8 + nm * 76
    back = read_dff(write_dff(_clump([g]))).geometries[0].breakable
    assert back.triangles == [(0, 1, 2)] and back.tex_names == ["brick"]


def test_w2_ped_attractor_is_56_bytes_and_keeps_tail():
    ped = PedAttractor2dfx(loc=(0, 0, 0), attractor_type=4, external_script="atm",
                           ped_existing_probability=80, flags=0x23, unknown=1)
    body = _plugin(write_dff(_fx(ped)), CHUNK_2DFXPLG)
    count = unpack_from('<I', body, 0)[0]
    assert count == 1
    etype, esize = unpack_from('<II', body, 4 + 12)
    assert (etype, esize) == (3, 56)
    back = read_dff(write_dff(_fx(ped))).geometries[0].ext_2dfx.entries[0]
    assert back.flags == 0x23 and back.unknown == 1


def test_w8_long_texture_name_refused():
    g = _geom()
    g.materials[0].texture.name = "t" * (TEXTURE_NAME_MAX + 1)
    with pytest.raises(DffLimitError):
        write_dff(_clump([g]))
    g.materials[0].texture.name = "t" * TEXTURE_NAME_MAX
    write_dff(_clump([g]))


def test_w12_unknown_2dfx_type_dropped_with_warning():
    c = _fx(RawUnknown2dfx(effect_id=2, loc=(0, 0, 0), raw=b"\0" * 8),
            RawUnknown2dfx(effect_id=8, loc=(0, 0, 0), raw=pack('<I', 5)))
    blob = write_dff(c)
    assert any("2DFX" in w and "2" in w for w in DFF_EXPORT_WARNINGS)
    entries = read_dff(blob).geometries[0].ext_2dfx.entries
    assert [e.effect_id for e in entries] == [8]


def test_w13_2dfx_names_keep_a_nul_in_24_bytes():
    light = Light2dfx(loc=(0, 0, 0), corona_tex_name="c" * 30, shadow_tex_name="s" * 24)
    part = Particle2dfx(loc=(0, 0, 0), effect_name="p" * 24)
    blob = write_dff(_fx(light, part))
    body = _plugin(blob, CHUNK_2DFXPLG)
    ext = _read_2dfx_plugin(BinaryReader(body), len(body))
    assert ext.entries[0].corona_tex_name == "c" * 23
    assert ext.entries[0].shadow_tex_name == "s" * 23
    assert ext.entries[1].effect_name == "p" * 23
    assert sum(1 for w in DFF_EXPORT_WARNINGS if "2DFX" in w) == 3
    # the raw fields end in a NUL
    light_payload = body[4 + 20:4 + 20 + 80]
    assert light_payload[0x19 + 23] == 0 and light_payload[0x31 + 23] == 0


def test_w14_night_colours_padded_to_vertex_count():
    g = _geom(prelit=True)
    g.extra_colors = ExtraVertColors(colors=[RGBA(1, 2, 3, 4)])
    blob = write_dff(_clump([g]))
    body = _plugin(blob, CHUNK_EXTRA_COLORS)
    assert len(body) == 4 + 3 * 4
    assert any("numVertices" in w for w in DFF_EXPORT_WARNINGS)
    g.extra_colors = ExtraVertColors(colors=[RGBA()] * 5)
    body = _plugin(write_dff(_clump([g])), CHUNK_EXTRA_COLORS)
    assert len(body) == 4 + 3 * 4
