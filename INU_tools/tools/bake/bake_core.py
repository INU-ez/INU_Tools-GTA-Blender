# INU_tools.tools.bake.bake_core — Слой 1 подсистемы запекания.
#
# Движок запекания, ничего не знающий про INU-семантику карт. Отвечает
# за: проверку доступности Cycles, обратимый снапшот состояния сцены
# (BakeStateGuard), создание/переиспользование целевой картинки,
# инъекцию активной image-ноды на материалы объекта, сам вызов
# bpy.ops.object.bake и numpy I/O пикселей.
#
# НЕ знает про конкретные карты (AO/Shadow/Bevel) — это слой bake_maps.
# НЕ импортирует bpy-зависимые верхние слои. См. docs/BAKE_FEATURE_PLAN.md.
#
# ВАЖНО: НЕ добавлять `from __future__ import annotations` сюда — модуль
# в перспективе соседствует с PropertyGroup-регистрацией; держим единый
# стиль с остальным аддоном (см. предупреждение в __init__.py).

import numpy as np
import bpy


# Имена datablock'ов, которые подсистема создаёт во время запекания и
# обязана за собой убрать. Namespaced под INU, чтобы:
#   * get-or-reuse по имени не плодил `.001`-дубликаты;
#   * defensive sweep (M5) мог вычистить осколки после hard-crash.
BAKE_NODE_NAME = 'INU_bake_tex'
PLACEHOLDER_MAT_NAME = 'INU_bake_placeholder'


# ── Cycles availability ──────────────────────────────────────────────

def cycles_available(scene=None):
    """True, если движок Cycles доступен (аддон Cycles включён).

    `render.engine` — ДИНАМИЧЕСКИЙ enum: пункт 'CYCLES' регистрируется
    аддоном Cycles в рантайме и НЕ попадает в статический
    `bl_rna.properties['engine'].enum_items` (проверено — даёт ложный
    False, хотя bake с CYCLES при этом проходит). Поэтому смотрим
    напрямую, зарегистрирован ли RenderEngine с bl_idname 'CYCLES'; в
    запас — включён ли аддон 'cycles' в preferences. Cycles идёт в
    комплекте Blender, но пользователь может его отключить.

    `scene` оставлен в сигнатуре для совместимости вызовов; не нужен.
    """
    try:
        for cls in bpy.types.RenderEngine.__subclasses__():
            if getattr(cls, 'bl_idname', '') == 'CYCLES':
                return True
    except Exception:
        pass
    try:
        return 'cycles' in bpy.context.preferences.addons
    except Exception:
        return False


def _gpu_compute_available():
    """True, если в настройках Cycles включена хотя бы одна НЕ-CPU карта
    (CUDA/OptiX/HIP/Metal/oneAPI). Только тогда есть смысл ставить
    scene.cycles.device='GPU' — иначе запекание упадёт обратно на CPU."""
    try:
        addon = bpy.context.preferences.addons.get('cycles')
        cprefs = addon.preferences if addon else None
        if cprefs is None:
            return False
        if getattr(cprefs, 'compute_device_type', 'NONE') in (None, '', 'NONE'):
            return False
        # Заполнить список устройств (на свежем запуске он может быть пуст).
        try:
            cprefs.get_devices()
        except Exception:
            pass
        for d in getattr(cprefs, 'devices', []):
            if getattr(d, 'use', False) and getattr(d, 'type', 'CPU') != 'CPU':
                return True
        return False
    except Exception:
        return False


# ── Scene-state guard ────────────────────────────────────────────────

class BakeStateGuard:
    """Context-manager: снимает снапшот состояния рендера/запекания на
    входе и ВСЕГДА восстанавливает его на выходе (включая исключения).

    Оборачивать им нужно ВЕСЬ прогон запекания (все карты сразу), а не
    каждую карту — engine/samples/world снапшотятся один раз, а
    per-map меняются только bake.use_pass_* + cycles.samples внутри
    скоупа (см. run_cycles_bake). Это исправляет избыточный churn из
    ревью (C9).

    На входе выставляет базовую конфигурацию запекания: engine=CYCLES,
    bake.target='IMAGE_TEXTURES', denoising off. Всё, что трогаем —
    предварительно снапшотим по имени атрибута и аккуратно (через
    hasattr) восстанавливаем, чтобы пережить версионные различия RNA.

    Изоляция чужого света (hide_render сторонних ламп/эмиссии) сюда НЕ
    входит — она привязана к светозависимым картам и добавляется
    отдельным композируемым guard'ом на этапе M3 (C2/C3/C10).

    Использование::

        with BakeStateGuard(context):
            ...  # настроить картинку, ноды, вызвать bake
        # тут сцена уже восстановлена байт-в-байт
    """

    # Атрибуты scene.render.bake, которые подсистема может менять.
    _BAKE_ATTRS = (
        'target', 'margin', 'margin_type',
        'use_pass_direct', 'use_pass_indirect', 'use_pass_color',
        'use_selected_to_active', 'use_clear',
        'max_ray_distance', 'cage_extrusion', 'use_cage',
        'normal_space',
    )
    # Атрибуты scene.cycles, которые подсистема может менять.
    # use_adaptive_sampling — КРИТИЧНО: при нём cy.samples это лишь МАКСИМУМ,
    # Cycles останавливается раньше по порогу шума → пресет «Качество» и
    # ползунок сэмплов почти не влияют (Cycles сам решает, сколько считать).
    # Отключаем → сэмплы детерминированы, качество реально меняет результат.
    _CYCLES_ATTRS = ('samples', 'use_denoising', 'bake_type', 'device',
                     'use_adaptive_sampling')

    def __init__(self, context):
        self.context = context
        self.scene = context.scene
        self._snap = {}          # (owner, attr) -> value
        self._world = None
        self._active = None
        self._mode = None

    def __enter__(self):
        scene = self.scene
        # render.engine
        self._snap[('render', 'engine')] = scene.render.engine
        # bake settings (только реально существующие в этой версии)
        bake = scene.render.bake
        for a in self._BAKE_ATTRS:
            if hasattr(bake, a):
                self._snap[('bake', a)] = getattr(bake, a)
        # cycles settings (если Cycles присутствует как scene-проперти)
        cy = getattr(scene, 'cycles', None)
        if cy is not None:
            for a in self._CYCLES_ATTRS:
                if hasattr(cy, a):
                    self._snap[('cycles', a)] = getattr(cy, a)
        # world + активный объект + режим
        self._world = scene.world
        vl = self.context.view_layer
        self._active = vl.objects.active
        self._mode = getattr(self._active, 'mode', None)

        # ── базовая конфигурация запекания ──
        scene.render.engine = 'CYCLES'
        bake = scene.render.bake
        if hasattr(bake, 'target'):
            bake.target = 'IMAGE_TEXTURES'
        if cy is not None and hasattr(cy, 'use_denoising'):
            cy.use_denoising = False
        # Точное число сэмплов (иначе adaptive sampling глушит эффект качества).
        if cy is not None and hasattr(cy, 'use_adaptive_sampling'):
            cy.use_adaptive_sampling = False
        # Авто-GPU: если в настройках Blender включена GPU-карта Cycles —
        # печём на ней (быстрее на AO/тенях/GI/AA). Иначе оставляем CPU.
        # Раньше device не трогали → запекание всегда шло как в сцене (CPU
        # по умолчанию), отсюда «нет разницы от GPU».
        if cy is not None and hasattr(cy, 'device') and _gpu_compute_available():
            try:
                cy.device = 'GPU'
            except Exception:
                pass
        return self

    def __exit__(self, exc_type, exc, tb):
        scene = self.scene
        # world — отдельно (PointerProperty)
        try:
            scene.world = self._world
        except Exception:
            pass
        cy = getattr(scene, 'cycles', None)
        bake = scene.render.bake
        for (owner, attr), val in self._snap.items():
            try:
                if owner == 'render':
                    setattr(scene.render, attr, val)
                elif owner == 'bake':
                    if hasattr(bake, attr):
                        setattr(bake, attr, val)
                elif owner == 'cycles' and cy is not None:
                    if hasattr(cy, attr):
                        setattr(cy, attr, val)
            except Exception:
                pass
        # активный объект + режим (порядок: сначала active, потом mode)
        try:
            if self._active is not None:
                self.context.view_layer.objects.active = self._active
        except Exception:
            pass
        try:
            if self._mode and self._mode != 'OBJECT':
                bpy.ops.object.mode_set(mode=self._mode)
        except Exception:
            pass
        return False  # не подавлять исключения


# ── Target image ─────────────────────────────────────────────────────

def setup_target_image(name, width, height, *, alpha=True,
                       float_buffer=False, transient=False):
    """Получить-или-переиспользовать картинку `name` нужного размера.

    Никогда не делаем remove+new (это плодит `.001`-дубликаты, т.к.
    fake-user картинку remove не удаляет, а new() авто-суффиксит — см.
    тот же баг в ops/txd_import.py). Вместо этого при несовпадении
    размера ресайзим in-place через Image.scale, сохраняя datablock и
    его пользователей.

    transient=True → use_fake_user=False (промежуточные per-map карты,
    которые должны быть сборщик-мусора-абельны); финальная текстура —
    transient=False (use_fake_user=True, живёт в .blend).
    """
    img = bpy.data.images.get(name)
    if img is not None:
        if img.size[0] != width or img.size[1] != height:
            img.scale(width, height)
    else:
        img = bpy.data.images.new(name, width, height,
                                  alpha=alpha, float_buffer=float_buffer)
    img.use_fake_user = not transient
    return img


# ── Active image-node injection ──────────────────────────────────────

def _ensure_bake_node(mat, image):
    """Создать-или-переиспользовать на материале активную image-ноду
    BAKE_NODE_NAME, указывающую на `image`. Cycles печёт именно в
    активную image-ноду активного материала каждого слота.

    Возвращает (node, prev_active_node) для последующего восстановления.
    """
    mat.use_nodes = True
    nt = mat.node_tree
    node = nt.nodes.get(BAKE_NODE_NAME)
    if node is None or node.type != 'TEX_IMAGE':
        node = nt.nodes.new('ShaderNodeTexImage')
        node.name = BAKE_NODE_NAME
        node.label = BAKE_NODE_NAME
    prev_active = nt.nodes.active
    node.image = image
    node.select = True
    nt.nodes.active = node
    return node, prev_active


def _get_placeholder_mat():
    mat = bpy.data.materials.get(PLACEHOLDER_MAT_NAME)
    if mat is None:
        mat = bpy.data.materials.new(PLACEHOLDER_MAT_NAME)
    mat.use_nodes = True
    return mat


def prepare_bake_targets(obj, image):
    """Подготовить все материалы `obj` к запеканию в `image`.

    Обрабатывает мульти-материал (инъекция ноды в каждый уникальный
    материал), объект без слотов и ПУСТЫЕ слоты (material=None).

    ВАЖНО: пустые слоты заполняются placeholder'ом ПО МЕСТУ (не новым
    слотом). Иначе bpy.ops.object.bake ругается «No active image found
    for material slot N» на любом слоте с material=None и не пишет
    результат — типичный кейс для low-poly billboard-плоскости с пустым
    слотом после composite-preview.

    Возвращает record для restore_bake_targets().
    """
    record = {'nodes': [], 'placeholder': None, 'filled': []}

    if not obj.material_slots:
        # Совсем без слотов — добавляем временный placeholder-слот.
        mat = _get_placeholder_mat()
        obj.data.materials.append(mat)
        record['placeholder'] = (obj, len(obj.data.materials) - 1, mat)
    else:
        # Заполняем пустые слоты placeholder'ом по месту.
        ph = None
        for slot in obj.material_slots:
            if slot.material is None:
                if ph is None:
                    ph = _get_placeholder_mat()
                slot.material = ph
                record['filled'].append(slot)

    mats = [s.material for s in obj.material_slots if s.material]
    seen = set()
    for mat in mats:
        if mat.name in seen:        # один материал в нескольких слотах — раз
            continue
        seen.add(mat.name)
        node, prev_active = _ensure_bake_node(mat, image)
        record['nodes'].append((mat, prev_active))
    return record


def restore_bake_targets(record):
    """Снять всё, что навесил prepare_bake_targets: удалить
    BAKE_NODE_NAME-ноды, вернуть прежнюю активную ноду, убрать
    placeholder-материал и его слот."""
    for mat, prev_active in record.get('nodes', ()):
        nt = getattr(mat, 'node_tree', None)
        if nt is None:
            continue
        n = nt.nodes.get(BAKE_NODE_NAME)
        if n is not None:
            try:
                nt.nodes.remove(n)
            except Exception:
                pass
        try:
            nt.nodes.active = prev_active
        except Exception:
            pass

    # Пустые слоты, временно залитые placeholder'ом — вернуть в None.
    for slot in record.get('filled', ()):
        try:
            slot.material = None
        except Exception:
            pass

    ph = record.get('placeholder')
    if ph is not None:
        obj, idx, mat = ph
        try:
            obj.data.materials.pop(index=idx)
        except Exception:
            pass

    # Placeholder-материал (из обоих путей) удаляем, если больше не нужен.
    phmat = bpy.data.materials.get(PLACEHOLDER_MAT_NAME)
    if phmat is not None and phmat.users == 0:
        try:
            bpy.data.materials.remove(phmat)
        except Exception:
            pass


# ── Target UV (UV→UV bake) ───────────────────────────────────────────
# Cycles печёт в АКТИВНУЮ render-UV объекта (проверено: выбор UV меняет
# раскладку результата). Для trim-развёрток (наложения/тайлинг) печь в
# рабочую UV бессмысленно — каша; вместо этого печём в отдельную чистую
# UV-карту, не трогая trim. Материал при этом продолжает читать текстуры
# со своей UV — так получается перенос «одна UV → другая».

def set_active_uv(obj, uv_name):
    """Сделать `uv_name` активной И active_render UV объекта. Возвращает
    токен для restore_active_uv (или None, если карты нет)."""
    uvs = getattr(obj.data, 'uv_layers', None)
    if not uvs or uv_name not in uvs:
        return None
    prev_active = uvs.active.name if uvs.active else None
    prev_render = next((u.name for u in uvs if u.active_render), None)
    for u in uvs:
        u.active_render = (u.name == uv_name)
    uvs.active = uvs[uv_name]
    return (obj, prev_active, prev_render)


def restore_active_uv(token):
    if token is None:
        return
    obj, prev_active, prev_render = token
    uvs = getattr(obj.data, 'uv_layers', None)
    if not uvs:
        return
    if prev_render is not None:
        for u in uvs:
            u.active_render = (u.name == prev_render)
    if prev_active and prev_active in uvs:
        uvs.active = uvs[prev_active]


_SRC_UV_NODE = 'INU_bake_srcuv'


def pin_image_nodes_to_uv(obj, uv_name):
    """Прикрепить КАЖДУЮ Image-Texture ноду материалов объекта к UVMap-ноде
    с `uv_name`, чтобы текстуры продолжали сэмплиться с ИСХОДНОЙ UV даже
    после переключения активной UV на целевую (UV→UV). Без этого нода без
    UV Map сэмплит по активной UV → при запекании в другую UV берёт не те
    пиксели → каша (так делает и TexTools — пинит источник).

    Трогаем только ноды с НЕподключённым Vector (явный UV Map / mapping
    пользователя уважаем). Возвращает токен для unpin_image_nodes.
    """
    created = []
    seen = set()
    for slot in obj.material_slots:
        mat = slot.material
        if (not mat or mat.name in seen or not mat.use_nodes
                or not mat.node_tree):
            continue
        seen.add(mat.name)
        nt = mat.node_tree
        for node in list(nt.nodes):
            if node.type != 'TEX_IMAGE':
                continue
            vec = node.inputs.get('Vector')
            if vec is None or vec.is_linked:
                continue
            uvm = nt.nodes.new('ShaderNodeUVMap')
            uvm.name = _SRC_UV_NODE
            uvm.uv_map = uv_name
            nt.links.new(uvm.outputs['UV'], vec)
            created.append((nt, uvm))
    return created


def unpin_image_nodes(token):
    for nt, uvm in (token or ()):
        try:
            nt.nodes.remove(uvm)
        except Exception:
            pass


# ── Bake invocation ──────────────────────────────────────────────────

def run_cycles_bake(bake_type, *, margin=8, use_clear=True,
                    pass_direct=None, pass_indirect=None, pass_color=None,
                    samples=None, selected_to_active=False,
                    cage_extrusion=0.0, max_ray_distance=0.0):
    """Один вызов bpy.ops.object.bake с заданными per-map настройками.

    pass_* флаги ставятся на scene.render.bake (откуда bake() их читает);
    type/margin/use_clear передаются аргументами.

    selected_to_active=True → перенос с выделенных (хайполи) на активный
    (лоуполи), с cage_extrusion и опц. max_ray_distance (hi→low, M9b).

    Предполагается, что вызывающий уже:
      * внутри BakeStateGuard (движок CYCLES, цель IMAGE_TEXTURES);
      * выставил нужное выделение/активный объект;
      * назначил активную image-ноду через prepare_bake_targets.
    """
    scene = bpy.context.scene
    bake = scene.render.bake
    cy = getattr(scene, 'cycles', None)
    if samples is not None and cy is not None and hasattr(cy, 'samples'):
        cy.samples = samples
    if pass_direct is not None and hasattr(bake, 'use_pass_direct'):
        bake.use_pass_direct = pass_direct
    if pass_indirect is not None and hasattr(bake, 'use_pass_indirect'):
        bake.use_pass_indirect = pass_indirect
    if pass_color is not None and hasattr(bake, 'use_pass_color'):
        bake.use_pass_color = pass_color

    kwargs = dict(type=bake_type, margin=margin, use_clear=use_clear,
                  use_selected_to_active=selected_to_active)
    if selected_to_active:
        kwargs['cage_extrusion'] = cage_extrusion
        if max_ray_distance and max_ray_distance > 0.0:
            kwargs['max_ray_distance'] = max_ray_distance
    bpy.ops.object.bake(**kwargs)


# ── numpy pixel I/O ──────────────────────────────────────────────────

def read_image_to_numpy(image):
    """Прочитать пиксели `image` в (h, w, channels) float32 в нативном
    для Blender порядке (снизу вверх, RGBA).

    Читаем пиксели напрямую через foreach_get — НЕ полагаемся на
    image.has_data: он возвращает False на packed-only картинках сразу
    после pack(), хотя пиксели уже доступны (см. тот же нюанс в
    ops/texture_ops.image_has_significant_alpha).
    """
    w, h = image.size
    ch = image.channels
    buf = np.empty(w * h * ch, dtype=np.float32)
    image.pixels.foreach_get(buf)
    return buf.reshape(h, w, ch)


def write_numpy_to_image(image, arr, *, pack=True):
    """Записать (h, w, channels) float32 массив в `image`.

    Порядок пикселей — нативный Blender (снизу вверх): массив,
    полученный из read_image_to_numpy и обработанный numpy'ем, пишется
    обратно без flip. Flip нужен только при обмене с внешним порядком
    байт (TXD), здесь мы не покидаем систему координат Blender.
    """
    flat = np.ascontiguousarray(arr, dtype=np.float32).ravel()
    # Буфер картинки мог «откатиться» к старому размеру после scale():
    # любой colormanage-сигнал (alpha_mode, colorspace) перечитывает её из
    # packed-данных. Сверяем с массивом и ресайзим прямо перед записью —
    # иначе foreach_set падает с «expected N, got M».
    if arr.ndim == 3 and len(image.pixels) != flat.size:
        h, w = arr.shape[:2]
        image.scale(w, h)
    image.pixels.foreach_set(flat)
    if pack:
        try:
            image.pack()
        except Exception:
            pass
    image.update()


# ── Denoise (OIDN via Compositor) ────────────────────────────────────
# Имя временной сцены-денойзера (get-or-reuse под INU-неймспейсом).
DENOISE_SCENE_NAME = 'INU_Denoise'


def denoise_image(image, context=None, albedo=None, normal=None):
    """Денойзить `image` ин-плейс. Два пути:

    1. **OIDN-нода компоузера** (Blender 4.x, встроенный, feature-guided по
       albedo/normal — лучше по качеству). Работает только там, где у сцены
       есть встроенное `node_tree`.
    2. **Bilateral (чистый numpy)** — фолбэк на Blender 5.x (компоузер стал
       node-группой: `CompositorNodeComposite`/`Viewer` в группе не
       существуют, readback невозможен) и при любом сбое пути 1. Работает
       на любой версии без зависимостей.

    Возвращает True при успехе, False — если не удалось ни то ни другое.
    НИКОГДА не бросает — денойз не должен ронять запекание."""
    if _denoise_compositor(image, context, albedo, normal):
        return True
    return _denoise_bilateral(image)


def _denoise_bilateral(image):
    """Фолбэк-денойз: bilateral на чистом numpy (см. bake_composite). Не
    OIDN-качество, но краесохраняющее и версия-независимое. Ин-плейс."""
    try:
        from .bake_composite import bilateral_denoise
        arr = read_image_to_numpy(image)
        out = bilateral_denoise(arr)
        write_numpy_to_image(image, np.ascontiguousarray(out), pack=True)
        return True
    except Exception as e:
        print(f"[INU bake_core] bilateral denoise skipped: {e}")
        return False


def _denoise_compositor(image, context=None, albedo=None, normal=None):
    """OIDN через компоузер (Blender 4.x). Временная сцена с графом
    ``Image → Denoise → Composite/Viewer``, рендер под размер картинки,
    результат из ``'Viewer Node'`` пишется обратно. На 5.x (нет
    scene.node_tree) сразу False → вызывающий уйдёт в bilateral.

    `context` — контекст вызывающего: сцену подменяем на ОКНЕ КОНТЕКСТА
    (bpy.ops.render.render рендерит сцену контекста; со вторым окном подмена
    на windows[0] отрендерила бы настоящую сцену пользователя)."""
    tmp = None
    try:
        ctx = context if context is not None else bpy.context
        win = getattr(ctx, 'window', None)
        if win is None:
            wm = getattr(ctx, 'window_manager', None)
            win = wm.windows[0] if (wm and len(wm.windows)) else None
        if win is None:                       # headless — рендер-op недоступен
            return False
        w, h = image.size
        if w == 0 or h == 0:
            return False

        tmp = bpy.data.scenes.new(DENOISE_SCENE_NAME)
        # Blender 5.x: scene.node_tree убран (компоузер — node-группа, где нет
        # Composite/Viewer). Тогда компоузер-путь не годится → False (фолбэк).
        if not hasattr(tmp, 'node_tree'):
            return False
        try:
            tmp.render.engine = 'BLENDER_WORKBENCH'   # дёшево: 3D нам не нужен
        except Exception:
            pass
        tmp.render.resolution_x = w
        tmp.render.resolution_y = h
        tmp.render.resolution_percentage = 100
        tmp.render.use_compositing = True
        tmp.render.use_sequencer = False
        try:
            tmp.use_nodes = True
        except Exception:
            pass
        nt = getattr(tmp, 'node_tree', None)
        if nt is None:
            return False
        nt.nodes.clear()
        n_img = nt.nodes.new('CompositorNodeImage')
        n_img.image = image
        n_dn = nt.nodes.new('CompositorNodeDenoise')
        n_out = nt.nodes.new('CompositorNodeComposite')
        n_view = nt.nodes.new('CompositorNodeViewer')
        nt.links.new(n_img.outputs['Image'], n_dn.inputs['Image'])
        # Доп-пассы (feature-guided): albedo/normal того же размера → чище края.
        for _feat, _sock in ((albedo, 'Albedo'), (normal, 'Normal')):
            if (_feat is not None and _sock in n_dn.inputs
                    and _feat.size[0] == w and _feat.size[1] == h):
                fn = nt.nodes.new('CompositorNodeImage')
                fn.image = _feat
                nt.links.new(fn.outputs['Image'], n_dn.inputs[_sock])
        nt.links.new(n_dn.outputs['Image'], n_out.inputs['Image'])
        nt.links.new(n_dn.outputs['Image'], n_view.inputs['Image'])

        prev_scene = win.scene
        win.scene = tmp
        try:
            bpy.ops.render.render(write_still=False)
        finally:
            try:
                win.scene = prev_scene
            except Exception:
                pass

        viewer = bpy.data.images.get('Viewer Node')
        if viewer is None or viewer.size[0] != w or viewer.size[1] != h:
            return False
        arr = read_image_to_numpy(viewer)
        tgt_ch = image.channels
        if arr.shape[2] != tgt_ch:
            if arr.shape[2] > tgt_ch:
                arr = arr[:, :, :tgt_ch]
            else:
                pad = np.ones((h, w, tgt_ch - arr.shape[2]), np.float32)
                arr = np.concatenate([arr, pad], axis=2)
        write_numpy_to_image(image, np.ascontiguousarray(arr), pack=True)
        return True
    except Exception as e:
        print(f"[INU bake_core] compositor denoise skipped: {e}")
        return False
    finally:
        if tmp is not None:
            try:
                bpy.data.scenes.remove(tmp)
            except Exception:
                pass


# ── Smoke test ───────────────────────────────────────────────────────

def selftest(width=4, height=4):
    """Дымовой тест numpy<->image round-trip. Запуск из консоли Blender::

        from INU_tools.tools.bake import bake_core
        bake_core.selftest()

    Создаёт транзитную картинку, пишет случайный паттерн, читает назад,
    сверяет и удаляет. Возвращает True при совпадении.

    float_buffer=True обязателен: на обычной (8-битной) картинке пиксели
    квантуются до 1/255 (~4e-3), и точный round-trip невозможен в
    принципе — это свойство хранения, а не плумбинга. Float-буфер
    доказывает, что foreach_get/set лосслесс. Для качества промежуточные
    per-map bake-цели тоже стоит делать float (M4/M5).
    """
    name = 'INU_bake_selftest'
    img = setup_target_image(name, width, height, transient=True,
                             float_buffer=True)
    src = np.random.rand(height, width, img.channels).astype(np.float32)
    write_numpy_to_image(img, src, pack=False)
    back = read_image_to_numpy(img)
    ok = bool(np.allclose(src, back, atol=1e-6))
    max_diff = float(np.abs(src - back).max())
    try:
        bpy.data.images.remove(img)
    except Exception:
        pass
    print(f"[INU bake_core] selftest round-trip: "
          f"{'OK' if ok else 'FAIL'} (max diff {max_diff:.2e})")
    return ok
