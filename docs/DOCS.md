# INU_Tools (GTA SA) — Documentation

> **[Русская версия / Russian version](DOCS_rus.md)**

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
  - [Floating window (Validation)](#floating-window-validation)
- [Multi-game support (III / VC / SA)](#multi-game-support-iii--vc--sa)
- [Export / Import](#export--import)
  - [DFF (Models)](#dff-models)
  - [COL (Collision)](#col-collision)
  - [TXD (Textures)](#txd-textures)
  - [Export All (Batch)](#export-all-batch)
- [IDE / IPL / IMG](#ide--ipl--img)
  - [Import Map Workflow](#import-map-workflow)
  - [IDE (Definitions)](#ide-definitions)
  - [IPL (Placement)](#ipl-placement)
  - [IPL Sections](#ipl-sections)
  - [IMG Archive](#img-archive)
  - [Preset / data folder](#preset--data-folder)
  - [BBox Mode](#bbox-mode)
  - [Model type detection (DFF / LOD / COL)](#model-type-detection-dff--lod--col)
  - [LOD Detection](#lod-detection)
  - [Model ID Manager](#model-id-manager)
- [Materials](#materials)
  - [GTA Material](#gta-material)
  - [COL Surface Types](#col-surface-types)
  - [Textures](#textures)
  - [Alpha Materials](#alpha-materials)
- [Prelight (Vertex Colors)](#prelight-vertex-colors)
  - [Baking](#baking)
  - [Scatter Color](#scatter-color)
  - [Post-Processing](#post-processing)
  - [COL Light](#col-light)
  - [Presets](#presets)
  - [Adjust Color (per-attribute V-offset)](#adjust-color-per-attribute-v-offset)
- [2DFX Effects](#2dfx-effects)
- [Particle Effects (effects.fxp)](#particle-effects-effectsfxp)
- [UV Tools](#uv-tools)
- [Check](#check)
  - [Validate Scene](#validate-scene)
  - [Export audits — "Game will crash"](#export-audits--game-will-crash)
  - [File Scanner](#file-scanner)
  - [Lint Profiles](#lint-profiles)
  - [Map Analyzer (Game Validator)](#map-analyzer-game-validator)
- [Texture Browser](#texture-browser)
- [Texture Baking](#texture-baking-210)
- [Characters (Skinned DFF)](#characters-skinned-dff)
- [Animated Map Objects](#animated-map-objects)
- [Cutscene Cameras (.dat)](#cutscene-cameras-dat)
- [Handsign (ghands.ifp)](#handsign-ghandsifp)
- [Fragment Mesh](#fragment-mesh)
- [Split into Chunks](#split-into-chunks)
- [Water IO](#water-io)
- [Map zones (map.zon)](#map-zones-mapzon)
- [Path IO](#path-io)
- [Vehicles](#vehicles)
- [Grass](#grass)
- [X Radar Maker](#x-radar-maker)
- [Time cycles (timecyc.dat)](#time-cycles-timecycdat)
- [LightMap (beta_MTA)](#lightmap-beta_mta)
- [Integrations](#integrations)
  - [Ariane Bridge](#ariane-bridge)
- [Asset Library](#asset-library)
- [Advanced](#advanced)
  - [Map Export](#map-export)
  - [Binary IPL Write](#binary-ipl-write)
  - [UV Animation](#uv-animation-210)
  - [Breakable Objects](#breakable-objects)
  - [IFP Batch Import](#ifp-batch-import)
  - [GTA Material Panel](#gta-material-panel)
  - [Bitmaps Manager](#bitmaps-manager)
  - [CST IO](#cst-io)
  - [Vehicle Scale Helper](#vehicle-scale-helper)
  - [Vehicle Damage Variants](#vehicle-damage-variants)
  - [Train Station Markers](#train-station-markers)
  - [Roadblocks & Traffic Lights](#roadblocks--traffic-lights)
  - [FLA4 Path Format](#fla4-path-format)
- [Technical Reference](#technical-reference)
  - [Project Structure](#project-structure)
  - [Core Modules](#core-modules)
  - [File Formats](#file-formats)
  - [Object Properties (INUObjectProps)](#object-properties-inuobjectprops)
  - [Material Properties (INUMaterialProps)](#material-properties-inumaterialprops)
  - [Scene Properties](#scene-properties)

---

## Installation

1. Download the `INU_tools/` folder (or zip archive)
2. Place `INU_tools/` into Blender addons folder:
   - **Windows:** `%APPDATA%/Blender Foundation/Blender/<version>/scripts/addons/`
   - **Linux:** `~/.config/blender/<version>/scripts/addons/`
   - **macOS:** `/Users/<name>/Library/Application Support/Blender/<version>/scripts/addons/`
3. Blender → Edit → Preferences → Add-ons → enable **"INU_tools(gta_sa)"**

**Requirements:**
- Blender 2.83+ (4.2+ for installs through extensions.blender.org)
- Itera Tools 3 — optional, for vertex lighting

**Settings persistence:** all paths (Game Root, IDE, IPL, IMG, textures) and presets (profiles, material & ID presets, pipeline flag defaults) live in a user-writable data folder — `paths.json` plus per-feature subfolders. By default this is Blender's per-user extension directory; you can point it at any folder of your own via **Properties → Scene → INU Tools → Preset folder** (see [Preset / data folder](#preset--data-folder)). Settings survive addon updates and are restored automatically when Blender starts.

---

## Quick Start

### Export a model to GTA SA

1. Name objects so types are auto-detected — put `LOD` in LOD names (`LODmybuilding`), and use `_DFF` / `_COL` when a model and its collision share a base name (see [Model type detection](#model-type-detection-dff--lod--col))
2. Set **Model ID**, **TXD Name**, **Draw Distance** in object properties (`obj.inu`)
3. Select all, click **Export All** → choose folder
4. Output: `mybuilding.dff`, `mybuilding.col`, `LODmybuilding.dff`, `mybuilding.txd`

### Import the entire GTA SA map

1. Set **Game Root** to GTA SA folder (e.g. `D:\GTA San Andreas\`)
2. Click **Extract Resources** — extracts DFF/COL/textures from IMG into `.inu_cache/` (one-time, ~8 s for one region)
3. Click **Import Map** — cache-only import, ~30 s for a full LA-sized district

### Hotkeys

| Key | Action |
|-----|--------|
| `Shift+T` | Toggle UV Editor |
| `Shift+A` | Add GTA SA model (Army.dff / Admiral.dff) |

### Floating window (Validation)

A free-floating GPU-rendered window gives one-click access to the pre-export sweep without scrolling the N-sidebar:

| Window | What it holds | Toggle |
|---|---|---|
| **Validation** | Pre-export sweep results (quaternions, paintjob, UV-anim × night vcols, _ok/_dam pairs) with one-click fixes | Click 🪟 in the **Check** panel header |

The floater is **draggable** (any non-button area), **collapsible** to the title bar, **dockable per-workspace** (Lock icon — appears only in pinned workspace), and uses your current Blender theme palette. Position survives `.blend` save/load.

> The other floaters (Info, Import/Export, Lighting, IDE/IPL/IMG) had their launch buttons removed — only Validation remains. The underlying floater code still exists, but those windows are no longer exposed in the UI.

---

## Multi-game support (III / VC / SA)

The active game is picked from the top of the **GTA Tools** N-sidebar — three buttons **San Andreas / Vice City / GTA III**. Every exporter, validator, and lint check routes through this choice. Default = San Andreas (the addon's primary target). Import auto-detects the file's game and either flips the scene (when fresh) or shows a warning suggesting to switch the tab manually.

### Format matrix

| Format | III (RW 3.3) | VC (RW 3.5) | SA (RW 3.6) |
|---|:-:|:-:|:-:|
| **DFF** read | ✅ auto-detect by RW version | ✅ | ✅ |
| **DFF** write | ✅ (skips SA-only Night vcols, Pipeline chunk, UV anim) | ✅ (skips Night vcols, Pipeline) | ✅ |
| **COL** | ✅ `COLL` v1 | ✅ `COL2` v2 | ✅ `COL3` v3 |
| **TXD** | ✅ (RW lib_id per game) | ✅ | ✅ |
| **IDE** | ✅ (5-field OBJS, no `txdp`/`2dfx`) | ✅ (5-field, no `2dfx`) | ✅ (multi-mesh, `txdp`, `2dfx`) |
| **IDE cars cols** | 12 | 13 (+ `anims`) | 15 (+ flags, wheel split) |
| **IDE peds cols** | 7 | 10 (+ anim_file, radio×2) | 14 (+ flags, voice×3) |
| **IPL inst cols** | 12 (scale, no interior) | 13 (interior + scale) | 11 (lod_index, no scale) |
| **IPL binary** | — | — | ✅ `bnry` |
| **IMG** | ✅ VER1 (split `.dir` + `.img`) | ✅ VER1 | ✅ VER2 |
| **IFP** | ✅ ANPK chunked | ✅ ANPK | ✅ ANPK + ANP3 compressed |
| **2DFX storage** | IDE `2dfx` section | IDE `2dfx` section | DFF chunk 0x253F2F8 |
| **2DFX types** | Light, Particle, Strobe | + PedAttractor, SunGlare | + Type 5 (special-IDE) |
| **Surface IDs** | 0–84 (clamp on write) | 0–85 | 0–178 |
| **model_id ceiling** | 6500 | 8500 | 19999 |

### Switching games

**Manual:** click III / VC / SA in the GTA Tools header.

**Automatic on import:** the import operators (DFF/COL/IPL/TXD/IMG) have a "Game" dropdown in the file browser sidebar with **Auto** as the default. Auto reads the file's header/columns and stamps the right game on imported objects. If the detected game differs from the active scene's:

- **Fresh scene (game=SA + 0 INU-tagged objects):** scene auto-flips to detected.
- **Populated scene:** WARNING shown — `Imported file = VC, but the scene's active game = SA. Switch the GTA Tools tab to "VC"`. Tab switch is manual to avoid surprise flips in mixed-game projects.

**On export:** every export dialog opens with an **"Export to game:"** block at the very top — a PC/Mobile row over a SA/VC/III row — that sets the output's RW version (III 3.3 / VC 3.4 / SA 3.6) and IPL/IDE column layout. It defaults to the project game (set by auto-detect on import); override it right before exporting.

**GTA III textures (auto R↔B):** III uses palettized (PAL8) textures whose palette is stored BGRA. The importer auto-swaps R↔B **only** for D3D8 palettized textures, so III colours import correctly (bark stays brown, not blue). VC (16-bit) and SA are left untouched — no manual toggle, keyed off each texture's own `platform_id`.

### Cross-game translation (lossy)

When you import a III file and export it as SA (or vice versa), the writer routes data through canonical-category tables so the bytes match the target engine's expectations.

- **COL surface IDs** — 12 canonical categories (TARMAC, GRASS, WOOD, METAL, GLASS, …) via `core/surface_translate.py`. SA's 178 surfaces collapse to ~12 categories on cross-game; SA → VC → SA loses sub-type distinctions like `GRASS_SHORT` vs `GRASS_LONG`. Each material carries `inu.col_source_game` so this only fires on actual game mismatch.
- **IDE objs.flags** — bit values mean different things per game. Example: bit `0x20` is `IGNORE_LIGHTING` in III/VC but anim-only in SA. `core/ide_flag_translate.py` translates via 19 categories. UI shows only the checkboxes valid for the active game (III=6, VC=10, SA=15).
- **PEDS cars_can_drive** — VC inserted `normal` at bit 0, shifting III's positions by 1. `core/ped_mask_translate.py` re-maps via canonical class names. `IdePed.source_game` tags imported peds.

### Validate Scene — cross-game warnings

When the scene targets III/VC but objects still carry SA-only features, **Validate before export** flags them:

- `model_id > vanilla_max` (would need FLA)
- `has_night_vcols` (SA-only RW extension)
- `has_multi_mesh_lod` (downgrades to single-mesh)
- `has_uv_anim_material` (III-only; UV anim is RW 3.5+)
- `fx_2dfx_ids` outside per-game allowlist

### Known limitations

- **Full map round-trip is SA-only.** III/VC modders can import vanilla DFF/COL/TXD/IDE/IPL/IMG individually, but the Map Import pipeline (district auto-split, bulk IMG rebuild) was authored for SA's data layout.
- **Asset Library Builder is SA-only.** Future work — needs III/VC source parsers.
- **IFP** — ANP3 (compressed int16) is SA-native; III/VC auto-downgrade to ANPK with a warning if you forget to switch the export format.
- **2DFX import for III/VC IDE** creates placeholder Empties (position + type + color), with raw type_params stashed on the Empty for byte-identical re-export. Per-type Blender prop mapping (corona texture, particle name, attractor behaviour) is partial — Light and Particle are wired; PedAttractor / SunGlare / Strobe re-emit via stashed params only.

---

## Export / Import

**Panel:** View3D → Sidebar (N) → GTA Tools → Export / Import

> The 🌐 planet icon in the panel header opens [Ariane support (INU Tools + DragonFF)](https://github.com/INU-ez/ariane-support-INU-Tools-and-DragonFF-) — a map editor for round-trips with the addon (temporary fork until Ariane's public release).

### DFF (Models)

| Button | Operator | Description |
|--------|----------|-------------|
| Import DFF | `gtatools.import_dff` | Import .dff file with mesh, materials, UV maps |
| Export DFF | `gtatools.export_dff` | Export selected mesh to .dff (GTA SA v3.6.0.3) |

**Export includes:** geometry, materials, vertex colors (Day/Night), UV maps, normals, 2DFX effects, BinMesh PLG.

**Auto TXD:** when importing DFF, automatically imports .txd from the same directory if found.

**Textures from files (2.4.0):** whatever the TXD did not cover (or everything, when there is no
`.txd` next to the model) is pulled in as ordinary images — `png / jpg / tga / bmp / dds / tiff /
webp` — by looking for a file named after the texture in the model's folder **and its subfolders**.
Drag-drop goes through the same path. The report says how many textures came from there:
`textures from files: N`.

**Platform (2.4.0):** a **PC / Mobile** selector in the import panel. Mobile DFFs are recognised from
the data itself; the selector sets the default for later exports and hints.

**Import 2DFX:** a toggle on DFF import (single Import, the Import-All file browser, and drag-drop). Creates the 2DFX effect empties baked into the DFF — lamps/coronas, particles, ped attractors, sun glare, signs, etc. On by default; turn it off to import the model geometry without its effects.

> 💡 **Example — import a single model:** File → Import → GTA SA DFF → pick `admiral.dff`. The addon parses geometry, materials, UV. If `admiral.txd` sits next to it, textures are applied automatically.

> 💡 **Example — export a single mesh:** select mesh → N → Export / Import → **Export DFF** → choose path → saves with current materials and vertex colors.

#### DFF format limits (uint16 / uint8)
RenderWare packs triangle indices and counts into small integer types — these limits apply **per geometry (Atomic)**:

| Field | Type | Max |
|---|---|---|
| Vertices | u16 (triangle index in `<4H>`) | 65 536 |
| Triangles | — | 65 536 |
| Materials | u16 (material index in triangle) | 65 536 |
| UV layers | u8 (bits 16-23 of geometry flags) | 255 (SA renders max 2) |
| Bones in Skin PLG | u8 | 255 |

If a mesh exceeds the limit, export raises a clear error such as:
```
admiral.dff: geometry #0: 78432 vertices — RenderWare stores triangle indices
in uint16 (max 65536). Split the mesh or simplify (Decimate).
```

**There is no workaround**: the limit is hard-coded into the binary format and the RenderWare engine. Either split the mesh into multiple `model_id`s or simplify the geometry.

### COL (Collision)

| Button | Operator | Description |
|--------|----------|-------------|
| Import COL | `gtatools.import_col` | Import .col with surface materials |
| Export COL | `gtatools.export_col` | Export as COL3 format |
| Generate COL | `gtatools.auto_col` | Build a collision mesh from the selected model — **Convex hull** or **Bounding box** |

**Generate COL** (`gtatools.auto_col`, button "Generate COL" in the Export/Import section): select a model and it creates an editable `<name>_COL` mesh, either a **convex hull** ("Convex Hull") or an axis-aligned **bounding box** ("Bounding Box"). The mesh is tagged `inu.type='COL'` and flows into normal COL export; you can edit it afterwards like any COL.

COL export writes surface material IDs and keeps the geometry in model-local space. It bakes the object's **scale** but **not its rotation** — a viewport rotation is placement (it belongs in the IPL), so it is never baked into the collision, and the COL matches the DFF under the same IPL placement.

> 💡 **Example:** create a cube, name it `mybuilding_COL`, assign a material with `col_mat_index = 0` (default asphalt) in Properties → Material → **COL Surface Type**. Select → **Export COL** → you get `mybuilding.col` with the correct surface material.

#### COL format limits (uint16)
COL2/COL3/COL4 stores counts and indices as **uint16**, so per-model limits are:

| Field | Max |
|---|---|
| Vertices | 65 536 |
| Faces (triangles) | 65 535 |
| Spheres / boxes | 65 535 each |
| Shadow mesh (verts/faces) | same limits |
| Header `model_id` | 65 535 |

If a mesh exceeds the limit, export raises a clear error such as:
```
collision.col: 'collision': 78432 faces — COL format supports max 65535.
Split the mesh or simplify (Decimate).
```

**There is no workaround**: the limit is hard-coded into the COL format and the RenderWare engine. Either split the mesh into multiple `model_id`s or simplify (vanilla SA collisions are typically below 5–10k tris).

### TXD (Textures)

| Button | Operator | Description |
|--------|----------|-------------|
| Import TXD | `gtatools.import_txd` | Extract textures and assign to materials |
| Export TXD | `gtatools.export_txd` | Compile textures into .txd archive |

**Compression backend:** pure-numpy DXT encoder bundled with the addon (`core/dxt.py`) — vectorized BC1/BC3, ~7× faster than the old cluster-fit path on the textures vanilla SA actually ships. No external binaries needed. An experimental `bpy.gpu` compute-shader path is selectable in Scene properties (`gtatools_dxt_backend`).

**Supported formats:** DXT1 (opaque), DXT3 (sharp alpha), DXT5 (smooth alpha). Auto-detected based on alpha channel.

> 💡 **Example — quick TXD build:** a mesh with 3 textures (brick, window with alpha, logo) → select → **Export TXD** → you get a `.txd` where brick is DXT1, window is DXT5, logo is DXT3 — format auto-picked based on each image's alpha channel.

**Append to existing TXD (2.1.0).** The export dialog (and Export All) has an **"Append to existing"** checkbox. If the chosen `.txd` already exists, the scene's textures are **added/updated** in it (matched by name, case-insensitive) while **every other texture in the file (from other models) is kept byte-for-byte**. Without the checkbox the file is fully overwritten.

> ⚠ **Gotcha — cache & in-place edits.** Encoded DXT is cached by `session_uid+size`, so an in-place pixel edit (Image Editor) used to ship the stale version. The cache is now cleared on every manual export — but if you recolour a texture with a **material node** (Hue/Sat etc.), export **ignores** it: it reads the Image datablock itself, not the node result. Bake/save the edit into the image.

> ⚠ **Gotcha — textures too dark/bright (bit depth).** `image.pixels` for **16/32-bit** PNGs (and EXR) are scene-linear, while **8-bit** ones are already sRGB. The exporter accounts for this (it linear→sRGB-encodes only float images). If a TXD texture's brightness looks off, check the source bit depth and colour space (sRGB vs Non-Color).

### Export All (Batch)

| Button | Operator | Description |
|--------|----------|-------------|
| Export All (To Folder) | `gtatools.export_all` | Batch export DFF+COL+LOD+TXD |

Select your model + its LOD + collision (types are auto-detected — `LOD` in the name marks a LOD, `_DFF`/`_COL` separate a model from its collision), click Export All, choose output folder.

**Toggles:** DFF / COL / LOD / TXD — enable/disable each format.

**Pipeline:** None / Building (Day/Night vertex colors) / Reflections (window reflections).

> 💡 **Example — export a building with LOD and collision:** you have three meshes `hospital_DFF`, `hospital_LOD`, `hospital_COL`. Select all three → **To Folder** → you get 4 files at once: `hospital.dff` + `hospitalLOD.dff` + `hospital.col` + `hospital.txd`. Ready to drop into the game.

### File Menu

All formats are also accessible via **File > Import** and **File > Export**:
- GTA SA DFF (.dff)
- GTA SA COL (.col)
- GTA SA TXD (.txd)
- GTA SA IDE (.ide)
- GTA SA IPL (.ipl)

### Drag & Drop

Drag PNG/JPG/TGA images from File Browser into the 3D viewport to automatically create a material with that texture assigned.

---

### Multi-select DFF Import (2.1.0)

**Menu:** File → Import → **INU Import** *(or View3D → Sidebar (N) → GTA Tools → Export / Import → **DFF**)*

The DFF importer now accepts many files at once. Ctrl- or Shift-click any number of `.dff` files in the file browser and every one is imported as a separate model in a single run, with a live progress bar (press **ESC** to abort — models already built stay in the scene).

**Pipeline:**
1. In the N-panel open **GTA Tools → Export / Import** and click the **Import** button, then pick **DFF** — or use the popover **DFF** entry directly.
2. In the file browser, Ctrl/Shift-select all the `.dff` files you want.
3. (Optional) In the sidebar set **Game** — leave on **Auto-detect** to read each file's RW version, or force III / Vice City / San Andreas.
4. (Optional) toggle **Auto TXD** — see *smart TXD auto-pull* below.
5. Click **Import DFF**. Each selected file is parsed and built in turn; the status bar shows `current/total`.

**What you get automatically (no extra clicks):**

| Feature | What it does |
| --- | --- |
| Smart TXD auto-pull | With **Auto TXD** on, for each DFF the addon looks for a matching `.txd` next to it: ① `<dffname>.txd` in the same folder, ② a `.txd` covering ≥50% of the DFF's textures (highest coverage wins, smaller file breaks ties), ③ the only `.txd` in the folder. Only the textures that DFF actually references are decoded, so dropping a model into an already-loaded map stays fast. |
| LOD-aware naming | A file recognised as a LOD (e.g. `LODham_orz_str_18`) is named `ham_orz_str_18_LOD`; normal models get the `_DFF` suffix. Multi-part DFFs keep clean frame names. |
| Auto weld + sharpen | Map/terrain meshes (no authored normals) are welded and their hard edges split right into the geometry — no piles of EdgeSplit modifiers, so FPS stays high. |
| Custom split normals | The DFF's per-vertex normals are re-applied as custom split normals, so the model shades **exactly** as it was authored (hard/soft edges preserved). |

> 💡 **Example — import a whole folder of buildings at once:** Open **INU Import**, press Ctrl+A in the file browser to select every `.dff` in a building folder, and import. Each becomes its own object, each pulls its matching `.txd`, LODs are named `…_LOD`, and authored shading is preserved — no per-file repetition.

> Drag-and-drop also works: drag one or several `.dff` files straight into the 3D viewport and they import as a batch with the same auto-TXD behaviour.

### Import dialog — format filter (2.1.0)

**Menu:** File → Import → **INU Import**

The **INU Import** dialog is a pure dispatcher: it imports **exactly** the files you tick, each through its own importer by extension. The sidebar header **Show formats:** has six toggle buttons that filter which file types the browser shows:

| Toggle | Extension |
| --- | --- |
| **DFF** | `*.dff` |
| **COL** | `*.col` |
| **CST** | `*.cst` |
| **TXD** | `*.txd` |
| **IDE** | `*.ide` |
| **IPL** | `*.ipl` |

- Untick a format and those files disappear from the browser; the list re-filters instantly.
- There is **no** auto-TXD pull here — if you want textures, tick **TXD** and select the `.txd` in the list. (Auto-TXD lives in **Import DFF** / drag-drop, not here.)
- If a `.txd` is selected alongside a `.dff`, the TXD is loaded first so the DFF's materials immediately pick up its images.

> 💡 **Example — load a model plus its textures and collision in one go:** Open **INU Import**, leave **DFF**, **TXD** and **COL** ticked, untick the rest, select `bistro.dff`, `bistro.txd` and `bistro.col`, and import. All three load together with textures already linked.

### Export DFF — per model (2.1.0)

**Panel:** View3D → Sidebar (N) → GTA Tools → Export / Import → **DFF** (under the **Export** popover)

The mirror of multi-select import: select several models and get **one `.dff` per model**, each named from its model name. Parts of a single model (a hierarchy) export into one file.

**Pipeline:**
1. Select the model(s) in the viewport. The panel's top box shows the detected **DFF / LOD / COL** counts so you can confirm the batch size.
2. Open the **Export** popover and click **DFF**.
3. In the file browser pick the destination **folder**. The sidebar reminds you *"Each selected model → its own .dff"* and shows the **Pipeline + DFF Flags** block (these come straight from each object's N-panel DFF Flags — no separate export override).
4. Confirm. Each model group is written as `<modelname>.dff`.

> 💡 **Example — export 10 reworked props:** Box-select 10 prop meshes, **Export → DFF**, choose your `models/` folder. You get 10 separate `.dff` files named after the meshes, each carrying its own DFF flags.

### Export All — to folder or into .img (2.1.0)

**Panel:** View3D → Sidebar (N) → GTA Tools → Export / Import → **Export** → **All → Folder** or **All → IMG**

**Export All** writes every selected model group — DFF + LOD + COL + TXD (+ optional CST) — in one pass. In the export dialog the **What to export:** row holds the format toggles:

| Toggle | Output per model |
| --- | --- |
| **DFF** | `<name>.dff` |
| **COL** | `<name>.col` |
| **LOD** | `LOD<name>.dff` |
| **TXD** | `<name>.txd` (textures from the DFF + LOD) |
| **CST** | `<name>.cst` *(2.1.0 — collision in Collision File Editor II text format, same mesh as the .col)* |

Conditional options appear when their format is on: a **COL Library** package toggle (all collisions into one multi-entry `.col`), shared-TXD packaging, and the collision auto-light block (shared by COL and CST).

**Also to IDE / IPL** *(paths from the panel)*: when ticked, after the models are written the exporter also appends each one to the **IDE** and **IPL** files currently picked in the **IDE / IPL / IMG** panel (id, name, TXD, draw distance + placement, and the recomputed `lod_index`).

**All → IMG:** at the bottom of the dialog, the **All → IMG** toggle redirects the whole export straight into the `.img` archive whose path is set in the addon preferences — the chosen folder is ignored. If no `.img` path is configured the dialog shows an error and the export is blocked.

**Pipeline (to a folder):**
1. Select all the models to export.
2. **Export → All → Folder**.
3. In the dialog tick the formats you want under **What to export:** (e.g. DFF + COL + TXD).
4. Pick the destination folder and confirm. Files are written per model group with a progress bar.

**Pipeline (into gta3.img):**
1. Set the `.img` path in the addon preferences once.
2. Select the models, then **Export → All → IMG** (or open **All → Folder** and tick **All → IMG**).
3. Confirm — every model is packed directly into that archive, no folder needed.

> 💡 **Example — export 10 selected models straight into gta3.img:** With the addon's `.img` path pointing at `gta3.img`, select your 10 finished buildings and run **Export → All → IMG**. Their DFFs (and TXDs/COLs for the ticked formats) are written into the archive in one operation — no intermediate folder, no manual repacking.

---

## IDE / IPL / IMG

**Panel:** View3D → Sidebar (N) → GTA Tools → IDE / IPL / IMG
**Settings:** Properties → Scene → INU Tools → Import Map

### Import / Export / Map — three tabs

The top of the IDE / IPL / IMG panel has three toggle buttons, **Import** | **Export** | **Map**, like the Ariane tab. These used to be separate collapsible sub-panels. The active tab's button is depressed; everything below belongs to it. The **Map** tab holds the full map import/export workflow (Game Root, region, resource extraction, Import Map / Export Map, BBox) — it moved here from *Properties → Scene → INU Tools*.

**Import tab** — pulls models from the game into the scene:
- **IDE folder** — the game root, or any folder holding `.ide` files (the narrower, the faster the scan).
- **IPL** — multi-select: the 📁 button accepts Ctrl/Shift, and picked files accumulate in the collapsible **IPL to import** list. Import merges all selected IPLs (with a `lod_index` offset).
- **IMG** — path to the primary archive + **LOD / TXD / COL** toggles. These are **ON = load** (the old "Skip" prefixes are gone — LOD on pulls LOD models, TXD on pulls textures, COL on pulls collisions).
- **Find IDE** — scans the game folder for the `.ide` files that declare the selected IPLs' models (**IDE with IPL models** list).
- **Find IMG** — scans the game folder recursively for every `.img` that actually contains the IPL's model DFFs (**IMG with IPL models** list). Import then pulls models from the primary IMG **plus** all found custom archives (e.g. `maps/RESOURCES`). Needed when a custom map's models are split across several `.img`.
- **Import** — the big button. IMG import is **modal**: an **"Import from IMG: X/Y"** counter shows at the bottom, Blender doesn't freeze, and **ESC** cancels. On import it fills: TXD name, LOD partner (`inu.lod_object` from the IPL `lod_index`), distances (LOD → LOD Dist, main model → Draw Dist), and the IDE link (status "In IDE (file)", just like IPL).
- **Refresh from IDE/IPL** — pulls fresh data (distances / TXD / flags / coordinates) from the files **into the scene** (file→scene direction). Handy after editing the files by hand.

**Export tab** — writing and syncing back to files. At the top sits the **Selected model** status box:
- **Selected model** — a per-file status board for the active model. It shows the model name plus one status row each for **IDE**, **IPL** and **IMG** — "In IDE (file)" / "Not in IDE" / "params differ", "In IPL (file)" / "coordinates differ" / "duplicate", "In IMG (file)" / "Not in IMG". Each row carries its own action buttons: **Add** / **Export** (write this model to its own file), a **🗑** to remove it from that file, and a **🔄** icon (in the IPL row, **🔄 = restore coordinates from IPL**; in the IMG row, verify which archive holds the DFF). At the model name: **Check** (read-only present/missing/no-ID) and **🗑 Remove from IDE+IPL** (remove from *both* IDE and IPL and clear link tracking — distinct from a single-file **🗑**).
- Collapsible **IPL to export** and **IDE to export** boxes (collapsed by default) — the *same* shared lists populated on the Import tab (Find IDE/IMG, multi-select IPL) — a round-trip. Each header carries icon-only buttons: **🔄 Refresh-from-files** · **＋ Add** · **📁 Folder** · **🗑 Clear**.
- The **📄 (open in text editor)** button next to the IPL/IDE paths and in the found lists opens the file in the OS external editor.
- Below: **Additional (IPL)** (cull/paths/garages sections + "Replace Empty") and the **IMG** box (Export to IMG / Remove from IMG / Rebuild IMG).

### Adding models to the game — full pipeline

The end-to-end flow for putting one or more models (with or without LOD) into GTA SA. Example: four models, each with a main model, collision, textures and a LOD:

```
base   →  base.dff   base.col   base.txd   LODbase.dff
base1  →  base1.dff  base1.col  base1.txd  LODbase1.dff
base2  →  base2.dff  base2.col  base2.txd  LODbase2.dff
base3  →  base3.dff  base3.col  base3.txd  LODbase3.dff
```

**What each piece is:** **DFF** = the model itself · **COL** = collision · **TXD** = texture container · **LOD** = the low-detail model shown at distance · **IMG** = the game's big archive of .dff/.txd/.col · **IDE** = the model's "passport" (ID, name, TXD, draw distance, flags) · **IPL** = placement in the world (coordinates, rotation, and the main↔LOD link).

**Order that won't break: ID → IMG → IDE → IPL → Rebuild IMG.**

**1. Name objects correctly.** Main model → `base`; LOD → `LODbase` (the `LOD` marker tags it); collision → set its type to COL (or leave it untextured). The addon groups everything by base name: `base` + `LODbase` + collision = one model. Explicit suffixes also work as a manual override (`_DFF`/`_dff`, `_LOD`/`_lod`, `_COL`/`_col`, case-insensitive).

**2. Assign Model IDs FIRST.** The game references models by a numeric ID. ID Manager → Auto-Assign gives each model and each LOD a free ID, e.g. `base`=18000, `LODbase`=18001, `base1`=18002 … **If an ID is still 0, Add-to-IDE/IPL refuses with an error** — a row with ID 0 corrupts the game (0 = the player model). Always assign IDs before adding.

**3. Pack into the IMG.** Pick your `.img`, Export to IMG. It builds and stores `base.dff`, `LODbase.dff`, `base.col`, `base.txd` (× all models). **Name limit: each entry name is ≤ 24 chars incl. extension.** The longest is the LOD (`LOD`+base+`.dff`), so if `base` is too long the export **blocks and asks you to shorten** — a truncated name wouldn't match the IDE/IPL and the model would be invisible. (Collision note: `base.col` goes into the IMG; make sure your setup actually loads collision from there, or embed it in the DFF.)

**4. Add to IDE (define the models).** Pick your `.ide`, Add to IDE. One line per model + one per LOD:
```
18000, base,    base,  299, flags
18001, LODbase, base,  999, flags     ← LOD: own ID, same TXD, far draw distance
18002, base1,   base1, 299, flags
...
```
Rows go to the **picked file** (the chosen file always wins — no silent split). Flags imported from another game (VC/III) are auto-translated to SA.

**5. Add to IPL (place in the world).** Pick your `.ipl`, position the objects, Add to IPL. Each row: ID, name, interior, X/Y/Z, rotation, and **lod_index** — a pointer to the LOD's row in the same IPL. **Select the main model AND its LOD together** so the LOD lands in the same file and the link is set. Adding them separately / to different files loses the link — the addon now tries to recover it from the file and warns if it can't. Coordinates/rotation come from the object's real world transform (parenting and rotation included).

**6. Rebuild IMG (compact).** After exports — especially re-exports — use Rebuild IMG to reclaim dead space (each replace appends new data and leaks the old block). It rewrites the archive cleanly via an atomic file swap.

**In game:** IPL says "model 18000 stands at X" → IDE says ID 18000 is `base`, TXD `base`, draw 299 → the streamer loads `base.dff`/`base.txd`/collision from the IMG → at distance it swaps to `LODbase.dff` (18001). Same in parallel for `base1`/`base2`/`base3`.

### Import Map Workflow

**Step 1: Setup**
- Set **Game Root** to GTA SA installation folder
- Select **Region** (auto-detected from gta.dat: LA, SF, VEGAS, COUNTRY, etc.)
- Make sure **Skip 2DFX** is on for map import (default) — otherwise every street light, corona, and ped-attractor in the district becomes a Blender Light/Empty object (thousands of them) and the viewport grinds to a halt. Leave it off only when importing a single model where you want the effects.
- **Load COL** toggle (default off) — pulls collisions from the cache alongside DFF geometry. Needed for the round-trip workflow (import part of the map → edit → export to IMG in another build). Turn it off if you only care about geometry and want a lighter scene.

**Step 2: Extract Resources**
- Click **Extract Resources** — extracts all DFF, COL, and textures from IMG archives into `.inu_cache/` folder next to your .blend file (so save the .blend first)
- Textures are decoded to PNG in parallel (4 workers, numpy DXT). Already cached files are skipped on re-run
- Typical time: ~8 seconds for one region

**Step 3: Import Map**
- Click **Import Map** — cache-only, reads DFFs, PNG textures and (optionally) COLs from `.inu_cache/` — no IMG access during import
- If cache is empty, the operator reports *"Cache is empty — run «Extract Resources» first"* and bails out
- DFFs are parsed in parallel (4-worker thread pool, numpy releases GIL) while the main thread creates Blender objects — no wait between stages
- COLs are parsed in the same pool. SA ships district-wide lib-COL files (LAs.col, LAn.col …) each containing hundreds of ColModel entries, so the map is keyed by model name (not filename); a DFF named `building01` automatically gets its `building01` ColModel if one exists anywhere in the cached COL libs
- Objects auto-sorted into collections — with **Group by IPL** off, into four flat buckets:
  - **Map_DFF_Far** — draw distance 300+
  - **Map_DFF_Mid** — draw distance 100-299
  - **Map_DFF_Near** — draw distance <100
  - **Map_LOD** — LOD models (detected by name: `LODfoo`, `foo_LOD`, `foo1LOD`, `modeLODlaett`)
  - **Map_COL** — collision meshes (created lazily, only if `Load COL` is on AND at least one match is found). Each COL object shares the transform of its DFF instance
- **Group by IPL** toggle (**default on**) — instead of the four flat `Map_DFF_*` / `Map_LOD` buckets and the global `Map_COL`, objects go into per-IPL collection trees, named after the source IPL filenames (no `Map_` prefix — keeps the round-trip readable, the parent's name matches the original IPL exactly):
  ```
  vegasN/
    vegasN_DFF
    vegasN_LOD
    vegasN_COL
  vegasS/
    vegasS_DFF
    vegasS_LOD
    vegasS_COL
  vegasn_stream0/
    …
  ```
  Each parent collection is hidden during import and re-shown afterwards; sub-collections are created lazily, so an IPL with no LODs gets no `_LOD` sub. Useful when you want to:
  - Hide an entire district at once (toggle the parent's eye icon — DFFs, LODs and collisions go dark together)
  - Co-author a map — author A edits `vegasN`, author B edits `vegasS`, no overlap
  - Keep IPL provenance visible in the outliner so you know where each model came from
  - Round-trip: import → edit → re-export with **Map Export → Split: By collection** rebuilds the original district structure; the collection's name is reused as the district's basename
  - Source IPL is taken from each instance's parent file basename (text IPLs by file path, binary IPLs by their entry name in the IMG archive)
- Typical time: ~30 seconds for a full LA-sized district with COL enabled

**Performance tuning (advanced):**

Enable **Profile Import / Extract** in *Scene → INU Tools → Performance* to dump a timing report into `.inu_cache/_profile.log`. Useful if you want to see where time goes (per-stage wall time, per-thread breakdown, slowest individual calls).

Stage names worth knowing in the report:
- `submit parse jobs` — one-shot; should be sub-second
- `parse wait` — how long the main thread blocked on a DFF worker; near zero means workers keep ahead
- `parse COL files` — upfront aggregation of all .col entries into `model_name → ColModel`
- `loop iter` — total time spent inside the generator body (compare against `Total wall time`; the delta is Blender UI overhead)
- `build objects` / `build_mesh` — bpy work per DFF
- `build COL` / `reuse COL` / `COL transform` — per-model and per-instance COL steps
- `reuse (copy)` — `src.copy()` for repeat instances
- `TXD cache load` — PNG assignment to material nodes
- `transform apply` — DFF location/rotation + inu props

### IDE (Definitions)

> **Per-object properties:** Model ID, Draw Distance, LOD Distance, IDE Flags, Interior, LOD index live in **Properties → Object → "GTA SA: IDE / IPL"**. The same panel shows **ID conflict detection** — if multiple objects share the same Model ID, the addon highlights the error with names of conflicting objects.


IDE files define model properties: ID, texture dictionary, draw distance, flags.

| Button | Operator | Description |
|--------|----------|-------------|
| Add | `gtatools.upsert_ide` | Insert/update entry in IDE file (auto-LOD) |
| Remove | `gtatools.remove_ide` | Remove entry by Model ID |
| Export | `gtatools.export_ide` | Write selected objects to a new IDE file |

> **Add / Del / Export** live on the **Export** tab. There is no standalone "Import" button anymore: geometry comes from **Import from IMG** (Import tab), and **Refresh from IDE/IPL** pulls the definitions into the scene.

**All sections supported:** objs, tobj, anim, cars, peds, weap, hier, txdp.

**Auto-LOD:** when adding DFF+LOD pair, the following are assigned automatically:
- **Model ID:** LOD = DFF ID + 1 (e.g. DFF ID 3500 → LOD ID 3501)
- **Draw Distance:** LOD = 999 (maximum visibility). The HD model is visible up to its draw distance (e.g. 299m), then LOD appears and stays visible up to 999m
- **TXD:** LOD uses the same texture dictionary as DFF

> 💡 **Example — add a building to mymap.ide:** select `building01_DFF` and `building01_LOD` → Object Properties → **INU Tools: Model** → set `Model ID = 3500` on DFF → N → IDE / IPL / IMG → IDE section → set path to `mymap.ide` → **Add**. Two lines get written: `3500, building01, building01, 299` and `3501, LODbuilding01, building01, 999`.

**IDE Flags** (15 checkboxes in object properties):

| Flag | Bit | Description |
|------|-----|-------------|
| IS_ROAD | 1 | Road surface |
| DRAW_LAST | 4 | Transparent, draw last |
| ADDITIVE | 8 | Additive blending |
| NO_ZBUFFER_WRITE | 64 | Don't write to Z-buffer |
| NO_SHADOWS | 128 | Don't receive shadows |
| GLASS_TYPE_1 | 512 | Breakable glass |
| GLASS_TYPE_2 | 1024 | Cracked glass |
| GARAGE_DOOR | 2048 | Garage door |
| DAMAGABLE | 4096 | Destructible |
| IS_TREE | 8192 | Tree, sways in wind |
| IS_PALM | 16384 | Palm tree, sways in wind |
| NO_FLYER_COL | 32768 | No collision with aircraft |
| IS_TAG | 1048576 | Graffiti tag |
| NO_BACKFACE_CULL | 2097152 | Render both sides |
| BREAKABLE_STATUE | 4194304 | Breakable statue |

### IPL (Placement)

IPL files define object positions, rotations, and LOD links on the map.

| Button | Operator | Description |
|--------|----------|-------------|
| Add | `gtatools.upsert_ipl` | Insert/update placement (auto-LOD linking) |
| Remove | `gtatools.remove_ipl` | Remove by Model ID. When an entry is deleted from the middle of the file, all LOD indices of remaining objects are automatically recalculated — otherwise the game would reference wrong lines and may crash |
| Export | `gtatools.export_ipl` | Write selected objects with world transforms |

> The IPL box no longer has a standalone Import button — placement is done by **Import from IMG** (Import tab), and stubs are resolved by "Replace Empty" under **Additional (IPL)**.

**Quaternion conversion:** GTA SA stores (X,Y,Z,W) conjugated, Blender uses (W,X,Y,Z). Conversion is automatic.

**Binary IPL:** files with `bnry` header (inside IMG archives) are read automatically.

> 💡 **Example — place a model on the map:** imported `building01.dff`, set Model ID 3500. Move/rotate it freely in the scene → IPL → **Export** → pick `mymap.ipl` → the line `3500, building01, 0, X, Y, Z, QX, QY, QZ, QW, lod` is written with the real world coordinates.

### IPL Sections

All IPL sections are supported for import/export as Blender objects:

| Section | Collection | Visualization |
|---------|-----------|---------------|
| cull | IPL_Cull | Wireframe cube |
| grge | IPL_Garage | Empty (cube) |
| enex | IPL_Enex | Empty (axes) — enter + exit points |
| pick | IPL_Pickup | Empty (sphere) |
| cars | IPL_Cars | Empty (arrow) |
| auzo | IPL_Auzo | Cube mesh or Empty (sphere) |
| jump | IPL_Jump | Cube mesh — start + target + camera |
| occl | IPL_Occl | Wireframe cube with rotation |
| zone | IPL_Zone | Wireframe cube |

| Button | Operator | Description |
|--------|----------|-------------|
| Sections IPL ↓ | `gtatools.import_ipl_sections` | Import all sections from IPL file |
| Sections IPL ↑ | `gtatools.export_ipl_sections` | Export all section collections to IPL file |
| Replace Empty | `gtatools.replace_ipl_placeholders` | When IPL import can't find a model, it creates an Empty with `_empty` suffix in IPL_Empty collection. After adding the model to the scene, click this button — the model moves to the Empty's position and the Empty is removed |

### IMG Archive

| Button | Operator | Description |
|--------|----------|-------------|
| Export to IMG | `gtatools.export_to_img` | Pack DFF+COL+LOD+TXD directly into .img archive |

> **Import from IMG** (`gtatools.import_from_img`) and the **LOD / TXD / COL** toggles (ON = load) moved to the **Import** tab (now modal, with an "Import from IMG: X/Y" counter, ESC to cancel). The Export tab's IMG box keeps only writing and archive service: **Export to IMG**, **Remove from IMG**, **Rebuild IMG**.

**Export to IMG dialog — per-model hierarchy.** The dialog is a tree with one box per selected model:
- **DFF** — a checkbox (include this model) plus its **TXD name** field (hidden when **Shared TXD** is on).
- Indented under it, a **LOD** checkbox and a **COL** checkbox. If the model has no LOD in the scene, the row reads **"LOD: main model (stub)"** — the main model is written as the LOD (stub). If it has no COL, the row reads **"COL: empty stub"** — an empty bounding-box COL is created so the game still finds collision by ID.
- At the top of the dialog: an **IMG archive** dropdown — defaults to the model's own IMG (the archive it was imported from), or any `.img` in the game folder.
- **Shared TXD** toggle + name field — packs all textures of every exported model into one shared `.txd` (default `textures.txd`) instead of one `.txd` per model.
- **Rebuild after export** checkbox — compacts the IMG right after writing, reclaiming the dead space left by replaced entries.

**Batch writer + parallel encode (big exports):** `Export to IMG` opens the archive once, appends every new payload sequentially, and rewrites the directory exactly once at the end — not per-file. Plus DFF and COL serialisation (`to_bytes()` / `write_col()`) runs in a 4-worker `ThreadPoolExecutor` (numpy/zlib release the GIL). For a full-district export this replaces ~3000 directory rewrites (~2.6 GB of redundant writes) with one, plus ~4× speedup on the CPU-bound encode — typically **5–15× end-to-end**.

> 💡 **Example — batch upload to gta3.img:** you have 50 buildings ready to export. Select the buildings → **Export to IMG** → the per-model dialog opens, each model as a box (DFF + its TXD name, plus indented LOD/COL checkboxes; models with no LOD/COL show a "stub" note). Pick the **IMG archive** (defaults to each model's own IMG), optionally toggle **Shared TXD** if they share textures, and tick **Rebuild after export** to compact in one go. Click OK — all DFF+COL+LOD+TXD get encoded in parallel and written to the archive.

### Preset / data folder

**Panel:** Properties → Scene → INU Tools → ▸ **Preset folder** *(collapsible)*

All INU Tools presets and saved data live under one user-writable root: `paths.json` (Game Root / IDE / IPL / IMG / texture paths) plus the `profiles/`, `material_presets/`, `id_presets/` subfolders and the per-pipeline DFF-flag defaults. By default the root is Blender's per-user extension directory (the addon never writes inside its own folder — required by the extensions platform).

| Button | Operator | Description |
|--------|----------|-------------|
| Change | `gtatools.set_preset_dir` | Pick a new folder; existing presets are merge-copied into it, then storage switches over |
| (open) | `gtatools.open_preset_dir` | Open the current folder in your file manager |
| Reset to default | `gtatools.reset_preset_dir` | Forget the custom folder and go back to the default location |

The chosen folder is remembered globally (across `.blend` files and Blender restarts) via a tiny pointer file at the default location. If the custom folder later goes missing (e.g. an unplugged drive), the addon silently falls back to the default. The header line shows **Default** or **Custom folder** plus the full path.

> 💡 **Example — keep presets on a project drive:** open **Preset folder** → **Change** → pick `F:\GTA Project\INU presets`. Your existing profiles and material presets are copied there, and from now on everything reads/writes from that folder — handy for syncing presets between machines or keeping them next to a project.

### BBox Mode

| Button | Operator | Description |
|--------|----------|-------------|
| BBox: ON/OFF | `gtatools.toggle_bbox` | Toggle Bounding Box display for map objects |

When enabled, all Map_ collection objects switch to `BOUNDS` display. Objects within 300m of the selected object stay as `TEXTURED`. Updates automatically when selection changes.

> 💡 **Example:** imported the LA map (5000+ objects), Blender struggles with viewport rendering. Toggle **BBox: ON** → distant buildings become wireframe boxes, objects within 300m of your selected one stay fully textured. Viewport flies.

### Model type detection (DFF / LOD / COL)

The addon detects a mesh's model type **automatically** — no need to rename the
scene. The old editable "Suffixes / Prefixes" section was removed; the suffixes
remain as a manual **override**.

Detection order (top to bottom — first match wins):

1. **Explicit marker on the name** — suffix `_DFF` / `_LOD` / `_COL` / `_SHA`
   (or a prefix) → that type. Use it to force a type by hand.
2. **Object tag `inu.type = COL/SHA`** (stamped by the COL importer and the
   Batch Set Type button) → **COL**. Reliable for anything imported as `.col`;
   checked before the LOD rule so a collision with an accidental `lod` in its
   name isn't read as a LOD.
3. **A `lod` token** anywhere in the name (**case-insensitive** — the same rule
   the map importer uses) → **LOD**. `LODfunc_detail`, `func_LOD`, vanilla
   lowercase `lodxxx` → LOD; the base name is taken without `lod` (so it pairs
   with the HD model).
4. **Texture heuristic** — a material with an image → **DFF**; no materials, or
   materials with no texture → **COL**.

> 💡 Addon-imported meshes already carry the type tag; external meshes (map
> converters, e.g. `func_detail` / `LODfunc_detail`) are classified by name and
> textures with no renaming.

> ⚠️ An **untextured visible DFF** (vertex-colour / flat-colour, no image) lands
> in COL via rule 4. If such a model must be a DFF, add a `_DFF` suffix.

**Why the suffixes stayed (override):** Blender can't hold two objects with the
same name, so a DFF and its COL sharing one base name can't coexist — you'll use
`_DFF` / `_COL` for the pair. The suffix also sets the base name used to pair
models on export.

When exporting IDE/IPL, LOD models are always written with the `LOD` prefix
(GTA SA format).

### LOD Detection

When importing maps, INU Tools decides which models are LODs in two layers:

**Layer 1 (authoritative) — IPL cross-reference.** Every IPL `inst` line has a `lod_index` field pointing to its LOD companion's line in the same file. Any instance another line references is a LOD regardless of its name. 100% reliable for properly authored maps.

**Layer 2 (fallback) — name.** When no IPL context is available, a name is a LOD if it **contains `lod` anywhere (case-insensitive)** — prefix `LODfoo` / `lodfoo`, suffix `foo_LOD`, or embedded `des_damlodbit04`. For real GTA map names `lod` reliably means a LOD; the rare English words that contain it (`lodge`, `explode`) don't occur as model names. This is the same `is_lod_name` rule the **type detector** (above) uses, so import and export agree.

**Base-name stripping** (`strip_lod_marker`) removes the marker to recover the base name for COL/DFF/LOD pairing:

| Name | Stripped to |
|---|---|
| `LODbush2b`, `lod_tree` | `bush2b`, `tree` |
| `bush1b_LOD`, `tatar_str_1LOD` | `bush1b`, `tatar_str_1` |
| `modeLODlaett` (embedded) | `modelaett` |
| `barrier1` (no `lod`) | `barrier1` (unchanged) |

**When it matters.** Used for map-import renaming, `Replace IPL Placeholders`, collection sorting, and COL/DFF pairing — getting the base name right sends a model to `Map_LOD` instead of `Map_DFF_*` and lets paired-object utilities find the HD twin.

> Implementation: `is_lod_name()` and `strip_lod_marker()` in [core/ipl.py](INU_tools/core/ipl.py); reused by `classify_model()` in [core/model_classify.py](INU_tools/core/model_classify.py).

### Model ID Manager

**Panel:** N-sidebar (`N`) → GTA Tools → **ID Manager** *(dedicated subpanel in DATA zone)*

- Shows free/used ID count
- **Next free ID** displayed
- **Auto Assign** — assigns next free ID to selected objects
- **Assign from ID...** — assign sequential IDs starting from a specific number. By default it honours the exact start (321, 322, 323…); tick **Skip occupied IDs** to jump over numbers already in use (and it warns if the range overlaps other objects)
- **Release** — marks ID as free
- **Extend IDs (FLA)** — add IDs beyond 19999 for Fastman Limit Adjuster
- IDs stored in `model_ids.txt` in INU_Preset folder

> 💡 **Example — assign IDs to a batch of buildings:** imported 50 new buildings (no IDs). Select all → **Assign** → each object gets the next free ID starting from the first available (e.g. 3500, 3501, 3502 …). Now you can batch-export them into IDE.

> 💡 **Example — separate ID preset per map:** working on map `mycity`. Create preset with **+** → name `mycity`. All IDs you hand out in this scene now go into `INU_Preset/id_presets/mycity.txt` — no conflicts with your main project. Switch preset back to `default` — your previous ID database is back.

---

### Multi-IPL Sync (2.1.0)

**Panel:** the **Import** tab (**IPL to import** list, multi-select) and the **Export** tab (**IPL to export** list) — the lists are shared. The reconcile button is now **Refresh from IDE/IPL** (`gtatools.link_sync`) on the Import tab, replacing the former "Sync".

A district is rarely one `.ipl`. Vanilla SA splits each region across several files (`LAn.ipl`, `LAs.ipl`, `LAe.ipl`, streamed chunks…), and the single **IPL File** picker in the box above only reconciles one of them per click. The Multi-IPL Sync list lets you register every `.ipl` that makes up a map and reconcile your whole scene against all of them in **one** pass.

When the list is empty, **Sync** behaves exactly as before — it uses the single IPL path from the IPL box. As soon as the list has entries, **Sync** iterates every listed file instead.

**Pipeline:**
1. Expand **Sync multiple IPL** (▸ disclosure triangle, collapsed by default — the row shows a live `(N)` count once files are added).
2. **Add** → file dialog. Multi-select is supported: hold **Ctrl/Shift** to pick several `.ipl` files at once. Duplicates (same absolute path) are silently skipped; the report reads **"Added IPL: N"**.
3. Each row shows a short clickable path label + an **X** to drop that one file. **Clear** empties the whole list.
4. Click **Sync** (the unified IDE+IPL button below the list).

What one Sync pass does, per object:
- **Already linked** (object carries an IPL link) → its position/rotation is pulled **from** the IPL it belongs to, back into Blender.
- **Not yet linked** (e.g. fresh after Map Import) → matched by `(Model ID + world position)` against the files; on a hit it gets linked to that file.

**Per-file skip accounting.** Each object belongs to at most one IPL in the set, so a naive sum of per-file skips would massively over-count (an object that lives in `LAs.ipl` is a "no match" for `LAn.ipl`). The multi-file pass instead unions the linked + synced object **names** across all files and treats only the genuinely untouched remainder as *skipped*. An object that already carries a link to another file in the set is left alone — it is not re-stolen by a coincidental content match elsewhere.

The alarming "nothing matched" warning fires **only** when truly zero objects linked or synced — a `skipped N` with successful work elsewhere is normal (that part of the selection just lives in a file you didn't list).

> 💡 **Example — sync Los Santos after Map Import:** you imported the LS district and have ~2000 fresh objects with no IPL links yet. Open **Sync multiple IPL** → **Add** → Ctrl-select `LAn.ipl`, `LAs.ipl`, `LAe.ipl`, `LAw.ipl`, `LAhills.ipl` → the row now reads `Sync multiple IPL (5)`. Deselect everything (Sync then sweeps every mesh in the scene) → **Sync**. Each object is matched against whichever of the 5 files holds its placement, and you get `Sync IPL: updated 0, new links 1980, skipped 20 (5 IPL)` — the 20 skips are props you added by hand that aren't in any vanilla IPL.

### Adding and removing in IDE/IPL: how the sync works

**Panel:** View3D → Sidebar (N) → GTA Tools → IDE / IPL / IMG → IDE / IPL boxes → **Add** / **Del**, plus the selected-model box (**Add** ↑, 🗑, ▶)

**Where Add writes.** When a file is picked in the box, every selected model is written **there**. If a model used to be in another file, you get a warning that its row is still in the old file. With the box empty, each model goes to its own file (the one it was imported from or last added to). **Del** removes from the picked file. 🗑 in the model box removes from the model's own file.

**How the addon finds a model's row.** A model remembers what it last wrote: file, Model ID, name, position and rotation. No line numbers are stored anywhere. Before every write the file is read again and the row is looked up by that content. So a repeated **Add** updates the row in place instead of adding a duplicate. Edits in another tool, deleted rows and reordering break nothing. A row nudged by hand (up to 2 m) is found nearby. A deleted row is added again, and the report warns about it.

**The LOD always travels with its model.** You don't need to select the `LOD…` mesh. The partner comes from the **LOD partner** field (`inu.lod_object`), or, when that is empty, from the scene mesh with the same base name (`LODhouse` for `house`). Each placement gets **its own** LOD at its own spot. A copy (Shift+D) adds a new model row and a new LOD row and leaves the original's rows alone. `lod_index` is recomputed for every row in the file on every write. It stays correct for all neighbours after **Del**, and the removed model's LOD goes with it unless another model still uses it. A LOD with no Model ID takes **ID = DFF + 1**.

**Copies.** A copy (Shift+D / Ctrl+D) inherits the original's link. The addon tells them apart by the object name remembered at write time. The copy becomes a new placement, and its status reads **Copy — will be added as a new instance**.

**IDE: someone else's row is never overwritten.** An IDE row is updated only when that ID in the file holds the same model (same name, or this model's previous name). These cases are a **conflict**: the model isn't written and the report says why:
- the ID is taken by a different model;
- the ID is used in another section (`anim`, `cars`…);
- the model's name is already in the file under another ID.

Changing a model's Model ID updates its own row with the new ID. `tobj` rows keep their hours, multi-mesh rows keep their extra draw distances.

**Summary before writing — only when there's a problem.** A normal Add or Del writes straight away. If there is a conflict, a model without a Model ID, a LOD without its model or a lost row, a dialog lists them first. Press **OK** and everything else is written.

**File safety.**
- Only the needed lines change. Comments, blank lines, other rows' number formatting, `path`/`mult` sections, line endings and a BOM stay as they were.
- The file is written through a temp file, so an interrupted write can't corrupt it.
- The first write of a file in a session leaves `<file>.bak` with its previous state.
- Binary IPLs from an IMG (`bnry`) are not edited, and the report says so.

**Import links right away.** Map import, IMG import and IPL import link each model to its row in the text IPL. **Add** and **Del** work straight after an import, no **Check** needed.

**Check / Update from IPL / ▶.**
- **Check** moves nothing. It drops the link of a model whose row is gone from the file. An unlinked model is recognised by a row of its model nearby (0.5 m) or by the only free row of that model.
- **Update from IPL** moves models to the positions in the file.
- **▶** puts the selected model back at its IPL coordinates.

**Setting the LOD partner — "Find LOD".** Press **Find LOD** (`gtatools.auto_find_lod`) next to the **LOD** row in the model box. It finds the LOD twins of the selected models by base name and fills `inu.lod_object`. The report reads `LOD found: N, not found: M`. If a LOD's name doesn't match the model's base name, set the partner by hand.

> 💡 **Example — a copy of a house with its LOD:** `house` (ID 3500) and `LODhouse` (ID 3501) are already in `mymap.ipl`. Shift+D on `house`, move the copy, select it and press **Add**. The result is `IPL: added 1, LOD +1 ~0`. The file gets two new rows: the copy and its own LOD at its spot. The original's rows are untouched.

> 💡 **Example — update two buildings in their own files:** `bank01` came from `LAn.ipl`, `tower05` from `LAs.ipl`. Move both, select them and press **Add** ↑ in the model box, or **Add** with the IPL box empty. Each building is written, with its LOD, to its own file.

### Inline path pickers for IDE / IPL / IMG (2.1.0)

**Panel:** View3D → Sidebar (N) → GTA Tools → IDE / IPL / IMG → IDE / IPL / IMG box headers

Each of the three boxes carries a 📁 **file-browser button** in its header. Click it to pick the target file; the box then shows the chosen path as a short, read-only label (last two path segments, e.g. `…/data/maps/LA/LAn.ipl`) under the header. If nothing is set yet, the label reads **File not selected**. The label itself is not editable inline — to change a path, click 📁 again. The same picker serves all three boxes; the file dialog filters to `*.ipl / *.ide / *.img`.

### Apply to Selected — batch-edit IDE properties (2.4.0)

**Panel:** View3D → Sidebar (N) → GTA Tools → IDE / IPL / IMG → selected-model box →
**Apply to selected (N)** button (appears once more than one model is selected)

Opens a dialog that writes IDE properties to every selected mesh at once. Each field has **its own
checkbox** on the left: only the ticked fields are overwritten, everything else is left as it is.

| Field | Notes |
|---|---|
| **Draw Dist** | Draw distance (ticked by default). |
| **LOD Dist** | LOD distance. |
| **Model ID** | With **Sequential (+1)** the first model gets the given ID and each next one +1. Objects are ordered by name (not by selection order, which follows Blender's internal scene order). |
| **TXD** | Texture dictionary name. |
| **Interior** | Interior number. |
| **IDE Flags** | Numeric flag value. |
| **COL Library** | `.col` library name. |

Source: [`ops/col_surface_ops.py`](INU_tools/ops/col_surface_ops.py) → `gtatools.batch_set_distance`.

### Opening IDE / IPL in an editor (2.4.0)

The 📄 button next to a file path opens it in the **OS text editor** (like double-clicking it in the
file manager). Turn on **Open IPL/IDE in Blender's editor** in the addon preferences
(*Edit → Preferences → Add-ons → INU Tools*) and the file is loaded into Blender's own text editor
instead — into an open TEXT_EDITOR area, or a new window when there is none. Handy when you do not
want to leave Blender over a single line.

### Region filter pulls streamed child IPLs (2.1.0)

**Panel:** View3D → Sidebar (N) → GTA Tools → IDE / IPL / IMG → Import Map (Region selector)

When you import a single region (Map Region ≠ ALL), the old folder rule only loaded IPLs physically sitting in `maps/<region>/`. That silently dropped **streamed / child IPLs** — vanilla splits big districts into a base file plus streamed chunks named `<base>_<suffix>` (e.g. `countn2` → `countn2_stream3`) that usually live **outside** the region folder. The region filter now keeps a chunk if **either** its folder is the selected region **or** its basename is `<base>_<suffix>` where `<base>` is one of the region's base IPLs. So selecting the countryside now pulls in `countn2.ipl` **and** `countn2_stream3.ipl` — the district loads whole. The `_` guard keeps `countn` from grabbing unrelated `countnXYZ` files. The system console prints which IPLs the region filter dropped vs loaded, so an incomplete district can be traced.

**Map import — "Skip 2DFX".** The Import Map toggle **Skip 2DFX** (default ON) controls whether 2DFX effects (lights, particles…) are imported with each model. It is read once at import start and passed explicitly into the builder, so the bulk/modal path can't silently flip back to "load 2DFX". Leaving it ON makes a map import lighter and faster; turn it OFF only when you actually need the 2DFX data in-scene.

**Texture-alpha auto-link.** During Map Import, the first time each material is seen the addon inspects its image: if it has genuinely transparent pixels (foliage, fences, windows) it wires *texture Alpha → BSDF Alpha* and switches the material to alpha-test so the cutouts render correctly; opaque textures are untouched. This runs once per material (not per instance), so a district reusing one fence texture across hundreds of buildings pays the check exactly once.

---

## Materials

### GTA Material

**Panel:** Properties → Material → GTA Material

| Property | Description |
|----------|-------------|
| Environment Map | Reflection texture with coefficient (0-1) |
| Bump Map | Normal map texture |
| Reflection | Mirror reflection with scale, offset, intensity |
| Specular | Specular highlight with level and texture |
| Dual Texture | Second texture with blend modes (11 options for Src/Dst) |
| UV Animation | Animated UV scrolling with animation name |

> 💡 **Example — building window with reflections:** create a material `building_window` → enable ☑ Environment Map → set texture `xenvmap`, coefficient `0.6` → in-game the window will reflect the sky/clouds moving over the city. For transparent glass, additionally enable FB Alpha.

### GTA Material Presets

**Panel:** View3D → Sidebar (N) → GTA Tools → **GTA Material** → **EFFECTS** tab → **Quick presets**

Four one-click buttons write a full GTA effect setup onto the active material in a single click — no dropdown, no save dialog. The button labels appear in the UI in Russian:

| Button (RU / EN) | Preset | What it sets |
|---|---|---|
| **Glass** | `VEHICLE_GLASS` | Car glass: env map with framebuffer alpha |
| **Chrome** | `CHROME` | Strong environment reflection + specular (bumpers, trim) |
| **Paint** | `VEHICLE` | Car body: `xvehicleenv128` env map + `vehiclespecdot64` specular + reflection |
| **Reset** | `GENERIC` | Clears every effect flag — plain textured material |

#### Example — modeling a car

Say you're building a car with body, glass and chrome-trim materials.

**Step 1.** Select the car-body material in the object's material stack → click **Paint**. Env map, specular and reflection are all set at once.

**Step 2.** Switch to the glass material → **Glass**. Done.

**Step 3.** Select the bumper/trim material → **Chrome**. Made a mistake → **Reset** clears it back to a plain textured material.

> 💡 Use **Copy to Selected** below the buttons to push the active material's GTA settings onto the materials of every other selected object in one go.

### COL Surface Types

**Panel:** Properties → Material → COL Surface Type

179 GTA SA surface materials organized in 13 categories. Searchable dropdown with category filtering. Each surface has:
- Surface ID (0-178)
- Flags, Brightness, Light
- Day Light (0-15), Night Light (0-15)

> 💡 **Example — wooden bar floor:** bar floor mesh → new material `bar_wood_floor` → COL Surface Type → search for `wood` → pick `WOOD_BENCH` (ID 9). Now character footsteps on this COL will play the wooden sound, and bullets will leave splinters.

### Textures

**Panel:** Properties → Scene → INU Tools → Textures

- **System textures** — path to a shared texture folder (e.g. `System_textures` from MTA/GTA)
- **.blend folder** — automatically points to the current .blend file's directory. Refresh button 🔄 updates the path
- **Load Textures** — searches for PNG/TGA/JPG files matching material names on the object. Searches both folders: system and .blend. If a material is named `brick_wall`, the addon finds `brick_wall.png` in the specified folders and assigns it as texture
- **Drag & Drop** — drag images from File Browser directly into the viewport to create a new material with the texture

> 💡 **Example — auto-assign textures by name:** unzipped 100 PNG textures into `F:/gta_textures/`. Scene has 100 materials named like `brick01`, `brick02`, `roof_tile` (no textures yet). Set `F:/gta_textures/` as System textures → select objects → **Load Textures** → the addon finds `brick01.png`, `brick02.png` etc. and attaches them to the matching materials automatically.

### Alpha Materials

**Panel:** Properties → Material → **GTA Material** → **Alpha** tab

A bulk editor for the transparency mode of alpha materials — GTA maps carry hundreds of alpha-cutout materials (fences, foliage, windows) and fixing each one in Blender's native Material panel is tedious. The tool scans the scene (or the selection), lists every alpha material in a scrollable list with a per-row blend-mode dropdown, and offers one-click bulk actions.

- **Scope** — **Scene** (whole scene) or **Selected** (selected objects only).
- **Filter mode** — how a material counts as "alpha":
  - **NODE** (default) — the Principled BSDF's **Alpha** input is actually wired (the material genuinely uses texture alpha).
  - **CHANNEL** — the base texture has a *significant* alpha channel.
  - **TRANSPARENT** — the material's blend method is already non-opaque.
  - **ALL** — any of the above.
- **Scan** — (re)builds the list under the current scope + filter; the header shows how many were found.
- **Blend mode for all** + **Apply to all** (Apply blend mode to all) — set one transparency mode (OPAQUE / CLIP / HASHED / BLEND) on every listed material at once.
- **Select objects** — select the objects that use the listed alpha materials.

> **Unified transparency standard:** applying any transparent mode also switches Blender's *Show Backface* / transparency-overlap **off** — the project's standard for GTA alpha materials — and writes both the legacy `blend_method` and the 4.2+ `surface_render_method` so it also takes on EEVEE Next.

---

## Prelight (Vertex Colors)

> **Important in 1.6.3:** baking now respects **smooth/flat shading** (uses `loop.normal` instead of `poly.normal`). Also **hidden lights** (via 👁 viewport, 📷 render, or hidden collection) **are skipped** during baking — previously all point lights in the scene were used.


**Panel:** View3D → Sidebar (N) → GTA Tools → Prelight

> **Lighting panel — three tabs.** The top of the Lighting panel has toggle buttons **PreLight** | **Prelight COL** | **Itera** (formerly separate collapsible sub-panels; LightMap is not in this switch). The 🌐 planet icon in the header opens [Itera Tools 3](https://itera.gumroad.com/l/IteraTools3). The prelight settings block is **always shown**; with no mesh selected it is greyed out (disabled), not hidden.

### Baking

1. **Create Day/Night** — creates `Day` and `Night` color attributes
2. **Lights (8 lamps)** — places 8 point lights around the object; **Sun** adds an independent directional source
3. **Bake (Fast)** — CPU bake without shadows
4. **Bake with Shadows** — raycast shadow baking via depsgraph

**Light sources — the toggle row** below the bake buttons chooses what the bake samples. It is no longer just the 8-lamp rig:
- **Point / Sun / Spot / Area** — four toggles, one per Blender light type. Only the enabled types contribute, so you can bake from your own scene lamps of any kind, not only the auto-placed 8 point lights.
- **HDRI** (World, 🌐) — also add world/HDRI lighting: the sky colour is sampled along each vertex normal and combined with the lamps. The HDRI is taken from the viewport's *Scene Environment* (studio light) or the real `scene.world`.

**Settings:**
- Ambient (0-1) — base brightness
- Intensity (0-1) — light strength
- Gamma (0.5-3.0) — gamma correction
- Shadows toggle

> 💡 **Example — prelight a building for your map:** select the building mesh → Prelight → **Create Day/Night** → **Create 8 Lights** (8 point lights auto-placed around the object) → toggle ☑ Shadows → **Bake with Shadows**. The `Day` attribute gets filled with soft-shadowed lighting. Then same for Night (usually drop Intensity to 0.3 and switch light color to blueish) — switch to the Night attribute before Bake.

### Scatter Color

**Sub-panel:** Prelight → Tools → Scatter Color

Paints a tinted color **around** selected faces (instead of redistributing existing prelight). Useful for spilling a localized accent color onto neighboring geometry — neon reflections, accent glows under spotlights, dirt around drains.

**Parameters:**
- *Strength* (0–1) — center-vertex saturation of the chosen color (1 = fully replace existing colors at the centre).
- *Distance* (0–1) — radius as fraction of the mesh's bbox half-diagonal. 0 = only selected verts; 1 = falloff covers half-diagonal.
- *Color* — picked from the active **Vertex Paint brush** (so painting workflow stays unified). Falls back to a scene color picker if no brush is active.

The falloff is linear by KDTree distance — vertices further from any selected polygon receive proportionally less colour.

### Post-Processing

| Tool | Description |
|------|-------------|
| Smooth | Average colors between neighboring vertices |
| Smooth Between Objects | Smooth at seams between different meshes |
| Contrast | Adjust color contrast |
| Brightness | Adjust brightness offset |
| Gamma | Gamma correction |

> 💡 **Example — seam between two buildings:** two adjacent buildings stand flush. You baked prelight on each separately — a visible vertex-color seam at the border. Select both → **Smooth Between Objects** (passes 2, strength 0.5) → the gradient flows smoothly across the meshes, seam gone.

### COL Light

**Panel:** View3D → Sidebar (N) → GTA Tools → Prelight COL

Convert vertex colors to COL Day/Night Light values (0-15). Auto-splits materials by brightness ranges.

- **Preview** — visualize light values on mesh
- **Bake** — write values to COL material properties
- **Day/Night ranges** — adjustable thresholds

> 💡 **Example — tunnel COL lighting:** COL mesh of a tunnel has vertex colors with a dark center and lighter edges. Open Prelight COL → **👁 Preview** — mesh gets painted with numbers 0-15. Adjust Day range (min=0, max=6) so center is 0 (dark) and entrance is 6 (lighter) → **Bake COL Light** → materials get the corresponding Day/Night Light values. In-game, cars entering the tunnel will auto-darken.

### Presets

**Header row** at the top of the Prelight panel — preset selector plus 4 buttons.

Stored as `.json` in `INU_Preset/` folder. A preset captures everything bake-related across the panel and its sub-panels:
- **Bake** — Ambient, Intensity, Gamma, Shadows
- **Modulate Color** — mode (OFF/Day/Night), mix, contrast, gamma
- **Adjust Color** — V-offset
- **Scatter Color** — strength, distance
- **Post-Processing** — smooth iterations/factor, contrast, brightness, gamma
- **Per-object Day/Night** — V-offset per attribute, plus a flag whether to auto-create missing Day/Night attributes on Load

| Button | Action |
|---|---|
| ✓ | **Save to Selected Preset** — overwrites the preset currently chosen in the dropdown with current scene values. Status bar reports diff: which fields changed (`old → new`) and which were added. No name dialog. |
| ⬇ Load | Pull preset values into the scene + active mesh (creates Day/Night attrs if the preset asked for them). |
| + Save | Create a NEW preset (opens name dialog). |
| − Delete | Delete the selected preset file. |

> 💡 **Example workflow:** craft your night look — Modulate Color = Night, Day V = +30, Night V = −20 → **+ Save** → name `my_night`. Tweak Modulate Mix from 0.002 to 0.005 → **✓** overwrites `my_night`, status bar shows `modulate_mix: 0.002 → 0.005`. Switch to a different scene → pick `my_night` → **⬇ Load** → all settings restored on whichever mesh you're working on.

### Adjust Color (per-attribute V-offset)

Each Day/Night row in the colour-attribute selector has its own V-offset slider:

```
[Day]    V: +30.0   [-]
[Night]  V: -20.0   [-]
```

Type a value → press Enter → the brightness offset is applied **immediately** to that attribute's vertex colors (only this object). The value persists per-object and survives re-baking — after a fresh bake the offset is automatically re-applied to the new colors.

### Vertex Color Management

| Button | Description |
|--------|-------------|
| Create Day/Night | Creates both `Day` and `Night` color attributes |
| Day + / Night + | Create individual color attribute |
| Day - / Night - | Remove individual color attribute |
| Toggle Preview | Enable/disable Day/Night mix visualization in viewport |
| ⧉ (under Preview) | **Copy the alpha** of the active attribute into the other one (Day↔Night), keeping its RGB. With `Day` active the alpha goes to `Night` and vice versa; if the target attribute does not exist yet it is created as a full copy of the active one |
| 🗑 (next to Day/Night) | **Clear vertex alpha** on the active attribute: the alpha channel is filled with 1.0 and the RGB kept, so the model exports fully opaque. Applies to every selected mesh |
| Add LightMap | Load lightmap texture and connect to UV2 (Multiply blend) |
| 👁 LightMap | Toggle lightmap visibility (mute/unmute) |
| ➖ LightMap | Remove lightmap nodes from materials |
| Analyze | Show vertex color histogram (min/max/avg) |
| Reset | Reset bake settings to defaults |

**Edit/Paint modes:** buttons to switch between Object, Edit, and Vertex Paint modes for quick workflow.

> 💡 **Example — quick-start Night from the Day bake:** you've only baked the `Day` attribute → **Day → Night** → `Night` gets created as a copy of `Day`. Now open Post-Processing → **Brightness** = −0.3 → apply to Night → you've got a darkened version of the daytime bake. Then tweak manually (add yellow fill around lamp posts, etc.).

### VC Layer System (BETA)

**Section:** Prelight panel → ▸ **Vertex Color Layers (BETA)** (collapsible, between LightMap and Bake)

Photoshop-style **non-destructive** vertex color editing. Stack of named layers per scope (Day / Night), each with its own opacity / blend mode / brightness / contrast. The composite is written back into `Day` / `Night` automatically — both for live viewport preview AND on DFF export. Layers themselves stay editable in the .blend.

**Purpose:** when you want to:
- Add a green tint to walls without re-baking lighting
- Hand-paint a window glow on top of an Itera bake
- Adjust shadow intensity in one area without touching the rest
- Try a colour variation, then revert with one slider

**Storage:** each layer is a `BYTE_COLOR` color attribute on the mesh, named `VCL_D_<label>` (Day stack) or `VCL_N_<label>` (Night stack). Capped at **10 layers per scope**. Visible in the Color Attributes list under "Additional attributes" — layers are first-class data, painted with Blender's standard Vertex Paint mode.

#### Pipeline (typical workflow)

1. **Create `Day` / `Night`** — already there from your bake or via the regular Day/Night buttons above
2. **Add Layer** — click [+] in "Day layers" — creates `VCL_D_Layer_1`, fully transparent
3. **Paint the layer** — click **Paint** on the active layer row → enters Vertex Paint mode on `VCL_D_Layer_1`
4. **Tune layer** — adjust Opacity / Blend Mode / Brightness / Contrast on the active layer
5. **Toggle Live Preview** ON → `Day` attribute now shows the composite (base + all visible Day layers)
6. **Export DFF** — composite is auto-flattened into `Day` / `Night` for the duration of the export; layers stay intact in the .blend

#### Buttons

| Button | Description |
|--------|-------------|
| **▸ Vertex Color Layers (BETA)** | Expand / collapse the section |
| **Live preview** (toggle) | Hijack `Day` / `Night` to show the composite. ON: original baked into custom prop, composite written into `Day` / `Night` live. OFF: originals restored from backup |
| **↻** | Refresh composite manually (when Live Preview is on) |
| **☀ Day** / **🌙 Night** | Switch active color attribute to `Day` or `Night` (which holds the composite when Live Preview is on). The currently-shown scope's button is depressed |
| "Additional attributes" list | All non-Day/Night color attributes (VCL layers, custom prelight). Radio = activate, ❌ = remove |
| **Day layers** [+] | Create a new Day-stack layer (cap: 10) |
| **Day layers** [−] | Remove the active layer + its attribute |
| **Day layers** [▲] [▼] | Reorder active layer in the blend stack |
| Per-row [☑] | Multi-select for group editing |
| Per-row [👁] | Visibility — hidden = excluded from composite (alpha → 0) |
| Per-row [🔒] | Lock paint — slider edits still work, but Vertex Paint won't write |
| Per-row label | Click to rename (renames the underlying attribute too) |
| Per-row opacity slider | 0–1 layer opacity in the blend |
| **Mode** | Blend mode: Normal / Multiply / Add / Subtract |
| **Brightness before** | Pre-blend brightness offset on this layer's pixels (−1..+1) |
| **Contrast before** | Pre-blend contrast scale around 0.5 mid-grey (0..3) |
| **Paint** | Activate this layer's attribute + enter Vertex Paint mode |
| **→ Base** | Promote this VCL layer to a standalone color attribute (drops VCL prefix) |
| Multi-edit footer (Absolute / Relative) | Group sliders applied to all selected (☑) layers |
| **Recolour selected…** | Replace RGB of all painted pixels in selected layers with a chosen colour (alpha untouched) |

#### Live Preview details

- **ON:** `Day` (and `Night`) attributes are overwritten with the composite of their stack. Original data lives in `mesh["_vcl_backup_day"]` / `mesh["_vcl_backup_night"]` as a base64-encoded float buffer
- **OFF:** originals restored from backup; backup custom props removed
- Composite recomputes on: any layer slider change, `▲`/`▼` move, layer add/remove/promote/demote, paint stroke (depsgraph hook detects when active is a `VCL_*`)
- The recompose is debounced ~100 ms via a one-shot `bpy.app.timers` so a rapid drag-slide produces one final composite, not 50

> ⚠ **Don't paint directly on `Day` / `Night` while Live Preview is ON.** Those attributes hold the composite; your stroke gets overwritten on the next recompose. Paint on a layer instead — click **Paint** on the row.

#### Export-time auto-flatten

DFF exporter wraps `build_dff_clump` in a context manager:
1. Snapshot current `Day` / `Night` to memory
2. Composite Day stack into `Day`, Night stack into `Night`
3. DFF writer reads composite vertex colors → writes into the file
4. Restore `Day` / `Night` from snapshot

Net effect: the .blend looks exactly like before export, but the .dff contains the flattened result. No manual «commit» step needed.

> 💡 **Example — testing a colour variant for the green roof:** you have a building with `Day` baked. Add a Day layer named `green_roof`, paint the roof green, opacity 0.6, blend Normal. Live Preview ON → see the composite. Export DFF, test in game. Don't like it — back to Blender, set `green_roof` opacity to 0.3, re-export. Want it gone — `[−]` removes the layer; `Day` is back to the original bake on its own.

### Prelight Sun (2.1.0)

**Button:** Prelight panel → **Sun** — also in the Lighting floater.

Adds a single directional **SUN** light to the prelight rig (the same #BCBCBC colour as the 8-point ring, angled top-front). It is baked together with the point lights, so you get an even directional fill on top of the local point lighting — useful for flat roofs / large façades that the point ring alone lights unevenly.

**Pipeline:**
1. Select the mesh → **Create Day/Night** (if not done).
2. **Create 8 Lights** (optional — Sun works with or without them).
3. **Sun** → a `Prelight_Sun` is created (toggle again to remove it).
4. **Bake** / **Bake with Shadows** — the Sun contributes to the bake like any other light.

> 💡 Works even with no active mesh selected (it only manages the light). Hide it via the 👁 outliner toggle to bake without the directional fill, like any other light.

### Bake Over Existing (additive)

**Buttons:** Prelight panel → **Bake on top** / **Bake on top with shadows** (the tall row above the normal Bake row; mirrored in the Lighting floater).

Normal **Bake** *overwrites* the active Day/Night attribute. **Bake on top** instead *adds* the new bake on top of the current prelight (Add, clamped to 1.0), so you can layer several lighting passes.

**Pipeline:**
1. Bake your base lighting normally (overwrites).
2. Add/move some lights (e.g. a warm lamp near a doorway).
3. **Bake on top** → only the new light's contribution is added on top — the base is preserved.

> 💡 Plain **Bake** always re-bakes from scratch (clean). **Bake on top** never resets — repeat it to accumulate multiple passes (sun pass + lamp pass + neon pass).

### Fill Day/Night Prelight

**Sub-panel:** Prelight → Tools → **Fill one colour**.

Flood-fills the `Day` and `Night` attributes from two colour pickers in one click — byte-exact (`color_srgb`), preserving existing vertex alpha, and it sets the Day/Night export flags so the model exports as a day/night prelit object.

**Pipeline:**
1. Pick **Day** and **Night** colours.
2. Optional: ☑ **Selected only** (selected faces only) — fills just the selection, in Edit Mode.
3. **Apply**.

> 💡 **Example — flat ambient base:** new building with no bake yet. Fill Day = RGB(0.75,0.75,0.75), Night = RGB(0.3,0.3,0.38) → instant neutral day/night base you can then bake *over* or hand-paint.

### Foliage / Tree Prelight (2.1.0)

**Sub-panel:** Prelight → ▸ **Foliage / trees**.

Geometric crown shading + leaf tint for trees and bushes — **no scene lights needed**. It computes a radial gradient from the crown centre outward (and optionally top-down), so leaves get a natural darker-inside / brighter-outside look. Split into two independent operations, each with its own material picker:

- **Shade** — brightness gradient (the lighting look).
- **Colour** — colour tint gradient (autumn/season tinting, bottom darkening).

**Key settings:**
- *Sphere / Cylinder* — radial metric (sphere = full 3D radius; cylinder = ignore height, good for tall trees).
- *Inside / Outside* — brightness (or colour) at crown centre vs edge.
- *Curve* — gradient falloff shape.
- *Highlight top / Highlight height* (Colour block) — multiplicative brightness boost toward the top of the crown.
- *Variation* — per-leaf random noise so it doesn't look uniform.
- *Darken bottom* — extra darkening at the bottom of the crown.
- *Bake colour* / *Reset* — snapshot the current prelight before tinting, and restore it.

**Pipeline:**
1. Select the tree mesh → expand **Foliage / trees**.
2. Pick the leaf material in **Shade**, set Sphere/Cylinder + Inside/Outside → **apply** → crown shading baked into the active layer.
3. (Optional) Pick the material in **Colour**, set a tint + Highlight top + Darken bottom → **Bake colour** (snapshots first) → apply.
4. Not happy with the tint → **Reset** restores the pre-tint prelight.

> 💡 **Two-sided leaf cards:** duplicated leaf planes (same position, flipped normals) are matched by vertex position, so both sides of a fence/leaf card receive the same colour even on triangulated meshes.

### Light Cutter — Light → Topology (2.1.0)

**Sub-panel:** Prelight → Tools → **Light → topology** (Tools).

Builds geometry under a lamp and bakes a smooth radial light pool into it — for soft prelit light circles on floors that a coarse mesh can't show. A visible **wire cutter** (concentric ring cylinders, or a sphere) lets you dial in the size/rings before cutting.

**Settings:**
- *Type* — Cylinder (concentric rings, for floors) / Sphere.
- *Radius* / *Segments* — overall size + roundness.
- *Rings* — per-ring radius list (each ring its own slider); more rings = smoother gradient.

**Pipeline:**
1. Select the lamp (or place the 3D cursor) → set Type / Radius / Segments.
2. **Create cutter** → a wire `INU_LightCutter` appears at the lamp. Tweak radius / segments / add rings — it **rebuilds live**. Move it where you want the light pool.
3. Choose the mode:
   - ☑ **As separate geometry** → builds a clean separate disc, conformed to the surface below.
   - ☐ off → pick a **floor** target → it knives the rings into that mesh.
4. **Cut by cutter** → geometry is cut and a radial gradient (bright centre → dark edge, × lamp colour) is baked into `Day`.

> 💡 The cutter is a normal wire object — you can enter Edit Mode and tweak its polygons/rings manually; changing a ring slider afterwards rebuilds it.

### Multi-Object Paint (Merge / Split)

**Sub-panel:** Prelight → Tools — **Merge for painting** / **Split apart**.

Paint Day/Night vertex colours across **many models at once**. It merges the selected meshes into a single textured throwaway proxy, you brush-paint on it, then it copies the colours back to each original by loop range.

**Pipeline:**
1. Select all the meshes you want to paint together.
2. **Merge for painting** → a temporary merged proxy is created in Vertex Paint mode (textures visible).
3. Paint Day (and/or Night) across the whole cluster as if it were one object.
4. **Split apart** → colours are written back to each original mesh; the proxy is removed.

> 💡 **Example — a row of shopfronts:** 6 separate building DFFs that should share one continuous evening gradient. Merge → paint the gradient once across all 6 → split. Each model keeps its own slice, the gradient flows seamlessly across them.

### Vertex Alpha Preview (scene-wide)

**Button:** Prelight (and Textures) → **Vertex alpha (scene)** + 🗑 cleanup.

Shows per-vertex transparency in the viewport, independent of the RGB prelight preview. It scans the scene, finds only the meshes/material-slots whose Day/Night alpha is actually `< 255` (fences, foliage, glass, LOD edges) and wires their vertex alpha into the material's Alpha + a blended draw mode. Solid geometry is never touched.

**Pipeline:**
1. **Vertex alpha (scene)** ON → all fading models go translucent in the viewport per their vertex alpha.
2. Edit / bake / erase alpha as needed.
3. **Vertex alpha (scene)** OFF → preview nodes are fully removed (graph left clean).
4. 🗑 **(cleanup)** — the *check*: removes leftover AlphaView nodes from any material that no longer has vertex alpha (e.g. you erased it on some meshes), keeping them only where still needed. Runs automatically on enable, or anytime via the button.

> 💡 Only slots that actually fade get wired — a mesh mixing an opaque wall material and a transparent glass material keeps nodes only on the glass.

> ⚠ **Gotcha — alpha will NOT show in-game without an IDE flag.**
> The Blender viewport preview ≠ the in-game render. For per-vertex (or texture) alpha to actually render in GTA SA, the object's **IDE** definition must carry a transparency flag:
>
> | Flag | Name | Effect |
> |------|------|--------|
> | **4** | DRAW_LAST | Object is transparent, drawn after opaque ones. Basic alpha cutout: fences, foliage, simple glass. |
> | **64** | NO_ZBUFFER_WRITE | Skips z-buffer writes so transparency layers can stack. |
> | **68** = 4+64 | DRAW_LAST + NO_ZBUFFER_WRITE | Full alpha range for **vertex colour AND textures** (soft fade, soft glass). Cost: no z-write → possible sorting artifacts (the object can show through another). Use it when you specifically need a smooth vertex-alpha gradient. |
>
> Set the flag in **N-panel → IDE/IPL** (the object's flags field); it's written on IDE export. Without it the alpha exists in Blender but the model is fully opaque in-game. Source: [GTAMods — Item Definition / IDE Flags](https://gtamods.com/wiki/Item_Definition).

---

## 2DFX Effects

**Panel:** View3D → Sidebar (N) → GTA Tools → 2DFX Effects

Create and configure 2DFX effects that export into DFF files.

**Effect types:**
- **Light** — street lights, neons, coronas
- **Particle** — smoke, fire
- **Ped Attractor** — ATM, bench, bus stop
- **Sun Glare** — sun reflection on surfaces

### Light Properties

| Property | Options |
|----------|---------|
| Presets | Default, OnAllDay, Lamp Post, Lamp Post Coast, BB Pickup, Flashing (3 types), Train Crossing, Traffic |
| Corona Texture | 34 textures (coronastar, coronamoon, headlight, etc.) |
| Shadow Texture | 13 textures (shad_exp, shad_car, lamp_shad_64, etc.) |
| Show Mode | Default, Random Flashing, Flash Rain, Only Rain, No Rain |
| Flare Type | None, Type 1-3 |
| Color | RGBA color picker |
| Corona Size | Float |
| Draw Distance | Float |
| Light Range | Float |
| Shadow Size | Float |
| Flags 1/2 | Integer |

**Attach to Model:** parent 2DFX Empty to mesh object. Coordinates auto-recalculate on export.

> ⚠ **Gotcha — effect textures (coronas/shadows/water) are NOT bundled with the addon.** They are GTA SA assets (Rockstar IP), so the preview pulls them from your own game. The 2DFX panel header shows the **real source** inline on the **"Create Effect: …"** line — a short `.txd` path, or **"Not selected"** when there's no source. The folder button (📁) next to it picks your own `.txd` (e.g. `particle.txd`) — picking it loads the textures; there's no separate "Load" button anymore.
>
> With no explicit `.txd`, the addon resolves from the **Game Root** in order: `models/particle.txd` → `particle2.txd` / `effectsPC.txd` / `misc.txd` → embedded `gta3.img/particle.txd`. The preview pulls textures lazily. With no source, the corona/shadow render as a flat placeholder (doesn't affect DFF export — only the texture name is written there).

**Detach All from Mesh:** batch detach all 2DFX from selected mesh. The mesh's UI shows a list of all attached 2DFX with individual detach buttons.

**Preview:** real-time corona/shadow visualization in viewport. Billboard tracking implemented via **draw handler** *(1.6.3)* — works reliably across scene switches.

**Apply Settings**: copies the active 2DFX's settings — its `inu.*` props plus the raw `2dfx_*` custom properties — onto every other selected 2DFX Empty at once. Select the targets, keep the source active, click the button; the affected previews rebuild automatically afterwards.

**Relationship lines**: a checkbox that toggles the dashed parent→child relationship-line overlay drawn from each mesh to its attached 2DFX Empties.

**Preview auto-rebuild:** duplicating or copying a 2DFX Empty (Shift+D, or Ctrl+C / Ctrl+V) automatically regenerates its preview — a background timer detects the fresh copy and rebuilds the missing corona/shadow rig, so native Blender duplication just works without pressing any button.

> 💡 **Example — street lamp:** select the lamp post mesh → 2DFX → **Create Light** → an Empty with default lamp appears. Move the Empty to the top of the post → pick preset **Lamp Post** → ✓ Apply (sets yellow color, coronastar texture, 200m draw distance). Parenting to the mesh is automatic → Empty.parent = post. On DFF export, 2DFX coordinates are written relative to the mesh.

> 💡 **Example — flashing red emergency:** Create Light → preset **Flashing (Maverick1)** → ✓ Apply → Show Mode `1 RANDOM_FLASHING` is set automatically. In-game this corona will flash red randomly — perfect for emergency lights or police beacons.

---

### 2DFX Light flags & corona/shadow (2.1.0)

**Panel:** `N-panel ▸ INU ▸ 2DFX Effects` (with a Light-type 2DFX Empty selected) ▸ section **Flags**, **Light Properties**, **Shadow**

In 2.1.0 the day/night visibility flags were corrected (they were off-by-one before, so "night-only" lamps still glowed in daytime), and corona/shadow handling was clarified.

#### Day / night visibility flags

Open the **Flags** section. The buttons under **Visibility** are toggles — a depressed (highlighted) button means the bit is ON. Hover any button to see what the bit does.

| Button | Raw bit | Meaning |
|---|---|---|
| **AT_DAY** | flags1 bit 5 | Light is visible during the day (06:00–20:00) |
| **AT_NIGHT** | flags1 bit 6 | Light is visible at night (20:00–06:00) |
| **Blink 1** / Blinking 1 | flags1 bit 7 | Light blinks (pattern 1) |

The default for a new light is both **AT_DAY** + **AT_NIGHT** ON (always-on lamp).

**Pipeline — make a light glow ONLY at night:**
1. Select the Light 2DFX Empty.
2. Expand **Flags** ▸ **Visibility**.
3. Enable **AT_NIGHT** (click so it is depressed/highlighted).
4. Disable **AT_DAY** (click so it is no longer depressed).
5. Done — the lamp is dark at daytime and lit at night.

#### Corona only — no ground light pool / shadow

The visible glowing sprite (the "light") is the **corona**, driven by **Corona Size** in **Light Properties**. The ground light pool / shadow patch and the surrounding flood-light are driven by **Shadow/Spot Size** in the **Shadow** section.

**Pipeline — keep only the corona, remove the ground pool:**
1. Expand the **Shadow** section.
2. Set **Shadow Size** to **0**. The panel confirms: *"Size = 0 → corona only, no pool"*.
3. Make sure **Corona Size** in **Light Properties** is greater than 0 — that is the part you keep. (Corona Size 0 = no visible glow at all.)

#### Per-object preview materials (multiple lamps, same corona texture)

Previously, several lamps that shared one corona texture (e.g. every street lamp using `coronastar`) collapsed onto a single shared preview material, so only one corona actually rendered in the viewport. Each light now gets its own preview material keyed to the object, so every lamp renders its corona.

- New lights and refreshed lights get this automatically.
- If an **existing** scene still shows only one corona: select each lamp and click **Refresh Preview** at the top of the panel to rebuild its per-object material.

#### Hover tooltips

Hover (don't click) these controls for an in-panel explanation:

- **Show Mode** and **Flare Type** enum items — each option (DEFAULT, RANDOM_FLASHING, FLASH_RAIN, ONLY_RAIN, NO_RAIN, FLASH_5, lens-flare types) describes its behaviour.
- **Corona Name** / **Shadow Name** entries — each texture (`coronastar`, `coronamoon`, `shad_exp`, vehicle/ped silhouettes…) describes its look.
- In the **Shadow** section: **Distance** = how many metres down the light pool is projected; **Multiplier** = brightness/contrast of the ground pool (0–255).

> 💡 **Example — night-only street lamp:** Select the lamp's Light 2DFX Empty ▸ **Flags** ▸ **Visibility**: turn ON **AT_NIGHT**, turn OFF **AT_DAY**. Leave **Corona Size** at ~1.0 and **Shadow Size** at ~8 for a glowing lamp with a soft ground pool that only appears after dark.

> 💡 **Example — corona-only neon (no ground pool):** In **Light Properties** set **Corona Size** to taste and pick a corona in **Corona Name** (e.g. `coronastar`). In the **Shadow** section set **Shadow Size** to **0** — you get a floating glow with no light circle on the ground. If you have several such signs sharing the same corona texture, click **Refresh Preview** on each so they all render.

---

## Particle Effects (effects.fxp)

Full editor for GTA SA's `effects.fxp` — a plain-text file containing **82 particle systems** (fire, smoke, blood, sparks, water, gun shells, etc.) that the engine plays when an object with a `Particle` 2DFX entry is loaded.

**File location:** `<game_root>/models/effects.fxp` — auto-resolved from `gtatools_game_root` Scene property.
**Texture source:** `<game_root>/models/particle.txd` — sprite atlas referenced by emitters via the `TEXTURE` field.

### End-to-end pipeline

```
┌────────────────────────────────────────────────────────────────────────┐
│  1. SETTING UP THE SCENE                                              │
│  Game Root → effects.fxp is parsed → dropdown populated with 82 names │
└────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────────────────────┐
│  2. ATTACHING A PARTICLE TO A MODEL                                   │
│  2DFX panel → Create Effect → Particle → Empty appears at cursor      │
│  Pick effect name from particle_effect_2dfx dropdown                  │
│  Select DFF mesh + Shift-click Empty → Attach to Model button         │
└────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────────────────────┐
│  3. EDITING THE EMITTER                                               │
│  Properties → emitter Empty → INU Particle Properties                 │
│  Tweak texture, blend, colors, size, life, force, etc.                │
│  Add curves for time-varying params (size growth, color fade)         │
└────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────────────────────┐
│  4. VIEWPORT PREVIEW (live)                                           │
│  Refresh Preview → particles spawn in viewport at 30 FPS              │
│  Camera-facing billboards, real color/alpha-over-life shader          │
└────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────────────────────┐
│  5. SAVING TO effects.fxp                                             │
│  Save Particle Effect → write edits back (auto .fxp.bak on first run) │
│  Optionally Overwrite checkbox to update an existing system           │
│  Or save as a new system name (e.g. prt_fire_custom_1)                │
└────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────────────────────┐
│  6. EXPORTING THE DFF                                                 │
│  Export DFF → particle Empty's `2dfx_effect_name` is written into     │
│  the DFF's 2DFX section as a string referencing the system name       │
└────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────────────────────┐
│  7. IN-GAME                                                           │
│  Replace <game>/models/gta3.img DFF + drop effects.fxp into models/   │
│  Engine reads 2DFX → looks up effect by name → plays the system       │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Setting up the scene

Set **Game Root** in **N-sidebar → GTA Tools → Import Map** (collapsible block). The dropdown of available particle effects is fed by `<game_root>/models/effects.fxp`:

- File is parsed once on first dropdown open and cached (key = path + mtime); re-parsed automatically when you save a new system.
- If Game Root is empty or `effects.fxp` is missing — dropdown shows `<Game Root not set>` / `<effects.fxp not found>`.
- Use **Reload effects.fxp** operator if you edited the file externally.

### 2. Attaching a particle to a model

A particle effect is bound to a mesh via a child **Empty** with a `Particle` 2DFX tag.

1. Open **N-sidebar → GTA Tools → 2DFX Effects** (or open the **2DFX floater** with the 🪟 icon).
2. **Create Effect ▾ → Particle** — an Empty is created at the 3D cursor and tagged with `effect_2dfx = 'PARTICLE'`.
3. With the Empty selected, open **Properties → Object → INU Tools: Model** → scroll to the **Particle Effect** dropdown. Pick a system name (e.g. `prt_blood`, `prt_fire_med`, `prt_smoke_huge`).
4. **Attach to model:**
   - Select the DFF mesh you want to attach the effect to.
   - **Shift-click the particle Empty** so it becomes the active object (Empty active + mesh additionally selected).
   - In the 2DFX panel click **Attach to Model** (`gtatools.attach_2dfx`).
   - The Empty becomes a child of the mesh, world position is preserved.

If you need to break the link later — click **Detach from Model** (single effect) or **Detach All from Mesh** (batch unparent of every 2DFX child of the selected mesh).

The Empty now references a system in `effects.fxp`. Its local transform relative to the parent mesh = spawn point + emission orientation in the model's local space.

### 3. Editing the emitter

When a particle Empty is active, **Properties → Object → INU Particle Properties** exposes the full emitter:

**Sprite & blending**

| Property | Default | Description |
|---|---|---|
| `Texture` | from system | Sprite name in `particle.txd` (e.g. `sphere`, `smoke3`, `flame`) |
| `SrcBlend` | 4 | D3D9 source blend factor (`4`=SrcAlpha for additive-alpha, `2`=One for pure additive) |
| `DstBlend` | 5 | D3D9 destination blend factor (`5`=InvSrcAlpha) |

> **Common blend recipes:** SrcAlpha + InvSrcAlpha = alpha-blended sprite (smoke, blood). One + One = additive (fire, magic glow). One + InvSrcAlpha = pre-multiplied (modern engines).

**Colors over lifetime**

- `color_start` — RGBA at birth (time = 0)
- `color_end` — RGBA at death (time = 1)
- `color_mid_enabled` + `color_mid` + `color_mid_time` — optional third point for 3-stop interpolation (e.g. fire: yellow → red-orange → black)

**Size**

- `size_start` — particle size at birth (world units)
- `size_end` — at death

**Emission**

| Property | Description |
|---|---|
| `life` | Particle lifetime in seconds (e.g. 1.5 for smoke, 0.3 for sparks) |
| `life_bias` | ± random offset around base life |
| `rate` | Particles per second |
| `speed` | Initial speed (world units / sec) |
| `speed_bias` | ± random offset |
| `direction` | Emission direction (XYZ vector, normalised) |
| `angle_min` / `angle_max` | Cone spread (radians, 0 = laser, π = full sphere) |
| `volume` (XYZ extents) | Spawn box around origin |
| `volume_radius` | Spawn sphere radius (overrides box when > 0) |
| `volume_min` | Inner box (annular spawn for ring effects) |
| `offset` | Spawn offset from emitter origin |
| `rotation_min` / `rotation_max` | Initial sprite rotation (radians) |
| `rotspeed_min` / `rotspeed_max` | Sprite spin speed |

**Physics**

| Property | Description |
|---|---|
| `force` | Constant force vector (gravity goes here, e.g. `(0, 0, -9.8)`) |
| `friction` | Velocity damping (1.0 = no friction, 0.5 = strong drag) |
| `wind` | Multiplier on engine wind vector (0 = no wind, 1 = full coupling) |
| `noise` | Perlin-noise turbulence magnitude |
| `jitter` | Per-frame random jitter (≠ noise — jitter is uncorrelated) |
| `ground_bounce` | Collision response with ground plane (0 = pass through, 1 = full bounce) |
| `ground_speedmult` | Velocity multiplier after bounce |

**System (whole effect, not per-emitter)**

| Property | Description |
|---|---|
| `sys_length` | Total system duration in seconds (0 = infinite, e.g. fire) |
| `sys_playmode` | Playback mode: 0 = play once, 1 = loop, 2 = one-shot burst, 3 = continuous-with-fade |
| `sys_culldist` | Distance at which the engine stops simulating (LOD cull) |

### 4. Viewport preview & simulation

Two visual feedback modes — **static preview** (default) and **live simulation** (opt-in).

**Static preview** — a single camera-facing quad child of the Empty, textured with the effect's first emitter sprite and tinted with `color_start`. No animation, no spawning — just shows where the effect lives and what it looks like at birth.

- Created automatically when you create a 2DFX Particle or pick an effect name.
- Updated when you change the texture / color via **Refresh Preview** button (also fires automatically after `Switch Emitter` and `Save Particle Effect`).
- Removed via **Remove Preview** button (or `gtatools.remove_2dfx_preview`).
- Billboard rotation handled by a background timer that aligns the quad to the active 3D viewport's camera.

**Live simulation** — actual GPU-driven particle simulator. Scene-wide toggle, runs at 30 Hz:

- Toggle: **N-sidebar → 2DFX panel → Simulation** checkbox (`▶` / `⏸` icon depending on state). Scene property `gtatools_particle_sim`.
- On enable, registers a `bpy.app.timers` tick at `1/30 s` and walks every PARTICLE Empty in the scene.
- Each Empty gets a child mesh `<empty_name>_psim` with a pool of up to **`MAX_PARTICLES_PER_EMITTER = 64`** quads.
- Per-particle state (position, velocity, age, life) lives in module-level dicts — ephemeral, not saved to `.blend`.
- Quads always face the active 3D viewport (orthonormal basis derived from `region_3d.view_rotation`).
- Off-screen → particles tick but no mesh updates.
- On disable, all `_psim` meshes are removed.

> **Static preview** vs **simulation** can both be on at the same time — the preview is the «what does this effect look like in screenshots» reference, simulation is for tuning emission/forces in motion. Simulation is gated globally because each emitter consumes a small per-tick CPU cost (32 emitters × 64 particles × 30 Hz = ~60K vector ops/sec).

### 5. Curves (parameter animation)

Any per-particle parameter can be **animated over particle lifetime** with a piecewise-linear curve. Curves replace static values at runtime: e.g. instead of constant size, the game will sample size from the curve at each particle's normalised age.

**Curve editor location:** scroll past the static properties to the **Particle Curves** section.

**Workflow:**

1. Pick a curve channel from the dropdown — `SIZE.SIZEX`, `COLOUR.RED`, `COLOUR.GREEN`, `COLOUR.BLUE`, `COLOUR.ALPHA`, `EMRATE`, `EMSPEED`, etc.
2. The keyframe list appears with `+` (add row), `−` (remove row), and a UIList for selecting active row.
3. Each row is a `(TIME, VAL)` pair:
   - `TIME` ∈ `[0, 1]` — normalised particle age (0 = birth, 1 = death)
   - `VAL` — channel value at that time
4. Keys are sorted automatically on write.
5. Click **Write Curve to effects.fxp** to persist this curve to disk.

**Example — fire size growth:**

```
SIZE.SIZEX:
  (0.00, 0.5)   ← birth: small ember
  (0.30, 2.0)   ← peak flame
  (1.00, 0.1)   ← death: dissipated
```

**Example — fire color fade:**

```
COLOUR.RED:    (0.0, 1.0) → (1.0, 0.3)
COLOUR.GREEN:  (0.0, 0.8) → (1.0, 0.0)
COLOUR.BLUE:   (0.0, 0.2) → (1.0, 0.0)
COLOUR.ALPHA:  (0.0, 1.0) → (0.7, 0.5) → (1.0, 0.0)
```

> Curves OVERRIDE the static `color_start` / `color_end` / `size_start` / `size_end` values for that channel. To disable a curve, remove all its keys.

### 6. Multi-emitter systems

Many vanilla systems contain multiple emitters that play together. Example: `prt_cardebris` has 4 emitters (chunks, sparks, dust, smoke) for a single car crash effect.

- **Switch Emitter ▾** dropdown in INU Particle Properties cycles between the system's emitters.
- Each emitter has its own sprite, blend, colors, curves — they're independent.
- When you save the effect, all emitters are written.
- When you create a new effect via **New Effect**, only **one** emitter is created — to add more, edit `effects.fxp` directly or clone from a multi-emitter template.

### 7. Saving to effects.fxp

One save operator (`gtatools.save_particle_effect`) with two behaviours selected via a popup dialog:

| Field | What it does |
|---|---|
| `effect_name` | Target system name. Defaults to the currently-selected effect — keep it the same to save in place, or type a new name to **clone** the current effect under that name. |
| `overwrite` | When checked AND the target name already exists, the existing system is overwritten. When unchecked AND the name exists → operator errors out (safety net against accidental overwrite). Ignored when `effect_name` is new. |

Plus two related operators:

| Operator | What it does |
|---|---|
| **Particle Effect New** (`gtatools.particle_effect_new`) | Create a blank new effect from scratch (not a clone). Single emitter with a `sphere` texture, white color fading to alpha=0, life=1.0, rate=10. |
| **Particle Effect Delete** (`gtatools.particle_effect_delete`) | Remove the currently-selected effect from `effects.fxp` after a confirmation dialog. |
| **Reload effects.fxp** (`gtatools.reload_effects_fxp`) | Drop the in-memory FXP cache. Useful if you edited the file externally and need the dropdown / preview to re-read from disk. |

**Save algorithm — what actually happens on click:**

1. Re-reads `effects.fxp` from disk (not from cache — avoids stale state).
2. If `effect_name` is **new** → deep-copies the current system, renames it, appends.
3. If `effect_name` **exists** + `overwrite` checked → reuses the existing system in place.
4. Calls `_apply_particle_props_to_emitter` which writes **only the fields that DIFFER** from the current emitter state (dirty check):
   - Static fields (texture, blend, color, size, life, force, etc.) are compared one-by-one.
   - Curves with more than one keyframe and matching the static value are **NOT touched** — preserves multi-keyframe animations the user hasn't edited.
   - System header (`LENGTH`, `PLAYMODE`, `CULLDIST`) is dirty-checked separately.
5. **No-op early exit:** if not cloning AND zero fields changed → message «No changes — file untouched», nothing written.
6. **Auto-backup** on first actual write of the session — creates `effects.fxp.bak` (only if no `.bak` exists yet). Subsequent writes don't update the backup, so `.bak` is always «session start» state.
7. Write file with CRLF line endings, then `clear_cache()` so the next dropdown open re-reads.

**Saving a single curve** is separate — **Write Curve to FXP** (`gtatools.particle_curve_write`) writes ONLY the currently-edited curve channel (e.g. `COLOUR.RED`), leaving all other curves and scalar fields untouched. Use this for iterative curve tuning without the full-system save.

> **Edit buffer behaviour:** when you switch the dropdown to a different effect, all unsaved edits are reset to the new system's values. **Save before switching**, or your changes are lost.

### 8. Exporting the DFF

The particle binding is stored on the Empty as a custom property `2dfx_effect_name = '<system_name>'`. DFF export reads this and writes a `PARTICLE` 2DFX entry into the DFF's 2DFX chunk: a **24-byte ASCII zero-padded string** containing the system name (truncated if longer than 24 chars).

Nothing else needs to be exported — the particle parameters live in `effects.fxp`, not in the DFF.

**Export path:** `File → Export → INU Export` (or N-panel → Export → DFF) → the DFF picks up every particle Empty parented to the mesh and emits one 2DFX entry per Empty.

### 9. In-game

1. Replace the model in `gta_sa/models/gta3.img` (use **IMG Export** to rebuild the archive with your DFF).
2. Replace `gta_sa/models/effects.fxp` with the edited file.
3. Backup vanilla files first (always).
4. Run the game — particles play at the Empty's local position relative to the model, oriented along the emitter's local axes.

> For testing on **MTA:SA** the workflow is the same, but particles only spawn when a MOD-loaded model with that 2DFX entry is in view.

### Common recipes

**Chimney smoke**

```
Texture: smoke3
SrcBlend / DstBlend: 4 / 5 (alpha-blended)
color_start: (0.4, 0.4, 0.4, 0.8)   light grey, opaque
color_end:   (0.2, 0.2, 0.2, 0.0)   dark grey, transparent
size_start: 0.3 → size_end: 2.5
life: 4.0
rate: 5
direction: (0, 0, 1) — straight up
speed: 0.8, angle_min/max: 0/0.3 (slight cone)
force: (0, 0, 0.3) — buoyancy
wind: 0.5
```

**Sparks (e.g. broken wire)**

```
Texture: spark
SrcBlend / DstBlend: 2 / 2 (additive)
color_start: (1.0, 0.9, 0.4, 1.0) → color_end: (1.0, 0.2, 0.0, 0.0)
size: 0.05 → 0.02
life: 0.4
rate: 30
direction: (0, 0, 1) + angle_max π/3 (45° cone)
speed: 3.0, speed_bias: 1.0
force: (0, 0, -9.8) — gravity pulls them down
ground_bounce: 0.3
```

**Fountain water**

```
Texture: water_drop
SrcBlend / DstBlend: 4 / 5
color: white-tinted blue, alpha 1 → 0
size: 0.1 → 0.05
life: 1.5
rate: 80
direction: (0, 0, 1), angle 0.2
speed: 5.0
force: (0, 0, -9.8)
```

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Dropdown shows `<Game Root not set>` | Set `gtatools_game_root` in Import Map panel |
| Dropdown shows `<effects.fxp not found>` | Check that `<game_root>/models/effects.fxp` exists |
| Particles don't appear in viewport | Click **Refresh Preview** — preview cache may be stale |
| Particles spawn but no texture | `particle.txd` is missing or the texture name doesn't match any entry — see the texture browser to verify |
| Edits disappear when switching effects | You must **Save** before switching — unsaved buffer is reset |
| Edits don't show in game | `effects.fxp` not copied to game folder, OR engine cache: delete `gta_sa.set` to force re-read |
| Curves not applying | Make sure curve has at least 2 keys; single-key curves are ignored |

### Implementation reference

- Parser / writer: [core/fxp.py](../INU_tools/core/fxp.py) — `read_fxp(path)`, `write_fxp(path, fxf)`, cached by `load_cached()`
- Per-object props: `INUObjectProps.particle_*` in `__init__.py:1103+`
- Operators: [ops/effects_ops.py](../INU_tools/ops/effects_ops.py) — 17 operators total (CRUD + curve editing + 2DFX attach)
- Viewport simulator: [ops/fx_preview.py](../INU_tools/ops/fx_preview.py) — 30 FPS update via `frame_change_post`, billboard GPU material with vertex color emission

---

## UV Tools

**Panel:** UV Editor → Sidebar (N) → GTA Tools

| Tool | Description |
|------|-------------|
| UV Grid Randomizer | Randomize UV positions within grid cells |
| Snap to Grid | Snap UV islands to nearest cell |
| 9 Alignment Points | Choose position within cell (top-left, center, etc.) |
| Link Polygons | Move polygons with overlapping UVs together |
| Show UV Grid | Visualize GTA texture atlas grid |
| Island Scale — To grid | Fit island UV height (Rows) / width (Columns) to the Value/Texture-size fraction |
| Island Scale — Texel | Set real texel density (area-based, TexTools-style) |

**Grid settings:** columns × rows (default 4×4).

> 💡 **Example — UV grid for a 4×4 atlas:** ground mesh with 16 grass variants in a 4×4 atlas. In Edit Mode select faces → UV Editor → **UV Grid Randomizer** → each face's UV coords land in a random cell of the 16. In the viewport the ground shows natural variety without manual texture assignment.

### Island Scale

**Box:** UV Editor → Sidebar (N) → GTA Tools → **Island Scale** (below the UV Grid Randomizer).

Two ways to normalise UV island scale. Fields: **Texture** (Texture size, 128…4096, default 512) and **Value**.

- **To grid** — uniformly scales each island so its UV **height** (when **Rows** is set) or **width** (when **Columns** is set) becomes `Value / Texture size`. Aspect is preserved, 3D size is ignored (pure UV fraction). Works **only** when exactly one of Rows **or** Columns is set (not both); the hint line shows the active axis.
- **Texel** — real texel density (px per unit), area-based (UV↔3D) like TexTools. It accounts for the actual geometry size, so detail is levelled across islands. Computed on local geometry — apply object scale first.

> 💡 **Example — uniform texel across buildings:** select all faces in Edit Mode → **Texture** 1024, **Value** 256 → **Texel** → every island is scaled to 256 px/unit, one consistent texture density everywhere.

---

## Check

**Panel:** View3D → Sidebar (N) → GTA Tools → Check

| Button | Description |
|--------|-------------|
| Check Vertex | Find loose vertex and edges |
| Check N-gon | Find polygons with 5+ vertex |
| Check Materials | Check 50 material limit per object |
| Cleanup Materials | Merge duplicate materials and textures (.001, .002) |
| Sort Materials | Sort materials by name (natural sorting) |
| Reset Transform | Zero out Location and Rotation for selected meshes (Scale untouched) |
| LOD/COL → DFF | Snap LOD and COL to their corresponding DFF position |
| DFF / LOD / COL | Hide/show objects by type |
| Type: OBJ/COL/SHA/NON | Batch assign type to selected objects with auto-rename |

> 💡 **Example — preflight a building before export:** ready to export a house. In the Check panel, in sequence: **Check Vertex** (no loose ones) → **Check N-gon** (all faces 3–4 verts) → **Check Materials** (≤50) → **Cleanup Materials** (merge .001 duplicates) → **LOD/COL → DFF** (snap pair to HD position). Now you can safely export — no known issues.

> **Duplicate cleanup:** on IDE and IPL export, Blender duplicate suffixes (.001, .002, etc.) are automatically stripped from model names.

### Validate Scene

**Validate** runs the scene through a set of rules and collects the findings into a list. The list is
**grouped by model**: one row per object — a disclosure triangle, an icon for its type (model / LOD /
COL / material / action), the name and a problem count. Click a row to expand its problems; the arrow
button jumps to the object (and reveals it in the Outliner). While everything is collapsed you get the
overview: which models have problems and how many.

Checked: duplicate `model_id`s, orphan LOD/COL with no model of their own, unlinked 2DFX, empty and
oversized meshes, materials without a texture, unnormalised quaternions in actions, inconsistent
suffixes/prefixes, non-uniform scale, `_ok` / `_dam` pairs, paintjob materials, UV animation together
with night colours, extra colour attributes, Light Beam ASI, plus the cross-game warnings (see
[Validate Scene — cross-game warnings](#validate-scene--cross-game-warnings)).

New in 2.4.0:
- **Loose geometry** — vertices and edges with no faces (what "Check Vertex" selects): such geometry
  exports as garbage or silently disappears.
- **Non-Latin name** — Cyrillic and other non-ASCII characters in an object name. GTA SA accepts only
  Latin letters, digits and underscores in model names; anything else is never found in game.
- A COL is no longer reported as a duplicate of its own model: collisions have no `model_id` of their
  own, they are bound to the DFF by name.

### Export audits — "Game will crash"

Since 2.4.0 every exporter checks what it is about to write against what `gta_sa.exe` actually reads
(the rules were taken from the engine's decompilation). DFF (map and skin), COL, TXD, IFP, IDE, IPL,
`water.dat`, `timecyc.dat`, zones, `plants.dat` and `effects.fxp` all go through it.

Findings reach the operator report at two levels:

| Level | Text | What it means |
|---|---|---|
| **ERROR** | `Game will crash — …` | The engine dereferences something that is not there and faults: missing wheel dummies on a vehicle, a skin with no HAnim node table, out-of-range indices, a clump with no atomics, a collision with offsets past its own record. |
| **WARNING** | `Model: …`, `Skin: …`, `Vehicle dummy: …` | The file loads, but something is lost or differs from vanilla: a truncated name, a dropped 2DFX entry of an unknown type, an over-long data line. |

Each line names the geometry, bone, effect or file row in question, so there is nothing to guess.
Full details of every finding are printed to the System Console.

> The file is still **written** (except when the export is stopped by a real error — a mesh above
> 65 535 vertices, say, or a texture name longer than 31 characters). The report tells you how the
> game will behave; it is not a refusal to work.

### Cleanup Materials — details

The button finds datablocks with `.001`, `.002`, etc. suffix and merges them with the original in a single pass — materials and textures (images) are processed separately.

**Materials:**
- All `material_slots` on meshes that reference a duplicate are switched to the original.
- If no original with the base name exists — the first duplicate is renamed to the base name and becomes the original.
- Unused duplicates (`users == 0`) are removed from `bpy.data.materials`.

**Textures (safe mode):**
- The image reference is replaced inside `Image Texture` nodes in all materials **and** node groups (shader/geometry/compositor).
- A duplicate is merged with the original **only if the absolute file path matches** (`bpy.path.abspath` with library awareness). This prevents false merges in GTA SA, where identically-named textures often come from different TXDs.
- For packed/generated images (no filepath), a weak `source + size` key is used.
- Textures with different paths are **not merged** and counted in the "Skipped" stat.

**Status bar report:**
```
Materials: 12/3 | Textures: 8/2 | Skipped (different paths): 1
```
Format — `merged_slots/removed_duplicates`.

### File Scanner

**Sub-panel:** View3D → Sidebar (N) → GTA Tools → Check → File Scanner

Lints `.dff`, `.col`, `.txd` files **on disk** for crash-prone byte patterns — without importing them into Blender. Useful when:
- you've collected models from multiple sources and want to vet them before packing into IMG;
- a freshly-built map crashes the game and you need to find the offender;
- you're auditing converted/ported models (gmod → SA, etc.).

**Workflow:**
1. Pick a folder via the file picker.
2. Toggle which formats to scan (DFF / COL / TXD checkboxes).
3. Optionally enable «Recursive» to walk subfolders. **Default off** — prevents accidental sweeps of `gta_sa\models\`.
4. Press **Scan**. Progress bar appears in the status bar.
5. Results show in a scrollable list: `severity_icon  filename: short message`. Click a row to see the full description, file path, and «Reveal in Explorer» button.
6. Filter «Only ERROR» (default on) hides WARN/INFO so you focus on real crashes.

**What's checked:**

*COL — collision file format*
- Magic + filesize header consistency
- Bounding sphere/box NaN/Inf or inverted (`min > max`)
- Sphere-collider radius validity, vertex coords inside `(−256, 256)` int16/128.0 range
- Face indices within vertex count
- Surface ID range: vanilla ≤ 178, FLA ≤ 254
- Shadow mesh offset overflow (the Manu-class `0x415D47` streaming crash)
- Face-groups count within documented 1024 cap

*DFF — RenderWare model*
- RW chunk integrity, RW version sanity (vanilla SA = `0x36003`)
- Atomic indices into frame/geometry arrays
- Frame parent-tree validity (no cycles, no forward refs)
- Per-geometry vertex/triangle/material limits (u16 caps + soft warnings)
- UV layer count vs. flag bits agreement
- Skin PLG: bone count u8, max_weights ≤ 4, bone-index validity
- Triangle.material in range
- NaN/Inf in vertex positions, bounding sphere
- `GEOM_NATIVE` flag (PS2/Xbox-only data dropped onto PC engine)
- 2DFX entry count

*TXD — texture dictionary*
- `platform_id` (8 = D3D8, 9 = D3D9 — anything else won't load on PC SA)
- Bit depth in `{4, 8, 16, 24, 32}`
- Power-of-two dimensions (vanilla D3D8 path requires POT — known crashes at `0x004C9691` / `0x00732924` / `0x00749B7B`)
- DXT block alignment (×4)
- AUTO_MIPMAP flag mutual exclusion with `num_levels > 1`
- PAL + DXT mutually exclusive
- Mipmap count vs. `log2(max(w,h))`
- Empty / duplicate / overlong texture names

Every issue code carries a long-form explanation block in the panel («What it means:») describing the root cause and how to fix.

**Save report:**
Three destinations:
- 🟢 **Next to .blend** — default; warns if the scene isn't saved.
- 🟡 **Same folder as scanned files**.
- 🟠 **Custom folder** — file picker.

Output: `inu_lint_<timestamp>.txt` with grouped results.

### Lint Profiles

**Sub-panel:** View3D → Sidebar (N) → GTA Tools → Check → Lint Profile

Single EnumProperty `gtatools_lint_profile` switches the threshold/severity ruleset used by both **File Scanner** and **Map Analyzer**.

| Profile | What it does |
|---|---|
| **STANDARD** | Default — thresholds calibrated against vanilla SA assets (zero false positives on `F:\AllDFF` reference set) |
| **FLA** | Assumes [Fastman92 Limit Adjuster](https://fastman92.com/) is installed — silences FLA-required warnings (Model ID > 19999, surface ID > 178, etc.) |
| **STRICT** | Tighter thresholds (e.g. material limit 50 instead of 100), useful for QA passes before shipping a mod |
| **LENIENT** | Drops all INFO-level diagnostics — useful when auditing legacy projects where minor warnings are noise |

The active profile applies to both **on-disk** (File Scanner) and **cross-file** (Map Analyzer) checks. Switching profile re-evaluates currently-loaded scan results — no need to re-scan.

### Map Analyzer (Game Validator)

**Sub-panel:** View3D → Sidebar (N) → GTA Tools → Check → Map Analyzer

Cross-references **IDE** files (definitions) against **IPL** files (placements) to catch consistency errors before they crash the game.

**Input modes** (one of three):
1. **From game** — uses `gtatools_game_root` + `gta.dat` resolution to collect every active IDE/IPL pair.
2. **From folder** — pick a directory; walks it recursively for `.ide` and `.ipl` files.
3. **Manual lists** — UIList of IDE files + UIList of IPL files; «Add file» picker for each.

**Optional IMG verification** — if a list of files inside the archive is provided, IDE entries are cross-checked against actual DFF/TXD presence.

**Checks performed:**
- **Orphan placements** — IPL `INST` line references a model not defined in any IDE
- **Unused IDs** — IDE entry never placed in any IPL (won't crash, but bloats stream slots)
- **Duplicate IDs** — same model_id defined in two different IDEs
- **NaN coordinates** — position/rotation contains NaN or Inf
- **Interior range** — `inst.interior_id` outside the valid `[0, 256]` window
- **Draw distance sanity** — IDE's `drawdist` ≤ 0 or absurdly large
- **Missing TXD** — IDE references a TXD that isn't in the IMG archive (only when IMG-verify mode is on)
- **Field count** — IPL line has the wrong number of comma-separated tokens

**Results UIList** groups issues by severity (Critical / Warning / Info) with the `LintIssue` shape shared from File Scanner. Click a row → full description + «Open IDE/IPL file» button.

**Save report** — same 3-destination picker as File Scanner.

---

## Texture Browser

**Sub-panel:** View3D → Sidebar (N) → GTA Tools → Texture Browser

Inventory tool for browsing every texture across one or more sources without importing them. Useful when:
- you're hunting for a specific texture by name across multiple TXDs;
- you need to know «which TXD contains `roof_tile_03`?»;
- you're cross-referencing what gets used by what before exporting a TXD batch.

**Sources** (radio-selector):
1. **From IMG** — picks every `.txd` inside a chosen `.img` archive.
2. **From folder** — walks a directory recursively for `.txd` files.
3. **From IDE list** — reads the IDE files' `txd` column and resolves them against `gtatools_game_root`.

**UIList row**: thumbnail preview · `texture_name` · `WxH` · `format` · source `.txd`. Click a row to load the full-resolution texture into the preview pane. Search box filters by name (substring match).

**Cross-reference** («used by» — toggle): for the selected texture, scans all materials in the current `.blend` and lists which objects reference it. Click an object name to jump-select it in the viewport.

Decoding is lazy — texture headers (name + dimensions + format) are read upfront, pixel data only when the row is selected. ~1000 textures in a folder typically scan in under 1 s.

---

## Texture Baking `(2.1.0)`

INU Tools includes a layered texture-baking system (think Photoshop layers, but each layer is a baked map). You stack maps such as AO, Diffuse and Bevel, blend them live on the model, then flatten the stack into a single GTA-ready diffuse texture. The light needed for AO/Shadow/Diffuse-Lit is generated internally — you do not need any lamps in your scene. Baking uses **Cycles** (it must be enabled in your Blender add-ons), and if you have a GPU compute device enabled in Blender Preferences it is used automatically.

**Panel:** `3D Viewport → Sidebar (N) → GTA Tools → Texture Bake`
(the baked texture is shown automatically in the Image Editor)

### Output size, padding & anti-aliasing

Settings at the top of the panel apply to every map you bake:

| Setting | Description |
|---|---|
| **Size** | Square power-of-two preset (32 … 8192). Sets X and Y together. |
| **X / Y** | Independent width/height; each snaps to the nearest power of two. |
| **Padding** | Bleed in pixels past the UV island edges (default 8). |
| **AA** | Supersampling: bakes at an internally larger resolution and shrinks down — removes jaggies/banding (TexTools-style). `Off`, `2×` (default), `4×` (cleaner, slower). Internal resolution is capped at 4096, and Cycles samples are reduced by AA² so AA is almost free on noisy maps. |

> 💡 The output texture name is derived automatically from your model name (known `_DFF` / `_LOD` / `_COL` prefixes and `_hi` / `_low` suffixes are stripped) — there is no name field.

### Bake modes

**Panel:** `Texture Bake` → **Mode** row — the three mode buttons (UV → UV / Hi → Low / Camera) are shown directly at the top of the bake box (the old collapsible "Bake" header was removed).

| Mode | What it does |
|---|---|
| **UV → UV** | Bakes the object onto itself. Source = render UV (the 📷 `active_render` layer); target = the **selected** UV layer. Designed for trim sheets: keep textures on the trim UV and bake light/AO into a separate clean UV. |
| **Hi → Low** | Transfers detail from a high-poly onto a selected low-poly. The pair is found by name suffixes `_hi` / `_low` (e.g. `wheel_hi` ↔ `wheel_low`). The low-poly must have a UV layout. Cage / Max Ray live in **Advanced**. |
| **Camera** | Renders the object with an orthographic camera into a texture with transparency. For billboard trees / impostors: nothing is clipped, the silhouette fills the frame and alpha is taken from it. |

When a mesh is selected the panel shows live info under the mode row (source/target UV, detected Hi/Low pair, or camera framing).

**Camera mode specifics:**
- If the selected model has a `_hi` / `_low` pair, the **high-poly is rendered** and mapped onto the **low-poly billboard plane**; the camera orients itself **along the plane's normal** and the plane's UV is reprojected from that exact viewpoint, so the texture lands pixel-perfect.
- If there is no pair, the object renders itself along a world axis you pick with **View**: `Front −Y` / `Back +Y` / `Right +X` / `Left −X` / `Top +Z`.
- **Padding** — extra room around the silhouette so the crown doesn't touch the texture edge.
- Camera mode renders with EEVEE (matching Material Preview), produces a clean **standard Principled material** with alpha-clip, and does **not** build a layer composite.

> 💡 **Example — tree billboard via Camera mode:**
> 1. Model the detailed tree as `tree_hi` and a flat billboard quad as `tree_low`, and give `tree_low` a UV layout.
> 2. Select the pair, open **Texture Bake**, set **Size** 512, **AA** `2×`.
> 3. Set **Mode** → **Camera**. The panel confirms `Render: tree_hi`, `Onto model: tree_low`, `View: by plane normal`.
> 4. Add one **Diffuse** layer and press **Bake**.
> 5. The billboard now wears a standard material with the rendered tree and a clean alpha silhouette. Save it with **Save as**.

### The layer stack

**Sub-panel:** `Texture Bake → Add layer` and the layer list below it

The stack reads like Photoshop: the **bottom** layer is the base, layers above blend down onto it. New layers are added at the **top**.

> The layer stack is **per-model** — each object keeps its own bake layers (stored on `obj.inu`), not a single scene-global stack. Select a different model and its own stack appears.

**Add a layer:** in the **Add layer** box, pick a map in the dropdown → **Add**. The layer appears at the top of the list with that map's default blend mode and opacity. (Normal Map is added with **Desaturate** already on.)

**Per-layer row controls:**

| Control | Description |
|---|---|
| Eye toggle | Enable/disable the layer in the composite and in flatten. |
| Layer name | Click to **select** the layer (its baked map shows in the Image Editor and its parameters appear in **Selected layer**). |
| **Bake** | Bakes **only this layer's** map into its own image. |
| Save icon (✓) | Saves this single map to a file (enabled once the map is baked). |
| **X / ▲ / ▼** | Remove / move up / move down the selected layer. Order = blend order. |

**Selected layer parameters** (**Selected layer** box):
- **Mode** (Blend mode) — how this layer blends onto the layers below (18 modes, below).
- **Opacity** — 0…1, mixes this layer's blend result over the layers below.
- **Contrast** / **Gamma** — per-layer tone adjustment, live in the preview and the final flatten.
- **Desaturate** — *Normal Map layers only*; greyscales the layer to remove the blue tangent-space tint (like flattening a normal map in Photoshop).

### Available maps

| Map | Default blend | Notes |
|---|---|---|
| **AO** | Multiply | Ambient occlusion. Noisy → uses Samples. |
| **Diffuse** | Normal | Flat albedo (base color, no lighting). |
| **Diffuse Lit** | Normal | Albedo lit by the **scene's own lights** ("Scene light" toggle ON by default), or by an internal 5-sun dome rig when the toggle is off. |
| **Shadow** | Multiply | Cast/contact shadow (no albedo) from the **scene's own lights** by default, or from a single internal key sun when "Scene light" is off. |
| **Bevel** | Overlay | Edge-wear mask from a Bevel-normal trick (lighter on edges). |
| **Normal Map** | Normal | Tangent-space normals. Added with Desaturate on. |
| **Emission** | Normal | The material's own emissive output. |
| **Emission Light (GI)** | Add | Indirect bounce light *from* emissive faces onto neighbours. Noisy → uses Samples. |
| **LightMap** | Multiply | Full GI from the **real scene light** (lamps, sun, world + bounce). Unlike Shadow / Diffuse Lit it does **not** use an internal rig and does **not** isolate the scene — it bakes your actual lights. Very noisy → high Samples + optional OIDN denoise. See below. |
| **Dirt (Cavity)** | Multiply | Dirt in the cavities: the mask darkens wherever the surface is concave. |
| **Edge Wear** | Add | Worn edges: convex corners get lighter (chipped paint, scuffs). |
| **Curvature** | Overlay | Grey curvature map: 0.5 is flat, cavities darker, ridges lighter. |
| **Height** | Multiply | Height gradient over the object's world Z: bright at the bottom (dirt and damp near the ground). |
| **Thickness** | Multiply | Thickness (inside-AO): thick parts dark, thin parts light. Noisy → uses Samples. |
| **Grunge** | Multiply | Procedural grunge: 3D noise in object space, seamless across the surface. |
| **Paint** | Multiply | An empty white layer for hand-painting — never baked, see the **Paint** button below. |
| **Alpha** | Normal | Material transparency. It does **not** join the RGB stack — it drives the result's alpha channel. This is a **cutout**, not translucency: `>= 0.5` is a solid pixel, below that is a hole (GTA's convention, and the same threshold the bake itself applies). The layer's `opacity` multiplies the finished mask, so you can weaken the whole cutout with it. |

The six Dirt / Edge Wear / Curvature / Height / Thickness / Grunge masks are derived from the
**geometry**, with no lighting: the object's materials are swapped for an EMIT material for the
duration of the bake, the same trick Bevel uses. Scene lights, lamps and the HDRI do not affect them.

### Paint — editing a map by hand

The **Paint** button on a layer row switches Blender to **Texture Paint** and makes that layer's
image the paint slot while the live composite stays on screen, so you see each stroke land in the
final texture (WYSIWYG). Press **Tab** to leave.

- Available on any **already baked** layer and on the **Paint** layer.
- The Paint layer starts white (with the Multiply blend, white changes nothing): paint dark and you
  add dirt and shading on top of what was baked.
- The brush projects through the **bake UV**; the active UV layer is switched for you.

### LightMap — GI from the real scene light

Unlike Shadow / Diffuse Lit (internal light rig, scene isolated), **LightMap** bakes the
**actual lights, sun and world** of your scene with global illumination (direct + indirect,
no albedo → a clean lighting multiplier). Move a lamp and the bake changes — it's your real
lighting, à la *The Lightmapper*.

- **Denoise** (Advanced → **Denoise**): cleans the noise of *any* light-dependent map
  (AO / Shadow / Diffuse Lit / Emission GI / LightMap), not just the LightMap. Uses Blender's
  built-in **OIDN** (compositor Denoise node — no external binary) on Blender 4.x, and falls back
  to a **numpy bilateral filter** on Blender 5.x / headless. Clean maps (Diffuse / Normal /
  Emission / Bevel) don't get it. On by default.
- **LightMap samples** (Advanced → **LightMap samples**): separate, higher sample budget
  (GI is noisier than AO).
- **Apply as** (Advanced → **Apply as**) + the **Apply LightMap** button pick how
  the baked LightMap is used in GTA SA (SA has no native lightmap-UV):

| Apply mode | What it does | GTA SA target |
|---|---|---|
| **Layer in stack** | Leaves it as a MULTIPLY layer — flatten/save yourself | Any (manual) |
| **Bake into diffuse** | `LightMap × <base>_DIFFUSE` → one texture (needs a baked Diffuse layer) | Vanilla, no shader |
| **To vertex prelight** | Samples the LightMap per-loop into the **Day** prelight color attribute | Vanilla static lighting |
| **Separate texture + 2 UV** | Saves an `LP_<base>` texture and wires it via a 2nd UV channel Multiply shader (auto-unwraps a non-overlapping **LightMap** UV when **Auto lightmap-UV** is on) | MTA custom shader |

> 💡 **Example — bake a scene-lit LightMap into vertex prelight:**
> 1. Light your scene (sun + lamps + a world/sky). Select the building mesh.
> 2. **Texture Bake** → **Add layer** → **LightMap** → **Add**.
> 3. **Advanced** → keep **Denoise** on, set **Apply as** → **To vertex prelight**.
> 4. Press **Bake** (the map captures your real lights + bounce, denoised).
> 5. Press **Apply LightMap** → the lighting lands in the **Day** vcol; export the DFF as usual.

### Blend modes (18)

Each layer's **Mode** (Blend mode) dropdown matches Blender's Mix node / Photoshop and is identical in the live preview and the final flatten:
Normal, Darken, Multiply, Color Burn, Lighten, Screen, Color Dodge, Add, Overlay, Soft Light, Linear Light, Difference, Subtract, Divide, Hue, Saturation, Color, Value.

### Advanced settings

**Sub-panel:** `Texture Bake → Advanced` (collapsed by default). Filtered to the **selected** layer's map — only relevant options show:
- **Samples** — Cycles samples for noisy maps (AO / lit / GI).
- **Scene lights** (**Shadow / Diffuse-Lit only**, default **ON**) — bake these maps from the **real scene lights** (your lamps / sun / world), the way LightMap does. Off = the internal calibrated SUN rig (works even with no lamps in the scene).
- **Light exposure** (Shadow / Diffuse Lit) — energy multiplier for the internal light rig. Shown only when **Scene lights** is off.
- **Isolate object** (shared, default **ON**) — hide every *other* mesh in the scene for the duration of the bake (lamps are left alone). Fixes **black AO** when the model sits among other map objects (neighbours no longer shadow it) and speeds the bake up (Cycles builds its BVH from the target only). Off = bake with neighbours' shadows. Not applied in **Camera** mode.
- **Bevel radius** / **Bevel samples** / **Selected faces only** — only for the Bevel map. "Selected faces only" now applies specifically to Bevel; with multiple Bevel layers each gets its own image.
- **Transparent background** (shared, default OFF): off — the baked-map background outside the UV islands is filled with the texture's **average colour** (alpha 1), so seams/mips don't bleed black; on — the background is transparent (alpha 0). Does not affect the **ALPHA** map, decal layers, or **Camera** mode, where alpha is meaningful.
- **LightMap** map only (see the LightMap section): **Quality** (sample preset Preview→Production, or Custom→**LightMap samples**), **Light mode** (Combined / Indirect only / Direct only), **Denoise** + **Denoise by albedo/normal** (feature-guided), **Intensity** (exposure) + **Softening** (Gaussian blur), **Apply as**, **Auto lightmap-UV**. Intensity/Softening re-apply without re-baking via the **Post-process** button.
- **Cage** / **Max Ray** — only in **Hi → Low** mode (Max Ray 0 = auto).

> **Baking quality (2.1.x):** compositing and the **Save as** flatten now run in **linear space**, so the saved texture matches the live preview and the in-game look. **Adaptive sampling is disabled** during bakes, so the **Samples** slider actually controls the result (higher = cleaner — no early-out cutting it short).

### Previewing and saving

After baking, two actions appear at the bottom of the panel:

| Button | Description |
|---|---|
| **Show texture** / **Hide texture** | Toggles a flat-emission preview of the baked result directly on the model (visible under any lighting). For a layer stack it shows the live node composite — editing opacity/blend/contrast/gamma updates it instantly. Click again to restore your original materials and render UV. |
| **Save as** | Flattens the enabled layers into one texture (numpy composite, sRGB) and saves it to a file, with a **Size** downscale option: `Original` / `½` / `¼` / `⅛` (proper box-averaging — cleaner than baking small directly). |
| **Show over base (UV2)** | Final two-UV look: builds a node material where the model's **base texture (via its own UV1)** is multiplied by the **baked stack composite (via the bake UV / UV2)** — i.e. `TexUV1 × TexUV2`. Use when you bake AO/LightMap into a separate UV2 and want to see them over the existing diffuse. Per-material (each slot keeps its own base). Click **Hide texture** to restore. |

> 💡 **Example — bake AO + Diffuse and flatten to a TXD texture:**
> 1. Select the building mesh; make sure the working texture UV is the render UV (📷). Open **Texture Bake**, set **Size** 1024, **AA** `2×`, **Mode** → **UV → UV**.
> 2. **Add layer** → **Diffuse** → **Add** (base layer).
> 3. **AO** → **Add** (lands on top with Multiply).
> 4. (Optional) select the AO layer and lower **Opacity** to soften the occlusion.
> 5. Press **Bake** — the live composite appears on the model; inspect via **Show texture**.
> 6. **Save as** → `Original` (or `½` for 512) → save the PNG.
> 7. Import that PNG into your TXD with the texture/TXD tools as the model's diffuse.

---

## Characters (Skinned DFF)

Import/export GTA SA character models with skeleton and animations.

> This section covers **skeletal animation of characters/peds** (the "Character" tab of the Animations panel). Animating static map props with moving parts (windmills, cranes) → see [Animated Map Objects](#animated-map-objects) below.

**Import:**
- Armature with bone hierarchy
- Vertex weights (skin data)
- Bone matrices (Skin PLG)
- Compatible with Kams Script and original game models

**Export:**
- Round-trip with byte-level accuracy
- Correct material indices in BinMesh PLG

**Export settings for characters:** in object properties (`obj.inu`) it's recommended to enable **Normals** and disable **Vertex Colors** — GTA SA characters use normals for dynamic engine lighting instead of baked vertex colors like buildings

> 💡 **Example — import CJ and customize:** File → Import → GTA SA DFF → `cj.dff`. Imports armature + skinned mesh. Edit the mesh (add a hat, tweak proportions) → check weights → **Export DFF** → you get `cj_custom.dff` with the same armature skeleton but modified geometry. Animations from `ped.ifp` apply without any reworking — same skeleton.

### IFP Animations

| Button | Operator | Description |
|--------|----------|-------------|
| Import IFP | `gtatools.import_ifp` | Load animation file (294+ animations in ped.ifp) |
| Export IFP | `gtatools.export_ifp` | Save Blender Actions as IFP |
| Apply | `gtatools.apply_ifp` | Assign animation to armature |

Searchable animation list in the panel.

> 💡 **Example — preview a walk cycle:** imported `cj.dff` with armature → **Import IFP** → pick `ped.ifp` → the list loads 294 animations (WALK_civi, RUN_civi, IDLE_stance, etc.). Type `walk` in the search → pick `WALK_civi` → **Apply Animation** → the walk cycle is applied to CJ's armature, hit Play in Timeline — character walks.

> 💡 **Example — batch import an animation folder:** 50 .ifp files in a folder → Animations panel → **Batch folder…** → pick the folder → all IFPs loaded as separate Actions. Each animation accessible via regular Action Editor.

---

## Animated Map Objects

**Panel:** View3D → Sidebar (N) → GTA Tools → Animated Map Object

GTA SA's standard way to animate **static map props with moving parts** — windmills, cranes, weather vanes, gate doors, propellers, fans. INU Tools uses an **Empty-rig** approach (mimics the Kams 3ds Max script) instead of an armature — this sidesteps the `rest_quat` bug of the bone-flow that caused IFP geometry stepping.

### Required artifacts

For one animated model the game needs **three coordinated artifacts**:

| File | Contains |
|------|----------|
| `<base>.dff` | Frame hierarchy + HAnim PLG (marks animated "bones" by `bone_id`) + meshes |
| `<base>.ifp` | One animation with a track per animated part |
| IDE `anim` entry | `model_id, model_name, txd_name, anim_file, drawdist, flags` |

At runtime: engine parses IDE → sees `anim` entry → loads DFF + IFP → applies the IFP track to the bone hierarchy from the DFF by matching frame names.

INU automates **all three steps** via the **Empty-rig** flow.

### 🚨 Critical rules (READ BEFORE STARTING)

1. **Model name length ≤ 12 chars.** GTA SA uses fixed-size buffers for frame/bone names. Names longer than ~16 chars **crash the game** when the IFP is applied (access violation at `0x534134`). Use short names like `mill`, `gate`, `vane` — NOT `airport_billboard_lvS`.
2. **Animation name in IFP = model name.** The IDE's 4th field is the IFP pack name; inside the pack the game looks for an animation **named equal to the model name (2nd field)**. INU forces this automatically (`action_name=base` in the exporter).
3. **IFP must live inside an IMG archive** (`gta3.img`), NOT as a loose file in `anim/`. The streaming system only scans IMG archives for map-object animations.
4. **IDE entry must be in the `anim` section**, not `objs`. This tells the engine the model has an associated IFP.

### Mesh preparation

Split the model into **two (or more) parts**:
- **Static mesh** — windmill base / crane chassis / vane frame. **Name:** `mill_base` (no suffix), **Model ID:** `0` (not set).
- **Animated mesh** — blades / boom / rooster. **Name:** `mill_blades`, **Model ID:** unique game ID (e.g. `19000`).

> ⚠️ **Model ID is set ONLY on the animated mesh** in Object → INU Tools → Model ID. On the static mesh it stays `0`. Both meshes end up in one `.dff` and the game references the whole model via the single `model_id` in the IDE anim entry.

> ⚠️ **Keep names ≤ 12 chars.** The pivot is auto-named `<rig_name>_pivot1`. With rig `mill` (4 chars) → pivot `mill_pivot1` (11) is fine. With rig `airprtbits12_lvS` (16) → pivot `airprtbits12_lvS_pivot1` (23) → **GAME CRASHES**.

### Setup

Select the animated mesh, **N → Animated Map Object → Setup** (popup):
- **Base name:** short, ≤ 12 chars. E.g. `mill`, `gate`, `vane`. Used as:
  - Empty prefix (`mill_root`, `mill_pivot1`)
  - File names (`mill.dff`, `mill.ifp`)
  - `model_name` in IDE
  - **Animation name in IFP** (forced by the exporter)
- **Action name:** informational only (shown in Action Editor), does NOT control the IFP animation name
- **Rotation axis:** Z (windmill blades) / Y (airplane propeller) / X (boom gate)
- **Turns per cycle:** 1
- **Duration:** 60 frames (= 2 sec @ FPS=30)
- **Active mesh:** "Parent to pivot" — animated mesh attaches to pivot1

Result:
```
mill_root           Empty (ARROWS)    bone_id=0   ← root, static base anchor
└── mill_pivot1     Empty (SPHERE)    bone_id=1   ← rotates, Action on rotation_quaternion
    └── mill_blades                                ← animated mesh
```

### Parent the static mesh

The static mesh (`mill_base`) goes **under root**, NOT under pivot (otherwise it would rotate too):

- **Manually:** select `mill_base` → Shift-click `mill_root` → `Ctrl+P → Object`
- **Via eyedropper:** in N-panel, click the eyedropper "To root (static)" → click `mill_base` in viewport

### Multi-part rig

Two animated parts at once (blades + a rooster on top)? Press **N → Animated Map Object → +Pivot**:

- Creates `mill_pivot2` (bone_id=2) with its own Action
- Attach the second animated mesh under it via the "To pivot" eyedropper
- The IFP will contain **both** tracks in one animation; both parts rotate independently in-game

### Validate (optional, recommended)

**N → Animated Map Object → Validate** checks:
- All pivots under one root
- Unique `inu_bone_id` (no collisions)
- Action exists on each animated pivot
- Mesh-children parented correctly
- **Name length within the safe limit**

Issues appear in Blender's Info area.

### Export

Select **any object of the rig** (Empty root, pivot, or mesh — the exporter auto-finds the rig via `_find_animobj_empty_root`). Press **`DFF+IFP+IDE`** in the N-panel (NOT the "Export" button — that's for standalone IFP flow). Popup:

- **Folder:** where to write
- **Base name:** `mill` — DFF / IFP / IDE `model_name`
- **TXD name:** `mill` (usually same as base)
- **Model ID:** auto-filled from the animated mesh
- **Draw distance:** 300
- **Write IDE entry:** ✓ — appends to the `anim` section of `Scene → INU Tools → IDE Path`
- **IFP name:** empty = base name. Or a shared name like `myhood_anims` to bundle multiple rigs into one IFP
- **IFP mode:** `Append` (default) — adds to existing .ifp without loss
- **Existing IFP:** optional path to an existing file (e.g. `<game>/anim/myhood.ifp`)

Outputs:
- **`mill.dff`** — Empty hierarchy + static + animated meshes + HAnim PLG on root (with full bone tree) and each pivot
- **`mill.ifp`** — **ANP3** format (SA compressed), one animation named `'mill'` (== base name), `bone_id=-1`, first keyframe at `t=0.0`
- IDE file updated with:
  ```
  anim
  19000, mill, mill, mill, 300, 0
  end
  ```

### Place in-game

1. **DFF + TXD → into `gta3.img`** via **N → IDE/IPL/IMG → Export to IMG**, or with IMG Tool manually
2. **IFP → into `gta3.img` too** (NOT into loose `anim/` folder!). All vanilla animated map object IFPs live in `gta3.img` (counxref.ifp, airport.ifp, etc.).
3. **IDE** already updated by the exporter
4. **IPL** — place the object on the map via `Object IDE/IPL` (Properties → Object) → IPL Export. The game animates wherever an `inst <model_id>` row references this ID.

**Rebuild Archive** after replacing any file in the IMG — without it the game uses stale offsets.

After launch — the model animates at every placement.

### 🛑 Pitfalls (ALL CRITICAL)

#### A. Names

| Problem | Symptom | Fix |
|---------|---------|-----|
| **Name > 12 chars** | Crash `0x534134` access violation on animation apply | Use short names (≤ 12 chars) |
| **Cyrillic in Action name** | IFP gets name `'????????'` → game doesn't find animation | INU forces `action_name=base` (ASCII model name) — should auto-fix |
| **Animation name ≠ model name** | Game doesn't find animation → silently doesn't animate (no crash) | INU does this automatically; don't hand-edit IDE |

#### B. IDE

| Problem | Symptom | Fix |
|---------|---------|-----|
| **Entry in `objs` section** | Game loads as a static object, IFP isn't applied | Move to `anim` section (INU does this automatically) |
| **Flag ≠ 0 or = 2097152** | Optional. Vanilla uses `2097152` (bit 21) for animated. Works without it too. | Set `2097152` in the 6th field to match vanilla |
| **Model ID on the static mesh** | Duplicate IDE entries, game gets confused | Static mesh Model ID must be `0` |

#### C. IMG / streaming

| Problem | Symptom | Fix |
|---------|---------|-----|
| **IFP in `anim/` folder** | Game can't find the animation (loose .ifp isn't scanned by streaming for map objects) | Put IFP in `gta3.img` |
| **Forgot Rebuild Archive** | Stale offsets, new file invisible | After any IMG file replacement — Rebuild |
| **Duplicate name across IDEs** | Conflict, undefined behavior | One model_name = one IDE entry across the whole mod |

#### D. DFF internals (INU handles automatically)

| Aspect | What INU does | Why |
|--------|---------------|-----|
| **HAnim PLG on root** | Writes full bone tree | Engine requires this for bone hierarchy |
| **HAnim PLG on each pivot** | Minimal `{bone_id}` | Marks the bone in the hierarchy |
| **`bone_type` in bone list** | `[0, 1]` for 2 bones, `[0, 3, 0, …, 1]` for more | Exact match with vanilla RW format |
| **`frame.flags = 0x20003` on root** | Auto-set for animobj root | Without this the HAnim hierarchy walker fails inside the engine |
| **ATOMIC `flags = 5`** (render + collision) | Default in `core/dff.py` | Without the collision bit the engine crashes on collision tests |
| **DFS pivot sort** | Empties with `inu_bone_id` come first in hierarchy | Pivot becomes `idx=1` (as in vanilla), not `idx=2+` |

#### E. IFP internals (INU handles automatically)

| Aspect | What INU does | Why |
|--------|---------------|-----|
| **ANP3 format** | Forced in `build_ifp_from_empty_rig` | The vanilla SA format (counxref.ifp, airport.ifp) |
| **`bone_id = -1`** | For all bones | Vanilla always uses `-1`; the game matches by frame name |
| **First keyframe at t=0.0** | Normalised via `(frame - frame_start) / fps` | Without this the game can't find the initial key |
| **Root excluded** | `inu_animobj_empty_root` is skipped in IFP | In vanilla the root is never animated |

#### F. Other

- **"No animations to export"** — you pressed **«Export»** instead of **`DFF+IFP+IDE`**. «Export» is the standalone IFP operator for armatures, not for Empty-rigs.
- **DFF stepping in-game** — quaternions weren't normalised at export. Fixed in v2.0.0 (`ifp_export.py` via `bl_quat.normalize()`). Re-export if you used an older version.
- **Skinned peds:** Empty-rig is for **map objects**. Skinned characters use the armature + IK-rig workflow (`ik_rig.py`).

### 🔬 Crash diagnostics

If the game crashes when the model appears:

1. **Check name length** — over 12 chars? Shorten it.
2. **Check IDE section** — is the model in `anim`? (not `objs`)
3. **Check IFP in IMG** — does `gta3.img` contain `<base>.ifp`?
4. **Install `crashes.asi` + `CrashRpt1402.dll`** — captures the address. `0x534134` typically = HAnim / CClumpAnimMgr (name length or structure issue).
5. **Isolation:** temporarily move the IDE entry into `objs` (flag=0). If it loads — the crash is in the animation. If it still crashes — something else is wrong (other mod / config / scripts).

---

## Cutscene Cameras (.dat)

**Panel:** View3D → Sidebar (N) → GTA Tools → **Animations** → **Camera (cutscene .dat)** box

Import/export a GTA cutscene-camera trajectory (`.dat`, the same format as the `SetCamera.ms` MaxScript).

| Button | Operator | Description |
|--------|----------|-------------|
| Import | `gtatools.import_camera_dat` | Load a camera `.dat` — builds a **Camera + Empty** (`…​.Target`) linked by a **Track To** constraint |
| Export | `gtatools.export_camera_dat` | Write the Camera + its Target back to `.dat` |

The `.dat` is a text file of four blocks (FOV keys, Roll angle, camera position, target position), each closed by `;`, then padded with zeros to a multiple of 2048. Coordinates are metres, Z-up — 1:1 with Blender, with a single Z-offset (−1.0 on import, +1.0 on export) to work around the engine's Z-bug, exactly like the original script. FOV is stored as the camera's vertical field of view.

---

## Handsign (ghands.ifp)

**Panel:** View3D → Sidebar (N) → GTA Tools → **Animations** → **Handsign Tools** box

Author gang-sign gestures for `ghands.ifp`. In GTA SA a hand sign is **three separate skeletons/animations** in one file: `gsignN` / `gsignNlh` (the pose of the player's **arms**; the `lh` variant is left-arm-only, used when a weapon is in the right hand), `lhgsignN` (the fingers of the left hand model `shandl.dff`) and `rhgsignN` (the fingers of the right hand `shandr.dff`) — 20 blocks in all (`gsign1..5` + `gsign1lh..5lh` + `lhgsign1..5` + `rhgsign1..5`).

| Button | Operator | Description |
|--------|----------|-------------|
| Attach hands | `gtatools.handsign_attach` | **Child Of** constrain the hand models' forearm/wrist bones to the player skeleton's wrists so the hands ride along when you animate the gesture in the viewport (bones are not merged) |
| Detach hands | `gtatools.handsign_detach` | Remove those constraints |
| Export gesture → ghands.ifp | `gtatools.handsign_export` | Export the gesture in one pass — the three active actions (arms + both hands) via the standard IFP exporter, one armature at a time |

> The export back-fills each bone's canonical SA `bone_id` by name (ped and hand skeletons use separate id tables) — without a correct `bone_id` the ANP3 animation wouldn't be applied by the game.

---

## Fragment Mesh

**Panel:** View3D → Sidebar (N) → GTA Tools → **Check** → **Fragment mesh** button (`gtatools.fragment_mesh`)

Split the active mesh into separate **shard objects** (a port of `object_explode.ms`). Each shard is a full copy of the object with the "foreign" faces deleted, so UVs, vertex colours and materials are preserved as-is.

| Mode | What it does |
|---|---|
| **Grid (X/Y step)** | Slice into a rectangular grid by X/Y step. |
| **Clusters (N seeds)** | Group faces by the nearest of **N** random seeds — a coarse Voronoi split **without** adding new cuts (existing faces are just partitioned). |

Options in the dialog: **X / Y step** (grid step) or **Shard count / Seed** (scatter), **Shard name** (base name), and **Delete original** (on by default). For true geometric fracturing with real break planes, use Blender's built-in **Cell Fracture**.

---

## Split into Chunks

**Panel:** View3D → Sidebar (N) → GTA Tools → **Check** → **Split into chunks** button (`gtatools.chunk_map`)

Cut a large map mesh into square pieces along a **global XY grid**, turning one huge model into a
set of objects you can export as separate DFFs, each with its own COL and its own IPL row.

| Option | What it does |
|---|---|
| **Chunk size (m)** | Side of the square. The grid is global (X = k·size), so neighbouring objects are cut along the same lines. |
| **Cut mode** | **Along grid lines** — faces are physically cut exactly on the cell borders. **By existing geometry** — nothing is cut, a face goes to the chunk its centre falls into. |
| **Separate materials** | Give every chunk its own copies of the materials (needed if you will paint chunks individually). |
| **Center origin** | Put each chunk's origin at its geometric centre (otherwise the shared origin is kept). |
| **Hide original** | Hide the source mesh in the viewport and render after slicing. |

Chunks are full copies of the object with the "foreign" faces deleted, so UVs (both sets), vertex
colours, normals and materials survive as-is. Names follow `<Base>_Chunk_X_Y`.

Source: [`ops/chunk_ops.py`](INU_tools/ops/chunk_ops.py) → `GTATOOLS_OT_chunk_map`. Adapted from
[ChunkTools](https://github.com/milevskiy27/ChunkTools) (milevskiy27, Apache-2.0).

---

## Water IO

**Panel:** View3D → Sidebar (N) → GTA Tools → Water

| Button | Description |
|--------|-------------|
| Import Water | Load water.dat |
| Export Water | Save water.dat (from Water collection) |
| Add Water | Create water quad with current settings |
| Snap to Grid | Align vertices to 4-unit grid |
| Snap to Block (500) | Align vertices to the nearest 500-block corner |
| Split by Blocks (500) | Cut the selected water along the 500×500 block grid (the blue lines of the limits overlay) so every face sits inside a single block — oversized/straddling faces render untextured in-game. The pieces are also separated into one object per block (`Water_-3_2` etc.), carrying over the water flag, material and collection; the original object is removed. Untick **Separate into objects** in the operator panel (F9) to keep it all as one mesh. N-gons left by the cut are triangulated, and water params (speed / wave height) are carried over to the new vertices |
| Stitch Edges | Merge overlapping water quads |
| Show Limits (500) | Viewport overlay: block grid + face tint (green fits / orange straddles / red >500) |

**Water properties:**
- Flag: 0=Default visible, 1=Invisible, 2=Shallow visible, 3=Shallow invisible
- Speed X/Y/Z — flow velocity
- Wave Height — wave intensity
- Texture: waterclear256 with flow animation

> 💡 **Example — lake for a custom map:** View3D → Water → **Add Water** → params: Flag `0` (default visible), Wave Height 0.3m, Speed 0.02 — a 100×100m quad appears with water properties. Scale it to match the lake size → **Snap to Grid** so vertices align with GTA's regular grid → **Export Water** → you get `water.dat` ready for in-game use.

---

## Map zones (map.zon)

**Panel:** View3D → Sidebar (N) → GTA Tools → map.zon

Zones from `data/map.zon` and `data/info.zon` — rectangular areas of the map: `map.zon` holds map zones (type 3), `info.zon` the navigation zones with GXT names (type 0). Total conversions add their own types (e.g. 4 for weather zones). Both files share one line format:

```
name, type, x1, y1, z1, x2, y2, z2, level, GXT-key
LA01, 3, 480.0, -3000.0, -500.0, 3000.0, -850.0, 500.0, 1, UNUSED
```

| Button | Description |
|--------|-------------|
| Import | Load a `.zon` — every zone becomes a wireframe box in the `ZON_<file name>` collection. Re-importing the same file replaces the old boxes |
| Export | Write the zones back to a `.zon`. Selected boxes are written, or the whole collection of that file when nothing is selected. The old file is copied next to it as `.bak` once |
| New zone | A 100×100×100 box at the 3D cursor, type 3 (map zone) |
| Lines to clipboard | Generate ready-made lines for the selected objects and put them in the clipboard (and in the `INU_map_zon` text block in the Text Editor) — paste them into `map.zon` by hand. A plain mesh is measured by its bounds, so you can select a building and get a line covering it |

**Zone properties** (edited in the panel while a box is selected): name, type, level (island / region: 0 generic, 1 LS, 2 SF, 3 LV; mods extend it), GXT key (`UNUSED` when the zone has no name). Coordinates come from the box bounds — move and scale it with plain Blender tools.

**Worth knowing:**
- Line order is preserved: the engine returns the **first** matching zone, so reordering changes behaviour. New zones are appended at the end.
- Zones you didn't touch are written as their original line, character for character — import + export with no edits leaves the file identical (comments, header and line endings included).
- A reversed bbox (`x1 > x2` etc.) can never match in game — such zones are listed in the import report, but never silently "fixed".
- The engine splits a line on commas **and spaces**, so a stray space inside a number shifts every column after it. The addon reads it the same way the game does and reports such lines (see the system console).

---

## Path IO

**Panel:** View3D → Sidebar (N) → GTA Tools → Paths

### Paths IPL (Vehicle/Pedestrian)

| Button | Description |
|--------|-------------|
| Import paths.ipl | Load path definitions |
| Export paths.ipl | Save path data for gta.dat |
| Create Path | New path curve |
| Convert to Path | Convert edges/curve to path data |

Auto-splits into groups of 12 nodes (GTA SA limit).

> 💡 **Example — create a vehicle path with a roadblock:** Paths → **Create Path** → a curve appears → Edit Mode → add points along the road. In Edit Curve mode the panel reveals flag buttons: select one point in the middle of the road → **Toggle Roadblock** → that point becomes a roadblock stop. At an intersection select a point → **Traffic → Normal** → cars will wait at the traffic light there. **Export paths.ipl** → the encoded flags are written to the file.

### Train Tracks

| Button | Description |
|--------|-------------|
| Import tracks.dat | Load train track data |
| Export tracks.dat | Save track definitions |
| Create Track | New track curve |
| Mark Station | Toggle station point (edit mode) |

> 💡 **Example — add a new station on an existing track:** imported tracks.dat (curve loaded from points), Edit Mode → select a point at the desired spot → **Mark Station** → the point is flagged as a stop (marker becomes visible via **Refresh Station Markers** — a visible Empty sphere). Export → station flag is written for that point in tracks.dat.

### Compiled Nodes

| Button | Description |
|--------|-------------|
| Import NODES.dat | Load compiled binary path nodes (multi-file selection) |
| Export NODES.dat | Save compiled nodes to selected folder |

**Import:** select multiple files (nodes0.dat, nodes1.dat, ...) at once. Each imported object gets a `nodes_filename` property with the source file name.

**Export** works in two modes:
1. **By filename** — if objects have `nodes_filename` property (set on import), nodes are grouped by source files and saved with the same names
2. **Auto-split by zones** — objects without `nodes_filename` are automatically distributed across the GTA SA map zone grid (8x8, 64 zones, 750 units per zone). Each vertex is assigned to a zone by coordinates: `gx = (X + 3000) / 750`, `gy = (3000 - Y) / 750`. Files are saved as `nodes0.dat` ... `nodes63.dat`

> **Zone grid:** GTA SA map ranges from -3000 to +3000 on X and Y. Zones are numbered left-to-right, top-to-bottom (zone = gy × 8 + gx).

---

## Vehicles

**Panel:** View3D → Sidebar (N) → GTA Tools → **Vehicles**

Vehicle-workflow tools: quick single-DFF export, uniform scaling of the whole vehicle hierarchy, and `_ok` / `_dam` damage-variant management.

| Button | Operator | Description |
|--------|----------|-------------|
| Export vehicle (single DFF)… | `gtatools.quick_single_export` | Turns on "Single DFF" mode and opens the export dialog — the whole vehicle (collision + spheres) ships into one `.dff` |
| Vehicle scale… | `gtatools.vehicle_scale` | Proportionally scales the whole hierarchy (root Empty + meshes + dummies), baking scale into mesh data. Options: `factor`, `dummies_only` |
| Create _dam | `gtatools.vehicle_add_damage_variant` | Makes a damaged (`_dam`) duplicate of the active mesh (source renamed to `_ok` if needed). `_dam` is viewport-hidden but still exported into the DFF |
| Show: OK / Dam / Both | `gtatools.vehicle_show_damage` | Toggles viewport visibility: intact / damaged / both. Preview only — does not affect export |
| Check pairs | `gtatools.vehicle_pair_report` | Scans for `_ok`/`_dam` pairs, reports unpaired meshes (the engine skips them on damage). Details in the system console |

### Frame Hierarchy

Collapsible sub-panel under Vehicles — an indented tree of the active object's frames with per-row reparenting, plus validation and L/R mirroring. Frame names are written verbatim into the DFF, so exact naming matters.

| Button | Operator | Description |
|--------|----------|-------------|
| Validate Vehicle | `gtatools.frame_validate` | Checks dummy names against the vanilla SA template; lists missing required ones and suspicious wheel names (no `_lf/_rf/_lb/_rb`) |
| Mirror L↔R | `gtatools.frame_mirror_lr` | For selected `_lf`/`_lb` frames creates a mirrored twin (`_rf`/`_rb`) with local X flipped |
| ⤴ (per row) | `gtatools.frame_reparent` | Make this frame the parent of the active one (world position kept, `matrix_parent_inverse` reset — DFF requirement) |
| ⛓ (per row) | `gtatools.frame_reparent` | Unparent the frame (make it a root) |
| Frame name | `gtatools.frame_select` | Click selects the frame. **F2** renames the active frame |

> 💡 **Typical order:** scale if needed → select a mesh and "Create _dam" for each damaged twin → edit `_dam` → preview OK/Dam/Both → "Check pairs" → "Export vehicle (single DFF)".

---

## Grass

**Panel:** View3D → Sidebar (N) → GTA Tools → **Grass**

Editor for GTA SA procedural grass from `plants.dat`: import/edit/export entries, a live scatter preview in the viewport, and assigning a plants.dat surface (COL material) to selected faces so grass grows there.

| Button | Operator | Description |
|--------|----------|-------------|
| Show grass | `gtatools.grass_preview` | Live-preview toggle: builds temporary grass cards on the selected COL meshes from the plants.dat entries and updates as you edit. Press again to remove. Preview is not exported |
| Import | `gtatools.grass_import` | Parses `plants.dat` into the editable entry list |
| Export | `gtatools.grass_export` | Writes the list back to `plants.dat`, preserving the game's formatting; backs the original up once as `plants.dat.bak` |
| + / − / duplicate | `gtatools.grass_add` / `grass_remove` / `grass_duplicate` | Add / remove / duplicate an entry |
| Assign to selected faces | `gtatools.grass_apply_surface` | Assigns the entry's surface to the selected faces (auto-creates a COL material with the right surface ID) — this marks faces as grass-bearing |

**Paths:** `.txd` (`gtatools_grass_txd_path`, grass sprites) and `.dat` (`gtatools_plants_dat_path`; falls back to Game Root).

**Selected-entry fields** (collapsible sections): **Base** (PCD id, density), **Texture** (slot/model id, UV offset — sprite `txgrass{Slot}_{UVoff}`), **Color** (RGB, intensity + variation, alpha), **Size** (XY/Z scale + variances), **Wind** (bend scale + variation). The magnifier by the name opens the COL surface picker.

> 💡 **Order:** set `.txd`/`.dat` → Import (or +) → pick an entry, its surface and fields → "Assign to selected faces" on terrain faces → "Show grass" to preview → Export.

---

## X Radar Maker

**Panel:** View3D → Sidebar (N) → GTA Tools → **X Radar Maker**

Renders the scene top-down (ortho camera) into GTA SA minimap/radar tiles (PNG) and packs them into TXD archives. The SA map is assumed to span −3000…3000 on X/Y.

**Settings** (`scene.inu_settings.*`):
- **Folder** (`gtatools_radar_output`) — where PNGs (and a `txd/` subfolder) are saved.
- **Grid** (`gtatools_radar_grid`) — the N×N tile grid (`radar00`, `radar01`, …).
- **Size** (`gtatools_radar_size`) — pixel resolution of each tile.
- **Height** (`gtatools_radar_height`) — Z height of the ortho camera.
- **Indices** (`gtatools_radar_specific`) — comma-separated indices (`0,1,8,9`) for the SPECIFIC mode.

| Button | Operator | Description |
|--------|----------|-------------|
| Generate → Generate radar | `gtatools.radar_generate` (`ALL`) | Full grid×grid of `radarNN.png` tiles |
| Generate → Menu radar (3x3) | `gtatools.radar_generate` (`MENU`) | 3×3 menu radar (`MapTop01…MapBot03`) |
| Generate → Full radar | `gtatools.radar_generate` (`FULL`) | One full-map image `FullRadar.png` |
| Generate → Full menu | `gtatools.radar_generate` (`FULL_MENU`) | One image `FullMenuRadar.png` |
| Generate → Specific tiles | `gtatools.radar_generate` (`SPECIFIC`) | Only the tiles listed in "Indices" |
| Pack into TXD | `gtatools.radar_pack_txd` | Packs `radarNN.png` into TXDs (one tile = one TXD) in `output/txd/`; missing PNGs are skipped |

> 💡 **Order:** set folder, grid, size and height → "Generate" → pick a mode (ALL for the game grid, or SPECIFIC with indices) → "Pack into TXD".

---

## Time cycles (timecyc.dat)

**Panel:** View3D → Sidebar (N) → GTA Tools → **Time cycles**

Reads `data/timecyc.dat` (and `timecycp.dat`), turns a weather + hour into
actual Blender lighting, and writes edits back to the file.

A timecyc file holds one block per weather (23 in vanilla SA) and exactly
**8 time slots** inside each: 00:00, 05:00, 06:00, 07:00, 12:00, 19:00,
20:00, 22:00. The game interpolates linearly between neighbouring slots
(22:00 → 00:00 wraps through midnight), and so does the panel — the hour
slider is continuous, but you always **edit a slot**, never an arbitrary hour.

**GTA III and Vice City** go through the same import: the game is detected
from the file's shape (24 rows per weather → III at 40 numbers per row, VC at
52), the slots become **24 — one per hour**, and the panel only shows that
game's fields: III has no object ambient, water or PostFX but has top clouds
and a **Trails** colour (blur, RGBA); VC has two ambient pairs (normal and
with Trails on), top clouds, Trails RGB and water. Export writes the file in
its native format regardless of the "Game" tab.

| Button | Description |
|--------|-------------|
| Import | Load a `timecyc.dat`, apply it to the scene and switch viewports to Material Preview |
| Export | Write the file back. Untouched rows are written byte-for-byte (comments, tabs, CRLF included), a `.bak` of the previous file is left next to it |
| **Time-cycle on/off** | Master toggle at the top of the panel: **ON** — apply the whole cycle to the scene (light, fog, prelight game look on models) and enable live preview; **OFF** — full reset (materials back to PBR, world and compositor clean) |
| Revert slot | Return the current slot to the values on disk |
| Re-read file | Reload from disk, dropping all unsaved edits |
| To all slots of the weather | Copy the current slot into every slot of this weather (8 for SA, 24 for III/VC) |

**Live preview is always on.** While the cycle is enabled, any change to the hour/weather/slot fields rebuilds the scene immediately — there is no separate "Live preview" or "Apply" button any more, and the viewport is switched to Material Preview automatically. The hour slider follows the **slot**: drag the hour to 21:00 → "Edit slot" switches to the nearest slot (20:00) and shows its fields below; picking a slot in the dropdown conversely sets the hour to that slot's time.

**What maps onto what**

| timecyc | Blender |
|---------|---------|
| Sky top / Sky bot | World gradient — zenith ↔ horizon colour, sharpness set by "Horizon sharpness" |
| Amb / Amb_Obj | Ambient background (which of the two is used is a preview toggle) |
| Dir + DirectionalMult | Colour and energy of the `INU_Timecyc_Sun` sun lamp |
| SunSz | Sun angular size |
| FarClp | Fog density and, optionally, the viewport clip end |
| WaterRGBA | Base colour + alpha of the imported water material (`waterclear256`) |
| PostFX 1 / 2 | The frame colour filter — **always on** while the cycle is active (no toggle; without it the image doesn't match the game). The game draws it as a fullscreen quad textured with the frame, blend `SRCALPHA/ONE`, so `out = in*(1 + rgb1*a1 + rgb2*a2)` (SkyGfx `postfx.cpp`, PC path). For vanilla `EXTRASUNNY_LA` at midday that is a gain of **1.91 / 1.76 / 1.42** — which is exactly why the game frame is lighter and more cyan than the raw timecyc sky. Applied as a **screen** stage in the compositor, right after the fog and over the whole frame — sky included — multiplied in gamma space, exactly where the game applies it |

**Matching the game's lighting**

SA is not PBR, so the preview does not light the scene the way Blender normally would. What the engine actually does, from the reversed pipelines:

```
prelight = day*dayparam + night*nightparam
colour   = (prelight*surfDiff + ambient*surfAmb) * matCol      // ambient is ADDED
final    = colour * texture
```

(SkyGfx `shaders/vs/xboxBuildingVS.hlsl` / `ps2BuildingVS.hlsl`; the ambient register is filled from `CTimeCycle::GetAmbient* × CCoronas::LightsMult`.) Buildings get **no** directional light and cast **no** shadows — all their lighting is baked into the vertex colours. Directional plus the brighter `Amb_Obj` go to cars, peds and objects instead (`MTACalcGTAVehicleDiffuse`: `saturate(TotalDiffuse + TotalAmbient + emissive)`).

The panel reproduces that:

| Toggle | What it does |
|--------|--------------|
| **Game look (unlit)** (on by default) | The prelight colour goes straight into Emission, bypassing PBR — no shadows, no speculars, and no blue tint from the sky. This is what makes the viewport match a game screenshot. |
| **Apply to scene models** | Turns the prelight preview on for every mesh with vertex colours and wires them to the current mode — the fastest way to get a whole imported map looking right. |
| **Fog** (on by default) | Fade into the horizon colour by distance — a **screen** stage in the compositor, driven by the depth pass, exactly like the game's fixed-function fog. It therefore covers everything in frame, including objects the prelight preview never touched. `FogSt` and `FarClp` come from the slot in metres (`TimeCycle.cpp` keeps them as-is; far clip is pulled towards 1000 when the camera climbs above 200). Knobs: **Fog curve** (1 = the honest RW ramp, higher pushes the haze towards the horizon) and **Fog distance ×** (the in-game frame also depends on the draw-distance slider, which timecyc does not carry). The sky threshold is fixed at **0.819 × the viewport clip end**: the sky (at clip distance) stays fog-free so the gradient survives, while all geometry closer than the clip gets fog. This fixes the old "fog cuts off" on large maps (far geometry sticking out sharp) and the reverse (fog flooding the sky) — the threshold now tracks the real clip. |

Ambient (`Amb`) is added to the prelight inside the shared node group and then clamped (`saturate`), exactly as the engine does it — which is why it looks almost black in the panel at midday: all the daytime brightness comes from the baked prelight, not from ambient.

This is also why **weather changes how strong the prelight looks**. There is no per-weather prelight multiplier in the engine — `CCoronas::LightsMult`, which scales the ambient register, is just a fade-in to 1.0 after a load (`LightsMult = min(TimeStep*0.03 + LightsMult, 1)`), not a weather value. What differs is `Amb` itself: a clear slot has an almost black `Amb`, so the baked prelight shows at full contrast; an overcast or rainy slot has a much brighter `Amb`, which lifts the shadows and washes the prelight out. Compare the `Amb` swatch between two weathers in the slot editor and you will see the whole effect.

Fog and PostFX are **screen** stages: they live in the scene compositor (`INU_TC_*` nodes) and need Compositor turned on in the viewport shading — the addon switches it on automatically when the cycle is enabled (Import / master toggle). Blender computes viewport compositing on EEVEE, which is what the preview uses anyway. Your own compositor nodes are left alone: whatever fed `Composite` before is remembered and restored when both toggles go off. In Solid shading there is no compositor, so neither effect shows there.

Objects **without** the prelight preview stay on ordinary PBR: they are lit by the world (ambient `Amb_Obj` by default, with the sky kept as camera background only) and get no node fog.

**Prelight by time of day (Day ↔ Night)**

SA keeps the night vertex colours in a separate DFF section (Extra Vert Colour) and the engine writes the blend into the prelight itself:

```
preLit = day * (1 - dnParam) + night * dnParam
```

(`CCustomBuildingDNPipeline::SetPrelitColors`; in game the day→night swap lands on 20:00 → 21:00, the same hours street lamps and headlights come on.)

**Prelight by time of day** reproduces that with nodes and is **always on** while the cycle is active (no UI toggle): one shared group `INU_Timecyc_DayNight` reads the `Day` and `Night` colour attributes and mixes them by a single internal Value. Moving the hour slider changes that one number, so a whole map updates without touching hundreds of materials.

- It hooks into materials where the **prelight preview** is already on — the panel says so when there are none (press "Apply to scene models").
- The dusk/dawn hours are fixed: 20:00 → 21:00 (from the engine) and 05:00 → 06:00 (from the timecyc slots). They used to be editable in the UI — that block was removed and the values are now constant.
- Meshes without a `Night` attribute are left on their day colours — the group gates on the night attribute's alpha, which is zero when the attribute is missing, so nothing turns black at night.

**Worth knowing:**
- Row width is detected per file: vanilla SA is 51 values (with `Dir` RGB, no `DirectionalMult`), some total conversions ship 52. Short rows — the vanilla `UNDERWATER` block has one — keep their width on export, so no column is ever added or lost.
- If a row is shorter than the schema, the panel says so: its fields are read shifted, exactly the way the game's parser reads them.
- Fog is a compositor **screen** stage (not a World volume) and is on by default with the cycle; it costs real viewport frames on a full map, so turn the **Fog** toggle off if the viewport gets heavy.
- This is an atmosphere match, not a pixel match. SA is not PBR — it lights the world as `texture × (prelight vcol × ambient + directional)` — so use it to pick lighting and shoot screenshots, not to predict the in-game frame exactly.

---

## Integrations

### Itera Tools 3

**Panel:** View3D → Sidebar (N) → GTA Tools → Itera Tools 3

| Button | Description |
|--------|-------------|
| Vertex Lit Linear | Applies a special material for previewing Itera lighting on the model |
| Quickstart | Creates a modifier on the model and a collection with light sources |
| Remove Itera | Removes the lighting material and restores the original materials |

**Workflow:**
1. Click **Vertex Lit Linear** — a lighting preview material is applied to the model
2. Click **Quickstart** — a modifier and light collection appear
3. Position and configure the lights as needed
4. In the model's modifier, set **Output Type / Bake → Vertex Colors**
5. In the **Export Vertex Color** field, type your color attribute name — `Day` or `Night`
6. When lighting is finalized — **apply the modifier**
7. A third extra color attribute will appear — you can delete it
8. Click **Remove Itera** — original materials are restored on the model

> **IMPORTANT:** Do not edit the model's geometry or materials while Itera material is active. Modifying the model in this state can corrupt UV coordinates and break texture assignments.

Panel is only visible when Itera Tools 3 is installed in Asset Libraries.

### LightMap (beta_MTA)

**Panel:** View3D → Sidebar (N) → GTA Tools → Lightmap Generator (beta)

Generate Lua code for MTA SA lightmap scripts. The MTA script replaces shaders at runtime, adding a second UV layer with the lightmap over the base textures.

**Full workflow:**

1. **Create UV1** — main UV layout for model textures (bricks, roof, etc.)
2. **Create UV2** — second UV layout specifically for the lightmap. Each polygon must occupy a unique space with no overlaps. In Blender: UV Editor → UV → Smart UV Project or manually
3. **Bake lighting to a texture using UV2** — use any baking method you prefer (Blender Bake, Cycles, third-party addons). The result must be baked to a texture using the UV2 layout
4. **Save lightmap** as a PNG file (e.g. `lightmaps/building01.png`)
5. **Export DFF** — make sure both UV layers are enabled in object properties (`uv_map1` and `uv_map2`). The addon writes both UVs to the DFF file
6. **Generate code:**
   - Select the object
   - Set the **lightmap path** (relative, as in MTA resources)
   - Set the **Model ID**
   - Click **Generate**
7. **Copy** the result into your MTA Lua script

| Button | Operator | Description |
|--------|----------|-------------|
| Load Lightmap | `gtatools.load_lightmap` | Load lightmap image for preview |
| **LightMap from folder…** | `gtatools.lightmap_folder` | Hand out lightmaps to a batch of models from one folder: `<name>_d` is the day map, `<name>_n` the night one (matched against the object or mesh name) |
| **Day** / **Night** | `gtatools.lightmap_daynight` | Switch the display between the day and night maps. With nothing selected it switches the whole scene |
| Remove Lightmap | `gtatools.remove_lightmap` | Remove loaded lightmap |
| Generate | `gtatools.lightmap_generate` | Generate Lua code from object textures |
| Copy | `gtatools.lightmap_copy` | Copy result to clipboard |
| Clear | `gtatools.lightmap_clear` | Clear generated code |

**Output:** Lua table with texture names and lightmap references:
```lua
{
    textures = {
        "brick_wall",
        "roof_tile",
    },
    lightmap = "lightmaps/building01.png",
    models = {3500}
},
```

> **IMPORTANT:** UV2 is required — without a second UV layer, the lightmap will use UV1 coordinates and look incorrect.

The MTA lightmap script itself is available in the [Issues](../../issues) section of the repository.

### Pipeline

Render pipeline determines how the GTA SA engine processes the model:
- **None** — no pipeline. Suitable for most objects: furniture, fences, vegetation, characters
- **Building** (0x53F2009A) — Day/Night vertex colors. Required for buildings and map objects that have vertex colors — without this pipeline, day/night color transitions won't work in-game
- **Reflections** (0x53F20098) — window reflections. Only for window models that should reflect the environment. Windows must be a separate model from the building

> 💡 **Example:** a house `house01` needs day/night lighting → Object Properties → INU Tools: Model → Pipeline = **Day/Night**. Split the windows of this house into a separate mesh `house01_windows` → its Pipeline = **Reflections** so they reflect the street. The fence in front of the house `house01_fence` → Pipeline = **None**.

### Normals

The **Normals** toggle controls vertex normal export in DFF:
- **Enabled** — the model receives dynamic lighting from the GTA SA engine. Required for: characters, vehicles, weapons, interactive objects
- **Disabled** — the model is lit only by baked vertex colors. Used for: buildings, roads, map objects

> 💡 **Example:** CJ (character) — ☑ Normals (engine lights him based on sun and lamps). Map building with baked vertex colors — ☐ Normals (otherwise the engine overlays its own lighting and the visual breaks).

### Ariane Bridge

Live two-way link between the **Ariane** map editor and Blender — click a model in Ariane and it lands in Blender ready to edit; send it back with one button.

**Panel:** N → GTA Tools → **Export / Import** → **Ariane** tab. The shared **selection block** (Selected / DFF / LOD / COL) sits on top; the bridge controls are grouped below it.

| Control | What it does |
|---------|--------------|
| 📁 game folder | Path to the game — the bridge exchanges files via `<game>\ariane\bridge`. **Set this first**; the row is highlighted red until it is. |
| **Manual import** | Pull whatever Ariane has dropped into the inbox, once. |
| **⟳ Auto** | Toggle the watcher — auto-imports models as Ariane sends them. |
| **Export → Ariane** | Send the selected meshes back to Ariane (DFF + TXD, plus any attached **2DFX** empties — the mesh's direct children tagged `inu.type == '2DFX'` — so coronas/particles/lights ride along with the model). |
| **COL / LOD / Position** | Include collision / distant LOD / position in that export. |
| **Live sync** | Two-way live sync of position, selection and camera between Blender and Ariane (needs the ⟳ watcher on). |
| **More** ▸ | Rare/advanced: **Sync deletions** (deleting in Blender soft-deletes the instance in Ariane), **Create model** (register a brand-new model), **Clear cache**. |

**Workflow:**
1. Set the **game folder** (📁).
2. In Ariane, click **Export to Blender** on a model → it appears in Blender (turn on **⟳ Auto** to auto-import a whole selection as it streams in).
3. Edit / prelight the model in Blender.
4. **Export → Ariane** → it's rebuilt in the game.
5. For live editing, turn on **Live sync** — move or select in either app and the other follows.

---

## Asset Library

**Panel:** View3D → Sidebar (N) → **GTA Library** (its own N-panel tab, `bl_category = 'GTA Library'` — separate from the main *GTA Tools* tab)

Builds a Blender Asset Library from any IDE/IPL/IMG set — vanilla SA, a custom map, or a modded archive. Every prop becomes a mark-as-asset with a thumbnail you can drag straight into the scene from Blender's **Asset Browser**.

**Workflow:**
1. **Save your .blend** — required (the builder needs a working directory).
2. **Set GTA Root + Region** (in Setup panel) — points at `gta_sa.exe` folder; region narrows IDE/IPL parsing.
3. **Extract Resources** — unpacks DFF/TXD/COL caches once. Re-runs are skipped if cache already exists.
4. **Set Output folder** — empty folder where the library `.blend` and thumbnails will live.
5. Click **Build Asset Library**. Status text shows phase (cache scan → IDE read → preview gen → finalise).
6. **Edit → Preferences → File Paths → Asset Libraries → Add → your Output folder.**

After that, the Asset Browser shows every vanilla prop as a draggable thumbnail.

**Options:**
- *Preview size (px)* — thumbnail resolution (default 256, larger = slower but crisper).
- *Skip previews* — fastest mode, uses Blender placeholder icons. Good for quick iteration.
- *Skip existing .blend files* — incremental rebuild; only new models get processed.
- *Regenerate previews* — rerun the thumbnail pass without re-extracting.

> 💡 **First build is slow** (~15–30 min for the full vanilla map at 256 px; custom maps usually finish in a few minutes), subsequent rebuilds are minutes thanks to the «Skip existing .blend files» toggle.

---

## Advanced

> Originally introduced in 1.6.4 as experimental — the features below have stabilised through several release cycles. Edge-case bugs still surface occasionally; report any in [Issues](../../issues).

### Map Export

Unified one-click export of a scene district: DFF + COL + TXD + IDE + IPL into a single folder.

**Location:** View3D → Sidebar (N) → GTA Tools → *Map Export* panel → button **Export Map…**

**Workflow:**
1. Select the objects that form a district (DFF meshes, their LOD and COL siblings — detection by suffix/prefix).
2. Click *Export Map…*, pick a target folder.
3. Toggle what to emit (DFF / COL / TXD / IDE / IPL) and optionally *Binary IPL*.
4. Set *Base Name* (used for the shared TXD/IDE/IPL filenames) and *ID Pool Start* (first auto-assigned Model ID for DFFs with `model_id == 0`).

**What it does:**
- Groups objects by base name via `get_model_type()` — one DFF + optional LOD + zero-or-more COL meshes per group
- Auto-assigns Model IDs from `[id_pool_start, 19999]` to any DFF with `inu.model_id == 0`, writing them back into the object
- Exports per-group `*.dff` and `*.col` with existing exporters
- **TXD: one `.txd` per unique `inu.txd_name`** — DFFs with the same `txd_name` (e.g. `vegas01.txd` shared by 50 buildings) get bucketed into one shared TXD; DFFs with their own dedicated TXD (`cj.txd`) get their own file. Empty `txd_name` falls back to the model's own base name. Preserves the vanilla SA layout exactly when the scene was imported with IDE-populated `txd_name`s
- **COL: one `.col` library per unique `inu.col_name`** (when `col_library` toggle is on) — same pattern as TXD. `col_name` is auto-populated on Map Import to the source `.col` filename (`vegasN`, `LAs`, `LAn`, …). Round-trip rebuilds the original library file with all its original model entries. Empty `col_name` falls back to `txd_name` then to the model's own base name. Disabling `col_library` writes one `<base>.col` per individual DFF instead
- Writes one `{base_name}.ide` (objs section) and one `{base_name}.ipl` (inst section) covering the entire selection
- The operator runs as a **modal generator** with a window-manager timer: status bar shows current group / TXD bucket / IPL stage (`vegasN: TXD vegas02 (12 models)`), the viewport stays responsive, **ESC** cancels the export.

Source: [`tools/map_export.py`](INU_tools/tools/map_export.py).

#### Split modes (auto-split into districts)

The **Split** dropdown in the Map Export dialog sidebar controls how the selection is broken into separate districts at export time. Three modes:

| Mode | District naming | Use case |
|---|---|---|
| **No split** (default) | Single district named `base_name` | Hand-crafted small maps, explicit naming |
| **XY grid** | `<base>_x<cx>_y<cy>` per non-empty cell | Very large scenes (50 k+ DFFs), streaming-bound mods, co-op authoring by spatial region |
| **By collection** | Top-level collection name per bucket | Round-trip with Group-by-IPL import — `vegasn_stream0` in Blender → `vegasn_stream0.ipl` on output |

##### XY grid

Each DFF's world-origin `(x, y)` is divided by `cell_size` and floored to give a cell index `(cx, cy)`. LOD/COL siblings travel with their DFF; cell membership is decided by the DFF only. Each non-empty cell becomes a subdirectory named `<base>_x<cx>_y<cy>` under the chosen target folder (negative indices use `m` prefix, e.g. `district_xm3_y1`, so directory names never start with a dash). If splitting yields exactly one cell, the operator silently falls back to *No split* — leaving the toggle on for small scenes is harmless.

**Cell size guidance:** 256 m matches SA's vanilla streaming radius (a model in cell N becomes visible to the player roughly when they enter cell N±1). 128 m for very dense interiors; 512 m or 1024 m when most models are large terrain meshes (highways, rivers).

##### By collection

Bins DFFs by the name of their topmost user collection (the one directly under the scene root). The collection's name becomes the district name — so a `vegasn_stream0` collection in the outliner produces `vegasn_stream0.ipl`, `vegasn_stream0.ide`, `vegasn_stream0.col`, `vegasn_stream0.txd` inside `target_dir/vegasn_stream0/`. This is the natural round-trip for *Map Import → Group by IPL → edit → re-export*: the Map Import operator names the parent collections after the source IPL filenames, and re-exporting with the *By collection* split mode rebuilds the original district structure.

DFFs that live only in the scene root collection (or in no collection at all) land under a `unsorted/` bucket. If only one bucket has any DFFs the operator falls back to *No split* — so this mode is also safe to leave on for hand-curated small scenes.

Source: [`tools/map_export.py`](INU_tools/tools/map_export.py) → `compute_grid_cells`, `compute_collection_cells`, `format_cell_name`, `_build_top_collection_lookup`, `export_map(..., split_mode='GRID' | 'COLLECTION', cell_size=...)`.

### Binary IPL Write

Adds `bnry`-format output to the IPL exporter (read was already supported).

**Location:** File → Export → *Export IPL* (or the per-object IPL export operator) → checkbox **Binary (bnry)**.

**Format:** 76-byte header (`bnry` magic + 6 uint32 counts + 12 uint32 offsets), then packed `inst` entries (40 bytes each: 7 floats + 3 ints) and `cars` entries (48 bytes: 4 floats + 8 ints). Other sections (`cull`, `grge`, `zone`, …) are **not** written — Rockstar's binary IPLs only contain `inst` and `cars`, matching vanilla SA behaviour.

Source: [`core/ipl.py`](INU_tools/core/ipl.py) → `_write_binary_ipl`, `write_binary_ipl`, `write_ipl(..., binary=True)`.

### UV Animation `(2.1.0)`

GTA SA UV animation (chunks `0x2B` UV-anim dict + `0x135` material PLG, Kam's `UVanim_tool` layout) is authored on the **material** and previewed live in the viewport. v2.1.0 splits it into two modes — a constant **Scroll** and per-frame **Keyframes** authored on a Mapping node — plus a Spacebar live preview.

**Material panel:** Properties → Material → *GTA Material* → block **UV Animation**.

**Pipeline (common setup):**
1. Build a material with an **Image Texture** node feeding the BSDF *Base Color* (tileable texture for scrolls).
2. Enable ☑ **UV Animation**. This both flags the material for export and builds the in-shader preview rig (a `UVMap → Mapping → texture Vector` chain named `INU_UVAnim_*`).
3. Set **Animation Name** — the UVAnim name written to the DFF (defaults to the material name, max 31 chars).
4. Choose a mode below (**Scroll** / **Keyframes**), set its values, and press **Spacebar** in the 3D viewport to watch the texture move (use Material Preview or Rendered shading).

> Turning the toggle **off** removes the preview nodes and frees the texture Vector inputs — the mesh returns to static UVs. The preview only attaches to texture nodes whose Vector input is *unconnected*, so it never clobbers a custom mapping you already wired.

#### Scroll mode (constant speed)

**Material panel:** *GTA Material* → **UV Animation** → **Scroll**.

A constant linear scroll. The preview hangs drivers on the Mapping node's *Location* (`speed × frame / fps`) so the viewport scrolls at exactly the speed that exports.

**Settings:**
- **Speed U** — units/sec along U. `+` scrolls right, `−` left.
- **Speed V** — units/sec along V. `+` scrolls down, `−` up.
- **Duration** — cycle length in seconds.

On export this writes two keyframes: t=0 identity, and t=Duration with translation = `speed × duration`.

**Pick matching speed + duration:** for a seamless loop, `Speed × Duration` must be a **whole UV unit** (1, 2, 3…). A fractional product (e.g. 0.7) makes the texture jump on every cycle wrap.

| Effect | Speed U | Speed V | Duration | Shift per cycle |
|---|---|---|---|---|
| Slow conveyor (down) | 0 | 0.5 | 2.0 | 1 V unit |
| Fast belt left | −2.0 | 0 | 1.0 | 2 U units |
| Neon scrolling right | 1.0 | 0 | 4.0 | 4 U units |
| Water (diagonal) | 0.2 | 0.1 | 5.0 | 1 U + 0.5 V |

> 💡 **Example — scrolling water / conveyor:** make a tileable strip texture, enable **UV Animation** → **Scroll**, set **Speed V = 0.5**, **Duration = 2.0** (= 1 V unit per cycle, seamless). Press Spacebar — the surface flows in the viewport, and the same motion ships in the DFF.

#### Keyframe mode (author your own keys) `(2.1.0)`

**Material panel:** *GTA Material* → **UV Animation** → **Keyframes**.
**UV Editor → N → GTA Tools → UV Animation:** insert/clear keys here.

Instead of a fixed scroll you author keys directly on the preview Mapping node's **Location** (UV shift) and **Scale**. The exporter reads those keys back and writes them as real UVAnim frames — multiple steps, holds, jumps, scale pulses. No drivers are placed in this mode, so your keys are free to set.

In **Keyframe** mode the material panel just points you to the UV editor. Open the **UV Editor** (the GTA Tools panel has a button to split one out), press **N**, and open the **GTA Tools → UV Animation** panel. It shows:
- **Frame** — the current timeline frame.
- **UV Shift** — Mapping *Location* X/Y for this frame.
- **Scale** — Mapping *Scale* for this frame.
- **Insert Key** — keys both Location and Scale at the current frame (auto-creates the rig if missing).
- **Clear** — removes all UV-anim keys on this material.

**Pipeline:**
1. Material panel → enable **UV Animation**, choose **Keyframes**.
2. UV Editor → N → **GTA Tools → UV Animation**.
3. Go to a frame, set **UV Shift** / **Scale**, press **Insert Key** (panel hint: "Change Shift/Frame → Insert Key").
4. Advance the timeline, change the values, **Insert Key** again. Repeat per step.
5. **Spacebar** to preview; export when happy. The first key becomes t=0; frame times are converted to seconds by the scene FPS, and the last key sets the duration.

> Each key stores Location (UV translation) and Scale. If the panel says "Node not created (no texture?)", the material has no Image Texture with a free Vector input — add/connect one first. If you switch to Keyframe mode but leave **no** keys, export quietly falls back to Scroll (Speed U/V).

> 💡 **Example — 4-frame switching sign:** UV-map the sign face onto column 1 of a 4-column texture atlas. Frame 1: **UV Shift = (0, 0)** → **Insert Key**. Frame 13: **(0.25, 0)** → key. Frame 25: **(0.5, 0)** → key. Frame 37: **(0.75, 0)** → key. With constant interpolation you get a hard-switching 4-state sign; with linear, a sliding ticker.

#### Export & engine support

Any DFF export path (single DFF, Export All, Export to IMG) picks up the material's **UV Animation** flag automatically and writes the `0x2B` dict + `0x135` material PLG — no IDE flag needed. After replacing the DFF in an IMG, **Rebuild Archive** so the game drops its cached copy.

> ⚠️ **The #1 reason "the animation doesn't play in single-player" is night vertex colors.** If the model has night vertex colors (the **Night** flag in DFF Flags, or the **Day/Night** pipeline, which writes `extra_colors` into the DFF), retail GTA SA's engine **will not play** the UV animation: the colour shows up but nothing moves. This is confirmed in-game and documented in SA modding tutorials. **librw-based viewers** and **euryopa** ignore night vcols, so the animation runs there — which makes it look like an export/DFF bug when it isn't. **Fix:** clear the **Night** flag / drop the night layer on the animated model (you can keep the day prelight so the model isn't black). The addon flags this conflict for you — the **Night** row in DFF Flags turns red, and the pre-export **Validate Scene** sweep warns when a mesh has both a UV-anim material and night colors.

Two more conditions from the tutorials: the animated **material must not be shared** with other parts of the model (sharing the texture is fine); UV anim does **not** show on **skins or vehicles** in single-player — only on static map models (**Breakable** is compatible).

**Other engine notes:** beyond night vcols, the retail renderer is generally selective about UV anim. **librw-based viewers** and **MTA:SA with a shader** (see the bundled MTA shader workflow) animate it correctly. If motion still doesn't show and the model definitely has no night colors, verify by re-importing the DFF (the round-trip re-populates Scroll mode's **Speed U/V + Duration**) or by loading it in a librw viewer.

### Breakable Objects

Marks a mesh as destructible by the GTA SA physics engine via chunk `0x253F2FD`.

**Location:** Properties → Object → *GTA SA: IDE / IPL* panel → **Breakable** checkbox.

**What is written (fixed in 2.4.0):** after the magic word the engine (`BreakableStreamRead`) expects
a **full copy of the mesh** — vertices, UVs, colours, triangles, materials and texture names — not a
record of buffer sizes. The addon used to write a 32-byte chunk, which desynchronised the RW stream
so the model never loaded at all. The copy is now built from the geometry itself (one piece per
material), and the chunk has no force / offset / buffer fields — the engine format has none either,
so those fields were removed from the panel. The checkbox is all the exporter reads.

Source: [`core/dff.py`](INU_tools/core/dff.py) → `BreakableData`, `CHUNK_BREAKABLE`; [`ops/dff_export.py`](INU_tools/ops/dff_export.py) → breakable block inside `_process_mesh`.

### IFP Batch Import

Import a folder of `.ifp` files and stack every animation onto one NLA track of the active armature.

**Location:** View3D → Sidebar (N) → GTA Tools → *Anim* panel → button **Batch folder…**.

**Options:**
- **Name Prefix** — only apply animations whose name starts with this prefix (case-insensitive). Empty = all.
- **Mode: NLA Sequential** — stack clips on one NLA track with a gap between them
- **Mode: Actions Only** — just create the Actions, no NLA arrangement
- **Gap Between Clips** — frames between consecutive strips (NLA mode only)

**Use case:** scrub through 294 animations from `ped.ifp` consecutively without manually importing each one.

Source: [`ops/ifp_import.py`](INU_tools/ops/ifp_import.py) → `enumerate_animations`, `batch_apply_sequential`, `GTATOOLS_OT_ifp_batch_import`.

### GTA Material Panel

A condensed material UI that writes GTA-specific properties in one click.

**Location:** Properties → Material → *GTA Material* panel → **EFFECTS** tab.

**Quick presets** (four buttons under *Quick presets*):
- **Glass** — `xvehicleenv128` env map with framebuffer alpha (VEHICLE_GLASS)
- **Chrome** — strong env reflection + specular (CHROME)
- **Paint** — `xvehicleenv128` env + `vehiclespecdot64` specular + reflection blend (VEHICLE)
- **Reset** — clears every effect flag back to a plain textured material (GENERIC)

Each button one-shot-applies its effect configuration to `mat.inu.*` (round-trips through the DFF writer). The operator `gtatools.material_preset` also accepts the extra built-in ids `PED` / `ENV` / `DUAL` / `SPECULAR` via scripting/F3.

Plus the **Vehicle Color Slot** dropdown (Primary / Secondary / Third / Fourth / Headlights / Taillights) — writes the carcols magic tag into the material's base RGB.

Source: [`tools/gta_material_panel.py`](INU_tools/tools/gta_material_panel.py).

### Bitmaps Manager

Texture-management utilities: scan for missing files, resolve paths from a search folder, batch-copy used textures, find duplicates.

**Location:** View3D → Sidebar (N) → GTA Tools → *Bitmaps Manager* panel.

**Operators:**
- **Scan Missing Textures** — walks every material, lists images whose `filepath` can't be found. Count is stored on the scene and shown in the panel.
- **Resolve From Folder…** — walks the chosen folder recursively, matches by basename (with or without extension), patches `image.filepath` and reloads.
- **Copy Used To Folder…** — copies every texture used by at least one material into the target folder. Optional **Subfolder per TXD** creates `target/{txd_name}/texture.png` by walking mesh objects and reading `obj.inu.txd_name`. If a material is used across multiple TXDs, the texture lands in each one.
- **Find Duplicates** — MD5-hashes every reachable texture file and reports groups of identical files to the System Console.

Source: [`tools/bitmaps_manager.py`](INU_tools/tools/bitmaps_manager.py).

### CST IO

Text serialisation of COL collision data, compatible in spirit with Steve's COL Editor. Alternative to the binary `.col` format for hand-editing or diffing.

**Where:** CST is handled entirely through the **CST** checkbox in the Import / Export dialogs (Export All writes `<name>.cst` next to the `.col`), and by **drag & dropping** a `.cst` file into the viewport to import it. There are no standalone CST operators.

**Format:** line-based, one directive per structure. Multiple MODEL blocks per file supported.
```
MODEL my_col
ID 1234
VERSION 3
BOUNDS 0 0 0 5.0 -2 -2 -2 2 2 2
SPHERE 0 0 1 0.5  0 0 0 0
BOX -1 -1 0 1 1 2  0 0 0 0
VERTEX 1.0 2.0 0.0
FACE 0 1 2  0 0 0 0
SHADOW_VERTEX 0 0 0
SHADOW_FACE 0 1 2  0 0 0 0
END
```

Each `SPHERE` / `BOX` / `FACE` ends with 4 surface tokens: `material flags brightness light`. Anything after `#` is a comment.

Source: [`core/cst.py`](INU_tools/core/cst.py), [`ops/cst_import.py`](INU_tools/ops/cst_import.py), [`ops/cst_export.py`](INU_tools/ops/cst_export.py).

### Vehicle Scale Helper

Uniformly rescale a whole vehicle hierarchy (Empty root + mesh + dummy children) preserving the structure for DFF export.

**Location:** View3D → Sidebar (N) → GTA Tools → *Vehicles* panel → button **Vehicle scale…** (also exposed as the operator `gtatools.vehicle_scale` for scripting).

**Options:**
- **Factor** — uniform scale multiplier
- **Dummies Only** — if enabled, only move the dummy empties; mesh vertices stay the size they were

**What it does:** walks the hierarchy DFS, multiplies every `obj.location` by the factor, clears `matrix_parent_inverse` to identity, applies `Matrix.Scale(factor)` to mesh data (copies shared meshes first) and Armature data, resets `scale` to `(1,1,1)` on every object. Empty display sizes scale too.

Source: [`tools/vehicle_scale.py`](INU_tools/tools/vehicle_scale.py).

### Vehicle Damage Variants

Manage paired `_ok` / `_dam` body atomics for vehicle DFFs. The GTA SA engine swaps the visible mesh between the two variants when a panel takes damage — naming convention is the only contract: an atomic ending in `_ok` and one ending in `_dam` (with the same prefix) form a damage pair, e.g. `bonnet_ok` ↔ `bonnet_dam`, `door_lf_ok` ↔ `door_lf_dam`.

**Location:** View3D → Sidebar (N) → GTA Tools → *Vehicles* panel → block **Damage variants**.

**Operators:**

| Button | What it does |
|---|---|
| **Create _dam** (`gtatools.vehicle_add_damage_variant`) | Duplicates the active mesh's data into a new object named `<base>_dam`, parented to the same Empty as the source. If the source has no `_ok` / `_dam` suffix, it is auto-renamed to `<name>_ok` first. The new `_dam` is `hide_viewport=True` so the user previews the OK state by default — DFF export walks the full hierarchy regardless of viewport flag, so the variant still ships into the `.dff`. |
| **Show OK / Dam / Both** (`gtatools.vehicle_show_damage`) | Toggles `hide_viewport` on every `_ok` and `_dam` mesh in the active object's hierarchy (or the whole scene if no active object). `OK` shows `_ok`, hides `_dam`. `Dam` shows `_dam`, hides `_ok`. `Both` shows everything (useful for debugging). Affects viewport only — does not change DFF export. |
| **Check pairs** (`gtatools.vehicle_pair_report`) | Walks the active hierarchy and prints to the System Console: paired `_ok+_dam` meshes, orphan `_ok` (no matching `_dam`), orphan `_dam` (no matching `_ok`). Reports a summary in the status bar; if any orphans exist the level is `WARNING`. Orphan parts won't have a damaged variant in-game (the engine looks up the pair at load time). |

**Workflow tutorial — bonnet damage:**

1. Model the OK bonnet, name the mesh `bonnet_ok`. Place it under `bonnet_dummy` empty for the door-pivot transform.
2. Select `bonnet_ok` → click **Create _dam**. A new mesh `bonnet_dam` appears with the same shape, hidden in viewport.
3. Click **Show Dam** → the OK mesh hides, damaged mesh becomes visible. Edit the mesh (push verts inward, add dents).
4. **Show OK** to compare quickly. **Show Both** if you want to see both meshes overlaid (handy for keeping silhouettes consistent).
5. Run **Check pairs** — should report `1 paired, 0 orphans`. Add `door_lf_ok`/`_dam`, `boot_ok`/`_dam`, repeat.
6. Export the DFF normally — both variants ride along into the `.dff`. In game the engine swaps them on damage based on per-component health.

**Notes:**
- The hide-on-create behaviour applies only to viewport (`hide_viewport`). Render flag stays untouched, so collection-driven exporters (Map Export, Export to IMG) don't lose the variant.
- Use **Show OK** before exporting if you need a clean DFF preview screenshot — the `_dam` meshes are mostly cosmetic eyesores at full visibility.
- `wheel_*` and `*_dummy` empties have no damage variant in vanilla SA — only painted body parts (chassis, doors, bonnet, bumpers, windshield, mudguards, boot) ship with `_ok` / `_dam` pairs.

Source: [`tools/vehicle_scale.py`](INU_tools/tools/vehicle_scale.py) → `_strip_damage_suffix`, `find_damage_pairs`, `GTATOOLS_OT_vehicle_add_damage_variant`, `GTATOOLS_OT_vehicle_show_damage`, `GTATOOLS_OT_vehicle_pair_report`.

### Train Station Markers

Visible Empty spheres on train-track curves at every station point, so stations are readable in Object mode without entering Edit mode.

**Location:** Operator `gtatools.refresh_station_markers` (active track curve with `path_type == 'track'`).

**What it does:** wipes old markers parented to the track, reads `station_indices` (set by the existing `gtatools.mark_station`), places a sphere Empty at every station point with `empty_display_size = 3.0`, parents it to the track with identity parent-inverse so the local position maps 1:1 to the curve point.

Source: [`ops/ifp_import.py`](INU_tools/ops/ifp_import.py) → `_refresh_station_markers`, `GTATOOLS_OT_refresh_station_markers`.

### Roadblocks & Traffic Lights

Per-node flag editor for paths.ipl curves: roadblock bit + traffic-light kind.

**Location:** Edit Curve mode on a `path_type == 'path_ipl'` curve → operator `gtatools.path_node_flag` with these actions:
- **Toggle Roadblock** — flip bit 12 (cops barrier) on every selected point
- **Clear / Normal / Rail / Bus Traffic Light** — set bits 8–11 to 0 / 1 / 2 / 3

Works on filtered spline points, but writes into the original IDProp slots (which include empty-padding nodes from the 12-per-group IPL format).

Source: [`core/paths.py`](INU_tools/core/paths.py) → flag constants + `decode_node_flags` / `encode_node_flags`; [`ops/ifp_import.py`](INU_tools/ops/ifp_import.py) → `GTATOOLS_OT_path_node_flag`.

### FLA4 Path Format

Extended `nodes*.dat` format used by Fastman Limit Adjuster 4. Adds 12 bytes per path node (spawn probability, speed limit in km/h, lane count override) on top of the vanilla 28-byte structure, for a total of 40 bytes per node.

**Detection:** a file is treated as FLA4 when it starts with the ASCII magic `FLA4`. Counts + offsets layout is otherwise identical to vanilla.

**Location:** File → Export → *Export Path Nodes* → checkbox **FLA4 Format**. Import auto-detects.

Source: [`core/paths.py`](INU_tools/core/paths.py) → `FLA4_MAGIC`, `FLA4_PATH_NODE_SIZE`, FLA4 branches in `read_nodes` / `write_nodes`; [`ops/path_export.py`](INU_tools/ops/path_export.py) → `export_nodes(..., fla4=True)`.

---

## Technical Reference

### Project Structure

```
INU_tools/
├── __init__.py                  # Addon entry: bl_info, registration, top-level props (~4400 lines)
├── blender_manifest.toml        # extensions.blender.org manifest (id, version, permissions)
├── scene_settings.py            # INUSceneSettings PropertyGroup (240 fields)
│
├── core/                        # Pure-Python parsers (no Blender dependency, unit-testable)
│   ├── dff.py                   # RenderWare DFF reader/writer (Clump, Frame, Geometry, Skin/2DFX/BinMesh PLG)
│   ├── col.py                   # COL1/2/3/4 collision format
│   ├── txd.py                   # TXD texture dictionary (DXT1/3/5, RASTER_*, PAL8)
│   ├── txd_mobile.py            # Mobile (iOS/Android) 4-file TXD container detection
│   ├── dxt.py                   # Pure-numpy DXT1/BC3 encoder (no external binaries)
│   ├── dxt_gpu.py               # Optional GPU compute-shader DXT path
│   ├── ide.py                   # IDE definition file I/O
│   ├── ide_flag_translate.py    # Per-game IDE flag bit translation (III/VC/SA)
│   ├── ipl.py                   # IPL instance file I/O (text + binary)
│   ├── ifp.py                   # IFP animation format (ANP3 / ANPK / ANP2)
│   ├── img.py                   # IMG v2 / v1 archive (read/write/extract/replace)
│   ├── paths.py                 # paths.ipl + tracks.dat + nodes*.dat
│   ├── water.py                 # water.dat (vertex quads + types)
│   ├── gta_dat.py               # gta.dat / gta_int.dat / default.dat parser
│   ├── fxp.py                   # effects.fxp parser/writer (FXSystem/FXEmitter/FXCurve)
│   ├── cst.py                   # CST text COL format (Steve's editor)
│   ├── rwbinary.py              # Low-level RenderWare binary chunk helpers
│   ├── validate.py              # Pre-export sanity checks (quaternions, paintjob pairs, …)
│   ├── file_lint.py             # On-disk DFF/COL/TXD crash-pattern linter
│   ├── lint_profile.py          # STANDARD / FLA / STRICT / LENIENT profiles
│   ├── map_lint.py              # Cross-file IDE↔IPL validator
│   ├── game_versions.py         # III / VC / SA detection by file signatures
│   ├── surface_translate.py     # COL surface ID translation tables (per-game)
│   ├── ped_mask_translate.py    # Ped mask bit mapping (III/VC/SA)
│   ├── texture_index.py         # Fast IMG/TXD texture inventory
│   ├── bitmap_diff.py           # Find orphaned images/materials in .blend
│   └── vc_layers.py             # Vertex-color layers — naming + composite math
│
├── ops/                         # Blender operators (51 modules, ~140 operators total)
│   ├── floater/                 # GPU-rendered free-floating windows package
│   │   ├── base.py              # Floater base class + modal + draw handler
│   │   ├── theme.py             # Palette/radius/sizes pulled from current Blender theme
│   │   ├── gpu_shaders.py       # SDF rounded-rect + icon shaders
│   │   ├── text_atlas.py        # BLF glyph atlas via baked texture
│   │   ├── widgets.py           # _draw_button / toggle / slider / dropdown / box
│   │   ├── layout_solver.py     # Mini UILayout port (Column/Row/Box solver)
│   │   ├── info.py              # Info floater
│   │   ├── ie.py                # Import/Export floater
│   │   ├── validation.py        # Validation floater
│   │   ├── lighting.py          # Lighting floater
│   │   └── iii.py               # IDE/IPL/IMG floater
│   ├── dff_import.py, dff_export.py       # DFF ↔ Blender mesh (rigged + 2DFX + multi-game)
│   ├── col_import.py, col_export.py       # COL ↔ Blender (mesh + sphere/box empties)
│   ├── cst_import.py, cst_export.py       # CST text COL format
│   ├── txd_import.py, txd_export.py       # TXD ↔ Blender Images
│   ├── ide_import.py, ide_export.py       # IDE ↔ object props
│   ├── ipl_import.py, ipl_export.py       # IPL ↔ object placement
│   ├── ipl_sections.py                    # IPL Cull/Garage/Enex/Pickup/Cars/Auzo/Jump/Zone/Occl
│   ├── ifp_import.py, ifp_export.py       # IFP ↔ Blender Actions
│   ├── ifp_ops.py                         # IFP batch / range-apply
│   ├── img_ops.py                         # IMG archive ops (extract / rebuild / scan)
│   ├── inu_export.py                      # File → Export → INU Export (unified dialog)
│   ├── map_ops.py                         # Import Map + map region scan + bbox
│   ├── map_analyzer_ops.py                # Cross-file Map Analyzer (Game Validator)
│   ├── id_manager_ops.py                  # ID Manager (model_id allocation, FLA range)
│   ├── ide_ipl.py                         # IDE/IPL helper ops
│   ├── effects_ops.py                     # 2DFX presets + particle effects + attach/detach
│   ├── particle_sim.py                    # 30 Hz particle viewport simulator
│   ├── fx_preview.py                      # 2DFX static preview (billboards / corona / shadow)
│   ├── animobj_ops.py                     # Animated Map Object (empty-rig flow)
│   ├── ik_rig.py                          # Skinned ped IK rig + FK↔IK bake
│   ├── frame_hierarchy.py                 # Frame Hierarchy Editor (DFF frame tree)
│   ├── vehicle.py                         # Vehicle helpers (damage variants, _ok/_dam)
│   ├── paintjob_ops.py                    # Vehicle paintjob pairs
│   ├── light_ops.py                       # Prelight bake + preview + scatter (45 ops)
│   ├── prelight_preset_ops.py             # Prelight preset save/load/apply
│   ├── texture_ops.py                     # Material texture management
│   ├── texture_browser_ops.py             # Texture Browser UIList
│   ├── col_surface_ops.py                 # COL surface assignment + day/night light
│   ├── water_import.py, water_export.py   # water.dat ↔ mesh
│   ├── water_geometry_ops.py              # Water quad creation helpers
│   ├── path_import.py, path_export.py     # paths.ipl + nodes*.dat ↔ Blender curves
│   ├── path_curves.py                     # Path curve helpers (segment ops)
│   ├── world_ops.py                       # World-space operators (track export, toggle viz)
│   ├── radar_ops.py                       # X Radar Maker (minimap tiles)
│   ├── build_library_ops.py               # Asset Library builder operator
│   ├── object_utils_ops.py                # Generic object utilities (reset xform, hide by type)
│   ├── check.py                           # Check panel ops (vertex / n-gon / materials)
│   ├── validate_scene.py                  # Pre-export validation + auto-fix ops
│   ├── file_scanner_ops.py                # On-disk DFF/COL/TXD lint operator
│   ├── graph_keys_ops.py                  # Graph editor key utilities
│   ├── weight_paint_ops.py                # Weight paint helpers (start/apply/cancel merge)
│   ├── onboarding_ops.py                  # First-launch onboarding flow
│   └── viewport_floater.py                # Floater lifecycle host (register/cleanup/restore)
│
├── tools/                       # Utility modules (Blender-aware helpers)
│   ├── txd_export.py            # TXD compile pipeline (CPU/GPU/parallel)
│   ├── prelight.py              # Vertex-color bake + scatter + smooth + post-FX
│   ├── col_light.py             # COL light preview + bake
│   ├── uv_tools.py              # UV grid tools (panel in UV Editor)
│   ├── model_utils.py           # DFF/LOD/COL detection by suffix, MapGroup
│   ├── map_export.py            # Unified scene → IPL+IDE+DFF+COL+TXD pipeline
│   ├── build_library.py         # Asset Library builder (worker-side)
│   ├── compat.py                # Blender version-feature flags + shader-node-mix shim
│   ├── user_data.py             # bpy.utils.extension_path_user helper
│   ├── profiles.py              # N-sidebar layout profiles (JSON)
│   ├── profiler.py              # Lightweight performance probe
│   ├── bitmaps_manager.py       # Bitmap browser / unused cleanup
│   ├── gta_material_panel.py    # GTA Material panel (SURFACE/EFFECTS/PIPELINE)
│   ├── vehicle_scale.py         # Vehicle proportion helper
│   └── vc_layers.py             # Vertex Color Layers (Blender-side PropertyGroup + UIList)
│
├── ui/                          # UI infrastructure (panels + layout system)
│   ├── panels.py                # All N-sidebar / Properties panels
│   ├── registry.py              # Zone-based panel order (single source of truth)
│   ├── layout_rules.py          # Blender-native layout metrics (widget_unit, box_pad, …)
│   └── library_panel.py         # Asset Library builder panel
│
├── data/
│   ├── surface_materials.py     # 179 GTA SA surface types
│   ├── material_presets.py      # Material preset bundles (used by SURFACE/EFFECTS tabs)
│   ├── id_manager.py            # Model ID allocation state
│   ├── icon_previews.py         # bpy.utils.previews collection for PNG icons
│   ├── icons/                   # native PNG bake of Blender icons (floaters; see icons/native/NOTICE.txt)
│   ├── fonts/                   # Inter font atlas + OFL.txt (license) for floater text
│   │                            # (FX effect textures are NOT bundled — loaded from the player's particle.txd)
│   ├── presets/                 # Bundled prelight + paintjob JSON presets
│   └── models/                  # Bundled DFFs (Army.dff, Admiral.dff for Shift+A menu)
│
└── locale/
    ├── __init__.py              # T() function + active language picker
    ├── eng.py                   # English translations (2049 keys)
    └── spa.py                   # Spanish translations (2370 keys)
```

### Core Modules

#### dff.py — RenderWare DFF Format
Reads/writes RenderWare binary streams. Supports: Clump, Frame List, Geometry List, Geometry (vertices, normals, UV, vertex colors), Material List, Material, Texture, Atomic, **Skin PLG** (bone weights), **2DFX PLG** (Light / Particle / Ped Attractor / Sun Glare entries), **BinMesh PLG**, **MatFX PLG** (env map / bump map / reflections), **UV Animation Dictionary** (chunk 0x2B), **Native Data PLG** (mobile geometry), **HAnim PLG** (bone hierarchy), **breakable objects** (chunk 0x253F2FD). Round-trip preserves non-Clump first chunks (e.g. UV anim dict).

#### col.py — Collision Format
Supports COL1, COL2, COL3 (GTA SA default), COL4. Reads/writes: mesh faces, vertices, face groups, **spheres**, **boxes** (with `display_type='CUBE'` empties), surface properties (material, flags, brightness, day/night light nibbles).

#### txd.py + dxt.py — Texture Dictionary
Pure-numpy DXT1/BC3 encoder/decoder (~7× faster than the old cluster-fit path). Handles DXT1, DXT3, DXT5, RASTER_8888, RASTER_888 (32-bit BGRX), RASTER_565, RASTER_1555, RASTER_4444, PAL8 (paletted). Platform: D3D8/D3D9. Optional `dxt_gpu.py` for compute-shader path.

#### txd_mobile.py — Mobile TXD container
Detects the 4-file mobile container (`.pvr` / `.etc` / `.dxt` + `.txt` / `.toc` / `.dat` / `.tmb`). Pixel decode delegated to TxdGen (no in-tree PVRTC/ETC1 codec).

#### ide.py + ide_flag_translate.py — Item Definition
All sections: objs (static), tobj (timed), anim (animated), cars (vehicles), peds (pedestrians), weap (weapons), hier (hierarchy), txdp (TXD parents). Per-game flag bit translation in `ide_flag_translate.py` — same logical flag (e.g. "drawlast") has different bit positions in III/VC/SA.

#### ipl.py — Item Placement
All sections: inst (instances), cull (cull zones), grge (garages), enex (entry/exit), pick (pickups), cars (parked vehicles), auzo (audio zones), jump (stunt jumps), occl (occlusion), tcyc (time cycle), zone (map zones). Supports both **text** and **binary** IPL (`bnry` header). FLA `real_interior` (12-th column) optional.

#### img.py — IMG Archive
v2 (GTA SA) and v1 (GTA III/VC). `ImgReader` context manager for fast sequential reads. Functions: `read_directory`, `extract_file`, `replace_or_add`, `remove_file`, `create_img`. Sector-aligned (2048 bytes).

#### ifp.py — Animation Format
Three sub-formats: **ANP3** (SA), **ANPK** (III/VC), **ANP2** (custom). `source_format` is preserved on round-trip. KF time is in **seconds** canonically; importer converts.

#### paths.py — Path Data
- `paths.ipl` — vehicle/pedestrian path text format (pre-compiled)
- `tracks.dat` — train tracks
- `nodes*.dat` — compiled binary path nodes (vehicle / ped / navi) with FLA4 extension support and structured `navi_links` / `link_lengths` / `path_intersections` post-link tail

#### fxp.py — Particle Effects File
Pure-text effects.fxp parser. Dataclass hierarchy: `FXFile → FXSystem → FXEmitter → FXInfoBlock`. Curves stored as `FXCurve` with piecewise-linear `sample(t)`. CRLF output preserved. `load_cached(path)` with mtime-based invalidation.

#### water.py — water.dat
Quad definitions with per-vertex flow speed (X/Y/Z) and water type (0–3). MTA round-trip compatible.

#### gta_dat.py — Game Data
Parses `gta.dat`, `gta_int.dat`, `default.dat`. Extracts IDE/IPL/IMG paths in declaration order. `extract_regions()` returns folder names from MAPS directory for dynamic region filtering.

#### game_versions.py — Multi-game detection
Detects III / VC / SA by file content signatures (RW version, IPL header markers, IDE column counts). `game_of_scene(scene)` returns the active game; `game_of_file(path)` for stand-alone detection.

#### file_lint.py + lint_profile.py + map_lint.py — Linting
- `file_lint.py` — on-disk DFF/COL/TXD scanner; emits `LintIssue(code, severity, file, message)` records.
- `lint_profile.py` — STANDARD / FLA / STRICT / LENIENT profiles override default thresholds + post-filter issues by code/severity.
- `map_lint.py` — cross-file IDE↔IPL validator (orphan references, duplicate IDs, IMG cross-verify).

#### vc_layers.py — Vertex Color Layers
Pure-logic naming and composite math (Photoshop-style layers). `recompose_stack(mesh, scope)` blends `VCL_<scope>_*` layers into `Day` / `Night` base attributes.

#### rwbinary.py — RenderWare Chunk Helpers
Low-level utilities used by dff/txd/col writers: chunk header pack/unpack, alignment, RW version encoding.

#### validate.py — Pre-export Sanity Checks
Quaternion normalisation, paintjob `_ok ↔ _dam` pair checks, UV-anim × night-vcol conflict (night vcols disable UV animation in retail SA), duplicate model_id detection.

### File Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| DFF | .dff | RenderWare model (geometry, materials, UV, vertex colors, 2DFX, skin) |
| COL | .col | Collision (COL1/2/3/4) mesh + sphere/box + surface props |
| CST | .cst | Steve's COL Editor text format (twin of COL) |
| TXD | .txd | Texture archive (DXT compressed, D3D8/D3D9) |
| TXD mobile | (4 files) | `<name>.<fmt>.txt/.toc/.dat/.tmb` container (PVRTC/ETC1) |
| IDE | .ide | Object definitions (text, comma-separated) |
| IPL | .ipl | Object placement (text or binary with `bnry` header) |
| IFP | .ifp | Skeletal animations (ANP3/ANPK/ANP2) |
| IMG | .img | VER2 (SA) or VER1 (III/VC) archive |
| FXP | .fxp | `effects.fxp` particle systems (text despite extension) |
| water.dat | .dat | Water quad definitions |
| paths.ipl | .ipl | Vehicle / pedestrian path definitions |
| tracks.dat | .dat | Train track definitions |
| NODES*.dat | .dat | Compiled binary path nodes |
| gta.dat | .dat | Master file listing IDE/IPL/IMG to load |

### Object Properties (INUObjectProps)

`obj.inu` — 102 fields. Grouped by feature:

**Core type & ID** (8) — `type` (OBJ/COL/SHA/2DFX/NON), `model_id`, `txd_name`, `col_name`, `lod_object` (round-trip), `draw_distance`, `lod_distance`, `interior_id`

**IDE flags** (15) — per-flag booleans translated to per-game bits via `ide_flag_translate.py`: `flag_is_road`, `flag_draw_last`, `flag_additive`, `flag_no_zbuffer`, `flag_no_shadows`, `flag_no_backface`, `flag_damagable`, `flag_breakable`, `flag_is_tree`, `flag_is_palm`, `flag_glass_1`, `flag_glass_2`, `flag_garage_door`, `flag_no_flyer_col`, `flag_is_tag`

**DFF export flags** (10) — `light`, `modulate_color`, `set_material_alpha`, `light_beam_asi`, `export_normals`, `export_binsplit`, `uv_map1`, `uv_map2`, `day_cols`, `night_cols`

**Pipeline** (2) — `pipeline` (NONE / 0x53F2009A Vehicle / 0x53F20098 D/N / 0x53F2009C Building / PED), `real_interior` (FLA optional)

**Breakable Object** (5) — `breakable_enable`, `breakable_vertices_count`, `breakable_faces_count`, `breakable_materials_count`, `breakable_position_index`

**2DFX Light** (15) — `effect_2dfx`, `color_2dfx`, `preset_2dfx`, `corona_size_2dfx`, `shadow_size_2dfx`, `corona_tex_2dfx` (34 textures), `shadow_tex_2dfx`, `show_mode_2dfx`, `flare_type_2dfx`, plus custom props for `corona_far_clip`, `pointlight_range`, `shadow_z_distance`, `flags1/2`, `look_direction`

**2DFX Particle** (28) — see [Particle Effects](#particle-effects-effectsfxp) — `particle_effect_2dfx`, `particle_emitter_index`, `particle_texture`, `particle_src_blend`/`dst_blend`, `particle_color_start/mid/end`, `particle_size_start/end`, `particle_life`/`life_bias`, `particle_rate`, `particle_speed`/`speed_bias`, `particle_direction`, `particle_angle_min`/`max`, `particle_volume`/`volume_radius`/`volume_min`, `particle_force`, `particle_friction`, `particle_wind`, `particle_noise`, `particle_jitter`, `particle_rotation_min`/`max`, `particle_rotspeed_min`/`max`, `particle_ground_bounce`/`speedmult`, `particle_sys_length`/`playmode`/`culldist`, `particle_curve_name`, `particle_curve_keys` (CollectionProperty), `particle_curve_key_index`

**Vehicle damage** (3) — `damage_kind` (none/ok/dam), `damage_pair_name`, `damage_role`

**Prelight V-offset** (3) — `gtatools_v_offset_day`, `gtatools_v_offset_night`, `gtatools_v_offset_auto`

### Material Properties (INUMaterialProps)

`mat.inu` — 38 fields. Grouped by tab:

**SURFACE** (7) — `col_mat_index` (0-178), `col_flags`, `col_brightness`, `col_light` (legacy raw byte), `col_day_light` (0-15), `col_night_light` (0-15), `col_pipeline`

**EFFECTS — Env Map** (3) — `export_env_map`, `env_map_tex`, `env_map_coef`

**EFFECTS — Bump Map** (3) — `export_bump_map`, `bump_map_tex`, `bump_map_coef`

**EFFECTS — Specular** (3) — `export_specular`, `specular_level`, `specular_texture`

**EFFECTS — Reflection** (5) — `export_reflection`, `reflection_scale_x/y`, `reflection_offset_x/y`, `reflection_intensity`

**EFFECTS — Dual Texture** (4) — `export_dual_tex`, `dual_tex_src_blend` (11 options), `dual_tex_dst_blend` (11 options), `dual_tex_texture`

**EFFECTS — UV Animation** (2) — `export_animation`, `animation_name`

**PIPELINE & misc** (11) — `ambient`, `material_tab` (active tab persisted per-material), Modulate Color params (`modulate_mix`, `modulate_contrast`, `modulate_gamma`), etc.

### Scene Properties (INUSceneSettings)

Accessed via `scene.inu_settings`. 240 fields registered as a single `PointerProperty` (one slot on `bpy.types.Scene`). Grouped by feature area:

**Paths** — `gtatools_game_root`, `gtatools_ide_path`, `gtatools_ipl_path`, `gtatools_img_path`, `gtatools_texture_path1/2`, `gtatools_map_region`

**Multi-game** — `gtatools_game_version` (III/VC/SA), `gtatools_platform` (PC/MOBILE)

**Import options** — `gtatools_img_skip_lod`, `gtatools_img_load_txd`, `gtatools_map_load_col`, `gtatools_txd_auto_import`, `gtatools_dxt_backend` (numpy / numpy_fast / gpu)

**Export options** — `gtatools_img_export_dff/col/txd`, `gtatools_export_all_dff/col/lod/txd`, `gtatools_export_pipeline`, `gtatools_suffix_dff/lod/col`

**Prelight** — `gtatools_bake_ambient/intensity/gamma`, `gtatools_bake_shadows`, `gtatools_modulate_mode`, `gtatools_modulate_mix/contrast/gamma`, `gtatools_prelight_preset`

**2DFX & Particles** — `gtatools_particle_sim` (live simulation toggle), `gtatools_show_dff_flags`, `gtatools_show_suffix_settings`

**Water** — `gtatools_water_flag` (0-3), `gtatools_water_speed_x/y/z`

**UV Editor** — `gtatools_uv_grid_cols/rows`, `gtatools_uv_lock_islands`, `gtatools_uv_align_position`

**Validation / Lint** — `gtatools_lint_profile` (STANDARD/FLA/STRICT/LENIENT), `gtatools_validate_*` collections (issues list)

**Floater state** — per-floater `inu_floater_*_visible`/`_collapsed`/`_locked`/`_workspace`/`_x`/`_y` (six props × 5 floaters = 30 fields)

**ID Manager** — `gtatools_id_pool_*`, `gtatools_id_manager_*` (preset state, conflict detection)

**Map analyzer / texture browser** — input sources (IDE/IPL/IMG lists), result UILists, filters

> Full list: see `INU_tools/scene_settings.py:405` (class `INUSceneSettings`). Property bag is intentionally consolidated into one PropertyGroup — extensions.blender.org review requirement (no per-prop `bpy.types.Scene.x = …` direct attachments).

