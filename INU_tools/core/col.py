# INU_tools.core.col
# GTA SA collision format (COL1 / COL2 / COL3 / COL4) reader and writer.
# Pure Python, no Blender dependency.
#
# Written from scratch based on public COL format specifications:
#   https://gtamods.com/wiki/Collision_File
#
# COL file layout:
#   Header (28 bytes): magic(4) + filesize(4) + model_name(22) + model_id(2)
#   TBounds: bounding sphere + AABB
#   Body: version-dependent (spheres, boxes, vertices, faces, shadow mesh)

from dataclasses import dataclass, field
from struct import error as StructError
from .rwbinary import BinaryReader, BinaryWriter


# ── Data structures ──────────────────────────────────────────────

@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Surface:
    """Collision surface properties."""
    material: int = 0    # Surface type ID (0-178 for GTA SA)
    flags: int = 0
    brightness: int = 0
    light: int = 0


@dataclass
class Bounds:
    """Bounding sphere + axis-aligned bounding box."""
    center: Vec3 = field(default_factory=Vec3)
    radius: float = 0.0
    bb_min: Vec3 = field(default_factory=Vec3)
    bb_max: Vec3 = field(default_factory=Vec3)


@dataclass
class ColSphere:
    """Sphere collision primitive."""
    center: Vec3 = field(default_factory=Vec3)
    radius: float = 0.0
    surface: Surface = field(default_factory=Surface)


@dataclass
class ColBox:
    """Box collision primitive."""
    bb_min: Vec3 = field(default_factory=Vec3)
    bb_max: Vec3 = field(default_factory=Vec3)
    surface: Surface = field(default_factory=Surface)


@dataclass
class ColFace:
    """Triangle face with vertex indices + surface."""
    a: int = 0
    b: int = 0
    c: int = 0
    surface: Surface = field(default_factory=Surface)


@dataclass
class FaceGroup:
    """COL2/3 face group (flag 8): an AABB over the inclusive face range
    ``first..last``; the engine tests the box before any triangle of the
    group (CCollision::ProcessColModels). Faces outside every group never
    collide with moving entities, so groups must cover 0..numFaces-1."""
    bb_min: Vec3 = field(default_factory=Vec3)
    bb_max: Vec3 = field(default_factory=Vec3)
    first: int = 0
    last: int = 0


@dataclass
class ColModel:
    """Complete collision model."""
    version: int = 3           # 1=COLL, 2=COL2, 3=COL3, 4=COL4
    model_name: str = ""
    model_id: int = 0
    bounds: Bounds = field(default_factory=Bounds)
    spheres: list = field(default_factory=list)       # list[ColSphere]
    boxes: list = field(default_factory=list)          # list[ColBox]
    vertices: list = field(default_factory=list)       # list[Vec3]
    faces: list = field(default_factory=list)          # list[ColFace]
    shadow_vertices: list = field(default_factory=list)  # list[Vec3]
    shadow_faces: list = field(default_factory=list)     # list[ColFace]
    face_groups: list = field(default_factory=list)      # list[FaceGroup] (W6)
    flags: int = 0


# ── Magic numbers ────────────────────────────────────────────────

_VERSION_MAGIC = {
    1: b'COLL',
    2: b'COL2',
    3: b'COL3',
    4: b'COL4',
}
_MAGIC_VERSION = {v: k for k, v in _VERSION_MAGIC.items()}

# Header: magic(4) + file_size(4) + model_name(22) + model_id(2) = 32 bytes
_HEADER_SIZE = 32
_MODEL_NAME_LEN = 22
# The name is hashed up to its NUL, so 21 chars + NUL fit the field (COL-03).
MODEL_NAME_MAX = 21
_FACE_GROUP_SIZE = 28   # bb_min 3f, bb_max 3f, i16 first, i16 last

# Warnings collected by the last ``read_col`` (W11: a truncated / corrupt
# model stops the read like the engine does instead of raising).
COL_READ_WARNINGS = []


# ── Reader ───────────────────────────────────────────────────────

def _read_vec3(r: BinaryReader) -> Vec3:
    x, y, z = r.read('<3f')
    return Vec3(x, y, z)


def _read_surface(r: BinaryReader) -> Surface:
    mat, flags, bright, light = r.read('<4B')
    return Surface(mat, flags, bright, light)


def _read_bounds_v1(r: BinaryReader) -> Bounds:
    """COL1: radius, center, min, max."""
    b = Bounds()
    b.radius = r.read_float()
    b.center = _read_vec3(r)
    b.bb_min = _read_vec3(r)
    b.bb_max = _read_vec3(r)
    return b


def _read_bounds_v2(r: BinaryReader) -> Bounds:
    """COL2+: min, max, center, radius."""
    b = Bounds()
    b.bb_min = _read_vec3(r)
    b.bb_max = _read_vec3(r)
    b.center = _read_vec3(r)
    b.radius = r.read_float()
    return b


def _read_sphere_v1(r: BinaryReader) -> ColSphere:
    s = ColSphere()
    s.radius = r.read_float()
    s.center = _read_vec3(r)
    s.surface = _read_surface(r)
    return s


def _read_sphere_v2(r: BinaryReader) -> ColSphere:
    s = ColSphere()
    s.center = _read_vec3(r)
    s.radius = r.read_float()
    s.surface = _read_surface(r)
    return s


def _read_box(r: BinaryReader) -> ColBox:
    b = ColBox()
    b.bb_min = _read_vec3(r)
    b.bb_max = _read_vec3(r)
    b.surface = _read_surface(r)
    return b


def _read_face_v1(r: BinaryReader) -> ColFace:
    """COL1: 3x uint32 indices + full surface."""
    a, b, c = r.read('<3I')
    surface = _read_surface(r)
    return ColFace(a, b, c, surface)


def _read_face_v2(r: BinaryReader) -> ColFace:
    """COL2+: 3x uint16 indices + material(u8) + light(u8)."""
    a, b, c = r.read('<3H')
    mat = r.read_u8()
    light = r.read_u8()
    return ColFace(a, b, c, Surface(material=mat, light=light))


def _read_vertex_v1(r: BinaryReader) -> Vec3:
    """COL1: float vertices."""
    x, y, z = r.read('<3f')
    return Vec3(x, y, z)


def _read_vertex_v2(r: BinaryReader) -> Vec3:
    """COL2+: compressed int16 vertices (divide by 128)."""
    x, y, z = r.read('<3h')
    return Vec3(x / 128.0, y / 128.0, z / 128.0)


def _read_col1_body(r: BinaryReader, model: ColModel, model_end: int = -1):
    """Read COL1 body: count-prefixed blocks.

    ``model_end`` (absolute offset of the next model) bounds every count:
    a block that would run past it means a corrupt model (W11) and raises
    ``ValueError`` for ``read_col`` to stop on.
    """
    def _count(stride: int) -> int:
        n = r.read_u32()
        if model_end >= 0 and n * stride > model_end - r.pos:
            raise ValueError(f"count {n} × {stride} B runs past the model")
        return n

    # Spheres
    for _ in range(_count(20)):
        model.spheres.append(_read_sphere_v1(r))

    r.skip(4)  # unknown count (documented on gtamods)

    # Boxes
    for _ in range(_count(28)):
        model.boxes.append(_read_box(r))

    # Vertices
    for _ in range(_count(12)):
        model.vertices.append(_read_vertex_v1(r))

    # Faces
    for _ in range(_count(16)):
        model.faces.append(_read_face_v1(r))


def _read_col2_body(r: BinaryReader, model: ColModel, header_start: int):
    """Read COL2/3/4 body: offset-based layout."""
    (sphere_count, box_count, face_count, line_count,
     flags,
     spheres_off, boxes_off, lines_off,
     verts_off, faces_off, tri_planes_off
     ) = r.read('<HHHBxIIIIIII')

    model.flags = flags

    shadow_face_count = 0
    shadow_verts_off = 0
    shadow_faces_off = 0

    if model.version >= 3:
        shadow_face_count, shadow_verts_off, shadow_faces_off = r.read('<III')

    if model.version >= 4:
        r.skip(4)

    # Data offsets are relative to (header_start + 4) in the file,
    # because they skip the magic+size 8-byte prefix but the documented
    # offsets include model_name+model_id (24 bytes).
    base = header_start + 4  # after magic(4) only; size is part of body

    # Spheres
    r.seek(base + spheres_off)
    for _ in range(sphere_count):
        model.spheres.append(_read_sphere_v2(r))

    # Boxes
    r.seek(base + boxes_off)
    for _ in range(box_count):
        model.boxes.append(_read_box(r))

    # Faces
    r.seek(base + faces_off)
    for _ in range(face_count):
        model.faces.append(_read_face_v2(r))

    # Face groups (flag 8, W6): ``[groups][u32 count]`` sit right before the
    # face block — the engine reads the count at faces - 4 and the groups
    # growing downwards from there.
    if (flags & 8) and face_count and faces_off >= 4:
        r.seek(base + faces_off - 4)
        group_count = r.read_u32()
        if 0 < group_count < 0x10000 and faces_off >= 4 + group_count * _FACE_GROUP_SIZE:
            r.seek(base + faces_off - 4 - group_count * _FACE_GROUP_SIZE)
            for _ in range(group_count):
                g = FaceGroup()
                g.bb_min = _read_vec3(r)
                g.bb_max = _read_vec3(r)
                g.first, g.last = r.read('<hh')
                model.face_groups.append(g)

    # Vertex count: derived from max face index
    vert_count = 0
    for f in model.faces:
        vert_count = max(vert_count, f.a + 1, f.b + 1, f.c + 1)

    # Vertices (compressed int16)
    r.seek(base + verts_off)
    for _ in range(vert_count):
        model.vertices.append(_read_vertex_v2(r))

    # Shadow mesh (COL3+, flag bit 4)
    if model.version >= 3 and (flags & 16):
        # Shadow vertices: count derived from offset gap
        r.seek(base + shadow_verts_off)
        shadow_vert_count = (shadow_faces_off - shadow_verts_off) // 6  # 3 x int16 = 6 bytes
        for _ in range(shadow_vert_count):
            model.shadow_vertices.append(_read_vertex_v2(r))

        # Shadow faces
        r.seek(base + shadow_faces_off)
        for _ in range(shadow_face_count):
            model.shadow_faces.append(_read_face_v2(r))


def read_col(data: bytes) -> list:
    """
    Read a COL file (may contain multiple models).
    Returns list of ColModel.

    A truncated or corrupt model ends the read at that model with a
    warning in ``COL_READ_WARNINGS`` (W11) — the engine's loaders stop at
    the first bad entry too — instead of raising ``struct.error``.
    """
    r = BinaryReader(data)
    models = []
    COL_READ_WARNINGS.clear()

    while r.remaining() >= _HEADER_SIZE:
        header_start = r.pos

        magic = r.read_bytes(4)
        if magic not in _MAGIC_VERSION:
            break

        version = _MAGIC_VERSION[magic]
        file_size = r.read_u32()
        model_name = r.read_str(_MODEL_NAME_LEN)
        model_id = r.read_u16()

        model = ColModel(
            version=version,
            model_name=model_name,
            model_id=model_id,
        )

        try:
            if header_start + 8 + file_size > len(data):
                raise ValueError(
                    f"size {file_size} runs {header_start + 8 + file_size - len(data)} bytes past the end of the file")
            # Bounds
            if version == 1:
                model.bounds = _read_bounds_v1(r)
                _read_col1_body(r, model, header_start + 8 + file_size)
            else:
                model.bounds = _read_bounds_v2(r)
                _read_col2_body(r, model, header_start)
        except (StructError, ValueError, IndexError) as e:
            _w = _t(
                "COL: модель «{0}» (#{1}) обрезана или повреждена ({2}) — чтение остановлено на ней, как это делает движок."
            ).format(model_name or '?', len(models), e)
            COL_READ_WARNINGS.append(_w)
            print(f"[COL WARNING] {_w}")
            break

        # Jump to next model
        r.seek(header_start + file_size + 8)
        models.append(model)

    return models


def read_col_file(filepath: str) -> list:
    """Read COL models from a file."""
    with open(filepath, 'rb') as f:
        return read_col(f.read())


# ── Writer ───────────────────────────────────────────────────────

_U16_MAX = 65535


class ColLimitError(ValueError):
    """Raised when a ColModel exceeds the binary format's uint16 limits.

    Wraps the cryptic ``struct.pack('H', ...)`` overflow with a message
    that names the model and the specific count that broke the limit.
    """
    pass


def _t(s: str) -> str:
    """Lazy translation — falls back to raw Russian outside Blender so
    this pure-Python module stays import-safe for standalone tests."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


def _validate_col_writable(model: 'ColModel'):
    """Reject models that would overflow COL's uint16 fields.

    COL2/COL3/COL4 stores sphere/box/face counts and face vertex indices
    as uint16 (max 65 535). The COL header (all versions) stores model_id
    as uint16. COL1 uses uint32 for counts and indices, so only model_id
    is checked there.
    """
    name = model.model_name or "<unnamed>"

    if not (0 <= model.model_id <= _U16_MAX):
        raise ColLimitError(_t(
            "'{0}': model_id={1} вне диапазона 0..{2} (заголовок COL хранит ID в uint16)"
        ).format(name, model.model_id, _U16_MAX))

    if model.version == 1:
        return

    n_spheres = len(model.spheres)
    if n_spheres > _U16_MAX:
        raise ColLimitError(_t(
            "'{0}': {1} сфер — COL2/3/4 поддерживает максимум {2}"
        ).format(name, n_spheres, _U16_MAX))

    n_boxes = len(model.boxes)
    if n_boxes > _U16_MAX:
        raise ColLimitError(_t(
            "'{0}': {1} боксов — COL2/3/4 поддерживает максимум {2}"
        ).format(name, n_boxes, _U16_MAX))

    n_faces = len(model.faces)
    if n_faces > _U16_MAX:
        raise ColLimitError(_t(
            "'{0}': {1} треугольников — COL формат поддерживает максимум {2}. Разбей меш на части или упрости коллизию (Decimate)."
        ).format(name, n_faces, _U16_MAX))

    n_verts = len(model.vertices)
    if n_verts > _U16_MAX + 1:
        raise ColLimitError(_t(
            "'{0}': {1} вершин — COL хранит индексы в uint16 (максимум {2} вершин). Разбей меш на части или упрости коллизию (Decimate)."
        ).format(name, n_verts, _U16_MAX + 1))

    n_sh_faces = len(model.shadow_faces)
    if n_sh_faces > _U16_MAX:
        raise ColLimitError(_t(
            "'{0}': {1} shadow-треугольников — максимум {2}"
        ).format(name, n_sh_faces, _U16_MAX))

    n_sh_verts = len(model.shadow_vertices)
    if n_sh_verts > _U16_MAX + 1:
        raise ColLimitError(_t(
            "'{0}': {1} shadow-вершин — максимум {2}"
        ).format(name, n_sh_verts, _U16_MAX + 1))


def _write_vec3(w: BinaryWriter, v: Vec3):
    w.write_vec3(v.x, v.y, v.z)


def _write_surface(w: BinaryWriter, s: Surface):
    w.write('<4B', s.material, s.flags, s.brightness, s.light)


def _write_bounds_v1(w: BinaryWriter, b: Bounds):
    w.write_float(b.radius)
    _write_vec3(w, b.center)
    _write_vec3(w, b.bb_min)
    _write_vec3(w, b.bb_max)


def _write_bounds_v2(w: BinaryWriter, b: Bounds):
    _write_vec3(w, b.bb_min)
    _write_vec3(w, b.bb_max)
    _write_vec3(w, b.center)
    w.write_float(b.radius)


def _write_sphere_v1(w: BinaryWriter, s: ColSphere):
    w.write_float(s.radius)
    _write_vec3(w, s.center)
    _write_surface(w, s.surface)


def _write_sphere_v2(w: BinaryWriter, s: ColSphere):
    _write_vec3(w, s.center)
    w.write_float(s.radius)
    _write_surface(w, s.surface)


def _write_box(w: BinaryWriter, b: ColBox):
    _write_vec3(w, b.bb_min)
    _write_vec3(w, b.bb_max)
    _write_surface(w, b.surface)


def _write_face_v1(w: BinaryWriter, f: ColFace):
    w.write('<3I', f.a, f.b, f.c)
    _write_surface(w, f.surface)


def _write_face_v2(w: BinaryWriter, f: ColFace):
    w.write('<3H', f.a, f.b, f.c)
    w.write_u8(f.surface.material)
    w.write_u8(f.surface.light)


def _write_vertex_compressed(w: BinaryWriter, v: Vec3):
    """Write vertex as int16 * 128.

    Uses round() (nearest) rather than int() (truncate toward zero): plain
    truncation biases every vertex ~half a quantum toward the origin (up to
    1/128 ≈ 8 mm), and the systematic bias also pushes near-coincident verts
    together, spawning zero-area collision faces. Rounding halves the error
    and reduces those collapses.
    """
    w.write_i16(max(-32768, min(32767, round(v.x * 128))))
    w.write_i16(max(-32768, min(32767, round(v.y * 128))))
    w.write_i16(max(-32768, min(32767, round(v.z * 128))))


def _write_vertex_float(w: BinaryWriter, v: Vec3):
    _write_vec3(w, v)


def _write_col1_body(w: BinaryWriter, model: ColModel):
    """Write COL1 body."""
    # Spheres
    w.write_u32(len(model.spheres))
    for s in model.spheres:
        _write_sphere_v1(w, s)

    w.write_u32(0)  # unknown count

    # Boxes
    w.write_u32(len(model.boxes))
    for b in model.boxes:
        _write_box(w, b)

    # Vertices
    w.write_u32(len(model.vertices))
    for v in model.vertices:
        _write_vertex_float(w, v)

    # Faces
    w.write_u32(len(model.faces))
    for f in model.faces:
        _write_face_v1(w, f)


def _write_col2_body(w: BinaryWriter, model: ColModel):
    """Write COL2/3/4 body with offset-based layout."""
    # We build the data blocks first, tracking offsets,
    # then prepend the header with the correct offsets.

    # Calculate header size (from start of counts to start of data)
    # counts+flags+offsets: 2+2+2+1+1+4 + 6*4 = 36 bytes base
    header_size = 36
    if model.version >= 3:
        header_size += 12  # shadow_face_count + 2 offsets
    if model.version >= 4:
        header_size += 4   # extra padding

    # The offsets in the file are relative to the start of the body
    # (after the 4-byte magic). The body starts at: magic(4)+size(4)+name(22)+id(2)+bounds(40) = 72
    # But offsets are from after magic(4), so offset_base = size(4)+name(22)+id(2)+bounds(40) = 68
    bounds_size = 40  # 4 floats * 3 vectors + 1 float = 40 bytes
    offset_base = 4 + _MODEL_NAME_LEN + 2 + bounds_size  # = 68

    # Build data blocks
    data = BinaryWriter()

    # Spheres
    spheres_off = offset_base + header_size + len(data)
    for s in model.spheres:
        _write_sphere_v2(data, s)

    # Boxes
    boxes_off = offset_base + header_size + len(data)
    for b in model.boxes:
        _write_box(data, b)

    lines_off = 0  # Not implemented

    # Vertices (compressed)
    verts_off = offset_base + header_size + len(data)
    for v in model.vertices:
        _write_vertex_compressed(data, v)

    # Face groups (W6): ``[groups][u32 count]`` directly before the faces,
    # exactly where the engine looks for them (pTriangles - 4 - 28 * n).
    has_groups = bool(model.face_groups) and bool(model.faces)
    if has_groups:
        for g in model.face_groups:
            _write_vec3(data, g.bb_min)
            _write_vec3(data, g.bb_max)
            data.write('<hh', g.first, g.last)
        data.write_u32(len(model.face_groups))

    # Faces
    faces_off = offset_base + header_size + len(data)
    for f in model.faces:
        _write_face_v2(data, f)

    tri_planes_off = 0  # Not implemented

    # Shadow mesh
    has_shadow = model.version >= 3 and len(model.shadow_faces) > 0
    flags = 0
    flags |= 2 if (model.spheres or model.boxes or model.faces) else 0
    flags |= 8 if has_groups else 0
    flags |= 16 if has_shadow else 0

    if has_shadow:
        shadow_verts_off = offset_base + header_size + len(data)
        for v in model.shadow_vertices:
            _write_vertex_compressed(data, v)

        shadow_faces_off = offset_base + header_size + len(data)
        for f in model.shadow_faces:
            _write_face_v2(data, f)
    else:
        # Point to end of data (like DragonFF) — zero offsets can corrupt collision
        shadow_verts_off = offset_base + header_size + len(data)
        shadow_faces_off = offset_base + header_size + len(data)

    # Now write the header
    w.write('<HHHBxI',
            len(model.spheres),
            len(model.boxes),
            len(model.faces),
            0,  # line_count
            flags)
    w.write('<6I',
            spheres_off, boxes_off, lines_off,
            verts_off, faces_off, tri_planes_off)

    if model.version >= 3:
        w.write('<III',
                len(model.shadow_faces),
                shadow_verts_off,
                shadow_faces_off)

    if model.version >= 4:
        w.write_u32(0)

    # Append data blocks
    w.write_bytes(data.to_bytes())


def _clamp_surfaces_for_target(model: 'ColModel', target_game: str) -> int:
    """In-place clamp every Surface.material on the model into the
    target game's valid range. Returns the count of clamped surfaces
    (useful for the export report). Surfaces already within range are
    left alone — this is *not* a full game-to-game translation, just a
    safety net so the written byte never points at a non-existent
    entry in the target's surface table.

    Note: see ``core.surface_translate`` for the richer category-aware
    mapping when the source game is known.
    """
    from . import surface_translate
    count = 0
    def _walk(surface):
        nonlocal count
        clamped = surface_translate.clamp_surface_for_game(
            surface.material, target_game)
        if clamped != surface.material:
            surface.material = clamped
            count += 1
    for s in model.spheres:
        _walk(s.surface)
    for b in model.boxes:
        _walk(b.surface)
    for f in model.faces:
        _walk(f.surface)
    return count


def write_col(models: list, target_game: str = '') -> bytes:
    """
    Write one or more ColModel to COL binary format.
    Returns bytes.

    ``target_game`` ('III' / 'VC' / 'SA') clamps every surface ID into
    that game's table as a final safety pass — a byte past the table
    makes the engine read garbage material properties. The COL version
    says nothing about the game (SA ships COL1 weapons.col and COL2
    seabed/levelmap archives with SA surface IDs, W3), so with no target
    given nothing is clamped; ``core.col_lint`` reports out-of-range IDs.
    """
    out = BinaryWriter()

    for model in models:
        _validate_col_writable(model)
        if target_game:
            _clamp_surfaces_for_target(model, target_game)

        # Build body first to know its size
        body = BinaryWriter()

        # Bounds
        if model.version == 1:
            _write_bounds_v1(body, model.bounds)
            _write_col1_body(body, model)
        else:
            _write_bounds_v2(body, model.bounds)
            _write_col2_body(body, model)

        body_bytes = body.to_bytes()

        # Header
        magic = _VERSION_MAGIC.get(model.version, b'COL3')
        # file_size = body size + model_name(22) + model_id(2) = body + 24
        file_size = len(body_bytes) + _MODEL_NAME_LEN + 2

        out.write_bytes(magic)
        out.write_u32(file_size)
        out.write_str(model.model_name, _MODEL_NAME_LEN)
        out.write_u16(model.model_id)
        out.write_bytes(body_bytes)

    return out.to_bytes()


def write_col_file(filepath: str, models: list, target_game: str = ''):
    """Write COL models to a file."""
    with open(filepath, 'wb') as f:
        f.write(write_col(models, target_game=target_game))
