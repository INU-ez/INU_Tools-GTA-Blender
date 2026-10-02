# INU_tools.ops.img_ops — IMG archive operators.
#
# Phase 3 of UI redesign: extracted from __init__.py without behavior
# changes. Five operators + two helpers (_refresh_img_entries,
# _append_export_report) live here. The Extract Resources modal is the
# heaviest — keeps its modal/timer/threadpool flow intact.

import os
import time
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import bpy
from bpy.props import BoolProperty, StringProperty

# T must be top-level — operator class bodies use T("...") in property
# descriptions which evaluate at class-definition time.
# _get_cache_dir / _write_png / _append_export_report live further down
# in the parent __init__.py than this import — pull them lazily inside
# each method so registration order doesn't matter.
from .. import T
from ..tools.compat import safe_icon, inu_icon
# ──────────────────────────── helpers ─────────────────────────────────

def _read_png_dimensions(path):
    """Read width × height from a PNG file's IHDR chunk. Returns (0, 0)
    if the file isn't a valid PNG. Used by Extract Resources to dedupe
    by resolution rather than by raw-vs-compressed byte count, which
    was meaningless (raw RGBA is almost always larger than its PNG)."""
    try:
        with open(path, 'rb') as f:
            sig = f.read(8)
            if sig != b'\x89PNG\r\n\x1a\n':
                return 0, 0
            f.read(8)  # IHDR length(4) + chunk-type "IHDR"(4)
            w = int.from_bytes(f.read(4), 'big')
            h = int.from_bytes(f.read(4), 'big')
            return w, h
    except (OSError, ValueError):
        return 0, 0


def _refresh_img_entries(scn, img_path):
    """Directly refresh IMG entries list."""
    scn.inu_settings.gtatools_img_entries.clear()
    try:
        from ..core.img import read_directory
        entries = read_directory(img_path)
        for entry in entries:
            item = scn.inu_settings.gtatools_img_entries.add()
            item.name = entry.name
        scn.inu_settings.gtatools_img_entries_index = max(0, len(entries) - 1)
    except Exception:
        pass


def _same_img(a, b):
    """Один и тот же архив (регистр, «//», «..» в пути не важны)."""
    if not a or not b:
        return False
    n = lambda p: os.path.normcase(os.path.normpath(bpy.path.abspath(p)))
    return n(a) == n(b)


def _stamp_img_status(jobs, written, img_path):
    """jobs [(имя записи .dff, объект)] → «В IMG» у реально записанных."""
    for fn, o in jobs:
        if fn.lower() in written and hasattr(o, 'inu'):
            o.inu.img_target_file = img_path


def _copy_jobs(objs, classify, lod_name):
    """Выделенные копии (house.001…, LOD каждой расстановки) → jobs под их
    именем записи: Import/Verify ставят статус каждой копии, Remove снимает
    у всех копий — Export ставит так же."""
    jobs = []
    for o in objs:
        if o.type != 'MESH':
            continue
        mt, b = classify(o)
        if mt == 'DFF' and b:
            jobs.append((b.rstrip('_') + '.dff', o))
        elif mt == 'LOD' and b:
            jobs.append((lod_name(o, b.rstrip('_')) + '.dff', o))
    return jobs


# ──────────────────────────── operators ───────────────────────────────

class GTATOOLS_OT_refresh_img_list(bpy.types.Operator):
    """Обновить список файлов IMG архива"""
    bl_idname = "gtatools.refresh_img_list"
    bl_label = "INU: Refresh IMG List"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.img import read_directory
        scn = context.scene
        img_path = bpy.path.abspath(scn.inu_settings.gtatools_img_path)
        if not img_path or not os.path.isfile(img_path):
            self.report({'WARNING'}, T("Укажите путь к IMG"))
            return {'CANCELLED'}

        scn.inu_settings.gtatools_img_entries.clear()
        try:
            entries = read_directory(img_path)
            for entry in entries:
                item = scn.inu_settings.gtatools_img_entries.add()
                item.name = entry.name
            scn.inu_settings.gtatools_img_entries_index = max(0, len(entries) - 1)
            self.report({'INFO'}, f"{T('Файлов:')} {len(scn.inu_settings.gtatools_img_entries)}")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}


class GTATOOLS_OT_extract_resources(bpy.types.Operator):
    """Извлечь все DFF, COL и текстуры из IMG-архивов GTA SA.

    Кеш создаётся в папке .inu_cache/ рядом с твоим .blend файлом,
    поэтому сцену нужно сначала сохранить — без сохранённого .blend
    кешу некуда лечь, и оператор откажется работать.

    Региональный фильтр (если выбран) сужает извлечение до TXD/моделей,
    реально используемых в этом регионе по IDE/IPL — экономит минуты
    на больших картах. ALL = извлечь всё"""
    bl_idname = "gtatools.extract_textures"
    bl_label = "INU: Extract Resources"
    bl_options = {'REGISTER'}

    _timer = None
    _gen = None

    def invoke(self, context, event):
        scene = context.scene

        # Cache lives next to the .blend file (see _get_cache_dir).
        # Without a saved .blend the cache lands in a temp folder
        # that vanishes on Blender restart — extraction would burn
        # minutes for nothing. Block until the user saves.
        if not bpy.data.filepath:
            self.report({'ERROR'}, T(
                "Сначала сохраните сцену (.blend) — кеш создаётся "
                "рядом с ней. Без сохранения извлечение уйдёт "
                "во временную папку и пропадёт"))
            return {'CANCELLED'}

        game_root = bpy.path.abspath(scene.inu_settings.gtatools_game_root)

        if not game_root or not os.path.isdir(game_root):
            self.report({'ERROR'}, T("Укажите корневую папку GTA SA"))
            return {'CANCELLED'}

        from ..core.gta_dat import find_all_resources
        from ..core.img import read_directory
        from ..core.ide import read_ide
        from ..core.ipl import read_ipl
        from ..core import map_files

        info = find_all_resources(game_root)

        # All IMG archives in the game's load order (core/map_files →
        # gta_dat.img_load_order: SA gta3.img, gta_int.img, IMG lines of
        # the .dat; III/VC the last CDIMAGE first), the
        # user-set `gtatools_img_path`, then every other `.img` under
        # game_root alphabetically — catches custom installs, mod archives,
        # additional `playerN.img`, `cutscene.img`, district-split mods, etc.
        # A name found in several archives is taken from the first, as the
        # game streams it.
        img_paths = map_files.game_archives(
            game_root, info.img_paths,
            bpy.path.abspath(scene.inu_settings.gtatools_img_path))
        # Always log the final IMG list — helps users diagnose why some
        # archives weren't picked up (path typos / permission errors / etc.).
        print(f"\n[Extract Resources] game_root = {game_root}")
        print(f"[Extract Resources] {len(img_paths)} IMG archive(s) to process:")
        for ip in img_paths:
            print(f"  - {ip}")
        print()

        if not img_paths:
            self.report({'ERROR'}, T("Не найден IMG архив"))
            return {'CANCELLED'}

        # One directory read per archive — shared by the region pass and
        # the extraction plan below.
        dirs = {}

        def _dir(ip):
            if ip not in dirs:
                try:
                    dirs[ip] = read_directory(ip)
                except Exception as ex:
                    print(f"[Extract Resources] {ip}: {ex}")
                    dirs[ip] = []
            return dirs[ip]

        # Region filter — when picked, walk the region's IPLs to gather
        # used model_ids, look those up in IDE files to get TXD names,
        # then only extract those TXDs. Saves minutes on large extracts.
        #
        # The IPLs are the set Scan lists and Import Map reads
        # (core/map_files.region_files): text IPLs of gta.dat in
        # maps/<region>/ + their <stem>_stream<N>.ipl from the archives —
        # vanilla SA places a lot of district geometry that way
        # (countn2_stream*, int_la_stream* of gta_int.img…). Scan
        # checkboxes are not applied: a few TXDs more do no harm.
        region = getattr(scene.inu_settings, 'gtatools_map_region', 'ALL')
        needed_txds = None  # None = "extract everything"
        if region != 'ALL':
            ide_txd_by_id = {}
            for p in info.ide_paths:
                if os.path.isfile(p):
                    try:
                        ide = read_ide(p)
                        for obj in ide.objects:
                            ide_txd_by_id[obj.model_id] = obj.txd_name
                        for anim in ide.anims:
                            ide_txd_by_id.setdefault(anim.model_id, anim.txd_name)
                    except Exception:
                        pass

            used_ids = set()
            text_ipls, bin_ipls = map_files.region_files(
                [p for p in info.ipl_paths if os.path.isfile(p)], img_paths,
                region, _dir, game_root)

            # Pass 1: text IPLs from gta.dat
            text_ipl_count = 0
            for p in text_ipls:
                try:
                    ipl = read_ipl(p)
                    for inst in ipl.instances:
                        used_ids.add(inst.model_id)
                    text_ipl_count += 1
                except Exception:
                    pass

            # Pass 2: streamed IPLs inside the archives — `bnry` blobs or,
            # rarely, text; parse them to pull instance model_ids. Read by
            # directory record (the one the game streams), not by name.
            bin_ipl_count = 0
            by_arch = {}
            for _n, ip, e in bin_ipls:
                by_arch.setdefault(ip, []).append(e)
            for ip, recs in by_arch.items():
                try:
                    with open(ip, 'rb') as fh:
                        for e in recs:
                            try:
                                ipl_parsed = map_files.read_ipl_bytes(
                                    map_files.read_entry(fh, e))
                                for inst in ipl_parsed.instances:
                                    used_ids.add(inst.model_id)
                                bin_ipl_count += 1
                            except Exception:
                                pass
                except Exception:
                    pass

            print(f"[Extract Resources] region={region}: scanned "
                  f"{text_ipl_count} text IPLs + {bin_ipl_count} binary IPLs, "
                  f"{len(used_ids)} unique model_ids")

            needed_txds = {
                ide_txd_by_id[mid].lower()
                for mid in used_ids
                if mid in ide_txd_by_id and ide_txd_by_id[mid]
            }

        from .. import _get_cache_dir
        cache_dir = _get_cache_dir()
        tex_dir = os.path.join(cache_dir, 'textures')
        os.makedirs(tex_dir, exist_ok=True)

        # What the cache already holds — .inu_cache/_extract_index.json
        # (core/map_files, shared with INU Max): every file remembers the
        # archive record it came from. An unchanged archive is not read at
        # all; in a changed one the records are compared by CRC and only
        # the changed ones are written / decoded again — a model replaced
        # in the IMG (Export to IMG, a mod) reaches the cache.
        index = map_files.load_index(cache_dir)
        try:
            have_files = {n.lower() for n in os.listdir(cache_dir)}
        except OSError:
            have_files = set()
        try:
            have_png = {n.lower() for n in os.listdir(tex_dir)
                        if n.lower().endswith('.png')}
        except OSError:
            have_png = set()
        stale = map_files.reset_tex_index(index, have_png)
        multi = set()
        winners = map_files.extract_winners(img_paths, _dir, multi=multi)
        states = {ip: map_files.archive_state(ip) for ip in img_paths}
        plan = map_files.plan_extract(winners, index, states, have_files,
                                      have_png, needed_txds)
        # TXDs to read, for accurate progress (after region filter if any)
        txd_total = sum(len(v) for v in plan['txd'].values())

        self._img_paths = img_paths
        self._cache_dir = cache_dir
        self._tex_dir = tex_dir
        self._txd_total = txd_total
        self._region = region
        self._index = index
        self._index_saved = False
        self._plan = plan
        self._states = states
        self._have_png = have_png
        self._stale = stale         # PNGs of an older decode — rewritten once
        self._wrote = {}            # PNG → TXDs that wrote it (_settle_pngs)
        self._multi = len(multi)    # names found in several archives
        self._same = plan['same']   # records the cache already holds
        self._dff_count = 0
        self._col_count = 0
        self._tex_count = 0
        self._skipped = 0
        self._txd_progress = 0
        # Per-reason skip counters — folded in on the main thread by
        # _work's drain loop (workers only return results). Final report
        # shows the breakdown so the user can see WHY textures are missing
        # (region filter vs parse error vs degenerate header vs
        # already-extracted-larger).
        self._skip_reasons = {
            'archive_filtered': 0,  # TXD archive didn't match region IPL
            'parse_error': 0,       # read_txd raised on the archive
            'no_name': 0,           # texture name was empty/all-null
            'zero_dims': 0,         # width or height was 0
            'no_pixels': 0,         # pixel data was empty
            'dedup': 0,             # existing PNG already at >= resolution
            'write_error': 0,       # _write_png raised
        }

        from ..tools.profiler import Profiler
        self._profiler = Profiler(
            f"Extract Resources ({region})",
            enabled=bool(getattr(scene.inu_settings, 'gtatools_profile_enabled', False)),
        )

        self._gen = self._work(context)
        wm = context.window_manager
        wm.progress_begin(0, max(txd_total, 1))
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(T("Извлечение ресурсов..."))
        return {'RUNNING_MODAL'}

    def _work(self, context):
        import zlib
        from ..core.img import safe_filename
        from ..core.txd import read_txd
        from ..core import map_files
        from .. import _write_png

        cache_dir = self._cache_dir
        tex_dir = self._tex_dir
        prof = self._profiler
        plan = self._plan
        index = self._index
        files = index.setdefault('files', {})
        txds = index.setdefault('txd', {})
        txd_png = index.setdefault('txd_png', {})
        stale = self._stale

        err_log_path = os.path.join(cache_dir, '_txd_errors.log')
        skip_log_path = os.path.join(cache_dir, '_extract_skipped.log')

        # Reset both logs at start of each extraction so the user always
        # sees results from this run, not a growing all-time history.
        for _log_path in (skip_log_path, err_log_path):
            try:
                if os.path.isfile(_log_path):
                    os.remove(_log_path)
            except Exception:
                pass

        # Counter updates + log writes run ONLY on the main (generator)
        # thread: worker threads return their results and the drain loop
        # aggregates them here. Exactly one writer → no locks needed.
        # (extensions.blender.org rejects `threading`; the numpy/zlib work
        # still parallelises through the ThreadPoolExecutor below, which
        # never touches this shared state.)
        def _log_err(msg):
            try:
                with open(err_log_path, 'a', encoding='utf-8') as lf:
                    lf.write(msg + '\n')
            except Exception:
                pass

        def _log_skip(reason: str, tex_name: str, source: str, extra: str = ""):
            """Increment counter + record one line per skipped texture."""
            self._skip_reasons[reason] = self._skip_reasons.get(reason, 0) + 1
            self._skipped += 1
            try:
                with open(skip_log_path, 'a', encoding='utf-8') as lf:
                    lf.write(f"{reason:18s} | {tex_name[:40]:40s} | "
                             f"{source[:30]:30s} | {extra}\n")
            except Exception:
                pass

        def _process_txd(entry_name: str, txd_data: bytes):
            """Worker thread: parse TXD bytes and write a PNG per texture.

            PURE with respect to shared state — returns a result dict
            (``tex_count`` / ``skips`` / ``errors`` / ``pngs``); the main
            thread folds it into the counters, logs and the index (see
            ``_aggregate``). The one exception is ``stale``: a PNG
            rewritten here leaves the set (set ops are atomic).
            numpy DXT decompress (in read_txd) and zlib.compress (in
            _write_png) both release the GIL — so N workers do real
            parallel work on multi-core CPUs.
            """
            result = {'tex_count': 0, 'skips': [], 'errors': [], 'pngs': [],
                      'wrote': []}
            try:
                with prof.stage('read_txd (numpy DXT)', note=entry_name):
                    textures = read_txd(txd_data)
            except Exception as e:
                result['errors'].append(f"{entry_name}: {e}")
                result['skips'].append(('parse_error', '*', entry_name, str(e)))
                return result

            for tex in textures:
                raw_name = (tex.name or '').rstrip('\x00')
                # tex.name comes from a TXD that may carry garbage bytes —
                # `_read_str32` decodes with errors='replace' so non-ASCII
                # turns into '?'. Sanitize before forming a filesystem path
                # so corrupt archives don't crash the writer on Windows.
                name = safe_filename(raw_name)
                if not name:
                    result['skips'].append(
                        ('no_name', raw_name or '<empty>', entry_name, ''))
                    continue
                if tex.width == 0 or tex.height == 0:
                    result['skips'].append(
                        ('zero_dims', name, entry_name, f"{tex.width}x{tex.height}"))
                    continue
                if not tex.pixels:
                    result['skips'].append(
                        ('no_pixels', name, entry_name, f"{tex.width}x{tex.height}"))
                    continue

                png_path = os.path.join(tex_dir, name + '.png')
                png_key = (name + '.png').lower()
                result['pngs'].append(png_key)

                # Dedup: read existing PNG's actual resolution from its
                # IHDR. Skip only when the file on disk is at least as
                # large as the new texture in BOTH dimensions — protects
                # against a downscale variant from another IMG overwriting
                # a higher-res original. The previous comparison of
                # raw-RGBA bytes vs compressed PNG bytes was meaningless.
                # A PNG of an older decode (``stale``) is rewritten once,
                # whatever its size.
                if os.path.isfile(png_path) and png_key not in stale:
                    ew, eh = _read_png_dimensions(png_path)
                    if ew >= tex.width and eh >= tex.height:
                        result['skips'].append(
                            ('dedup', name, entry_name,
                             f"existing {ew}x{eh} >= new {tex.width}x{tex.height}"))
                        continue

                pixels = tex.pixels
                # R↔B: palette (PAL8/PAL4) textures of D3D8 — GTA III —
                # keep their palette as BGRA; same rule as txd_import.
                if (getattr(tex, 'platform_id', 0) == 8
                        and getattr(tex, 'raster_format', 0) & 0x6000
                        and len(pixels) % 4 == 0):
                    swapped = bytearray(pixels)
                    swapped[0::4], swapped[2::4] = pixels[2::4], pixels[0::4]
                    pixels = bytes(swapped)
                try:
                    with prof.stage('_write_png'):
                        _write_png(png_path, pixels, tex.width, tex.height)
                    stale.discard(png_key)
                    result['tex_count'] += 1
                    result['wrote'].append(
                        (png_key, png_path, tex.width * tex.height))
                except Exception as e:
                    result['errors'].append(f"{entry_name}/{name}: {e}")
                    result['skips'].append(
                        ('write_error', name, entry_name, str(e)))
            return result

        def _aggregate(fut, key, stamp):
            """Main thread: fold one finished future's result into the
            shared counters / logs and the index. Surfaces a worker crash
            to the error log instead of silently dropping it."""
            try:
                res = fut.result()
            except Exception as e:
                _log_err(f"worker crashed: {e}")
                txds.pop(key, None)
                return
            self._tex_count += res['tex_count']
            for msg in res['errors']:
                _log_err(msg)
            for skip in res['skips']:
                _log_skip(*skip)
            if res['errors']:
                # Broken / half-written TXD: no stamp → checked next run.
                txds.pop(key, None)
            else:
                txds[key] = stamp
                txd_png[key] = res['pngs']
            for png_key, png_path, area in res['wrote']:
                self._wrote.setdefault(png_key, [png_path, []])[1].append(
                    (area, key))

        # Worker count — start conservative (4). Bumping to 8 is safe too
        # but diminishing returns above that since IMG reads are serial.
        workers = min(os.cpu_count() or 4, 4)

        # Only the records invoke planned (new or changed since the last
        # run), each read by its own directory record — not by name, an
        # archive may repeat a name — in one forward pass per archive.
        for ip in self._img_paths:
            filtered = plan['filtered'].get(ip, [])
            for _key, entry in filtered:
                # Region filter excluded this TXD — log at archive level
                # so the user can see if their region pick was too narrow.
                _log_skip('archive_filtered', '*', entry.name,
                          f"region={self._region}")
            todo_files = plan['files'].get(ip, [])
            todo_txd = plan['txd'].get(ip, [])
            try:
                if todo_files or todo_txd:
                    with open(ip, 'rb') as fh:
                        for i, (key, entry) in enumerate(todo_files):
                            out_path = os.path.join(cache_dir,
                                                    safe_filename(entry.name))
                            try:
                                with prof.stage('extract DFF+COL',
                                                note=os.path.basename(ip)):
                                    wrote = map_files.refresh_file(
                                        fh, ip, key, entry, out_path, files)
                            except Exception as e:
                                _log_err(f"{entry.name}: {e}")
                                files.pop(key, None)
                                continue
                            if not wrote:
                                self._same += 1     # archive changed, record not
                            elif key.endswith('.dff'):
                                self._dff_count += 1
                            else:
                                self._col_count += 1
                            if i % 64 == 63:
                                yield

                        # TXD processing — main thread reads bytes, the pool
                        # crunches numpy/zlib. ThreadPoolExecutor's __exit__
                        # would block the generator until every worker finishes
                        # (freezes the UI); manage the pool manually and yield
                        # during drain so modal ticks fire and progress updates.
                        # Results are aggregated on THIS thread (see _aggregate)
                        # — no shared-state locks, no `threading` import.
                        import time as _t
                        pool = ThreadPoolExecutor(max_workers=workers)
                        # Track on self so _cleanup() can tear it down on ESC
                        # — otherwise worker threads would keep churning after
                        # the operator returns CANCELLED.
                        self._pool = pool
                        pending = []
                        try:
                            for key, entry in todo_txd:
                                with prof.stage('img.read (TXD bytes)'):
                                    txd_data = map_files.read_entry(fh, entry)
                                if not txd_data:
                                    _log_skip('parse_error', '*', entry.name,
                                              "empty read")
                                    txds.pop(key, None)
                                    self._txd_progress += 1
                                    continue
                                stamp = map_files.entry_stamp(
                                    ip, entry, zlib.crc32(txd_data))
                                if map_files.cached_ok(
                                        txds.get(key), ip, entry, crc=stamp[3],
                                        have_output=map_files.txd_outputs_present(
                                            index, key, self._have_png)):
                                    # Archive changed, this TXD did not.
                                    self._same += 1
                                    self._txd_progress += 1
                                    if self._txd_progress % 64 == 0:
                                        yield   # progress + ESC on a long run
                                    continue

                                pending.append((pool.submit(
                                    _process_txd, entry.name, txd_data), key, stamp))
                                yield  # let modal tick between submits

                            # Drain — aggregate each future as it completes,
                            # yielding so the UI keeps updating every ~50 ms.
                            # Progress advances as the main thread observes each
                            # finished future (replaces the old done-callback).
                            while pending:
                                still = []
                                for job in pending:
                                    if job[0].done():
                                        _aggregate(*job)
                                        self._txd_progress += 1
                                    else:
                                        still.append(job)
                                pending = still
                                if pending:
                                    _t.sleep(0.01)
                                yield
                        finally:
                            pool.shutdown(wait=False)
                            self._pool = None
                # Every planned record of this archive went through.
                self._settle_pngs()
                map_files.finish_archive(index, ip, self._states.get(ip),
                                         [k for k, _e in filtered])
            except Exception as _ip_err:
                # Don't let one bad archive abort the whole extraction —
                # but DO surface the failure so users can diagnose.
                # Silent swallowing here previously masked a parser bug
                # that made every Silent Hill TC IMG appear to extract
                # zero files for over a year.
                import traceback as _tb
                print(f"\n[Extract Resources] FAILED on {ip}:")
                _tb.print_exc()
                print()

        self._save_index()

        if prof.enabled:
            prof.print_report()
            prof.save_log(os.path.join(cache_dir, '_profile.log'))

    def _settle_pngs(self):
        """Neighbouring TXDs decode side by side in the pool: when two hold
        a texture of one name, both can find no PNG (or a stale one) and
        write it — the smaller may land last. Drop the stamp of every TXD
        whose PNG lost that way: the next run decodes it again and the
        resolution check keeps the larger one (as before the index)."""
        wrote, self._wrote = getattr(self, '_wrote', {}), {}
        txds = self._index.setdefault('txd', {})
        for png_path, writers in wrote.values():
            if len(writers) < 2:
                continue
            ew, eh = _read_png_dimensions(png_path)
            for area, key in writers:
                if area > ew * eh:
                    txds.pop(key, None)

    def _save_index(self):
        """Write .inu_cache/_extract_index.json once per run — after ESC too,
        so what got extracted is not redone next time."""
        if getattr(self, '_index_saved', True):
            return
        self._index_saved = True
        from ..core import map_files
        self._settle_pngs()
        try:
            self._index['tex_stale'] = sorted(self._stale.copy())
            map_files.save_index(self._cache_dir, self._index)
        except Exception as e:
            print(f"[Extract Resources] index not saved: {e}")

    def modal(self, context, event):
        if event.type == 'ESC':
            self._cleanup(context)
            self.report({'WARNING'}, T("Отменено"))
            return {'CANCELLED'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        wm = context.window_manager
        deadline = time.monotonic() + 0.1

        while time.monotonic() < deadline:
            try:
                next(self._gen)
            except StopIteration:
                self._cleanup(context)

                # Build breakdown — surface only the categories that
                # actually fired this run, otherwise the message is noise.
                # Detailed per-texture log lives in _extract_skipped.log.
                reasons = {k: v for k, v in self._skip_reasons.items() if v}
                breakdown = ""
                if reasons:
                    parts = ", ".join(f"{k}={v}" for k, v in
                                      sorted(reasons.items(), key=lambda kv: -kv[1]))
                    breakdown = f" [{parts}]"
                # Print the full breakdown to the system console so it's
                # easy to copy-paste into a bug report; the operator
                # status line keeps a short version for the header bar.
                full_msg = (f"DFF: {self._dff_count}, COL: {self._col_count}, "
                            f"{T('Извлечено текстур:')} {self._tex_count}, "
                            f"{T('пропущено:')} {self._skipped}{breakdown}")
                if self._same:
                    full_msg += f", {T('без изменений:')} {self._same}"
                if self._multi:
                    full_msg += ", " + T(
                        "файлов в нескольких архивах (взяты из первого "
                        "по порядку игры): {0}").format(self._multi)
                print(f"[Extract Resources] {full_msg}")
                if reasons:
                    print(f"[Extract Resources] подробности по каждой текстуре: "
                          f"{os.path.join(self._cache_dir, '_extract_skipped.log')}")
                self.report({'INFO'}, full_msg)
                return {'FINISHED'}

        wm.progress_update(self._txd_progress)
        context.workspace.status_text_set(
            f"TXD: {self._txd_progress}/{self._txd_total} | "
            f"DFF: {self._dff_count} COL: {self._col_count}")

        return {'RUNNING_MODAL'}

    def _cleanup(self, context):
        # Order matters on ESC: kill the pool first so its workers stop
        # picking up new tasks, then close the generator (its finally
        # block clears self._pool). cancel_futures requires Python 3.9+
        # which Blender 4.2 satisfies.
        pool = getattr(self, '_pool', None)
        if pool is not None:
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._pool = None

        gen = getattr(self, '_gen', None)
        if gen is not None:
            try:
                gen.close()
            except Exception:
                pass
            self._gen = None
        # ESC — keep what got extracted so far (no-op after a full run).
        self._save_index()

        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.window_manager.progress_end()
        context.workspace.status_text_set(None)


class _IdeGridInstance:
    """Псевдо-инстанс для «импорта по IDE» (когда IPL не выбран): одна
    определённая модель, разложенная сеткой. Поля — как у IPL-инстанса,
    чтобы import_from_img обрабатывал её тем же циклом."""
    __slots__ = ('model_name', 'model_id', 'pos_x', 'pos_y', 'pos_z',
                 'rot_w', 'rot_x', 'rot_y', 'rot_z', 'lod_index')


def _instances_from_ide(ide_models, step=30.0):
    """Псевдо-инстансы из определений IDE — каждая уникальная модель один
    раз, сеткой (чтобы модели не накладывались друг на друга). Позволяет
    «Импорт всех моделей» работать и без IPL — только по явно выбранным IDE
    (бокс IDE + «Найти IDE»), не по всем IDE папки игры."""
    import math
    uniq = {}
    for mid, ide_obj in ide_models.items():
        nm = (getattr(ide_obj, 'model_name', '') or '').strip()
        if nm and nm.lower() not in uniq:
            uniq[nm.lower()] = (nm, mid)
    items = list(uniq.values())
    cols = max(1, int(math.ceil(math.sqrt(len(items) or 1))))
    out = []
    for i, (nm, mid) in enumerate(items):
        pi = _IdeGridInstance()
        pi.model_name = nm
        pi.model_id = mid
        pi.pos_x = (i % cols) * step
        pi.pos_y = (i // cols) * step
        pi.pos_z = 0.0
        pi.rot_w, pi.rot_x, pi.rot_y, pi.rot_z = 1.0, 0.0, 0.0, 0.0
        pi.lod_index = -1
        out.append(pi)
    return out


def _ipl_paths_for_import(settings):
    """IPL-файлы для импорта/сканов: список синхронизации (мультивыбор), иначе
    один выбранный путь. Возвращает список существующих путей без дублей."""
    out, seen = [], set()
    for it in getattr(settings, 'gtatools_ipl_sync_list', []):
        p = bpy.path.abspath(it.path) if it.path else ''
        if p and os.path.isfile(p):
            k = os.path.normcase(os.path.normpath(p))
            if k not in seen:
                seen.add(k)
                out.append(p)
    if out:
        return out
    single = bpy.path.abspath(getattr(settings, 'gtatools_ipl_path', '') or '')
    return [single] if single and os.path.isfile(single) else []


def _is_binary_ipl(path):
    """Двоичный IPL (заголовок bnry — стрим-IPL SA из IMG)."""
    try:
        with open(path, 'rb') as f:
            return f.read(4) == b'bnry'
    except OSError:
        return False


def _merge_ipl_instances(paths):
    """Слить инстансы IPL-файлов `paths` в один список.

    Возвращает (instances, inst_src, binary_rows):
      • текстовый IPL — lod_index указывает В СВОЙ файл: сдвигаем на смещение
        его строк в общем списке (вне своего файла → -1, а не в соседний);
        inst_src[idx] = (путь, смещение) — привязка к строке (map_link);
      • двоичный IPL — lod_index указывает в ТЕКСТОВЫЙ IPL района (игра:
        IplEntityIndexArrays[relatedIpl]), которого в списке нет → -1; имён в
        файле нет (даст IDE по ID), к строке не привязываем (Add/Sync двоичный
        IPL не пишут); индексы строк — в binary_rows."""
    from ..core.ipl import read_ipl
    instances, inst_src, binary_rows = [], {}, []
    for p in paths:
        try:
            ipl = read_ipl(p)
        except Exception:
            continue
        binary = _is_binary_ipl(p)
        base, n_local = len(instances), len(ipl.instances)
        for k, inst in enumerate(ipl.instances):
            li = getattr(inst, 'lod_index', -1)
            if binary:
                inst.lod_index = -1
                binary_rows.append(base + k)
            else:
                inst.lod_index = (base + li if li is not None
                                  and 0 <= li < n_local else -1)
                inst_src[base + k] = (p, base)
            instances.append(inst)
    return instances, inst_src, binary_rows


def _name_binary_rows(instances, binary_rows, ide_models):
    """Имена строк двоичного IPL — из IDE по ID (в самом файле имён нет)."""
    for i in binary_rows:
        inst = instances[i]
        if not inst.model_name and inst.model_id in ide_models:
            inst.model_name = ide_models[inst.model_id].model_name


_img_tex_index_cache = {}   # (path, size) -> {texture_lower: set(txd_lower)}


def _get_img_texture_index(img_path):
    """{texture_name → {txd_name}} для всех текстур в IMG. Кэш по (путь, размер)
    — строится один раз (scan_img читает только имена, без декода)."""
    try:
        key = (os.path.normcase(img_path), os.path.getsize(img_path))
    except OSError:
        key = (os.path.normcase(img_path), 0)
    idx = _img_tex_index_cache.get(key)
    if idx is not None:
        return idx
    idx = {}
    try:
        from ..core.texture_index import scan_img
        for e in scan_img(img_path):
            tn = (getattr(e, 'texture_name', '') or '').lower()
            if tn:
                idx.setdefault(tn, set()).add(
                    (getattr(e, 'txd_name', '') or '').lower())
    except Exception:
        idx = {}
    _img_tex_index_cache[key] = idx
    return idx


def _rescue_textures_from_img(archives, img_index, tmpdir, extract_file, import_txd):
    """Дотянуть текстуры ИЗ АРХИВОВ (`archives` — те же, по которым построен
    img_index) для материалов, у которых имя текстуры (dff_texture_name) есть,
    а картинки нет. Нужный .txd ищется по СОДЕРЖИМОМУ (индекс имён,
    scan_img — без декода пикселей), БЕЗ IDE: IPL/DFF достаточно. Учитывается
    только выигравшая копия TXD (та, что в img_index). Импортируется минимальный
    набор TXD (greedy set-cover) и из каждого — только недостающие текстуры
    (name_filter): уже привязанные одноимённые картинки не перезаписываются.
    Возвращает число подгруженных TXD."""
    # 1. Материалы с именем текстуры, но без картинки.
    missing = set()
    for mat in bpy.data.materials:
        tn = (mat.get('dff_texture_name') or '').strip().lower()
        if not tn:
            continue
        has_img = False
        if getattr(mat, 'use_nodes', False) and mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and getattr(n, 'image', None):
                    has_img = True
                    break
        if not has_img:
            missing.add(tn)
    if not missing:
        return 0
    # 2. Индекс texture→txd по всем архивам (только имена, кэш по размеру
    #    архива — повторные импорты не пересканируют весь gta3.img). TXD,
    #    лежащий в нескольких архивах, — только из того, откуда его берёт
    #    img_index.
    txd_provides = {}
    for arch in archives:
        idx = _get_img_texture_index(arch)
        for tn in missing:
            for txd in idx.get(tn, ()):
                if img_index.get(txd + '.txd', (None,))[0] == arch:
                    txd_provides.setdefault(txd, set()).add(tn)
    # 3. Greedy set-cover: минимум TXD, покрывающих все missing.
    remaining = set(missing)
    chosen = []
    while remaining and txd_provides:
        best = max(txd_provides, key=lambda t: len(txd_provides[t] & remaining))
        cover = txd_provides[best] & remaining
        if not cover:
            break
        chosen.append((best, cover))
        remaining -= cover
        txd_provides.pop(best, None)
    # 4. Импортировать выбранные TXD из их архивов (привязка по имени).
    loaded = 0
    for txd, cover in chosen:
        hit = img_index.get(txd + '.txd')
        if hit is None:
            continue
        data = extract_file(hit[0], hit[1])
        if not data:
            continue
        p = os.path.join(tmpdir, txd + '.txd')
        try:
            with open(p, 'wb') as f:
                f.write(data)
            import_txd(filepath=p, name_filter=cover)
            loaded += 1
        except Exception:
            pass
    return loaded


_col_names_cache = {}   # (path, size, mtime) -> {запись .col: [[модель, смещение, длина], ...]}


def _col_names_in_img(arch):
    """{запись .col: [[модель, смещение, длина], ...]} — по заголовкам моделей
    COL (сигнатура, размер, имя), без разбора геометрии. Ванильная коллизия
    лежит в библиотеках (один .col на много моделей): игра привязывает модель
    COL по имени из её заголовка, имя записи не важно. Кэш по (путь, размер,
    mtime)."""
    import struct
    from ..core.img import read_directory, SECTOR
    key = (os.path.normcase(arch), os.path.getsize(arch), os.path.getmtime(arch))
    out = _col_names_cache.get(key)
    if out is not None:
        return out
    magics = (b'COLL', b'COL2', b'COL3', b'COL4')
    out, seen = {}, set()
    with open(arch, 'rb') as f:
        for e in read_directory(arch):
            low = e.name.lower()
            # extract_file берёт первую запись с этим именем — её и индексируем.
            if not low.endswith('.col') or low in seen:
                continue
            seen.add(low)
            base, end = e.offset * SECTOR, (e.offset + e.size) * SECTOR
            pos, models = 0, []
            while base + pos + 32 <= end:
                f.seek(base + pos)
                hdr = f.read(32)
                if len(hdr) < 32 or hdr[:4] not in magics:
                    break
                size = struct.unpack_from('<I', hdr, 4)[0]
                if size <= 0:
                    break
                name = hdr[8:30].split(b'\x00', 1)[0].decode('ascii', 'replace')
                models.append([name, pos, 8 + size])
                pos += 8 + size
            if models:
                out[e.name] = models
    _col_names_cache[key] = out
    return out


def _col_index_for(archives):
    """{модель: (архив, запись .col, смещение, длина)} по всем `archives` —
    правило как у img_index: первое вхождение по порядку архивов побеждает."""
    idx = {}
    for arch in archives:
        try:
            names = _col_names_in_img(arch)
        except Exception:
            continue
        for entry, models in names.items():
            for m, off, ln in models:
                if m:
                    idx.setdefault(m.lower(), (arch, entry, off, ln))
    return idx


class GTATOOLS_OT_import_from_img(bpy.types.Operator):
    """Импорт всех моделей из IMG: по IPL (с расстановкой) ИЛИ по IDE (все
    определённые модели, разложенные сеткой). Геометрия и ТЕКСТУРЫ достаются
    из IMG on-the-fly (текстуры — по содержимому, IDE не требуется)."""
    bl_idname = "gtatools.import_from_img"
    bl_label = "INU: Import from IMG"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Быстрая проверка, затем МОДАЛЬНЫЙ запуск: прогресс внизу и без
        # зависания Blender (как «Импорт карт»). Тяжёлый цикл — в _work-генераторе.
        img_path = bpy.path.abspath(context.scene.inu_settings.gtatools_img_path)
        _found = [p for p in
                  (context.scene.get('gtatools_found_imgs', '') or '').split('\n')
                  if p and os.path.isfile(p)]
        # IMG-строку убрали: базой могут быть найденные архивы («Найти IMG»).
        # Ошибка только если совсем нет ни ручного IMG, ни найденных.
        if (not img_path or not os.path.isfile(img_path)) and not _found:
            self.report({'ERROR'},
                        T("Нет IMG: нажми «Найти IMG» или укажи архив"))
            return {'CANCELLED'}
        self._gen = self._work(context)
        self._final = None          # (level, msg) — отчёт при завершении
        self._total = 0
        self._done = 0
        wm = context.window_manager
        wm.progress_begin(0, 1)
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(T("Импорт из IMG..."))
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            try:
                self._gen.close()
            except Exception:                         # noqa: BLE001
                pass
            self._finish(context)
            self.report({'WARNING'}, T("Отменено"))
            return {'CANCELLED'}
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        import time
        wm = context.window_manager
        deadline = time.monotonic() + 0.08
        try:
            while time.monotonic() < deadline:
                next(self._gen)
        except StopIteration:
            self._finish(context)
            if self._final:
                self.report({self._final[0]}, self._final[1])
            return {'FINISHED'}
        except Exception as e:                        # noqa: BLE001
            self._finish(context)
            self.report({'ERROR'}, T("Ошибка импорта: ") + str(e))
            return {'CANCELLED'}
        if self._total:
            wm.progress_update(min(1.0, self._done / self._total))
        context.workspace.status_text_set(
            f"{T('Импорт из IMG:')} {self._done}/{self._total or '?'}")
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        wm = context.window_manager
        if getattr(self, '_timer', None):
            wm.event_timer_remove(self._timer)
            self._timer = None
        wm.progress_end()
        context.workspace.status_text_set(None)

    def _work(self, context):
        from ..core.img import extract_file, read_directory
        from ..core.ide import read_ide
        from ..core.ipl import read_ipl
        from .dff_import import import_dff as inu_import_dff
        from .txd_import import import_txd as inu_import_txd
        from mathutils import Quaternion, Vector

        scene = context.scene
        img_path = bpy.path.abspath(scene.inu_settings.gtatools_img_path)
        ide_path = bpy.path.abspath(scene.inu_settings.gtatools_ide_path)
        ipl_path = bpy.path.abspath(scene.inu_settings.gtatools_ipl_path)
        game_root = bpy.path.abspath(scene.inu_settings.gtatools_game_root)

        # Архивы: основной IMG + найденные «Найти IMG», без повторов, в порядке
        # загрузки игрой (SA — первый зарегистрированный, III/VC — последний
        # CDIMAGE): модель из нескольких архивов берётся как в игре.
        from ..core.gta_dat import order_archives, dat_game
        archives = order_archives(
            [p for p in [img_path] + (scene.get('gtatools_found_imgs', '') or '').split('\n')
             if p and os.path.isfile(p)], game_root)

        # Auto-detect game from the IMG archive's format (VER2 magic →
        # SA, sibling .dir present → VC fallback). Auto-flips scene
        # game on fresh scenes, otherwise warns about mismatch so the
        # user can manually switch the GTA Tools tab.
        try:
            from ..core import game_versions as gv
            detected = gv.detect_game_from_img(
                img_path if os.path.isfile(img_path)
                else (archives[0] if archives else ''))
            # IMG у III и VC одинаковый (VER1 + .dir) — III узнаём по папке игры.
            if detected == gv.GAME_VC and dat_game(game_root) == gv.GAME_III:
                detected = gv.GAME_III
            switched = gv.maybe_set_game_from_import(scene, detected)
            if not switched:
                warn = gv.check_game_mismatch_warning(scene, detected)
                if warn:
                    self.report({'WARNING'}, warn)
        except Exception:
            pass

        ide_models = {}
        ide_source = {}   # model_id -> IDE-файл: для статуса «В IDE» и экспорта
                          # «каждая модель в свой IDE» (round-trip)
        instances = []
        # idx → (text IPL path, index offset of that file in `instances`):
        # imported models get linked to their row right away (map_link).
        inst_src = {}
        binary_rows = []   # строки двоичного IPL: имя дадут IDE по ID

        def _load_ide_into(p):
            """Прочитать IDE `p` в ide_models и запомнить источник (model_id→p).
            Первый источник побеждает (приоритет уже загруженных определений)."""
            try:
                ide = read_ide(p)
            except Exception:
                return
            for o in ide.objects:
                if o.model_id not in ide_models:
                    ide_models[o.model_id] = o
                    ide_source[o.model_id] = p
            for a in ide.anims:
                if a.model_id not in ide_models:
                    ide_models[a.model_id] = a
                    ide_source[a.model_id] = p

        use_gta_dat = getattr(scene.inu_settings, 'gtatools_img_use_gta_dat', False)
        skip_lod = getattr(scene.inu_settings, 'gtatools_img_skip_lod', False)
        load_txd = getattr(scene.inu_settings, 'gtatools_img_load_txd', True)
        load_col = getattr(scene.inu_settings, 'gtatools_map_load_col', True)

        gta_dat_mode = bool(use_gta_dat and game_root and os.path.isdir(game_root))
        ipl_list = [] if gta_dat_mode else _ipl_paths_for_import(scene.inu_settings)

        if gta_dat_mode:
            from ..core.gta_dat import find_all_resources
            info = find_all_resources(game_root)

            for p in info.ide_paths:
                if os.path.isfile(p):
                    _load_ide_into(p)

            # Имя текстового IPL (lower, без расширения) → (смещение, строк):
            # lod_index его *_stream*.ipl указывает в него (CIplStore::LoadIpl).
            _text_tb = {}
            for p in info.ipl_paths:
                if os.path.isfile(p):
                    try:
                        ipl = read_ipl(p)
                    except Exception:
                        continue
                    # lod_index указывает В СВОЙ файл — сдвигаем на смещение.
                    _base = len(instances)
                    _text_tb.setdefault(
                        os.path.splitext(os.path.basename(p))[0].lower(),
                        (_base, len(ipl.instances)))
                    for _k, _inst in enumerate(ipl.instances):
                        _li = getattr(_inst, 'lod_index', -1)
                        if _li is not None and _li >= 0:
                            _inst.lod_index = _li + _base
                        inst_src[_base + _k] = (p, _base)
                        instances.append(_inst)

            # Also read binary IPL from IMG (stream files)
            img_dir = read_directory(img_path)
            # Имя, повторённое в архиве, игра грузит один раз (extract_file
            # и так отдаёт одну запись) — иначе расстановки задвоятся.
            _seen_ipl = set()
            for e in img_dir:
                if e.name.lower() in _seen_ipl:
                    continue
                _seen_ipl.add(e.name.lower())
                if e.name.lower().endswith('.ipl'):
                    try:
                        ipl_data = extract_file(img_path, e.name)
                        if ipl_data and ipl_data[:4] == b'bnry':
                            ipl = read_ipl.__wrapped__(ipl_data) if hasattr(read_ipl, '__wrapped__') else None
                            if ipl is None:
                                from ..core.ipl import _read_binary_ipl
                                from ..core.map_files import (binary_stem,
                                                              rebase_binary_lod)
                                ipl_parsed = _read_binary_ipl(ipl_data)
                                # lod_index — в текстовый IPL района, не в
                                # общий список (нет его → без LOD).
                                _tb = _text_tb.get(binary_stem(e.name))
                                for _inst in ipl_parsed.instances:
                                    _inst.lod_index = rebase_binary_lod(
                                        getattr(_inst, 'lod_index', -1), _tb)
                                instances.extend(ipl_parsed.instances)
                    except Exception:
                        pass
        else:
            if ide_path and os.path.isfile(ide_path):
                _load_ide_into(ide_path)
            elif ipl_list and game_root and os.path.isdir(game_root):
                # Авто-IDE: IDE не выбран, но задана папка с IDE — читаем ВСЕ
                # .ide из неё (корень игры → по gta.dat, иначе рекурсивный скан).
                # Только при IPL: модель находится по имени из IPL; IDE лишь
                # даёт TXD/дальность/флаги, лишние определения не участвуют.
                # Без IPL сетку по ним не строим — только из явно выбранных IDE.
                from ..core.gta_dat import list_ide_files
                for p in list_ide_files(game_root):
                    if os.path.isfile(p):
                        _load_ide_into(p)

            # Мультивыбор IPL: сливаем инстансы из всех выбранных .ipl. lod_index
            # указывает В СВОЙ IPL, поэтому при слиянии сдвигаем его на смещение
            # инстансов этого файла — иначе LOD-привязка уедет. Двоичный IPL —
            # без имён, LOD и привязки к строке (см. _merge_ipl_instances).
            instances, inst_src, binary_rows = _merge_ipl_instances(ipl_list)

        # Подгрузить найденные «Найти IDE» — тогда txd_name/дальность/флаги
        # проставятся для ВСЕХ моделей IPL (кастомная карта часто разложена по
        # нескольким IDE). Уже загруженные из выбранного IDE имеют приоритет.
        _found_ides = [p for p in
                       (scene.get('gtatools_found_ides', '') or '').split('\n')
                       if p and os.path.isfile(p)]
        for _p in _found_ides:
            _load_ide_into(_p)
        # Строки двоичного IPL: имя модели — из загруженных IDE по ID.
        _name_binary_rows(instances, binary_rows, ide_models)

        # «Только по IDE»: без IPL расставлять негде — импортируем КАЖДУЮ
        # определённую в IDE модель раз, сеткой. Только из ЯВНО выбранных IDE
        # (бокс IDE + «Найти IDE»); IPL без строк inst — ошибка, а не сетка
        # всех моделей игры.
        if not instances:
            if ipl_list:
                self._final = ('ERROR', T("В IPL нет моделей"))
                return
            if gta_dat_mode:
                self._final = ('ERROR', T("Укажите IPL или IDE файл"))
                return
            explicit = ([ide_path] if ide_path and os.path.isfile(ide_path)
                        else []) + _found_ides
            if not explicit:
                self._final = ('ERROR', T("Укажите IPL или IDE файл"))
                return
            instances = _instances_from_ide(ide_models)
            inst_src = {}
            if not instances:
                self._final = ('ERROR', T("В IDE нет моделей"))
                return
        self._total = len(instances)

        # Индекс имя→(архив, реальное_имя) по `archives` (список выше).
        # Модели кастомной карты часто разложены по нескольким .img (maps/
        # RESOURCES) — тянем каждую из архива, где она реально лежит. Имя,
        # которое есть в нескольких архивах (или дважды в одном), берём как
        # игра — первое по порядку загрузки; такие DFF — в отчёт.
        img_index = {}
        _multi_arch = set()     # DFF, лежащие в нескольких архивах
        _multi_used = set()     # из них реально взятые из архива
        for _p in archives:
            try:
                for e in read_directory(_p):
                    _k = e.name.lower()
                    _hit = img_index.get(_k)
                    if _hit is None:
                        img_index[_k] = (_p, e.name)
                    elif _hit[0] != _p and _k.endswith('.dff'):
                        _multi_arch.add(_k)
            except Exception:
                continue
        # Коллизия: {модель: (архив, запись .col, смещение, длина)} по именам из
        # заголовков COL тех же `archives` — ванильная лежит в библиотеках (один
        # .col на много моделей), своя — в <модель>.col; находятся обе.
        col_index = _col_index_for(archives) if load_col else {}
        col_bytes = {}          # (архив, запись) → байты .col, одна распаковка
        col_mat_cache = {}      # материалы поверхностей COL — общие на прогон
        n_col = 0               # моделей, получивших коллизию
        n_col_empty = 0         # пустая запись COL (только имя и границы)

        def _get_or_create_collection(name):
            col = bpy.data.collections.get(name)
            if not col:
                col = bpy.data.collections.new(name)
                context.scene.collection.children.link(col)
            return col

        dff_collection = _get_or_create_collection("Map_DFF")
        lod_collection = _get_or_create_collection("Map_LOD")
        # Map_COL — только при включённом COL (иначе пустая коллекция).
        col_collection = _get_or_create_collection("Map_COL") if load_col else None

        imported_count = 0
        skipped_count = 0
        skip_lod_count = 0      # пропущено как LOD (Skip LOD включён)
        skip_noimg_count = 0    # <модель>.dff не найден в выбранном IMG
        skip_noname_count = 0   # нет имени модели (строка двоичного IPL не из IDE)
        _noimg_sample = []      # первые имена, которых нет в IMG (для диагностики)
        errors = []

        from ..core.ipl import is_lod_name, lod_instance_indices
        lod_refs = lod_instance_indices(instances)

        # ── Уже стоящие в сцене (повторный импорт того же IPL) ──
        # Раньше каждый импорт ставил всё заново: дубли объектов на тех же
        # координатах + повторная распаковка DFF/TXD. Теперь по inu.model_id:
        #   • инстанс с той же позицией/поворотом уже в сцене → пропускаем;
        #   • новый инстанс уже загруженной модели → linked-копия объекта
        #     из сцены, без распаковки и без дублей материалов.
        # scene_placed: model_id → [(loc, quat, [объекты инстанса])].
        from ..core.model_classify import explicit_name_type, reuse_key
        from ..tools.model_utils import _strip_dup_suffix
        scene_placed = {}
        for _o in context.scene.objects:
            if _o.type != 'MESH' or not hasattr(_o, 'inu'):
                continue
            _mid = int(_o.inu.model_id)
            if _mid <= 0:
                continue
            # Коллизия (тег COL/SHA или явный _COL/_SHA) — не модель: не
            # клонируем её вместо DFF и не считаем инстанс уже стоящим.
            if (getattr(_o.inu, 'type', 'OBJ') in ('COL', 'SHA')
                    or explicit_name_type(_strip_dup_suffix(_o.name))[0] == 'COL'):
                continue
            _loc, _q, _ = _o.matrix_world.decompose()
            _groups = scene_placed.setdefault(_mid, [])
            for _g in _groups:
                # Тот же инстанс (мульти-атомик DFF = несколько мешей в
                # одной точке) — добираем объект в его группу.
                if (_g[0] - _loc).length < 1e-3:
                    _g[2].append(_o)
                    break
            else:
                _groups.append((_loc.copy(), _q.copy(), [_o]))

        # Модель из сцены берём, только если совпали И ID, И имя (как в Max):
        # тот же ID у другой модели (чужой мод, ID Manager) — не наша модель.
        # Имя — любого меша группы, плюс ipl_last_name/ide_last_name
        # (переживают переименование объекта).
        scene_models = {}
        for _mid, _groups in scene_placed.items():
            for _g in _groups:
                for _o in _g[2]:
                    for _nm in (_strip_dup_suffix(_o.name), _o.inu.ipl_last_name,
                                _o.inu.ide_last_name):
                        _k = reuse_key(_nm)
                        if _k:
                            scene_models.setdefault((_k, _mid), _g[2])

        def _find_placed(model_id, pos, rot):
            """Группа объектов инстанса model_id, уже стоящего в pos/rot."""
            for _loc, _q, _objs in scene_placed.get(model_id, ()):
                if (_loc - Vector(pos)).length > 1e-3:
                    continue
                # q и -q — один поворот.
                if abs(_q.dot(rot)) < 0.9999:
                    continue
                return _objs
            return None

        skip_placed_count = 0   # уже стоят в сцене (тот же model_id+позиция)
        reused_count = 0        # инстансов взято linked-копией из сцены

        with tempfile.TemporaryDirectory() as tmpdir:
            imported_models = {}
            # TXD, уже импортированные в этом прогоне. Один общий архив
            # (basement.txd, 276 текстур ≈ 4 с) на 5000 инстансов раньше
            # декодировался ЗАНОВО на каждый — часы вместо минут. Картинки
            # после первого импорта уже в bpy.data.images, и материалы
            # следующих DFF цепляют их по имени при создании.
            txd_imported = set()
            # Главный объект каждого инстанса — для LOD-привязки после цикла
            # (inu.lod_object из IPL lod_index).
            instance_to_obj = [None] * len(instances)

            for idx, inst in enumerate(instances):
                self._done = idx
                if idx % 16 == 0:
                    yield          # отдать управление Blender (прогресс/отклик)
                model_name = inst.model_name or ''
                if not model_name:
                    # Строка двоичного IPL, чьего ID нет в IDE: без имени не
                    # найти ни DFF в архиве, ни модель в сцене.
                    skipped_count += 1
                    skip_noname_count += 1
                    continue
                is_lod = idx in lod_refs or is_lod_name(model_name)

                if skip_lod and is_lod:
                    skipped_count += 1
                    skip_lod_count += 1
                    continue

                target_collection = lod_collection if is_lod else dff_collection

                pos = (inst.pos_x, inst.pos_y, inst.pos_z)
                # GTA SA quaternion is stored conjugated
                rot = Quaternion((inst.rot_w, inst.rot_x, inst.rot_y, inst.rot_z)).conjugated()

                # Этот инстанс уже стоит в сцене → не дублируем. Главный меш
                # всё равно запоминаем: LOD-привязка ниже должна сработать,
                # даже если новая модель ссылается на уже стоящий LOD.
                _placed = _find_placed(inst.model_id, pos, rot)
                if _placed is not None:
                    skipped_count += 1
                    skip_placed_count += 1
                    instance_to_obj[idx] = _placed[0]
                    continue

                dff_filename = model_name + '.dff'

                _scene_src = None
                if model_name not in imported_models:
                    _k = reuse_key(model_name)
                    _scene_src = scene_models.get((_k, inst.model_id)) if _k else None

                if _scene_src is None and dff_filename.lower() not in img_index:
                    skipped_count += 1
                    skip_noimg_count += 1
                    if len(_noimg_sample) < 5:
                        _noimg_sample.append(model_name)
                    continue

                if model_name in imported_models or _scene_src is not None:
                    src_list = imported_models.get(model_name) or _scene_src
                    new_objects = []
                    from .map_link import clear_ipl
                    for src_obj in src_list:
                        new_obj = src_obj.copy()
                        new_obj.data = src_obj.data  # linked duplicate
                        # Копия тащит IPL-связь и LOD оригинала (ipl_uuid,
                        # сырой lod_index, lod_object): два объекта с одним
                        # ipl_uuid ломают upsert в Add to IPL, экспорт писал бы
                        # чужой LOD. Строка текстового IPL — свой штамп ниже.
                        if hasattr(new_obj, 'inu'):
                            clear_ipl(new_obj)
                            new_obj.inu.lod_object = None
                        target_collection.objects.link(new_obj)
                        new_objects.append(new_obj)
                    if _scene_src is not None:
                        reused_count += 1
                        imported_models[model_name] = new_objects
                else:
                    _di = img_index[dff_filename.lower()]
                    dff_data = extract_file(_di[0], _di[1])
                    if not dff_data:
                        errors.append(f"{model_name}: DFF extract failed")
                        continue
                    if dff_filename.lower() in _multi_arch:
                        _multi_used.add(dff_filename.lower())

                    dff_path = os.path.join(tmpdir, dff_filename)
                    with open(dff_path, 'wb') as f:
                        f.write(dff_data)

                    try:
                        before = set(context.scene.objects)
                        inu_import_dff(filepath=dff_path, context=context)
                        after = set(context.scene.objects)
                        # По имени — порядок (и главный меш ниже) не зависит
                        # от порядка множества.
                        new_objects = sorted(after - before, key=lambda o: o.name)

                        if load_txd:
                            txd_name = model_name
                            if inst.model_id in ide_models:
                                txd_name = ide_models[inst.model_id].txd_name

                            txd_filename = txd_name + '.txd'
                            _txd_key = txd_filename.lower()
                            if _txd_key in img_index and _txd_key not in txd_imported:
                                txd_imported.add(_txd_key)
                                _ti = img_index[_txd_key]
                                txd_data = extract_file(_ti[0], _ti[1])
                                if txd_data:
                                    txd_path = os.path.join(tmpdir, txd_filename)
                                    with open(txd_path, 'wb') as f:
                                        f.write(txd_data)
                                    try:
                                        inu_import_txd(filepath=txd_path)
                                    except Exception:
                                        # One unreadable TXD in the archive
                                        # must not abort the whole map import.
                                        pass

                        for obj in new_objects:
                            for c in list(obj.users_collection):
                                c.objects.unlink(obj)
                            target_collection.objects.link(obj)

                        # Коллизия — по имени модели из col_index, один раз на
                        # модель (на её первой расстановке).
                        _ch = col_index.get(model_name.lower())
                        if _ch is not None:
                            try:
                                from ..core.col import read_col
                                from .col_import import import_col_from_models
                                _ck = (_ch[0], _ch[1].lower())
                                if _ck not in col_bytes:
                                    col_bytes[_ck] = extract_file(_ch[0], _ch[1]) or b''
                                _cm = read_col(col_bytes[_ck][_ch[2]:_ch[2] + _ch[3]])[:1]
                                if _cm and not (_cm[0].faces or _cm[0].shadow_faces
                                                or _cm[0].spheres or _cm[0].boxes):
                                    n_col_empty += 1
                                elif _cm:
                                    # Сетка + SHA (+ inu_col_bounds), сферы и
                                    # боксы — всё в пространстве модели; как в
                                    # Import Map, примитивы — дети сетки COL
                                    # (иначе SHA, иначе меша-держателя без
                                    # геометрии у модели из одних сфер/боксов).
                                    col_objects = import_col_from_models(
                                        _cm, bulk_mode=True,
                                        target_collection=col_collection,
                                        material_cache=col_mat_cache,
                                        with_prims=True)
                                    # Место — как у DFF. Сетка COL (иначе SHA)
                                    # встаёт на инстанс, остальное — её дети:
                                    # их location остаётся в пространстве
                                    # модели (так их читает экспорт COL).
                                    _anchor = next((o for o in col_objects
                                                    if o.inu.type == 'COL'),
                                                   col_objects[0] if col_objects else None)
                                    for co in col_objects:
                                        if co is _anchor:
                                            co.location = pos
                                            co.rotation_mode = 'QUATERNION'
                                            co.rotation_quaternion = rot
                                        elif co.parent is None:
                                            co.parent = _anchor
                                    if _anchor is not None and _anchor.inu.type == 'COL':
                                        _sfx_col = getattr(scene.inu_settings, 'gtatools_suffix_col', '_COL')
                                        _pfx_col = getattr(scene.inu_settings, 'gtatools_prefix_col', '')
                                        from ..core.ipl import strip_lod_marker
                                        base_col = strip_lod_marker(model_name)
                                        if _sfx_col:
                                            _anchor.name = base_col + _sfx_col
                                        elif _pfx_col:
                                            _anchor.name = _pfx_col + base_col
                                    n_col += 1
                            except Exception:
                                # COL is optional decoration for the
                                # instance — a bad one leaves the DFF
                                # imported instead of killing the run.
                                pass

                        imported_models[model_name] = new_objects
                    except Exception as e:
                        errors.append(f"{model_name}: {str(e)}")
                        continue

                _sfx_dff = getattr(scene.inu_settings, 'gtatools_suffix_dff', '_DFF')
                _sfx_lod = getattr(scene.inu_settings, 'gtatools_suffix_lod', '_LOD')
                _pfx_dff = getattr(scene.inu_settings, 'gtatools_prefix_dff', '')
                _pfx_lod = getattr(scene.inu_settings, 'gtatools_prefix_lod', '')
                for obj in new_objects:
                    # Встроенная коллизия DFF (тег COL/SHA) — без _DFF: маркер
                    # перебил бы тег, и экспорт записал бы её как геометрию.
                    if obj.type == 'MESH' and getattr(getattr(obj, 'inu', None),
                                                      'type', 'OBJ') not in ('COL', 'SHA'):
                        base = obj.name
                        if '.dff' in base.lower():
                            base = base.split('.dff')[0]
                        if '.' in base:
                            b, s = base.rsplit('.', 1)
                            if s.isdigit():
                                base = b
                        # Strip _0/_1/etc suffix added when DFF has multiple atomics
                        if '_' in base:
                            b, s = base.rsplit('_', 1)
                            if s.isdigit():
                                base = b

                        if is_lod:
                            from ..core.ipl import strip_lod_marker
                            base = strip_lod_marker(base)
                            if _sfx_lod:
                                obj.name = base + _sfx_lod
                            elif _pfx_lod:
                                obj.name = _pfx_lod + base
                        else:
                            if _sfx_dff:
                                # Don't double the suffix when the source name
                                # already carries it (e.g. re-imported from an
                                # IMG whose DFF was stored as «name_DFF.dff») —
                                # that produced «name_DFF_DFF».
                                if base.upper().endswith(_sfx_dff.upper()):
                                    base = base[:-len(_sfx_dff)]
                                obj.name = base + _sfx_dff
                            elif _pfx_dff:
                                if base.upper().startswith(_pfx_dff.upper()):
                                    base = base[len(_pfx_dff):]
                                obj.name = _pfx_dff + base

                for obj in new_objects:
                    if obj.type == 'MESH':
                        obj.location = pos
                        obj.rotation_mode = 'QUATERNION'
                        obj.rotation_quaternion = rot
                        if hasattr(obj, 'inu'):
                            obj.inu.model_id = inst.model_id
                            # Interior и 12-я колонка FLA — из строки IPL (у сетки
                            # «по IDE» их нет → 0), иначе Add перепишет строку с 0.
                            obj.inu.interior_id = int(getattr(inst, 'interior', 0) or 0)
                            obj.inu.real_interior = int(getattr(inst, 'real_interior', 0) or 0)
                            # IMG-источник → статус «В IMG» + цель по умолчанию
                            # для экспорта модели в IMG.
                            _src_img = img_index.get(dff_filename.lower(),
                                                     ('', ''))[0]
                            if _src_img:
                                obj.inu.img_target_file = _src_img
                            if inst.model_id in ide_models:
                                ide_obj = ide_models[inst.model_id]
                                # LOD-строка: её дистанция в IDE — это LOD Dist,
                                # а не обычная Draw Dist. Кладём в нужное поле.
                                if is_lod:
                                    obj.inu.lod_draw_distance = ide_obj.draw_distance
                                else:
                                    obj.inu.draw_distance = ide_obj.draw_distance
                                obj.inu.ide_flags = ide_obj.flags
                                obj.inu.txd_name = ide_obj.txd_name
                                # Пометить «в IDE» (как IPL-привязку) + запомнить
                                # исходный IDE-файл → статус синка работает и
                                # экспорт пишет модель в её IDE.
                                _srcide = ide_source.get(inst.model_id, '')
                                if _srcide:
                                    obj.inu.ide_linked = True
                                    obj.inu.ide_target_file = _srcide
                                    obj.inu.ide_last_draw_distance = ide_obj.draw_distance
                                    obj.inu.ide_last_txd_name = obj.inu.txd_name
                                    obj.inu.ide_last_flags = obj.inu.ide_flags
                                    obj.inu.ide_last_model_id = int(inst.model_id)
                                    obj.inu.ide_last_name = ide_obj.model_name
                            elif not obj.inu.txd_name:
                                # Нет записи в IDE — TXD носит имя модели (так он
                                # и грузился из архива). Заполняем поле, иначе оно
                                # пустое, хотя текстуры подгрузились.
                                obj.inu.txd_name = model_name

                # Главный меш инстанса — для LOD-привязки после цикла.
                # Мульти-атомик DFF (bar_barrier10: _L0 + _dam) — целая
                # часть, первая в DFF (map_link.main_rank), не случайный меш.
                from .map_link import main_rank
                _main = min((o for o in new_objects if o.type == 'MESH'),
                            key=main_rank, default=None)
                if _main is not None:
                    instance_to_obj[idx] = _main
                    # Сразу привязать к строке своего IPL (Add/Del/Sync найдут
                    # её по содержимому). LOD-строки — через lod_index модели.
                    _src = inst_src.get(idx)
                    if _src is not None and not is_lod and hasattr(_main, 'inu'):
                        from .map_link import stamp_ipl, norm
                        _li = getattr(inst, 'lod_index', -1)
                        stamp_ipl(_main, norm(_src[0]), inst,
                                  _li - _src[1] if _li is not None and _li >= 0
                                  else -1, fresh=True)
                imported_count += 1

            # ── Дотягивание текстур из IMG (по содержимому, без IDE) ──
            # Материалы, которым TXD не достался (напр. общая растительность,
            # чей txd_name не в выбранном IDE), добираем прямо из архивов —
            # тех же, что у img_index (основной IMG может быть пуст).
            # Только при включённом TXD — иначе текстуры не грузим вовсе.
            if load_txd:
                _rescue_textures_from_img(archives, img_index, tmpdir,
                                          extract_file, inu_import_txd)

            # ── LOD-привязка: inu.lod_object из IPL lod_index ──
            # lod_index инстанса указывает на позицию LOD-инстанса в этом же IPL.
            # Ставим PointerProperty на главную модель → панель показывает LOD
            # Dist, экспорт пересчитывает lod_index обратно. Работает, если LOD
            # тоже импортированы (Skip LOD выключен).
            _n = len(instances)
            for _idx, _inst in enumerate(instances):
                _main = instance_to_obj[_idx]
                if _main is None:
                    continue
                _li = getattr(_inst, 'lod_index', -1)
                if 0 <= _li < _n:
                    _lodo = instance_to_obj[_li]
                    if _lodo is not None and hasattr(_main, 'inu'):
                        try:
                            _main.inu.lod_object = _lodo
                            # LOD Dist основной модели = дистанция её LOD-партнёра
                            # (у LOD lod_draw_distance уже из IDE-строки выше).
                            if hasattr(_lodo, 'inu'):
                                _main.inu.lod_draw_distance = \
                                    _lodo.inu.lod_draw_distance
                        except Exception:
                            pass

        msg = f"{T('Импортировано:')} {imported_count}"
        if skipped_count:
            msg += f", {T('пропущено:')} {skipped_count}"
            # Разбивка причин — чтобы не гадать, почему ничего не загрузилось.
            reasons = []
            if skip_placed_count:
                reasons.append(f"{skip_placed_count} {T('уже в сцене')}")
            if skip_lod_count:
                reasons.append(f"{skip_lod_count} {T('LOD — снимите «Skip LOD»')}")
            if skip_noimg_count:
                reasons.append(f"{skip_noimg_count} {T('нет DFF в IMG')}")
            if skip_noname_count:
                reasons.append(f"{skip_noname_count} {T('нет имени модели (нет в IDE)')}")
            if reasons:
                msg += " (" + ", ".join(reasons) + ")"
        if errors:
            msg += f", {T('ошибок:')} {len(errors)}"
            for e in errors[:5]:
                print(f"[Map Import] {e}")
        if load_col:
            msg += f", {T('коллизия, моделей:')} {n_col}"
            if n_col_empty:
                msg += f", {T('пустых записей COL:')} {n_col_empty}"
        if _multi_used:
            # Папка игры без data/*.dat — порядок архивов лишь алфавитный.
            msg += ", " + (
                T("моделей в нескольких архивах (взяты как в игре): {0}")
                if dat_game(game_root) else
                T("моделей в нескольких архивах (папка игры не распознана — "
                  "взяты по алфавиту архивов): {0}")).format(len(_multi_used))
            print("[IMG import] в нескольких архивах, взяты из (примеры): "
                  + ", ".join(f"{n} ({os.path.basename(img_index[n][0])})"
                              for n in sorted(_multi_used)[:5]))
        # Диагностика в консоль: сколько файлов реально в IMG и примеры имён,
        # которых там не нашлось (для «нет DFF в IMG»).
        if skip_noimg_count:
            print(f"[IMG import] файлов в архиве: {len(img_index)}; "
                  f"не найдено DFF (примеры): {_noimg_sample}")
        self._final = ('INFO', msg)
        return


def _img_key(path):
    """Путь архива для сравнения: абсолютный, без разницы в регистре/слэшах."""
    return os.path.normcase(os.path.normpath(bpy.path.abspath(path))) if path else ''


def _remove_plan(context, objs):
    """Remove from IMG для выделенных *objs* → (план по архивам — см.
    core.img_remove.remove_plan, части плана, заметки).

    Архив у каждой модели свой (img_target_file; у LOD без своего — архив его
    модели, у COL — модели). LOD — только выделенный сам. TXD проверяется по
    IDE списка «IDE для экспорта», игры (default.dat + gta*.dat), бокса и
    своим IDE моделей сцены, плюс по моделям сцены."""
    from ..core.img import ImgReader, read_directory
    from ..core.col_library import col_index
    from ..core.gta_dat import game_ide_paths
    from ..core.img_remove import remove_plan, scene_txd_users, txd_users
    from ..tools.model_utils import get_model_type
    from .map_link import LodIndex, ide_linked_file, lod_hd_names, lod_model_name

    s = context.scene.inu_settings
    lodix = LodIndex()
    # Модели сцены: их TXD, владельцы LOD, их IDE.
    dffs, lods, dff_by_base, owner_of, own_ides = [], [], {}, {}, []
    for o in context.scene.objects:
        if o.type != 'MESH' or not hasattr(o, 'inu'):
            continue
        mt, base = get_model_type(o)
        if not base:
            continue
        own = ide_linked_file(o)
        if own and own not in own_ides:
            own_ides.append(own)
        if mt == 'COL':
            # Без тега COL/SHA — модель без текстурного материала: её TXD ей
            # всё равно нужен.
            if o.inu.type not in ('COL', 'SHA') and (o.inu.txd_name or '').strip():
                dffs.append((base, o.inu.txd_name))
            continue
        if mt == 'LOD':
            lods.append((o, base))
            continue
        dffs.append((base, o.inu.txd_name))
        dff_by_base.setdefault(base.lower(), o)
        lodo = lodix.partner(o)
        if lodo is not None:
            owner_of.setdefault(lodo.name, (o, base))
    # По имени модели LOD: у копий (LODhouse.001) тот же владелец. Имя LOD —
    # для его модели (III/VC: по правилу игры, как Export to IMG его пишет).
    hd_of = lod_hd_names(context.scene.objects)
    owner_by_lod, lod_rows = {}, []
    for o, b in lods:
        lname = lod_model_name(o, b, hd=hd_of.get(id(o), ''))
        lod_rows.append((lname, o.inu.txd_name))
        if o.name in owner_of:
            owner_by_lod.setdefault(lname.lower(), owner_of[o.name])

    groups = {}          # (вид, имя модели) → [вид, имя, объекты]
    for o in objs:
        mt, base = get_model_type(o)
        if not base:
            continue
        kind = mt.lower()
        name = (lod_model_name(o, base, hd=hd_of.get(id(o), ''))
                if kind == 'lod' else base)
        groups.setdefault((kind, name.lower()), [kind, name, []])[2].append(o)

    sel = {o.name for o in objs}
    notes, parts, arch_of = [], [], {}
    for kind, name, group in groups.values():
        o = group[0]
        extra, fallback = {}, ''
        if kind == 'dff':
            extra['txd'] = (o.inu.txd_name or '').strip() or name
            lodo = lodix.partner(o)
            if lodo is not None and lodo.name not in sel:
                # LOD часто общий у нескольких моделей — только в список.
                extra['lod'] = lod_model_name(lodo, get_model_type(lodo)[1] or name,
                                              hd=hd_of.get(id(lodo), '') or name)
        elif kind == 'lod':
            dff, dff_base = owner_by_lod.get(name.lower(), (None, ''))
            fallback = dff.inu.img_target_file if dff else ''
            dff_txd = ((dff.inu.txd_name or '').strip() or dff_base) if dff else ''
            extra['txd'] = (o.inu.txd_name or '').strip() or dff_txd
        else:
            dff = dff_by_base.get(name.lower())
            fallback = dff.inu.img_target_file if dff else ''
        raws = [g.inu.img_target_file for g in group if g.inu.img_target_file]
        seen = set()
        for raw in raws or [fallback]:
            path = os.path.normpath(bpy.path.abspath(raw)) if raw else ''
            key = os.path.normcase(path)
            if key in seen:
                continue
            seen.add(key)
            if not path or not os.path.isfile(path):
                notes.append(T("«{0}»: не в IMG — нажмите «Проверить IMG»").format(o.name))
                continue
            parts.append(dict(kind=kind, arch=arch_of.setdefault(key, path),
                              name=name, **extra))

    names_by_arch, col_idx_by_arch = {}, {}
    for arch in dict.fromkeys(p['arch'] for p in parts):
        try:
            names = {}
            for e in read_directory(arch):
                names.setdefault(e.name.lower(), e.name)
            if any(p['arch'] == arch and p['kind'] != 'lod' for p in parts):
                with ImgReader(arch) as rd:
                    col_idx_by_arch[arch] = col_index(rd)
            names_by_arch[arch] = names
        except Exception as e:
            notes.append(f"{os.path.basename(arch)}: {e}")

    users, game_dats = {}, []
    if any(p.get('txd') and (p['txd'] + '.txd').lower() in names_by_arch.get(p['arch'], ())
           for p in parts):
        ides = [bpy.path.abspath(it.path) for it in s.gtatools_ide_sync_list if it.path]
        root = bpy.path.abspath(s.gtatools_game_root or '')
        if root and os.path.isdir(root):
            game_ides, game_dats = game_ide_paths(root)
            ides += game_ides
        if s.gtatools_ide_path:
            ides.append(bpy.path.abspath(s.gtatools_ide_path))
        users, bad = txd_users(ides + own_ides)
        if bad:
            notes.append(T("IDE не прочитаны: {0}").format(
                ", ".join(os.path.basename(p) for p in bad[:5])))
        for txd, models in scene_txd_users(
                dffs, [(n, txd, owner_by_lod.get(n.lower(), (None, ''))[1])
                       for n, txd in lod_rows]).items():
            users.setdefault(txd, set()).update(models)
    todo = remove_plan(parts, names_by_arch, col_idx_by_arch, users)
    for arch, t in todo.items():
        for name in t['missing']:
            notes.append(T("«{0}»: нет в {1} — нажмите «Проверить IMG»").format(
                name, os.path.basename(arch)))
    if not game_dats and any(e.lower().endswith('.txd')
                             for t in todo.values() for e in t['entries']):
        notes.insert(0, T("Папка игры не задана — TXD сверены только со сценой и списками IDE"))
    return todo, parts, list(dict.fromkeys(notes))


def _remove_lines(todo):
    """Строки окна Remove from IMG: что уйдёт из каждого архива, что остаётся."""
    lines = []
    for arch, t in todo.items():
        what = list(t['entries']) + [T("{0} (из {1})").format(", ".join(ms), lib)
                                     for lib, ms in t['libs'].items()]
        sub = ["    " + ", ".join(what[i:i + 3]) for i in range(0, len(what), 3)]
        for txd, who, n in t['kept_txd']:
            sub.append("    " + T("{0} оставлен — нужен {1}").format(
                txd, who + (f" +{n - 1}" if n > 1 else "")))
        for lod in t['kept_lod']:
            sub.append("    " + T("LOD «{0}» оставлен — выделите LOD, чтобы удалить").format(lod))
        if sub:
            lines += [os.path.basename(arch) + ":"] + sub
    return lines


class GTATOOLS_OT_remove_from_img(bpy.types.Operator):
    """Удалить выделенные модели из IMG — каждую из её архива (статус «В IMG»):
DFF, TXD — только если он больше никому не нужен (IDE игры и списков, модели
сцены), коллизию — записью из .col архива. LOD удаляется, только если выделен.
Перед удалением — список и вопрос"""
    bl_idname = "gtatools.remove_from_img"
    bl_label = "INU: Remove from IMG"
    bl_options = {'REGISTER'}

    # Не используется: архив у каждой модели свой (img_target_file). Оставлено
    # для совместимости — 🗑 в боксе всё ещё передаёт архив активной модели.
    target_img: StringProperty(default="", options={'HIDDEN'})

    _lines = []
    _notes = []

    def invoke(self, context, event):
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        todo, _parts, notes = _remove_plan(context, objs)
        if not any(t['entries'] or t['libs'] for t in todo.values()):
            for n in notes:
                self.report({'WARNING'}, n)
            if not notes:
                self.report({'WARNING'}, T("Файлы не найдены в IMG"))
            return {'CANCELLED'}
        # Заметки видны всегда (до «Удалить?»), режется только перечень.
        shown = notes[:5] + ([T("… ещё {0}").format(len(notes) - 5)]
                             if len(notes) > 5 else [])
        lines, room = _remove_lines(todo), 20 - len(shown)
        type(self)._lines = lines[:room] + (
            [T("… ещё {0}").format(len(lines) - room)] if len(lines) > room else [])
        type(self)._notes = shown
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=T("Будет удалено из архивов:"), **inu_icon(safe_icon('TRASH')))
        for line in type(self)._lines:
            col.label(text=line)
        if type(self)._notes:
            col.separator()
            for line in type(self)._notes:
                col.label(text=line, **inu_icon(safe_icon('ERROR')))
        col.separator()
        col.label(text=T("Удалить?"))

    def execute(self, context):
        from ..core.img_remove import remove_entries
        from ..tools.model_utils import get_model_type
        from .map_link import lod_hd_names, lod_model_name

        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        # План заново — файлы могли измениться, пока было открыто окно.
        todo, parts, notes = _remove_plan(context, objs)
        for n in notes:
            self.report({'WARNING'}, n)
        removed, errors, changed, cleared = [], [], set(), set()
        for arch, t in todo.items():
            if not (t['entries'] or t['libs']):
                continue
            done = []
            try:
                remove_entries(arch, t['entries'], t['libs'], done)
            except PermissionError:
                errors.append(T("Файл .img занят — закрой игру: {0}").format(
                    os.path.basename(arch)))
            except Exception as e:
                errors.append(f"{os.path.basename(arch)}: {e}")
            if not done:
                continue
            changed.add(_img_key(arch))
            gone = {d.lower() for d in done if isinstance(d, str)}
            removed += [d if isinstance(d, str) else
                        T("{0} (из {1})").format(", ".join(d[1]), d[0]) for d in done]
            cleared.update((_img_key(arch), p['name'].lower()) for p in parts
                           if p['arch'] == arch and p['kind'] != 'col'
                           and (p['name'] + '.dff').lower() in gone)
        # «Не в IMG» у всех копий моделей, чей DFF ушёл из ИХ архива.
        arch_keys = {k for k, _n in cleared}
        hd_of = lod_hd_names(context.scene.objects) if cleared else {}
        for o in (context.scene.objects if cleared else ()):
            if (o.type != 'MESH' or not hasattr(o, 'inu')
                    or _img_key(o.inu.img_target_file) not in arch_keys):
                continue
            mt, base = get_model_type(o)
            name = (lod_model_name(o, base, hd=hd_of.get(id(o), ''))
                    if mt == 'LOD' else base)
            if mt in ('DFF', 'LOD') and (_img_key(o.inu.img_target_file),
                                         (name or '').lower()) in cleared:
                o.inu.img_target_file = ''
        img_path = context.scene.inu_settings.gtatools_img_path
        if img_path and _img_key(img_path) in changed:
            _refresh_img_entries(context.scene, bpy.path.abspath(img_path))
        if removed:
            self.report({'INFO'}, f"IMG: {T('удалено')} {', '.join(removed)}")
        elif not errors and not notes:
            self.report({'WARNING'}, T("Файлы не найдены в IMG"))
        for e in errors:
            self.report({'ERROR'}, e)
        return {'FINISHED'} if removed else {'CANCELLED'}


class GTATOOLS_OT_verify_img_link(bpy.types.Operator):
    """Проверить, в каком IMG-архиве папки игры лежит DFF выделенных моделей,
и обновить статус «В IMG» (img_target_file). Не найдено ни в одном архиве →
статус станет «Не в IMG». Читает только оглавления архивов (быстро)"""
    bl_idname = "gtatools.verify_img_link"
    bl_label = "INU: Verify IMG"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.img import read_directory
        from ..tools.model_utils import get_model_type
        from .map_link import lod_hd_names, lod_model_name
        scn = context.scene

        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        # Собрать все .img: основной путь + рекурсивно по папке игры.
        img_paths = []
        _mp = bpy.path.abspath(scn.inu_settings.gtatools_img_path)
        if _mp and os.path.isfile(_mp):
            img_paths.append(_mp)
        game_root = bpy.path.abspath(scn.inu_settings.gtatools_game_root)
        if game_root and os.path.isdir(game_root):
            for dp, _dn, fns in os.walk(game_root):
                for f in fns:
                    if f.lower().endswith('.img'):
                        img_paths.append(os.path.join(dp, f))
        # Без повторов, в порядке загрузки игрой (как Extract / Import Map):
        # штамп — архив, из которого игра берёт модель (Export to IMG пишет
        # модель со своим архивом именно в него). Архив из панели — сразу
        # после архивов из .dat.
        from ..core.map_files import order_archives
        uniq = order_archives(img_paths, game_root,
                              extra=[_mp] if _mp and os.path.isfile(_mp) else [])
        if not uniq:
            self.report({'ERROR'},
                        T("Нет IMG: укажи архив или папку игры"))
            return {'CANCELLED'}

        # dff-имя (в нижнем регистре) → путь к архиву (первое совпадение).
        name_to_img = {}
        failed = []
        for p in uniq:
            try:
                for e in read_directory(p):
                    nm = e.name.lower()
                    if nm.endswith('.dff'):
                        name_to_img.setdefault(nm, p)
            except Exception:
                failed.append(os.path.basename(p))
                continue

        found = lost = 0
        hd_of = None
        for o in objs:
            _mt, base = get_model_type(o)
            if not base:
                base = o.name
            # LOD — своя модель IDE: его .dff под своим именем (LODhouse.dff;
            # III/VC — по правилу игры для его модели, как пишет Export to IMG).
            if _mt == 'LOD' and hd_of is None:
                hd_of = lod_hd_names(scn.objects)
            fname = (lod_model_name(o, base, hd=hd_of.get(id(o), ''))
                     if _mt == 'LOD' else base)
            src = name_to_img.get((fname + '.dff').lower())
            if src:
                o.inu.img_target_file = src
                found += 1
            else:
                # Архив не прочитан — модель может быть в нём: связь не снимать.
                if not failed:
                    o.inu.img_target_file = ''
                lost += 1
        self.report({'INFO'},
                    T("Проверка IMG: найдено {0}, не в архивах {1}").format(
                        found, lost))
        if failed:
            self.report({'WARNING'},
                        T("Не прочитаны (связи не сняты): {0}").format(
                            ", ".join(failed)))
        return {'FINISHED'}


class GTATOOLS_OT_rebuild_img(bpy.types.Operator):
    """Перестроить (компактировать) IMG-архив: убрать мёртвое место,
    оставшееся от перезаписей моделей (replace добавляет данные в конец,
    старый блок не освобождается). Файл заменяется атомарно."""
    bl_idname = "gtatools.rebuild_img"
    bl_label = "INU: Rebuild IMG"
    bl_options = {'REGISTER'}

    # Архив (пусто → gtatools_img_path). Кнопка в строке IMG передаёт
    # «В IMG» активной модели, иначе IMG из настроек (как в Max).
    target_img: StringProperty(default="", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        # classmethod не видит target_img — пускаем, если есть хоть одна цель.
        s = getattr(context.scene, 'inu_settings', None)
        if s and getattr(s, 'gtatools_img_path', ''):
            return True
        ao = context.active_object
        return bool(ao and getattr(getattr(ao, 'inu', None),
                                   'img_target_file', ''))

    def _img_path(self, context):
        s = context.scene.inu_settings
        return bpy.path.abspath(
            self.target_img or getattr(s, 'gtatools_img_path', '') or '')

    def invoke(self, context, event):
        img_path = self._img_path(context)
        if not img_path or not os.path.isfile(img_path):
            return self.execute(context)   # покажет ошибку
        # Вопрос с именем архива и числом записей: целью может оказаться
        # ванильный gta3.img из настроек, а Rebuild читает весь архив.
        try:
            from ..core.img import read_directory
            n = len(read_directory(img_path))
        except Exception:
            n = '?'
        msg = T("Сжать {0} (записей: {1}) — убрать мёртвое место от "
                "заменённых записей; записи и их порядок сохраняются").format(
                    os.path.basename(img_path), n)
        wm = context.window_manager
        try:
            return wm.invoke_confirm(self, event,
                                     title=T("Пересобрать IMG (компакт)"),
                                     message=msg, icon='WARNING')
        except TypeError:   # старый Blender: без title/message
            return wm.invoke_confirm(self, event)

    def execute(self, context):
        s = context.scene.inu_settings
        img_path = self._img_path(context)
        if not img_path or not os.path.isfile(img_path):
            self.report({'ERROR'}, T("Укажите существующий .img файл"))
            return {'CANCELLED'}
        try:
            from ..core.img import rebuild_img
            stats = rebuild_img(img_path)
        except PermissionError:
            self.report({'ERROR'}, T("Файл .img занят — закрой игру: {0}").format(
                os.path.basename(img_path)))
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Rebuild error: {e}")
            return {'CANCELLED'}
        saved_mb = stats['saved'] / (1024.0 * 1024.0)
        self.report({'INFO'}, T(
            "IMG перестроен: {0} записей, освобождено {1:.1f} МБ").format(
                stats['entries'], saved_mb))
        # Список записей в панели — только если пересобран архив из настроек
        # (refresh_img_list перекрыл бы отчёт своим «Файлов: N»).
        _main = bpy.path.abspath(getattr(s, 'gtatools_img_path', '') or '')
        if _main and (os.path.normcase(os.path.abspath(_main))
                      == os.path.normcase(os.path.abspath(img_path))):
            _refresh_img_entries(context.scene, img_path)
        return {'FINISHED'}


class GTATOOLS_OT_scan_ide_for_ipl(bpy.types.Operator):
    """Найти IDE: прочитать выбранный IPL и найти в указанной папке .ide-файлы,
    где определены его модели (по Model ID). Если папка — корень игры (есть
    data/gta.dat), берётся канонический список; иначе рекурсивный скан *.ide.
    Если модели из разных IDE — покажет список. Ничего не импортирует."""
    bl_idname = "gtatools.scan_ide_for_ipl"
    bl_label = "INU: Найти IDE по IPL"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.ipl import read_ipl
        from ..core.ide import find_ides_for_model_ids
        from ..core.gta_dat import list_ide_files
        s = context.scene.inu_settings
        ipl_paths = _ipl_paths_for_import(s)
        ide_root = bpy.path.abspath(s.gtatools_game_root)
        if not ipl_paths:
            self.report({'ERROR'}, T("Выберите IPL-файл"))
            return {'CANCELLED'}
        if not ide_root or not os.path.isdir(ide_root):
            self.report({'ERROR'}, T("Укажите папку с IDE"))
            return {'CANCELLED'}
        model_ids = set()
        for _ip in ipl_paths:
            try:
                model_ids |= {inst.model_id for inst in read_ipl(_ip).instances}
            except Exception:
                pass
        if not model_ids:
            context.scene['gtatools_found_ides'] = ""
            self.report({'WARNING'}, T("В IPL нет моделей"))
            return {'CANCELLED'}
        found = find_ides_for_model_ids(list_ide_files(ide_root), model_ids)
        # Список путей храним строкой (список строк в ID-property нельзя).
        context.scene['gtatools_found_ides'] = "\n".join(sorted(found.keys()))
        # Round-trip: наполняем список IDE «Синхронизации»/Экспорта теми же
        # найденными IDE, чтобы обратный экспорт писал каждую модель в её IDE.
        coll = context.scene.inu_settings.gtatools_ide_sync_list
        coll.clear()
        for _p in sorted(found.keys()):
            coll.add().path = _p
        covered = len({mid for ids in found.values() for mid in ids})
        self.report(
            {'INFO'},
            T("Найдено IDE: {0} · моделей покрыто {1}/{2}").format(
                len(found), covered, len(model_ids)))
        return {'FINISHED'}


def _find_img_files_in_dir(root):
    """Все .img архивы в папке `root` (рекурсивно). Возвращает list путей."""
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith('.img'):
                out.append(os.path.join(dirpath, fn))
    return out


class GTATOOLS_OT_scan_img_for_ipl(bpy.types.Operator):
    """Найти IMG: прочитать выбранный IPL и найти в папке игры все .img архивы,
    в которых реально лежат DFF его моделей. Модели кастомной карты часто
    разложены по нескольким .img (напр. maps/RESOURCES) — импорт затем тянет их
    из всех найденных архивов, а не только из основного. Ничего не импортирует."""
    bl_idname = "gtatools.scan_img_for_ipl"
    bl_label = "INU: Найти IMG по IPL"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.ipl import read_ipl
        from ..core.img import read_directory
        s = context.scene.inu_settings
        ipl_paths = _ipl_paths_for_import(s)
        root = bpy.path.abspath(s.gtatools_game_root)
        if not ipl_paths:
            self.report({'ERROR'}, T("Выберите IPL-файл"))
            return {'CANCELLED'}
        if not root or not os.path.isdir(root):
            self.report({'ERROR'}, T("Укажите папку игры"))
            return {'CANCELLED'}
        want = set()
        unnamed = set()       # ID строк без имени (двоичный IPL)
        for _ip in ipl_paths:
            try:
                for inst in read_ipl(_ip).instances:
                    if inst.model_name:
                        want.add(inst.model_name.lower() + '.dff')
                    elif inst.model_id > 0:
                        unnamed.add(inst.model_id)
            except Exception:
                pass
        if unnamed:
            # Двоичный IPL: имён в файле нет — берём из IDE по ID, как импорт:
            # бокс IDE (иначе IDE папки игры), затем «Найти IDE»; первый
            # источник побеждает.
            from ..core.ide import read_ide
            from ..core.gta_dat import list_ide_files
            ide_path = bpy.path.abspath(s.gtatools_ide_path)
            srcs = ([ide_path] if ide_path and os.path.isfile(ide_path)
                    else list(list_ide_files(root)))
            srcs += [p for p in (context.scene.get('gtatools_found_ides', '')
                                 or '').split('\n') if p and os.path.isfile(p)]
            names = {}
            for p in srcs:
                try:
                    ide = read_ide(p)
                except Exception:
                    continue
                for o in list(ide.objects) + list(ide.anims):
                    names.setdefault(o.model_id, o.model_name)
            want |= {names[i].lower() + '.dff' for i in unnamed if names.get(i)}
        if not want:
            context.scene['gtatools_found_imgs'] = ""
            self.report({'WARNING'}, T("В IPL нет моделей"))
            return {'CANCELLED'}

        found = []            # пути .img, где нашлась хоть одна нужная модель
        covered = set()       # покрытые dff-имена (по всем архивам)
        for img_path in _find_img_files_in_dir(root):
            try:
                names = {e.name.lower() for e in read_directory(img_path)}
            except Exception:
                continue
            hit = want & names
            if hit:
                found.append(img_path)
                covered |= hit
        # Список путей храним строкой (список строк в ID-property нельзя).
        context.scene['gtatools_found_imgs'] = "\n".join(found)
        self.report(
            {'INFO'},
            T("Найдено IMG: {0} · моделей покрыто {1}/{2}").format(
                len(found), len(covered), len(want)))
        return {'FINISHED'}


class GTATOOLS_OT_open_url(bpy.types.Operator):
    """Открыть сайт в браузере (обёртка над wm.url_open с нормальным тултипом)."""
    bl_idname = "gtatools.open_url"
    bl_label = "INU: Открыть сайт"
    bl_options = {'REGISTER'}

    url: StringProperty()
    tip: StringProperty()

    @classmethod
    def description(cls, context, properties):
        return properties.tip or T("Открыть сайт в браузере")

    def execute(self, context):
        if not self.url:
            return {'CANCELLED'}
        bpy.ops.wm.url_open(url=self.url)
        return {'FINISHED'}


class GTATOOLS_OT_open_text_file(bpy.types.Operator):
    """Открыть файл (IDE/IPL) в текстовом редакторе. По умолчанию — во ВНЕШНЕМ
    редакторе ОС (как двойной клик в проводнике). Галочкой в настройках аддона
    «Открывать IPL/IDE в редакторе Blender» можно переключить на встроенный
    текст-редактор Blender (в новом окне)."""
    bl_idname = "gtatools.open_text_file"
    bl_label = "INU: Открыть в текст-редакторе"
    bl_options = {'REGISTER'}

    filepath: StringProperty()

    def execute(self, context):
        path = bpy.path.abspath(self.filepath) if self.filepath else ''
        if not path or not os.path.isfile(path):
            self.report({'ERROR'}, T("Файл не найден"))
            return {'CANCELLED'}
        # Настройка аддона: внешний редактор ОС или встроенный в Blender.
        addon_key = __package__.split('.')[0]
        _addon = context.preferences.addons.get(addon_key)
        use_blender = bool(getattr(getattr(_addon, 'preferences', None),
                                   'open_text_in_blender', False))
        if use_blender:
            return self._open_in_blender(context, path)
        # Открыть внешним приложением ОС (ассоциация с текстовым редактором —
        # Блокнот и т.п.), как двойной клик в проводнике. Через блендеровский
        # wm.path_open — без subprocess, проходит store-compliance.
        try:
            bpy.ops.wm.path_open(filepath=path)
        except Exception as e:                        # noqa: BLE001
            self.report({'ERROR'}, T("Не удалось открыть: {0}").format(e))
            return {'CANCELLED'}
        return {'FINISHED'}

    def _open_in_blender(self, context, path):
        """Загрузить файл во встроенный текст-редактор Blender и показать его —
        в существующей области TEXT_EDITOR, иначе в новом окне."""
        try:
            _want = os.path.normcase(os.path.abspath(path))
            text = None
            for t in bpy.data.texts:
                tp = bpy.path.abspath(t.filepath) if t.filepath else ''
                if tp and os.path.normcase(os.path.abspath(tp)) == _want:
                    text = t
                    break
            if text is None:
                text = bpy.data.texts.load(path)
            # Показать: сначала ищем уже открытый текст-редактор в этом окне.
            for area in context.screen.areas:
                if area.type == 'TEXT_EDITOR':
                    area.spaces.active.text = text
                    return {'FINISHED'}
            # Нет открытого — новое окно, его большую область в TEXT_EDITOR.
            bpy.ops.wm.window_new()
            win = context.window_manager.windows[-1]
            area = max(win.screen.areas, key=lambda a: a.width * a.height)
            area.type = 'TEXT_EDITOR'
            area.spaces.active.text = text
        except Exception as e:                        # noqa: BLE001
            self.report({'ERROR'},
                        T("Не удалось открыть в Blender: {0}").format(e))
            return {'CANCELLED'}
        return {'FINISHED'}


def _plan_txd_buckets(groups, txd_for, lod_src_of, lod_txd_of):
    """[(base, models)] → {имя TXD: [объекты]}, один .txd на корзину.
    Модель — в TXD из окна (txd_for), текстуры LOD-а — в TXD LOD-а
    (lod_txd_of; заглушка / нет LOD → lod_src_of даёт None). Имена записей
    IMG без регистра: House и house — одна корзина."""
    buckets = defaultdict(list)
    names = {}
    for base, models in groups:
        pairs = []
        if models['DFF'] is not None:
            pairs.append((txd_for(base), models['DFF']))
        lod = lod_src_of(base, models)
        if lod is not None:
            pairs.append((lod_txd_of(base, models, lod), lod))
        for name, obj in pairs:
            name = names.setdefault(name.lower(), name)
            if all(o is not obj for o in buckets[name]):
                buckets[name].append(obj)
    return buckets


def _txd_writeback(buckets, written):
    """[(объект, имя TXD)]: чьи текстуры легли в записанный TXD, а
    inu.txd_name другой. Корзина не записана (нет текстур, ошибка) — никого."""
    out = []
    for name, objs in buckets.items():
        if (name + '.txd').lower() not in written:
            continue
        for o in objs:
            inu = getattr(o, 'inu', None)
            if inu is not None and (getattr(inu, 'txd_name', '') or '') != name:
                out.append((o, name))
    return out


def _export_routes(context, groups, want=None, target_img=''):
    """Export to IMG: ({архив: [base]}, [base без архива]). Модель со своим
    IMG (img_target_file) — всегда в него: игра берёт первую копию (SA:
    gta3 → gta_int → IMG из gta.dat; III/VC: CDIMAGE раньше gta3), запись
    в другой архив её не заменит. Модели без своего — в выбранный в окне
    архив, иначе в IMG из настроек (пусто — target_img кнопки строки IMG).
    Только пути: каталоги архивов не читаются (годится и для draw)."""
    from ..core.img_routing import route_groups
    s = context.scene.inu_settings
    choice = getattr(s, 'gtatools_export_img_target', 'SELF') or 'SELF'
    cands = [choice] if choice != 'SELF' else [s.gtatools_img_path, target_img]
    default = next((p for p in (bpy.path.abspath(c) for c in cands if c)
                    if os.path.isfile(p)), '')
    own = {}
    for base, models in groups.items():
        if want is None or want(base):
            src = models['DFF'] or models['LOD']
            tf = getattr(getattr(src, 'inu', None), 'img_target_file', '') or ''
            own[base] = bpy.path.abspath(tf) if tf else ''
    return route_groups(own, default)


def _img_report_path(blend_path):
    """_export_report.txt — рядом с .blend, а не в папке models игры.
    Сцена не сохранена — None: итог только в строке отчёта."""
    if not blend_path:
        return None
    return os.path.join(os.path.dirname(blend_path), "_export_report.txt")


def _export_lod_routes(context, groups, routes, want, lod_src=None):
    """Archive of each enabled LOD (including a scene LOD not selected)."""
    from ..core.img_routing import lod_routes
    from ..tools.model_utils import find_related_models
    plan = {e.model_name: e for e in context.window_manager.gtatools_txd_export_plan}
    own = {}
    for base, models in groups.items():
        if not want(base):
            continue
        if lod_src is not None:
            src = lod_src(base, models)
        else:
            entry = plan.get(base)
            src = (bpy.data.objects.get(entry.lod_name)
                   if entry is not None and entry.lod_found else None)
            src = src or models['LOD'] or find_related_models(base).get('LOD')
        tf = (getattr(getattr(src, 'inu', None), 'img_target_file', '') or ''
              if src is not models['DFF'] else '')
        own[base] = bpy.path.abspath(tf) if tf else ''
    return lod_routes(own, {b: a for a, bases in routes.items() for b in bases})


# Export to IMG: модели (base), не легшие ни в один архив (нет архива /
# архив отказал). All → IMG тогда не пишет IDE/IPL: строки на модели, которых
# нет в IMG. Заполняется заново каждым execute.
_export_unwritten = set()

# Export to IMG: итог записавшего прогона — {'summary': (уровень, текст),
# 'mobile': текст или None}. All → IMG зовёт оператор через bpy.ops, а отчёты
# вложенного оператора Blender в строку состояния / Info не пускает (только в
# консоль) — Export All повторяет итог сам.
_export_final = {}


def _col_prim_index(objects):
    """{модель (lower): [(пустышка, суффикс .NNN или '')]} — сферы/боксы
    коллизии сцены: EMPTY с видом SPHERE/CUBE и именем из импорта COL
    («<модель>_sphere_N» / «<модель>_box_N», col_import). В систему COL-меша
    их переводит build_col_model."""
    import re
    idx = {}
    for o in objects:
        if (getattr(o, 'type', None) != 'EMPTY' or getattr(
                o, 'empty_display_type', '') not in ('SPHERE', 'CUBE')):
            continue
        m = re.fullmatch(r'(.+)_(?:sphere|box)_\d+(\.\d+)?', o.name, re.IGNORECASE)
        if m:
            idx.setdefault(m.group(1).lower(), []).append((o, m.group(2) or ''))
    return idx


def _col_prims_of(idx, base, col_name=''):
    """Сферы/боксы модели base из _col_prim_index. Суффикс .NNN — только как
    у её COL-меша (x_COL.001 → x_sphere_0.001): второй импорт той же COL не
    удваивает сферы; без меша — только без суффикса."""
    import re
    m = re.search(r'\.\d+$', col_name or '')
    want = m.group(0) if m else ''
    return [o for o, suf in idx.get(base.lower(), ()) if suf == want]


def _col_lib_put(data, name, make):
    """Запись модели name в .col архива: есть — заменена на месте (make
    получает её model_id), нет — дописана в конец. Чужие записи — байт в
    байт. Паддинг сектора за последней записью отброшен (col_splice): VC не
    грузит библиотеку с хвостом ≥2056 байт, а запись за паддингом игра не
    видит. → (байты, сколько записей заменено)."""
    from ..core.col_library import col_splice
    out, n, _left = col_splice(data, name, make)
    return (out if n else out + make(0)), n


def fill_export_plan(context, groups, *, want_lod=True, want_col=True,
                     lod_stub=False, col_stub=False):
    """Строки окна Export to IMG (wm.gtatools_txd_export_plan) по группам
    моделей. Имя TXD — obj.inu.txd_name, иначе имя модели; LOD/COL — из
    группы выделения, иначе по имени по сцене. Найденные LOD/COL включены
    (want_lod / want_col), заглушки — только при lod_stub / col_stub. Окно
    зовёт с умолчаниями, All → IMG (Export All) — с галками своего окна."""
    from ..tools.model_utils import find_related_models
    wm = context.window_manager
    wm.gtatools_txd_export_plan.clear()
    prim_idx = _col_prim_index(context.scene.objects)
    for base_name, models in groups.items():
        entry = wm.gtatools_txd_export_plan.add()
        entry.model_name = base_name
        entry.include = True
        src = models['DFF'] or models['LOD']
        prefilled = ''
        if src is not None and hasattr(src, 'inu'):
            prefilled = getattr(src.inu, 'txd_name', '') or ''
        entry.txd_name = prefilled or base_name
        # Подтянуть LOD/COL по всей сцене (не только среди выделенных):
        # сначала из группы выделения, иначе поиск по имени по сцене.
        related = find_related_models(base_name)
        lod_obj = models.get('LOD') or related.get('LOD')
        col_obj = models.get('COL') or related.get('COL')
        # Сферы/боксы (x_sphere_0, x_box_0 из импорта COL) — тоже
        # коллизия модели, и без COL-меша.
        prims = _col_prims_of(prim_idx, base_name,
                              col_obj.name if col_obj else '')
        entry.lod_found = bool(lod_obj)
        entry.col_found = bool(col_obj) or bool(prims)
        entry.col_prims = len(prims)
        entry.lod_name = lod_obj.name if lod_obj else ""
        entry.col_name = col_obj.name if col_obj else ""
        # Найденные LOD/COL — включены; заглушки (копия модели под
        # LOD-именем, пустая COL) — только по явной галке: иначе они
        # затирают настоящие LOD/COL, лежащие в архиве. Сферы/боксы без
        # COL-меша — тоже по галке: без меша они пишутся по сырому
        # location, а стоящие на месте модели в мире (импорт из IMG)
        # увели бы её запись в библиотеке за километры.
        entry.inc_lod = bool(want_lod and (lod_stub or entry.lod_found))
        entry.inc_col = bool(want_col and (col_stub or bool(col_obj)))
    wm.gtatools_txd_export_plan_index = 0


class GTATOOLS_OT_export_to_img(bpy.types.Operator):
    """Экспортировать DFF + TXD + COL прямо в .img архив"""
    bl_idname = "gtatools.export_to_img"
    bl_label = "INU: Export to IMG"
    bl_options = {'REGISTER'}

    shared_txd: BoolProperty(
        name=T("Общий TXD"),
        description=T("Пакует все текстуры в один .txd. Выключено — один .txd на каждую уникальную строку txd_name из списка ниже"),
        default=False,
    )
    shared_txd_name: StringProperty(
        name=T("Имя общего TXD"),
        description=T("Имя .txd файла без расширения"),
        default="textures",
    )
    # Архив для моделей без своего IMG, если в настройках пусто (кнопка
    # строки IMG передаёт архив активной модели). См. _export_routes.
    target_img: StringProperty(default="", options={'HIDDEN', 'SKIP_SAVE'})
    # All → IMG (Export All): его галки DFF / TXD / «Пустая коллизия». Не
    # запоминаются (SKIP_SAVE) — иначе кнопка Export на панели и это окно
    # молча перестали бы писать DFF / TXD.
    skip_dff: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    skip_txd: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    empty_col: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    rebuild_after: BoolProperty(
        name=T("Пересобрать после экспорта"),
        description=T("После записи сжать (компактнуть) IMG-архив — убрать мёртвое место от старых версий моделей"),
        default=False,
    )

    def invoke(self, context, event):
        from ..tools.model_utils import find_all_selected_model_groups

        groups = find_all_selected_model_groups()
        if not groups:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        # Архив — у каждой модели свой (_export_routes); выбор в списке
        # окна (запомненный) касается только моделей без своего IMG.
        # Отказ — только если архив не нашла ни одна модель.
        if not _export_routes(context, groups, target_img=self.target_img)[0]:
            self.report({'ERROR'}, T("Укажите путь к .img архиву"))
            return {'CANCELLED'}

        # Pre-fill the dialog's shared-TXD widgets from the scene-level
        # unified toggle. Users configure once in the Unified Export
        # panel ("Общий TXD" + name); the dialog remembers that state
        # without them having to tick it again here. Свойства Export All —
        # в inu_settings (на самой сцене их нет).
        self.shared_txd = bool(getattr(
            context.scene.inu_settings, 'gtatools_export_all_txd_shared', False))
        self.shared_txd_name = getattr(
            context.scene.inu_settings, 'gtatools_export_all_txd_shared_name',
            'textures') or 'textures'

        # Populate the WindowManager TXD plan collection. Pre-fill each row
        # with obj.inu.txd_name if set, otherwise fall back to base_name —
        # that matches the game's default "model and its TXD share a name".
        wm = context.window_manager
        fill_export_plan(context, groups)

        return wm.invoke_props_dialog(self, width=460)

    def draw(self, context):
        from ..tools.model_utils import find_all_selected_model_groups
        layout = self.layout
        wm = context.window_manager
        scn = context.scene

        # Архив для моделей без своего IMG: «IMG из настроек» или .img из
        # папки игры. Модель со своим IMG пишется в него при любом выборе —
        # раскладка по архивам в рамке, куда идёт модель — в её строке DFF.
        layout.prop(scn.inu_settings, "gtatools_export_img_target",
                    text=T("IMG для моделей без своего"))
        plan = {e.model_name: e for e in wm.gtatools_txd_export_plan}
        groups = find_all_selected_model_groups()
        routes, no_arch = _export_routes(
            context, groups,
            want=lambda b: b not in plan or plan[b].include
            or plan[b].inc_lod or plan[b].inc_col,
            target_img=self.target_img)
        dest = {b: os.path.basename(a) for a, bs in routes.items() for b in bs}
        lod_dest, no_lod_arch = _export_lod_routes(
            context, groups, routes, lambda b: b in plan and plan[b].inc_lod)
        info = layout.box()
        for arch, bases in routes.items():
            info.label(text=f"{os.path.basename(arch)} — {T('Моделей:')} {len(bases)}",
                       **inu_icon(safe_icon('PACKAGE')))
        if no_arch:
            info.label(text=T("Без IMG-архива: {0} — выберите архив выше").format(
                len(no_arch)), **inu_icon(safe_icon('ERROR')))
        info.label(text=T("Модель со своим IMG пишется в него: игра берёт первую копию"),
                   **inu_icon(safe_icon('INFO')))

        # Format pick moved here from the main panel — same scene
        # props the «To folder» path uses, so toggling here also
        # affects the next folder export and vice-versa.
        # Общий TXD (упаковка всех текстур в один .txd) — общее для всех.
        row = layout.row(align=True)
        row.prop(self, "shared_txd")
        sub = row.row(align=True)
        sub.active = self.shared_txd
        sub.prop(self, "shared_txd_name", text="")

        # Иерархия по каждой модели: DFF (галочка + имя TXD), под ним с
        # отступом — LOD и COL, каждая со своей галочкой. Найденные в сцене
        # LOD/COL — включены; заглушки (LOD = копия основной модели, COL =
        # пустая габаритная) — выключены, только по явной галке.
        layout.label(text=T("Что экспортировать:"))
        for entry in wm.gtatools_txd_export_plan:
            mb = layout.box().column(align=True)
            r = mb.row(align=True)
            r.prop(entry, "include", text="")
            rs = r.row(align=True)
            rs.active = entry.include
            _to = dest.get(entry.model_name) or (
                T("нет архива") if entry.model_name in no_arch else "")
            rs.label(text="DFF: " + (entry.model_name or "?")
                     + (f"  → {_to}" if _to else ""),
                     **inu_icon(safe_icon('MESH_DATA')))
            if not self.shared_txd:
                rs.prop(entry, "txd_name", text="",
                        **inu_icon(safe_icon('TEXTURE')))
            # LOD (с отступом).
            r2 = mb.row(align=True)
            r2.separator(factor=2.5)
            r2.prop(entry, "inc_lod", text="")
            rs2 = r2.row(align=True)
            rs2.active = entry.inc_lod
            _lod_to = os.path.basename(lod_dest.get(entry.model_name, '')) or (
                T("нет архива") if entry.model_name in no_lod_arch else '')
            rs2.label(
                text=(("LOD: " + entry.lod_name) if entry.lod_found
                      else T("LOD: основная модель (заглушка)"))
                     + (f"  → {_lod_to}" if _lod_to else ''),
                **inu_icon(safe_icon('MOD_DECIM')))
            # COL (с отступом).
            r3 = mb.row(align=True)
            r3.separator(factor=2.5)
            r3.prop(entry, "inc_col", text="")
            rs3 = r3.row(align=True)
            rs3.active = entry.inc_col
            _prims = (T("сферы/боксы ({0})").format(entry.col_prims)
                      if entry.col_prims else "")
            rs3.label(
                text=("COL: " + " + ".join(p for p in (entry.col_name, _prims) if p))
                if entry.col_found else T("COL: пустая заглушка"),
                **inu_icon(safe_icon('MESH_CUBE')))

        layout.separator()
        layout.prop(self, "rebuild_after",
                    **inu_icon(safe_icon('FILE_REFRESH')))

    def execute(self, context):
        from ..core.img import ImgWriter, ImgReader
        from ..core.dff import GTA_SA_VERSION
        from ..core.col import write_col
        from ..core.model_classify import lod_has_own_txd
        from ..core.txd import split_txd_sections
        from ..tools.model_utils import find_all_selected_model_groups
        from ..tools.txd_export import export_txd, update_txd
        from .dff_export import build_dff_clump, _uv_anim_dropped_names
        from .col_export import build_col_model, export_col_library, audit_col
        from .map_link import lod_hd_names, lod_model_name, lod_name_note, new_lod_name

        model_groups = find_all_selected_model_groups()
        if not model_groups:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        # III/VC: модель каждого LOD сцены — имя LOD по правилу игры и без
        # модели в выделении (как Add to IDE).
        lod_hd = lod_hd_names(context.scene.objects)
        lod_notes = {}      # имя LOD → почему игра его не свяжет ('' — свяжет)

        # Что экспортировать теперь решают ПОЭЛЕМЕНТНЫЕ галочки диалога
        # (иерархия DFF → LOD/COL по каждой модели), а не глобальные тумблеры.
        # DFF+TXD идут по `include`; LOD по `inc_lod` (нет LOD в сцене → копия
        # основной модели); COL по `inc_col` (нет COL → пустая габаритная).
        col_library = bool(getattr(context.scene.inu_settings, 'gtatools_export_all_col_library', False))
        col_library_name = getattr(context.scene.inu_settings, 'gtatools_export_all_col_library_name', '') or 'collision'
        backend = getattr(context.scene.inu_settings, 'gtatools_dxt_backend', 'numpy')

        wm = context.window_manager
        plan_by_name = {}
        active_main = active_lod = None   # set after checking every archive
        for entry in wm.gtatools_txd_export_plan:
            plan_by_name[entry.model_name] = entry

        def _plan_entry(base):
            return plan_by_name.get(base)

        def _is_included(base):
            # DFF (и TXD) модели включены.
            e = _plan_entry(base)
            return (e.include if e is not None else True) and (
                active_main is None or base in active_main)

        def _inc_lod(base):
            e = _plan_entry(base)
            return bool(e is not None and e.inc_lod) and (
                active_lod is None or base in active_lod)

        def _inc_col(base):
            e = _plan_entry(base)
            return bool(e is not None and e.inc_col) and (
                active_main is None or base in active_main)

        def _want_group(base):
            # Группу вообще обрабатываем, если включена хоть одна её часть.
            return _is_included(base) or _inc_lod(base) or _inc_col(base)

        def _lod_src(base, models):
            # Объект-источник LOD: найденный в сцене LOD, иначе — основная
            # модель (пишем её копию под LOD-именем, как «заглушку»).
            e = _plan_entry(base)
            if e is not None and e.lod_found and e.lod_name:
                obj = bpy.data.objects.get(e.lod_name)
                if obj is not None:
                    return obj
            return models['LOD'] or models['DFF']

        _lod_names = {}     # база → имя LOD: считается один раз за экспорт

        def _lod_file(base, models):
            # Имя LOD в IMG: настоящее имя найденного LOD (xyz_lod,
            # tatar_str_1LOD — как map_link.lod_model_name); заглушка из
            # основной модели — LOD<база>. В III/VC — по правилу игры для
            # модели (house → LODse), как Add to IDE, если имя не занято
            # другой моделью (map_link.lod_name_taken — обход всей сцены,
            # поэтому один раз на модель).
            if base in _lod_names:
                return _lod_names[base]
            src = _lod_src(base, models)
            if src is not None and src is not models['DFF']:
                hd = base if models['DFF'] else lod_hd.get(id(src), '')
                name = lod_model_name(src, base, hd=hd)
            else:
                src, hd = None, base
                name = new_lod_name(base, base)
            if name not in lod_notes:
                lod_notes[name] = lod_name_note(src, name, hd)
            _lod_names[base] = name
            return name

        def _col_src(base, models):
            # Объект-источник COL (или None → пустая габаритная заглушка).
            if self.empty_col:   # «Пустая коллизия» All → IMG — у всех
                return None
            e = _plan_entry(base)
            if e is not None and e.col_found and e.col_name:
                obj = bpy.data.objects.get(e.col_name)
                if obj is not None:
                    return obj
            return models['COL']

        def _txd_for(base):
            e = _plan_entry(base)
            if self.shared_txd:
                return (self.shared_txd_name or 'textures').strip() or 'textures'
            if e is not None and e.txd_name.strip():
                return e.txd_name.strip()
            return base

        _lod_off_layer = []

        def _lod_tex_src(base, models):
            # Чьи текстуры LOD-а идут в TXD: LOD, который пишется (найден в
            # сцене, не обязательно выделен), иначе выделенный LOD. Заглушка
            # (копия модели) — нет: её текстуры и так в TXD модели.
            src = _lod_src(base, models) if _inc_lod(base) else models['LOD']
            if src is None or src is models['DFF']:
                return None
            if context.view_layer.objects.get(src.name) is None:
                _lod_off_layer.append(src.name)   # не выделить → текстур не собрать
                return None
            return src

        def _lod_txd(base, models, src):
            # Свой TXD LOD-а (lanlod при lanroad модели) остаётся, если он
            # правда свой; пустой / тот же, что у модели, — TXD из окна, как
            # в общем режиме и у группы из одного LOD (окно — из его TXD).
            dff = models['DFF']
            if self.shared_txd or dff is None:
                return _txd_for(base)
            own = (getattr(getattr(src, 'inu', None), 'txd_name', '') or '').strip()
            dff_txd = (getattr(getattr(dff, 'inu', None), 'txd_name', '')
                       or '').strip() or base
            return own if lod_has_own_txd(own, dff_txd) else _txd_for(base)

        # Каждая модель — в свой архив (_export_routes): свой IMG — всегда,
        # без своего — выбранный в окне / из настроек. Модели без архива —
        # строкой в отчёте, остальные пишутся.
        routes, no_arch = _export_routes(context, model_groups, _want_group,
                                         self.target_img)
        main_arch = {b: a for a, bases in routes.items() for b in bases}
        lod_arch, no_lod_arch = _export_lod_routes(
            context, model_groups, routes,
            lambda b: _inc_lod(b) or (_is_included(b) and not self.skip_txd
                                     and model_groups[b]['LOD'] is not None), _lod_src)
        # LOD-only archives take the same format / writable pre-check as HD.
        for a in lod_arch.values():
            routes.setdefault(a, [])
        _export_unwritten.clear()
        _export_unwritten.update(no_arch)
        _export_unwritten.update(no_lod_arch)
        if no_arch and not routes:
            self.report({'ERROR'}, T("Укажите путь к .img архиву"))
            return {'CANCELLED'}
        _routed = {b for bs in routes.values() for b in bs} | set(lod_arch)
        model_groups = {b: m for b, m in model_groups.items() if b in _routed}

        # Корзины TXD — один раз: для проверки имён, прогресса, чтения
        # прежних TXD архива и записи.
        txd_buckets = _plan_txd_buckets(
            [(b, m) for b, m in model_groups.items()
             if _is_included(b) and not self.skip_txd and (m['DFF'] or m['LOD'])],
            _txd_for, _lod_tex_src, _lod_txd)

        # #3: GTA SA IMG directory name field is 24 bytes, but the game reads
        # it as a C-string and force-terminates name[23]='\0' (CdDirectory) —
        # so the USABLE max is 23 chars: exactly-24 loses its last char (.dff
        # → .df) and no longer matches the IDE/IPL reference → invisible
        # model. Note a stub LOD name is 'LOD'+base+'.dff' (= base + 7 chars),
        # so it overflows first. Non-ASCII names (Cyrillic etc.) are rejected
        # by the writer too. Validate up front with the writer's own
        # predicate — before txd_name / progress bar are touched — and refuse
        # the whole export rather than write a half-updated archive. (Same
        # 23+NUL pattern as map_lint.py.)
        from ..core.img import _check_entry_name
        _bad_names = []
        for _bn, _models in model_groups.items():
            if not _want_group(_bn):
                continue
            _names = []
            if _is_included(_bn) and not self.skip_dff and _models['DFF']:
                _names.append(_bn + '.dff')
            if _inc_lod(_bn):
                _names.append(_lod_file(_bn, _models) + '.dff')
            if not col_library and _inc_col(_bn):
                _names.append(_bn + '.col')
            if col_library and _inc_col(_bn):
                _names.append(col_library_name + '.col')
            for _nm in _names:
                try:
                    _check_entry_name(_nm)
                except ValueError:
                    _bad_names.append(_nm)
        for _nm in txd_buckets:   # TXD модели и свой TXD LOD-а
            try:
                _check_entry_name(_nm + '.txd')
            except ValueError:
                _bad_names.append(_nm + '.txd')
        if _bad_names:
            _bad_names = sorted(set(_bad_names))
            self.report({'ERROR'}, T(
                "Имя для IMG длиннее 23 символов или не ASCII — игра его не "
                "найдёт: {0}. Переименуй модель / TXD.").format(
                    ", ".join(_bad_names[:8])
                    + ("…" if len(_bad_names) > 8 else "")))
            return {'CANCELLED'}

        # Формат архива (VER1 .img+.dir / VER2) — из самого файла, а не из
        # игры сцены: иначе SA-архив в III/VC-сцене писался бы как VER1
        # (новые записи — в лишний .dir, игра их не видит), а VC-архив в
        # SA-сцене ронял бы экспорт. DFF/COL при этом пишутся под игру
        # сцены, а архив другой игры их не прочитает (VC берёт из IMG только
        # COLL — re-VC FileLoader.cpp:229, RW 3.4 не читает 3.6) → отказ.
        from ..core import game_versions as gv
        from ..core.img import (create_img, detect_img_version, read_directory,
                                IMG_VERSION_2, _sibling_dir_path)
        _scene_game = gv.game_of_scene(context.scene)
        _want_ver = gv.profile_for(_scene_game).img_version
        # По каждому архиву. Не прошёл (занят / не IMG / другой игры) — его
        # модели пропускаются строкой в отчёте, остальные архивы пишутся.
        base_txd, arch_names, arch_fail = {}, {}, []
        # архив → {модель (lower): [.col с её записью]}, {.col (lower): байты}
        col_idx, lib_bytes = {}, {}
        # Маршруты до отсева: общий TXD / библиотека COL учитывают и модели
        # пропущенных архивов (_targets) — иначе рядом ляжет неполная копия.
        _all_routes, _all_groups = dict(routes), model_groups
        for img_path in list(routes):
            _err = None
            try:
                # Пустой файл без .dir — ещё не архив: размечаем под игру сцены.
                if (os.path.getsize(img_path) == 0
                        and not os.path.isfile(_sibling_dir_path(img_path))):
                    create_img(img_path, version=_want_ver)
                # Ни шапки VER2, ни .dir рядом (VC-архив без своего .dir, не
                # IMG) — формат не определить: ошибкой, а не «VER2 (SA)» ниже.
                arch_names[img_path] = {
                    e.name.lower() for e in read_directory(img_path)}
                # Прежние TXD архива — для слияния в цикле TXD ниже.
                base_txd[img_path] = {}
                with ImgReader(img_path) as _rd:
                    for _n in txd_buckets:
                        _b = _rd.read(_n + '.txd')
                        if _b:
                            base_txd[img_path][_n.lower()] = _b
                    # COL модели — туда, где её запись уже лежит (своя
                    # библиотека архива): где чья и байты этих .col, плюс
                    # библиотека из Export All — для дописывания.
                    if any(_inc_col(_b) for _b in routes[img_path]):
                        from ..core.col_library import col_index
                        _idx = col_idx[img_path] = col_index(_rd)
                        _need = {_en for _b in routes[img_path] if _inc_col(_b)
                                 for _en in _idx.get(_b.lower(), [])}
                        if col_library:
                            _need.add(col_library_name + '.col')
                        else:   # свой <модель>.col с чужими записями
                            _need |= {_b + '.col' for _b in routes[img_path]
                                      if _inc_col(_b) and (_b + '.col').lower()
                                      in arch_names[img_path]}
                        lib_bytes[img_path] = {
                            _en.lower(): _rd.read(_en) or b'' for _en in _need}
                # Проба записи сразу: запущенная игра даёт читать, но не
                # писать — иначе «занят» выяснится после сборки DFF/TXD.
                open(img_path, 'r+b').close()
                if detect_img_version(img_path) != IMG_VERSION_2:
                    open(_sibling_dir_path(img_path), 'r+b').close()
            except PermissionError:
                # Архив держит игра / IMG-редактор — та же подсказка, что ниже.
                _err = ({'WARNING'}, T(
                    "Файл .img занят — закрой игру перед экспортом: {0}").format(
                        os.path.basename(img_path)))
            except (ValueError, OSError) as e:
                _err = ({'ERROR'}, T("IMG: не удалось записать {0}: {1}").format(
                    os.path.basename(img_path), e))
            else:
                _arch_ver = detect_img_version(img_path)
                if _arch_ver != _want_ver:
                    _err = ({'ERROR'}, T(
                        "Архив {0} — формат {1}, а игра сцены — {2}: игра не прочитает "
                        "такие DFF/COL. Переключи игру во вкладке GTA Tools или выбери "
                        "другой архив.").format(
                            os.path.basename(img_path),
                            'VER2 (SA)' if _arch_ver == IMG_VERSION_2
                            else 'VER1 (III/VC)',
                            _scene_game))
            if _err:
                arch_fail.append(_err)
                _export_unwritten.update(routes[img_path])
                _export_unwritten.update(b for b, a in lod_arch.items() if a == img_path)
                del routes[img_path]
        if arch_fail and not routes:
            for _lvl, _msg in arch_fail:
                self.report(_lvl, _msg)
            return {'CANCELLED'}
        active_main = {b for b, a in main_arch.items() if a in routes}
        active_lod = {b for b, a in lod_arch.items() if a in routes}
        _routed = active_main | active_lod
        model_groups = {b: m for b, m in model_groups.items() if b in _routed}

        results = [T("«{0}»: нет IMG-архива — выберите архив в окне").format(_b)
                   for _b in no_arch]
        results += [T("«{0}»: IMG LOD не найден — LOD пропущен").format(_b)
                    for _b in no_lod_arch]
        for _n in _lod_off_layer:
            results.append(T("{0}: LOD не в слое вида — его текстуры не записаны").format(_n))

        # Архив каждой записи DFF / LOD / COL (записываемые архивы) и каждого
        # объекта-источника (TXD, библиотека COL) — архив его модели, у
        # моделей пропущенного архива тоже.
        arch_of_entry, arch_of_obj = {}, {}
        lod_entry_targets, extra_arch_of_obj = defaultdict(list), defaultdict(list)
        for img_path, _bases in _all_routes.items():
            for _b in _bases:
                _m = _all_groups[_b]
                # Имя LOD — только у записываемого LOD (в III/VC его расчёт
                # обходит сцену).
                for _fn in ([_b + '.dff', _b + '.col']):
                    if img_path in routes:
                        arch_of_entry.setdefault(_fn.lower(), img_path)
                for _o in (_m['DFF'], _m['COL'], _col_src(_b, _m)):
                    if _o is not None:
                        arch_of_obj.setdefault(_o.name, img_path)

        required_txd = defaultdict(list)
        for _b, _a in lod_arch.items():
            _m = _all_groups[_b]
            _o = _lod_src(_b, _m)
            if _a in routes and _inc_lod(_b):
                _fn = (_lod_file(_b, _m) + '.dff').lower()
                arch_of_entry.setdefault(_fn, _a)
                if _a not in lod_entry_targets[_fn]:
                    lod_entry_targets[_fn].append(_a)
            if _o is not None and _o is not _m['DFF']:
                arch_of_obj[_o.name] = _a
                if _a not in extra_arch_of_obj[_o.name]:
                    extra_arch_of_obj[_o.name].append(_a)
                # A full TXD bucket, never a partial same-named dictionary.
                required_txd[(_lod_txd(_b, _m, _o) + '.txd').lower()].append(_a)
        # A selected LOD can contribute textures even with its DFF toggle off.
        for _b, _m in _all_groups.items():
            _o = _lod_src(_b, _m)
            if _o is not None and _o is not _m['DFF'] and _o.name not in arch_of_obj:
                _tf = getattr(getattr(_o, 'inu', None), 'img_target_file', '') or ''
                arch_of_obj[_o.name] = bpy.path.abspath(_tf) if _tf else main_arch.get(_b, '')
            if _m['DFF'] is not None and _m['DFF'].name not in arch_of_obj:
                arch_of_obj[_m['DFF'].name] = main_arch.get(_b, '')

        from ..core.img_routing import shared_targets
        _mixed = {}   # общая запись моделей из разных архивов → её архивы

        def _targets(entry, objs):
            # Общая запись моделей из разных архивов (TXD, библиотека COL):
            # туда, где она уже есть (её и прочтёт игра), нет нигде — в архив
            # первой модели; в каждый — целиком, иначе два неполных
            # одноимённых файла и модели второго архива без текстур.
            # Пропущенный архив целью не станет, но решает: запись там есть
            # (не прочитан — считаем, что есть) — новую не создаём, строка.
            # Записываемые — первыми: «архив первой модели» — из них.
            users = sorted((a for o in objs for a in extra_arch_of_obj.get(
                o.name, [arch_of_obj[o.name]])),
                           key=lambda a: a not in routes)
            required = (required_txd.get(entry.lower(), ())
                        if all(any(a in routes for a in extra_arch_of_obj.get(
                            o.name, [arch_of_obj[o.name]])) for o in objs) else ())
            out = [a for a in shared_targets(
                users, lambda a: entry.lower() in arch_names.get(a, {entry.lower()}),
                required=required)
                if a in routes]
            if not out:
                results.append(T("{0}: не записан — пропущен архив {1}").format(
                    entry, ", ".join(os.path.basename(a) for a in dict.fromkeys(users)
                                     if a not in routes)))
            elif len(set(users)) > 1:
                _mixed[entry] = out
            return out

        # Корзина — объекты моделей записываемых архивов, архивы-цели — по
        # всем её моделям. Нечего или некуда писать — корзину не пишем.
        txd_targets = {}
        for _n in list(txd_buckets):
            _users = txd_buckets[_n]
            txd_buckets[_n] = [o for o in _users if any(a in routes for a in
                extra_arch_of_obj.get(o.name, [arch_of_obj.get(o.name)]))]
            if txd_buckets[_n]:
                txd_targets[_n] = _targets(_n + '.txd', _users)
            if not txd_targets.get(_n):
                del txd_buckets[_n]

        # Счётчики для сводки в статус-баре: сколько DFF/LOD/COL/TXD реально
        # записано в архив (успешные writer.add), помимо списка файлов.
        n_dff = n_lod = n_col = n_txd = 0

        # COL модели правится там, где её запись уже есть в архиве (цикл
        # групп). Нигде нет — отдельный <модель>.col, а в режиме библиотеки
        # (Export All) — в конец <имя>.col: его модели — такие (у моделей
        # пропущенного архива записи не видно — тоже его). Где <имя>.col уже
        # есть — смотрим и по моделям, чья запись нашлась (она могла лечь в
        # архив другой модели — иначе рядом вторая, неполная); нет нигде — в
        # архив первой модели без записи.
        library_col_objects, _lib_in = [], []
        if col_library:
            _arch_of = {_b: _a for _a, _bs in _all_routes.items() for _b in _bs}
            for _base, _models in _all_groups.items():
                if not _inc_col(_base):
                    continue
                # (+ COL-меш: при «Пустой коллизии» _col_src — None, а у
                # выделенной одной COL нет ни DFF, ни LOD)
                _o = (_col_src(_base, _models) or _models['DFF'] or _models['LOD']
                      or _models['COL'])
                if col_idx.get(_arch_of[_base], {}).get(_base.lower()):
                    _lib_in.append(_o)
                else:
                    library_col_objects.append(_o)
        # Как у TXD: пишутся COL моделей записываемых архивов, цели — по всем.
        _lib_users = library_col_objects
        library_col_objects = [o for o in _lib_users
                               if arch_of_obj.get(o.name) in routes]
        lib_targets = (_targets(col_library_name + '.col', _lib_users + _lib_in)
                       if library_col_objects else [])

        # Pick the DFF RW version + COL version once for this whole bulk
        # export — scene's gtatools_game drives III/VC/SA dispatch (RW
        # 3.3/3.5/3.6 for DFF, COL v1/v2/v3). IMG VER1/VER2 comes from the
        # archive file itself (checked against the game above).
        from .dff_export import _resolve_export_version
        from .col_export import _resolve_col_version
        dff_rw_version = _resolve_export_version(context)
        col_version = _resolve_col_version(context)
        # Surface-ID clamp in write_col is keyed on the game, not the COL
        # version (SA ships COL2 archives with SA ids) — same target the
        # standalone COL exporter resolves, so an id past the 179-row
        # table never reaches the file (COL-18).
        from ..core import game_versions as gv
        col_target_game = gv.game_of_scene(context.scene)
        dff_target_platform = getattr(context.scene.inu_settings,
                                      'gtatools_platform', 'PC')

        # Progress estimate. Exact TXD-bucket count is only known after
        # the per-group pass, but counting each write op (LOD/DFF/COL per
        # group — a library COL too, one tick per bucket and target
        # archive) gives a meaningful live progress.
        included_groups = [(b, m) for b, m in model_groups.items() if _want_group(b)]
        total_steps = 0
        for _base, _m in included_groups:
            if _inc_lod(_base): total_steps += 1
            if _is_included(_base) and not self.skip_dff and _m['DFF']: total_steps += 1
            if _inc_col(_base): total_steps += 1
        total_steps += sum(len(t) for t in txd_targets.values())
        total_steps = max(1, total_steps)

        wm.progress_begin(0, total_steps)
        step = 0

        def _tick(label=""):
            nonlocal step
            step += 1
            wm.progress_update(step)
            if label:
                context.workspace.status_text_set(
                    f"{T('Экспорт в IMG:')} {step}/{total_steps} {label}")

        context.workspace.status_text_set(T("Экспорт в IMG..."))

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # DFF/LOD objects are bucketed by resolved TXD name above
                # (txd_buckets) — every bucket produces one .txd per target
                # archive (txd_targets).
                encode_jobs: list = []  # (filename, callable_returning_bytes, label)
                lod_files = set()  # имена LOD-файлов — для счётчика n_lod
                lod_encoded = set()  # a shared LOD is built once, written to each target
                # «В IMG» после записи: (имя .dff, объект) + что реально легло.
                stamp_jobs = []
                # Сначала всё собрать, затем одна сессия ImgWriter на архив:
                # архив → [(имя записи, байты или файл во tmpdir, пометка к
                # строке отчёта, строка после записи)]; архив → что легло.
                arch_files = defaultdict(list)
                written_by = {}
                # .col архивов с правленой записью: архив → {имя (lower): [имя,
                # байты, [модели]]}; модели в конец библиотеки Export All;
                # сколько наших записей в .col (счётчик COL).
                libs, lib_pending, col_recs = defaultdict(dict), [], {}
                prim_idx = (_col_prim_index(context.scene.objects)
                            if not self.empty_col
                            and any(_inc_col(b) for b in model_groups) else {})

                for base_name, models in model_groups.items():
                    if not _want_group(base_name):
                        continue

                    if _inc_lod(base_name):
                        lod_name = _lod_file(base_name, models)
                        lod_files.add(lod_name + '.dff')
                        if lod_notes.get(lod_name):
                            results.append(lod_notes[lod_name])
                        # Источник LOD: найденный в сцене LOD, иначе — копия
                        # основной модели (заглушка) под LOD-именем.
                        lod_obj = _lod_src(base_name, models)
                        if lod_name + '.dff' in lod_encoded:
                            _tick(lod_name + '.dff')
                        elif lod_obj is None:
                            results.append(f"{lod_name}.dff: нет геометрии-источника")
                        else:
                            try:
                                clump = build_dff_clump([lod_obj], version=dff_rw_version, col_model_name=lod_name)
                                _uv = _uv_anim_dropped_names(clump, dff_rw_version)
                                if _uv:
                                    results.append(f"{lod_name}.dff: " + T('UV-анимация не записана: в GTA III/VC её нет ({0})').format(', '.join(_uv)))
                                if dff_target_platform == 'MOBILE':
                                    for g in clump.geometries:
                                        if not g.raw_native_data_plg:
                                            g.is_native_ogl = True
                                    clump.is_mobile = True
                                encode_jobs.append((lod_name + '.dff', clump.to_bytes, f"{lod_name}.dff"))
                                lod_encoded.add(lod_name + '.dff')
                                # Заглушка (копия основной модели) статус не даёт.
                                if lod_obj is not models['DFF']:
                                    stamp_jobs.append((lod_name + '.dff', lod_obj))
                            except Exception as e:
                                results.append(f"{lod_name}.dff error: {e}")
                                _tick(f"{lod_name}.dff")

                    if _is_included(base_name) and not self.skip_dff and models['DFF']:
                        try:
                            dff_objs = [models['DFF']]
                            for child in models['DFF'].children:
                                if child.type == 'EMPTY' and getattr(child, 'inu', None) and child.inu.type == '2DFX':
                                    dff_objs.append(child)
                            clump = build_dff_clump(dff_objs, version=dff_rw_version, col_model_name=base_name)
                            _uv = _uv_anim_dropped_names(clump, dff_rw_version)
                            if _uv:
                                results.append(f"{base_name}.dff: " + T('UV-анимация не записана: в GTA III/VC её нет ({0})').format(', '.join(_uv)))
                            if dff_target_platform == 'MOBILE':
                                for g in clump.geometries:
                                    if not g.raw_native_data_plg:
                                        g.is_native_ogl = True
                                clump.is_mobile = True
                            encode_jobs.append((base_name + '.dff', clump.to_bytes, f"{base_name}.dff"))
                            stamp_jobs.append((base_name + '.dff', models['DFF']))
                        except Exception as e:
                            results.append(f"{base_name}.dff error: {e}")
                            _tick(f"{base_name}.dff")

                    if _inc_col(base_name):
                        try:
                            col_obj = _col_src(base_name, models)
                            # + сферы/боксы модели (x_sphere_0 / x_box_0 из
                            # импорта COL) — раньше терялись.
                            col_src = ([col_obj] if col_obj else []) + _col_prims_of(
                                prim_idx, base_name, col_obj.name if col_obj else '')
                            is_empty = not col_src   # нет COL → заглушка
                            # Empty COL → measure bounds off the visual model so
                            # GTA doesn't cull it (zero sphere = disappears).
                            _bref = None
                            if is_empty:
                                # (+ COL-меш: «Пустая коллизия» у группы из
                                # одной COL — как экспорт в папку; иначе нули)
                                _vis = models['DFF'] or models['LOD'] or models['COL']
                                _bref = [_vis] if _vis else None
                            col_model = build_col_model(col_src, version=col_version, model_name=base_name, empty=is_empty, bounds_ref=_bref)
                            # Линт COL под целевую игру (clamp surface-id in-place)
                            # + сбор проблем в отчёт (раньше молча терялись).
                            _cfatal, _cwarn = audit_col(
                                [col_model], target_game=col_target_game)
                            for _w in _cwarn:
                                results.append(f"{base_name}.col: {_w}")
                            for _f in _cfatal:
                                results.append(f"{base_name}.col: ⚠ {_f}")

                            def _make(mid, m=col_model):
                                m.model_id = mid
                                return write_col([m], target_game=col_target_game)
                            # Запись модели уже в .col архива (своя библиотека,
                            # прежний <модель>.col) — правится на месте: второй
                            # <модель>.col спорил бы с ней в игре (побеждает
                            # последний загруженный), а замена .col целиком
                            # стёрла бы коллизию чужих моделей библиотеки.
                            _arch = arch_of_entry[(base_name + '.col').lower()]
                            _where = col_idx.get(_arch, {}).get(base_name.lower(), [])
                            if not _where and not col_library and (
                                    base_name + '.col').lower() in lib_bytes.get(_arch, {}):
                                # Свой <модель>.col есть, но записи модели в нём
                                # нет (библиотека под её именем) — дописать в
                                # него: замена целиком стёрла бы чужие записи.
                                _where = [base_name + '.col']
                            if _where:
                                for _en in _where:
                                    _lib = libs[_arch].setdefault(_en.lower(), [
                                        _en, lib_bytes[_arch].get(_en.lower(), b''), []])
                                    _lib[1] = _col_lib_put(_lib[1], base_name, _make)[0]
                                    _lib[2].append(base_name)
                                _tick(f"{base_name}.col")
                            elif col_library:
                                if lib_targets:   # некуда — строка «не записан» выше
                                    lib_pending.append((base_name, _make))
                                _tick(f"{base_name}.col")
                            else:
                                encode_jobs.append((base_name + '.col', (lambda m=col_model: write_col([m], target_game=col_target_game)), f"{base_name}.col"))
                        except Exception as e:
                            results.append(f"{base_name}.col error: {e}")
                            _tick(f"{base_name}.col")

                if encode_jobs:
                    enc_workers = min(os.cpu_count() or 4, 4)
                    with ThreadPoolExecutor(max_workers=enc_workers) as enc_pool:
                        futures = [(filename, label, enc_pool.submit(encoder)) for filename, encoder, label in encode_jobs]
                        for filename, label, fut in futures:
                            try:
                                data = fut.result()
                                for _a in lod_entry_targets.get(
                                        filename.lower(), [arch_of_entry[filename.lower()]]):
                                    arch_files[_a].append((filename, data, "", ""))
                            except Exception as e:
                                results.append(f"{filename} error: {e}")
                            _tick(label)

                if txd_buckets:
                    arch_no = {a: i for i, a in enumerate(routes)}
                    for txd_name, sources in txd_buckets.items():
                        if not sources:
                            continue
                        # По TXD на каждый архив-цель: слияние — со своим
                        # TXD этого архива; файл лежит во tmpdir до записи.
                        for img_path in txd_targets[txd_name]:
                            txd_path = os.path.join(
                                tmpdir, f"{arch_no[img_path]}_{txd_name}.txd")
                            prev_active = context.view_layer.objects.active
                            prev_selected = [o for o in context.selected_objects]
                            try:
                                bpy.ops.object.select_all(action='DESELECT')
                                for src in sources:
                                    src.select_set(True)
                                context.view_layer.objects.active = sources[0]
                                # TXD района / машины с тюнингом делят многие
                                # модели: сливаем с тем, что уже в архиве —
                                # одноимённые текстуры заменяются, остальные
                                # остаются байт в байт, RW lib id — прежний.
                                base = base_txd[img_path].get(txd_name.lower())
                                not_txd = (base is not None
                                           and split_txd_sections(base)[0] is None)
                                if base is not None and not not_txd:
                                    with open(txd_path, 'wb') as f:
                                        f.write(base)
                                    result, msg, _ = update_txd(txd_path, context, True, backend=backend)
                                else:
                                    base = None
                                    result, msg, _ = export_txd(txd_path, context, True, backend=backend)
                                if result == {'FINISHED'}:
                                    arch_files[img_path].append((
                                        txd_name + '.txd', txd_path,
                                        f" ({msg})" if base is not None
                                        else f" ({len(sources)} models)",
                                        T("{0}.txd: в архиве не TXD — заменён").format(txd_name)
                                        if not_txd else ""))
                                else:
                                    results.append(f"{txd_name}.txd: {msg}")
                            except Exception as e:
                                results.append(f"{txd_name}.txd error: {e}")
                            finally:
                                bpy.ops.object.select_all(action='DESELECT')
                                for o in prev_selected:
                                    o.select_set(True)
                                if prev_active is not None:
                                    context.view_layer.objects.active = prev_active
                            _tick(f"{txd_name}.txd")

                # Библиотека Export All: модели без записи в архиве — в конец
                # <имя>.col, в каждый архив-цель целиком; прежние её записи
                # остаются. Затем все правленые .col — к записи.
                lib_filename = f"{col_library_name}.col"
                for img_path in (lib_targets if lib_pending else []):
                    _lib = libs[img_path].setdefault(lib_filename.lower(), [
                        lib_filename,
                        lib_bytes.get(img_path, {}).get(lib_filename.lower(), b''), []])
                    for _b, _mk in lib_pending:
                        try:
                            _lib[1] = _col_lib_put(_lib[1], _b, _mk)[0]
                            _lib[2].append(_b)
                        except Exception as e:
                            results.append(f"{_b}.col error: {e}")
                for img_path, _libs in libs.items():
                    for _name, _data, _bs in _libs.values():
                        if _bs:
                            col_recs[(img_path, _name.lower())] = len(_bs)
                            arch_files[img_path].append((_name, _data, " (" + ", ".join(
                                _bs[:4]) + (f" +{len(_bs) - 4}" if len(_bs) > 4 else "") + ")", ""))

                # Запись: одна сессия ImgWriter на архив. Архив занят / не
                # открылся — строка в отчёте, остальные архивы пишутся.
                for img_path, files in arch_files.items():
                    _pfx = (os.path.basename(img_path) + ": ") if len(routes) > 1 else ""
                    written = set()
                    try:
                        with ImgWriter(img_path) as writer:
                            for filename, data, note, extra in files:
                                try:
                                    if isinstance(data, str):   # TXD / библиотека — файл во tmpdir
                                        with open(data, 'rb') as f:
                                            data = f.read()
                                    status = writer.add(filename, data)
                                except Exception as e:
                                    results.append(f"{_pfx}{filename} error: {e}")
                                    continue
                                written.add(filename.lower())
                                results.append(f"{_pfx}{filename} {status}{note}")
                                if extra:
                                    results.append(_pfx + extra)
                                _low = filename.lower()
                                if _low.endswith('.col'):
                                    # библиотека — наши записи в ней
                                    n_col += col_recs.get((img_path, _low), 1)
                                elif _low.endswith('.txd'):
                                    n_txd += 1
                                elif filename in lod_files:
                                    n_lod += 1
                                elif _low.endswith('.dff'):
                                    n_dff += 1
                    except PermissionError:
                        # .img заблокирован (чаще всего запущена игра, которая
                        # держит архив открытым) — строка вместо трейсбека.
                        arch_fail.append(({'WARNING'}, T(
                            "Файл .img занят — закрой игру перед экспортом: {0}").format(
                                os.path.basename(img_path))))
                        _export_unwritten.update(routes[img_path])
                        _export_unwritten.update(b for b, a in lod_arch.items() if a == img_path)
                        continue
                    except (ValueError, OSError) as e:
                        # Не IMG / битая шапка («Not a VER2») / ошибка диска.
                        # PermissionError (подкласс OSError) — выше.
                        arch_fail.append(({'ERROR'}, T(
                            "IMG: не удалось записать {0}: {1}").format(
                                os.path.basename(img_path), e)))
                        _export_unwritten.update(routes[img_path])
                        _export_unwritten.update(b for b, a in lod_arch.items() if a == img_path)
                        continue
                    written_by[img_path] = written

                # Пулы движка: игра грузит ВСЕГО ≤255 отдельных .col-файлов и
                # ≤10150 COL-моделей (CColModel). Аддон не знает всю игру, но
                # предупреждает, если сам этот экспорт упирается в лимит —
                # тогда стоит объединить коллизии в один library .col.
                _n_col_files = sum(1 for _fn, _e, _l in encode_jobs
                                   if _fn.lower().endswith('.col'))
                # + новые .col-библиотеки (правка лежащей файлов не прибавляет)
                _n_col_files += sum(1 for _a, _ls in libs.items()
                                    for _k, _v in _ls.items()
                                    if _v[2] and _k not in arch_names.get(_a, ()))
                if _n_col_files > 255:
                    results.append(T(
                        "⚠ .col-файлов за экспорт: {0} — движок грузит ≤255 "
                        "всего. Объедини коллизии в один library .col.").format(
                            _n_col_files))
                if n_col > 10150:
                    results.append(T(
                        "⚠ COL-моделей: {0} — лимит движка 10150 (CColModel).")
                        .format(n_col))
        finally:
            # Always reset UI progress/status, even on unexpected error.
            wm.progress_end()
            context.workspace.status_text_set(None)

        # Ни один архив не записан (занят / не IMG / другой игры) — отказ,
        # как раньше; часть записана — об остальных предупреждение + строка.
        if arch_fail and not written_by:
            if results:   # ошибки сборки и пр. — не терять за отказом архива
                self.report({'WARNING'}, "IMG: " + ", ".join(results[:6])
                            + (f" (+{len(results) - 6})" if len(results) > 6 else ""))
            for _lvl, _msg in arch_fail:
                self.report(_lvl, _msg)
            return {'CANCELLED'}
        # A failed LOD write makes its model's IDE/IPL export incomplete too.
        for _b, _m in _all_groups.items():
            _e = _plan_entry(_b)
            if _inc_lod(_b):
                _a = lod_arch.get(_b, '')
                if (_lod_file(_b, _m) + '.dff').lower() not in written_by.get(_a, ()):
                    _export_unwritten.add(_b)
                if _e.include and not self.skip_txd:
                    _o = _lod_src(_b, _m)
                    if _o is not None and _o is not _m['DFF']:
                        _txd = (_lod_txd(_b, _m, _o) + '.txd').lower()
                        if _txd not in written_by.get(_a, ()):
                            _export_unwritten.add(_b)
        # Сбой архива и куда легла общая запись — в начало: строка отчёта
        # показывает только первые 6.
        _head = [_msg for _lvl, _msg in arch_fail]
        for _e, _outs in _mixed.items():
            _ok = [os.path.basename(a) for a in _outs
                   if _e.lower() in written_by.get(a, ())]
            if _ok:
                _head.append(T("{0}: модели из разных архивов — записан в {1}").format(
                    _e, ", ".join(_ok)))
        results[:0] = _head
        for _lvl, _msg in arch_fail:
            self.report({'WARNING'}, _msg)

        # Каталоги архивов записаны (ImgWriter.__exit__) → «В IMG» у моделей,
        # чьи DFF/LOD реально легли — у каждой её архив. До rebuild: если он
        # упадёт, записи всё равно уже в архиве.
        from ..tools.model_utils import get_model_type
        stamp_jobs += _copy_jobs(context.selected_objects, get_model_type,
                                 lambda o, b: lod_model_name(
                                     o, b, hd=lod_hd.get(id(o), '')))
        for img_path, written in written_by.items():
            _stamp_img_status(stamp_jobs, written, img_path)
        # Имя TXD — только теперь (отказ / ошибка выше оставляют как было):
        # модели и LOD-у, чьи текстуры легли в записанный TXD (правка имени
        # в окне, общий TXD). Свой TXD LOD-а не меняется — туда и писали.
        for _o, _n in _txd_writeback(txd_buckets, set().union(*written_by.values())):
            _o.inu.txd_name = _n

        from .. import _append_export_report
        # Пересборка (компактирование) архивов сразу после экспорта — по галочке.
        if self.rebuild_after:
            from ..core.img import rebuild_img
            for img_path in written_by:
                _pfx = (os.path.basename(img_path) + ": ") if len(written_by) > 1 else ""
                try:
                    _st = rebuild_img(img_path)
                    _mb = _st['saved'] / (1024.0 * 1024.0)
                    results.append(f"{_pfx}rebuild: {_st['entries']} записей, -{_mb:.1f} МБ")
                except Exception as e:
                    results.append(f"{_pfx}rebuild error: {e}")
        # Список записей — архив из настроек, если он записан, иначе первый.
        _main = next((a for a in written_by if _same_img(
            a, context.scene.inu_settings.gtatools_img_path)), next(iter(written_by), ""))
        if _main:
            _refresh_img_entries(context.scene, _main)
        try:
            # Рядом с .blend (не в папке models игры); сцена не сохранена —
            # файла нет, итог только в строке отчёта ниже.
            report_path = _img_report_path(bpy.data.filepath)
            if report_path:
                rows = [f"IMG: {a}" for a in routes]
                rows.extend(f"- {row}" for row in results)
                _append_export_report(report_path, "Export to IMG", rows)
        except Exception as e:
            self.report({'WARNING'}, f"{T('Не удалось записать отчёт:')} {e}")
        if results:
            counts = []
            if n_dff:
                counts.append(f"DFF {n_dff}")
            if n_col:
                counts.append(f"COL {n_col}")
            if n_lod:
                counts.append(f"LOD {n_lod}")
            if n_txd:
                counts.append(f"TXD {n_txd}")
            preview = ', '.join(results[:6])
            more = f" (+{len(results) - 6})" if len(results) > 6 else ""
            summary = (", ".join(counts) + " — ") if counts else ""
            self.report({'INFO'}, f"IMG: {summary}{preview}{more}")
        else:
            self.report({'WARNING'}, T("IMG: нет результатов экспорта"))
        # Mobile: TXD всё равно PC-формата (PVRTC/ETC1 не пишем), как в
        # Export TXD — после сводки, последним отчётом.
        from ..tools.txd_export import mobile_txd_warning
        _mob = mobile_txd_warning(dff_target_platform, n_txd)
        if _mob:
            self.report({'WARNING'}, _mob)
        # Итог — и для All → IMG (_export_final): там этот оператор вложенный.
        _export_final.update(mobile=_mob, summary=(
            ({'INFO'}, f"IMG: {summary}{preview}{more}") if results
            else ({'WARNING'}, T("IMG: нет результатов экспорта"))))
        return {'FINISHED'}
