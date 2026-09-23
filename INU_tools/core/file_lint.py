# INU_tools.core.file_lint
# Binary file linter for DFF / COL / TXD — finds crash-prone patterns
# in compiled assets WITHOUT loading them into Blender. Pure Python,
# bpy-free, unit-testable.
#
# Phase 1: COL only. Catches the Manu 2026-05-03 crash 0x415D47 class
# (collision streaming nullptr+0x262) — typically caused by COL files
# with a shadow flag set but zero shadow faces, or by surface IDs
# beyond the vanilla 0..179 range.
#
# Issue codes are stable identifiers — do not rename without updating
# UI / tests / docs.

from dataclasses import dataclass, field
from math import isnan, isinf
import os
import struct
from typing import List, Literal

from . import lint_profile


Severity = Literal['ERROR', 'WARN', 'INFO']


@dataclass(frozen=True)
class LintIssue:
    severity: Severity
    code: str           # stable key: 'COL_SHADOW_INCONSISTENT', etc.
    file: str           # absolute path
    where: str          # 'model[1].sphere[7]' / '' for file-level
    message: str        # human-readable

    def format_short(self) -> str:
        loc = f" {self.where}" if self.where else ""
        return f"{self.severity:5s} {self.code:28s}{loc}: {self.message}"


# ── Helpers ──────────────────────────────────────────────────────

def _bad_float(v) -> bool:
    """True if the float is NaN or infinite — both crash the engine."""
    try:
        return isnan(v) or isinf(v)
    except TypeError:
        return True


# ── COL linter ───────────────────────────────────────────────────
#
# Surface ID range: vanilla SA accepts 0..178 (179 if you count «road»
# variants). Fastman92 Limit Adjuster widens to 0..254. We warn at
# >178 and error at >254 — a value that big *will* read past the
# surface table no matter the loader.
_COL_SURFACE_VANILLA_MAX = 178
_COL_SURFACE_FLA_MAX = 254


# ── Issue code → human-readable explanation ──────────────────────
#
# Used by the panel to show a 2-3 line description for the selected
# issue. Keep the messages terse but actionable. New codes MUST be
# added here too — the panel falls back to "(нет описания)" otherwise.
EXPLANATIONS = {
    # --- COL: file-level
    'COL_FS_ERROR': "Файл COL не читается с диска (нет прав / сломан / removed). "
                     "Проверь существование файла и его permissions.",
    'COL_TOO_SMALL': "Файл меньше минимального COL-заголовка (28 байт). "
                      "Скорее всего обрезан или вообще не COL.",
    'COL_BAD_MAGIC': "Первые 4 байта не совпадают с сигнатурой COLL/COL2/COL3/COL4. "
                      "Это либо неверное расширение, либо файл поломан.",
    'COL_PARSE_FAIL': "Парсер COL упал на чтении. Файл повреждён или формат "
                       "нестандартный. Откройте в COL Editor для ручной проверки.",
    'COL_NO_MODELS': "Файл выглядит как COL, но не содержит ни одной модели. "
                      "Скорее всего пустой или с битым заголовком.",
    'COL_HEADER_FILESIZE_MISMATCH':
        "Поле filesize в заголовке не совпадает с реальным размером на диске. "
        "Стримминг GTA читает по этому полю и может уйти за буфер → CTD.",
    'COL_SHADOW_OFFSETS_BAD':
        "shadow_face_count > 0, но смещения shadow_verts_off / shadow_faces_off "
        "указывают за пределы файла. Это и есть классический crash 0x415D47 "
        "при стриминге коллизии (у Manu 2026-05-03).",
    # --- COL: per-model
    'COL_BAD_BOUND_RADIUS':
        "Bounding sphere радиус NaN/Inf или ≤ 0. Движок использует bound для "
        "кулинга — некорректное значение либо отключит видимость, либо упадёт.",
    'COL_BAD_BBOX':
        "Bounding box содержит NaN/Inf. Может произойти при ошибке экспорта "
        "пустого меша. Пересохрани COL из исходника.",
    'COL_BBOX_INVERTED':
        "Bounding box имеет min > max. Эту ошибку допускают некоторые экспортёры "
        "при экспорте «вывернутых» нормалей. Безопасно но указывает на проблему.",
    'COL_BAD_SPHERE_RADIUS':
        "Коллайдер-сфера с радиусом ≤ 0 или NaN/Inf. Физика падает при контакте.",
    'COL_BAD_SPHERE_CENTER':
        "Center коллайдер-сферы содержит NaN/Inf. Объект не будет обнаруживаться.",
    'COL_FACE_NO_VERTS':
        "Модель содержит грани, но нет вершин. Стрим прочитает за невыделенный "
        "буфер → почти гарантированный CTD.",
    'COL_FACE_INDEX_OOR':
        "Индекс вершины в треугольнике ≥ количества вершин. Engine читает "
        "вершину за пределами буфера → CTD при касании.",
    'COL_SURFACE_ID_OOR':
        "Surface ID > 254 — невозможно даже с FLA. Перезапиши surface IDs "
        "корректным значением (vanilla 0-178, FLA до 254).",
    'COL_SURFACE_ID_FLA_ONLY':
        "Surface ID 179-254 — будет работать только с Fastman92 Limit Adjuster. "
        "На ванильной SA вызовет CTD при загрузке IPL.",
    'COL_SHADOW_NO_VERTS':
        "Модель имеет shadow_faces > 0, но shadow_vertices = 0. Тени упадут "
        "при первом raycast — двигатель прочитает 3 индекса в пустой буфер.",
    'COL_FACE_COUNT_HIGH':
        "Слишком много граней в коллизии. Vanilla SA props редко имеют >5k "
        "collision faces — выше начнётся stutter в физике.",
    'COL_FACE_COUNT_VERY_HIGH':
        "Очень большая коллизия. Engine начинает заметно проседать на физ-проверках. "
        "Разделить меш или сильно упростить (Decimate / Convex hull).",
    'COL_VERT_COUNT_VERY_HIGH':
        "Близко к u16-лимиту вершин коллизии (65 535). Если меш ещё растёт — "
        "лимит будет превышен и парсер упадёт.",

    # --- DFF (Phase 2)
    'DFF_FS_ERROR': "Файл DFF не читается с диска.",
    'DFF_TOO_SMALL': "Файл меньше минимального RW-заголовка. Битый или не DFF.",
    'DFF_PARSE_FAIL': "Парсер DFF упал. Файл повреждён или версия RW не поддерживается.",
    'DFF_PARSER_INCOMPATIBLE':
        "Файл начинается с валидного RW чанка, но не с Clump (0x10) — "
        "наш парсер не умеет такой entry point. Vanilla SA имеет файлы "
        "вроде chinafurn1.dff которые начинаются с 0x2B (UV anim dict) "
        "перед Clump. В игре загружаются нормально — линтер просто не "
        "может проверить содержимое.",
    'DFF_GEOM_VERT_COUNT_HARD':
        "Geometry превышает u16-лимит вершин (65 535). Engine читает индекс "
        "по 2 байта — индекс старше 65 535 интерпретируется как 0 → CTD.",
    'DFF_GEOM_VERT_COUNT_HIGH':
        "Geometry близко к u16-лимиту вершин. Глюки рендера обычно начинаются "
        "уже при 32k+. Разбить на несколько geometry или Decimate.",
    'DFF_GEOM_TRI_COUNT_HARD':
        "Geometry превышает u16-лимит треугольников (65 535).",
    'DFF_GEOM_TRI_COUNT_HIGH':
        "Geometry имеет очень много треугольников. На практике стабильно работает "
        "до ~30-40k, дальше зависит от GPU драйвера.",
    'DFF_GEOM_MAT_COUNT_VANILLA':
        "Geometry имеет >50 материалов. Vanilla SA рендерит максимум 50 — "
        "выше материалы будут пропущены или вызовут CTD.",
    'DFF_GEOM_MAT_COUNT_HARD':
        "Geometry превышает u16-лимит материалов (65 535).",
    'DFF_GEOM_UV_LAYERS_HIGH':
        "Geometry имеет >2 UV-слоёв. Vanilla SA использует только 2 (UV0 + lightmap UV2). "
        "Лишние слои не рендерятся, но занимают место и могут запутать LightMap.",
    'DFF_SKIN_BONES_HARD':
        "Skin PLG: число костей превышает u8-лимит (255). Анимация будет битая или CTD.",
    'DFF_SKIN_WEIGHTS_HARD':
        "Skin PLG: max_weights > 4. Engine считает максимум 4 — лишние веса игнорируются.",
    'DFF_2DFX_COUNT_HIGH':
        "На объекте >8 эффектов 2DFX. Может вызвать визуальные лаги при загрузке "
        "света/частиц вокруг объекта.",
    'DFF_ATOMIC_FRAME_OOR':
        "Atomic ссылается на frame_index за пределами массива frames. Стрим "
        "разыменует за буфер при настройке трансформа → CTD.",
    'DFF_ATOMIC_GEOM_OOR':
        "Atomic ссылается на geometry_index за пределами geometries. Тоже "
        "вызовет out-of-bounds при инициализации меша.",
    'DFF_ATOMIC_FRAME_NOT_ROOT':
        "Skinned clump: atomic.frame_index указывает внутрь иерархии костей "
        "(на потомка корня скелета), а должен быть корнем или его родителем. "
        "SA streaming вылетит при попытке прицепить атомик к листу скелета.",
    'DFF_FRAME_PARENT_OOR':
        "Frame.parent указывает на несуществующий frame или на самого себя. "
        "Ломает иерархию костей и трансформов.",
    'DFF_TRI_INDEX_OOR':
        "Triangle ссылается на vertex с индексом >= количества вершин. "
        "Render будет читать память за вершинным буфером.",
    'DFF_VERT_NAN':
        "Vertex position содержит NaN/Inf. После трансформа окажется в "
        "бесконечности — bounding sphere сломается, объект пропадёт.",
    'DFF_BSPHERE_BAD':
        "Bounding sphere geometry имеет отрицательный или NaN/Inf радиус. "
        "Кулинг будет работать неправильно.",
    'DFF_SKIN_BONE_INDEX_OOR':
        "В skin PLG bone_indices ссылается на кость за пределами num_bones. "
        "Анимация привяжет вершину к мусорной матрице — деформация улетит.",
    'DFF_GEOM_NATIVE_ON_PC':
        "Geometry flags содержит бит GEOM_NATIVE (0x01000000). Это значит, "
        "что данные геометрии лежат в платформенной extension (PS2/Xbox), а "
        "не в стандартном Geometry struct. PC engine не умеет читать native "
        "PS2-данные → CTD при первом рендере. Конвертируй через TxdGen в PC.",
    'DFF_UV_FLAG_MISMATCH':
        "Количество UV-слоёв в flags ((flags>>16)&0xFF) не совпадает с реальным "
        "массивом uv_layers. Engine читает UV по количеству из flags — пробежит "
        "за конец буфера и прочитает мусор / упадёт.",
    'DFF_PRELIT_FLAG_NO_DATA':
        "Bit GEOM_PRELIT (0x08) во flags выставлен, но массив prelit_colors пуст. "
        "Engine попытается прочитать N×4 байта vertex colors из несуществующего "
        "буфера → читает за память, чаще всего CTD.",
    'DFF_PRELIT_DATA_NO_FLAG':
        "В DFF есть prelit_colors, но bit GEOM_PRELIT не выставлен. Engine их "
        "просто проигнорирует — vertex освещение работать не будет.",
    'DFF_TRI_MATERIAL_OOR':
        "Triangle.material ссылается на индекс за пределами массива материалов. "
        "Engine попытается отрисовать с несуществующим материалом → undefined "
        "behaviour / чёрная текстура / CTD.",
    'DFF_RW_VERSION_NOT_SA':
        "RW-версия в Clump не соответствует ожидаемой для SA (0x36003). Файл "
        "может загрузиться через альт. путь, но какие-то extensions (paintjob, "
        "specular, 2DFX) могут быть проигнорированы.",
    # --- COL — additional checks
    'COL_FLAG_NOT_EMPTY_MISSING':
        "Bit 1 (\"not empty\") во flags COL2/3/4 не выставлен, но в модели есть "
        "коллизионные данные. Engine может пропустить эту модель при загрузке.",
    'COL_SHADOW_FLAG_NO_DATA':
        "Bit 4 (\"has shadow mesh\") во flags выставлен, но shadow_face_count = 0. "
        "Engine ожидает shadow данные и будет читать их по offset → может прочитать "
        "мусор как shadow faces.",
    'COL_SHADOW_DATA_NO_FLAG':
        "shadow_face_count > 0, но bit 4 во flags не выставлен. Engine не "
        "пометит модель как имеющую shadow → данные просто будут проигнорированы, "
        "тени от объекта не будут рисоваться.",
    'COL_FACE_GROUPS_TOO_MANY':
        "face_groups > 1024 — задокументированный crash threshold (gtamods wiki). "
        "Engine выделяет фиксированный буфер на face groups, переполнение = CTD.",
    'COL_FACE_GROUPS_BAD_COUNT':
        "Количество face_groups неадекватно большое — данные либо повреждены, "
        "либо exporter записал u32 туда, где должен был быть u16.",
    'COL_VERT_OUT_OF_RANGE':
        "COL2/3/4 хранит вершины как int16/128.0 — диапазон строго (-256, 256). "
        "Координата за этими пределами означает что в файле произошёл int16 overflow "
        "при экспорте, и реальная вершина «обернулась» (например +300 → -212). "
        "Raycasts будут попадать в мнимые места.",

    # --- TXD (Phase 3)
    'TXD_FS_ERROR': "Файл TXD не читается с диска.",
    'TXD_TOO_SMALL': "Файл меньше RW-заголовка. Битый или не TXD.",
    'TXD_PARSE_FAIL': "Парсер TXD упал. Возможно D3D9 формат вместо D3D8.",
    'TXD_TEX_NAME_TOO_LONG':
        "Имя текстуры > 32 символов. Engine обрежет до 32 → материал не найдёт текстуру.",
    'TXD_TEX_DIMS_BAD':
        "Width или height ≤ 0 или NaN. D3D откажется создавать текстуру.",
    'TXD_TEX_NPOT':
        "Размеры текстуры не являются степенью двойки (примеры плохих: 257, 511, "
        "100, 600). Vanilla SA D3D8-путь принимает только POT — допустимо "
        "1/2/4/8/16/32/64/128/256/512/1024/2048/4096. Это известный крэш по "
        "адресам 0x004C9691 / 0x00732924 / 0x00749B7B (Junior CrashList).",
    'TXD_TEX_TOO_LARGE':
        "Размер > 1024px. Vanilla SA stream budget рассчитан на 256-512px текстуры. "
        "Может вызвать stuttering при стриминге.",
    'TXD_DXT_NOT_ALIGNED':
        "Размер DXT-текстуры не кратен 4. DXT блоки 4x4, мипмапы будут битые.",
    'TXD_PLATFORM_ID_BAD':
        "platform_id в Texture Native не равен 8 (D3D8) или 9 (D3D9). 5 = Xbox, "
        "6 или 'PS2\\0' = PS2. PC SA не сможет загрузить такую текстуру — "
        "конвертируй TxdGen в формат PC.",
    'TXD_TEX_NAME_EMPTY':
        "Имя текстуры пустое. Material lookup ищет по имени — материал никогда "
        "не найдёт эту текстуру.",
    'TXD_TEX_NAME_DUPLICATE':
        "В одном TXD две текстуры с одинаковым именем. RW lookup возвращает "
        "первую — вторая никогда не используется. Удали дубль или переименуй.",
    'TXD_DEPTH_BAD':
        "Bit-depth текстуры не из набора {4, 8, 16, 24, 32}. RW raster format "
        "не поддерживает другие значения — engine прочитает scanlines с "
        "неправильным шагом → битая картинка / CTD.",
    'TXD_AUTOMIPMAP_WITH_LEVELS':
        "Bit AUTO_MIPMAP (0x1000) в raster_format одновременно с num_levels > 1. "
        "По спеке RW они взаимно исключают — TXD archive не загрузится "
        "(gtamods wiki: «Otherwise the TXD archive will fail to load»).",
    'TXD_RASTER_PAL_AND_DXT':
        "Текстура одновременно палитра (PAL4 / PAL8 в raster_format) И DXT (fourcc). "
        "Это взаимно исключающие режимы хранения — readers пойдут не по той ветке "
        "и прочитают мусорные палитру/блоки.",
    'TXD_NUM_LEVELS_OOR':
        "num_levels (количество мипмапов) больше чем log2(max(width,height))+1. "
        "Engine попытается прочитать мипмап-уровень, которого нет в данных, "
        "и упрётся в следующий чанк.",
    'TXD_NO_TEXTURES':
        "TXD валидный по структуре, но не содержит ни одной Texture Native. "
        "Material запросы к этому TXD просто ничего не вернут.",

    # --- Scanner-level
    'SCAN_NOT_A_DIR': "Указанный путь не является директорией.",
}


def explain(code: str) -> str:
    """Return long-form explanation for an issue code, or a placeholder."""
    return EXPLANATIONS.get(code, "(нет описания для этого кода)")


def _lint_col_raw_header(path: str, raw: bytes) -> List[LintIssue]:
    """Sniff the COL header bytes for filesize / shadow-offset bugs.

    Doesn't validate every model — just walks the chained header chunks
    (a single .col can contain multiple models back-to-back) and checks
    invariants the high-level parser would silently truncate past.
    """
    out: List[LintIssue] = []
    n = len(raw)
    pos = 0
    model_idx = 0

    while pos + 28 <= n:
        magic = raw[pos:pos+4]
        if magic not in (b'COLL', b'COL2', b'COL3', b'COL4'):
            break

        version = {b'COLL': 1, b'COL2': 2, b'COL3': 3, b'COL4': 4}[magic]
        # filesize is the size of (model_name + model_id + body) — i.e.
        # the bytes AFTER magic+filesize themselves. So next model starts
        # at pos + 8 + filesize.
        filesize = struct.unpack_from('<I', raw, pos + 4)[0]
        next_pos = pos + 8 + filesize

        if next_pos > n:
            out.append(LintIssue('ERROR', 'COL_HEADER_FILESIZE_MISMATCH',
                path, f"model[{model_idx}] @ offset {pos}",
                f"header filesize claims chunk ends at {next_pos}, file is only {n} bytes"))
            break  # any further iteration would be guesswork

        # Read flags + counts from COL2/3/4 fixed header. We need them
        # both for the shadow check AND for flag-bit consistency tests.
        col2_hdr_off = pos + 72  # 4 magic + 4 size + 22 name + 2 id + 40 bounds
        if version >= 2 and col2_hdr_off + 28 <= n:
            (sphere_count, box_count, face_count, line_count, _pad,
             flags) = struct.unpack_from('<HHHBBI', raw, col2_hdr_off)

            # Flag bit 1 (0x02) = "not empty" — must be set when there
            # is collision geometry. If unset but data exists, engine
            # may skip the model entirely.
            has_data = (sphere_count + box_count + face_count) > 0
            if has_data and not (flags & 0x02):
                out.append(LintIssue('WARN', 'COL_FLAG_NOT_EMPTY_MISSING',
                    path, f"model[{model_idx}] @ offset {pos}",
                    f"flags={flags:#x} bit 1 (not_empty) unset, but model has "
                    f"{sphere_count}sph/{box_count}box/{face_count}face — "
                    "engine may skip loading"))

        # Face groups (COL2+) — flag bit 3 (0x08) indicates presence.
        # Group count is u32 at (faces_off - 4); each group is 28 bytes.
        # Documented crash threshold: > 1024 groups.
        if version >= 2 and filesize > 0:
            # Re-read flags + faces_off from the COL2/3/4 header.
            if col2_hdr_off + 28 <= n:
                # Layout: HHH B B I (sphere/box/face/line/pad/flags)
                # then 6 offsets: spheres,boxes,lines,verts,faces,tri_planes
                # We need flags (already have it) and faces_off (5th of 6 offsets).
                offsets_start = col2_hdr_off + 12  # past HHHBBI = 12 bytes
                if offsets_start + 24 <= n:
                    spheres_off, boxes_off, lines_off, verts_off, faces_off, _tp_off = \
                        struct.unpack_from('<IIIIII', raw, offsets_start)
                    has_face_groups = bool(flags & 0x08)
                    if has_face_groups and faces_off >= 4:
                        base = pos + 4
                        gcount_at = base + faces_off - 4
                        if 0 <= gcount_at + 4 <= n:
                            group_count = struct.unpack_from('<I', raw, gcount_at)[0]
                            if group_count > 1024:
                                out.append(LintIssue('ERROR', 'COL_FACE_GROUPS_TOO_MANY',
                                    path, f"model[{model_idx}] @ offset {pos}",
                                    f"face_groups={group_count} > 1024 — documented crash threshold"))
                            elif group_count > 65535 // 28:
                                # Sanity: groups area shouldn't push outside chunk.
                                out.append(LintIssue('ERROR', 'COL_FACE_GROUPS_BAD_COUNT',
                                    path, f"model[{model_idx}] @ offset {pos}",
                                    f"face_groups={group_count} unreasonably large"))

        if version >= 3 and filesize > 0:
            # Shadow header is at offset (pos + 100). NOTE: vanilla SA
            # writes shadow_face_count>0 alongside offsets=0,0 as a
            # sentinel meaning "no shadow data for this model" — the
            # engine only follows the offsets when both are non-zero.
            # Therefore we ONLY flag a real bug when offsets are
            # non-zero AND point outside the chunk. The flag-bit-4
            # consistency checks that earlier versions had were dropped
            # — vanilla doesn't set bit 4 even when shadow data exists,
            # so any heuristic on it is unreliable.
            shadow_off = pos + 100
            if shadow_off + 12 <= n:
                sh_face_count, sh_verts_off, sh_faces_off = struct.unpack_from(
                    '<III', raw, shadow_off)
                if sh_face_count > 0 and sh_verts_off > 0 and sh_faces_off > 0:
                    base = pos + 4
                    needed_faces_end = base + sh_faces_off + sh_face_count * 8
                    needed_verts_start = base + sh_verts_off
                    file_chunk_end = pos + 8 + filesize
                    if (needed_faces_end > file_chunk_end
                            or needed_verts_start >= file_chunk_end
                            or sh_verts_off >= sh_faces_off):
                        out.append(LintIssue('ERROR', 'COL_SHADOW_OFFSETS_BAD',
                            path, f"model[{model_idx}] @ offset {pos}",
                            f"shadow_face_count={sh_face_count} but offsets "
                            f"(verts={sh_verts_off}, faces={sh_faces_off}) "
                            f"point outside chunk [{base}..{file_chunk_end}]"))

        pos = next_pos
        model_idx += 1

    return out


def lint_col(path: str, profile: str = lint_profile.STANDARD,
             game: str = 'SA') -> List[LintIssue]:
    """Lint a single .col file. Returns a list of LintIssue (may be empty).

    Reuses core/col.py reader; on parse failure, emits a single
    PARSE_FAIL issue and stops. Successful parse is followed by a
    series of structural checks (bounds, sphere radii, face indices,
    surface IDs, shadow consistency).

    ``game`` (III/VC/SA) selects the vanilla surface-ID ceiling for
    the COL_SURFACE_ID_FLA_ONLY check: III=84, VC=85, SA=178. Above
    those, Fastman92 Limit Adjuster is required.
    """
    issues: List[LintIssue] = []
    # Per-game surface-ID range. III/VC have far fewer surface types
    # than SA's 178 — a surface 100 in a III .col loads as garbage.
    from . import game_versions as _gv
    _surface_vanilla_max = _gv.profile_for(game).surface_id_max

    try:
        size_on_disk = os.path.getsize(path)
    except OSError as e:
        return [LintIssue('ERROR', 'COL_FS_ERROR', path, '', f"{e.__class__.__name__}: {e}")]

    if size_on_disk < 32:
        return [LintIssue('ERROR', 'COL_TOO_SMALL', path, '',
                          f"file is {size_on_disk} bytes — COL header alone is 28")]

    # Read the whole file once: cheap (COL files are small) and lets
    # us do raw-byte checks without re-opening.
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError as e:
        return [LintIssue('ERROR', 'COL_FS_ERROR', path, '',
                          f"{e.__class__.__name__}: {e}")]

    if raw[:4] not in (b'COLL', b'COL2', b'COL3', b'COL4'):
        return [LintIssue('ERROR', 'COL_BAD_MAGIC', path, '',
                          f"first 4 bytes {raw[:4]!r} — expected COLL/COL2/COL3/COL4")]

    # Raw header pre-parse: catches the Manu 0x415D47 class of bugs
    # that the high-level parser would silently swallow (truncated
    # shadow buffer, filesize mismatch).
    issues.extend(_lint_col_raw_header(path, raw))

    try:
        from .col import read_col_file
        models = read_col_file(path)
    except Exception as e:
        return issues + [LintIssue('ERROR', 'COL_PARSE_FAIL', path, '',
                                   f"{e.__class__.__name__}: {e}")]

    if not models:
        return issues + [LintIssue('ERROR', 'COL_NO_MODELS', path, '',
                                   "file parsed but contained zero ColModels")]

    for mi, m in enumerate(models):
        prefix = f"model[{mi}] '{m.model_name}'"

        # Bounds: bad radius / NaN / inverted bbox crashes the streamer
        # before any geometry is touched. ERROR on all of these.
        b = m.bounds
        if _bad_float(b.radius) or b.radius <= 0:
            issues.append(LintIssue('ERROR', 'COL_BAD_BOUND_RADIUS',
                path, prefix,
                f"bound radius={b.radius!r} (must be > 0 and finite)"))
        for axis in ('x', 'y', 'z'):
            mn, mx = getattr(b.bb_min, axis), getattr(b.bb_max, axis)
            if _bad_float(mn) or _bad_float(mx):
                issues.append(LintIssue('ERROR', 'COL_BAD_BBOX',
                    path, prefix,
                    f"bbox.{axis} contains NaN/Inf (min={mn!r}, max={mx!r})"))
            elif mn > mx:
                issues.append(LintIssue('ERROR', 'COL_BBOX_INVERTED',
                    path, prefix,
                    f"bbox.{axis}: min ({mn:.3f}) > max ({mx:.3f})"))

        # Spheres: same NaN / non-positive radius rule.
        for si, sp in enumerate(m.spheres):
            if _bad_float(sp.radius) or sp.radius <= 0:
                issues.append(LintIssue('ERROR', 'COL_BAD_SPHERE_RADIUS',
                    path, f"{prefix}.sphere[{si}]",
                    f"radius={sp.radius!r} (must be > 0 and finite)"))
            for axis in ('x', 'y', 'z'):
                v = getattr(sp.center, axis)
                if _bad_float(v):
                    issues.append(LintIssue('ERROR', 'COL_BAD_SPHERE_CENTER',
                        path, f"{prefix}.sphere[{si}]",
                        f"center.{axis}={v!r}"))
                    break

        # Face indices must point inside the vertex array. Out-of-range
        # is a likely cause of streaming crashes — engine reads past
        # the vertex buffer.
        nv = len(m.vertices)
        for fi, fc in enumerate(m.faces):
            if nv == 0:
                issues.append(LintIssue('ERROR', 'COL_FACE_NO_VERTS',
                    path, f"{prefix}.face[{fi}]",
                    "face references a vertex but model has 0 vertices"))
                break  # one report per model is enough
            for which, idx in (('a', fc.a), ('b', fc.b), ('c', fc.c)):
                if idx >= nv:
                    issues.append(LintIssue('ERROR', 'COL_FACE_INDEX_OOR',
                        path, f"{prefix}.face[{fi}]",
                        f"index {which}={idx} >= vertex count {nv}"))
                    break  # one report per face

        # Surface IDs. Vanilla per game: III=84, VC=85, SA=178. FLA: 254.
        bad_vanilla = []
        bad_fla = []
        for fi, fc in enumerate(m.faces):
            sid = fc.surface.material
            if sid > _COL_SURFACE_FLA_MAX:
                bad_fla.append((fi, sid))
            elif sid > _surface_vanilla_max:
                bad_vanilla.append((fi, sid))
        if bad_fla:
            fi, sid = bad_fla[0]
            issues.append(LintIssue('ERROR', 'COL_SURFACE_ID_OOR',
                path, f"{prefix}.face[{fi}]",
                f"surface ID {sid} > {_COL_SURFACE_FLA_MAX} (max even with FLA)"
                + (f"; +{len(bad_fla)-1} more" if len(bad_fla) > 1 else "")))
        if bad_vanilla:
            fi, sid = bad_vanilla[0]
            issues.append(LintIssue('WARN', 'COL_SURFACE_ID_FLA_ONLY',
                path, f"{prefix}.face[{fi}]",
                f"surface ID {sid} > {_surface_vanilla_max} (needs FLA to load)"
                + (f"; +{len(bad_vanilla)-1} more" if len(bad_vanilla) > 1 else "")))

        # Shadow mesh sanity (COL3+). Note: model.flags bit 1 ("has
        # collision data") and bit 3 ("has face groups") do NOT gate
        # shadow presence — that's controlled by `shadow_face_count`
        # in the header. We only flag a real inconsistency: file says
        # there are shadow faces but no shadow vertices were parsed.
        if m.version >= 3:
            n_sh_faces = len(m.shadow_faces)
            n_sh_verts = len(m.shadow_vertices)
            if n_sh_faces > 0 and n_sh_verts == 0:
                issues.append(LintIssue('ERROR', 'COL_SHADOW_NO_VERTS',
                    path, prefix,
                    f"shadow has {n_sh_faces} faces but 0 vertices"))

        # Vertex coords must fit in (-256, 256) — COL2/3/4 stores them
        # as int16 / 128.0, so anything outside that range is data corruption
        # (the writer would have wrapped the int16). Reading wrapped
        # vertices produces near-far flicker and broken raycasts.
        for vi, v in enumerate(m.vertices):
            for axis_name, axis_val in (('x', v.x), ('y', v.y), ('z', v.z)):
                if abs(axis_val) > 256.0:
                    issues.append(LintIssue('ERROR', 'COL_VERT_OUT_OF_RANGE',
                        path, f"{prefix}.vert[{vi}]",
                        f"{axis_name}={axis_val:.2f} outside int16/128.0 range "
                        "(-256..256) — likely wrap-around in writer"))
                    break  # one report per vertex
            else:
                continue
            break  # one report per model

        # Practical face count limits (vanilla SA performance):
        # ~10k is a soft warning, ~30k means physics will lag, hard
        # u16 cap at 65 535. Same idea for COL2/3/4 vertex count.
        nf = len(m.faces)
        if nf > 30000:
            issues.append(LintIssue('WARN', 'COL_FACE_COUNT_VERY_HIGH',
                path, prefix,
                f"{nf} collision faces — physics/streaming will lag (vanilla props ≤ 5k)"))
        elif nf > 10000:
            issues.append(LintIssue('WARN', 'COL_FACE_COUNT_HIGH',
                path, prefix,
                f"{nf} collision faces — vanilla props rarely exceed 5k; consider Decimate"))
        if nv > 30000:
            issues.append(LintIssue('WARN', 'COL_VERT_COUNT_VERY_HIGH',
                path, prefix,
                f"{nv} collision vertices — close to u16 limit (65 535)"))

    return lint_profile.apply_filter(issues, profile)


# ── DFF / TXD stubs (Phase 2/3) ──────────────────────────────────

_DFF_VERT_HARD = 65535          # u16 index limit
_DFF_VERT_SOFT = 32000          # rendering glitches start
_DFF_TRI_SOFT = 30000           # stable up to ~30-40k
# Vanilla SA building/interior DFFs commonly carry 50-65 materials per
# geometry (see int2labig301.dff = 61, lod_liberty07.dff = 57). The
# practical "50-material" rule was for vehicles, not maps. Threshold
# bumped well above observed vanilla.
_DFF_MAT_VANILLA = 100
_DFF_MAT_HARD = 65535
# Vanilla SA buildings sometimes use 3 UV layers (env map + lightmap +
# diffuse). 2 was misremembered as a hard cap. Hard u8 cap is 255.
_DFF_UV_LAYERS_HARD = 255
_DFF_BONES_HARD = 255           # u8
# 2DFX limit was a vehicle rule-of-thumb. Vanilla airport DFFs carry
# 45+ light entries without crashing (airport_11_sfse.dff = 45).
# Don't warn until we see something genuinely outlier.
_DFF_2DFX_SOFT = 200


def lint_dff(path: str, profile: str = lint_profile.STANDARD) -> List[LintIssue]:
    """Lint a single .dff: per-geometry limits (vertices/triangles/
    materials/UV/skin/2DFX) and atomic/frame index validity.

    Reuses core/dff.py reader. On parse failure emits PARSE_FAIL.

    ``profile`` selects threshold overrides + post-filter:
    STANDARD keeps module defaults, STRICT tightens vert/tri/mat/2dfx
    soft limits, FLA / LENIENT only affect the post-filter step.
    """
    issues: List[LintIssue] = []
    _cfg = lint_profile.get_profile(profile)
    _vert_soft = _cfg.dff_vert_soft if _cfg.dff_vert_soft is not None else _DFF_VERT_SOFT
    _tri_soft = _cfg.dff_tri_soft if _cfg.dff_tri_soft is not None else _DFF_TRI_SOFT
    _mat_vanilla = _cfg.dff_mat_vanilla if _cfg.dff_mat_vanilla is not None else _DFF_MAT_VANILLA
    _2dfx_soft = _cfg.dff_2dfx_soft if _cfg.dff_2dfx_soft is not None else _DFF_2DFX_SOFT

    try:
        size = os.path.getsize(path)
    except OSError as e:
        return [LintIssue('ERROR', 'DFF_FS_ERROR', path, '',
                          f"{e.__class__.__name__}: {e}")]

    if size < 12:
        return [LintIssue('ERROR', 'DFF_TOO_SMALL', path, '',
                          f"file is {size} bytes — RW header alone is 12")]

    try:
        from .dff import read_dff_file
        clump = read_dff_file(path)
    except Exception as e:
        # Distinguish "file is corrupt" from "our parser doesn't know
        # this RW chunk order". The reader's first sanity check is
        # `Expected Clump chunk (0x10), got 0xNN` — when 0xNN is a
        # valid RW chunk type, the file is fine but starts with e.g.
        # an Anim/UV-anim dictionary that we don't read yet. Vanilla
        # files like `chinafurn1.dff` start with chunk 0x2B and load
        # fine in-game.
        msg = f"{e.__class__.__name__}: {e}"
        if "Expected Clump chunk" in msg:
            try:
                with open(path, 'rb') as f:
                    head = f.read(4)
                first_chunk = int.from_bytes(head, 'little') if len(head) == 4 else 0
            except OSError:
                first_chunk = 0
            # 0x01..0x4F is the standard RW chunk type range.
            if 0x01 <= first_chunk <= 0x4F:
                return [LintIssue('WARN', 'DFF_PARSER_INCOMPATIBLE', path, '',
                    f"first chunk type 0x{first_chunk:X} — valid RW chunk that "
                    "our parser doesn't recognise as a DFF entry point. File "
                    "may still load in-game; lint cannot inspect it further.")]
        return [LintIssue('ERROR', 'DFF_PARSE_FAIL', path, '', msg)]

    n_frames = len(clump.frames)
    n_geoms = len(clump.geometries)

    # Atomic indices must point inside the frame/geometry arrays —
    # out-of-range is the typical streaming-time crash for DFFs from
    # rebuilt IMG archives.
    for ai, atom in enumerate(clump.atomics):
        if atom.frame_index < 0 or atom.frame_index >= n_frames:
            issues.append(LintIssue('ERROR', 'DFF_ATOMIC_FRAME_OOR',
                path, f"atomic[{ai}]",
                f"frame_index={atom.frame_index} but only {n_frames} frames"))
        if atom.geometry_index < 0 or atom.geometry_index >= n_geoms:
            issues.append(LintIssue('ERROR', 'DFF_ATOMIC_GEOM_OOR',
                path, f"atomic[{ai}]",
                f"geometry_index={atom.geometry_index} but only {n_geoms} geometries"))

    # ── Skinned clump: atomic must attach at skeleton root, not a child bone ──
    # Find the skeleton root: the frame whose HAnim plugin carries the bone
    # array (only the root frame has a non-empty bones list — all others
    # have boneCount=0 placeholders). For SA peds this is normally frame[1]
    # ("Normal") with frame[0] being the absolute scene root above it.
    #
    # Soldier.dff at the reference site had atomic.frame_index = 32 (= last
    # bone "L Toe0"), causing a streaming crash. SA's clump-setup code reads
    # atomic.frame as the model's attach point — when it lands deep inside
    # the bone tree the skin matrices and parent transforms are computed
    # against the wrong basis and the loader dies before the ped spawns.
    skel_root_idx = None
    for fi, frame in enumerate(clump.frames):
        hanim = getattr(frame, 'hanim', None)
        if hanim is not None and getattr(hanim, 'bones', None):
            skel_root_idx = fi
            break
    if skel_root_idx is not None:
        for ai, atom in enumerate(clump.atomics):
            if not (0 <= atom.frame_index < n_frames):
                continue   # already reported as OOR above
            if atom.frame_index <= skel_root_idx:
                continue   # at-or-above skeleton root — valid attachment
            # Walk parent chain from the atomic's frame upward — if it
            # passes through the skeleton root, the atomic is anchored
            # inside the bone hierarchy.
            cur = atom.frame_index
            seen = set()
            inside_skeleton = False
            while cur != -1 and cur not in seen and 0 <= cur < n_frames:
                seen.add(cur)
                if cur == skel_root_idx:
                    inside_skeleton = True
                    break
                cur = clump.frames[cur].parent
            if inside_skeleton:
                bone_name = clump.frames[atom.frame_index].name or '?'
                root_name = clump.frames[skel_root_idx].name or '?'
                issues.append(LintIssue('ERROR', 'DFF_ATOMIC_FRAME_NOT_ROOT',
                    path, f"atomic[{ai}]",
                    f"frame_index={atom.frame_index} ('{bone_name}') is a "
                    f"descendant of skeleton root frame[{skel_root_idx}] "
                    f"('{root_name}'). Set it to {skel_root_idx} (root) "
                    f"or {clump.frames[skel_root_idx].parent} (parent of root)."))

    # Frame parents form a tree — each parent index must be < own index
    # or -1 (root). Cyclic / forward refs corrupt the bone hierarchy.
    for fi, frame in enumerate(clump.frames):
        if frame.parent != -1 and (frame.parent < 0 or frame.parent >= n_frames or frame.parent == fi):
            issues.append(LintIssue('ERROR', 'DFF_FRAME_PARENT_OOR',
                path, f"frame[{fi}] '{frame.name}'",
                f"parent={frame.parent} (must be -1 or 0..{n_frames-1}, not self)"))

    # Per-geometry checks
    for gi, g in enumerate(clump.geometries):
        prefix = f"geometry[{gi}]"
        nv = len(g.vertices)
        nt = len(g.triangles)
        nm = len(g.materials)
        nu = len(g.uv_layers)

        # Vertex / triangle / material limits
        if nv > _DFF_VERT_HARD:
            issues.append(LintIssue('ERROR', 'DFF_GEOM_VERT_COUNT_HARD',
                path, prefix,
                f"{nv} vertices — u16 limit is {_DFF_VERT_HARD}"))
        elif nv > _vert_soft:
            issues.append(LintIssue('WARN', 'DFF_GEOM_VERT_COUNT_HIGH',
                path, prefix,
                f"{nv} vertices — close to u16 limit, glitches likely past {_vert_soft}"))

        if nt > _DFF_VERT_HARD:
            issues.append(LintIssue('ERROR', 'DFF_GEOM_TRI_COUNT_HARD',
                path, prefix,
                f"{nt} triangles — u16 index limit is {_DFF_VERT_HARD}"))
        elif nt > _tri_soft:
            issues.append(LintIssue('WARN', 'DFF_GEOM_TRI_COUNT_HIGH',
                path, prefix,
                f"{nt} triangles — vanilla SA stable up to ~{_tri_soft}"))

        if nm > _DFF_MAT_HARD:
            issues.append(LintIssue('ERROR', 'DFF_GEOM_MAT_COUNT_HARD',
                path, prefix,
                f"{nm} materials — u16 limit is {_DFF_MAT_HARD}"))
        elif nm > _mat_vanilla:
            issues.append(LintIssue('WARN', 'DFF_GEOM_MAT_COUNT_VANILLA',
                path, prefix,
                f"{nm} materials — practical cap is {_mat_vanilla}"))

        if nu > _DFF_UV_LAYERS_HARD:
            issues.append(LintIssue('ERROR', 'DFF_GEOM_UV_LAYERS_HARD',
                path, prefix,
                f"{nu} UV layers — u8 limit is {_DFF_UV_LAYERS_HARD}"))
        # No soft warning on UV-layer count: vanilla SA buildings have
        # up to 3 layers (int_boxing07.dff, range_main.dff). The
        # earlier «>2» heuristic was a false positive across vanilla.

        # Triangle indices vs vertex array
        for ti, tri in enumerate(g.triangles[:1000]):  # cap for perf
            for which, idx in (('a', tri.a), ('b', tri.b), ('c', tri.c)):
                if idx >= nv:
                    issues.append(LintIssue('ERROR', 'DFF_TRI_INDEX_OOR',
                        path, f"{prefix}.tri[{ti}]",
                        f"index {which}={idx} >= vertex count {nv}"))
                    break
            if any(getattr(tri, k) >= nv for k in ('a', 'b', 'c')):
                break  # one triangle report per geometry is enough

        # NaN/Inf in vertex positions
        for vi, v in enumerate(g.vertices):
            if any(_bad_float(c) for c in v):
                issues.append(LintIssue('ERROR', 'DFF_VERT_NAN',
                    path, f"{prefix}.vertex[{vi}]",
                    f"NaN/Inf in position {v!r}"))
                break  # one report per geom

        # Bounding sphere
        bs = g.bounding_sphere
        if _bad_float(bs.radius) or bs.radius < 0:
            issues.append(LintIssue('ERROR', 'DFF_BSPHERE_BAD',
                path, prefix,
                f"bounding sphere radius={bs.radius!r}"))

        # Skin PLG
        if g.skin is not None:
            sk = g.skin
            if sk.num_bones > _DFF_BONES_HARD:
                issues.append(LintIssue('ERROR', 'DFF_SKIN_BONES_HARD',
                    path, prefix,
                    f"skin: {sk.num_bones} bones — u8 limit is {_DFF_BONES_HARD}"))
            if sk.max_weights > 4:
                issues.append(LintIssue('WARN', 'DFF_SKIN_WEIGHTS_HARD',
                    path, prefix,
                    f"skin: max_weights={sk.max_weights} but engine reads only 4"))
            # bone_indices reference existing bones
            for vi, bi_tuple in enumerate(sk.bone_indices[:200]):
                if any(b >= sk.num_bones for b in bi_tuple if b > 0):
                    bad = [b for b in bi_tuple if b >= sk.num_bones]
                    issues.append(LintIssue('ERROR', 'DFF_SKIN_BONE_INDEX_OOR',
                        path, f"{prefix}.vert[{vi}]",
                        f"bone index {bad} >= num_bones {sk.num_bones}"))
                    break

        # 2DFX count
        if g.ext_2dfx is not None:
            n2 = len(g.ext_2dfx.entries)
            if n2 > _2dfx_soft:
                issues.append(LintIssue('WARN', 'DFF_2DFX_COUNT_HIGH',
                    path, prefix,
                    f"{n2} 2DFX entries — practical cap is {_2dfx_soft}"))

        # GEOM_NATIVE flag — data is in a platform-extension, not in
        # the standard struct. PC engine doesn't know how to read PS2
        # native geometry → CTD on first render.
        flags = getattr(g, '_import_flags', None)
        if flags is not None:
            if flags & 0x01000000:  # GEOM_NATIVE
                issues.append(LintIssue('ERROR', 'DFF_GEOM_NATIVE_ON_PC',
                    path, prefix,
                    f"flags=0x{flags:X} has GEOM_NATIVE bit (0x01000000) — "
                    "data is in PS2/Xbox platform extension, PC engine cannot read"))

            # UV layer count from upper byte of flags vs actual array length.
            num_uv_flag = (flags >> 16) & 0xFF
            # Old derivation: if upper byte is 0, look at GEOM_TEXTURED/2.
            if num_uv_flag == 0:
                if flags & 0x80:    # GEOM_TEXTURED2
                    num_uv_flag = 2
                elif flags & 0x04:  # GEOM_TEXTURED
                    num_uv_flag = 1
            if num_uv_flag != nu and not (flags & 0x01000000):
                issues.append(LintIssue('ERROR', 'DFF_UV_FLAG_MISMATCH',
                    path, prefix,
                    f"flags say {num_uv_flag} UV layers, actual array has {nu} — "
                    "engine reads by flag count and will run past buffer"))

            # Prelit colors flag vs data presence
            has_prelit_flag = bool(flags & 0x08)  # GEOM_PRELIT
            has_prelit_data = nv > 0 and len(g.prelit_colors) > 0
            if has_prelit_flag and not has_prelit_data and nv > 0 and not (flags & 0x01000000):
                issues.append(LintIssue('WARN', 'DFF_PRELIT_FLAG_NO_DATA',
                    path, prefix,
                    "GEOM_PRELIT flag set but prelit_colors array is empty"))
            elif has_prelit_data and not has_prelit_flag:
                issues.append(LintIssue('WARN', 'DFF_PRELIT_DATA_NO_FLAG',
                    path, prefix,
                    "prelit_colors present but GEOM_PRELIT flag unset — "
                    "engine will skip the data"))

        # Triangle.material must reference an existing material.
        if nm > 0:
            for ti, tri in enumerate(g.triangles[:1000]):
                if tri.material >= nm:
                    issues.append(LintIssue('ERROR', 'DFF_TRI_MATERIAL_OOR',
                        path, f"{prefix}.tri[{ti}]",
                        f"material index {tri.material} >= material count {nm}"))
                    break

    # ── RW version sanity (clump-level) ─────────────────────────
    # SA standard is 0x36003. Other RW3 versions might load but vehicle
    # code paths assume specific extensions.
    if clump.version not in (0x36003, 0x35000, 0x34003, 0x34000, 0x33002):
        issues.append(LintIssue('WARN', 'DFF_RW_VERSION_NOT_SA',
            path, '',
            f"RW version 0x{clump.version:X} — vanilla SA writes 0x36003. "
            "Loader may misroute or refuse the file."))

    return lint_profile.apply_filter(issues, profile)


_TXD_NAME_HARD = 32          # u8-length textures buffer (32 bytes incl. null)
_TXD_SIZE_VANILLA = 1024     # SA stream budget — props rarely exceed this

# Valid RW platform_id values for PC SA. 8 = D3D8 (vanilla), 9 = D3D9 (rare).
# 5 = Xbox, 6 / "PS2\0" = PS2 — neither loads on PC SA.
_TXD_PLATFORM_PC = (8, 9)
# Valid bit depths per RW raster spec. 24 only for FORMAT_888 (rare).
_TXD_DEPTH_VALID = {4, 8, 16, 24, 32}
# Raster format flag bits (gtamods.com/wiki/Raster_(RW_Section))
_RF_AUTO_MIPMAP = 0x1000
_RF_PAL4        = 0x4000
_RF_PAL8        = 0x2000
_RF_MIPMAP      = 0x8000


def _is_pot(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


# RW chunk types relevant to TXD lint
_RW_CHUNK_STRUCT      = 0x01
_RW_CHUNK_TEX_NATIVE  = 0x15
_RW_CHUNK_TEX_DICT    = 0x16


def _scan_txd_natives(raw: bytes) -> list:
    """Lightweight chunk walker — yields (platform_id, name, raster_fmt,
    fourcc, width, height, depth, num_levels) for each Texture Native.

    Doesn't decode pixel data, so it's safe to run on any sanely-formed
    TXD even when the high-level parser refuses (e.g. unsupported
    platform_id). Returns [] on malformed chunks.
    """
    out = []
    n = len(raw)
    if n < 12:
        return out
    # Top-level: Texture Dictionary (0x16)
    ct, cs, cl = struct.unpack_from('<III', raw, 0)
    if ct != _RW_CHUNK_TEX_DICT:
        return out
    pos = 12
    # Struct chunk: tex_count u16, device_id u16, then padding to chunk size
    if pos + 12 > n:
        return out
    ct_s, cs_s, _ = struct.unpack_from('<III', raw, pos)
    if ct_s != _RW_CHUNK_STRUCT:
        return out
    pos += 12
    if pos + 4 > n:
        return out
    tex_count = struct.unpack_from('<H', raw, pos)[0]
    # Skip rest of struct
    pos += cs_s - 0  # struct header data already counted in cs_s? No — cs_s is the data length
    # Re-derive: struct chunk payload is at original (12+12)..(12+12+cs_s)
    pos = 12 + 12 + cs_s

    for _ in range(tex_count):
        if pos + 12 > n:
            break
        ct_t, cs_t, _ = struct.unpack_from('<III', raw, pos)
        chunk_payload = pos + 12
        chunk_end = chunk_payload + cs_t
        if ct_t == _RW_CHUNK_TEX_NATIVE and chunk_payload + 12 <= n:
            # Texture Native body: Struct chunk first.
            ct_st, cs_st, _ = struct.unpack_from('<III', raw, chunk_payload)
            if ct_st == _RW_CHUNK_STRUCT and chunk_payload + 12 + 92 <= n:
                base = chunk_payload + 12
                # Layout: platform_id u32, filter_flags u32,
                # name(32), mask(32), raster_format u32, fourcc u32,
                # width u16, height u16, depth u8, num_levels u8,
                # raster_type u8, compression_flag u8.
                platform_id = struct.unpack_from('<I', raw, base)[0]
                name_bytes = raw[base + 8 : base + 8 + 32]
                name = name_bytes.split(b'\x00', 1)[0].decode('ascii', errors='replace')
                raster_fmt = struct.unpack_from('<I', raw, base + 72)[0]
                fourcc     = struct.unpack_from('<I', raw, base + 76)[0]
                width      = struct.unpack_from('<H', raw, base + 80)[0]
                height     = struct.unpack_from('<H', raw, base + 82)[0]
                depth      = raw[base + 84]
                num_levels = raw[base + 85]
                out.append((platform_id, name, raster_fmt, fourcc,
                            width, height, depth, num_levels))
        pos = chunk_end
    return out


def lint_txd(path: str, profile: str = lint_profile.STANDARD) -> List[LintIssue]:
    """Lint a single .txd: per-texture name length, dimensions, POT,
    DXT block alignment, platform_id, depth, mipmap consistency.

    Uses a lightweight raw-bytes chunk walker (does not decode pixels).
    Catches platform mismatches (PS2/Xbox dropped into PC TXD) that
    would silently fail in the decoder fallback path.

    ``profile`` selects threshold overrides: STRICT tightens
    TXD_TEX_TOO_LARGE from 1024 to 512 px.
    """
    issues: List[LintIssue] = []
    _cfg = lint_profile.get_profile(profile)
    _size_vanilla = (_cfg.txd_size_vanilla
                     if _cfg.txd_size_vanilla is not None
                     else _TXD_SIZE_VANILLA)

    try:
        size = os.path.getsize(path)
    except OSError as e:
        return [LintIssue('ERROR', 'TXD_FS_ERROR', path, '',
                          f"{e.__class__.__name__}: {e}")]

    if size < 12:
        return [LintIssue('ERROR', 'TXD_TOO_SMALL', path, '',
                          f"file is {size} bytes — RW header alone is 12")]

    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError as e:
        return [LintIssue('ERROR', 'TXD_FS_ERROR', path, '',
                          f"{e.__class__.__name__}: {e}")]

    natives = _scan_txd_natives(raw)
    if not natives:
        # Either malformed, or a vanilla placeholder TXD (cj_banditlod,
        # changeme, etc. all ship empty). Run full parser to distinguish:
        # if it parses cleanly with 0 textures — that's a placeholder, no
        # report. If it raises — report PARSE_FAIL.
        try:
            from .txd import read_txd_file
            read_txd_file(path)
        except Exception as e:
            return [LintIssue('ERROR', 'TXD_PARSE_FAIL', path, '',
                              f"{e.__class__.__name__}: {e}")]
        return []  # placeholder TXD — silent

    seen_names = {}  # name → first index (for duplicate detection)

    for ti, (platform_id, name, raster_fmt, fourcc, w, h, depth, num_levels) \
            in enumerate(natives):
        prefix = f"texture[{ti}] '{name}'"

        # Platform ID — PC = 8 / 9 only.
        if platform_id not in _TXD_PLATFORM_PC:
            issues.append(LintIssue('ERROR', 'TXD_PLATFORM_ID_BAD',
                path, prefix,
                f"platform_id={platform_id} (expected 8=D3D8 or 9=D3D9; "
                f"5=Xbox, 6=PS2 won't load on PC SA)"))

        # Name length / empty / duplicates
        if not name:
            issues.append(LintIssue('ERROR', 'TXD_TEX_NAME_EMPTY',
                path, f"texture[{ti}]",
                "empty texture name — material lookup will fail"))
        else:
            if len(name) > _TXD_NAME_HARD - 1:
                # Buffer is 32 bytes incl. null → max 31 visible chars.
                issues.append(LintIssue('ERROR', 'TXD_TEX_NAME_TOO_LONG',
                    path, prefix,
                    f"name is {len(name)} chars — buffer fits {_TXD_NAME_HARD-1} (incl. null)"))
            if name in seen_names:
                issues.append(LintIssue('WARN', 'TXD_TEX_NAME_DUPLICATE',
                    path, prefix,
                    f"name appears earlier as texture[{seen_names[name]}] — "
                    "material lookup returns first match only"))
            else:
                seen_names[name] = ti

        # Dimensions
        if w <= 0 or h <= 0:
            issues.append(LintIssue('ERROR', 'TXD_TEX_DIMS_BAD',
                path, prefix,
                f"width={w}, height={h} (must be > 0)"))
            continue

        if not _is_pot(w) or not _is_pot(h):
            issues.append(LintIssue('ERROR', 'TXD_TEX_NPOT',
                path, prefix,
                f"{w}x{h} — размеры не степень двойки. "
                "Допустимы только 1/2/4/8/16/32/64/128/256/512/1024/2048/4096"))

        if w > _size_vanilla or h > _size_vanilla:
            issues.append(LintIssue('WARN', 'TXD_TEX_TOO_LARGE',
                path, prefix,
                f"{w}x{h} > {_size_vanilla} — stream budget spike"))

        # Bit depth — must be a sane RW value.
        if depth not in _TXD_DEPTH_VALID:
            issues.append(LintIssue('ERROR', 'TXD_DEPTH_BAD',
                path, prefix,
                f"depth={depth} bits (valid: 4, 8, 16, 24, 32)"))

        # DXT alignment: blocks are 4×4.
        if fourcc and ((w & 3) or (h & 3)):
            issues.append(LintIssue('ERROR', 'TXD_DXT_NOT_ALIGNED',
                path, prefix,
                f"{w}x{h} not aligned to 4 — DXT blocks are 4x4"))

        # AUTO_MIPMAP is mutually exclusive with explicit mipmaps:
        # if AUTO_MIPMAP is on, num_levels must be 1, else TXD won't load.
        if (raster_fmt & _RF_AUTO_MIPMAP) and num_levels > 1:
            issues.append(LintIssue('ERROR', 'TXD_AUTOMIPMAP_WITH_LEVELS',
                path, prefix,
                f"AUTO_MIPMAP flag set AND num_levels={num_levels} — "
                "TXD archive will fail to load"))

        # PAL + DXT mutual exclusion: a palette-indexed format can't
        # also be DXT-compressed — readers branch incorrectly.
        if fourcc and (raster_fmt & (_RF_PAL4 | _RF_PAL8)):
            issues.append(LintIssue('ERROR', 'TXD_RASTER_PAL_AND_DXT',
                path, prefix,
                f"raster_format=0x{raster_fmt:X} has PAL + fourcc=0x{fourcc:X} "
                "(DXT) — formats are mutually exclusive"))

        # num_levels overflow check: max log2(max(w,h))+1.
        # E.g. 256x256 → max 9 levels (256, 128, 64, 32, 16, 8, 4, 2, 1).
        max_dim = max(w, h)
        max_levels = 1
        while (1 << max_levels) <= max_dim:
            max_levels += 1
        if num_levels > max_levels:
            issues.append(LintIssue('ERROR', 'TXD_NUM_LEVELS_OOR',
                path, prefix,
                f"num_levels={num_levels} > max possible {max_levels} for {w}x{h}"))

    return lint_profile.apply_filter(issues, profile)


# ── Folder scanner ───────────────────────────────────────────────

def scan_folder(folder: str, *, scan_dff=True, scan_col=True, scan_txd=True,
                recursive=False, progress_cb=None,
                profile: str = lint_profile.STANDARD,
                game: str = 'SA') -> List[LintIssue]:
    """Walk a folder, lint matching files, return all issues.

    progress_cb(i, n, path) — optional callback for UI progress bars.
    profile — see core.lint_profile; propagated to every per-file
    linter so STRICT thresholds + FLA/LENIENT silencing apply
    uniformly.
    game — III/VC/SA target; drives per-game ceilings inside the
    per-file linters (surface_id_max, etc.).
    """
    if not os.path.isdir(folder):
        return [LintIssue('ERROR', 'SCAN_NOT_A_DIR', folder, '',
                          "path is not a directory")]

    targets = []
    for root, dirs, files in os.walk(folder):
        for fn in files:
            ext = fn.lower().rsplit('.', 1)[-1] if '.' in fn else ''
            if ext == 'col' and scan_col:
                targets.append((os.path.join(root, fn), 'col'))
            elif ext == 'dff' and scan_dff:
                targets.append((os.path.join(root, fn), 'dff'))
            elif ext == 'txd' and scan_txd:
                targets.append((os.path.join(root, fn), 'txd'))
        if not recursive:
            dirs.clear()

    issues: List[LintIssue] = []
    for i, (path, kind) in enumerate(targets):
        if progress_cb:
            progress_cb(i, len(targets), path)
        if kind == 'col':
            issues.extend(lint_col(path, profile=profile, game=game))
        elif kind == 'dff':
            issues.extend(lint_dff(path, profile=profile))
        elif kind == 'txd':
            issues.extend(lint_txd(path, profile=profile))
    return issues
