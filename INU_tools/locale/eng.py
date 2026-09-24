# English translation for INU_tools
# Keys are Russian strings used in the addon code.
# Values are English translations.

LANG = {
    "Sync импорт": "Sync import",
    "Импортировать 2DFX": "Import 2DFX",
    "Импорт:": "Import:",
    "Импорт из игры:": "Import from game:",
    "Платформа:": "Platform:",
    "текстуры из файлов": "textures from files",
    "Найти LOD автоматически": "Find LODs automatically",
    "Поиск LOD": "Find LOD",
    "Выдели модели": "Select models",
    "LOD найден: {0}, не найдено: {1}": "LODs found: {0}, not found: {1}",
    "В IDE, изменено: {0}": "In IDE, changed: {0}",
    "Тайм-цикл вкл/выкл": "Time-cycle on/off",
    "Включить или выключить тайм-цикл целиком: ВКЛ — применить к сцене (свет, туман, игровой вид прилайта), ВЫКЛ — вернуть сцену как было (материалы в PBR, мир и композитор чистые)": "Turn the whole time-cycle on or off: ON — apply to the scene (light, fog, prelight game look); OFF — restore the scene as it was (materials back to PBR, world and compositor clean)",
    "Игровой вид: моделей %d, материалов %d — %s": "Game look: %d models, %d materials — %s",
    "INU: Сгенерировать COL": "INU: Generate COL",
    "Сгенерировать коллизию (<имя>_COL) из выделенной модели: выпуклая оболочка или габаритный бокс. Меш редактируемый, дальше идёт в COL-экспорт.": "Generate collision (<name>_COL) from the selected model: a convex hull or a bounding box. The mesh is editable and goes on to COL export.",
    "На какой высоте небо доходит до цвета зенита. 1.0 растягивает переход на всю полусферу, и в кадре виден только горизонтный цвет": "At what height the sky reaches the zenith color. 1.0 stretches the transition across the whole hemisphere, so only the horizon color shows in frame",
    "Где начинается небо — как доля клипа вьюпорта. Всё ближе получает туман, дальше — небо (туман не кладём, градиент цел). Меньше — небо начинается раньше (если градиент пропал), больше — туман тянется дальше (если дальний край торчит без тумана)": "Where the sky begins — as a fraction of the viewport clip. Everything closer gets fog, farther is sky (no fog, the gradient stays intact). Lower — the sky starts sooner (if the gradient disappeared); higher — the fog reaches farther (if the far edge sticks out without fog)",
    "Пропускать размещения, которые в сцене уже есть: совпал ID модели и позиция. Удобно доимпортировать соседний кусок карты, не плодя копии": "Skip placements already in the scene: matching model ID and position. Handy for importing an adjacent map piece without spawning duplicates",
    "Live: время суток (ползунок таймцикла) и погода синхронизируются с ariane в обе стороны. Ведущий — активное окно (как у камеры): крутишь в ariane → двигается ползунок в Blender, и наоборот. Погода по индексу (обе стороны читают один timecyc.dat). Плюс живая правка таймцикла: меняешь поля среза (небо/солнце/туман/цвета) — ariane применяет их в тот же кадр. Требует включённого watcher": "Live: time of day (the time-cycle slider) and weather sync with Ariane both ways. The leader is the active window (like the camera): drag in Ariane → the slider moves in Blender, and vice versa. Weather by index (both sides read the same timecyc.dat). Plus live time-cycle editing: change slice fields (sky/sun/fog/colors) — Ariane applies them in the same frame. Requires the watcher enabled",
    "Из какой игры импортируем (когда Auto выключен)": "Which game to import from (when Auto is off)",
    "Метка размещения при импорте карты: «имя модели|x|y|z». По ней «Без дублей» узнаёт, что этот кусок карты уже стоит в сцене": "Placement tag from map import: «model name|x|y|z». «No duplicates» uses it to know this map piece is already in the scene",
    "Без дублей": "No duplicates",
    "уже есть в сцене": "already in the scene",
    "Определять игру автоматически по RW-версии файла": "Detect the game automatically from the file's RW version",
    "Синхр. время/погоду": "Sync time/weather",
    "Вода": "Water",
    "Небо с (× клип)": "Sky starts at (× clip)",
    "Флаги IDE": "IDE Flags",
    "Выдели модель": "Select a model",
    "IPL Проверка: связано новых {0}, ОК {1}, исправлено {2}, удалено {3}, orphan {4}": "IPL Check: newly linked {0}, OK {1}, repaired {2}, removed {3}, orphan {4}",
    "Нет мешей с вершинными цветами — включать нечего": "No meshes with vertex colors — nothing to enable",
    "Тайм-цикл включён": "Time-cycle ON",
    "Тайм-цикл выключен": "Time-cycle OFF",
    "Создавать пустышки-эффекты 2DFX из DFF (лампы/короны, частицы, ped attractor, sun glare, знаки и т.д.). Выключи, чтобы импортировать модель без эффектов": "Create 2DFX effect empties from the DFF (lamps/coronas, particles, ped attractor, sun glare, signs, etc.). Turn off to import the model without effects",
    "Сгенерировать COL": "Generate COL",
    "Тип коллизии": "Collision type",
    "Выпуклая оболочка": "Convex hull",
    "Выпуклая оболочка вокруг модели — точнее по форме, чем бокс": "A convex hull around the model — closer to the shape than a box",
    "Габаритный бокс": "Bounding box",
    "Осевой габаритный бокс — самый дешёвый, для простых/дальних моделей": "An axis-aligned bounding box — the cheapest, for simple/distant models",
    "Коллизия создана: {0}": "Collision created: {0}",
    "Нет модели для коллизии": "No model to build collision from",
    "Авто-LOD из основной модели": "Auto-LOD from main model",
    "Если LOD-меша (<имя>_LOD) в сцене нет — отправить копию основной модели как дальний LOD. Выключи, если у модели LOD не предусмотрен": "If there is no LOD mesh (<name>_LOD) in the scene, send a copy of the main model as the distant LOD. Turn off if the model is not meant to have a LOD",
    "{0}: нет LOD — авто из основной модели": "{0}: no LOD — auto from the main model",
    "Пустая COL если нет своей": "Empty COL when none",
    "Если у группы нет реального _COL: ВКЛ — пустая габаритная COL (без граней, bounds от меша); ВЫКЛ — COL из геометрии основной модели. В обоих случаях в сцене создаётся объект _COL для правки": "If the group has no real _COL: ON — an empty bounding-box COL (no faces, bounds from the mesh); OFF — a COL from the main model's geometry. In both cases a _COL object is created in the scene for editing",
    "{0}: нет своей COL — будет создана автоматически": "{0}: no own COL — one will be created automatically",
    "В папке ariane найдена игра {0}, а сцена настроена на {1} — файлы уйдут в формате {1}. Переключи игру во вкладке GTA Tools.": "The ariane folder holds {0}, but the scene is set to {1} — files will be written in {1} format. Switch the game in the GTA Tools tab.",
    "Игра: {0} — DFF/TXD RW {1}, COL{2}, TXD {3}": "Game: {0} — DFF/TXD RW {1}, COL{2}, TXD {3}",
    "{0}: id моделей до {1} (сток) — выше нужен limit adjuster; имя модели ≤ {2} символов": "{0}: model ids up to {1} (stock) — beyond that needs a limit adjuster; model name ≤ {2} chars",
    # ── Enum items / raw text / reports localized by audit ──
    "Обычный экспорт/импорт в файлы": "Normal export/import to files",
    "Мост с запущенной ariane (live-обмен)": "Bridge with running Ariane (live exchange)",
    "rot = rot @ flip (относительно самой кости)": "rot = rot @ flip (relative to the bone itself)",
    "rot = flip @ rot (относительно арматуры)": "rot = flip @ rot (relative to the armature)",
    "Точечный источник света / корона / неон.\nУличные фонари, фары машин, светящиеся окна зданий, неоновые вывески. В игре рисуется как 2D-корона с альфа-блендингом, видна на расстоянии. Поддерживает цвет, затухание, мерцание, типы (street/lamp/police), вкл/выкл по времени суток.": "Point light source / corona / neon.\nStreet lamps, car headlights, glowing building windows, neon signs. In-game it is drawn as a 2D corona with alpha blending, visible from a distance. Supports color, falloff, flicker, types (street/lamp/police), on/off by time of day.",
    "Точка привязки эмиттера частиц из models/effects.fxp.\nДым из труб, всплески воды у причалов, искры на электрических столбах, огонь в бочках, пар из вентиляции. Сама система частиц выбирается по имени (prt_smoke_huge, water_splash, prt_fire и т.д.) из effects.fxp — там 82 системы.": "Particle emitter anchor point from models/effects.fxp.\nSmoke from chimneys, water splashes at piers, sparks on power poles, fire in barrels, steam from vents. The particle system itself is chosen by name (prt_smoke_huge, water_splash, prt_fire, etc.) from effects.fxp - 82 systems there.",
    "Точка интереса для NPC.\nПешеходы подходят к этой точке и проигрывают анимацию: банкомат (ATM), скамейка, продавец у ларька, граффити, точка «осмотреться». Имеет тип поведения (SCRIPTED/SEAT/STOP/TRIGGER_SCRIPT/LOOK_AT/SCRIPTED_2/PARK/STEP), направление куда поворачиваться, опционально model_id определённого ped'а.": "Point of interest for NPCs.\nPedestrians walk up to this point and play an animation: ATM, bench, stall vendor, graffiti, a 'look around' spot. Has a behavior type (SCRIPTED/SEAT/STOP/TRIGGER_SCRIPT/LOOK_AT/SCRIPTED_2/PARK/STEP), a facing direction, and optionally the model_id of a specific ped.",
    "Точка отражения солнца на поверхности.\nЯркий блик когда камера смотрит в сторону солнца через эту точку. Используется на крышах автомобилей, стёклах окон, металлических деталях. Рисуется как корона с альфа-блендингом, размер и яркость зависят от угла между направлением точки и солнцем.": "Sun reflection point on a surface.\nA bright glint when the camera looks toward the sun through this point. Used on car roofs, window glass, metal parts. Drawn as a corona with alpha blending; size and brightness depend on the angle between the point's direction and the sun.",
    "Вход/Выход (интерьер)": "Enter/Exit (interior)",
    "Маркер входа/выхода в интерьер (тип 6).\nПара маркеров: вход на позиции объекта и выход на exit-позиции. Хранит угол поворота маркеров, радиус, номер интерьера, имя интерьера, время вкл/выкл. Раньше жил в IPL (секция enex), в SA — прямо в DFF.": "Interior enter/exit marker (type 6).\nA pair of markers: the entry at the object's position and the exit at the exit position. Stores the marker rotation angle, radius, interior number, interior name, on/off time. It used to live in the IPL (enex section); in SA it is right in the DFF.",
    "Дорожный знак (текст)": "Road sign (text)",
    "Текстовый знак на меше (тип 7).\nДо 4 строк текста, рисуемых движком поверх геометрии (указатели улиц). Хранит размер, поворот и флаги (число строк, макс. символов, цвет: белый/чёрный/серый/красный).": "Text sign on a mesh (type 7).\nUp to 4 lines of text drawn by the engine over the geometry (street signs). Stores the size, rotation and flags (line count, max characters, color: white/black/grey/red).",
    "Эскалатор (тип 10).\nЗадаёт три точки — низ, верх и конец — и направление (вверх/вниз). Движок двигает педов по этой траектории. Используется в аэропортах и торговых центрах SA.": "Escalator (type 10).\nDefines three points - bottom, top and end - and a direction (up/down). The engine moves peds along this path. Used in SA airports and malls.",
    "Raw (сохранённый)": "Raw (preserved)",
    "Нередактируемый 2DFX-эффект, сохранённый байт-в-байт при импорте (типы 8 trigger / 9 cover и прочие). Не меняй вручную — служит для точного round-trip.": "Non-editable 2DFX effect preserved byte-for-byte on import (types 8 trigger / 9 cover and others). Do not edit by hand - it exists for an exact round-trip.",
    "Оригинал": "Original",
    "Полный запечённый размер": "Full baked size",
    "В 2 раза меньше": "2x smaller",
    "В 4 раза меньше": "4x smaller",
    "В 8 раз меньше": "8x smaller",
    "Оставить каждый N-ный из выделенных ключей, остальные удалить": "Keep every Nth selected key, delete the rest",
    "Авто (по ошибке)": "Auto (by error)",
    "Удалить избыточные ключи, лежащие близко к интерполяции между соседями (Blender'овский decimate ERROR-mode)": "Remove redundant keys that lie close to the interpolation between neighbors (Blender's decimate ERROR mode)",
    "Ступенька": "Step",
    "Все каналы (local)": "All channels (local)",
    "Обработать все F-curve в bone-local координатах (rotation, location, любые свойства)": "Process all F-curves in bone-local coordinates (rotation, location, any properties)",
    "Только translation, по мировой оси X (per-frame depsgraph eval, медленнее)": "Translation only, along the world X axis (per-frame depsgraph eval, slower)",
    "Только translation, по мировой оси Y": "Translation only, along the world Y axis",
    "Только translation, по мировой оси Z": "Translation only, along the world Z axis",
    "Крона": "Canopy",
    "Только затенение кроны": "Canopy shading only",
    "Только цвет листвы": "Foliage color only",
    "Всё": "Everything",
    "Затенение + цвет": "Shading + color",
    "Хром": "Chrome",
    "Нет .cst файлов": "No .cst files",
    # ── Operator docstring tooltips localized by audit ──
    "Однократно мигрировать данные из старых версий аддона.\n\n    Конвертирует текущий .blend: старые дефолты Modulate Color, тяжёлый\n    граф превью прилайта → минимальный, кастом-свойства 2DFX-размеров →\n    поля PropertyGroup, Scene-свойства pre-Step-9 → scene.inu_settings.\n    Запускать только если открыли старый проект — на новых сценах не\n    нужно.": "One-time migration of data from older addon versions. Converts the current .blend: old Modulate Color defaults, heavy prelight-preview graph -> minimal, 2DFX-size custom props -> PropertyGroup fields, pre-Step-9 Scene props -> scene.inu_settings. Run only when you open an old project - not needed on new scenes.",
    "Однократно мигрировать данные из старых версий аддона.\n\nКонвертирует текущий .blend: старые дефолты Modulate Color, тяжёлый\nграф превью прилайта → минимальный, кастом-свойства 2DFX-размеров →\nполя PropertyGroup, Scene-свойства pre-Step-9 → scene.inu_settings.\nЗапускать только если открыли старый проект — на новых сценах не\nнужно.": "One-time migration of data from older addon versions. Converts the current .blend: old Modulate Color defaults, heavy prelight-preview graph -> minimal, 2DFX-size custom props -> PropertyGroup fields, pre-Step-9 Scene props -> scene.inu_settings. Run only when you open an old project - not needed on new scenes.",
    "Собрать альфа-материалы сцены (или выделения) в список по\n    выбранному режиму фильтра.": "Collect the scene's (or selection's) alpha materials into a list by the chosen filter mode.",
    "Собрать альфа-материалы сцены (или выделения) в список по\nвыбранному режиму фильтра.": "Collect the scene's (or selection's) alpha materials into a list by the chosen filter mode.",
    "Применить выбранный режим прозрачности ко всем материалам из\n    списка.": "Apply the chosen transparency mode to every material in the list.",
    "Применить выбранный режим прозрачности ко всем материалам из\nсписка.": "Apply the chosen transparency mode to every material in the list.",
    "Выделить объекты, использующие материалы из списка.": "Select objects that use the materials from the list.",
    "Экспортировать animated map object одним кликом: пишет\n<base>.dff + <base>.ifp в выбранную папку. Опционально дописывает\nили обновляет anim-запись в указанном IDE-файле.": "Export an animated map object in one click: writes\n    <base>.dff + <base>.ifp to the chosen folder. Optionally appends\n    or updates the anim entry in the specified IDE file.",
    "Проверить Empty-rig: есть ли root + pivot, корректные BoneID,\nAction на pivot, припарентенные меши. Сообщает первую ошибку.": "Validate an Empty-rig: presence of root + pivot, correct BoneIDs,\n    Action on the pivot, parented meshes. Reports the first issue found.",
    "Припарентить выделенные меши к pivot Empty-rig'а — меш будет\nкрутиться вместе с rig'ом. Если rig'ов несколько, используется\nтот в иерархии которого уже находится активный объект.": "Parent selected meshes to the rig pivot — they will rotate with\n    the rig. If several rigs exist, the one containing the active\n    object is preferred.",
    "Добавить ещё один pivot Empty в существующий Empty-rig — для\n    моделей с несколькими анимированными частями (например мельница +\n    противовес). Каждому pivot'у выдаётся свой BoneID и Action.\n\n    Если выделен меш — он сразу парентится к новому pivot'у.\n    Если выделена кость старого pivot'а или root — новый pivot\n    создаётся как ребёнок root'а того же rig'а.\n    ": "Add another pivot Empty to an existing Empty-rig - for models with several animated parts (e.g. windmill + counterweight). Each pivot gets its own BoneID and Action. If a mesh is selected it is parented to the new pivot right away. If an old pivot bone or root is selected, the new pivot is created as a child of that rig's root.",
    "Добавить ещё один pivot Empty в существующий Empty-rig — для\nмоделей с несколькими анимированными частями (например мельница +\nпротивовес). Каждому pivot'у выдаётся свой BoneID и Action.\n\nЕсли выделен меш — он сразу парентится к новому pivot'у.\nЕсли выделена кость старого pivot'а или root — новый pivot\nсоздаётся как ребёнок root'а того же rig'а.": "Add another pivot Empty to an existing Empty-rig - for models with several animated parts (e.g. windmill + counterweight). Each pivot gets its own BoneID and Action. If a mesh is selected it is parented to the new pivot right away. If an old pivot bone or root is selected, the new pivot is created as a child of that rig's root.",
    "Припарентить выделенные меши к root Empty-rig'а — они останутся\nстатичными как 'основание' (как корпус мельницы без лопастей).": "Parent selected meshes to the rig root — they stay static as the\n    base (e.g. the windmill body without its blades).",
    "Создать НОВУЮ модель в ariane из выделенной геометрии. Шлёт DFF+TXD, реальные\n    COL/LOD если есть (<имя>_COL / <имя>_LOD), иначе авто-COL. Новый id, Mod Loader.": "Create a NEW model in Ariane from the selected geometry. Sends DFF+TXD, real COL/LOD if present (<name>_COL / <name>_LOD), otherwise auto-COL. New id, Mod Loader.",
    "Создать НОВУЮ модель в ariane из выделенной геометрии. Шлёт DFF+TXD, реальные\nCOL/LOD если есть (<имя>_COL / <имя>_LOD), иначе авто-COL. Новый id, Mod Loader.": "Create a NEW model in Ariane from the selected geometry. Sends DFF+TXD, real COL/LOD if present (<name>_COL / <name>_LOD), otherwise auto-COL. New id, Mod Loader.",
    "Отправить выделенные модели обратно в ariane (DFF+TXD+позиция, live-reload).": "Send the selected models back to Ariane (DFF+TXD+position, live-reload).",
    "Обновить только позицию выделенных моделей в ariane (без экспорта DFF/TXD).": "Update only the position of the selected models in Ariane (without exporting DFF/TXD).",
    "Привязать модели к УЖЕ существующим инстансам Ariane — БЕЗ дублей.\n\n    Для сцены, которая уже стоит в карте Ariane (импортировал из файлов игры,\n    а не через мост): «Экспорт → Ariane» пытался бы СОЗДАТЬ дубли. Эта кнопка\n    вместо создания МАТЧИТ объекты с инстансами Ariane по модель+позиция и\n    вешает их guid/iid → после этого live-синк работает.\n\n    Ariane выгружает свой список инстансов в <bridge>\\instances.txt, строка:\n        guid <TAB> iid <TAB> model <TAB> x <TAB> y <TAB> z\n    ": "Bind models to ALREADY existing Ariane instances - WITHOUT duplicates. For a scene already placed in the Ariane map (imported from game files, not through the bridge): 'Export -> Ariane' would CREATE duplicates. This button instead MATCHES objects with Ariane instances by model+position and assigns their guid/iid -> live sync then works. Ariane dumps its instance list to <bridge>\\instances.txt, line: guid <TAB> iid <TAB> model <TAB> x <TAB> y <TAB> z",
    "Привязать модели к УЖЕ существующим инстансам Ariane — БЕЗ дублей.\n\nДля сцены, которая уже стоит в карте Ariane (импортировал из файлов игры,\nа не через мост): «Экспорт → Ariane» пытался бы СОЗДАТЬ дубли. Эта кнопка\nвместо создания МАТЧИТ объекты с инстансами Ariane по модель+позиция и\nвешает их guid/iid → после этого live-синк работает.\n\nAriane выгружает свой список инстансов в <bridge>\\instances.txt, строка:\n    guid <TAB> iid <TAB> model <TAB> x <TAB> y <TAB> z": "Bind models to ALREADY existing Ariane instances - WITHOUT duplicates. For a scene already placed in the Ariane map (imported from game files, not through the bridge): 'Export -> Ariane' would CREATE duplicates. This button instead MATCHES objects with Ariane instances by model+position and assigns their guid/iid -> live sync then works. Ariane dumps its instance list to <bridge>\\instances.txt, line: guid <TAB> iid <TAB> model <TAB> x <TAB> y <TAB> z",
    "Вкл/выкл слежение за ariane: авто-импорт присланных моделей (DFF+LOD).": "Toggle watching Ariane: auto-import sent models (DFF+LOD).",
    "Очистить папки моста (inbox/outbox/overrides). Делай между сессиями —\n    во время работы ariane её живые правки лежат в overrides.": "Clear the bridge folders (inbox/outbox/overrides). Do it between sessions - while working, Ariane's live edits live in overrides.",
    "Очистить папки моста (inbox/outbox/overrides). Делай между сессиями —\nво время работы ariane её живые правки лежат в overrides.": "Clear the bridge folders (inbox/outbox/overrides). Do it between sessions - while working, Ariane's live edits live in overrides.",
    "Указать папку игры с ariane для моста (обмен через <папка>\\ariane\\bridge).": "Point to Ariane's game folder for the bridge (exchange via <folder>\\ariane\\bridge).",
    "Разово импортировать всё, что сейчас лежит в инбоксе ariane.": "One-off import of everything currently in Ariane's inbox.",
    "Выбрать слой (его карта показывается в Image-редакторе).": "Select a layer (its map is shown in the Image editor).",
    "Запечь карты активного объекта в свои картинки и собрать живой\n    нодовый композит. Свет для карт генерируется самой подсистемой —\n    внешние источники сцены не нужны. only_map_id — запечь только одну\n    карту (per-layer Bake).": "Bake the active object's maps into their own images and build a live node composite. The lighting for the maps is generated by the subsystem itself - external scene lights are not needed. only_map_id - bake just one map (per-layer Bake).",
    "Запечь карты активного объекта в свои картинки и собрать живой\nнодовый композит. Свет для карт генерируется самой подсистемой —\nвнешние источники сцены не нужны. only_map_id — запечь только одну\nкарту (per-layer Bake).": "Bake the active object's maps into their own images and build a live node composite. The lighting for the maps is generated by the subsystem itself - external scene lights are not needed. only_map_id - bake just one map (per-layer Bake).",
    "Добавить слой карты в стек запекания": "Add a map layer to the bake stack.",
    "Удалить слой из стека запекания": "Remove a layer from the bake stack.",
    "Переместить слой вверх/вниз в стеке (порядок = порядок смешивания)": "Move a layer up/down in the stack (order = blend order).",
    "Показать/скрыть запечённую текстуру прямо на модели (flat-эмиссия,\n    видно при любом освещении). Для UV→UV переключает отображение на UV, в\n    которую запекали; для hi→low просто показывает на лоуполи. Повторный\n    клик возвращает исходные материалы и рендер-UV.\n\n    Исходные материалы/UV хранятся в custom-props объекта (переживают\n    перезагрузку аддона и сохранение .blend).": "Show/hide the baked texture right on the model (flat emission, visible under any lighting). For UV->UV it switches the display to the UV you baked into; for hi->low it just shows on the low-poly. Clicking again restores the original materials and render UV. Original materials/UVs are stored in the object's custom props (survive addon reload and .blend save).",
    "Показать/скрыть запечённую текстуру прямо на модели (flat-эмиссия,\nвидно при любом освещении). Для UV→UV переключает отображение на UV, в\nкоторую запекали; для hi→low просто показывает на лоуполи. Повторный\nклик возвращает исходные материалы и рендер-UV.\n\nИсходные материалы/UV хранятся в custom-props объекта (переживают\nперезагрузку аддона и сохранение .blend).": "Show/hide the baked texture right on the model (flat emission, visible under any lighting). For UV->UV it switches the display to the UV you baked into; for hi->low it just shows on the low-poly. Clicking again restores the original materials and render UV. Original materials/UVs are stored in the object's custom props (survive addon reload and .blend save).",
    "Свести стек слоёв (per-map картинки <base>_<map>) в ОДНУ текстуру\n    <base> numpy-композитом и сохранить её в файл («Сохранить как»).": "Flatten the layer stack (per-map images <base>_<map>) into ONE texture <base> via a numpy composite and save it to a file ('Save as').",
    "Свести стек слоёв (per-map картинки <base>_<map>) в ОДНУ текстуру\n<base> numpy-композитом и сохранить её в файл («Сохранить как»).": "Flatten the layer stack (per-map images <base>_<map>) into ONE texture <base> via a numpy composite and save it to a file ('Save as').",
    "Сохранить картинку выбранной карты (<base>_<map>) в файл. Для слоя с\n    «Декаль» (или карты ALPHA) сохраняет RGBA с вычисленной\n    альфой — как в общем сведении, но для одной карты.": "Save the selected map's image (<base>_<map>) to a file. For a layer with 'Decal' (or the ALPHA map) it saves RGBA with computed alpha - as in the full flatten, but for a single map.",
    "Сохранить картинку выбранной карты (<base>_<map>) в файл. Для слоя с\n«Декаль» (или карты ALPHA) сохраняет RGBA с вычисленной\nальфой — как в общем сведении, но для одной карты.": "Save the selected map's image (<base>_<map>) to a file. For a layer with 'Decal' (or the ALPHA map) it saves RGBA with computed alpha - as in the full flatten, but for a single map.",
    "Применить запечённый LightMap выбранным способом\n    (gtatools_bake_lightmap_apply): оставить слоем / впечь в диффуз /\n    записать в vertex prelight «Day».": "Apply the baked LightMap in the chosen way (gtatools_bake_lightmap_apply): keep as a layer / bake into diffuse / write into vertex prelight 'Day'.",
    "Применить запечённый LightMap выбранным способом\n(gtatools_bake_lightmap_apply): оставить слоем / впечь в диффуз /\nзаписать в vertex prelight «Day».": "Apply the baked LightMap in the chosen way (gtatools_bake_lightmap_apply): keep as a layer / bake into diffuse / write into vertex prelight 'Day'.",
    "Применить Интенсивность и Смягчение к запечённому LightMap — быстро,\n    без повторной запечки. Крутишь ползунки → жмёшь → результат обновился.": "Apply Intensity and Softening to the baked LightMap - fast, without re-baking. Turn the sliders -> click -> result updates.",
    "Применить Интенсивность и Смягчение к запечённому LightMap — быстро,\nбез повторной запечки. Крутишь ползунки → жмёшь → результат обновился.": "Apply Intensity and Softening to the baked LightMap - fast, without re-baking. Turn the sliders -> click -> result updates.",
    "Показать финальный вид на модели: базовая текстура (через свою UV1) ×\n    запечённый композит стека (через UV запекания, UV2). Как в игре с двумя\n    UV-каналами.\n\n    Строит per-слот preview-материал: TexUV1 (база) × TexUV2 (композит) →\n    эмиссия. Композит запечённых карт сводится в <base>_OVER. Базовая\n    текстура и её UV берутся из ИСХОДНОГО материала каждого слота. Снять —\n    кнопкой «Скрыть текстуру» (возврат исходных материалов).": "Show the final look on the model: base texture (via its UV1) x baked stack composite (via the bake UV, UV2). Like in-game with two UV channels. Builds a per-slot preview material: TexUV1 (base) x TexUV2 (composite) -> emission. The baked-map composite is flattened into <base>_OVER. The base texture and its UV come from each slot's ORIGINAL material. Remove with the 'Hide texture' button (restores original materials).",
    "Показать финальный вид на модели: базовая текстура (через свою UV1) ×\nзапечённый композит стека (через UV запекания, UV2). Как в игре с двумя\nUV-каналами.\n\nСтроит per-слот preview-материал: TexUV1 (база) × TexUV2 (композит) →\nэмиссия. Композит запечённых карт сводится в <base>_OVER. Базовая\nтекстура и её UV берутся из ИСХОДНОГО материала каждого слота. Снять —\nкнопкой «Скрыть текстуру» (возврат исходных материалов).": "Show the final look on the model: base texture (via its UV1) x baked stack composite (via the bake UV, UV2). Like in-game with two UV channels. Builds a per-slot preview material: TexUV1 (base) x TexUV2 (composite) -> emission. The baked-map composite is flattened into <base>_OVER. The base texture and its UV come from each slot's ORIGINAL material. Remove with the 'Hide texture' button (restores original materials).",
    "Собрать Blender Asset Library из извлечённых ресурсов.\n\nWalks every IDE in gta.dat / default.dat, classifies every cached DFF\nby category (Cars / Peds / Weapons / Map Objects per region / LOD /\nInteriors), imports each into a Collection, marks as an asset, embeds\nINU metadata (model_id, txd_name, draw_distance, ide_flags), and\noptionally renders a thumbnail. Output is a folder with one .blend\nper category plus blender_assets.cats.txt — point Blender's Asset\nLibrary preferences at it and you're done.": "Build a Blender Asset Library from extracted resources.\n\n    Walks every IDE in gta.dat / default.dat, classifies every cached DFF\n    by category (Cars / Peds / Weapons / Map Objects per region / LOD /\n    Interiors), imports each into a Collection, marks as an asset, embeds\n    INU metadata (model_id, txd_name, draw_distance, ide_flags), and\n    optionally renders a thumbnail. Output is a folder with one .blend\n    per category plus blender_assets.cats.txt — point Blender's Asset\n    Library preferences at it and you're done.",
    "Перегенерировать превьюшки в существующей Asset Library.\n\nIterates every ``<output>/*.blend``, opens it in this Blender\ninstance, re-renders thumbnails for every asset-marked collection,\nthen saves the .blend back. The asset list / metadata / textures\nare untouched — only the preview pixels are refreshed. Useful for\nbumping ``preview_size`` from 128 to 256 (or vice-versa) without\nwaiting through a full DFF re-import.\n\nStays in-process (modal generator) — opens .blend files in the\ncurrent session, headless subprocess would lose that scene-state\nintegration with the asset browser. Speed-up isn't critical for\npreview-only refresh anyway.": "Regenerate previews in an existing Asset Library.\n\n    Iterates every ``<output>/*.blend``, opens it in this Blender\n    instance, re-renders thumbnails for every asset-marked collection,\n    then saves the .blend back. The asset list / metadata / textures\n    are untouched — only the preview pixels are refreshed. Useful for\n    bumping ``preview_size`` from 128 to 256 (or vice-versa) without\n    waiting through a full DFF re-import.\n\n    Stays in-process (modal generator) — opens .blend files in the\n    current session, headless subprocess would lose that scene-state\n    integration with the asset browser. Speed-up isn't critical for\n    preview-only refresh anyway.",
    "Импорт катсцен-камеры GTA (.dat) — FOV, позиция, цель": "Import a GTA cutscene camera (.dat) - FOV, position, target.",
    "Экспорт активной камеры в катсцен-.dat GTA": "Export the active camera to a GTA cutscene .dat.",
    "Импорт COL коллизии GTA SA с прогресс-баром.\nESC прерывает импорт, уже созданные объекты остаются в сцене.": "Import a GTA SA collision COL with progress bar.\n    ESC interrupts the import — already-created objects stay in the scene.",
    "Импорт COL при перетаскивании во viewport (батч, прогресс + ESC).\n\n    Принимает несколько файлов сразу. Селекция игнорируется — COL\n    создаёт собственные mesh-объекты, не цепляется к существующим.\n    ": "Import COL when dragged into the viewport (batch, progress + ESC). Accepts several files at once. Selection is ignored - COL creates its own mesh objects, it doesn't attach to existing ones.",
    "Импорт COL при перетаскивании во viewport (батч, прогресс + ESC).\n\nПринимает несколько файлов сразу. Селекция игнорируется — COL\nсоздаёт собственные mesh-объекты, не цепляется к существующим.": "Import COL when dragged into the viewport (batch, progress + ESC). Accepts several files at once. Selection is ignored - COL creates its own mesh objects, it doesn't attach to existing ones.",
    "Добавить/убрать материал из избранного (★).\n\n    Избранные показываются первыми в списке и отмечаются звёздочкой.\n    Список хранится в пользовательских данных — сохраняется между\n    файлами и перезапусками Blender.": "Add/remove a material from favorites (star). Favorites show first in the list and are marked with a star. The list is stored in user data - it persists across files and Blender restarts.",
    "Добавить/убрать материал из избранного (★).\n\nИзбранные показываются первыми в списке и отмечаются звёздочкой.\nСписок хранится в пользовательских данных — сохраняется между\nфайлами и перезапусками Blender.": "Add/remove a material from favorites (star). Favorites show first in the list and are marked with a star. The list is stored in user data - it persists across files and Blender restarts.",
    "Выбрать тип поверхности для COL материала.\n\n    Alt+клик — сразу «ко всем выделенным COL» (можно и галкой в пикере).": "Choose the surface type for a COL material. Alt+click - apply to all selected COL at once (also available via the checkbox in the picker).",
    "Выбрать тип поверхности для COL материала.\n\nAlt+клик — сразу «ко всем выделенным COL» (можно и галкой в пикере).": "Choose the surface type for a COL material. Alt+click - apply to all selected COL at once (also available via the checkbox in the picker).",
    "Задать Draw Distance и/или LOD Distance всем выделенным MESH-объектам.\n\nПо умолчанию поля заполняются значениями активного объекта — можно\nизменить и применить к выделению одним действием. Галочки слева\nвыбирают какие именно поля переписывать (удобно менять только одно)": "Set Draw Distance and/or LOD Distance on every selected MESH object.\n\nFields are prefilled from the active object — tweak and apply to the entire selection in one action. The left-hand checkboxes pick which fields to overwrite (handy for changing only one)",
    "Импорт CST при перетаскивании во viewport (принимает несколько файлов).": "Import CST when dragged into the viewport (accepts several files).",
    "Импорт DFF модели GTA SA с прогресс-баром.\n    ESC прерывает импорт, уже созданные объекты остаются в сцене.": "Import a GTA SA DFF model with a progress bar. ESC interrupts the import - already-created objects stay in the scene.",
    "Импорт DFF модели GTA SA с прогресс-баром.\nESC прерывает импорт, уже созданные объекты остаются в сцене.": "Import a GTA SA DFF model with a progress bar. ESC interrupts the import - already-created objects stay in the scene.",
    "Импорт DFF при перетаскивании во viewport (батч, прогресс + ESC).\n\n    Принимает несколько файлов сразу (батч), каждый импортируется\n    как отдельная модель. Та же логика автоматического подцепления\n    одноимённого .txd, что и в обычном импорте.\n    ": "Import DFF when dragged into the viewport (batch, progress + ESC). Accepts several files at once (batch), each imported as a separate model. Same automatic pickup of the same-named .txd as in a normal import.",
    "Импорт DFF при перетаскивании во viewport (батч, прогресс + ESC).\n\nПринимает несколько файлов сразу (батч), каждый импортируется\nкак отдельная модель. Та же логика автоматического подцепления\nодноимённого .txd, что и в обычном импорте.": "Import DFF when dragged into the viewport (batch, progress + ESC). Accepts several files at once (batch), each imported as a separate model. Same automatic pickup of the same-named .txd as in a normal import.",
    "Скопировать настройки активного 2DFX на все ОСТАЛЬНЫЕ выделенные пустышки.\n\n    Мульти-редактирование: правишь один 2DFX (он — активный объект),\n    выделяешь группу целевых пустышек и применяешь — все настройки (цвет,\n    размеры короны/тени, текстуры, флаги) уходят на всех разом. Превью у\n    целей обновляется автоматически.\n\n    Дублирование (Shift+D) больше не требует этой кнопки: копия 2DFX уже\n    несёт все настройки и сама получает превью.": "Copy the active 2DFX's settings onto all OTHER selected empties. Multi-editing: you tweak one 2DFX (the active object), select a group of target empties and apply - all settings (color, corona/shadow sizes, textures, flags) go to all of them at once. The targets' previews update automatically. Duplication (Shift+D) no longer needs this button: a 2DFX copy already carries all settings and gets its own preview.",
    "Скопировать настройки активного 2DFX на все ОСТАЛЬНЫЕ выделенные пустышки.\n\nМульти-редактирование: правишь один 2DFX (он — активный объект),\nвыделяешь группу целевых пустышек и применяешь — все настройки (цвет,\nразмеры короны/тени, текстуры, флаги) уходят на всех разом. Превью у\nцелей обновляется автоматически.\n\nДублирование (Shift+D) больше не требует этой кнопки: копия 2DFX уже\nнесёт все настройки и сама получает превью.": "Copy the active 2DFX's settings onto all OTHER selected empties. Multi-editing: you tweak one 2DFX (the active object), select a group of target empties and apply - all settings (color, corona/shadow sizes, textures, flags) go to all of them at once. The targets' previews update automatically. Duplication (Shift+D) no longer needs this button: a 2DFX copy already carries all settings and gets its own preview.",
    "Загрузить текстуры эффектов (короны/тени/вода) из указанного .txd.\n\n    Текстуры эффектов GTA SA в аддон НЕ входят (это ассеты игры) — укажи путь\n    к .txd (например particle.txd) в поле выше, либо задай Game Root, и они\n    загрузятся из твоей игры для превью 2DFX.": "Load effect textures (coronas/shadows/water) from the given .txd. GTA SA effect textures are NOT bundled with the addon (they are game assets) - point to a .txd (e.g. particle.txd) in the field above, or set a Game Root, and they will load from your game for the 2DFX preview.",
    "Загрузить текстуры эффектов (короны/тени/вода) из указанного .txd.\n\nТекстуры эффектов GTA SA в аддон НЕ входят (это ассеты игры) — укажи путь\nк .txd (например particle.txd) в поле выше, либо задай Game Root, и они\nзагрузятся из твоей игры для превью 2DFX.": "Load effect textures (coronas/shadows/water) from the given .txd. GTA SA effect textures are NOT bundled with the addon (they are game assets) - point to a .txd (e.g. particle.txd) in the field above, or set a Game Root, and they will load from your game for the 2DFX preview.",
    "Выбрать .txd с текстурами эффектов (particle.txd и т.п.).\n\n    Открывает файловый браузер (фильтр *.txd) и записывает путь в\n    scene.inu_settings.gtatools_fx_txd_path. Сама загрузка текстур —\n    отдельной кнопкой «Загрузить текстуры эффектов»\n    (gtatools.load_fx_textures). Кнопка-папка живёт в заголовке панели\n    2DFX (GTATOOLS_PT_2dfx_panel.draw_header_preset).": "Choose a .txd with effect textures (particle.txd etc.). Opens a file browser (filter *.txd) and writes the path into scene.inu_settings.gtatools_fx_txd_path. The actual texture loading is a separate button, 'Load effect textures' (gtatools.load_fx_textures). The folder button lives in the 2DFX panel header (GTATOOLS_PT_2dfx_panel.draw_header_preset).",
    "Выбрать .txd с текстурами эффектов (particle.txd и т.п.).\n\nОткрывает файловый браузер (фильтр *.txd) и записывает путь в\nscene.inu_settings.gtatools_fx_txd_path. Сама загрузка текстур —\nотдельной кнопкой «Загрузить текстуры эффектов»\n(gtatools.load_fx_textures). Кнопка-папка живёт в заголовке панели\n2DFX (GTATOOLS_PT_2dfx_panel.draw_header_preset).": "Choose a .txd with effect textures (particle.txd etc.). Opens a file browser (filter *.txd) and writes the path into scene.inu_settings.gtatools_fx_txd_path. The actual texture loading is a separate button, 'Load effect textures' (gtatools.load_fx_textures). The folder button lives in the 2DFX panel header (GTATOOLS_PT_2dfx_panel.draw_header_preset).",
    "Расколоть меш на отдельные объекты-осколки (сетка / кластеры)": "Split a mesh into separate shard objects (grid / clusters).",
    "Сделать активным указанный фрейм (используется панелью при клике\nна строку дерева).": "Make the specified frame active (used by the panel when clicking\n    on a tree row).",
    "Назначить parent: активный объект становится родителем для остальных\nвыделенных. Мировая позиция каждого ребёнка сохраняется, а\nmatrix_parent_inverse сбрасывается в identity (DFF requirement).": "Set parent: active object becomes the parent of the other selected ones. World position of every child is preserved, and matrix_parent_inverse is reset to identity (DFF requirement).",
    "Снять parent с выделенных объектов (parent → None). Мировая\nпозиция сохраняется.": "Clear parent on selected objects (parent → None). World position is preserved.",
    "Сделать указанный фрейм РОДИТЕЛЕМ активного — клик прямо в дереве\n    панели: сначала выдели дочерний фрейм, потом жми эту кнопку на строке\n    будущего родителя. Мировая позиция сохраняется, matrix_parent_inverse\n    сбрасывается в identity (требование DFF).": "Make the specified frame the PARENT of the active one - click right in the panel tree: first select the child frame, then press this button on the future parent's row. World position is preserved, matrix_parent_inverse is reset to identity (DFF requirement).",
    "Сделать указанный фрейм РОДИТЕЛЕМ активного — клик прямо в дереве\nпанели: сначала выдели дочерний фрейм, потом жми эту кнопку на строке\nбудущего родителя. Мировая позиция сохраняется, matrix_parent_inverse\nсбрасывается в identity (требование DFF).": "Make the specified frame the PARENT of the active one - click right in the panel tree: first select the child frame, then press this button on the future parent's row. World position is preserved, matrix_parent_inverse is reset to identity (DFF requirement).",
    "Проверить иерархию активного объекта против vanilla SA шаблона.\nТип шаблона выбирается атрибутом ``template`` оператора.": "Validate the active object's hierarchy against the vanilla SA template.\n    Template type is selected by the operator's ``template`` attribute.",
    "Создать зеркальную копию выделенных фреймов: ``_lf`` → ``_rf``,\n``_lb`` → ``_rb`` (X отражается, остальные оси без изменений). Если\nзеркальный близнец уже существует — оператор его не трогает.": "Create a mirrored copy of selected frames: ``_lf`` → ``_rf``,\n    ``_lb`` → ``_rb`` (X is mirrored, other axes unchanged). If the\n    mirrored twin already exists — operator leaves it alone.",
    "Прореживание выделенных ключей. Stride — оставить каждый N-ный\nключ. Auto — удалить ключи которые лежат на прямой между соседями\n(избыточные).": "Thin out selected keyframes. Stride — keep every Nth key. Auto — remove keys lying on the straight line between neighbours (redundant).",
    "Прицепить кисти (shandl/shandr) к скелету игрока НА УРОВНЕ КОСТЕЙ\n    (совет ligabesar): кость предплечья кисти ' L ForeArm01' следует за\n    ' L ForeArm' игрока, а ' L Hand01' — за ' L Hand' (и то же для R), через\n    Copy Transforms. Кисть остаётся ОТДЕЛЬНОЙ armature; связываются только\n    соответствующие кости → авто-позиция и ориентация без ручного\n    выравнивания. Пальцы (дети ' L Hand01') не связаны — их анимируешь сам.": "Attach the hands (shandl/shandr) to the player skeleton AT BONE LEVEL (ligabesar's tip): the hand forearm bone ' L ForeArm01' follows the player's ' L ForeArm', and ' L Hand01' follows ' L Hand' (same for R), via Copy Transforms. The hand stays a SEPARATE armature; only the matching bones are linked -> auto position and orientation without manual alignment. Fingers (children of ' L Hand01') are not linked - you animate them yourself.",
    "Прицепить кисти (shandl/shandr) к скелету игрока НА УРОВНЕ КОСТЕЙ\n(совет ligabesar): кость предплечья кисти ' L ForeArm01' следует за\n' L ForeArm' игрока, а ' L Hand01' — за ' L Hand' (и то же для R), через\nCopy Transforms. Кисть остаётся ОТДЕЛЬНОЙ armature; связываются только\nсоответствующие кости → авто-позиция и ориентация без ручного\nвыравнивания. Пальцы (дети ' L Hand01') не связаны — их анимируешь сам.": "Attach the hands (shandl/shandr) to the player skeleton AT BONE LEVEL (ligabesar's tip): the hand forearm bone ' L ForeArm01' follows the player's ' L ForeArm', and ' L Hand01' follows ' L Hand' (same for R), via Copy Transforms. The hand stays a SEPARATE armature; only the matching bones are linked -> auto position and orientation without manual alignment. Fingers (children of ' L Hand01') are not linked - you animate them yourself.",
    "Отцепить кисти — снять все привязки Handsign (Child Of), кисти снова\n    свободны. Ничего не удаляет, только констрейнты.": "Detach the hands - remove all Handsign bindings (Child Of), the hands are free again. Nothing is deleted, only the constraints.",
    "Отцепить кисти — снять все привязки Handsign (Child Of), кисти снова\nсвободны. Ничего не удаляет, только констрейнты.": "Detach the hands - remove all Handsign bindings (Child Of), the hands are free again. Nothing is deleted, only the constraints.",
    "Экспорт жеста в ОДИН заход: берёт активную Action каждого из трёх\n    скелетов (рука→gsignN, левые пальцы→lhgsignN, правые→rhgsignN), строит\n    блоки и вливает их в ghands.ifp одним merge — совпавшие по имени блоки\n    заменяются, остальные (вся ваниль) остаются байт-в-байт. Имя Action =\n    имя блока в IFP, поэтому назови Actions правильно (gsign6/lhgsign6/…).": "Export a gesture in ONE go: takes the active Action of each of the three skeletons (arm->gsignN, left fingers->lhgsignN, right->rhgsignN), builds the blocks and merges them into ghands.ifp in a single merge - blocks matching by name are replaced, the rest (all the vanilla ones) stay byte-for-byte. The Action name = the block name in the IFP, so name your Actions correctly (gsign6/lhgsign6/...).",
    "Экспорт жеста в ОДИН заход: берёт активную Action каждого из трёх\nскелетов (рука→gsignN, левые пальцы→lhgsignN, правые→rhgsignN), строит\nблоки и вливает их в ghands.ifp одним merge — совпавшие по имени блоки\nзаменяются, остальные (вся ваниль) остаются байт-в-байт. Имя Action =\nимя блока в IFP, поэтому назови Actions правильно (gsign6/lhgsign6/…).": "Export a gesture in ONE go: takes the active Action of each of the three skeletons (arm->gsignN, left fingers->lhgsignN, right->rhgsignN), builds the blocks and merges them into ghands.ifp in a single merge - blocks matching by name are replaced, the rest (all the vanilla ones) stay byte-for-byte. The Action name = the block name in the IFP, so name your Actions correctly (gsign6/lhgsign6/...).",
    "Добавить/обновить выделенное в файлах IDE + IPL одним действием: пишет и\n    IDE (определение модели), и IPL (расстановку) в выбранные файлы. Обёртка\n    над Add to IDE + Add to IPL — их логика (авто-LOD, маршрутизация,\n    tracking) не дублируется. Не путать с «Export Map» (вся карта).": "Add/update the selection in the IDE + IPL files in one action: writes both the IDE (model definition) and the IPL (placement) to the chosen files. A wrapper over Add to IDE + Add to IPL - their logic (auto-LOD, routing, tracking) is not duplicated. Not to be confused with 'Export Map' (the whole map).",
    "Добавить/обновить выделенное в файлах IDE + IPL одним действием: пишет и\nIDE (определение модели), и IPL (расстановку) в выбранные файлы. Обёртка\nнад Add to IDE + Add to IPL — их логика (авто-LOD, маршрутизация,\ntracking) не дублируется. Не путать с «Export Map» (вся карта).": "Add/update the selection in the IDE + IPL files in one action: writes both the IDE (model definition) and the IPL (placement) to the chosen files. A wrapper over Add to IDE + Add to IPL - their logic (auto-LOD, routing, tracking) is not duplicated. Not to be confused with 'Export Map' (the whole map).",
    "Убрать выделенное из файлов IDE и IPL (удаляет их записи).": "Remove the selection from the IDE and IPL files (deletes their entries).",
    "Импортировать ВЫБРАННЫЙ в панели IDE-файл (без диалога — берёт путь из\n    строки IDE). Сопоставляет определения с объектами сцены.": "Import the IDE file SELECTED in the panel (no dialog - takes the path from the IDE row). Matches definitions to scene objects.",
    "Импортировать ВЫБРАННЫЙ в панели IDE-файл (без диалога — берёт путь из\nстроки IDE). Сопоставляет определения с объектами сцены.": "Import the IDE file SELECTED in the panel (no dialog - takes the path from the IDE row). Matches definitions to scene objects.",
    "Импортировать ВЫБРАННЫЙ в панели IPL-файл (без диалога — берёт путь из\n    строки IPL). Расставляет объекты по IPL.": "Import the IPL file SELECTED in the panel (no dialog - takes the path from the IPL row). Places objects according to the IPL.",
    "Импортировать ВЫБРАННЫЙ в панели IPL-файл (без диалога — берёт путь из\nстроки IPL). Расставляет объекты по IPL.": "Import the IPL file SELECTED in the panel (no dialog - takes the path from the IPL row). Places objects according to the IPL.",
    "Add: записать/обновить ВЫДЕЛЕННЫЕ модели в ВЫБРАННЫЙ .ide (id, txd, дистанция, флаги). Обновляет существующие строки на месте; LOD-пары связываются автоматически. Для новых моделей нужен Model ID. Отличие от Export: пишет в уже выбранный файл, а не создаёт новый": "Add: write/update the SELECTED models in the CHOSEN .ide (id, txd, distance, flags). Updates existing lines in place; LOD pairs are linked automatically. New models need a Model ID. Unlike Export: writes into the already-chosen file instead of creating a new one.",
    "Add: записать/обновить РАССТАНОВКУ выделенных моделей в ВЫБРАННЫЙ .ipl (позиция + поворот). Перемещённую модель обновляет на месте (не плодит дубли), LOD-привязка авто. Отличие от Export: пишет в уже выбранный файл, а не создаёт новый": "Add: write/update the PLACEMENT of the selected models in the CHOSEN .ipl (position + rotation). A moved model is updated in place (no duplicates), LOD linking is automatic. Unlike Export: writes into the already-chosen file instead of creating a new one.",
    "Выбрать файл и записать путь в настройку (для коротких меток путей\n    IDE/IPL в боксах редактора — метку нельзя править инлайн).": "Choose a file and write the path into a setting (for the short path labels of IDE/IPL in the editor boxes - the label can't be edited inline).",
    "Выбрать файл и записать путь в настройку (для коротких меток путей\nIDE/IPL в боксах редактора — метку нельзя править инлайн).": "Choose a file and write the path into a setting (for the short path labels of IDE/IPL in the editor boxes - the label can't be edited inline).",
    "Синхронизация Blender ↔ IPL.\n\n    Bi-directional:\n      • Если у объекта НЕТ uuid и его (model_id + позиция) совпадает с\n        какой-то строкой IPL — линкует: генерирует uuid, регистрирует в\n        sidecar. Это автолинковка после Map Import.\n      • Если у объекта uuid есть — подтягивает позицию ИЗ IPL в Blender\n        (после внешней правки файла).\n\n    Если заполнен список «Sync несколько IPL» — проходит по всем файлам\n    из него; иначе по единственному gtatools_ipl_path. Работает по\n    выделению (или по всем mesh-объектам если selection пуст).\n    ": "Blender <-> IPL sync. Bi-directional: if an object has NO uuid and its (model_id + position) matches some IPL line, it links them - generates a uuid, registers it in the sidecar (the auto-link after Map Import). If the object has a uuid, it pulls the position FROM the IPL into Blender (after an external file edit). If the 'Sync several IPL' list is filled, it goes through all its files; otherwise the single gtatools_ipl_path. Works on the selection (or all mesh objects if the selection is empty).",
    "Синхронизация Blender ↔ IPL.\n\nBi-directional:\n  • Если у объекта НЕТ uuid и его (model_id + позиция) совпадает с\n    какой-то строкой IPL — линкует: генерирует uuid, регистрирует в\n    sidecar. Это автолинковка после Map Import.\n  • Если у объекта uuid есть — подтягивает позицию ИЗ IPL в Blender\n    (после внешней правки файла).\n\nЕсли заполнен список «Sync несколько IPL» — проходит по всем файлам\nиз него; иначе по единственному gtatools_ipl_path. Работает по\nвыделению (или по всем mesh-объектам если selection пуст).": "Blender <-> IPL sync. Bi-directional: if an object has NO uuid and its (model_id + position) matches some IPL line, it links them - generates a uuid, registers it in the sidecar (the auto-link after Map Import). If the object has a uuid, it pulls the position FROM the IPL into Blender (after an external file edit). If the 'Sync several IPL' list is filled, it goes through all its files; otherwise the single gtatools_ipl_path. Works on the selection (or all mesh objects if the selection is empty).",
    "Вернуть выделенные модели на их координаты из IPL (позиция и поворот).\n\nИщет строку модели: сначала по связи (uuid) в её родном IPL, иначе по Model ID\nв родном файле, а если не нашлось — во всех IPL папки игры. Один инстанс —\nставит по нему; несколько — берёт ближайший к текущему положению": "Return the selected models to their coordinates from the IPL (position and rotation). Finds the model's line: first by link (uuid) in its home IPL, otherwise by Model ID in its home file, and if not found - across all IPL of the game folder. One instance - places by it; several - takes the one nearest to the current position.",
    "Добавить один или несколько IPL в список синхронизации.\n    Файловый диалог поддерживает множественный выбор (Ctrl/Shift).": "Add one or several IPL to the sync list. The file dialog supports multi-selection (Ctrl/Shift).",
    "Добавить один или несколько IPL в список синхронизации.\nФайловый диалог поддерживает множественный выбор (Ctrl/Shift).": "Add one or several IPL to the sync list. The file dialog supports multi-selection (Ctrl/Shift).",
    "Добавить в список синхронизации ВСЕ .ipl из выбранной папки —\n    по умолчанию включая подпапки (рекурсивно).": "Add ALL .ipl from the chosen folder to the sync list - by default including subfolders (recursively).",
    "Добавить в список синхронизации ВСЕ .ipl из выбранной папки —\nпо умолчанию включая подпапки (рекурсивно).": "Add ALL .ipl from the chosen folder to the sync list - by default including subfolders (recursively).",
    "Убрать IPL из списка синхронизации.": "Remove an IPL from the sync list.",
    "Добавить один или несколько IDE в список синхронизации.\n    Файловый диалог поддерживает множественный выбор (Ctrl/Shift).": "Add one or several IDE to the sync list. The file dialog supports multi-selection (Ctrl/Shift).",
    "Добавить один или несколько IDE в список синхронизации.\nФайловый диалог поддерживает множественный выбор (Ctrl/Shift).": "Add one or several IDE to the sync list. The file dialog supports multi-selection (Ctrl/Shift).",
    "Добавить в список синхронизации ВСЕ .ide из выбранной папки —\n    по умолчанию включая подпапки (рекурсивно).": "Add ALL .ide from the chosen folder to the sync list - by default including subfolders (recursively).",
    "Добавить в список синхронизации ВСЕ .ide из выбранной папки —\nпо умолчанию включая подпапки (рекурсивно).": "Add ALL .ide from the chosen folder to the sync list - by default including subfolders (recursively).",
    "Убрать IDE из списка синхронизации.": "Remove an IDE from the sync list.",
    "Экспорт «каждая модель в свой IDE»: обновляет строки выделенных моделей\n    в тех IDE, откуда они пришли (ide_target_file, проставляется импортом). Модели\n    без IDE (новые) не пишутся — о них сообщается, добавь их через «Add» в\n    выбранный IDE.": "Export 'each model to its own IDE': updates the lines of the selected models in the IDEs they came from (ide_target_file, set on import). Models without an IDE (new ones) are not written - they are reported, add them via 'Add' to the chosen IDE.",
    "Экспорт «каждая модель в свой IDE»: обновляет строки выделенных моделей\nв тех IDE, откуда они пришли (ide_target_file, проставляется импортом). Модели\nбез IDE (новые) не пишутся — о них сообщается, добавь их через «Add» в\nвыбранный IDE.": "Export 'each model to its own IDE': updates the lines of the selected models in the IDEs they came from (ide_target_file, set on import). Models without an IDE (new ones) are not written - they are reported, add them via 'Add' to the chosen IDE.",
    "Обновить координаты выделенных моделей в их родных IPL.\n\nКаждая модель пишется в тот IPL, откуда её импортировали — записывается новая\nпозиция и поворот. Удобно после того как подвинул модель в сцене. Файл,\nвыбранный в боксе IPL, при этом не используется": "Update the coordinates of the selected models in their home IPL. Each model is written to the IPL it was imported from - the new position and rotation are recorded. Handy after you moved a model in the scene. The file chosen in the IPL box is not used here.",
    "Удалить выделенные объекты из IPL и очистить ссылки.\n\nОбъекты остаются в Blender, но их inst-строки удаляются из IPL. Парный LOD\nмодели удаляется тоже (если он не нужен другой оставшейся модели). Индексы\nстрок и lod_index у остальных пересчитываются заново, чтобы ссылки не съехали": "Remove the selected objects from the IPL and clear their links. The objects stay in Blender, but their inst lines are deleted from the IPL. The model's paired LOD is deleted too (if no other remaining model needs it). The line indices and lod_index of the rest are recomputed so links don't drift.",
    "Проверить все ссылки sidecar'а на валидность. Сообщает orphan'ы\n    (uuid в sidecar, объект удалён из Blender) и broken links\n    (line_idx за пределами IPL или content не совпадает).": "Check all sidecar links for validity. Reports orphans (uuid in the sidecar, object deleted from Blender) and broken links (line_idx out of the IPL range or content mismatch).",
    "Проверить все ссылки sidecar'а на валидность. Сообщает orphan'ы\n(uuid в sidecar, объект удалён из Blender) и broken links\n(line_idx за пределами IPL или content не совпадает).": "Check all sidecar links for validity. Reports orphans (uuid in the sidecar, object deleted from Blender) and broken links (line_idx out of the IPL range or content mismatch).",
    "Синхронизация Blender ↔ IDE.\n\n    Bi-directional, аналогично Sync для IPL:\n      • Если model_id объекта найден в IDE → подтягивает draw_distance,\n        txd_name, flags из IDE в obj.inu props.  Это автолинковка после\n        Map Import и кейс пост-внешней-правки IDE.\n      • Если model_id не найден → пропускает (записи нет, нечего тянуть).\n\n    Работает по выделению; пустое выделение = всё meshes сцены.\n    ": "Blender <-> IDE sync. Bi-directional, like the IPL Sync: if the object's model_id is found in the IDE -> pulls draw_distance, txd_name, flags from the IDE into obj.inu props (the auto-link after Map Import and the post-external-IDE-edit case). If the model_id is not found -> skips (no entry, nothing to pull). Works on the selection; empty selection = all scene meshes.",
    "Синхронизация Blender ↔ IDE.\n\nBi-directional, аналогично Sync для IPL:\n  • Если model_id объекта найден в IDE → подтягивает draw_distance,\n    txd_name, flags из IDE в obj.inu props.  Это автолинковка после\n    Map Import и кейс пост-внешней-правки IDE.\n  • Если model_id не найден → пропускает (записи нет, нечего тянуть).\n\nРаботает по выделению; пустое выделение = всё meshes сцены.": "Blender <-> IDE sync. Bi-directional, like the IPL Sync: if the object's model_id is found in the IDE -> pulls draw_distance, txd_name, flags from the IDE into obj.inu props (the auto-link after Map Import and the post-external-IDE-edit case). If the model_id is not found -> skips (no entry, nothing to pull). Works on the selection; empty selection = all scene meshes.",
    "Удалить выделенные объекты из IDE и очистить tracking-поля.\n    Объекты остаются в Blender, но их записи в IDE удаляются по model_id.": "Remove the selected objects from the IDE and clear the tracking fields. The objects stay in Blender, but their entries in the IDE are deleted by model_id.",
    "Удалить выделенные объекты из IDE и очистить tracking-поля.\nОбъекты остаются в Blender, но их записи в IDE удаляются по model_id.": "Remove the selected objects from the IDE and clear the tracking fields. The objects stay in Blender, but their entries in the IDE are deleted by model_id.",
    "Проверить, что model_id всех выделенных объектов есть в IDE.\n    Сообщает: present (есть), missing (нет), zero_id (Model ID не задан).": "Check that the model_id of all selected objects exists in the IDE. Reports: present, missing, zero_id (Model ID not set).",
    "Проверить, что model_id всех выделенных объектов есть в IDE.\nСообщает: present (есть), missing (нет), zero_id (Model ID не задан).": "Check that the model_id of all selected objects exists in the IDE. Reports: present, missing, zero_id (Model ID not set).",
    "Sync для обоих файлов: IDE + IPL.\n\n    Не добавляет свой собственный финальный report — это бы перетёрло\n    детальный отчёт inner-операторов в status-bar Blender'а\n    («Sync: linked 0, обновлено 0, пропущено 2 — все без Model ID»).\n    Сохраняем info-сообщение последнего inner-вызова видимым.\n    ": "Sync for both files: IDE + IPL. Does not add its own final report - that would overwrite the detailed report of the inner operators in Blender's status bar ('Sync: linked 0, updated 0, skipped 2 - all without Model ID'). We keep the last inner call's info message visible.",
    "Sync для обоих файлов: IDE + IPL.\n\nНе добавляет свой собственный финальный report — это бы перетёрло\nдетальный отчёт inner-операторов в status-bar Blender'а\n(«Sync: linked 0, обновлено 0, пропущено 2 — все без Model ID»).\nСохраняем info-сообщение последнего inner-вызова видимым.": "Sync for both files: IDE + IPL. Does not add its own final report - that would overwrite the detailed report of the inner operators in Blender's status bar ('Sync: linked 0, updated 0, skipped 2 - all without Model ID'). We keep the last inner call's info message visible.",
    "Unlink из обоих файлов: IDE + IPL для выделенных объектов.": "Unlink from both files: IDE + IPL for the selected objects.",
    "Verify обоих: IDE-ссылок (по model_id) + IPL-ссылок (по uuid+sidecar).": "Verify both: IDE links (by model_id) + IPL links (by uuid+sidecar).",
    "Del: удалить строки ВЫДЕЛЕННЫХ моделей из выбранного .ide (по Model ID)": "Del: delete the lines of the SELECTED models from the chosen .ide (by Model ID).",
    "Del: удалить расстановку ВЫДЕЛЕННЫХ моделей из выбранного .ipl": "Del: delete the placement of the SELECTED models from the chosen .ipl.",
    "Export: сохранить определения ВЫДЕЛЕННЫХ моделей в НОВЫЙ .ide-файл (диалог сохранения). Отличие от Add: создаёт отдельный файл, а не дописывает в уже выбранный": "Export: save the definitions of the SELECTED models to a NEW .ide file (save dialog). Unlike Add: creates a separate file instead of appending to the already-chosen one.",
    "Export: сохранить расстановку ВЫДЕЛЕННЫХ моделей в НОВЫЙ .ipl-файл (диалог сохранения). Отличие от Add: создаёт отдельный файл, а не дописывает в уже выбранный": "Export: save the placement of the SELECTED models to a NEW .ipl file (save dialog). Unlike Add: creates a separate file instead of appending to the already-chosen one.",
    "Import: загрузить .ide (диалог) и сопоставить определения (id, txd, дистанция, флаги) с моделями в сцене по имени. Геометрию не грузит — только свойства": "Import: load an .ide (dialog) and match its definitions (id, txd, distance, flags) to scene models by name. Doesn't load geometry - only properties.",
    "Import: загрузить .ipl (диалог) и расставить объекты по позициям из файла (модели без геометрии — как Empty-заглушки). Геометрию тянет «Импорт из IMG»": "Import: load an .ipl (dialog) and place objects at the positions from the file (models without geometry - as Empty placeholders). The geometry is pulled by 'Import from IMG'.",
    "Создать новый пресет ID.\n\n    Пустой пресет создаётся готовым к `Создать файл ID` (Заполнить 321-19999).\n    Опция «Скопировать с активного» дублирует текущий файл ID, чтобы не\n    начинать с нуля, если часть ID уже назначена.\n    ": "Create a new ID preset. An empty preset is created ready for 'Create ID file' (fill 321-19999). The 'Copy from active' option duplicates the current ID file so you don't start from scratch if part of the ID is already assigned.",
    "Создать новый пресет ID.\n\nПустой пресет создаётся готовым к `Создать файл ID` (Заполнить 321-19999).\nОпция «Скопировать с активного» дублирует текущий файл ID, чтобы не\nначинать с нуля, если часть ID уже назначена.": "Create a new ID preset. An empty preset is created ready for 'Create ID file' (fill 321-19999). The 'Copy from active' option duplicates the current ID file so you don't start from scratch if part of the ID is already assigned.",
    "Диагностика round-trip для IFP — проверяет что read → write → read\nне теряет анимации, не путает кости и не ломает квартернионы.\n\nВыбранный файл не меняется: экспорт идёт во временный файл рядом,\nрезультат сравнивается с оригиналом и удаляется. Отчёт показывает\nсчётчики и максимальные численные отклонения (dRot, dTrans, dTime)": "Round-trip diagnostics for IFP — checks that read → write → read doesn't lose animations, mix up bones or break quaternions.\n\n    The selected file is not modified: export goes to a temp file next to it, the result is compared with the original and deleted. Report shows counters and maximum numerical deltas (dRot, dTrans, dTime)",
    "Добавить или заменить анимации в существующем IFP-паке.\n\nОткрывает ped.ifp / anim.ifp (или любой другой .ifp), подменяет\nанимации по имени (case-insensitive) или дописывает в конец, и\nсохраняет файл обратно. Остальные анимации пака сохраняются.\nПозволяет обойтись без внешних IFP-редакторов при правке одной\nанимации в ванильном паке": "Add or replace animations in an existing IFP pack.\n\n    Opens ped.ifp / anim.ifp (or any other .ifp), overwrites animations\n    by name (case-insensitive) or appends them, then saves the file back.\n    Other animations in the pack stay intact. Lets you skip external\n    IFP editors when editing a single animation in a vanilla pack",
    "Переключить живой preview IFP-анимации без коммита в Action.\n\nПозволяет быстро пробежаться по 294 ванильным анимациям `ped.ifp`\nпростым переключением Action-dropdown'а без захламления Action\nEditor'а. Handler frame_change_post напрямую пишет в pose bones\nпри скрабе Timeline. Повторный клик — выключает preview и\nвосстанавливает предыдущий Action арматуры": "Toggle live IFP animation preview without committing to Action.\n\n    Lets you quickly browse through 294 vanilla `ped.ifp` animations\n    by simply switching the Action dropdown, without cluttering the\n    Action Editor. The frame_change_post handler writes directly to\n    pose bones when scrubbing the Timeline. A repeated click — turns\n    off preview and restores the armature's previous Action",
    "Исправить sign-discontinuities кватернионов на диапазоне кадров.\nМежду двумя соседними ключами с dot < 0 кость крутится длинной\nдорогой через 360°. Скрипт находит такие пары и инвертирует знак\nкватерниона на втором ключе — q и -q описывают одинаковую ротацию,\nно интерполяция между ними после флипа идёт коротким путём.\n\nИдемпотентный — повторный прогон не ухудшит, иногда нужен 2-й\nпроход чтобы вылезли ранее скрытые разрывы.": "Fix quaternion sign-discontinuities over a frame range.\n    Between two adjacent keys with dot < 0 the bone takes the long path through 360°. The script finds such pairs and flips the sign of the second key — q and -q describe the same rotation, but interpolation after the flip takes the short path.\n\n    Idempotent — a repeat run won't make things worse; sometimes a 2nd pass is needed for earlier-hidden discontinuities to surface.",
    "Отзеркалить активную анимацию по оси X/Y/Z (in-place).\n\n    Blender-овские встроенные зеркала ломают GTA-анимацию, потому что\n    GTA-риг не именует кости .L/.R и имеет свой roll/rest. Здесь зеркало\n    делается в armature-space через FK: для каждого кадра читаем мировую\n    матрицу каждой кости, отражаем её конъюгацией `flip @ W @ flip`\n    (позиция и поворот отражаются, det остаётся +1 — без негатив-скейла),\n    и назначаем результат ПАРНОЙ L/R кости (при включённом обмене).\n    Так «повернуть налево» превращается в «повернуть направо», а не в\n    вывернутую наизнанку позу.": "Mirror the active animation along the X/Y/Z axis (in-place). Blender's built-in mirrors break GTA animation because the GTA rig doesn't name bones .L/.R and has its own roll/rest. Here the mirror is done in armature-space via FK: for each frame we read every bone's world matrix, reflect it by conjugation 'flip @ W @ flip' (position and rotation are reflected, det stays +1 - no negative scale), and assign the result to the PAIRED L/R bone (when swapping is on). So 'turn left' becomes 'turn right' instead of an inside-out pose.",
    "Отзеркалить активную анимацию по оси X/Y/Z (in-place).\n\nBlender-овские встроенные зеркала ломают GTA-анимацию, потому что\nGTA-риг не именует кости .L/.R и имеет свой roll/rest. Здесь зеркало\nделается в armature-space через FK: для каждого кадра читаем мировую\nматрицу каждой кости, отражаем её конъюгацией `flip @ W @ flip`\n(позиция и поворот отражаются, det остаётся +1 — без негатив-скейла),\nи назначаем результат ПАРНОЙ L/R кости (при включённом обмене).\nТак «повернуть налево» превращается в «повернуть направо», а не в\nвывернутую наизнанку позу.": "Mirror the active animation along the X/Y/Z axis (in-place). Blender's built-in mirrors break GTA animation because the GTA rig doesn't name bones .L/.R and has its own roll/rest. Here the mirror is done in armature-space via FK: for each frame we read every bone's world matrix, reflect it by conjugation 'flip @ W @ flip' (position and rotation are reflected, det stays +1 - no negative scale), and assign the result to the PAIRED L/R bone (when swapping is on). So 'turn left' becomes 'turn right' instead of an inside-out pose.",
    "Сгладить ключи между выделенными опорными.\n\nUse-case: запечённая анимация с ключом на каждом кадре (например 700\nключей). Хочешь опустить кость на кадре 70 — двигаешь её там, потом\nв Dope Sheet/Graph Editor выделяешь 3 ключа (50, 70, 90: первый,\nредактированный, последний) и нажимаешь эту кнопку. Промежуточные\nключи (51-69 и 71-89) перезаписываются smooth-step интерполяцией\nмежду соседними опорными — будто там никаких ключей и не было.\n\nРежимы оси:\n- ALL — обрабатывает ВСЕ F-curve (включая rotation, scale) в bone-\n  local координатах. Быстро.\n- WORLD_X/Y/Z — обрабатывает только .location и считает в МИРОВЫХ\n  координатах. Учитывает поворот родительских костей и armature.\n  Медленнее (per-frame depsgraph eval), но даёт правильный «по Z\n  вниз» эффект независимо от ориентации кости.\n\nАнкоры берутся из выделенных ключей, минимум 2.\nСтруктура «ключ на каждом кадре» сохраняется (важно для round-trip\nв IFP).": "Smooth keys between selected anchors.\n\n    Use-case: a baked animation with a key on every frame (e.g. 700\n    keys). You want to lower the bone at frame 70 — you move it there, then\n    in Dope Sheet/Graph Editor you select 3 keys (50, 70, 90: first,\n    edited, last) and press this button. Intermediate\n    keys (51-69 and 71-89) are overwritten with smooth-step interpolation\n    between the adjacent anchors — as if no keys had been there at all.\n\n    Axis modes:\n    - ALL — processes ALL F-curves (including rotation, scale) in bone-\n      local coordinates. Fast.\n    - WORLD_X/Y/Z — processes only .location and computes in WORLD\n      coordinates. Takes parent bone rotation and armature into account.\n      Slower (per-frame depsgraph eval), but gives the correct «down\n      along Z» effect regardless of bone orientation.\n\n    Anchors are taken from the selected keys, minimum 2.\n    The «key on every frame» structure is preserved (important for IFP\n    round-trip).",
    "Удалить активную Action арматуры из файла полностью.\nВ отличие от кнопки X в Action Editor (которая только отвязывает),\nэтот оператор стирает Action из bpy.data.actions — полезно чтобы\nв IFP-экспорт не попадали забытые анимации.": "Delete the armature's active Action from the file entirely.\n    Unlike the X button in Action Editor (which only unlinks),\n    this operator wipes the Action from bpy.data.actions — useful so\n    forgotten animations don't end up in the IFP export.",
    "Накинуть bone-based IK на стандартные цепочки SA-педа.\nСоздаёт non-deform контрольные кости внутри армча: запястья,\nступни, голову и корень. На deform-кости — IK-constraint и\nCopy Rotation/Location, target — соответствующая control-кость.\nКонтроллы окрашены зелёным (THEME09). Перед Export IFP — Bake\n& Clear IK, которая всё снимет и удалит control-кости.": "Apply bone-based IK to the standard SA-ped chains.\n    Creates non-deform control bones inside the armature: wrists,\n    feet, head and root. Deform bones get IK-constraints and\n    Copy Rotation/Location targeting the matching control bone.\n    Controls are coloured green (THEME09). Before Export IFP — Bake\n    & Clear IK, which removes everything and deletes the control bones.",
    "Запечь визуальную позу с IK на deform-кости, удалить\nIK-constraints и control-кости. Делать ПЕРЕД Export IFP —\nиначе ифп получит сырые ротации без учёта IK.": "Bake the visual IK pose onto the deform bones and remove\n    IK-constraints and control bones. Do this BEFORE Export IFP —\n    otherwise IFP would get raw rotations without IK applied.",
    "Создать \"пол\" — плоскость 10×10м с процедурной сеткой,\n    которая работает как ограничитель для ног IK-рига. После\n    Add IK Rig стопы автоматически получают Floor constraint\n    с этой плоскостью как target — двигаешь плоскость по Z,\n    стопы клемпятся выше неё. Зазор (offset над плоскостью)\n    настраивается слайдером \"Зазор\" ": "Create a 'floor' - a 10x10m plane with a procedural grid that acts as a clamp for the IK-rig legs. After Add IK Rig the feet automatically get a Floor constraint with this plane as target - move the plane along Z and the feet are clamped above it. The gap (offset above the plane) is adjustable with the 'Gap' slider.",
    "Создать \"пол\" — плоскость 10×10м с процедурной сеткой,\nкоторая работает как ограничитель для ног IK-рига. После\nAdd IK Rig стопы автоматически получают Floor constraint\nс этой плоскостью как target — двигаешь плоскость по Z,\nстопы клемпятся выше неё. Зазор (offset над плоскостью)\nнастраивается слайдером \"Зазор\" ": "Create a 'floor' - a 10x10m plane with a procedural grid that acts as a clamp for the IK-rig legs. After Add IK Rig the feet automatically get a Floor constraint with this plane as target - move the plane along Z and the feet are clamped above it. The gap (offset above the plane) is adjustable with the 'Gap' slider.",
    "Извлечь все DFF, COL и текстуры из IMG-архивов GTA SA.\n\nКеш создаётся в папке .inu_cache/ рядом с твоим .blend файлом,\nпоэтому сцену нужно сначала сохранить — без сохранённого .blend\nкешу некуда лечь, и оператор откажется работать.\n\nРегиональный фильтр (если выбран) сужает извлечение до TXD/моделей,\nреально используемых в этом регионе по IDE/IPL — экономит минуты\nна больших картах. ALL = извлечь всё": "Extract all DFF, COL and textures from GTA SA IMG archives.\n\n    The cache is created in the .inu_cache/ folder next to your .blend file,\n    so the scene must be saved first — without a saved .blend there's\n    nowhere to put the cache, and the operator will refuse to run.\n\n    The region filter (when chosen) narrows extraction to TXD/models\n    actually used in that region per IDE/IPL — saves minutes\n    on big maps. ALL = extract everything",
    "Импорт всех моделей из IMG: по IPL (с расстановкой) ИЛИ по IDE (все\n    определённые модели, разложенные сеткой). Геометрия и ТЕКСТУРЫ достаются\n    из IMG on-the-fly (текстуры — по содержимому, IDE не требуется).": "Import all models from IMG: by IPL (with placement) OR by IDE (all defined models laid out in a grid). Geometry and TEXTURES are pulled from the IMG on-the-fly (textures by content, no IDE required).",
    "Импорт всех моделей из IMG: по IPL (с расстановкой) ИЛИ по IDE (все\nопределённые модели, разложенные сеткой). Геометрия и ТЕКСТУРЫ достаются\nиз IMG on-the-fly (текстуры — по содержимому, IDE не требуется).": "Import all models from IMG: by IPL (with placement) OR by IDE (all defined models laid out in a grid). Geometry and TEXTURES are pulled from the IMG on-the-fly (textures by content, no IDE required).",
    "Проверить, в каком IMG-архиве папки игры лежит DFF выделенных моделей,\nи обновить статус «В IMG» (img_target_file). Не найдено ни в одном архиве →\nстатус станет «Не в IMG». Читает только оглавления архивов (быстро)": "Check which IMG archive of the game folder holds the DFF of the selected models, and update the 'In IMG' status (img_target_file). Not found in any archive -> the status becomes 'Not in IMG'. Reads only the archive tables of contents (fast).",
    "Перестроить (компактировать) IMG-архив: убрать мёртвое место,\n    оставшееся от перезаписей моделей (replace добавляет данные в конец,\n    старый блок не освобождается). Файл заменяется атомарно.": "Rebuild (compact) an IMG archive: remove the dead space left from model overwrites (replace appends data at the end, the old block is not freed). The file is replaced atomically.",
    "Перестроить (компактировать) IMG-архив: убрать мёртвое место,\nоставшееся от перезаписей моделей (replace добавляет данные в конец,\nстарый блок не освобождается). Файл заменяется атомарно.": "Rebuild (compact) an IMG archive: remove the dead space left from model overwrites (replace appends data at the end, the old block is not freed). The file is replaced atomically.",
    "Найти IDE: прочитать выбранный IPL и найти в указанной папке .ide-файлы,\n    где определены его модели (по Model ID). Если папка — корень игры (есть\n    data/gta.dat), берётся канонический список; иначе рекурсивный скан *.ide.\n    Если модели из разных IDE — покажет список. Ничего не импортирует.": "Find IDE: read the chosen IPL and find in the given folder the .ide files where its models are defined (by Model ID). If the folder is the game root (has data/gta.dat), the canonical list is used; otherwise a recursive *.ide scan. If models come from different IDEs - it shows a list. Imports nothing.",
    "Найти IDE: прочитать выбранный IPL и найти в указанной папке .ide-файлы,\nгде определены его модели (по Model ID). Если папка — корень игры (есть\ndata/gta.dat), берётся канонический список; иначе рекурсивный скан *.ide.\nЕсли модели из разных IDE — покажет список. Ничего не импортирует.": "Find IDE: read the chosen IPL and find in the given folder the .ide files where its models are defined (by Model ID). If the folder is the game root (has data/gta.dat), the canonical list is used; otherwise a recursive *.ide scan. If models come from different IDEs - it shows a list. Imports nothing.",
    "Найти IMG: прочитать выбранный IPL и найти в папке игры все .img архивы,\n    в которых реально лежат DFF его моделей. Модели кастомной карты часто\n    разложены по нескольким .img (напр. maps/RESOURCES) — импорт затем тянет их\n    из всех найденных архивов, а не только из основного. Ничего не импортирует.": "Find IMG: read the chosen IPL and find in the game folder all the .img archives that actually hold the DFF of its models. Custom-map models are often spread across several .img (e.g. maps/RESOURCES) - the import then pulls them from all the archives found, not just the main one. Imports nothing.",
    "Найти IMG: прочитать выбранный IPL и найти в папке игры все .img архивы,\nв которых реально лежат DFF его моделей. Модели кастомной карты часто\nразложены по нескольким .img (напр. maps/RESOURCES) — импорт затем тянет их\nиз всех найденных архивов, а не только из основного. Ничего не импортирует.": "Find IMG: read the chosen IPL and find in the game folder all the .img archives that actually hold the DFF of its models. Custom-map models are often spread across several .img (e.g. maps/RESOURCES) - the import then pulls them from all the archives found, not just the main one. Imports nothing.",
    "Открыть сайт в браузере (обёртка над wm.url_open с нормальным тултипом).": "Open a website in the browser (a wrapper over wm.url_open with a proper tooltip).",
    "Открыть файл (IDE/IPL) во ВНЕШНЕМ текстовом редакторе ОС (как двойной\n    клик в проводнике — Блокнот и т.п.), не в редакторе Blender.": "Open a file (IDE/IPL) in the OS's EXTERNAL text editor (like a double-click in Explorer - Notepad etc.), not in Blender's editor.",
    "Открыть файл (IDE/IPL) во ВНЕШНЕМ текстовом редакторе ОС (как двойной\nклик в проводнике — Блокнот и т.п.), не в редакторе Blender.": "Open a file (IDE/IPL) in the OS's EXTERNAL text editor (like a double-click in Explorer - Notepad etc.), not in Blender's editor.",
    "Импорт GTA SA файлов (.dff/.col/.cst/.txd/.ide/.ipl) с авто-определением формата": "Import GTA SA files (.dff/.col/.cst/.txd/.ide/.ipl) with automatic format detection.",
    "Быстрый экспорт одной модели (машина / пед) в ОДИН .dff.\n\n    Включает режим «Один DFF» + формат DFF и сразу открывает диалог Export All\n    — остаётся выбрать папку/имя и нажать Export. Коллизия машины (меш +\n    сферы) встраивается в .dff автоматически. Кнопка для тематических вкладок\n    («Машины», «Скины»), чтобы не искать экспорт в общем меню.": "Quick export of a single model (vehicle / ped) to ONE .dff. Enables 'Single DFF' mode + DFF format and opens the Export All dialog right away - you only pick folder/name and press Export. The vehicle's collision (mesh + spheres) is embedded into the .dff automatically. A button for the themed tabs ('Vehicles', 'Skins') so you don't have to hunt for export in the general menu.",
    "Быстрый экспорт одной модели (машина / пед) в ОДИН .dff.\n\nВключает режим «Один DFF» + формат DFF и сразу открывает диалог Export All\n— остаётся выбрать папку/имя и нажать Export. Коллизия машины (меш +\nсферы) встраивается в .dff автоматически. Кнопка для тематических вкладок\n(«Машины», «Скины»), чтобы не искать экспорт в общем меню.": "Quick export of a single model (vehicle / ped) to ONE .dff. Enables 'Single DFF' mode + DFF format and opens the Export All dialog right away - you only pick folder/name and press Export. The vehicle's collision (mesh + spheres) is embedded into the .dff automatically. A button for the themed tabs ('Vehicles', 'Skins') so you don't have to hunt for export in the general menu.",
    "Экспорт выделенных моделей в .dff — по одному файлу на модель.\n\n    Зеркало импорта: выделил несколько моделей → получил несколько .dff\n    (имена из имён моделей), части одной модели (иерархия) → в один файл.\n    Тот же общий движок, что и Export All, только включён один формат.": "Export the selected models to .dff - one file per model. The mirror of import: you select several models -> you get several .dff (names from the model names), parts of one model (hierarchy) -> into one file. The same shared engine as Export All, just with a single format enabled.",
    "Экспорт выделенных моделей в .dff — по одному файлу на модель.\n\nЗеркало импорта: выделил несколько моделей → получил несколько .dff\n(имена из имён моделей), части одной модели (иерархия) → в один файл.\nТот же общий движок, что и Export All, только включён один формат.": "Export the selected models to .dff - one file per model. The mirror of import: you select several models -> you get several .dff (names from the model names), parts of one model (hierarchy) -> into one file. The same shared engine as Export All, just with a single format enabled.",
    "Прилайт листвы: темнее в центре кроны, светлее на периферии,\n    + опциональная смена цвета листвы (tint). Геометрический градиент,\n    без света сцены — для billboard-листвы деревьев.": "Foliage prelight: darker in the center of the crown, lighter at the edges, + optional foliage tint change. A geometric gradient, no scene light - for billboard tree foliage.",
    "Прилайт листвы: темнее в центре кроны, светлее на периферии,\n+ опциональная смена цвета листвы (tint). Геометрический градиент,\nбез света сцены — для billboard-листвы деревьев.": "Foliage prelight: darker in the center of the crown, lighter at the edges, + optional foliage tint change. A geometric gradient, no scene light - for billboard tree foliage.",
    "Сбросить прилайт модели к состоянию, сохранённому при «Запечь цвет».": "Reset the model's prelight to the state saved at 'Bake color'.",
    "Добавить кольцо в список резака света": "Add a ring to the light-cutter list.",
    "Удалить кольцо из списка резака света": "Remove a ring from the light-cutter list.",
    "Создать вайр-резак света (цилиндр с кольцами или сфера). Меняй\n    радиус/сегменты/кольца — он обновляется вживую. Двигай куда нужно,\n    затем «Нарезать по резаку».": "Create a wire light-cutter (a cylinder with rings, or a sphere). Change radius/segments/rings - it updates live. Move it where needed, then 'Cut by cutter'.",
    "Создать вайр-резак света (цилиндр с кольцами или сфера). Меняй\nрадиус/сегменты/кольца — он обновляется вживую. Двигай куда нужно,\nзатем «Нарезать по резаку».": "Create a wire light-cutter (a cylinder with rings, or a sphere). Change radius/segments/rings - it updates live. Move it where needed, then 'Cut by cutter'.",
    "Нарезать по резаку: либо чистый отдельный диск (кольца+заливка,\n    повторяет рельеф), либо врезать кольца в пол. Запекает радиальный\n    градиент света (центр ярко → край тёмно, кольца = ступени плавности).": "Cut by the cutter: either a clean separate disc (rings+fill, following the relief), or cut rings into the floor. Bakes a radial light gradient (bright center -> dark edge, rings = smoothness steps).",
    "Нарезать по резаку: либо чистый отдельный диск (кольца+заливка,\nповторяет рельеф), либо врезать кольца в пол. Запекает радиальный\nградиент света (центр ярко → край тёмно, кольца = ступени плавности).": "Cut by the cutter: either a clean separate disc (rings+fill, following the relief), or cut rings into the floor. Bakes a radial light gradient (bright center -> dark edge, rings = smoothness steps).",
    "Создать/удалить «солнце» для prelight (отдельно от 8 точек).\n\n    Направленный источник под углом «сверху-спереди» (как солнце GTA), цвет\n    как у 8 ламп. Запекается теми же кнопками (POINT и SUN считаются вместе).\n    Энергию подгони, если ярче/темнее восьмёрки.": "Create/remove a 'sun' for prelight (separate from the 8 points). A directional source at a 'top-front' angle (like the GTA sun), colored like the 8 lamps. Baked with the same buttons (POINT and SUN are counted together). Tune the energy if it's brighter/darker than the eight.",
    "Создать/удалить «солнце» для prelight (отдельно от 8 точек).\n\nНаправленный источник под углом «сверху-спереди» (как солнце GTA), цвет\nкак у 8 ламп. Запекается теми же кнопками (POINT и SUN считаются вместе).\nЭнергию подгони, если ярче/темнее восьмёрки.": "Create/remove a 'sun' for prelight (separate from the 8 points). A directional source at a 'top-front' angle (like the GTA sun), colored like the 8 lamps. Baked with the same buttons (POINT and SUN are counted together). Tune the energy if it's brighter/darker than the eight.",
    "Залить прилайт одним плоским цветом: Day своим цветом, Night своим.\n\n    RGB пишется напрямую в `color_srgb` (байт-в-байт, без gamma —\n    значения COLOR_GAMMA-пропа уже в sRGB), вертекс-альфа сохраняется.\n    Дефолты — доминирующие тона из test.dff (день 124, ночь 83).": "Fill the prelight with one flat color: Day with its color, Night with its own. RGB is written directly into 'color_srgb' (byte-for-byte, no gamma - the COLOR_GAMMA prop values are already in sRGB), vertex alpha is preserved. Defaults are the dominant tones from test.dff (day 124, night 83).",
    "Залить прилайт одним плоским цветом: Day своим цветом, Night своим.\n\nRGB пишется напрямую в `color_srgb` (байт-в-байт, без gamma —\nзначения COLOR_GAMMA-пропа уже в sRGB), вертекс-альфа сохраняется.\nДефолты — доминирующие тона из test.dff (день 124, ночь 83).": "Fill the prelight with one flat color: Day with its color, Night with its own. RGB is written directly into 'color_srgb' (byte-for-byte, no gamma - the COLOR_GAMMA prop values are already in sRGB), vertex alpha is preserved. Defaults are the dominant tones from test.dff (day 124, night 83).",
    "Объединить выделенные меши во временную модель для покраски прилайта\n    кистью сразу по всем. Оригиналы сохраняются (скрыты); «Разъединить»\n    вернёт их как были — со своими именами и центрами.": "Merge the selected meshes into a temporary model to paint the prelight with a brush across all of them at once. The originals are kept (hidden); 'Split' returns them as they were - with their own names and origins.",
    "Объединить выделенные меши во временную модель для покраски прилайта\nкистью сразу по всем. Оригиналы сохраняются (скрыты); «Разъединить»\nвернёт их как были — со своими именами и центрами.": "Merge the selected meshes into a temporary model to paint the prelight with a brush across all of them at once. The originals are kept (hidden); 'Split' returns them as they were - with their own names and origins.",
    "Разъединить: перенести покраску прилайта обратно на оригиналы (Day и\n    Night), вернуть их видимыми со своими именами/центрами, удалить\n    временную модель.": "Split: transfer the prelight painting back onto the originals (Day and Night), return them visible with their own names/origins, and delete the temporary model.",
    "Разъединить: перенести покраску прилайта обратно на оригиналы (Day и\nNight), вернуть их видимыми со своими именами/центрами, удалить\nвременную модель.": "Split: transfer the prelight painting back onto the originals (Day and Night), return them visible with their own names/origins, and delete the temporary model.",
    "Перенести АЛЬФУ вершин с активного цветового атрибута (Day/Night)\n    на второй, сохранив его RGB. Направление определяется тем, какой\n    атрибут сейчас выбран радиокнопкой: активный Day → льёт альфу в Night,\n    активный Night → в Day. Если атрибута-приёмника ещё нет — он создаётся\n    полной копией активного (RGB+альфа), чтобы не остался мусорный цвет.\n    Работает по всем выделенным мешам (у каждого свой активный атрибут).": "Transfer the vertex ALPHA from the active color attribute (Day/Night) to the other one, keeping its RGB. The direction depends on which attribute is currently selected by the radio button: active Day -> pours alpha into Night, active Night -> into Day. If the target attribute doesn't exist yet - it is created as a full copy of the active one (RGB+alpha) so no junk color remains. Works across all selected meshes (each has its own active attribute).",
    "Перенести АЛЬФУ вершин с активного цветового атрибута (Day/Night)\nна второй, сохранив его RGB. Направление определяется тем, какой\nатрибут сейчас выбран радиокнопкой: активный Day → льёт альфу в Night,\nактивный Night → в Day. Если атрибута-приёмника ещё нет — он создаётся\nполной копией активного (RGB+альфа), чтобы не остался мусорный цвет.\nРаботает по всем выделенным мешам (у каждого свой активный атрибут).": "Transfer the vertex ALPHA from the active color attribute (Day/Night) to the other one, keeping its RGB. The direction depends on which attribute is currently selected by the radio button: active Day -> pours alpha into Night, active Night -> into Day. If the target attribute doesn't exist yet - it is created as a full copy of the active one (RGB+alpha) so no junk color remains. Works across all selected meshes (each has its own active attribute).",
    "Показать прозрачность по альфе вершин во вьюпорте, независимо от\n    превью prelight (RGB). Заводит альфа-канал активного слоя в Alpha\n    материала и включает blended-режим отрисовки.": "Show transparency by vertex alpha in the viewport, independently of the prelight (RGB) preview. Feeds the active layer's alpha channel into the material's Alpha and enables blended draw mode.",
    "Показать прозрачность по альфе вершин во вьюпорте, независимо от\nпревью prelight (RGB). Заводит альфа-канал активного слоя в Alpha\nматериала и включает blended-режим отрисовки.": "Show transparency by vertex alpha in the viewport, independently of the prelight (RGB) preview. Feeds the active layer's alpha channel into the material's Alpha and enables blended draw mode.",
    "Проверить сцену и удалить ноды превью альфы (AlphaView_*) из всех\n    материалов, которым они больше не нужны — где вертекс-альфа стёрта или\n    меш стал полностью непрозрачным. Материалы, ещё используемые\n    прозрачными мешами, не трогаются.": "Check the scene and remove the alpha-preview nodes (AlphaView_*) from all materials that no longer need them - where the vertex alpha was erased or the mesh became fully opaque. Materials still used by transparent meshes are left untouched.",
    "Проверить сцену и удалить ноды превью альфы (AlphaView_*) из всех\nматериалов, которым они больше не нужны — где вертекс-альфа стёрта или\nмеш стал полностью непрозрачным. Материалы, ещё используемые\nпрозрачными мешами, не трогаются.": "Check the scene and remove the alpha-preview nodes (AlphaView_*) from all materials that no longer need them - where the vertex alpha was erased or the mesh became fully opaque. Materials still used by transparent meshes are left untouched.",
    "Выбрать папку для хранения всех пресетов и данных INU Tools.\n    Существующие пресеты копируются в новую папку.": "Choose the folder for storing all INU Tools presets and data. Existing presets are copied to the new folder.",
    "Выбрать папку для хранения всех пресетов и данных INU Tools.\nСуществующие пресеты копируются в новую папку.": "Choose the folder for storing all INU Tools presets and data. Existing presets are copied to the new folder.",
    "Вернуть папку пресетов к расположению по умолчанию": "Return the presets folder to its default location.",
    "Открыть текущую папку пресетов в проводнике": "Open the current presets folder in the file explorer.",
    "Включить или выключить все текстовые IPL в списке одной кнопкой": "Turn all text IPL in the list on or off with one button.",
    "Открыть документацию аддона на GitHub. Язык подбирается\nпод текущую локаль Blender.": "Open the addon's documentation on GitHub. Language is picked\n    to match the current Blender locale.",
    "Открыть страницу последнего релиза на GitHub — там полный\nchangelog текущей версии, рендерится из RELEASE_NOTES.": "Open the latest release page on GitHub — full changelog of\n    the current version, rendered from RELEASE_NOTES.",
    "Проверить все материалы со слотами Paintjob:\nоба слота должны быть заполнены, и у материала должна быть основная\nтекстура — иначе игра не подхватит paintjob в Pay'n'Spray.": "Validate all materials with Paintjob slots:\n    both slots must be filled, and the material must have a main\n    texture — otherwise the game won't pick up the paintjob in Pay'n'Spray.",
    "Bulk-set sapath_* свойств для всех выделенных Curve.\n\nОпции с -1 / 0 значением «не менять». Полезно для разом установить\ntype=Vehicle + traffic=enabled + spawn=1.0 на массу путей после\nимпорта или ручной правки.": "Bulk-set sapath_* properties on all selected Curves.\n\n    Options with a -1 / 0 value mean «keep as is». Handy for setting\n    type=Vehicle + traffic=enabled + spawn=1.0 on lots of paths after\n    import or manual edits in one go.",
    "Добавить TrafficLight / RoadBlock / Connector / SpecialNode на\nактивный knot выделенной Curve.": "Add a TrafficLight / RoadBlock / Connector / SpecialNode on the\n    active knot of the selected Curve.",
    "Включить фоновую синхронизацию позиций path accessory'ев\nс их родительскими Curve'ами": "Enable background sync of path accessory positions\n    with their parent Curves",
    "Загрузить строки из plants.dat в список для редактирования.\n    Текущий список будет заменён.": "Load the lines from plants.dat into the list for editing. The current list will be replaced.",
    "Загрузить строки из plants.dat в список для редактирования.\nТекущий список будет заменён.": "Load the lines from plants.dat into the list for editing. The current list will be replaced.",
    "Записать список обратно в plants.dat. Старый файл сохраняется\n    рядом как plants.dat.bak.": "Write the list back to plants.dat. The old file is saved next to it as plants.dat.bak.",
    "Записать список обратно в plants.dat. Старый файл сохраняется\nрядом как plants.dat.bak.": "Write the list back to plants.dat. The old file is saved next to it as plants.dat.bak.",
    "Добавить новую запись травы. Имя поверхности берётся из активного\n    COL-материала, если он есть.": "Add a new grass entry. The surface name is taken from the active COL material, if there is one.",
    "Добавить новую запись травы. Имя поверхности берётся из активного\nCOL-материала, если он есть.": "Add a new grass entry. The surface name is taken from the active COL material, if there is one.",
    "Удалить выбранную запись травы.": "Delete the selected grass entry.",
    "Показать траву — переключатель живого предпросмотра. Пока активна,\n    трава автоматически обновляется при правке параметров. Нажми ещё раз,\n    чтобы убрать.": "Show grass - a live preview toggle. While active, the grass updates automatically as you edit the parameters. Click again to remove it.",
    "Показать траву — переключатель живого предпросмотра. Пока активна,\nтрава автоматически обновляется при правке параметров. Нажми ещё раз,\nчтобы убрать.": "Show grass - a live preview toggle. While active, the grass updates automatically as you edit the parameters. Click again to remove it.",
    "Убрать предпросмотр травы.": "Remove the grass preview.",
    "Сгенерировать траву РЕАЛЬНОЙ ГЕОМЕТРИЕЙ (постоянный меш-объект),\n    который экспортируется вместе с моделью. В отличие от предпросмотра —\n    объект остаётся в сцене и не удаляется.": "Generate grass as REAL GEOMETRY (a permanent mesh object) that is exported together with the model. Unlike the preview - the object stays in the scene and is not deleted.",
    "Сгенерировать траву РЕАЛЬНОЙ ГЕОМЕТРИЕЙ (постоянный меш-объект),\nкоторый экспортируется вместе с моделью. В отличие от предпросмотра —\nобъект остаётся в сцене и не удаляется.": "Generate grass as REAL GEOMETRY (a permanent mesh object) that is exported together with the model. Unlike the preview - the object stays in the scene and is not deleted.",
    "Удалить сгенерированную геометрию травы.": "Delete the generated grass geometry.",
    "Назначить поверхность выбранной grass-записи выделенным полигонам.\n    Материал коллизии с нужным ID создаётся автоматически.": "Assign the surface of the selected grass entry to the selected polygons. A collision material with the required ID is created automatically.",
    "Назначить поверхность выбранной grass-записи выделенным полигонам.\nМатериал коллизии с нужным ID создаётся автоматически.": "Assign the surface of the selected grass entry to the selected polygons. A collision material with the required ID is created automatically.",
    "Дублировать выбранную запись (удобно для второго PCDid одной\n    поверхности).": "Duplicate the selected entry (handy for a second PCDid of the same surface).",
    "Дублировать выбранную запись (удобно для второго PCDid одной\nповерхности).": "Duplicate the selected entry (handy for a second PCDid of the same surface).",
    "Просканировать TXD по выбранному источнику и заполнить\nTexture Browser метаданными (без декодинга пикселей)": "Scan TXD from the chosen source and populate\n    Texture Browser with metadata (without decoding pixels)",
    "Включить / выключить альфу (прозрачность) на всех материалах сцены.\n\n    ВКЛ — подключает альфу текстуры к шейдеру там, где у текстуры есть\n    прозрачные пиксели (листва, заборы, окна), и ставит HASHED.\n    ВЫКЛ — снимает связь и делает материалы OPAQUE.": "Turn alpha (transparency) on/off on all scene materials. ON - connects the texture alpha to the shader where the texture has transparent pixels (foliage, fences, windows) and sets HASHED. OFF - removes the link and makes the materials OPAQUE.",
    "Включить / выключить альфу (прозрачность) на всех материалах сцены.\n\nВКЛ — подключает альфу текстуры к шейдеру там, где у текстуры есть\nпрозрачные пиксели (листва, заборы, окна), и ставит HASHED.\nВЫКЛ — снимает связь и делает материалы OPAQUE.": "Turn alpha (transparency) on/off on all scene materials. ON - connects the texture alpha to the shader where the texture has transparent pixels (foliage, fences, windows) and sets HASHED. OFF - removes the link and makes the materials OPAQUE.",
    "Запустить полную проверку сцены: paintjob слоты, нормировку\nкватернионов в Action'ах, Modulate Color на прилайтах и парность\n_ok/_dam. Результаты пишутся в панель — кликом можно перейти к\nпроблемному объекту или починить автоматически.": "Run a full scene check: paintjob slots, Action quaternion\n    normalisation, Modulate Color on prelight meshes and\n    _ok/_dam pairing. Results are written to the panel — a click\n    can jump to the problem object or fix it automatically.",
    "Нормализовать все кватернионные ключи в указанном Action.\nИдентично тому что делает IFP-экспортёр на лету, но пишет правку\nобратно в Action — на след. экспорт уже нечего нормировать.": "Normalise every quaternion key in the specified Action.\n    Identical to what the IFP exporter does on the fly, but writes the\n    fix back into the Action — next export has nothing left to normalise.",
    "Переименовать объект, заменив неправильный разделитель в\nсуффиксе на тот, что задан в настройках суффиксов сцены.\n\nПрименимо только к мисматчу типа «.DFF при настройке _DFF» —\nт.е. имя оканчивается на конфигурированный bare-token, но через\nдругой разделитель. Двойной суффикс (body_LOD_DFF) не трогаем —\nтам нет однозначного автоматического fix'а.": "Rename the object, replacing the wrong separator in the\n    suffix with the one set in scene suffix preferences.\n\n    Applies only to mismatches like «.DFF when configured as _DFF» —\n    i.e. the name ends with the configured bare-token but via\n    a different separator. A double suffix (body_LOD_DFF) is left\n    alone — there's no unambiguous automatic fix.",
    "Применить стандартные SA-настройки для материала кузова машины:\nenv map = xvehicleenv128, specular = vehiclespecdot64, blend = 0.05, + Vehicle pipeline.\nЭквивалент кнопки \"SA Vehicle default\" из Kam's GTA_Material.ms.": "Apply standard SA vehicle body settings:\nenv map = xvehicleenv128, specular = vehiclespecdot64, blend = 0.05, + Vehicle pipeline.\nEquivalent to Kam's GTA_Material.ms 'SA Vehicle default' button.",
    "Привязать вершины воды к ближайшему узлу лимитной сетки (кратным 500 — углы блоков воды GTA SA)": "Snap water vertices to the nearest node of the limit grid (multiples of 500 - GTA SA water block corners).",
    "Показать сетку блоков воды 500×500 и подсветить грани: зелёный — влезает, оранжевый — на границе, красный — больше 500": "Show the 500x500 water block grid and highlight faces: green - fits, orange - on the border, red - larger than 500.",
    "Временно слить co-located вершины для редактирования весов.\n\n    Backup'ит mesh datablock, усредняет веса между cluster-mate'ами,\n    делает bmesh remove_doubles. В Outliner'е остаётся один объект.\n    ": "Temporarily merge co-located vertices for weight editing. Backs up the mesh datablock, averages weights between cluster-mates, and does a bmesh remove_doubles. In the Outliner one object remains.",
    "Временно слить co-located вершины для редактирования весов.\n\nBackup'ит mesh datablock, усредняет веса между cluster-mate'ами,\nделает bmesh remove_doubles. В Outliner'е остаётся один объект.": "Temporarily merge co-located vertices for weight editing. Backs up the mesh datablock, averages weights between cluster-mates, and does a bmesh remove_doubles. In the Outliner one object remains.",
    "Применить покрашенные веса обратно на оригинальную split-геометрию.\n\n    Считывает веса с merged-меша, swap'ает mesh datablock обратно на\n    backup (со split-вершинами), распределяет веса по cluster-mate'ам\n    через position-match.\n    ": "Apply the painted weights back onto the original split geometry. Reads the weights from the merged mesh, swaps the mesh datablock back to the backup (with split vertices), and distributes the weights to the cluster-mates by position-match.",
    "Применить покрашенные веса обратно на оригинальную split-геометрию.\n\nСчитывает веса с merged-меша, swap'ает mesh datablock обратно на\nbackup (со split-вершинами), распределяет веса по cluster-mate'ам\nчерез position-match.": "Apply the painted weights back onto the original split geometry. Reads the weights from the merged mesh, swaps the mesh datablock back to the backup (with split vertices), and distributes the weights to the cluster-mates by position-match.",
    "Откатить merge без сохранения покрашенных весов.\n\n    Swap'ает mesh datablock обратно на backup, удаляет merged-копию.\n    Веса покрашенные в merged-режиме теряются.\n    ": "Roll back the merge without saving the painted weights. Swaps the mesh datablock back to the backup and deletes the merged copy. Weights painted in merged mode are lost.",
    "Откатить merge без сохранения покрашенных весов.\n\nSwap'ает mesh datablock обратно на backup, удаляет merged-копию.\nВеса покрашенные в merged-режиме теряются.": "Roll back the merge without saving the painted weights. Swaps the mesh datablock back to the backup and deletes the merged copy. Weights painted in merged mode are lost.",
    "Импорт зон из map.zon / info.zon — каждая зона становится\n    рамкой-боксом в сцене. Повторный импорт того же файла заменяет\n    старые боксы": "Import zones from map.zon / info.zon - each zone becomes a box frame in the scene. Re-importing the same file replaces the old boxes.",
    "Импорт зон из map.zon / info.zon — каждая зона становится\nрамкой-боксом в сцене. Повторный импорт того же файла заменяет\nстарые боксы": "Import zones from map.zon / info.zon - each zone becomes a box frame in the scene. Re-importing the same file replaces the old boxes.",
    "Экспорт зон обратно в map.zon / info.zon. Пишутся выделенные боксы,\n    а если ничего не выделено — вся коллекция ZON_<имя файла>.\n    Незатронутые зоны сохраняются строка в строку, старый файл\n    копируется рядом как .bak": "Export zones back to map.zon / info.zon. The selected boxes are written, and if nothing is selected - the whole ZON_<filename> collection. Untouched zones are preserved line by line, the old file is copied next to it as .bak.",
    "Экспорт зон обратно в map.zon / info.zon. Пишутся выделенные боксы,\nа если ничего не выделено — вся коллекция ZON_<имя файла>.\nНезатронутые зоны сохраняются строка в строку, старый файл\nкопируется рядом как .bak": "Export zones back to map.zon / info.zon. The selected boxes are written, and if nothing is selected - the whole ZON_<filename> collection. Untouched zones are preserved line by line, the old file is copied next to it as .bak.",
    "Сгенерировать строки зон для выделенных объектов и положить их в\n    буфер обмена — можно сразу вставить в map.zon. Строки заодно кладутся\n    в текстовый блок INU_map_zon (Text Editor). Для обычного меша зона\n    считается по его габаритам": "Generate zone lines for the selected objects and put them on the clipboard - you can paste them straight into map.zon. The lines are also placed in the INU_map_zon text block (Text Editor). For an ordinary mesh the zone is computed from its bounds.",
    "Сгенерировать строки зон для выделенных объектов и положить их в\nбуфер обмена — можно сразу вставить в map.zon. Строки заодно кладутся\nв текстовый блок INU_map_zon (Text Editor). Для обычного меша зона\nсчитается по его габаритам": "Generate zone lines for the selected objects and put them on the clipboard - you can paste them straight into map.zon. The lines are also placed in the INU_map_zon text block (Text Editor). For an ordinary mesh the zone is computed from its bounds.",
    "Создать новую зону — бокс 100×100×100 в позиции 3D-курсора.\n    Имя, тип, уровень и GXT-ключ правятся ниже в панели": "Create a new zone - a 100x100x100 box at the 3D cursor position. The name, type, level and GXT key are edited below in the panel.",
    "Создать новую зону — бокс 100×100×100 в позиции 3D-курсора.\nИмя, тип, уровень и GXT-ключ правятся ниже в панели": "Create a new zone - a 100x100x100 box at the 3D cursor position. The name, type, level and GXT key are edited below in the panel.",
    "Удалить неиспользуемые текстуры и (опционально) материалы из сцены.\n\nuse_fake_user-помеченные datablocks пропускаются — это явный знак\n«оставить даже без ссылок». Действие необратимо без Ctrl+Z, поэтому\nпоказывает подтверждение со счётчиками перед удалением": "Remove unused textures and (optionally) materials from the scene.\n\n    use_fake_user-flagged datablocks are skipped — that's an explicit signal\n    «keep even with no references». The action is irreversible without Ctrl+Z, so it\n    shows a confirmation with counters before deleting",
    "Скопировать GTA-настройки активного материала на материалы всех\n    выделенных объектов (эффекты, фильтр текстуры, RW-затенение, цвет).": "Copy the active material's GTA settings onto the materials of all selected objects (effects, texture filter, RW shading, color).",
    "Скопировать GTA-настройки активного материала на материалы всех\nвыделенных объектов (эффекты, фильтр текстуры, RW-затенение, цвет).": "Copy the active material's GTA settings onto the materials of all selected objects (effects, texture filter, RW shading, color).",
    "Создать новый профиль. Маленький popup только с именем и\nописанием — все панели включаются по умолчанию, видимость и\nпорядок настраиваются после через кнопку ⚙ (Edit Profile).": "Create a new profile. A small popup with just the name and\n    description — all panels are on by default; visibility and\n    order are tuned afterwards via the ⚙ button (Edit Profile).",
    "Click-to-pick / click-to-place reorder: первый клик «берёт»\nпанель (она подсвечивается), второй клик по другой панели\n«кладёт» её на это место. Эмулирует drag-and-drop через два\nклика — Blender Python не отдаёт настоящий drag для custom\nitems в popup'е.": "Click-to-pick / click-to-place reorder: first click «picks» a\n    panel (it highlights), second click on another panel\n    «places» it at that spot. Emulates drag-and-drop via two\n    clicks — Blender Python doesn't expose a real drag for custom\n    items in a popup.",
    "Eye-toggle: переключает видимость одной панели в активном\nпрофиле. Позиция панели в `order` не меняется — только\nmembership в `hidden` set.": "Eye-toggle: flips visibility of a single panel in the active\n    profile. The panel's position in `order` isn't changed —\n    only membership in the `hidden` set.",
    "Открыть редактор активного профиля в отдельном popup-окне.\nТа же UI что и inline-список, но скрытая за одной кнопкой —\nmain panel остаётся чистой пока юзер не настраивает layout.": "Open the editor for the active profile in a separate popup\n    window. Same UI as the inline list, but hidden behind one\n    button — the main panel stays clean until the user tunes layout.",
    "Вписать острова в масштаб сетки (вариант B): равномерно масштабировать\n    каждый остров так, чтобы его ВЫСОТА (при Рядах) или ШИРИНА (при Колонках)\n    в UV стала = Значение / Размер текстуры. Пропорции сохраняются, 3D-размер\n    не учитывается (чистая доля UV). Работает только по рядам ИЛИ колонкам.": "Fit islands to the grid scale (variant B): uniformly scale each island so its HEIGHT (for Rows) or WIDTH (for Columns) in UV becomes = Value / Texture size. Proportions are kept, 3D size is ignored (pure UV fraction). Works by rows OR columns only.",
    "Вписать острова в масштаб сетки (вариант B): равномерно масштабировать\nкаждый остров так, чтобы его ВЫСОТА (при Рядах) или ШИРИНА (при Колонках)\nв UV стала = Значение / Размер текстуры. Пропорции сохраняются, 3D-размер\nне учитывается (чистая доля UV). Работает только по рядам ИЛИ колонкам.": "Fit islands to the grid scale (variant B): uniformly scale each island so its HEIGHT (for Rows) or WIDTH (for Columns) in UV becomes = Value / Texture size. Proportions are kept, 3D size is ignored (pure UV fraction). Works by rows OR columns only.",
    "Настоящий тексель: равномерно масштабировать каждый остров так, чтобы\n    плотность текселя стала = Значение px/юнит — по площади (UV↔3D), как в\n    TexTools. Учитывает реальный размер геометрии (детализация выравнивается).\n    Примечание: считает по локальной геометрии — применяй масштаб объекта.": "True texel: uniformly scale each island so the texel density becomes = Value px/unit - by area (UV<->3D), like in TexTools. Takes the real geometry size into account (detail is evened out). Note: it computes on local geometry - apply the object scale.",
    "Настоящий тексель: равномерно масштабировать каждый остров так, чтобы\nплотность текселя стала = Значение px/юнит — по площади (UV↔3D), как в\nTexTools. Учитывает реальный размер геометрии (детализация выравнивается).\nПримечание: считает по локальной геометрии — применяй масштаб объекта.": "True texel: uniformly scale each island so the texel density becomes = Value px/unit - by area (UV<->3D), like in TexTools. Takes the real geometry size into account (detail is evened out). Note: it computes on local geometry - apply the object scale.",
    "Вставить ключ UV-анимации (Сдвиг/Масштаб) на текущем кадре": "Insert a UV-animation key (Offset/Scale) at the current frame.",
    "Удалить все ключи UV-анимации этого материала": "Delete all UV-animation keys of this material.",
    "Добавить новый слой в текущий стек (Day или Night).\n\nСоздаёт ``BYTE_COLOR``/``CORNER`` атрибут с префиксом ``VCL_D_`` или\n``VCL_N_`` и инициализирует его прозрачным (alpha=0). Стек ограничен\n10 слоями — операция отказывает с предупреждением при переполнении": "Add a new layer to the current stack (Day or Night).\n\n    Creates a ``BYTE_COLOR``/``CORNER`` attribute prefixed with ``VCL_D_`` or\n    ``VCL_N_`` and initialises it as transparent (alpha=0). Stack is capped\n    at 10 layers — operation refuses with a warning on overflow",
    "Сделать слой полноценным прилайт-атрибутом (убрать VCL_<scope>_ префикс).\n\nАтрибут останется на меше под коротким именем — но из стека VCL\nисчезнет. Полезно когда заведомо «временный» слой пора зафиксировать\nкак новый базовый прилайт": "Promote a layer to a full-fledged prelight attribute (strip the VCL_<scope>_ prefix).\n\n    The attribute stays on the mesh under the short name — but disappears\n    from the VCL stack. Useful when a deliberately «temporary» layer is ready\n    to be locked in as a new base prelight",
    "Сделать атрибут Day или Night активным в Color Attributes.\n\nВ hijack-режиме (Live Preview ON) Day и Night содержат итоговую\nкомпозицию своего стека — клик на эту кнопку просто переключает\nактивный color attribute на нужный, чтобы viewport показал нужный\nстек. Если Live Preview OFF — Day/Night содержат оригиналы, кнопки\nработают как обычный «выбрать атрибут»": "Make the Day or Night attribute active in Color Attributes.\n\n    In hijack mode (Live Preview ON) Day and Night contain the final\n    composition of their stack — clicking this button just switches the\n    active color attribute to the one you need so the viewport shows the\n    right stack. If Live Preview is OFF — Day/Night contain the originals,\n    the buttons behave like a regular «pick attribute»",
    "Пересобрать composite в Day/Night вручную.\n\nИспользуется когда нужно форсировать пересчёт без триггера через\nслайдер — например после ручного редактирования атрибутов через\nMesh Data Properties": "Rebuild the Day/Night composite manually.\n\n    Used when you need to force a recompute without triggering via a\n    slider — e.g. after manually editing the attributes via\n    Mesh Data Properties",
    "Применить значение слайдера к выделенным слоям.\n\nРежим 'ABSOLUTE' — всем выделенным присваивается одно и то же\nзначение. 'RELATIVE' — каждое значение сдвигается на дельту\nотносительно своего текущего": "Apply the slider value to the selected layers.\n\n    Mode 'ABSOLUTE' — all selected get the same value. 'RELATIVE' —\n    each value is shifted by the delta relative to its current one",
    "Перекрасить выделенные слои — заменить RGB всех окрашенных\nпикселей на выбранный цвет (alpha сохраняется).\n\nПолезно когда хочешь поменять оттенок группы слоёв, не трогая то\nчто под ними и не перерисовывая руками": "Recolor selected layers — replace the RGB of every coloured\n    pixel with the chosen colour (alpha is preserved).\n\n    Useful when you want to change the tint of a group of layers without\n    touching what's underneath or repainting by hand",
    "Сделать color attribute этого слоя активным на меше + (опционально) переключиться в Vertex Paint.\n\nИспользуется UIList'ом — клик по строке слоя сразу даёт пользователю\nрисовать в нужный атрибут без ручного переключения в Mesh Data\nProperties → Color Attributes": "Make this layer's color attribute active on the mesh + (optionally) switch to Vertex Paint.\n\n    Used by the UIList — clicking on a layer row lets the user paint into\n    the correct attribute without manually switching in Mesh Data\n    Properties → Color Attributes",
    # ── Raw (non-T) descriptions localized by audit ──
    "Ariane watcher (вкл/выкл)": "Ariane watcher (on/off)",
    "Ariane: импортировать сейчас": "Ariane: import now",
    "Ariane: обновить позицию": "Ariane: update position",
    "Ariane: отправить обратно": "Ariane: send back",
    "Ariane: очистить кэш моста": "Ariane: clear bridge cache",
    "Ariane: создать модель": "Ariane: create model",
    "INU: + Кольцо": "INU: + Ring",
    "INU: - Кольцо": "INU: - Ring",
    "INU: Export DFF (по моделям)": "INU: Export DFF (per model)",
    "INU: Добавить в IDE + IPL": "INU: Add to IDE + IPL",
    "INU: Найти IDE по IPL": "INU: Find IDE by IPL",
    "INU: Найти IMG по IPL": "INU: Find IMG by IPL",
    "INU: Нарезать по резаку": "INU: Cut by cutter",
    "INU: Открыть в текст-редакторе": "INU: Open in text editor",
    "INU: Открыть сайт": "INU: Open website",
    "INU: Отцепить кисти": "INU: Detach hands",
    "INU: Прилайтить листву": "INU: Prelight foliage",
    "INU: Прицепить кисти к скелету": "INU: Attach hands to skeleton",
    "INU: Сброс цвета листвы": "INU: Reset foliage color",
    "INU: Создать резак света": "INU: Create light cutter",
    "INU: Убрать из IDE/IPL": "INU: Remove from IDE/IPL",
    "INU: Экспорт (один DFF)": "INU: Export (single DFF)",
    "INU: Экспорт жеста в ghands.ifp": "INU: Export gesture to ghands.ifp",
    "Выбрать слой": "Select layer",
    "Запечь только слой с этим ключом (uid|map_id) — для per-layer «Запечь», чтобы не затрагивать другие слои той же карты": "Bake only the layer with this key (uid|map_id) — for per-layer 'Bake', so the other layers of the same map are not affected",
    "Запечь только эту карту (пусто = все включённые слои)": "Bake only this map (empty = all enabled layers)",
    "Индекс слоя (-1 = выбранный)": "Layer index (-1 = selected)",
    "Интервал опроса": "Poll interval",
    "Искать .ide и во всех вложенных папках": "Search for .ide in all subfolders too",
    "Искать .ipl и во всех вложенных папках": "Search for .ipl in all subfolders too",
    "Какую карту сохранить (пусто = выбранный слой)": "Which map to save (empty = selected layer)",
    "Папка игры (ariane)": "Game folder (ariane)",
    "Переместить слой": "Move layer",
    "Привязывать только выделенные объекты (иначе всю сцену)": "Bind only the selected objects (otherwise the whole scene)",
    "Режим панели": "Panel mode",
    "Сохранить карту": "Save map",
    "Трава": "Grass",
    "Удалить слой": "Delete layer",
    # ── end raw-descriptions audit ──
    # ── Added by locale audit: strings that were missing from EN ──
    "В какой IMG писать при «Экспорт в IMG»: родной IMG модели (img_target_file) или конкретный архив из папки игры. Обновляет запись, если модель там есть, иначе добавляет": "Which IMG to write to on 'Export to IMG': the model's own IMG (img_target_file) or a specific archive from the game folder. Updates the entry if the model is already there, otherwise adds it",
    "Live: синхронизация удалений в обе стороны. Удалил в Blender → мягкое удаление инстанса в ariane; удалил в ariane → объект СКРЫВАЕТСЯ в Blender (обратимо — undelete в ariane его показывает). Выключено по умолчанию, чтобы можно было удалять свободно, не трогая другую сторону": "Live: two-way deletion sync. Delete in Blender → soft-delete the instance in ariane; delete in ariane → the object is HIDDEN in Blender (reversible — undelete in ariane brings it back). Off by default so you can delete freely without touching the other side",
    "Bevel только вдоль ВЫДЕЛЕННЫХ рёбер: маска по вершинам выделенных рёбер домножается на маску кромок. Действует ТОЛЬКО на Bevel. Переход у ребра мягкий (интерполяция по граням). Выдели рёбра в Edit Mode перед запеканием": "Bevel only along SELECTED edges: a mask over the vertices of the selected edges is multiplied by the edge mask. Affects ONLY Bevel. The transition at the edge is soft (interpolated across faces). Select the edges in Edit Mode before baking",
    "Изолировать объект": "Isolate object",
    "На время бейка прятать прочие МЕШ-объекты сцены (лампы не трогаются). Чинит чёрный AO (соседи по сцене больше не затеняют модель) и ускоряет бейк (Cycles строит BVH только по цели). Выкл = запекать с тенями от соседей": "Hide the other MESH objects in the scene during baking (lamps are left alone). Fixes black AO (scene neighbours no longer occlude the model) and speeds up baking (Cycles builds the BVH for the target only). Off = bake with shadows from neighbours",
    "Показать ползунки визуальной коррекции превью прилайта (яркость/контраст/гамма/насыщенность). Только вьюпорт — на экспорт не влияет": "Show the sliders for visual correction of the prelight preview (brightness/contrast/gamma/saturation). Viewport only — does not affect export",
    "Пересобрать после экспорта": "Rebuild after export",
    "После записи сжать (компактнуть) IMG-архив — убрать мёртвое место от старых версий моделей": "After writing, compact the IMG archive — remove the dead space left by old versions of the models",
    "IMG архив": "IMG archive",
    "LOD: основная модель (заглушка)": "LOD: main model (stub)",
    "COL: пустая заглушка": "COL: empty stub",
    "Открыть наш форк Ariane (GitHub) — редактор карт для round-trip с аддоном (временно, до релиза Ariane)": "Open our Ariane fork (GitHub) — a map editor for round-trip with the addon (temporary, until Ariane's release)",
    "Путь к IMG-архиву, откуда модель импортирована (или куда последний раз экспортирована). Даёт статус «В IMG» и цель по умолчанию для экспорта модели в IMG": "Path to the IMG archive the model was imported from (or last exported to). Provides the 'In IMG' status and the default target for exporting the model to IMG",
    "Model ID на момент последней привязки к IDE. Если текущий Model ID отличается (например скопировал модель и сменил ID) — привязка к старой строке IDE неактуальна": "The Model ID at the time of the last IDE link. If the current Model ID differs (e.g. you copied the model and changed the ID), the link to the old IDE line is no longer valid",
    "Включить DFF модели в экспорт": "Include the model's DFF in the export",
    "Экспортировать LOD этой модели. Если LOD в сцене нет — уйдёт копия основной модели под LOD-именем": "Export this model's LOD. If there is no LOD in the scene, a copy of the main model is written under the LOD name",
    "Экспортировать COL (коллизию). Если COL в сцене нет — будет создана пустая габаритная COL-заглушка": "Export the COL (collision). If there is no COL in the scene, an empty bounding-box COL stub is created",
    # ── end audit additions ──
    "Радиус узла в вершинах": "Junction radius on vertices",
    "INU: Радиус узла в вершинах": "INU: Junction Radius On Vertices",
    "Радиус узла задан вершинам:": "Junction radius set on vertices:",
    "Насколько далеко от этой вершины обрываются лучи. Развилке нужен радиус побольше: тогда между расходящимися дорогами появляется клин. 0 — общий радиус из модификатора": "How far from this vertex the arms are cut off. A fork needs a larger radius: that is what leaves a gore between the diverging roads. 0 — the shared radius from the modifier",
    "Радиус узла, который кнопка запишет выделенным вершинам. Развилке нужен побольше: тогда между расходящимися дорогами появляется клин. 0 — общий радиус из модификатора": "The junction radius the button writes to the selected vertices. A fork needs a larger one: that is what leaves a gore between the diverging roads. 0 — the shared radius from the modifier",
    "Тип узла": "Junction type",
    "Площадка": "Plate",
    "Без узла": "No junction",
    "Лучи подрезаются, между ними строится площадка перекрёстка": "The arms are trimmed and a junction plate is built between them",
    "Лучи доводятся до самой вершины, между ними ничего не строится": "The arms run all the way to the vertex and nothing is built between them",
    "Тип узла на выделенных вершинах": "Junction type on the selected vertices",
    "Тип узла задан вершинам:": "Junction type set on vertices:",
    "INU: Тип узла": "INU: Junction Type",
    "Урезать радиус так, чтобы дуга влезла между соседними вершинами. Держи включённым: без него на коротком отрезке дуги налезают друг на друга, путь разворачивается сам на себя, дорога закольцовывается и Blender может встать намертво. Выключать имеет смысл только когда вершины стоят заведомо далеко друг от друга": "Trim the radius so the arc fits between neighbouring vertices. Keep it on: without it the arcs overlap on a short segment, the path folds back on itself, the road closes into a loop and Blender can hang. Turning it off makes sense only when the vertices are known to be far apart",
    "Вершина": "Vertex",
    "Радиус поворота в этой вершине, метры": "Turn radius at this vertex, metres",
    "Свои радиусы по вершинам": "Per-vertex radii",
    "INU: Обновить список радиусов": "INU: Refresh The Radii List",
    "INU: Добавить вершины в список": "INU: Add Vertices To The List",
    "INU: Убрать вершину из списка": "INU: Remove A Vertex From The List",
    "INU: Выделить вершину списка": "INU: Select The Listed Vertex",
    "Вершин со своим радиусом:": "Vertices with their own radius:",
    "Добавлено вершин:": "Vertices added:",
    "Вершина убрана:": "Vertex removed:",
    "Выделена вершина:": "Vertex selected:",
    "Ограничивать радиус": "Limit the radius",
    "Урезать радиус так, чтобы дуга влезла между соседними вершинами. Пока включено, поворот меняет радиус сам, когда ты двигаешь соседние точки — в том числе по высоте. Выключено: радиус ровно такой, какой задан, но на коротком отрезке дуги могут налезть друг на друга": "Trim the radius so the arc fits between neighbouring vertices. While this is on, a turn changes its own radius whenever you move the neighbouring points — height included. Off: the radius is exactly what you asked for, but on a short segment the arcs may overlap",
    "Радиус поворота, который кнопка «Радиус в вершинах» запишет выделенным вершинам сети. 0 — вернуть им общий радиус из модификатора": "The turn radius the «Radius on vertices» button writes to the selected network vertices. 0 — give them back the shared radius from the modifier",
    "Радиус в вершинах": "Radius on vertices",
    "INU: Радиус в вершинах": "INU: Radius On Vertices",
    "Радиус задан вершинам:": "Radius set on vertices:",
    "Радиус поворота": "Turn radius",
    "Сегментов в повороте": "Turn segments",
    "Сохранить": "Save",
    "Загрузить": "Load",
    "INU: Сохранить радиусы": "INU: Save Radii",
    "INU: Загрузить радиусы": "INU: Load Radii",
    "У этой сети радиусы не задавались": "No radii were set on this network",
    "Радиусов сохранено:": "Radii saved:",
    "Радиусов возвращено:": "Radii restored:",
    "Не нашлось вершин под:": "No vertices found for:",
    "В файле нет радиусов": "The file has no radii",
    "Не удалось сохранить:": "Could not save:",
    "Не удалось прочитать:": "Could not read:",
    "Допуск": "Tolerance",
    "Радиус скругления углов перекрёстка, метры. По умолчанию 0: контур площадки состоит из точек устьев, и скругление срезает именно те углы, которыми она приваривается к дороге. Включай, только если сечение частое": "Corner rounding radius of the junction, metres. 0 by default: the junction contour is made of the road mouths, and rounding cuts exactly the corners it is welded to the road by. Turn it up only when the section is dense",
    "Скругление углов": "Corner rounding",
    "Радиус скругления углов перекрёстка, метры. 0 — острые углы": "Corner rounding radius of the junction, metres. 0 — sharp corners",
    "Группа": "Group",
    "Устарела, нужна": "Outdated, needs",
    "Обновить дорогу": "Update the road",
    "Сеть": "Network",
    "Радиус узла": "Junction radius",
    "На сколько метров дороги не доходят до узловой вершины. Этот же радиус задаёт размер самого перекрёстка: его устья стоят ровно там, где кончается полотно": "How many metres the roads stop short of a junction vertex. The same radius sets the size of the junction itself: its mouths sit exactly where the road surface ends",
    "Ширина": "Width",
    "Ширина ленты, когда сечение не задано, метры": "Width of the plain strip when no section is given, metres",
    "Объект, с переднего края которого берётся форма дороги. Моделируй его сверху: X — поперёк дороги (0 = ось), Y — вдоль, Z — высота. Пусто — дорога будет простой лентой заданной ширины": "The object whose front edge gives the road its shape. Model it from above: X — across the road (0 = centreline), Y — along, Z — height. Empty — the road is a plain strip of the given width",
    "Включи, если твой кусок вытянут по X, а не по Y": "Turn this on if your piece runs along X rather than Y",
    "Длина стартового ребра, метры. Дальше тянешь его как обычную сетку: E — новое ребро, M — слить вершины в перекрёсток": "Length of the starting edge, metres. From there you pull it like any mesh: E for a new edge, M to merge vertices into a junction",
    "Сеть создана. Сечение можно указать в параметрах, иначе дорога будет лентой": "Network created. You can set the section in the parameters, otherwise the road stays a plain strip",
    "Сеть создана по сечению:": "Network created from the section:",
    "INU: Дорога из моей сетки": "INU: Road From My Mesh",
    "Дорога из моей сетки": "Road from my mesh",
    "Активным должен быть меш-сеть": "The active object must be the network mesh",
    "Сеть навешена на:": "Network attached to:",
    "INU: Пересобрать группу сети": "INU: Rebuild Network Group",
    "Группа сети пересобрана": "Network group rebuilt",
    "Выдели свой кусок вместе с дорогой": "Select your piece together with the road",
    "Собрать дороги в сеть": "Merge roads into a network",
    "INU: Собрать дороги в сеть": "INU: Merge Roads Into A Network",
    "Выдели хотя бы две дороги": "Select at least two roads",
    "Дороги разного вида — у сети останется вид активной": "The roads are of different kinds — the network keeps the active one's kind",
    "Не удалось собрать:": "Could not merge:",
    "Дорог собрано:": "Roads merged:",
    "Вместо построенного узла разложить по пересечениям выделенный меш. Тогда выдели его вместе с дорогами": "Instead of the built junction, lay the selected mesh at every crossing. Select it together with the roads then",
    "Разложить мой кусок": "Lay out my piece",
    "Дорога не привязана": "No road linked",
    "Перестроить": "Rebuild",
    "Встроенный профиль на кривую": "Built-in profile onto the curve",
    "Тайлами": "By tiles",
    "По сечению": "By section",
    "Выдели свой кусок вместе с кривой": "Select your piece together with the curve",
    "Из моего объекта": "From my object",
    "Запас": "Margin",
    "На сколько метров узел выходит за расчётные углы. Больше запас — шире перекрёсток и дальше отходят дороги": "How many metres the junction extends past the computed corners. A larger margin means a wider junction and roads pulled further back",
    "Сегментов в углу": "Corner segments",
    "Из скольких отрезков собран скруглённый угол перекрёстка. 0 — острый угол": "How many segments make up a rounded junction corner. 0 — a sharp corner",
    "Замер направления": "Direction probe",
    "На каком расстоянии от узла снимается направление дороги. Меньше — точнее на крутых поворотах, больше — устойчивее на мелко нарезанных кривых": "How far from the junction the road direction is measured. Smaller is more accurate on tight bends, larger is steadier on finely cut curves",
    "Сколько метров узла занимает один повтор текстуры": "How many metres of the junction one texture repeat takes",
    "Не удалось построить перекрёстки:": "Could not build the junctions:",
    "Перекрёстков построено:": "Junctions built:",
    "Из пересечений не вышло ни одного узла: в каждом меньше трёх лучей": "None of the crossings produced a junction: each has fewer than three arms",
    "Точки": "Points",
    "Узел": "Junction piece",
    "Перекрёстки": "Junctions",
    "Перекрёстки на дорогах": "Junctions on roads",
    "INU: Перекрёстки на дорогах": "INU: Junctions On Roads",
    "Кусок перекрёстка": "Junction piece",
    "Объект-узел, который ляжет в каждую точку пересечения дорог. Моделируй его сверху и по центру: начало координат — середина перекрёстка, X и Y — лучи дорог": "The junction object placed at every crossing of the roads. Model it from above and centred: the origin is the middle of the junction, X and Y are the road arms",
    "Доворот": "Extra turn",
    "Общий доворот всех кусков вокруг вертикали. Нужен, если ты смоделировал узел лучами не по X, а по диагонали": "A shared turn of every piece around the vertical. Needed if you modelled the junction with its arms diagonal rather than along X",
    "Общий масштаб кусков. Проще подогнать им размер узла под ширину дороги, чем перемоделировать сам кусок": "A shared scale of the pieces. Easier to match the junction size to the road width than to remodel the piece",
    "Объект перекрёстков. Дорога сама вырежет в себе дырку под каждым куском, чтобы полотно не лезло сквозь него. Пока поле пустое, ничего не вырезается": "The junctions object. The road cuts a hole in itself under every piece so the surface does not poke through it. While the field is empty nothing is cut",
    "Зазор выреза": "Cut clearance",
    "На сколько метров вокруг куска перекрёстка убирается полотно. Дырка получается по форме самого куска: режется всё, что ближе этого зазора к нему. Больше зазор — шире щель по краю": "How many metres around the junction piece the road surface is removed. The hole takes the shape of the piece itself: everything closer than this clearance is cut. A larger clearance means a wider gap along the edge",
    "Выдели дороги — хотя бы одну кривую": "Select roads — at least one curve",
    "Дороги нигде не пересекаются в плане": "The roads do not cross anywhere in plan",
    "Не удалось посчитать перекрёстки:": "Could not compute the junctions:",
    "Перекрёстков найдено:": "Junctions found:",
    "Выбери кусок узла в поле «Кусок перекрёстка»": "Pick the junction piece in the «Junction piece» field",
    "размах куска": "piece reach",
    "м": "m",
    "Дороги (коллекция)": "Roads (collection)",
    "Коллекция дорог, если их несколько объектов: земля подстроится под все сразу. Одна кривая с несколькими сплайнами — тоже несколько дорог, её достаточно положить в поле «Дорога»": "A collection of roads when there is more than one object: the ground adapts to all of them at once. One curve with several splines is several roads too — that one only needs the «Road» field",
    "Сечение": "Section",
    "Объект, с переднего края которого снимается форма дороги. Моделируй его сверху: X — поперёк дороги (0 = ось), Y — вдоль, Z — высота. Сколько вершин в переднем ряду, столько полос и будет у дороги": "The object whose front edge gives the road its shape. Model it from above: X — across the road (0 = centreline), Y — along, Z — height. As many vertices as the front row has, as many strips the road gets",
    "Сечение вдоль X": "Section runs along X",
    "Включи, если твой кусок вытянут по X, а не по Y — он будет повёрнут на 90° перед снятием сечения": "Turn this on if your piece runs along X rather than Y — it will be rotated by 90° before the section is taken",
    "Длина одного полигона вдоль дороги. Держится постоянной: тянешь сплайн — секции не растягиваются, а добавляются новые": "Length of one polygon along the road. It stays constant: stretch the spline and the sections do not stretch, new ones are added",
    "Радиус скругления углов кривой, метры. 0 — выключить": "Corner rounding radius of the curve, metres. 0 — off",
    "Сколько метров дороги занимает один повтор текстуры вдоль. Считается от пройденного расстояния, поэтому UV не растянется ни при какой длине дороги": "How many metres of road one texture repeat takes along it. Computed from the distance travelled, so the UVs never stretch at any road length",
    "Сколько метров поперёк дороги занимает один повтор текстуры. Считается по самому сечению, от его левого края: поставь равным ширине сечения — и текстура ляжет ровно по ширине, от 0 до 1": "How many metres across the road one texture repeat takes. Measured along the section itself from its left edge: set it to the section width and the texture fits the width exactly, from 0 to 1",
    "INU: Дорога по моему сечению": "INU: Road From My Section",
    "Дорога по моему сечению": "Road from my section",
    "Сечение протянуто вдоль кривой:": "Section swept along the curve:",
    "Выбери объект-сечение в поле «Сечение»": "Pick the section object in the «Section» field",
    "Свой кусок: выдели его вместе с кривой": "Your own piece: select it together with the curve",
    "Сечение: передний ряд тянется вперёд,": "Section: the front row is swept forward,",
    "длина секции своя, UV считаются в метрах": "its own section length, UVs measured in metres",
    "Тайл: кусок целиком кладётся копиями": "Tile: the whole piece is laid out as copies",
    "материалы с сечения, UV по метрам": "materials from the section, UVs by metres",
    "Дробление тайла": "Tile subdivision",
    "Сколько раз поделить тайл перед укладкой. Нужно, если ты нарезал его редко: на повороте такой тайл срезает угол, сколько бы их ни легло. Каждое деление учетверяет полигоны, так что 1-2 обычно хватает": "How many times to subdivide the tile before laying it. Needed if you cut it sparsely: on a bend such a tile cuts the corner no matter how many are laid. Each subdivision quadruples the polygons, so 1-2 is usually enough",
    "Шаг клетки": "Cage step",
    "Расстояние между точками клетки, метры. Держится постоянным: растёт участок — точек становится больше, а не реже": "Distance between cage points, metres. It stays constant: as the patch grows there are more points, not sparser ones",
    "Сторона клетки, метры. Берётся из участка": "Side of the cage, metres. Taken from the patch",
    "Подогнать клетку под размер участка, сохранив вылепленное": "Fit the cage to the patch size, keeping what was sculpted",
    "Вылепленное сохранится:": "What you sculpted is kept:",
    "новые точки достроятся вокруг, плоскими": "new points are added around it, flat",
    "Размер полигона": "Polygon size",
    "Сторона треугольника земли, метры. Держится постоянной: тянешь участок больше — полигоны не растягиваются, а добавляются новые. На склонах их тоже становится больше, потому что склон длиннее своей проекции. Ставь примерно в длину секции дороги": "Side of a ground triangle, metres. It stays constant: stretch the patch and the polygons do not stretch, new ones are added. Slopes get more of them too, because a slope is longer than its footprint. Set it close to the road section length",
    "Сторона треугольника земли, метры": "Side of a ground triangle, metres",
    "Сглаживание": "Smooth shading",
    "Мягкое затенение вдоль дороги. Без него на изгибах видны грани секций. Учти, что сглаживается и перелом на бордюре с откосом — если нужен чёткий край, выключи": "Soft shading along the road. Without it the section facets show on bends. Note that the crease at the shoulder and slope gets smoothed too — turn it off if you need a crisp edge",
    "Мягкое затенение земли и перехода. Без него на холмах и на стыке с дорогой видны отдельные грани": "Soft shading of the ground and the skirt. Without it individual facets show on the hills and at the seam with the road",
    "Захват, шагов сетки": "Reach, grid steps",
    "На сколько шагов собственной сетки земля дотягивается до кромки перехода. Считается от шага, а не в метрах, поэтому работает при любом разрешении. Меньше полутора — до кромки дотянутся не все точки и она пойдёт зубцами; больше — утянет к дороге лишние ряды": "How many of its own grid steps the ground reaches out to the skirt edge. Measured in steps rather than metres, so it works at any resolution. Below one and a half not every point reaches the edge and it comes out jagged; above that it drags in extra rows",
    "Полоса между дорогой и землёй, которую земля строит сама. Держи меньше радиуса самого крутого поворота: она откладывается от кромки, а отступ шире радиуса заворачивается сам на себя. 0 — без перехода, земля пришивается прямо к дороге": "The band between road and ground that the ground builds itself. Keep it below the tightest turn radius: it is offset from the edge, and an offset wider than the radius folds over itself. 0 — no skirt, the ground is sewn straight to the road",
    "Плотность перехода": "Skirt density",
    "Во сколько раз внешний край перехода плотнее или реже дороги, степенями двойки. Минус — реже, плюс — плотнее, 0 — как у дороги. Подбирай так, чтобы сойтись с шагом сетки земли": "How much denser or sparser the skirt's outer edge is than the road, in powers of two. Minus — sparser, plus — denser, 0 — same as the road. Tune it to match your ground grid step",
    "Плотность края": "Edge density",
    "Во сколько раз внешний край плотнее или реже дороги, степенями двойки. Минус — реже: -1 вдвое, -2 вчетверо, -3 в восемь раз. Плюс — плотнее, ровно так же. 0 — как у дороги, один ровный ряд. Рядов строится столько, сколько нужно шагов: по одному на каждое удвоение или деление": "How much denser or sparser the outer edge is than the road, in powers of two. Minus — sparser: -1 twice, -2 four times, -3 eight times. Plus — denser, exactly the same way. 0 — same as the road, one plain ring. As many rings are built as there are steps: one per doubling or halving",
    "не привязан": "not linked",
    "На сколько метров земля ниже полотна там, где она уходит под него. Нужно, только если земля пришивается прямо к дороге, без перехода: небольшой зазор убирает мерцание совпавших поверхностей. На саму кромку не влияет — она всегда садится точно": "How many metres the ground sits below the road where it runs underneath. Needed only when the ground is sewn straight to the road with no skirt: a small gap removes z-fighting between coincident surfaces. It does not affect the rim itself — that always lands exactly",
    "Длина секции": "Section length",
    "Длина одного полигона вдоль дороги. Она держится постоянной: тянешь сплайн — секции не растягиваются, а добавляются новые. Меньше длина — плавнее повороты и больше полигонов": "Length of one polygon along the road. It stays constant: drag the spline and the sections do not stretch, new ones are added instead. Shorter — smoother turns and more polygons",
    "Секций": "Sections",
    "На сколько секций делится дорога вдоль кривой. Больше секций — плавнее повороты и больше полигонов. От этого же числа считает переход: каждый его ряд прореживает вершины вдвое": "How many sections the road is split into along the curve. More sections — smoother turns and more polygons. The skirt counts from this same number: each of its rings halves the vertex count",
    "Рядов": "Rings",
    "Сколько рядов в переходе. Каждый ряд прореживает вершины вдвое: 1 ряд — вдвое реже дороги, 2 ряда — вчетверо, 3 — в восемь раз. Считай, сколько раз надо поделить пополам, чтобы дойти до плотности своей земли": "How many rings the skirt has. Each ring halves the vertex count: 1 ring — twice as sparse as the road, 2 rings — four times, 3 — eight times. Count how many halvings it takes to reach your ground's density",
    "Переход": "Skirt",
    "Объект перехода между дорогой и землёй. Земля не лезет туда, где он лежит, и садится точно на его внешний край. Пусто — земля пришивается прямо к дороге": "The skirt object between road and ground. The ground stays out of where it lies and lands exactly on its outer edge. Empty — the ground is sewn straight to the road",
    "Объект дороги, от кромки которого строится переход": "The road object whose edge the skirt is built from",
    "Ширина перехода": "Skirt width",
    "Насколько переход уходит от кромки дороги, метры. Держи меньше радиуса самого крутого поворота: кольца строятся отступом от контура, а отступ шире радиуса заворачивается сам на себя": "How far the skirt reaches from the road edge, metres. Keep it below the tightest turn radius: the rings are built by offsetting the outline, and an offset wider than the radius folds over itself",
    "Шаг на внешнем крае, м": "Outer edge step, m",
    "Расстояние между вершинами на внешнем крае. Поставь равным шагу сетки своей земли — тогда плотности совпадут и земля пришьётся один к одному": "Distance between vertices on the outer edge. Set it equal to your ground grid step — then the densities match and the ground sews one to one",
    "Спуск наружу": "Outward drop",
    "На сколько метров внешний край ниже кромки дороги. 0 — переход идёт горизонтально от того уровня, где кончился откос": "How many metres the outer edge sits below the road edge. 0 — the skirt runs level from where the slope ended",
    "Сколько метров занимает один повтор текстуры": "How many metres one texture repeat covers",
    "INU: Новый переход": "INU: New Skirt",
    "Создать переход между дорогой и землёй": "Create the skirt between road and ground",
    "Выдели дорогу": "Select a road",
    "Не удалось создать переход:": "Could not create the skirt:",
    "Переход создан:": "Skirt created:",
    "INU: Привязать переход": "INU: Link Skirt",
    "Привязать переход к активному ландшафту": "Link the skirt to the active terrain",
    "Выдели переход вместе с ландшафтом": "Select the skirt together with the terrain",
    "Переход привязан:": "Skirt linked:",
    "Переход у дороги": "Skirt at the road",
    "Привязать переход": "Link skirt",
    "Дорога и переход": "Road and skirt",
    "Ширина кольца": "Ring width",
    "Ширина одного кольца перехода, метры. Колец три, так что полоса перехода выходит втрое шире. Ставь около шага сетки земли": "Width of one transition ring, metres. There are three rings, so the transition band comes out three times as wide. Set it close to the ground grid step",
    "Сшивать автоматически": "Stitch automatically",
    "Пересобирать шов с дорогой сам, как только подвинешь сплайн, клетку или параметры. Считается не во время движения, а после того как отпустишь": "Rebuild the seam with the road by itself as soon as you move the spline, the cage or a parameter. It computes after you let go, not while you drag",
    "INU: Сшить ландшафт с дорогой": "INU: Stitch Terrain To Road",
    "Сшить землю с дорогой: чистый шов вершина в вершину": "Stitch the ground to the road: a clean vertex-to-vertex seam",
    "Ширина полосы": "Band width",
    "Полоса земли вдоль дороги, которая снимается и перекладывается заново. 0 — посчитать от радиуса притягивания. Должна быть шире него, иначе кривые веера от живой врезки останутся на месте": "The band of ground along the road that gets stripped and rebuilt. 0 — derive it from the snap radius. It must be wider than that radius, otherwise the crooked fans from the live carve stay put",
    "Скрыть исходники": "Hide the sources",
    "Спрятать процедурный ландшафт после сшивки. Сам он никуда не девается — правишь дальше и жмёшь кнопку снова": "Hide the procedural terrain after stitching. It does not go anywhere — keep editing and press the button again",
    "Сначала укажи дорогу в поле «Дорога»": "Pick the road in the «Road» field first",
    "Не удалось сшить:": "Could not stitch:",
    "Сшито:": "Stitched:",
    "в шве": "in the seam",
    "Шов с дорогой:": "Seam with the road:",
    "полоса у дороги перекладывается заново": "the band along the road is rebuilt from scratch",
    "вершина в вершину, без щелей и T-стыков": "vertex to vertex, no cracks and no T-junctions",
    "Сшить с дорогой": "Stitch to road",
    "На каком расстоянии от дороги точки земли садятся на её вершины, метры. Ставь примерно в полтора шага сетки: мало — до кромки дотянутся не все точки и она пойдёт зубцами, много — утянет к дороге лишние ряды": "Within what distance from the road ground points land on its vertices, metres. Set it to about one and a half grid steps: too little and not every point reaches the rim, so it comes out jagged; too much and it drags in extra rows",
    "Кромка садится на вершины дороги:": "The rim lands on the road's vertices:",
    "шаг сегмента дороги ≥ шага сетки земли": "road segment step ≥ ground grid step",
    "Клетка": "Cage",
    "Редкая сетка, которой ты лепишь крупную форму. Тянешь её точки вверх — под ними вырастает гора. Читается вертикально сверху, поэтому двигать имеет смысл по Z": "The sparse grid you shape the large forms with. Pull its points up and a mountain grows beneath them. It is read vertically from above, so moving along Z is what counts",
    "Сторона квадратного куска земли, метры. Большие территории лучше собирать из нескольких участков — их проще резать на модели под лимиты игры": "Side of the square ground patch, metres. Large areas are better assembled from several patches — they are easier to split into models within the game's limits",
    "Сколько вершин по стороне. Чем больше, тем чётче кромка у дороги и тем тяжелее сцена. 128 на участок в 200 м даёт шаг примерно полтора метра": "Vertices per side. The more there are, the crisper the rim at the road and the heavier the scene. 128 over a 200 m patch gives about a metre and a half per step",
    "Создать процедурный участок земли вместе с клеткой управления": "Create a procedural ground patch together with its control cage",
    "Сколько вершин по стороне у самой земли": "Vertices per side of the ground itself",
    "Разрешение клетки": "Cage resolution",
    "Сколько точек по стороне у клетки. Редкая клетка даёт плавные крупные формы, частая — больше контроля и больше возни": "Points per side of the cage. A sparse cage gives smooth large forms, a dense one gives more control and more fiddling",
    "Сколько точек по стороне у клетки": "Points per side of the cage",
    "INU: Править клетку ландшафта": "INU: Edit Terrain Cage",
    "Перейти к правке клетки активного ландшафта": "Jump into editing the active terrain's cage",
    "У этого ландшафта нет клетки — укажи её в поле «Клетка»": "This terrain has no cage — pick one in the «Cage» field",
    "Не удалось войти в правку:": "Could not enter edit mode:",
    "Тяни точки клетки по Z — земля пойдёт следом": "Pull the cage points along Z — the ground follows",
    "INU: Перестроить клетку": "INU: Rebuild Cage",
    "Заново выложить клетку с другим размером и плотностью": "Lay out the cage again with a different size and density",
    "Сторона клетки, метры. Обычно равна размеру участка": "Side of the cage, metres. Normally equal to the patch size",
    "Клетка выкладывается заново — всё, что было вылеплено, сбросится": "The cage is laid out from scratch — everything you sculpted is reset",
    "Не удалось перестроить клетку:": "Could not rebuild the cage:",
    "Клетка перестроена:": "Cage rebuilt:",
    "Править клетку": "Edit cage",
    "Перестроить клетку": "Rebuild cage",
    "Крупную форму задаёт клетка:": "The cage sets the large shape:",
    "выдели точки → G Z → тяни вверх": "select points → G Z → pull up",
    "рельеф и врезка пересчитаются следом": "relief and carving recompute right after",
    "Разброс высот сгенерированного рельефа, метры. 0 — плоско, и тогда останется только то, что вылепишь руками": "Height spread of the generated relief, metres. 0 — flat, leaving only what you shape by hand",
    "Детализация рельефа": "Relief detail",
    "Сколько мелких слоёв подмешивается к крупным холмам. 0 — гладкие волны, 4-6 — похоже на настоящую местность, больше — каменистая изрезанность и лишние полигоны в запекании": "How many fine layers are mixed into the large hills. 0 — smooth waves, 4-6 — looks like real terrain, more — rocky ruggedness and wasted polygons at bake time",
    "Рельеф генерируется, правки — поверх него:": "The relief is generated, your edits go on top:",
    "вылепленное переживает смену параметров": "what you sculpt survives parameter changes",
    "Вырезать под дорогой": "Carve under the road",
    "Убрать землю из-под полотна и посадить кромку дырки ровно на его контур. Выключено — земля просто продавливается под дорогу, не разрываясь": "Remove the ground from under the road surface and seat the hole rim exactly on its outline. Off — the ground is merely pressed down under the road, unbroken",
    "Радиус притягивания": "Snap radius",
    "На каком расстоянии от дороги точки земли притягиваются к её контуру, метры. Ставь примерно в полтора шага сетки: мало — кромка получится зубчатой, много — утянет к дороге лишнее": "Within what distance from the road ground points get snapped to its outline, metres. Set it to about one and a half grid steps: too little and the rim comes out jagged, too much and it drags in more than it should",
    "Высота шума": "Noise height",
    "Разброс мелкой неровности поверх вылепленной формы, метры. 0 — только то, что вылепил руками": "Spread of the fine unevenness on top of the sculpted shape, metres. 0 — only what you shaped by hand",
    "Размер холмов шума": "Noise hill size",
    "Сколько метров занимает один бугор шума. Меньше — мелкая рябь, больше — пологие складки": "How many metres one noise bump spans. Smaller — fine ripple, larger — gentle folds",
    "Вариант шума": "Noise variant",
    "Сдвигает шум. Меняй, если рисунок не нравится — размеры останутся те же": "Shifts the noise. Change it if you dislike the pattern — the sizes stay the same",
    "Объект дороги, под который подстраивается земля. Пока поле пустое, лежит просто вылепленный рельеф": "The road object the ground adapts to. While the field is empty, the sculpted relief just sits there",
    "На каком расстоянии от дороги земля возвращается к своей форме, метры. Меньше — обрывистые борта, больше — пологий выход в поле": "Over what distance from the road the ground returns to its own shape, metres. Smaller — steep banks, larger — a gentle run-out into the field",
    "На сколько метров земля ниже полотна. Небольшой зазор убирает мерцание совпавших поверхностей в игре": "How many metres the ground sits below the road surface. A small gap removes z-fighting between coincident surfaces in game",
    "Шум поверх формы": "Noise on top of the shape",
    "Создать участок земли: редактируемая сетка + подстройка под дорогу": "Create a ground patch: an editable grid plus road adaptation",
    "Сторона квадратного куска земли, метры": "Side of the square ground patch, metres",
    "Сколько вершин по стороне. Это обычная сетка, её можно тянуть руками — чем она плотнее, тем мельче лепятся детали и тем чётче кромка у дороги": "Vertices per side. It is an ordinary grid you can pull by hand — the denser it is, the finer the details you can sculpt and the crisper the rim at the road",
    "Сколько вершин по стороне": "Vertices per side",
    "INU: Перестроить сетку ландшафта": "INU: Rebuild Terrain Grid",
    "Заново выложить сетку ландшафта с другим размером и плотностью": "Lay out the terrain grid again with a different size and density",
    "Сетка выкладывается заново — всё, что было вылеплено, сбросится": "The grid is laid out from scratch — everything you sculpted is reset",
    "Не удалось перестроить сетку:": "Could not rebuild the grid:",
    "Сетка перестроена:": "Grid rebuilt:",
    "Перестроить сетку": "Rebuild grid",
    "Форму лепи прямо в сетке:": "Shape it right in the grid:",
    "Tab → выдели точки → O → тяни вверх": "Tab → select points → O → pull up",
    "материал земли с Surface ID для COL": "ground material with a COL Surface ID",
    "материалы и UV — как на твоём тайле": "materials and UVs — exactly as on your tile",
    "Размер участка": "Patch size",
    "Сторона квадратного куска земли, метры. Большие территории лучше собирать из нескольких таких участков — так их потом проще резать на модели под лимиты игры": "Side of the square ground patch, metres. Large areas are better assembled from several patches — they are easier to split into models within the game's limits later",
    "Разрешение сетки": "Grid resolution",
    "Сколько вершин по стороне. Чем больше, тем чётче ложится край дороги — и тем тяжелее сцена. 128 на участок в 200 м даёт шаг примерно полтора метра": "Vertices per side. The more there are, the crisper the road edge sits — and the heavier the scene. 128 over a 200 m patch gives about a metre and a half per step",
    "Высота рельефа": "Relief height",
    "Разброс высот от низа до верха, метры. 0 — идеально плоско": "Height spread from bottom to top, metres. 0 — perfectly flat",
    "Размер холмов": "Hill size",
    "Сколько метров занимает один холм. Меньше — мелкая рябь, больше — пологие складки": "How many metres one hill spans. Smaller — fine ripple, larger — gentle folds",
    "Вариант рельефа": "Relief variant",
    "Сдвигает шум. Меняй, если форма холмов не нравится — размеры останутся те же, рисунок будет другой": "Shifts the noise. Change it if you dislike the hill shapes — the sizes stay, the pattern differs",
    "Ширина слияния": "Blend width",
    "На каком расстоянии от дороги земля возвращается к своему рельефу, метры. Меньше — обрывистые борта, больше — пологий выход в поле": "Over what distance from the road the ground returns to its own relief, metres. Smaller — steep banks, larger — a gentle run-out into the field",
    "Утопить под дорогой": "Sink under the road",
    "На сколько метров земля ниже полотна дороги. Небольшой зазор убирает мерцание совпавших поверхностей в игре": "How many metres the ground sits below the road surface. A small gap removes z-fighting between coincident surfaces in game",
    "UV, метров на тайл": "UV, metres per tile",
    "Сколько метров земли занимает один повтор текстуры": "How many metres of ground one texture repeat covers",
    "Дорога": "Road",
    "Объект дороги, под который подстраивается земля. Пока поле пустое, строится чистый рельеф без коридора": "The road object the ground adapts to. While the field is empty, plain relief is built with no corridor",
    "INU: Новый ландшафт": "INU: New Terrain",
    "Создать участок процедурной земли, подстраивающейся под дорогу": "Create a patch of procedural ground that adapts to the road",
    "INU: Привязать ландшафт к дороге": "INU: Link Terrain To Road",
    "Привязать активный ландшафт к выделенной дороге": "Link the active terrain to the selected road",
    "Не удалось создать ландшафт:": "Could not create the terrain:",
    "Ландшафт привязан к дороге:": "Terrain linked to the road:",
    "Ландшафт создан. Укажи дорогу в поле «Дорога»": "Terrain created. Pick the road in the «Road» field",
    "Выдели дорогу вместе с ландшафтом": "Select the road together with the terrain",
    "В группе ландшафта нет поля «Дорога»": "The terrain group has no «Road» field",
    "Новый ландшафт": "New terrain",
    "Привязать к дороге": "Link to road",
    "Земля": "Ground",
    "Участок": "Patch",
    "Рельеф": "Relief",
    "INU: Дорога из моего тайла": "INU: Road From My Tile",
    "Пустить свой кусок дороги вдоль выделенной кривой": "Run your own road piece along the selected curve",
    "Дорога из моего тайла": "Road from my tile",
    "Тайл уложен вдоль кривой:": "Tile laid along the curve:",
    "Выбери объект-тайл в поле «Тайл»": "Pick the tile object in the «Tile» field",
    "Свой тайл: выдели его вместе с кривой": "Your own tile: select it together with the curve",
    "моделируй сверху: X поперёк, Y вдоль, Z вверх": "model it top-down: X across, Y along, Z up",
    "Тайл": "Tile",
    "Объект-кусок дороги, который поедет вдоль кривой. Моделируй его сверху: X — поперёк дороги (0 = ось), Y — вдоль, Z — высота. Нарежь его поперечными петлями: чем их больше, тем плавнее он ляжет в поворот": "The road-piece object that will run along the curve. Model it top-down: X across the road (0 = centreline), Y along, Z up. Cut it with cross loops — the more there are, the smoother it bends into a turn",
    "Тайл лежит вдоль X": "Tile runs along X",
    "Включи, если твой кусок дороги вытянут по X, а не по Y — он будет повёрнут на 90° перед укладкой": "Turn on if your road piece is stretched along X instead of Y — it will be rotated 90° before being laid",
    "Радиус скругления углов кривой, метры. Если поворот круче полуширины тайла, его внутренняя кромка заворачивается сама на себя. 0 — выключить": "Corner fillet radius of the curve, metres. When a turn is tighter than half the tile width, its inner edge folds over itself. 0 — off",
    "Скругление поворотов": "Corner fillet",
    "Радиус скругления углов кривой, метры. Если поворот круче полуширины дороги, внутренняя кромка заворачивается сама на себя — получается излом. Скругление это снимает. 0 — выключить и вести дорогу строго по кривой": "Corner fillet radius of the curve, metres. When a turn is tighter than half the road width, the inner edge folds over itself and you get a kink. The fillet removes it. 0 — off, the road follows the curve exactly",
    "Текстурирование": "Texturing",
    # --- GTA Geo: procedural road (geometry nodes) ---
    "Ширина полотна": "Road width",
    "Ширина асфальта от края до края, метры. Две полосы SA — примерно 6 м": "Asphalt width edge to edge, metres. Two SA lanes are about 6 m",
    "Подъём центра": "Crown height",
    "На сколько метров середина полотна выше краёв. Небольшой подъём (3–8 см) не даёт дороге выглядеть плоской наклейкой": "How many metres the centre of the roadway sits above its edges. A small crown (3–8 cm) keeps the road from looking like a flat decal",
    "Ширина обочины": "Shoulder width",
    "Ширина обочины с каждой стороны, метры. 0 — обочины нет": "Shoulder width on each side, metres. 0 — no shoulder",
    "Просадка обочины": "Shoulder drop",
    "На сколько метров внешний край обочины ниже края асфальта": "How many metres the outer shoulder edge sits below the asphalt edge",
    "Ширина откоса": "Slope width",
    "Горизонтальная ширина откоса к земле, метры. Именно этой полосой дорога будет сшиваться с ландшафтом на 3 этапе": "Horizontal width of the slope down to the ground, metres. This is the band the road gets stitched to the terrain by in stage 3",
    "Спуск откоса": "Slope drop",
    "На сколько метров низ откоса ниже обочины": "How many metres the bottom of the slope sits below the shoulder",
    "Шаг сегмента": "Segment step",
    "Длина одного сегмента дороги вдоль кривой, метры. Меньше шаг — плавнее повороты и больше полигонов": "Length of one road segment along the curve, metres. Smaller step — smoother turns and more polygons",
    "UV поперёк, м": "UV across, m",
    "Сколько метров поперёк дороги занимает один повтор текстуры. Поставь равным ширине полотна — и текстура асфальта ляжет ровно по ширине, от 0 до 1": "How many metres across the road one texture repeat covers. Set it to the road width and the asphalt texture maps exactly across, from 0 to 1",
    "UV вдоль, м": "UV along, m",
    "Сколько метров вдоль дороги занимает один повтор текстуры": "How many metres along the road one texture repeat covers",
    "INU: Новая дорога": "INU: New Road",
    "INU: Дорога из кривой": "INU: Road From Curve",
    "INU: Запечь дорогу в меш": "INU: Bake Road To Mesh",
    "INU: Пересобрать нод-группу дороги": "INU: Rebuild Road Node Group",
    "Создать новую процедурную дорогу: кривая + модификатор INU_Road": "Create a new procedural road: a curve plus the INU_Road modifier",
    "Навесить дорогу на уже выделенные кривые": "Attach the road to the curves that are already selected",
    "Запечь дорогу в обычный меш — готовый к экспорту в DFF": "Bake the road into a regular mesh — ready for DFF export",
    "Пересобрать нод-группу INU_Road с нуля": "Rebuild the INU_Road node group from scratch",
    "Длина": "Length",
    "Длина стартовой прямой, метры. Дальше кривую тянешь и гнёшь как обычно — дорога перестроится": "Length of the starting straight, metres. After that you drag and bend the curve as usual — the road rebuilds",
    "Не удалось создать дорогу:": "Could not create the road:",
    "Дорога создана:": "Road created:",
    "Выдели хотя бы одну кривую": "Select at least one curve",
    "Ошибка на": "Error on",
    "Дорога навешена на кривых:": "Road attached to curves:",
    "Чужих материалов сдвинуто в конец списка:": "Foreign materials moved to the end of the slot list:",
    "Скрыть кривую": "Hide the curve",
    "Спрятать исходную кривую после запекания. Сама кривая никуда не девается — её видно в Outliner, и дорогу всегда можно перегенерировать": "Hide the source curve after baking. The curve itself stays — it is still in the Outliner, and the road can always be regenerated",
    "Не удалось запечь дорогу:": "Could not bake the road:",
    "Дорога пустая — проверь, что у кривой есть хотя бы две точки": "The road is empty — check that the curve has at least two points",
    "Запечено:": "Baked:",
    "вершин": "verts",
    "треугольников": "tris",
    "Не удалось пересобрать:": "Could not rebuild:",
    "Нод-группа дороги пересобрана. Параметры модификаторов сброшены к дефолтным": "Road node group rebuilt. Modifier parameters are reset to defaults",
    "Профиль дороги": "Road profile",
    "Полотно": "Roadway",
    "Обочина": "Shoulder",
    "Откос": "Slope",
    "Детализация и UV": "Detail & UV",
    "Новая дорога": "New road",
    "Дорога из кривой": "Road from curve",
    "Дорога строится по кривой:": "The road is built along a curve:",
    "двигай точки кривой — форма пересчитается": "move the curve points — the shape rebuilds",
    "наклон точки (Tilt) даёт вираж в повороте": "point Tilt gives banking in turns",
    "Вершин:": "Verts:",
    "треугольников:": "tris:",
    "Что получится на выходе:": "What you get:",
    "обычный меш с UV и прелайтом Day": "a regular mesh with UVs and the Day prelight",
    "3 материала: асфальт / обочина / откос": "3 materials: asphalt / shoulder / slope",
    "Surface ID для COL уже проставлен": "COL Surface ID is already set",
    "Запечь в меш": "Bake to mesh",
    "Пересобрать нод-группу": "Rebuild node group",
    # --- Ariane bridge ---
    "{0}: нет COL — авто из геометрии": "{0}: no COL — auto from geometry",
    "{0}: нет LOD — без дальнего меша": "{0}: no LOD — no distant mesh",
    "Продолжить создание модели?": "Create the model anyway?",
    "Создать модель": "Create model",
    "Отправлено моделей: {0}": "Models sent: {0}",
    "Создать инстанс": "Create instance",
    "Создано в ariane: {0}": "Created in ariane: {0}",
    "Синхр. камеру": "Sync camera",
    "Синхр. выделение": "Sync selection",
    "Live-синхронизация": "Live sync",
    "Переносить позицию": "Transfer position",
    "Ручной импорт": "Manual import",
    "Экспорт → Ariane": "Export → Ariane",
    "Обновить позицию": "Update position",
    "Очистить кэш": "Clear cache",
    "указать папку игры": "set game folder",
    "импортирую… {0}/{1}": "importing… {0}/{1}",
    "импорт {0} (ош {1}) · отпр {2}": "import {0} (err {1}) · sent {2}",
    "Ariane принял: {0} (ош {1})": "Ariane accepted: {0} (err {1})",
    "В ariane отправлено: {0} модель(ей)": "Sent to ariane: {0} model(s)",
    "Нет выделенных мешей": "No selected meshes",
    "Позиция обновлена: {0} модель(ей)": "Position updated: {0} model(s)",
    "Нет моделей с ariane_iid (сначала импортируй из ariane)": "No models with ariane_iid (import from ariane first)",
    "Ariane watcher выключен": "Ariane watcher off",
    "Ariane watcher включён · {0}": "Ariane watcher on · {0}",
    "Ariane: удалено файлов из кэша: {0}": "Ariane: cache files removed: {0}",
    "Ariane: импортировано {0} модель(ей)": "Ariane: imported {0} model(s)",
    # --- map.zon / info.zon zones ---
    "Зон в сцене:": "Zones in scene:",
    "Зон импортировано:": "Zones imported:",
    "Зон записано:": "Zones written:",
    "Зона создана:": "Zone created:",
    "Зон с перевёрнутым bbox (в игре не сработают):":
        "Zones with a reversed bbox (dead in game):",
    "Повторяющиеся имена зон:": "Duplicate zone names:",
    "Нет зон для экспорта": "No zones to export",
    "Ничего не выделено": "Nothing selected",
    "Новая зона": "New zone",
    "Строки в буфер": "Lines to clipboard",
    "Строк в буфере:": "Lines in clipboard:",
    "по габаритам:": "from bounds:",
    "Нулевой размер по одной из осей": "Zero size on one of the axes",
    "Выдели бокс зоны, чтобы править параметры":
        "Select a zone box to edit its parameters",
    "В сцене несколько наборов зон — выдели нужные боксы или назови файл как коллекцию ZON_*":
        "The scene holds several zone sets — select the boxes you want, "
        "or name the file after a ZON_* collection",
    "Путь к файлу зон (data/map.zon или data/info.zon)":
        "Path to the zone file (data/map.zon or data/info.zon)",
    "0 — навигация (info.zon)": "0 — navigation (info.zon)",
    "3 — зона карты (map.zon)": "3 — map zone (map.zon)",
    "4 — погода (мод)": "4 — weather (mod)",
    "свой тип": "custom type",
    "Уровень": "Level",
    "замечаний:": "warnings:",
    "см. консоль": "see console",
    # --- v2.3.0: added missing translations ---
    "Эффекты": "Effects",
    "Ещё": "More",
    "Импорт всех моделей": "Import all models",
    "Укажите IPL или IDE файл": "Set an IPL or IDE file",
    "Укажите IDE файл": "Set an IDE file",
    "Укажите IPL файл": "Set an IPL file",
    "Импорт / Экспорт по отдельности": "Import / Export separately",
    "Достать/впихнуть отдельную модель в .img": "Extract/inject a single model in the .img",
    "Импорт/экспорт по отдельности, синхронизация, секции IPL": "Import/export separately, sync, IPL sections",
    "Не в IDE/IPL": "Not in IDE/IPL",
    "В IDE/IPL — параметры разошлись": "In IDE/IPL — parameters drifted",
    "В IDE + IPL": "In IDE + IPL",
    "В IDE": "In IDE",
    "В IPL": "In IPL",
    "Добавить в IDE + IPL": "Add to IDE + IPL",
    "Обновить в IDE + IPL": "Update in IDE + IPL",
    "Убрать из IDE/IPL": "Remove from IDE/IPL",
    "Импорт / Экспорт IDE/IPL": "Import / Export IDE/IPL",
    "Импорт/экспорт IDE и IPL по отдельности": "Import/export IDE and IPL separately",
    "Импорт IDE": "Import IDE",
    "Экспорт IDE": "Export IDE",
    "Импорт IPL": "Import IPL",
    "Экспорт IPL": "Export IPL",
    "Архив IMG": "IMG archive",
    "Импорт моделей": "Model import",
    "Запоминается для всех импортов (меню, отдельный Import DFF, перетаскивание .dff)": "Remembered for all imports (menu, standalone Import DFF, .dff drag-and-drop)",
    "plants.dat не найден — укажи путь или Game Root": "plants.dat not found — set the path or Game Root",
    "Автоматически добавляет поворот 180° к Root на каждом кадре (заменяет ручную правку после зеркала). Компенсирует разницу между rest- и игровой ориентацией скелета GTA": "Automatically adds a 180° rotation to Root on every frame (replaces the manual fix after mirroring). Compensates for the difference between the rest and in-game orientation of the GTA skeleton",
    "Альфа (129-255; ниже — полупрозрачнее)": "Alpha (129-255; lower = more translucent)",
    "Анимация отзеркалена": "Animation mirrored",
    "Байт-в-байт round-trip, не редактируется": "Byte-exact round-trip, not editable",
    "Белый": "White",
    "В каком пространстве применять доворот 180°. Если результат неверный — переключи вариант": "Which space to apply the 180° turn in. If the result is wrong, switch the option",
    "ВКЛ — обрабатывать как СТАНДАРТНУЮ модель GTA SA (сварка + острые рёбра, как раньше). ВЫКЛ — КАСТОМНАЯ модель: связать рассыпанную геометрию и сохранить двусторонние заборы": "ON — process as a STANDARD GTA SA model (weld + sharp edges, as before). OFF — CUSTOM model: connect loose geometry and keep double-sided fences",
    "Вверх": "Up",
    "Верх": "Top",
    "Верхняя точка эскалатора": "Escalator top point",
    "Ветер": "Wind",
    "Вкл": "On",
    "Включить": "Enable",
    "Вниз": "Down",
    "Время вкл": "Time on",
    "Время выкл": "Time off",
    "Вход/Выход": "Enter/Exit",
    "Вход/Выход (интерьер):": "Enter/Exit (interior):",
    "Высота травинки": "Grass blade height",
    "Генерация геометрией": "Geometry generation",
    "Дорожный знак": "Road sign",
    "Дорожный знак (текст):": "Road sign (text):",
    "Едет вверх": "Goes up",
    "Едет вниз": "Goes down",
    "Загружено записей:": "Entries loaded:",
    "Записано в": "Written to",
    "Записей:": "Entries:",
    "Импортируй plants.dat или добавь запись": "Import plants.dat or add an entry",
    "Имя интерьера": "Interior name",
    "Индекс определения покрова для поверхности (0-2). На одну поверхность можно до 3 определений": "Cover definition index for the surface (0-2). Up to 3 definitions per surface",
    "Интенсивность цвета (0-255)": "Color intensity (0-255)",
    "Интерьер #": "Interior #",
    "Какой из 16 тайлов «большой» текстуры 64x1024 (0-15)": "Which of the 16 tiles of the 'big' 64x1024 texture (0-15)",
    "Красный": "Red",
    "Куда телепортирует игрока (координаты интерьера)": "Where it teleports the player (interior coordinates)",
    "Назначено полигонам:": "Assigned to polygons:",
    "Назначить выделенным полигонам": "Assign to selected polygons",
    "Направление игрока при выходе из интерьера (градусы)": "Player facing when exiting the interior (degrees)",
    "Направление, куда повёрнут игрок при входе (градусы)": "Direction the player faces on entry (degrees)",
    "Не выделено ни одного полигона": "No polygons selected",
    "Негировать одну координату смещения Root (замена ручного «By Values / Over Cursor Value» при курсоре на 0)": "Negate one Root offset coordinate (replaces the manual 'By Values / Over Cursor Value' with the cursor at 0)",
    "Неизвестная поверхность записи": "Unknown entry surface",
    "Нет grass-записей под материалы сцены — импортируй plants.dat": "No grass entries for the scene materials — import plants.dat",
    "Нет выбранной записи травы": "No grass entry selected",
    "Нет граней с подходящим grass-материалом на выделении": "No faces with a matching grass material in the selection",
    "Нижняя точка эскалатора (модельное пространство)": "Escalator bottom point (model space)",
    "Низ": "Bottom",
    "Номер интерьерного мира (0 = обычный мир)": "Interior world number (0 = normal world)",
    "Ориентация плоскости знака": "Sign plane orientation",
    "Основа": "Base",
    "Ось, вокруг которой Root доворачивается на 180°": "Axis around which Root is turned 180°",
    "Отзеркалить анимацию (L/R)": "Mirror animation (L/R)",
    "Отражать и поворот корневой кости. Если после зеркала персонаж встаёт «на голову» — выключи: тогда поворот Root останется как в оригинале, отразится только смещение (движение вперёд/назад)": "Also mirror the root bone rotation. If the character ends up upside-down after mirroring, turn this off: then the Root rotation stays as in the original and only the offset (forward/backward motion) is mirrored",
    "Отражать поворот Root": "Mirror Root rotation",
    "Ошибка записи:": "Write error:",
    "Ошибка чтения:": "Read error:",
    "Плотность: травинок на 1 м² (1.0 густо, 0.1 редко, 0 — нет)": "Density: blades per 1 m² (1.0 dense, 0.1 sparse, 0 = none)",
    "Поверхность": "Surface",
    "Поворот": "Rotation",
    "Позиция выхода": "Exit position",
    "Показать траву": "Show grass",
    "Пространство": "Space",
    "Процедурная трава движка (data/plants.dat)": "Engine procedural grass (data/plants.dat)",
    "Путь к .txd с текстурой травы (напр. plant1.txd). Пусто — карточки просто цветные": "Path to the .txd with the grass texture (e.g. plant1.txd). Empty = cards are just colored",
    "Путь к data/plants.dat. Пусто → берётся из Game Root": "Path to data/plants.dat. Empty → taken from Game Root",
    "Радиус X": "Radius X",
    "Радиус Y": "Radius Y",
    "Разброс высоты": "Height variation",
    "Разброс интенсивности (работает при I<255)": "Intensity variation (works when I<255)",
    "Разброс качания между травинками (0-10)": "Sway variation between blades (0-10)",
    "Разброс размера по ширине": "Width size variation",
    "Размер травинки по ширине": "Grass blade width",
    "Реальная геометрия травы, экспортируется вместе с мешем": "Real grass geometry, exported with the mesh",
    "Сгенерировать": "Generate",
    "Серый": "Gray",
    "Сила качания на ветру (отрицательная = против ветра)": "Wind sway strength (negative = against the wind)",
    "Символов/строку": "Chars/line",
    "Сколько строк текста используется": "How many text lines are used",
    "Слот: набор геометрии + «большая» текстура в plant1.txd. Должен быть одинаковым для всех PCDid одной поверхности": "Slot: geometry set + 'big' texture in plant1.txd. Must be the same for all PCDids of one surface",
    "Создана геометрия травы:": "Grass geometry created:",
    "Сохранённый эффект": "Saved effect",
    "Список пуст — нечего экспортировать": "List is empty — nothing to export",
    "Способ": "Method",
    "Спрайт: txgrass{Slot}_{UVoff} в .txd": "Sprite: txgrass{Slot}_{UVoff} in the .txd",
    "Строк": "Lines",
    "Строка %d": "Line %d",
    "Строка 1": "Line 1",
    "Строка 2": "Line 2",
    "Строка 3": "Line 3",
    "Строка 4": "Line 4",
    "Субмодель (0-3)": "Submodel (0-3)",
    "Текстура .txd": ".txd texture",
    "Тонировать цветом": "Tint with color",
    "Точка схода (Z как у верха при движении вверх, как у низа — при движении вниз)": "Vanishing point (Z as the top when going up, as the bottom when going down)",
    "Травинок в предпросмотре:": "Grass blades in preview:",
    "Угол входа": "Entry angle",
    "Угол выхода": "Exit angle",
    "Укажи путь к plants.dat или Game Root": "Set the path to plants.dat or Game Root",
    "Умножать спрайт на цвет из plants.dat (как в игре). Выключено — показывать текстуру как есть (для проверки)": "Multiply the sprite by the color from plants.dat (as in game). Off = show the texture as-is (for checking)",
    "Цвет неба": "Sky color",
    "Чёрный": "Black",
    "Ширина и высота области текста на меше": "Width and height of the text area on the mesh",
    "Эскалатор": "Escalator",
    "Эскалатор:": "Escalator:",
    "достигнут лимит": "limit reached",
    "поверхностей:": "surfaces:",
    "пропущено строк:": "lines skipped:",
    # --- export vertex-alpha toggle ---
    "Vertex Alpha": "Vertex Alpha",
    "Записывать вершинную альфу (прозрачность vertex colors) в DFF. По умолчанию ВЫКЛ — редко нужна и может дать случайную альфу (напр. на LOD). Включай осознанно для стёкол/листвы/заборов; при выключенной альфа всегда 255 (непрозрачно)": "Write per-vertex alpha (vertex-color transparency) into the DFF. OFF by default — rarely needed and can leak accidental alpha (e.g. on LODs). Turn on deliberately for glass/foliage/fences; when off, alpha is always 255 (opaque)",
    # --- alpha blend-mode labels ---
    "Непрозрачность": "Opaque",
    "Альфа-усечение": "Alpha Clip",
    "Альфа-смешивание": "Alpha Blend",
    # --- material EFFECTS collapsible sections ---
    "GTA-эффекты": "GTA effects",
    "Машина": "Vehicle",
    "Свернуть/развернуть GTA-эффекты (env map, bump, reflection, specular, dual, UV-аним)": "Collapse/expand GTA effects (env map, bump, reflection, specular, dual, UV anim)",
    "Свернуть/развернуть блок машины (слот цвета + Paintjob)": "Collapse/expand the vehicle block (color slot + Paintjob)",
    "Массовая замена режима прозрачности у альфа-материалов сцены": "Bulk-change the blend mode of the scene's alpha materials",
    # --- alpha-materials bulk tool ---
    "blend_method уже не Opaque": "blend_method is already non-opaque",
    "Альфа текстуры подключена ко входу Alpha шейдера": "Texture alpha is wired to the shader Alpha input",
    "Альфа-хеш": "Alpha Hashed",
    "Вся сцена": "Whole scene",
    "Выделено объектов": "Objects selected",
    "Выделить объекты": "Select objects",
    "Есть альфа-канал": "Has alpha channel",
    "Любой из критериев выше": "Any of the criteria above",
    "Найдено альфа-материалов": "Alpha materials found",
    "Нет альфа-материалов — нажми «Обновить»": "No alpha materials — press “Refresh”",
    "Область": "Scope",
    "По ноде альфы": "By alpha node",
    "Применить ко всем": "Apply to all",
    "Режим для всех": "Mode for all",
    "Режим прозрачности изменён у": "Blend mode changed on",
    "Собирать по всей сцене": "Collect across the whole scene",
    "Только материалы выделенных объектов": "Only materials of selected objects",
    "У текстуры есть значимый альфа-канал": "The texture has a significant alpha channel",
    "Уже прозрачные": "Already transparent",
    "материал(ов)": "material(s)",
    # --- v2.2.0: added missing translations ---
    "2DFX-размеры, Scene-свойства pre-Step-9.": "2DFX sizes, Scene props pre-Step-9.",
    "IDE/IPL: файлы не выбраны в панели — пропущено": "IDE/IPL: no files picked in the panel — skipped",
    "IMG перестроен: {0} записей, освобождено {1:.1f} МБ": "IMG rebuilt: {0} entries, {1:.1f} MB freed",
    "LOD занимает уже занятый ID: ": "LOD uses an already-occupied ID: ",
    "LOD-связь потеряна (lod_index = -1) у: {0}. Выдели DFF и его LOD вместе, или держи их в одном IPL.": "LOD link lost (lod_index = -1) for: {0}. Select the DFF and its LOD together, or keep them in one IPL.",
    "Model ID = 0 у: {0}. Назначь ID (ID Manager → Auto-Assign) перед добавлением.": "Model ID = 0 for: {0}. Assign an ID (ID Manager → Auto-Assign) before adding.",
    "Миграция данных из старых .blend (по требованию):": "Data migration from old .blend files (on demand):",
    "Миграция старых данных завершена": "Legacy data migration complete",
    "Нет запечённых карт": "No baked maps",
    "Отменено — сцена будет перезагружена": "Cancelled — the scene will be reloaded",
    "Пересобрать IMG (компакт)": "Rebuild IMG (compact)",
    "Показ поверх UV1 выключен": "Show over UV1 turned off",
    "После экспорта также дописать модели в IDE и IPL, выбранные в панели IDE / IPL / IMG (id, имя, TXD, дальность + расстановка и lod_index). Пути берутся из полей IDE / IPL панели": "After export, also append models to the IDE and IPL files picked in the IDE / IPL / IMG panel (id, name, TXD, draw distance + placement and lod_index). Paths are taken from the panel's IDE / IPL fields",
    "Регенерация превью открывает .blend файлы библиотеки в этом окне Blender. Включи галочку «Разрешить сборку Asset Library» в настройках.": "Regenerating previews opens the library .blend files in this Blender window. Enable the “Allow Asset Library build” checkbox in settings.",
    "Сборка Asset Library пересобирает текущую сцену (импортирует тысячи моделей и очищает данные сцены). Включи галочку «Разрешить сборку Asset Library» в настройках.": "Building the Asset Library rebuilds the current scene (imports thousands of models and clears scene data). Enable the “Allow Asset Library build” checkbox in settings.",
    "Сборка библиотеки…": "Building library…",
    "Сначала сохраните сцену (.blend) — кеш создаётся рядом с ней, и после сборки файл будет открыт заново": "Save the scene first (.blend) — the cache is created next to it, and the file is reopened after the build",
    "Совместимость со старыми версиями": "Legacy compatibility",
    "Сохрани изменения — сборка очищает текущую сцену и потеряет несохранённую работу (после сборки твой файл будет открыт заново)": "Save your changes — the build clears the current scene and will lose unsaved work (your file is reopened after the build)",
    "Также в IDE / IPL (пути из панели)": "Also to IDE / IPL (paths from panel)",
    "Укажите существующий .img файл": "Specify an existing .img file",
    "дефолты Modulate Color, граф превью прилайта,": "Modulate Color defaults, prelight preview graph,",
    # bl_info
    "Набор инструментов для работы с GTA SA моделями. Requires DragonFF addon":
        "Toolset for GTA SA models. Requires DragonFF addon",

    # Material panel
    "Материал коллизии": "Collision Material",
    "RW-затенение:": "RW shading:",
    "Фоновое (ambient)": "Ambient",
    "Зеркальное (specular)": "Specular",
    "Рассеянное (diffuse)": "Diffuse",
    "Цвет / прозрачность:": "Color / transparency:",
    "Цвет (RGBA)": "Color (RGBA)",
    "Режим прозрачности": "Blend mode",
    "Метод рендеринга": "Render method",
    "Перекрытие прозрачности": "Transparency overlap",
    "Текстура:": "Texture:",
    "Фильтрация": "Filtering",
    "Адресация U": "Address U",
    "Маска": "Mask",
    "Быстрые пресеты:": "Quick presets:",
    "Стекло": "Glass",
    "Краска": "Paint",
    "Сброс": "Reset",
    "Копировать на выделенные": "Copy to selected",
    "Имя": "Name",
    "Только активную анимацию": "Active animation only",
    "Экспортировать ТОЛЬКО активную Action арматуры — одну анимацию, а не весь пак. По умолчанию экспорт собирает все импортированные (ifp_source) Actions + активную; с этой галкой — ровно одну активную, будь она своя новая ИЛИ существующая из импортнутого ped.ifp.": "Export ONLY the armature's active Action — a single animation, not the whole pack. By default export gathers every imported (ifp_source) Action plus the active one; with this on, exactly the active one, whether it's your new Action OR an existing one from an imported ped.ifp.",
    "Нет активной анимации на арматуре": "No active animation on the armature",
    "Выдели целевые пустышки (Shift+клик), источник — активным": "Select target empties (Shift+click); keep the source active",
    "Выдели меш вместе с 2DFX": "Select a mesh together with the 2DFX",
    "Нет выделенных 2DFX": "No 2DFX selected",
    "Привязано 2DFX: {0} → '{1}'": "Attached 2DFX: {0} → '{1}'",
    "Выдели меш + 2DFX (можно несколько), затем нажмите": "Select a mesh + 2DFX (several allowed), then click",
    "Пропускать занятые ID": "Skip occupied IDs",
    "Вкл — пропускать уже занятые ID (как авто-назначение). Выкл — строго по порядку от стартового, даже если занято": "On — skip already-occupied IDs (like auto-assign). Off — strictly sequential from the start ID, even if occupied",
    "конфликтов с занятыми:": "conflicts with occupied:",
    "{0} объектов были привязаны к другому IPL — записаны в выбранный (проверь дубли в старом файле)": "{0} objects were linked to a different IPL — written to the selected one (check the old file for duplicates)",
    "{0} были в другом IDE (проверь дубли)": "{0} were in a different IDE (check for duplicates)",
    "Настройки 2DFX применены к {0}": "2DFX settings applied to {0}",

    # Property descriptions
    "Выделить найденные проблемные элементы": "Select found problem elements",
    "Количество колонок в сетке текстуры": "Number of columns in texture grid",
    "Количество рядов в сетке текстуры": "Number of rows in texture grid",
    "Позиция UV в ячейке": "UV position in cell",
    "Полигоны с пересекающимися UV перемещаются вместе": "Polygons with overlapping UVs move together",
    "Путь к папке с системными текстурами GTA": "Path to GTA system textures folder",
    "Путь к папке где находится .blend файл": "Path to folder where .blend file is located",
    "Не экспортировать TXD при Export All": "Do not export TXD with Export All",
    "Пропустить TXD": "Skip TXD",

    # Enum items
    "Центр": "Center",
    "По центру ячейки": "Center of cell",
    "Сверху слева": "Top Left",
    "В верхнем левом углу": "In top left corner",
    "Сверху": "Top",
    "Сверху по центру": "Top center",
    "Сверху справа": "Top Right",
    "В верхнем правом углу": "In top right corner",
    "Слева": "Left",
    "Слева по центру": "Left center",
    "Справа": "Right",
    "Справа по центру": "Right center",
    "Снизу слева": "Bottom Left",
    "В нижнем левом углу": "In bottom left corner",
    "Снизу": "Bottom",
    "Снизу по центру": "Bottom center",
    "Снизу справа": "Bottom Right",
    "В нижнем правом углу": "In bottom right corner",

    # UI text
    "Статус: Готов": "Status: Ready",
    "Статус: Не найден": "Status: Not found",
    "Папка .blend:": ".blend Folder:",
    "Загрузить текстуры": "Load Textures",
    "Очистка материалов": "Cleanup Materials",
    "Проверить материалы": "Check Materials",
    "Очистить всё": "Clear All",
    "Отменить": "Undo",
    "Колонки": "Columns",
    "Ряды": "Rows",
    "Скрыть сетку": "Hide Grid",
    "Показать сетку": "Show Grid",
    "Позиция": "Position",
    "Связать полигоны": "Link Polygons",
    "Рандом": "Random",
    "Привязать": "Snap",

    # Report messages
    "Выберите меш объект!": "Select a mesh object!",
    "Не меш объект": "Not a mesh object",
    "Геометрия в порядке!": "Geometry is OK!",
    "висящих вершин": "loose vertex",
    "висящих рёбер": "loose edges",
    "N-gons не найдены!": "No N-gons found!",
    "N-gons (5+ вершин)": "N-gons (5+ vertex)",
    "Нечего удалять - геометрия чистая!": "Nothing to delete - geometry is clean!",
    "Удалено:": "Deleted:",
    "вершин,": "vertex,",
    "рёбер": "edges",
    "Выделите модели для экспорта!": "Select models for export!",
    "Не удалось определить имя модели!": "Could not determine model name!",
    "Экспортировано:": "Exported:",
    "Ошибки:": "Errors:",
    "Найдено:": "Found:",
    "Среди выделенных не найдено DFF/LOD/COL моделей": "No DFF/LOD/COL models found among selected",
    "Укажите хотя бы один путь к папке с текстурами!": "Specify at least one path to textures folder!",
    "Выберите материал в списке!": "Select a material in the list!",
    "Выберите корректный материал!": "Select a valid material!",
    "Не удалось загрузить": "Failed to load",
    "Загружена текстура:": "Texture loaded:",
    "Текстура уже подключена:": "Texture already connected:",
    "Текстура не найдена:": "Texture not found:",
    "Путь установлен": "Path set",
    "Сначала сохраните .blend файл!": "Save .blend file first!",
    "Файл не указан!": "File not specified!",
    "Неподдерживаемый формат:": "Unsupported format:",
    "Ошибка загрузки:": "Loading error:",
    "Создан материал:": "Material created:",
    "Выделите меш объекты!": "Select mesh objects!",
    "Объектов:": "Objects:",
    "всего материалов:": "total materials:",
    "превышен лимит:": "limit exceeded:",
    "Объединено:": "Merged:",
    "слотов, удалено:": "slots, removed:",
    "дубликатов": "duplicates",
    "Дубликаты материалов не найдены": "No duplicate materials found",
    "Сортировка материалов": "Sort Materials",
    "Материалы уже отсортированы": "Materials already sorted",
    "Отсортировано материалов:": "Materials sorted:",
    "Сохраните .blend файл сначала!": "Save .blend file first!",
    "Текстуры с приставкой LP_ не найдены в папке:": "Textures with LP_ prefix not found in folder:",
    "Не удалось применить лайтмап - нет подходящих материалов": "Could not apply lightmap - no suitable materials",
    "Настройки сброшены по умолчанию": "Settings reset to default",
    "Код очищен": "Code cleared",
    "Сетка UV включена": "UV grid enabled",
    "Сетка UV выключена": "UV grid disabled",
    "Укажите количество колонок и рядов!": "Specify number of columns and rows!",
    "Выделите полигоны!": "Select polygons!",
    "Рандомизировано:": "Randomized:",
    "групп": "groups",
    "полигонов": "polygons",
    "Привязано:": "Snapped:",
    "Выберите меш!": "Select a mesh!",
    "Нет vertex colors!": "No vertex colors!",
    "Выделено": "Selected",
    "меш(ей)": "mesh(es)",

    # Operator docstrings
    "Проверить геометрию на висящие вершины и рёбра": "Check geometry for loose vertex and edges",
    "Проверить геометрию на N-gons (полигоны с 5+ вершинами)": "Check geometry for N-gons (polygons with 5+ vertex)",
    "Удалить висящие вершины и рёбра": "Delete loose vertex and edges",
    "Экспортировать текстуры в TXD архив": "Export textures to TXD archive",
    "Экспортировать DFF модель": "Export DFF model",
    "Экспортировать COL модель коллизии": "Export COL collision model",
    "Экспорт всех выделенных моделей (DFF + COL + LOD + TXD)": "Export all selected models (DFF + COL + LOD + TXD)",
    "Определить модели DFF, LOD, COL среди выделенных": "Detect DFF, LOD, COL models among selected",
    "Применить GTA SA Prelight к выделенному объекту": "Apply GTA SA Prelight to selected object",
    "Усреднить vertex colors для компланарных граней": "Average vertex colors for coplanar faces",
    "Сгенерировать код lightmap для выделенного объекта": "Generate lightmap code for selected object",
    "Копировать результат в буфер обмена": "Copy result to clipboard",
    "Очистить сгенерированный код": "Clear generated code",
    "Создать 8 источников света для запекания prelight вокруг объекта": "Create 8 lights for prelight baking around object",
    "Удалить все источники света prelight": "Remove all prelight lights",
    "Запечь освещение от Point источников в vertex colors": "Bake lighting from Point sources to vertex colors",
    "Быстрое запекание vertex colors от Point источников (без теней)": "Quick bake vertex colors from Point sources (no shadows)",
    "Сбросить настройки запекания по умолчанию": "Reset bake settings to default",
    "Сбросить настройки Scatter Light по умолчанию": "Reset Scatter Light settings to default",
    "Анализировать vertex colors выделенного объекта": "Analyze vertex colors of selected object",
    "Применить смещение яркости (V) к vertex colors": "Apply brightness offset (V) to vertex colors",
    "Загрузить Lightmap из папки с .blend файлом (текстуры с приставкой LP_)": "Load Lightmap from .blend folder (textures with LP_ prefix)",
    "Удалить Lightmap из материалов объекта": "Remove Lightmap from object materials",
    "Создать Day и Night color attributes": "Create Day and Night color attributes",
    "Переключить превью prelight - показать vertex colors с текстурами": "Toggle prelight preview - show vertex colors with textures",
    "Кликните на полигон чтобы взять его цвет": "Click on polygon to pick its color",
    "Залить выделенные грани цветом": "Fill selected faces with color",
    "Восстановить цвета, изменённые заливкой": "Restore colors changed by fill",
    "Удалить цвет из списка и восстановить оригинальные цвета": "Delete color from list and restore original colors",
    "Выделить полигоны с этим цветом": "Select polygons with this color",
    "Удалить scatter уровень (пересчитать цвета)": "Delete scatter level (recalculate colors)",
    "Очистить все scatter уровни цвета": "Clear all scatter levels of color",
    "Рассеять свет от выделенных граней к соседним": "Scatter light from selected faces to neighbors",
    "Переключить режим выделения граней в Vertex Paint": "Toggle face selection mode in Vertex Paint",
    "Переключить в Edit Mode для выделения граней": "Switch to Edit Mode for face selection",
    "Переключить в Vertex Paint Mode": "Switch to Vertex Paint Mode",
    "Выбрать color attribute и обновить превью prelight": "Select color attribute and update prelight preview",
    "Добавить новый color attribute": "Add new color attribute",
    "Удалить активный color attribute": "Delete active color attribute",
    "Создать color attribute": "Create color attribute",
    "Удалить color attribute по имени": "Delete color attribute by name",
    "Загрузить текстуры по именам материалов из указанных папок": "Load textures by material names from specified folders",
    "Установить путь к папке .blend файла": "Set path to .blend file folder",
    "Создать материал из перетаскиваемой текстуры": "Create material from dropped texture",
    "Проверить количество материалов на выделенных объектах": "Check material count on selected objects",
    "Объединить дубликаты материалов (.001, .002, и т.д.) с оригиналами": "Merge duplicate materials (.001, .002, etc.) with originals",
    "Показать/скрыть сетку на UV": "Show/hide grid on UV",
    "Рандомно распределить UV выделенных полигонов по сетке (для окон, вариаций)": "Randomly distribute UV of selected polygons on grid (for windows, variations)",
    "Привязать UV выделенных полигонов к ближайшей ячейке сетки": "Snap UV of selected polygons to nearest grid cell",

    # Panel docstrings
    "Главная панель GTA Tools": "GTA Tools main panel",
    "Панель экспорта GTA моделей": "GTA models export panel",
    "Панель INU Tools в Properties > Scene": "INU Tools panel in Properties > Scene",
    "Панель Prelight": "Prelight panel",
    "Расширенные настройки запекания": "Advanced bake settings",
    "Панель инструментов Vertex Paint": "Vertex Paint tools panel",
    "Панель генератора Lightmap": "Lightmap generator panel",
    "Панель UV инструментов GTA Tools": "GTA Tools UV panel",

    # Internal docstrings
    "Проверить, подключена ли нода к чему-либо (любой выход)": "Check if node is connected to anything (any output)",
    "Определить тип модели по суффиксу: LOD, COL, DFF в конце названия": "Determine model type by suffix: LOD, COL, DFF at end of name",
    "Найти связанные модели (DFF, LOD, COL) по базовому имени": "Find related models (DFF, LOD, COL) by base name",
    "Найти модели DFF, LOD, COL только среди выделенных объектов": "Find DFF, LOD, COL models only among selected objects",
    "Получить базовое имя из выделенных моделей": "Get base name from selected models",
    "Сохранить базовые цвета если ещё не сохранены": "Save base colors if not saved yet",
    "Пересчитать цвет одного loop: ИТОГ = (База ИЛИ Fill) + Σ Scatter": "Recalculate color of one loop: RESULT = (Base OR Fill) + Σ Scatter",
    "Пересчитать цвета для указанных loops (или всех если не указано)": "Recalculate colors for specified loops (or all if not specified)",
    "Добавить Fill слой для указанных loops": "Add Fill layer for specified loops",
    "Получить список уровней scatter для цвета": "Get list of scatter levels for color",
    "Удалить Scatter слой и пересчитать цвета": "Delete Scatter layer and recalculate colors",
    "Удалить все Scatter слои для цвета и пересчитать": "Delete all Scatter layers for color and recalculate",
    "Удалить Fill цвет и все его Scatter слои, пересчитать": "Delete Fill color and all its Scatter layers, recalculate",
    "Удалить цвет из списка по индексу": "Delete color from list by index",
    "Получить Fill цвет выделенных полигонов": "Get Fill color of selected polygons",
    "Проверить объект на висящие вершины и рёбра (не присоединённые к полигонам)": "Check object for loose vertex and edges (not attached to polygons)",
    "Элемент списка цветов заливки": "Fill color list item",

    # Material Backup
    "Исправить коллекцию освещения Itera Tools — сделать локальной и привязать к сцене": "Fix Itera Tools light collection — make local and link to scene",
    "Коллекция 'Template Scene - Vertex Lights' не найдена": "Collection 'Template Scene - Vertex Lights' not found",
    "Не удалось сделать коллекцию локальной": "Failed to make collection local",
    "Коллекция освещения Itera привязана к сцене": "Itera light collection linked to scene",
    "Исправить коллекцию Itera": "Fix Itera Collection",
    "Коллекция Itera исправлена": "Itera Collection Fixed",
    "Сохранить материалы объекта в буфер": "Save object materials to buffer",
    "Восстановить сохранённые материалы на объект": "Restore saved materials to object",
    "Материалы сохранены": "Materials saved",
    "Материалы восстановлены": "Materials restored",
    "Нет сохранённых материалов!": "No saved materials!",
    "Материал не найден:": "Material not found:",

    # Post-processing
    "Пост-обработка vertex colors": "Post-process vertex colors",
    "Сгладить vertex colors между соседними вершинами": "Smooth vertex colors between neighboring vertex",
    "Применить контраст к vertex colors": "Apply contrast to vertex colors",
    "Применить яркость к vertex colors": "Apply brightness to vertex colors",
    "Применить гамма-коррекцию к vertex colors": "Apply gamma correction to vertex colors",
    "Количество итераций сглаживания": "Number of smoothing iterations",
    "Сила сглаживания (0 = без изменений, 1 = полное усреднение)": "Smoothing factor (0 = no change, 1 = full average)",
    "Контраст (1 = без изменений, <1 = меньше, >1 = больше)": "Contrast (1 = no change, <1 = less, >1 = more)",
    "Яркость смещение (-1..+1)": "Brightness offset (-1..+1)",
    "Гамма-коррекция (1 = без изменений, <1 = светлее, >1 = темнее)": "Gamma correction (1 = no change, <1 = lighter, >1 = darker)",
    "Панель пост-обработки vertex colors": "Vertex colors post-processing panel",

    # COL Surface
    "Выберите COL меш-объект": "Select a COL mesh object",
    "Нет материалов на объекте": "No materials on object",
    "Тип поверхности GTA SA для коллизии": "GTA SA surface type for collision",
    "Назначить surface ID на выбранный материал": "Assign surface ID to selected material",
    "Surface ID назначен:": "Surface ID assigned:",
    "COL Surface Materials:": "COL Surface Materials:",
    "введите запрос для фильтрации": "type to filter",

    # Info tooltips
    "Текстура короны (светящийся спрайт)": "Corona texture (glowing sprite)",
    "Текстура тени на земле под источником света": "Shadow texture on ground under light source",

    "None — без pipeline\nVehicle — машины (отражения кузова, env map)\nBuilding DN — здания с day/night vertex colors\nBuilding — обычные здания":
        "None — no pipeline\nVehicle — cars (body reflections, env map)\nBuilding DN — buildings with day/night vertex colors\nBuilding — plain buildings",

    "DFF — модель (меш, материалы, UV)\nCOL — коллизия\nTXD — текстуры\nCheck vertex — висящие вершины и рёбра\nCheck N-gon — полигоны с 5+ вершинами\nCheck Material — лимит 50 материалов\nGPU — сжатие текстур на видеокарте":
        "DFF — model (mesh, materials, UV)\nCOL — collision\nTXD — textures\nCheck vertex — loose vertex and edges\nCheck N-gon — polygons with 5+ vertex\nCheck Material — 50 material limit\nGPU — texture compression on GPU",

    "DFF — импорт модели с мешем и материалами\nCOL — импорт коллизии\nTXD — импорт текстур\nImport TXD — автоимпорт текстур при импорте DFF":
        "DFF — import model with mesh and materials\nCOL — import collision\nTXD — import textures\nImport TXD — auto-import textures when importing DFF",

    "Light — уличные фонари, неон, corona\nParticle — дым, огонь, частицы\nPed Attractor — точки притяжения NPC (банкомат, скамейка)\nSun Glare — блик солнца на поверхности":
        "Light — street lights, neon, corona\nParticle — smoke, fire, particles\nPed Attractor — NPC attraction points (ATM, bench)\nSun Glare — sun glare on surface",

    "Color — цвет короны и света\nCorona Size — размер короны\nDraw Distance — дальность отрисовки\nLight Range — радиус точечного света":
        "Color — corona and light color\nCorona Size — corona size\nDraw Distance — draw distance\nLight Range — point light radius",

    "DEFAULT — всегда видим\nRANDOM_FLASHING — случайное мерцание\nFLASH_RAIN — мерцает в дождь\nONLY_RAIN — видим только в дождь\nNO_RAIN — не видим в дождь\nFLASH_5 — вариант мерцания 2":
        "DEFAULT — always visible\nRANDOM_FLASHING — random flashing\nFLASH_RAIN — flashes in rain\nONLY_RAIN — visible only in rain\nNO_RAIN — not visible in rain\nFLASH_5 — flashing variant 2",

    "None — без бликов линзы\nType 1/2/3 — разные стили бликов линзы":
        "None — no lens flare\nType 1/2/3 — different lens flare styles",

    "Light — динамическое освещение модели\nModulate Material Color — цвет материала влияет на модель\nExport Normals — экспорт нормалей (отключить для map объектов)":
        "Light — dynamic lighting on model\nModulate Material Color — material color affects model\nExport Normals — export normals (disable for map objects)",

    "Day — дневные вертексные цвета (prelight)\nNight — ночные вертексные цвета (требует Pipeline: Building)":
        "Day — daytime vertex colors (prelight)\nNight — nighttime vertex colors (requires Pipeline: Building)",

    "UV Map 1 — основная UV развёртка\nUV Map 2 — вторая UV (для lightmap и т.д.)\nBin Mesh PLG — совместимость с просмотрщиками DFF":
        "UV Map 1 — primary UV map\nUV Map 2 — secondary UV (for lightmap etc.)\nBin Mesh PLG — compatibility with DFF viewers",

    "Day — дневные вертексные цвета\nNight — ночные вертексные цвета\nDay/Night — создать оба атрибута\n+/- — добавить или удалить атрибут\nSave Materials — сохранить материалы (для Itera Tools)\nRestore — восстановить сохранённые материалы":
        "Day — daytime vertex colors\nNight — nighttime vertex colors\nDay/Night — create both attributes\n+/- — add or remove attribute\nSave Materials — save materials (for Itera Tools)\nRestore — restore saved materials",

    "V — смещение яркости vertex colors\nПоложительное значение — светлее\nОтрицательное — темнее":
        "V — brightness offset for vertex colors\nPositive value — brighter\nNegative — darker",

    "Сглаживание vertex colors между соседними вершинами\nIterations — количество проходов\nFactor — сила сглаживания (0-1)":
        "Smooth vertex colors between neighboring vertex\nIterations — number of passes\nFactor — smoothing strength (0-1)",

    "Контраст vertex colors\n1.0 — без изменений\n< 1.0 — меньше контраст\n> 1.0 — больше контраст":
        "Vertex colors contrast\n1.0 — no change\n< 1.0 — less contrast\n> 1.0 — more contrast",

    "Яркость vertex colors\n0.0 — без изменений\n> 0 — светлее\n< 0 — темнее":
        "Vertex colors brightness\n0.0 — no change\n> 0 — brighter\n< 0 — darker",

    "Гамма-коррекция vertex colors\n1.0 — без изменений\n< 1.0 — светлее (тени)\n> 1.0 — темнее (тени)":
        "Vertex colors gamma correction\n1.0 — no change\n< 1.0 — lighter (shadows)\n> 1.0 — darker (shadows)",

    "Диапазон дневного освещения для COL материалов\nMin/Max — значения от 0 до 15\nЯркость vertex colors конвертируется в этот диапазон":
        "Day lighting range for COL materials\nMin/Max — values from 0 to 15\nVertex colors brightness is converted to this range",

    "Диапазон ночного освещения для COL материалов\nMin/Max — значения от 0 до 15\nИспользует Night color attribute если есть":
        "Night lighting range for COL materials\nMin/Max — values from 0 to 15\nUses Night color attribute if available",

    "Тени — включить расчёт теней при запекании\nЗапечь — быстрое запекание без теней\nС тенями — запекание с raycast тенями (медленнее, но точнее)":
        "Shadows — enable shadow calculation when baking\nBake — fast baking without shadows\nWith Shadows — baking with raycast shadows (slower but more accurate)",

    # Buttons
    "Запекание:": "Bake:",
    "Тени": "Shadows",
    "Запечь": "Bake",
    "С тенями": "With Shadows",
    "Экспорт всего (DFF+COL+LOD+TXD)": "Export All (DFF+COL+LOD+TXD)",
    "Проверка": "Check",
    "Проверка вершин": "Check Vertex",
    "Проверка N-gon": "Check N-gon",
    "Проверка материалов": "Check Materials",
    "Привязать к модели": "Attach to Model",
    "Выделите меш + 2DFX, затем нажмите": "Select mesh + 2DFX, then click",
    "Обновить превью": "Refresh Preview",
    "Удалить превью": "Remove Preview",
    "Применить": "Apply",
    "Создать 8 ламп": "Create 8 Lights",
    "Удалить": "Remove",
    "Сохранить материалы": "Save Materials",
    "Восстановить": "Restore",
    "Запечь COL Light": "Bake COL Light",
    "Сгладить": "Smooth",
    "Сглаживание:": "Smooth:",
    "Контраст:": "Contrast:",
    "Контраст": "Contrast",
    "Яркость:": "Brightness:",
    "Яркость": "Brightness",
    "Гамма:": "Gamma:",
    "Гамма": "Gamma",
    "Проходы": "Iterations",
    "Сила": "Factor",
    "Мин.": "Min",
    "Макс.": "Max",

    # 2DFX panel
    "Пресеты:": "Presets:",
    "Свойства света:": "Light Properties:",
    "Имя короны:": "Corona Name:",
    "Режим показа:": "Show Mode:",
    "Тип бликов:": "Flare Type:",
    "Имя тени:": "Shadow Name:",
    "Флаги 1": "Flags 1",
    "Флаги 2": "Flags 2",
    "Солнечный блик": "Sun Glare",
    "Только позиция (без доп. данных)": "Position only (no extra data)",
    "Модель:": "Model:",
    "Цвет:": "Color:",
    "Размер короны": "Corona Size",
    "Дальность отрисовки": "Draw Distance",
    "Радиус света": "Light Range",
    "Отражение короны": "Corona Reflection",
    "Размер тени": "Shadow Size",
    "Дистанция тени": "Shadow Distance",
    "Множитель тени": "Shadow Multiplier",
    "Вектор направления:": "Look Direction:",
    "Свойства частицы:": "Particle Properties:",
    "Имя эффекта": "Effect Name",
    "Точка притяжения:": "Ped Attractor:",
    "Тип аттрактора": "Attractor Type",
    "Матрица поворота": "Rotation Matrix",
    "Внешний скрипт": "External Script",
    "Вероятность NPC": "Ped Probability",

    # Prelight panel
    "Цветовые атрибуты:": "Color Attributes:",
    "Настройка цвета:": "Adjust Color:",
    "Сохранено:": "Saved:",
    "мат.": "mat(s)",
    "Окружающий": "Ambient",
    "Интенсивность": "Intensity",

    # Prelight COL panel
    "Дневной свет:": "Day Light:",
    "Ночной свет:": "Night Light:",
    "Нет vertex colors": "No vertex colors",
    "COL light материалов:": "COL light materials:",
    "Дневной свет": "Day Light",
    "Ночной свет": "Night Light",

    # Scatter Light
    "Рассеянный свет:": "Scatter Light:",
    "Затухание": "Falloff",
    "Итерации": "Iterations",
    "Радиус (0=авто)": "Radius (0=auto)",
    "Рассеять от выделенных": "Scatter from Selected",

    # Lightmap panel
    "Текстура Lightmap:": "Lightmap Texture:",
    "Загрузить (LP_)": "Load (LP_)",
    "Генерация кода:": "Generate Code:",
    "Генерировать": "Generate",
    "Путь": "Path",
    "ID модели": "Model ID",
    "Результат:": "Result:",
    "Копировать": "Copy",
    "Очистить": "Clear",
    "Нажмите кнопку для генерации": "Press button to generate",

    # UV panel
    "Рандомизатор UV сетки": "UV Grid Randomizer",

    # Scene panel
    "Системные текстуры:": "System Textures:",

    # Material Effects panel
    "Фоновое затенение": "Ambient Shading",
    "Карта окружения": "Environment Map",
    "Текстура": "Texture",
    "Коэффициент": "Coefficient",
    "Использовать FB Alpha": "Use FB Alpha",
    "Карта высот": "Bump Map",
    "Текстура карты высот": "Height Map Texture",
    "Отражение материала": "Reflection Material",
    "Масштаб X": "Scale X",
    "Смещение X": "Offset X",
    "Зеркальный материал": "Specular Material",
    "Уровень зеркальности": "Specular Level",
    "UV Анимация": "UV Animation",
    "Имя анимации": "Animation Name",

    # Object Props panel
    "Флаги геометрии:": "Geometry Flags:",
    "Вертексные цвета:": "Vertex Colors:",
    "UV карты:": "UV Maps:",
    "Тип": "Type",
    "Свет (rpGEOMETRYLIGHT)": "Light (rpGEOMETRYLIGHT)",
    "Цвет материала модулирует": "Modulate Material Color",
    "Экспорт нормалей": "Export Normals",
    "Дневные верт. цвета": "Day Vertex Colours",
    "Ночные верт. цвета": "Night Vertex Colours",
    "UV карта 1": "UV Map 1",
    "UV карта 2": "UV Map 2",
    "Bin Mesh PLG": "Bin Mesh PLG",

    # Export/Import section headers
    "Экспорт по одному:": "Export Individual:",
    "Импорт по одному:": "Import Individual:",
    "Импорт TXD": "Import TXD",

    # Vertex Paint panel (hidden)
    "Режим:": "Mode:",
    "Редактор": "Edit",
    "Рисование": "Paint",
    "Выделение граней": "Face Select",
    "Заливка граней:": "Fill Faces:",
    "Залить": "Fill",

    # Import/Export File operators
    "Импорт DFF модели GTA SA": "Import GTA SA DFF model",
    "Импорт COL коллизии GTA SA": "Import GTA SA COL collision model",
    "Импорт TXD текстур GTA SA": "Import GTA SA TXD texture dictionary",
    "Экспорт DFF модели GTA SA": "Export GTA SA DFF model",
    "Экспорт COL коллизии GTA SA": "Export GTA SA COL collision model",
    "Экспорт TXD текстур GTA SA": "Export GTA SA TXD texture archive",

    # 2DFX operators
    "Применить пресет 2DFX к активному объекту": "Apply 2DFX preset to active object",
    "Создать 2DFX эффект с настройками по умолчанию": "Create 2DFX effect with default properties",
    "Обновить визуальный превью (свет + корона + тень) для выбранного 2DFX": "Recreate visual preview (light + corona + shadow) for selected 2DFX",
    "Удалить визуальный превью из выбранного 2DFX": "Remove visual preview from selected 2DFX",
    "Привязать 2DFX к модели (сделать дочерним)": "Attach 2DFX to mesh model (make it a child)",
    "Отвязать 2DFX от родительской модели": "Detach 2DFX from parent model",

    # COL operators
    "Назначить тип поверхности GTA SA для COL коллизии": "Assign GTA SA surface type for COL collision",
    "Выбрать тип поверхности для COL материала": "Pick surface type for COL material",
    "Конвертировать vertex colors в COL Day/Night Light (разбиение материалов по яркости)": "Convert vertex colors to COL Day/Night Light (split materials by brightness)",
    "Удалить COL light материалы, созданные Bake COL Light": "Remove COL light materials created by Bake COL Light",
    "Конвертировать vertex colors в COL Day/Night Light": "Convert vertex colors to COL Day/Night Light",

    # Panel docstrings
    "Выбор типа поверхности COL в свойствах материала": "COL Surface Type selector in Material Properties",
    "Панель эффектов материала в свойствах материала": "Material Effects panel in Material Properties",
    "Панель свойств объекта GTA SA": "GTA SA Object Properties panel",
    "Залить выделенные грани цветом в режиме vertex paint": "Fill selected faces with color in vertex paint mode",
    "Залить выделенные грани цветом через систему слоёв": "Fill selected faces with color using layer system",
    "Восстановить все цвета к базовым (удалить fill и scatter слои)": "Restore all colors to base (remove fill and scatter layers)",

    # Property descriptions (tooltips on sliders/checkboxes)
    "Цвет короны и света": "Corona and light color",
    "Рендер-пайплайн движка": "Rendering pipeline for the engine",
    "Экспорт нормалей вершин (отключить для map объектов)": "Export vertex normals (disable for map objects)",
    "Экспорт Bin Mesh PLG (совместимость с просмотрщиками DFF)": "Export Bin Mesh PLG (increases compatibility with DFF viewers)",
    "Экспорт первой UV карты": "Export first UV map",
    "Экспорт второй UV карты": "Export second UV map",
    "Экспорт дневных vertex colors": "Export day vertex prelight colors",
    "Экспорт ночных vertex colors": "Export night vertex colors",
    "Материал для Sphere/Cone": "Material for Sphere/Cone",
    "Флаги для Sphere/Cone": "Flags for Sphere/Cone",
    "Яркость для Sphere/Cone": "Brightness for Sphere/Cone",
    "Свет для Sphere/Cone": "Light for Sphere/Cone",
    "ID типа поверхности COL (0-178)": "COL surface type ID (0-178)",
    "Выделить найденные проблемные элементы": "Select found problem elements",
    "Экспортировать текстуры только из выделенных объектов": "Export textures only from selected objects",
    "Расстояние ламп от центра": "Distance of lights from center",
    "Рассчитать тени (медленнее, но точнее)": "Calculate shadows (slower but more accurate)",
    "Включить или выключить превью prelight": "Enable or disable prelight preview",
    "Фильтр типов поверхности": "Filter surface types",
    "Базовый рассеянный свет (ниже = темнее тени)": "Base ambient light (lower = darker shadows)",
    "Множитель интенсивности света (ниже = темнее)": "Light intensity multiplier (lower = darker)",
    "Гамма-коррекция (ниже = темнее)": "Gamma correction (lower = darker)",
    "Включить тени при запекании (raycast проверка перекрытий)": "Enable shadow casting during bake (rays check for occlusion)",
    "Смещение яркости как в 3Ds Max Adjust Color V (-80 для ночи)": "Brightness offset like 3Ds Max Adjust Color V (-80 for night)",
    "Интенсивность рассеивания света": "Light scatter intensity",
    "Скорость затухания света (выше = быстрее)": "How quickly light fades (higher = faster falloff)",
    "Количество слоёв соседних граней": "How many neighbor layers to affect",
    "Радиус поиска соседних граней (0 = авто по размеру грани)": "Search radius for nearby faces (0 = auto based on face size)",
    "Рендер-пайплайн для экспорта DFF": "Rendering pipeline for DFF export",
    "Экспортировать DFF при Export All": "Export DFF with Export All",
    "Экспортировать COL при Export All": "Export COL with Export All",
    "Экспортировать LOD при Export All": "Export LOD with Export All",
    "Экспортировать TXD при Export All": "Export TXD with Export All",
    "Минимальное значение дневного света (тень)": "Minimum Day Light value (shadow)",
    "Максимальное значение дневного света (свет)": "Maximum Day Light value (lit)",
    "Минимальное значение ночного света (тень)": "Minimum Night Light value (shadow)",
    "Максимальное значение ночного света (свет)": "Maximum Night Light value (lit)",
    "Автоимпорт TXD текстур при импорте DFF": "Auto-import TXD texture dictionary when importing DFF",
    "Папка для поиска TXD при импорте DFF (пусто = автопоиск в папке DFF)": "Custom folder to search for TXD files during DFF import (leave empty for auto-search in DFF folder)",
    "Количество колонок в сетке текстуры": "Number of columns in texture grid",
    "Количество рядов в сетке текстуры": "Number of rows in texture grid",
    "Позиция UV в ячейке": "UV position in cell",
    "Полигоны с пересекающимися UV перемещаются вместе": "Polygons with overlapping UVs move together",
    "Путь к папке с системными текстурами GTA": "Path to GTA system textures folder",
    "Путь к папке где находится .blend файл": "Path to folder where .blend file is located",
    "Флаг rpGEOMETRYLIGHT — динамическое освещение": "rpGEOMETRYLIGHT flag — dynamic lighting",
    "Флаг rpGEOMETRYMODULATEMATERIALCOLOR — цвет материала влияет на модель": "rpGEOMETRYMODULATEMATERIALCOLOR flag — material color affects model",

    # IDE / IPL
    "ID модели в GTA SA (IDE/IPL)": "Model ID in GTA SA (IDE/IPL)",
    "Имя словаря текстур (IDE). По умолчанию = имя модели": "Texture dictionary name (IDE). Default = model name",
    "Дальность прорисовки объекта (IDE)": "Object draw distance (IDE)",
    "Флаги объекта в IDE": "Object flags in IDE",
    "ID интерьера для IPL (0 = экстерьер)": "Interior ID for IPL (0 = exterior)",
    "Индекс LOD модели в IPL (-1 = нет LOD)": "LOD model index in IPL (-1 = no LOD)",
    "Экспорт IDE (определение объектов GTA SA)": "Export IDE (GTA SA object definitions)",
    "Экспорт IPL (размещение объектов GTA SA)": "Export IPL (GTA SA object placements)",
    "Импорт IDE (определения объектов GTA SA)": "Import IDE (GTA SA object definitions)",
    "Импорт IPL (размещение объектов GTA SA)": "Import IPL (GTA SA object placements)",
    "Экспорт IDE определений GTA SA": "Export GTA SA IDE definitions",
    "Экспорт IPL размещения GTA SA": "Export GTA SA IPL placements",
    "Импорт IDE определений GTA SA": "Import GTA SA IDE definitions",
    "Импорт IPL размещения GTA SA": "Import GTA SA IPL placements",
    "Model ID — ID модели в GTA SA\nTXD Name — словарь текстур\nDraw Distance — дальность прорисовки\nIDE Flags — флаги объекта\nInterior — ID интерьера (0 = улица)\nLOD Index — индекс LOD модели (-1 = нет)":
        "Model ID — model ID in GTA SA\nTXD Name — texture dictionary\nDraw Distance — rendering distance\nIDE Flags — object flags\nInterior — interior ID (0 = outdoor)\nLOD Index — LOD model index (-1 = none)",
    "DFF — импорт модели с мешем и материалами\nCOL — импорт коллизии\nTXD — импорт текстур\nIDE — определения объектов\nIPL — размещение объектов\nImport TXD — автоимпорт текстур при импорте DFF":
        "DFF — import model with mesh and materials\nCOL — import collision\nTXD — import textures\nIDE — object definitions\nIPL — object placements\nImport TXD — auto-import textures with DFF import",

    # IMG archive
    "Путь к .img архиву GTA SA для экспорта моделей": "Path to GTA SA .img archive for model export",
    "Экспорт DFF в IMG": "Export DFF to IMG",
    "Экспорт COL в IMG": "Export COL to IMG",
    "Экспорт TXD в IMG": "Export TXD to IMG",
    "Экспортировать DFF + TXD + COL прямо в .img архив": "Export DFF + TXD + COL directly into .img archive",
    "Укажите путь к .img архиву": "Specify path to .img archive",
    "Экспорт в IMG": "Export to IMG",

    # Game root / gta.dat
    "Корневая папка GTA SA для автопоиска IDE/IPL/IMG": "GTA SA root folder for auto-discovering IDE/IPL/IMG",
    "Укажите корневую папку GTA SA": "Specify GTA SA root folder",
    "Не найден data/gta.dat в указанной папке": "data/gta.dat not found in the specified folder",
    "Искать все IDE/IPL через gta.dat (нужна корневая папка игры)": "Find all IDE/IPL via gta.dat (requires game root folder)",

    # IDE / IPL panel
    "Панель IDE / IPL для работы с существующими файлами GTA SA": "IDE / IPL panel for working with existing GTA SA files",
    "Путь к IDE файлу GTA SA для добавления/обновления записей": "Path to GTA SA IDE file for adding/updating entries",
    "Путь к IPL файлу GTA SA для добавления/обновления записей": "Path to GTA SA IPL file for adding/updating entries",
    "Добавить / обновить запись в существующем IDE файле": "Add / update entry in existing IDE file",
    "Добавить / обновить запись в существующем IPL файле": "Add / update entry in existing IPL file",
    "Удалить запись из IDE файла по Model ID": "Remove entry from IDE file by Model ID",
    "Удалить запись из IPL файла по Model ID": "Remove entry from IPL file by Model ID",
    "Укажите путь к IDE файлу": "Specify path to IDE file",
    "Укажите путь к IPL файлу": "Specify path to IPL file",
    "Выделите меш объекты": "Select mesh objects",
    "Выделите меш объект": "Select a mesh object",
    "объектов с Model ID = 0, задайте ID в свойствах": "objects with Model ID = 0, set ID in properties",
    "обновлено": "updated",
    "добавлено": "added",
    "удалено": "removed",
    "Нет объектов с Model ID > 0": "No objects with Model ID > 0",
    "Добавить": "Add",
    "Удалить": "Remove",
    "Импорт": "Import",
    "Экспорт": "Export",

    # v1.5.2 — IDE/IPL/IMG, ID Manager, Suffixes, COL Light, Presets
    "IDE / IPL / IMG": "IDE / IPL / IMG",
    "Текстуры": "Textures",
    "Суффиксы моделей": "Model Suffixes",
    "Менеджер ID": "ID Manager",
    "Свободных:": "Free:",
    "Занятых:": "Used:",
    "Следующий свободный:": "Next free:",
    "Свободные:": "Free:",
    "Назначить ID выделенным": "Assign IDs to selected",
    "Открыть файл ID": "Open ID file",
    "Назначено ID:": "Assigned IDs:",
    "Все ID очищены": "All IDs cleared",
    "освобождён": "released",
    "Нет свободных ID в model_ids.txt": "No free IDs in model_ids.txt",
    "Нет свободных ID в активном пресете": "No free IDs in the active preset",
    "Показать пути IDE/IPL/IMG": "Show IDE/IPL/IMG paths",
    "Показать настройки текстур": "Show texture settings",
    "Показать настройки суффиксов": "Show suffix settings",
    "Показать менеджер ID": "Show ID Manager",
    "Показать флаги IDE": "Show IDE flags",
    "Суффикс для DFF моделей (например _DFF или DFF)": "Suffix for DFF models (e.g. _DFF or DFF)",
    "Суффикс для LOD моделей (например _LOD или LOD)": "Suffix for LOD models (e.g. _LOD or LOD)",
    "Суффикс для COL моделей (например _COL или COL)": "Suffix for COL models (e.g. _COL or COL)",
    "Порог яркости: 0 = без порога, 100 = максимальная отсечка": "Brightness threshold: 0 = max cutoff, 100 = no cutoff",
    "Порог": "Threshold",
    "Край": "Edge",
    "Контраст": "Contrast",
    "Цифры": "Numbers",
    "Размер": "Size",
    "Скрыть превью": "Hide preview",
    "Превью COL Light": "Preview COL Light",
    "Дневной свет:": "Day light:",
    "Ночной свет:": "Night light:",
    "Мин.": "Min.",
    "Макс.": "Max.",
    "Импорт из IMG": "Import from IMG",
    "Игра": "Game",
    "Папка с IDE": "IDE folder",
    "Найти IDE": "Find IDE",
    "IDE найдены ({0}):": "IDE found ({0}):",
    "IDE с моделями из IPL ({0}):": "IDE with this IPL's models ({0}):",
    "Укажите папку с IDE": "Set the IDE folder",
    "Прицепить кисти": "Attach hands",
    "Отцепить": "Detach",
    "Не найден скелет игрока (кости ' L Hand'/' R Hand')": "Player skeleton not found (' L Hand'/' R Hand' bones)",
    "Не найдены кисти (shandl/shandr с ' L Hand01'/' R Hand01')": "Hand models not found (shandl/shandr with ' L Hand01'/' R Hand01')",
    "Прицеплено кистей: {0}": "Hands attached: {0}",
    "Снято привязок: {0}": "Constraints removed: {0}",
    "Экспорт жеста → ghands.ifp": "Export gesture → ghands.ifp",
    "Нет активных анимаций (назначь Action на ped/shandl/shandr)": "No active actions (assign an Action to ped/shandl/shandr)",
    "Неизвестные кости — {0}": "Unknown bones — {0}",
    "ghands.ifp: заменено {0}, добавлено {1} · {2} ({3})": "ghands.ifp: replaced {0}, added {1} · {2} ({3})",
    "Выберите IPL-файл": "Select an IPL file",
    "Укажите путь к игре (Game Root)": "Set the game path (Game Root)",
    "Не удалось прочитать IPL: {0}": "Could not read IPL: {0}",
    "В IPL нет моделей": "The IPL has no models",
    "Найдено IDE: {0} · моделей покрыто {1}/{2}": "IDE found: {0} · models covered {1}/{2}",
    "Извлечь ресурсы": "Extract Resources",
    "Собрать карту": "Build Map",
    "Bounds / Textured": "Bounds / Textured",
    "Bounds: ON": "Bounds: ON",
    "Bounds: OFF": "Bounds: OFF",
    "Загрузить .glb": "Load .glb",
    "уникальных моделей": "unique meshes",
    "Нет моделей для импорта": "No models to import",
    "Нет DFF файлов в кэше. Сначала извлеките ресурсы.": "No DFF files in cache. Extract resources first.",
    "Извлечено текстур:": "Textures extracted:",
    "Импорт карты": "Import Map",
    "Без LOD": "Skip LOD",
    "Без TXD": "Skip TXD",
    "Без коллизии": "Skip COL",
    "Заменить на DFF": "Replace with DFF",
    "Заменено:": "Replaced:",
    "Выделите fake объекты карты": "Select fake map objects",
    "Импорт плоскостей вместо моделей (быстрый превью карты)": "Import planes instead of models (fast map preview)",
    "Район карты для импорта": "Map region to import",
    "Не найден gta3.img": "gta3.img not found",
    "Не найден IMG архив": "IMG archive not found",
    "Кеш пуст — сначала запустите «Извлечь ресурсы»": "Cache is empty — run «Extract Resources» first",
    "Секции IPL": "IPL Sections",
    "Пропустить LOD модели при импорте": "Skip LOD models during import",
    "Загружать TXD текстуры вместе с DFF": "Load TXD textures with DFF",
    "Импортировано:": "Imported:",
    "Экспорт в IMG": "Export to IMG",
    "Укажите путь к IMG архиву в INU Tools": "Set IMG archive path in INU Tools",
    "IPL файл пуст или не указан": "IPL file is empty or not specified",
    "Пропустить LOD модели при импорте": "Skip LOD models during import",
    "Загружать TXD текстуры вместе с DFF": "Load TXD textures with DFF",
    "Импортировано:": "Imported:",
    "пропущено:": "skipped:",
    "ошибок:": "errors:",
    "Укажите путь к IDE файлу": "Set IDE file path",
    "Укажите путь к IPL файлу": "Set IPL file path",
    "Нет объектов с Model ID > 0": "No objects with Model ID > 0",
    "объектов с Model ID = 0, задайте ID в свойствах": "objects with Model ID = 0, set ID in properties",
    "обновлено": "updated",
    "добавлено": "added",
    "удалено": "removed",
    "Пресеты:": "Presets:",
    "Пресет загружен:": "Preset loaded:",
    "Пресет не найден": "Preset not found",
    "Пресет сохранён:": "Preset saved:",
    "Пресет удалён:": "Preset deleted:",
    "Выбрать пресет настроек прелайта": "Select prelight settings preset",
    "Сгладить между объектами": "Smooth between objects",
    "Сглажено стыков:": "Smoothed seams:",
    "Выделите минимум 2 меш объекта": "Select at least 2 mesh objects",
    "Нет vertex colors": "No vertex colors",
    "Максимальное расстояние между вершинами для сопоставления": "Maximum distance between vertex for matching",
    "Открыт:": "Opened:",
    "Проверка вершин": "Check Vertex",
    "Проверка N-gon": "Check N-gon",
    "Проверка материалов": "Check materials",
    "Очистка материалов": "Cleanup materials",
    "Сортировка материалов": "Sort materials",
    "Сброс трансформ": "Reset Transform",
    "Сброшено объектов:": "Objects reset:",
    "LightMap UV2": "LightMap UV2",
    "Добавить LightMap": "Add LightMap",
    "Привязанные 2DFX:": "Attached 2DFX:",
    "Отвязать все": "Detach All",
    "материалов": "materials",
    "удалено": "removed",
    "Файл не найден": "File not found",
    "COL light материалов:": "COL light materials:",
    "Запечь COL Light": "Bake COL Light",

    # Water IO
    "Добавить воду": "Add Water",
    "Параметры воды:": "Water Parameters:",
    "Скорость течения:": "Flow Speed:",
    "Волны": "Waves",
    "Применить": "Apply",
    "Инструменты:": "Tools:",
    "Привязка к сетке (x4)": "Snap to Grid (x4)",
    "Привязка к блоку (500)": "Snap to Block (500)",
    "Привязано к блоку:": "Snapped to block:",
    "Порезать по блокам (500)": "Split by Blocks (500)",
    "Порезано по блокам:": "Split by blocks:",
    "объектов:": "objects:",
    "Разделить на объекты": "Separate into objects",
    "Разнести куски по отдельным объектам — по одному на блок 500×500":
        "Move the pieces into separate objects — one per 500x500 block",
    "Выделите водные объекты": "Select water objects",
    "Выйдите из режима редактирования": "Leave Edit Mode first",
    "Сшить края": "Stitch Edges",
    "Показать лимиты (500)": "Show Limits (500)",
    "Не влезает:": "Oversize:",
    "на границе:": "on border:",
    "Все грани влезают": "All faces fit",
    "Лимиты воды: показаны": "Water limits: shown",
    "Лимиты воды: скрыты": "Water limits: hidden",
    "Привязать к блоку 500": "Snap to 500 block",
    "Сторона квада в юнитах. 500 — максимум, влезающий в один блок воды GTA SA": "Quad side in units. 500 is the maximum that fits one GTA SA water block",
    "Разместить квад так, чтобы он лёг в игровую сетку блоков 500×500 (иначе вода рендерится без текстуры)": "Place the quad so it lands on the 500×500 water-block grid (otherwise water renders without a texture)",
    "Обычная / Невидимая": "Default / Invisible",
    "Обычная / Видимая": "Default / Visible",
    "Мелкая / Невидимая": "Shallow / Invisible",
    "Мелкая / Видимая": "Shallow / Visible",
    "Глубокая вода, не отображается (подводные зоны)": "Deep water, not rendered (underwater zones)",
    "Глубокая вода с волнами (океан, реки)": "Deep water with waves (ocean, rivers)",
    "Мелкая вода, не отображается (анимация хождения по воде)": "Shallow water, not rendered (wade animation)",
    "Мелкая вода, отображается (лужи, пруды)": "Shallow water, rendered (puddles, ponds)",

    # Path IO
    "Пути": "Paths",
    "Маршруты полётов:": "Flight Paths:",
    "Ж/д пути:": "Train Tracks:",
    "Пешеходные/Авто пути:": "Ped/Vehicle Paths:",
    "Маршрут полёта": "Flight Path",
    "Ж/д путь": "Train Track",
    "Авто пути": "Vehicle Paths",
    "Пешеходные пути": "Ped Paths",
    "Навигационные точки": "Navigation Nodes",
    "Создать ж/д путь": "Add Train Track",
    "Станция (вкл/выкл)": "Station (toggle)",
    "Авто путь": "Vehicle Path",
    "Пеш. путь": "Ped Path",
    "Ж/д путь создан. Редактируйте в Edit Mode": "Train track created. Edit in Edit Mode",
    "Авто путь создан. Добавляйте вершины в Edit Mode": "Vehicle path created. Add vertex in Edit Mode",
    "Пешеходный путь создан. Добавляйте вершины в Edit Mode": "Ped path created. Add vertex in Edit Mode",
    "Пути (paths.ipl):": "Paths (paths.ipl):",
    "Создать путь": "Add Path",
    "Скомпилированные (NODES):": "Compiled (NODES):",
    "Геометрия путей": "Path geometry",
    "Создать или скрыть геометрию визуализации путей":
        "Create or hide path visualisation geometry",
    "Путь IPL": "Path IPL",
    "Авто": "Vehicle",
    "Пешеходный": "Pedestrian",
    "Автомобильный путь": "Vehicle path",
    "Пешеходный путь": "Pedestrian path",
    "Конвертировать в путь": "Convert to Path",
    "Нельзя конвертировать меш с полигонами": "Cannot convert mesh with polygons",

    # IFP Animations
    "Анимации": "Animations",
    "Анимации IFP (GTA SA):": "IFP Animations (GTA SA):",
    "анимаций загружено": "animations loaded",
    "Анимация": "Animation",
    "Применить анимацию": "Apply Animation",
    "Текущая": "Current",
    "Выделите скелет для применения": "Select armature to apply",
    "Выделите скелет (Armature)": "Select an armature",
    "Разблокировать редактирование": "Unlock Editing",
    "Редактирование разблокировано. Геометрия будет пересчитана при экспорте": "Editing unlocked. Geometry will be rebuilt on export",
    "Экспорт: побайтовая копия": "Export: byte-perfect copy",
    "Редактирование разблокировано": "Editing unlocked",
    "Экспорт: пересчёт геометрии": "Export: geometry rebuild",
    "Скин: побайтовая копия": "Skin: byte-perfect copy",
    "Скин: пересчёт геометрии": "Skin: geometry rebuild",

    # v1.6.0 / v1.6.1
    "Извлечь ресурсы": "Extract Resources",
    "Собрать карту в .glb": "Build Map .glb",
    "Импорт карты .glb": "Import Map .glb",
    "Заменить Empty": "Replace Empty",
    "Удалить из IMG": "Remove from IMG",
    "Файлы IMG": "IMG Files",
    "Обновить список": "Refresh List",
    "Создать файл ID": "Create ID File",
    "Загрузить из игры": "Load from Game",
    "Открыть файл ID": "Open ID File",
    "Назначить ID выделенным": "Assign ID to Selected",
    "Синхронизировать сцену": "Sync Scene",
    "Заполнить ID (321-19999)": "Fill IDs (321-19999)",
    "Занято ID:": "Used IDs:",
    "Загружено ID:": "Loaded IDs:",
    "Добавлено ID:": "Added IDs:",
    "Очищено ID:": "Cleared IDs:",
    "Очистить ID": "Clear ID",
    "Очистить ID выделенных": "Clear selected IDs",
    "освобождено в пресете:": "freed in preset:",
    "Загружать коллизии из кеша при импорте карты. Нужно для round-trip (импорт части карты → редактирование → экспорт в IMG другой сборки). При выключенном — только DFF геометрия, сцена легче": "Load collisions from cache during map import. Needed for round-trip (import part of map → edit → export to IMG in another build). When off — geometry only, scene stays lighter",
    "Освободить фантомы": "Free phantoms",
    "Освобождено фантомных ID:": "Phantom IDs freed:",
    "Освободить записи пресета, у которых нет соответствующего объекта в сцене": "Free preset entries with no matching scene object",
    "Shared TXD": "Shared TXD",
    "Добавить в IFP": "Merge Into IFP",
    "Неизвестные кости в Action:": "Unknown bones in Action:",
    "неизвестные кости:": "unknown bones:",
    "Проверить round-trip": "Validate round-trip",
    "Начальный индекс": "Start index",
    "0-based индекс первой анимации в отфильтрованном списке. Удобно бить ped.ifp на порции: 0..49 проверил → 50..99 следующим проходом, не забивая сцену сразу всеми 294 клипами": "0-based index of the first animation in the filtered list. Handy for slicing ped.ifp: run 0..49, then 50..99, instead of dumping all 294 clips into the scene at once",
    "Сколько применить": "Count",
    "Максимум анимаций для обработки в этом запуске. 0 = все оставшиеся после start_index": "Maximum animations to process in this run. 0 = all remaining after start_index",
    "диапазон": "range",
    "из": "of",
    "Выберите анимацию в списке": "Pick an animation from the list",
    "Preview ●": "Preview ●",
    "Прорежать ключи": "Decimate keyframes",
    "Формат": "Format",
    "Кодировка IFP-файла на диске. ANP3 — компактный формат GTA SA (int16). ANPK / ANP2 — chunked float32 (GTA III, VC, плюс совместим с SA)": "On-disk IFP encoding. ANP3 — compact GTA SA format (int16). ANPK / ANP2 — chunked float32 (GTA III, VC, also loadable in SA)",
    "Chunked float32 — III, VC, читается и в SA": "Chunked float32 — III, VC, also loaded by SA",
    "Flat int16-compressed — родной формат GTA SA, минимальный размер файла": "Flat int16-compressed — native GTA SA format, smallest file size",
    "Удалять keyframe'ы которые лежат на линейной интерполяции между соседями. Уменьшает размер .ifp без потери качества — первый и последний ключ каждой кости сохраняются всегда": "Drop keyframes that lie on a linear interpolation between neighbours. Reduces .ifp size without quality loss — first and last keyframe of every bone are always preserved",
    "Допуск поворота": "Rotation tolerance",
    "Max-norm tolerance по XYZW quaternion. 1e-3 безопасно — ANP3 квантует rotation c точностью 1/4096 ≈ 2.4e-4, поэтому ниже не имеет смысла": "Max-norm tolerance on XYZW quaternion. 1e-3 is safe — ANP3 quantises rotation at 1/4096 ≈ 2.4e-4, going below that brings no benefit",
    "Допуск позиции": "Translation tolerance",
    "Max-norm tolerance по XYZ translation в DFF-единицах (обычно метры). 1e-3 = около 1 мм — незаметно при обычных масштабах сцены": "Max-norm tolerance on XYZ translation in DFF units (usually metres). 1e-3 ≈ 1 mm — invisible at typical scene scales",
    "с прореживанием": "decimated",
    "прорежено": "decimated",
    "ключей": "keys",
    "Нет анимаций для экспорта": "No animations to export",
    "Нет анимаций для merge": "No animations to merge",
    "Укажите .ifp файл": "Pick an .ifp file",
    "Анимации:": "Animations:",
    "Кости:": "Bones:",
    "Ключи:": "Keyframes:",
    "Макс. отклонение поворота:": "Max rotation delta:",
    "Макс. отклонение позиции:": "Max translation delta:",
    "Макс. отклонение времени:": "Max time delta:",
    "Потеряны анимации:": "Missing animations:",
    "Анимаций с потерянными костями:": "Animations with missing bones:",
    "Несовпадений по числу ключей:": "Keyframe-count mismatches:",
    "Round-trip: OK ✓": "Round-trip: OK ✓",
    "Round-trip: расхождения ⚠": "Round-trip: mismatches ⚠",
    "Только текущая анимация": "Current action only",
    "Имя пакета (оставьте пустым чтобы сохранить имя существующего файла)": "Package name (leave empty to keep the existing file's name)",
    "Экспортировать только активную Action арматуры (Action Editor). Иначе — все Actions с меткой ifp_source плюс активная": "Export only the armature's active Action (Action Editor). Otherwise — all Actions tagged with ifp_source plus the active one",
    "У арматуры нет активной Action — включите опцию «Только текущая» выкл. или присвойте Action": "Armature has no active Action — either disable «Current action only» or assign an Action",
    "заменено": "replaced",
    "Добавить или заменить анимации в существующем IFP-паке.\n\n    Открывает ped.ifp / anim.ifp (или любой другой .ifp), подменяет\n    анимации по имени (case-insensitive) или дописывает в конец, и\n    сохраняет файл обратно. Остальные анимации пака сохраняются.\n    Позволяет обойтись без внешних IFP-редакторов при правке одной\n    анимации в ванильном паке": "Add or replace animations in an existing IFP pack.\n\n    Opens ped.ifp / anim.ifp (or any other .ifp), overwrites animations\n    by name (case-insensitive) or appends them, then saves the file back.\n    Other animations in the pack stay intact. Lets you skip external\n    IFP editors when editing a single animation in a vanilla pack",
    "Писать все текстуры в один общий .txd файл вместо отдельного .txd на каждую модель. Полезно для районов и сборок где множество моделей делят одни и те же текстуры": "Pack all textures into one shared .txd file instead of a separate .txd per model. Handy for districts and builds where many models share the same textures",
    "Имя общего .txd": "Shared .txd name",
    "Имя общего .txd файла без расширения (например 'district' → district.txd)": "Name of the shared .txd file without extension (e.g. 'district' → district.txd)",
    "Все ID очищены": "All IDs cleared",
    "Файл ID не найден. Нажмите 'Создать файл ID'": "ID file not found. Click 'Create ID File'",
    "Свободных:": "Free:",
    "Занятых:": "Used:",
    "Следующий свободный:": "Next free:",
    "Свободные:": "Free:",
    "ещё": "more",
    "LOD/COL → DFF": "LOD/COL → DFF",
    "Перемещено:": "Moved:",
    "Сшить вершины": "Snap Border Vertex",
    "вершин усреднено": "vertex averaged",
    "Суффиксы / Префиксы": "Suffixes / Prefixes",
    "Суффиксы:": "Suffixes:",
    "Префиксы:": "Prefixes:",
    "суффикс ИЛИ префикс": "suffix OR prefix",
    "Секции IPL": "IPL Sections",
    "Количество записей в IDE файле": "Number of entries in IDE file",
    "Количество записей в IPL файле": "Number of entries in IPL file",
    "конфликт с": "conflict with",
    "Укажите путь к .img архиву": "Specify path to .img archive",
    "Файлы не найдены в IMG": "Files not found in IMG",
    "Авто TXD": "Auto TXD",
    "Стандартная модель GTA SA (vanilla)": "Standard GTA SA model (vanilla)",
    "Кастом: связать + сохранить заборы": "Custom: connect + keep fences",
    "Авто-сварка + острые рёбра": "Auto-weld + sharp edges",
    "Авто-острые рёбра (vanilla)": "Auto sharp edges (vanilla)",
    "Кастомная модель: импорт как есть": "Custom model: import as-is",
    "Как импортировать DFF?": "How to import the DFF?",
    "текстур импортировано": "textures imported",
    "Поиск по ID или имени модели": "Search by ID or model name",
    "Дистанция LOD": "LOD Distance",
    "Дальность прорисовки LOD модели (IDE)": "LOD model draw distance (IDE)",
    "Префикс для DFF моделей": "Prefix for DFF models",
    "Префикс для LOD моделей": "Prefix for LOD models",
    "Префикс для COL моделей": "Prefix for COL models",
    "Укажите корневую папку GTA SA": "Specify GTA SA root folder",
    "Район карты для импорта": "Map region for import",
    "Нет DFF файлов в кэше. Сначала извлеките ресурсы.": "No DFF files in cache. Extract resources first.",
    "Ошибка чтения IMG": "IMG read error",
    "Укажите путь к IMG": "Specify path to IMG",
    "Файлов:": "Files:",
    "Отсортировано:": "Sorted:",
    "BBox: OFF": "BBox: OFF",
    "BBox: ON": "BBox: ON",
    "Links: OFF": "Links: OFF",
    "Links: ON": "Links: ON",
    "Import Map": "Import Map",
    "Вся карта": "Entire Map",
    "Блик солнца": "Sun Glare",
    "Свет": "Light",
    "Частица": "Particle",
    "Ped Attractor": "Ped Attractor",
    "Тип эффекта": "Effect Type",
    "Убрать Itera": "Remove Itera",
    "Импорт DFF": "Import DFF",
    "Экспорт DFF": "Export DFF",
    "Импорт COL": "Import COL",
    "Экспорт COL": "Export COL",
    "Экспорт TXD": "Export TXD",
    "Экспорт / Импорт": "Export / Import",
    "Импорт всей карты": "Import Entire Map",
    "Выберите 2DFX Empty для редактирования": "Select a 2DFX Empty to edit",
    "Itera Tools 3 не найден в библиотеках ассетов": "Itera Tools 3 not found in Asset Libraries",
    "Itera не найден в библиотеках ассетов": "Itera not found in Asset Libraries",
    "Коллекции Itera привязаны к сцене": "Itera collections linked to scene",
    "Линейное освещение вершин с UV текстурой": "Vertex Lit Linear with UV texture",
    "Не найден Armature!": "Armature not found!",
    "Нет активного объекта!": "No active object!",
    "Нет граничных вершин": "No border vertex",
    "Показать цифры на полигонах": "Show numbers on polygons",
    "Порог яркости: 0 = без порога, 100 = максимальная отсечка": "Brightness threshold: 0 = no threshold, 100 = max cutoff",
    "Размер цифр на полигонах": "Number size on polygons",
    "Контраст: резкость перехода между тёмными и светлыми зонами": "Contrast: sharpness between dark and light zones",
    "Сдвиг границы COL освещения: + расширяет зелёную зону, — сужает": "COL light boundary shift: + expands green zone, — shrinks",
    "Статус: Готов": "Status: Ready",
    "Статус: Не найден": "Status: Not Found",
    "Суффикс для DFF моделей": "Suffix for DFF models",
    "Суффикс для LOD моделей": "Suffix for LOD models",
    "Суффикс для COL моделей": "Suffix for COL models",
    "Day — дневные вертексные цвета (prelight)\nNight — ночные вертексные цвета (требует Pipeline: Building)":
        "Day — daytime vertex colors (prelight)\nNight — nighttime vertex colors (requires Pipeline: Building)",
    "None — без pipeline\nVehicle — машины (отражения кузова, env map)\nBuilding DN — здания с day/night vertex colors\nBuilding — обычные здания\n\nNormals — динамическое освещение движком (персонажи, транспорт, оружие)\nОтключить для зданий и объектов карты (используют vertex colors)":
        "None — no pipeline\nVehicle — cars (body reflections, env map)\nBuilding DN — buildings with day/night vertex colors\nBuilding — plain buildings\n\nNormals — dynamic engine lighting (characters, vehicles, weapons)\nDisable for buildings and map objects (use vertex colors)",
    # FLA / ID Manager
    "Расширить ID (FLA)": "Extend IDs (FLA)",
    "Количество ID для добавления": "Number of IDs to add",

    # ID Presets (v1.6.4+)
    "Пресет ID": "ID Preset",
    "Пресет": "Preset",
    "Активный файл со списком ID. Каждый пресет — отдельный .txt в папке data/id_presets/":
        "Active file with the ID list. Each preset is a separate .txt in data/id_presets/",
    "Название пресета": "Preset name",
    "Имя нового пресета": "Name of the new preset",
    "Название": "Name",
    "Имя нового пресета. Будет сохранён как data/id_presets/<имя>.txt":
        "Name of the new preset. Will be stored as data/id_presets/<name>.txt",
    "Скопировать с активного": "Copy from active",
    "Создать пресет как копию текущего активного":
        "Create the preset as a copy of the current active one",
    "Введите название пресета": "Enter a preset name",
    "Пресет уже существует или не удалось создать":
        "Preset already exists or could not be created",
    "Создан пресет:": "Preset created:",
    "Пресет 'default' удалить нельзя": "The 'default' preset cannot be deleted",
    "Не удалось удалить пресет": "Failed to delete the preset",
    "Удалён пресет:": "Preset deleted:",
    "Новое название": "New name",
    "Введите новое название": "Enter a new name",
    "Не удалось переименовать (имя занято или ошибка)":
        "Failed to rename (name taken or error)",
    "Переименован:": "Renamed:",
    "Заполнить активный пресет ID (321-19999, все свободные)":
        "Fill the active ID preset (321-19999, all free)",
    "Открыть файл активного ID пресета в текстовом редакторе":
        "Open the active ID preset file in a text editor",
    "Создать новый пресет ID.\n\n    Пустой пресет создаётся готовым к `Создать файл ID` (Заполнить 321-19999).\n    Опция «Скопировать с активного» дублирует текущий файл ID, чтобы не\n    начинать с нуля, если часть ID уже назначена.":
        "Create a new ID preset.\n\nAn empty preset is ready for 'Create ID File' (fill 321-19999).\nThe 'Copy from active' option duplicates the current ID file so you\ndon't have to start from scratch when some IDs are already assigned.",
    "Удалить активный пресет ID. Пресет «default» удалить нельзя":
        "Delete the active ID preset. The 'default' preset cannot be removed",
    "Переименовать активный пресет ID": "Rename the active ID preset",

    # Batch operations
    "Назначить с ID...": "Assign from ID...",
    "Начальный ID для назначения": "Starting ID for assignment",
    "Назначено ID:": "Assigned IDs:",
    "Тип:": "Type:",

    # X Radar Maker
    "Папка": "Folder",
    "Сетка": "Grid",
    "Размер": "Size",
    "Высота": "Height",
    "Индексы": "Indices",
    "Генерировать радар": "Generate Radar",
    "Меню радар (3x3)": "Menu Radar (3x3)",
    "Полный радар": "Full Radar",
    "Полный меню": "Full Menu",
    "Указанные тайлы": "Specific Tiles",
    "Упаковать в TXD": "Pack to TXD",
    "тайлов сохранено": "tiles saved",
    "архивов создано": "archives created",
    "Укажите папку для сохранения": "Specify output folder",
    "Укажите индексы тайлов (например 0,1,8,9)": "Specify tile indices (e.g. 0,1,8,9)",
    "Папка для сохранения тайлов радара": "Folder for saving radar tiles",
    "Размер сетки (8 = 64 тайла)": "Grid size (8 = 64 tiles)",
    "Размер тайла в пикселях": "Tile size in pixels",
    "Высота камеры": "Camera height",
    "Индексы тайлов через запятую (0,1,5,63)": "Tile indices comma-separated (0,1,5,63)",

    # v1.6.3 — Particle Effects (effects.fxp)
    "Имя эффекта из effects.fxp": "Effect name from effects.fxp",
    "Индекс редактируемого эмиттера (для систем с несколькими)": "Index of edited emitter (for multi-emitter systems)",
    "Редактируемая кривая в формате INFO.FIELD (например SIZE.SIZEX)": "Edited curve in INFO.FIELD format (e.g. SIZE.SIZEX)",
    "Имя спрайта из particle.txd": "Sprite name from particle.txd",
    "Добавить промежуточный ключ для плавного fade-in/fade-out": "Add intermediate key for smooth fade-in/fade-out",
    "Позиция промежуточного ключа по времени жизни (0..1)": "Intermediate key position over lifetime (0..1)",
    "Размер частицы в начале жизни": "Particle size at start of life",
    "Размер частицы в конце жизни": "Particle size at end of life",
    "Длительность жизни частицы в секундах": "Particle lifetime in seconds",
    "Количество частиц в секунду": "Particles per second",
    "Начальная скорость частицы": "Particle initial speed",
    "Направление эмиссии": "Emission direction",
    "Анимировать 2DFX частицы в viewport": "Animate 2DFX particles in viewport",
    "Имя нового эффекта (должно быть уникальным)": "New effect name (must be unique)",
    "Создастся пустая система с одним эмиттером": "An empty system with one emitter will be created",
    "Текстура: sphere. Жизнь 1с, rate 10/с, цвет белый": "Texture: sphere. Life 1s, rate 10/s, color white",
    "Действие необратимо (хотя есть .bak)": "Action is irreversible (though .bak is available)",
    "Имя системы в effects.fxp (можно новое — тогда клонируется из текущей)": "System name in effects.fxp (new name clones from current)",
    "Перезаписать существующую систему с таким именем": "Overwrite existing system with this name",
    "При первой записи создастся effects.fxp.bak": "On first write effects.fxp.bak will be created",
    "Эффект": "Effect",
    "Симуляция": "Simulation",
    "Переключение сбросит правки — сохраняйте первыми": "Switching will reset edits — save first",
    "Спрайт и смешивание": "Sprite & blending",
    "Текстура": "Texture",
    "Цвет (start → end)": "Color (start → end)",
    "Начало": "Start",
    "Средний": "Middle",
    "Конец": "End",
    "Эмиссия": "Emission",
    "Жизнь": "Life",
    "Скорость": "Speed",
    "Направление": "Direction",
    "Физика": "Physics",
    "Система": "System",
    "Кривые (keyframes)": "Curves (keyframes)",
    "Выбрать кривую...": "Select curve...",
    "Нет ключей": "No keys",
    "Записать кривую в effects.fxp": "Write curve to effects.fxp",
    "Сохранить в effects.fxp": "Save to effects.fxp",
    "effects.fxp не найден:": "effects.fxp not found:",
    "Ошибка парсинга effects.fxp:": "effects.fxp parse error:",
    "Reload effects.fxp": "Reload effects.fxp",

    # v1.6.3 — Object Properties IDE/IPL panel
    "GTA SA: IDE / IPL": "GTA SA: IDE / IPL",

    # v1.6.3 — Bone Management
    "Выделите кость в Armature": "Select a bone in Armature",
    "Выделите Armature": "Select an Armature",
    "Не найдены пары костей L/R": "No L/R bone pairs found",
    "Armature не найден": "Armature not found",
    "Костей:": "Bones:",
    "Переименовать": "Rename",
    "Выделить": "Select",
    "Выделите кость для редактирования": "Select a bone to edit",
    "Инструменты весов:": "Weight Tools:",
    "Нормализовать (4 кости)": "Normalize (4 bones)",
    "Зеркалировать X (L↔R)": "Mirror X (L↔R)",
    "Список костей:": "Bone List:",

    # v1.6.3 — Vertex Paint panel
    "Пост-обработка:": "Post-processing:",
    "Объект": "Object",

    # v1.6.3 — Shared TXD
    "Общий TXD": "Shared TXD",
    "Имя общего TXD файла для нескольких DFF моделей": "Shared TXD filename for multiple DFF models",
    "Дописать в существующий": "Append to existing",
    "Если выбранный TXD уже существует — добавить/обновить в нём текстуры сцены, сохранив остальные текстуры файла (от других моделей). Иначе файл перезаписывается целиком.": "If the chosen TXD already exists, add/update the scene's textures in it while keeping the file's other textures (from other models). Otherwise the file is fully overwritten.",
    "Дописать в существующий TXD": "Append to existing TXD",
    "Один DFF (машина/пед)": "Single DFF (vehicle / ped)",
    "вне иерархии корня, пропущено объектов": "outside the root hierarchy, objects skipped",
    "корень": "root",
    "COL-меш не найден — коллизия не встроена в .dff": "No COL mesh found — collision not embedded into the .dff",
    "Экспортировать ВСЮ выделенную иерархию в ОДИН .dff (машина, пед, любая многокомпонентная модель), а не разбивать по именам на отдельные файлы. TXD/COL при этом пишутся одним общим файлом. Имя берётся из поля имени внизу.": "Export the WHOLE selected hierarchy into ONE .dff (vehicle, ped, any multi-part model) instead of splitting by name into separate files. TXD/COL are written as one shared file. The name is taken from the filename field below.",
    "Ничего не экспортировано": "Nothing was exported",
    "Текстуры в": "Textures into",
    "Имя экспорта:": "Export name:",
    "Несколько моделей — имена по моделям": "Multiple models — named per model",
    "Модель не выделена": "No model selected",
    "TXD эффектов": "FX TXD",
    "Не выбран": "Not selected",
    "У выделенной модели нет пары: name_hi/name_low или GTA DFF/LOD (name_dff/name_lod)": "The selected model has no pair: name_hi/name_low or a GTA DFF/LOD pair (name_dff/name_lod)",
    "Путь к .txd с текстурами эффектов GTA SA (короны, тени, вода — например particle.txd). Эти текстуры НЕ входят в аддон (это ассеты игры) и грузятся отсюда для превью 2DFX. Если пусто — ищутся автоматически в папке игры (Game Root).": "Path to a .txd with GTA SA effect textures (coronas, shadows, water — e.g. particle.txd). These textures are NOT bundled with the addon (they are game assets) and are loaded from here for the 2DFX preview. If empty, they are auto-found in the game folder (Game Root).",
    "Текстуры эффектов (.txd):": "Effect textures (.txd):",
    "Загрузить текстуры эффектов": "Load effect textures",
    "текстур эффектов загружено": "effect textures loaded",
    "Текстуры эффектов не найдены — укажи particle.txd или путь к игре (Game Root)": "No effect textures found — set particle.txd or the game path (Game Root)",
    "Разрешить сборку Asset Library": "Allow Asset Library build",
    "Сборка Asset Library запускает ФОНОВЫЙ процесс Blender (blender --background) на встроенном скрипте. Это безопасно (запускается сам Blender, не сторонняя программа), но по умолчанию выключено. Включи, если осознанно пользуешься этой функцией.": "Building the Asset Library spawns a BACKGROUND Blender process (blender --background) running a bundled script. It is safe (Blender itself runs, not a third-party program), but it is off by default. Enable it if you deliberately use this feature.",
    "Разрешить сборку (фоновый процесс Blender)": "Allow build (background Blender process)",
    "Сборка Asset Library запускает фоновый процесс Blender. Включи галочку «Разрешить сборку Asset Library» в настройках.": "Building the Asset Library spawns a background Blender process. Enable the \"Allow Asset Library build\" checkbox in the settings.",
    "Регенерация превью запускает фоновый процесс Blender. Включи галочку «Разрешить сборку Asset Library» в настройках.": "Regenerating previews spawns a background Blender process. Enable the \"Allow Asset Library build\" checkbox in the settings.",
    "Если .txd уже существует — добавить/обновить в нём текстуры модели, сохранив остальные текстуры файла (от других моделей). Иначе .txd перезаписывается целиком.": "If the .txd already exists, add/update the model's textures in it while keeping the file's other textures (from other models). Otherwise the .txd is fully overwritten.",
    "Не удалось прочитать существующий TXD": "Could not read the existing TXD",
    "Нет текстур для добавления": "No textures to add",
    "TXD обновлён": "TXD updated",
    "обновлено": "updated",
    "добавлено": "added",
    "всего": "total",

    # v1.6.3 — Copy color attributes
    "Day → Night": "Day → Night",
    "Night → Day": "Night → Day",
    "Альфа вершин перенесена": "Vertex alpha transferred",
    "Активным должен быть атрибут Day или Night":
        "The active attribute must be Day or Night",
    "объектов": "objects",

    # v1.6.4 — Experimental features
    # Operator docstrings
    "Проверить все материалы и показать текстуры, файлы которых не найдены":
        "Scan all materials and report textures whose files cannot be found",
    "Рекурсивно искать в выбранной папке и подставлять image.filepath для найденных по имени недостающих текстур":
        "Search a folder recursively and patch image.filepath for any missing texture found by name",
    "Скопировать все используемые материалами текстуры сцены в выбранную папку":
        "Copy every texture used by scene materials into the chosen folder",
    "Хэшировать все файлы текстур и показать группы одинаковых файлов":
        "Hash every texture file and report groups of identical files",
    "Пропорционально масштабировать всю иерархию машины (Empty-корень + меши + дамми), сохраняя структуру. Применяет масштаб к данным меша чтобы DFF-экспорт остался чистым":
        "Rescale the active vehicle hierarchy (Empty root + meshes + dummies) preserving structure. Applies scale to mesh data so DFF export stays clean",
    "Экспортировать выделение как готовый район GTA SA (DFF + COL + TXD + IDE + IPL в одну папку)":
        "Export the current selection as a ready-to-ship GTA SA map (DFF + COL + TXD + IDE + IPL in one folder)",
    "Импортировать все *.ifp из папки и уложить анимации на NLA-трек активного armature":
        "Import every *.ifp in a folder and stack animations on an NLA track of the active armature",
    "Пересоздать видимые Empty-маркеры для каждой станции на активном ж/д пути":
        "Recreate visible Empty markers for every station on the active train track",
    "Переключить roadblock или задать тип светофора на выделенных точках кривой пути":
        "Toggle roadblock or set traffic-light kind on selected spline points of the active path curve",
    "Импорт текстового файла Steve's COL Editor (.cst)":
        "Import a Steve's COL Editor text file (.cst)",
    "Экспорт выделения в текстовый файл Steve's COL Editor (.cst)":
        "Export selection as Steve's COL Editor text file (.cst)",
    "Записать выбранный GTA Material пресет в свойства mat.inu.*":
        "Write the selected GTA Material preset into mat.inu.* properties",

    # Property descriptions
    "Создать подпапку на каждый txd_name (читается с mesh-объектов)":
        "Create a subfolder per txd_name (read from mesh objects)",
    "Множитель равномерного масштаба — применяется к позициям и вершинам":
        "Uniform scale factor applied to positions and vertices",
    "Двигать только дамми-Empty, меши не трогать":
        "Move only the dummy empties, leave meshes untouched",
    "Первый ID для DFF у которых inu.model_id == 0":
        "First ID assigned to DFFs that have inu.model_id == 0",
    "Применять только анимации, имя которых начинается с этого префикса (регистронезависимо)":
        "Only apply animations whose name starts with this prefix (case-insensitive)",
    "Уложить клипы на один NLA-трек с зазором":
        "Stack clips on one NLA track with a gap",
    "Создать Actions, без NLA":
        "Create Actions, no NLA arrangement",
    "Переключить бит 12 (барьер копов) на каждой выделенной точке":
        "Flip bit 12 (cops barrier) on every selected point",
    "Поставить traffic_light=0 на каждой выделенной точке":
        "Write traffic_light=0 on every selected point",
    "Поставить traffic_light=1 на каждой выделенной точке":
        "Write traffic_light=1 on every selected point",
    "Поставить traffic_light=2 на каждой выделенной точке":
        "Write traffic_light=2 on every selected point",
    "Поставить traffic_light=3 на каждой выделенной точке":
        "Write traffic_light=3 on every selected point",

    # UI buttons / labels
    "Импорт CST": "Import CST",
    "Экспорт CST": "Export CST",
    "Масштаб машины…": "Vehicle Scale…",
    "Экспорт машины (один DFF)…": "Export vehicle (single DFF)…",
    "Экспорт скина (один DFF)…": "Export skin (single DFF)…",
    # --- cutscene camera (.dat) ---
    "Камера (катсцена .dat)": "Camera (cutscene .dat)",
    "Камера импортирована: ": "Camera imported: ",
    "Камера экспортирована: ": "Camera exported: ",
    "У камеры нет цели (Track To / Empty «.Target»)": "Camera has no target (Track To / Empty “.Target”)",
    "Нужно ≥2 ключей позиции у камеры и у цели": "Need ≥2 position keyframes on both camera and target",
    "FPS сцены должен быть 30 для катсцен-камеры": "Scene FPS must be 30 for a cutscene camera",
    "Z-offset −1.0": "Z-offset −1.0",
    "Z-offset +1.0": "Z-offset +1.0",
    "Обход Z-бага движка: вычесть 1.0 из Z при импорте (и вернуть при экспорте). Как в оригинальном SetCamera": "Engine Z-bug workaround: subtract 1.0 from Z on import (and add it back on export). As in the original SetCamera",
    "Вернуть 1.0 к Z при экспорте (парно к импорту)": "Add 1.0 back to Z on export (paired with import)",
    # --- breakable extra fields ---
    "Смещение силы": "Force offset",
    "Смещение точки приложения силы разлома (по умолчанию 0,0,0)": "Offset of the break-force application point (default 0,0,0)",
    "Авто-буферы осколков": "Auto shard buffers",
    "Авто-размер буферов сломанной копии по текущей геометрии. Выключи только если движку не хватает места под осколки": "Auto-size the broken-copy buffers from current geometry. Turn off only if the engine runs out of room for the shards",
    "Вершины": "Verts",
    "Грани": "Faces",
    "UV": "UVs",
    "Резерв вершин под сломанную копию": "Vertex reserve for the broken copy",
    "Резерв граней под сломанную копию": "Face reserve for the broken copy",
    "Резерв материалов под сломанную копию": "Material reserve for the broken copy",
    "Резерв UV под сломанную копию": "UV reserve for the broken copy",
    # --- mesh fragmentation tool ---
    "Фрагментация меша": "Fragment mesh",
    "Разделить на чанки": "Split into chunks",
    "Размер чанка (м)": "Chunk size (m)",
    "Сторона квадратного чанка в метрах": "Side length of a square chunk in meters",
    "Способ резки": "Cut mode",
    "По линиям сетки": "Along grid lines",
    "Физически режет полигоны точно по границам ячеек": "Physically splits polygons exactly on cell borders",
    "По существующей геометрии": "By existing geometry",
    "Не режет полигоны; относит грань к чанку по её центру": "Doesn't split polygons; assigns a face to a chunk by its center",
    "Раздельные материалы": "Separate materials",
    "Создать уникальные копии материалов для каждого чанка": "Create unique material copies for each chunk",
    "Центр origin": "Center origin",
    "Поставить точку origin в геометрический центр чанка": "Set the origin point to the chunk's geometric center",
    "Скрыть оригинал": "Hide original",
    "Спрятать исходный меш во вьюпорте и рендере после нарезки": "Hide the source mesh in viewport and render after slicing",
    "Не на что резать (нет граней)": "Nothing to slice (no faces)",
    "Чанки: {0}/{1}": "Chunks: {0}/{1}",
    "Карта разделена на {0} чанков": "Map split into {0} chunks",
    "Сетка (шаг X/Y)": "Grid (X/Y step)",
    "Нарезать по прямоугольной сетке — как object_explode": "Slice along a rectangular grid — like object_explode",
    "Кластеры (N семян)": "Clusters (N seeds)",
    "Сгруппировать грани по ближайшему из N случайных семян": "Group faces by nearest of N random seeds",
    "Шаг X": "X step",
    "Шаг Y": "Y step",
    "Число осколков": "Shard count",
    "Имя осколков": "Shard name",
    "Удалить оригинал": "Delete original",
    "Получился 1 осколок — уменьши шаг / добавь семян": "Got 1 shard — reduce the step / add seeds",
    "Осколков создано": "Shards created",
    # --- IDE flag checkbox labels (Russian + original in parens) ---
    "Рисовать последним (DRAW_LAST)": "Draw last (DRAW_LAST)",
    "Аддитивный (ADDITIVE)": "Additive (ADDITIVE)",
    "Без Z-буфера (NO_ZBUFFER_WRITE)": "No Z-buffer (NO_ZBUFFER_WRITE)",
    "Без затухания (DO_NOT_FADE)": "No fade (DO_NOT_FADE)",
    "Динамический свет (IGNORE_LIGHTING)": "Dynamic light (IGNORE_LIGHTING)",
    "Туннель метро (IS_SUBWAY)": "Subway tunnel (IS_SUBWAY)",
    "Дорога (IS_ROAD)": "Road (IS_ROAD)",
    "Без теней (NO_SHADOWS)": "No shadows (NO_SHADOWS)",
    "Стекло разбиваемое (GLASS_TYPE_1)": "Breakable glass (GLASS_TYPE_1)",
    "Стекло с трещинами (GLASS_TYPE_2)": "Cracked glass (GLASS_TYPE_2)",
    "Игнор. дистанции (IGNORE_DRAW_DIST)": "Ignore draw dist (IGNORE_DRAW_DIST)",
    "Дверь гаража (GARAGE_DOOR)": "Garage door (GARAGE_DOOR)",
    "Повреждаемый (DAMAGABLE)": "Damageable (DAMAGABLE)",
    "Дерево (IS_TREE)": "Tree (IS_TREE)",
    "Пальма (IS_PALM)": "Palm (IS_PALM)",
    "Без колл. с авиа (NO_FLYER_COL)": "No flyer collision (NO_FLYER_COL)",
    "Граффити-тег (IS_TAG)": "Graffiti tag (IS_TAG)",
    "Двусторонний (NO_BACKFACE_CULL)": "Double-sided (NO_BACKFACE_CULL)",
    "Разрушаемая статуя (BREAKABLE_STATUE)": "Breakable statue (BREAKABLE_STATUE)",
    "Batch папка…": "Batch Folder…",
    "Обновить маркеры станций": "Refresh Station Markers",
    "Флаги выделенных точек:": "Flags on selected points:",
    "Переключить Roadblock": "Toggle Roadblock",
    "Светофор —": "Light —",
    "Обычн.": "Normal",
    "Ж/д": "Rail",
    "Авт.": "Bus",
    "Разрушаемый (Breakable)": "Breakable",
    "Писать UV Anim в DFF": "Write UV Anim to DFF",
    "UV Анимация": "UV Animation",
    "Имя анимации": "Animation name",
    "Длительность": "Duration",
    "Break Force": "Break Force",

    # Binary IPL selector
    "Сканировать IMG архивы и собрать список бинарных IPL для выбранного района. После скана можно галочками включать/выключать конкретные файлы":
        "Scan IMG archives and collect the list of binary IPLs for the selected region. After the scan you can enable/disable individual files via checkboxes",
    "Включить этот бинарный IPL в сборку карты":
        "Include this binary IPL when building the map",
    "Включить или выключить все бинарные IPL в списке одной кнопкой":
        "Enable or disable every binary IPL in the list at once",
    "Развернуть список бинарных IPL для галочек":
        "Expand the list of binary IPLs to see individual checkboxes",
    "Бинарные IPL": "Binary IPLs",
    "Район изменился — пересканируйте": "Region changed — rescan",
    "Список пуст — нажмите Scan": "List is empty — click Scan",
    "Все": "All",
    "Никакие": "None",
    "Без 2DFX": "No 2DFX",
    "Не импортировать 2DFX-эффекты (лампы, частицы, ped attractors, sun glare) при импорте карты и DFF":
        "Skip 2DFX effects (lights, particles, ped attractors, sun glare) when importing the map or a DFF",

    # Pipeline enum tooltips
    "Без указания pipeline — использовать стандартный рендер RenderWare. Подходит для простых объектов, которым не нужны специальные эффекты движка":
        "No pipeline — use the plain RenderWare renderer. Suitable for simple objects that need no engine-specific effects",
    "Pipeline кузова машины (RSPIPE_PC_CustomCarEnvMap). Добавляет env-map отражения неба/облаков/улицы. Используется совместно с текстурами vehicleenv128 + vehiclespecdot64 на материале":
        "Car body pipeline (RSPIPE_PC_CustomCarEnvMap). Adds env-map reflections of sky/clouds/street. Pair with vehicleenv128 + vehiclespecdot64 textures on the material",
    "Pipeline здания с day/night vertex colors (RSPIPE_PC_CustomBuildingDN). Движок плавно смешивает дневной и ночной слои vertex colors по игровому времени. Требует ДВА Color Attribute слоя (Day + Night) на меше":
        "Building pipeline with day/night vertex colors (RSPIPE_PC_CustomBuildingDN). The engine blends day and night color layers based on in-game time. Requires TWO Color Attribute layers (Day + Night) on the mesh",
    "Простой pipeline здания (RSPIPE_PC_CustomBuilding). Статическое освещение через один слой vertex colors. Работает быстрее чем Day/Night, но нет смены по времени суток":
        "Plain building pipeline (RSPIPE_PC_CustomBuilding). Static lighting via one vertex color layer. Faster than Day/Night but no time-of-day transition",
    "Указать произвольное значение pipeline ID через поле Custom Pipeline":
        "Enter an arbitrary pipeline ID via the Custom Pipeline field",

    # UV Animation property descriptions
    "Вписать простую UV-прокрутку в экспортируемый DFF":
        "Embed a simple UV-scroll animation into the exported DFF",
    "Скорость прокрутки UV по U в секунду":
        "UV scroll speed along U per second",
    "Скорость прокрутки UV по V в секунду":
        "UV scroll speed along V per second",
    "Длительность цикла UV-анимации":
        "Duration of the UV animation cycle",

    # ── Operator/Panel docstrings (auto-translated via register loop) ───
    "IDE/IPL свойства в Object Properties": "IDE / IPL properties in Object Properties",
    "X Radar Maker — генерация тайлов мини-карты GTA SA":
        "X Radar Maker — generate GTA SA radar tiles",
    "Включить/выключить отображение LightMap UV2":
        "Toggle LightMap UV2 display",
    "Выбрать активный ключ для удаления":
        "Select the active keyframe for removal",
    "Выбрать имя эффекта из effects.fxp":
        "Pick an effect name from effects.fxp",
    "Выбрать кривую для редактирования":
        "Pick a curve to edit",
    "Выбрать позицию привязки UV в ячейке":
        "Pick the UV snap anchor inside the cell",
    "Выставить Vehicle pipeline (0x53F2009A) на выделенных MESH-объектах.\n    Нужен чтобы кузов получил env-map отражения в игре.":
        "Set the Vehicle pipeline (0x53F2009A) on selected MESH objects.\nRequired so the body gets env-map reflections in game.",
    "Генерировать тайлы радара GTA SA":
        "Generate GTA SA radar tiles",
    "Добавить / обновить запись в существующем IDE файле (авто-LOD)":
        "Insert / update an entry in an existing IDE file (auto-LOD)",
    "Добавить / обновить запись в существующем IPL файле (авто-LOD привязка)":
        "Insert / update an entry in an existing IPL file (auto-LOD linkage)",
    "Добавить ID (Fastman Limit Adjuster)":
        "Add IDs (Fastman Limit Adjuster)",
    "Добавить ID из объектов сцены в менеджер":
        "Add IDs from scene objects into the manager",
    "Добавить ключевой кадр в конец кривой":
        "Append a keyframe to the end of the curve",
    "Единый экспорт INU — DFF, COL, TXD, IDE, IPL в одну папку":
        "Unified INU export — DFF, COL, TXD, IDE, IPL into one folder",
    "Загрузить выбранный пресет":
        "Load the selected preset",
    "Загрузить занятые ID из IDE файлов GTA SA":
        "Load occupied IDs from GTA SA IDE files",
    "Задать параметры воды для выделенных объектов":
        "Set water parameters on selected objects",
    "Заменить IPL Empty-плейсхолдеры на модели из сцены":
        "Replace IPL empty placeholders with scene models",
    "Заменить выделенные fake-объекты на DFF модели из IMG":
        "Replace selected fake objects with real DFF models from IMG",
    "Записать буфер ключей обратно в effects.fxp для выбранной кривой":
        "Write the keyframe buffer back to effects.fxp for the selected curve",
    "Извлечь все DFF, COL и текстуры из IMG в .inu_cache/":
        "Extract all DFF, COL and textures from IMG into .inu_cache/",
    "Импорт GTA SA файлов (.dff/.col/.txd/.ide/.ipl) с авто-определением формата":
        "Import GTA SA files (.dff/.col/.txd/.ide/.ipl) with auto format detection",
    "Импорт IFP — анимации GTA SA":
        "Import IFP — GTA SA animations",
    "Импорт TXD при перетаскивании во viewport":
        "Import TXD on drag-and-drop into the viewport",
    "Импорт flight.dat — маршруты полётов":
        "Import flight.dat — flight paths",
    "Импорт nodes.dat — пешеходные/авто пути (мультивыбор)":
        "Import nodes.dat — pedestrian / vehicle paths (multi-select)",
    "Импорт paths.ipl — пути для gta.dat":
        "Import paths.ipl — paths listed in gta.dat",
    "Импорт tracks.dat — железнодорожные пути":
        "Import tracks.dat — railway paths",
    "Импорт water.dat": "Import water.dat",
    "Импорт карты GTA SA: автопоиск IDE/IPL/IMG по папке игры":
        "Import GTA SA map: auto-discover IDE/IPL/IMG from the game folder",
    "Импорт секций IPL (cull, grge, enex, pick, cars, auzo, jump, occl)":
        "Import IPL sections (cull, grge, enex, pick, cars, auzo, jump, occl)",
    "Импортировать .glb карты с сортировкой по коллекциям":
        "Import map .glb with per-collection sorting",
    "Импортировать модели из IMG архива (по списку из IDE/IPL)":
        "Import models from an IMG archive (driven by IDE/IPL)",
    "Интеграция с Itera Tools 3 — материалы освещения":
        "Itera Tools 3 integration — lighting materials",
    "Конвертировать кривую или рёбра меша в путь paths.ipl":
        "Convert a curve or mesh edges into a paths.ipl path",
    "Копировать vertex colors из одного атрибута в другой (Day ↔ Night)":
        "Copy vertex colors between attributes (Day ↔ Night)",
    "Массовое переключение типа объектов (OBJ/COL/SHA/2DFX/NON)":
        "Batch switch object type (OBJ/COL/SHA/2DFX/NON)",
    "Назначить ID всем выделенным объектам с Model ID = 0":
        "Assign IDs to every selected object with Model ID = 0",
    "Назначить последовательные ID выделенным объектам начиная с указанного":
        "Assign sequential IDs to selected objects starting from a given value",
    "Найти все IDE/IPL/IMG по gta.dat из корневой папки игры":
        "Find every IDE/IPL/IMG referenced by gta.dat from the game root",
    "Обновить список файлов IMG архива":
        "Refresh the IMG archive file list",
    "Объединить дубликаты материалов и текстур (.001, .002, и т.д.) с оригиналами":
        "Merge duplicate materials and textures (.001, .002, etc.) with their originals",
    "Освободить ID": "Release ID",
    "Отвязать все 2DFX/частицы от выделенного меша":
        "Detach every 2DFX / particle from the selected mesh",
    "Отметить/снять выбранные точки кривой как станции (flag=1)":
        "Toggle the station flag (flag=1) on the selected curve points",
    "Очистить Model ID у выделенных объектов":
        "Clear Model ID on selected objects",
    "Очистить все занятые ID": "Clear all occupied IDs",
    "Очистить сохранённые raw DFF данные для экспорта отредактированной геометрии":
        "Clear the cached raw DFF data so edited geometry is exported",
    "Панель IDE / IPL / IMG для работы с существующими файлами GTA SA":
        "IDE / IPL / IMG panel for working with existing GTA SA files",
    "Панель Path IO": "Path IO panel",
    "Панель Water IO": "Water IO panel",
    "Панель анимаций IFP": "IFP animations panel",
    "Панель проверки геометрии и материалов":
        "Geometry and materials check panel",
    "Панель экспорта/импорта GTA моделей":
        "GTA model export / import panel",
    "Переключить все Map_ объекты между Bounding Box и Textured":
        "Toggle every Map_ object between Bounding Box and Textured",
    "Переключить редактируемый эмиттер в системе с несколькими":
        "Switch the editable emitter in a multi-emitter system",
    "Перечитать effects.fxp с диска (сбросить кэш)":
        "Reload effects.fxp from disk (flush cache)",
    "Подтянуть LOD и COL к позиции DFF модели":
        "Snap LOD and COL to the DFF model's position",
    "Показать/скрыть линии связей DFF↔LOD↔COL":
        "Show / hide DFF ↔ LOD ↔ COL link lines",
    "Превью COL Night Light — зелёная визуализация и числа на полигонах":
        "Preview COL Night Light — green overlay and per-face numbers",
    "Привязать вершины воды к кратным 4 координатам (требование GTA SA)":
        "Snap water vertices to multiples of 4 (GTA SA requirement)",
    "Применить IFP анимацию к выделенному скелету":
        "Apply an IFP animation to the selected armature",
    "Применить Itera материал из библиотеки к выделенным объектам":
        "Apply an Itera material from the library to selected objects",
    "Применить Quickstart Vertex Lightable Surface — модификатор + коллекция со светом":
        "Apply Quickstart Vertex Lightable Surface — modifier + light collection",
    "Применить стандартные SA-настройки для материала кузова машины:\n    env map = xvehicleenv128, specular = vehiclespecdot64, blend = 0.05, + Vehicle pipeline.\n    Эквивалент кнопки \"SA Vehicle default\" из Kam's GTA_Material.ms.":
        "Apply standard SA vehicle body settings:\nenv map = xvehicleenv128, specular = vehiclespecdot64, blend = 0.05, + Vehicle pipeline.\nEquivalent to Kam's GTA_Material.ms 'SA Vehicle default' button.",
    "Применить текстуру LightMap на UV2 (Multiply) для выделенных объектов":
        "Apply a LightMap texture on UV2 (Multiply) for selected objects",
    "Сброс Location и Rotation в (0,0,0) для выделенных мешей":
        "Reset Location and Rotation to (0, 0, 0) on selected meshes",
    "Сгладить vertex colors на стыках между выделенными объектами":
        "Smooth vertex colors across seams between selected objects",
    "Скрыть/показать DFF, LOD или COL объекты во всей сцене":
        "Hide / show DFF, LOD or COL objects across the whole scene",
    "Собрать один .glb файл карты (все модели с позициями из IPL)":
        "Build a single map .glb (all models with IPL positions)",
    "Создать водный полигон с параметрами GTA SA":
        "Create a water polygon with GTA SA parameters",
    "Создать новый автомобильный путь (меш с вершинами)":
        "Create a new vehicle path (vertex mesh)",
    "Создать новый ж/д путь (кривая)":
        "Create a new railway path (curve)",
    "Создать новый пешеходный путь (меш с вершинами)":
        "Create a new pedestrian path (vertex mesh)",
    "Создать новый пустой эффект в effects.fxp":
        "Create a new empty effect in effects.fxp",
    "Создать новый путь для paths.ipl":
        "Create a new path for paths.ipl",
    "Сохранить правки эффекта обратно в effects.fxp (с автобэкапом)":
        "Save effect edits back to effects.fxp (with auto-backup)",
    "Сохранить текущие настройки как пресет":
        "Save current settings as a preset",
    "Сшить края двух водных плоскостей (выровнять ближайшие вершины)":
        "Stitch the edges of two water planes (align nearest vertices)",
    "Порезать воду по сетке блоков 500×500 — каждая грань ляжет внутрь одного блока (иначе вода рендерится без текстуры)":
        "Cut water along the 500x500 block grid so every face sits inside a single block (otherwise water renders untextured)",
    "Убрать Itera материал и восстановить оригинальные":
        "Remove the Itera material and restore the originals",
    "Убрать LightMap UV2 из материалов выделенных объектов":
        "Remove LightMap UV2 from selected objects' materials",
    "Удалить DFF/TXD/COL выделенных моделей из IMG архива":
        "Remove selected models' DFF / TXD / COL from the IMG archive",
    "Удалить color attribute по имени на всех выделенных объектах":
        "Delete a color attribute by name across all selected objects",
    "Удалить активный ключевой кадр": "Delete the active keyframe",
    "Удалить выбранный пресет": "Delete the selected preset",
    "Удалить текущий эффект из effects.fxp (с автобэкапом)":
        "Delete the current effect from effects.fxp (with auto-backup)",
    "Упаковать тайлы радара в TXD архивы (1 тайл = 1 TXD)":
        "Pack radar tiles into TXD archives (1 tile = 1 TXD)",
    "Экспорт IFP — анимации GTA SA": "Export IFP — GTA SA animations",
    "Экспорт flight.dat — маршруты полётов": "Export flight.dat — flight paths",
    "Экспорт nodes.dat — группировка по имени файла или авто-разбиение по зонам":
        "Export nodes.dat — group by filename or auto-split by zones",
    "Экспорт paths.ipl — пути для gta.dat":
        "Export paths.ipl — paths listed in gta.dat",
    "Экспорт tracks.dat — железнодорожные пути":
        "Export tracks.dat — railway paths",
    "Экспорт water.dat": "Export water.dat",
    "Экспорт секций IPL из коллекций IPL_* в файл":
        "Export IPL sections from IPL_* collections into a file",
    "Экспортировать один общий TXD для нескольких DFF моделей":
        "Export a single shared TXD for multiple DFF models",

    # ── Particle property descriptions (effects.fxp) ────────────────────
    "CULLDIST — расстояние отсечения эффекта в игре":
        "CULLDIST — effect cull distance in game",
    "EMANGLE MAX — максимальный угол конуса эмиссии":
        "EMANGLE MAX — maximum emission cone angle",
    "EMANGLE MIN — минимальный угол конуса эмиссии":
        "EMANGLE MIN — minimum emission cone angle",
    "EMLIFE BIAS — случайный разброс длительности жизни":
        "EMLIFE BIAS — random lifetime scatter",
    "EMPOS X/Y/Z — смещение точки спавна":
        "EMPOS X/Y/Z — spawn point offset",
    "EMROTATION ANGLEMAX — макс начальный поворот спрайта":
        "EMROTATION ANGLEMAX — max initial sprite rotation",
    "EMROTATION ANGLEMIN — мин начальный поворот спрайта":
        "EMROTATION ANGLEMIN — min initial sprite rotation",
    "EMSIZE половина размера бокса эмиссии (centered)":
        "EMSIZE — half-extent of the emission box (centered)",
    "EMSPEED BIAS — случайный разброс начальной скорости":
        "EMSPEED BIAS — random initial-speed scatter",
    "FORCE X/Y/Z — постоянное ускорение (например -9.8 по Z = гравитация)":
        "FORCE X/Y/Z — constant acceleration (e.g. -9.8 on Z = gravity)",
    "FRICTION — сопротивление воздуха": "FRICTION — air resistance",
    "GROUNDCOLLIDE BOUNCE — сила отскока при ударе о землю":
        "GROUNDCOLLIDE BOUNCE — bounce factor on ground hit",
    "GROUNDCOLLIDE SPEEDMULT — потеря скорости при ударе":
        "GROUNDCOLLIDE SPEEDMULT — speed loss on impact",
    "JITTER JITTERFACTOR — резкий случайный дёрг":
        "JITTER JITTERFACTOR — sharp random jitter",
    "LENGTH — длительность цикла системы в секундах":
        "LENGTH — system cycle duration in seconds",
    "NOISE — сглаженное случайное движение":
        "NOISE — smoothed random motion",
    "PLAYMODE — режим проигрывания (0-3)": "PLAYMODE — play mode (0-3)",
    "ROTSPEED MAXCW — макс скорость вращения спрайта":
        "ROTSPEED MAXCW — max sprite rotation speed",
    "ROTSPEED MINCW — мин скорость вращения спрайта":
        "ROTSPEED MINCW — min sprite rotation speed",
    "WIND WINDFACTOR — восприимчивость к ветру игры":
        "WIND WINDFACTOR — game wind responsiveness",

    # ── Status / report / label strings ─────────────────────────────────
    "Автоматически ставить material alpha = 254 при наличии vertex alpha < 255.\nНужно для стандартных прозрачных мешей (стёкла, дым). Выключи если материал должен остаться opaque":
        "Automatically set material alpha = 254 when any vertex alpha < 255.\nNeeded for standard transparent meshes (glass, smoke). Disable if the material must stay opaque",
    "Восстановлено:": "Restored:",
    "Выберите папку для экспорта": "Pick an output folder",
    "Выделите объекты с нодами": "Select objects that carry nodes",
    "Извлечение ресурсов...": "Extracting resources...",
    "Импорт .glb...": "Importing .glb...",
    "Импорт .glb:": "Import .glb:",
    "Импорт карты...": "Importing map...",
    "Импорт карты:": "Import map:",
    "Источник:": "Source:",
    "Материалов:": "Materials:",
    "Не найден 3D Viewport": "No 3D Viewport found",
    "Не найдено моделей для экспорта": "No models to export",
    "Нет меш объектов для экспорта": "No mesh objects to export",
    "Нет файлов для импорта": "No files to import",
    "Нечего экспортировать": "Nothing to export",
    "Node group не найден:": "Node group not found:",
    "Открыть/Закрыть UV Editor": "Open / Close UV Editor",
    "Отменено": "Cancelled",
    "Ошибка загрузки node group:": "Failed to load node group:",
    "Писать IPL в бинарном формате (только inst+cars)":
        "Write IPL in binary format (inst + cars only)",
    "Писать nodes*.dat в расширенном FLA4 формате (spawn/speed/lanes per-node)":
        "Write nodes*.dat in extended FLA4 format (per-node spawn / speed / lanes)",
    "Пометить геометрию как разрушаемую (пишет чанк 0x253F2FD в DFF)":
        "Mark geometry as breakable (writes chunk 0x253F2FD into the DFF)",
    "Помечает меш как объёмный луч света для плагина SA_Light.asi.\nУстанавливает material color = (254,254,254,254) — этот маркер плагин ищет во время рендера.\n\nТРЕБУЕТ SA_Light.asi в корне GTA SA. Без плагина меш будет рендериться как обычный полупрозрачный объект с жёстким срезом alpha.\n\nДля использования:\n1. Собери меш-конус/куб формой луча\n2. Покрась vertex colors как хочешь (любые значения alpha)\n3. Включи этот флаг + Set Material Alpha выключи\n4. Экспорт → плагин автоматически включит плавный alpha blend на этом меше":
        "Mark the mesh as a volumetric light beam for the SA_Light.asi plugin.\nSets material color = (254, 254, 254, 254) — the plugin looks for this marker at render time.\n\nREQUIRES SA_Light.asi in the GTA SA root. Without the plugin the mesh renders as an ordinary semi-transparent object with hard alpha cutoff.\n\nHow to use:\n1. Build a cone / box mesh shaped like the beam\n2. Paint vertex colors however you want (any alpha values)\n3. Enable this flag + disable Set Material Alpha\n4. Export — the plugin switches this mesh to smooth alpha blending automatically",
    "Превью COL Light включено": "COL Light preview enabled",
    "Превью COL Light выключено": "COL Light preview disabled",
    "Привязано вершин:": "Snapped vertices:",
    "Применить SA Vehicle defaults": "Apply SA Vehicle defaults",
    "Пропущено (разные пути):": "Skipped (different paths):",
    "Сборка карты...": "Building map...",
    "Сборка карты:": "Building map:",
    "Сила, нужная чтобы сломать объект (умолчание 1.0)":
        "Force required to break the object (default 1.0)",
    "Слот цвета машины:": "Vehicle color slot:",
    "Слот цвета машины: движок SA подставит цвет из carcols.dat. Меняет базовый RGB материала на магическую метку.":
        "Vehicle color slot: the SA engine substitutes the color from carcols.dat. Replaces the material's base RGB with the magic marker.",
    "Сшито вершин:": "Stitched vertices:",
    "Текстур:": "Textures:",
    "Формат:": "Format:",
    "пропущено": "skipped",

    # ── IDE flag descriptions (wrapped with T() after fix) ──────────────
    "Дорога (1)": "Road (1)",
    "Прозрачный, рисовать последним (4)": "Transparent, draw last (4)",
    "Аддитивный блендинг (8)": "Additive blending (8)",
    "Не писать в Z-буфер (64)": "Don't write Z-buffer (64)",
    "Не получать тени (128)": "Don't receive shadows (128)",
    "Стекло разбиваемое (512)": "Breakable glass (512)",
    "Стекло с трещинами (1024)": "Cracked glass (1024)",
    "Дверь гаража (2048)": "Garage door (2048)",
    "Разрушаемый (4096)": "Breakable (4096)",
    "Дерево, качается на ветру (8192)": "Tree, sways in wind (8192)",
    "Пальма, качается на ветру (16384)": "Palm, sways in wind (16384)",
    "Нет коллизии с летающим (32768)": "No collision with flying (32768)",
    "Граффити тег (1048576)": "Graffiti tag (1048576)",
    "Рисовать обе стороны (2097152)": "Draw both sides (2097152)",
    "Разрушаемая статуя (4194304)": "Breakable statue (4194304)",

    # ── Vehicle color slot labels / enums ───────────────────────────────
    "Обычный материал, не связан с carcols": "Plain material, unrelated to carcols",
    "Основной цвет (первый в carcols.dat)": "Primary color (first in carcols.dat)",
    "Второй цвет": "Secondary color",
    "Третий цвет (некоторые машины)": "Third color (some vehicles)",
    "Четвёртый цвет": "Fourth color",
    "Левая фара": "Left headlight",
    "Правая фара": "Right headlight",
    "Левый задний фонарь": "Left tail light",
    "Правый задний фонарь": "Right tail light",

    # ── Misc property descriptions & confirmations ──────────────────────
    "Я понимаю что это перезапишет effects.fxp":
        "I understand this will overwrite effects.fxp",
    "<Game Root не задан>": "<Game Root not set>",
    "<effects.fxp не найден>": "<effects.fxp not found>",
    "<нет эффектов>": "<no effects>",

    # ── Report messages (FXP editor, misc) ──────────────────────────────
    "Имя пустое": "Name is empty",
    "Подтверждение не получено": "Confirmation not given",
    "Имя эффекта пустое": "Effect name is empty",
    "Эффект не выбран": "No effect selected",
    "У эффекта один эмиттер": "Effect has a single emitter",
    "Нет изменений — файл не тронут": "No changes — file left untouched",

    # ── IFP batch / Bitmaps / Map Export / Vehicle Scale tooltips ───────
    "Применять только анимации, имя которых начинается с этого префикса (регистронезависимо)":
        "Only apply animations whose name starts with this prefix (case-insensitive)",
    "Уложить клипы на один NLA-трек с зазором":
        "Lay clips onto one NLA track with a gap between them",
    "Создать Actions, без NLA": "Create Actions only, no NLA",
    "Создать подпапку на каждый txd_name (читается с mesh-объектов)":
        "Create a subfolder per txd_name (read from mesh objects)",
    "Первый ID для DFF у которых inu.model_id == 0":
        "Starting ID for DFFs whose inu.model_id == 0",
    "Множитель равномерного масштаба — применяется к позициям и вершинам":
        "Uniform scale factor — applied to positions and vertices",
    "Двигать только дамми-Empty, меши не трогать":
        "Move dummy Empties only, leave meshes untouched",

    # ── Imported-class docstrings (tools/* and ops/*) ───────────────────
    "Конвертировать vertex colors в COL Day/Night Light (разбиение материалов по яркости)":
        "Convert vertex colors to COL Day / Night Light (split materials by brightness)",
    "Удалить COL light материалы, созданные Bake COL Light":
        "Delete COL light materials created by Bake COL Light",
    "Проверить все материалы и показать текстуры, файлы которых не найдены":
        "Scan every material and list textures whose files are missing",
    "Рекурсивно искать в выбранной папке и подставлять image.filepath для найденных по имени недостающих текстур":
        "Recursively scan the chosen folder and reassign image.filepath for missing textures found by name",
    "Скопировать все используемые материалами текстуры сцены в выбранную папку":
        "Copy every texture used by scene materials into the chosen folder",
    "Хэшировать все файлы текстур и показать группы одинаковых файлов":
        "Hash every texture file and group identical files together",
    "Импорт текстового файла Steve's COL Editor (.cst)":
        "Import a Steve's COL Editor text file (.cst)",
    "Экспорт выделения в текстовый файл Steve's COL Editor (.cst)":
        "Export the selection to a Steve's COL Editor text file (.cst)",
    "Пропорционально масштабировать всю иерархию машины (Empty-корень + меши + дамми), сохраняя структуру. Применяет масштаб к данным меша чтобы DFF-экспорт остался чистым":
        "Uniformly scale the whole vehicle hierarchy (Empty root + meshes + dummies) while preserving structure. Applies the scale to mesh data so DFF export stays clean",

    # ── COL library mode ────────────────────────────────────────────────
    "Library (несколько коллизий)": "Library (multiple collisions)",
    "Сгруппировать выделение по базовому имени (house1_COL + house1_SHA → одна запись 'house1') и записать все группы в один .col файл подряд. Так vanilla SA хранит <district>.col и vehicles.col":
        "Group the selection by base name (house1_COL + house1_SHA → one record 'house1') and write every group into a single .col file back-to-back. This is how vanilla SA stores <district>.col and vehicles.col",
    "COL Library": "COL Library",
    "Писать все коллизии в один .col файл (multi-entry library). Каждая запись в файле — отдельная коллизия со своим model_id, сопоставляется с DFF по ID":
        "Write every collision into a single .col file (multi-entry library). Each record has its own model_id and links to a DFF by matching ID",
    "Имя library .col": "Library .col name",
    "Имя общего .col файла без расширения (например 'district' → district.col)":
        "Name of the combined .col file without extension (e.g. 'district' → district.col)",
    "Писать все коллизии в один <district>.col файл (multi-entry library). Каждая запись в файле — отдельная коллизия со своим model_id, сопоставляется с DFF по ID":
        "Write every collision into a single <district>.col file (multi-entry library). Each record has its own model_id and links to a DFF by matching ID",

    # ── Batch set distance ──────────────────────────────────────────────
    "Задать Draw Distance и/или LOD Distance всем выделенным MESH-объектам.\n\n    По умолчанию поля заполняются значениями активного объекта — можно\n    изменить и применить к выделению одним действием. Галочки слева\n    выбирают какие именно поля переписывать (удобно менять только одно)":
        "Set Draw Distance and/or LOD Distance on every selected MESH object.\n\nFields are prefilled from the active object — tweak and apply to the entire selection in one action. The left-hand checkboxes pick which fields to overwrite (handy for changing only one)",
    "Применить Draw Dist": "Apply Draw Dist",
    "Применить LOD Dist": "Apply LOD Dist",
    "Задать IDE-свойства (дистанции, Model ID, TXD, Interior, флаги,\nCOL Library) всем выделенным MESH-объектам.\n\nПо умолчанию поля заполняются значениями активного объекта — можно\nизменить и применить к выделению одним действием. Галочки слева\nвыбирают какие именно поля переписывать (удобно менять только одно)":
        "Set IDE properties (distances, Model ID, TXD, Interior, flags, COL Library) on every selected MESH object.\n\nFields are prefilled from the active object — tweak and apply to the entire selection in one action. The left-hand checkboxes pick which fields to overwrite (handy for changing only one)",
    "Задать IDE-свойства (дистанции, Model ID, TXD, Interior, флаги,\n    COL Library) всем выделенным MESH-объектам.\n\n    По умолчанию поля заполняются значениями активного объекта — можно\n    изменить и применить к выделению одним действием. Галочки слева\n    выбирают какие именно поля переписывать (удобно менять только одно)":
        "Set IDE properties (distances, Model ID, TXD, Interior, flags, COL Library) on every selected MESH object.\n\nFields are prefilled from the active object — tweak and apply to the entire selection in one action. The left-hand checkboxes pick which fields to overwrite (handy for changing only one)",
    "Применить Model ID": "Apply Model ID",
    "По порядку (+1)": "Sequential (+1)",
    "Первому объекту — указанный ID, каждому следующему +1 (объекты идут по имени). Снято — один и тот же ID всем":
        "First object gets the given ID, each next one +1 (objects sorted by name). Unchecked — the same ID for all",
    "Применить TXD": "Apply TXD",
    "Применить Interior": "Apply Interior",
    "Применить IDE Flags": "Apply IDE Flags",
    "Применить COL Library": "Apply COL Library",
    "объектов будет изменено": "objects will be modified",
    "Включите хотя бы одну галочку": "Enable at least one checkbox",
    "Изменено:": "Modified:",
    "Применить к выделенным": "Apply to selected",
    "Применить настройки": "Apply settings",
    "Убрать из модели": "Remove from model",
    "Настройки — в свойствах пустышки": "Settings — in the empty's properties",
    "Связи (пунктир)": "Relationship lines",
    "Путь IDE — не .ide файл, проверь бокс IDE": "IDE path is not a .ide file — check the IDE box",
    "Путь IPL — не .ipl файл, проверь бокс IPL": "IPL path is not a .ipl file — check the IPL box",
    "Синхронизация с файлами": "Sync with files",
    "Обновление сцены из файлов, отвязка, проверка": "Refresh scene from files, unlink, verify",
    "Дополнительно (IPL)": "Advanced (IPL)",
    "Секции IPL (cull/пути/гаражи) и замена Empty-заглушек": "IPL sections (cull/paths/garages) and replacing Empty placeholders",
    "Обновить": "Refresh",
    "Отвязать": "Unlink",
    "Проверить": "Verify",
    "Секции IPL (cull, пути, гаражи…):": "IPL sections (cull, paths, garages…):",
    "Заменить Empty на модели": "Replace Empty with models",
    "Присвоить выделенным:": "Assign to selected:",
    "Очистить выделенные": "Clear selected",
    "База ID и сервис": "ID database & service",
    "Управление пресетом ID: sync, из игры, GC, лимит FLA": "Manage the ID preset: sync, from-game, GC, FLA limit",

    # ── Export-to-IMG TXD plan dialog ───────────────────────────────────
    "Экспортировать DFF + TXD + COL прямо в .img архив.\n\n    Перед записью открывается диалог со списком моделей и их TXD именами —\n    можно переключить режим на один общий TXD, отключить отдельные модели,\n    или отредактировать имя архива для каждой (модели с одинаковым TXD\n    именем попадут в один .txd с объединёнными текстурами)":
        "Export DFF + TXD + COL directly into an .img archive.\n\nBefore writing a dialog opens with the list of models and their TXD names — switch to a single shared TXD, disable individual models, or edit the archive name per model (models with the same TXD name merge into one .txd)",
    "Общий TXD": "Shared TXD",
    "Пакует все текстуры в один .txd. Выключено — один .txd на каждую уникальную строку txd_name из списка ниже":
        "Pack every texture into a single .txd. When off, each unique txd_name from the list below gets its own .txd",
    "Имя общего TXD": "Shared TXD name",
    "Имя .txd файла без расширения": "Name of the .txd file without extension",
    "Имя TXD архива для этой модели. Модели с одинаковым именем попадут в один .txd (textures merged)":
        "TXD archive name for this model. Models sharing a name merge into one .txd (textures combined)",
    "Включить модель в экспорт": "Include this model in the export",
    "IMG:": "IMG:",
    "Моделей:": "Models:",
    "TXD имя на модель:": "TXD name per model:",
    "Общий TXD включён — список игнорируется":
        "Shared TXD enabled — the list is ignored",

    # Bitmaps Manager panel
    # VC Layer System
    "Слои Vertex Color": "Vertex Color Layers",
    "Слои Vertex Color (BETA)": "Vertex Color Layers (BETA)",
    "База (прилайт):": "Base (prelight):",
    "Нет атрибутов прилайта": "No prelight attributes",
    "Слои Day": "Day Layers",
    "Слои Night": "Night Layers",
    "Стек пуст — жми +": "Stack empty — click +",
    "Имя слоя": "Layer name",
    "Видимое имя слоя. Изменение переименует атрибут на меше": "Visible layer name. Editing renames the underlying mesh attribute",
    "Куда композится": "Compose target",
    "Day / Night — в какой стек этот слой вкладывается при flatten": "Day / Night — which stack this layer composes into on flatten",
    "Прозрачность": "Opacity",
    "Какая часть слоя смешивается с тем что под ним": "How much of the layer blends over what's beneath",
    "Режим": "Mode",
    "Как этот слой смешивается со стеком ниже": "How this layer blends with the stack below",
    "Виден": "Visible",
    "Выключенный слой исключается из flatten (alpha → 0)": "Hidden layer is excluded from flatten (alpha → 0)",
    "Заблокирован": "Locked",
    "Запрещает рисование на слое. Слайдеры остаются доступны": "Disables painting on the layer. Sliders remain editable",
    "Выделен": "Selected",
    "Включить в групповое редактирование (multi-edit slider'ы)": "Include in multi-edit slider operations",
    "Яркость до": "Brightness pre",
    "Яркость после": "Brightness post",
    "Контраст до": "Contrast pre",
    "Контраст после": "Contrast post",
    "Сдвиг яркости пикселей этого слоя ДО блендинга": "Brightness offset applied to this layer's pixels BEFORE blending",
    "Контраст пикселей этого слоя ДО блендинга": "Contrast applied to this layer's pixels BEFORE blending",
    "Лимит {n} слоёв для стека {scope} достигнут": "Limit of {n} layers for {scope} stack reached",
    "Слой с именем {} уже есть": "A layer named {} already exists",
    "Атрибут не найден": "Attribute not found",
    "Не VCL-атрибут": "Not a VCL attribute",
    "Это уже VCL-слой": "Already a VCL layer",
    "Атрибут «{}» уже есть — переименуйте слой перед promote": "Attribute «{}» already exists — rename the layer before promoting",
    "Атрибут «{}» уже есть": "Attribute «{}» already exists",
    "Стек": "Stack",
    "Редактируем Day-стек": "Editing Day stack",
    "Редактируем Night-стек": "Editing Night stack",
    "Multi-edit": "Multi-edit",
    "Как групповые слайдеры применяются к выделенным слоям": "How group sliders are applied to selected layers",
    "Absolute": "Absolute",
    "Relative": "Relative",
    "Все выделенные получают одинаковое значение": "All selected get the same value",
    "Все выделенные сдвигаются на одну дельту от текущего": "All selected shift by the same delta from current",
    "Выделенные слои ({}):": "Selected layers ({}):",
    "(групповые слайдеры — Фаза 2)": "(group sliders — Phase 2)",
    "Рисовать": "Paint",
    "→ База": "→ Base",
    "Live preview": "Live preview",
    "Дополнительные атрибуты:": "Additional attributes:",
    "Авто-композиция стека при изменении любого слайдера или мазке кистью": "Auto-recompose stack on any slider change or brush stroke",
    "Композит пуст — добавь хотя бы один слой": "Composite is empty — add at least one layer",
    "Атрибут «{}» не существует": "Attribute «{}» does not exist",
    "Live Preview выключен — нечего обновлять": "Live Preview is off — nothing to refresh",
    "Day/Night показывают композит — рисуй на слое": "Day/Night show the composite — paint on a layer",
    "BETA": "BETA",
    "IMG: нет результатов экспорта": "IMG: no export results",
    "Файл .img занят — закрой игру перед экспортом: {0}": "The .img file is locked — close the game before exporting: {0}",
    "⚠ .col-файлов за экспорт: {0} — движок грузит ≤255 всего. Объедини коллизии в один library .col.": "⚠ .col files this export: {0} — the engine loads ≤255 total. Merge collisions into one library .col.",
    "⚠ COL-моделей: {0} — лимит движка 10150 (CColModel).": "⚠ COL models: {0} — engine limit is 10150 (CColModel).",
    "Будут перекрашены": "Will be recoloured",
    "Перекрасить выделенные…": "Recolor Selected…",
    "Цвет": "Color",
    "Нет выделенных слоёв": "No selected layers",

    "Менеджер текстур": "Bitmaps Manager",
    "Сканировать": "Scan",
    "Пропущено": "Missing",
    "Найти в папке…": "Resolve From Folder…",
    "Скопировать в папку…": "Copy Used To Folder…",
    "Найти дубликаты": "Find Duplicates",
    "Найти неиспользуемые": "Find Unused",
    "Удалить неиспользуемые…": "Remove Unused…",
    "Неисп.": "Unused",
    "Будет удалено:": "Will be removed:",
    "Текстуры": "Textures",
    "Материалы": "Materials",
    "пропущены": "skipped",
    "Также удалить неиспользуемые материалы": "Also remove unused materials",
    "Удалить также материалы, не назначенные ни на один меш-слот": "Also remove materials not assigned to any mesh slot",
    "use_fake_user-помеченные пропускаются": "use_fake_user-flagged are skipped",

    # Unified Export (Stage 3)
    "Экспорт:": "Export:",
    "Экспорт...": "Exporting...",
    "INU Export...": "INU Export...",
    "INU Export:": "INU Export:",
    "В папку": "To Folder",
    "В IMG": "To IMG",

    # ID Manager buttons (Stage 4 / 2-column layout)
    "Назначить": "Assign",
    "Создать": "Create",
    "Sync": "Sync",
    "С ID...": "From ID...",
    "Очистить выд.": "Clear Selected",
    "Расширить FLA": "Extend FLA",
    "Из игры": "From Game",
    "Открыть файл": "Open File",

    # Import Map (Build/Load .glb pair)
    "Собрать .glb": "Build .glb",
    "Импорт .glb": "Import .glb",
    "Auto-discover": "Auto-discover",

    # Object INU Tools panel (Stage 6)
    "По имени:": "By name:",
    "Экспортировать как": "Export as",
    "Маркер в имени важнее — экспорт как": "Name marker wins — exported as",

    # IMG export progress
    "Экспорт в IMG:": "Export to IMG:",
    "Экспорт в IMG...": "Exporting to IMG...",

    # Build Map .glb — no auto-import
    "Собрано:": "Built:",
    "инстансов": "instances",

    # Direct map import
    "Import Map (прямой)": "Import Map (direct)",

    # Profiler
    "Профайлер": "Profiler",
    "Замерять время операций и записывать отчёт в .inu_cache/_profile.log. Включай только для отладки — добавляет небольшой overhead на каждый шаг":
        "Time each stage and write a report to .inu_cache/_profile.log. Enable only for debugging — adds a small overhead per step",
    "Профайлер (debug timings)": "Profiler (debug timings)",

    # ── 1.6.6 — Map Export split modes ──────────────────────────────────
    "Разбиение": "Split",
    "Как разбить выделение на отдельные district'ы при экспорте":
        "How to split the selection into separate districts during export",
    "Без разбиения": "No split",
    "Один общий district, все DFF в корне target_dir. base_name используется для имён IDE/IPL/COL/TXD":
        "One shared district, all DFFs in the target directory root. base_name is used for IDE/IPL/COL/TXD filenames",
    "XY-сетка": "XY grid",
    "Биннить DFF по XY-координате origin'а на ячейки cell_size метров. Каждая непустая ячейка получает подпапку <base>_x<cx>_y<cy> со своими IDE/IPL/COL/TXD":
        "Bin DFFs by their XY origin into cell_size-meter cells. Each non-empty cell gets a <base>_x<cx>_y<cy> subdirectory with its own IDE/IPL/COL/TXD",
    "По коллекциям": "By collection",
    "Биннить DFF по имени верхней (top-level) коллекции, в которой объект лежит. Имя коллекции становится именем district'а — идеально для round-trip с Group-by-IPL импортом (vegasn_stream0 в Blender → vegasn_stream0.ipl на выходе)":
        "Bin DFFs by the name of the top-level collection they live in. The collection name becomes the district name — ideal for round-trip with Group-by-IPL import (vegasn_stream0 in Blender → vegasn_stream0.ipl on output)",
    "Размер ячейки (м)": "Cell size (m)",
    "Сторона квадратной ячейки в метрах для разбиения по XY-сетке. 256 м соответствует ванильному радиусу стриминга. Уменьшай для более мелких чанков, увеличивай если районов получается слишком много":
        "Side of the square cell in meters for XY-grid splitting. 256 m matches the vanilla streaming radius. Decrease for finer chunks, increase if you end up with too many districts",

    # ── 1.6.6 — Vehicle damage variants ─────────────────────────────────
    "Damage variants": "Damage variants",
    "Добавить _dam вариант": "Add _dam variant",
    "Состояние повреждений": "Damage state",
    "Состояние": "State",
    "Damaged": "Damaged",
    "Оба": "Both",
    "Показать целые меши, скрыть _dam": "Show OK meshes, hide _dam",
    "Показать повреждённые _dam меши, скрыть _ok": "Show damaged _dam meshes, hide _ok",
    "Показать оба варианта одновременно": "Show both variants simultaneously",
    "Проверить _ok/_dam пары": "Check _ok/_dam pairs",
    "Создать _dam": "Create _dam",
    "Dam": "Dam",
    "Проверить пары": "Check pairs",
    "Показать:": "Show:",
    "Создан": "Created",
    "Пар": "Pairs",
    "одиночные _ok": "lonely _ok",
    "одиночные _dam": "lonely _dam",
    "детали в системной консоли": "details in system console",

    # ── 1.6.6 — Map import: group by IPL ────────────────────────────────
    "Группировать по IPL": "Group by IPL",
    "Создавать отдельную коллекцию на каждый IPL-файл (Map_LAn, Map_LAs, Map_SF…) вместо одиночных Map_DFF_Far/Mid/Near. Удобно для скрытия районов целиком и для совместного редактирования карты. LOD-меши идут в коллекцию своего IPL вместе с обычными мешами":
        "Create a separate collection per IPL file (Map_LAn, Map_LAs, Map_SF…) instead of the unified Map_DFF_Far/Mid/Near buckets. Handy for hiding whole districts and for co-op map editing. LOD meshes go into their IPL's collection alongside regular meshes",

    # ── 1.6.6 — Map Export modal progress ───────────────────────────────
    "Map Export: подготовка...": "Map Export: preparing...",
    "Ошибка экспорта": "Export error",

    # ── 1.6.6 — Vehicle panel ───────────────────────────────────────────
    "Машины": "Vehicles",
    "Целевые коллекции": "Target collections",
    "Целевые коллекции:": "Target collections:",
    "Какие top-level коллекции экспортировать. Авто-инициализация по выделению в outliner; если не угадало — отметь галочками вручную. Имеет смысл вместе с режимом «По коллекциям»":
        "Which top-level collections to export. Auto-initialised from the outliner selection; if it didn't catch them, tick the boxes manually. Most useful with «By collection» split mode",
    "(пусто = выделение из outliner на момент нажатия)":
        "(empty = outliner selection captured when button was pressed)",
    "Export Map": "Export Map",

    # ── 1.6.6 — LOD round-trip + COL library property ──────────────────
    "COL Library": "COL Library",
    "Имя .col-библиотеки в которой хранится коллизия модели. Заполняется автоматически при Map Import (= имя исходного .col файла). При Map Export DFF группируются в одну .col-библиотеку по совпадающему col_name. Пусто → fallback на txd_name, затем на имя модели":
        "Name of the .col library this model's collision belongs to. Auto-populated on Map Import (= source .col filename). On Map Export, DFFs sharing a col_name are merged into one .col library. Empty → falls back to txd_name, then to the model's own name",
    "LOD partner": "LOD partner",
    "LOD-модель этой DFF — заполняется автоматически при Map Import из IPL lod_index. При Map Export пересчитывается в lod_index = позицию LOD-инстанса в выходном IPL. Пусто = модель не имеет LOD":
        "LOD model paired with this DFF — auto-populated on Map Import from the source IPL's lod_index. On Map Export it is converted back into a lod_index = position of the LOD instance in the output IPL. Empty = no LOD partner",

    # ── 1.7.0 — IK Rig, Animated Map Object, Frame Hierarchy, Paintjob,
    #          Profile system, 2DFX UX, Texture Manager dropdowns ──
    # IK Rig
    "Add IK Rig": "Add IK Rig",
    "Bake & Clear IK": "Bake & Clear IK",
    "IK Rig": "IK Rig",
    "Ground plane создан": "Ground plane created",
    "Цвет IK-контроллов": "IK control colour",
    "Форма IK-эмпти": "IK empty shape",
    "Какой примитив рисовать на IK-target и pole": "Which primitive to draw at IK target and pole",
    "Множитель размера всех IK-контролов ": "Size multiplier for all IK controls ",
    "Смещение куба руки/ноги": "Hand/foot cube offset",
    "Пол": "Floor",
    "Коллизия": "Collision",
    "Показывать кубы запястий и ступней ": "Show wrist and ankle cubes ",
    "Показывать кубы-маркеры на локтях и ": "Show elbow/knee marker cubes on ",
    "Показывать кубы головы, верхнего торса ": "Show head and upper-torso cubes ",
    "Показывать корневой куб (мастер-контроль ": "Show root cube (master control ",
    "Руки/ноги": "Hands/feet",
    "Локти/колени": "Elbows/knees",
    "Голова/торс": "Head/torso",
    "Голова/торс/плечи": "Head/torso/shoulders",
    "Корень": "Root",
    "Настройки пола, коллизии, цвета IK, плюс ": "Floor, collision and IK colour settings, plus ",
    "Дополнительно": "Advanced",
    "Дополнить": "Append",

    # Animated Map Object
    "Animated Map Object": "Animated Map Object",
    "Animated Map Object — мельницы, краны, флюгеры": "Animated Map Object — windmills, cranes, weather vanes",
    "Animated object готов к экспорту": "Animated object ready for export",
    "Animated rig готов": "Animated rig ready",
    "Setup rig": "Setup rig",
    "Validate": "Validate",
    "DFF+IFP+IDE": "DFF+IFP+IDE",
    "Дописать IDE entry": "Append IDE entry",
    "Добавить anim-запись в IDE-файл, заданный в Scene → INU Tools → IDE Path": "Add an anim entry to the IDE file set in Scene → INU Tools → IDE Path",
    "IDE path не задан — anim-запись пропущена": "IDE path is empty — anim entry skipped",
    "Имя файлов без расширения (например 'mill')": "File name without extension (e.g. 'mill')",
    "Куда положить .dff и .ifp": "Where to put .dff and .ifp",
    "Имя action": "Action name",
    "Имя IFP": "IFP name",
    "IFP файл": "IFP file",
    "Формат IFP": "IFP format",
    "Режим IFP": "IFP mode",
    "Перезаписать файл — старые анимации удаляются": "Overwrite file — existing animations are wiped",
    "Подгрузить существующий, добавить новые анимации, ": "Append new animations to the existing file, ",
    "Подгрузить существующий, заменить ТОЛЬКО анимации ": "Load existing, replace ONLY the animations ",
    "Новый": "New",
    "перезаписываю": "overwriting",
    "пропущено (уже есть)": "skipped (already present)",
    "анимаций": "animations",
    "Имя кости": "Bone name",
    "Все вершины меша получат weight=1.0 на эту кость": "All mesh vertices get weight=1.0 on this bone",
    "Ось": "Axis",
    "Ось вращения": "Rotation axis",
    "Оборотов за цикл": "Turns per cycle",
    "Длительность (кадров)": "Duration (frames)",
    "В обратную сторону": "Reverse direction",
    "Auto": "Auto",
    "Вручную": "Manual",
    "Manual режим — keyframes управляются вручную": "Manual mode — keyframes are managed by hand",
    "Переключение в Auto перезапишет твои ключи": "Switching to Auto will overwrite your keyframes",
    "Цикл точно зацикливается (целое число оборотов)": "Loop is exactly cyclic (integer turns count)",
    "об/сек при FPS": "rev/s at FPS",
    "оборотов/сек при FPS": "turns/s at FPS",
    "Что экспортировать:": "What to export:",
    "Объекты": "Objects",
    "Персонажи": "Characters",
    "Раздел панели Анимации": "Animations panel tab",
    "Выдели MESH и нажми Setup rig": "Select a MESH and press Setup rig",
    "Выделите MESH": "Select a MESH",
    "Выделите MESH или ARMATURE": "Select a MESH or ARMATURE",
    "Активный объект — не MESH и не ARMATURE": "Active object is not MESH or ARMATURE",
    "На MESH нет Armature modifier": "MESH has no Armature modifier",
    "Armature modifier указывает на другой скелет": "Armature modifier points to a different skeleton",
    "В скелете 0 костей": "Skeleton has 0 bones",
    "Не нашли пару MESH+ARMATURE — запустите Validate": "MESH+ARMATURE pair not found — run Validate",
    "Кости без vertex group:": "Bones without vertex group:",
    "Не найдена кость": "Bone not found",
    "Не найдены кости: ": "Bones not found: ",
    "К armature не привязан Action": "No Action linked to armature",
    "Нет Action на armature — IFP будет пустой": "No Action on armature — IFP will be empty",
    "Нет Armature — animated object без скелета не работает": "No Armature — animated object can't work without a skeleton",
    "Нет MESH": "No MESH",
    "В Action меньше 2 keyframe — анимации нет": "Action has fewer than 2 keyframes — no animation",
    "В action нет ключей — IFP не записан": "Action has no keyframes — IFP wasn't written",

    # Frame Hierarchy editor
    "Иерархия фреймов": "Frame hierarchy",
    "Rename": "Rename",
    "Set Parent": "Set Parent",
    "Unparent": "Unparent",
    "Клик — выделить · стрелка ⤴ — сделать родителем выделенного":
        "Click = select · arrow ⤴ = make parent of the selected frame",
    "Клик — выделить · ⤴ — родитель выделенного · ⛓ — снять родителя · F2 — переименовать":
        "Click = select · ⤴ = parent of selected · ⛓ = unparent · F2 = rename",
    "Снять родителя — сделать": "Unparent — make",
    "корневым": "a root",
    "выделенный фрейм": "the selected frame",
    "Сделать": "Make",
    "родителем выделенного фрейма": "the parent of the selected frame",
    "корень": "root",
    "Нельзя назначить объект родителем самого себя":
        "Can't parent an object to itself",
    "Циклическая иерархия недопустима": "Circular hierarchy is not allowed",
    "Validate Vehicle": "Validate Vehicle",
    "Validate Ped": "Validate Ped",
    "Зеркало L↔R": "Mirror L↔R",
    "Новое имя фрейма (точное соответствие требуется для машин и педов)": "New frame name (exact match required for vehicles and peds)",
    "сняли parent с": "unparented",
    "зеркально создано": "mirrored",
    "иерархия OK": "hierarchy OK",
    "parent": "parent",

    # Paintjob
    "Paintjob (Pay'n'Spray):": "Paintjob (Pay'n'Spray):",
    "Раскраска 1": "Paint 1",
    "Раскраска 2": "Paint 2",
    "Все paintjob материалы OK": "All paintjob materials OK",
    "Paintjob проблем": "Paintjob issues",
    "Paintjob'ов в сцене нет": "No paintjobs in the scene",
    "заполнен только Paintjob 1 — нужны оба": "only Paintjob 1 is set — both are required",
    "заполнен только Paintjob 2 — нужны оба": "only Paintjob 2 is set — both are required",
    "Нужны обе альтернативы (1 и 2)": "Both alternatives (1 and 2) are required",

    # Profile system
    "Профиль": "Profile",
    "Настройки": "Settings",
    "Раскройте нужный инструмент:": "Expand the tool you need:",

    # Prelight panel polish
    "Скопировать:": "Copy:",

    # Adaptive map auto-split (1.7.0)
    "Адаптивная сетка": "Adaptive grid",
    "Quadtree-разбиение по плотности: ячейка делится 2×2 пока в ней больше max_per_cell DFF. Плотные районы получают мелкие ячейки, разреженные остаются одной большой. Гарантирует число DFF на ячейку вместо равномерного пространственного разбиения. Имена подпапок: <base>_q<path>, где path — путь по квадрантам (0=SW, 1=SE, 2=NW, 3=NE)":
        "Density-driven quadtree subdivision: a cell splits 2×2 whenever it holds more than max_per_cell DFFs. Dense regions get small cells, sparse regions stay as one big cell. Guarantees per-cell DFF count instead of uniform spatial sub-division. Subdirectory naming: <base>_q<path>, where path is the quadrant path (0=SW, 1=SE, 2=NW, 3=NE)",
    "Макс. DFF на ячейку": "Max DFFs per cell",
    "Целевой потолок DFF в одной адаптивной ячейке. Когда число превышено — ячейка делится на 4. Меньше = больше мелких ячеек (тоньше streaming, но больше IPL-файлов). Больше = крупные ячейки. Vanilla SA streaming-радиус хорошо работает с ~150-300 DFF на IPL":
        "Target ceiling for DFFs in one adaptive cell. When exceeded the cell is split into 4. Lower = more small cells (finer streaming but more IPL files). Higher = bigger cells. Vanilla SA streaming radius works well with ~150-300 DFFs per IPL",
    "Мин. размер ячейки (м)": "Min cell size (m)",
    "Минимальная сторона ячейки для адаптивной сетки — нижняя граница рекурсии. Защищает от бесконечного деления когда много DFF разделяют одну XY-точку (вертикально стопкой, как небоскрёбы). При достижении этого предела ячейка остаётся, даже если в ней больше max_per_cell":
        "Minimum cell side length for the adaptive grid — recursion floor. Protects against infinite splitting when many DFFs share one XY point (stacked vertical like skyscrapers). On reaching this floor the cell is kept even if it still holds more than max_per_cell",

    # 2DFX panel — collapsible sections, semantic flag groups
    "Свойства света": "Light properties",
    "Поведение": "Behaviour",
    "Тень": "Shadow",
    "Флаги": "Flags",
    "Создать эффект": "Create effect",
    "Light — уличные фонари, неон, corona\nParticle — дым, огонь, частицы\nPed Attractor — точки притяжения NPC (банкомат, скамейка)\nSun Glare — блик солнца на поверхности":
        "Light — street lights, neon, corona\nParticle — smoke, fire, particles\nPed Attractor — NPC attractor points (ATM, bench)\nSun Glare — sun glare on surfaces",
    "Видимость:": "Visibility:",
    "Эффекты короны:": "Corona effects:",
    "Мерцание:": "Blinking:",
    "Доп.:": "Misc.:",
    "Множитель": "Multiplier",
    "Дистанция": "Distance",

    # Particle effect properties
    "Angle min": "Angle min",
    "Angle max": "Angle max",
    "Bounce": "Bounce",
    "Box": "Box",
    "Cull dist": "Cull dist",
    "Force": "Force",
    "Friction": "Friction",
    "Jitter": "Jitter",
    "Length": "Length",
    "Life bias": "Life bias",
    "Mid time": "Mid time",
    "Middle": "Middle",
    "Noise": "Noise",
    "Offset": "Offset",
    "Play mode": "Play mode",
    "Preview": "Preview",
    "Rate": "Rate",
    "Rot min": "Rot min",
    "Rot max": "Rot max",
    "RotSpd min": "RotSpd min",
    "RotSpd max": "RotSpd max",
    "Speed bias": "Speed bias",
    "SpeedMult": "SpeedMult",
    "Wind": "Wind",
    "Draw distance": "Draw distance",

    # DFF Flags / pipeline tooltips
    "Day": "Day",
    "Night": "Night",
    "Pipeline здания с day/night vertex colors (RSPIPE_PC_CustomBuildingDN). Движок плавно смешивает дневной и ночной слои vertex colors по игровому времени. Требует ДВА Color Attribute слоя (Day + Night) на меше. Mesh-флаги Day/Night здесь не нужны — переход делает pipeline через VC":
        "Building day/night vertex-colour pipeline (RSPIPE_PC_CustomBuildingDN). The engine smoothly blends a day and a night vertex-colour layer by in-game time. Requires TWO Color Attribute layers (Day + Night) on the mesh. Mesh Day/Night flags are NOT needed here — the pipeline does the transition via VC",

    # Auto-TXD picker help text
    "Как ищется TXD:": "How TXD is matched:",
    "1. <имя_dff>.txd в той же папке": "1. <dff_name>.txd in the same folder",
    "2. .txd с покрытием ≥50% текстур DFF": "2. .txd that covers ≥50% of DFF textures",
    "3. Единственный .txd в папке": "3. The only .txd in the folder",
    "   (выбирается с макс. покрытием,": "   (the one with the highest coverage,",
    "    меньший по размеру при равенстве)": "    smaller in size on a tie)",
    "Иначе — warning, ничего не грузится": "Otherwise a warning is shown and nothing is loaded",
    "TXD не найден": "TXD not found",
    "не найден ни по имени": "not found by name",
    "и нет .txd с подходящими текстурами": "and no .txd with matching textures",
    "ни по покрытию ≥50% текстур в": "nor by ≥50% texture coverage in",
    "доп. папка": "extra folder",
    "Укажите существующую папку": "Enter an existing folder",

    # IDE / Map workflow
    "Model ID": "Model ID",
    "Model ID = 0 — IDE entry пропущена": "Model ID = 0 — IDE entry skipped",
    "Model ID = 0 — задай в Object Properties → ": "Model ID = 0 — set it in Object Properties → ",
    "Имя TXD для IDE entry (обычно совпадает с base_name)": "TXD name for the IDE entry (usually matches base_name)",
    "Базовое имя": "Base name",
    "Базовое имя для общего TXD (без .txd)": "Base name for the shared TXD (without .txd)",
    "Базовое имя не может быть пустым": "Base name can't be empty",
    "Имя не может быть пустым": "Name can't be empty",
    "Имя": "Name",
    "Сначала сохраните .blend": "Save the .blend first",
    "Кеш пуст — будут расставлены только Empty по ": "Cache is empty — only Empty placeholders will be spawned at ",
    "Кеш пуст — карта без моделей": "Cache is empty — map without models",
    "Не найден файл: ": "File not found: ",
    "Не удалось записать отчёт:": "Failed to write report:",
    "Ничего не найдено": "Nothing found",
    # COL surface picker
    "Избранное": "Favorites",
    "В избранное": "Add to favorites",
    "Убрать из избранного": "Remove from favorites",
    "Только выделенное": "Selected only",
    "Используются:": "In use:",
    "Свободные ID:": "Free IDs:",

    # Texture Manager dropdowns
    "Светофор": "Traffic light",

    # Misc tooltips/help
    "TXD": "TXD",
    "TXD не будет загружаться автоматически": "TXD won't be loaded automatically",
    "(см. System Console)": "(see System Console)",
    "см. System Console": "see System Console",
    "...": "...",
    "Action Editor / Pose Mode": "Action Editor / Pose Mode",
    "Обновить совпадения": "Refresh matches",
    "Создать ID": "Create ID",
    "Связи: ON": "Links: ON",
    "Связи: OFF": "Links: OFF",
    "All → Папка": "All → Folder",
    "All → IMG": "All → IMG",
    "RW-эффекты материала: env map, bump, specular, reflection, dual texture, UV anim":
        "RW material effects: env map, bump, specular, reflection, dual texture, UV anim",
    "Пресеты материала и сводка активных эффектов": "Material presets and active-effect summary",
    "IFP импорт/экспорт, применение анимации к скелету, IK Rig": "IFP import/export, applying animation to a skeleton, IK Rig",
    "Показать сервисные кнопки": "Show service buttons",
    "Ошибок": "Errors",
    "Предупреждений": "Warnings",
    "предупреждений": "warnings",
    "моделей": "models",
    "текстур": "textures",
    "OFF (по умолчанию): каждая DFF получает свой отдельный <model>.col файл — соответствует ванильному SA где у большинства моделей коллизии в собственных файлах.\nON: все коллизии группируются в .col-библиотеки по inu.col_name (vegasN.col, LAs.col, …). Полезно когда есть осознанная shared collision на много моделей":
        "OFF (default): each DFF gets its own <model>.col file — matches vanilla SA where most models keep collision in standalone files.\nON: collisions are grouped into .col libraries by inu.col_name (vegasN.col, LAs.col, …). Useful when shared collision across many models is intentional",
    "Помечает меш как объёмный луч света для плагина SA_Light.asi.\nУстанавливает material color = (254,254,254,254) — этот маркер плагин ищет во время рендера.\n\nТРЕБУЕТ SA_Light.asi в корне GTA SA. Без плагина меш будет рендериться как обычный полупрозрачный объект с жёстким срезом alpha.\n\nДля использования:\n1. Собери меш-конус/куб формой луча\n2. Покрась vertex colors как хочешь (любые значения alpha)\n3. Включи этот флаг + Set Material Alpha выключи\n4. Экспорт → плагин автоматически включит плавный alpha blend на этом меше":
        "Marks the mesh as a volumetric light beam for the SA_Light.asi plugin.\nSets material color = (254,254,254,254) — the marker the plugin scans for at render time.\n\nREQUIRES SA_Light.asi in the GTA SA root. Without the plugin the mesh renders as a regular semi-transparent object with hard alpha cutoff.\n\nUsage:\n1. Build a cone/cube mesh shaped like the beam\n2. Paint vertex colors as you wish (any alpha values)\n3. Enable this flag + disable Set Material Alpha\n4. Export → the plugin automatically applies smooth alpha blend on this mesh",
    "Автоматически ставить material alpha = 254 при наличии vertex alpha < 255.\nНужно для стандартных прозрачных мешей (стёкла, дым). Выключи если материал должен остаться opaque":
        "Automatically sets material alpha = 254 when any vertex alpha < 255.\nUseful for standard transparent meshes (glass, smoke). Disable if the material must stay opaque",
    "Day — дневные вертексные цвета\nNight — ночные вертексные цвета\nDay/Night — создать оба атрибута\n+/- — добавить или удалить атрибут\nSave Materials — сохранить материалы (для Itera Tools)\nRestore — восстановить сохранённые материалы":
        "Day — daytime vertex colours\nNight — nighttime vertex colours\nDay/Night — create both attributes\n+/- — add or remove an attribute\nSave Materials — save materials (for Itera Tools)\nRestore — restore saved materials",
    "Гамма-коррекция vertex colors\n1.0 — без изменений\n< 1.0 — светлее (тени)\n> 1.0 — темнее (тени)":
        "Gamma correction for vertex colors\n1.0 — unchanged\n< 1.0 — brighter (shadows)\n> 1.0 — darker (shadows)",
    "Контраст vertex colors\n1.0 — без изменений\n< 1.0 — меньше контраст\n> 1.0 — больше контраст":
        "Contrast of vertex colors\n1.0 — unchanged\n< 1.0 — less contrast\n> 1.0 — more contrast",
    "Сглаживание vertex colors между соседними вершинами\nIterations — количество проходов\nFactor — сила сглаживания (0-1)":
        "Vertex-color smoothing between adjacent vertices\nIterations — number of passes\nFactor — smoothing strength (0-1)",
    "Яркость vertex colors\n0.0 — без изменений\n> 0 — светлее\n< 0 — темнее":
        "Vertex-color brightness\n0.0 — unchanged\n> 0 — brighter\n< 0 — darker",
    "V — смещение яркости vertex colors\nПоложительное значение — светлее\nОтрицательное — темнее":
        "V — vertex-color brightness offset\nPositive — brighter\nNegative — darker",
    "Тени — включить расчёт теней при запекании\nЗапечь — быстрое запекание без теней\nС тенями — запекание с raycast тенями (медленнее, но точнее)":
        "Shadows — enable shadow calculation during baking\nBake — fast baking without shadows\nWith Shadows — raycast-shadow baking (slower but more accurate)",
    "Диапазон дневного освещения для COL материалов\nMin/Max — значения от 0 до 15\nЯркость vertex colors конвертируется в этот диапазон":
        "Daytime light range for COL materials\nMin/Max — values from 0 to 15\nVertex-color brightness is mapped into this range",
    "Диапазон ночного освещения для COL материалов\nMin/Max — значения от 0 до 15\nИспользует Night color attribute если есть":
        "Nighttime light range for COL materials\nMin/Max — values from 0 to 15\nUses the Night color attribute if present",
    "COL Surface Type — тип физической поверхности и Day/Night Light":
        "COL Surface Type — physical surface type and Day/Night Light",

    # Validate Scene + COL Import + Onboarding strings (added 2026-05-02)
    "Action не найден": "Action not found",
    "COL Import отменён": "COL Import cancelled",
    "COL Import: подготовка...": "COL Import: preparing...",
    "Fastman92 Limit Adjuster: 12-я колонка `realInterior` в IPL inst. Обычная SA читает только 11 колонок — это поле игнорируется без FLA. Пусто (0) = не использовать. Включить запись 12-й колонки можно в Map Export → FLA Extended IPL":
        "Fastman92 Limit Adjuster: 12th `realInterior` column in IPL inst. Vanilla SA reads only 11 columns — this field is ignored without FLA. Empty (0) = not used. Enable 12th column writing in Map Export → FLA Extended IPL",
    "Rebuild Archive в IMG-туле — иначе игра подтянет старую запись":
        "Rebuild Archive in IMG tool — otherwise game keeps the old entry",
    "Имя Action содержит спецсимволы — IDE entry может не сработать":
        "Action name contains special characters — IDE entry may not work",
    "Материал без носителя": "Material without owner",
    "Материал не найден": "Material not found",
    "Не выбран ни один .col файл": "No .col file selected",
    "Не удалось удалить": "Failed to delete",
    "Нормализовано ключей": "Keyframes normalised",
    "Нормализовать": "Normalise",
    "Объект вне View Layer": "Object outside View Layer",
    "Объект не найден": "Object not found",
    "Открыть полный changelog на GitHub": "Open full changelog on GitHub",
    "Ошибка импорта COL": "COL import error",
    "Перейти": "Go to",
    "Проверить сцену": "Validate scene",
    "Проверка перед экспортом": "Pre-export check",
    "Русский": "Russian",
    "Снять": "Disable",
    "Сцена готова к экспорту — проблем не найдено":
        "Scene ready to export — no problems found",
    "Удалена Action": "Action deleted",
    "Что делать если такой .ifp уже существует на диске":
        "What to do if such .ifp already exists on disk",
    "Экспорт пройдёт OK, замечаний": "Export will proceed OK, notes",
    "включи коллекцию в outliner": "enable collection in outliner",
    "выбери armature и повтори": "pick armature and retry",
    "нет основной текстуры — paintjob не к чему привязать":
        "no base texture — paintjob has nothing to bind to",
    "объект(ов)": "object(s)",
    "с ошибкой": "with error",
    "файлов": "files",
    "из": "of",
    "Docs": "Docs",
    "Issues": "Issues",
    "Только SAMP": "SAMP only",
    "Блокировать Map Export при SAMP-предупреждениях":
        "Block Map Export on SAMP warnings",
    "FLA: real_interior": "FLA: real_interior",
    "Записать 12-ю колонку realInterior в каждой inst-строке IPL. Fastman92 Limit Adjuster читает её, vanilla SA молча игнорирует. Значение берётся из obj.inu.real_interior":
        "Write the 12th realInterior column in each IPL inst row. Fastman92 Limit Adjuster reads it, vanilla SA silently ignores. Value is taken from obj.inu.real_interior",

    # Profile editor popup hints
    "Взято:": "Picked:",
    "клик на другую = переместить сюда": "click another = move here",
    "Клик на название = взять, потом клик на другую = поставить":
        "Click the name = pick up, then click another = drop here",

    # Validate Scene category labels
    "Кватернионы": "Quaternions",
    "Modulate Color": "Modulate Color",
    "Пары _ok / _dam": "_ok / _dam pairs",
    "Сирые LOD / COL": "Orphan LOD / COL",
    "Непривязанный 2DFX": "Unattached 2DFX",
    "Дубликаты model_id": "Duplicate model_id",
    "Пустые меши": "Empty meshes",
    "Большие меши": "Large meshes",
    "Материал без текстуры": "Material without texture",
    "Суффиксы / префиксы": "Suffixes / prefixes",
    "Scale объектов": "Object scale",

    # Validate Scene — static issue messages
    "заполнен только Paintjob 2 — нужны оба":
        "only Paintjob 2 filled — both required",
    "заполнен только Paintjob 1 — нужны оба":
        "only Paintjob 1 filled — both required",
    "Night ломает UV-анимацию в retail SA":
        "Night vcols break UV animation in retail SA",
    "Сними Night (ночные vcol) на UV-аним модели":
        "Disable Night (night vcols) on UV-anim models",
    "Ночные vertex colors (Night) отключают UV-анимацию в retail SA — сними Night на этой модели":
        "Night vertex colors disable UV animation in retail SA — clear Night on this model",
    "Меш без текстур определён как COL — он не попадёт в DFF/IDE/IPL экспорт. Добавь текстуру или пометь тип COL явно":
        "Untextured mesh classified as COL — it will be skipped by DFF/IDE/IPL export. Add a texture or tag it COL explicitly",
    "Не-латинское имя": "Non-Latin name",
    "Инфо": "Info",
    "Висящая геометрия": "Loose geometry",
    "Висящая геометрия: вершин {v}, рёбер {e} — почисти меш («Проверка вершин» их выделит)":
        "Loose geometry: {v} verts, {e} edges — clean the mesh («Check vertices» selects them)",
    "COL — без Model ID (привязка к DFF по имени)": "COL — no Model ID (bound to its DFF by name)",
    "Меш без текстур (COL)": "Untextured mesh (COL)",
    "Имя содержит не-латинские символы (напр. кириллицу) — GTA SA не примет. Переименуй латиницей (a-z, 0-9, _)":
        "Name has non-Latin characters (e.g. Cyrillic) — GTA SA won't accept it. Rename using Latin (a-z, 0-9, _)",
    "Имя для IMG длиннее 23 символов — обрежется и не совпадёт с IDE/IPL: {0}. Укороти имя модели.":
        "IMG entry name longer than 23 characters — it will be truncated and won't match IDE/IPL: {0}. Shorten the model name.",
    "IPL: пропущены строки с model_id 0 (задай ID): ":
        "IPL: rows with model_id 0 skipped (assign an ID): ",
    "LOD без main DFF — engine не сможет переключиться между ближним и дальним LOD":
        "LOD without a main DFF — the engine can't switch between near/far LODs",
    "COL без main DFF — коллизия не привязана к модели":
        "COL without a main DFF — collision is not linked to a model",
    "меш с 0 вершин — экспортируется как пустой атомик":
        "mesh with 0 vertices — exports as an empty atomic",
    "материал без image texture — pipeline скорее всего ожидает базовую":
        "material without image texture — pipeline likely expects a base one",
    "флаг Light Beam ASI включён, но SA_Light.asi не найден в game root — плагин не активируется":
        "Light Beam ASI flag is set but SA_Light.asi not found in game root — plugin won't activate",
    "нет парного _dam": "no paired _dam",
    "нет парного _ok": "no paired _ok",

    # Validate Scene — interpolated message templates
    "{count} ненормированных ключей (экспорт чинит сам, но preview прыгает)":
        "{count} non-unit keyframes (export auto-normalises, but preview stutters)",
    "2DFX не привязан к MESH (parent: {parent}) — не попадёт в DFF":
        "2DFX not parented to a MESH (parent: {parent}) — won't go into the DFF",
    "model_id={mid} занят {count} разными моделями: {names}":
        "model_id={mid} is used by {count} different models: {names}",
    "{count} вершин — лимит атомика 65535, возможно стоит разрезать":
        "{count} vertices — atomic limit is 65535, consider splitting",
    "имя содержит '{combo}' — лишний суффикс рядом с {kind}":
        "name contains '{combo}' — extra suffix next to {kind}",
    "имя оканчивается на '{alt}', но настройка ожидает '{sfx}'":
        "name ends with '{alt}' but settings expect '{sfx}'",
    "отрицательный scale ({sx:.2f}, {sy:.2f}, {sz:.2f}) — нормали вывернутся, faces могут стать невидимы":
        "negative scale ({sx:.2f}, {sy:.2f}, {sz:.2f}) — normals flip, faces may become invisible",
    "non-uniform scale ({sx:.2f}, {sy:.2f}, {sz:.2f}) — перед экспортом сделай Ctrl+A → All Transforms":
        "non-uniform scale ({sx:.2f}, {sy:.2f}, {sz:.2f}) — Ctrl+A → All Transforms before export",

    # Validate Scene — fix button label + new fix operator strings
    "Исправить": "Fix",
    "Не нашёл несоответствия суффикса для этого объекта":
        "No suffix mismatch found for this object",

    # ── v1.9.0 ──────────────────────────────────────────────────────
    # File Scanner / Binary linter
    "Скан файлов": "File Scanner",
    "Сканировать": "Scan",
    "Что это значит:": "What it means:",
    "Открыть в Проводнике": "Reveal in Explorer",
    "Сохранить отчёт:": "Save report:",
    "Сохранить .txt": "Save .txt",
    "Список пуст — запустите скан": "List empty — run a scan",
    "Скан завершён": "Scan complete",
    "Скан завершён: проблем не найдено":
        "Scan complete: no issues found",
    "Включите хотя бы один тип файла (DFF/COL/TXD)":
        "Enable at least one file type (DFF/COL/TXD)",
    "Укажите существующую папку": "Pick an existing folder",
    "Нет результатов для сохранения — сначала запустите скан":
        "No results to save — run a scan first",
    "Сцена не сохранена — сохраните .blend или выберите другую папку для отчёта":
        "Scene not saved — save the .blend or choose another report folder",
    "Папка скана не задана — выберите .blend или свою папку":
        "Scan folder not set — choose .blend or a custom folder",
    "Своя папка для отчёта не задана или не существует":
        "Custom report folder not set or doesn't exist",
    "Неизвестный target для отчёта": "Unknown report target",
    "Нет выбранной строки": "No row selected",
    "Файл не найден:": "File not found:",
    "Отчёт сохранён:": "Report saved:",
    "Сцена не сохранена!": "Scene not saved!",
    "Сцена не сохранена": "Scene not saved",

    # Asset Library / Build Library
    "Собрать Asset Library": "Build Asset Library",
    "Извлечь ресурсы": "Extract resources",
    "Корневая папка GTA SA": "GTA SA root folder",
    "Регион": "Region",
    "Параметры": "Parameters",
    "Размер превью (px)": "Preview size (px)",
    "Перегенерировать превью": "Regenerate previews",
    "Без превьюшек (быстрее, но без миниатюр)":
        "Skip previews (faster, but no thumbnails)",
    "Пропускать готовые .blend": "Skip existing .blend files",
    "Сборка библиотеки...": "Building library...",
    "Сканирование кеша...": "Scanning cache...",
    "Чтение IDE файлов...": "Reading IDE files...",
    "Перегенерация превью...": "Regenerating previews...",
    "Финализация...": "Finalising...",
    "Инициализация...": "Initialising...",
    "Превью: готово": "Previews: done",
    "Готовность": "Readiness",
    "Готово": "Ready",
    "Старт": "Start",
    "Кеш найден": "Cache found",
    "Кеш пуст — Extract Resources": "Cache empty — run Extract Resources",
    "Game Root указан": "Game Root set",
    "Game Root не указан": "Game Root not set",
    "Output задан": "Output set",
    "Output не задан": "Output not set",
    ".blend сохранён": ".blend saved",
    "Имя уже занято": "Name already taken",
    "Укажите корневую папку GTA SA": "Pick the GTA SA root folder",
    "Как пользоваться": "How to use",
    "1. Сохрани .blend": "1. Save the .blend",
    "1. Извлечь ресурсы": "1. Extract resources",
    "2. Папка библиотеки": "2. Library folder",
    "2. Укажи Game Root и регион": "2. Set Game Root and region",
    "3. Извлеки ресурсы": "3. Extract resources",
    "4. Укажи папку Output": "4. Set the Output folder",
    "5. Жми «Собрать»": "5. Hit «Build»",
    "6. Edit > Preferences > File Paths >": "6. Edit > Preferences > File Paths >",
    "   Asset Libraries > Add → твой Output":
        "   Asset Libraries > Add → your Output",

    # Prelight: V-offset inline + scatter color sub-panel
    "Дальность": "Distance",
    "Цвет (из кисти)": "Color (from brush)",
    "Запечь с тенями": "Bake with shadows",
    "Сначала выберите пресет в списке": "Pick a preset from the list first",
    "без изменений": "no changes",

    # Misc UI / IK
    "OK": "OK",
    "Отменено": "Cancelled",
    "Root motion (walk/run)": "Root motion (walk/run)",
    "Настройка анимации": "Animation setup",
    "Исправить кватернионы (sign-flip)": "Fix quaternions (sign-flip)",
    "Отзеркалить анимацию": "Mirror animation",
    "Авто-доворот Root на 180°": "Auto-turn Root by 180°",
    "Довернуть Root на 180°": "Turn Root by 180°",
    "Ось доворота Root": "Root turn axis",
    "Пространство доворота Root": "Root turn space",
    "Локальное": "Local",
    "Глобальное": "Global",
    "Инверсия Root Location": "Root Location invert",
    "Не инвертировать": "Do not invert",
    "Ось зеркала": "Mirror axis",
    "Менять L/R кости": "Swap L/R bones",
    "Лево ↔ право (обычное зеркало)": "Left ↔ right (normal mirror)",
    "Вперёд ↔ назад": "Front ↔ back",
    "Верх ↔ низ": "Top ↔ bottom",
    "Нет ключей анимации": "No animation keyframes",
    "Анимация отзеркалена по оси": "Animation mirrored along axis",
    "обмен L/R только по оси": "L/R swap only on axis",
    "кадров": "frames",
    "кривых": "curves",
    "Не найдено кривых поворота костей": "No bone rotation curves found",
    "Поменять L/R кости": "Swap L/R bones",
    "Переставлено ключей L/R": "L/R keys swapped",
    "Не найдено парных L/R костей": "No paired L/R bones found",
    "Плоскость отражения анимации в armature-space: "
    "X — лево↔право (сагиттальная), Y — вперёд↔назад, "
    "Z — верх↔низ":
        "Reflection plane in armature space: X — left↔right (sagittal), "
        "Y — front↔back, Z — top↔bottom",
    "Обменивать данные парных костей 'L …'↔'R …' "
    "(настоящее зеркало гуманоида). Выключи для чистого "
    "геометрического флипа без обмена":
        "Swap paired 'L …'↔'R …' bone data (true humanoid mirror). "
        "Disable for a plain geometric flip without swapping",
    "Сгладить между выделенными ключами":
        "Smooth between selected anchor keys",
    "Сгладить ключей":
        "Smoothed keys",
    "Выдели минимум 2 ключа в Dope Sheet как опорные":
        "Select at least 2 keyframes in the Dope Sheet to use as anchors",
    "Размер тени / интенсивность света":
        "Shadow size / light intensity",
    "VC Layers System": "VC Layers System",
    "Выдели объект чтобы увидеть иерархию":
        "Select an object to see the hierarchy",
    # === Added 2026-05-18 (parity sync with spa.py + new NEW-only strings) ===

    # --- 44 keys imported from SA eng.py ---
    'Auto: ползунки сами пересчитывают keyframes цикла.\nManual: ползунки заморожены, ты сам ставишь keyframes в Action Editor / Pose Mode. Переключение Manual→Auto перезапишет твои ключи значениями ниже':
        'Auto: sliders auto-recompute cycle keyframes.\nManual: sliders are frozen — you set keyframes yourself in Action Editor / Pose Mode. Switching Manual→Auto will overwrite your keys with the values below',
    'ID модели для IDE — должен быть свободен в карте.\n0 = не задан (исправь в Object Properties → INU Tools → Model ID)':
        'Model ID for IDE — must be free on the map.\n0 = not set (fix in Object Properties → INU Tools → Model ID)',
    'Library Output не указан или не существует':
        'Library Output is not set or does not exist',
    'Model ID = 0 — задай в Object Properties → INU Tools → Model ID':
        'Model ID = 0 — set it in Object Properties → INU Tools → Model ID',
    'Scene → INU Tools → IDE Path не задан — anim-запись не будет дописана':
        'Scene → INU Tools → IDE Path is not set — anim entry will not be appended',
    'Автоматически ставить material.alpha = 254 при наличии\nvertex alpha < 255 хоть на одной вершине меша.\n\nВКЛЮЧАТЬ: для прозрачных мешей (стёкла, дым, листва)\nесли хочешь чтобы движок воспринял геометрию как\nalpha-blended объект и сортировал её правильно.\n\nВЫКЛЮЧАТЬ (по умолчанию): материал остаётся opaque,\nvertex alpha не задаёт прозрачность всего объекта.\nПолезно когда vertex alpha используется для других\nцелей (vcol fade, light beam masking)':
        'Automatically set material.alpha = 254 when at least one\nvertex of the mesh has vertex alpha < 255.\n\nENABLE: for transparent meshes (glass, smoke, foliage)\nif you want the engine to treat the geometry as an\nalpha-blended object and sort it correctly.\n\nDISABLE (default): material stays opaque,\nvertex alpha does not drive whole-object transparency.\nUseful when vertex alpha is used for other purposes\n(vcol fade, light beam masking)',
    "Альтернативная текстура для Pay'n'Spray paintjob 1.\nБудет упакована в TXD как <base>_paintjob1, где <base> — имя основной текстуры этого материала.":
        "Alternate texture for Pay'n'Spray paintjob 1.\nPacked into TXD as <base>_paintjob1, where <base> is the name of this material's main texture.",
    "Альтернативная текстура для Pay'n'Spray paintjob 2.\nБудет упакована в TXD как <base>_paintjob2.":
        "Alternate texture for Pay'n'Spray paintjob 2.\nPacked into TXD as <base>_paintjob2.",
    "Базовое имя для .ifp (без расширения). Пусто = взять из «Базовое имя». Можно ввести общее имя типа 'myhood_anims' чтобы складывать анимации мельницы, крана и флюгера в один файл":
        "Base name for .ifp (without extension). Empty = take from «Base name». You can enter a common name like 'myhood_anims' to pack windmill, crane and weathervane animations into a single file",
    'Библиотека собрана за':
        'Library built in',
    'Библиотека:':
        'Library:',
    'В кеше нет DFF файлов — запустите «Извлечь ресурсы»':
        'No DFF files in cache — run «Extract resources»',
    'Длина цикла в кадрах. Скорость = обороты_за_цикл × fps_сцены / длительность':
        'Cycle length in frames. Speed = rotations_per_cycle × scene_fps / duration',
    'Длина цикла в кадрах. Скорость вращения = оборотов_за_цикл / длительность × fps_сцены':
        'Cycle length in frames. Rotation speed = rotations_per_cycle / duration × scene_fps',
    'Имя Blender Action — попадёт в IFP как имя анимации. Игра ищет анимацию по этому имени из IDE anim entry':
        'Blender Action name — written into IFP as animation name. Game looks up the animation by this name from the IDE anim entry',
    'Имя кости которую крутит rig. Меняется только если ты переименовал кость вручную в Edit Mode скелета':
        'Name of the bone driven by the rig. Change only if you renamed the bone manually in skeleton Edit Mode',
    'Имя кости — попадёт в DFF Frame name и в IFP bone-track. Принято использовать что-то описательное: blades, propeller, gear...':
        'Bone name — written into DFF Frame name and IFP bone-track. Convention is something descriptive: blades, propeller, gear...',
    'Кеш пуст — будут расставлены только Empty по IPL без геометрии. Для полной карты сначала запустите «Извлечь ресурсы»':
        'Cache is empty — only Empties will be placed per IPL without geometry. For a full map, run «Extract resources» first',
    'Крутить против часовой стрелки (с точки зрения +оси). Удобно если меш вышел зеркальным или физика подразумевает вращение в другую сторону':
        'Rotate counter-clockwise (looking down the +axis). Useful if the mesh ended up mirrored or the physics implies the opposite rotation direction',
    "Не найден исполняемый файл Blender'а":
        'Blender executable not found',
    'Перевёрнуто ключей':
        'Keys flipped',
    'Перезаписан:':
        'Overwritten:',
    'Подгрузить существующий, добавить новые анимации, заменить с тем же именем':
        'Load existing, add new animations, replace those with the same name',
    'Подгрузить существующий, заменить ТОЛЬКО анимации с совпадающим именем, новые НЕ добавлять':
        'Load existing, replace ONLY animations with a matching name, do NOT add new ones',
    'Превью обновлены за':
        'Previews refreshed in',
    'Сборка библиотеки (headless)…':
        'Building library (headless)…',
    'Сборка завершена':
        'Build finished',
    'Сначала сохраните сцену (.blend) — кеш создаётся рядом с ней':
        'Save the scene (.blend) first — cache is created next to it',
    'Сначала сохраните сцену (.blend) — кеш создаётся рядом с ней. Без сохранения извлечение уйдёт во временную папку и пропадёт':
        'Save the scene (.blend) first — cache is created next to it. Without saving, extraction will go to a temp folder and be lost',
    'Собрать все текстуры из выделенных DFF в один общий TXD.\nАвто-включает «Только выделенное» и подставляет имя ниже.':
        'Collect all textures from selected DFFs into one shared TXD.\nAuto-enables «Selected only» and fills in the name below.',
    'Сохрани текущую сцену — оператор открывает .blend файлы библиотеки в этом окне Blender и потеряет несохранённые изменения':
        'Save the current scene — the operator opens library .blend files in this Blender window and will lose unsaved changes',
    'Удалить кеш после сборки':
        'Delete cache after build',
    'Укажите папку для библиотеки в INU настройках (Library Output Path)':
        'Set the library folder in INU settings (Library Output Path)',
    'Флаг rpGEOMETRYLIGHT — геометрия принимает\nдинамическое освещение от движка (sun + ambient).\n\nБез флага: меш рендерится как unlit, виден только\nvertex prelight × matCol. Используется для\nself-illuminated объектов (вывески, окна с\nзапечённым свечением)':
        'rpGEOMETRYLIGHT flag — geometry receives\ndynamic lighting from the engine (sun + ambient).\n\nWithout the flag: mesh is rendered as unlit, visible\nonly via vertex prelight × matCol. Used for\nself-illuminated objects (signs, windows with\nbaked glow)',
    'Флаг rpGEOMETRYMODULATEMATERIALCOLOR — vertex prelight\nумножается на material color и ambient_obj в runtime.\n\nВЫКЛЮЧИ если хочешь чтобы prelight использовался «как\nесть» без модуляции (нужно для запечённого ночного\nосвещения, эффектов flicker от prelight). Стандарт\nу ванильных зданий — включён':
        'rpGEOMETRYMODULATEMATERIALCOLOR flag — vertex prelight\nis multiplied by material color and ambient_obj at runtime.\n\nDISABLE if you want prelight used «as-is» without\nmodulation (needed for baked night lighting, flicker\neffects from prelight). Standard for vanilla buildings —\nenabled',
    'Целое число полных оборотов за анимацию. Игра проигрывает цикл повторно — модель возвращается в стартовую позицию точно (без визуального рывка на стыке)':
        'Integer number of full rotations per animation. Game replays the cycle — model returns to start position exactly (no visual jerk at the seam)',
    'Целое число полных оборотов за анимацию. Цикл проигрывается повторно — модель возвращается в стартовую позицию точно (без визуального рывка)':
        'Integer number of full rotations per animation. Cycle is replayed — model returns to start position exactly (no visual jerk)',
    "Экспорт chunk'а Bin Mesh PLG в DFF.\n\nСодержит индексы триангуляции в том виде в котором\nдвижок ожидает их у себя в RpAtomic. Без него:\n• MEd / DFF Viewer не показывает геометрию\n• некоторые версии движка не рендерят меш\n\nВыключать имеет смысл только при микро-оптимизации\nразмера DFF когда модель не идёт в игру":
        "Export the Bin Mesh PLG chunk into DFF.\n\nContains triangulation indices in the form the\nengine expects on RpAtomic. Without it:\n• MEd / DFF Viewer doesn't show the geometry\n• some engine versions won't render the mesh\n\nOnly worth disabling to micro-optimize DFF size when\nthe model isn't shipped in the game",
    "Экспорт второй UV-карты — используется для lightmap'ов\nи dual-pass материалов. Если меш без второй UV-карты,\nфлаг безопасно оставить включённым (DFF не получит\nлишний chunk)":
        "Export the second UV map — used for lightmaps\nand dual-pass materials. If the mesh has no second UV map,\nit's safe to keep this flag on (DFF won't get an\nextra chunk)",
    'Экспорт дневных vertex colors (атрибут «Day»).\nЭто ванильный prelight который игра умножает на\nambient_obj в runtime. Выключи только если хочешь\nDFF без vertex colors (редкий случай)':
        'Export day vertex colors (attribute «Day»).\nThis is the vanilla prelight that the game multiplies\nby ambient_obj at runtime. Disable only if you want\na DFF without vertex colors (rare case)',
    "Экспорт нормалей вершин в DFF.\n\nВКЛЮЧАТЬ: для скиннингованных объектов (peds, vehicles)\nи любых моделей у которых динамическое освещение должно\nкорректно реагировать на смену освещения сцены.\n\nВЫКЛЮЧАТЬ (по умолчанию для map-объектов): нормали\nудваивают размер vertex stream'а; статичные здания\nобычно полностью освещены через vertex prelight, и\nдвижок нормали не использует. Файл получается меньше":
        'Export vertex normals into DFF.\n\nENABLE: for skinned objects (peds, vehicles)\nand any model whose dynamic lighting must respond\ncorrectly to changes in scene lighting.\n\nDISABLE (default for map objects): normals double\nthe vertex stream size; static buildings are usually\nfully lit via vertex prelight and the engine ignores\nnormals. File ends up smaller',
    'Экспорт ночных vertex colors (атрибут «Night»,\nRpExtraVertColors chunk). Игра берёт их в ночное\nвремя через timecyc-blend. Если у меша нет «Night»\nслоя — chunk не пишется автоматически':
        'Export night vertex colors (attribute «Night»,\nRpExtraVertColors chunk). Game uses them at night\nvia timecyc-blend. If the mesh has no «Night» layer,\nthe chunk is not written automatically',
    'Экспорт первой UV-карты — основной набор текстурных\nкоординат. Должен быть включён почти всегда —\nвыключи только если меш специально без UV':
        'Export the first UV map — the main set of texture\ncoordinates. Should be on almost always —\ndisable only if the mesh is intentionally without UV',
    'изменено':
        'changed',

    # --- 84 keys new to NEW codebase (multi-game III/VC/SA, weight-merge, presets) ---
    "'Default' read-only — сохрани под другим именем (Save)":
        "'Default' is read-only — save under a different name (Save)",
    "'Default' зарезервирован — выбери другое имя":
        "'Default' is reserved — pick another name",
    "'Default' нельзя переименовать — это встроенный пресет":
        "Cannot rename 'Default' — it's a built-in preset",
    "'Default' нельзя удалить — это встроенный пресет":
        "Cannot delete 'Default' — it's a built-in preset",
    "Backup идентичен текущему mesh'у (Undo схлопнул). Тэг очищен.":
        'Backup is identical to current mesh (Undo collapsed it). Tag cleared.',
    "Backup идентичен текущему mesh'у. Тэг очищен.":
        'Backup is identical to current mesh. Tag cleared.',
    'Cross-ref с IDE (used by)':
        'Cross-ref with IDE (used by)',
    'IDE cross-ref активен':
        'IDE cross-ref active',
    'IDE файлы:':
        'IDE files:',
    'IPL файлы:':
        'IPL files:',
    'Merge откатан, веса восстановлены':
        'Merge rolled back, weights restored',
    'Merged для weight paint:':
        'Merged for weight paint:',
    'Weight Paint: швы':
        'Weight Paint: seams',
    "cluster'ов,":
        'clusters,',
    'Авто-определение':
        'Auto-detect',
    'Аддитивный блендинг (8) · III/VC/SA':
        'Additive blending (8) · III/VC/SA',
    'Анализ завершён: проблем не найдено':
        'Analysis complete: no issues found',
    'Анализ карты завершён':
        'Map analysis complete',
    'Анализ карты/файлов':
        'Map/file analysis',
    'Архив':
        'Archive',
    'Без затухания на дистанции (2) · III/VC':
        'No distance fade (2) · III/VC',
    'Веса применены к':
        'Weights applied to',
    'Выдели минимум 2 ключа .location в Dope Sheet как опорные':
        'Select at least 2 .location keys in the Dope Sheet as anchors',
    'Граффити тег (1048576) · SA only':
        'Graffiti tag (1048576) · SA only',
    'Дверь гаража (2048) · SA only':
        'Garage door (2048) · SA only',
    'Дерево, качается на ветру (8192) · SA only':
        'Tree, sways in wind (8192) · SA only',
    'Динамическое освещение вместо статического (32) · III/VC':
        'Dynamic lighting instead of static (32) · III/VC',
    'Дорога, wet reflections (1) · VC/SA':
        'Road, wet reflections (1) · VC/SA',
    'Игнорировать draw distance (256) · VC only — typical для LOD-моделей':
        'Ignore draw distance (256) · VC only — typical for LOD models',
    'Игра':
        'Game',
    'Игра-источник IDE flags (III/VC/SA). Используется при экспорте для перевода битов между играми':
        'Source game for IDE flags (III/VC/SA). Used at export to translate bits between games',
    'Игра-источник Surface ID (III/VC/SA). Использует core.surface_translate при экспорте в другую игру':
        'Source game for Surface ID (III/VC/SA). Uses core.surface_translate when exporting to another game',
    'Из какой игры импортируем COL. Auto — по magic header':
        'Which game to import COL from. Auto — by magic header',
    'Из какой игры импортируем IPL. Auto — по числу колонок в inst-секции':
        'Which game to import IPL from. Auto — by column count in inst section',
    'Из какой игры импортируем. Auto — определить по RW-версии файла':
        'Which game to import from. Auto — detect by file RW version',
    'Использует gta.dat':
        'Uses gta.dat',
    'Лампы удалены':
        'Lights removed',
    'Между объектами:':
        'Between objects:',
    'Найдено':
        'Found',
    'Не жми Ctrl+Z — Undo ломает backup-mesh!':
        "Don't press Ctrl+Z — Undo breaks the backup-mesh!",
    'Не найдено translation-каналов для смещения в мировом пространстве':
        'No translation channels found for world-space offset',
    'Не писать в Z-буфер (64) · III/VC/SA':
        'No write to Z-buffer (64) · III/VC/SA',
    'Не получать тени (128) · VC/SA':
        'Do not receive shadows (128) · VC/SA',
    'Неизвестный режим input':
        'Unknown input mode',
    'Неизвестный режим источника':
        'Unknown source mode',
    'Нет mesh-объектов для сброса':
        'No mesh objects to reset',
    'Нет коллизии с летающим (32768) · SA only':
        'No collision with flying (32768) · SA only',
    'Нет результатов для сохранения — сначала запустите анализ':
        'No results to save — run the analysis first',
    'Объединить для покраски':
        'Merge for painting',
    'Откатить':
        'Roll back',
    'Пальма, качается на ветру (16384) · SA only':
        'Palm, sways in wind (16384) · SA only',
    'Поддержка':
        'Support',
    'Подтянуть тени':
        'Pull up shadows',
    'Применить и вернуть швы':
        'Apply and restore seams',
    'Принудительно III':
        'Force III',
    'Принудительно SA':
        'Force SA',
    'Принудительно VC':
        'Force VC',
    'Проанализировать':
        'Analyze',
    'Проверять модели в IMG':
        'Check models in IMG',
    'Прозрачный, рисовать последним (4) · III/VC/SA':
        'Transparent, draw last (4) · III/VC/SA',
    'Прочитать RW версию и угадать игру':
        'Read RW version and guess game',
    'РЕЖИМ MERGE: не меняй геометрию!':
        "MERGE MODE: don't modify geometry!",
    'Разрушаемая статуя (4194304) · SA only':
        'Breakable statue (4194304) · SA only',
    'Разрушаемый ok/dam (4096) · SA only':
        'Breakable ok/dam (4096) · SA only',
    'Рассеять цвет:':
        'Scatter color:',
    'Рисовать обе стороны (2097152) · SA only':
        'Draw both sides (2097152) · SA only',
    'Свет (8 ламп)':
        'Light (8 lamps)',
    'Сглажено ключей':
        'Keys smoothed',
    'Слить co-located вершины для покраски:':
        'Merge co-located vertices for painting:',
    "Список IDE/IPL пуст — добавь файлы кнопкой '+'":
        "IDE/IPL list is empty — add files with the '+' button",
    "Список файлов пуст — добавь .img / .txd кнопкой '+'":
        "File list is empty — add .img / .txd with the '+' button",
    'Стекло разбиваемое (512) · VC/SA':
        'Breakable glass (512) · VC/SA',
    'Стекло с трещинами (1024) · VC/SA':
        'Cracked glass (1024) · VC/SA',
    'Сцена не сохранена — сохраните .blend, отчёт пишется рядом':
        'Scene not saved — save the .blend, report is written next to it',
    'Текстур найдено':
        'Textures found',
    'Текстуры (TXD)':
        'Textures (TXD)',
    'Туннель, видим только в cull-зоне (16) · III only':
        'Tunnel, visible only in cull zone (16) · III only',
    'Укажите gta.dat файл в Map Analyzer':
        'Specify gta.dat file in Map Analyzer',
    'Укажите существующий .dat файл':
        'Specify an existing .dat file',
    'Файлы (.img / .txd):':
        'Files (.img / .txd):',
    'вершин. Не меняй геометрию!':
        "vertices. Don't change the geometry!",
    'вершинам, split-геометрия восстановлена':
        'vertices, split geometry restored',
    'ламп':
        'lights',
    'сглажено ключей':
        'keys smoothed',

    # Operator bl_label / bl_description (raw — no T()) — found 2026-05-18
    "INU: Импорт": "INU: Import",
    "INU: Экспорт": "INU: Export",
    "INU: Материалы": "INU: Materials",
    "INU: Текстуры": "INU: Textures",
    "INU: Создать 2DFX": "INU: Create 2DFX",
    "INU: Сохранить пресет": "INU: Save Preset",
    "INU: Удалить пресет": "INU: Delete Preset",
    "INU: Генерировать радар": "INU: Generate Radar",
    "INU: Светофор": "INU: Traffic Light",
    "Инструменты": "Tools",
    "Проредить ключи": "Thin keyframes",
    # === Wrapped at 2026-05-18 (display strings via T()) ===
    ' ключей':
        'keys',
    ' ключей записано':
        'keys written',
    ' материал(ов)':
        'material(s)',
    ' моделей)':
        'models)',
    ' уже _dam — выбери _ok вариант':
        'already _dam — pick the _ok variant',
    ' уже есть в сцене — связана пара':
        'already in scene — pair linked',
    ' файлов (':
        'files (',
    "' не найден в effects.fxp":
        "' not found in effects.fxp",
    "' не найдена":
        "' not found",
    "' не найдена — нечего клонировать":
        "' not found — nothing to clone",
    "' нет эмиттеров":
        "' has no emitters",
    "' уже существует":
        "' already exists",
    "' уже существует (снимите галку 'Overwrite' нельзя, включите её)":
        "' already exists (you cannot uncheck 'Overwrite' — turn it on)",
    ', интерполяция применена к ':
        ', interpolation applied to ',
    'ALL удалить нельзя':
        'Cannot delete ALL',
    'Auto-decimate выполнен, интерполяция применена к ':
        'Auto-decimate done, interpolation applied to ',
    'Game Root не задан':
        'Game Root is not set',
    'Lightmap не найден в материалах':
        'Lightmap not found in materials',
    'Lightmap удалён из ':
        'Lightmap removed from ',
    'effects.fxp не найден: ':
        'effects.fxp not found: ',
    'Автобусный':
        'Bus',
    'Без светофора':
        'No traffic light',
    'Блик солнца':
        'Sun Glare',
    'Выделено: ...':
        'Selected: ...',
    'Генерировать радар':
        'Generate Radar',
    'Железнодорожный':
        'Railroad',
    "Имя 'ALL' зарезервировано":
        "The name 'ALL' is reserved",
    'Имя содержит недопустимые символы или слишком длинное':
        'Name contains invalid characters or is too long',
    'Интерполяция оставшихся ключей:':
        'Interpolation for remaining keys:',
    "Исходная система '":
        "Source system '",
    'Меню радар (3x3)':
        'Radar menu (3x3)',
    "Не нашёл F-curve'ы — выбери анимированный объект.":
        'No F-curves found — select an animated object.',
    'Не удалось загрузить ':
        'Failed to load ',
    'Не удалось создать бэкап: ':
        'Failed to create backup: ',
    'Неверный ключ кривой: ':
        'Invalid curve key: ',
    'Нет выделенных ключей. Выдели нужные ключи в Graph Editor.':
        'No selected keys. Select the keys you need in Graph Editor.',
    'Обычный':
        'Normal',
    'Ошибка записи профиля':
        'Profile write error',
    'Ошибка записи: ':
        'Write error: ',
    'Ошибка парсинга effects.fxp: ':
        'effects.fxp parse error: ',
    'Ошибка парсинга: ':
        'Parse error: ',
    'Ошибка применения правок: ':
        'Edit application error: ',
    'Ошибка сохранения':
        'Save error',
    'Ошибка удаления':
        'Delete error',
    'Полный меню':
        'Full Menu',
    'Полный радар':
        'Full Radar',
    'Применить':
        'Apply',
    'Проредить выделенные ключи':
        'Thin selected keys',
    'Свет':
        'Light',
    "Система '":
        "System '",
    'Создан эффект: ':
        'Effect created: ',
    'Создан: ':
        'Created: ',
    'Сохранить как…':
        'Save as…',
    "У системы '":
        "System '",
    'Удалено ключей: ':
        'Keys removed: ',
    'Удалено: ':
        'Removed: ',
    'Удалить':
        'Delete',
    'Удалён: ':
        'Deleted: ',
    'Указанные тайлы':
        'Specified tiles',
    'Частица':
        'Particle',
    "Эффект '":
        "Effect '",
    'имя обязательно':
        'name is required',
    'не удалось удалить':
        'failed to delete',
    'нет выбранного пресета':
        'no preset selected',
    'ошибка сохранения':
        'save error',
    'сохранён: ':
        'saved: ',
    'удалён: ':
        'deleted: ',

    # === Docstring / prop translations added 2026-05-18 ===
    'Создать рiг для animated map object (мельница, кран, флюгер):\n    Armature с одной костью + Action с цикличной Z-вращением.\n\n    Все вершины активного меша автоматически привязываются к\n    единственной кости (vertex group weight=1.0). Готово к экспорту в\n    DFF + IFP без ручной настройки скелета.':
        'Create a rig for animated map object (windmill, crane, weathervane):\n    Armature with one bone + Action with a cyclic Z rotation.\n\n    All vertices of the active mesh are auto-bound to the single bone (vertex group weight=1.0). Ready to export to DFF + IFP without manual skeleton setup.',
    'Проверить настройку animated map object перед экспортом:\n    есть ли armature, привязан ли меш, заданы ли веса, есть ли action,\n    цикличный ли он. Лог проблем в System Console.':
        'Validate animated map object setup before export: armature presence, mesh binding, weights, action presence and cyclicity. Issues are logged to the System Console.',
    'Экспортировать animated map object одним кликом: пишет\n    <base>.dff + <base>.ifp в выбранную папку. Опционально дописывает\n    или обновляет anim-запись в указанном IDE-файле.':
        'Export the animated map object in one click: writes <base>.dff + <base>.ifp into the chosen folder. Optionally appends or updates the anim entry in the specified IDE file.',
    "Собрать Blender Asset Library из извлечённых ресурсов.\n\n    Walks every IDE in gta.dat / default.dat, classifies every cached DFF\n    by category (Cars / Peds / Weapons / Map Objects per region / LOD /\n    Interiors), imports each into a Collection, marks as an asset, embeds\n    INU metadata (model_id, txd_name, draw_distance, ide_flags), and\n    optionally renders a thumbnail. Output is a folder with one .blend\n    per category plus blender_assets.cats.txt — point Blender's Asset\n    Library preferences at it and you're done.":
        "Build a Blender Asset Library from extracted resources.\n\n    Walks every IDE in gta.dat / default.dat, classifies every cached DFF\n    by category (Cars / Peds / Weapons / Map Objects per region / LOD /\n    Interiors), imports each into a Collection, marks as an asset, embeds\n    INU metadata (model_id, txd_name, draw_distance, ide_flags), and\n    optionally renders a thumbnail. Output is a folder with one .blend\n    per category plus blender_assets.cats.txt — point Blender's Asset\n    Library preferences at it and you're done.",
    "Перегенерировать превьюшки в существующей Asset Library.\n\n    Iterates every ``<output>/*.blend``, opens it in this Blender\n    instance, re-renders thumbnails for every asset-marked collection,\n    then saves the .blend back. The asset list / metadata / textures\n    are untouched — only the preview pixels are refreshed. Useful for\n    bumping ``preview_size`` from 128 to 256 (or vice-versa) without\n    waiting through a full DFF re-import.\n\n    Stays in-process (modal generator) — opens .blend files in the\n    current session, headless subprocess would lose that scene-state\n    integration with the asset browser. Speed-up isn't critical for\n    preview-only refresh anyway.":
        "Regenerate previews in an existing Asset Library.\n\n    Iterates every ``<output>/*.blend``, opens it in this Blender\n    instance, re-renders thumbnails for every asset-marked collection,\n    then saves the .blend back. The asset list / metadata / textures\n    are untouched — only the preview pixels are refreshed. Useful for\n    bumping ``preview_size`` from 128 to 256 (or vice-versa) without\n    waiting through a full DFF re-import.\n\n    Stays in-process (modal generator) — opens .blend files in the\n    current session, headless subprocess would lose that scene-state\n    integration with the asset browser. Speed-up isn't critical for\n    preview-only refresh anyway.",
    'Импорт COL коллизии GTA SA с прогресс-баром.\n    ESC прерывает импорт, уже созданные объекты остаются в сцене.':
        'Import a GTA SA collision COL with progress bar.\n    ESC interrupts the import — already-created objects stay in the scene.',
    'Импорт COL при перетаскивании во viewport (батч, прогресс + ESC).\n\n    Принимает несколько файлов сразу. Селекция игнорируется — COL\n    создаёт собственные mesh-объекты, не цепляется к существующим.':
        "Import COL on drag-and-drop into the viewport (batch, progress + ESC).\n\n    Accepts multiple files at once. Selection is ignored — COL\n    creates its own mesh objects, it doesn't attach to existing ones.",
    'Импорт DFF при перетаскивании во viewport.\n\n    Принимает несколько файлов сразу (батч), каждый импортируется\n    как отдельная модель. Та же логика автоматического подцепления\n    одноимённого .txd, что и в обычном импорте.':
        'Import DFF on drag-and-drop into the viewport.\n\n    Accepts multiple files at once (batch); each is imported as a separate model. Same auto-attach logic for the matching .txd as the regular import.',
    'Переключить один бит в 2dfx_flags1 / 2dfx_flags2 на активном объекте.':
        'Toggle one bit in 2dfx_flags1 / 2dfx_flags2 on the active object.',
    'Сканировать выбранную папку на crash-prone паттерны в DFF/COL/TXD':
        'Scan selected folder for crash-prone patterns in DFF/COL/TXD',
    'Сохранить результат скана в .txt':
        'Save scan result to .txt',
    'Открыть папку файла в Проводнике':
        "Open file's folder in Explorer",
    'Очистить список результатов':
        'Clear results list',
    'Сделать активным указанный фрейм (используется панелью при клике\n    на строку дерева).':
        'Make the specified frame active (used by the panel when clicking\n    on a tree row).',
    'Переименовать активный фрейм.':
        'Rename the active frame.',
    'Назначить parent: активный объект становится родителем для остальных\n    выделенных. Мировая позиция каждого ребёнка сохраняется, а\n    matrix_parent_inverse сбрасывается в identity (DFF requirement).':
        'Set parent: active object becomes the parent of the other selected ones. World position of every child is preserved, and matrix_parent_inverse is reset to identity (DFF requirement).',
    'Снять parent с выделенных объектов (parent → None). Мировая\n    позиция сохраняется.':
        'Clear parent on selected objects (parent → None). World position is preserved.',
    'Проверить иерархию активного объекта против vanilla SA шаблона.\n    Тип шаблона выбирается атрибутом ``template`` оператора.':
        "Validate the active object's hierarchy against the vanilla SA template.\n    Template type is selected by the operator's ``template`` attribute.",
    'Создать зеркальную копию выделенных фреймов: ``_lf`` → ``_rf``,\n    ``_lb`` → ``_rb`` (X отражается, остальные оси без изменений). Если\n    зеркальный близнец уже существует — оператор его не трогает.':
        'Create a mirrored copy of selected frames: ``_lf`` → ``_rf``,\n    ``_lb`` → ``_rb`` (X is mirrored, other axes unchanged). If the\n    mirrored twin already exists — operator leaves it alone.',
    'Прореживание выделенных ключей. Stride — оставить каждый N-ный\n    ключ. Auto — удалить ключи которые лежат на прямой между соседями\n    (избыточные).':
        'Thin out selected keyframes. Stride — keep every Nth key. Auto — remove keys lying on the straight line between neighbours (redundant).',
    'N-panel в Graph Editor с прореживанием ключей.':
        'N-panel in the Graph Editor for thinning keyframes.',
    'Диагностика round-trip для IFP — проверяет что read → write → read\n    не теряет анимации, не путает кости и не ломает квартернионы.\n\n    Выбранный файл не меняется: экспорт идёт во временный файл рядом,\n    результат сравнивается с оригиналом и удаляется. Отчёт показывает\n    счётчики и максимальные численные отклонения (dRot, dTrans, dTime)':
        "Round-trip diagnostics for IFP — checks that read → write → read doesn't lose animations, mix up bones or break quaternions.\n\n    The selected file is not modified: export goes to a temp file next to it, the result is compared with the original and deleted. Report shows counters and maximum numerical deltas (dRot, dTrans, dTime)",
    "Переключить живой preview IFP-анимации без коммита в Action.\n\n    Позволяет быстро пробежаться по 294 ванильным анимациям `ped.ifp`\n    простым переключением Action-dropdown'а без захламления Action\n    Editor'а. Handler frame_change_post напрямую пишет в pose bones\n    при скрабе Timeline. Повторный клик — выключает preview и\n    восстанавливает предыдущий Action арматуры":
        "Toggle live IFP animation preview without committing to Action.\n\n    Lets you quickly browse through 294 vanilla `ped.ifp` animations\n    by simply switching the Action dropdown, without cluttering the\n    Action Editor. The frame_change_post handler writes directly to\n    pose bones when scrubbing the Timeline. A repeated click — turns\n    off preview and restores the armature's previous Action",
    'Исправить sign-discontinuities кватернионов на диапазоне кадров.\n    Между двумя соседними ключами с dot < 0 кость крутится длинной\n    дорогой через 360°. Скрипт находит такие пары и инвертирует знак\n    кватерниона на втором ключе — q и -q описывают одинаковую ротацию,\n    но интерполяция между ними после флипа идёт коротким путём.\n\n    Идемпотентный — повторный прогон не ухудшит, иногда нужен 2-й\n    проход чтобы вылезли ранее скрытые разрывы.':
        "Fix quaternion sign-discontinuities over a frame range.\n    Between two adjacent keys with dot < 0 the bone takes the long path through 360°. The script finds such pairs and flips the sign of the second key — q and -q describe the same rotation, but interpolation after the flip takes the short path.\n\n    Idempotent — a repeat run won't make things worse; sometimes a 2nd pass is needed for earlier-hidden discontinuities to surface.",
    'Сгладить ключи между выделенными опорными.\n\n    Use-case: запечённая анимация с ключом на каждом кадре (например 700\n    ключей). Хочешь опустить кость на кадре 70 — двигаешь её там, потом\n    в Dope Sheet/Graph Editor выделяешь 3 ключа (50, 70, 90: первый,\n    редактированный, последний) и нажимаешь эту кнопку. Промежуточные\n    ключи (51-69 и 71-89) перезаписываются smooth-step интерполяцией\n    между соседними опорными — будто там никаких ключей и не было.\n\n    Режимы оси:\n    - ALL — обрабатывает ВСЕ F-curve (включая rotation, scale) в bone-\n      local координатах. Быстро.\n    - WORLD_X/Y/Z — обрабатывает только .location и считает в МИРОВЫХ\n      координатах. Учитывает поворот родительских костей и armature.\n      Медленнее (per-frame depsgraph eval), но даёт правильный «по Z\n      вниз» эффект независимо от ориентации кости.\n\n    Анкоры берутся из выделенных ключей, минимум 2.\n    Структура «ключ на каждом кадре» сохраняется (важно для round-trip\n    в IFP).':
        'Smooth keys between selected anchors.\n\n    Use-case: a baked animation with a key on every frame (e.g. 700\n    keys). You want to lower the bone at frame 70 — you move it there, then\n    in Dope Sheet/Graph Editor you select 3 keys (50, 70, 90: first,\n    edited, last) and press this button. Intermediate\n    keys (51-69 and 71-89) are overwritten with smooth-step interpolation\n    between the adjacent anchors — as if no keys had been there at all.\n\n    Axis modes:\n    - ALL — processes ALL F-curves (including rotation, scale) in bone-\n      local coordinates. Fast.\n    - WORLD_X/Y/Z — processes only .location and computes in WORLD\n      coordinates. Takes parent bone rotation and armature into account.\n      Slower (per-frame depsgraph eval), but gives the correct «down\n      along Z» effect regardless of bone orientation.\n\n    Anchors are taken from the selected keys, minimum 2.\n    The «key on every frame» structure is preserved (important for IFP\n    round-trip).',
    'Удалить активную Action арматуры из файла полностью.\n    В отличие от кнопки X в Action Editor (которая только отвязывает),\n    этот оператор стирает Action из bpy.data.actions — полезно чтобы\n    в IFP-экспорт не попадали забытые анимации.':
        "Delete the armature's active Action from the file entirely.\n    Unlike the X button in Action Editor (which only unlinks),\n    this operator wipes the Action from bpy.data.actions — useful so\n    forgotten animations don't end up in the IFP export.",
    'Накинуть bone-based IK на стандартные цепочки SA-педа.\n    Создаёт non-deform контрольные кости внутри армча: запястья,\n    ступни, голову и корень. На deform-кости — IK-constraint и\n    Copy Rotation/Location, target — соответствующая control-кость.\n    Контроллы окрашены зелёным (THEME09). Перед Export IFP — Bake\n    & Clear IK, которая всё снимет и удалит control-кости.':
        'Apply bone-based IK to the standard SA-ped chains.\n    Creates non-deform control bones inside the armature: wrists,\n    feet, head and root. Deform bones get IK-constraints and\n    Copy Rotation/Location targeting the matching control bone.\n    Controls are coloured green (THEME09). Before Export IFP — Bake\n    & Clear IK, which removes everything and deletes the control bones.',
    'Запечь визуальную позу с IK на deform-кости, удалить\n    IK-constraints и control-кости. Делать ПЕРЕД Export IFP —\n    иначе ифп получит сырые ротации без учёта IK.':
        'Bake the visual IK pose onto the deform bones and remove\n    IK-constraints and control bones. Do this BEFORE Export IFP —\n    otherwise IFP would get raw rotations without IK applied.',
    'Создать "пол" — плоскость 10×10м с процедурной сеткой,\n    которая работает как ограничитель для ног IK-рига. После\n    Add IK Rig стопы автоматически получают Floor constraint\n    с этой плоскостью как target — двигаешь плоскость по Z,\n    стопы клемпятся выше неё. Зазор (offset над плоскостью)\n    настраивается слайдером "Зазор"':
        'Create a "floor" — a 10×10m plane with a procedural grid\n    that acts as a limiter for the IK rig\'s feet. After\n    Add IK Rig the feet automatically get a Floor constraint\n    targeting this plane — you move the plane along Z,\n    feet clamp above it. The gap (offset above the plane)\n    is tuned with the "Gap" slider',
    'Извлечь все DFF, COL и текстуры из IMG-архивов GTA SA.\n\n    Кеш создаётся в папке .inu_cache/ рядом с твоим .blend файлом,\n    поэтому сцену нужно сначала сохранить — без сохранённого .blend\n    кешу некуда лечь, и оператор откажется работать.\n\n    Региональный фильтр (если выбран) сужает извлечение до TXD/моделей,\n    реально используемых в этом регионе по IDE/IPL — экономит минуты\n    на больших картах. ALL = извлечь всё':
        "Extract all DFF, COL and textures from GTA SA IMG archives.\n\n    The cache is created in the .inu_cache/ folder next to your .blend file,\n    so the scene must be saved first — without a saved .blend there's\n    nowhere to put the cache, and the operator will refuse to run.\n\n    The region filter (when chosen) narrows extraction to TXD/models\n    actually used in that region per IDE/IPL — saves minutes\n    on big maps. ALL = extract everything",
    'Toggle 8-light setup: создать если ламп нет, удалить если есть':
        'Toggle 8-light setup: create if no lamps exist, remove if they do',
    'Подтянуть тёмные участки к ярким, сохраняя шаг между гранями':
        'Lift dark areas towards the bright ones while preserving the step between faces',
    'Рассеять выбранный цвет вокруг выделенных полигонов с убыванием по расстоянию':
        'Scatter the chosen colour around the selected polygons with distance falloff',
    'Добавить IDE файл в список Custom':
        'Add IDE file to the Custom list',
    'Добавить IPL файл в список Custom':
        'Add IPL file to the Custom list',
    'Удалить запись IDE из Custom списка':
        'Remove an IDE entry from the Custom list',
    'Удалить запись IPL из Custom списка':
        'Remove an IPL entry from the Custom list',
    'Очистить список результатов':
        'Clear results list',
    'Сохранить результаты анализа в .txt':
        'Save analysis results to .txt',
    'Открыть документацию аддона на GitHub. Язык подбирается\n    под текущую локаль Blender.':
        "Open the addon's documentation on GitHub. Language is picked\n    to match the current Blender locale.",
    'Открыть issues аддона на GitHub — для багрепортов и пожеланий.':
        "Open the addon's issues on GitHub — for bug reports and feature requests.",
    'Открыть страницу последнего релиза на GitHub — там полный\n    changelog текущей версии, рендерится из RELEASE_NOTES.':
        'Open the latest release page on GitHub — full changelog of\n    the current version, rendered from RELEASE_NOTES.',
    'Показать краткий обзор новых фич текущей версии.':
        'Show a brief overview of the new features in this version.',
    "Проверить все материалы со слотами Paintjob:\n    оба слота должны быть заполнены, и у материала должна быть основная\n    текстура — иначе игра не подхватит paintjob в Pay'n'Spray.":
        "Validate all materials with Paintjob slots:\n    both slots must be filled, and the material must have a main\n    texture — otherwise the game won't pick up the paintjob in Pay'n'Spray.",
    'Перезаписать выбранный пресет текущими настройками (без диалога имени)':
        'Overwrite the selected preset with the current settings (no name dialog)',
    'Переименовать выбранный пресет':
        'Rename the selected preset',
    'Просканировать TXD по выбранному источнику и заполнить\n    Texture Browser метаданными (без декодинга пикселей)':
        'Scan TXD from the chosen source and populate\n    Texture Browser with metadata (without decoding pixels)',
    'Очистить результаты Texture Browser':
        'Clear Texture Browser results',
    'Добавить .img / .txd в список Custom':
        'Add .img / .txd to the Custom list',
    'Удалить запись из Custom-списка':
        'Remove an entry from the Custom list',
    "Запустить полную проверку сцены: paintjob слоты, нормировку\n    кватернионов в Action'ах, Modulate Color на прилайтах и парность\n    _ok/_dam. Результаты пишутся в панель — кликом можно перейти к\n    проблемному объекту или починить автоматически.":
        'Run a full scene check: paintjob slots, Action quaternion\n    normalisation, Modulate Color on prelight meshes and\n    _ok/_dam pairing. Results are written to the panel — a click\n    can jump to the problem object or fix it automatically.',
    'Очистить список результатов.':
        'Clear results list.',
    'Сделать активным объект/материал из строки результата.':
        'Make the object/material from the result row active.',
    'Нормализовать все кватернионные ключи в указанном Action.\n    Идентично тому что делает IFP-экспортёр на лету, но пишет правку\n    обратно в Action — на след. экспорт уже нечего нормировать.':
        'Normalise every quaternion key in the specified Action.\n    Identical to what the IFP exporter does on the fly, but writes the\n    fix back into the Action — next export has nothing left to normalise.',
    "Переименовать объект, заменив неправильный разделитель в\n    суффиксе на тот, что задан в настройках суффиксов сцены.\n\n    Применимо только к мисматчу типа «.DFF при настройке _DFF» —\n    т.е. имя оканчивается на конфигурированный bare-token, но через\n    другой разделитель. Двойной суффикс (body_LOD_DFF) не трогаем —\n    там нет однозначного автоматического fix'а.":
        "Rename the object, replacing the wrong separator in the\n    suffix with the one set in scene suffix preferences.\n\n    Applies only to mismatches like «.DFF when configured as _DFF» —\n    i.e. the name ends with the configured bare-token but via\n    a different separator. A double suffix (body_LOD_DFF) is left\n    alone — there's no unambiguous automatic fix.",
    "Временно слить co-located вершины для редактирования весов.\n\n    Backup'ит mesh datablock, усредняет веса между cluster-mate'ами,\n    делает bmesh remove_doubles. В Outliner'е остаётся один объект.":
        'Temporarily merge co-located vertices for weight editing.\n\n    Backs up the mesh datablock, averages weights between cluster-mates,\n    runs bmesh remove_doubles. A single object remains in the Outliner.',
    "Применить покрашенные веса обратно на оригинальную split-геометрию.\n\n    Считывает веса с merged-меша, swap'ает mesh datablock обратно на\n    backup (со split-вершинами), распределяет веса по cluster-mate'ам\n    через position-match.":
        'Apply painted weights back to the original split geometry.\n\n    Reads weights from the merged mesh, swaps the mesh datablock back to\n    the backup (with split vertices), distributes the weights across the\n    cluster-mates via position-match.',
    "Откатить merge без сохранения покрашенных весов.\n\n    Swap'ает mesh datablock обратно на backup, удаляет merged-копию.\n    Веса покрашенные в merged-режиме теряются.":
        'Roll back the merge without saving painted weights.\n\n    Swaps the mesh datablock back to the backup, removes the merged copy.\n    Weights painted in merged mode are lost.',
    "Фоновый модал — диспатчит события на все видимые floater'ы":
        'Background modal — dispatches events to all visible floaters',
    'Показать / скрыть плавающее окно INU Floater':
        'Show / hide an INU Floater window',
    'Найти неиспользуемые текстуры и материалы — те, на которые не ссылается ни один меш-слот в сцене':
        'Find unused textures and materials — those not referenced by any mesh slot in the scene',
    'Удалить неиспользуемые текстуры и (опционально) материалы из сцены.\n\n    use_fake_user-помеченные datablocks пропускаются — это явный знак\n    «оставить даже без ссылок». Действие необратимо без Ctrl+Z, поэтому\n    показывает подтверждение со счётчиками перед удалением':
        "Remove unused textures and (optionally) materials from the scene.\n\n    use_fake_user-flagged datablocks are skipped — that's an explicit signal\n    «keep even with no references». The action is irreversible without Ctrl+Z, so it\n    shows a confirmation with counters before deleting",
    'Сохранить текущие настройки материала как новый пресет':
        'Save current material settings as a new preset',
    'Удалить пользовательский пресет (встроенные удалить нельзя)':
        "Delete a user preset (built-ins can't be deleted)",
    'Создать новый профиль. Маленький popup только с именем и\n    описанием — все панели включаются по умолчанию, видимость и\n    порядок настраиваются после через кнопку ⚙ (Edit Profile).':
        'Create a new profile. A small popup with just the name and\n    description — all panels are on by default; visibility and\n    order are tuned afterwards via the ⚙ button (Edit Profile).',
    'Удалить активный пользовательский профиль (ALL удалить нельзя).':
        'Delete the active user profile (ALL cannot be deleted).',
    "Click-to-pick / click-to-place reorder: первый клик «берёт»\n    панель (она подсвечивается), второй клик по другой панели\n    «кладёт» её на это место. Эмулирует drag-and-drop через два\n    клика — Blender Python не отдаёт настоящий drag для custom\n    items в popup'е.":
        "Click-to-pick / click-to-place reorder: first click «picks» a\n    panel (it highlights), second click on another panel\n    «places» it at that spot. Emulates drag-and-drop via two\n    clicks — Blender Python doesn't expose a real drag for custom\n    items in a popup.",
    'Eye-toggle: переключает видимость одной панели в активном\n    профиле. Позиция панели в `order` не меняется — только\n    membership в `hidden` set.':
        "Eye-toggle: flips visibility of a single panel in the active\n    profile. The panel's position in `order` isn't changed —\n    only membership in the `hidden` set.",
    'Открыть редактор активного профиля в отдельном popup-окне.\n    Та же UI что и inline-список, но скрытая за одной кнопкой —\n    main panel остаётся чистой пока юзер не настраивает layout.':
        'Open the editor for the active profile in a separate popup\n    window. Same UI as the inline list, but hidden behind one\n    button — the main panel stays clean until the user tunes layout.',
    'Добавить новый слой в текущий стек (Day или Night).\n\n    Создаёт ``BYTE_COLOR``/``CORNER`` атрибут с префиксом ``VCL_D_`` или\n    ``VCL_N_`` и инициализирует его прозрачным (alpha=0). Стек ограничен\n    10 слоями — операция отказывает с предупреждением при переполнении':
        'Add a new layer to the current stack (Day or Night).\n\n    Creates a ``BYTE_COLOR``/``CORNER`` attribute prefixed with ``VCL_D_`` or\n    ``VCL_N_`` and initialises it as transparent (alpha=0). Stack is capped\n    at 10 layers — operation refuses with a warning on overflow',
    'Удалить активный слой и его color attribute. Действие undo-able':
        'Remove the active layer and its color attribute. Action is undo-able',
    'Переместить активный слой вверх/вниз в стеке (меняет порядок блендинга)':
        'Move the active layer up/down in the stack (changes blend order)',
    'Сделать слой полноценным прилайт-атрибутом (убрать VCL_<scope>_ префикс).\n\n    Атрибут останется на меше под коротким именем — но из стека VCL\n    исчезнет. Полезно когда заведомо «временный» слой пора зафиксировать\n    как новый базовый прилайт':
        'Promote a layer to a full-fledged prelight attribute (strip the VCL_<scope>_ prefix).\n\n    The attribute stays on the mesh under the short name — but disappears\n    from the VCL stack. Useful when a deliberately «temporary» layer is ready\n    to be locked in as a new base prelight',
    'Превратить произвольный color attribute в VCL-слой (добавить префикс).\n\n    Scope (Day или Night) определяется параметром оператора — на UI\n    кнопки «→ Day» / «→ Night» рядом с не-VCL атрибутами в секции «База»':
        'Demote an arbitrary color attribute into a VCL layer (add the prefix).\n\n    Scope (Day or Night) is set by the operator parameter — in the UI\n    «→ Day» / «→ Night» buttons appear next to non-VCL attributes in the «Base» section',
    'Сделать атрибут Day или Night активным в Color Attributes.\n\n    В hijack-режиме (Live Preview ON) Day и Night содержат итоговую\n    композицию своего стека — клик на эту кнопку просто переключает\n    активный color attribute на нужный, чтобы viewport показал нужный\n    стек. Если Live Preview OFF — Day/Night содержат оригиналы, кнопки\n    работают как обычный «выбрать атрибут»':
        'Make the Day or Night attribute active in Color Attributes.\n\n    In hijack mode (Live Preview ON) Day and Night contain the final\n    composition of their stack — clicking this button just switches the\n    active color attribute to the one you need so the viewport shows the\n    right stack. If Live Preview is OFF — Day/Night contain the originals,\n    the buttons behave like a regular «pick attribute»',
    'Пересобрать composite в Day/Night вручную.\n\n    Используется когда нужно форсировать пересчёт без триггера через\n    слайдер — например после ручного редактирования атрибутов через\n    Mesh Data Properties':
        'Rebuild the Day/Night composite manually.\n\n    Used when you need to force a recompute without triggering via a\n    slider — e.g. after manually editing the attributes via\n    Mesh Data Properties',
    "Применить значение слайдера к выделенным слоям.\n\n    Режим 'ABSOLUTE' — всем выделенным присваивается одно и то же\n    значение. 'RELATIVE' — каждое значение сдвигается на дельту\n    относительно своего текущего":
        "Apply the slider value to the selected layers.\n\n    Mode 'ABSOLUTE' — all selected get the same value. 'RELATIVE' —\n    each value is shifted by the delta relative to its current one",
    'Перекрасить выделенные слои — заменить RGB всех окрашенных\n    пикселей на выбранный цвет (alpha сохраняется).\n\n    Полезно когда хочешь поменять оттенок группы слоёв, не трогая то\n    что под ними и не перерисовывая руками':
        "Recolor selected layers — replace the RGB of every coloured\n    pixel with the chosen colour (alpha is preserved).\n\n    Useful when you want to change the tint of a group of layers without\n    touching what's underneath or repainting by hand",
    "Сделать color attribute этого слоя активным на меше + (опционально) переключиться в Vertex Paint.\n\n    Используется UIList'ом — клик по строке слоя сразу даёт пользователю\n    рисовать в нужный атрибут без ручного переключения в Mesh Data\n    Properties → Color Attributes":
        "Make this layer's color attribute active on the mesh + (optionally) switch to Vertex Paint.\n\n    Used by the UIList — clicking on a layer row lets the user paint into\n    the correct attribute without manually switching in Mesh Data\n    Properties → Color Attributes",
    'Создать поврежденный (_dam) дубликат активного меша. Если у источника нет суффикса, ему присваивается _ok. Поврежденный вариант ставится в ту же иерархию и скрывается во viewport (но остаётся видим для DFF-экспорта)':
        'Create a damaged (_dam) duplicate of the active mesh. If the source has no suffix, _ok is assigned to it. The damaged variant is placed in the same hierarchy and hidden in the viewport (but stays visible for DFF export)',
    'Переключить отображение OK / Damaged частей машины во viewport. Сканирует иерархию активной машины (или всю сцену, если активного объекта нет) и скрывает _ok или _dam меши в зависимости от выбранного состояния. Не влияет на DFF-экспорт':
        "Toggle OK / Damaged vehicle parts display in the viewport. Scans the active vehicle's hierarchy (or the whole scene if no active object) and hides _ok or _dam meshes depending on the chosen state. Does not affect DFF export",
    'Найти и отчитаться о парах _ok / _dam в активной иерархии. Предупреждает если у меша есть _ok без _dam (или наоборот) — такой меш пропускается движком при повреждениях':
        'Find and report _ok / _dam pairs in the active hierarchy. Warns when a mesh has _ok without _dam (or vice versa) — such a mesh is skipped by the engine on damage',
    'Главная панель GTA Tools — root of the N-sidebar tab. Not in\n    PANELS registry: roots have no bl_order (they own the tab) and\n    Phase 5 will need one root per tab, handled separately.':
        'Main GTA Tools panel — root of the N-sidebar tab. Not in\n    PANELS registry: roots have no bl_order (they own the tab) and\n    Phase 5 will need one root per tab, handled separately.',
    'Pre-export sweep: paintjob slots, quaternion normalisation,\n    Modulate Color на прилайтах, парность _ok/_dam.\n\n    Sub-panel живёт внутри Export panel — pre-flight check рядом с\n    кнопкой экспорта, без отдельного слота в registry.':
        'Pre-export sweep: paintjob slots, quaternion normalisation,\n    Modulate Color on prelight meshes, _ok/_dam pairing.\n\n    Sub-panel lives inside the Export panel — pre-flight check next\n    to the export button, no separate slot in the registry.',
    'Scrollable list of binary file lint issues. Filters by severity\n    («Только ERROR» toggle) and free-text search via the standard\n    UIList search field.':
        'Scrollable list of binary file lint issues. Filters by severity\n    («ERRORS only» toggle) and free-text search via the standard\n    UIList search field.',
    'Combined sub-panel внутри «Проверка»: переключатель сверху между\n    двумя режимами анализа — DFF/COL/TXD файлы или IDE/IPL карта.\n\n    Историческое имя ``GTATOOLS_PT_file_scanner`` оставлено, чтобы\n    layouts с ``bl_parent_id`` не сломались — содержание расширено\n    на два подрежима.':
        "Combined sub-panel inside «Validation»: top toggle between\n    two analysis modes — DFF/COL/TXD files or IDE/IPL map.\n\n    The historical name ``GTATOOLS_PT_file_scanner`` is kept so\n    layouts with ``bl_parent_id`` don't break — the content is\n    extended to two sub-modes.",
    'Result list for the Map Analyzer panel. Same shape as the file\n    scanner list but reads its own «Только ERROR» toggle from\n    ``gtatools_map_analyzer_only_errors`` so the two panels filter\n    independently.':
        'Result list for the Map Analyzer panel. Same shape as the file\n    scanner list but reads its own «ERRORS only» toggle from\n    ``gtatools_map_analyzer_only_errors`` so the two panels filter\n    independently.',
    'Frame Hierarchy Editor — компактное дерево фреймов активного\n    объекта + операторы для безопасного rename / set-parent / validate\n    против vanilla SA шаблонов (vehicle, ped). DFF-frame-list пишется\n    точно по этим именам, так что любая опечатка ломает поведение в\n    игре — лучше отловить здесь, чем после копирования в IMG.':
        'Frame Hierarchy Editor — compact tree of frames of the active\n    object + operators for safe rename / set-parent / validate against\n    vanilla SA templates (vehicle, ped). The DFF frame list is written\n    using exactly these names, so any typo breaks behavior in the\n    game — better caught here than after copying to IMG.',
    'Менеджер ID моделей GTA SA':
        'GTA SA Model ID Manager',
    'Lighting — общий контейнер для всех инструментов по работе со светом\n    и vertex colors. Объединяет 5 подпанелей (Prelight, Prelight COL,\n    Vertex Paint, LightMap, Itera Tools 3) под одним заголовком, чтобы не\n    раздувать N-sidebar пятью отдельными top-level панелями. Все дети\n    свёрнуты по умолчанию — юзер раскрывает только нужный.':
        "Lighting — common container for all light / vertex-color tools.\n    Bundles 5 sub-panels (Prelight, Prelight COL, Vertex Paint,\n    LightMap, Itera Tools 3) under one heading so the N-sidebar isn't\n    bloated with five separate top-level panels. All children are\n    collapsed by default — the user expands only what they need.",
    'Sub-panel: инструменты для работы со светом / vertex colors.':
        'Sub-panel: tools for working with light / vertex colors.',
    "Документация, баг-репорты и What's New — внизу панели":
        "Documentation, bug reports and What's New — at the bottom of the panel",
    'V-offset для Day vcol — применяется автоматически при изменении':
        'V-offset for Day vcol — applied automatically when changed',
    'V-offset для Night vcol — применяется автоматически при изменении':
        'V-offset for Night vcol — applied automatically when changed',
    'Из какой игры импортируем TXD. Auto — по RW-версии в chunk header':
        'Which game to import TXD from. Auto — by RW version in chunk header',
    'Имя пресета (буквы, цифры, дефис, подчёркивание, пробел)':
        'Preset name (letters, digits, hyphen, underscore, space)',
    'Описание':
        'Description',
    'Короткое описание (необязательно)':
        'Short description (optional)',
    'Имя нового профиля. Заменит существующий с тем же именем':
        'Name of the new profile. Replaces any existing one with the same name',
    'Короткая подсказка для tooltip в dropdown':
        'Short hint shown as tooltip in the dropdown',

    # ── Mobile TXD warning (txd_export.py) ──
    'TXD сохранён в PC формате. Для mobile конвертируй через TxdGen (PVRTC/ETC1).':
        'TXD saved in PC format. For mobile use TxdGen (PVRTC/ETC1) to convert.',

    # ── Empty-rig (Kams-style) animated map object (animobj_ops.py) ──
    "Префикс для имени Empty'ев: <base>_root + <base>_pivot. Совпадает с именем модели DFF/IFP":
        "Prefix for Empty names: <base>_root + <base>_pivot. Matches the DFF/IFP model name",
    'Имя Blender Action на pivot Empty — попадёт в IFP. Игра ищет анимацию по этому имени из IDE anim entry':
        "Blender Action name on the pivot Empty — written to IFP. The game looks up animations by this name in the IDE anim entry",
    'После Setup припарентите статичный меш к <base>_root,':
        'After Setup, parent the static mesh to <base>_root,',
    'а анимируемый — к <base>_pivot':
        'and the animated mesh to <base>_pivot',
    'Empty rig: ни один pivot не дал ключей — IFP не записан':
        'Empty rig: no pivot produced any keys — IFP was not written',
    'Не нашли root Empty — запустите Setup (Empty rig)':
        'No root Empty found — run Setup (Empty rig)',
    'Rig содержит только root — нужен хотя бы один pivot Empty':
        'Rig only contains a root — at least one pivot Empty is required',
    'Ни один pivot не имеет Action с keyframes':
        'No pivot has an Action with keyframes',
    'В rig нет меша — припарентите DFF меш к root или pivot':
        'Rig has no mesh — parent the DFF mesh to root or pivot',
    "Выделите объект rig'а":
        'Select an object in the rig',
    'Auto: ползунки сами пересчитывают keyframes цикла.\nManual: ползунки заморожены, ты сам ставишь keyframes':
        'Auto: sliders rebuild the cycle keyframes themselves.\nManual: sliders frozen, you place keyframes yourself',

    # ── UI buttons for both rig flavours (ui/panels.py) ──
    'Setup (skin)':
        'Setup (skin)',
    'Setup (Empty)':
        'Setup (Empty)',
    'Validate (skin)':
        'Validate (skin)',
    'Validate (Empty)':
        'Validate (Empty)',
    'Выдели MESH/Empty и нажми Setup (skin) или Setup (Empty)':
        'Select MESH/Empty and press Setup (skin) or Setup (Empty)',

    # ── Curve-based path workflow (path_curves.py + panels.py) ──
    'Меш не содержит рёбер — путь не построен':
        'Mesh has no edges — path was not built',
    'Не нашли цепочек путей в меше':
        'No path chains found in the mesh',
    'кривых построено':
        'curves built',
    'Куда сохранить nodes*.dat':
        'Where to save nodes*.dat',
    'Записать в расширенном FLA4 формате (для Fastman92 limit adjuster)':
        'Write in the extended FLA4 format (for Fastman92 limit adjuster)',
    'Выделите хотя бы одну Curve':
        'Select at least one Curve',
    'нод записано в':
        'nodes written to',
    'Curve workflow (Kams / ZZPuma):':
        'Curve workflow (Kams / ZZPuma):',
    'Меш → Curves':
        'Mesh → Curves',
    'Curves → .dat':
        'Curves → .dat',
    'Атрибуты:':
        'Attributes:',

    # ── ZZPuma-style extras: pathset, selection, bulk, accessories ──
    'Path set':
        'Path set',
    'Размер регионной сетки. 64 = vanilla SA. Большие значения требуют Fastman92 limit adjuster (FLA4)':
        'Region grid size. 64 = vanilla SA. Larger values require the Fastman92 limit adjuster (FLA4)',
    'Записать всю карту':
        'Write entire map',
    'Создать пустые nodes*.dat для всех регионов pathSet\'а, не только для тех где есть Curve\'ы. Vanilla SA требует наличия всех 64 файлов':
        "Emit empty nodes*.dat for every region in the pathSet, not only those that have Curves. Vanilla SA requires all 64 files to exist",
    'пустых':
        'empty',
    'ped Curve выделено':
        'ped Curves selected',
    'vehicle Curve выделено':
        'vehicle Curves selected',
    'Curve выделено':
        'Curves selected',
    'Curve перекрашено':
        'Curves recoloured',
    'Скопировано props:':
        'Props copied:',
    'Буфер пуст — сначала Pick на исходной Curve':
        'Clipboard is empty — Pick from a source Curve first',
    'Props применены к':
        'Props applied to',
    'Не менять':
        'Keep',
    'Включён':
        'Enabled',
    'Выключён':
        'Disabled',
    'Выключен':
        'Disabled',
    'Нет':
        'No',
    'Да':
        'Yes',
    'Spawn rate':
        'Spawn rate',
    'Spawn probability 0.0-1.0. Введи -1 чтобы не менять':
        'Spawn probability 0.0-1.0. Enter -1 to skip',
    'Width':
        'Width',
    'Path width. Введи -1 чтобы не менять':
        'Path width. Enter -1 to skip',
    'Highway':
        'Highway',
    'Boats':
        'Boats',
    'Parking':
        'Parking',
    'Traffic':
        'Traffic',
    'Bulk-set применён к':
        'Bulk-set applied to',

    # Accessories
    'TrafficLight':
        'TrafficLight',
    'RoadBlock':
        'RoadBlock',
    'Connector':
        'Connector',
    'SpecialNode':
        'SpecialNode',
    'Светофор: spawn\'ится на сегменте между knot и knot+1':
        'TrafficLight: spawned on the segment between knot and knot+1',
    'Дорожный блок копов на самом knot':
        'Police road block exactly at the knot',
    'Connector нода (для inter-region путей FLA4)':
        'Connector node (for inter-region paths in FLA4)',
    'Универсальный маркер для special-логики':
        'Universal marker for special-purpose logic',
    'Knot index':
        'Knot index',
    'Индекс knot\'а на родительской Curve (0-based)':
        'Knot index on the parent Curve (0-based)',
    'Создан':
        'Created',
    'Удалено accessory:':
        'Removed accessories:',

    # Auto-sync + debug
    'Auto-sync включён':
        'Auto-sync enabled',
    'Что показать':
        'What to show',
    'Node IDs':
        'Node IDs',
    'Navi IDs':
        'Navi IDs',
    'Выключить всё':
        'Turn everything off',

    # UI labels for new buttons
    'Peds':
        'Peds',
    'Vehs':
        'Vehs',
    'Все':
        'All',
    'Pick':
        'Pick',
    'Apply':
        'Apply',
    'Bulk':
        'Bulk',
    'Colors':
        'Colors',
    '+TL/RB/CO':
        '+TL/RB/CO',
    'Удалить':
        'Remove',
    'Sync':
        'Sync',
    'Off':
        'Off',
    'Тип':
        'Type',

    # ── Operator tooltips (bl_description from docstrings) ──
    'Выделить все Curve-пути типа Ped (sapath_type=1)':
        'Select all Curve paths of type Ped (sapath_type=1)',
    'Выделить все Curve-пути типа Vehicle (sapath_type=2)':
        'Select all Curve paths of type Vehicle (sapath_type=2)',
    'Выделить все Curve-пути с sapath_* свойствами':
        'Select every Curve path that carries sapath_* properties',
    'Перекрасить wireframe выделенных Curve-путей по их типу/флагам':
        'Recolour wireframe of the selected Curve paths according to their type/flags',
    'Скопировать sapath_* свойства активной Curve во внутренний буфер':
        "Copy sapath_* properties of the active Curve into the addon's clipboard",
    'Применить ранее скопированные sapath_* к выделенным Curve':
        'Apply the previously picked sapath_* properties to every selected Curve',
    'Bulk-set sapath_* свойств для всех выделенных Curve.\n\n    Опции с -1 / 0 значением «не менять». Полезно для разом установить\n    type=Vehicle + traffic=enabled + spawn=1.0 на массу путей после\n    импорта или ручной правки.':
        "Bulk-set sapath_* properties on all selected Curves.\n\n    Options with a -1 / 0 value mean «keep as is». Handy for setting\n    type=Vehicle + traffic=enabled + spawn=1.0 on lots of paths after\n    import or manual edits in one go.",
    'Добавить TrafficLight / RoadBlock / Connector / SpecialNode на\n    активный knot выделенной Curve.':
        'Add a TrafficLight / RoadBlock / Connector / SpecialNode on the\n    active knot of the selected Curve.',
    'Удалить выделенные path accessory объекты':
        'Remove the selected path accessory objects',
    "Включить фоновую синхронизацию позиций path accessory'ев\n    с их родительскими Curve'ами":
        'Enable background sync of path accessory positions\n    with their parent Curves',
    'Включить/выключить debug overlay для путей (NodeID/AreaID на нодах)':
        'Toggle the path debug overlay (NodeID/AreaID labels on nodes)',
    'Создать Empty-rig для animated map object в стиле Kams скриптов:\n    два Empty (root + pivot) с user-prop BoneID и циклической Action на\n    pivot. Меши парентится вручную — статичные к root, анимируемые к pivot.\n    Не требует armature/skin — обходит rest_quat баг bone-flow.':
        "Build an Empty-based rig for an animated map object, Kams-style:\n    two Empty objects (root + pivot) with a BoneID user-prop and a cyclic\n    Action on the pivot. Meshes are parented manually — static to root,\n    animated to pivot. Skips the armature/skin path and side-steps the\n    rest_quat bug of the bone flow.",
    'Проверить Empty-rig: есть ли root + pivot, корректные BoneID,\n    Action на pivot, припарентенные меши. Сообщает первую ошибку.':
        'Validate an Empty-rig: presence of root + pivot, correct BoneIDs,\n    Action on the pivot, parented meshes. Reports the first issue found.',

    # Pre-existing armature-rig animobj docstrings (English fill-ins)
    'Создать рiг для animated map object (мельница, кран, флюгер):\n    Armature с одной костью + Action с цикличной Z-вращением.\n\n    Все вершины активного меша автоматически привязываются к\n    единственной кости (vertex group weight=1.0). Готово к экспорту в\n    DFF + IFP без ручной настройки скелета.':
        'Build a rig for an animated map object (windmill, crane, vane):\n    a single-bone Armature + an Action with a cyclic Z rotation.\n\n    Every vertex of the active mesh is automatically weighted to the\n    sole bone (vertex group weight=1.0). Ready for DFF + IFP export\n    without any manual skeleton setup.',
    'Проверить настройку animated map object перед экспортом:\n    есть ли armature, привязка ли все, единая ли кость, есть ли action,\n    нормальные ли ID. Все находки в System Console.':
        'Validate the animated map object setup before export:\n    armature present, all vertices weighted, single bone, Action present,\n    sensible IDs. Findings are printed to the System Console.',
    'Экспортировать animated map object одним кликом: пишет\n    <base>.dff + <base>.ifp в выбранную папку. Опционально дописывает\n    или обновляет anim-запись в указанном IDE-файле.':
        'Export an animated map object in one click: writes\n    <base>.dff + <base>.ifp to the chosen folder. Optionally appends\n    or updates the anim entry in the specified IDE file.',

    # ── Empty-rig setup: auto-parent option + sanity warnings ──
    'Активный меш':
        'Active mesh',
    'Что сделать с активным меш-объектом после Setup:\n  Pivot — припарентить к pivot (будет крутиться вместе с rig\'ом)\n  Root  — припарентить к root (останется статичным как \'основание\')\n  Нет   — не трогать':
        "What to do with the active mesh after Setup:\n  Pivot — parent to pivot (mesh follows the rotating rig)\n  Root  — parent to root (mesh stays static as a base)\n  None  — leave the mesh alone",
    'Парентить к pivot':
        'Parent to pivot',
    'Парентить к root':
        'Parent to root',
    'Не парентить':
        'Do not parent',
    'Меш будет крутиться вместе с pivot':
        'The mesh will rotate with the pivot',
    'Меш остаётся статичным как основание':
        'The mesh stays static as the base',
    'Не трогать активный меш':
        'Leave the active mesh alone',
    'Этот меш скиннирован (Armature). Empty-rig для map-объектов, не персонажей':
        'This mesh is skinned (Armature). Empty-rig is for map objects, not characters',
    'Для персонажей используй Setup (skin) + Character Animation':
        'For characters use Setup (skin) + Character Animation',

    # ── Post-setup parenting helpers ──
    "Припарентить выделенные меши к pivot Empty-rig'а — меш будет\n    крутиться вместе с rig'ом. Если rig'ов несколько, используется\n    тот в иерархии которого уже находится активный объект.":
        'Parent selected meshes to the rig pivot — they will rotate with\n    the rig. If several rigs exist, the one containing the active\n    object is preferred.',
    "Припарентить выделенные меши к root Empty-rig'а — они останутся\n    статичными как 'основание' (как корпус мельницы без лопастей).":
        "Parent selected meshes to the rig root — they stay static as the\n    base (e.g. the windmill body without its blades).",
    "В сцене нет Empty-rig'а — сначала Setup (Empty)":
        'No Empty-rig in the scene — run Setup (Empty) first',
    "У rig'а нет pivot Empty":
        'The rig has no pivot Empty',
    'меш(а) припарентено к':
        'mesh(es) parented to',

    # ── Panel labels for child counts + parenting buttons ──
    'Меш под pivot:':
        'Meshes under pivot:',
    'под root:':
        'under root:',
    'Pivot пустой — анимация не будет видна. Выдели меш и нажми «К pivot»':
        'Pivot has no mesh — animation will not be visible. Select a mesh and press «To pivot»',
    'К pivot':
        'To pivot',
    'К root':
        'To root',

    # ── Add Pivot operator (multi-part rigs) ──
    "Добавить ещё один pivot Empty в существующий Empty-rig — для\n    моделей с несколькими анимированными частями (например мельница +\n    противовес). Каждому pivot'у выдаётся свой BoneID и Action.\n\n    Если выделен меш — он сразу парентится к новому pivot'у.\n    Если выделена кость старого pivot'а или root — новый pivot\n    создаётся как ребёнок root'а того же rig'а.":
        'Add another pivot Empty to an existing Empty-rig — for models\n    with several animated parts (e.g. windmill + counterweight). Each\n    pivot gets its own BoneID and Action.\n\n    If a mesh is active — it is parented to the new pivot immediately.\n    If a previous pivot or root is active — the new pivot is created\n    as a child of the same rig root.',
    "Имя pivot'а":
        'Pivot name',
    "Суффикс для нового Empty: <rig>_<name>. Имя action автоматически берётся таким же":
        'Suffix for the new Empty: <rig>_<name>. The Action name is taken from this too',
    'Припарентить активный меш':
        'Parent active mesh',
    'Сразу подвесить активный меш под новый pivot':
        'Immediately hang the active mesh under the new pivot',
    '+Pivot':
        '+Pivot',
    "Структура rig'а:":
        'Rig structure:',

    # ── Orphan-mesh panel (when a non-rig mesh is active and a rig exists) ──
    "Меш вне rig'а:":
        'Mesh outside rig:',
    "Этот меш не входит в иерархию rig'а. Прикрепи его:":
        'This mesh is not part of any rig hierarchy. Attach it:',
    'К pivot (анимирован)':
        'To pivot (animated)',
    'К root (статика)':
        'To root (static)',
    'Target rig:':
        'Target rig:',

    # ── Multi-select Setup hint ──
    'Других мешей в выделении (→ root):':
        'Other meshes in selection (→ root):',

    # ── Cleaned-up Setup/Validate labels (armature flow removed) ──
    'Setup':
        'Setup',
    'Validate':
        'Validate',
    'Выдели меш и нажми Setup':
        'Select a mesh and press Setup',
    'Выбери меш пипеткой выше — rig создастся автоматически':
        'Pick a mesh with the eyedropper above — the rig will be created automatically',

    'Статика:':
        'Static:',
    'Пипеткой выбери анимированную часть ↓':
        'Pick the animated part with the eyedropper ↓',
    'Выдели меш-основание (станет статикой)':
        'Select a base mesh (will become the static part)',

    # ── Eyedropper picker for adding meshes to rig ──
    'Куда добавить':
        'Where to add',
    'Куда привесить выбранный меш:\n  К pivot — на первый pivot (анимация общая со всем pivot\'ом)\n  Новый pivot — создать отдельный pivot с собственной анимацией\n  К root — статичная часть без анимации':
        "Where to attach the picked mesh:\n  To pivot — to the first pivot (shares animation with that pivot)\n  New pivot — create a fresh pivot with its own animation\n  To root — static part with no animation",
    'Новый pivot':
        'New pivot',
    'Создать новый pivot и привесить меш к нему':
        'Create a new pivot and parent the mesh to it',
    'К существующему pivot':
        'To existing pivot',
    "Парентить к первому pivot'у (одна анимация на всех)":
        'Parent to the first pivot (one shared animation)',
    'К root (статика)':
        'To root (static)',
    'Статичная часть, не будет крутиться':
        'Static part — will not rotate',
    'Меш':
        'Mesh',
    'Кликни на пипетку и выбери меш в сцене или 3D-окне. Он автоматически добавится в rig согласно выбору «Куда добавить»':
        'Click the eyedropper and pick a mesh in the scene or 3D viewport. It will be attached to the rig according to «Where to add»',
    'Добавить меш в rig:':
        'Add mesh to rig:',
    'Или возьми пипеткой:':
        'Or use the eyedropper:',
    # === TXD per-mesh export strings (2026-05-18) ===
    'Не удалось экспортировать ни одного TXD':
        'Failed to export any TXD',
    'TXD записано в':
        'TXDs written to',
    'с ошибками':
        'with errors',

    # === v2.0.0 misc gaps ===
    'Action Editor':
        'Action Editor',
    'Damage variants:':
        'Damage variants:',
    'FLA4':
        'FLA4',
    'Ped':
        'Ped',
    'Used by':
        'Used by',
    'Vehicle':
        'Vehicle',
    "В сцене нет Empty-rig'а — сначала Setup":
        "No Empty-rig in scene — run Setup first",
    "Нет анимированных pivot'ов — IFP будет пустой":
        "No animated pivots — IFP would be empty",

    # === weight_paint_ops.py (Py 3.11 f-string fix) ===
    "Backup '{n}' исчез (вероятно Undo). ":
        "Backup '{n}' disappeared (Undo'd?). ",
    'Тэг очищен, текущая геометрия принята как есть. ':
        'Tag cleared, current geometry kept as-is. ',
    'Тэг очищен, текущая геометрия принята как есть.':
        'Tag cleared, current geometry kept as-is.',
    'Изменения весов сделанные после Undo сохранены.':
        'Weight changes made after Undo are preserved.',

    # === animobj_export — explicit existing-IFP picker ===
    'Дополнить файл':
        'Append to file',
    'Существующий IFP (опционально)':
        'Existing IFP (optional)',
    "Указать конкретный .ifp файл куда дополнить анимацию. Когда задан — игнорируется «Папка» и «Имя IFP», анимация пишется СЮДА. Удобно для merge'а в <game>/anim/myhood.ifp или подобных общих файлов вне папки экспорта DFF":
        "Pick a specific .ifp file to append the animation into. When set, «Folder» and «IFP name» are ignored — the animation goes HERE. Useful for merging into <game>/anim/myhood.ifp or other shared files outside the DFF export folder",

    # === IPL/IDE link tracking + Export dialog ===
    "DFF Flags (активный объект, из N-панели):":
        "DFF Flags (active object, from N-panel):",
    "Draw distance на момент последнего Add to IDE":
        "Draw distance at the last Add to IDE",
    "IDE файл не найден": "IDE file not found",
    "IDE: удалено {0} записей": "IDE: removed {0} entries",
    "IPL правили извне: {0} ссылок исправлено, {1} удалено":
        "IPL edited externally: {0} links repaired, {1} removed",
    "IPL файл не найден": "IPL file not found",
    "Model ID на момент последней записи/чтения строки IPL (по нему строка находится снова)":
        'Model ID at the last write/read of the IPL row (used to find the row again)',
    "Object flags на момент последнего Add to IDE":
        "Object flags at the last Add to IDE",
    "Sync IDE: linked {0}, пропущено {1}":
        "Sync IDE: linked {0}, skipped {1}",
    "Sync: linked {0}, обновлено {1}, пропущено {2}":
        "Sync: linked {0}, updated {1}, skipped {2}",
    "TXD имя на момент последнего Add to IDE":
        "TXD name at the last Add to IDE",
    "True если model_id этого объекта был успешно записан в IDE через Add":
        "True if this object's model_id was successfully written to the IDE via Add",
    "В IDE ({0})": "In IDE ({0})",
    "В IDE, параметры разошлись": "In IDE, parameters drifted",
    "В IPL ({0})": "In IPL ({0})",
    "В IPL, координаты разошлись": "In IPL, coordinates drifted",
    "Копия — добавится новым инстансом": "Copy — will be added as a new instance",
    "Не выбрано ни одного .ipl": "No .ipl selected",
    "Папка игры": "Game folder",
    "В IMG ({0})": "In IMG ({0})",
    "Не в IMG": "Not in IMG",
    "Убрать": "Remove",
    "{0}: без текстуры — TXD не создан (добавь текстуру, если модель должна быть текстурной)": "{0}: no texture — TXD not created (add a texture if the model is meant to be textured)",
    "Коррекция превью": "Preview correction",
    "Только превью — на экспорт не влияет": "Preview only — doesn't affect export",
    "Проверка IMG: найдено {0}, не в архивах {1}": "IMG check: found {0}, not in archives {1}",
    "Нет IMG: укажи архив или папку игры": "No IMG: set an archive or the game folder",
    "Не в IDE — сменился ID (был {0})": "Not in IDE — Model ID changed (was {0})",
    "IDE Verify: есть {0}, нет {1}, снято {3}, без ID {2}": "IDE Verify: present {0}, missing {1}, cleared {3}, no ID {2}",
    "Удалено из IPL: {0} (+ {1} LOD), осталось: {2}": "Removed from IPL: {0} (+ {1} LOD), left: {2}",
    "Родной IMG модели": "Model's own IMG",
    "IMG, откуда пришла модель (img_target_file)": "The IMG the model came from (img_target_file)",
    "IMG для экспорта": "IMG to export to",
    "В IMG": "To IMG",
    "У модели нет своего IMG — выбери IMG в списке": "The model has no IMG of its own — pick one from the list",
    "Карта": "Map",
    "Полный импорт/экспорт карты (gta.dat, бинарные/текстовые IPL, регионы)": "Full map import/export (gta.dat, binary/text IPLs, regions)",
    "Нет IMG: нажми «Найти IMG» или укажи архив": "No IMG: press «Find IMG» or set an archive",
    "Выделенная модель:": "Selected model:",
    "Нет выделенной модели": "No model selected",
    "Вернуть координаты из IPL": "Restore coords from IPL",
    "У выделенной модели нет своего IPL — сначала добавь её в IPL кнопкой «Add»": "The selected model has no IPL yet — add it to an IPL first with «Add»",
    "Вернул координаты из IPL: {0}, не найдено: {1}": "Restored coords from IPL: {0}, not found: {1}",
    "(неоднозначных: {0} — взят ближайший)": "(ambiguous: {0} — nearest taken)",
    "Выделите объекты с Model ID > 0": "Select objects with Model ID > 0",
    "Выделите объекты с привязкой к IPL": "Select objects linked to an IPL",
    "Кватернион (x,y,z,w) на момент последнего экспорта в IPL":
        "Quaternion (x,y,z,w) at the last IPL export",
    "Координаты на момент последнего экспорта в IPL. Если текущая позиция отличается — Add to IPL обновит существующую строку вместо добавления новой":
        "Coordinates at the last IPL export. If the current position differs, Add to IPL updates the existing row instead of appending a new one",
    "Не в IDE": "Not in IDE",
    "Не в IPL": "Not in IPL",
    "Не найдено записей для удаления": "No entries found to remove",
    "Нет связанных объектов для этого IPL": "No linked objects for this IPL",
    "Проверка: {0} ссылок ОК, {1} исправлено, {2} удалено, {3} orphan":
        "Verify: {0} links OK, {1} repaired, {2} removed, {3} orphan",
    "Путь к IDE-файлу куда этот объект был экспортирован последним":
        "Path to the IDE file this object was last exported to",
    "Путь к IPL-файлу куда этот объект был экспортирован последним":
        "Path to the IPL file this object was last exported to",
    "Стабильный ID этой расстановки в IPL. Пустой = объект ещё не экспортировался в IPL. Авто-генерируется при первом «Add to IPL»":
        "Stable ID of this placement in the IPL. Empty = object not yet exported to IPL. Auto-generated on the first «Add to IPL»",
    "Текстовые IPL": "Text IPLs",
    "Удалено из IPL: {0}, осталось записей: {1}":
        "Removed from IPL: {0}, entries left: {1}",
    "Уже в списке: {0}": "Already in list: {0}",
    "все без Model ID": "all without Model ID",
    "все целевые строки уже заняты другими объектами":
        "all target rows already taken by other objects",
    "ни одного совпадения по (model_id+pos) в этом IPL":
        "no match by (model_id+pos) in this IPL",
    "ни одного совпадения по (model_id+pos)":
        "no match by (model_id+pos)",
    "Sync несколько IPL": "Sync multiple IPL",
    "({0} IPL)": "({0} IPL)",
    "файлов не найдено: {0}": "files not found: {0}",
    "записи разнесены по {0} IPL-файлам": "spread across {0} IPL files",
    "записи разнесены по {0} IDE-файлам": "spread across {0} IDE files",
    "без имени в IDE": "no name in IDE",
    "нет DFF в IMG": "no DFF in IMG",
    "уже в сцене": "already in scene",
    "ошибка DFF": "DFF error",
    "Альфа сцены: ВКЛ": "Scene alpha: ON",
    "Альфа сцены: ВЫКЛ": "Scene alpha: OFF",
    "Альфа": "Alpha",
    "включена": "enabled",
    "выключена": "disabled",
    "материалов": "materials",
    "Запечь поверх": "Bake over",
    "Запечь поверх с тенями": "Bake over (shadows)",
    "Рисовать по нескольким:": "Paint across several:",
    "Объедини → крась кистью → Разъедини": "Merge → brush-paint → Split",
    "Объединить": "Merge",
    "Разъединить": "Split",
    "Выделите 2+ меша": "Select 2+ meshes",
    "Пустые меши": "Empty meshes",
    "Уже есть объединение — сначала «Разъединить»":
        "A merge already exists — Split it first",
    "Объединено для покраски": "Merged for painting",
    "войдите в Vertex Paint": "enter Vertex Paint",
    "Нет объединённой модели": "No merged model",
    "Разъединено": "Split",
    "Залить одним цветом:": "Fill with one color:",
    "День": "Day",
    "Ночь": "Night",
    "Только выделенные": "Selected only",
    "Нет мешей для заливки": "No meshes to fill",
    "Прилайт залит: {0} мешей. День={1} Ночь={2}":
        "Prelight filled: {0} meshes. Day={1} Night={2}",
    "Добавлено IPL: {0}": "Added IPL: {0}",


    # === property descriptions audit batch ===
    'Сдвиг границы COL освещения':
        'COL lighting boundary offset',
    'Порог яркости':
        'Brightness threshold',
    'Замерять время операций':
        'Measure operation timing',
    'Развернуть список текстовых IPL для галочек':
        'Expand the text IPL list for checkboxes',
    'Не импортировать 2DFX-эффекты при импорте':
        "Don't import 2DFX effects on import",
    'Искать все IDE/IPL через gta.dat':
        'Find all IDE/IPL via gta.dat',
    'Загружать коллизии из кеша при импорте карты':
        'Load collisions from cache on map import',
    'Создавать отдельную коллекцию на каждый IPL-файл':
        'Create a separate collection per IPL file',
    'Целевая игра для экспорта / валидации. Импорт авто-детектит игру по RW-версии':
        'Target game for export / validation. Import auto-detects the game by RW version',
    'Платформа':
        'Platform',
    'Целевая платформа: PC (vanilla) или Mobile (iOS/Android, Native Data PLG)':
        'Target platform: PC (vanilla) or Mobile (iOS/Android, Native Data PLG)',
    'Путь к IDE файлу GTA SA':
        'Path to GTA SA IDE file',
    'Путь к IPL файлу GTA SA':
        'Path to GTA SA IPL file',
    'Имя общего TXD файла':
        'Shared TXD file name',
    'Папка для поиска TXD при импорте DFF':
        'Folder to search for TXD on DFF import',
    'Папка куда писать собранную Asset Library (13 .blend файлов + blender_assets.cats.txt + textures/)':
        'Folder to write the built Asset Library to (13 .blend files + blender_assets.cats.txt + textures/)',
    'Без превью':
        'No previews',
    'Не рендерить превьюшки. В ~3× быстрее, но Asset Browser показывает заглушки вместо миниатюр':
        "Don't render previews. ~3x faster, but the Asset Browser shows placeholders instead of thumbnails",
    'Размер превью':
        'Preview size',
    'Размер превьюшек в пикселях. 128 — стандарт Blender, 256 крупнее но в 4× медленнее на рендере':
        'Preview size in pixels. 128 is the Blender standard, 256 is larger but 4x slower to render',
    'Пропускать готовые':
        'Skip existing',
    'Пропускать категории чьи .blend уже существуют в Output. Удобно при инкрементальном добавлении новых моделей после установки модов':
        'Skip categories whose .blend already exists in Output. Handy for incrementally adding new models after installing mods',
    'После успешной сборки библиотеки удалить папку .inu_cache/ (DFF, COL, исходные PNG). Освобождает много места на диске. Текстуры в самой библиотеке остаются — при включённой галочке они принудительно копируются в библиотеку (не симлинком). Будь готов что Import Map после этого потребует повторно «Извлечь ресурсы»':
        'After a successful library build, delete the .inu_cache/ folder (DFF, COL, source PNG). Frees a lot of disk space. Textures in the library itself stay — when enabled they are force-copied into the library (not symlinked). Note that Import Map will then need «Extract resources» again',
    'Включить в сборку машины/мотоциклы/лодки/самолёты. Имеет смысл только при выбранном регионе — при ALL категория всё равно строится':
        'Include cars/bikes/boats/planes in the build. Only meaningful with a region selected — with ALL the category is built anyway',
    'Включить в сборку модели NPC / игрока. Имеет смысл только при выбранном регионе':
        'Include NPC / player models in the build. Only meaningful with a region selected',
    'Включить в сборку модели оружия. Имеет смысл только при выбранном регионе':
        'Include weapon models in the build. Only meaningful with a region selected',
    'Включить в сборку Interior-объекты (data/maps/interior). Имеет смысл только при выбранном регионе':
        'Include interior objects (data/maps/interior) in the build. Only meaningful with a region selected',
    'Currently hiding DFF meshes via the «Проверка» toggle':
        'Currently hiding DFF meshes via the «Check» toggle',
    'Currently hiding LOD meshes via the «Проверка» toggle':
        'Currently hiding LOD meshes via the «Check» toggle',
    'Currently hiding COL meshes via the «Проверка» toggle':
        'Currently hiding COL meshes via the «Check» toggle',
    'Currently hiding shadow meshes via the «Проверка» toggle':
        'Currently hiding shadow meshes via the «Check» toggle',
    'Бэкенд сжатия DXT-текстур.\nPure numpy, без внешних бинарей — соответствует требованиям\nextensions.blender.org. Поверх любого бэкенда работает кэш по\nsession_uid: повторный экспорт без правок текстур почти мгновенный.':
        'DXT texture compression backend.\nPure numpy, no external binaries — meets the\nextensions.blender.org requirements. A session_uid cache sits on top of\nany backend: re-export without texture edits is near-instant.',
    'Куда привесить выбранный пипеткой меш:\n  Новый pivot — анимированная часть (своя ось/скорость)\n  К существующему pivot — на тот же pivot что и предыдущая\n  К root — статичная часть без анимации':
        'Where to attach the eyedropper-picked mesh:\n  New pivot — animated part (own axis/speed)\n  To existing pivot — same pivot as the previous one\n  To root — static part without animation',
    "Кликни на пипетку и выбери меш в сцене или 3D-окне. Если rig'а ещё нет — он создастся автоматически. После пика поле очищается — можно сразу подбирать следующий":
        "Click the eyedropper and pick a mesh in the scene or 3D view. If there's no rig yet — it's created automatically. After picking the field clears so you can pick the next one right away",
    'Какие панели показывать в N-sidebar':
        'Which panels to show in the N-sidebar',
    'Активный файл со списком ID':
        'Active file with the ID list',
    'Развернуть редкие операции':
        'Expand rare operations',
    'Цвет всех IK-контрольных костей':
        'Color of all IK control bones',
    'Высота виртуальной коллизии над плоскостью-полом':
        'Height of the virtual collision above the floor plane',
    'Настройки пола, коллизии, цвета IK':
        'Floor, collision and IK color settings',
    'Включить для анимаций которые двигают персонажа':
        'Enable for animations that move the character',
    'Утилиты для исправления sign-discontinuities':
        'Utilities to fix sign discontinuities',
    'Первый кадр диапазона':
        'First frame of the range',
    'Последний кадр диапазона':
        'Last frame of the range',
    'Ось вдоль которой сглаживать ключи между опорными. ALL — все каналы в локальных координатах кости; WORLD_X/Y/Z — только translation, в мировых координатах (медленнее, but учитывает поворот родителей)':
        "Axis along which to smooth keys between anchors. ALL — all channels in the bone's local space; WORLD_X/Y/Z — translation only, in world space (slower, but accounts for parent rotation)",
    'Визуальный сдвиг кубов IK для рук и ног':
        'Visual offset of the IK cubes for hands and feet',
    'Множитель размера всех IK-контролов':
        'Size multiplier for all IK controls',
    'Показывать кубы запястий и ступней':
        'Show wrist and foot cubes',
    'Показывать кубы-маркеры на локтях и коленях':
        'Show marker cubes on elbows and knees',
    'Показывать кубы головы, верхнего торса и ключиц':
        'Show head, upper torso and clavicle cubes',
    'Показывать корневой куб':
        'Show the root cube',
    'Базовый рассеянный свет':
        'Base ambient light',
    'Множитель интенсивности света':
        'Light intensity multiplier',
    'Гамма-коррекция':
        'Gamma correction',
    'Включить тени при запекании':
        'Enable shadows during baking',
    'Preview-режим':
        'Preview mode',
    'Сколько ambient добавлять к prelight':
        'How much ambient to add to prelight',
    'Контраст финального изображения':
        'Final image contrast',
    'Гамма финального изображения':
        'Final image gamma',
    'Смещение яркости':
        'Brightness offset',
    'Сглаживание vertex colors между соседними вершинами.\nIterations — количество проходов.\nБольше проходов = плавнее переходы':
        'Smooth vertex colors between neighbouring vertices.\nIterations — number of passes.\nMore passes = smoother transitions',
    'Сила сглаживания за один проход (0-1).\n0 — без эффекта, 1 — vertex берёт полное среднее соседей':
        'Smoothing strength per pass (0-1).\n0 — no effect, 1 — vertex takes the full average of neighbours',
    'Контраст vertex colors.\n1.0 — без изменений\n< 1.0 — меньше контраст\n> 1.0 — больше контраст':
        'Vertex color contrast.\n1.0 — unchanged\n< 1.0 — less contrast\n> 1.0 — more contrast',
    'Яркость vertex colors (additive offset).\n0.0 — без изменений\n> 0 — светлее\n< 0 — темнее':
        'Vertex color brightness (additive offset).\n0.0 — unchanged\n> 0 — lighter\n< 0 — darker',
    'Подтягивает тёмные участки к самой яркой точке, сохраняя шаг между гранями.\n0 — без изменений\n0.3-0.5 — рекомендуемый диапазон\n1 — все цвета доходят до max (теряется визуальный шаг)':
        'Pulls dark areas towards the brightest point while preserving the step between faces.\n0 — unchanged\n0.3-0.5 — recommended range\n1 — all colors reach max (the visual step is lost)',
    'Гамма-коррекция vertex colors.\n1.0 — без изменений\n< 1.0 — светлее (lift тени)\n> 1.0 — темнее (deepen тени)':
        'Vertex color gamma correction.\n1.0 — unchanged\n< 1.0 — lighter (lift shadows)\n> 1.0 — darker (deepen shadows)',
    'Скорость затухания света':
        'Light falloff rate',
    'Радиус поиска соседних граней':
        'Neighbour face search radius',
    'Цвет, которым заливаются вершины вокруг выделенных полигонов':
        'Color used to fill vertices around the selected polygons',
    'Сила вклада цвета в центре. 0 — ничего не делать, 1 — полностью заменить vcols в центре на выбранный цвет':
        'Strength of the color contribution at the center. 0 — do nothing, 1 — fully replace center vcols with the chosen color',
    'Радиус как доля половины bbox-диагонали меша. 0 — только выделенные вершины, 1 — расходится на половину диагонали':
        'Radius as a fraction of half the mesh bbox diagonal. 0 — selected vertices only, 1 — spreads across half the diagonal',
    'Режим прореживания':
        'Decimation mode',
    'Оставить каждый N-ный из выделенных (2 = удалить каждый второй)':
        'Keep every Nth of the selected (2 = remove every second)',
    'Порог ошибки':
        'Error threshold',
    'Чем выше — тем агрессивнее срез избыточных ключей':
        'The higher, the more aggressively redundant keys are culled',
    'Интерполяция':
        'Interpolation',
    'Писать все коллизии в один .col файл':
        'Write all collisions into a single .col file',
    'Имя общего .col файла без расширения':
        'Shared .col file name without extension',
    'Писать все текстуры в один общий .txd файл':
        'Write all textures into one shared .txd file',
    'Имя общего .txd файла без расширения':
        'Shared .txd file name without extension',
    'Папка с DFF/COL/TXD для сканирования':
        'Folder with DFF/COL/TXD to scan',
    'Включая подпапки':
        'Include subfolders',
    'Рекурсивный обход подпапок. По умолчанию выключено, чтобы случайно не просканировать всю систему':
        'Recursively walk subfolders. Off by default to avoid accidentally scanning the whole system',
    'Только ERROR':
        'ERROR only',
    'Скрыть WARN/INFO в списке (фильтр draw, коллекция не пересоздаётся)':
        'Hide WARN/INFO in the list (draw filter, collection not rebuilt)',
    'Куда сохранять отчёт':
        'Where to save the report',
    'Папка для отчёта':
        'Report folder',
    'Источник':
        'Source',
    '.dat файл':
        '.dat file',
    'Папка с IDE/IPL':
        'Folder with IDE/IPL',
    'Рекурсивный обход подпапок при FOLDER-режиме':
        'Recursively walk subfolders in FOLDER mode',
    'Авто-поиск всех *.img в области скана (DAT-строки / FOLDER walk / CUSTOM parent dirs) и cross-check IDE entries — flag missing DFF/TXD':
        'Auto-find all *.img in the scan area (DAT lines / FOLDER walk / CUSTOM parent dirs) and cross-check IDE entries — flag missing DFF/TXD',
    'Скрыть WARN/INFO в списке (фильтр draw)':
        'Hide WARN/INFO in the list (draw filter)',
    'Откуда брать TXD-файлы для индекса':
        'Where to take TXD files for the index from',
    'Папка со стандалон-TXD для сканирования':
        'Folder with standalone TXD to scan',
    'Подсчитать сколько IDE-моделей используют каждый TXD (используется тот же набор IDE что и у Map Analyzer)':
        'Count how many IDE models use each TXD (uses the same IDE set as Map Analyzer)',
    'Поиск':
        'Search',
    'Фильтр по имени текстуры или TXD':
        'Filter by texture or TXD name',
    'Стандарт (vanilla SA) / FLA / Строгий / Мягкий':
        'Standard (vanilla SA) / FLA / Strict / Lenient',
    'Оставить каждый N-ный ключ (2 = удалить каждый второй)':
        'Keep every Nth key (2 = remove every second)',
    'True — кубический ease-in/out (без углов на анкорах). False — линейная интерполяция':
        'True — cubic ease-in/out (no corners at anchors). False — linear interpolation',
    'Ось вдоль которой сглаживать':
        'Axis along which to smooth',

    # === f-string error/report templates ===
    'геометрия #{0}: {1} вершин — RenderWare хранит индексы треугольников в uint16 (максимум {2} вершин). Экспорт продолжен, но модель может отображаться некорректно. Рекомендуется разбить меш на части или упростить (Decimate).':
        'geometry #{0}: {1} vertices — RenderWare stores triangle indices as uint16 (max {2} vertices). Export continued, but the model may render incorrectly. Splitting the mesh or simplifying it (Decimate) is recommended.',
    'геометрия #{0}: {1} треугольников — много для одной геометрии. Экспорт продолжен (счётчик треугольников u32), но движок/инструменты могут тормозить. Рекомендуется разбить меш на части.':
        'geometry #{0}: {1} triangles — a lot for a single geometry. Export continued (triangle count is u32), but the engine/tools may lag. Splitting the mesh is recommended.',
    'геометрия #{0}: {1} материалов — RenderWare хранит material-индекс в uint16 (максимум {2}). Используй меньше материалов.':
        'geometry #{0}: {1} materials — RenderWare stores the material index as uint16 (max {2}). Use fewer materials.',
    'геометрия #{0}: {1} UV-слоёв — флаги геометрии хранят кол-во UV в uint8 (максимум {2}). GTA SA рендерит максимум 2.':
        'geometry #{0}: {1} UV layers — geometry flags store the UV count as uint8 (max {2}). GTA SA renders at most 2.',
    'геометрия #{0}: skin.num_bones={1} — RenderWare skin хранит счётчики костей в uint8 (максимум {2}).':
        'geometry #{0}: skin.num_bones={1} — RenderWare skin stores bone counts as uint8 (max {2}).',
    'геометрия #{0}: skin.num_used={1} > {2} (uint8).':
        'geometry #{0}: skin.num_used={1} > {2} (uint8).',
    'геометрия #{0}: skin.max_weights={1} > {2} (uint8).':
        'geometry #{0}: skin.max_weights={1} > {2} (uint8).',
    'геометрия #{0}: skin.bones_used содержит индекс {1} вне 0..{2} (uint8).':
        'geometry #{0}: skin.bones_used contains index {1} outside 0..{2} (uint8).',
    'геометрия #{0}: skin.bone_indices[{1}] содержит индекс {2} вне 0..{3} (uint8). Слишком много костей в арматуре.':
        'geometry #{0}: skin.bone_indices[{1}] contains index {2} outside 0..{3} (uint8). Too many bones in the armature.',
    "'{0}': model_id={1} вне диапазона 0..{2} (заголовок COL хранит ID в uint16)":
        "'{0}': model_id={1} out of range 0..{2} (the COL header stores the ID as uint16)",
    "'{0}': {1} сфер — COL2/3/4 поддерживает максимум {2}":
        "'{0}': {1} spheres — COL2/3/4 supports at most {2}",
    "'{0}': {1} боксов — COL2/3/4 поддерживает максимум {2}":
        "'{0}': {1} boxes — COL2/3/4 supports at most {2}",
    "'{0}': {1} треугольников — COL формат поддерживает максимум {2}. Разбей меш на части или упрости коллизию (Decimate).":
        "'{0}': {1} triangles — the COL format supports at most {2}. Split the mesh or simplify the collision (Decimate).",
    "'{0}': {1} вершин — COL хранит индексы в uint16 (максимум {2} вершин). Разбей меш на части или упрости коллизию (Decimate).":
        "'{0}': {1} vertices — COL stores indices as uint16 (max {2} vertices). Split the mesh or simplify the collision (Decimate).",
    "'{0}': {1} shadow-треугольников — максимум {2}":
        "'{0}': {1} shadow triangles — max {2}",
    "'{0}': {1} shadow-вершин — максимум {2}":
        "'{0}': {1} shadow vertices — max {2}",
    'OK: {0} Empties, {1} с анимацией, {2} меш(а)':
        'OK: {0} Empties, {1} animated, {2} mesh(es)',
    'Не получилось вызвать decimate: {0}. Активируй окно Graph Editor.':
        'Failed to call decimate: {0}. Activate a Graph Editor window.',
    'ANP3 не поддерживается в {0} — переключаюсь на ANPK':
        'ANP3 is not supported in {0} — switching to ANPK',
    "Папка пресетов": "Preset folder",
    "Своя папка": "Custom folder",
    "По умолчанию": "Default",
    "Изменить": "Change",
    "Сбросить на стандартную": "Reset to default",
    "Выберите существующую папку": "Select an existing folder",
    "Папка пресетов: {0} (скопировано файлов: {1})":
        "Preset folder: {0} (files copied: {1})",
    "Папка пресетов сброшена: {0}": "Preset folder reset: {0}",
    "Авто-свет коллизии": "Auto COL light",
    "Значение": "Value",
    # COL auto-light scene-property tooltips
    ("Заполнять байт освещения коллизии у фейсов, где он "
     "равен 0 (нет COL-материала / day+night не заданы). "
     "Повторяет поведение Kam's CST-экспорта (light=78), "
     "иначе коллизия в игре остаётся неосвещённой. "
     "Заданные вручную и импортированные значения не "
     "трогаются"):
        ("Fill the collision light byte on faces where it is 0 (no COL "
         "material / day+night unset). Mirrors Kam's CST export "
         "(light=78); otherwise the collision stays unlit in-game. "
         "Manually set and imported values are left untouched"),
    ("Значение байта освещения для незаполненных фейсов. "
     "78 = день≈15 / ночь 4 (дефолт Kam). Упаковка: "
     "день = младший ниббл, ночь = старший ниббл"):
        ("Light byte written to unfilled faces. 78 = day≈15 / night 4 "
         "(Kam's default). Packing: day = low nibble, night = high nibble"),

    # ── v2.1.0 additions (foliage / lightcut / bake / UV-anim / 2DFX / alpha) ──
    " карт": " maps",
    "(назовите модели вида name_hi и name_low)": "(name the models like name_hi and name_low)",
    "+ Кольцо": "+ Ring",
    ".dff .col .cst .txd .ide .ipl — каждый по своему типу": ".dff .col .cst .txd .ide .ipl — each by its own type",
    "Cycles недоступен — включите аддон Cycles": "Cycles unavailable — enable the Cycles addon",
    "DFF Import отменён": "DFF Import cancelled",
    "DFF Import: подготовка...": "DFF Import: preparing...",
    "IDE Verify: present {0}, missing {1}, zero_id {2}": "IDE Verify: present {0}, missing {1}, zero_id {2}",
    "INU Import отменён": "INU Import cancelled",
    "INU Import: подготовка...": "INU Import: preparing...",
    "Live-композит собран: ": "Live composite assembled: ",
    "N-панель → GTA Tools → UV Анимация": "N-panel → GTA Tools → UV Animation",
    "Pipeline:": "Pipeline:",
    "RW-эффекты материала: env map, bump, specular, reflection, dual texture, UV anim + пресеты": "Material RW effects: env map, bump, specular, reflection, dual texture, UV anim + presets",
    "Sync IPL: обновлено {1}, новых связей {0}, пропущено {2}": "Sync IPL: updated {1}, new links {0}, skipped {2}",
    "UV обновлена: ": "UV updated: ",
    "UV создана, авто-развёртка не удалась: ": "UV created, auto-unwrap failed: ",
    "АА": "AA",
    "Автоматически ставить material.alpha = 254 при наличии\nvertex alpha < 255 хоть на одной вершине меша.\n\nВКЛЮЧАТЬ: для прозрачных мешей (стёкла, дым, листва)\nесли хочешь чтобы движок воспринял геометрию как\nalpha-blended объект и сортировал её правильно.\n\nВЫКЛЮЧАТЬ (по умолчанию): материал остаётся opaque,\nvertex alpha не задаёт прозрачность всего объекта.\nПолезно когда vertex alpha используется для других\n": "Automatically set material.alpha = 254 when vertex\nalpha < 255 on at least one vertex of the mesh.\n\nENABLE: for transparent meshes (glass, smoke, foliage)\nif you want the engine to treat the geometry as an\nalpha-blended object and sort it correctly.\n\nDISABLE (default): the material stays opaque,\nvertex alpha does not set transparency of the whole object.\nUseful when vertex alpha is used for other\n",
    "Активная UV: ": "Active UV: ",
    "Альфа вершин выключена": "Vertex alpha disabled",
    "Альфа вершин: моделей": "Vertex alpha: models",
    "Альфа вершины (сцена)": "Vertex alpha (scene)",
    "Нет активного цветового атрибута": "No active colour attribute",
    "Альфа вершин очищена": "Vertex alpha cleared",
    "Лишние цветовые атрибуты: {extra}. GTA использует только Day и Night — остальные не экспортируются и сбивают превью альфы вершин. Удали лишние цветовые атрибуты.": "Extra colour attributes: {extra}. GTA uses only Day and Night — the rest are not exported and confuse the vertex-alpha preview. Delete the extra colour attributes.",
    "Без линзовых бликов. Обычный выбор для уличных ламп": "No lens flares. The usual choice for street lamps",
    "Большая метка-мишень": "Large target marker",
    "Быстро запечь свет от ламп в активный канал (Day/Night), без теней. ПЕРЕЗАПИСЫВАЕТ текущий цвет": "Quickly bake lamp light into the active channel (Day/Night), without shadows. OVERWRITES the current color",
    "Быстрое стробоскопическое мигание (~5 Гц) — маяки, спецсигналы, проблесковые огни": "Fast strobe flashing (~5 Hz) — beacons, emergency lights, flashing lights",
    "В сцене нет моделей с вертекс-альфой": "No models with vertex alpha in the scene",
    "Видна только во время дождя, в сухую погоду полностью выключена": "Visible only during rain, fully off in dry weather",
    "Включить или выключить превью альфы вершин": "Enable or disable vertex alpha preview",
    "Внутри": "Inside",
    "Вписать UV-анимацию в экспортируемый DFF. Также строит ноды предпросмотра — текстура едет в вьюпорте при проигрывании таймлайна": "Embed UV animation into the exported DFF. Also builds preview nodes — the texture moves in the viewport during timeline playback",
    "Вставить ключ": "Insert key",
    "Выберите меш-дерево": "Select a tree mesh",
    "Выбранный слой": "Selected layer",
    "Выделите меш-объект": "Select a mesh object",
    "Выделите модель": "Select a model",
    "Высота подсветки": "Highlight height",
    "Высотное облако (спец. использование)": "High-altitude cloud (special use)",
    "Геометрия (пол)": "Geometry (floor)",
    "Горизонтальная линия-блик (как от фар)": "Horizontal flare line (like from headlights)",
    "Для выбранной карты доп. настроек нет": "No extra settings for the selected map",
    "Для реза в пол укажи «Геометрия»": "For cutting into the floor select \"Geometry\"",
    "Добавить слой": "Add layer",
    "Добавьте хотя бы один слой карты": "Add at least one map layer",
    "Запекание": "Baking",
    "Запекать в UV: ": "Bake to UV: ",
    "Запечено камерой (стандартный материал)": "Baked with camera (standard material)",
    "Запечено карт: ": "Maps baked: ",
    "Запечь поверх существующего прилайта (сложение), а не перезаписывать": "Bake on top of the existing prelight (additive) instead of overwriting",
    "Запечь свет от ламп ПОВЕРХ существующего прилайта (сложение, Add), без теней. Текущий цвет НЕ стирается — к нему добавляется освещённость. Пишет в активный канал (Day/Night), значения зажимаются в 0–1": "Bake lamp light ON TOP of the existing prelight (additive, Add), without shadows. The current color is NOT erased — illumination is added to it. Writes to the active channel (Day/Night), values are clamped to 0–1",
    "Запечь свет от ламп и солнца ПОВЕРХ существующего прилайта (сложение, Add) с расчётом теней. Текущий цвет НЕ стирается — к нему добавляется освещённость. Пишет в активный канал (Day/Night), значения зажимаются в 0–1": "Bake lamp and sun light ON TOP of the existing prelight (additive, Add) with shadow computation. The current color is NOT erased — illumination is added to it. Writes to the active channel (Day/Night), values are clamped to 0–1",
    "Запечь свет от ламп и солнца в активный канал (Day/Night) с расчётом теней. ПЕРЕЗАПИСЫВАЕТ текущий цвет": "Bake lamp and sun light into the active channel (Day/Night) with shadow computation. OVERWRITES the current color",
    "Запечь цвет": "Bake color",
    "Затемнить низ": "Darken bottom",
    "Импортируются только выбранные файлы": "Only selected files are imported",
    "Индекс knot'а на родительской Curve (0-based)": "Knot index on the parent Curve (0-based)",
    "Использовать звезду короны как световое пятно на земле": "Use the corona star as a light spot on the ground",
    "Кадр: ": "Frame: ",
    "Каждая выделенная LOD-модель → LOD<имя>.dff": "Each selected LOD model → LOD<name>.dff",
    "Каждая выделенная модель → свой .dff": "Each selected model → its own .dff",
    "Классическая звезда-блик — стандартная корона уличных фонарей. Универсальный выбор": "Classic flare star — the standard corona for street lamps. A universal choice",
    "Ключ UV вставлен на кадре ": "UV key inserted at frame ",
    "Ключевые кадры": "Keyframes",
    "Ключей нет": "No keys",
    "Ключи UV очищены: ": "UV keys cleared: ",
    "Ключи — в UV-редакторе:": "Keys — in the UV editor:",
    "Кольца (от центра к краю):": "Rings (from center to edge):",
    "Кольцо как пятно на земле": "Ring as a spot on the ground",
    "Корона фары": "Headlight corona",
    "Корона фары, вариант 2": "Headlight corona, variant 2",
    "Кривая": "Curve",
    "Крона (затенение):": "Crown (shading):",
    "Куда привесить выбранный меш:\n  К pivot — на первый pivot (анимация общая со всем pivot'ом)\n  Новый pivot — создать отдельный pivot с собственной анимацией\n  К root — статичная часть без анимации": "Where to attach the selected mesh:\n  To pivot — to the first pivot (animation shared with the whole pivot)\n  New pivot — create a separate pivot with its own animation\n  To root — static part without animation",
    "Линзовый блик (lens flare) — лучи/гало как от яркого источника при взгляде на него. Стиль 1": "Lens flare — rays/halo as from a bright source when looking at it. Style 1",
    "Линзовый блик, стиль 2 (другой набор лучей/колец)": "Lens flare, style 2 (a different set of rays/rings)",
    "Линзовый блик, стиль 3": "Lens flare, style 3",
    "Лишних нодов альфы не найдено": "No extra alpha nodes found",
    "Лужа крови (декаль на земле)": "Blood pool (decal on the ground)",
    "Лужа крови (обычно как декаль)": "Blood pool (usually as a decal)",
    "Лунное гало — крупное мягкое свечение": "Moon halo — a large soft glow",
    "Масштаб": "Scale",
    "Материал": "Material",
    "Материал без свойств INU": "Material without INU properties",
    "Мелкая частица морской пены (спец. использование)": "Small sea foam particle (special use)",
    "Меняй Сдвиг/Кадр → «Вставить ключ»": "Change Offset/Frame → \"Insert key\"",
    "Мерцает ТОЛЬКО во время дождя, в сухую погоду горит ровно": "Flickers ONLY during rain, glows steadily in dry weather",
    "Метка захвата цели (прицел)": "Target lock marker (crosshair)",
    "Метка захвата цели, готов к выстрелу": "Target lock marker, ready to fire",
    "Мягкое круглое пятно (обычно для тени, не для короны)": "Soft round spot (usually for a shadow, not a corona)",
    "Мягкое круглое пятно — универсальный «световой круг» под лампой. Стандартный выбор для фонарей": "Soft round spot — a universal \"light circle\" under a lamp. The standard choice for lamps",
    "Мягкое круглое свечение без лучей (как луна)": "Soft round glow without rays (like the moon)",
    "Мягкое круглое свечение как пятно на земле": "Soft round glow as a spot on the ground",
    "На модель: ": "Per model: ",
    "Нарезать по резаку": "Cut by the cutter",
    "Не выбран ни один .dff файл": "No .dff file selected",
    "Не удалось построить диск": "Failed to build the disc",
    "Не удалось сохранить: ": "Failed to save: ",
    "Не удалось уменьшить: ": "Failed to downscale: ",
    "Нет активного материала": "No active material",
    "Нет валидных карт": "No valid maps",
    "Нет запечённого результата — сначала запеките": "No baked result — bake first",
    "Нет запечённых карт для сведения": "No baked maps to merge",
    "Нет картинки карты": "No map image",
    "Нет ноды UV-анимации (нет текстуры на материале?)": "No UV animation node (no texture on the material?)",
    "Нет слоёв — добавьте выше": "No layers — add one above",
    "Нет сохранённого прилайта — сначала «Запечь цвет»": "No saved prelight — \"Bake color\" first",
    "Нода не создана (нет текстуры?)": "Node not created (no texture?)",
    "Нужны текстуры — выдели .txd в списке": "Textures needed — select a .txd in the list",
    "Обе стороны (дубли)": "Both sides (duplicates)",
    "Облако с маской (спец. использование)": "Cloud with mask (special use)",
    "Обычный режим: лампа горит постоянно (днём/ночью — по флагам видимости). Подходит для большинства уличных ламп": "Normal mode: the lamp glows constantly (day/night — by visibility flags). Suitable for most street lamps",
    "Отдельным объектом": "As a separate object",
    "Отступ": "Margin",
    "Очищено материалов: ": "Materials cleaned: ",
    "Ошибка запекания: ": "Bake error: ",
    "Запекание…": "Baking…",
    "Запекание отменено": "Baking cancelled",
    "Запекание {0}/{1}: {2}": "Baking {0}/{1}: {2}",
    "Слой не найден": "Layer not found",
    "Слой ещё не запечён — сначала «Запечь»": "Layer not baked yet — press «Bake» first",
    "Не удалось войти в режим рисования: {0}": "Could not enter paint mode: {0}",
    "Рисуй по слою «{0}». Выход — Tab": "Paint on layer «{0}». Exit — Tab",
    "Ошибка импорта DFF": "DFF import error",
    "Ошибка: ": "Error: ",
    "Папка игнорируется — экспорт в этот IMG": "Folder is ignored — export goes to this IMG",
    "Подсветить верх": "Highlight top",
    "Показать текстуру": "Show texture",
    "Показывать форматы:": "Show formats:",
    "Постоянная линейная прокрутка по Speed U/V": "Constant linear scrolling by Speed U/V",
    "Превью включено": "Preview enabled",
    "Превью выключено": "Preview disabled",
    "Прилайт сброшен к состоянию до «Запечь цвет»": "Prelight reset to the state before \"Bake color\"",
    "Прилайтить крону": "Prelight the crown",
    "Прокрутка": "Scroll",
    "Профайлер (тайминги в консоль)": "Profiler (timings to console)",
    "Пути IDE / IPL / IMG — в панели «IDE / IPL»": "IDE / IPL / IMG paths — in the \"IDE / IPL\" panel",
    "Путь к .img не задан в настройках аддона": "The .img path is not set in the addon preferences",
    "Радиус": "Radius",
    "Разброс": "Spread",
    "Размер = 0 → только корона, без пятна": "Size = 0 → only corona, no spot",
    "Размер короны — сияющего спрайта, который всегда повёрнут к камере (видимый «огонёк» лампы). 0 — корона не видна. Это и есть сам видимый свет": "Corona size — the glowing sprite that always faces the camera (the visible \"glow\" of the lamp). 0 — the corona is invisible. This is the visible light itself",
    "Размер при сохранении:": "Size on save:",
    "Размер пятна": "Spot size",
    "Размер светового пятна (тени) на земле под лампой и яркость заливающего света вокруг. ЧТОБЫ ОСТАВИТЬ ТОЛЬКО КОРОНУ без пятна и подсветки — поставь 0 (корона при этом сохранится, ей управляет «Размер короны»)": "Size of the light spot (shadow) on the ground under the lamp and the brightness of the surrounding fill light. TO KEEP ONLY THE CORONA without a spot and fill — set 0 (the corona is preserved, it is controlled by \"Corona size\")",
    "Размер текстуры": "Texture size",
    "Размытое гало/отражение как пятно на земле": "Blurred halo/reflection as a spot on the ground",
    "Размытое гало/отражение — рассеянное мягкое свечение": "Blurred halo/reflection — a diffuse soft glow",
    "Ракурс": "Angle",
    "Ракурс: по нормали плоскости": "Angle: along the plane normal",
    "Не сбрасывать мою UV": "Keep my UV",
    "Режим Камера обычно ПЕРЕЗАПИСЫВАЕТ активную UV проекцией камеры. С этой галкой проекция пишется в ОТДЕЛЬНЫЙ слой «INU_BakeUV», а твоя активная UV остаётся целой — на модели две UV: своя + под запечённую текстуру": "Camera mode normally OVERWRITES the active UV with the camera projection. With this on, the projection goes into a SEPARATE 'INU_BakeUV' layer and your active UV stays intact — the model gets two UVs: yours + one for the baked texture",
    "Режим UV-анимации": "UV animation mode",
    "Резак создан — крути настройки (обновляется), потом «Нарезать»": "Cutter created — tweak settings (updates live), then \"Cut\"",
    "Рендер: ": "Render: ",
    "Сброс": "Reset",
    "Свет → топология:": "Light → topology:",
    "Световой круг под уличным фонарём (64×64), чуть резче shad_exp": "Light circle under a street lamp (64×64), a bit sharper than shad_exp",
    "Световой круг фонаря (обычно для тени)": "Lamp light circle (usually for a shadow)",
    "Светофор: spawn'ится на сегменте между knot и knot+1": "Traffic light: spawns on the segment between knot and knot+1",
    "Светящееся кольцо": "Glowing ring",
    "Своя анимация: расставь ключи на ноде Mapping (Location/Scale), экспорт прочитает их": "Custom animation: place keys on the Mapping node (Location/Scale), the export will read them",
    "Сдвиг UV": "UV offset",
    "Сегменты": "Segments",
    "Сила цвета": "Color strength",
    "Силуэт RC-самолёта (обычно для тени)": "RC plane silhouette (usually for a shadow)",
    "Силуэт вертолёта (обычно для тени)": "Helicopter silhouette (usually for a shadow)",
    "Силуэт машины (обычно для тени)": "Car silhouette (usually for a shadow)",
    "Силуэт мотоцикла (обычно для тени)": "Motorcycle silhouette (usually for a shadow)",
    "Силуэт пешехода (обычно для тени)": "Pedestrian silhouette (usually for a shadow)",
    "Скрывается во время дождя, видна только в сухую погоду": "Hides during rain, visible only in dry weather",
    "Скрыть текстуру": "Hide texture",
    "След на воде (спец. использование)": "Water trail (special use)",
    "След от заноса (спец. использование)": "Skid mark (special use)",
    "Случайное мерцание вкл/выкл со случайным интервалом — неисправная/моргающая лампа, аварийки": "Random on/off flicker at random intervals — a faulty/blinking lamp, hazard lights",
    "Снаружи": "Outside",
    "Создана UV: ": "UV created: ",
    "Создать пустые nodes*.dat для всех регионов pathSet'а, не только для тех где есть Curve'ы. Vanilla SA требует наличия всех 64 файлов": "Create empty nodes*.dat for all pathSet regions, not only those with Curves. Vanilla SA requires all 64 files to be present",
    "Создать резак": "Create cutter",
    "Солнце": "Sun",
    "Солнце создано": "Sun created",
    "Солнце удалено": "Sun removed",
    "Сохранено: ": "Saved: ",
    "Сохранить как": "Save as",
    "Сохранённый прилайт не подходит (меш изменился)": "The saved prelight does not match (the mesh changed)",
    "Сплошной белый круг — чистое световое пятно без рисунка": "Solid white circle — a pure light spot with no pattern",
    "Сплошной белый круг — чистое свечение без рисунка": "Solid white circle — a pure glow with no pattern",
    "Спрайт-указатель (спец. использование)": "Pointer sprite (special use)",
    "Текстура облака (спец. использование)": "Cloud texture (special use)",
    "Текстура травы (спец. использование)": "Grass texture (special use)",
    "Текстура травы, вариант 2 (спец. использование)": "Grass texture, variant 2 (special use)",
    "Текстура чистой воды (спец. использование)": "Clear water texture (special use)",
    "Текстура шрифта дорожных знаков (спец. использование)": "Road sign font texture (special use)",
    "Тень-силуэт RC-самолёта": "RC plane shadow silhouette",
    "Тень-силуэт вертолёта": "Helicopter shadow silhouette",
    "Тень-силуэт легковой машины": "Car shadow silhouette",
    "Тень-силуэт мотоцикла": "Motorcycle shadow silhouette",
    "Тень-силуэт пешехода": "Pedestrian shadow silhouette",
    "Только выделенные грани": "Selected faces only",
    "Трещина на стекле (спец. использование)": "Glass crack (special use)",
    "У выделенной модели нет пары по суффиксам ": "The selected model has no suffix-matched pair ",
    "У лоуполи нет UV-развёртки": "The lowpoly has no UV unwrap",
    "У объекта нет UV-развёртки": "The object has no UV unwrap",
    "У объекта нет UV-развёртки для запекания": "The object has no UV unwrap to bake to",
    "Укажите путь к .img архиву в настройках аддона": "Set the path to the .img archive in the addon preferences",
    "Файл не выбран": "No file selected",
    "Финишный флаг (спец. использование)": "Finish flag (special use)",
    "Форма": "Shape",
    "Цвет листвы (свет / тень):": "Foliage color (light / shadow):",
    "Что сделать с активным меш-объектом после Setup:\n  Pivot — припарентить к pivot (будет крутиться вместе с rig'ом)\n  Root  — припарентить к root (останется статичным как 'основание')\n  Нет   — не трогать": "What to do with the active mesh object after Setup:\n  Pivot — parent to the pivot (will spin together with the rig)\n  Root  — parent to the root (stays static as a 'base')\n  None  — leave untouched",
    "Экспортировать прямо в .img архив, путь к которому задан в настройках аддона. Выбор папки при этом игнорируется": "Export directly into the .img archive whose path is set in the addon preferences. The folder selection is ignored",
    "Эта карта ещё не запечена": "This map is not baked yet",
    "Эффект машины (спец. использование)": "Vehicle effect (special use)",
    "Яркость солнца (≈ среднему 8 точек)": "Sun brightness (≈ average of 8 points)",
    "готово": "done",
    "и нет .txd с покрытием ≥50% в": "and no .txd with ≥50% coverage in",
    "ничего": "nothing",
    "связывание альфы...": "linking alpha...",
    "▶ Пробел — предпросмотр": "▶ Space — preview",
    "▶ Пробел — предпросмотр (Material Preview / Rendered)": "▶ Space — preview (Material Preview / Rendered)",
    "Освещение": "Lighting",
    "Редактирование через N-панель": "Editing via the N-panel",
    "В IDE, разошлись": "In IDE, drifted",
    "В IPL, разошлись": "In IPL, drifted",
    "Листва / Дерево": "Foliage / Tree",

    # -- LightMap bake (GI from real scene light) --
    "Денойз": "Denoise",
    "Шумоподавление": "Noise reduction",
    "Шумоподавление запечённого LightMap встроенным OIDN (нода Denoise компоузера). GI-запечка шумная — денойз почти обязателен для чистого результата": "Denoise the baked LightMap with the built-in OIDN (compositor Denoise node). GI baking is noisy — denoising is almost mandatory for a clean result",
    "Шумоподавление шумных карт (AO / Shadow / Diffuse Lit / Emission GI / LightMap). Их запечка светозависимая/GI и шумит — денойз чистит. К плоским картам не применяется": "Denoise the noisy maps (AO / Shadow / Diffuse Lit / Emission GI / LightMap). Their bake is light-dependent / GI and grainy — denoise cleans it. Not applied to flat maps",
    "Сэмплы LightMap": "LightMap samples",
    "Сэмплы Cycles для карты LightMap. GI шумнее AO — нужно больше. С денойзом можно ниже": "Cycles samples for the LightMap. GI is noisier than AO — needs more. With denoising you can go lower",
    "Применить как": "Apply as",
    "Слой в стеке": "Layer in stack",
    "Оставить MULTIPLY-слоем в стеке — сведёте/сохраните сами, как остальные карты": "Keep it as a MULTIPLY layer in the stack — flatten/save yourself, like the other maps",
    "Впечь в диффуз": "Bake into diffuse",
    "Умножить LightMap × диффуз-текстуру → одна готовая текстура. Работает в ванильной GTA SA без шейдеров": "Multiply LightMap × diffuse texture → one ready texture. Works in vanilla GTA SA without shaders",
    "В vertex prelight": "To vertex prelight",
    "Сэмплировать LightMap по вершинам в prelight-цвета «Day» — нативное статическое освещение GTA SA": "Sample the LightMap per-vertex into the \"Day\" prelight colors — native GTA SA static lighting",
    "Отдельная текстура + 2 UV": "Separate texture + 2 UV",
    "Сохранить как LP_-текстуру и повесить через 2-й UV-канал Multiply-шейдером (нужен MTA). Макс. качество": "Save as an LP_ texture and attach via a 2nd UV channel with a Multiply shader (needs MTA). Max quality",
    "Как использовать запечённый LightMap в GTA SA": "How to use the baked LightMap in GTA SA",
    "Авто lightmap-UV": "Auto lightmap UV",
    "Качество": "Quality",
    "Пресет сэмплов LightMap (как в The_Lightmapper). «Своё» — использовать ползунок «Сэмплы LightMap»": "LightMap sample preset (like The_Lightmapper). \"Custom\" — use the \"LightMap samples\" slider",
    "Своё": "Custom",
    "Из ползунка «Сэмплы LightMap»": "From the \"LightMap samples\" slider",
    "Черновик": "Preview",
    "32 сэмпла — быстро, для превью": "32 samples — fast, for preview",
    "Средне": "Medium",
    "128 сэмплов": "128 samples",
    "Высоко": "High",
    "512 сэмплов": "512 samples",
    "Продакшн": "Production",
    "1024 сэмпла — чисто, медленно": "1024 samples — clean, slow",
    "Режим света": "Light mode",
    "Какой свет запекать в LightMap": "Which light to bake into the LightMap",
    "Полный (прямой+отражённый)": "Full (direct + indirect)",
    "Прямой свет + глобальное освещение (GI). Обычный выбор": "Direct light + global illumination (GI). The usual choice",
    "Только отражённый (GI)": "Indirect only (GI)",
    "Только непрямой отскок света — прямой оставить динамическим/в prelight": "Only the indirect bounce — leave direct light dynamic / in prelight",
    "Только прямой": "Direct only",
    "Только прямой свет и тени, без отскока": "Only direct light and shadows, no bounce",
    "Денойз по albedo/normal": "Denoise with albedo/normal",
    "Скормить денойзеру запечённые Diffuse (albedo) и Normal как доп-пассы — чище результат на краях. Работает, если эти карты запечены в том же размере": "Feed the baked Diffuse (albedo) and Normal to the denoiser as extra passes — cleaner edges. Works if those maps are baked at the same size",
    "Интенсивность": "Intensity",
    "Яркость запечённого LightMap. Меняется без пере-запекания — кнопкой «Обновить лайтмап» ниже": "Brightness of the baked LightMap. Change without re-baking via the \"Update lightmap\" button below",
    "Смягчение": "Softening",
    "Размытие LightMap — сглаживает зерно/блочность. 0 = выкл. Меняется без пере-запекания — кнопкой «Обновить лайтмап» ниже": "Blur of the LightMap — smooths grain / blockiness. 0 = off. Change without re-baking via the \"Update lightmap\" button below",
    "Обновить лайтмап": "Update lightmap",
    "Применить Интенсивность и Смягчение к запечённому LightMap — быстро, без повторной запечки. Крутишь ползунки → жмёшь → результат обновился.": "Apply Intensity and Softening to the baked LightMap — fast, without re-baking. Drag the sliders → click → the result updates.",
    "Лайтмап обновлён": "Lightmap updated",
    "LightMap запечён — превью на модели": "LightMap baked — preview on model",
    "Показать поверх базы (UV2)": "Show over base (UV2)",
    "Показать поверх UV1": "Show over UV1",
    "Объединить и сохранить": "Merge and save",
    "Показано: база(UV1) × запечённое(UV2), UV2: ": "Shown: base(UV1) × baked(UV2), UV2: ",
    "Создать отдельный непересекающийся UV-канал «LightMap» авто-развёрткой (для режима «Отдельная текстура + 2 UV»)": "Create a separate non-overlapping \"LightMap\" UV channel by auto-unwrap (for the \"Separate texture + 2 UV\" mode)",
    "Применить LightMap": "Apply LightMap",
    "Сначала запеките слой LightMap": "Bake the LightMap layer first",
    "LightMap — слой в стеке. Сведите «Сохранить как»": "LightMap is a layer in the stack. Flatten with \"Save as\"",
    "Нет запечённого Diffuse — добавьте слой Diffuse и запеките": "No baked Diffuse — add a Diffuse layer and bake",
    "Размеры Diffuse и LightMap не совпадают — печатайте в одном размере": "Diffuse and LightMap sizes differ — bake them at the same size",
    "LightMap впечён в диффуз: ": "LightMap baked into diffuse: ",
    "У объекта нет UV для сэмплинга LightMap": "The object has no UV to sample the LightMap",
    "Не удалось создать prelight-атрибут «Day»": "Could not create the \"Day\" prelight attribute",
    "LightMap записан в prelight «Day»": "LightMap written into the \"Day\" prelight",
    "LightMap записан в prelight «Day» — превью прилайта включено": "LightMap written into the \"Day\" prelight — prelight preview enabled",
    "Нет материалов с Principled BSDF для lightmap-UV2": "No Principled BSDF materials for the lightmap UV2",
    "LightMap как LP_-текстура на ": "LightMap as an LP_ texture on ",
    " материал(ов), UV2: ": " material(s), UV2: ",

    # -- v2.1.0 scene_settings localisation --
    "3D-расстояние от центра кроны — для округлых крон": "3D distance from the crown center — for rounded crowns",
    "Bevel радиус": "Bevel radius",
    "DAT файл": "DAT file",
    "GTA-листья часто продублированы (две грани в одной точке). Красить обе стороны одинаково — иначе лист закрашен только с одной стороны": "GTA leaves are often duplicated (two faces at the same point). Paint both sides equally — otherwise the leaf is painted on only one side",
    "IFP импорт/экспорт, IK Rig": "IFP import/export, IK Rig",
    "Pipeline здания с day/night vertex colors": "Building pipeline with Day/Night vertex colors",
    "Pipeline кузова машины": "Vehicle body pipeline",
    "Preset для персонажа: pipeline ID = 0, SkinPLG обязателен, MatFX/day-night vcols отключены. Используется для экспорта скиннутых ped-моделей. На самом экспорте автоматически выставляет ped-friendly defaults: has_skin=True, day_cols=False, night_cols=False, matfx=False": "Preset for a character: pipeline ID = 0, SkinPLG required, MatFX/Day-Night vcols disabled. Used for exporting skinned ped models. On export it automatically sets ped-friendly defaults: has_skin=True, day_cols=False, night_cols=False, matfx=False",
    "Work-in-progress. bpy.gpu compute shader через RGBA32F image-\nслот (в Blender 5.1 ещё нет публичного SSBO API). На практике\nне даёт выигрыша: readback Buffer'а упирается в Python GIL и\nвыходит медленнее обоих CPU-режимов. Оставлено как задел —\nоживёт когда в Blender добавят GPUStorageBuf. Сейчас используй\nNumpy или Numpy fast": "Work-in-progress. bpy.gpu compute shader via an RGBA32F image\nslot (Blender 5.1 still has no public SSBO API). In practice\nit gives no gain: the Buffer readback hits the Python GIL and\nends up slower than both CPU modes. Kept as groundwork —\nit will come alive once Blender adds GPUStorageBuf. For now use\nNumpy or Numpy fast",
    "gta.dat / default.dat / кастомный — следует за IDE/IPL/IMG строками": "gta.dat / default.dat / custom — follows the IDE/IPL/IMG lines",
    "Альфа сцены": "Scene alpha",
    "Без ambient — только prelight": "No ambient — prelight only",
    "Без pipeline": "No pipeline",
    "Без сглаживания (быстро)": "No smoothing (fast)",
    "Безье": "Bezier",
    "В папке скана": "In the scan folder",
    "В папке текущей сцены (.blend должен быть сохранён)": "In the current scene's folder (.blend must be saved)",
    "ВКЛ — создать чистый отдельный диск (пол не трогать). ВЫКЛ — врезать кольца прямо в пол": "ON — create a clean separate disc (leave the floor untouched). OFF — cut the rings directly into the floor",
    "Влияние на": "Influence on",
    "Вручную выбранные .img / .txd": "Manually selected .img / .txd",
    "Выдавливание cage (на сколько отодвинуть лучи от лоуполи к хайполи)": "Cage extrusion (how far to push the rays from the lowpoly toward the highpoly)",
    "Выкл": "Off",
    "Высота текстуры (привязка к степеням двойки)": "Texture height (snapped to powers of two)",
    "Геометрия": "Geometry",
    "Глубокая вода с волнами": "Deep water with waves",
    "Глубокая вода, не отображается": "Deep water, not rendered",
    "Горизонтальное расстояние от оси ствола — для вытянутых/колонновидных": "Horizontal distance from the trunk axis — for elongated/columnar shapes",
    "Для массовых тестовых прогонов и итеративной работы над\nгеометрией, когда пиксельное качество не критично.\nBbox-int на всех мипах, ~1.7× быстрее режима Numpy\n(~0.27с на тех же 54 текстурах).\nКачество: на типовых текстурах (бетон, кирпич, дороги) на глаз\nне отличается. На текстурах с резкими альфа-границами — заборы\n(a_fence_*), листва, проволока — могут быть видимые артефакты\nдо −5 dB PSNR. Перед релизом переключи обратно на Numpy": "For mass test runs and iterative work on\ngeometry, when pixel-level quality isn't critical.\nBbox-int on all mips, ~1.7× faster than Numpy mode\n(~0.27s on the same 54 textures).\nQuality: on typical textures (concrete, brick, roads) it's\nindistinguishable by eye. On textures with sharp alpha edges — fences\n(a_fence_*), foliage, wire — there can be visible artifacts\nup to −5 dB PSNR. Switch back to Numpy before release",
    "Доп. затемнение нижней части кроны (самозатенение сверху). 0 — выкл": "Extra darkening of the lower crown (self-shadowing from above). 0 — off",
    "Доп. затемнение нижней части кроны для операции «Цвет» (отдельно от настройки кроны). 0 — выкл": "Extra darkening of the lower crown for the \"Color\" operation (separate from the crown setting). 0 — off",
    "Доп. подсветка макушки кроны (имитация солнца сверху). 0 — выкл": "Extra highlight on the crown top (simulating sun from above). 0 — off",
    "Жёстче пороги: draw_distance > 800m, mat > 50, vert > 16k, 2DFX > 100, texture > 512px. Для QA сборки": "Stricter thresholds: draw_distance > 800m, mat > 50, vert > 16k, 2DFX > 100, texture > 512px. For QA builds",
    "Залив за края UV-островов, px": "Bleed beyond the UV island edges, px",
    "Залить только выделенные меши (иначе — все меши сцены)": "Fill only the selected meshes (otherwise — all meshes in the scene)",
    "Заменить": "Replace",
    "Замерять время операций импорта и выводить тайминги по стадиям в системную консоль (Window → Toggle System Console). Полезно для диагностики тормозов": "Measure the time of import operations and print per-stage timings to the system console (Window → Toggle System Console). Useful for diagnosing slowdowns",
    "Запас вокруг силуэта (доля размера) — чтобы крона не упиралась в края текстуры": "Margin around the silhouette (fraction of size) — so the crown doesn't hit the texture edges",
    "Запечь сам объект: текстуры берутся с рендер-UV (источник), результат пишется в выделенную UV (цель). Для trim-развёрток": "Bake the object itself: textures are taken from the render UV (source), the result is written to the selected UV (target). For trim layouts",
    "Из gta.dat по путям сцены — все *.img и *.txd": "From gta.dat via the scene paths — all *.img and *.txd",
    "Каждый N-ный": "Every Nth",
    "Как высоко по Z достаёт подсветка верха: 1 — вся крона, 0.3 — только верхние 30%. Ниже — подсветки нет": "How far up the Z axis the top highlight reaches: 1 — the whole crown, 0.3 — only the top 30%. Below that — no highlight",
    "Как наложить результат на текущие vertex colors": "How to apply the result onto the current vertex colors",
    "Как смешивать с нижними слоями": "How to blend with the layers below",
    "Как считать «внутри/снаружи»": "How to compute \"inside/outside\"",
    "Какую карту добавить новым слоем": "Which map to add as a new layer",
    "Какую карту печь в этом слое": "Which map to bake in this layer",
    "Калибровано под vanilla SA — поведение из коробки": "Calibrated for vanilla SA — out-of-the-box behavior",
    "Камера": "Camera",
    "Камера на +X, смотрит вдоль −X": "Camera at +X, looking along −X",
    "Камера на +Y, смотрит вдоль −Y": "Camera at +Y, looking along −Y",
    "Камера на −X, смотрит вдоль +X": "Camera at −X, looking along +X",
    "Камера на −Y, смотрит вдоль +Y": "Camera at −Y, looking along +Y",
    "Камера сверху, смотрит вниз": "Camera from above, looking down",
    "Карта": "Map",
    "Квадратный пресет размера (синхронит X/Y)": "Square size preset (syncs X/Y)",
    "Количество полигонов по окружности кольца (стороны круга). Больше — круглее, но больше геометрии": "Number of polygons around the ring circumference (sides of the circle). More — rounder, but more geometry",
    "Концентрические кольца (для пола)": "Concentric rings (for the floor)",
    "Красить только выделенные в Edit Mode грани": "Paint only the faces selected in Edit Mode",
    "Красить только грани с этим материалом (пусто = весь меш). Ствол с другим материалом не затрагивается": "Paint only faces with this material (empty = the whole mesh). A trunk with a different material is not affected",
    "Кривизна градиента: >1 расширяет светлую зону, <1 — тёмную": "Gradient curvature: >1 expands the light zone, <1 — the dark one",
    "Линейная": "Linear",
    "Макс. дистанция луча (0 = авто)": "Max ray distance (0 = auto)",
    "Материал (цвет)": "Material (color)",
    "Материал для операции «Цвет листвы» (своя независимая цель; пусто = весь меш)": "Material for the \"Foliage Color\" operation (its own independent target; empty = the whole mesh)",
    "Материал листвы": "Foliage material",
    "Мелкая вода, не отображается": "Shallow water, not rendered",
    "Мелкая вода, отображается": "Shallow water, rendered",
    "Меш, в который резать (земля под лампой). Пусто — найти автоматически лучом вниз от лампы": "Mesh to cut into (ground under the lamp). Empty — find it automatically by a ray cast down from the lamp",
    "Множитель энергии внутреннего свет-рига для карт Shadow / Diffuse-Lit. Больше — ярче": "Energy multiplier of the internal light rig for Shadow / Diffuse-Lit maps. More — brighter",
    "Мягкий": "Soft",
    "На первый pivot — общая анимация с другими мешами под ним": "To the first pivot — shared animation with the other meshes under it",
    "Задаёт альфа-канал (прозрачность)": "Sets the result's alpha channel (transparency)",
    "Сила альфы": "Alpha strength",
    "Источник": "Source",
    "Источник альфы": "Alpha source",
    "Откуда брать альфу: прозрачность материала или яркость другой карты стека (напр. Shadow)": "Where the alpha comes from: material transparency, or the brightness of another stack map (e.g. Shadow)",
    "Инвертировать": "Invert",
    "Инвертировать альфу: показывать ТЁМНЫЕ участки, скрывать светлые (для тени — включи)": "Invert the alpha: show DARK areas, hide light ones (turn on for a shadow)",
    "Декаль": "Decal",
    "Увести яркость карты в прозрачность: тёмное (тень) видно, светлое убирается. Порог/Мягкость отсекают серое": "Route the map's brightness into transparency: dark (shadow) is visible, light is removed. Threshold/Softness cut off the gray",
    "Порог": "Threshold",
    "Яркость, выше которой пиксель скрывается (прозрачный). Ниже порога — видно. Опусти, чтобы убрать серый пол": "Brightness above which a pixel is hidden (transparent); below it is visible. Lower it to remove the gray floor",
    "Мягкость": "Softness",
    "Ширина мягкого перехода у порога (0 — резкая граница)": "Width of the soft transition at the threshold (0 = hard edge)",
    "Инверсия цвета": "Invert color",
    "Инвертировать: показывать СВЕТЛОЕ вместо тёмного": "Invert: show LIGHT instead of dark",
    "Свет от сцены": "Scene lights",
    "Печь Shadow / Diffuse-Lit от реальных источников света сцены (твои лампы/солнце/world), как LightMap. Выкл — внутренний калиброванный SUN (работает даже без ламп)": "Bake Shadow / Diffuse-Lit from the real scene lights (your lamps/sun/world), like LightMap. Off — internal calibrated SUN (works even without lamps)",
    "Обесцветить": "Desaturate",
    "Обесцветить слой (в серое по яркости) — убирает синий оттенок Normal Map. Для Normal сразу сводит уже запечённую карту в серое": "Desaturate the layer (to gray by luminance) — removes the blue tint of the Normal Map. For Normal it immediately converts the already-baked map to gray",
    "Оставить каждый N-ный ключ": "Keep every Nth keyframe",
    "Отрендерить объект ортокамерой в текстуру с прозрачностью. Для billboard-деревьев/импостеров: ничего не обрезается, альфа берётся из силуэта": "Render the object with an ortho camera into a texture with transparency. For billboard trees/impostors: nothing is cropped, alpha is taken from the silhouette",
    "Оттенок затенённых листьев (центр кроны) — обычно темнее и холоднее": "Tint of shaded leaves (crown center) — usually darker and cooler",
    "Оттенок освещённых листьев (периферия/снаружи кроны)": "Tint of lit leaves (periphery/outside of the crown)",
    "Перенести деталь с хайполи на выделенный лоуполи (в разработке)": "Transfer detail from the highpoly onto the selected lowpoly (in development)",
    "Печь в 2× и ужать": "Bake at 2× and downscale",
    "Печь в 4× и ужать (чисто, медленнее)": "Bake at 4× and downscale (clean, slower)",
    "Плавная кривая между ключами": "Smooth curve between keyframes",
    "Поверх (×)": "Over (×)",
    "Показать список IPL для пакетной синхронизации": "Show the IPL list for batch synchronization",
    "Полностью заменить vertex colors результатом": "Fully replace the vertex colors with the result",
    "Постоянная": "Constant",
    "Просканировать одну папку рекурсивно": "Scan a single folder recursively",
    "Простой pipeline здания": "Simple building pipeline",
    "Прямые линии между ключами": "Straight lines between keyframes",
    "Прячем все INFO-уровни. Для легаси-проектов где informational шум перевешивает сигнал": "Hide all INFO levels. For legacy projects where informational noise outweighs the signal",
    "Радиус зоны света (метры) — задаёт размер круга. 0 — взять Custom Distance лампы, если включён": "Light zone radius (meters) — sets the circle size. 0 — use the lamp's Custom Distance, if enabled",
    "Радиус скругления для Bevel-карты (в единицах сцены)": "Rounding radius for the Bevel map (in scene units)",
    "Рекомендуемый режим для финального экспорта в IMG.\nRange-fit на mip 0 (главный уровень детализации) + bbox-int\nна меньших мипах. Лучшее качество без внешних бинарей.\nСкорость: ~0.5с на 54 текстурах (1024²).\nБери его, если не уверен какой выбрать": "Recommended mode for the final export to IMG.\nRange-fit on mip 0 (main level of detail) + bbox-int\non the smaller mips. Best quality, no external binaries.\nSpeed: ~0.5s on 54 textures (1024²).\nPick it if you're unsure which to choose",
    "Ручной список IDE и IPL файлов": "Manual list of IDE and IPL files",
    "Рядом с .blend": "Next to the .blend",
    "С какой стороны смотрит ортокамера": "Which side the ortho camera looks from",
    "Свернуть/развернуть выбор режима запекания": "Collapse/expand the bake mode selection",
    "Сверху +Z": "Top +Z",
    "Свет (экспозиция)": "Light (exposure)",
    "Свои пути": "Custom paths",
    "Сзади +Y": "Back +Y",
    "Сила влияния": "Influence strength",
    "Сила оттенка. 0 — цвет не меняется (только затенение), 1 — полный tint": "Tint strength. 0 — color unchanged (shading only), 1 — full tint",
    "Скан DFF/COL/TXD на диске": "Scan DFF/COL/TXD on disk",
    "Сканировать все *.ide / *.ipl в указанной папке": "Scan all *.ide / *.ipl in the specified folder",
    "Слева −X": "Left −X",
    "Случайная вариация яркости по вершинам — листва неоднородна. 0 — выкл; чем больше, тем сильнее темнеют отдельные листья": "Random brightness variation per vertex — foliage is non-uniform. 0 — off; the higher it is, the more individual leaves darken",
    "Создать новый pivot и привесить меш к нему — он будет крутиться отдельно": "Create a new pivot and attach the mesh to it — it will rotate separately",
    "Спереди −Y": "Front −Y",
    "Справа +X": "Right +X",
    "Стандарт": "Standard",
    "Статичная часть, не крутится": "Static part, does not rotate",
    "Строгий": "Strict",
    "Ступенька — без интерполяции": "Step — no interpolation",
    "Суперсэмплинг: печь во внутреннем бóльшем разрешении и ужимать до целевого — убирает лесенки/полосы на текстуре (как в TexTools). Работает и на Diffuse, в отличие от сэмплов. Дороже по времени/памяти": "Supersampling: bake at a higher internal resolution and downscale to the target — removes jaggies/banding on the texture (like in TexTools). Works on Diffuse too, unlike samples. More expensive in time/memory",
    "Сфера": "Sphere",
    "Сфера (радиус + сегменты)": "Sphere (radius + segments)",
    "Считаем что Fastman92 Limit Adjuster установлен: глушим warnings про ID > 19999, interior > 18, COL surface > 178": "Assume Fastman92 Limit Adjuster is installed: suppress warnings about ID > 19999, interior > 18, COL surface > 178",
    "Сэмплы Cycles для шумных карт (AO / свет)": "Cycles samples for noisy maps (AO / light)",
    "Текущее состояние альфы на материалах сцены (для кнопки-переключателя)": "Current alpha state on the scene's materials (for the toggle button)",
    "Тип резака": "Cutter type",
    "Туда же, откуда брались файлы": "To the same place the files came from",
    "Удалить избыточные (колинеарные) ключи": "Remove redundant (collinear) keyframes",
    "Указать вручную": "Specify manually",
    "Умножить на существующий прилайт — затенение и оттенок накладываются, запечённый свет сохраняется": "Multiply by the existing prelight — shading and tint are applied on top, the baked light is preserved",
    "Файлы": "Files",
    "Цвет дневного прилайта (Day). По умолчанию 124,124,124 — доминирующий тон": "Day prelight color (Day). Default 124,124,124 — the dominant tone",
    "Цвет ночного прилайта (Night). По умолчанию 83,83,83 — доминирующий тон": "Night prelight color (Night). Default 83,83,83 — the dominant tone",
    "Цвет света": "Light color",
    "Цвет тени": "Shadow color",
    "Цилиндр": "Cylinder",
    "Что запекаем": "What we bake",
    "Ширина текстуры (привязка к степеням двойки)": "Texture width (snapped to powers of two)",
    "Экспортировать коллизию в текстовый .cst (Collision File Editor II) при Export All": "Export collision to a text .cst (Collision File Editor II) on Export All",
    "Яркость в центре кроны (темнее)": "Brightness at the crown center (darker)",
    "Яркость на периферии кроны (светлее)": "Brightness at the crown periphery (lighter)",

    # -- v2.1.0 bake blend-mode descriptions --
    "Заменяет нижний слой": "Replaces the layer below",
    "Минимум из двух — затемнение": "Minimum of the two — darken",
    "Умножение (затемнение) — AO / Shadow": "Multiply (darken) — AO / Shadow",
    "Затемнение основы — резкий контраст теней": "Burns the base — sharp shadow contrast",
    "Максимум из двух — осветление": "Maximum of the two — lighten",
    "Экран (осветление)": "Screen (lighten)",
    "Осветление основы — резкие блики": "Dodges the base — sharp highlights",
    "Сложение (осветление)": "Add (lighten)",
    "Перекрытие — контраст / износ кромок": "Overlay — contrast / edge wear",
    "Мягкий свет — деликатный контраст": "Soft light — gentle contrast",
    "Линейный свет — жёсткий контраст": "Linear light — hard contrast",
    "Модуль разности — инверсия пересечений": "Absolute difference — inverts overlaps",
    "Вычитание (затемнение)": "Subtract (darken)",
    "Деление (осветление)": "Divide (lighten)",
    "Тон верхнего, насыщенность и яркость нижнего": "Hue of the top, saturation and value of the bottom",
    "Насыщенность верхнего, тон и яркость нижнего": "Saturation of the top, hue and value of the bottom",
    "Тон и насыщенность верхнего, яркость нижнего": "Hue and saturation of the top, value of the bottom",
    "Яркость верхнего, тон и насыщенность нижнего": "Value of the top, hue and saturation of the bottom",
    "Врезать в пол не вышло, построен диск": "Floor cut failed, built a disc",
    "Нет 3D-вьюпорта для проекции — включи режим «Отдельной геометрией»": "No 3D viewport for projection — enable «Separate geometry» mode",
    "Выдели меш-объект для DFF-флагов": "Select a mesh object to edit DFF flags",
    "Записать COL без геометрии (ноль faces/вершин/сфер/боксов, нулевой bounds), но с именем модели. Для моделей, у которых не должно быть коллизии, но запись COL обязана существовать и быть привязана к модели. Геометрия выделенных объектов игнорируется — берётся только имя": "Write COL with no geometry (zero faces/verts/spheres/boxes, zero bounds) but with the model name. For models that should have no collision yet still require a COL record to exist and be bound to the model. The geometry of the selected objects is ignored — only the name is taken",
    "Писать COL/CST без геометрии (ноль faces/вершин/сфер/боксов, нулевой bounds), но с именем модели. Для моделей, которым коллизия не нужна, но запись COL должна существовать и быть привязана к модели": "Write COL/CST with no geometry (zero faces/verts/spheres/boxes, zero bounds) but with the model name. For models that don't need collision but still require a COL record to exist and be bound to the model",
    "Пустая коллизия": "Empty collision",
    # --- Prelight preview correction (viewport-only) ---
    "Коррекция превью (вьюпорт):": "Preview correction (viewport):",
    "Только визуально — на экспорт не влияет": "Visual only — doesn't affect export",
    "Насыщенность": "Saturation",
    "Яркость (превью)": "Brightness (preview)",
    "Контраст (превью)": "Contrast (preview)",
    "Гамма (превью)": "Gamma (preview)",
    "Насыщенность (превью)": "Saturation (preview)",
    "Только вьюпорт: яркость прилайта в превью. На экспорт НЕ влияет": "Viewport only: prelight brightness in the preview. Does NOT affect export",
    "Только вьюпорт: контраст прилайта в превью. На экспорт НЕ влияет": "Viewport only: prelight contrast in the preview. Does NOT affect export",
    "Только вьюпорт: гамма прилайта в превью. <1 — светлее. На экспорт НЕ влияет": "Viewport only: prelight gamma in the preview. <1 = brighter. Does NOT affect export",
    "Только вьюпорт: насыщенность прилайта в превью. 1 — как есть, 0 — ч/б. На экспорт НЕ влияет": "Viewport only: prelight saturation in the preview. 1 = as-is, 0 = grayscale. Does NOT affect export",
    # --- Export game selector / auto-detect ---
    "Экспорт в игру:": "Export to game:",
    # --- Ariane bridge (redesigned panel) ---
    "укажи папку игры": "set game folder",
    "Синхр. удаления": "Sync deletions",
    "Показать редкие/продвинутые действия моста": "Show rare / advanced bridge actions",
    # --- Auto-TXD (non-fatal) ---
    "авто-TXD пропущен": "auto-TXD skipped",
    # --- Texture bake ---
    "Учитывать PreLight": "Include PreLight",
    "Суффикс имени": "Name suffix",
    "Укажи папку с IPL": "Pick a folder with IPL files",
    "Только выделенные полигоны": "Selected faces only",
    "Только выделенные рёбра": "Selected edges only",
    "Прозрачный фон": "Transparent background",
    "Источники прилайта:": "Prelight sources:",
    "Учитывать точечные лампы (Point) при запекании прилайта": "Include Point lamps when baking prelight",
    "Учитывать солнце (Sun) при запекании прилайта": "Include the Sun when baking prelight",
    "Учитывать прожекторы (Spot, с конусом) при запекании прилайта": "Include Spot lamps (with cone) when baking prelight",
    "Учитывать площадные лампы (Area) при запекании прилайта (считаются как точечный источник)": "Include Area lamps when baking prelight (treated as a point source)",
    "Добавить освещение от мира/HDRI (World): цвет неба сэмплится по направлению нормали. Можно комбинировать с лампами через тумблеры Point/Sun/Spot/Area": "Add world/HDRI lighting (World): the sky colour is sampled along the normal. Can be combined with lamps via the Point/Sun/Spot/Area toggles",
    "Ко всем выделенным COL": "To all selected COL",
    "Ошибка импорта: ": "Import error: ",
    "Импорт из IMG...": "Importing from IMG...",
    "Импорт из IMG:": "Import from IMG:",
    "Не удалось открыть: {0}": "Could not open: {0}",
    "Не удалось открыть в Blender: {0}": "Could not open in Blender: {0}",
    "Открытие IPL / IDE": "Opening IPL / IDE",
    "Открывать IPL/IDE в редакторе Blender": "Open IPL/IDE in Blender's editor",
    "ВКЛ — открывать файлы IDE/IPL во встроенном текстовом редакторе Blender (в новом окне). ВЫКЛ — во внешнем редакторе ОС (Блокнот и т.п.), как двойной клик в проводнике": "ON — open IDE/IPL files in Blender's built-in text editor (in a new window). OFF — in the OS external editor (Notepad etc.), like a double-click in the file browser",
    "ВЫКЛ — внешний редактор ОС · ВКЛ — текст-редактор Blender": "OFF — OS external editor · ON — Blender text editor",
    "выбрано IPL: {0}": "IPL selected: {0}",
    "IPL для импорта ({0}):": "IPL to import ({0}):",
    "IPL для импорта": "IPL to import",
    "IMG с моделями из IPL": "IMG with IPL models",
    "IDE с моделями из IPL": "IDE with IPL models",
    "Sync несколько IDE": "Sync multiple IDE",
    "Экспорт в свои IDE": "Export to own IDE",
    "Добавлено IDE: {0}": "IDE added: {0}",
    "Добавлено IDE из папки: {0} (найдено {1})":
        "IDE added from folder: {0} (found {1})",
    "Укажи папку с IDE": "Pick a folder with IDE files",
    "IDE: обновлено {0}, добавлено {1}, файлов {2}":
        "IDE: updated {0}, added {1}, files {2}",
    "новых вне IDE: {0} (добавь через «Add»)":
        "new outside IDE: {0} (add via «Add»)",
    "Обновить из IDE/IPL": "Refresh from IDE/IPL",
    "Обновить из IDE": "Refresh from IDE",
    "Обновить из IPL": "Refresh from IPL",
    "Нет IDE: укажи файл или папку игры": "No IDE: pick a file or the game folder",
    "Sync IDE: linked {0}, пропущено {1} ({2} IDE)":
        "Sync IDE: linked {0}, skipped {1} ({2} IDE)",
    "Открыть сайт в браузере": "Open the website in the browser",
    "Открыть сайт Ariane — редактор карт для round-trip с аддоном":
        "Open the Ariane website — map editor for round-trip with the addon",
    "Открыть сайт Itera Tools 3 — материалы освещения (companion)":
        "Open the Itera Tools 3 website — lighting materials (companion)",
    "Убрать из IDE+IPL": "Remove from IDE+IPL",
    "IPL для экспорта": "IPL to export",
    "IDE для экспорта": "IDE to export",
    "Масштаб островов": "Island scale",
    "Размер текстуры": "Texture size",
    "Текстура": "Texture",
    "Значение": "Value",
    "В сетку": "To grid",
    "Тексель": "Texel",
    "ось: высота (Ряды)": "axis: height (Rows)",
    "ось: ширина (Колонки)": "axis: width (Columns)",
    "задай только Ряды ИЛИ только Колонки":
        "set only Rows OR only Columns",
    "Задай ТОЛЬКО ряды ИЛИ только колонки (не оба)":
        "Set ONLY rows OR only columns (not both)",
    "Размер текстуры и значение должны быть > 0":
        "Texture size and value must be > 0",
    "Вписано островов:": "Islands fitted:",
    "Тексель задан:": "Texel density set:",
    "островов": "islands",
    "LOD — снимите «Skip LOD»": "LOD — uncheck «Skip LOD»",
    "Найти IMG": "Find IMG",
    "IMG с моделями из IPL ({0}):": "IMG with IPL models ({0}):",
    "Найдено IMG: {0} · моделей покрыто {1}/{2}":
        "Found IMG: {0} · models covered {1}/{2}",
    "Укажите папку игры": "Set the game folder",
    ("IDE: id не найден в файле для: {0} — правка ушла в НОВУЮ строку "
     "(дубликат), существующая не обновлена. Проверь Model ID объекта"):
        ("IDE: id not found in file for: {0} — the edit went to a NEW line "
         "(duplicate), the existing one was not updated. Check the object's "
         "Model ID"),
    'ANP3 — родной формат GTA SA (int16, как ванильный ghands.ifp; читается игрой И сторонними тулзами вроде GTA Anim Manager). ANPK / ANP2 — chunked float32 (III/VC, тоже читается SA)': 'ANP3 — native GTA SA format (int16, like vanilla ghands.ifp; read by the game AND third-party tools like GTA Anim Manager). ANPK / ANP2 — chunked float32 (III/VC, also read by SA)',
    'Live: перемещение, выделение и камера синхронизируются между ariane и Blender в реальном времени (по ariane_guid). Один переключатель на всё; требует включённого watcher': 'Live: movement, selection and camera sync between ariane and Blender in real time (by ariane_guid). One toggle for all; requires the watcher enabled',
    'Live: удаление импортированного объекта в Blender мягко удаляет инстанс в ariane (Ctrl+Z восстанавливает). Выключено по умолчанию — чтобы можно было удалять в Blender, не трогая карту в ariane': 'Live: deleting an imported object in Blender softly removes the instance in ariane (Ctrl+Z restores). Off by default — so you can delete in Blender without touching the map in ariane',
    'Surface ID назначен материалам:': 'Surface ID assigned to materials:',
    'instances.txt пуст или битый': 'instances.txt is empty or corrupt',
    'Вершинные цвета → COL Day/Night': 'Vertex colors → COL Day/Night',
    'Вкл — фон запечённых карт прозрачный (альфа 0 там, где нет развёртки). Выкл (по умолчанию) — фон заливается СРЕДНИМ цветом текстуры (альфа 1), чтобы на швах/мипах не лезла чернота. Не влияет на карту ALPHA и слои-декали — у них альфа значима': 'On — baked maps keep a transparent background (alpha 0 where there is no UV). Off (default) — the background is filled with the texture AVERAGE color (alpha 1) so seams/mips do not show black. Does not affect the ALPHA map or decal layers — their alpha is meaningful',
    'Вкладка панели Экспорт/Импорт: обычный экспорт/импорт или мост Ariane': 'Export/Import panel tab: normal export/import or the Ariane bridge',
    'Во сколько раз уменьшить текстуру при сохранении': 'How much to downscale the texture on save',
    'Выдавливание cage (на сколько раздуть лоуполи наружу перед пуском лучей к хайполи). 0 = как TexTools: лучи идут от самой поверхности лоуполи. БОЛЬШЕ 0 раздувает лоуполи и на близких параллельных стенах кидает лучи на СОСЕДНЮЮ стену → стены «меняются местами». Поднимай только если хайполи торчит наружу за лоуполи': 'Cage extrusion (how far to inflate the low-poly outward before shooting rays to the high-poly). 0 = like TexTools: rays start from the low-poly surface itself. ABOVE 0 inflates the low-poly and on close parallel walls shoots rays onto the NEIGHBORING wall → walls swap places. Raise only if the high-poly sticks out past the low-poly',
    'Добавлено IPL из папки: {0} (найдено {1})': 'IPL added from folder: {0} (found {1})',
    'Запекать Bevel (UV→UV) только по ВЫДЕЛЕННЫМ граням — карта ляжет лишь на них, и на сложной модели это сильно быстрее. Действует ТОЛЬКО на Bevel; Diffuse/AO/Normal/LightMap всегда печатаются целиком. Выдели грани в Edit Mode перед запеканием': 'Bake Bevel (UV→UV) only on SELECTED faces — the map lands only on them, and on a complex model it is much faster. Affects ONLY Bevel; Diffuse/AO/Normal/LightMap always bake fully. Select faces in Edit Mode before baking',
    'Запекать хайполи ВМЕСТЕ с прилайтом (vertex colors × текстура): включает превью прилайта на хайполи на время бейка. Выкл = чистая текстура без освещения прилайта': 'Bake the high-poly TOGETHER with prelight (vertex colors × texture): turns on the prelight preview on the high-poly during the bake. Off = clean texture without prelight lighting',
    'Запись IDE/IPL/IMG': 'Write IDE/IPL/IMG',
    'Импорт моделей из игры': 'Import models from the game',
    'Интеграция с Itera Tools 3': 'Itera Tools 3 integration',
    'Как часто watcher проверяет инбокс ariane (сек). Опрос дешёвый — реальный импорт запускается только по poke-файлу от ariane': 'How often the watcher checks the ariane inbox (sec). Polling is cheap — the real import runs only on a poke file from ariane',
    'Макс. дистанция луча (0 = без лимита, как TexTools)': 'Max ray distance (0 = no limit, like TexTools)',
    'Назначить поверхность материалам ВСЕХ выделенных COL-объектов, а не только текущему': 'Assign the surface to the materials of ALL selected COL objects, not just the current one',
    'Нет instances.txt от Ariane. Ariane должна выгрузить список инстансов: guid<TAB>iid<TAB>model<TAB>x<TAB>y<TAB>z': 'No instances.txt from Ariane. Ariane must dump the instance list: guid<TAB>iid<TAB>model<TAB>x<TAB>y<TAB>z',
    'Папка игры с ariane для моста (обмен через <папка>\\ariane\\bridge). Пусто → берётся Game Root, иначе %LOCALAPPDATA%': 'Game folder with ariane for the bridge (exchange via <folder>\\ariane\\bridge). Empty → uses Game Root, otherwise %LOCALAPPDATA%',
    'Переключение Импорт / Экспорт в панели IDE/IPL/IMG': 'Switch Import / Export in the IDE/IPL/IMG panel',
    'Переключение инструментов в панели Освещение': 'Switch tools in the Lighting panel',
    'При «Экспорт → Ariane» переносить и позицию/поворот объекта (двигает инстанс в ariane и авто-сохраняет IPL). Выкл = только геометрия/текстуры': 'On Export → Ariane also transfer the object position/rotation (moves the instance in ariane and auto-saves the IPL). Off = geometry/textures only',
    'Привязано к Ariane: {0} из {1} инстансов': 'Bound to Ariane: {0} of {1} instances',
    'Привязать к Ariane': 'Bind to Ariane',
    'Прилайт вершинными цветами': 'Prelight with vertex colors',
    'Размер текстуры в пикселях (для расчёта масштаба/текселя)': 'Texture size in pixels (for scale/texel calculation)',
    'Родной SA — как ванильный ghands.ifp': 'Native SA — like vanilla ghands.ifp',
    'Слать и LOD-модель (LOD<имя>) при «Экспорт → Ariane»': 'Also send the LOD model (LOD<name>) on Export → Ariane',
    'Слать коллизию (COL) при «Экспорт → Ariane» (live-перезагрузка коллизии в ariane). DFF и TXD шлются всегда': 'Send collision (COL) on Export → Ariane (live collision reload in ariane). DFF and TXD are always sent',
    'Слать назад IDE-свойства (draw distance) при Экспорт → Ariane. Меняет модель в ariane целиком (все инстансы). Выключено по умолчанию, чтобы случайно не переписать дальность у моделей без правок': 'Send IDE properties (draw distance) back on Export → Ariane. Changes the whole model in ariane (all instances). Off by default so you do not accidentally overwrite the distance of unmodified models',
    "Удалять keyframe'ы на линейной интерполяции между соседями. Уменьшает размер без потери качества — первый и последний ключ каждой кости сохраняются всегда": 'Remove keyframes on linear interpolation between neighbors. Reduces size without quality loss — the first and last key of each bone are always kept',
    'Целевой размер: для «В сетку» — сколько пикселей должна занимать высота(ряды)/ширина(колонки) острова; для текселя — плотность px на юнит': 'Target size: for To grid — how many pixels the island height(rows)/width(columns) should span; for texel — density in px per unit',
    "Что дописать к имени модели в имени файла. Например '_DEFAULT' → grozdom97_DEFAULT.png. Меняй под свою текстуру в TXD": "What to append to the model name in the file name. E.g. '_DEFAULT' → grozdom97_DEFAULT.png. Adjust to your texture in the TXD",
    'Тип узла на вершине': 'Junction type at vertex',
    'Стык': 'Mitre',
    'Лучи режут друг друга по середине между осями — узел закрывается без нахлёста': 'Arms cut each other halfway between axes — the junction closes with no overlap',
    'Полотна проходят насквозь, ничего не режется': 'Road surfaces pass straight through, nothing is cut',
    'Лучи режут друг друга по середине': 'Arms cut each other halfway',
    'Полотна проходят насквозь': 'Surfaces pass straight through',
    'Что происходит с полотнами в этой вершине': 'What happens to the road surfaces at this vertex',
    'Свои значения по вершинам': 'Per-vertex values',
    'Профиль не доходит до этой вершины на «Отступ у узла», а перекрёсток закрывает сплошная заливка полотна': 'The profile stops short of this vertex by the junction gap; the junction itself is covered by the solid road fill',
    'Профиль идёт через вершину насквозь, ничего не обрезается': 'The profile runs straight through the vertex, nothing is trimmed',
    'Профиль обрезан, узел закрыт заливкой': 'Profile trimmed, junction covered by the fill',
    'Профиль идёт насквозь': 'Profile runs straight through',
    'Отступ у узла': 'Junction gap',
    'На сколько метров сечение (бордюры, тротуары) не доходит до перекрёстка. Само полотно узел закрывает заливкой, а профиль в него упираться не должен. 0 — вести профиль до самого узла': 'How many metres the cross-section (curbs, sidewalks) stops short of a junction. The road surface covers the junction with a fill, so the profile must not run into it. 0 — carry the profile all the way in',

    # ── Тайм-циклы (timecyc.dat) ──
    'Тайм-циклы': 'Time cycles',
    'Правка среза': 'Edit time slot',
    'Настройки превью': 'Preview settings',
    'Панель тайм-циклов: timecyc.dat → освещение сцены и обратно.': 'Time-cycle panel: timecyc.dat → scene lighting and back.',
    'Правка одного временно́го среза выбранной погоды.': 'Editing a single time slot of the selected weather.',
    'Ручки превью: как значения среза ложатся на свет Blender.': 'Preview knobs: how the slot values map onto Blender lighting.',
    'Состояние вкладки «Тайм-циклы».': 'State of the Time cycles panel.',
    'Загрузить timecyc.dat и показать его освещение в сцене': 'Load timecyc.dat and show its lighting in the scene',
    'Записать timecyc.dat. Нетронутые строки сохраняются как есть, рядом кладётся .bak': 'Write timecyc.dat. Untouched lines are kept byte-for-byte, a .bak is left next to it',
    'Пересобрать освещение сцены по текущим погоде и часу': 'Rebuild the scene lighting from the current weather and hour',
    'Перевести вьюпорт в Material Preview со сценическим миром и светом': 'Switch the viewport to Material Preview with scene world and scene lights',
    'Вернуть текущий срез к значениям из файла': 'Revert the current time slot to the values from the file',
    'Перечитать файл с диска — все несохранённые правки пропадут': 'Re-read the file from disk — all unsaved edits are lost',
    'Скопировать текущий срез во все 8 срезов этой погоды': 'Copy the current time slot into all 8 slots of this weather',
    'Применить к сцене': 'Apply to scene',
    'Показать в вьюпорте': 'Show in viewport',
    'Откатить срез': 'Revert slot',
    'Перечитать файл': 'Re-read file',
    'Во все срезы погоды': 'To all slots of the weather',
    'Сохранить .bak': 'Keep .bak',
    'Положить рядом копию прежнего файла': 'Leave a copy of the previous file next to it',
    'Файл не найден: ': 'File not found: ',
    'Ошибка чтения timecyc: ': 'timecyc read error: ',
    'Ошибка записи timecyc: ': 'timecyc write error: ',
    'timecyc: погод %d, ширина строки %d': 'timecyc: %d weathers, row width %d',
    'timecyc не загружен': 'timecyc is not loaded',
    'timecyc записан, изменённых срезов: %d': 'timecyc written, changed slots: %d',
    'Не найден 3D-вьюпорт': 'No 3D viewport found',
    'Не удалось перечитать файл': 'Could not re-read the file',
    'Отброшено изменённых срезов: %d': 'Discarded changed slots: %d',
    'Срез размножен на всю погоду': 'The slot was copied across the whole weather',
    'Погода': 'Weather',
    'Срез': 'Time slot',
    'Время суток': 'Time of day',
    'Живое превью': 'Live preview',
    'Обновлять освещение сцены при каждом изменении': 'Update the scene lighting on every change',
    'Полночь': 'Midnight',
    'Раннее утро': 'Early morning',
    'Рассвет': 'Dawn',
    'Утро': 'Morning',
    'Полдень': 'Midday',
    'Вечер': 'Evening',
    'Закат': 'Sunset',
    'Яркость неба': 'Sky strength',
    'Сила ambient': 'Ambient strength',
    'Ambient объектов': 'Object ambient',
    'Брать Amb_Obj вместо Amb — как в игре светятся машины и педы, а не здания': 'Use Amb_Obj instead of Amb — the ambient the game applies to cars and peds, not buildings',
    'Резкость горизонта': 'Horizon sharpness',
    'На какой высоте небо доходит до цвета зенита': 'At what height the sky reaches the zenith colour',
    'Сила солнца': 'Sun strength',
    'Азимут': 'Azimuth',
    'Поворот дуги солнца вокруг сцены': "Rotation of the sun's arc around the scene",
    'Объёмный туман по дальности прорисовки. На большой карте заметно грузит вьюпорт': 'Volumetric fog driven by the draw distance. On a big map it noticeably slows the viewport',
    'Плотность тумана': 'Fog density',
    'Красить воду': 'Tint water',
    'Подставлять WaterRGBA в материал импортированной воды': 'Push WaterRGBA into the material of imported water',
    'Дальность вьюпорта': 'Viewport clip end',
    'Поднимать clip end вьюпорта до FarClp среза': "Raise the viewport clip end to the slot's FarClp",
    'Ambient (мир)': 'Ambient (world)',
    'Ambient (объекты)': 'Ambient (objects)',
    'Directional': 'Directional',
    'Небо: зенит': 'Sky: zenith',
    'Небо: горизонт': 'Sky: horizon',
    'Солнце: ядро': 'Sun: core',
    'Солнце: корона': 'Sun: corona',
    'Нижние облака': 'Low clouds',
    'Облака у горизонта': 'Clouds at horizon',
    'Вода: альфа': 'Water: alpha',
    'PostFX 1': 'PostFX 1',
    'PostFX 2': 'PostFX 2',
    'PostFX 1: альфа': 'PostFX 1: alpha',
    'PostFX 2: альфа': 'PostFX 2: alpha',
    'Размер солнца': 'Sun size',
    'Размер блика': 'Sprite size',
    'Яркость блика': 'Sprite brightness',
    'Тени от света': 'Light shadows',
    'Тени столбов': 'Pole shadows',
    'Дальность прорисовки': 'Draw distance',
    'Начало тумана': 'Fog start',
    'Свет на земле': 'Light on ground',
    'Прозрачность облаков': 'Cloud alpha',
    'Мин. яркость бликов': 'Min highlight intensity',
    'Туман под водой': 'Underwater fog',
    'Множитель directional': 'Directional multiplier',
    'Файл не загружен': 'No file loaded',
    'data/timecyc.dat из папки игры': 'data/timecyc.dat from the game folder',
    'Не сохранено срезов: %d': 'Unsaved slots: %d',
    'Между срезами': 'Between slots',
    'Срез недоступен': 'Slot unavailable',
    'Ambient (мир, Trails)': 'Ambient (world, Trails)',
    'Ambient (объекты, Trails)': 'Ambient (objects, Trails)',
    'Ambient мира (Trails)': 'World ambient (Trails)',
    'Ambient объектов (Trails)': 'Object ambient (Trails)',
    'Верхние облака': 'Top clouds',
    'Верхние': 'Top',
    'Тени деревьев': 'Tree shadows',
    'Trails / blur': 'Trails / blur',
    'Trails: альфа': 'Trails: alpha',
    'Trails (blur):': 'Trails (blur):',
    'timecyc: %s, погод %d, срезов %d, ширина строки %d': 'timecyc: %s, %d weathers, %d slots, row width %d',
    'timecyc.dat из {0}, а игра сцены — {1}': 'timecyc.dat is from {0}, but the scene game is {1}',
    'Строка короче схемы: %d из %d': 'Row shorter than the schema: %d of %d',
    'Поля читаются со сдвигом — как их видит игра': 'Fields are read shifted — exactly as the game sees them',
    'Небо и солнце:': 'Sky and sun:',
    'Зенит': 'Zenith',
    'Горизонт': 'Horizon',
    'Ядро солнца': 'Sun core',
    'Корона': 'Corona',
    'Свет и тени:': 'Light and shadows:',
    'Ambient мира': 'World ambient',
    'Множитель dir': 'Dir multiplier',
    'Мин. блики': 'Min highlights',
    'Туман и дальность:': 'Fog and distance:',
    'Дальность (FarClp)': 'Distance (FarClp)',
    'Облака:': 'Clouds:',
    'Нижние': 'Low',
    'У горизонта': 'At horizon',
    'Вода:': 'Water:',
    'PostFX:': 'PostFX:',
    'Слой 1': 'Layer 1',
    'Слой 2': 'Layer 2',
    'Альфа 1': 'Alpha 1',
    'Альфа 2': 'Alpha 2',
    'В вьюпорте не показывается': 'Not shown in the viewport',
    'Небо и ambient:': 'Sky and ambient:',
    'Туман': 'Fog',
    'Файл': 'File',
    'Время': 'Time',
    'Ambient отдельно от неба': 'Ambient separate from sky',
    'Небо остаётся фоном для камеры, а сцену освещает отдельный цвет Amb. Держится на Light Path — в EEVEE может сработать не так, как в Cycles': 'The sky stays the camera background while a separate Amb colour lights the scene. Relies on Light Path — EEVEE may treat it differently than Cycles',
    'Прилайт по времени суток': 'Prelight by time of day',
    'Смешивать вершинные цвета Day и Night по часам — как это делает игра. Работает на материалах, где включено превью прилайта': 'Blend the Day and Night vertex colours by the hour, the way the game does. Applies to materials where the prelight preview is on',
    'Закат: начало': 'Dusk: start',
    'Закат: конец': 'Dusk: end',
    'Рассвет: начало': 'Dawn: start',
    'Рассвет: конец': 'Dawn: end',
    'С какого часа прилайт начинает уходить в ночной': 'The hour at which the prelight starts turning into the night one',
    'К какому часу прилайт становится полностью ночным': 'The hour by which the prelight is fully the night one',
    'С какого часа ночной прилайт начинает уходить': 'The hour at which the night prelight starts fading out',
    'К какому часу прилайт становится полностью дневным': 'The hour by which the prelight is fully the day one',
    'Ночной вес: %.2f': 'Night weight: %.2f',
    'Прилайт Day/Night:': 'Day/Night prelight:',
    'Нет материалов с превью прилайта': 'No materials with the prelight preview',
    'Включите его в панели PreLight': 'Turn it on in the PreLight panel',
    'Как в игре (unlit)': 'Game look (unlit)',
    "Отдавать цвет прилайта напрямую, мимо PBR: игра рисует здания fixed-function'ом — без теней, бликов и подсветки от неба": 'Send the prelight colour straight out, bypassing PBR: the game draws buildings with the fixed-function pipeline — no shadows, no speculars, no sky tint',
    'Гасить цвет по расстоянию от FogSt до FarClp — той же фиксированной функцией, что и игра. Работает там же, где превью прилайта': 'Fade the colour by distance from FogSt to FarClp with the same fixed function the game uses. Works wherever the prelight preview does',
    'Directional-подсветка для машин, педов и объектов (Dir из среза). Здания в игре её не получают, и теней солнце не бросает': 'Directional light for cars, peds and objects (Dir from the slot). Buildings never get it in game, and the sun casts no shadows',
    'По FogSt → FarClp среза': "By the slot's FogSt → FarClp",
    'Для машин и объектов; теней в игре нет': 'For cars and objects; the game has no shadows',
    'Применить к моделям сцены': 'Apply to scene models',
    'Включить превью прилайта на всех мешах с вершинными цветами и привести их к игровому виду': 'Turn the prelight preview on for every mesh with vertex colours and bring them to the game look',
    'Не найдено мешей с вершинными цветами': 'No meshes with vertex colours found',
    'Игровой вид: моделей %d, материалов %d': 'Game look: %d models, %d materials',
    'Кривая тумана': 'Fog curve',
    '1 — честная линейка FogSt→FarClp, как у RW. Больше — дымка набирается ближе к горизонту, как выглядит кадр игры': '1 is the honest FogSt→FarClp ramp RW uses. Higher pushes the haze towards the horizon, closer to how the game frame looks',
    'Дальность тумана ×': 'Fog distance ×',
    'Растянуть обе дистанции. В игре на кадр влияет ещё и ползунок дальности прорисовки, которого в timecyc нет': 'Stretch both distances. In game the frame also depends on the draw-distance slider, which timecyc does not carry',
    'Туман: срез не загружен': 'Fog: no slot loaded',
    'Туман: %d → %d м': 'Fog: %d → %d m',
    'Нейтрально': 'Neutral',
    'Сбросить коррекцию превью в нейтраль — превью покажет прилайт ровно таким, каким он уйдёт в игру': 'Reset the preview correction to neutral — the preview then shows the prelight exactly as it will go into the game',
    'Только вьюпорт, на экспорт не влияет': 'Viewport only, does not affect export',
    'PostFX (цветофильтр)': 'PostFX (colour filter)',
    'Цветофильтр кадра из PostFX1/PostFX2 среза: out = in*(1 + rgb1*a1 + rgb2*a2). Именно он делает картинку игры светлее и цветнее значений timecyc': "The frame colour filter from the slot's PostFX1/PostFX2: out = in*(1 + rgb1*a1 + rgb2*a2). This is what makes the game frame lighter and more colourful than the raw timecyc values",
    'Множитель кадра: 1.00 / 1.00 / 1.00': 'Frame gain: 1.00 / 1.00 / 1.00',
    'Множитель кадра: %.2f / %.2f / %.2f': 'Frame gain: %.2f / %.2f / %.2f',
    'Экранные эффекты (композитор):': 'Screen effects (compositor):',
    'Нужен Compositor в шейдинге вьюпорта': 'Needs Compositor on in viewport shading',
    'Погод в файле: %d': 'Weathers in file: %d',
    'Не удалось применить срез — смотрите системную консоль': 'Could not apply the slot — see the system console',
    'Сбросить превью': 'Reset preview',
    'Убрать всё, что тайм-цикл добавил в сцену: вернуть материалы в PBR, снять игровой вид, вычистить ноды из композитора': 'Remove everything the time cycle added: materials back to PBR, game look off, our nodes out of the compositor',
    'Превью сброшено: материалов %d из %d': 'Preview reset: %d of %d materials',
    'Включить композитор': 'Enable compositor',
    'Включить композитор в вьюпорте — без него экранные туман и PostFX не считаются': 'Enable the compositor in the viewport — without it the screen-space fog and PostFX are not computed',
    'Не удалось включить — сделайте это в шейдинге вьюпорта (Compositor)': 'Could not enable it — do it in the viewport shading popover (Compositor)',
    'Композитор включён в вьюпортах: %d': 'Compositor enabled in %d viewports',
    'Композитор вьюпорта: вкл (%d из %d)': 'Viewport compositor: on (%d of %d)',
    'Композитор вьюпорта выключен — экранных эффектов не видно': 'Viewport compositor is off — screen effects are invisible',
    'Диагностика превью': 'Diagnose preview',
    'Напечатать в системную консоль полное состояние превью: цепочка композитора, значения, клип, пассы': 'Print the full preview state to the system console: compositor chain, values, clip, passes',
    'Диагностика напечатана в системную консоль': 'Diagnostics printed to the system console',
    'Порог неба (м)': 'Sky threshold (m)',
    'Дальше этой глубины туман не накладывается — там уже небо. 0 — считать автоматически по клипу вьюпорта; если небо всё равно заливается одним цветом, поставьте вручную (обычно 2–5 дальностей тумана)': 'Beyond this depth no fog is applied — that is already sky. 0 means auto from the viewport clip end; if the sky still floods with one colour, set it by hand (usually 2-5 fog distances)',
    # --- GTA Geo: заготовки Auto-Building ---
    'Примеры': 'Examples',
    'Выдели здание': 'Select a building',
    'Объектов:': 'Objects:',
    'Основание добавлено': 'Base added',
    'Притащить коллекцию примеров Auto-Building — готовые здания,\n    по которым видно, как размечены грани и что лежит в наборах': 'Bring in the Auto-Building examples collection — finished buildings that show how the faces are marked up and what goes into the kits',
    'Притащить Auto-Base — заготовку основания под здание': 'Bring in Auto-Base — a starter base for a building',
    # Export audits: skin/HAnim lint (core/skin_lint.py), IFP lint (core/ifp_lint.py), writer limits
    'Игра упадёт': 'Game will crash',
    'Игра упадёт — нет дамми': 'Game will crash — missing dummy',
    'Игра упадёт — скин': 'Game will crash — skin',
    'Игра упадёт — модель': 'Game will crash — model',
    'Скин': 'Skin',
    'Модель': 'Model',
    'Дамми машины': 'Vehicle dummy',
    'Игра упадёт — IFP': 'Game will crash — IFP',
    'имя фрейма «{0}» длиннее {1} символов — движок хранит имя в 24-байтовом слоте и упадёт при загрузке. Переименуй объект/кость.': 'frame name "{0}" is longer than {1} characters — the engine keeps the name in a 24-byte slot and crashes at load. Rename the object/bone.',
    'геометрия #{0}: {1} вершин — RenderWare хранит индексы треугольников в uint16 (максимум {2} вершин). Разбей меш на части или упрости (Decimate).': 'geometry #{0}: {1} vertices — RenderWare stores triangle indices as uint16 (max {2} vertices). Split the mesh or simplify it (Decimate).',
    '{0} / {1}, ключ {2}: компонент кватерниона {3} не влезает в int16 (|c| < 8.0). Нормализуй поворот.': '{0} / {1}, key {2}: quaternion component {3} does not fit int16 (|c| < 8.0). Normalise the rotation.',
    '{0} / {1}, ключ {2}: время {3:.2f} с = {4} тиков — больше {5} (uint16). Укороти анимацию.': '{0} / {1}, key {2}: time {3:.2f} s = {4} ticks — more than {5} (uint16). Shorten the animation.',
    '{0} / {1}, ключ {2}: смещение {3} не влезает в int16 (|v| < 32.0 единиц). Кость уехала слишком далеко.': '{0} / {1}, key {2}: translation {3} does not fit int16 (|v| < 32.0 units). The bone moved too far.',
    'нет таблицы узлов HAnim (numNodes > 0) ни на одном фрейме — движок пишет по нулевому указателю при загрузке (C01).': 'no HAnim node table (numNodes > 0) on any frame — the engine writes through a NULL pointer at load (C01).',
    'в клампе нет атомиков — CreateHitColModelSkinned обратится к NULL-иерархии (C02).': 'the clump has no atomics — CreateHitColModelSkinned dereferences a NULL hierarchy (C02).',
    'последний атомик файла (геометрия #{0}) без скина — движок берёт его как первый, иерархия не назначится, краш при загрузке (C02).': 'the last atomic in the file (geometry #{0}) has no skin — the engine treats it as the first one, no hierarchy gets assigned, crash at load (C02).',
    'HAnim «{0}»: флаг 0x2 (без матриц) — движок упадёт при загрузке (C03).': 'HAnim "{0}": flag 0x2 (no matrices) — the engine crashes at load (C03).',
    'HAnim «{0}»: размер ключа {1} < {2} — переполнение кучи при каждом спавне (C04).': 'HAnim "{0}": keyframe size {1} < {2} — heap overflow on every spawn (C04).',
    'HAnim «{0}»: {1} узлов — больше {2}, переполнение буфера матриц (C15).': 'HAnim "{0}": {1} nodes — more than {2}, matrix buffer overflow (C15).',
    'HAnim «{0}»: версия 0x{1:X} вместо 0x100 — RpClumpStreamRead вернёт NULL, модель не загрузится (C21).': 'HAnim "{0}": version 0x{1:X} instead of 0x100 — RpClumpStreamRead returns NULL, the model will not load (C21).',
    'таблица узлов HAnim есть на {0} фреймах ({1}) — движок использует первую найденную, остальные утекут (C26).': 'HAnim node table present on {0} frames ({1}) — the engine uses the first one found, the rest leak (C26).',
    'HAnim: таблица узлов лежит на корневом фрейме «{0}» — пед отрисуется в начале координат. Таблицу несёт первая кость (потомок корня) (C16).': 'HAnim: the node table sits on the clump root frame "{0}" — the ped renders at the world origin. The first bone (a child of the root) must carry it (C16).',
    'HAnim: id кости {0} повторяется (узлы {1} и {2}) — коллизия и анимация будут крутить разные копии (C18).': 'HAnim: bone id {0} is duplicated (nodes {1} and {2}) — collision and animation will drive different copies (C18).',
    'HAnim: узел {0} (id {1}) несёт индекс {2} — порядок узлов не совпадает с порядком матриц скина (C19).': 'HAnim: node {0} (id {1}) carries index {2} — node order does not match the skin matrix order (C19).',
    'HAnim: глубина push {0} на узле {1} — больше {2}, стек костей затрёт адрес возврата (C17).': 'HAnim: push depth {0} at node {1} — more than {2}, the bone stack overwrites the return address (C17).',
    'HAnim: узел {0} (id {1}) делает pop из пустого стека, а за ним ещё есть узлы — следующая кость получит мусорную родительскую матрицу (C17).': 'HAnim: node {0} (id {1}) pops an empty stack with nodes still to follow — the next bone gets a garbage parent matrix (C17).',
    'HAnim: нет костей с id {0} — движок обращается к ним на каждом педе (хит-сферы, тени, m_apBones) и пишет мимо массива матриц (C20).': 'HAnim: no bones with id {0} — the engine dereferences them on every ped (hit spheres, shadows, m_apBones) and writes past the matrix array (C20).',
    'HAnim: нет костей с id {0} — используются по условию (дождь, открытая машина, байк, пальцы, лицо); без них там будет мусор (C20).': 'HAnim: no bones with id {0} — used conditionally (rain, open-top car, bike, fingers, face); those paths will produce garbage without them (C20).',
    'геометрия #{0}: skin.num_bones = 0 — таблица костей нулевого размера, порча кучи при спавне (C07).': 'geometry #{0}: skin.num_bones = 0 — zero-sized bone table, heap corruption on spawn (C07).',
    'геометрия #{0}: {1} костей — больше {2}, переполнение стека при спавне (C05).': 'geometry #{0}: {1} bones — more than {2}, stack overflow on spawn (C05).',
    'геометрия #{0}: костей в скине {1}, а узлов в HAnim {2} — палитра и ключи читаются мимо массивов (C06).': 'geometry #{0}: {1} bones in the skin but {2} HAnim nodes — palette and keyframes are read past their arrays (C06).',
    'геометрия #{0}: матриц скина {1}, а num_bones = {2} — размер чанка не сойдётся с заголовком, модель не загрузится (C23).': 'geometry #{0}: {1} skin matrices but num_bones = {2} — chunk size will not match the header, the model will not load (C23).',
    'геометрия #{0}: веса заданы для {1}/{2} вершин, а вершин {3} — размер чанка не сойдётся с заголовком (C23).': 'geometry #{0}: weights given for {1}/{2} vertices but there are {3} — chunk size will not match the header (C23).',
    'геометрия #{0}: max_weights = {1} — допустимо 1..4 (0 переключает движок на старый формат, >4 ломает шейдер) (C11/C13).': 'geometry #{0}: max_weights = {1} — must be 1..4 (0 switches the engine to the old layout, >4 breaks the shader) (C11/C13).',
    'геометрия #{0}: список используемых костей пуст — палитра костей не загрузится, пед деформируется чужими матрицами (C11).': 'geometry #{0}: the used-bone list is empty — the bone palette is never uploaded, the ped deforms with another model\'s matrices (C11).',
    'геометрия #{0}: num_used = {1}, а в списке {2} костей — размер чанка не сойдётся (C23).': 'geometry #{0}: num_used = {1} but the list has {2} bones — chunk size will not match (C23).',
    'геометрия #{0}: {1} вершин без единого веса — движок делит 1/0 при нормализации, вершины станут NaN (C08).': 'geometry #{0}: {1} vertices with no weight at all — the engine divides 1/0 while normalising, those vertices become NaN (C08).',
    'геометрия #{0}: у {1} вершин сумма весов ≠ 1 — движок нормализует только последний атомик (C09).': 'geometry #{0}: {1} vertices whose weights do not sum to 1 — the engine only normalises the last atomic (C09).',
    'геометрия #{0}: {1} отрицательных весов — сортировка весов в движке сравнивает биты float (C09).': 'geometry #{0}: {1} negative weights — the engine sorts weights by comparing float bits (C09).',
    'геометрия #{0}: {1} весов NaN/inf (C09).': 'geometry #{0}: {1} NaN/inf weights (C09).',
    'геометрия #{0}: индексы костей {1} ≥ num_bones ({2}) — такие вершины прилипнут к кости 0 (C10).': 'geometry #{0}: bone indices {1} ≥ num_bones ({2}) — those vertices stick to bone 0 (C10).',
    'геометрия #{0}: кости {1} имеют веса, но не входят в список используемых — их матрица не загрузится в палитру и останется от предыдущей модели.': 'geometry #{0}: bones {1} carry weights but are missing from the used-bone list — their matrix is never uploaded and stays from the previous model.',
    'геометрия #{0}: матрица кости {1} содержит NaN/inf (C25).': 'geometry #{0}: bone matrix {1} contains NaN/inf (C25).',
    'геометрия #{0}: матрица кости {1} вырождена (det ≈ 0) — обратная даст мусорные смещения костей (C25).': 'geometry #{0}: bone matrix {1} is singular (det ≈ 0) — its inverse gives garbage bone offsets (C25).',
    'имя пакета «{0}» длиннее {1} символов — strncpy(16) обрежет его, блок не совпадёт с записью в IMG (IFP-11).': 'package name "{0}" is longer than {1} characters — strncpy(16) truncates it, the block will not match the IMG entry (IFP-11).',
    'имя пакета «{0}» не совпадает с именем файла «{1}» — игра заведёт второй блок, зарегистрированный по IMG останется пустым, AddAnimation упадёт (IFP-20).': 'package name "{0}" differs from the file name "{1}" — the game creates a second block, the one registered from the IMG stays empty, AddAnimation crashes (IFP-20).',
    'всего анимаций {0} + {1} > {2} — ms_aAnimations переполнится, анимация №2500 затрёт заголовок блока ped (IFP-22).': 'total animations {0} + {1} > {2} — ms_aAnimations overflows, animation #2500 overwrites the ped block header (IFP-22).',
    'анимация «{0}» повторяет «{1}» (имена сравниваются без регистра) — вторая недостижима (IFP-18).': 'animation "{0}" duplicates "{1}" (names compare case-insensitively) — the second one is unreachable (IFP-18).',
    'анимация «{0}»: имя длиннее {1} символов — в файл уйдёт обрезанное, по своему имени она не найдётся (IFP-11).': 'animation "{0}": name longer than {1} characters — it is written truncated and cannot be found by its own name (IFP-11).',
    'анимация «{0}» без единой кости — new[0] и чтение мимо массива при выгрузке (IFP-02).': 'animation "{0}" has no bones — new[0] and an out-of-bounds read on unload (IFP-02).',
    'анимация «{0}»: {1} костей — счётчик int16, максимум {2} (IFP-10).': 'animation "{0}": {1} bones — int16 counter, max {2} (IFP-10).',
    'анимация «{0}»: смешаны сжатые и несжатые кости — движок берёт класс по первой кости и читает остальные с неверным шагом (IFP-05).': 'animation "{0}": compressed and uncompressed bones are mixed — the engine takes the class from the first bone and reads the rest with the wrong stride (IFP-05).',
    'анимация «{0}»: кость «{1}» (id {2}) задана дважды — играть будет последняя (IFP-18).': 'animation "{0}": bone "{1}" (id {2}) is given twice — the last one plays (IFP-18).',
    'анимация «{0}»: имя кости «{1}» длиннее {2} символов — в файл уйдёт обрезанное (IFP-11).': 'animation "{0}": bone name "{1}" is longer than {2} characters — it is written truncated (IFP-11).',
    'анимация «{0}» / «{1}»: тип ключей {2} без поворота — такого типа кадра нет, поток рассинхронизируется (IFP-04).': 'animation "{0}" / "{1}": key type {2} without rotation — no such frame type exists, the stream desyncs (IFP-04).',
    'анимация «{0}» / «{1}»: 0 ключей — CalcTotalTime читает кадр -1 (IFP-01).': 'animation "{0}" / "{1}": 0 keys — CalcTotalTime reads frame -1 (IFP-01).',
    'анимация «{0}» / «{1}»: {2} ключей — счётчик int16, максимум {3} (IFP-10).': 'animation "{0}" / "{1}": {2} keys — int16 counter, max {3} (IFP-10).',
    'анимация «{0}»: ключи смещения на не-корневых костях ({1}) — наличие смещения заменяет bind-позицию кости (IFP-19).': 'animation "{0}": translation keys on non-root bones ({1}) — a translation track replaces the bone\'s bind position (IFP-19).',
    'анимация «{0}»: ключи масштаба ({1}) — движок их читает и выбрасывает; ANP3 их не хранит (IFP-21).': 'animation "{0}": scale keys ({1}) — the engine reads and discards them; ANP3 cannot store them (IFP-21).',
    '{0} / {1}: первый ключ на {2:.3f} с, а не на 0 — движок никогда не конвертирует нулевой кадр и добавляет его время на каждом витке цикла (IFP-06).': '{0} / {1}: first key at {2:.3f} s, not 0 — the engine never converts frame 0 and adds its time on every loop wrap (IFP-06).',
    '{0} / {1}: время ключей убывает ({2:.3f} с после {3:.3f} с) — отрицательная дельта, зацикленная анимация повесит игру (IFP-07).': '{0} / {1}: key times decrease ({2:.3f} s after {3:.3f} s) — negative delta, a looping animation hangs the game (IFP-07).',
    '{0} / {1}: все {2} ключей на одном времени — нулевая длительность, зацикленная анимация повесит игру (IFP-07).': '{0} / {1}: all {2} keys at the same time — zero duration, a looping animation hangs the game (IFP-07).',
    '{0} / {1}: {2} пар ключей на одном тике — схлопнутся в скачок (IFP-08).': '{0} / {1}: {2} key pairs on the same tick — they collapse into a jump (IFP-08).',
    '{0} / {1}: последний ключ на {2:.1f} с — больше {3:.1f} с, тик int16 переполнится и время станет отрицательным (IFP-09).': '{0} / {1}: last key at {2:.1f} s — more than {3:.1f} s, the int16 tick overflows and the time goes negative (IFP-09).',
    '{0} / {1}: кватернион с NaN/inf — матрица кости станет NaN, меш исчезнет (IFP-16).': '{0} / {1}: quaternion with NaN/inf — the bone matrix becomes NaN, the mesh vanishes (IFP-16).',
    '{0} / {1}: смещение с NaN/inf (IFP-16).': '{0} / {1}: translation with NaN/inf (IFP-16).',
    '{0} / {1}: {2} ключей с компонентом кватерниона ≥ 8 — int16/4096 переполнится (IFP-09).': '{0} / {1}: {2} keys with a quaternion component ≥ 8 — int16/4096 overflows (IFP-09).',
    '{0} / {1}: {2} ключей со смещением ≥ 32 единиц — int16/1024 переполнится, кость прыгнет (IFP-09).': '{0} / {1}: {2} keys with a translation ≥ 32 units — int16/1024 overflows, the bone jumps (IFP-09).',
    '{0} / {1}: {2} ненормированных кватернионов (|q| ≠ 1 ± 0.005) — slerp смешает с неверными весами (IFP-16).': '{0} / {1}: {2} non-unit quaternions (|q| ≠ 1 ± 0.005) — slerp blends with wrong weights (IFP-16).',
    # Export audits: map DFF lint (core/mapdff_lint.py), COL lint (core/col_lint.py), TXD lint (core/txd_lint.py), writer fixes W1/W2/W8/W11..W14
    '2DFX: имя {0} «{1}» длиннее {2} символов — обрезано до «{3}» (24-байтовое поле с NUL).': '2DFX: {0} name "{1}" is longer than {2} characters — cut to "{3}" (24-byte field incl. NUL).',
    '2DFX: эффект типа {0} неизвестен целевой игре — движок не умеет его пропустить, запись убрана из экспорта.': '2DFX: effect type {0} is unknown to the target game — the engine cannot skip it, the entry was dropped from the export.',
    'имя текстуры «{0}» длиннее {1} символов — TXD хранит 31 символ, материал не найдёт свою текстуру. Переименуй текстуру.': 'texture name "{0}" is longer than {1} characters — the TXD keeps 31, the material will never find its texture. Rename the texture.',
    'ночных цветов {0}, а вершин {1} — список выровнен по числу вершин (движок читает ровно numVertices×4 байта).': '{0} night colours for {1} vertices — the list was padded/cut to the vertex count (the engine reads exactly numVertices×4 bytes).',
    'COL: модель «{0}» (#{1}) обрезана или повреждена ({2}) — чтение остановлено на ней, как это делает движок.': 'COL: model "{0}" (#{1}) is truncated or corrupt ({2}) — reading stopped there, as the engine does.',
    'в клампе нет фреймов — RpClumpStreamRead возьмёт кадр из пустого массива, краш при загрузке (DFF-03).': 'the clump has no frames — RpClumpStreamRead takes a frame from an empty array, crash at load (DFF-03).',
    'в клампе нет атомиков — модель objs никогда не загрузится, а anim-модель уронит игру при первом размещении (DFF-03/DFF-40).': 'the clump has no atomics — an objs model never loads and an anim model crashes the game on first placement (DFF-03/DFF-40).',
    '{0} обычных атомиков ({1}) — для objs/tobj движок берёт только первый в файле, остальные не рисуются и их 2DFX теряются; это нормально лишь для anim-моделей (DFF-27).': '{0} plain atomics ({1}) — for objs/tobj the engine keeps only the first in the file, the others are never drawn and their 2DFX are lost; fine only for anim models (DFF-27).',
    'геометрия #{0}: нет материалов при {1} треугольниках — _rpMaterialListGetMaterial разыменует NULL, краш при загрузке (DFF-14).': 'geometry #{0}: no materials with {1} triangles — _rpMaterialListGetMaterial dereferences NULL, crash at load (DFF-14).',
    'геометрия #{0}: {1} вершин — RpGeometryCreate отказывает от 65536, модель не загрузится (DFF-09). Разбей меш.': 'geometry #{0}: {1} vertices — RpGeometryCreate refuses 65536 and up, the model never loads (DFF-09). Split the mesh.',
    'геометрия #{0}: {1} вершин / {2} треугольников — пустая геометрия ничего не рисует, поведение DN-пайплайна на ней не проверено (DFF-26).': 'geometry #{0}: {1} vertices / {2} triangles — an empty geometry draws nothing and the DN pipeline is unverified on it (DFF-26).',
    'геометрия #{0}: {1} UV-слоёв — больше 8 затирают указатели RpGeometry, краш при загрузке (DFF-11).': 'geometry #{0}: {1} UV layers — more than 8 overwrite RpGeometry pointers, crash at load (DFF-11).',
    'геометрия #{0}: флаг NATIVE (0x01000000) на PC-геометрии — вершины читаются в NULL, краш при загрузке (DFF-12).': 'geometry #{0}: NATIVE flag (0x01000000) on a PC geometry — vertices are read into NULL, crash at load (DFF-12).',
    'геометрия #{0}: prelight-цветов {1}, а вершин {2} — поток рассинхронизируется, модель не загрузится (DFF-13).': 'geometry #{0}: {1} prelight colours for {2} vertices — the stream desynchronises, the model never loads (DFF-13).',
    'геометрия #{0}: нормалей {1}, а вершин {2} — поток рассинхронизируется, модель не загрузится (DFF-13).': 'geometry #{0}: {1} normals for {2} vertices — the stream desynchronises, the model never loads (DFF-13).',
    'геометрия #{0}: {1} треугольников ссылаются на вершины вне 0..{2} — индексы выходят за вершинный буфер (DFF-23).': 'geometry #{0}: {1} triangles reference vertices outside 0..{2} — indices run past the vertex buffer (DFF-23).',
    'геометрия #{0}: {1} треугольников ссылаются на материал вне 0..{2} — мусорный указатель материала, краш при загрузке/отрисовке (DFF-20/DFF-21).': 'geometry #{0}: {1} triangles reference a material outside 0..{2} — garbage material pointer, crash at load/render (DFF-20/DFF-21).',
    'геометрия #{0}: pipeline 0x{1:X} неизвестен движку — атомик останется на стандартном RW-пайплайне без шейдера зданий (DFF-08).': 'geometry #{0}: pipeline 0x{1:X} is unknown to the engine — the atomic stays on the stock RW pipeline without the building shader (DFF-08).',
    'геометрия #{0}: breakable — UV ({1}) / цветов ({2}) не по числу вершин ({3}), движок прочитает мусор (DFF-60).': 'geometry #{0}: breakable — UVs ({1}) / colours ({2}) do not match the vertex count ({3}), the engine reads garbage (DFF-60).',
    'геометрия #{0}: breakable — материалов треугольников {1} при {2} треугольниках (DFF-60).': 'geometry #{0}: breakable — {1} triangle materials for {2} triangles (DFF-60).',
    'геометрия #{0}: breakable — треугольник ссылается на вершину вне 0..{1}, краш при разрушении (DFF-60).': 'geometry #{0}: breakable — a triangle references a vertex outside 0..{1}, crash when the object breaks (DFF-60).',
    'геометрия #{0}: breakable — треугольник ссылается на материал вне 0..{1}, краш при разрушении (DFF-60).': 'geometry #{0}: breakable — a triangle references a material outside 0..{1}, crash when the object breaks (DFF-60).',
    'геометрия #{0}: breakable — масок/цветов не по числу материалов ({1}), недостающие будут дописаны пустыми (DFF-60).': 'geometry #{0}: breakable — masks/colours do not match the material count ({1}), missing ones are written empty (DFF-60).',
    'имя модели «{0}» длиннее {1} символов — IDE/IMG держат 23 + NUL, LoadObject переполнит стек (DFF-70).': 'model name "{0}" is longer than {1} characters — IDE/IMG hold 23 + NUL, LoadObject overflows the stack (DFF-70).',
    '{0} 2DFX-эффектов на модель — счётчик в model-info байтовый, лишние потеряются или прочитаются не из того слота (DFF-33).': '{0} 2DFX effects on one model — the model-info counter is a byte, extra effects are lost or read from the wrong slot (DFF-33).',
    'фрейм {0} «{1}»: родитель {2} идёт не раньше него — RwFrameAddChild получит мусорный указатель, краш при загрузке (DFF-06).': 'frame {0} "{1}": parent {2} does not precede it — RwFrameAddChild gets a garbage pointer, crash at load (DFF-06).',
    'атомик {0}: индекс фрейма {1} вне 0..{2} — движок читает указатель за массивом фреймов, краш при загрузке (DFF-05).': 'atomic {0}: frame index {1} outside 0..{2} — the engine reads a pointer past the frame array, crash at load (DFF-05).',
    'атомик {0}: индекс геометрии {1} вне 0..{2} — RpGeometryAddRef по мусорному указателю, краш при загрузке (DFF-07).': 'atomic {0}: geometry index {1} outside 0..{2} — RpGeometryAddRef on a garbage pointer, crash at load (DFF-07).',
    'атомик {0}: нет флага rpATOMICRENDER (4) — в anim-модели такой атомик не рисуется (DFF-41).': 'atomic {0}: no rpATOMICRENDER flag (4) — in an anim model such an atomic is never drawn (DFF-41).',
    'атомик «{0}» с суффиксом _dam — у модели в IDE обязан стоять флаг 0x1000 (damageable), иначе SetDamagedAtomic пишет по NULL и игра падает (DFF-28).': 'atomic "{0}" with the _dam suffix — the model\'s IDE line must carry flag 0x1000 (damageable), otherwise SetDamagedAtomic writes through NULL and the game crashes (DFF-28).',
    'фрейм атомика «{0}» несёт запечённый поворот/масштаб — для objs-модели движок его отбрасывает (ориентация берётся из IPL) (DFF-29).': 'the atomic\'s frame "{0}" carries a baked rotation/scale — for an objs model the engine discards it (orientation comes from the IPL) (DFF-29).',
    'геометрия #{0}, материал {1}: чёрный цвет материала при флаге Modulate — prelight × 0, модель будет чёрной (DFF-46).': 'geometry #{0}, material {1}: black material colour with the Modulate flag — prelight × 0, the model renders black (DFF-46).',
    'геометрия #{0}: {1} UV-слоёв — пайплайны SA используют не больше 2, остальные балласт (DFF-11).': 'geometry #{0}: {1} UV layers — the SA pipelines use at most 2, the rest is dead weight (DFF-11).',
    'геометрия #{0}: UV-слой {1} содержит {2} координат при {3} вершинах — поток рассинхронизируется, модель не загрузится (DFF-13).': 'geometry #{0}: UV layer {1} holds {2} coordinates for {3} vertices — the stream desynchronises, the model never loads (DFF-13).',
    'геометрия #{0}: радиус ограничивающей сферы {1} — движок считает её «всегда в кадре» и отключает клиппинг, треугольники у камеры порвёт (DFF-25).': 'geometry #{0}: bounding sphere radius {1} — the engine treats it as "always in view" and disables clipping, triangles near the camera tear (DFF-25).',
    'геометрия #{0}: ночные цвета без дневных (prelight) — дневной буфер остаётся неинициализированным, днём модель будет случайного цвета (DFF-43).': 'geometry #{0}: night colours without day colours (prelight) — the day buffer stays uninitialised, the model shows random colours by day (DFF-43).',
    'геометрия #{0}: ночных цветов {1}, а вершин {2} — при экспорте список выровняют по числу вершин (DFF-45/W14).': 'geometry #{0}: {1} night colours for {2} vertices — the export pads/cuts the list to the vertex count (DFF-45/W14).',
    'геометрия #{0}, 2DFX #{1}: тип {2} неизвестен целевой игре — движок не умеет его пропустить, при экспорте запись убирается (DFF-32/W12).': 'geometry #{0}, 2DFX #{1}: type {2} is unknown to the target game — the engine cannot skip it, the export drops the entry (DFF-32/W12).',
    'геометрия #{0}: breakable — имя текстуры «{1}» длиннее {2} символов, не совпадёт с TXD (DFF-60/W8).': 'geometry #{0}: breakable — texture name "{1}" is longer than {2} characters, it will not match the TXD (DFF-60/W8).',
    'геометрия #{0}, материал {1}: имя текстуры «{2}» длиннее {3} символов — TXD хранит 31, текстура никогда не найдётся (DFF-19/W8).': 'geometry #{0}, material {1}: texture name "{2}" is longer than {3} characters — the TXD keeps 31, the texture is never found (DFF-19/W8).',
    'геометрия #{0}, материал {1}: имя текстуры «{2}» не ASCII — запишется с «?» и не совпадёт с TXD (DFF-19).': 'geometry #{0}, material {1}: texture name "{2}" is not ASCII — written with "?" and will not match the TXD (DFF-19).',
    'геометрия #{0}, материал {1}: имя маски «{2}» длиннее {3} символов — будет обрезано движком (DFF-19).': 'geometry #{0}, material {1}: mask name "{2}" is longer than {3} characters — the engine truncates it (DFF-19).',
    'геометрия #{0}, материал {1}: {2} UV-анимаций — движок читает не больше {3}, лишние имена рассинхронизируют поток, модель не загрузится (DFF-54).': 'geometry #{0}, material {1}: {2} UV animations — the engine reads at most {3}, the extra names desynchronise the stream, the model never loads (DFF-54).',
    'геометрия #{0}: ограничивающая сфера (r={1:.3f}) не накрывает вершины (самая дальняя на {2:.3f}) — клиппинг у камеры отключится раньше времени (DFF-25).': 'geometry #{0}: the bounding sphere (r={1:.3f}) does not enclose the vertices (farthest at {2:.3f}) — clipping near the camera switches off too early (DFF-25).',
    'геометрия #{0}, 2DFX #{1}: эффект в {2:.1f} м от центра модели (сфера r={3:.1f}) — вероятно, не то положение; отсечётся вместе с моделью (DFF-39).': 'geometry #{0}, 2DFX #{1}: effect {2:.1f} m from the model centre (sphere r={3:.1f}) — probably misplaced; it is culled with the model (DFF-39).',
    'геометрия #{0}, материал {1}: текстура с пустым именем — RwTextureRead вернёт NULL, материал отрисуется без текстуры (DFF-19).': 'geometry #{0}, material {1}: texture with an empty name — RwTextureRead returns NULL, the material renders untextured (DFF-19).',
    'геометрия #{0}, материал {1}: имя UV-анимации «{2}» длиннее {3} символов — 32-байтовое поле без NUL (DFF-54).': 'geometry #{0}, material {1}: UV animation name "{2}" is longer than {3} characters — 32-byte field without a NUL (DFF-54).',
    'геометрия #{0}, 2DFX #{1}: у света есть тень (shadow_size={2}), но нет текстуры тени — RenderStaticShadows разыменует NULL, краш при отрисовке (DFF-34).': 'geometry #{0}, 2DFX #{1}: the light casts a shadow (shadow_size={2}) but has no shadow texture — RenderStaticShadows dereferences NULL, crash at render (DFF-34).',
    'геометрия #{0}, 2DFX #{1}: у света нет текстуры короны — корона не отрисуется (DFF-34).': 'geometry #{0}, 2DFX #{1}: the light has no corona texture — the corona is never drawn (DFF-34).',
    'геометрия #{0}, 2DFX #{1}: у света не стоит ни «днём», ни «ночью» — он никогда не включится (DFF-35).': 'geometry #{0}, 2DFX #{1}: the light has neither "at day" nor "at night" set — it never switches on (DFF-35).',
    'геометрия #{0}, 2DFX #{1}: режим короны {2} > {3} — свет никогда не включится (DFF-35).': 'geometry #{0}, 2DFX #{1}: corona mode {2} > {3} — the light never switches on (DFF-35).',
    'геометрия #{0}, 2DFX #{1}: отрицательный размер/дальность света — движок не проверяет, будет мусор (DFF-35).': 'geometry #{0}, 2DFX #{1}: negative light size/range — the engine does not check it, garbage (DFF-35).',
    'геометрия #{0}, материал {1}: UV-анимация «{2}» отсутствует в словаре — движок подставит статичную (DFF-51).': 'geometry #{0}, material {1}: UV animation "{2}" is missing from the dictionary — the engine substitutes a static one (DFF-51).',
    'геометрия #{0}, 2DFX #{1}: имя {2} «{3}» длиннее {4} символов — при экспорте обрежется (DFF-34/W13).': 'geometry #{0}, 2DFX #{1}: {2} name "{3}" is longer than {4} characters — the export truncates it (DFF-34/W13).',
    'геометрия #{0}, 2DFX #{1}: у частиц пустое имя системы — эффект не создастся (DFF-36).': 'geometry #{0}, 2DFX #{1}: the particle has an empty system name — the effect is never created (DFF-36).',
    'геометрия #{0}, 2DFX #{1}: имя скрипта аттрактора «{2}» длиннее 8 символов — обрежется (DFF-38).': 'geometry #{0}, 2DFX #{1}: attractor script name "{2}" is longer than 8 characters — truncated (DFF-38).',
    'геометрия #{0}, 2DFX #{1}: имя интерьера «{2}» длиннее 8 символов — обрежется (DFF-38).': 'geometry #{0}, 2DFX #{1}: interior name "{2}" is longer than 8 characters — truncated (DFF-38).',
    'геометрия #{0}, 2DFX #{1}: у знака больше 4 строк или строка длиннее 16 символов — обрежется (DFF-38).': 'geometry #{0}, 2DFX #{1}: the sign has more than 4 lines or a line longer than 16 characters — truncated (DFF-38).',
    'геометрия #{0}, 2DFX #{1}: запись типа {2} занимает {3} байт вместо {4} — движок её пропустит (DFF-32).': 'geometry #{0}, 2DFX #{1}: a type {2} entry takes {3} bytes instead of {4} — the engine skips it (DFF-32).',
    'COL без имени — запись не сопоставится ни с одной моделью из IDE (COL-25).': 'COL without a name — the entry matches no IDE model (COL-25).',
    'COL «{0}»: имя длиннее {1} символов — в 22-байтовом поле не остаётся NUL, движок хэширует мусор и модель не находит свою коллизию (COL-03).': 'COL "{0}": name longer than {1} characters — no room for the NUL in the 22-byte field, the engine hashes garbage and the model never finds its collision (COL-03).',
    'COL «{0}»: {1} треугольников — движок хранит счётчик как int16, от 32768 все треугольники игнорируются, а с face-группами игра падает (COL-11).': 'COL "{0}": {1} triangles — the engine keeps the count as int16, from 32768 every triangle is ignored and with face groups the game crashes (COL-11).',
    'COL «{0}»: {1} вершин — индексы u16, геометрия за 65536-й вершиной недостижима (COL-10).': 'COL "{0}": {1} vertices — indices are u16, geometry past the 65536th vertex is unreachable (COL-10).',
    'COL «{0}»: {1} треугольников ссылаются на вершины вне 0..{2} — плоскости читаются из чужой памяти (COL-09).': 'COL "{0}": {1} triangles reference vertices outside 0..{2} — planes are read from foreign memory (COL-09).',
    'COL «{0}»: surface id {1} > {2} — таблица поверхностей на 179 строк, трение/звук/частицы прочитаются из чужой памяти (COL-18).': 'COL "{0}": surface id {1} > {2} — the surface table has 179 rows, friction/sound/particles are read from foreign memory (COL-18).',
    'COL «{0}»: {1} поверхностей с id вне таблицы {2} — в файл записан 0 (COL-18).': 'COL "{0}": {1} surfaces with an id outside the {2} table — written to the file as 0 (COL-18).',
    'COL «{0}»: face-группы без треугольников — при экспорте не запишутся (COL-15).': 'COL "{0}": face groups without triangles — they are not written (COL-15).',
    'COL «{0}»: {1} треугольников не входят ни в одну face-группу — они не сталкиваются с движущимися объектами (COL-16).': 'COL "{0}": {1} triangles belong to no face group — they never collide with moving entities (COL-16).',
    'COL «{0}»: радиус ограничивающей сферы {1} — движок отсекает по ней и модель, и коллизию: объект исчезнет (COL-23).': 'COL "{0}": bounding sphere radius {1} — the engine culls both the model and its collision by it: the object disappears (COL-23).',
    'COL «{0}»: {1} точек коллизии вне ограничивающего бокса — объект попадёт не во все секторы мира, часть коллизии не сработает (COL-23).': 'COL "{0}": {1} collision points outside the bounding box — the object misses some world sectors, part of the collision never fires (COL-23).',
    'COL «{0}»: {1} точек коллизии вне ограничивающей сферы — по ней отсекается и видимая модель, и широкая фаза столкновений (COL-23).': 'COL "{0}": {1} collision points outside the bounding sphere — it culls both the visible model and the collision broad phase (COL-23).',
    'COL «{0}»: {1} {2} — счётчик читается как int16, примитивы пропадут или парсер собьётся (COL-12).': 'COL "{0}": {1} {2} — the count is read as int16, primitives vanish or the parser derails (COL-12).',
    'COL «{0}»: координата вершины {1:.2f} за пределом ±{2} — int16/128 переполняется, грань уедет на 512 м (COL-13). Держи коллизию в 255 м от начала модели.': 'COL "{0}": vertex coordinate {1:.2f} beyond ±{2} — int16/128 overflows, the face jumps 512 m (COL-13). Keep the collision within 255 m of the model origin.',
    'COL «{0}»: расстояние плоскости грани {1:.1f} ≥ {2} — int16 переполняется, тесты линий/сфер промахнутся (COL-14). Сдвинь коллизию ближе к началу модели.': 'COL "{0}": face plane distance {1:.1f} ≥ {2} — int16 overflows, line/sphere tests miss (COL-14). Move the collision closer to the model origin.',
    'COL «{0}»: {1} shadow-треугольников без shadow-вершин (COL-22).': 'COL "{0}": {1} shadow triangles without shadow vertices (COL-22).',
    'COL «{0}»: {1} shadow-вершин без shadow-треугольников — тень не запишется (COL-21).': 'COL "{0}": {1} shadow vertices without shadow triangles — the shadow is not written (COL-21).',
    'COL «{0}»: face-группа {1} охватывает {2}..{3} при {4} треугольниках — движок читает треугольники и плоскости за массивом (COL-16).': 'COL "{0}": face group {1} spans {2}..{3} with {4} triangles — the engine reads triangles and planes past the arrays (COL-16).',
    'COL «{0}»: face-группа {1}: first {2} > last {3} — группа пропускается (COL-16).': 'COL "{0}": face group {1}: first {2} > last {3} — the group is skipped (COL-16).',
    'COL «{0}»: face-группа {1}: {2} треугольников торчат из её бокса — с ними не столкнутся машины и педы (COL-17).': 'COL "{0}": face group {1}: {2} triangles stick out of its box — cars and peds never collide with them (COL-17).',
    'COL «{0}»: имя повторяется (записи {1} и {2}) — движок выделит вторую CColModel и потеряет одну из коллизий при выгрузке (COL-24).': 'COL "{0}": duplicate name (entries {1} and {2}) — the engine allocates a second CColModel and loses one collision on unload (COL-24).',
    'COL «{0}»: координата вершины {1:.2f} — у самой границы ±{2} (COL-13).': 'COL "{0}": vertex coordinate {1:.2f} — right at the ±{2} limit (COL-13).',
    'COL «{0}»: {1} shadow-треугольников ссылаются на вершины вне 0..{2} (COL-22).': 'COL "{0}": {1} shadow triangles reference vertices outside 0..{2} (COL-22).',
    'TXD: за заголовком словаря нет STRUCT (TXD-STRUCTLEN).': 'TXD: no STRUCT after the dictionary header (TXD-STRUCTLEN).',
    'TXD: файл короче заголовка чанка (TXD-STRUCTLEN).': 'TXD: the file is shorter than a chunk header (TXD-STRUCTLEN).',
    'TXD: нет STRUCT словаря (TXD-STRUCTLEN).': 'TXD: no dictionary STRUCT (TXD-STRUCTLEN).',
    'TXD, текстура {0}: platform {1} вместо {2} — _rwD3D9NativeTextureRead вернёт 0, словарь не загрузится (TXD-PLATFORM).': 'TXD, texture {0}: platform {1} instead of {2} — _rwD3D9NativeTextureRead returns 0, the dictionary never loads (TXD-PLATFORM).',
    'TXD, текстура {0}: пустое имя — ни один материал её не найдёт (TXD-NAME-LEN).': 'TXD, texture {0}: empty name — no material can find it (TXD-NAME-LEN).',
    'TXD, текстура {0}: имя маски длиннее {1} символов — обрежется (TXD-MASK).': 'TXD, texture {0}: mask name longer than {1} characters — truncated (TXD-MASK).',
    'TXD, текстура {0}: имя повторяет текстуру #{1} — движок берёт последнюю в файле, обе остаются в памяти (TXD-NAME-DUP).': 'TXD, texture {0}: same name as texture #{1} — the engine uses the last one in the file, both stay in memory (TXD-NAME-DUP).',
    'TXD, текстура {0}: фильтр {1} вне 1..6 — SetSamplerState получит мусор из таблицы (TXD-FILTER).': 'TXD, texture {0}: filter {1} outside 1..6 — SetSamplerState gets garbage from the table (TXD-FILTER).',
    'TXD, текстура {0}: адресация UV {1}/{2} вне 1..4 — SetSamplerState получит мусор из таблицы (TXD-FILTER).': 'TXD, texture {0}: UV addressing {1}/{2} outside 1..4 — SetSamplerState gets garbage from the table (TXD-FILTER).',
    'TXD, текстура {0}: размер {1}×{2} — растр без D3D-текстуры, RwRasterLock разыменует NULL (TXD-ZERO-DIM).': 'TXD, texture {0}: size {1}×{2} — a raster without a D3D texture, RwRasterLock dereferences NULL (TXD-ZERO-DIM).',
    'TXD, текстура {0}: палитровый формат (PAL4/PAL8) — D3DFMT_P8 не поддерживает ни один современный драйвер, словарь не загрузится (TXD-PALETTE).': 'TXD, texture {0}: palettised format (PAL4/PAL8) — no modern driver supports D3DFMT_P8, the dictionary never loads (TXD-PALETTE).',
    'TXD, текстура {0}: автогенерация мипов (0x1000 / флаг 4) — читается один уровень, остальные байты ломают поток (TXD-AUTOMIP).': 'TXD, texture {0}: auto mipmaps (0x1000 / flag 4) — only one level is read, the remaining bytes break the stream (TXD-AUTOMIP).',
    'TXD, текстура {0}: флаг cube map — несжатые кубы не грузятся вовсе, сжатые ждут 6 граней (TXD-CUBE).': 'TXD, texture {0}: cube map flag — uncompressed cubes never load, compressed ones expect 6 faces (TXD-CUBE).',
    'TXD, текстура {0}: rasterFormat 0x{1:X} содержит лишние биты — сравнение с растром не сойдётся, словарь не загрузится (TXD-FORMAT-MISMATCH).': 'TXD, texture {0}: rasterFormat 0x{1:X} carries stray bits — the raster compare fails, the dictionary never loads (TXD-FORMAT-MISMATCH).',
    'TXD, текстура {0}: флаг compressed={1}, а d3dFormat 0x{2:X} {3} DXT — форматы противоречат, словарь не загрузится (TXD-FORMAT-MISMATCH).': 'TXD, texture {0}: compressed flag={1} but d3dFormat 0x{2:X} {3} DXT — the formats contradict, the dictionary never loads (TXD-FORMAT-MISMATCH).',
    'TXD, текстура {0}: {1} мип-уровней при {2} у D3D-текстуры — RwRasterLock лишнего уровня вернёт NULL, RwStreamRead в 0 (TXD-NUMLEVELS-OVER).': 'TXD, texture {0}: {1} mip levels while the D3D texture has {2} — RwRasterLock on the extra level returns NULL, RwStreamRead into 0 (TXD-NUMLEVELS-OVER).',
    'TXD, текстура {0}: уровни {1} короче поверхности — хвост уровня остаётся мусором/чужой текстурой (TXD-LEVEL-SHORT).': 'TXD, texture {0}: levels {1} are shorter than the surface — the tail of the level stays garbage / another texture (TXD-LEVEL-SHORT).',
    'TXD, текстура {0}: после последнего уровня в STRUCT остаётся {1} байт — следующий FindChunk прочитает их как заголовок, словарь не загрузится (TXD-STRUCT-TRAILING).': 'TXD, texture {0}: {1} bytes remain in the STRUCT after the last level — the next FindChunk parses them as a header, the dictionary never loads (TXD-STRUCT-TRAILING).',
    'TXD: первый чанк 0x{0:X}, а не Texture Dictionary (0x16) — словарь не загрузится (TXD-VERSION).': 'TXD: first chunk is 0x{0:X}, not Texture Dictionary (0x16) — the dictionary never loads (TXD-VERSION).',
    'TXD: версия RW 0x{0:X} вне {1} — чанк отвергается, словарь не загрузится (TXD-VERSION).': 'TXD: RW version 0x{0:X} outside {1} — the chunk is rejected, the dictionary never loads (TXD-VERSION).',
    'TXD: в заголовке {0} текстур, в файле {1} — FindChunk упрётся в конец файла, словарь не загрузится (TXD-COUNT).': 'TXD: header says {0} textures, the file has {1} — FindChunk hits the end of file, the dictionary never loads (TXD-COUNT).',
    'TXD, текстура {0}: за заголовком Texture Native нет STRUCT — RwStreamFindChunk уйдёт в конец файла, словарь не загрузится (TXD-STRUCT-TRAILING).': 'TXD, texture {0}: no STRUCT after the Texture Native header — RwStreamFindChunk runs to the end of file, the dictionary never loads (TXD-STRUCT-TRAILING).',
    'TXD, текстура {0}: версия RW 0x{1:X} вне {2} — чанк отвергается, словарь не загрузится (TXD-VERSION).': 'TXD, texture {0}: RW version 0x{1:X} outside {2} — the chunk is rejected, the dictionary never loads (TXD-VERSION).',
    'TXD, текстура {0}: STRUCT длиной {1} байт короче заголовка растра — словарь не загрузится (TXD-STRUCT-TRAILING).': 'TXD, texture {0}: STRUCT of {1} bytes is shorter than the raster header — the dictionary never loads (TXD-STRUCT-TRAILING).',
    'TXD, текстура {0}: обрезанный заголовок Texture Native (TXD-STRUCT-TRAILING).': 'TXD, texture {0}: truncated Texture Native header (TXD-STRUCT-TRAILING).',
    'TXD, текстура {0}: имя длиннее {1} символов — движок обрежет до 31, и материал DFF с полным именем её не найдёт (TXD-NAME-LEN).': 'TXD, texture {0}: name longer than {1} characters — the engine cuts it to 31 and a DFF material with the full name never finds it (TXD-NAME-LEN).',
    'TXD, текстура {0}: rasterType 0 вместо 4 — грузится, но не как текстура по умолчанию (TXD-RASTERTYPE).': 'TXD, texture {0}: rasterType 0 instead of 4 — loads, but not as a default texture raster (TXD-RASTERTYPE).',
    'TXD, текстура {0}: rasterType {1} вместо 4 — создание растра или lock провалятся, словарь не загрузится или игра упадёт (TXD-RASTERTYPE).': 'TXD, texture {0}: rasterType {1} instead of 4 — raster creation or lock fails, the dictionary never loads or the game crashes (TXD-RASTERTYPE).',
    'TXD, текстура {0}: размер {1}×{2} не степень двойки — на картах с POW2 словарь не загрузится (TXD-DIMS).': 'TXD, texture {0}: size {1}×{2} is not a power of two — on POW2-only cards the dictionary never loads (TXD-DIMS).',
    'TXD, текстура {0}: размер {1}×{2} больше {3} — превышает лимит старых карт (TXD-DIMS).': 'TXD, texture {0}: size {1}×{2} above {3} — exceeds the limit of older cards (TXD-DIMS).',
    'TXD, текстура {0}: nibble формата 0x{1:X}00 при DXT — допустимы 0x100..0x600/0xA00, иначе словарь не загрузится (TXD-FORMAT-MISMATCH).': 'TXD, texture {0}: format nibble 0x{1:X}00 with DXT — only 0x100..0x600/0xA00 are accepted, otherwise the dictionary never loads (TXD-FORMAT-MISMATCH).',
    'TXD, текстура {0}: DXT3/DXT5 без флага alpha — отрисуется непрозрачной (TXD-ALPHA-FLAG).': 'TXD, texture {0}: DXT3/DXT5 without the alpha flag — drawn opaque (TXD-ALPHA-FLAG).',
    'TXD, текстура {0}: DXT при размере {1}×{2} меньше блока 4×4 (TXD-DIMS).': 'TXD, texture {0}: DXT at {1}×{2}, smaller than a 4×4 block (TXD-DIMS).',
    'TXD, текстура {0}: nibble формата 0x{1:X}00 вне таблицы растров — словарь не загрузится (TXD-FORMAT-MISMATCH).': 'TXD, texture {0}: format nibble 0x{1:X}00 outside the raster table — the dictionary never loads (TXD-FORMAT-MISMATCH).',
    'TXD, текстура {0}: 0 мип-уровней — ни один уровень не читается, текстура из мусора (TXD-NUMLEVELS-UNDER).': 'TXD, texture {0}: 0 mip levels — no level is read, the texture is garbage (TXD-NUMLEVELS-UNDER).',
    'TXD «{0}»: имя файла длиннее {1} символов — LoadCdDirectory молча пропустит запись в IMG, модели с этим TXD никогда не загрузятся (TXD-IMGNAME).': 'TXD "{0}": file name longer than {1} characters — LoadCdDirectory silently skips the IMG entry, models using this TXD never load (TXD-IMGNAME).',
    'TXD: STRUCT словаря длиной {0} байт — читается в 4-байтовый слот стека, от 13 байт затирает адрес возврата: краш (TXD-STRUCTLEN).': 'TXD: dictionary STRUCT of {0} bytes — read into a 4-byte stack slot, from 13 bytes it overwrites the return address: crash (TXD-STRUCTLEN).',
    'TXD: STRUCT словаря длиной {0} байт вместо 4 — переполнение локальной переменной, словарь не загрузится (TXD-STRUCTLEN).': 'TXD: dictionary STRUCT of {0} bytes instead of 4 — overflows a stack local, the dictionary never loads (TXD-STRUCTLEN).',
    'TXD: в заголовке {0} текстур, в файле {1} — лишние никогда не загрузятся (TXD-COUNT).': 'TXD: header says {0} textures, the file has {1} — the extra ones never load (TXD-COUNT).',
    'TXD, текстура {0}: несжатый формат 0x{1:X}00 требует D3DFORMAT {2}, в файле {3} — словарь не загрузится (TXD-FORMAT-MISMATCH).': 'TXD, texture {0}: uncompressed format 0x{1:X}00 requires D3DFORMAT {2}, the file has {3} — the dictionary never loads (TXD-FORMAT-MISMATCH).',
    'TXD, текстура {0}: STRUCT кончился до уровня {1} — поток рассинхронизируется, словарь не загрузится (TXD-STRUCT-TRAILING).': 'TXD, texture {0}: the STRUCT ends before level {1} — the stream desynchronises, the dictionary never loads (TXD-STRUCT-TRAILING).',
    'TXD, текстура {0}: уровень {1} выходит за STRUCT на {2} байт — поток рассинхронизируется (TXD-STRUCT-TRAILING).': 'TXD, texture {0}: level {1} runs {2} bytes past the STRUCT — the stream desynchronises (TXD-STRUCT-TRAILING).',
    'TXD, текстура #{0}: версия RW 0x{1:X} вне {2} — чанк отвергается, словарь не загрузится (TXD-VERSION).': 'TXD, texture #{0}: RW version 0x{1:X} outside {2} — the chunk is rejected, the dictionary never loads (TXD-VERSION).',
    'TXD, текстура {0}: флаг MIPMAP при одном уровне — мипов не будет (TXD-NUMLEVELS-UNDER).': 'TXD, texture {0}: MIPMAP flag with a single level — there will be no mips (TXD-NUMLEVELS-UNDER).',
    'TXD, текстура {0}: {1} мип-уровней из {2} — непрочитанные уровни остаются мусором (TXD-NUMLEVELS-UNDER).': 'TXD, texture {0}: {1} mip levels out of {2} — the unread levels stay garbage (TXD-NUMLEVELS-UNDER).',
    'TXD, текстура {0}: уровень {1} занимает {2} байт при поверхности {3} — запись за пределы D3D-текстуры, порча кучи (TXD-LEVEL-OVERSIZE).': 'TXD, texture {0}: level {1} takes {2} bytes for a {3}-byte surface — writes past the D3D texture, heap corruption (TXD-LEVEL-OVERSIZE).',

    # ── core/textdata_lint.py + ops/textdata_audit.py — text data files audit (DAT-*) ──
    'Полигон {0}': 'Polygon {0}',
    '{0} срез {1}': '{0} sample {1}',
    '{0} / эмиттер {1}': '{0} / emitter {1}',
    'gta.dat строка {0}': 'gta.dat line {0}',
    'интерьер: имя файла кончается на int.ipl': 'interior: the file name ends with int.ipl',
    'карта': 'map',
    'одноимённого текстового IPL': 'the text IPL of the same name',
    'этого файла': 'this file',
    '{0}: строка длиннее {1} байт — движок прочтёт её как две записи (DAT-01).': '{0}: line longer than {1} bytes — the engine reads it as two records (DAT-01).',
    'Квады должны быть прямоугольниками по осям, треугольники — с двумя вершинами на одной линии X или Y: движок сортирует вершины по (y, x) и рисует мусор ({0} шт.: {1}) (DAT-45b).': 'Quads must be axis-aligned rectangles and triangles must have two vertices on one X or Y line: the engine sorts the vertices by (y, x) and renders garbage otherwise ({0}: {1}) (DAT-45b).',
    'Вырожденные полигоны (все X или все Y равны) движок молча выбрасывает ({0} шт.: {1}) (DAT-45b).': 'Degenerate polygons (all X or all Y equal) are silently dropped by the engine ({0}: {1}) (DAT-45b).',
    'Квадов {0} — таблица WaterQuads вмещает {1} (ваниль заполняет её целиком); 302-й затирает треугольники (DAT-44).': '{0} quads — the WaterQuads table holds {1} (vanilla fills it completely); the 302nd overwrites the triangle table (DAT-44).',
    'Треугольников {0} — таблица WaterTriangles вмещает {1}; 7-й затирает свой же счётчик (DAT-44).': '{0} triangles — the WaterTriangles table holds {1}; the 7th overwrites its own counter (DAT-44).',
    'Уникальных вершин {0} — в ванильном water.dat их {1}, реальная ёмкость m_aVertices не проверена; лишние могут писаться поверх соседних глобалов (DAT-44).': '{0} distinct vertices — vanilla water.dat has {1}, the real m_aVertices capacity is unverified; the rest may be written over the neighbouring globals (DAT-44).',
    'Полигонов на блок слишком много: список комбинаций ≈{0} записей при лимите {1} (DAT-44).': 'Too many polygons per block: the combo list needs ≈{0} entries, the limit is {1} (DAT-44).',
    'Полигонов шире 500 по стороне: {0}, пересекающих границу 500-блока: {1} — в игре такие могут рисоваться без текстуры (наблюдение, не проверка парсера).': 'Polygons wider than 500 on a side: {0}, crossing a 500-block boundary: {1} — in-game these may render without a texture (an observation, not a parser check).',
    'cull: {0} зон с нулевыми флагами после маски — движок их отбрасывает ({1}) (DAT-28).': 'cull: {0} zones with zero flags after masking — the engine drops them ({1}) (DAT-28).',
    'cull: {0} атрибутных зон в файле — таблица вмещает {1} (ваниль уже 1180) (DAT-28).': 'cull: {0} attribute zones in the file — the table holds {1} (vanilla already uses 1180) (DAT-28).',
    'cull: {0} туннельных зон — таблица вмещает {1} (ваниль 36) (DAT-28).': 'cull: {0} tunnel zones — the table holds {1} (vanilla 36) (DAT-28).',
    'cull: {0} зеркальных зон — таблица вмещает {1} (ваниль 65) (DAT-28).': 'cull: {0} mirror zones — the table holds {1} (vanilla 65) (DAT-28).',
    'occl: {0} объёмов с двумя нулевыми размерами — COcclusion::AddOne их отбрасывает ({1}) (DAT-29).': 'occl: {0} volumes with two zero dimensions — COcclusion::AddOne drops them ({1}) (DAT-29).',
    'occl: {0} окклюдеров в файле при лимите {1} ({2}) — лишние молча отбрасываются (DAT-29).': 'occl: {0} occluders in the file, limit {1} ({2}) — the rest are silently dropped (DAT-29).',
    'grge: {0} гаражей — aGarages вмещает {1} (ваниль заполняет все 50) (DAT-31).': 'grge: {0} garages — aGarages holds {1} (vanilla fills all 50) (DAT-31).',
    'enex: {0} маркеров в файле — пул на {1} (ваниль 376); лишние пишут флаги в запись 0 (DAT-30).': 'enex: {0} markers in the file — the pool holds {1} (vanilla 376); the rest write their flags into entry 0 (DAT-30).',
    'auzo: {0} боксов — таблица вмещает {1} (DAT-36).': 'auzo: {0} boxes — the table holds {1} (DAT-36).',
    'auzo: {0} сфер — таблица вмещает {1} и в ванили уже полна; 4-я затирает состояние камеры (DAT-36).': 'auzo: {0} spheres — the table holds {1} and is already full in vanilla; a 4th overwrites camera state (DAT-36).',
    'tcyc: {0} боксов — m_aBoxes вмещает {1} (ваниль 8); лишние пишут поверх соседних глобалов (DAT-35).': 'tcyc: {0} boxes — m_aBoxes holds {1} (vanilla 8); the rest are written over the neighbouring globals (DAT-35).',
    'cars: {0} генераторов с моделью вне -1 / 400..630 — CreateCarGenerator их отбрасывает ({1}) (DAT-34).': 'cars: {0} generators with a model outside -1 / 400..630 — CreateCarGenerator drops them ({1}) (DAT-34).',
    'cars: {0} генераторов — пул на {1}, лишние отбрасываются (DAT-34).': 'cars: {0} generators — the pool holds {1}, the rest are dropped (DAT-34).',
    'pick: {0} пикапов с id вне таблицы движка (4..6, 9..55 без 30 и 42) — отбрасываются ({1}) (DAT-33).': 'pick: {0} pickups with an id outside the engine table (4..6, 9..55 without 30 and 42) — dropped ({1}) (DAT-33).',
    'zone: {0} навигационных зон в файле — NavigationZoneArray вмещает {1} (ваниль уже 378); 381-я затирает m_CurrLevel (DAT-27).': 'zone: {0} navigation zones in the file — NavigationZoneArray holds {1} (vanilla already has 378); the 381st overwrites m_CurrLevel (DAT-27).',
    'zone: {0} зон карты в файле — MapZoneArray вмещает {1}; 40-я затирает счётчик zone-info (DAT-27).': 'zone: {0} map zones in the file — MapZoneArray holds {1}; the 40th overwrites the zone-info counter (DAT-27).',
    '{0}: имя модели «{1}» длиннее {2} символов — name[24] переполняется в буфер txd, хеш модели ломается, она никогда не загрузится (DAT-09).': '{0}: model name "{1}" longer than {2} characters — name[24] overruns into the txd buffer, the model hash breaks and it never loads (DAT-09).',
    '{0}: имя TXD «{1}» длиннее {2} символов — txd[24] лежит под адресом возврата, краш (DAT-09).': '{0}: TXD name "{1}" longer than {2} characters — txd[24] sits under the return address, crash (DAT-09).',
    '{0}: имя модели или TXD содержит пробел — сдвинет все поля строки (DAT-08b).': '{0}: the model or TXD name contains a space — every following field shifts (DAT-08b).',
    '{0} разных TXD в файле — пул TexDictionary на {1} записей, AddTxdSlot пишет в NULL (DAT-15).': '{0} distinct TXDs in the file — the TexDictionary pool has {1} entries, AddTxdSlot writes to NULL (DAT-15).',
    '2dfx: {0} записей — хранилище на {1} (ваниль уже занимает 97) (DAT-16).': '2dfx: {0} entries — the store holds {1} (vanilla already uses 97) (DAT-16).',
    '{0} разных поверхностей — таблица на {1}; LoadPlantsDat вернёт false, трава отключится целиком (DAT-46a).': '{0} distinct surfaces — the table holds {1}; LoadPlantsDat returns false and ALL grass is disabled (DAT-46a).',
    '{0}: флаг {1} вне 0..3 — движок читает только биты 0 (видимость) и 1 (мелководье) (DAT-45c).': '{0}: flag {1} outside 0..3 — the engine reads only bit 0 (visible) and bit 1 (shallow) (DAT-45c).',
    '{0}: id модели вне 0..19999 — чтение за пределами ms_modelInfoPtrs, краш (DAT-21).': '{0}: model id outside 0..19999 — read past ms_modelInfoPtrs, crash (DAT-21).',
    '{0}: имя модели длиннее {1} символов — переполнение буфера name[24] (DAT-09).': '{0}: model name longer than {1} characters — overruns the name[24] buffer (DAT-09).',
    '{0}: NaN/inf в позиции или повороте — матрица объекта станет NaN (DAT-23).': '{0}: NaN/inf in the position or rotation — the object matrix becomes NaN (DAT-23).',
    '{0}: |rot_w| = {1:.4f} > 1 — acos даёт NaN, объект невидим и без коллизии (DAT-23).': '{0}: |rot_w| = {1:.4f} > 1 — acos yields NaN, the object is invisible and has no collision (DAT-23).',
    '{0}: поле interior {1} содержит биты вне 0..255 + 0x100..0x1000 — движок их игнорирует (DAT-24).': '{0}: interior field {1} has bits outside 0..255 + 0x100..0x1000 — the engine ignores them (DAT-24).',
    '{0}: позиция ({1:.0f}, {2:.0f}) за пределами ±3000 — CEntity::Add прижмёт её к крайнему сектору (DAT-25).': '{0}: position ({1:.0f}, {2:.0f}) outside ±3000 — CEntity::Add clamps it into the edge sector (DAT-25).',
    'inst #{0}: {1} LOD-детей — счётчик m_nNumLodChildren восьмибитный, переполнится (DAT-22).': 'inst #{0}: {1} LOD children — the m_nNumLodChildren counter is 8-bit and wraps (DAT-22).',
    'bnry: {0} inst / {1} cars — счётчики читаются как int16, секция ≥ 32768 пропускается (DAT-37).': 'bnry: {0} inst / {1} cars — the counts are read as int16, a section ≥ 32768 is skipped (DAT-37).',
    'bnry: имя файла «{0}» длиннее {1} символов — переполняет IplDef.name[18] при AddIplSlot (DAT-39).': 'bnry: file name "{0}" longer than {1} characters — overruns IplDef.name[18] in AddIplSlot (DAT-39).',
    'bnry: секции {0} в бинарном IPL не сохраняются — движок читает только inst и cars (DAT-37).': 'bnry: sections {0} are not stored in a binary IPL — the engine reads only inst and cars (DAT-37).',
    '{0} строк inst в одном текстовом IPL — gCurrIplInstances вмещает {1} (DAT-26).': '{0} inst lines in one text IPL — gCurrIplInstances holds {1} (DAT-26).',
    'grge #{0}: имя «{1}» длиннее {2} символов — name[8] лежит под адресом возврата, краш (DAT-31).': 'grge #{0}: name "{1}" longer than {2} characters — name[8] sits under the return address, crash (DAT-31).',
    'enex #{0}: имя «{1}» длиннее {2} символов — переполнение name[32], краш (DAT-30).': 'enex #{0}: name "{1}" longer than {2} characters — overruns name[32], crash (DAT-30).',
    'auzo #{0}: имя «{1}» длиннее 15 символов — переполнение name[16], краш (DAT-36).': 'auzo #{0}: name "{1}" longer than 15 characters — overruns name[16], crash (DAT-36).',
    '{0}: имя или GXT-ключ пусты либо содержат пробел — sscanf не наберёт ровно 10 полей, зона выброшена (DAT-27).': '{0}: the name or GXT key is empty or contains a space — sscanf will not get exactly 10 fields, the zone is dropped (DAT-27).',
    '{0}: имя длиннее {1} символов — CreateZone хранит 7 (strncpy), остаток отрезается (DAT-27).': '{0}: name longer than {1} characters — CreateZone keeps 7 (strncpy), the rest is cut (DAT-27).',
    '{0}: GXT-ключ «{1}» длиннее 11 символов — переполнение info[12], затирает границы зоны (DAT-27b).': '{0}: GXT key "{1}" longer than 11 characters — overruns info[12] and corrupts the zone bounds (DAT-27b).',
    '{0}: level {1} хранится байтом (DAT-27).': '{0}: level {1} is stored as a byte (DAT-27).',
    '{0}: id вне 0..19999 — запись за пределы ms_modelInfoPtrs (DAT-06).': '{0}: id outside 0..19999 — write past ms_modelInfoPtrs (DAT-06).',
    '{0}: id уже определён в этом файле ({1}) — вторая запись молча заменяет первую (DAT-07).': '{0}: id already defined in this file ({1}) — the second entry silently replaces the first (DAT-07).',
    '{0}: {1} дистанций — движок знает формы с 1..3 мешами, строка прочтётся мусором (DAT-08).': '{0}: {1} draw distances — the engine knows the 1..3 mesh forms only, the line is read as garbage (DAT-08).',
    '{0}: дистанция {1} < 4.0 — LoadObject перечитает строку как legacy-форму со счётчиком мешей: дистанция возьмётся из колонки флагов, объект станет невидимым (DAT-08).': '{0}: draw distance {1} < 4.0 — LoadObject re-parses the line as the legacy mesh-count form: the distance is taken from the flags column and the object becomes invisible (DAT-08).',
    '{0}: флаги 0x{1:X} содержат биты выше 0x400000, которых движок не знает (DAT-14).': '{0}: flags 0x{1:X} contain bits above 0x400000 the engine does not know (DAT-14).',
    '{0}: часы {1}..{2} вне 0..24 — хранятся байтами (DAT-08).': '{0}: hours {1}..{2} outside 0..24 — stored as bytes (DAT-08).',
    '{0}: имя анимации «{1}» длиннее {2} символов — anim[16] лежит под буфером имени модели и затирает его (DAT-10).': '{0}: animation name "{1}" longer than {2} characters — anim[16] sits under the model-name buffer and overwrites it (DAT-10).',
    '{0}: имя анимации «{1}» длиннее {2} символов — переполнение anim[16] (DAT-09).': '{0}: animation name "{1}" longer than {2} characters — overruns anim[16] (DAT-09).',
    '{0}: тип «{1}» длиннее 7 символов — type[8] затирает уже прочитанный id (DAT-13).': '{0}: type "{1}" longer than 7 characters — type[8] overwrites the already parsed id (DAT-13).',
    '{0}: класс «{1}» длиннее 15 символов — переполнение class[16] (DAT-09).': '{0}: class "{1}" longer than 15 characters — overruns class[16] (DAT-09).',
    '{0}: имя TXD «{1}» длиннее {2} символов — теряет NUL и склеивается с voice1, пед без текстур (DAT-09).': '{0}: TXD name "{1}" longer than {2} characters — loses its NUL and merges with voice1, textureless ped (DAT-09).',
    '{0}: группа анимаций «{1}» отсутствует в animgrp.dat — индекс за концом таблицы, краш при спавне (DAT-12).': '{0}: animation group "{1}" is not in animgrp.dat — index past the end of the table, crash at spawn (DAT-12).',
    '{0} записей в хранилище {1} — оно вмещает {2}; лишние затирают счётчик следующего хранилища (DAT-07).': "{0} entries in the {1} store — it holds {2}; the rest overwrite the next store's counter (DAT-07).",
    '2dfx: записи модели {0} идут не подряд — Add2dEffect хранит первый индекс + счётчик, эффекты смешаются (DAT-16).': '2dfx: the entries of model {0} are not consecutive — Add2dEffect stores first index + count, the effects get mixed up (DAT-16).',
    '2dfx: модель {0} не определена в этом IDE — если её нет и в ранее загруженном IDE, ms_modelInfoPtrs даст NULL, краш (DAT-16).': '2dfx: model {0} is not defined in this IDE — if no earlier IDE defines it either, ms_modelInfoPtrs yields NULL, crash (DAT-16).',
    'Строк данных {0}, нужно ровно {1} (23 погоды × 8 срезов) — на короткий файл движок вызывает sscanf(NULL), краш (DAT-42a).': '{0} data lines, exactly {1} required (23 weathers × 8 samples) — on a short file the engine calls sscanf(NULL), crash (DAT-42a).',
    'Строка {0} «{1}» — не данные и не комментарий на «//»: движок скормит её sscanf, все следующие срезы сдвинутся (DAT-42b).': 'Line {0} "{1}" is neither data nor a "//" comment: the engine feeds it to sscanf and every following sample shifts (DAT-42b).',
    'Строк данных {0}, нужно ровно {1} ({2} погод × 24 часа) — движок читает строки подряд без проверки конца буфера (DAT-42a).': '{0} data lines, exactly {1} required ({2} weathers × 24 hours) — the engine reads rows back to back with no end-of-buffer check (DAT-42a).',
    '{0}: {1} чисел в строке вместо {2} — недостающие колонки движок берёт с предыдущей строки (DAT-42c).': '{0}: {1} numbers in the row instead of {2} — the engine takes the missing columns from the previous row (DAT-42c).',
    'Скопировать текущий срез во все срезы этой погоды (8 у SA, 24 у III/VC)': 'Copy the current time slot into every slot of this weather (8 for SA, 24 for III/VC)',
    '{0}: sscanf споткнулся посреди строки (дробное число в целой колонке) — остаток колонок игра берёт с предыдущей строки; при правке срез запишется целиком (DAT-42c).': '{0}: sscanf stops mid-line (a fraction in an integer column) — the game takes the remaining columns from the previous line; an edit rewrites the whole sample (DAT-42c).',
    '{0}: light_on_ground = {1} — хранится как uint8(v·10), диапазон 0..25.5 (DAT-42d).': '{0}: light_on_ground = {1} — stored as uint8(v·10), range 0..25.5 (DAT-42d).',
    '{0}: имя поверхности пустое или с пробелом — строка не даст ровно 18 токенов, LoadPlantsDat вернёт false, трава отключится целиком (DAT-46a).': '{0}: the surface name is empty or contains a space — the line will not give exactly 18 tokens, LoadPlantsDat returns false and ALL grass is disabled (DAT-46a).',
    '{0}: нет полей {1} — строка не даст 18 токенов, трава отключится целиком (DAT-46a).': '{0}: missing fields {1} — the line will not give 18 tokens, ALL grass is disabled (DAT-46a).',
    '{0}: имя начинается с «;» — движок примет строку за комментарий (DAT-46a).': '{0}: the name starts with ";" — the engine treats the line as a comment (DAT-46a).',
    '{0}: поверхность «{1}» неизвестна движку (GetSurfaceIdFromName) — LoadPlantsDat вернёт false, трава отключится целиком (DAT-46a).': '{0}: surface "{1}" is unknown to the engine (GetSurfaceIdFromName) — LoadPlantsDat returns false and ALL grass is disabled (DAT-46a).',
    '{0}: PCDid {1} вне 0..2 — движок подставит 0 и затрёт первое определение (DAT-46b).': '{0}: PCDid {1} outside 0..2 — the engine substitutes 0 and overwrites the first definition (DAT-46b).',
    '{0}: SlotID {1} вне 0..3 — индекс за пределами PC_PlantModelsTab, мусор/краш при отрисовке (DAT-46b).': '{0}: SlotID {1} outside 0..3 — index past PC_PlantModelsTab, garbage/crash at render (DAT-46b).',
    '{0}: ModelID {1} вне 0..3 — индекс за пределами таблицы моделей, мусор/краш (DAT-46b).': '{0}: ModelID {1} outside 0..3 — index past the model table, garbage/crash (DAT-46b).',
    '{0}: UVoff {1} вне 0..3 — четыре текстуры на слот (DAT-46b).': '{0}: UVoff {1} outside 0..3 — four textures per slot (DAT-46b).',
    '{0}: NUM_PRIMS = {1} — буфер имён текстур рассчитан на {2} эмиттеров, переполнение стека (DAT-47a).': '{0}: NUM_PRIMS = {1} — the texture-name scratch holds {2} emitters, stack overflow (DAT-47a).',
    'gta.dat строка {0}: путь {1} длиннее {2} символов — переполнение local_40[64], краш (DAT-05).': 'gta.dat line {0}: {1} path longer than {2} characters — overruns local_40[64], crash (DAT-05).',
    'gta.dat строка {0}: путь IDE длиннее {1} символов — переполнение local_100[256], краш (DAT-05).': 'gta.dat line {0}: IDE path longer than {1} characters — overruns local_100[256], crash (DAT-05).',
    '{0}: {1} вершин — water.dat принимает только 3 или 4, строка прочтётся мусором (DAT-43).': '{0}: {1} vertices — water.dat accepts only 3 or 4, the line is read as garbage (DAT-43).',
    '{0}: NaN/inf в вершине — sscanf сорвётся, строка прочтётся мусором (DAT-43).': '{0}: NaN/inf in a vertex — sscanf fails, the line is read as garbage (DAT-43).',
    '{0}: координата ({1:.3f}, {2:.3f}) не целая — движок отбросит дробную часть (DAT-45).': '{0}: coordinate ({1:.3f}, {2:.3f}) is not integral — the engine truncates the fraction (DAT-45).',
    '{0}: вершина ({1:.0f}, {2:.0f}) за пределами ±3000 — движок прижмёт её к краю и обнулит высоту/волны (DAT-45a).': '{0}: vertex ({1:.0f}, {2:.0f}) outside ±3000 — the engine clamps it to the edge and resets height/waves (DAT-45a).',
    '{0}: течение ({1:.3f}, {2:.3f}) — |flow|·64 не влезает в int8, нужно |flow| < 2 (DAT-45a).': '{0}: flow ({1:.3f}, {2:.3f}) — |flow|·64 does not fit int8, |flow| < 2 required (DAT-45a).',
    '{0}: id модели не определён ни в одном IDE — NULL в LinkLods, краш при загрузке (DAT-21).': '{0}: model id is not defined by any IDE — NULL in LinkLods, crash at load (DAT-21).',
    '{0}: id модели нет в {1} — он должен быть определён в другом загружаемом IDE, иначе NULL в LinkLods и краш (DAT-21).': '{0}: model id is not in {1} — it must be defined by another loaded IDE, otherwise NULL in LinkLods and a crash (DAT-21).',
    '{0}: lod_index {1} вне списка inst ({2}: 0..{3}) — LinkLods разыменует мусор (DAT-22).': '{0}: lod_index {1} outside the inst list ({2}: 0..{3}) — LinkLods dereferences garbage (DAT-22).',
    '{0}: кватернион не нормирован (|q| = {1:.4f}) — SetRotate даст масштабированную матрицу (DAT-23).': '{0}: quaternion not normalised (|q| = {1:.4f}) — SetRotate produces a scaled matrix (DAT-23).',
    '{0} строк inst в одном текстовом IPL — ёмкость gCurrIplInstances не подтверждена (1000 по plugin-sdk, ваниль ≤ 718) (DAT-26).': '{0} inst lines in one text IPL — the gCurrIplInstances capacity is unverified (1000 per plugin-sdk, vanilla ≤ 718) (DAT-26).',
    'grge #{0}: имя «{1}» пустое или с пробелом — sscanf не наберёт 11 полей, гараж пропущен (DAT-31).': 'grge #{0}: name "{1}" is empty or contains a space — sscanf will not get 11 fields, the garage is skipped (DAT-31).',
    'enex #{0}: имя «{1}» с пробелом — %s оборвёт его, остальные поля получат значения по умолчанию (DAT-30).': 'enex #{0}: name "{1}" contains a space — %s cuts it, the remaining fields get their defaults (DAT-30).',
    'auzo #{0}: имя «{1}» длиннее {2} символов — в 8-байтовом поле теряется NUL, имя читается мусором (DAT-36).': 'auzo #{0}: name "{1}" longer than {2} characters — the 8-byte field loses its NUL, the name reads as garbage (DAT-36).',
    '{0}: в строке {1} полей вместо 10 — LoadZone вызывает CreateZone только при ровно 10 (DAT-27).': '{0}: {1} fields on the line instead of 10 — LoadZone calls CreateZone only with exactly 10 (DAT-27).',
    '{0}: GXT-ключ «{1}» длиннее {2} символов — хранится 7, остаток отрезается (DAT-27).': '{0}: GXT key "{1}" longer than {2} characters — 7 are kept, the rest is cut (DAT-27).',
    '{0}: тип {1} — ваниль принимает 0/1 (навигация) и 3 (карта), остальное молча отбрасывается (DAT-27).': '{0}: type {1} — vanilla accepts 0/1 (navigation) and 3 (map), anything else is silently dropped (DAT-27).',
    '{0}: координата {1} не влезает в int16 (DAT-27).': '{0}: coordinate {1} does not fit int16 (DAT-27).',
    '{0}: дистанция {1} < 2.0 — экземпляры создаются невидимыми (DAT-25b).': '{0}: draw distance {1} < 2.0 — instances are created invisible (DAT-25b).',
    '{0}: тип «{1}» неизвестен движку — останется значение конструктора (DAT-13).': '{0}: type "{1}" is unknown to the engine — the constructor default stays (DAT-13).',
    '{0}: класс «{1}» неизвестен движку — останется значение конструктора (DAT-13).': '{0}: class "{1}" is unknown to the engine — the constructor default stays (DAT-13).',
    '{0}: поле {1} «{2}» длиннее {3} символов — переполнение стекового буфера (DAT-09).': '{0}: field {1} "{2}" longer than {3} characters — stack buffer overrun (DAT-09).',
    'txdp {0}: имя «{1}» длиннее {2} символов — переполнение буфера [32] (DAT-09).': 'txdp {0}: name "{1}" longer than {2} characters — overruns the [32] buffer (DAT-09).',
    'Строк данных {0} при {1} читаемых — хвост файла игнорируется (DAT-42a).': '{0} data lines, {1} are read — the tail of the file is ignored (DAT-42a).',
    '{0}: {1} = {2} вне 0..255 — хранится байтом, значение обернётся (DAT-42d).': '{0}: {1} = {2} outside 0..255 — stored as a byte, the value wraps (DAT-42d).',
    '{0}: альфа {1} = {2} — хранится как uint8(a·2): 0..127 точно, 255 → 254, остальное обернётся (DAT-42d).': '{0}: alpha {1} = {2} — stored as uint8(a·2): 0..127 exact, 255 → 254, anything else wraps (DAT-42d).',
    '{0}: {1} = {2} — хранится как int8(v·10), максимум 12.7 (DAT-42d).': '{0}: {1} = {2} — stored as int8(v·10), maximum 12.7 (DAT-42d).',
    '{0}: {1} = {2} вне 0..255 — хранится байтом (DAT-42d).': '{0}: {1} = {2} outside 0..255 — stored as a byte (DAT-42d).',
    '{0}: {1} = {2} не влезает в int16 (DAT-42d).': '{0}: {1} = {2} does not fit int16 (DAT-42d).',
    '{0}: directional mult {1} — движок хранит uint8(int(v))·100, осмысленны только 0, 1, 2 (DAT-42d).': '{0}: directional mult {1} — the engine stores uint8(int(v))·100, only 0, 1, 2 are meaningful (DAT-42d).',
    '{0}: нечисловые id — sscanf/atoi даст мусор (DAT-46b).': '{0}: non-numeric ids — sscanf/atoi yields garbage (DAT-46b).',
    '{0}: SlotID {1} — из models\\grass загружаются только слоты 0 и 1 (DAT-46b).': '{0}: SlotID {1} — only slots 0 and 1 are loaded from models\\grass (DAT-46b).',
    '{0}: {1} = {2} вне 0..255 — хранится байтом (DAT-46b).': '{0}: {1} = {2} outside 0..255 — stored as a byte (DAT-46b).',
    '{0}: {1} не число (DAT-46a).': '{0}: {1} is not a number (DAT-46a).',
    'gta.dat строка {0}: {1} после первой строки IPL — Init2 уже отработал, эти модели никогда не подгрузятся (DAT-04).': 'gta.dat line {0}: {1} after the first IPL line — Init2 has already run, these models never stream (DAT-04).',
    'gta.dat строка {0}: между {1} и путём должен быть ровно один пробел — иначе путь берётся со сдвигом, файл не откроется, fgets(NULL) (DAT-03).': 'gta.dat line {0}: exactly one space must separate {1} from the path — otherwise the path is taken at an offset, the file does not open, fgets(NULL) (DAT-03).',
    '{0}: lod_index указывает на саму себя (DAT-22).': '{0}: lod_index points at itself (DAT-22).',
    'enex #{0}: имя «{1}» длиннее {2} символов — AddOne хранит только {2} (strncpy), пара по имени может не совпасть (DAT-30).': 'enex #{0}: name "{1}" longer than {2} characters — AddOne keeps only {2} (strncpy), the pair may not match by name (DAT-30).',
    '{0}: имя текстуры «{1}» длиннее {2} символов — переполняет 32-байтовый слот (DAT-47a).': '{0}: texture name "{1}" longer than {2} characters — overruns the 32-byte slot (DAT-47a).',
    '{0}: неизвестное FX_INFO_{1}_DATA — движок пишет в NULL, краш (DAT-47b).': '{0}: unknown FX_INFO_{1}_DATA — the engine writes to NULL, crash (DAT-47b).',
    '{0}: {1} кривых вместо {2} — читатель сдвинется по строкам, все дальнейшие значения станут мусором (DAT-47c).': '{0}: {1} curves instead of {2} — the reader drifts by lines, every following value becomes garbage (DAT-47c).',
    '{0}: текстуры «{1}» нет в effectsPC.txd — частицы без текстуры (DAT-48).': '{0}: texture "{1}" is not in effectsPC.txd — untextured particles (DAT-48).',
    '{0} / {1}: NUM_KEYS = {2} — хранится как int8, максимум {3} (DAT-47c).': '{0} / {1}: NUM_KEYS = {2} — stored as int8, maximum {3} (DAT-47c).',
    '{0} / {1}: NaN/inf в значении ключа (DAT-47c).': '{0} / {1}: NaN/inf in a key value (DAT-47c).',
    '{0} / {1}: {2} ключей при {3} у первой кривой — массив времён выделен по первой кривой, запись за его пределы (DAT-47c).': '{0} / {1}: {2} keys while the first curve has {3} — the time array is allocated from the first curve, write past its end (DAT-47c).',
    '{0} / {1}: время ключа {2} — хранится как int16(t·256), нужно |t| < 128 (DAT-47c).': '{0} / {1}: key time {2} — stored as int16(t·256), |t| < 128 required (DAT-47c).',
    '{0} / {1}: {2} ключей при {3} у первой кривой — времена общие на все кривые info, хвост читается мусором (DAT-47c).': '{0} / {1}: {2} keys while the first curve has {3} — the times are shared by every curve of the info, the tail reads as garbage (DAT-47c).',
    '{0}: ещё {1} предупреждений — см. консоль': '{0}: {1} more warnings — see the console',
    '{0}: ещё {1} ошибок — см. консоль': '{0}: {1} more errors — see the console',
    'Проверять модели при экспорте': 'Audit models on export',
    'После записи каждого DFF прогонять проверку на краши/баги в игре\n(индексы вершин/материалов, dummy машин, скин, 2DFX, имена и т.д.),\nпредупреждения — в консоль и панель.\nОТКЛЮЧИ для МАССОВОГО экспорта тысяч уже проверенных моделей —\nаудит гоняется на каждую модель и заметно замедляет.': "After writing each DFF, run the in-game crash/bug audit\n(vertex/material indices, vehicle dummies, skin, 2DFX, names, etc.),\nwarnings go to the console and the panel.\nTURN OFF for MASS export of thousands of already-checked models —\nthe audit runs on every model and slows it down noticeably.",
    'Игра не примет': 'The game will not accept',
    # ── Vehicle dummy audit (check_vehicle_names) ──
    'ось переднего левого колеса': 'front-left wheel axle',
    'ось переднего правого колеса': 'front-right wheel axle',
    'ось заднего левого колеса': 'rear-left wheel axle',
    'ось заднего правого колеса': 'rear-right wheel axle',
    'верхний dummy всей машины': 'top-level dummy of the whole vehicle',
    'верхний dummy байка': 'top-level dummy of the bike',
    'переднее колесо': 'front wheel',
    'заднее колесо': 'rear wheel',
    'есть как «{0}», суффикс уйдёт в DFF': 'present as "{0}" — the suffix will go into the DFF',
    'wheel без _lf/_rf/_lb/_rb': 'wheel without _lf/_rf/_lb/_rb',

    # LightMap из папки (_d / _n) и переключение день/ночь
    'пропущено (нет цветового входа):': 'skipped (no colour input):',
    'Показать': 'Show',
    'Показать дневные карты': 'Show the day maps',
    'Показать ночные карты': 'Show the night maps',
    'Папка не найдена': 'Folder not found',
    'В папке нет карт с суффиксом _d / _n': 'No maps with a _d / _n suffix in the folder',
    'Для выделенных моделей карт в папке не нашлось': 'No maps in the folder match the selected models',
    'день': 'day',
    'ночь': 'night',
    'без карт:': 'without maps:',
    'Нет загруженных карт — «LightMap из папки…»': 'No maps loaded — use “LightMap from folder…”',
    'LightMap из папки…': 'LightMap from folder…',

    # INU Export = основной экспорт (LOD/COL/CST/TXD)
    'Экспортировать LOD-модели (LOD<имя>.dff)': 'Export LOD models (LOD<name>.dff)',
    'Коллизия текстом для Collision File Editor II (.cst)': 'Collision as Collision File Editor II text (.cst)',
    'Вся выделенная иерархия — в ОДИН .dff, коллизия внутрь него': 'The whole selected hierarchy into ONE .dff, collision embedded in it',
    'Записать запись без геометрии (границы — по видимой модели)': 'Write a geometry-less record (bounds taken from the visible model)',
    'Все текстуры экспортируемых моделей — в ОДИН файл с именем ниже.\nБез этой галочки каждая модель получает свой <имя>.txd': 'Every texture of the exported models into ONE file named below.\nWithout this each model gets its own <name>.txd',
    'Имя общего TXD без .txd': 'Shared TXD name without .txd',
    'Если TXD уже есть — добавить/обновить в нём текстуры сцены, сохранив остальные (от других моделей). Иначе файл перезаписывается целиком': "If the TXD already exists — add/update the scene's textures in it and keep the rest (from other models). Otherwise the file is overwritten entirely",
    'Общий TXD — все модели в один файл': 'Shared TXD — every model into one file',
    'Текстуры пойдут в отдельные .txd по моделям': 'Textures will go into separate .txd files, one per model',
    # ── IDE/IPL sync (core/mapsync, ops/map_link) ──
    'ID {0} в файле занят другой моделью «{1}» — «{2}» не записана. Проверь Model ID': 'ID {0} is taken in the file by another model «{1}» — «{2}» not written. Check the Model ID',
    'ID {0} в файле принадлежит «{1}», а не «{2}» — не удалено': 'ID {0} in the file belongs to «{1}», not «{2}» — not removed',
    'ID {0} ещё стоит в IPL у {1} объектов': 'ID {0} is still placed in IPL by {1} objects',
    'ID {0} уже занят в секции {1} («{2}») — «{3}» не записана': 'ID {0} is already used in section {1} («{2}») — «{3}» not written',
    'IPL Проверка': 'IPL check',
    'LOD удалено {0}': 'LOD removed {0}',
    'LOD — пишется вместе с моделью': 'LOD — written together with its model',
    '{0} копий — добавлены новыми расстановками': '{0} copies — added as new placements',
    '{0} строк(и) ссылались на удалённый LOD — их lod_index сброшен в -1': '{0} row(s) pointed at a removed LOD — their lod_index was reset to -1',
    '{0}: бинарный IPL (из IMG) — редактировать нельзя': '{0}: binary IPL (from an IMG) — cannot be edited',
    '«{0}» была в {1} — записана в выбранный {2}': '«{0}» was in {1} — written to the chosen {2}',
    '«{0}» была в {1} — записана в выбранный {2}, в старом файле строка осталась': '«{0}» was in {1} — written to the chosen {2}; its row is still in the old file',
    '«{0}» уже есть в файле с ID {1} — не записана (поставь модели этот ID или удали ту строку)': '«{0}» is already in the file with ID {1} — not written (give the model that ID or delete that row)',
    '«{0}»: ID изменён {1} → {2}': '«{0}»: ID changed {1} → {2}',
    '«{0}»: LOD без основной модели — выдели основную модель': '«{0}»: LOD without its main model — select the main model',
    '«{0}»: Model ID = 0 — не записана': '«{0}»: Model ID = 0 — not written',
    '«{0}»: нет своего IDE — выбери файл в панели IDE': '«{0}»: has no IDE of its own — pick a file in the IDE box',
    '«{0}»: нет своего IPL — выбери файл в панели IPL': '«{0}»: has no IPL of its own — pick a file in the IPL box',
    '«{0}»: нет IDE-файла': '«{0}»: no IDE file',
    '«{0}»: нет IPL-файла': '«{0}»: no IPL file',
    '«{0}»: прежняя строка в файле не найдена (удалена или правилась вручную) — добавлена заново': '«{0}»: its previous row is not in the file (deleted or edited by hand) — added again',
    '«{0}»: строка в файле была изменена вручную — найдена рядом и обновлена': '«{0}»: the row was edited by hand — found nearby and updated',
    '«{0}»: строка не найдена в файле — удалять нечего': '«{0}»: row not found in the file — nothing to remove',
    '«{0}»: у LOD нет Model ID — LOD не записан': '«{0}»: the LOD has no Model ID — LOD not written',
    '«{0}»: у копий разные параметры IDE — записаны параметры первой': '«{0}»: copies have different IDE settings — the first one was written',
    'Имя модели в строке IDE на момент последней записи/чтения': 'Model name in the IDE row at the last write/read',
    'Имя модели в строке IPL на момент последней записи/чтения': 'Model name in the IPL row at the last write/read',
    'Имя объекта, который записал строку IPL. У копии (Shift+D) имя другое — она добавится новой расстановкой, а не перезапишет строку оригинала': "Name of the object that wrote the IPL row. A copy (Shift+D) has a different name — it is added as a new placement instead of overwriting the original's row",
    'Координаты из IPL': 'Coords from IPL',
    'Остальное будет записано. Продолжить?': 'Everything else will be written. Continue?',
    'Перед записью найдены проблемы:': 'Problems found before writing:',
    'без изменений {0}': 'unchanged {0}',
    'добавлено {0}': 'added {0}',
    'конфликтов {0}': 'conflicts {0}',
    'нечего делать': 'nothing to do',
    'новых связей {0}': 'new links {0}',
    'обновлено {0}': 'updated {0}',
    'обновлено из файла {0}': 'updated from file {0}',
    'пропущено {0}': 'skipped {0}',
    'строка не найдена {0}': 'row not found {0}',
    'удалено {0}': 'removed {0}',
    '… ещё {0}': '… {0} more',
    'Add: записать/обновить ВЫДЕЛЕННЫЕ модели в ВЫБРАННЫЙ .ide (id, txd, дистанция, флаги). Обновляет свои строки на месте; LOD модели пишется вместе с ней. Чужую модель с тем же ID не перезаписывает — сообщает о конфликте. Отличие от Export: пишет в уже выбранный файл, а не создаёт новый': "Add: write/update the SELECTED models in the CHOSEN .ide (id, txd, distance, flags). Updates their own rows in place; the model's LOD is written with it. Another model with the same ID is never overwritten — a conflict is reported. Unlike Export: writes into the already chosen file instead of creating a new one",
    'Add: записать/обновить РАССТАНОВКУ выделенных моделей в ВЫБРАННЫЙ .ipl (позиция + поворот). Перемещённую модель обновляет на месте (не плодит дубли); LOD модели ставится вместе с ней, у каждой копии — свой LOD в её точке. Отличие от Export: пишет в уже выбранный файл, а не создаёт новый': "Add: write/update the PLACEMENT of the selected models in the CHOSEN .ipl (position + rotation). A moved model is updated in place (no duplicates); the model's LOD is placed with it, each copy gets its own LOD at its own spot. Unlike Export: writes into the already chosen file instead of creating a new one",
    'Синхронизация IPL → Blender.\n\n    Привязанные модели находят свою строку в своём IPL (по содержимому) и\n    получают её позицию/поворот. Непривязанные привязываются к ближайшей\n    свободной строке своей модели (в пределах 0.5 м) из списка IPL / папки\n    игры / выбранного файла. Работает по выделению, пустое выделение — вся\n    сцена.': 'Sync IPL → Blender.\n\nLinked models find their row in their own IPL (by content) and take its position/rotation. Unlinked ones get linked to the nearest free row of their model (within 0.5 m) from the IPL list / game folder / chosen file. Works on the selection; empty selection = the whole scene.',
    'Вернуть выделенные модели на их координаты из IPL (позиция и поворот).\n\nПривязанная модель берёт свою строку из своего IPL. Непривязанная — ближайшую\nсвободную строку своей модели во всех IPL (список / папка игры / выбранный)': 'Move the selected models back to their coordinates from IPL (position and rotation).\n\nA linked model takes its row from its own IPL. An unlinked one takes the nearest free row of its model in all IPLs (list / game folder / chosen)',
    'Экспорт «каждая модель в свой IDE»: обновляет строки выделенных моделей\n    в тех IDE, к которым они привязаны (импортом или прошлым Add). Модели без\n    своего IDE не пишутся — добавь их через «Add» в выбранный IDE.': 'Export «each model to its own IDE»: updates the rows of the selected models in the IDEs they are linked to (by import or a previous Add). Models without an IDE of their own are not written — add them with «Add» to the chosen IDE.',
    'Обновить координаты выделенных моделей в их родных IPL.\n\nКаждая модель пишется в тот IPL, к которому привязана (импортом или прошлым\nAdd) — новая позиция и поворот, LOD переезжает вместе с ней. Файл, выбранный в\nбоксе IPL, при этом не используется': 'Update the coordinates of the selected models in their own IPLs.\n\nEach model is written to the IPL it is linked to (by import or a previous Add) — new position and rotation, its LOD moves along. The file chosen in the IPL box is not used',
    'Удалить выделенные объекты из их IPL и снять привязку.\n\nОбъекты остаются в Blender, их inst-строки удаляются из того IPL, к которому\nони привязаны. LOD модели удаляется тоже (если он не нужен другой модели).\nlod_index всех остальных строк пересчитывается': "Remove the selected objects from their IPL and unlink them.\n\nThe objects stay in Blender; their inst rows are removed from the IPL they are linked to. The model's LOD is removed too (unless another model needs it). lod_index of all other rows is recomputed",
    'Проверить IPL-привязки, ничего не двигая.\n\nПривязанные модели ищут свою строку; если её больше нет — привязка снимается.\nНепривязанные узнаются по строке своей модели рядом (0.5 м) или по\nединственной свободной строке этой модели. Пустое выделение — вся сцена': 'Check IPL links without moving anything.\n\nLinked models look for their row; if it is gone, the link is removed. Unlinked ones are recognised by a row of their model nearby (0.5 m) or by the only free row of that model. Empty selection = the whole scene',
    'Удалить выделенные модели из их IDE и снять привязку.\n    Строка удаляется, только если под этим ID в файле именно эта модель.\n    LOD модели удаляется вместе с ней.': "Remove the selected models from their IDE and unlink them.\nA row is removed only if that ID in the file really is this model.\nThe model's LOD is removed with it.",
    'Verify обоих: IDE-ссылок (по model_id) + IPL-ссылок (строка ищется по содержимому).': 'Verify both: IDE links (by model_id) + IPL links (the row is found by content).',
    'Del: удалить строки ВЫДЕЛЕННЫХ моделей (и их LOD) из выбранного .ide. Удаляет только если под этим ID в файле именно эта модель': 'Del: remove the rows of the SELECTED models (and their LODs) from the chosen .ide. Removes only if that ID in the file really is this model',
    'Del: удалить расстановку ВЫДЕЛЕННЫХ моделей (и их LOD) из выбранного .ipl. Выделенный LOD без модели — отвязывается от своих моделей': 'Del: remove the placement of the SELECTED models (and their LODs) from the chosen .ipl. A LOD selected without its model is detached from its models',
    '«{0}»: LOD взят из IDE — {1} (ID {2}, {3})': '«{0}»: LOD taken from IDE — {1} (ID {2}, {3})',
    '«{0}»: у LOD «{1}» ID/имя самой модели — взят LOD из IDE': "«{0}»: LOD «{1}» has the model's own ID/name — LOD taken from the IDE",
    'LOD из IDE: {0} (ID {1})': 'LOD from IDE: {0} (ID {1})',
    'в IDE: {0}': 'in IDE: {0}',
    'LOD этой модели, найденный в IDE (меша LOD в сцене нет). «Add» в IPL ставит его строку вместе с моделью': "This model's LOD found in the IDE (no LOD mesh in the scene). IPL «Add» places its row together with the model",
    # Frame-hierarchy audit (ops/frame_hierarchy.py) — lower-case form used
    # inside a sentence, unlike the capitalised 'Игра упадёт' above.
    'игра упадёт': 'the game will crash',
    # GTA Geo (tab currently not registered — the properties still are).
    'Папка Auto-Building': 'Auto-Building folder',
    'Папка assets аддона Auto-Building — в ней лежит Auto-Building_1.2.6_Start.blend с заготовкой': 'The Auto-Building addon\'s assets folder — it holds Auto-Building_1.2.6_Start.blend with the starter object',
    # Rest of the GTA Geo strings (ops/geo_curb_ops, ops/geo_building_ops,
    # ui/geo_panels) — kept translated so the tab needs no locale work if
    # it is registered again.
    'Укажи папку assets Auto-Building': 'Set the Auto-Building assets folder',
    'Основание добавлено': 'Base added',
    'Заготовка здания добавлена': 'Building starter added',
    'В файле нет объекта заготовки': 'The file has no starter object',
    'Меш пустой — включи вывод реальной геометрии в модификаторе': 'The mesh is empty — enable real geometry output in the modifier',
    'Полигонов:': 'Faces:',
    'Выдели меш-объекты': 'Select mesh objects',
    'Тротуара в файле нет': 'There is no pavement in this file',
    'Снято:': 'Removed:',
    'Нет граней, заливать нечего:': 'No faces, nothing to fill:',
    'Группа собрана с замечаниями, смотри системную консоль:': 'The node group was built with warnings, see the System Console:',
    'Группа пересобрана, сборка': 'Node group rebuilt, build',
    'Тротуар добавлен на объектов:': 'Pavement added to objects:',
    'Процедурная застройка': 'Procedural environment',
    'из готовых кусков': 'from ready-made pieces',
    'Весь участок — тротуар по умолчанию': 'The whole patch is pavement by default',
    'Бордюр встаёт только вокруг травы': 'The kerb is only built around grass',
    'Новое здание': 'New building',
    'Собрать в меш': 'Build into a mesh',
    'Тротуар и бордюр': 'Pavement and kerb',
    'Выдели участок и нажми кнопку': 'Select a patch and press the button',
    'Настройки — в модификаторе «INU Curb»': 'The settings live in the «INU Curb» modifier',
    'Снять тротуар': 'Remove pavement',
    'Реальная геометрия': 'Real geometry',
    'Тротуаров в сцене:': 'Pavements in the scene:',
    'У меша нет граней': 'The mesh has no faces',
}
