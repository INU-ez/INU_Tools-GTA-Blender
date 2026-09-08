# INU_tools(gta_sa) for Blender 4.2+
# Copyright (C) 2024-2026  INU
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Material/Object property names are compatible with DragonFF by Parik (GPL-3.0)
# https://github.com/Parik27/DragonFF
#
# Объединённая панель инструментов для работы с GTA SA моделями
# Включает: Export (DFF, COL, LOD, TXD), Prelight, Lightmap Generator
#
# ВАЖНО: НЕ добавлять `from __future__ import annotations` в этот файл!
# Это включает PEP 563 (lazy stringified annotations), что ломает Blender'овскую
# регистрацию `prop: BoolProperty(...)` — bpy читает `cls.__annotations__`
# и ждёт там `_PropertyDeferred` объекты, а получает строки → "property not found".

bl_info = {
    "name": "INU_tools(gta_sa)",
    "author": "INU",
    "version": (2, 3, 2),
    # Минимум 2.83 LTS — поддержка через tools/compat.py:
    # • bake / preview / DFF I/O работают через legacy mesh.vertex_colors
    # • prelight preview shader использует ShaderNodeMixRGB на ≤3.3
    # • VC Layers System требует 3.2+ (на старых показывает warning)
    # • IK rig работает на pose.bones (без bone collections)
    # 2.80–2.82 не поддерживаются: критичные панели (Object IDE/IPL,
    # 2DFX Effects, Prelight, Lighting) ломаются из-за отсутствия
    # `ui_units_x` (2.83+), CHECKMARK (2.81+) и других мелких RNA-различий.
    # blender_manifest.toml для extensions.blender.org остаётся 4.2+ —
    # это второй канал distribution, для современного Blender'а.
    "blender": (2, 83, 0),
    "location": "View3D > Sidebar (N) > GTA Tools",
    "description": "Toolset for GTA SA models",
    "category": "3D View",
}

# Changelog:
# v1.7.0 - Большой UX-релиз + рефакторинг.
#        - Adaptive grid auto-split (tools/map_export.py compute_adaptive_cells):
#          quadtree-разбиение по плотности (max_per_cell, min_cell_size floor).
#          Плотные районы получают мелкие ячейки, разреженные остаются одной
#          большой. Имя ячейки <base>_q<path>, где path — путь по квадрантам
#          (0=SW, 1=SE, 2=NW, 3=NE). 13 unit-тестов в test_map_export_split.py.
#        - Prelight panel polish: убраны иконки FORWARD/BACK на кнопках Day↔Night
#          (выглядели как media play/back и спорили со стрелкой → в тексте),
#          лейбл «Скопировать:» как заголовок, удалены 3 layout.separator() и
#          info-кнопки перед лейблами — на 4-5 строк ниже.
#        - IK Rig для SA peds (ops/ik_rig.py): control-bones внутри армати с custom-shape
#          кубиками (chain/pole/rot/root), FK→IK bake при создании, brute-force
#          pole_angle калибровка, Bake & Clear IK перед IFP-экспортом, INU_Ground
#          floor plane 10×10м с FLOOR constraint и offset slider.
#        - Animated Map Object workflow (ops/animobj_ops.py): Setup rig → Validate →
#          Export DFF+IFP+IDE одной кнопкой. Ползунки axis/turns/duration/reverse
#          с auto-rebuild keyframes. Auto vs Manual режим управления Action.
#        - Frame Hierarchy Editor (ops/frame_hierarchy.py): Rename / Set Parent /
#          Unparent / Зеркало L↔R / Validate Vehicle (37 dummies) / Validate Ped
#          (31 кость) против vanilla SA шаблонов.
#        - Vehicle Paintjob (ops/paintjob_ops.py): material props paintjob_alt_1/_2
#          + TXD-хук пишет <base>_paintjob1/2 + Validate Paintjobs.
#        - Profile system (tools/profiles.py): JSON-storage наборов N-sidebar
#          панелей в INU_Preset/profiles/<name>.json со списком order и hidden,
#          dropdown в шапке + операторы save/edit/delete/pick_panel/toggle_panel.
#        - Smart auto-TXD picker (ops/dff_import.py): coverage-based scoring
#          (same-name → ≥50% coverage → solo). Использует core/txd.read_txd_texture_names
#          (header-only TXD parse, ~50× быстрее). Грузит с name_filter — только
#          нужные текстуры (vehicle.txd 150 → ~5 для одной двери).
#        - DFF/COL drag-drop в viewport (FH_dff_drop, FH_col_drop), TXD-drop
#          теперь цепляет материалы на выделенные меши.
#        - 2DFX panel: collapsible-секции (Свойства/Поведение/Тень/Флаги),
#          семантические группы флагов (Видимость/Эффекты короны/Мерцание/Доп.),
#          per-bit tooltips через operator description classmethod.
#        - DFF Flags pipeline-aware: Vehicle прячет Day/Night/Light Beam,
#          Day/Night pipeline прячет mesh-флаги Day/Night.
#        - Texture Manager dropdowns: Текстуры (Найти/Скопировать/Дубли/Найти-Удалить
#          unused) + Материалы (Check/Cleanup/Sort) — 9 кнопок → 3 строки.
#        - Compact mass export: «В папку» / «В IMG» уехали в дропдаун Экспорт ▾
#          как «All → Папка» / «All → IMG». Убран hint «Полный экспорт».
#        - Selection diagnostic: при множественном DFF показывает «name +N» count.
#        - Save-required wrappers (Extract Resources / Import Map / Export Map):
#          alert-box + disabled-кнопки пока .blend не сохранён. Soft cache-empty
#          warning на Import Map (Empty placeholders вместо hard cancel).
#        - Light Master container panel: 5 sub-panels (Prelight/Prelight COL/
#          Vertex Paint/Lightmap/Itera Tools) под одним заголовком.
#        - 4 dropdown menus: Create 2DFX / Radar Maker / Path Traffic / Import-Export.
#        - 2-column IDE/IPL panel layout, niche IPL utilities полной шириной снизу.
#        - Все operator bl_label получили префикс «INU: » для F3-поиска.
#        - Bug fixes: TXD import duplicates (vehiclelights128.001-005),
#          material dedup при DFF import (fingerprint всех effect-блоков),
#          2DFX preview plane size (corona_size * 5.0 → native), BreakableData
#          round-trip (reader не парсил), IFP export round-trip (rest_quat @ bl_quat
#          инверс), IFP custom skin root motion (bone_id fallback для 'Bip01'/'Root'),
#          Blender 5.x compat (layered Action API, default=set() fix).
#        - Refactor: __init__.py 16486 → 4327 строк. 22 новых ops/*.py модуля,
#          ui/panels.py (2820 строк), ui/registry.py с apply_order декоратором.
#        - 7 новых pytest файлов (~110 тестов) в dev/tests/: DFF/COL/IDE/IPL/IMG
#          round-trip + panel registry + profiles.
#        - Repo cleanup: docs/ папка, удалён COMPARISON.md.
#        - DOCS_rus.md +470 строк: новые рецепты IK Rig / Profile system /
#          Animated Map Object / Frame Hierarchy / Paintjob.
# v1.6.7 - Map round-trip preservation (полный цикл импорт→правка→экспорт):
#        - inu.col_name + inu.lod_object свойства для round-trip разметки COL/LOD
#          через scene props (не теряются при reload .blend).
#        - Group-by-IPL импорт: каждый исходный IPL → отдельная коллекция; By-collection
#          экспорт: каждая коллекция → свой IPL (плюс multi-collection picker с чекбоксами).
#        - Парность main ↔ LOD в IDE/IPL output: lod_index пересчитывается на позицию
#          LOD-инстанса в выходном IPL.
#        - TXD bucketing per-txd_name: модели с одинаковым inu.txd_name группируются
#          в один .txd; per-DFF COL по умолчанию (один col на модель, не one-shared).
#        - Modal Map Export с progress bar и ESC cancel; multi-collection чекбоксный
#          picker; параллельный DXT1.
#        - Format conformance: CRLF line endings в IDE/IPL/IFP, IPL inst dedup,
#          согласованность ID для .NNN дубликатов в outliner.
#        - Vehicles панель вынесена из Check как dedicated.
# v1.6.6 - Map auto-split (XY grid): tools/map_export.py auto_split=True + cell_size
#          (по умолчанию 256м) → каждая клетка свой IPL для эффективной streaming-загрузки.
#        - Vehicle damage variants: ops/vehicle.py операторы Add (создаёт _dam meshcopy
#          скрытый во viewport), Show OK/Dam/Both (toggle hide_viewport на парах),
#          Check pairs (отчёт с одиночными атомиками).
#        - VC Layer System (BETA): tools/vc_layers.py — composite vertex colors из
#          нескольких layers с per-layer opacity/brightness/contrast, multi-select.
#        - IFP write: ANP2 / ANPK форматы (раньше только ANP3), source_format
#          сохраняется при импорте → экспорт по умолчанию пишет в исходном формате.
#        - Bitmaps Manager: Find Unused / Remove Unused (orphan images + materials).
#        - COL parsing ~5× быстрее (numpy bulk decode фасов/вершин).
#        - Train paths verified: запись/чтение track1/track2.dat с прогоном round-trip.
# v1.6.5 - Производительность и round-trip карты — накопленные изменения после 1.6.4-beta
#        - Import Map ~10x быстрее: полный район LA за ~30 с (было 5+ мин)
#          - cache-only поток (никакого обращения к IMG в горячем цикле)
#          - параллельный DFF-парсинг: 4-worker ThreadPoolExecutor, split на
#            read_dff_file (main) + DffClump.to_bytes (worker) — numpy/zlib отпускают GIL
#          - material-cache по (texture_name, RGBA) — одна текстура на 500 моделей = один материал
#          - bulk_mode в import_dff: пропускает per-model view_layer.update/select_all
#            (O(N²) → O(N)), target_collection напрямую — без unlink+relink
#          - убран print("[DFF Parse] ...") на каждом frame (~170 с потерь на stdout)
#          - LOD-детекция теперь только по имени (is_lod_name), lod_refs из IPL отключён
#            из-за шумных данных ванили
#          - bulk_mode пропускает armature для ванильных DFF с HAnim без skin
#          - фикс IPL lod_index remap при мерже нескольких IPL в один список
#        - Import Map — Load COL toggle: коллизии подтягиваются рядом с геометрией
#          в Map_COL коллекцию, с transform'ом на каждый инстанс. Для round-trip
#          (импорт части карты → редактирование → экспорт в IMG другой сборки).
#          Парсинг .col параллелен в том же пуле, ключуется по внутреннему model_name.
#        - Export to IMG ~5-15x быстрее:
#          - ImgWriter context manager (core/img.py): директория читается и пишется
#            по одному разу вместо N раз (~2.6 ГБ лишних записей на большом экспорте)
#          - параллельное кодирование DFF/COL: build_dff_clump/build_col_model на main
#            (bpy reads), clump.to_bytes() в 4-поточном пуле
#        - Shared TXD toggle (симметрично с COL Library): пакует все текстуры в один
#          общий .txd вместо одного на модель — scene props gtatools_export_all_txd_shared[_name]
#        - Фикс «экспортируется только коллизия»: унифицированы тумблеры DFF/COL/LOD/TXD
#          между «В папку», «В IMG», «INU Export». Все операторы теперь читают
#          gtatools_export_all_*, устаревшие gtatools_img_export_* удалены.
#          Добавлен отдельный export_lod_flag (раньше LOD был привязан к DFF).
#        - ID Manager:
#          - новая reserve_id(model_id, name) — помечает ID занятым (append если нет)
#          - новая sync_scene_to_preset(objects) — подтягивает ID сцены в пресет,
#            вызывается в начале Auto Assign / Assign From
#          - новая gc_preset(objects) + кнопка «Освободить фантомы» в ID Manager панели —
#            освобождает слоты без backing-объекта
#          - Assign IDs from... теперь пишет в пресет через reserve_id на каждом назначении
#          - Clear Selected IDs не освобождает слот если другой объект сцены держит тот же ID
#            (защита от Shift+D-дубликатов с наследуемым inu.model_id)
#          - новая кнопка «Очистить ID» в Object Properties → INU Tools: Model, под полем Model ID
#        - UI pipeline reorganization (Этапы 1-6):
#          - все подпанели N-sidebar получили bl_order по категориям SETUP/MODEL/DATA/EXPORT
#          - Export панель наверху (bl_order=0), 3-кнопочный ряд: В папку / В IMG / INU Export
#          - Суффиксы/Префиксы и ID Manager вынесены из Scene Properties в N-sidebar
#          - новая панель «INU Tools: Model» в Object Properties — все per-object props в одном месте
#          - Itera Tools 3 / Vertex Paint / LightMap скрыты через poll() до доработки
#          - убраны dead code: gtatools.prelight (35 строк), custom Twemoji PNG icons
#          - Bitmaps Manager переведён на русский (23 новых entries в locale/eng.py)
#        - Material Presets: формат перенесён из JSON в INU_Preset, добавлено undo для
#          7 операторов (Set Preset, Fill Colors, Scatter Light, Bake, Post-Process, ...)
#        - Progress bars: добавлены в Build Map / Export to IMG / Extract Resources
#        - ID Manager multi-preset: поддержка нескольких файлов пресетов
#          в INU_Preset/id_presets/<name>.txt с UI create/rename/delete
#        - LOD Detection: обработка нерегулярных имён ванили (LODfoo / foo_LOD /
#          foo1LOD / modeLODlaett) — is_lod_name покрывает все 4 паттерна
#        - Profiler: thread-safe Profiler в tools/profiler.py + Scene toggle
#          gtatools_profile_enabled — отчёт в .inu_cache/_profile.log
#        - Skip 2DFX по умолчанию = True для bulk-импорта карты (иначе тысячи
#          Light/Empty объектов роняют viewport)
# v1.6.4 - (pre-release) 11 экспериментальных фич — проверка в игре ещё не проведена
#        - Map Export: единый экспорт сцены → DFF + COL + TXD + IDE + IPL одной кнопкой
#          (tools/map_export.py, авто-паринг LOD/COL, пул ID из настройки для пустых model_id=0)
#        - Binary IPL Write: запись в формате `bnry` (только inst+cars, как у Rockstar)
#          (core/ipl.py _write_binary_ipl + чекбокс Binary в GTATOOLS_OT_export_ipl)
#        - UV-анимация в DFF: простой U/V-скролл через чанки 0x2B + 0x135
#          (core/dff.py UVAnim/UVAnimDict, material props uv_anim_write/speed_u/v/duration)
#          ОГРАНИЧЕНИЕ: только запись, обратное чтение не реализовано
#        - Breakable Objects: чанк 0x253F2FD + сила разрушения per-object
#          (core/dff.py BreakableData, обj.inu.breakable/breakable_force)
#        - IFP Batch Import: папка с .ifp → стек на NLA-треке armature
#          (ops/ifp_import.py batch_apply_sequential, режимы NLA/Actions, зазор между клипами)
#        - GTA Material Panel: вкладка Properties → Material с dropdown пресетов
#          (Generic/Vehicle Body/Vehicle Glass/Ped/Env/Dual/Specular + vehicle color slot)
#        - Bitmaps Manager: scan missing / resolve from folder / batch copy / find duplicates
#          (tools/bitmaps_manager.py, панель в N-Sidebar GTA Tools)
#        - CST IO: текстовая сериализация COL (формат Steve's COL Editor, с shadow mesh)
#          (core/cst.py + ops/cst_import.py + ops/cst_export.py)
#        - Vehicle Scale Helper: пропорциональное масштабирование иерархии машины
#          (tools/vehicle_scale.py, опция Dummies Only)
#        - Train Station Markers: видимые Empty-сферы на станциях train-трека
#          (ops/ifp_import.py _refresh_station_markers)
#        - Roadblocks & Traffic Lights: переключение per-node флагов на выделенных path-IPL точках
#          (core/paths.py PATH_FLAG_* константы, ops/ifp_import.py GTATOOLS_OT_path_node_flag)
#        - FLA4 Path Format: чтение/запись расширенных nodes*.dat (spawn/speed/lanes per-node)
#          (core/paths.py FLA4_MAGIC + ветки в read_nodes/write_nodes, чекбокс в Export Path Nodes)
#        - Фиксы ревью: UV_ANIM_KEYFRAME_SIZE 36→32 (pack был короче на 4 байта),
#          path_node_flag правильный маппинг spline→IDProp через пропуск empty-нод,
#          station markers через matrix_parent_inverse.identity() + local pt.co,
#          map_export переключение в OBJECT mode перед select_all,
#          UVAnim.node_to_uv дефолт (1,0,...) вместо (0,...) — иначе анимация инертна
#        - Bitmaps Manager group_by_txd: читает obj.inu.txd_name (а не mat.get('txd_name'))
#          через обратный индекс материал→TXDs
#        - DOCS.md + DOCS_rus.md: новая секция "Experimental (v1.6.4)" с 12 подразделами
#        - README.md + README_rus.md: секция "Experimental (v1.6.4)" с warning-блоком,
#          Coming Soon сжат до одного пункта (Vehicles Phase 2+)
#        - bl_info warning: "Experimental features — not fully tested in-game"
#          (оранжевая метка в Blender Add-ons panel)
# v1.6.3 - Particle Effects: полноценный редактор GTA SA effects.fxp
#        - Парсер effects.fxp (text-based, 82 эффекта), кэш с auto-reload
#        - Симуляция частиц в viewport (30 FPS, до 64 частиц на эмиттер, billboard к камере)
#        - Dropdown выбора эффекта из 82 систем + multi-emitter switching
#        - Редактирование 40+ параметров: цвет, размер, скорость, направление, физика, ветер, гравитация
#        - Keyframe editor для curves (size/color/alpha over lifetime)
#        - Сохранение в effects.fxp с авто-бэкапом (.fxp.bak)
#        - Operators: New, Delete, Switch Emitter, Reload effects.fxp
#        - IDE/IPL Export: очистка .001 дубликатов перед записью
#        - IPL Upsert: поддержка нескольких instances одной модели (match по позиции)
#        - DFF Export: _read_texture идёт через Prelight_Mix/LM_Mix к реальной текстуре
#        - TXD Export: пропускает LM_Texture/Lightmap_Texture ноды
#        - LightMap UV2: Add/Toggle/Remove кнопки в Prelight панели (Multiply blend на UV2)
#        - Prelight Bake: использует loop.normal (smooth shading), пропускает скрытые лампы
#        - Reset Transform: сброс Location/Rotation в (0,0,0) для выделенных мешей
#        - Batch Set Type: массовое назначение OBJ/COL/SHA/NON с автопереименованием
#        - 2DFX: detach all from mesh, список привязанных в UI меша
#        - 2DFX Billboard: переход с timer на draw handler — фикс tracking при смене сцены
#        - DFF Flags: компактный список чекбоксов вместо больших кнопок
#        - Object Properties: новая панель "GTA SA: IDE / IPL" (перенос из N-панели)
#        - Nodes Export: авто-разбиение по зонам карты 8x8 (64 файла nodes0..63.dat)
#        - Nodes Import: мультифайловый импорт (несколько nodes*.dat за раз)
#        - ID Manager: Assign from ID..., Extend IDs (FLA, Fastman Limit Adjuster)
#        - .gitattributes: нормализация LF/CRLF
#        - Документация: Alpha threshold 57% (145/255) — задокументирован hard cutoff в GTA SA
# v1.6.1 - IPL Import: перемещение COL вместе с DFF, Empty с _empty суффиксом в коллекции IPL_Empty, кнопка Заменить Empty
#        - Префиксы моделей (DFF/LOD/COL) в настройках, авто-очистка конфликтов суффикс/префикс
#        - Все import/export используют пользовательские суффиксы/префиксы
#        - Model Links: визуализация связей DFF↔LOD↔COL пунктирными линиями
#        - LOD/COL → DFF: кнопка подтягивания к позиции DFF
#        - Скрытие DFF/LOD/COL по отдельности в панели Проверка
#        - Удалить из IMG по типу выделенного объекта (DFF+TXD / COL / LOD)
#        - Список файлов IMG (UIList с прокруткой и поиском)
#        - Менеджер ID: очистка ID выделенных, синхронизация сцены, создание файла 321-19999
#        - Проверка конфликтов ID (предупреждение в панели)
#        - Normals toggle в панели Pipeline
#        - Drag & Drop TXD с созданием материалов
# v1.6.0 - Import Map: workflow Extract → Build .glb → Import с автосортировкой по коллекциям
#        - BBox Mode: Bounding Box для далёких объектов (300м от выделения)
#        - IPL ZONE секция: парсинг/запись/визуализация зон карты
#        - Динамические регионы из gta.dat
#        - TXD: исправлена декомпрессия RASTER_888, улучшена детекция DXT
#        - GPU автодетект
#        - UI: объединены Экспорт/Импорт, компактный layout, панель Проверка на русском
#        - Экспорт коллекций (активная коллекция если ничего не выделено)
#        - Убраны: Fake mode, Bounds mode, LOD view, Auto-discover
# v1.4.7 - Export: COL Surface Type — панель выбора типа поверхности коллизии в Material Properties
#        - 179 материалов GTA SA с поиском по названию, запись через DragonFF col_mat_index
# v1.4.6 - Prelight: Post-Processing — новая подпанель пост-обработки vertex colors (Smooth, Contrast, Brightness, Gamma)
#        - Prelight: Fast Bake теперь поддерживает тени (raycast через depsgraph), переключатель Shadows в панели
#        - Export: новая подпанель DFF Flags — отображает флаги геометрии DragonFF (Light, Normals, Pipeline, UV Maps и др.)
# v1.4.5 - Export All: массовый экспорт нескольких групп моделей (Model1_DFF + Model2_DFF и т.д.)
#        - Lightmap Generator: панель снова доступна в интерфейсе
# v1.4.4 - Prelight: Fill Colors - покраска полигонов с пипеткой и системой уровней
#        - Prelight: Scatter Light - рассеивание света с настройками и уровнями
#        - Prelight: убраны лишние заголовки, оставлены только кнопки
#        - Color Attributes: раздельные кнопки создания/удаления Day и Night
#        - Color Attributes: кнопка Day/Night создаёт оба атрибута
#        - Drag-and-Drop: перетаскивание PNG/JPG/TGA из File Browser создаёт материал
#        - INU Tools панель перемещена в Properties > Scene
#        - Удалена пустая вкладка GTA Textures из N-панели
# v1.4.3 - TXD экспорт: исправлена прозрачность DXT3 текстур в игре
#        - TXD экспорт: текстуры с размером не кратным 4 пропускаются с предупреждением
# v1.4.2 - TXD экспорт: добавлен GPU режим через NVIDIA Texture Tools
# v1.4.1 - TXD экспорт: параллельная обработка текстур (до 8x быстрее)
# v1.4.0 - UV Editor: добавлена панель GTA Tools с UV Grid Randomizer и визуализацией сетки
#        - UV Editor: добавлена привязка UV к ближайшей ячейке сетки (Snap to Grid)
#        - UV Editor: добавлен выбор позиции UV в ячейке (9 вариантов выравнивания)
#        - UV Editor: добавлена функция "Связать полигоны" - полигоны с пересекающимися UV перемещаются вместе
#        - GTA Textures: проверка количества материалов (лимит 50)
#        - GTA Textures: загрузка текстуры только для выбранного материала
#        - GTA Textures: автоустановка Specular=0 и подключение Alpha канала
#        - Переведены все описания кнопок на русский язык
# v1.3.0 - Добавлена очистка материалов: объединение дубликатов (.001, .002, etc.)
# v1.2.9 - Добавлена вкладка GTA Textures: автозагрузка текстур по именам материалов
# v1.2.8 - COL экспорт теперь использует версию COL3 (GTA SA) вместо COL1
# v1.2.7 - DFF экспорт: добавлены only_selected=True и export_coll=False для исправления краша
# v1.2.6 - DFF экспорт теперь использует версию GTA SA (v3.6.0.3) вместо GTA 3
# v1.2.5 - Исправление имени модели внутри COL файла (base_name без суффикса COL)
# v1.2.4 - Добавлен прогресс-бар при Export All
# v1.2.3 - Автоустановка типа Collision Object для COL модели перед экспортом
# v1.2.2 - TXD в Export All берёт текстуры из DFF + LOD в один архив
# v1.2.1 - Поиск моделей только среди выделенных объектов
# v1.2.0 - Улучшено определение моделей по суффиксам DFF/LOD/COL (без разделителей)
# v1.1.0 - Добавлен экспорт DFF/COL/LOD/TXD, определение моделей по суффиксам
# v1.0.0 - Начальная версия

import bpy
import os
import time
import tempfile
import numpy as np
from bpy.props import StringProperty, BoolProperty, FloatProperty, FloatVectorProperty, IntProperty, CollectionProperty, EnumProperty, PointerProperty
from bpy.app.handlers import persistent

from .tools.compat import safe_icon, inu_icon
# =============================================================================
# LOCALIZATION SYSTEM
# =============================================================================

def get_locale():
    """Return the locale Blender is actually DISPLAYING the UI in.

    ``bpy.app.translations.locale`` reports the detected/configured locale
    (the system locale, e.g. 'ru_RU', even on a Russian Windows) regardless
    of whether interface translation is on. When the user has "Translate
    Interface" OFF — or English selected — Blender shows its English source
    strings, so we must emit English too, not the Russian source. Gate on
    ``use_translate_interface`` so the addon matches what Blender shows.
    """
    try:
        view = bpy.context.preferences.view
        if not getattr(view, 'use_translate_interface', True):
            return 'en_US'   # Blender shows English source → so do we
        return bpy.app.translations.locale or 'en_US'
    except Exception:
        return 'en_US'


# Map Blender locale prefix → locale/<code>.py filename
_LOCALE_TO_LANG = {
    'ru': None,   # Russian = source language, no translation needed
    'en': 'eng',
    'es': 'spa',
}

# Translation dictionary: Russian -> target language
from .locale import get_translation


def T(text):
    """Translate a Russian source string to the current Blender UI language.

    Code uses Russian strings as canonical keys. For Russian UI — returns
    the input as-is. For other languages — looks up translation in
    ``locale/<lang>.py``. Falls back to English (eng.py) if the current
    locale has no dedicated file.

    Note: when used in ``bl_label`` / ``bl_description`` class attributes,
    ``T()`` runs ONCE at class-definition time and the result is baked in.
    For dynamic translation (Blender re-translates on UI-language switch)
    rely on the ``bpy.app.translations`` registration in
    ``_register_blender_translations()`` and leave the raw Russian source
    in ``bl_label`` directly.
    """
    locale = get_locale()
    prefix = locale[:2].lower() if locale else 'en'
    lang_code = _LOCALE_TO_LANG.get(prefix, 'eng')
    if lang_code is None:
        return text  # Russian source — return verbatim
    tr = get_translation(lang_code)
    if tr:
        result = tr.get(text)
        if result:
            return result
    # Fallback to English if target language file is missing the key
    if lang_code != 'eng':
        eng = get_translation('eng')
        if eng:
            return eng.get(text, text)
    return text


# =============================================================================
# EXTRACTED MODULES
# =============================================================================

from .tools.model_utils import get_model_type
from .data.surface_materials import get_surface_name  # noqa: F401 — re-exported for `from .. import get_surface_name`
# COL Light: import module for mutable globals, classes separately
from .tools import col_light as _col_light_mod
from .tools.col_light import (
    GTATOOLS_OT_preview_col_light, GTATOOLS_OT_bake_col_light,
    GTATOOLS_OT_clear_col_light_mats,
)
# UV Tools: import module for mutable globals, classes separately
from .tools import uv_tools as _uv
from .tools.uv_tools import (
    GTATOOLS_OT_toggle_uv_editor, GTATOOLS_OT_toggle_uv_grid,
    GTATOOLS_OT_randomize_uv_grid, GTATOOLS_OT_snap_uv_to_grid,
    GTATOOLS_OT_uv_fit_grid_scale, GTATOOLS_OT_uv_texel_density,
    GTATOOLS_OT_set_uv_align, GTATOOLS_PT_uv_tools_panel,
    GTATOOLS_OT_uv_anim_insert_key, GTATOOLS_OT_uv_anim_clear_keys,
    GTATOOLS_PT_uv_anim_panel,
)
from .tools.bitmaps_manager import (
    GTATOOLS_OT_bitmaps_scan, GTATOOLS_OT_bitmaps_resolve,
    GTATOOLS_OT_bitmaps_copy, GTATOOLS_OT_bitmaps_find_dupes,
    GTATOOLS_OT_bitmaps_find_unused, GTATOOLS_OT_bitmaps_remove_unused,
    GTATOOLS_MT_textures_menu, GTATOOLS_MT_materials_menu,
    GTATOOLS_PT_bitmaps_panel,
)
from .tools.vc_layers import (
    GTATOOLS_VCLayerItem,
    GTATOOLS_OT_vcl_add, GTATOOLS_OT_vcl_remove, GTATOOLS_OT_vcl_move,
    GTATOOLS_OT_vcl_promote,
    GTATOOLS_OT_vcl_set_active_attr,
    GTATOOLS_OT_vcl_show_composite, GTATOOLS_OT_vcl_refresh_composite,
    GTATOOLS_OT_vcl_apply_multi, GTATOOLS_OT_vcl_recolor_selected,
    GTATOOLS_UL_vc_layers,
    vc_layers_register_load_handler, vc_layers_unregister_handlers,
    _on_active_layer_change as _vc_on_active_layer_change,
    _on_live_preview_toggle as _vc_on_live_preview_toggle,
)
# Phase 4: all panels + UIList classes moved to ui/panels.py.
# Imported AFTER def T because panels.py does `from .. import T` at
# top-level (T is referenced in class bodies for bl_label etc., evaluated
# at class-definition time so it can't be deferred).
from .ui.library_panel import GTATOOLS_PT_library_panel
from .ui.panels import (  # noqa: E501
    GTATOOLS_PT_material_panel,
    GTATOOLS_UL_txd_export_plan,
    GTATOOLS_UL_img_files,
    GTATOOLS_UL_ipl_sync_list,
    GTATOOLS_PT_main_panel,
    GTATOOLS_PT_ide_ipl_panel,
    GTATOOLS_PT_ide_ipl_import,
    GTATOOLS_PT_ide_ipl_export,
    GTATOOLS_PT_ide_ipl_map,
    GTATOOLS_PT_export_panel,
    GTATOOLS_PT_validate_scene,
    GTATOOLS_MT_create_2dfx,
    GTATOOLS_MT_radar_generate,
    GTATOOLS_MT_path_traffic,
    GTATOOLS_PT_check_panel,
    GTATOOLS_UL_lint_issues,
    GTATOOLS_PT_file_scanner,
    GTATOOLS_UL_map_lint_issues,
    GTATOOLS_PT_texture_browser,
    GTATOOLS_UL_texture_browser,
    GTATOOLS_PT_vehicle_panel,
    GTATOOLS_PT_frame_hierarchy,
    GTATOOLS_PT_frame_hierarchy_anim,
    GTATOOLS_UL_bake_layers,
    GTATOOLS_PT_uv_root,
    GTATOOLS_PT_bake_panel,
    GTATOOLS_PT_bake_advanced,
    GTATOOLS_PT_2dfx_panel,
    GTATOOLS_PT_2dfx_settings,
    GTATOOLS_PT_object_ide_ipl_panel,
    GTATOOLS_PT_object_inu_tools,
    GTATOOLS_PT_inu_tools_panel,
    GTATOOLS_PT_id_manager_panel,
    GTATOOLS_PT_light_master,
    GTATOOLS_PT_prelight_panel,
    GTATOOLS_PT_bake_settings_subpanel,
    GTATOOLS_PT_scatter_color_subpanel,
    GTATOOLS_PT_foliage_subpanel,
    GTATOOLS_PT_vc_postprocess_panel,
    GTATOOLS_PT_itera_panel,
    GTATOOLS_PT_prelight_col_panel,
    GTATOOLS_PT_lightmap_panel,
    GTATOOLS_PT_water_panel,
    GTATOOLS_PT_timecyc_panel,
    GTATOOLS_PT_timecyc_edit,
    GTATOOLS_PT_timecyc_preview,
    GTATOOLS_PT_zon_panel,
    GTATOOLS_UL_grass,
    GTATOOLS_PT_grass_panel,
    GTATOOLS_PT_anim_panel,
    GTATOOLS_PT_radar_panel,
    GTATOOLS_PT_paths_panel,
    GTATOOLS_PT_footer_panel,
)
from .ops.zon_ops import (
    GTATOOLS_OT_import_zon,
    GTATOOLS_OT_export_zon,
    GTATOOLS_OT_add_zon_zone,
    GTATOOLS_OT_zon_copy_lines,
)
from .ops.plants_ops import (
    GTATOOLS_OT_grass_import,
    GTATOOLS_OT_grass_export,
    GTATOOLS_OT_grass_add,
    GTATOOLS_OT_grass_remove,
    GTATOOLS_OT_grass_duplicate,
    GTATOOLS_OT_grass_apply_surface,
    GTATOOLS_OT_grass_preview,
    GTATOOLS_OT_grass_preview_clear,
    GTATOOLS_OT_grass_generate_geometry,
    GTATOOLS_OT_grass_geometry_clear,
)
# Material context-menu hook — register/unregister append/remove it.
from .ui.panels import _draw_sort_materials_menu
from .ops.bake_ops import (
    GTATOOLS_OT_bake_run,
    GTATOOLS_OT_bake_select_layer,
    GTATOOLS_OT_bake_layer_add,
    GTATOOLS_OT_bake_layer_remove,
    GTATOOLS_OT_bake_layer_move,
    GTATOOLS_OT_bake_preview,
    GTATOOLS_OT_bake_flatten,
    GTATOOLS_OT_bake_save_map,
    GTATOOLS_OT_bake_lightmap_apply,
    GTATOOLS_OT_bake_lightmap_postprocess,
    GTATOOLS_OT_bake_show_over_base,
)
from .ops.alpha_tools import (
    GTATOOLS_OT_alpha_scan,
    GTATOOLS_OT_alpha_apply_all,
    GTATOOLS_OT_alpha_select_objects,
    GTATOOLS_UL_alpha_mats,
)
from .scene_settings import (
    INUSceneSettings,
    INUTimecycWeather,
    INUTimecycProps,
    INUValidateIssue,
    INUBakeLayer,
    _bake_layer_index_update,
    INULightCutRing,
    GTATOOLS_BinaryIplEntry,
    GTATOOLS_TextIplEntry,
    GTATOOLS_ImgFileEntry,
    GTATOOLS_AlphaMatEntry,
    GTATOOLS_LintIssueItem,
    GTATOOLS_PathItem,
    GTATOOLS_TextureBrowserItem,
    INUGrassEntry,
)
from .ops.ifp_import import (
    GTATOOLS_OT_ifp_batch_import,
    GTATOOLS_OT_refresh_station_markers,
    GTATOOLS_OT_path_node_flag,
)
from .ops.cst_import import GTATOOLS_OT_drop_cst
from .ops.paintjob_ops import GTATOOLS_OT_validate_paintjobs
from .ops.onboarding_ops import (
    GTATOOLS_OT_open_docs,
    GTATOOLS_OT_open_issues,
    GTATOOLS_OT_open_release,
    GTATOOLS_OT_whats_new,
)
from .ops.validate_scene import (
    GTATOOLS_OT_validate_run,
    GTATOOLS_OT_validate_clear,
    GTATOOLS_OT_validate_goto,
    GTATOOLS_OT_validate_fix_quaternions,
    GTATOOLS_OT_validate_fix_suffix,
)
from .ops.frame_hierarchy import (
    GTATOOLS_OT_frame_select,
    GTATOOLS_OT_frame_rename,
    GTATOOLS_OT_frame_set_parent,
    GTATOOLS_OT_frame_unparent,
    GTATOOLS_OT_frame_reparent,
    GTATOOLS_OT_frame_validate,
    GTATOOLS_OT_frame_mirror_lr,
)
from .ops.animobj_ops import (
    GTATOOLS_OT_animobj_validate,
    GTATOOLS_OT_animobj_export,
    GTATOOLS_OT_animobj_parent_to_pivot,
    GTATOOLS_OT_animobj_parent_to_root,
    GTATOOLS_OT_animobj_add_pivot,
    INUAnimObjEmptyProps,
    INUAnimObjRigSettings,
)
from .ops.weight_paint_ops import (
    GTATOOLS_OT_weight_merge_start,
    GTATOOLS_OT_weight_merge_apply,
    GTATOOLS_OT_weight_merge_cancel,
)
from .ops.graph_keys_ops import (
    GTATOOLS_OT_thin_keyframes,
    GTATOOLS_PT_graph_thin_keys,
)
from .tools.profiles import (
    GTATOOLS_OT_profile_save,
    GTATOOLS_OT_profile_delete,
    GTATOOLS_OT_profile_pick_panel,
    GTATOOLS_OT_profile_toggle_panel,
    GTATOOLS_OT_profile_edit,
)
from .tools.vehicle_scale import (
    GTATOOLS_OT_vehicle_scale,
    GTATOOLS_OT_vehicle_add_damage_variant,
    GTATOOLS_OT_vehicle_show_damage,
    GTATOOLS_OT_vehicle_pair_report,
)
from .tools.map_export import (
    GTATOOLS_OT_map_export,
)
from .tools.gta_material_panel import (
    GTATOOLS_OT_material_preset,
    GTATOOLS_OT_copy_material_settings,
)

addon_keymaps = []

# =============================================================================
# PROPERTY GROUPS
# =============================================================================

# ── Particle curve keyframe PropertyGroup (used by B1 curve editor) ── #
class INUParticleKeyframe(bpy.types.PropertyGroup):
    """A single FX_KEYFLOAT_DATA entry (time, val) for the curve editor buffer."""
    time: FloatProperty(
        name="Time",
        default=0.0, min=0.0, max=1.0, precision=4,
    )
    val: FloatProperty(
        name="Value",
        default=0.0, precision=4,
    )


# ── Particle effect EnumProperty — dynamic items from effects.fxp ── #
# Module-level cache: EnumProperty items callbacks MUST return the same
# Python objects across calls, otherwise Blender shows garbled strings
# (strings get GC'd). We keep the last returned list alive here.
_particle_enum_items_cache = [('', '<not loaded>', '')]
_particle_enum_cache_key = None  # (path, mtime)


def _particle_effect_enum_items(self, context):
    """Items callback for INUObjectProps.particle_effect_2dfx."""
    global _particle_enum_items_cache, _particle_enum_cache_key
    try:
        game_root = bpy.path.abspath(
            getattr(context.scene.inu_settings, 'gtatools_game_root', '') or ''
        )
        if not game_root or not os.path.isdir(game_root):
            _particle_enum_items_cache = [('', T('<Game Root не задан>'), '')]
            _particle_enum_cache_key = None
            return _particle_enum_items_cache

        path = os.path.join(game_root, 'models', 'effects.fxp')
        if not os.path.isfile(path):
            _particle_enum_items_cache = [('', T('<effects.fxp не найден>'), '')]
            _particle_enum_cache_key = None
            return _particle_enum_items_cache

        mtime = os.path.getmtime(path)
        key = (path, mtime)
        if key == _particle_enum_cache_key:
            return _particle_enum_items_cache

        from .core import fxp as _fxp
        fxf = _fxp.load_cached(path)
        items = [(s.name, s.name, "") for s in fxf.systems]
        if not items:
            items = [('', T('<нет эффектов>'), '')]
        _particle_enum_items_cache = items
        _particle_enum_cache_key = key
        return _particle_enum_items_cache
    except Exception as ex:
        _particle_enum_items_cache = [('', f'<ошибка: {ex}>', '')]
        _particle_enum_cache_key = None
        return _particle_enum_items_cache


def _particle_effect_get(self):
    obj = self.id_data
    name = obj.get('2dfx_effect_name', '') or ''
    for i, item in enumerate(_particle_enum_items_cache):
        if item[0] == name:
            return i
    return 0


def _particle_effect_set(self, value):
    obj = self.id_data
    items = _particle_enum_items_cache
    if 0 <= value < len(items):
        name = items[value][0]
        if name:
            obj['2dfx_effect_name'] = name
            # Reset to the first emitter whenever the effect changes
            obj.inu.particle_emitter_index = 0
            try:
                _populate_particle_props_from_fxp(obj, name, 0)
            except Exception as e:
                print(f"[2DFX Particle] populate failed: {e}")
            try:
                from .ops.fx_preview import update_particle_preview
                update_particle_preview(obj)
            except Exception as e:
                print(f"[2DFX Particle] preview update failed: {e}")


def _sample_particle_from_emitter(em) -> dict:
    """Sample the editable particle parameters from a FXEmitter.

    Returns a dict with exactly the fields that our editor exposes, in the
    same shape/units as obj.inu.particle_*. Used both to populate from FXP
    and to detect user edits on save (so we only write changed fields).
    """
    tex_raw = (em.base_get('TEXTURE') or '').strip()
    tex = "" if tex_raw == 'NULL' else tex_raw
    try:
        src_blend = int(em.base_get('SRCBLENDID') or 4)
    except (TypeError, ValueError):
        src_blend = 4
    try:
        dst_blend = int(em.base_get('DSTBLENDID') or 5)
    except (TypeError, ValueError):
        dst_blend = 5

    def _curve(info_type, field, default=0.0, t=0.0):
        info = em.info(info_type)
        if not info:
            return default
        c = info.curves.get(field)
        if not c:
            return default
        return c.sample(t)

    def _rgba(t):
        return (
            max(min(_curve('COLOUR', 'RED', 255.0, t) / 255.0, 1.0), 0.0),
            max(min(_curve('COLOUR', 'GREEN', 255.0, t) / 255.0, 1.0), 0.0),
            max(min(_curve('COLOUR', 'BLUE', 255.0, t) / 255.0, 1.0), 0.0),
            max(min(_curve('COLOUR', 'ALPHA', 255.0, t) / 255.0, 1.0), 0.0),
        )

    # Detect a middle COLOUR keyframe: any COLOUR curve with > 2 keys.
    # Use the ALPHA curve's middle keyframe time as the canonical mid_time
    # (alpha is usually where fade-in/fade-out lives).
    colour = em.info('COLOUR')
    mid_enabled = False
    mid_time = 0.5
    if colour is not None:
        for name in ('ALPHA', 'RED', 'GREEN', 'BLUE'):
            c = colour.curves.get(name)
            if c is not None and len(c.keys) >= 3:
                mid_enabled = True
                if name == 'ALPHA':
                    mid_idx = len(c.keys) // 2
                    mid_time = max(0.01, min(c.keys[mid_idx].time, 0.99))
                    break

    return {
        'texture': tex,
        'src_blend': src_blend,
        'dst_blend': dst_blend,
        'color_start': _rgba(0.0),
        'color_end': _rgba(1.0),
        'color_mid_enabled': mid_enabled,
        'color_mid': _rgba(mid_time),
        'color_mid_time': mid_time,
        'size_start': max(_curve('SIZE', 'SIZEX', 0.3, 0.0), 0.0),
        'size_end': max(_curve('SIZE', 'SIZEX', 0.5, 1.0), 0.0),
        'life': max(_curve('EMLIFE', 'LIFE', 1.0, 0.0), 0.0),
        'life_bias': max(_curve('EMLIFE', 'BIAS', 0.0, 0.0), 0.0),
        'rate': max(_curve('EMRATE', 'RATE', 10.0, 0.0), 0.0),
        'speed': max(_curve('EMSPEED', 'SPEED', 1.0, 0.0), 0.0),
        'speed_bias': max(_curve('EMSPEED', 'BIAS', 0.0, 0.0), 0.0),
        'direction': (
            _curve('EMDIR', 'DIRX', 0.0, 0.0),
            _curve('EMDIR', 'DIRY', 0.0, 0.0),
            _curve('EMDIR', 'DIRZ', 1.0, 0.0),
        ),
        # Extended emission
        'angle_min': _curve('EMANGLE', 'MIN', 0.0, 0.0),
        'angle_max': _curve('EMANGLE', 'MAX', 0.0, 0.0),
        # EMSIZE as half-extent: half the min→max range per axis.
        # This loses any offset from origin but keeps the box size,
        # which is all that Box UI needs. Save always writes symmetric.
        'volume': (
            max(
                abs(_curve('EMSIZE', 'SIZEMAXX', 0.0, 0.0)),
                abs(_curve('EMSIZE', 'SIZEMINX', 0.0, 0.0)),
            ),
            max(
                abs(_curve('EMSIZE', 'SIZEMAXY', 0.0, 0.0)),
                abs(_curve('EMSIZE', 'SIZEMINY', 0.0, 0.0)),
            ),
            max(
                abs(_curve('EMSIZE', 'SIZEMAXZ', 0.0, 0.0)),
                abs(_curve('EMSIZE', 'SIZEMINZ', 0.0, 0.0)),
            ),
        ),
        'offset': (
            _curve('EMPOS', 'X', 0.0, 0.0),
            _curve('EMPOS', 'Y', 0.0, 0.0),
            _curve('EMPOS', 'Z', 0.0, 0.0),
        ),
        'rotation_min': _curve('EMROTATION', 'ANGLEMIN', 0.0, 0.0),
        'rotation_max': _curve('EMROTATION', 'ANGLEMAX', 0.0, 0.0),
        # Physics
        'force': (
            _curve('FORCE', 'FORCEX', 0.0, 0.0),
            _curve('FORCE', 'FORCEY', 0.0, 0.0),
            _curve('FORCE', 'FORCEZ', 0.0, 0.0),
        ),
        'friction': _curve('FRICTION', 'FRICTION', 0.0, 0.0),
        'wind': _curve('WIND', 'WINDFACTOR', 0.0, 0.0),
        'noise': _curve('NOISE', 'NOISE', 0.0, 0.0),
        'jitter': _curve('JITTER', 'JITTERFACTOR', 0.0, 0.0),
        'rotspeed_min': _curve('ROTSPEED', 'MINCW', 0.0, 0.0),
        'rotspeed_max': _curve('ROTSPEED', 'MAXCW', 0.0, 0.0),
        'ground_bounce': _curve('GROUNDCOLLIDE', 'BOUNCE', 0.0, 0.0),
        'ground_speedmult': _curve('GROUNDCOLLIDE', 'SPEEDMULT', 1.0, 0.0),
    }


def _get_effect_emitter_count(effect_name: str) -> int:
    """Return number of emitters in a named system, or 0 on any failure."""
    try:
        game_root = bpy.path.abspath(
            getattr(bpy.context.scene.inu_settings, 'gtatools_game_root', '') or ''
        )
        if not game_root:
            return 0
        fxp_path = os.path.join(game_root, 'models', 'effects.fxp')
        if not os.path.isfile(fxp_path):
            return 0
        from .core import fxp as _fxp
        fxf = _fxp.load_cached(fxp_path)
        system = fxf.find(effect_name)
        return len(system.emitters) if system else 0
    except Exception:
        return 0


def _populate_particle_props_from_fxp(obj, effect_name: str, emitter_index: int = 0) -> bool:
    """Copy the Nth emitter's parameters from effects.fxp onto obj.inu."""
    game_root = bpy.path.abspath(
        getattr(bpy.context.scene.inu_settings, 'gtatools_game_root', '') or ''
    )
    if not game_root:
        return False
    fxp_path = os.path.join(game_root, 'models', 'effects.fxp')
    if not os.path.isfile(fxp_path):
        return False

    from .core import fxp as _fxp
    fxf = _fxp.load_cached(fxp_path)
    system = fxf.find(effect_name)
    if system is None or not system.emitters:
        return False

    idx = max(0, min(emitter_index, len(system.emitters) - 1))
    vals = _sample_particle_from_emitter(system.emitters[idx])
    inu = obj.inu
    inu.particle_texture = vals['texture']
    inu.particle_src_blend = vals['src_blend']
    inu.particle_dst_blend = vals['dst_blend']
    inu.particle_color_start = vals['color_start']
    inu.particle_color_end = vals['color_end']
    inu.particle_color_mid_enabled = vals['color_mid_enabled']
    inu.particle_color_mid = vals['color_mid']
    inu.particle_color_mid_time = vals['color_mid_time']
    inu.particle_size_start = vals['size_start']
    inu.particle_size_end = vals['size_end']
    inu.particle_life = vals['life']
    inu.particle_life_bias = vals['life_bias']
    inu.particle_rate = vals['rate']
    inu.particle_speed = vals['speed']
    inu.particle_speed_bias = vals['speed_bias']
    inu.particle_direction = vals['direction']

    # Extended emission
    inu.particle_angle_min = vals['angle_min']
    inu.particle_angle_max = vals['angle_max']
    inu.particle_volume = vals['volume']
    inu.particle_offset = vals['offset']
    inu.particle_rotation_min = vals['rotation_min']
    inu.particle_rotation_max = vals['rotation_max']

    # Physics
    inu.particle_force = vals['force']
    inu.particle_friction = vals['friction']
    inu.particle_wind = vals['wind']
    inu.particle_noise = vals['noise']
    inu.particle_jitter = vals['jitter']
    inu.particle_rotspeed_min = vals['rotspeed_min']
    inu.particle_rotspeed_max = vals['rotspeed_max']
    inu.particle_ground_bounce = vals['ground_bounce']
    inu.particle_ground_speedmult = vals['ground_speedmult']

    # System-level settings from FX_SYSTEM_DATA header
    try:
        inu.particle_sys_length = float(system.header_get('LENGTH') or 1.0)
    except ValueError:
        pass
    try:
        inu.particle_sys_playmode = int(system.header_get('PLAYMODE') or 2)
    except ValueError:
        pass
    try:
        inu.particle_sys_culldist = float(system.header_get('CULLDIST') or 50.0)
    except ValueError:
        pass

    return True


_inu_flag_propagating = False


def _make_inu_flag_update(attr_name):
    """Propagate a DFF flag toggle from the active object to all other selected mesh objects.

    Only fires when the user edits the flag on the active object's panel — guards against
    recursion and against runs from import/export where properties are set programmatically
    on non-active objects.

    Также после ручного тогла авто-сохраняет текущий набор флагов как
    глобальный default для активного пайплайна (в user_data JSON) —
    чтобы при создании нового объекта или открытии другого .blend
    флаги в этом пайплайне применились автоматически.
    """
    def _update(self, context):
        global _inu_flag_propagating
        if _inu_flag_propagating:
            return
        active = context.active_object
        if not active or self.id_data != active:
            return
        selected = [o for o in context.selected_objects
                    if o.type == 'MESH' and o != active and hasattr(o, 'inu')]
        value = getattr(self, attr_name)
        if selected:
            _inu_flag_propagating = True
            try:
                for obj in selected:
                    if getattr(obj.inu, attr_name) != value:
                        setattr(obj.inu, attr_name, value)
            finally:
                _inu_flag_propagating = False
        # Global default snapshot (cross-.blend persistence)
        try:
            settings = getattr(context.scene, 'inu_settings', None)
            pipe = settings.gtatools_export_pipeline if settings else None
            if pipe in _PIPE_TO_SNAP:
                snap = {p: bool(getattr(self, p)) for p in _INU_FLAG_PROPS}
                _save_global_pipe_defaults(pipe, snap)
        except Exception:
            pass
    return _update


# ── Per-pipeline DFF-flag memory ────────────────────────────────────
# Each mesh object remembers its own ON/OFF combination of DFF flags
# для каждого из 4 трэкаемых пайплайнов. Когда юзер переключает
# scene.inu_settings.gtatools_export_pipeline, мы:
#   1) пакуем текущие live-флаги в JSON-snap для СТАРОГО пайплайна;
#   2) распаковываем snap НОВОГО пайплайна (если был) обратно
#      в live-флаги, иначе оставляем как есть.
# Snap'ы хранятся как hidden StringProperty на obj.inu, по одному
# на пайплайн. Список пайплайнов и список флагов — единая правда
# здесь, чтобы UI/export/restore не разъезжались.
_INU_FLAG_PROPS = (
    "export_normals", "light", "modulate_color", "set_material_alpha",
    "light_beam_asi", "export_binsplit", "uv_map1", "uv_map2",
    "day_cols", "night_cols",
)

_PIPE_TO_SNAP = {
    '0x53F2009A': 'flags_snap_vehicle',
    '0x53F20098': 'flags_snap_dn',
    '0x53F2009C': 'flags_snap_building',
    'PED':        'flags_snap_ped',
}

# Флаги, которые принудительно гасятся при выборе пайплайна, поверх
# восстановленного snapshot. D/N building светится через prelit vcols —
# dynamic Light не нужен и провоцирует мерцание при повороте камеры.
_PIPE_FORCE_OFF = {
    '0x53F20098': ('light',),  # D/N Building: dynamic light off
}

# ── Global per-pipeline flag defaults (cross-.blend persistence) ────
# Лежат в user_data/dff_pipeline_flag_defaults.json. Файл версионирован
# по bl_info['version'] — при апдейте аддона версия меняется, файл
# игнорируется → дефолты сбрасываются к code-defaults.
_PIPE_DEFAULTS_FILENAME = 'dff_pipeline_flag_defaults.json'


def _get_pipe_defaults_path():
    try:
        from .tools.user_data import get_user_data_dir
        return os.path.join(get_user_data_dir(), _PIPE_DEFAULTS_FILENAME)
    except Exception:
        return None


def _addon_version_key():
    return list(bl_info.get('version', (0, 0, 0)))


def _load_global_pipe_defaults():
    """Return ``{pipeline_id: {flag_name: bool}}`` or ``{}`` on miss /
    version mismatch."""
    import json as _json
    path = _get_pipe_defaults_path()
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = _json.load(f)
        if data.get('addon_version') != _addon_version_key():
            return {}
        pipes = data.get('pipelines', {})
        return pipes if isinstance(pipes, dict) else {}
    except Exception:
        return {}


def _save_global_pipe_defaults(pipe_id, snap):
    """Merge one pipeline's snapshot into the global defaults JSON file."""
    import json as _json
    path = _get_pipe_defaults_path()
    if not path:
        return
    data = {}
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = _json.load(f)
    except Exception:
        data = {}
    if not isinstance(data, dict) or data.get('addon_version') != _addon_version_key():
        data = {'addon_version': _addon_version_key(), 'pipelines': {}}
    data.setdefault('pipelines', {})[pipe_id] = snap
    try:
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)
    except Exception:
        pass


def _inu_pipeline_changed(self, context):
    """Scene-settings update callback for ``gtatools_export_pipeline``.

    ``self`` is the INUSceneSettings group. ``self.inu_prev_pipeline_internal``
    tracks the value we last saw; on transition we snapshot live flags
    into the previous pipeline's slot and restore the new pipeline's
    slot back onto the live properties for every mesh object in the
    scene that has ``obj.inu``.

    Только пайплайны из ``_PIPE_TO_SNAP`` участвуют в save/restore —
    NONE / Custom не имеют своего слота, чтобы не плодить пустые
    snapshots для дефолтного состояния."""
    global _inu_flag_propagating
    new_pipe = self.gtatools_export_pipeline
    old_pipe = self.inu_prev_pipeline_internal
    if old_pipe == new_pipe:
        return
    # update first so re-entrant draw/update calls see the new tag
    self.inu_prev_pipeline_internal = new_pipe

    import json as _json
    old_field = _PIPE_TO_SNAP.get(old_pipe)
    new_field = _PIPE_TO_SNAP.get(new_pipe)
    if old_field is None and new_field is None:
        return  # NONE→Custom or similar — nothing to snapshot

    scn = getattr(context, 'scene', None)
    if scn is None:
        return

    # Global cross-.blend defaults — fallback when per-object snap empty
    global_defaults = _load_global_pipe_defaults().get(new_pipe) if new_field else None
    if not isinstance(global_defaults, dict):
        global_defaults = None

    # Suppress _make_inu_flag_update's selection-propagation while we
    # mass-write flags: restoring snap on object X must not bleed into
    # selected siblings.
    prev_guard = _inu_flag_propagating
    _inu_flag_propagating = True
    try:
        for obj in scn.objects:
            if obj.type != 'MESH':
                continue
            inu = getattr(obj, 'inu', None)
            if inu is None:
                continue
            if old_field is not None:
                snap = {p: bool(getattr(inu, p)) for p in _INU_FLAG_PROPS}
                setattr(inu, old_field, _json.dumps(snap))
            if new_field is not None:
                raw = getattr(inu, new_field, "")
                snap = None
                if raw:
                    try:
                        snap = _json.loads(raw)
                    except (ValueError, TypeError):
                        snap = None
                if not isinstance(snap, dict):
                    snap = global_defaults  # may be None — leaves live as-is
                if isinstance(snap, dict):
                    for p in _INU_FLAG_PROPS:
                        if p in snap:
                            try:
                                setattr(inu, p, bool(snap[p]))
                            except Exception:
                                pass
            # Force-off несовместимых флагов поверх снапшота
            for p in _PIPE_FORCE_OFF.get(new_pipe, ()):
                try:
                    setattr(inu, p, False)
                except Exception:
                    pass
    finally:
        _inu_flag_propagating = prev_guard


def _lod_dist_sync_update(self, context):
    """Синхронизировать LOD Dist с LOD-партнёром: меняя LOD Distance на основной
    модели, у которой задан lod_object, ставим то же значение партнёру, чтобы
    его IDE-строка (берущая свою LOD Dist) сходилась. Защита от рекурсии — не
    трогаем, если значение уже совпадает."""
    partner = getattr(self, 'lod_object', None)
    if partner is None:
        return
    pinu = getattr(partner, 'inu', None)
    if pinu is None:
        return
    try:
        if abs(float(pinu.lod_draw_distance) - float(self.lod_draw_distance)) > 1e-4:
            pinu.lod_draw_distance = self.lod_draw_distance
    except Exception:
        pass


class INUObjectProps(bpy.types.PropertyGroup):
    """INU_tools object export properties (replaces DragonFF obj.dff)."""

    type : EnumProperty(
        items=[
            ('OBJ', 'Object', 'Object will be exported as a mesh or a dummy'),
            ('COL', 'Collision Object', 'Object is a collision object'),
            ('SHA', 'Shadow Object', 'Object is a shadow object'),
            ('2DFX', '2DFX Effect', 'Object is a 2DFX effect (light, particle, etc.)'),
            ('NON', "Don't export", 'Object will NOT be exported'),
        ],
        name="Type",
        default='OBJ',
    )

    effect_2dfx : EnumProperty(
        items=[
            ('LIGHT', 'Свет',
             "Точечный источник света / корона / неон.\n"
             "Уличные фонари, фары машин, светящиеся окна зданий, "
             "неоновые вывески. В игре рисуется как 2D-корона с альфа-"
             "блендингом, видна на расстоянии. Поддерживает цвет, "
             "затухание, мерцание, типы (street/lamp/police), "
             "вкл/выкл по времени суток."),
            ('PARTICLE', 'Частица',
             "Точка привязки эмиттера частиц из models/effects.fxp.\n"
             "Дым из труб, всплески воды у причалов, искры на "
             "электрических столбах, огонь в бочках, пар из "
             "вентиляции. Сама система частиц выбирается по имени "
             "(prt_smoke_huge, water_splash, prt_fire и т.д.) из "
             "effects.fxp — там 82 системы."),
            ('PED_ATTRACTOR', 'Ped Attractor',
             "Точка интереса для NPC.\n"
             "Пешеходы подходят к этой точке и проигрывают "
             "анимацию: банкомат (ATM), скамейка, продавец у ларька, "
             "граффити, точка «осмотреться». Имеет тип поведения "
             "(SCRIPTED/SEAT/STOP/TRIGGER_SCRIPT/LOOK_AT/SCRIPTED_2/"
             "PARK/STEP), направление куда поворачиваться, "
             "опционально model_id определённого ped'а."),
            ('SUN_GLARE', 'Блик солнца',
             "Точка отражения солнца на поверхности.\n"
             "Яркий блик когда камера смотрит в сторону солнца через "
             "эту точку. Используется на крышах автомобилей, стёклах "
             "окон, металлических деталях. Рисуется как корона с "
             "альфа-блендингом, размер и яркость зависят от угла "
             "между направлением точки и солнцем."),
            ('ENTER_EXIT', 'Вход/Выход (интерьер)',
             "Маркер входа/выхода в интерьер (тип 6).\n"
             "Пара маркеров: вход на позиции объекта и выход на "
             "exit-позиции. Хранит угол поворота маркеров, радиус, "
             "номер интерьера, имя интерьера, время вкл/выкл. Раньше "
             "жил в IPL (секция enex), в SA — прямо в DFF."),
            ('ROAD_SIGN', 'Дорожный знак (текст)',
             "Текстовый знак на меше (тип 7).\n"
             "До 4 строк текста, рисуемых движком поверх геометрии "
             "(указатели улиц). Хранит размер, поворот и флаги "
             "(число строк, макс. символов, цвет: белый/чёрный/"
             "серый/красный)."),
            ('ESCALATOR', 'Эскалатор',
             "Эскалатор (тип 10).\n"
             "Задаёт три точки — низ, верх и конец — и направление "
             "(вверх/вниз). Движок двигает педов по этой траектории. "
             "Используется в аэропортах и торговых центрах SA."),
            ('RAW_2DFX', 'Raw (сохранённый)',
             "Нередактируемый 2DFX-эффект, сохранённый байт-в-байт "
             "при импорте (типы 8 trigger / 9 cover и прочие). Не "
             "меняй вручную — служит для точного round-trip."),
        ],
        name="2DFX Effect Type",
        default='LIGHT',
    )

    particle_effect_2dfx : EnumProperty(
        name="Particle Effect",
        description=T("Имя эффекта из effects.fxp"),
        items=_particle_effect_enum_items,
        get=_particle_effect_get,
        set=_particle_effect_set,
    )

    particle_emitter_index : IntProperty(
        name="Emitter Index",
        description=T("Индекс редактируемого эмиттера (для систем с несколькими)"),
        default=0, min=0,
    )

    # ── Curve editor buffer (B1) ── #
    particle_curve_name : StringProperty(
        name="Curve",
        description=T("Редактируемая кривая в формате INFO.FIELD (например SIZE.SIZEX)"),
        default="",
    )
    particle_curve_keys : CollectionProperty(type=INUParticleKeyframe)
    particle_curve_key_index : IntProperty(default=0)

    # ── Particle editable per-instance properties ── #
    # These get populated from effects.fxp when the user picks an effect
    # from the dropdown. All reads for the billboard preview come from
    # these fields (not directly from the FXP file), so edits here are
    # instantly reflected and stored per-object.
    def _update_particle(self, context):
        obj = self.id_data
        if obj and obj.type == 'EMPTY' and self.type == '2DFX' and self.effect_2dfx == 'PARTICLE':
            try:
                from .ops.fx_preview import update_particle_preview
                update_particle_preview(obj)
            except Exception as e:
                print(f"[2DFX Particle] update error: {e}")

    particle_texture : StringProperty(
        name="Texture",
        description=T("Имя спрайта из particle.txd"),
        default="",
        update=_update_particle,
    )
    particle_src_blend : IntProperty(
        name="SRC Blend",
        description="D3D9 source blend factor (4=SRCALPHA, 2=ONE, ...)",
        default=4, min=0, max=17,
        update=_update_particle,
    )
    particle_dst_blend : IntProperty(
        name="DST Blend",
        description="D3D9 dest blend factor (5=INVSRCALPHA, 2=ONE for additive)",
        default=5, min=0, max=17,
        update=_update_particle,
    )
    particle_color_start : FloatVectorProperty(
        name="Color (start)",
        subtype='COLOR',
        size=4,
        min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
        update=_update_particle,
    )
    particle_color_end : FloatVectorProperty(
        name="Color (end)",
        subtype='COLOR',
        size=4,
        min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0, 0.0),
        update=_update_particle,
    )
    particle_color_mid_enabled : BoolProperty(
        name="Use middle colour",
        description=T("Добавить промежуточный ключ для плавного fade-in/fade-out"),
        default=False,
        update=_update_particle,
    )
    particle_color_mid : FloatVectorProperty(
        name="Color (mid)",
        subtype='COLOR',
        size=4,
        min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
        update=_update_particle,
    )
    particle_color_mid_time : FloatProperty(
        name="Mid time",
        description=T("Позиция промежуточного ключа по времени жизни (0..1)"),
        default=0.5, min=0.01, max=0.99, precision=3,
        update=_update_particle,
    )
    particle_size_start : FloatProperty(
        name="Size (start)",
        description=T("Размер частицы в начале жизни"),
        default=0.3, min=0.0, soft_max=10.0, precision=3,
        update=_update_particle,
    )
    particle_size_end : FloatProperty(
        name="Size (end)",
        description=T("Размер частицы в конце жизни"),
        default=0.5, min=0.0, soft_max=10.0, precision=3,
        update=_update_particle,
    )
    particle_life : FloatProperty(
        name="Life",
        description=T("Длительность жизни частицы в секундах"),
        default=1.0, min=0.0, soft_max=30.0, precision=3,
        update=_update_particle,
    )
    particle_rate : FloatProperty(
        name="Rate",
        description=T("Количество частиц в секунду"),
        default=10.0, min=0.0, soft_max=1000.0,
        update=_update_particle,
    )
    particle_speed : FloatProperty(
        name="Speed",
        description=T("Начальная скорость частицы"),
        default=1.0, min=0.0, soft_max=100.0, precision=3,
        update=_update_particle,
    )
    particle_direction : FloatVectorProperty(
        name="Direction",
        description=T("Направление эмиссии"),
        size=3,
        default=(0.0, 0.0, 1.0),
        update=_update_particle,
    )

    # ── System-level settings (FX_SYSTEM_DATA header) ── #
    particle_sys_length : FloatProperty(
        name="System Length",
        description=T("LENGTH — длительность цикла системы в секундах"),
        default=1.0, min=0.0, soft_max=100.0, precision=3,
        update=_update_particle,
    )
    particle_sys_playmode : IntProperty(
        name="Play Mode",
        description=T("PLAYMODE — режим проигрывания (0-3)"),
        default=2, min=0, max=3,
        update=_update_particle,
    )
    particle_sys_culldist : FloatProperty(
        name="Cull Distance",
        description=T("CULLDIST — расстояние отсечения эффекта в игре"),
        default=50.0, min=0.0, soft_max=500.0, precision=1,
        update=_update_particle,
    )

    # ── Extended emission (EMANGLE / EMSIZE / EMPOS / EMROTATION / biases) ── #
    particle_angle_min : FloatProperty(
        name="Angle Min",
        description=T("EMANGLE MIN — минимальный угол конуса эмиссии"),
        default=0.0, min=0.0, soft_max=180.0, precision=2,
        update=_update_particle,
    )
    particle_angle_max : FloatProperty(
        name="Angle Max",
        description=T("EMANGLE MAX — максимальный угол конуса эмиссии"),
        default=0.0, min=0.0, soft_max=180.0, precision=2,
        update=_update_particle,
    )
    # Box as half-extents — symmetric around the emitter. On save this
    # becomes SIZEMIN=-box, SIZEMAX=+box per axis in the FXP EMSIZE block.
    particle_volume : FloatVectorProperty(
        name="Box",
        description=T("EMSIZE половина размера бокса эмиссии (centered)"),
        size=3,
        default=(0.0, 0.0, 0.0),
        min=0.0, precision=3,
        update=_update_particle,
    )
    # Legacy storage — kept for back-compat with older blend files, not in UI
    particle_volume_radius : FloatProperty(
        name="Volume Radius (legacy)",
        default=0.0, min=0.0, precision=3,
    )
    particle_volume_min : FloatVectorProperty(
        name="Volume Min (legacy)",
        size=3, default=(0.0, 0.0, 0.0), precision=3,
    )
    particle_offset : FloatVectorProperty(
        name="Offset",
        description=T("EMPOS X/Y/Z — смещение точки спавна"),
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=3,
        update=_update_particle,
    )
    particle_rotation_min : FloatProperty(
        name="Rotation Min",
        description=T("EMROTATION ANGLEMIN — мин начальный поворот спрайта"),
        default=0.0, soft_min=-360.0, soft_max=360.0,
        update=_update_particle,
    )
    particle_rotation_max : FloatProperty(
        name="Rotation Max",
        description=T("EMROTATION ANGLEMAX — макс начальный поворот спрайта"),
        default=0.0, soft_min=-360.0, soft_max=360.0,
        update=_update_particle,
    )
    particle_life_bias : FloatProperty(
        name="Life Bias",
        description=T("EMLIFE BIAS — случайный разброс длительности жизни"),
        default=0.0, min=0.0, soft_max=10.0, precision=3,
        update=_update_particle,
    )
    particle_speed_bias : FloatProperty(
        name="Speed Bias",
        description=T("EMSPEED BIAS — случайный разброс начальной скорости"),
        default=0.0, min=0.0, soft_max=10.0, precision=3,
        update=_update_particle,
    )

    # ── Physics (FORCE / FRICTION / WIND / NOISE / JITTER / ROTSPEED / GROUNDCOLLIDE) ── #
    particle_force : FloatVectorProperty(
        name="Force",
        description=T("FORCE X/Y/Z — постоянное ускорение (например -9.8 по Z = гравитация)"),
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=3,
        update=_update_particle,
    )
    particle_friction : FloatProperty(
        name="Friction",
        description=T("FRICTION — сопротивление воздуха"),
        default=0.0, min=0.0, soft_max=10.0, precision=3,
        update=_update_particle,
    )
    particle_wind : FloatProperty(
        name="Wind",
        description=T("WIND WINDFACTOR — восприимчивость к ветру игры"),
        default=0.0, min=0.0, soft_max=10.0, precision=3,
        update=_update_particle,
    )
    particle_noise : FloatProperty(
        name="Noise",
        description=T("NOISE — сглаженное случайное движение"),
        default=0.0, min=0.0, soft_max=10.0, precision=3,
        update=_update_particle,
    )
    particle_jitter : FloatProperty(
        name="Jitter",
        description=T("JITTER JITTERFACTOR — резкий случайный дёрг"),
        default=0.0, min=0.0, soft_max=10.0, precision=3,
        update=_update_particle,
    )
    particle_rotspeed_min : FloatProperty(
        name="RotSpeed Min",
        description=T("ROTSPEED MINCW — мин скорость вращения спрайта"),
        default=0.0, soft_min=-360.0, soft_max=360.0,
        update=_update_particle,
    )
    particle_rotspeed_max : FloatProperty(
        name="RotSpeed Max",
        description=T("ROTSPEED MAXCW — макс скорость вращения спрайта"),
        default=0.0, soft_min=-360.0, soft_max=360.0,
        update=_update_particle,
    )
    particle_ground_bounce : FloatProperty(
        name="Ground Bounce",
        description=T("GROUNDCOLLIDE BOUNCE — сила отскока при ударе о землю"),
        default=0.0, min=0.0, soft_max=2.0, precision=3,
        update=_update_particle,
    )
    particle_ground_speedmult : FloatProperty(
        name="Ground SpeedMult",
        description=T("GROUNDCOLLIDE SPEEDMULT — потеря скорости при ударе"),
        default=1.0, min=0.0, soft_max=2.0, precision=3,
        update=_update_particle,
    )

    def _update_2dfx_preview(self, context):
        obj = self.id_data  # owner Object
        if obj and obj.type == 'EMPTY' and self.type == '2DFX' and self.effect_2dfx == 'LIGHT':
            try:
                from .ops.fx_preview import sync_preview_from_props
                sync_preview_from_props(obj)
            except Exception as e:
                print(f"[2DFX] Preview update error: {e}")

    def _update_escalator_preview(self, context):
        """Live-refresh the escalator wire the instant a point / direction
        changes — no button, no poll lag (these are real PropertyGroup
        fields, so editing one fires this callback immediately)."""
        obj = self.id_data
        if obj and obj.type == 'EMPTY' and self.type == '2DFX' and self.effect_2dfx == 'ESCALATOR':
            try:
                from .ops.fx_preview import sync_escalator_preview
                sync_escalator_preview(obj)
            except Exception as e:
                print(f"[2DFX] Escalator preview update error: {e}")

    esc_bottom : FloatVectorProperty(
        name=T("Низ"), size=3, subtype='XYZ', unit='LENGTH',
        description=T("Нижняя точка эскалатора (модельное пространство)"),
        update=_update_escalator_preview,
    )
    esc_top : FloatVectorProperty(
        name=T("Верх"), size=3, subtype='XYZ', unit='LENGTH',
        description=T("Верхняя точка эскалатора"),
        update=_update_escalator_preview,
    )
    esc_end : FloatVectorProperty(
        name=T("Конец"), size=3, subtype='XYZ', unit='LENGTH',
        description=T("Точка схода (Z как у верха при движении вверх, "
                      "как у низа — при движении вниз)"),
        update=_update_escalator_preview,
    )
    esc_direction : EnumProperty(
        items=[('1', T("Вверх"), T("Едет вверх")),
               ('0', T("Вниз"), T("Едет вниз"))],
        name=T("Направление"), default='1',
        update=_update_escalator_preview,
    )

    # ── Road sign (type 7) ──
    def _update_road_sign_preview(self, context):
        """Live-rebuild the sign preview (plane + text) on any edit.

        Only rebuilds when a preview already exists — otherwise setting the
        fields during import / create (before the Empty is linked to its
        collection) would spawn stray previews; the explicit create call at
        the end of those flows builds the first one."""
        obj = self.id_data
        if obj and obj.type == 'EMPTY' and self.type == '2DFX' and self.effect_2dfx == 'ROAD_SIGN':
            try:
                from .ops.fx_preview import (request_road_sign_rebuild,
                                             _has_preview_children)
                # Defer the remove+recreate to a timer — doing bpy.data object
                # churn from inside this update= callback is unsafe.
                if _has_preview_children(obj):
                    request_road_sign_rebuild(obj)
            except Exception as e:
                print(f"[2DFX] Road sign preview update error: {e}")

    sign_text0 : StringProperty(name=T("Строка 1"), maxlen=16,
                                update=_update_road_sign_preview)
    sign_text1 : StringProperty(name=T("Строка 2"), maxlen=16,
                                update=_update_road_sign_preview)
    sign_text2 : StringProperty(name=T("Строка 3"), maxlen=16,
                                update=_update_road_sign_preview)
    sign_text3 : StringProperty(name=T("Строка 4"), maxlen=16,
                                update=_update_road_sign_preview)
    sign_size : FloatVectorProperty(
        name=T("Размер"), size=2, default=(2.0, 1.0), min=0.0,
        description=T("Ширина и высота области текста на меше"),
        update=_update_road_sign_preview,
    )
    sign_rotation : FloatVectorProperty(
        name=T("Поворот"), size=3, subtype='EULER',
        default=(1.5707963, 0.0, 0.0),   # stand upright by default
        description=T("Ориентация плоскости знака"),
        update=_update_road_sign_preview,
    )
    sign_lines : IntProperty(
        name=T("Строк"), min=1, max=4, default=1,
        description=T("Сколько строк текста используется"),
        update=_update_road_sign_preview,
    )
    sign_maxchars : EnumProperty(
        items=[('16', '16', ''), ('2', '2', ''), ('4', '4', ''), ('8', '8', '')],
        name=T("Символов/строку"), default='16',
        update=_update_road_sign_preview,
    )
    sign_color : EnumProperty(
        items=[('WHITE', T("Белый"), ''), ('BLACK', T("Чёрный"), ''),
               ('GREY', T("Серый"), ''), ('RED', T("Красный"), '')],
        name=T("Цвет"), default='WHITE',
        update=_update_road_sign_preview,
    )

    # ── Enter/Exit (type 6) ──
    def _update_enterexit_preview(self, context):
        """Live-sync the enter-marker ring/arrow the instant a geometry field
        (radius / enter angle) changes. In-place, no-op without a preview."""
        obj = self.id_data
        if obj and obj.type == 'EMPTY' and self.type == '2DFX' and self.effect_2dfx == 'ENTER_EXIT':
            try:
                from .ops.fx_preview import sync_enterexit_preview
                sync_enterexit_preview(obj)
            except Exception as e:
                print(f"[2DFX] Enter/Exit preview update error: {e}")

    ee_enter_angle : FloatProperty(
        name=T("Угол входа"), default=0.0,
        description=T("Направление, куда повёрнут игрок при входе (градусы)"),
        update=_update_enterexit_preview,
    )
    ee_exit_angle : FloatProperty(
        name=T("Угол выхода"), default=0.0,
        description=T("Направление игрока при выходе из интерьера (градусы)"),
    )
    ee_radius_x : FloatProperty(
        name=T("Радиус X"), default=1.0, min=0.0,
        update=_update_enterexit_preview,
    )
    ee_radius_y : FloatProperty(
        name=T("Радиус Y"), default=1.0, min=0.0,
        update=_update_enterexit_preview,
    )
    ee_exit_loc : FloatVectorProperty(
        name=T("Позиция выхода"), size=3, subtype='XYZ',
        description=T("Куда телепортирует игрока (координаты интерьера)"),
    )
    ee_interior : IntProperty(
        name=T("Интерьер #"), min=0, max=65535, default=0,
        description=T("Номер интерьерного мира (0 = обычный мир)"),
    )
    ee_interior_name : StringProperty(name=T("Имя интерьера"), maxlen=8)
    ee_time_on : IntProperty(name=T("Время вкл"), min=0, max=24, default=0)
    ee_time_off : IntProperty(name=T("Время выкл"), min=0, max=24, default=24)
    ee_sky_color : IntProperty(name=T("Цвет неба"), min=0, max=255, default=0)
    ee_flags1 : IntProperty(name=T("Флаги 1"), min=0, max=255, default=0)
    ee_flags2 : IntProperty(name=T("Флаги 2"), min=0, max=255, default=0)
    ee_unknown : IntProperty(name=T("Unknown"), min=0, max=255, default=0)

    color_2dfx : FloatVectorProperty(
        name="2DFX Color",
        subtype='COLOR',
        size=4,
        min=0.0, max=1.0,
        default=(1.0, 1.0, 0.784, 1.0),
        description=T("Цвет короны и света"),
        update=_update_2dfx_preview,
    )

    corona_size_2dfx : FloatProperty(
        name="Corona Size",
        description=T("Размер короны — сияющего спрайта, который всегда "
                      "повёрнут к камере (видимый «огонёк» лампы). "
                      "0 — корона не видна. Это и есть сам видимый свет"),
        default=1.0, min=0.0, soft_max=10.0, precision=3,
        update=_update_2dfx_preview,
    )

    shadow_size_2dfx : FloatProperty(
        name="Shadow Size",
        description=T("Размер светового пятна (тени) на земле под лампой "
                      "и яркость заливающего света вокруг. "
                      "ЧТОБЫ ОСТАВИТЬ ТОЛЬКО КОРОНУ без пятна и подсветки — "
                      "поставь 0 (корона при этом сохранится, ей управляет "
                      "«Размер короны»)"),
        default=8.0, min=0.0, soft_max=50.0, precision=3,
        update=_update_2dfx_preview,
    )

    preset_2dfx : EnumProperty(
        items=[
            ('DEFAULT', 'Default', 'Default light settings'),
            ('ONALLDAY', 'OnAllDay', 'Always visible light'),
            ('LAMP_POST', 'Lamp Post', 'Standard lamp post'),
            ('LAMP_POST_COAST', 'Lamp Post Coast', 'Coastal lamp post (warm)'),
            ('BB_PICKUP', 'BB Pickup', 'Red pickup marker'),
            ('FLASHING_MAV1', 'Flashing (Maverick1)', 'Red blinking helicopter light'),
            ('FLASHING_MAV2', 'Flashing (Maverick2)', 'Green blinking helicopter light'),
            ('FLASHING_TUG', 'Flashing (Tug)', 'Orange blinking tug light'),
            ('TRAIN_CROSSING', 'Train Crossing', 'Red blinking train crossing'),
            ('TRAFFIC', 'Traffic', 'Traffic light'),
        ],
        name="2DFX Preset",
        default='DEFAULT',
    )

    def _update_2dfx_texture(self, context):
        """Recreate preview when texture changes."""
        obj = self.id_data
        if obj and obj.type == 'EMPTY' and self.type == '2DFX' and self.effect_2dfx == 'LIGHT':
            try:
                from .ops.fx_preview import remove_preview_children, create_light_preview
                remove_preview_children(obj)
                create_light_preview(obj)
            except Exception as e:
                print(f"[2DFX] Texture update error: {e}")

    corona_tex_2dfx : EnumProperty(
        items=[
            ('coronastar', 'coronastar',
             T("Классическая звезда-блик — стандартная корона уличных "
               "фонарей. Универсальный выбор")),
            ('coronamoon', 'coronamoon',
             T("Мягкое круглое свечение без лучей (как луна)")),
            ('coronaringb', 'coronaringb',
             T("Светящееся кольцо")),
            ('coronareflect', 'coronareflect',
             T("Размытое гало/отражение — рассеянное мягкое свечение")),
            ('coronaheadlightline', 'coronaheadlightline',
             T("Горизонтальная линия-блик (как от фар)")),
            ('headlight', 'headlight',
             T("Корона фары")),
            ('headlight1', 'headlight1',
             T("Корона фары, вариант 2")),
            ('lockon', 'lockon',
             T("Метка захвата цели (прицел)")),
            ('lockonFire', 'lockonFire',
             T("Метка захвата цели, готов к выстрелу")),
            ('lunar', 'lunar',
             T("Лунное гало — крупное мягкое свечение")),
            ('roadsignfont', 'roadsignfont',
             T("Текстура шрифта дорожных знаков (спец. использование)")),
            ('particleskid', 'particleskid',
             T("След от заноса (спец. использование)")),
            ('finishFlag', 'finishFlag',
             T("Финишный флаг (спец. использование)")),
            ('handman', 'handman',
             T("Спрайт-указатель (спец. использование)")),
            ('seabd32', 'seabd32',
             T("Мелкая частица морской пены (спец. использование)")),
            ('shad_exp', 'shad_exp',
             T("Мягкое круглое пятно (обычно для тени, не для короны)")),
            ('shad_car', 'shad_car',
             T("Силуэт машины (обычно для тени)")),
            ('shad_bike', 'shad_bike',
             T("Силуэт мотоцикла (обычно для тени)")),
            ('shad_heli', 'shad_heli',
             T("Силуэт вертолёта (обычно для тени)")),
            ('shad_ped', 'shad_ped',
             T("Силуэт пешехода (обычно для тени)")),
            ('shad_rcbaron', 'shad_rcbaron',
             T("Силуэт RC-самолёта (обычно для тени)")),
            ('lamp_shad_64', 'lamp_shad_64',
             T("Световой круг фонаря (обычно для тени)")),
            ('bloodpool_64', 'bloodpool_64',
             T("Лужа крови (обычно как декаль)")),
            ('target256', 'target256',
             T("Большая метка-мишень")),
            ('white', 'white',
             T("Сплошной белый круг — чистое свечение без рисунка")),
            ('cloud1', 'cloud1',
             T("Текстура облака (спец. использование)")),
            ('cloudhigh', 'cloudhigh',
             T("Высотное облако (спец. использование)")),
            ('cloudmasked', 'cloudmasked',
             T("Облако с маской (спец. использование)")),
            ('carfx1', 'carfx1',
             T("Эффект машины (спец. использование)")),
            ('wincrack_32', 'wincrack_32',
             T("Трещина на стекле (спец. использование)")),
            ('waterclear256', 'waterclear256',
             T("Текстура чистой воды (спец. использование)")),
            ('waterwake', 'waterwake',
             T("След на воде (спец. использование)")),
            ('txgrassbig0', 'txgrassbig0',
             T("Текстура травы (спец. использование)")),
            ('txgrassbig1', 'txgrassbig1',
             T("Текстура травы, вариант 2 (спец. использование)")),
        ],
        name="Corona Texture",
        default='coronastar',
        update=_update_2dfx_texture,
    )

    shadow_tex_2dfx : EnumProperty(
        items=[
            ('shad_exp', 'shad_exp',
             T("Мягкое круглое пятно — универсальный «световой круг» под "
               "лампой. Стандартный выбор для фонарей")),
            ('shad_car', 'shad_car',
             T("Тень-силуэт легковой машины")),
            ('shad_bike', 'shad_bike',
             T("Тень-силуэт мотоцикла")),
            ('shad_heli', 'shad_heli',
             T("Тень-силуэт вертолёта")),
            ('shad_ped', 'shad_ped',
             T("Тень-силуэт пешехода")),
            ('shad_rcbaron', 'shad_rcbaron',
             T("Тень-силуэт RC-самолёта")),
            ('lamp_shad_64', 'lamp_shad_64',
             T("Световой круг под уличным фонарём (64×64), чуть резче "
               "shad_exp")),
            ('bloodpool_64', 'bloodpool_64',
             T("Лужа крови (декаль на земле)")),
            ('coronastar', 'coronastar',
             T("Использовать звезду короны как световое пятно на земле")),
            ('coronamoon', 'coronamoon',
             T("Мягкое круглое свечение как пятно на земле")),
            ('coronaringb', 'coronaringb',
             T("Кольцо как пятно на земле")),
            ('coronareflect', 'coronareflect',
             T("Размытое гало/отражение как пятно на земле")),
            ('white', 'white',
             T("Сплошной белый круг — чистое световое пятно без рисунка")),
        ],
        name="Shadow Texture",
        default='shad_exp',
    )

    show_mode_2dfx : EnumProperty(
        items=[
            ('0', '0 DEFAULT',
             T("Обычный режим: лампа горит постоянно (днём/ночью — по "
               "флагам видимости). Подходит для большинства уличных ламп")),
            ('1', '1 RANDOM_FLASHING',
             T("Случайное мерцание вкл/выкл со случайным интервалом — "
               "неисправная/моргающая лампа, аварийки")),
            ('2', '2 FLASH_RAIN',
             T("Мерцает ТОЛЬКО во время дождя, в сухую погоду горит ровно")),
            ('3', '3 ONLY_RAIN',
             T("Видна только во время дождя, в сухую погоду полностью "
               "выключена")),
            ('4', '4 NO_RAIN',
             T("Скрывается во время дождя, видна только в сухую погоду")),
            ('5', '5 FLASH_5',
             T("Быстрое стробоскопическое мигание (~5 Гц) — маяки, "
               "спецсигналы, проблесковые огни")),
        ],
        name="Show Mode",
        default='0',
    )

    flare_type_2dfx : EnumProperty(
        items=[
            ('0', '0 None',
             T("Без линзовых бликов. Обычный выбор для уличных ламп")),
            ('1', '1 Type 1',
             T("Линзовый блик (lens flare) — лучи/гало как от яркого "
               "источника при взгляде на него. Стиль 1")),
            ('2', '2 Type 2',
             T("Линзовый блик, стиль 2 (другой набор лучей/колец)")),
            ('3', '3 Type 3',
             T("Линзовый блик, стиль 3")),
        ],
        name="Flare Type",
        default='0',
    )

    pipeline : EnumProperty(
        items=[
            ('NONE', 'None',
             T("Без указания pipeline — использовать стандартный рендер RenderWare. Подходит для простых объектов, которым не нужны специальные эффекты движка")),
            ('0x53F2009A', 'Vehicle',
             T("Pipeline кузова машины (RSPIPE_PC_CustomCarEnvMap). Добавляет env-map отражения неба/облаков/улицы. Используется совместно с текстурами vehicleenv128 + vehiclespecdot64 на материале")),
            ('0x53F20098', 'Day/Night',
             T("Pipeline здания с day/night vertex colors (RSPIPE_PC_CustomBuildingDN). Движок плавно смешивает дневной и ночной слои vertex colors по игровому времени. Требует ДВА Color Attribute слоя (Day + Night) на меше. Mesh-флаги Day/Night здесь не нужны — переход делает pipeline через VC")),
            ('0x53F2009C', 'Building',
             T("Простой pipeline здания (RSPIPE_PC_CustomBuilding). Статическое освещение через один слой vertex colors. Работает быстрее чем Day/Night, но нет смены по времени суток")),
            ('CUSTOM', 'Custom Pipeline',
             T("Указать произвольное значение pipeline ID через поле Custom Pipeline")),
        ],
        name="Pipeline",
        description=T("Рендер-пайплайн движка"),
    )
    custom_pipeline : StringProperty(name="Custom Pipeline")

    export_normals : BoolProperty(
        default=False,
        description=T("Экспорт нормалей вершин в DFF.\n\n"
                      "ВКЛЮЧАТЬ: для скиннингованных объектов (peds, vehicles)\n"
                      "и любых моделей у которых динамическое освещение должно\n"
                      "корректно реагировать на смену освещения сцены.\n\n"
                      "ВЫКЛЮЧАТЬ (по умолчанию для map-объектов): нормали\n"
                      "удваивают размер vertex stream'а; статичные здания\n"
                      "обычно полностью освещены через vertex prelight, и\n"
                      "движок нормали не использует. Файл получается меньше"),
        update=_make_inu_flag_update("export_normals"),
    )
    # ВНИМАНИЕ: галки 'export_binsplit' НЕТ в UI (ни в N-панели, ни в
    # I/E-флоатере) — и это намеренно. Bin Mesh PLG нужен ЛЮБОЙ рендеримой
    # геометрии GTA: без него модель невидима в MEd/вьюерах и не рисуется
    # частью движков. Единственный «плюс» отключения — экономия пары КБ на
    # модели, которая заведомо не идёт в игру, — для GTA-аддона смысла не
    # имеет, зато молча выдавал сломанный DFF (ночные цвета есть, bin mesh
    # нет). Свойство оставлено в коде (default=True) для round-trip и для
    # редких пайплайнов, которые осознанно выставят export_binsplit=False
    # через пресет/API (напр. bin mesh потом генерит внешний tristripifier).
    # Значение по-прежнему доезжает до DffGeometry.write_bin_mesh в экспорте.
    export_binsplit : BoolProperty(
        default=True,
        description=T("Экспорт chunk'а Bin Mesh PLG в DFF.\n\n"
                      "Содержит индексы триангуляции в том виде в котором\n"
                      "движок ожидает их у себя в RpAtomic. Без него:\n"
                      "• MEd / DFF Viewer не показывает геометрию\n"
                      "• некоторые версии движка не рендерят меш\n\n"
                      "Выключать имеет смысл только при микро-оптимизации\n"
                      "размера DFF когда модель не идёт в игру"),
        update=_make_inu_flag_update("export_binsplit"),
    )

    uv_map1 : BoolProperty(
        default=True,
        description=T("Экспорт первой UV-карты — основной набор текстурных\n"
                      "координат. Должен быть включён почти всегда —\n"
                      "выключи только если меш специально без UV"),
        update=_make_inu_flag_update("uv_map1"))
    uv_map2 : BoolProperty(
        default=True,
        description=T("Экспорт второй UV-карты — используется для lightmap'ов\n"
                      "и dual-pass материалов. Если меш без второй UV-карты,\n"
                      "флаг безопасно оставить включённым (DFF не получит\n"
                      "лишний chunk)"),
        update=_make_inu_flag_update("uv_map2"))
    day_cols : BoolProperty(
        default=True,
        description=T("Экспорт дневных vertex colors (атрибут «Day»).\n"
                      "Это ванильный prelight который игра умножает на\n"
                      "ambient_obj в runtime. Выключи только если хочешь\n"
                      "DFF без vertex colors (редкий случай)"),
        update=_make_inu_flag_update("day_cols"))
    night_cols : BoolProperty(
        default=True,
        description=T("Экспорт ночных vertex colors (атрибут «Night»,\n"
                      "RpExtraVertColors chunk). Игра берёт их в ночное\n"
                      "время через timecyc-blend. Если у меша нет «Night»\n"
                      "слоя — chunk не пишется автоматически"),
        update=_make_inu_flag_update("night_cols"))

    light : BoolProperty(
        default=True,
        description=T("Флаг rpGEOMETRYLIGHT — геометрия принимает\n"
                      "динамическое освещение от движка (sun + ambient).\n\n"
                      "Без флага: меш рендерится как unlit, виден только\n"
                      "vertex prelight × matCol. Используется для\n"
                      "self-illuminated объектов (вывески, окна с\n"
                      "запечённым свечением)"),
        update=_make_inu_flag_update("light"))
    modulate_color : BoolProperty(
        default=True,
        description=T("Флаг rpGEOMETRYMODULATEMATERIALCOLOR — vertex prelight\n"
                      "умножается на material color и ambient_obj в runtime.\n\n"
                      "ВЫКЛЮЧИ если хочешь чтобы prelight использовался «как\n"
                      "есть» без модуляции (нужно для запечённого ночного\n"
                      "освещения, эффектов flicker от prelight). Стандарт\n"
                      "у ванильных зданий — включён"),
        update=_make_inu_flag_update("modulate_color"))
    set_material_alpha : BoolProperty(
        default=False,
        description=T("Автоматически ставить material.alpha = 254 при наличии\n"
                      "vertex alpha < 255 хоть на одной вершине меша.\n\n"
                      "ВКЛЮЧАТЬ: для прозрачных мешей (стёкла, дым, листва)\n"
                      "если хочешь чтобы движок воспринял геометрию как\n"
                      "alpha-blended объект и сортировал её правильно.\n\n"
                      "ВЫКЛЮЧАТЬ (по умолчанию): материал остаётся opaque,\n"
                      "vertex alpha не задаёт прозрачность всего объекта.\n"
                      "Полезно когда vertex alpha используется для других\n"
                      "целей (vcol fade, light beam masking)"),
        update=_make_inu_flag_update("set_material_alpha"))
    light_beam_asi : BoolProperty(default=False, description="", update=_make_inu_flag_update("light_beam_asi"))

    # ── Per-pipeline flag snapshots (hidden) ──
    # JSON dict {prop_name: bool, ...} запоминающий какие DFF-флаги
    # были ON/OFF в последний раз когда этот пайплайн был активным.
    # Записывается/читается _inu_pipeline_changed при смене пайплайна.
    flags_snap_vehicle  : StringProperty(default="", options={'HIDDEN'})
    flags_snap_dn       : StringProperty(default="", options={'HIDDEN'})
    flags_snap_building : StringProperty(default="", options={'HIDDEN'})
    flags_snap_ped      : StringProperty(default="", options={'HIDDEN'})

    # ── IDE / IPL properties ──
    model_id : IntProperty(
        name="Model ID",
        default=0,
        min=0,
        description=T("ID модели в GTA SA (IDE/IPL)"),
    )
    map_key : StringProperty(
        name="Map Key",
        default="",
        description=T("Метка размещения при импорте карты: «имя модели|x|y|z». "
                      "По ней «Без дублей» узнаёт, что этот кусок карты уже "
                      "стоит в сцене"),
    )
    txd_name : StringProperty(
        name="TXD Name",
        default="",
        description=T("Имя словаря текстур (IDE). По умолчанию = имя модели"),
    )
    col_name : StringProperty(
        name="COL Library",
        default="",
        description=T("Имя .col-библиотеки в которой хранится коллизия модели. Заполняется автоматически при Map Import (= имя исходного .col файла). При Map Export DFF группируются в одну .col-библиотеку по совпадающему col_name. Пусто → fallback на txd_name, затем на имя модели"),
    )
    lod_object : PointerProperty(
        type=bpy.types.Object,
        name="LOD partner",
        description=T("LOD-модель этой DFF — заполняется автоматически при Map Import из IPL lod_index. При Map Export пересчитывается в lod_index = позицию LOD-инстанса в выходном IPL. Пусто = модель не имеет LOD"),
    )
    real_interior : IntProperty(
        name="Real Interior (FLA)",
        default=0,
        min=0,
        description=T("Fastman92 Limit Adjuster: 12-я колонка `realInterior` в IPL inst. Обычная SA читает только 11 колонок — это поле игнорируется без FLA. Пусто (0) = не использовать. Включить запись 12-й колонки можно в Map Export → FLA Extended IPL"),
    )
    draw_distance : FloatProperty(
        name="Draw Distance",
        default=299.0,
        min=0.0,
        description=T("Дальность прорисовки объекта (IDE)"),
    )
    lod_draw_distance : FloatProperty(
        name="LOD Distance",
        default=999.0,
        min=0.0,
        description=T("Дальность прорисовки LOD модели (IDE)"),
        update=_lod_dist_sync_update,
    )
    ide_flags : IntProperty(
        name="IDE Flags",
        default=0,
        min=0,
        description=T("Флаги объекта в IDE"),
    )

    # Breakable object extension (chunk 0x253F2FD)
    breakable : BoolProperty(
        name="Breakable Object",
        description=T("Пометить геометрию как разрушаемую (пишет чанк 0x253F2FD в DFF)"),
        default=False,
    )
    breakable_force : FloatProperty(
        name="Break Force",
        description=T("Сила, нужная чтобы сломать объект (умолчание 1.0)"),
        default=1.0, min=0.0,
    )
    breakable_offset : FloatVectorProperty(
        name="Break Offset",
        description=T("Смещение точки приложения силы разлома (по умолчанию 0,0,0)"),
        size=3, default=(0.0, 0.0, 0.0), subtype='TRANSLATION',
    )
    breakable_alloc_auto : BoolProperty(
        name="Auto Buffers",
        description=T("Авто-размер буферов сломанной копии по текущей геометрии. "
                      "Выключи только если движку не хватает места под осколки"),
        default=True,
    )
    breakable_verts_alloc : IntProperty(
        name="Verts", description=T("Резерв вершин под сломанную копию"),
        default=100, min=1,
    )
    breakable_faces_alloc : IntProperty(
        name="Faces", description=T("Резерв граней под сломанную копию"),
        default=200, min=1,
    )
    breakable_mats_alloc : IntProperty(
        name="Materials", description=T("Резерв материалов под сломанную копию"),
        default=1, min=1,
    )
    breakable_uvs_alloc : IntProperty(
        name="UVs", description=T("Резерв UV под сломанную копию"),
        default=100, min=1,
    )

    # IDE flag checkboxes with auto-sync to ide_flags.
    #
    # Bit values are verified against gtamods.com/wiki/Item_Definition.
    # Each property carries a "supported games" hint in its description
    # so the UI panel can filter the list per ``scene.gtatools_game``
    # (see ``IDE_FLAG_GAMES`` mapping in ui/panels.py).
    def _update_ide_flag(self, context):
        _FLAG_BITS = [
            # Stable across all 3 games:
            ('flag_draw_last', 4), ('flag_additive', 8),
            ('flag_no_zbuffer', 64),
            # III + VC (deprecated in SA):
            ('flag_do_not_fade', 2),
            ('flag_ignore_lighting', 32),
            # III only:
            ('flag_is_subway', 16),
            # VC + SA (not III):
            ('flag_is_road', 1),
            ('flag_no_shadows', 128),
            ('flag_glass_1', 512), ('flag_glass_2', 1024),
            # VC only:
            ('flag_ignore_draw_dist', 256),
            # SA only:
            ('flag_garage_door', 2048), ('flag_damagable', 4096),
            ('flag_is_tree', 8192), ('flag_is_palm', 16384),
            ('flag_no_flyer_col', 32768), ('flag_is_tag', 1048576),
            ('flag_no_backface', 2097152), ('flag_breakable', 4194304),
        ]
        val = 0
        for prop, bit in _FLAG_BITS:
            if getattr(self, prop, False):
                val |= bit
        self['ide_flags'] = val

    # Stable across III/VC/SA — show in every game's UI.
    flag_draw_last : BoolProperty(name=T("Рисовать последним (DRAW_LAST)"), description=T("Прозрачный, рисовать последним (4) · III/VC/SA"), default=False, update=_update_ide_flag)
    flag_additive : BoolProperty(name=T("Аддитивный (ADDITIVE)"), description=T("Аддитивный блендинг (8) · III/VC/SA"), default=False, update=_update_ide_flag)
    flag_no_zbuffer : BoolProperty(name=T("Без Z-буфера (NO_ZBUFFER_WRITE)"), description=T("Не писать в Z-буфер (64) · III/VC/SA"), default=False, update=_update_ide_flag)

    # III + VC (SA ignores these bits — checkbox hidden in SA scene).
    flag_do_not_fade : BoolProperty(name=T("Без затухания (DO_NOT_FADE)"), description=T("Без затухания на дистанции (2) · III/VC"), default=False, update=_update_ide_flag)
    flag_ignore_lighting : BoolProperty(name=T("Динамический свет (IGNORE_LIGHTING)"), description=T("Динамическое освещение вместо статического (32) · III/VC"), default=False, update=_update_ide_flag)

    # III only.
    flag_is_subway : BoolProperty(name=T("Туннель метро (IS_SUBWAY)"), description=T("Туннель, видим только в cull-зоне (16) · III only"), default=False, update=_update_ide_flag)

    # VC + SA (III lacks 0x1 IS_ROAD semantics — bit 0 was «ignored»).
    flag_is_road : BoolProperty(name=T("Дорога (IS_ROAD)"), description=T("Дорога, wet reflections (1) · VC/SA"), default=False, update=_update_ide_flag)
    flag_no_shadows : BoolProperty(name=T("Без теней (NO_SHADOWS)"), description=T("Не получать тени (128) · VC/SA"), default=False, update=_update_ide_flag)
    flag_glass_1 : BoolProperty(name=T("Стекло разбиваемое (GLASS_TYPE_1)"), description=T("Стекло разбиваемое (512) · VC/SA"), default=False, update=_update_ide_flag)
    flag_glass_2 : BoolProperty(name=T("Стекло с трещинами (GLASS_TYPE_2)"), description=T("Стекло с трещинами (1024) · VC/SA"), default=False, update=_update_ide_flag)

    # VC only.
    flag_ignore_draw_dist : BoolProperty(name=T("Игнор. дистанции (IGNORE_DRAW_DIST)"), description=T("Игнорировать draw distance (256) · VC only — typical для LOD-моделей"), default=False, update=_update_ide_flag)

    # SA only.
    flag_garage_door : BoolProperty(name=T("Дверь гаража (GARAGE_DOOR)"), description=T("Дверь гаража (2048) · SA only"), default=False, update=_update_ide_flag)
    flag_damagable : BoolProperty(name=T("Повреждаемый (DAMAGABLE)"), description=T("Разрушаемый ok/dam (4096) · SA only"), default=False, update=_update_ide_flag)
    flag_is_tree : BoolProperty(name=T("Дерево (IS_TREE)"), description=T("Дерево, качается на ветру (8192) · SA only"), default=False, update=_update_ide_flag)
    flag_is_palm : BoolProperty(name=T("Пальма (IS_PALM)"), description=T("Пальма, качается на ветру (16384) · SA only"), default=False, update=_update_ide_flag)
    flag_no_flyer_col : BoolProperty(name=T("Без колл. с авиа (NO_FLYER_COL)"), description=T("Нет коллизии с летающим (32768) · SA only"), default=False, update=_update_ide_flag)
    flag_is_tag : BoolProperty(name=T("Граффити-тег (IS_TAG)"), description=T("Граффити тег (1048576) · SA only"), default=False, update=_update_ide_flag)
    flag_no_backface : BoolProperty(name=T("Двусторонний (NO_BACKFACE_CULL)"), description=T("Рисовать обе стороны (2097152) · SA only"), default=False, update=_update_ide_flag)
    flag_breakable : BoolProperty(name=T("Разрушаемая статуя (BREAKABLE_STATUE)"), description=T("Разрушаемая статуя (4194304) · SA only"), default=False, update=_update_ide_flag)

    # Source game for the loaded IDE flags — set by ide_import when
    # known (defaults to '' = unknown). Read by export to decide
    # whether translate_flags() needs to run.
    ide_flags_source_game : StringProperty(name="IDE Flags Source",
        default="",
        description=T("Игра-источник IDE flags (III/VC/SA). Используется при экспорте для перевода битов между играми"))
    interior_id : IntProperty(
        name="Interior ID",
        default=0,
        min=0,
        description=T("ID интерьера для IPL (0 = экстерьер)"),
    )
    lod_index : IntProperty(
        name="LOD Index",
        default=-1,
        description=T("Индекс LOD модели в IPL (-1 = нет LOD)"),
    )

    # ── IPL link tracking ──
    # Per-object persistent identity for IPL upsert.  When an object is
    # first added to an IPL we mint a UUID and stash the exported
    # transform (last_pos / last_rot).  On the next ``Add to IPL`` we
    # compare the current world transform with ``ipl_last_pos``: if it
    # drifted, the existing IPL line is overwritten instead of a new
    # row being appended (avoids duplicate placements when iterating).
    # The sidecar (``<blend>/.inu_cache/ipl_links.json``) holds the
    # uuid → ``line_idx`` map plus a hash of the IPL file for external-
    # edit detection.  Fields are kept compact (no PointerProperty) so
    # an entire rig of duplicates costs ~80 bytes / obj.
    ipl_uuid : StringProperty(
        name="IPL UUID",
        description=T("Стабильный ID этой расстановки в IPL. Пустой = объект ещё не экспортировался в IPL. Авто-генерируется при первом «Add to IPL»"),
        default="",
    )
    ipl_target_file : StringProperty(
        name="IPL Target",
        subtype='FILE_PATH',
        description=T("Путь к IPL-файлу куда этот объект был экспортирован последним"),
        default="",
    )
    img_target_file : StringProperty(
        name="IMG Target",
        subtype='FILE_PATH',
        description=T("Путь к IMG-архиву, откуда модель импортирована (или куда "
                      "последний раз экспортирована). Даёт статус «В IMG» и "
                      "цель по умолчанию для экспорта модели в IMG"),
        default="",
    )
    ipl_last_pos : FloatVectorProperty(
        name="IPL Last Pos",
        size=3,
        default=(0.0, 0.0, 0.0),
        description=T("Координаты на момент последнего экспорта в IPL. Если текущая позиция отличается — Add to IPL обновит существующую строку вместо добавления новой"),
    )
    ipl_last_rot : FloatVectorProperty(
        name="IPL Last Rot",
        size=4,
        default=(0.0, 0.0, 0.0, 1.0),
        description=T("Кватернион (x,y,z,w) на момент последнего экспорта в IPL"),
    )
    ipl_last_model_id : IntProperty(
        name="IPL Last Model ID",
        default=0,
        description=T("Model ID на момент последнего экспорта в IPL (для content-match при рассинхроне sidecar'а)"),
    )

    # ── IDE link tracking ──
    # IDE entries are keyed by ``model_id`` (natural primary key) so we
    # don't need a UUID like IPL.  We only track the *last-exported
    # values* of fields the user can change in Blender — draw distance,
    # TXD name, flags — so the panel can show a "drifted" badge when
    # those drift away from the file, and Sync can push file→Blender
    # for the inverse direction (after an external IDE edit).
    ide_target_file : StringProperty(
        name="IDE Target",
        subtype='FILE_PATH',
        description=T("Путь к IDE-файлу куда этот объект был экспортирован последним"),
        default="",
    )
    ide_last_draw_distance : FloatProperty(
        name="IDE Last Draw Distance",
        default=0.0,
        description=T("Draw distance на момент последнего Add to IDE"),
    )
    ide_last_txd_name : StringProperty(
        name="IDE Last TXD",
        default="",
        description=T("TXD имя на момент последнего Add to IDE"),
    )
    ide_last_flags : IntProperty(
        name="IDE Last Flags",
        default=0,
        description=T("Object flags на момент последнего Add to IDE"),
    )
    ide_last_model_id : IntProperty(
        name="IDE Last Model ID",
        default=0,
        description=T("Model ID на момент последней привязки к IDE. Если "
                      "текущий Model ID отличается (например скопировал модель "
                      "и сменил ID) — привязка к старой строке IDE неактуальна"),
    )
    ide_linked : BoolProperty(
        name="IDE Linked",
        default=False,
        description=T("True если model_id этого объекта был успешно записан в IDE через Add"),
    )

    # Стек слоёв запекания текстур — PER-MODEL (переехал со сцены). У каждой
    # модели свой набор карт (Bevel/AO/Diffuse/…) со своими настройками.
    gtatools_bake_layers : CollectionProperty(type=INUBakeLayer)
    gtatools_bake_layers_index : IntProperty(
        default=0, update=_bake_layer_index_update)

    # Collision sphere/cone properties
    col_material : IntProperty(default=12, description=T("Материал для Sphere/Cone"))
    col_flags : IntProperty(default=0, description=T("Флаги для Sphere/Cone"))
    col_brightness : IntProperty(default=0, description=T("Яркость для Sphere/Cone"))
    col_light : IntProperty(default=0, description=T("Свет для Sphere/Cone"))


# GTA SA vehicle color slot → magic RGB marker value.
# Движок SA сканирует material.color.rgb, и если находит одно из магических значений
# — подставляет цвет из carcols.dat для нужного слота кузова/огня.
# Значения взяты из Kam's GTA_Material.ms (colhprIdx).
_VEHICLE_COLOR_SLOTS = {
    'NONE':    None,
    'PRIMARY':    (60,  255, 0),
    'SECONDARY':  (255, 0,   175),
    'THIRD':      (0,   255, 255),
    'FOURTH':     (255, 0,   255),
    'HL_LEFT':    (255, 175, 0),
    'HL_RIGHT':   (0,   255, 200),
    'TL_LEFT':    (185, 255, 0),
    'TL_RIGHT':   (255, 60,  0),
}

def _on_vehicle_color_slot_update(self, context):
    """При выборе слота красим базовый цвет материала в магическое RGB,
    по которому движок SA найдёт соответствующий carcols-цвет."""
    rgb = _VEHICLE_COLOR_SLOTS.get(self.vehicle_color_slot)
    if rgb is None:
        return
    mat = getattr(self, 'id_data', None)
    if mat is None:
        return
    # Устанавливаем diffuse color в Principled BSDF + material.diffuse_color
    r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
    try:
        mat.diffuse_color = (r, g, b, 1.0)
    except Exception:
        pass
    if mat.use_nodes and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                bc = node.inputs.get('Base Color')
                if bc is not None:
                    bc.default_value = (r, g, b, 1.0)
                break


def _uv_anim_preview_update(self, context):
    """При включении/выключении UV-анимации (или смене режима) строить/убирать/
    перестраивать ноды предпросмотра в шейдере (см. tools/uv_anim_preview)."""
    mat = self.id_data
    try:
        from .tools import uv_anim_preview
        if self.uv_anim_write:
            uv_anim_preview.setup(mat, mode=self.uv_anim_mode)
        else:
            uv_anim_preview.remove(mat)
    except Exception as exc:
        print(f"[INU] UV anim preview: {exc}")


class INUMaterialProps(bpy.types.PropertyGroup):
    """INU_tools material properties (replaces DragonFF mat.dff)."""

    # UI state — which tab is active in the unified Material panel.
    material_tab : EnumProperty(
        name="Material Tab",
        items=[
            ('EFFECTS',  "Effects",  T("RW-эффекты материала: env map, bump, specular, reflection, dual texture, UV anim + пресеты")),
            ('SURFACE',  T("Материал коллизии"),  T("COL Surface Type — тип физической поверхности и Day/Night Light")),
            ('ALPHA',    T("Альфа"),  T("Массовая замена режима прозрачности у альфа-материалов сцены")),
        ],
        default='EFFECTS',
    )

    ambient : FloatProperty(name="Ambient Shading", default=1.0)
    # RW surface lighting coefficients — preserved verbatim from the DFF.
    # Vanilla GTA uses specular=1.0, diffuse=1.0; reading these from Blender
    # shader inputs (Roughness/Specular) instead halved every material's
    # brightness on round-trip ("slightly darker after export").
    surf_specular : FloatProperty(name="Surface Specular", default=1.0)
    surf_diffuse  : FloatProperty(name="Surface Diffuse",  default=1.0)

    # Vehicle color slot — только для машин (GTA SA)
    vehicle_color_slot : EnumProperty(
        name="Vehicle Color Slot",
        description=T("Слот цвета машины: движок SA подставит цвет из carcols.dat. Меняет базовый RGB материала на магическую метку."),
        items=[
            ('NONE',      "None",           T("Обычный материал, не связан с carcols")),
            ('PRIMARY',   "Primary",        T("Основной цвет (первый в carcols.dat)")),
            ('SECONDARY', "Secondary",      T("Второй цвет")),
            ('THIRD',     "Third color",    T("Третий цвет (некоторые машины)")),
            ('FOURTH',    "Fourth color",   T("Четвёртый цвет")),
            ('HL_LEFT',   "Left Headlight", T("Левая фара")),
            ('HL_RIGHT',  "Right Headlight",T("Правая фара")),
            ('TL_LEFT',   "Left Taillight", T("Левый задний фонарь")),
            ('TL_RIGHT',  "Right Taillight",T("Правый задний фонарь")),
        ],
        default='NONE',
        update=_on_vehicle_color_slot_update,
    )

    # Collision surface
    col_mat_index : IntProperty(name="Surface ID", default=0, description=T("ID типа поверхности COL (0-178)"))
    col_flags : IntProperty(name="Flags", default=0)
    col_brightness : IntProperty(name="Brightness", default=0)
    col_light : IntProperty(name="Light", default=0)
    col_day_light : IntProperty(name="Day Light", default=0, min=0, max=15)
    col_night_light : IntProperty(name="Night Light", default=0, min=0, max=15)
    # Source game for surface IDs — set by COL import to the detected
    # game (III/VC/SA). Read by COL export when target game differs:
    # surface_id is routed through core.surface_translate to map a III
    # asphalt to SA asphalt rather than writing the same byte unchanged
    # (which would point at a different material in SA's larger table).
    # Empty string = unknown source, writer falls back to clamp-only.
    col_source_game : StringProperty(name="Source Game", default="",
        description=T("Игра-источник Surface ID (III/VC/SA). Использует core.surface_translate при экспорте в другую игру"))

    # Environment Map
    export_env_map : BoolProperty(name="Environment Map")
    env_map_tex : StringProperty()
    env_map_coef : FloatProperty(default=0.5)
    env_map_fb_alpha : BoolProperty()

    # Bump Map
    export_bump_map : BoolProperty(name="Bump Map")
    bump_map_tex : StringProperty()

    # Reflection
    export_reflection : BoolProperty(name="Reflection Material")
    reflection_scale_x : FloatProperty()
    reflection_scale_y : FloatProperty()
    reflection_offset_x : FloatProperty()
    reflection_offset_y : FloatProperty()
    reflection_intensity : FloatProperty()

    # Specular
    export_specular : BoolProperty(name="Specular Material")
    specular_level : FloatProperty()
    specular_texture : StringProperty()

    # Dual Texture / Blend Mode
    export_dual_tex : BoolProperty(name="Dual Texture / Blend Mode")
    dual_tex_src_blend : EnumProperty(
        name="Src Blend",
        items=[
            ('1', "Zero", ""),
            ('2', "One", ""),
            ('3', "Src Color", ""),
            ('4', "Inv Src Color", ""),
            ('5', "Src Alpha", ""),
            ('6', "Inv Src Alpha", ""),
            ('7', "Dest Alpha", ""),
            ('8', "Inv Dest Alpha", ""),
            ('9', "Dest Color", ""),
            ('10', "Inv Dest Color", ""),
            ('11', "Src Alpha Sat", ""),
        ],
        default='5',
    )
    dual_tex_dst_blend : EnumProperty(
        name="Dst Blend",
        items=[
            ('1', "Zero", ""),
            ('2', "One", ""),
            ('3', "Src Color", ""),
            ('4', "Inv Src Color", ""),
            ('5', "Src Alpha", ""),
            ('6', "Inv Src Alpha", ""),
            ('7', "Dest Alpha", ""),
            ('8', "Inv Dest Alpha", ""),
            ('9', "Dest Color", ""),
            ('10', "Inv Dest Color", ""),
            ('11', "Src Alpha Sat", ""),
        ],
        default='6',
    )
    dual_tex_texture : StringProperty(name="Dual Texture")

    # Texture filtering / addressing (the RW texture filterAddressing word).
    # Low byte = filter mode; nibbles 2-3 = U/V addressing. tex_filter_hi keeps
    # the high 16 bits (vanilla GTA sets 0x0001) so the word round-trips exactly.
    tex_filter : EnumProperty(
        name="Filtering",
        items=[
            ('0', "None", ""),
            ('1', "Nearest", ""),
            ('2', "Linear", ""),
            ('3', "Mip Nearest", ""),
            ('4', "Mip Linear", ""),
            ('5', "Linear Mip Nearest", ""),
            ('6', "Linear Mip Linear", ""),
        ],
        default='2',
    )
    tex_addr_u : EnumProperty(
        name="Address U",
        items=[
            ('0', "None", ""),
            ('1', "Wrap", ""),
            ('2', "Mirror", ""),
            ('3', "Clamp", ""),
            ('4', "Border", ""),
        ],
        default='1',
    )
    tex_addr_v : EnumProperty(
        name="Address V",
        items=[
            ('0', "None", ""),
            ('1', "Wrap", ""),
            ('2', "Mirror", ""),
            ('3', "Clamp", ""),
            ('4', "Border", ""),
        ],
        default='1',
    )
    tex_filter_hi : IntProperty(default=0x1)  # high 16 bits of filterAddressing
    mask_texture : StringProperty(name="Mask Texture")
    # Authoritative GTA texture name. Set on import; when non-empty the exporter
    # uses it verbatim (top priority over the Blender image/node name, which can
    # carry .001 suffixes), so the user can rename/fix it directly.
    texture_name : StringProperty(name="Texture Name")

    # UV Animation
    export_animation : BoolProperty(name="UV Animation")
    animation_name : StringProperty()
    # UV Animation written into DFF binary (chunks 0x2B / 0x135)
    uv_anim_write : BoolProperty(
        name="Write UV Anim to DFF",
        description=T("Вписать UV-анимацию в экспортируемый DFF. "
                      "Также строит ноды предпросмотра — текстура едет в "
                      "вьюпорте при проигрывании таймлайна"),
        default=False,
        update=_uv_anim_preview_update,
    )
    uv_anim_mode : EnumProperty(
        name="UV Anim Mode",
        description=T("Режим UV-анимации"),
        items=[
            ('SCROLL', T("Прокрутка"),
             T("Постоянная линейная прокрутка по Speed U/V")),
            ('KEYFRAME', T("Ключевые кадры"),
             T("Своя анимация: расставь ключи на ноде Mapping "
               "(Location/Scale), экспорт прочитает их")),
        ],
        default='SCROLL',
        update=_uv_anim_preview_update,
    )
    uv_anim_speed_u : FloatProperty(
        name="Scroll U",
        description=T("Скорость прокрутки UV по U в секунду"),
        default=0.0, precision=4,
    )
    uv_anim_speed_v : FloatProperty(
        name="Scroll V",
        description=T("Скорость прокрутки UV по V в секунду"),
        default=0.0, precision=4,
    )
    uv_anim_duration : FloatProperty(
        name="Duration (s)",
        description=T("Длительность цикла UV-анимации"),
        default=1.0, min=0.01, soft_max=60.0, precision=3,
    )

    # Vehicle Paintjob — alt textures packed into vehicle's TXD with names
    # '<base>_paintjob1' and '<base>_paintjob2', where <base> is the name
    # of this material's main image. The game swaps the active body
    # texture with one of these when the player buys a paintjob in
    # Pay'n'Spray. None on either field = no paintjob shipped.
    paintjob_alt_1 : PointerProperty(
        type=bpy.types.Image,
        name="Paintjob 1",
        description=T(
            "Альтернативная текстура для Pay'n'Spray paintjob 1.\n"
            "Будет упакована в TXD как <base>_paintjob1, где <base> — "
            "имя основной текстуры этого материала."),
    )
    paintjob_alt_2 : PointerProperty(
        type=bpy.types.Image,
        name="Paintjob 2",
        description=T(
            "Альтернативная текстура для Pay'n'Spray paintjob 2.\n"
            "Будет упакована в TXD как <base>_paintjob2."),
    )


# GTATOOLS_ImgFileEntry, GTATOOLS_BinaryIplEntry — moved to scene_settings.py
# (referenced by CollectionProperty fields inside INUSceneSettings).


class GTATOOLS_TxdExportEntry(bpy.types.PropertyGroup):
    """One row in the Export-to-IMG TXD plan popup.

    ``model_name`` is the DFF base name and acts as a lookup key back into
    the scene's model groups; ``txd_name`` is the destination archive name
    (editable per row); ``include`` lets the user drop a row out of the
    batch without affecting the rest of the selection.
    """
    model_name: StringProperty()
    txd_name: StringProperty(
        description=T("Имя TXD архива для этой модели. Модели с одинаковым именем попадут в один .txd (textures merged)"),
    )
    include: BoolProperty(
        name="",
        default=True,
        description=T("Включить DFF модели в экспорт"),
    )
    # Иерархия под DFF: LOD и COL. Включены по умолчанию. Имена/флаги
    # «найдено в сцене» заполняет invoke().
    inc_lod: BoolProperty(
        name="",
        default=True,
        description=T("Экспортировать LOD этой модели. Если LOD в сцене нет — уйдёт копия основной модели под LOD-именем"),
    )
    inc_col: BoolProperty(
        name="",
        default=True,
        description=T("Экспортировать COL (коллизию). Если COL в сцене нет — будет создана пустая габаритная COL-заглушка"),
    )
    lod_name: StringProperty()
    col_name: StringProperty()
    lod_found: BoolProperty(default=False)
    col_found: BoolProperty(default=False)


# IMG operators + _refresh_img_entries helper moved to ops/img_ops.py
# in Phase 3 of UI redesign.
from .ops.img_ops import (
    GTATOOLS_OT_refresh_img_list,
    GTATOOLS_OT_extract_resources,
    GTATOOLS_OT_import_from_img,
    GTATOOLS_OT_scan_ide_for_ipl,
    GTATOOLS_OT_scan_img_for_ipl,
    GTATOOLS_OT_open_url,
    GTATOOLS_OT_open_text_file,
    GTATOOLS_OT_remove_from_img,
    GTATOOLS_OT_verify_img_link,
    GTATOOLS_OT_export_to_img,
    GTATOOLS_OT_rebuild_img,
)

# Asset Library Builder — turns .inu_cache contents into a portable
# Blender Asset Library (one .blend per category, with thumbnails and
# embedded IDE metadata). Sibling to Extract Resources in the workflow.
from .ops.build_library_ops import (
    GTATOOLS_OT_build_asset_library,
    GTATOOLS_OT_regenerate_previews,
)


class GTATOOLS_FillColorItem(bpy.types.PropertyGroup):
    """Элемент списка цветов заливки"""
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0)
    )


# =============================================================================
# OPERATORS
# =============================================================================

# Check operators moved to ops/check.py in Phase 3 of UI redesign.
from .ops.check import (
    GTATOOLS_OT_check_geometry,
    GTATOOLS_OT_check_ngons,
)


# Vehicle operators moved to ops/vehicle.py in Phase 3 of UI redesign.
from .ops.vehicle import (
    GTATOOLS_OT_sa_vehicle_preset,
)


# DFF/COL/TXD import-export operators moved to ops/* in Phase 3 of UI
# redesign. Each engine module now also owns its Blender operator wrapper.
from .ops.txd_export import (
    GTATOOLS_OT_export_txd,
)
from .ops.dff_export import GTATOOLS_OT_export_dff
from .ops.col_export import GTATOOLS_OT_export_col
from .ops.auto_col_ops import GTATOOLS_OT_auto_col
from .ops.dff_import import (
    GTATOOLS_OT_import_dff,
    GTATOOLS_OT_drop_dff,
)
from .ops.ariane_bridge import (
    GTATOOLS_OT_ariane_watch,
    GTATOOLS_OT_ariane_import_now,
    GTATOOLS_OT_ariane_send,
    GTATOOLS_OT_ariane_send_pos,
    GTATOOLS_OT_ariane_create_model,
    GTATOOLS_OT_ariane_bind,
    GTATOOLS_OT_ariane_clear,
    GTATOOLS_OT_ariane_pick_game,
    stop_watch as _ariane_stop_watch,
)
from .ops.col_import import (
    GTATOOLS_OT_import_col,
    GTATOOLS_OT_drop_col,
)
if hasattr(bpy.types, 'FileHandler'):
    from .ops.dff_import import GTATOOLS_FH_dff_drop
    from .ops.col_import import GTATOOLS_FH_col_drop
    from .ops.cst_import import GTATOOLS_FH_cst_drop
from .ops.txd_import import GTATOOLS_OT_import_txd


def menu_func_export(self, context):
    self.layout.operator(GTATOOLS_OT_inu_export.bl_idname,
                         text="INU Export (.dff/.col/.txd/.ide/.ipl)")
    # Single-DFF export: the whole selected hierarchy → ONE .dff (vehicle /
    # ped / any multi-part model). INU Export / Export All split by model
    # name, which is wrong for a car (each part would become its own .dff).
    self.layout.operator(GTATOOLS_OT_export_dff.bl_idname,
                         text="INU Export DFF — single model (vehicle / ped)")


# ── IDE / IPL panel operators ──

def _ide_entry_from_obj(obj, auto_id=False):
    """Build IdeObject from a Blender mesh object."""
    from .core.ide import IdeObject
    inu = getattr(obj, 'inu', None)
    name = _clean_model_name_ide(obj.name)
    model_id = getattr(inu, 'model_id', 0) if inu else 0

    # Auto-assign ID from manager if 0
    if model_id == 0 and auto_id:
        from .data.id_manager import allocate_id
        model_id = allocate_id(name)
        if inu:
            inu.model_id = model_id

    txd_name = getattr(inu, 'txd_name', '') if inu else ''
    if not txd_name:
        txd_name = name
    draw_dist = getattr(inu, 'draw_distance', 299.0) if inu else 299.0
    # LOD-модель: в IDE-строку идёт LOD Dist (далёкая дальность), а не обычная
    # Draw Dist. Тип определяем автоклассификатором (как в панели «По имени: LOD»).
    if inu is not None:
        try:
            from .tools.model_utils import get_model_type
            if get_model_type(obj)[0] == 'LOD':
                draw_dist = getattr(inu, 'lod_draw_distance', draw_dist)
        except Exception:
            pass
    flags = getattr(inu, 'ide_flags', 0) if inu else 0
    # #9: translate flags when this object was imported tagged with a
    # different source game than the scene's target (mirrors the full-export
    # path in ide_export.py). Without this, Add-to-IDE writes raw bits that
    # mean the wrong thing across games. Same-game / unknown source passes
    # through unchanged.
    if inu:
        src_game = getattr(inu, 'ide_flags_source_game', '') or ''
        if src_game:
            try:
                from .core import game_versions
                tgt_game = game_versions.game_of_scene(bpy.context.scene)
                if tgt_game and src_game != tgt_game:
                    from .core.ide_flag_translate import translate_flags
                    flags = translate_flags(flags, src_game, tgt_game)
            except Exception:
                pass
    return IdeObject(model_id=model_id, model_name=name,
                     txd_name=txd_name, draw_distance=draw_dist, flags=flags)


def _ipl_entry_from_obj(obj):
    """Build IplInstance from a Blender mesh object."""
    from .core.ipl import IplInstance
    inu = getattr(obj, 'inu', None)
    name = _clean_model_name_ide(obj.name)
    model_id = getattr(inu, 'model_id', 0) if inu else 0
    interior = getattr(inu, 'interior_id', 0) if inu else 0
    lod_index = getattr(inu, 'lod_index', -1) if inu else -1
    real_interior = getattr(inu, 'real_interior', 0) if inu else 0
    loc = obj.matrix_world.translation
    rot = obj.matrix_world.to_quaternion().conjugated()
    return IplInstance(model_id=model_id, model_name=name,
                       interior=interior,
                       pos_x=loc.x, pos_y=loc.y, pos_z=loc.z,
                       rot_x=rot.x, rot_y=rot.y, rot_z=rot.z, rot_w=rot.w,
                       lod_index=lod_index, real_interior=real_interior)


def _clean_model_name_ide(name):
    # Strip Blender duplicate suffix FIRST (.001, .002, etc.)
    if '.' in name:
        b, s = name.rsplit('.', 1)
        if s.isdigit():
            name = b
    class _Mock:
        def __init__(self, n):
            self.name = n
    _, base = get_model_type(_Mock(name))
    return base


# Map auto-discover + binary IPL ops moved to ops/map_ops.py
# in Phase 3 of UI redesign.
from .ops.map_ops import (
    GTATOOLS_OT_discover_game,
    GTATOOLS_OT_set_preset_dir,
    GTATOOLS_OT_reset_preset_dir,
    GTATOOLS_OT_open_preset_dir,
    GTATOOLS_OT_binary_ipl_toggle_all,
    GTATOOLS_OT_text_ipl_toggle_all,
    GTATOOLS_OT_scan_binary_ipls,
)


# Map viewport/glTF/import ops moved to ops/map_ops.py in Phase 3
# (batch 3b). _bbox_* / _links_* globals + their draw handlers moved
# with the operators. Heavy import_map + replace-with-DFF too.
from .ops.map_ops import (
    GTATOOLS_OT_toggle_links,
    GTATOOLS_OT_toggle_bbox,
    GTATOOLS_OT_import_map,
)


# IMG operator moved to ops/img_ops.py in Phase 3 of UI redesign.


def _append_export_report(report_path: str, title: str, rows, max_chars: int = 200000):
    """Append one export run to text log and cap file size."""
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    block = [f"[{title}] {ts}"]
    block.extend(rows if rows else ["- no results"])
    payload = "\n".join(block) + "\n\n"

    try:
        if os.path.isfile(report_path):
            with open(report_path, 'r', encoding='utf-8', errors='replace') as f:
                prev = f.read()
        else:
            prev = ""
    except Exception:
        prev = ""

    merged = prev + payload
    if len(merged) > max_chars:
        merged = merged[-max_chars:]
        first_nl = merged.find('\n')
        if first_nl != -1:
            merged = merged[first_nl + 1:]

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(merged)


# IMG operator moved to ops/img_ops.py in Phase 3 of UI redesign.


# IDE/IPL operators (11 ops) moved to ops/ide_ipl.py in Phase 3 batch 4.
# Helpers _ide_entry_from_obj / _ipl_entry_from_obj / _clean_model_name_ide
# stay below as the single source of truth for INU Import/Export too.
from .ops.ide_ipl import (
    GTATOOLS_OT_add_to_map,
    GTATOOLS_OT_remove_from_map,
    GTATOOLS_OT_import_picked_ide,
    GTATOOLS_OT_import_picked_ipl,
    GTATOOLS_OT_upsert_ide,
    GTATOOLS_OT_upsert_ipl,
    GTATOOLS_OT_pick_setting_path,
    GTATOOLS_OT_ide_sync_from_file,
    GTATOOLS_OT_ide_remove_link,
    GTATOOLS_OT_ide_verify_links,
    GTATOOLS_OT_ipl_sync_from_file,
    GTATOOLS_OT_ipl_restore_coords,
    GTATOOLS_OT_ipl_sync_add,
    GTATOOLS_OT_ipl_sync_add_folder,
    GTATOOLS_OT_ipl_sync_remove,
    GTATOOLS_OT_ide_sync_add,
    GTATOOLS_OT_ide_sync_add_folder,
    GTATOOLS_OT_ide_sync_remove,
    GTATOOLS_OT_ide_sync_export,
    GTATOOLS_OT_ipl_sync_export,
    GTATOOLS_OT_ipl_remove_link,
    GTATOOLS_OT_ipl_verify_links,
    GTATOOLS_OT_link_sync,
    GTATOOLS_OT_link_unlink,
    GTATOOLS_OT_link_verify,
    GTATOOLS_OT_remove_ide,
    GTATOOLS_OT_remove_ipl,
    GTATOOLS_OT_export_ide,
    GTATOOLS_OT_export_ipl,
    GTATOOLS_OT_import_ipl_sections,
    GTATOOLS_OT_export_ipl_sections,
    GTATOOLS_OT_import_ide,
    GTATOOLS_OT_import_ipl,
    GTATOOLS_OT_replace_ipl_placeholders,
)


def _clean_name_typed_ipl(name):
    class _Mock:
        def __init__(self, n):
            self.name = n
    mt, base = get_model_type(_Mock(name))
    return base, mt or 'OTHER'


# INU Import/Export operators (3 ops) moved to ops/inu_export.py
# in Phase 3 batch 5. Helper _clean_name_typed_ipl stays above as it's
# also used by ops/ide_ipl.py.
from .ops.inu_export import (
    GTATOOLS_OT_inu_import,
    GTATOOLS_OT_export_all,
    GTATOOLS_OT_quick_single_export,
    GTATOOLS_OT_export_dff_models,
    GTATOOLS_OT_inu_export,
    menu_func_import,
)


class GTATOOLS_OT_info_tooltip(bpy.types.Operator):
    """"""
    bl_idname = "gtatools.info_tooltip"
    bl_label = ""
    bl_options = {'INTERNAL'}

    tooltip : StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def execute(self, context):
        return {'CANCELLED'}


def _draw_label_with_info(layout, text, tooltip, **icon_kw):
    """Draw info icon before label text. Pass icon via ``**inu_icon(...)``
    so either ``icon=`` (native) or ``icon_value=`` (Lucide PNG) reaches
    the label."""
    row = layout.row(align=True)
    sub = row.row(align=True)
    # ui_units_x added in Blender 2.83 — guard for 2.80–2.82 fallback
    # (без ширины row просто чуть шире, но draw не падает).
    try:
        sub.ui_units_x = 1.3
    except AttributeError:
        pass
    op = sub.operator("gtatools.info_tooltip", text="", **inu_icon('INFO'))
    op.tooltip = tooltip
    row.label(text=text, **icon_kw)


# Light/Lightmap/Itera/VertexPaint/Scatter operators moved to
# ops/light_ops.py in Phase 3 batch 6 (38 ops + helpers).
from .ops.light_ops import (
    GTATOOLS_OT_prelight_foliage,
    GTATOOLS_OT_foliage_color_reset,
    GTATOOLS_OT_light_topo_cut,
    GTATOOLS_OT_lightcut_ring_add,
    GTATOOLS_OT_lightcut_ring_remove,
    GTATOOLS_OT_lightcut_create,
    GTATOOLS_OT_lightmap_generate,
    GTATOOLS_OT_lightmap_copy,
    GTATOOLS_OT_lightmap_clear,
    GTATOOLS_OT_toggle_prelight_lights,
    GTATOOLS_OT_toggle_prelight_sun,
    GTATOOLS_OT_bake_vertex_colors,
    GTATOOLS_OT_bake_vertex_colors_simple,
    GTATOOLS_OT_reset_bake_settings,
    GTATOOLS_OT_reset_scatter_settings,
    GTATOOLS_OT_vc_smooth,
    GTATOOLS_OT_vc_contrast,
    GTATOOLS_OT_vc_brightness,
    GTATOOLS_OT_vc_gamma,
    GTATOOLS_OT_lift_shadows,
    GTATOOLS_OT_vc_smooth_between,
    GTATOOLS_OT_load_lightmap,
    GTATOOLS_OT_remove_lightmap,
    GTATOOLS_OT_fill_prelight,
    GTATOOLS_OT_prelight_merge_paint,
    GTATOOLS_OT_prelight_split_paint,
    GTATOOLS_OT_copy_color_attr,
    GTATOOLS_OT_copy_vertex_alpha,
    GTATOOLS_OT_prelight_preview,
    GTATOOLS_OT_alpha_preview,
    GTATOOLS_OT_alpha_cleanup,
    GTATOOLS_OT_fix_itera_collection,
    GTATOOLS_OT_apply_itera_material,
    GTATOOLS_OT_apply_itera_quickstart,
    GTATOOLS_OT_remove_itera_material,
    GTATOOLS_OT_eyedropper_color,
    GTATOOLS_OT_fill_faces,
    GTATOOLS_OT_restore_fill,
    GTATOOLS_OT_remove_fill_color,
    GTATOOLS_OT_select_fill_color,
    GTATOOLS_OT_delete_fill_color_level,
    GTATOOLS_OT_clear_fill_color_levels,
    GTATOOLS_OT_scatter_light,
    GTATOOLS_OT_scatter_color,
    GTATOOLS_OT_toggle_face_select,
    GTATOOLS_OT_switch_to_edit,
    GTATOOLS_OT_switch_to_vpaint,
    GTATOOLS_OT_select_color_attribute,
    GTATOOLS_OT_create_color_attr,
    GTATOOLS_OT_remove_color_attr,
)


# =============================================================================
# TEXTURE LOADER
# =============================================================================

# Operators moved to ops/texture_ops.py in Phase 3.
from .ops.texture_ops import (
    GTATOOLS_OT_toggle_scene_alpha,
    GTATOOLS_OT_load_textures,
    GTATOOLS_OT_set_blend_folder,
    GTATOOLS_OT_drop_texture_as_material,
    GTATOOLS_OT_drop_txd,
    GTATOOLS_OT_check_materials,
    GTATOOLS_OT_cleanup_materials,
    GTATOOLS_OT_sort_materials,
    GTATOOLS_OT_reset_transform,
    GTATOOLS_OT_apply_lightmap_uv2,
    GTATOOLS_OT_remove_lightmap_uv2,
    GTATOOLS_OT_toggle_lightmap_uv2,
)
if hasattr(bpy.types, 'FileHandler'):
    from .ops.texture_ops import (
        GTATOOLS_FH_texture_drop,
        GTATOOLS_FH_txd_drop,
    )
# =============================================================================
# PANELS
# =============================================================================

# Operators moved to ops/world_ops.py in Phase 3.
from .ops.timecyc_ops import (
    GTATOOLS_OT_import_timecyc,
    GTATOOLS_OT_export_timecyc,
    GTATOOLS_OT_timecyc_apply,
    GTATOOLS_OT_timecyc_viewport,
    GTATOOLS_OT_timecyc_setup_materials,
    GTATOOLS_OT_timecyc_compositor,
    GTATOOLS_OT_timecyc_diagnose,
    GTATOOLS_OT_timecyc_reset_preview,
    GTATOOLS_OT_timecyc_toggle,
    GTATOOLS_OT_timecyc_revert_slot,
    GTATOOLS_OT_timecyc_reload,
    GTATOOLS_OT_timecyc_copy_to_all_slots,
)
from .ops.world_ops import (
    GTATOOLS_OT_import_water,
    GTATOOLS_OT_export_water,
    GTATOOLS_OT_import_track,
    GTATOOLS_OT_export_track,
    GTATOOLS_OT_import_nodes,
    GTATOOLS_OT_export_nodes,
    GTATOOLS_OT_toggle_nodes_viz,
    GTATOOLS_OT_import_paths_ipl,
    GTATOOLS_OT_export_paths_ipl,
    GTATOOLS_OT_convert_to_path,
    GTATOOLS_OT_add_path_ipl,
    GTATOOLS_OT_add_track,
    GTATOOLS_OT_mark_station,
)
from .ops.path_curves import (
    GTATOOLS_OT_nodes_to_curves,
    GTATOOLS_OT_curves_to_nodes,
    GTATOOLS_OT_select_path_peds,
    GTATOOLS_OT_select_path_vehs,
    GTATOOLS_OT_select_path_all,
    GTATOOLS_OT_refresh_path_colors,
    GTATOOLS_OT_pick_path_props,
    GTATOOLS_OT_apply_path_props,
    GTATOOLS_OT_bulk_set_path_props,
    GTATOOLS_OT_add_path_accessory,
    GTATOOLS_OT_remove_path_accessory,
    GTATOOLS_OT_start_accessory_sync,
    GTATOOLS_OT_toggle_path_debug,
)
# Operators moved to ops/object_utils_ops.py in Phase 3.
from .ops.object_utils_ops import (
    GTATOOLS_OT_toggle_visibility,
    GTATOOLS_OT_snap_to_dff,
)
# ── 2DFX Light Presets ──
_2DFX_PRESETS = {
    'Default': dict(color=[255,255,255,255], corona_size=1.0, corona_far_clip=100.0,
                    pointlight_range=18.0, corona_tex='coronastar', corona_show_mode=0,
                    corona_flare_type=0, corona_enable_reflection=0, shadow_size=8.0,
                    shadow_z_distance=0, shadow_color_multiplier=40, shadow_tex='shad_exp',
                    flags1=96, flags2=0),
    'OnAllDay': dict(color=[255,255,255,255], corona_size=1.0, corona_far_clip=100.0,
                     pointlight_range=18.0, corona_tex='coronastar', corona_show_mode=0,
                     corona_flare_type=0, corona_enable_reflection=0, shadow_size=8.0,
                     shadow_z_distance=0, shadow_color_multiplier=40, shadow_tex='shad_exp',
                     flags1=96, flags2=0),
    'Lamp Post': dict(color=[255,255,171,255], corona_size=1.5, corona_far_clip=200.0,
                      pointlight_range=16.0, corona_tex='coronastar', corona_show_mode=0,
                      corona_flare_type=0, corona_enable_reflection=1, shadow_size=10.0,
                      shadow_z_distance=0, shadow_color_multiplier=40, shadow_tex='shad_exp',
                      flags1=64, flags2=0),
    'Lamp Post Coast': dict(color=[255,217,163,255], corona_size=1.2, corona_far_clip=200.0,
                            pointlight_range=14.0, corona_tex='coronamoon', corona_show_mode=0,
                            corona_flare_type=0, corona_enable_reflection=1, shadow_size=8.0,
                            shadow_z_distance=0, shadow_color_multiplier=40, shadow_tex='shad_exp',
                            flags1=64, flags2=0),
    'BB Pickup': dict(color=[255,0,0,255], corona_size=0.8, corona_far_clip=80.0,
                      pointlight_range=8.0, corona_tex='coronastar', corona_show_mode=0,
                      corona_flare_type=0, corona_enable_reflection=0, shadow_size=0.0,
                      shadow_z_distance=0, shadow_color_multiplier=0, shadow_tex='shad_exp',
                      flags1=96, flags2=0),
    'Flashing (Maverick1)': dict(color=[255,0,0,255], corona_size=0.5, corona_far_clip=200.0,
                                 pointlight_range=0.0, corona_tex='coronastar', corona_show_mode=1,
                                 corona_flare_type=0, corona_enable_reflection=0, shadow_size=0.0,
                                 shadow_z_distance=0, shadow_color_multiplier=0, shadow_tex='shad_exp',
                                 flags1=96, flags2=0),
    'Flashing (Maverick2)': dict(color=[0,255,0,255], corona_size=0.5, corona_far_clip=200.0,
                                 pointlight_range=0.0, corona_tex='coronastar', corona_show_mode=1,
                                 corona_flare_type=0, corona_enable_reflection=0, shadow_size=0.0,
                                 shadow_z_distance=0, shadow_color_multiplier=0, shadow_tex='shad_exp',
                                 flags1=96, flags2=0),
    'Flashing (Tug)': dict(color=[255,128,0,255], corona_size=0.4, corona_far_clip=150.0,
                           pointlight_range=0.0, corona_tex='coronastar', corona_show_mode=1,
                           corona_flare_type=0, corona_enable_reflection=0, shadow_size=0.0,
                           shadow_z_distance=0, shadow_color_multiplier=0, shadow_tex='shad_exp',
                           flags1=96, flags2=0),
    'Train Crossing': dict(color=[255,0,0,255], corona_size=1.0, corona_far_clip=200.0,
                           pointlight_range=12.0, corona_tex='coronastar', corona_show_mode=1,
                           corona_flare_type=0, corona_enable_reflection=1, shadow_size=0.0,
                           shadow_z_distance=0, shadow_color_multiplier=0, shadow_tex='shad_exp',
                           flags1=96, flags2=0),
    'Traffic': dict(color=[255,0,0,255], corona_size=0.7, corona_far_clip=120.0,
                    pointlight_range=6.0, corona_tex='coronastar', corona_show_mode=0,
                    corona_flare_type=0, corona_enable_reflection=0, shadow_size=0.0,
                    shadow_z_distance=0, shadow_color_multiplier=0, shadow_tex='shad_exp',
                    flags1=96, flags2=0),
}

_PRESET_NAMES = list(_2DFX_PRESETS.keys())


# Map EnumProperty identifiers to preset dict keys
_PRESET_MAP = {
    'DEFAULT': 'Default',
    'ONALLDAY': 'OnAllDay',
    'LAMP_POST': 'Lamp Post',
    'LAMP_POST_COAST': 'Lamp Post Coast',
    'BB_PICKUP': 'BB Pickup',
    'FLASHING_MAV1': 'Flashing (Maverick1)',
    'FLASHING_MAV2': 'Flashing (Maverick2)',
    'FLASHING_TUG': 'Flashing (Tug)',
    'TRAIN_CROSSING': 'Train Crossing',
    'TRAFFIC': 'Traffic',
}


# Operators moved to ops/effects_ops.py in Phase 3.
from .ops.effects_ops import (
    GTATOOLS_OT_apply_2dfx_preset,
    GTATOOLS_OT_create_2dfx,
    GTATOOLS_OT_apply_2dfx_to_selected,
    GTATOOLS_OT_toggle_2dfx_flag_bit,
    GTATOOLS_OT_load_fx_textures,
    GTATOOLS_OT_pick_fx_txd,
    GTATOOLS_OT_refresh_2dfx_preview,
    GTATOOLS_OT_remove_2dfx_preview,
    GTATOOLS_OT_particle_effect_new,
    GTATOOLS_OT_particle_effect_delete,
    GTATOOLS_OT_particle_curve_select,
    GTATOOLS_OT_particle_curve_key_add,
    GTATOOLS_OT_particle_curve_key_select_row,
    GTATOOLS_OT_particle_curve_key_remove,
    GTATOOLS_OT_particle_curve_write,
    GTATOOLS_OT_particle_emitter_switch,
    GTATOOLS_OT_reload_effects_fxp,
    GTATOOLS_OT_save_particle_effect,
    GTATOOLS_OT_attach_2dfx,
    GTATOOLS_OT_detach_2dfx,
    GTATOOLS_OT_detach_all_2dfx,
)
# Operators moved to ops/col_surface_ops.py in Phase 3.
from .ops.col_surface_ops import (
    GTATOOLS_OT_set_col_surface,
    GTATOOLS_OT_toggle_col_surface_fav,
    GTATOOLS_OT_col_surface_menu,
    GTATOOLS_OT_batch_set_distance,
)
# ============================================================================
# Preferences & ID Manager — N-sidebar subpanels
# ============================================================================
# NOTE: _draw_suffix_prefix удалён вместе с UI настройки суффиксов — тип
# модели определяется автоматически (core/model_classify); маркеры имени
# _DFF/_LOD/_COL остаются фикс-переопределением без редактирования.


def _draw_id_manager(layout, scene, context):
    """ID Manager UI — visually grouped into 4 sections:
      1. Preset row (which ID list file is active)
      2. Stats + search + paginated used-ID list
      3. Free-ID hint
      4. Action buttons grouped by purpose (selection / bulk / service)
    Service ops are collapsed by default to keep the panel compact —
    rarely-used buttons (FLA extend, GC, open-file) only show when
    the user expands that section.
    """
    _id_preset_sync(context)
    from .data.id_manager import get_free_ids, get_used_ids

    # ── 1. Preset row ──────────────────────────────────
    preset_row = layout.row(align=True)
    preset_row.prop(scene.inu_settings, "gtatools_id_preset", text="")
    preset_row.operator("gtatools.id_preset_new", text="", **inu_icon(safe_icon('ADD')))
    preset_row.operator("gtatools.id_preset_rename", text="", **inu_icon(safe_icon('GREASEPENCIL')))
    preset_row.operator("gtatools.id_preset_delete", text="", **inu_icon(safe_icon('REMOVE')))

    free = get_free_ids()
    used = get_used_ids()

    # ── 2. Stats + next free + search + used-list ─────
    stats_box = layout.box()
    stats_row = stats_box.row(align=True)
    from .tools.compat import ICON_CHECK
    stats_row.label(
        text=f"{T('Свободных:')} {len(free)}",
        **inu_icon(ICON_CHECK))
    stats_row.label(
        text=f"{T('Занятых:')} {len(used)}",
        **inu_icon(safe_icon('OBJECT_DATA')))
    if free:
        stats_box.label(
            text=f"{T('Следующий свободный:')} {free[0]}",
            **inu_icon(safe_icon('FORWARD')))

    layout.prop(scene.inu_settings, "gtatools_id_search", text="", **inu_icon(safe_icon('VIEWZOOM')))
    search = getattr(scene.inu_settings, 'gtatools_id_search', '').strip()
    page = getattr(scene.inu_settings, 'gtatools_id_page', 0)
    per_page = 20

    if used:
        filtered = []
        for id_num in sorted(used.keys()):
            name = used[id_num]
            if search:
                if search.isdigit():
                    if search not in str(id_num):
                        continue
                else:
                    if search.lower() not in name.lower():
                        continue
            filtered.append((id_num, name))

        total = len(filtered)
        max_page = max(0, (total - 1) // per_page)
        page = min(page, max_page)
        start = page * per_page
        page_items = filtered[start:start + per_page]

        if total == 0 and search:
            layout.label(
                text=T("Ничего не найдено"),
                **inu_icon(safe_icon('ERROR')))
        else:
            # 2 columns, COLUMN-major (top-to-bottom in col 1, then
            # top-to-bottom in col 2). Old layout was row-major
            # zigzag (1 2 / 3 4 / 5 6) — column-major (1 4 / 2 5 /
            # 3 6) reads naturally because IDs are sorted ascending
            # and the eye scans down each column rather than
            # bouncing across rows.
            sub = layout.box()
            sub.label(text=T("Используются:"),
                      **inu_icon(safe_icon('OUTLINER_OB_GROUP_INSTANCE')))
            n = len(page_items)
            half = (n + 1) // 2  # rows per column (col 1 ≥ col 2)
            col = sub.column(align=True)
            for r in range(half):
                row = col.row(align=True)
                # Column 1 entry — always present
                id_num, name = page_items[r]
                row.label(text=f"{id_num} {name}")
                op = row.operator(
                    "gtatools.id_manager_release",
                    text="", **inu_icon('X'))
                op.model_id = id_num
                # Column 2 entry — present unless we hit odd-count tail
                idx2 = r + half
                if idx2 < n:
                    id_num2, name2 = page_items[idx2]
                    row.label(text=f"{id_num2} {name2}")
                    op2 = row.operator(
                        "gtatools.id_manager_release",
                        text="", **inu_icon('X'))
                    op2.model_id = id_num2
                else:
                    # Filler so single tail entry doesn't take the
                    # full row width.
                    row.label(text="")
                    row.label(text="")

            if total > per_page:
                nav = sub.row(align=True)
                nav.prop(
                    scene.inu_settings, "gtatools_id_page",
                    text=f"{start+1}-{min(start+per_page, total)} / {total}")

    if free:
        sub = layout.box()
        sub.label(text=T("Свободные ID:"), **inu_icon(safe_icon('LIBRARY_DATA_DIRECT')))
        text = ", ".join(str(i) for i in sorted(free)[:20])
        if len(free) > 20:
            text += "..."
        sub.label(text=text)

    # ── 3. Actions: selection ops visible, preset/service collapsed ───
    # Assigning / clearing the SELECTED objects' IDs is the common case →
    # always shown. Preset-database + service ops (init, import-from-game, GC,
    # FLA limit, open file…) are rare → behind ONE disclosure triangle. A
    # single collapse SAVES space vs the old flat 6-row block AND groups the
    # buttons by purpose so they no longer read as one jumble.
    sel_box = layout.box().column(align=True)
    sel_box.label(text=T("Присвоить выделенным:"),
                  **inu_icon(safe_icon('RESTRICT_SELECT_OFF')))
    row = sel_box.row(align=True)
    row.operator("gtatools.id_manager_auto_assign",
                 text=T("Назначить"), **inu_icon(safe_icon('ADD')))
    row.operator("gtatools.id_manager_assign_from",
                 text=T("С ID..."), **inu_icon(safe_icon('SEQUENCE')))
    sel_box.operator("gtatools.id_manager_clear_selected",
                     text=T("Очистить выделенные"),
                     **inu_icon(safe_icon('REMOVE')))

    svc_expanded = getattr(scene.inu_settings, 'gtatools_show_id_service', False)
    svc_box = layout.box().column(align=True)
    svc_box.prop(scene.inu_settings, "gtatools_show_id_service",
                 **inu_icon(safe_icon('TRIA_DOWN' if svc_expanded
                                      else 'TRIA_RIGHT')),
                 text=T("База ID и сервис"), emboss=False)
    if svc_expanded:
        row = svc_box.row(align=True)
        row.operator("gtatools.id_manager_sync_scene",
                     text=T("Sync"), **inu_icon(safe_icon('FILE_REFRESH')))
        row.operator("gtatools.id_manager_from_game",
                     text=T("Из игры"), **inu_icon(safe_icon('IMPORT')))
        row = svc_box.row(align=True)
        row.operator("gtatools.id_manager_create",
                     text=T("Создать ID"), **inu_icon(safe_icon('FILE_NEW')))
        row.operator("gtatools.id_manager_extend",
                     text=T("Расширить FLA"), **inu_icon(safe_icon('ADD')))
        svc_box.operator("gtatools.id_manager_gc",
                         text=T("Освободить фантомы"),
                         **inu_icon(safe_icon('ORPHAN_DATA')))
        row = svc_box.row(align=True)
        row.operator("gtatools.id_manager_clear",
                     text=T("Очистить всё"), **inu_icon(safe_icon('TRASH')))
        row.operator("gtatools.id_manager_open_file",
                     text=T("Открыть файл ID"),
                     **inu_icon(safe_icon('FILE_TEXT')))


# Operators moved to ops/id_manager_ops.py in Phase 3.
from .ops.id_manager_ops import (
    GTATOOLS_OT_id_manager_open_file,
    GTATOOLS_OT_id_manager_release,
    GTATOOLS_OT_id_manager_auto_assign,
    GTATOOLS_OT_id_manager_assign_from,
    GTATOOLS_OT_batch_set_type,
    GTATOOLS_OT_id_manager_clear_selected,
    GTATOOLS_OT_id_manager_clear,
    GTATOOLS_OT_id_manager_create,
    GTATOOLS_OT_id_manager_extend,
    GTATOOLS_OT_id_manager_from_game,
    GTATOOLS_OT_id_manager_gc,
    GTATOOLS_OT_id_manager_sync_scene,
    GTATOOLS_OT_id_preset_new,
    GTATOOLS_OT_id_preset_delete,
    GTATOOLS_OT_id_preset_rename,
)
# Subpanel of light_master. bl_parent_id inherits bl_category, so no
# @apply_order — the registry only places top-level panels. Intra-parent
# bl_order literals are local (sibling order under light_master).
def _presets_dir():
    d = os.path.join(_get_user_config_dir(), 'presets')
    os.makedirs(d, exist_ok=True)
    return d


# Built-in Default preset — read-only, always first in the dropdown.
# Lives in code (not on disk) so it cannot be deleted or accidentally
# overwritten. Save/Apply/Rename operators reject the name "Default".
_DEFAULT_PRELIGHT_PRESET = {
    "name": "Default",
    "ambient": 0.10,
    "intensity": 0.05,
    "gamma": 0.50,
    "shadows": True,
    "modulate_mode": "OFF",
    "modulate_mix": 0.002,
    "modulate_contrast": 0.0,
    "modulate_gamma": 0.8,
    "v_offset": 0.0,
    "scatter_strength": 1.0,
    "scatter_distance": 0.3,
    "vc_smooth_iter": 1,
    "vc_smooth_factor": 0.5,
    "vc_contrast": 1.0,
    "vc_brightness": 0.0,
    "vc_gamma": 1.0,
    "lift_shadows": 0.5,
    "v_offset_day": 0.0,
    "v_offset_night": 0.0,
    "has_day_attr": True,
    "has_night_attr": True,
    "lights": [],
}


def _load_prelight_presets():
    import json
    presets = [dict(_DEFAULT_PRELIGHT_PRESET)]  # always first
    d = _presets_dir()
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    for f in sorted(os.listdir(d)):
        if f.endswith('.json'):
            try:
                with open(os.path.join(d, f), 'r', encoding='utf-8') as fh:
                    p = json.load(fh)
                    name = p.get('name')
                    if not name or name == _DEFAULT_PRELIGHT_PRESET['name']:
                        # Skip user-written file with the reserved name
                        # so the in-code Default always wins.
                        continue
                    presets.append(p)
            except (OSError, ValueError, AttributeError):
                # Unreadable file, malformed JSON, or a top-level array
                # instead of an object — skip that preset, keep the rest.
                continue
    return presets


def _save_preset_file(preset):
    import json
    d = _presets_dir()
    os.makedirs(d, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in preset['name'])
    path = os.path.join(d, f"{safe_name}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(preset, f, indent=2, ensure_ascii=False)


def _delete_preset_file(name):
    d = _presets_dir()
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
    path = os.path.join(d, f"{safe_name}.json")
    if os.path.isfile(path):
        os.remove(path)


def _get_preset_items(self, context):
    presets = _load_prelight_presets()
    items = [(p['name'], p['name'], '') for p in presets]
    return items if items else [('NONE', 'No presets', '')]


# Operators moved to ops/prelight_preset_ops.py in Phase 3.
from .ops.prelight_preset_ops import (
    GTATOOLS_OT_prelight_preset_load,
    GTATOOLS_OT_prelight_preset_save,
    GTATOOLS_OT_prelight_preset_delete,
    GTATOOLS_OT_prelight_preset_apply,
    GTATOOLS_OT_prelight_preset_rename,
    GTATOOLS_OT_prelight_view_reset,
)
# Operators moved to ops/water_geometry_ops.py in Phase 3.
from .ops import water_geometry_ops as _water_geo_mod
from .ops.water_geometry_ops import (
    GTATOOLS_OT_add_water,
    GTATOOLS_OT_water_snap_grid,
    GTATOOLS_OT_water_snap_block,
    GTATOOLS_OT_water_split_blocks,
    GTATOOLS_OT_water_set_params,
    GTATOOLS_OT_water_stitch,
    GTATOOLS_OT_toggle_water_limits,
)
from .ops.file_scanner_ops import (
    GTATOOLS_OT_scan_files,
    GTATOOLS_OT_scan_save_report,
    GTATOOLS_OT_scan_reveal_file,
    GTATOOLS_OT_scan_clear,
)
from .ops.map_analyzer_ops import (
    GTATOOLS_OT_analyze_map,
    GTATOOLS_OT_map_analyzer_add_ide,
    GTATOOLS_OT_map_analyzer_add_ipl,
    GTATOOLS_OT_map_analyzer_remove_ide,
    GTATOOLS_OT_map_analyzer_remove_ipl,
    GTATOOLS_OT_map_analyzer_clear,
    GTATOOLS_OT_map_analyzer_save_report,
)
from .ops.texture_browser_ops import (
    GTATOOLS_OT_scan_textures,
    GTATOOLS_OT_clear_texture_browser,
    GTATOOLS_OT_texture_browser_add_file,
    GTATOOLS_OT_texture_browser_remove_file,
)
# =============================================================================
# IFP (ANIMATION) OPERATORS
# =============================================================================

# Operators moved to ops/ifp_ops.py in Phase 3.
from .ops.ifp_ops import (
    GTATOOLS_OT_import_ifp,
    GTATOOLS_OT_export_ifp,
    GTATOOLS_OT_ifp_roundtrip,
    GTATOOLS_OT_merge_ifp,
    GTATOOLS_OT_ifp_preview_toggle,
    GTATOOLS_OT_apply_ifp,
    GTATOOLS_OT_fix_quat_signs,
    GTATOOLS_OT_mirror_anim,
    GTATOOLS_OT_smooth_between_anchors,
    GTATOOLS_OT_delete_active_action,
)
from .ops.camera_io import (
    GTATOOLS_OT_import_camera_dat,
    GTATOOLS_OT_export_camera_dat,
)
from .ops.fragment_ops import (
    GTATOOLS_OT_fragment_mesh,
)
from .ops.ik_rig import (
    GTATOOLS_OT_add_ik_rig,
    GTATOOLS_OT_bake_ik_rig,
    GTATOOLS_OT_add_ground_plane,
    _unregister_follow_handler as _ik_unregister_follow_handler,
    _on_file_load_ik as _ik_on_file_load,
)
from .ops.handsign_ops import (
    GTATOOLS_OT_handsign_attach,
    GTATOOLS_OT_handsign_detach,
    GTATOOLS_OT_handsign_export,
)
# ── X Radar Maker ────────────────────────────────────────────────────

# Operators moved to ops/radar_ops.py in Phase 3.
from .ops.radar_ops import (
    GTATOOLS_OT_radar_generate,
    GTATOOLS_OT_radar_pack_txd,
)
from .ops.viewport_floater import (
    GTATOOLS_OT_floater_modal,
    GTATOOLS_OT_floater_toggle,
)


# ── Legacy data migration — manual, on-demand ────────────────────────
# These conversions used to run on every file load (load_post), forcing
# every user through one-off calculations even on brand-new scenes.
# Per extensions.blender.org review feedback they're now a single button
# in the addon preferences. The per-conversion functions still live near
# the bottom of this module (``_on_file_load_migrate_*``); this operator
# just drives them on the current file.
class GTATOOLS_OT_run_legacy_migrations(bpy.types.Operator):
    """Однократно мигрировать данные из старых версий аддона.

    Конвертирует текущий .blend: старые дефолты Modulate Color, тяжёлый
    граф превью прилайта → минимальный, кастом-свойства 2DFX-размеров →
    поля PropertyGroup, Scene-свойства pre-Step-9 → scene.inu_settings.
    Запускать только если открыли старый проект — на новых сценах не
    нужно."""
    bl_idname = "gtatools.run_legacy_migrations"
    bl_label = "INU: Run Legacy Migrations"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Same order the old load_post chain used: modulate/prelight read
        # scene-level props, so run them before scene_settings moves those
        # props into inu_settings.
        for fn in (_on_file_load_migrate_modulate,
                   _on_file_load_migrate_prelight_nodes,
                   _on_file_load_migrate_2dfx_size,
                   _on_file_load_migrate_scene_settings):
            try:
                fn(None)
            except Exception as e:
                print(f"[INU] migration {getattr(fn, '__name__', '?')} "
                      f"failed: {e}")
        self.report({'INFO'}, T("Миграция старых данных завершена"))
        return {'FINISHED'}


class INUAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # Запоминается глобально (переживает смену файла и перезапуск Blender) —
    # чтобы галочку в импортах не приходилось переключать каждый раз.
    import_weld_sharpen: bpy.props.BoolProperty(
        name=T("Стандартная модель GTA SA (vanilla)"),
        description=T("ВКЛ — обрабатывать как СТАНДАРТНУЮ модель GTA SA "
                      "(сварка + острые рёбра, как раньше). ВЫКЛ — КАСТОМНАЯ "
                      "модель: связать рассыпанную геометрию и сохранить "
                      "двусторонние заборы"),
        default=False)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text=T("Импорт моделей"))
        box = col.box()
        box.prop(self, "import_weld_sharpen")
        box.label(
            text=T("Запоминается для всех импортов (меню, отдельный Import DFF, "
                   "перетаскивание .dff)"),
            icon='INFO')
        col.separator()
        col.label(text=T("Совместимость со старыми версиями"))
        box = col.box()
        box.label(
            text=T("Миграция данных из старых .blend (по требованию):"),
            icon='INFO')
        box.label(text=T("дефолты Modulate Color, граф превью прилайта,"))
        box.label(text=T("2DFX-размеры, Scene-свойства pre-Step-9."))
        box.operator("gtatools.run_legacy_migrations", icon='FILE_REFRESH')


# =============================================================================
# =============================================================================
# REGISTRATION
# =============================================================================

classes = (
    INUAddonPreferences,
    GTATOOLS_OT_run_legacy_migrations,
    INUParticleKeyframe,
    INUBakeLayer,          # ДО INUObjectProps: тот держит per-model стек слоёв
    INUObjectProps,
    INUMaterialProps,
    GTATOOLS_ImgFileEntry,
    GTATOOLS_AlphaMatEntry,
    GTATOOLS_OT_alpha_scan,
    GTATOOLS_OT_alpha_apply_all,
    GTATOOLS_OT_alpha_select_objects,
    GTATOOLS_UL_alpha_mats,
    GTATOOLS_BinaryIplEntry,
    GTATOOLS_TextIplEntry,
    GTATOOLS_LintIssueItem,
    GTATOOLS_PathItem,
    GTATOOLS_TextureBrowserItem,
    INUGrassEntry,
    GTATOOLS_TxdExportEntry,
    GTATOOLS_UL_txd_export_plan,
    GTATOOLS_UL_img_files,
    GTATOOLS_UL_ipl_sync_list,
    GTATOOLS_OT_refresh_img_list,
    GTATOOLS_OT_discover_game,
    GTATOOLS_OT_set_preset_dir,
    GTATOOLS_OT_reset_preset_dir,
    GTATOOLS_OT_open_preset_dir,
    GTATOOLS_OT_scan_binary_ipls,
    GTATOOLS_OT_binary_ipl_toggle_all,
    GTATOOLS_OT_text_ipl_toggle_all,
    GTATOOLS_FillColorItem,
    GTATOOLS_OT_toggle_visibility,
    GTATOOLS_OT_snap_to_dff,
    GTATOOLS_OT_check_geometry,
    GTATOOLS_OT_check_ngons,
    GTATOOLS_OT_sa_vehicle_preset,
    GTATOOLS_OT_export_txd,
    GTATOOLS_OT_copy_color_attr,
    GTATOOLS_OT_copy_vertex_alpha,
    GTATOOLS_OT_export_dff,
    GTATOOLS_OT_export_col,
    GTATOOLS_OT_auto_col,
    GTATOOLS_OT_export_all,
    GTATOOLS_OT_quick_single_export,
    GTATOOLS_OT_export_dff_models,
    GTATOOLS_OT_inu_export,
    GTATOOLS_OT_floater_modal,
    GTATOOLS_OT_floater_toggle,
    GTATOOLS_OT_info_tooltip,
    GTATOOLS_OT_prelight_foliage,
    GTATOOLS_OT_foliage_color_reset,
    GTATOOLS_OT_light_topo_cut,
    GTATOOLS_OT_lightcut_ring_add,
    GTATOOLS_OT_lightcut_ring_remove,
    GTATOOLS_OT_lightcut_create,
    GTATOOLS_OT_lightmap_generate,
    GTATOOLS_OT_lightmap_copy,
    GTATOOLS_OT_lightmap_clear,
    GTATOOLS_OT_toggle_prelight_lights,
    GTATOOLS_OT_toggle_prelight_sun,
    GTATOOLS_OT_bake_vertex_colors,
    GTATOOLS_OT_bake_vertex_colors_simple,
    GTATOOLS_OT_reset_bake_settings,
    GTATOOLS_OT_prelight_preset_load,
    GTATOOLS_OT_prelight_preset_save,
    GTATOOLS_OT_prelight_preset_delete,
    GTATOOLS_OT_prelight_preset_apply,
    GTATOOLS_OT_prelight_preset_rename,
    GTATOOLS_OT_prelight_view_reset,
    GTATOOLS_OT_reset_scatter_settings,
    GTATOOLS_OT_vc_smooth,
    GTATOOLS_OT_vc_contrast,
    GTATOOLS_OT_vc_brightness,
    GTATOOLS_OT_vc_gamma,
    GTATOOLS_OT_lift_shadows,
    GTATOOLS_OT_vc_smooth_between,
    GTATOOLS_OT_load_lightmap,
    GTATOOLS_OT_remove_lightmap,
    GTATOOLS_OT_fill_prelight,
    GTATOOLS_OT_prelight_merge_paint,
    GTATOOLS_OT_prelight_split_paint,
    GTATOOLS_OT_prelight_preview,
    GTATOOLS_OT_alpha_preview,
    GTATOOLS_OT_alpha_cleanup,
    GTATOOLS_OT_fix_itera_collection,
    GTATOOLS_OT_apply_itera_material,
    GTATOOLS_OT_apply_itera_quickstart,
    GTATOOLS_OT_remove_itera_material,
    GTATOOLS_OT_eyedropper_color,
    GTATOOLS_OT_fill_faces,
    GTATOOLS_OT_restore_fill,
    GTATOOLS_OT_remove_fill_color,
    GTATOOLS_OT_select_fill_color,
    GTATOOLS_OT_delete_fill_color_level,
    GTATOOLS_OT_clear_fill_color_levels,
    GTATOOLS_OT_scatter_light,
    GTATOOLS_OT_scatter_color,
    GTATOOLS_OT_toggle_face_select,
    GTATOOLS_OT_switch_to_edit,
    GTATOOLS_OT_switch_to_vpaint,
    GTATOOLS_OT_select_color_attribute,
    GTATOOLS_OT_create_color_attr,
    GTATOOLS_OT_remove_color_attr,
    GTATOOLS_OT_toggle_scene_alpha,
    GTATOOLS_OT_load_textures,
    GTATOOLS_OT_set_blend_folder,
    GTATOOLS_OT_drop_texture_as_material,
    GTATOOLS_OT_drop_txd,
    GTATOOLS_OT_check_materials,
    GTATOOLS_OT_cleanup_materials,
    GTATOOLS_OT_sort_materials,
    GTATOOLS_OT_reset_transform,
    GTATOOLS_OT_apply_lightmap_uv2,
    GTATOOLS_OT_remove_lightmap_uv2,
    GTATOOLS_OT_toggle_lightmap_uv2,
    GTATOOLS_OT_id_manager_open_file,
    GTATOOLS_OT_id_manager_release,
    GTATOOLS_OT_id_manager_auto_assign,
    GTATOOLS_OT_id_manager_assign_from,
    GTATOOLS_OT_batch_set_type,
    GTATOOLS_OT_batch_set_distance,
    GTATOOLS_OT_id_manager_clear_selected,
    GTATOOLS_OT_id_manager_clear,
    GTATOOLS_OT_id_manager_create,
    GTATOOLS_OT_id_manager_extend,
    GTATOOLS_OT_id_manager_gc,
    GTATOOLS_OT_id_manager_sync_scene,
    GTATOOLS_OT_id_manager_from_game,
    GTATOOLS_OT_id_preset_new,
    GTATOOLS_OT_id_preset_delete,
    GTATOOLS_OT_id_preset_rename,
    GTATOOLS_OT_toggle_uv_editor,
    GTATOOLS_OT_toggle_uv_grid,
    GTATOOLS_OT_randomize_uv_grid,
    GTATOOLS_OT_snap_uv_to_grid,
    GTATOOLS_OT_uv_fit_grid_scale,
    GTATOOLS_OT_uv_texel_density,
    GTATOOLS_OT_set_uv_align,
    GTATOOLS_OT_uv_anim_insert_key,
    GTATOOLS_OT_uv_anim_clear_keys,
    GTATOOLS_PT_main_panel,
    GTATOOLS_PT_library_panel,
    GTATOOLS_OT_import_dff,
    GTATOOLS_OT_drop_dff,
    GTATOOLS_OT_import_col,
    GTATOOLS_OT_drop_col,
    GTATOOLS_OT_drop_cst,
    GTATOOLS_OT_import_txd,
    GTATOOLS_OT_inu_import,
    GTATOOLS_OT_toggle_links,
    GTATOOLS_OT_toggle_bbox,
    GTATOOLS_OT_extract_resources,
    GTATOOLS_OT_build_asset_library,
    GTATOOLS_OT_regenerate_previews,
    GTATOOLS_OT_import_map,
    GTATOOLS_OT_import_ipl_sections,
    GTATOOLS_OT_export_ipl_sections,
    GTATOOLS_OT_import_from_img,
    GTATOOLS_OT_scan_ide_for_ipl,
    GTATOOLS_OT_scan_img_for_ipl,
    GTATOOLS_OT_open_url,
    GTATOOLS_OT_open_text_file,
    GTATOOLS_OT_import_water,
    GTATOOLS_OT_export_water,
    GTATOOLS_OT_add_water,
    GTATOOLS_OT_water_snap_grid,
    GTATOOLS_OT_water_snap_block,
    GTATOOLS_OT_water_split_blocks,
    GTATOOLS_OT_water_set_params,
    GTATOOLS_OT_water_stitch,
    GTATOOLS_OT_toggle_water_limits,
    GTATOOLS_OT_scan_files,
    GTATOOLS_OT_scan_save_report,
    GTATOOLS_OT_scan_reveal_file,
    GTATOOLS_OT_scan_clear,
    GTATOOLS_OT_analyze_map,
    GTATOOLS_OT_map_analyzer_add_ide,
    GTATOOLS_OT_map_analyzer_add_ipl,
    GTATOOLS_OT_map_analyzer_remove_ide,
    GTATOOLS_OT_map_analyzer_remove_ipl,
    GTATOOLS_OT_map_analyzer_clear,
    GTATOOLS_OT_map_analyzer_save_report,
    GTATOOLS_OT_scan_textures,
    GTATOOLS_OT_clear_texture_browser,
    GTATOOLS_OT_texture_browser_add_file,
    GTATOOLS_OT_texture_browser_remove_file,
    GTATOOLS_OT_import_track,
    GTATOOLS_OT_export_track,
    GTATOOLS_OT_import_nodes,
    GTATOOLS_OT_export_nodes,
    GTATOOLS_OT_toggle_nodes_viz,
    GTATOOLS_OT_nodes_to_curves,
    GTATOOLS_OT_curves_to_nodes,
    GTATOOLS_OT_select_path_peds,
    GTATOOLS_OT_select_path_vehs,
    GTATOOLS_OT_select_path_all,
    GTATOOLS_OT_refresh_path_colors,
    GTATOOLS_OT_pick_path_props,
    GTATOOLS_OT_apply_path_props,
    GTATOOLS_OT_bulk_set_path_props,
    GTATOOLS_OT_add_path_accessory,
    GTATOOLS_OT_remove_path_accessory,
    GTATOOLS_OT_start_accessory_sync,
    GTATOOLS_OT_toggle_path_debug,
    GTATOOLS_OT_import_ifp,
    GTATOOLS_OT_export_ifp,
    GTATOOLS_OT_merge_ifp,
    GTATOOLS_OT_ifp_roundtrip,
    GTATOOLS_OT_ifp_preview_toggle,
    GTATOOLS_OT_apply_ifp,
    GTATOOLS_OT_fix_quat_signs,
    GTATOOLS_OT_mirror_anim,
    GTATOOLS_OT_smooth_between_anchors,
    GTATOOLS_OT_delete_active_action,
    GTATOOLS_OT_import_camera_dat,
    GTATOOLS_OT_export_camera_dat,
    GTATOOLS_OT_fragment_mesh,
    GTATOOLS_OT_add_ik_rig,
    GTATOOLS_OT_bake_ik_rig,
    GTATOOLS_OT_add_ground_plane,
    GTATOOLS_OT_handsign_attach,
    GTATOOLS_OT_handsign_detach,
    GTATOOLS_OT_handsign_export,
    GTATOOLS_OT_import_paths_ipl,
    GTATOOLS_OT_export_paths_ipl,
    GTATOOLS_OT_convert_to_path,
    GTATOOLS_OT_add_path_ipl,
    GTATOOLS_OT_add_track,
    GTATOOLS_OT_mark_station,
    GTATOOLS_OT_export_to_img,
    GTATOOLS_OT_remove_from_img,
    GTATOOLS_OT_verify_img_link,
    GTATOOLS_OT_rebuild_img,
    GTATOOLS_OT_add_to_map,
    GTATOOLS_OT_remove_from_map,
    GTATOOLS_OT_import_picked_ide,
    GTATOOLS_OT_import_picked_ipl,
    GTATOOLS_OT_upsert_ide,
    GTATOOLS_OT_upsert_ipl,
    GTATOOLS_OT_pick_setting_path,
    GTATOOLS_OT_ide_sync_from_file,
    GTATOOLS_OT_ide_remove_link,
    GTATOOLS_OT_ide_verify_links,
    GTATOOLS_OT_ipl_sync_from_file,
    GTATOOLS_OT_ipl_restore_coords,
    GTATOOLS_OT_ipl_sync_add,
    GTATOOLS_OT_ipl_sync_add_folder,
    GTATOOLS_OT_ipl_sync_remove,
    GTATOOLS_OT_ide_sync_add,
    GTATOOLS_OT_ide_sync_add_folder,
    GTATOOLS_OT_ide_sync_remove,
    GTATOOLS_OT_ide_sync_export,
    GTATOOLS_OT_ipl_sync_export,
    GTATOOLS_OT_ipl_remove_link,
    GTATOOLS_OT_ipl_verify_links,
    GTATOOLS_OT_link_sync,
    GTATOOLS_OT_link_unlink,
    GTATOOLS_OT_link_verify,
    GTATOOLS_OT_remove_ide,
    GTATOOLS_OT_remove_ipl,
    GTATOOLS_OT_export_ide,
    GTATOOLS_OT_export_ipl,
    GTATOOLS_OT_import_ide,
    GTATOOLS_OT_import_ipl,
    GTATOOLS_OT_replace_ipl_placeholders,
    GTATOOLS_PT_ide_ipl_panel,
    GTATOOLS_PT_ide_ipl_import,
    GTATOOLS_PT_ide_ipl_export,
    GTATOOLS_PT_ide_ipl_map,
    GTATOOLS_PT_export_panel,
    GTATOOLS_PT_validate_scene,
    GTATOOLS_MT_create_2dfx,
    GTATOOLS_MT_radar_generate,
    GTATOOLS_MT_path_traffic,
    GTATOOLS_PT_check_panel,
    GTATOOLS_UL_lint_issues,
    GTATOOLS_PT_file_scanner,
    GTATOOLS_UL_map_lint_issues,
    GTATOOLS_PT_texture_browser,
    GTATOOLS_UL_texture_browser,
    GTATOOLS_PT_vehicle_panel,
    GTATOOLS_PT_frame_hierarchy,
    GTATOOLS_OT_apply_2dfx_preset,
    GTATOOLS_OT_create_2dfx,
    GTATOOLS_OT_apply_2dfx_to_selected,
    GTATOOLS_OT_toggle_2dfx_flag_bit,
    GTATOOLS_OT_attach_2dfx,
    GTATOOLS_OT_detach_2dfx,
    GTATOOLS_OT_detach_all_2dfx,
    GTATOOLS_OT_load_fx_textures,
    GTATOOLS_OT_pick_fx_txd,
    GTATOOLS_OT_refresh_2dfx_preview,
    GTATOOLS_OT_remove_2dfx_preview,
    GTATOOLS_OT_particle_effect_new,
    GTATOOLS_OT_particle_effect_delete,
    GTATOOLS_OT_particle_emitter_switch,
    GTATOOLS_OT_particle_curve_select,
    GTATOOLS_OT_particle_curve_key_add,
    GTATOOLS_OT_particle_curve_key_remove,
    GTATOOLS_OT_particle_curve_key_select_row,
    GTATOOLS_OT_particle_curve_write,
    GTATOOLS_OT_reload_effects_fxp,
    GTATOOLS_OT_save_particle_effect,
    GTATOOLS_OT_set_col_surface,
    GTATOOLS_OT_toggle_col_surface_fav,
    GTATOOLS_OT_col_surface_menu,
    GTATOOLS_PT_material_panel,
    # GTATOOLS_PT_object_ide_ipl_panel — убрана из N-панели: дублирует
    # «INU Tools: Model» (IDE / Placement) в свойствах. Класс оставлен в
    # импорте, но не регистрируется.
    GTATOOLS_PT_object_inu_tools,
    GTATOOLS_PT_inu_tools_panel,
    GTATOOLS_PT_id_manager_panel,
    # Phase 2: light_master must register before its 5 child light panels
    # so Blender can resolve their bl_parent_id at register time.
    GTATOOLS_OT_bake_run,
    GTATOOLS_OT_bake_select_layer,
    GTATOOLS_OT_bake_layer_add,
    GTATOOLS_OT_bake_layer_remove,
    GTATOOLS_OT_bake_layer_move,
    GTATOOLS_OT_bake_preview,
    GTATOOLS_OT_bake_flatten,
    GTATOOLS_OT_bake_save_map,
    GTATOOLS_OT_bake_lightmap_apply,
    GTATOOLS_OT_bake_lightmap_postprocess,
    GTATOOLS_OT_bake_show_over_base,
    GTATOOLS_UL_bake_layers,
    GTATOOLS_PT_uv_root,
    GTATOOLS_PT_bake_panel,
    GTATOOLS_PT_bake_advanced,
    GTATOOLS_PT_light_master,
    GTATOOLS_PT_itera_panel,
    GTATOOLS_PT_prelight_panel,
    GTATOOLS_PT_bake_settings_subpanel,
    GTATOOLS_PT_scatter_color_subpanel,
    GTATOOLS_PT_foliage_subpanel,
    GTATOOLS_PT_vc_postprocess_panel,
    GTATOOLS_OT_preview_col_light,
    GTATOOLS_OT_bake_col_light,
    GTATOOLS_OT_clear_col_light_mats,
    GTATOOLS_PT_prelight_col_panel,
    GTATOOLS_PT_2dfx_panel,
    GTATOOLS_PT_2dfx_settings,
    GTATOOLS_PT_lightmap_panel,
    GTATOOLS_PT_water_panel,
    GTATOOLS_PT_timecyc_panel,
    GTATOOLS_PT_timecyc_edit,
    GTATOOLS_PT_timecyc_preview,
    GTATOOLS_OT_import_timecyc,
    GTATOOLS_OT_export_timecyc,
    GTATOOLS_OT_timecyc_apply,
    GTATOOLS_OT_timecyc_viewport,
    GTATOOLS_OT_timecyc_setup_materials,
    GTATOOLS_OT_timecyc_compositor,
    GTATOOLS_OT_timecyc_diagnose,
    GTATOOLS_OT_timecyc_reset_preview,
    GTATOOLS_OT_timecyc_toggle,
    GTATOOLS_OT_timecyc_revert_slot,
    GTATOOLS_OT_timecyc_reload,
    GTATOOLS_OT_timecyc_copy_to_all_slots,
    GTATOOLS_OT_import_zon,
    GTATOOLS_OT_export_zon,
    GTATOOLS_OT_add_zon_zone,
    GTATOOLS_OT_zon_copy_lines,
    GTATOOLS_PT_zon_panel,
    GTATOOLS_OT_grass_import,
    GTATOOLS_OT_grass_export,
    GTATOOLS_OT_grass_add,
    GTATOOLS_OT_grass_remove,
    GTATOOLS_OT_grass_duplicate,
    GTATOOLS_OT_grass_apply_surface,
    GTATOOLS_OT_grass_preview,
    GTATOOLS_OT_grass_preview_clear,
    GTATOOLS_OT_grass_generate_geometry,
    GTATOOLS_OT_grass_geometry_clear,
    GTATOOLS_UL_grass,
    GTATOOLS_PT_grass_panel,
    GTATOOLS_PT_anim_panel,
    GTATOOLS_PT_frame_hierarchy_anim,
    GTATOOLS_OT_radar_generate,
    GTATOOLS_OT_radar_pack_txd,
    GTATOOLS_PT_radar_panel,
    GTATOOLS_PT_paths_panel,
    GTATOOLS_PT_footer_panel,
    GTATOOLS_PT_uv_tools_panel,
    GTATOOLS_PT_uv_anim_panel,
    GTATOOLS_OT_bitmaps_scan,
    GTATOOLS_OT_bitmaps_resolve,
    GTATOOLS_OT_bitmaps_copy,
    GTATOOLS_OT_bitmaps_find_unused,
    GTATOOLS_OT_bitmaps_remove_unused,
    GTATOOLS_OT_bitmaps_find_dupes,
    GTATOOLS_MT_textures_menu,
    GTATOOLS_MT_materials_menu,
    GTATOOLS_PT_bitmaps_panel,
    GTATOOLS_VCLayerItem,
    GTATOOLS_OT_vcl_add,
    GTATOOLS_OT_vcl_remove,
    GTATOOLS_OT_vcl_move,
    GTATOOLS_OT_vcl_promote,
    GTATOOLS_OT_vcl_set_active_attr,
    GTATOOLS_OT_vcl_show_composite,
    GTATOOLS_OT_vcl_refresh_composite,
    GTATOOLS_OT_vcl_apply_multi,
    GTATOOLS_OT_vcl_recolor_selected,
    GTATOOLS_UL_vc_layers,
    GTATOOLS_OT_ifp_batch_import,
    GTATOOLS_OT_refresh_station_markers,
    GTATOOLS_OT_path_node_flag,
    GTATOOLS_OT_map_export,
    GTATOOLS_OT_material_preset,
    GTATOOLS_OT_copy_material_settings,
    GTATOOLS_OT_validate_paintjobs,
    GTATOOLS_OT_open_docs,
    GTATOOLS_OT_open_issues,
    GTATOOLS_OT_open_release,
    GTATOOLS_OT_whats_new,
    INUValidateIssue,
    INULightCutRing,
    INUTimecycWeather,
    INUTimecycProps,
    GTATOOLS_OT_validate_run,
    GTATOOLS_OT_validate_clear,
    GTATOOLS_OT_validate_goto,
    GTATOOLS_OT_validate_fix_quaternions,
    GTATOOLS_OT_validate_fix_suffix,
    GTATOOLS_OT_frame_select,
    GTATOOLS_OT_frame_rename,
    GTATOOLS_OT_frame_set_parent,
    GTATOOLS_OT_frame_unparent,
    GTATOOLS_OT_frame_reparent,
    GTATOOLS_OT_frame_validate,
    GTATOOLS_OT_frame_mirror_lr,
    GTATOOLS_OT_animobj_validate,
    GTATOOLS_OT_animobj_export,
    INUAnimObjEmptyProps,
    INUAnimObjRigSettings,
    GTATOOLS_OT_animobj_parent_to_pivot,
    GTATOOLS_OT_animobj_parent_to_root,
    GTATOOLS_OT_animobj_add_pivot,
    GTATOOLS_OT_weight_merge_start,
    GTATOOLS_OT_weight_merge_apply,
    GTATOOLS_OT_weight_merge_cancel,
    GTATOOLS_OT_thin_keyframes,
    GTATOOLS_PT_graph_thin_keys,
    GTATOOLS_OT_profile_save,
    GTATOOLS_OT_profile_delete,
    GTATOOLS_OT_profile_pick_panel,
    GTATOOLS_OT_profile_toggle_panel,
    GTATOOLS_OT_profile_edit,
    GTATOOLS_OT_vehicle_scale,
    GTATOOLS_OT_vehicle_add_damage_variant,
    GTATOOLS_OT_vehicle_show_damage,
    GTATOOLS_OT_vehicle_pair_report,
)

# Drag-and-drop FileHandlers — Blender 4.1+ only.
if hasattr(bpy.types, 'FileHandler'):
    classes = classes + (
        GTATOOLS_FH_dff_drop,
        GTATOOLS_FH_col_drop,
        GTATOOLS_FH_cst_drop,
        GTATOOLS_FH_texture_drop,
        GTATOOLS_FH_txd_drop,
    )


# ── Persistent paths (saved in Blender config, survive addon updates) ──

_PATHS_FILE = None

def _write_png(path: str, pixels: bytes, width: int, height: int):
    """Write RGBA pixels to PNG file using numpy for scanline prep + zlib.

    numpy builds the filtered raw buffer (prepend 1 filter byte per row)
    in one C-level operation — ~5-10x faster than the Python for-row loop
    on big textures (e.g. 2048x2048).
    """
    import zlib
    import struct as _st

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = _st.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
        return _st.pack('>I', len(data)) + c + crc

    # IHDR
    ihdr = _st.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8bit RGBA

    # IDAT — raw scanlines with filter byte 0 per row (none filter).
    # Build via numpy: column-0 is zero filter byte, columns 1.. hold RGBA.
    stride = width * 4
    pixels_arr = np.frombuffer(pixels, dtype=np.uint8)[:height * stride].reshape(height, stride)
    filtered = np.empty((height, stride + 1), dtype=np.uint8)
    filtered[:, 0] = 0  # filter byte per scanline
    filtered[:, 1:] = pixels_arr

    compressed = zlib.compress(filtered.tobytes(), 1)  # fast compression

    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')  # PNG signature
        f.write(_chunk(b'IHDR', ihdr))
        f.write(_chunk(b'IDAT', compressed))
        f.write(_chunk(b'IEND', b''))


def _write_dds(path: str, tex):
    """Write a TxdTexture as an uncompressed RGBA DDS file for nvdecompress."""
    import struct as _st
    w, h = tex.width, tex.height
    # DDS header (128 bytes)
    header = bytearray(128)
    _st.pack_into('<4s', header, 0, b'DDS ')
    _st.pack_into('<I', header, 4, 124)        # header size
    _st.pack_into('<I', header, 8, 0x1 | 0x2 | 0x4 | 0x1000 | 0x8)  # flags
    _st.pack_into('<I', header, 12, h)          # height
    _st.pack_into('<I', header, 16, w)          # width
    _st.pack_into('<I', header, 20, w * 4)      # pitch
    # Pixel format at offset 76
    _st.pack_into('<I', header, 76, 32)         # pf size
    _st.pack_into('<I', header, 80, 0x41)       # pf flags (RGBA)
    _st.pack_into('<I', header, 88, 32)         # RGB bit count
    _st.pack_into('<I', header, 92, 0x000000FF)  # R mask
    _st.pack_into('<I', header, 96, 0x0000FF00)  # G mask
    _st.pack_into('<I', header, 100, 0x00FF0000) # B mask
    _st.pack_into('<I', header, 104, 0xFF000000) # A mask
    _st.pack_into('<I', header, 108, 0x1000)    # caps (texture)

    with open(path, 'wb') as f:
        f.write(header)
        f.write(tex.pixels)


_VEG_NAME_KEYWORDS = {'tree', 'palm', 'bush', 'grass', 'veg_', 'genveg_',
                       'cactus', 'cacti', 'fern', 'ivy', 'plant', 'flower',
                       'hedge', 'weed', 'leaf', 'leaves'}
_VEG_TXD_KEYWORDS = {'gta_tree_', 'gta_proc_', 'gta_cactus', 'veg_',
                      'gta_potplant', 'kbplantsm'}


def _is_vegetation(model_name: str, txd_name: str = "") -> bool:
    """Check if model is vegetation by name and TXD patterns."""
    low = model_name.lower()
    for kw in _VEG_NAME_KEYWORDS:
        if kw in low:
            return True
    if txd_name:
        txd_low = txd_name.lower()
        for kw in _VEG_TXD_KEYWORDS:
            if kw in txd_low:
                return True
    return False


def _sort_map_objects(context, objects: list, ide_models: dict):
    """Sort imported map objects into collections by category."""
    def _get_col(name):
        c = bpy.data.collections.get(name)
        if not c:
            c = bpy.data.collections.new(name)
            context.scene.collection.children.link(c)
        return c

    col_buildings = _get_col("Map_Buildings")
    col_props = _get_col("Map_Props")
    col_vegetation = _get_col("Map_Vegetation")
    col_small = _get_col("Map_Small")
    col_lod = _get_col("Map_LOD")

    # Build name→IDE lookup from ide_models
    name_to_ide = {}
    for mid, obj in ide_models.items():
        name_to_ide[obj.model_name.lower()] = obj

    for obj in objects:
        if obj.type not in ('MESH', 'EMPTY'):
            continue

        # Extract model name: "modelname.dff" or "modelname.dff.001"
        name = obj.name
        # Remove .dff suffix and Blender .NNN suffix
        model_name = name
        if '.dff' in model_name:
            model_name = model_name.split('.dff')[0]

        low = model_name.lower()

        # Find IDE data and set properties
        ide_obj = name_to_ide.get(low)
        if ide_obj and hasattr(obj, 'inu'):
            obj.inu.model_id = ide_obj.model_id
            obj.inu.txd_name = ide_obj.txd_name
            obj.inu.draw_distance = ide_obj.draw_distance
            obj.inu.ide_flags = ide_obj.flags

        dd = ide_obj.draw_distance if ide_obj else 299.0
        txd = ide_obj.txd_name if ide_obj else ""

        # Check LOD
        from .core.ipl import is_lod_name
        if is_lod_name(model_name):
            target = col_lod
        elif _is_vegetation(model_name, txd):
            target = col_vegetation
        elif dd >= 300:
            target = col_buildings
        elif dd >= 100:
            target = col_props
        else:
            target = col_small

        # Move to target collection
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        target.objects.link(obj)

    # Move duplicates (.001, .002 etc) into _Instances sub-collections
    for obj in objects:
        if obj.type != 'MESH':
            continue
        name = obj.name
        # Check for Blender duplicate suffix (.001, .002, etc)
        if '.' not in name:
            continue
        base, suffix = name.rsplit('.', 1)
        if not suffix.isdigit():
            continue
        # This is a duplicate — move to parent_Instances
        parent = obj.users_collection[0] if obj.users_collection else None
        if parent and parent.name.startswith('Map_') and not parent.name.endswith('_Instances'):
            inst_name = parent.name + "_Instances"
            inst_col = bpy.data.collections.get(inst_name)
            if not inst_col:
                inst_col = bpy.data.collections.new(inst_name)
                parent.children.link(inst_col)
            parent.objects.unlink(obj)
            inst_col.objects.link(obj)



def _load_textures_from_cache(tex_dir: str, objects: list) -> bool:
    """Load PNG textures from cache dir and assign to materials of objects.
    Returns True if at least one texture was loaded."""
    loaded = False
    # Cache: already loaded images by name
    _img_cache = {}

    for obj in objects:
        if obj.type != 'MESH' or not obj.data.materials:
            continue
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image is None:
                    tex_name = node.label or ''
                    if not tex_name:
                        # Fallback: material name without .001 suffix
                        tex_name = mat.name.rsplit('.', 1)[0] if '.' in mat.name and mat.name.rsplit('.', 1)[1].isdigit() else mat.name

                    # Check image cache first
                    if tex_name in _img_cache:
                        node.image = _img_cache[tex_name]
                        loaded = True
                        continue

                    png_path = os.path.join(tex_dir, tex_name + '.png')
                    if os.path.isfile(png_path):
                        img = bpy.data.images.get(tex_name)
                        if not img:
                            img = bpy.data.images.load(png_path)
                            img.name = tex_name
                        node.image = img
                        _img_cache[tex_name] = img
                        loaded = True
    return loaded


_map_region_cache = []
_map_region_cache_root = ""


def _get_map_region_items(self, context):
    """Dynamic enum items for map region selector, based on gta.dat paths."""
    global _map_region_cache, _map_region_cache_root

    items = [('ALL', T("Вся карта"), T("Импорт всей карты"))]

    game_root = bpy.path.abspath(getattr(context.scene.inu_settings, 'gtatools_game_root', ''))
    if not game_root or not os.path.isdir(game_root):
        return items

    # Cache: avoid re-parsing on every UI redraw
    if game_root == _map_region_cache_root and _map_region_cache:
        return _map_region_cache

    dat_path = os.path.join(game_root, 'data', 'gta.dat')
    if not os.path.isfile(dat_path):
        return items

    from .core.gta_dat import parse_gta_dat, extract_regions
    try:
        info = parse_gta_dat(dat_path)
        regions = extract_regions(info)
        for r in regions:
            items.append((r, r, f"Region: {r}"))
    except Exception:
        pass

    _map_region_cache = items
    _map_region_cache_root = game_root
    return items


# ID preset selector ─ dynamic EnumProperty
_id_preset_cache = []


def _get_id_preset_items(self, context):
    """Dynamic enum items for the Model ID preset selector."""
    global _id_preset_cache
    from .data.id_manager import list_presets
    names = list_presets()
    items = [(n, n, "") for n in names]
    if not items:
        items = [('default', 'default', '')]
    _id_preset_cache = items
    return _id_preset_cache


def _id_preset_update(self, context):
    """Sync id_manager's active preset whenever the selector changes."""
    from .data.id_manager import set_active_preset
    set_active_preset(self.gtatools_id_preset)


def _id_preset_sync(context):
    """Push the scene's current preset name into id_manager's module state."""
    try:
        from .data.id_manager import set_active_preset
        name = getattr(context.scene.inu_settings, 'gtatools_id_preset', 'default') or 'default'
        set_active_preset(name)
    except Exception:
        pass


def _get_cache_dir():
    """Get cache folder next to .blend file. Falls back to temp."""
    blend = bpy.data.filepath
    if blend:
        d = os.path.join(os.path.dirname(blend), '.inu_cache')
        os.makedirs(d, exist_ok=True)
        return d
    # Unsaved file — use temp
    return tempfile.mkdtemp(prefix='inu_')


def _get_user_config_dir():
    """Return the user-writable data directory for INU Tools.

    Per Blender ToS, addons must not write files inside their own
    folder. See ``tools/user_data.py`` for the full resolver — it
    uses ``bpy.utils.extension_path_user`` (Blender 4.2+) with a
    fallback to ``bpy.utils.user_resource('CONFIG')``.
    """
    from .tools.user_data import get_user_data_dir
    return get_user_data_dir()


def _get_paths_file():
    global _PATHS_FILE
    if _PATHS_FILE is None:
        _PATHS_FILE = os.path.join(_get_user_config_dir(), 'paths.json')
    return _PATHS_FILE

_SAVED_PATH_KEYS = [
    'gtatools_ide_path', 'gtatools_ipl_path', 'gtatools_img_path', 'gtatools_game_root',
    'gtatools_texture_path1', 'gtatools_texture_path2',
]

def _save_paths(self, context):
    """Save paths to config file when any path changes.

    PropertyGroup consolidation moved these props from scene.X to
    scene.inu_settings.X — both reads and writes here go through
    the PropertyGroup. Without this redirection, save would always
    write empty values and the JSON would never accumulate paths."""
    import json
    settings = context.scene.inu_settings
    data = {}
    for key in _SAVED_PATH_KEYS:
        val = getattr(settings, key, '')
        if val:
            data[key] = val
    try:
        with open(_get_paths_file(), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError:
        # Read-only config dir / no disk space. This is an update callback
        # on a path property — it must never interrupt the user's edit.
        pass

def _load_paths(scene):
    """Load saved paths from config file into scene properties.

    Uses scene.inu_settings (post-PropertyGroup-consolidation). The
    pre-1.8.0 path that wrote setattr(scene, key, val) silently
    no-op'd because the props no longer live on scene directly.

    Logs progress to console so the user can diagnose why a path
    didn't restore — silent failures here have been a long-running
    pain point. Catches the bare ``except`` previously used so we
    don't lose timing-related failures."""
    import json
    path = _get_paths_file()
    if not os.path.isfile(path):
        print(f"[INU paths] no paths.json at {path}")
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[INU paths] failed to parse {path}: {e}")
        return

    if scene is None:
        print("[INU paths] _load_paths called with scene=None — skipping")
        return
    settings = getattr(scene, 'inu_settings', None)
    if settings is None:
        print("[INU paths] scene.inu_settings not available yet — skipping")
        return

    restored = []
    for key, val in data.items():
        if key not in _SAVED_PATH_KEYS:
            continue
        if not hasattr(settings, key):
            print(f"[INU paths] settings has no attr {key} — skipping")
            continue
        try:
            setattr(settings, key, val)
            restored.append(key)
        except Exception as e:
            print(f"[INU paths] setattr {key}={val!r} failed: {e}")
    if restored:
        print(f"[INU paths] restored {len(restored)} paths: {', '.join(restored)}")


def _upd_suffix_dff(self, ctx):
    if self.gtatools_suffix_dff and self.gtatools_prefix_dff:
        self.gtatools_prefix_dff = ""

def _upd_suffix_lod(self, ctx):
    if self.gtatools_suffix_lod and self.gtatools_prefix_lod:
        self.gtatools_prefix_lod = ""

def _upd_suffix_col(self, ctx):
    if self.gtatools_suffix_col and self.gtatools_prefix_col:
        self.gtatools_prefix_col = ""

def _upd_prefix_dff(self, ctx):
    if self.gtatools_prefix_dff and self.gtatools_suffix_dff:
        self.gtatools_suffix_dff = ""

def _upd_prefix_lod(self, ctx):
    if self.gtatools_prefix_lod and self.gtatools_suffix_lod:
        self.gtatools_suffix_lod = ""

def _upd_prefix_col(self, ctx):
    if self.gtatools_prefix_col and self.gtatools_suffix_col:
        self.gtatools_suffix_col = ""


def _prewarm_dff_subsystem():
    """One-shot warmup that touches the slow lazily-initialised parts
    of Blender + the DFF import stack so the user's first
    Shift+A → GTA SA Model click doesn't pay the full cold-start cost.

    Cold-start budget on first DFF import:
      • bpy.data.materials/objects RNA init   ~200ms
      • first bpy.ops.object.select_all       ~100ms (undo bootstrap)
      • DFF parser numpy buffer setup         ~100ms
      • bmesh ops first call                  ~100ms

    We force all four here, well before the user clicks anything.
    Returning ``None`` from a timer callback means «don't repeat» —
    this runs exactly once per addon load.
    """
    try:
        # 1) Touch global collections — forces RNA init.
        _ = list(bpy.data.materials)
        _ = list(bpy.data.objects)
        # 2) Pull in the DFF + COL parser modules. They're already
        #    imported eagerly in this __init__.py, but referencing
        #    their hot symbols nudges any lazy submodule binding.
        from .core.dff import read_dff_file  # noqa: F401
        from .core.col import read_col_file  # noqa: F401
        from .ops.dff_import import import_dff  # noqa: F401
        # 3) numpy primitives — touch a small array so numpy's
        #    internal buffer pool gets allocated. The DFF parser
        #    creates large numpy arrays per-mesh; first allocation
        #    is the expensive one.
        try:
            import numpy as _np
            _np.zeros(16, dtype=_np.float32)
        except Exception:
            pass
    except Exception as e:
        print(f"[INU prewarm] skipped: {e}")
    return None  # don't reschedule


def _register_blender_translations():
    """Register the addon's localization with Blender's native i18n
    system so ``bl_label``/``bl_description`` translate dynamically
    when the user switches UI language.

    Background: ``T(...)`` is a regular Python function — when it
    appears as ``bl_label = T("Русский")`` it runs ONCE at class-
    definition time, the result is baked into ``bl_rna``, and never
    updates. Blender's own ``app.translations`` is the only way to
    have static class attributes follow locale changes — Blender
    consults the registered dict via ``pgettext_iface`` at draw time.

    Format: ``{locale: {(context, msg): translation}}``. Blender uses
    different contexts for different UI element types — panels often
    use ``"*"``, operators use ``"Operator"``, property names use
    ``"Property"`` etc. We register the SAME translation under the
    most common contexts so any UI element looking up our message
    finds it regardless of the context Blender picks.
    """
    from .locale import get_translation, available_languages

    # Mirror every entry across the contexts Blender consults for
    # different UI element kinds. Costs a few KiB of dict — negligible.
    contexts = ('*', 'Operator', 'Property', 'WindowManager')

    # Map our locale/<code>.py to Blender locale identifiers.
    # Blender 4.x lists Spanish as both 'es' (generic / Latin America) and
    # 'es_ES' (Spain) — when the user picks "Spanish" in the language
    # dropdown, ``bpy.app.translations.locale`` returns one or the other
    # depending on the OS / Blender build, so register under BOTH. Same
    # idea for English: en_US / en_GB / bare 'en'.
    # Extend this dict when adding new language files.
    LANG_TO_BLENDER_LOCALES = {
        'eng': ('en_US', 'en_GB', 'en'),
        'spa': ('es_ES', 'es'),
    }

    blender_dict = {}
    for lang_code in available_languages():
        blender_locales = LANG_TO_BLENDER_LOCALES.get(lang_code)
        if not blender_locales:
            continue
        lang_dict = get_translation(lang_code)
        if not lang_dict:
            continue
        entries = {}
        for k, v in lang_dict.items():
            for ctx in contexts:
                entries[(ctx, k)] = v
        for blender_locale in blender_locales:
            blender_dict[blender_locale] = entries

    # Метки карт запекания (AO/Diffuse/Shadow/Bevel/Diffuse Lit) должны
    # оставаться английскими: встроенный i18n Blender иначе переводит их в
    # выпадашках (AO→ОО, Shadow→Тень, Bevel→Фаска). Регистрируем identity-
    # перевод (метка → она же) для текущей и распространённых локалей, чтобы
    # перебить встроенный перевод.
    try:
        from .tools.bake import bake_map_enum_items
        force_en = [lbl for (_i, lbl, _d) in bake_map_enum_items()]
        for loc in {get_locale(), 'ru_RU', 'ru', 'es_ES', 'es', 'de_DE',
                    'fr_FR', 'ja_JP', 'zh_CN', 'zh_HANS', 'pt_BR', 'it_IT',
                    'ko_KR', 'uk_UA', 'pl_PL'}:
            d = blender_dict.setdefault(loc, {})
            for lbl in force_en:
                for ctx in contexts:
                    d[(ctx, lbl)] = lbl
    except Exception:
        pass

    if not blender_dict:
        return

    # Idempotent — addon reload may otherwise hit «already registered».
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass
    try:
        bpy.app.translations.register(__name__, blender_dict)
    except Exception as e:
        print(f"[INU translations] register failed: {e}")


def _unregister_blender_translations():
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass


# Ariane ↔ Blender bridge (watcher + reverse-send operators). The panel UI now
# lives as the «Ariane» tab inside GTATOOLS_PT_export_panel (draw_ariane_body).
classes = classes + (
    GTATOOLS_OT_ariane_watch,
    GTATOOLS_OT_ariane_import_now,
    GTATOOLS_OT_ariane_send,
    GTATOOLS_OT_ariane_send_pos,
    GTATOOLS_OT_ariane_create_model,
    GTATOOLS_OT_ariane_bind,
    GTATOOLS_OT_ariane_clear,
    GTATOOLS_OT_ariane_pick_game,
)


def register():
    # Hook the addon's localization into Blender's i18n FIRST — before
    # we touch class bl_descriptions. Once registered, raw Russian
    # strings on bl_label/bl_description get translated dynamically by
    # Blender at draw time when the user is on a non-Russian UI.
    _register_blender_translations()

    # Blender's native i18n only kicks in when "Translate Interface" is ON.
    # This addon's source strings are Russian, so with that toggle OFF a
    # non-Russian user sees raw Russian everywhere (only English-source labels
    # like "Lighting" render, and Blender translates those itself). Auto-enable
    # it for a non-Russian locale so our registered translations actually apply.
    # Russian/empty/unknown locales are left untouched — the source already IS
    # Russian, and we must not force-translate Blender's own UI for them.
    try:
        _loc = (bpy.app.translations.locale or '').lower()
        _view = bpy.context.preferences.view
        if (_loc and not _loc.startswith('ru')
                and not getattr(_view, 'use_translate_interface', True)):
            _view.use_translate_interface = True
    except Exception:                                    # noqa: BLE001
        pass

    # Load our PNG icons into a bpy.utils.previews collection so
    # `icon_value=icon_previews.get('NAME')` works in panel draw().
    from .data import icon_previews
    icon_previews.register()

    # Auto-fill operator tooltip from the class docstring when one
    # isn't explicitly set. We assign the *raw* Russian text rather
    # than T(...) — Blender's translation system above handles the
    # locale switch dynamically. Using T() here would snapshot the
    # text in whatever locale the addon loaded with and freeze it.
    for cls in classes:
        doc = getattr(cls, '__doc__', None)
        if doc and doc.strip():
            cls.bl_description = doc.strip()
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Already registered (addon reload without restart)
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)

    # INU property groups
    bpy.types.Object.inu = bpy.props.PointerProperty(type=INUObjectProps)
    bpy.types.Material.inu = bpy.props.PointerProperty(type=INUMaterialProps)
    # Per-pivot settings for Empty-based animated map object (Kams-style).
    # Lives on each pivot Empty alongside inu_animobj_empty_pivot=True flag.
    bpy.types.Object.inu_animobj_empty_props = bpy.props.PointerProperty(
        type=INUAnimObjEmptyProps)
    # Rig-level settings (lives on root Empty) — holds the «pick a mesh»
    # eyedropper picker + the target enum so users can attach further
    # meshes with one click.
    bpy.types.Object.inu_animobj_rig_settings = bpy.props.PointerProperty(
        type=INUAnimObjRigSettings)

    # Sort materials button in material context menu
    bpy.types.MATERIAL_MT_context_menu.append(_draw_sort_materials_menu)

    # Scene properties — consolidated in INUSceneSettings PropertyGroup.
    # See scene_settings.py for the full field list.
    bpy.utils.register_class(INUSceneSettings)
    bpy.types.Scene.inu_settings = bpy.props.PointerProperty(type=INUSceneSettings)

    # Floater framework — populate the registry of floater instances now
    # that INUSceneSettings is live (instances read scene props by name).
    try:
        from .ops.viewport_floater import register_floaters
        register_floaters()
    except Exception as e:
        print(f"[INU Floater] register_floaters failed: {e}")

    # CollectionProperty fields on non-Scene types stay outside the PG:
    #   - Object.gtatools_fill_colors      — per-object fill history
    #   - WindowManager.gtatools_txd_export_plan{,_index} — transient UI state
    # The 3 Scene-side CollectionProperties (inu_validate_issues,
    # gtatools_binary_ipls, gtatools_img_entries) live inside
    # INUSceneSettings now — see scene_settings.py.
    bpy.types.Object.gtatools_fill_colors = CollectionProperty(type=GTATOOLS_FillColorItem)

    # Per-object V-offsets for Day/Night vcols. Auto-applied via
    # update callback whenever the value changes (Enter pressed).
    # Storage: existing obj["v_offset_<name>"] custom-prop tracks
    # what's currently applied to colors; the callback feeds the new
    # target into apply_brightness_offset which computes the delta.
    def _apply_v_offset_to_attr(obj, attr_name, value):
        if obj is None or obj.type != 'MESH':
            return
        from .tools import compat
        from .tools.prelight import apply_brightness_offset
        mesh = obj.data
        layer = compat.vcol_get(mesh, attr_name)
        if layer is None:
            return
        saved = compat.vcol_active(mesh)
        saved_name = saved.name if saved else None
        try:
            if saved_name != attr_name:
                compat.vcol_active(mesh, layer)
            apply_brightness_offset(obj, value)
        finally:
            if saved_name and saved_name != attr_name:
                saved_layer = compat.vcol_get(mesh, saved_name)
                if saved_layer is not None:
                    compat.vcol_active(mesh, saved_layer)

    def _update_v_offset_day(self, context):
        _apply_v_offset_to_attr(self, "Day", self.gtatools_v_offset_day)

    def _update_v_offset_night(self, context):
        _apply_v_offset_to_attr(self, "Night", self.gtatools_v_offset_night)

    bpy.types.Object.gtatools_v_offset_day = bpy.props.FloatProperty(
        name="V Day",
        description="V-offset для Day vcol — применяется автоматически при изменении",
        default=0.0, min=-100.0, max=100.0,
        update=_update_v_offset_day,
    )
    bpy.types.Object.gtatools_v_offset_night = bpy.props.FloatProperty(
        name="V Night",
        description="V-offset для Night vcol — применяется автоматически при изменении",
        default=0.0, min=-100.0, max=100.0,
        update=_update_v_offset_night,
    )
    bpy.types.WindowManager.gtatools_txd_export_plan = CollectionProperty(
        type=GTATOOLS_TxdExportEntry)
    bpy.types.WindowManager.gtatools_txd_export_plan_index = IntProperty(
        default=0)
    # File scanner results — transient (WM, not Scene): не пишутся в .blend.
    bpy.types.WindowManager.gtatools_scan_results = CollectionProperty(
        type=GTATOOLS_LintIssueItem)
    bpy.types.WindowManager.gtatools_scan_results_index = IntProperty(default=0)
    # Map analyzer results — same shape as scanner, separate collection
    # so the two panels filter / clear independently.
    bpy.types.WindowManager.gtatools_map_analyzer_results = CollectionProperty(
        type=GTATOOLS_LintIssueItem)
    bpy.types.WindowManager.gtatools_map_analyzer_results_index = IntProperty(default=0)
    bpy.types.WindowManager.gtatools_map_analyzer_stats_summary = StringProperty(default="")
    # Texture Browser results — UIList of TextureBrowserItem. Index
    # carries an update callback that lazily decodes the selected
    # texture's pixels into a Blender Image for in-panel preview.
    from .ops.texture_browser_ops import on_index_update as _tb_idx_update
    bpy.types.WindowManager.gtatools_texture_browser_results = CollectionProperty(
        type=GTATOOLS_TextureBrowserItem)
    bpy.types.WindowManager.gtatools_texture_browser_results_index = IntProperty(
        default=0, update=_tb_idx_update)
    # Active-row index for the attached-2DFX template_list (scrollable list).
    bpy.types.WindowManager.inu_2dfx_idx = IntProperty(default=0)

    # Keymap: Shift+T — toggle UV Editor
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('gtatools.toggle_uv_editor', 'T', 'PRESS', shift=True)
        addon_keymaps.append((km, kmi))

    # File > Export / Import menus
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    # Pre-warm DFF import path so the user's first Shift+A → GTA SA
    # Model click is fast. Without this, the first click takes 1-3s
    # because Blender does cold-start work (RNA init for materials/
    # objects collections, first bpy.ops call setting up undo, numpy
    # JIT, bmesh setup) ON the call. Subsequent clicks are instant.
    # Run after a short delay so the UI doesn't stutter during
    # addon load — by the time the user actually hits Shift+A this
    # has long completed.
    bpy.app.timers.register(_prewarm_dff_subsystem,
                            first_interval=2.0)

    # 2DFX billboard rotation timer — start now and restart on file load
    from .ops.fx_preview import start_billboard_timer, start_preview_autobuild
    start_billboard_timer()
    # Keep every 2DFX Empty's preview rig in sync after duplicate/copy/append
    # (persistent timer — survives file loads, no restart needed).
    start_preview_autobuild()
    # Single consolidated load_post handler — see _on_file_load. Legacy
    # data migrations are NOT auto-run on file load anymore; they're a
    # manual operator in the addon preferences
    # (gtatools.run_legacy_migrations).
    bpy.app.handlers.load_post.append(_on_file_load)

    # Drop the UI model-type cache on any depsgraph change (rename / retag /
    # material edit) so panel draw() reads stay correct while idle redraws
    # skip the per-object material scan. Cheap (clears a dict). Marked
    # persistent HERE (not at module level — that would break bpy-less tests).
    from .tools.model_utils import invalidate_model_type_cache
    bpy.app.handlers.persistent(invalidate_model_type_cache)   # set _bpy_persistent
    if invalidate_model_type_cache not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(invalidate_model_type_cache)

    # Same deal for the panel draw() memos (whole-scene scans: ID
    # conflicts, zone/action counts, ...). Separate handler so each cache
    # owns its own invalidation; both skip transform-only batches.
    from .tools import draw_cache as _draw_cache
    bpy.app.handlers.persistent(_draw_cache.bump)
    if _draw_cache.bump not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_draw_cache.bump)

    # One-time migration of user data from the legacy <addons>/INU_Preset/
    # location to bpy.utils.extension_path_user. Idempotent — drops a
    # marker file in the new dir on first success.
    try:
        from .tools.user_data import migrate_legacy_inu_preset, get_user_data_dir
        migrate_legacy_inu_preset()
    except Exception as e:
        print(f"[INU] legacy INU_Preset migration failed: {e}")

    # Register the addon's user data dir with Blender's preset path
    # registry. JSON-based profiles / material / id presets live there;
    # this declares the location through the official API per
    # extensions.blender.org review feedback.
    try:
        _user_data_root = get_user_data_dir()
        if hasattr(bpy.utils, 'register_preset_path'):
            bpy.utils.register_preset_path(_user_data_root)
    except Exception as e:
        print(f"[INU] register_preset_path failed: {e}")

    # Deferred load paths (context.scene not available during register)
    def _deferred_load_paths():
        try:
            _load_paths(bpy.context.scene)
        except Exception as e:
            # One-shot timer at register time: an escaping error dumps a
            # traceback on startup and the saved paths are merely a
            # convenience — report the reason instead of hiding it.
            print(f"[INU] deferred path load failed: {e}")
        return None
    bpy.app.timers.register(_deferred_load_paths, first_interval=0.5)

    # VC Layer System — per-mesh stack of editing layers that compose
    # into Day / Night at export-flatten time. Stored on Mesh (data)
    # so linked-duplicate objects share the same layer stack.
    # Wrapped in try/except so a VCL bug never takes out the whole
    # addon — better to log loudly and keep the rest of the operators
    # functional than to leave the user with nothing.
    try:
        bpy.types.Mesh.gtatools_vc_layers = CollectionProperty(
            type=GTATOOLS_VCLayerItem)
        bpy.types.Mesh.gtatools_vc_active_layer = IntProperty(
            name="Active VC Layer", default=0, min=0,
            update=_vc_on_active_layer_change)
        bpy.types.Mesh.gtatools_vc_edit_target = EnumProperty(
            name=T("Стек"),
            items=[
                ('DAY',   T("Day"),   T("Редактируем Day-стек")),
                ('NIGHT', T("Night"), T("Редактируем Night-стек")),
            ],
            default='DAY',
        )
        bpy.types.Mesh.gtatools_vc_multi_mode = EnumProperty(
            name=T("Multi-edit"),
            description=T("Как групповые слайдеры применяются к выделенным слоям"),
            items=[
                ('ABSOLUTE', T("Absolute"),
                    T("Все выделенные получают одинаковое значение")),
                ('RELATIVE', T("Relative"),
                    T("Все выделенные сдвигаются на одну дельту от текущего")),
            ],
            default='ABSOLUTE',
        )
        bpy.types.Mesh.gtatools_vc_live_preview = BoolProperty(
            name=T("Live preview"),
            description=T("Авто-композиция стека при изменении любого слайдера или мазке кистью"),
            default=False,
            update=_vc_on_live_preview_toggle,
        )
        # Tracks which scope the VCL_PREVIEW buffer currently holds so
        # the panel can show «Preview: Day» / «Preview: Night» and the
        # update hook on layer sliders knows whether a same-scope edit
        # warrants a refresh.
        bpy.types.Mesh.gtatools_vc_preview_scope = EnumProperty(
            name="Preview Scope",
            items=[
                ('DAY',   "Day",   ""),
                ('NIGHT', "Night", ""),
            ],
            default='DAY',
            options={'HIDDEN'},
        )
        # Multi-edit scratch values — separate from per-layer fields so
        # adjusting them doesn't accidentally fire per-layer update
        # callbacks. User clicks "Apply" to push them to selected layers.
        bpy.types.Mesh.gtatools_vc_multi_opacity = FloatProperty(
            name="Multi Opacity", default=1.0, min=0.0, max=1.0,
            subtype='FACTOR')
        bpy.types.Mesh.gtatools_vc_multi_brightness = FloatProperty(
            name="Multi Brightness", default=0.0, min=-1.0, max=1.0,
            subtype='FACTOR')
        bpy.types.Mesh.gtatools_vc_multi_contrast = FloatProperty(
            name="Multi Contrast", default=1.0, min=0.0, max=3.0)
        # Section-expanded toggle for the inline «Слои Vertex Color»
        # block in the prelight panel — moved to INUSceneSettings.
        # gtatools_vc_layers_expanded is part of scene_settings.py.
        # Register only the load_post handler at addon enable; the
        # heavy depsgraph hook is attached lazily on first VCL use
        # (see vc_layers_register_paint_handler in tools/vc_layers.py).
        vc_layers_register_load_handler()
    except Exception as _e:
        import traceback
        print(f"[GTA Tools] VC Layer System register failed: {_e}")
        traceback.print_exc()

    print("[GTA Tools Panel] Addon registered!")


@persistent
def _on_file_load_restore_paths(dummy):
    """Restore saved paths after loading a .blend file."""
    _load_paths(bpy.context.scene)


@persistent
def _on_file_load_resume_toggles(dummy):
    """Re-arm the «Проверка» panel's stateful toggles after a .blend
    load. The toggle Bool flags survive in scene properties, but two
    pieces of runtime state don't:
      * Module globals in object_utils_ops mirror the hide-DFF/LOD/COL/
        SHA Bool flags — refresh them from scene state.
      * The DFF↔LOD↔COL links viewport overlay needs its draw handler
        re-registered if the user saved with it active.
    Without this hook the panel buttons still light up correctly (UI
    reads scene props) but the overlay stays invisible until the user
    clicks the toggle off-and-on again.
    """
    try:
        from .ops import object_utils_ops as _obj
        _obj._sync_module_globals(bpy.context.scene)
    except Exception:
        pass
    try:
        from .ops import map_ops as _map
        s = bpy.context.scene.inu_settings
        _map._links_active = bool(s.gtatools_links_active)
        if _map._links_active and _map._links_draw_handler is None:
            _map._links_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                _map._draw_model_links, (), 'WINDOW', 'POST_VIEW')
    except Exception:
        pass


# ── Migrate stale Modulate Color defaults ────────────────────────
# Property defaults применяются только к новым сценам. Если в .blend
# было сохранено значение со старым дефолтом, оно останется. Этот
# хендлер один раз поднимает старые значения до новых.
_MODULATE_DEFAULT_MIGRATIONS = {
    'gtatools_modulate_gamma': [(0.7, 0.8)],  # old → new
}


@persistent
def _on_file_load_migrate_modulate(dummy):
    """Bump scene's Modulate Color values from stale old defaults to new."""
    for scn in bpy.data.scenes:
        for prop_name, pairs in _MODULATE_DEFAULT_MIGRATIONS.items():
            try:
                cur = float(getattr(scn, prop_name))
            except (AttributeError, TypeError):
                continue
            for old, new in pairs:
                if abs(cur - old) < 1e-6:
                    setattr(scn, prop_name, new)
                    break


@persistent
def _on_file_load_migrate_prelight_nodes(dummy):
    """Мигрировать старый тяжёлый граф превью прилайта (8 нод с Modulate) на
    новый минимальный (VertexColor × текстура). Старые .blend держат в
    материалах лишние modulate-ноды — пересобираем превью: если оно было
    активно — строим минимальный граф, иначе удаляем остатки. Дёшево —
    трогаем только объекты, где реально есть наши preview-ноды."""
    try:
        from .tools.prelight import (setup_prelight_preview,
                                     PRELIGHT_LEGACY_NODES as LEGACY)
    except Exception:
        return
    # LEGACY — только ноды старого modulate-графа. Раньше в этот список по
    # ошибке входила Prelight_Mix — нода АКТУАЛЬНОГО превью, из-за чего
    # каждое открытие .blend «мигрировало» вообще все объекты с превью и
    # пересобирало их материалы (на карте — тысячи перекомпиляций шейдеров).
    for obj in bpy.data.objects:
        if obj.type != 'MESH' or obj.data is None:
            continue
        touched = False
        active = False
        for slot in obj.material_slots:
            m = slot.material
            if not m or not m.use_nodes or m.node_tree is None:
                continue
            ns = m.node_tree.nodes
            if any(ns.get(nm) for nm in LEGACY):
                touched = True
                if m.get('prelight_preview_active'):
                    active = True
        if touched:
            try:
                setup_prelight_preview(obj, enable=bool(active))
            except Exception as exc:
                print(f"[INU] prelight node migration failed for "
                      f"{obj.name}: {exc}")


@persistent
def _on_file_load_migrate_scene_settings(dummy):
    """Migrate Scene-level ``gtatools_*`` properties saved in .blend files
    (pre-Step 9) into the new ``scene.inu_settings`` PropertyGroup.

    Old saves had each setting registered directly on Scene; new code
    expects them under ``scene.inu_settings.<name>``. Without this
    handler, opening an old .blend would silently lose every saved path,
    UI toggle, and slider value.
    """
    # CollectionProperty fields can't be migrated by attribute copy —
    # each item would need to be re-added one-by-one. Users can rescan
    # binary IPLs / refresh IMG list / re-validate to repopulate.
    SKIP = {'gtatools_binary_ipls', 'gtatools_img_entries', 'inu_validate_issues',
            'gtatools_bake_layers'}
    for scene in bpy.data.scenes:
        settings = getattr(scene, 'inu_settings', None)
        if settings is None:
            continue
        for key in list(scene.keys()):
            if not key.startswith('gtatools_'):
                continue
            if key in SKIP:
                continue
            if not hasattr(settings, key):
                continue
            try:
                value = scene[key]
                # IDProperty arrays come back as IDPropertyArray — coerce
                # to plain list so the PropertyGroup setter accepts.
                if hasattr(value, 'to_list'):
                    value = value.to_list()
                setattr(settings, key, value)
                del scene[key]
            except Exception:
                pass


@persistent
def _on_file_load_sync_pipeline_prev(dummy):
    """Sync ``inu_prev_pipeline_internal`` со значением ``gtatools_export_pipeline``
    при загрузке .blend, чтобы первое переключение пайплайна в старой
    сцене корректно зафиксировало «откуда» сохранять flag-snapshot.
    Без этого save-в-старый-slot пропускается, и юзер теряет first-time
    edits при возврате на исходный пайплайн."""
    for scene in bpy.data.scenes:
        settings = getattr(scene, 'inu_settings', None)
        if settings is None:
            continue
        try:
            settings.inu_prev_pipeline_internal = settings.gtatools_export_pipeline
        except Exception:
            pass


@persistent
def _on_file_load_migrate_2dfx_size(dummy):
    """Migrate legacy ``obj['2dfx_corona_size']`` and ``obj['2dfx_shadow_size']``
    custom IDProperties to the new ``inu.corona_size_2dfx`` /
    ``inu.shadow_size_2dfx`` PropertyGroup fields.

    Custom props can't have ``update=`` callbacks, which forced a depsgraph
    handler for live preview. Migrating to PropertyGroup fields lets the
    update fire only on the property itself.
    """
    for obj in bpy.data.objects:
        if obj.type != 'EMPTY':
            continue
        inu = getattr(obj, 'inu', None)
        if not inu or inu.type != '2DFX':
            continue
        if '2dfx_corona_size' in obj:
            try:
                inu.corona_size_2dfx = float(obj['2dfx_corona_size'])
                del obj['2dfx_corona_size']
            except (TypeError, ValueError):
                pass
        if '2dfx_shadow_size' in obj:
            try:
                inu.shadow_size_2dfx = float(obj['2dfx_shadow_size'])
                del obj['2dfx_shadow_size']
            except (TypeError, ValueError):
                pass


@persistent
def _on_file_load_restart_timer(dummy):
    """Restart billboard timer after loading a new .blend file."""
    print("[2DFX] load_post handler fired — scheduling timer restart in 1s...")
    def _delayed_start():
        print("[2DFX] Delayed start — restarting billboard timer now")
        from .ops.fx_preview import start_billboard_timer
        start_billboard_timer()
        return None
    bpy.app.timers.register(_delayed_start, first_interval=1.0)


@persistent
def _on_file_load_floater(dummy):
    """Re-invoke the viewport floater modal if the saved scene had it on.

    Delayed via timer because at load_post fire-time the window manager
    may not yet have its VIEW_3D areas hooked up — invoking the modal
    immediately occasionally drops the registration.
    """
    def _delayed():
        from .ops.viewport_floater import restore_floater_if_visible
        restore_floater_if_visible()
        return None
    bpy.app.timers.register(_delayed, first_interval=0.5)


def _on_file_load(dummy):
    """Single consolidated load_post handler.

    Restores only the runtime state Blender doesn't persist across
    .blend loads — saved paths, panel toggles, the export-pipeline
    snapshot tracker, the 2DFX billboard timer, the viewport floater,
    and the IK follow-handler. Legacy *data migrations* are
    deliberately NOT run here: they live as a manual operator in the
    addon preferences (``gtatools.run_legacy_migrations``) so opening a
    file never forces every user through one-off conversion passes.
    One handler instead of nine also keeps registration fast and the
    app-handler list clean (extensions.blender.org review feedback).
    """
    for fn in (_on_file_load_restore_paths,
               _on_file_load_resume_toggles,
               _on_file_load_sync_pipeline_prev,
               _on_file_load_restart_timer,
               _on_file_load_floater,
               _ik_on_file_load):
        try:
            fn(dummy)
        except Exception as e:
            print(f"[INU] load handler {getattr(fn, '__name__', '?')} "
                  f"failed: {e}")


def _bake_defensive_sweep():
    """Удалить осколки bake-подсистемы после hard-crash (finally не
    срабатывает при сегфолте): неиспользуемые INU_Bevel_Mat /
    INU_bake_placeholder. НЕ трогает 'Prelight_Lights' — та коллекция
    принадлежит tools/prelight.py (C3 из плана)."""
    for mat_name in ('INU_Bevel_Mat', 'INU_bake_placeholder', 'INU_BakePreview'):
        m = bpy.data.materials.get(mat_name)
        if m is not None and m.users == 0:
            try:
                bpy.data.materials.remove(m)
            except Exception:
                pass


def unregister():

    # Stop the Ariane watcher timer so it doesn't outlive the addon reload.
    try:
        _ariane_stop_watch()
    except Exception:
        pass

    # Drop our locale dict before any classes go away — keeps Blender's
    # translation table clean across addon reloads.
    _unregister_blender_translations()

    # Bake subsystem: подчистить осколки INU_bake_* / INU_Bevel_* после
    # возможного hard-crash. 'Prelight_Lights' не трогаем (C3).
    try:
        _bake_defensive_sweep()
    except Exception:
        pass

    # Release the custom icon preview collection.
    try:
        from .data import icon_previews
        icon_previews.unregister()
    except Exception as e:
        print(f"[INU] icon_previews unregister failed: {e}")

    # Drop the floater GPU icon texture cache. Without this, a
    # disable/enable cycle leaves stale textures (and the dict-non-empty
    # short-circuit in _load_icons()) so new PNGs in data/icons/native/
    # never get loaded — user has to fully restart Blender.
    try:
        from .ops.floater import gpu_shaders as _gs
        _gs._free_icons()
    except Exception as e:
        print(f"[INU] floater _free_icons failed: {e}")

    # Unregister the addon's user data dir from Blender's preset path
    # registry (paired with register_preset_path call in register()).
    try:
        from .tools.user_data import get_user_data_dir
        if hasattr(bpy.utils, 'unregister_preset_path'):
            bpy.utils.unregister_preset_path(get_user_data_dir())
    except Exception as e:
        print(f"[INU] unregister_preset_path failed: {e}")

    # 2DFX billboard timer
    from .ops.fx_preview import (stop_billboard_timer, stop_preview_autobuild,
                                 stop_road_sign_timer)
    stop_billboard_timer()
    stop_preview_autobuild()
    stop_road_sign_timer()

    # IFP live preview — unregister frame-change handler so reload
    # doesn't leave a stale callable pointing at the old module.
    try:
        from .ops.ifp_import import preview_stop
        preview_stop()
    except Exception:
        pass

    # Consolidated load_post handler (replaces the former nine).
    if _on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_file_load)

    # UI model-type cache invalidator.
    try:
        from .tools.model_utils import invalidate_model_type_cache
        if invalidate_model_type_cache in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(invalidate_model_type_cache)
    except Exception:
        pass

    # Panel draw() memo invalidator.
    try:
        from .tools import draw_cache as _draw_cache
        if _draw_cache.bump in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(_draw_cache.bump)
        _draw_cache.clear()
    except Exception:
        pass

    # File > Export / Import menus
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    del bpy.types.Object.inu
    del bpy.types.Material.inu
    if hasattr(bpy.types.Object, 'inu_animobj_empty_props'):
        del bpy.types.Object.inu_animobj_empty_props
    if hasattr(bpy.types.Object, 'inu_animobj_rig_settings'):
        del bpy.types.Object.inu_animobj_rig_settings

    bpy.types.MATERIAL_MT_context_menu.remove(_draw_sort_materials_menu)

    # Remove keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    # Remove COL Light preview handlers
    for h in _col_light_mod._col_light_preview_handlers:
        bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
    _col_light_mod._col_light_preview_handlers.clear()
    _col_light_mod._col_light_preview_active = False

    # Remove Water Limits overlay handlers
    for h in _water_geo_mod._water_limits_handlers:
        bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
    _water_geo_mod._water_limits_handlers.clear()
    _water_geo_mod._water_limits_active = False

    # Remove model links draw handler — state lives in ops/map_ops.py
    # (a `global` declaration here would point at a non-existent
    # __init__.py-level binding and crash with NameError on unregister).
    from .ops import map_ops as _map_ops_mod
    if _map_ops_mod._links_draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(
            _map_ops_mod._links_draw_handler, 'WINDOW')
        _map_ops_mod._links_draw_handler = None
    _map_ops_mod._links_active = False

    # Remove UV grid draw handler
    if _uv._uv_grid_draw_handler is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_uv._uv_grid_draw_handler, 'WINDOW')
        _uv._uv_grid_draw_handler = None
    _uv._uv_grid_visible = False

    # Viewport Floater — drop draw handler + reset module state
    try:
        from .ops.viewport_floater import floater_cleanup
        floater_cleanup()
    except Exception as e:
        print(f"[INU Floater] cleanup failed: {e}")

    # Scene properties — single PointerProperty + PropertyGroup class.
    try:
        del bpy.types.Scene.inu_settings
    except (AttributeError, RuntimeError):
        pass
    try:
        bpy.utils.unregister_class(INUSceneSettings)
    except (RuntimeError, ValueError):
        pass

    # CollectionProperty fields outside the PG (Object / WindowManager).
    try:
        del bpy.types.WindowManager.gtatools_txd_export_plan
        del bpy.types.WindowManager.gtatools_txd_export_plan_index
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.gtatools_scan_results
        del bpy.types.WindowManager.gtatools_scan_results_index
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.gtatools_map_analyzer_results
        del bpy.types.WindowManager.gtatools_map_analyzer_results_index
        del bpy.types.WindowManager.gtatools_map_analyzer_stats_summary
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.inu_2dfx_idx
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.gtatools_texture_browser_results
        del bpy.types.WindowManager.gtatools_texture_browser_results_index
    except Exception:
        pass
    try:
        del bpy.types.Object.gtatools_fill_colors
    except (AttributeError, RuntimeError):
        pass
    try:
        del bpy.types.Object.gtatools_v_offset_day
        del bpy.types.Object.gtatools_v_offset_night
    except (AttributeError, RuntimeError):
        pass

    # Stop particle sim timer and drop meshes (the property itself lives
    # in INUSceneSettings now, but the timer needs explicit shutdown).
    try:
        from .ops import particle_sim
        particle_sim.stop_simulation()
    except Exception:
        pass

    # IK Rig — drop the lazy depsgraph/frame_change follow handler. The
    # load_post hook is wired into the consolidated _on_file_load handler
    # removed above, so there's no separate load_post entry to detach.
    try:
        _ik_unregister_follow_handler()
    except Exception:
        pass

    # VC Layer System — guarded delete so cleanup never blocks unregister.
    try:
        vc_layers_unregister_handlers()
    except Exception:
        pass
    for _attr in ('gtatools_vc_layers', 'gtatools_vc_active_layer',
                  'gtatools_vc_edit_target', 'gtatools_vc_multi_mode',
                  'gtatools_vc_live_preview',
                  'gtatools_vc_preview_scope',
                  'gtatools_vc_multi_opacity',
                  'gtatools_vc_multi_brightness',
                  'gtatools_vc_multi_contrast'):
        try:
            delattr(bpy.types.Mesh, _attr)
        except (AttributeError, RuntimeError):
            pass

    # Drop legacy phantom props from .blend files saved by old addon
    # versions (kept to keep updates clean across saves).
    for _attr in (
        'gtatools_modulate_preview',
        'gtatools_modulate_color',
        'gtatools_modulate_postfx1_color',
        'gtatools_modulate_postfx1_alpha',
        'gtatools_modulate_postfx2_color',
        'gtatools_modulate_postfx2_alpha',
    ):
        try:
            delattr(bpy.types.Scene, _attr)
        except (AttributeError, RuntimeError):
            pass

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("[GTA Tools Panel] Addon unregistered!")
