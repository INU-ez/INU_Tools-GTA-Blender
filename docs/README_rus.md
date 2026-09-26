<div align="center">

![INU Tools Logo](logo.jpg)

# INU_Tools (GTA SA)

**Blender-аддон для моддинга GTA San Andreas — полный пайплайн от моделинга до IMG-архива.**

<p>
  <img src="https://img.shields.io/badge/Blender-2.83%E2%80%935.1-orange?logo=blender" alt="Blender">
  <img src="https://img.shields.io/badge/Version-2.4.1-green" alt="Version">
  <img src="https://img.shields.io/badge/License-GPL--3.0-blue" alt="License">
</p>

**[🇬🇧 English](../README.md)** · **[📖 Документация](DOCS_rus.md)**

</div>

---

## Возможности

<table>
<tr>
<td width="50%" valign="top">

- **Живой мост с Ariane** — двусторонняя правка в реальном времени: импорт по клику, отправка моделей / позиций / инстансов обратно.
- **Нативные парсеры** DFF / COL / TXD / IDE / IPL / IMG / IFP / FXP — без внешних зависимостей.
- **Полный round-trip карты** — IMG → Blender → правка DFF + COL + TXD → IMG.
- **Экспорт сверен с движком** — каждый писатель проверяется по тому, что реально читает `gta_sa.exe`: всё, на чём игра упадёт, названо до записи файла.
- **Надёжная синхронизация IDE / IPL** — строка ищется по содержимому, а не по номеру: у копий своя расстановка и свой LOD, чужие строки не перезаписываются, файл пишется атомарно с резервной копией.
- **Редактор тайм-циклов** (`timecyc.dat`) — превью погоды и часа как настоящий свет, правка срезов, туман и PostFX; читает файлы SA, Vice City и III.
- **Запекание текстур и прилайта** — AO / Diffuse / Shadow / Alpha, процедурные маски грязи / износа кромок / кривизны / толщины / гранджа, ручная роспись любого слоя кистью, прилайт от всех ламп + HDRI, LightMap.
- **Skinned DFF + IFP** — педы с 294+ ванильными анимациями, IK-риг, редактор иерархии фреймов.
- **Редактор `effects.fxp`** — 82 системы частиц с живой симуляцией во вьюпорте.
- **ID Manager** — мульти-пресеты, sync со сценой, FLA-расширение, детекция конфликтов.
- **Мульти-игра** — GTA III / VC / SA с авто-детектом при импорте.
- **Производительность** — Import Map ~10×, Export to IMG ~5–15×.

</td>
<td width="50%" valign="top">

![2DFX tutorial](gif/cj-explosion.gif)

</td>
</tr>
</table>

→ **[Что нового](../../../releases/latest)** · [История версий](../../../releases)

## Поддержка форматов

| Формат | Импорт | Экспорт | Правка | Что это |
|---|:---:|:---:|:---:|---|
| **DFF** | ✅ | ✅ | ✅ | 3D-модель RenderWare (геометрия, скиннинг, материалы, 2DFX, флаги) |
| **COL** | ✅ | ✅ | ✅ | Коллизия (COL3, 179 типов поверхностей) |
| **TXD** | ✅ | ✅ | ✅ | Текстуры (DXT1/DXT5, параллельно, pure numpy, drag&drop) |
| **IDE** | ✅ | ✅ | ✅ | Определения объектов (objs/tobj/anim/cars/peds/weap/hier/txdp) |
| **IPL** | ✅ | ✅ | ✅ | Размещение объектов (текст + binary, 11 секций, FLA) |
| **IMG** | ✅ | ✅ | ✅ | Архив ресурсов (VER2) — DFF + LOD + COL + TXD |
| **IFP** | ✅ | ✅ | ✅ | Анимации (294+ ванильных, batch import, ANP3/ANPK/ANP2) |
| **FXP** | ✅ | ✅ | ✅ | Частицы `effects.fxp` — 82 системы, viewport-симуляция |
| **CST** | ✅ | ✅ | ✅ | Текстовый формат Steve's COL Editor |
| **water.dat** | ✅ | ✅ | ✅ | Вода: типы, snap, waterclear256 |
| **paths / tracks / nodes / flight** | ✅ | ✅ | ✅ | Пути машин/педов, ж/д, path nodes, маршруты полётов |

Плюс: тайм-циклы, зоны (`map.zon`/`info.zon`), камеры, растительность (`plants.dat`), X Radar Maker.
Подробности — в **[документации](DOCS_rus.md)**.

## Установка

**Blender 4.2+ (extensions):** [extensions.blender.org](https://extensions.blender.org) → *Get Extensions* → найди «INU Tools», либо *Edit → Preferences → Get Extensions → Install from Disk…* с релизным `.zip`.

**Вручную (Blender 2.83+):** скопируй папку `INU_tools/` в `Blender/<версия>/scripts/addons/`, затем *Edit → Preferences → Add-ons* → включи **INU_tools (gta_sa)**.

> Рекомендую ставить [последний релиз](../../../releases/latest). Ветка `main` — свежее, но там бывают баги и незаконченные фичи; если ловишь баг с `main`, укажи это в issue.

## Совместимость

| | |
|---|---|
| **Blender** | 2.83 – 5.1 (для extensions.blender.org — 4.2+) |
| **Игра** | GTA San Andreas (основная); Vice City и III — экспериментально |
| **MTA** | Совместим с MTA:SA |
| **ОС** | Windows / Linux / macOS |

<details>
<summary>Мульти-игра (III / VC / SA) — детали</summary>

Целевая игра задаётся дропдауном в шапке N-панели **GTA Tools** (SA / VC / III), все экспортёры идут через нужный диспатч форматов.

- **DFF/COL/TXD/IDE/IPL/IMG/IFP** читаются и пишутся для всех трёх игр (COLL/COL2/COL3, VER1/VER2, ANPK/ANP3 и т.д.).
- SA-only фичи (Pipeline-чанк, UV-аним, multi-mesh LOD, SunGlare) при записи в III/VC отбрасываются с предупреждением; форматы идут по движку каждой игры (VC PC — это RW 3.4.0.3, коллизии `COLL` и текстуры D3D8, а не RW 3.5).
- Редактор тайм-циклов читает `timecyc.dat` III и VC — 24 почасовых среза и поля именно этой игры (цвет Trails, верхние облака, пары Ambient у VC).
- Мост Ariane экспортирует под игру сцены и предупреждает, если рядом стоит установка другой игры.
- Полный round-trip карты — пока только для SA; для III/VC — импорт ассетов и экспорт отдельных DFF/COL/TXD.
- Кросс-игровой COL-экспорт схлопывает часть из 179 поверхностей SA (`GRASS_SHORT` ↔ `GRASS_LONG` и т.п.).

Полная таблица форматов по играм — в **[документации](DOCS_rus.md)**.

</details>

## Ссылки

- 📖 [Документация](DOCS_rus.md)
- 📹 [Видеоурок: IDE / IPL / IMG / Map](https://www.youtube.com/watch?v=Jw_R9QFYxWE)

## Благодарности

- **[DragonFF](https://github.com/Parik27/DragonFF)** (Parik, GPL-3.0) — совместимые имена свойств материалов/объектов для удобного перехода.
- **[RenderWare](https://en.wikipedia.org/wiki/RenderWare)** — движок GTA SA, документация форматов.
- **[Ariane](https://github.com/Dryxio/ariane)** (Dryxio) — редактор карт для III / VC / SA (librw / euryopa), с которым работает живой мост.
- **[Itera Tools 3](https://itera.gumroad.com/l/IteraTools3)** — vertex lighting; в аддоне есть подпанель для применения его пресетов.
- **[ChunkTools](https://github.com/milevskiy27/ChunkTools)** от **[milevskiy](https://github.com/milevskiy27)** (Apache-2.0) — из него адаптирована кнопка «Разделить на чанки».

**Автор:** INU (Discord `1.n.u` · [сервер](https://discord.gg/sqtGAVTGdy)) · зеркало анимаций — **yeezyk** · нарезка карты — **[milevskiy](https://github.com/milevskiy27)** · фикс тайминга ключей ANP3 — **[sexorcist00](https://github.com/sexorcist00)**

**Лицензия:** [GPL-3.0](LICENSE)
