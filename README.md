<div align="center">

![INU Tools Logo](docs/logo.jpg)

# INU_Tools (GTA SA)

**Blender addon for GTA San Andreas modding — full pipeline from modeling to IMG archive.**

<p>
  <img src="https://img.shields.io/badge/Blender-2.83%E2%80%935.1-orange?logo=blender" alt="Blender">
  <img src="https://img.shields.io/badge/Version-2.4.0-green" alt="Version">
  <img src="https://img.shields.io/badge/License-GPL--3.0-blue" alt="License">
</p>

**[🇷🇺 Русская версия](docs/README_rus.md)** · **[📖 Documentation](docs/DOCS.md)**

</div>

---

## Highlights

<table>
<tr>
<td width="50%" valign="top">

- **Live Ariane bridge** — two-way, real-time editing with the Ariane map editor: import on click, send models / positions / instances back.
- **Native parsers** DFF / COL / TXD / IDE / IPL / IMG / IFP / FXP — zero external dependencies.
- **Full map round-trip** — IMG → Blender → edit DFF + COL + TXD → IMG.
- **Export checked against the engine** — every writer is audited against what `gta_sa.exe` actually reads; anything the game would crash on is named before the file is written.
- **Reliable IDE / IPL sync** — rows are found by their content, not by line numbers: copies keep their own placement and LOD, other people's rows are never overwritten, files are written atomically with a backup.
- **Time-cycle editor** (`timecyc.dat`) — preview any weather + hour as real Blender lighting, edit slots, fog and PostFX; reads SA, Vice City and III files.
- **Texture & prelight baking** — AO / Diffuse / Shadow / Alpha, procedural dirt / edge wear / curvature / thickness / grunge masks, hand-painting on any layer, prelight from all light types + HDRI, LightMap.
- **Skinned DFF + IFP** — peds with 294+ vanilla animations, IK rig, frame-hierarchy editor.
- **`effects.fxp` editor** — 82 particle systems with live viewport simulation.
- **ID Manager** — multi-preset, scene sync, FLA range extension, conflict detection.
- **Multi-game** — GTA III / VC / SA, auto-detected on import.
- **Performance** — Import Map ~10×, Export to IMG ~5–15×.

</td>
<td width="50%" valign="top">

![2DFX tutorial](docs/gif/cj-explosion.gif)

</td>
</tr>
</table>

→ **[What's new](../../releases/latest)** · [Version history](../../releases)

## Format Support

| Format | Import | Export | Edit | What it is |
|---|:---:|:---:|:---:|---|
| **DFF** | ✅ | ✅ | ✅ | RenderWare 3D model (geometry, skinning, materials, 2DFX, flags) |
| **COL** | ✅ | ✅ | ✅ | Collision (COL3, 179 surface types) |
| **TXD** | ✅ | ✅ | ✅ | Textures (DXT1/DXT5, parallel, pure numpy, drag&drop) |
| **IDE** | ✅ | ✅ | ✅ | Object definitions (objs/tobj/anim/cars/peds/weap/hier/txdp) |
| **IPL** | ✅ | ✅ | ✅ | Object placement (text + binary, 11 sections, FLA) |
| **IMG** | ✅ | ✅ | ✅ | Resource archive (VER2) — DFF + LOD + COL + TXD |
| **IFP** | ✅ | ✅ | ✅ | Animations (294+ vanilla, batch import, ANP3/ANPK/ANP2) |
| **FXP** | ✅ | ✅ | ✅ | `effects.fxp` particles — 82 systems, viewport simulation |
| **CST** | ✅ | ✅ | ✅ | Steve's COL Editor text format |
| **water.dat** | ✅ | ✅ | ✅ | Water: types, snap, waterclear256 |
| **paths / tracks / nodes / flight** | ✅ | ✅ | ✅ | Vehicle/ped paths, rail, path nodes, flight routes |

Plus: time cycles, zones (`map.zon`/`info.zon`), cameras, plants (`plants.dat`), X Radar Maker.
Details in the **[documentation](docs/DOCS.md)**.

## Installation

**Blender 4.2+ (extensions):** [extensions.blender.org](https://extensions.blender.org) → *Get Extensions* → search "INU Tools", or *Edit → Preferences → Get Extensions → Install from Disk…* with the release `.zip`.

**Manual (Blender 2.83+):** copy the `INU_tools/` folder into `Blender/<version>/scripts/addons/`, then *Edit → Preferences → Add-ons* → enable **INU_tools (gta_sa)**.

> Recommended: install the [latest release](../../releases/latest). The `main` branch is fresher but may contain bugs and unfinished features; if you hit a bug from `main`, please mention it in the issue.

## Compatibility

| | |
|---|---|
| **Blender** | 2.83 – 5.1 (4.2+ for extensions.blender.org) |
| **Game** | GTA San Andreas (primary); Vice City and III — experimental |
| **MTA** | MTA:SA compatible |
| **OS** | Windows / Linux / macOS |

<details>
<summary>Multi-game support (III / VC / SA) — details</summary>

Set the target game from the **GTA Tools** N-sidebar header dropdown (SA / VC / III); every exporter routes through the right format dispatch.

- **DFF/COL/TXD/IDE/IPL/IMG/IFP** read and write for all three games (COLL/COL2/COL3, VER1/VER2, ANPK/ANP3, etc.).
- SA-only features (Pipeline chunk, UV anim, multi-mesh LOD, SunGlare) are dropped with a warning when writing to III/VC; the formats follow each game's engine (VC PC is RW 3.4.0.3 with `COLL` collisions and D3D8 textures, not RW 3.5).
- The time-cycle editor reads III and VC `timecyc.dat` too — 24 hourly slots and each game's own fields (Trails colour, top clouds, the VC ambient pairs).
- The Ariane bridge exports for the scene's game and warns when the ariane install next to it is a different one.
- Full map round-trip is SA-only for now; for III/VC — import assets and export individual DFF/COL/TXD.
- Cross-game COL export collapses some of SA's 179 surfaces (`GRASS_SHORT` ↔ `GRASS_LONG`, etc.).

The full per-game format table is in the **[documentation](docs/DOCS.md)**.

</details>

## Links

- 📖 [Documentation](docs/DOCS.md)
- 📹 [Video tutorial: IDE / IPL / IMG / Map](https://www.youtube.com/watch?v=Jw_R9QFYxWE)

## Credits

- **[DragonFF](https://github.com/Parik27/DragonFF)** (Parik, GPL-3.0) — compatible material/object property names for an easy transition.
- **[RenderWare](https://en.wikipedia.org/wiki/RenderWare)** — GTA SA engine, format documentation.
- **[Ariane](https://github.com/Dryxio/ariane)** (Dryxio) — map editor for III / VC / SA (librw / euryopa) that the live bridge talks to.
- **[Itera Tools 3](https://itera.gumroad.com/l/IteraTools3)** — vertex lighting; the addon has a sub-panel to apply its presets.
- **[ChunkTools](https://github.com/milevskiy27/ChunkTools)** by **[milevskiy](https://github.com/milevskiy27)** (Apache-2.0) — the "Split into chunks" tool is adapted from it.

**Author:** INU (Discord `1.n.u` · [server](https://discord.gg/sqtGAVTGdy)) · animation mirroring — **yeezyk** · map chunking — **[milevskiy](https://github.com/milevskiy27)**

**License:** [GPL-3.0](LICENSE)
