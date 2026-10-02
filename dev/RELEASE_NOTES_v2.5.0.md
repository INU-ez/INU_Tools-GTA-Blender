# v2.5.0: Editable Compiled NODES, safer IMG and IDE/IPL export, GTA III/VC path fixes

Feature and bugfix update since v2.4.1. Extend existing SA roads and pedestrian paths directly in Blender, with matching links and vehicle navigation on export. This release also includes the Blender / 3ds Max parity fixes and corrections to LOD placement, collision export, resource detection and model IDs.

## ✨ Added

- **Edit Compiled NODES with ordinary mesh tools.** Import `nodes0.dat` … `nodes63.dat`, use Extrude to extend a path or Subdivide to insert a point, and connect vertices with edges. Export rebuilds the graph and writes the corresponding vehicle navigation, link lengths and intersection data. New vehicle branches get one lane each way; an unambiguous subdivision keeps the original lane counts and direction.
- **Stable identities for imported NODES vertices.** Moving, duplicating and deleting points keeps the surviving nodes' properties attached to the correct vertices. Deleting a node removes incoming references; when old IDs change, export requires all 64 regions and updates neighbouring files too.
- **Export NODES directly from Edit Mode**, including multi-object Edit Mode. Selecting one imported category includes its vehicle, pedestrian and navigation companions from the same import. Empty imported regions remain available for selection and export.
- **Rebuild IMG** button with confirmation. Export to IMG also writes a report beside the `.blend` file.
- **ID Manager game reservations** stored separately in `<preset>.game`. Loading IDs from the game reads the startup files for SA, Vice City and III. Freeing a game ID asks for confirmation and makes it available for assignment.
- **Warning when adding a model that already exists in another IDE.** The message names the other file; its existing row is preserved.
- **Pedestrian Crossing controls for III/VC paths**, plus VC Roadblock controls using the actual flags field. Unsupported combinations are reported before editing.

## 🔧 Changed

- **IMG export follows each resource's archive.** Models and LODs use their own linked archives, shared LODs reach the archives of their related models, TXDs merge with existing dictionaries, and collision models go into their COL libraries. Missing or unwritable resource targets prevent the corresponding IDE/IPL rows from being written.
- **Remove from IMG checks shared resources.** It uses the model's archive and removes a TXD only when no loaded IDE still needs it. COL libraries are handled as libraries; the dialog lists the planned removals first.
- **Collection export respects collision ownership.** A COL in another collection is left there with a warning. Selection export keeps the existing related-COL lookup.
- **Path data follows the target game.** VC uses its native columns, flags, spawn rate and coordinate scale; III paths are read from IDE sections. SA reports that the IPL `path` section is ignored by the game. Traffic-light type is identified from game objects and is no longer presented as a writable IPL field.
- **Map analysis includes modloader files, TEXDICTION and CDIMAGE resources.** Non-streaming cutscene/script archives are excluded from automatic searches, and DFF/TXD availability is checked by the correct extension.
- New controls, warnings and messages are translated into **English and Spanish**.

## 🐛 Fixed

- **Enabling or updating the extension could fail with `_RestrictData`**, leaving classes registered and causing an `INUSceneSettings already registered` error on the next attempt. Existing path curves now initialize after registration, and disabling the extension cancels the pending initialization.
- **Compiled NODES edits previously ignored new mesh edges and reused properties by vertex index**, producing incorrect connections after topology changes. Export now rebuilds NodeLinks and NaviNode/NaviLinks together and checks addresses, capacity limits and compressed coordinates before writing.
- **NODES export from Edit Mode could report missing vertex identities.** It now reads the live editable mesh data, including when upgrading an unchanged legacy scene.
- **Empty NODES regions and zero IMG sector padding** now parse correctly instead of being treated as an unknown binary tail.
- **SA LOD placement keeps its offset and relative rotation** when the main model moves, rotates or is written into another IPL. LOD draw distance is honoured across IDE, IMG, map and Ariane export, with a fallback for older scenes.
- **Deleting base IPL rows referenced by streamed IPLs is blocked**, preserving the row numbers those files use for LOD references.
- **IDE/IPL sync** preserves untouched rows and III/VC scale, avoids duplicate LOD rows on repeated Add, and handles deletion with only a LOD selected. Unlink and Remove show the affected entries before proceeding.
- **Import from IMG and Import Map** preserve each placement, binary stream IPLs, interiors, COL/TXD import choices and collision models from COL libraries. Map scan, import and extraction use the same IPL set and the game's archive load order.
- **IMG handling** keeps the first duplicate entry as the game does; rebuilding preserves duplicate and empty entries. VER2 sizes, D3D8 alpha detection and III/VC IDE mesh counts are corrected.
- **Collision spheres and boxes** are measured relative to their COL model in each exporter. Primitive lighting uses the byte the game reads, surface values are clamped, regenerated COL bounds are reset, and COL libraries retain each model's IDE name. Legacy primitives left near the origin receive a reimport warning.
- **Model-ID assignment** keeps copies of one model together, prefers the next ID for its LOD and avoids consuming another model ID for that model's own COL. Sequential assignment skips COL objects. An empty preset file no longer silently clears game reservations.
- **Paletted TXD import** reads the correct PAL4 palette size and fixes D3D9 red/blue ordering while preserving III/VC D3D8 colours.
- **Prelight and light cutter** preserve painted vertex alpha. World-space lighting, repeated bake ambient, palette conversion, HDRI rotation and mirrored unwrap are corrected.
- **Other map tools:** repeated IPL-section import no longer duplicates objects; cull/garage/enex/jump/zone geometry, water polygons, X Radar grid, animation mirroring and Vehicle Scale are corrected. Zone names match the Outliner, texture previews keep III colours, and IDE flag checkboxes show the imported bits.
- **Game-file lookup works across letter case on Linux/macOS.** Windows-style paths from `gta.dat`, `gta_vc.dat` and `gta3.dat` resolve correctly, and differently spelled paths no longer count the same archive twice. IDE discovery uses the files the selected game actually loads.

## ♻️ Existing scenes

- If an earlier v2.5.0 enable attempt failed, restart Blender after installing the corrected ZIP to clear the classes left by that failed registration.
- Reimport old path scenes that were already edited without persistent point identities. Old III/VC path imports may also need reimporting for corrected coordinate scale. Keep imported NODES category meshes separate; add roads through the vehicle mesh rather than manually adding navigation vertices.
- New NODES points must stay in their region. If an edit changes old IDs, import and select all 64 regions for export. Ambiguous coincident duplicates, unsupported foreign-node deletion and unknown nonzero tails stop the export before writing. The batch is validated in advance; a late disk/OS error does not guarantee rollback of all 64 files.
- Reimport COL primitives from old scenes if their spheres/boxes were left at the origin. Vertex alpha painted before light-cutter baking is preserved.

## ✅ Verification

- **1810 tests passed** in the regular Python suite. Its three Blender-only IFP checks were also run successfully in native Blender; the remaining skipped GTA III `paths.ipl` check has no source file because III loads those paths from IDE.
- **20 checks passed without skips in Blender 5.1.2:** 11 NODES scenarios and 9 IFP checks, including real Edit Mode, Extrude/Subdivide, save/reload and export of all 64 original SA regions.
- The **v2.5.0 extension ZIP builds and passes Blender's validator**. All 11 store-compliance checks passed; the archive contains the new path modules and excludes development files and Python bytecode.
- The built ZIP is also checked through Blender's extension manager in a temporary local repository: enable/disable, repeated enable and initialization of an existing path curve. This check runs in the packaging CI job.
- Runtime behaviour in GTA SA has not yet been tested.
