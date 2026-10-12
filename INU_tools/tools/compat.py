# INU_tools.tools.compat — Blender API compatibility shims
#
# Минимальная поддерживаемая версия: Blender 2.83 LTS.
# 2.80–2.82 не поддерживаются (отсутствует UILayout.ui_units_x,
# CHECKMARK icon, ряд RNA-различий — критичные панели не рисуются).
# Этот модуль — единственное место где код знает о различиях между
# API-версиями. Все остальные модули обращаются сюда вместо if'ов
# по `bpy.app.version` или try/except'ов на отсутствующие attrs.
#
# Принцип: фичи, которые нельзя бэкпортировать (например VC Layers
# System на color_attributes 3.2+), показывают warning и отключают
# себя через `require_version` / `warn_unsupported`. Фичи, которые
# можно реализовать через старый API — обёрнуты в универсальные
# helper'ы (get_vcols, make_mix_rgba и т.п.).

import bpy


# ── Version constants ────────────────────────────────────────────────

# Под unit-тестами `bpy` стабится минимально и не имеет `bpy.app` —
# fall back на (0,0,0), чтобы все HAS_* флаги превратились в False
# (тесты не должны полагаться на конкретный Blender API).
BL = getattr(getattr(bpy, 'app', None), 'version', (0, 0, 0))

MIN_SUPPORTED = (2, 83, 0)

# Color Attributes API (mesh.color_attributes) — 3.2+. До этого был
# mesh.vertex_colors (только BYTE_COLOR per-corner).
HAS_COLOR_ATTRIBUTES = BL >= (3, 2, 0)


# ── Material node-tree compat ────────────────────────────────────────
# Material.use_nodes is deprecated on Blender 5.x — reading it emits a
# DeprecationWarning (spammy from panel draw). Use these helpers instead:
# on ≥5.0 node_tree presence is the real check; on Blender 4.x and
# older, use_nodes still gates node usage even if a node tree exists.

def material_uses_nodes(mat):
    """True if `mat` has an active shader node tree. Avoids the
    use_nodes DeprecationWarning on Blender ≥5.0."""
    if mat is None:
        return False
    nt = getattr(mat, 'node_tree', None)
    if nt is None:
        return False
    if BL < (5, 0, 0):
        return bool(getattr(mat, 'use_nodes', True))
    return True


def material_enable_nodes(mat):
    """Ensure `mat` uses a shader node tree, tolerating Blender versions
    where the use_nodes setter no longer exists."""
    if mat is None:
        return
    try:
        if not mat.use_nodes:
            mat.use_nodes = True
    except AttributeError:
        pass

# ShaderNodeMix (универсальный, RGBA/Vector/Float) — 3.4+. До этого
# для RGBA был ShaderNodeMixRGB с другими input-именами.
HAS_SHADER_NODE_MIX = BL >= (3, 4, 0)

# Bone Collections (armature.collections, bone.collections) — 4.0+.
# До этого bone groups + 32 layer'ов.
HAS_BONE_COLLECTIONS = BL >= (4, 0, 0)

# Principled BSDF v2 — 4.0+. Inputs переименованы: 'Emission' →
# 'Emission Color', subsurface group reshuffled, etc.
HAS_PRINCIPLED_V2 = BL >= (4, 0, 0)

# Node-group interface API (node_tree.interface.new_socket / .items_tree)
# — 4.0+. До этого сокеты группы создавались через
# node_tree.inputs.new(type, name) / node_tree.outputs.new(type, name).
# Старый API на 4.0+ удалён → прямой вызов падает. Используется
# bake-подсистемой (Bevel node-группа). См. node_group_new_output().
HAS_NODE_INTERFACE = BL >= (4, 0, 0)

# Layered Actions API (action.layers, slots, channelbag) — 4.4+. До
# этого action.fcurves напрямую.
HAS_LAYERED_ACTIONS = BL >= (4, 4, 0)

# `mesh.calc_normals_split()` убран в 4.1+ (нормали авто-доступны).
HAS_CALC_NORMALS_SPLIT = BL < (4, 1, 0)

# Extension manifest (blender_manifest.toml) — 4.2+. До этого только
# bl_info dict в __init__.py.
HAS_EXTENSION_MANIFEST = BL >= (4, 2, 0)


# ── Material transparency compat ─────────────────────────────────────
# EEVEE Next (4.2+) заменило legacy-настройки прозрачности:
#   ≤4.1                    4.2+
#   blend_method            surface_render_method ('BLENDED'/'DITHERED')
#   show_transparent_back   use_transparency_overlap
# Записать только legacy-имя на 4.2+ — тихий no-op: именно поэтому
# альфа-материал оставался «Смешанный/Dithered» с включённым
# «Перекрытие прозрачности». Все модули ходят сюда, а не в RNA напрямую.
#
# Стандарт проекта для GTA-альфы: Метод рендеринга = Колебание (CLIP →
# 'DITHERED' на 4.2+) + Перекрытие прозрачности ВЫКЛ. См. make_material_alpha().
# (Раньше был Смешанный/'BLENDED' — вернули на Колебание по просьбе.)

ALPHA_BLEND_MODE = 'CLIP'


def set_blend_method(mat, mode):
    """Выставить режим прозрачности на обоих поколениях EEVEE.

    ``mode`` ∈ OPAQUE / CLIP / HASHED / BLEND. На 4.2+ маппится в
    surface_render_method: BLEND → 'BLENDED', остальное → 'DITHERED'.
    Возвращает True, если хоть одно свойство удалось записать."""
    if mat is None:
        return False
    applied = False
    if hasattr(mat, 'blend_method'):
        try:
            mat.blend_method = mode
            applied = True
        except (TypeError, AttributeError):
            pass
    if hasattr(mat, 'surface_render_method'):
        try:
            mat.surface_render_method = 'BLENDED' if mode == 'BLEND' else 'DITHERED'
            applied = True
        except (TypeError, AttributeError):
            pass
    return applied


def blend_method_of(mat):
    """Текущий режим прозрачности как OPAQUE/CLIP/HASHED/BLEND.

    На 4.2+ авторитетен surface_render_method ('BLENDED' → BLEND);
    legacy blend_method там читается только чтобы отличить
    OPAQUE/CLIP/HASHED друг от друга."""
    if mat is None:
        return 'OPAQUE'
    srm = getattr(mat, 'surface_render_method', None)
    if srm is not None:
        if srm == 'BLENDED':
            return 'BLEND'
        legacy = getattr(mat, 'blend_method', 'CLIP')
        return legacy if legacy in ('OPAQUE', 'CLIP', 'HASHED') else 'CLIP'
    return getattr(mat, 'blend_method', 'OPAQUE')


def transparency_overlap(mat):
    """«Перекрытие прозрачности» (4.2+) / «Show Backface» (≤4.1)."""
    if mat is None:
        return False
    for attr in ('use_transparency_overlap', 'show_transparent_back'):
        if hasattr(mat, attr):
            return bool(getattr(mat, attr))
    return False


def set_transparency_overlap(mat, enabled):
    """Записать «Перекрытие прозрачности» под любым из имён (4.2+ и
    legacy). True — если значение реально изменилось."""
    if mat is None:
        return False
    changed = False
    for attr in ('use_transparency_overlap', 'show_transparent_back'):
        if hasattr(mat, attr) and bool(getattr(mat, attr)) != bool(enabled):
            try:
                setattr(mat, attr, bool(enabled))
                changed = True
            except (TypeError, AttributeError):
                pass
    return changed


def make_material_alpha(mat, mode=ALPHA_BLEND_MODE):
    """Привести альфа-материал к стандарту проекта: Метод рендеринга
    Колебание (DITHERED) + Перекрытие прозрачности выключено. True — если
    что-то изменилось (call-site'ы используют это для своих 'changed' флагов)."""
    if mat is None:
        return False
    changed = False
    if blend_method_of(mat) != mode:
        changed = set_blend_method(mat, mode) or changed
    if transparency_overlap(mat):
        changed = set_transparency_overlap(mat, False) or changed
    return changed


# ── Icon name shims ──────────────────────────────────────────────────
# Иконка 'CHECKMARK' появилась в 2.81. На 2.80 её нет — UILayout кидает
# исключение каждый кадр в draw_header(), что роняет UI до 2 fps. Любая
# незнакомая иконка вызывает тот же эффект — TypeError на enum, и весь
# оставшийся draw() в panel'е обрывается, кнопки/чекбоксы пропадают.
#
# Решение: на module-load интроспектируем реальный enum из bpy.types.
# safe_icon() возвращает запрошенную иконку если есть, иначе из таблицы
# ручных fallback'ов, иначе 'BLANK1' (везде валидный пустой 16×16).

def _collect_valid_icons():
    """Прочитать enum_items у UILayout.label.icon — возвращает set
    реальных иконок текущего Blender'а, или None при ошибке."""
    try:
        items = (bpy.types.UILayout.bl_rna
                 .functions['label']
                 .parameters['icon']
                 .enum_items)
        return set(items.keys())
    except Exception:
        return None


_VALID_ICONS = _collect_valid_icons()

# Ручные substitution'ы для важных «модернизированных» иконок —
# подобраны по смыслу/визуалу. Если новой иконки нет на старом
# Blender'е, подставляем ближайший аналог. Расширяется по мере
# обнаружения новых случаев.
_ICON_FALLBACKS = {
    'CHECKMARK':           'FILE_TICK',
    'OUTLINER_COLLECTION': 'GROUP',
    'IMAGE_RGB_ALPHA':     'IMAGE_RGB',
    'COLLECTION':          'GROUP',
    'COLLECTION_NEW':      'NEW',
    'GP_SELECT_POINTS':    'PARTICLE_POINT',
    'CURRENT_FILE':        'FILE_BLEND',
    'TOPBAR':              'WINDOW',
    'STATUSBAR':           'WINDOW',
    'WORKSPACE':           'WORKSPACE',  # есть на 2.80
    'CON_OBJECTSOLVER':    'CONSTRAINT',
    'BLENDER_LOGO_LARGE':  'BLENDER',
}


def safe_icon(name):
    """Вернуть `name` если иконка валидна в текущем Blender'е, иначе
    fallback из таблицы либо 'BLANK1' (универсально пустой слот).

    На современном Blender'е (≥ 2.81) — pass-through для всего, что
    использует аддон. Активная подмена включается только если иконки
    физически нет в enum'е — т.е. на старых версиях."""
    if _VALID_ICONS is None:
        return name  # introspection failed — trust caller
    if name in _VALID_ICONS:
        return name
    fb = _ICON_FALLBACKS.get(name)
    if fb is not None and fb in _VALID_ICONS:
        return fb
    return 'BLANK1' if 'BLANK1' in _VALID_ICONS else 'NONE'


# Backward-compat constant — раньше было `ICON_CHECK`, оставляем для
# уже подставленных мест.
ICON_CHECK = safe_icon('CHECKMARK')


# ── Icon source toggle ────────────────────────────────────────────
# When True, the addon prefers its custom Lucide PNG bake (under
# data/icons/) over Blender's stock icons — gives a recognisable
# uniform look across the N-panel and floater windows.
# When False, falls back to native Blender icons everywhere. Floaters
# still need PNGs to render via GPU (Blender's icon enum isn't
# accessible from custom draw handlers), so they go text-only on
# this path — but the N-panel and dialogs look fully native.
#
# Kept as a module-level flag so a one-line edit flips the look back
# without touching every call site. The data/icons/ folder is NOT
# deleted on flip — the PNGs stay so the switch is reversible.
USE_CUSTOM_ICONS = False


def inu_icon(name):
    """Return UILayout icon kwargs for `name`.

    When ``USE_CUSTOM_ICONS`` is True (custom Lucide bake mode):
    returns ``{'icon_value': <preview-id>}`` if the addon's PNG bake
    has a matching glyph, else falls back to ``{'icon':
    safe_icon(name)}``.

    When False (native mode, current default): always returns
    ``{'icon': safe_icon(name)}`` — Blender draws its built-in icon.

    Usage::

        layout.operator('foo.bar', text='X', **inu_icon('FILE_FOLDER'))

    The argument can be any expression that yields a Blender icon
    string at call time (literal or e.g. ``'HIDE_OFF' if on else
    'HIDE_ON'``) — resolution happens at draw time, not at import.

    ВАЖНО: некоторые UILayout-методы НЕ принимают ``icon_value`` —
    только string ``icon``. К таким относятся:

      * ``prop_search()`` — TypeError на ``icon_value``
      * большинство ``template_*()`` шаблонов

    Для них используй ``icon=safe_icon('NAME')`` напрямую вместо
    ``**inu_icon('NAME')`` — иначе TypeError при попытке отрисовки."""
    if not USE_CUSTOM_ICONS:
        return {'icon': safe_icon(name)}
    try:
        from ..data import icon_previews
        pid = icon_previews.get(name.lower())
    except Exception:
        pid = 0
    if pid:
        return {'icon_value': pid}
    return {'icon': safe_icon(name)}


# ── Vertex color attribute helpers ───────────────────────────────────
# Унифицированный API поверх mesh.color_attributes (3.2+) и старого
# mesh.vertex_colors (≤ 3.1). Все вызывающие модули должны
# использовать только эти функции, не лезть в mesh.* напрямую.

def vcol_collection(mesh):
    """Возвращает collection-объект (color_attributes или vertex_colors)."""
    if HAS_COLOR_ATTRIBUTES:
        return mesh.color_attributes
    return mesh.vertex_colors


def vcol_list(mesh):
    """Возвращает list всех vcol-слоёв."""
    return list(vcol_collection(mesh))


def vcol_get(mesh, name):
    """Возвращает vcol-слой по имени, либо None."""
    coll = vcol_collection(mesh)
    return coll.get(name)


def vcol_new(mesh, name, *, domain='CORNER', dtype='BYTE_COLOR'):
    """Создаёт новый vcol-слой.

    На 2.80-3.1 domain/dtype игнорируются (всегда CORNER + BYTE_COLOR).
    На 3.2+ domain может быть 'POINT' или 'CORNER'; dtype —
    'BYTE_COLOR' или 'FLOAT_COLOR'.

    Если на старом Blender'е запрошен FLOAT_COLOR — silently fallback
    на BYTE_COLOR (точность урежется до 8 бит/канал).
    """
    if HAS_COLOR_ATTRIBUTES:
        return mesh.color_attributes.new(name=name, type=dtype, domain=domain)
    return mesh.vertex_colors.new(name=name)


def vcol_remove(mesh, layer):
    """Удалить vcol-слой."""
    if HAS_COLOR_ATTRIBUTES:
        mesh.color_attributes.remove(layer)
    else:
        mesh.vertex_colors.remove(layer)


def vcol_active(mesh, layer=None):
    """Get/set активного vcol-слоя.

    layer=None → возвращает активный слой.
    layer=<layer> → ставит активным.
    """
    if HAS_COLOR_ATTRIBUTES:
        if layer is None:
            return mesh.color_attributes.active_color
        mesh.color_attributes.active_color = layer
        return layer
    if layer is None:
        return mesh.vertex_colors.active
    mesh.vertex_colors.active = layer
    return layer


def vcol_layer_name(layer):
    """Имя vcol-слоя (одинаково для обоих API, но wrapper для будущего)."""
    return layer.name


def vcol_data_type(layer):
    """'BYTE_COLOR' / 'FLOAT_COLOR'. На 2.80-3.1 всегда 'BYTE_COLOR'."""
    if HAS_COLOR_ATTRIBUTES:
        return getattr(layer, 'data_type', 'BYTE_COLOR')
    return 'BYTE_COLOR'


def vcol_domain(layer):
    """'POINT' / 'CORNER'. На 2.80-3.1 всегда 'CORNER'."""
    if HAS_COLOR_ATTRIBUTES:
        return getattr(layer, 'domain', 'CORNER')
    return 'CORNER'


# ── Shader node helpers ──────────────────────────────────────────────

# Mix node identifier + socket name constants — версионно-зависимые.
# Старый ShaderNodeMixRGB и новый ShaderNodeMix имеют разные имена
# input'ов и output'ов; чтобы каждый call-site не делал if-version,
# держим имена тут как константы.
if HAS_SHADER_NODE_MIX:
    MIX_NODE_TYPE = 'ShaderNodeMix'
    MIX_INPUT_FACTOR = 'Factor'
    MIX_INPUT_A = 'A'
    MIX_INPUT_B = 'B'
    MIX_OUTPUT_RESULT = 'Result'
else:
    MIX_NODE_TYPE = 'ShaderNodeMixRGB'
    MIX_INPUT_FACTOR = 'Fac'
    MIX_INPUT_A = 'Color1'
    MIX_INPUT_B = 'Color2'
    MIX_OUTPUT_RESULT = 'Color'


def setup_mix_rgba_node(node, *, blend='MIX'):
    """Сконфигурировать только что созданный mix-узел как RGBA-blend.

    На 3.4+ ставит data_type='RGBA' (на старых нет такого свойства).
    Всегда ставит blend_type. Используется парой с
    nodes.new(compat.MIX_NODE_TYPE).
    """
    if HAS_SHADER_NODE_MIX:
        node.data_type = 'RGBA'
    node.blend_type = blend


# ── ShaderNodeMix socket resolvers ──────────────────────────────────
# На 3.4+ ShaderNodeMix имеет ТРИ пары сокетов A/B (Float/Vector/Color).
# `node.inputs['B']` возвращает ПЕРВЫЙ — Float — даже когда data_type=
# 'RGBA' и Float-сокеты помечены как hidden/unavail. Прямое присваивание
# `node.inputs['B'].default_value = (1,1,1,1)` падает с TypeError на
# Float-сокете. Поэтому ниже хелперы фильтруют по `sock.type == 'RGBA'`,
# которые надёжно достают именно Color-сокеты на любой версии.

def _find_socket_by_name_and_type(sockets, name, sock_type):
    """Helper: прокрутить collection (inputs/outputs) и вернуть первый
    сокет с заданным `.name` и `.type`. None если не нашли."""
    for sock in sockets:
        if sock.name == name and sock.type == sock_type:
            return sock
    return None


def mix_input_factor(node):
    """Float Factor input (обоих node-типов одинаковый)."""
    if HAS_SHADER_NODE_MIX:
        s = _find_socket_by_name_and_type(node.inputs, 'Factor', 'VALUE')
        if s is not None:
            return s
    return node.inputs.get('Fac') or node.inputs.get('Factor')


def mix_input_a(node):
    """Color A input (RGBA-typed) для blend operations."""
    if HAS_SHADER_NODE_MIX:
        s = _find_socket_by_name_and_type(node.inputs, 'A', 'RGBA')
        if s is not None:
            return s
    return node.inputs.get('Color1') or node.inputs.get('A')


def mix_input_b(node):
    """Color B input (RGBA-typed) для blend operations."""
    if HAS_SHADER_NODE_MIX:
        s = _find_socket_by_name_and_type(node.inputs, 'B', 'RGBA')
        if s is not None:
            return s
    return node.inputs.get('Color2') or node.inputs.get('B')


def mix_output_result(node):
    """Color Result output (RGBA-typed) для дальнейших links."""
    if HAS_SHADER_NODE_MIX:
        s = _find_socket_by_name_and_type(node.outputs, 'Result', 'RGBA')
        if s is not None:
            return s
    return node.outputs.get('Color') or node.outputs.get('Result')


class _MixWrap:
    """Унифицированный handle поверх ShaderNodeMix или ShaderNodeMixRGB.

    Интерфейс одинаковый: .node, .factor, .a, .b, .result — везде
    socket'ы. Каллер может писать `wrap.factor.default_value = ...`
    и `links.new(wrap.result, ...)` без знаний о версии Blender.
    """
    __slots__ = ('node', 'factor', 'a', 'b', 'result')

    def __init__(self, node, factor, a, b, result):
        self.node = node
        self.factor = factor
        self.a = a
        self.b = b
        self.result = result


def make_mix_rgba(nodes, *, blend='MIX', name=None, label=None):
    """Создать RGBA-mix узел совместимо для всех версий.

    На 3.4+ → ShaderNodeMix с data_type='RGBA'.
    На 2.80-3.3 → ShaderNodeMixRGB.

    Возвращает _MixWrap с унифицированными socket'ами.
    """
    if HAS_SHADER_NODE_MIX:
        n = nodes.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        # IMPORTANT: ShaderNodeMix has TRIPLE A/B/Result sockets per
        # data_type. `n.inputs['A']` returns the Float A — broken for
        # RGBA mode. Use the resolvers that filter by socket .type.
        wrap = _MixWrap(n,
                        factor=mix_input_factor(n),
                        a=mix_input_a(n),
                        b=mix_input_b(n),
                        result=mix_output_result(n))
    else:
        n = nodes.new('ShaderNodeMixRGB')
        n.blend_type = blend
        wrap = _MixWrap(n,
                        factor=n.inputs['Fac'],
                        a=n.inputs['Color1'],
                        b=n.inputs['Color2'],
                        result=n.outputs['Color'])
    if name is not None:
        n.name = name
    if label is not None:
        n.label = label
    return wrap


def find_mix_rgba(nodes, name):
    """Найти ранее созданный mix-узел и вернуть _MixWrap (или None)."""
    n = nodes.get(name)
    if n is None:
        return None
    if n.bl_idname == 'ShaderNodeMix':
        return _MixWrap(n,
                        factor=mix_input_factor(n),
                        a=mix_input_a(n),
                        b=mix_input_b(n),
                        result=mix_output_result(n))
    if n.bl_idname == 'ShaderNodeMixRGB':
        return _MixWrap(n,
                        factor=n.inputs['Fac'],
                        a=n.inputs['Color1'],
                        b=n.inputs['Color2'],
                        result=n.outputs['Color'])
    return None


def principled_emission_input(principled_node):
    """Возвращает input-socket эмиссии у Principled BSDF.

    На 4.0+ это 'Emission Color', до 4.0 — 'Emission'.
    """
    return (principled_node.inputs.get('Emission Color')
            or principled_node.inputs.get('Emission'))


# ── Node-group socket helpers ────────────────────────────────────────
# На 4.0+ интерфейс node-группы (входы/выходы) создаётся через
# node_group.interface.new_socket(name, in_out=..., socket_type=...).
# До 4.0 — node_group.outputs.new(type, name) / .inputs.new(type, name).
# Старый API на 4.0+ удалён, новый на <4.0 отсутствует — поэтому любой
# код, строящий node-группы (bake Bevel), обязан идти через эти shim'ы.

def node_group_new_output(node_group, name, socket_type='NodeSocketColor'):
    """Создать output-сокет node-группы кросс-версионно. Возвращает
    созданный socket / interface-item.

    socket_type — RNA-имя типа: 'NodeSocketShader' (поверхность),
    'NodeSocketColor', 'NodeSocketFloat', 'NodeSocketVector'.
    """
    if HAS_NODE_INTERFACE:
        return node_group.interface.new_socket(
            name=name, in_out='OUTPUT', socket_type=socket_type)
    return node_group.outputs.new(socket_type, name)


def node_group_new_input(node_group, name, socket_type='NodeSocketFloat'):
    """Создать input-сокет node-группы кросс-версионно.
    См. node_group_new_output()."""
    if HAS_NODE_INTERFACE:
        return node_group.interface.new_socket(
            name=name, in_out='INPUT', socket_type=socket_type)
    return node_group.inputs.new(socket_type, name)


# ── Operator gating helpers ──────────────────────────────────────────

def supports(min_ver) -> bool:
    """True если текущий Blender ≥ min_ver."""
    return BL >= tuple(min_ver)


def version_str(ver) -> str:
    """(4, 0, 0) → '4.0'. (3, 2, 0) → '3.2'."""
    return f"{ver[0]}.{ver[1]}" + (f".{ver[2]}" if len(ver) > 2 and ver[2] else "")


def require_version_message(feature_name, min_ver) -> str:
    """Стандартный текст сообщения для unsupported фичи."""
    return f"{feature_name}: требуется Blender {version_str(min_ver)}+ (у вас {version_str(BL)})"


def warn_unsupported(operator, feature_name, min_ver):
    """Отчёт о неподдерживаемой фиче в self.report() оператора.

    Использование:
        if not supports((3, 2, 0)):
            return warn_unsupported(self, "VC Layers", (3, 2, 0))

    Возвращает {'CANCELLED'} — можно сразу `return`.
    """
    operator.report({'ERROR'}, require_version_message(feature_name, min_ver))
    return {'CANCELLED'}


def run_op_override(op, override, mode=None, **kwargs):
    """Вызвать bpy.ops-оператор `op` с context-override кросс-версионно.

    3.2+ → ``with bpy.context.temp_override(**override): op([mode], **kwargs)``
    <3.2 → ``op(override, [mode], **kwargs)`` — legacy dict-override стиль
           (override-словарь первым позиционным аргументом; убран в 3.2,
           но единственный способ на 2.83-3.1).

    `mode` — опциональный execution-context ('EXEC_DEFAULT' /
    'INVOKE_DEFAULT'); если None — не передаётся.

    None-значения из `override` отбрасываются (temp_override их молча
    игнорирует, а legacy-стиль может на них падать)."""
    override = {k: v for k, v in override.items() if v is not None}
    if supports((3, 2, 0)):
        with bpy.context.temp_override(**override):
            return op(mode, **kwargs) if mode else op(**kwargs)
    if mode:
        return op(override, mode, **kwargs)
    return op(override, **kwargs)


def poll_version(cls, min_ver, feature_name) -> bool:
    """Хелпер для classmethod poll(): True если Blender ≥ min_ver, иначе
    False + tooltip-сообщение (на 3.0+) — кнопка оператора становится
    серой/неактивной во ВСЕХ местах, где она нарисована, без правки UI.

    Использование внутри оператора::

        @classmethod
        def poll(cls, context):
            if not compat.poll_version(cls, (3, 2, 0), "Floater"):
                return False
            return True   # ... или существующая логика poll

    poll_message_set появился в 3.0 — на 2.83-2.93 tooltip'а не будет,
    но кнопка всё равно неактивна (что и требуется)."""
    if supports(min_ver):
        return True
    setter = getattr(cls, 'poll_message_set', None)
    if setter is not None:
        try:
            setter(require_version_message(feature_name, min_ver))
        except Exception:
            pass
    return False


# ── Module load sanity check ─────────────────────────────────────────

if BL < MIN_SUPPORTED:
    # Если кто-то всё-таки запустил аддон на ещё более древнем Blender'е —
    # не падать молча, а явно сказать.
    print(f"[INU Tools] WARNING: Blender {version_str(BL)} ниже "
          f"минимально поддерживаемого {version_str(MIN_SUPPORTED)}. "
          f"Часть функций может не работать.")
