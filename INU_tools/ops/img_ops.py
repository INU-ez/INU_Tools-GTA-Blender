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

        info = find_all_resources(game_root)

        # Collect all IMG archives — four sources, dedup by absolute path:
        #   1. Standard vanilla path: <game>/models/gta3.img
        #   2. Paths declared in gta.dat / gta_int.dat (via find_all_resources)
        #   3. User-set fallback (`gtatools_img_path`)
        #   4. Anything else with a `.img` extension anywhere under game_root —
        #      catches custom installs, mod archives, additional `playerN.img`,
        #      `cutscene.img`, district-split mods, etc. that aren't declared
        #      in gta.dat.
        img_paths = []

        def _add(path: str):
            if not path:
                return
            absp = os.path.normcase(os.path.abspath(path))
            if not os.path.isfile(path):
                return
            for existing in img_paths:
                if os.path.normcase(os.path.abspath(existing)) == absp:
                    return
            img_paths.append(path)

        _add(os.path.join(game_root, 'models', 'gta3.img'))
        for p in info.img_paths:
            _add(p)
        _add(bpy.path.abspath(scene.inu_settings.gtatools_img_path))

        # Recursive fallback — walk the whole game_root for `.img` files. Done
        # AFTER the priority sources so anything declared in gta.dat keeps its
        # position; only "extra" archives get appended at the end. Skip common
        # cache / hidden dirs to avoid scanning a 50-GB user backup folder.
        _SKIP_DIRS = {'.git', '.svn', '__pycache__', '.inu_cache', 'node_modules'}
        extra_count = 0
        for dirpath, dirnames, filenames in os.walk(game_root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fn in filenames:
                if fn.lower().endswith('.img'):
                    full = os.path.join(dirpath, fn)
                    before = len(img_paths)
                    _add(full)
                    if len(img_paths) > before:
                        extra_count += 1
        # Always log the final IMG list — helps users diagnose why some
        # archives weren't picked up (path typos / permission errors / etc.).
        print(f"\n[Extract Resources] game_root = {game_root}")
        print(f"[Extract Resources] {extra_count} extra .img file(s) via recursive walk")
        print(f"[Extract Resources] {len(img_paths)} IMG archive(s) to process:")
        for ip in img_paths:
            print(f"  - {ip}")
        print()

        if not img_paths:
            self.report({'ERROR'}, T("Не найден IMG архив"))
            return {'CANCELLED'}

        # Region filter — when picked, walk matching IPLs (BOTH text +
        # binary-from-IMG) to gather used model_ids, look those up in
        # IDE files to get TXD names, then only extract those TXDs.
        # Saves minutes on large extracts.
        #
        # Why scan binary IPLs too: vanilla SA places a lot of district
        # geometry via binary IPLs inside gta3.img (countn1.ipl,
        # countryS.ipl, …), and these aren't declared in gta.dat. The
        # previous version only walked text IPLs from gta.dat — for
        # COUNTRY that misses ~half of placements, which dropped the
        # corresponding TXDs from ``needed_txds`` and left them filtered.
        region = getattr(scene.inu_settings, 'gtatools_map_region', 'ALL')
        needed_txds = None  # None = "extract everything"
        if region != 'ALL':
            from ..core.ipl import _read_binary_ipl

            def _ipl_matches_region(path: str) -> bool:
                parts = path.replace('\\', '/').upper().split('/')
                for i, part in enumerate(parts):
                    if part == 'MAPS' and i + 1 < len(parts):
                        return parts[i + 1] == region
                name = path.replace('\\', '/').rsplit('/', 1)[-1].upper()
                return name.startswith(region)

            # Binary IPLs in gta3.img don't follow the folder-name region
            # picker. Vanilla SA filenames use abbreviated prefixes:
            # COUNTRY → countn*, country*, countxx; LA → la*; SF → sf*;
            # VEGAS → vegas*. Map the user-facing region label to the
            # filename prefixes the IMG actually contains.
            _BIN_IPL_PREFIXES = {
                'COUNTRY': ('COUNT',),    # countn*, country*, countxx, ...
                'LA':      ('LA',),
                'SF':      ('SF',),
                'VEGAS':   ('VEGAS',),
            }
            bin_ipl_prefixes = _BIN_IPL_PREFIXES.get(region, (region,))

            # Honour explicit binary-IPL toggles if the user curated them
            # (gtatools_binary_ipls is a per-scene checklist that the
            # sidebar's «Binary IPLs» panel surfaces).
            bi_entries = scene.inu_settings.gtatools_binary_ipls
            bi_enabled = {i.name.lower() for i in bi_entries if i.enabled}
            bi_use_selection = len(bi_entries) > 0

            def _bin_ipl_matches(name_lower: str) -> bool:
                if bi_use_selection:
                    return name_lower in bi_enabled
                upper = name_lower.upper()
                return any(upper.startswith(p) for p in bin_ipl_prefixes)

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

            # Pass 1: text IPLs from gta.dat
            text_ipl_count = 0
            for p in info.ipl_paths:
                if os.path.isfile(p) and _ipl_matches_region(p):
                    try:
                        ipl = read_ipl(p)
                        for inst in ipl.instances:
                            used_ids.add(inst.model_id)
                        text_ipl_count += 1
                    except Exception:
                        pass

            # Pass 2: binary IPLs inside IMG archives. Read the directory,
            # filter by name prefix or user selection, parse the bnry
            # blob to pull instance model_ids.
            bin_ipl_count = 0
            from ..core.img import extract_file
            for ip in img_paths:
                try:
                    for e in read_directory(ip):
                        low = e.name.lower()
                        if not low.endswith('.ipl'):
                            continue
                        if not _bin_ipl_matches(low):
                            continue
                        try:
                            ipl_data = extract_file(ip, e.name)
                            if ipl_data and ipl_data[:4] == b'bnry':
                                ipl_parsed = _read_binary_ipl(ipl_data)
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

        # Pre-count TXDs for accurate progress (after region filter if any)
        txd_total = 0
        for ip in img_paths:
            try:
                for e in read_directory(ip):
                    low = e.name.lower()
                    if not low.endswith('.txd'):
                        continue
                    if needed_txds is not None:
                        if low[:-4] not in needed_txds:
                            continue
                    txd_total += 1
            except Exception:
                pass

        self._img_paths = img_paths
        self._cache_dir = cache_dir
        self._tex_dir = tex_dir
        self._txd_total = txd_total
        self._needed_txds = needed_txds  # None = no filter
        self._region = region
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
        from ..core.img import ImgReader, safe_filename
        from ..core.txd import read_txd
        from .. import _write_png

        cache_dir = self._cache_dir
        tex_dir = self._tex_dir
        needed_txds = self._needed_txds
        prof = self._profiler

        err_log_path = os.path.join(cache_dir, '_txd_errors.log')
        skip_log_path = os.path.join(cache_dir, '_extract_skipped.log')

        # Reset skip log at start of each extraction so the user always
        # sees results from this run, not a growing all-time history.
        try:
            if os.path.isfile(skip_log_path):
                os.remove(skip_log_path)
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
            (``tex_count`` / ``skips`` / ``errors``); the main thread
            folds it into the counters and logs (see ``_aggregate``).
            numpy DXT decompress (in read_txd) and zlib.compress (in
            _write_png) both release the GIL — so N workers do real
            parallel work on multi-core CPUs.
            """
            result = {'tex_count': 0, 'skips': [], 'errors': []}
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

                # Dedup: read existing PNG's actual resolution from its
                # IHDR. Skip only when the file on disk is at least as
                # large as the new texture in BOTH dimensions — protects
                # against a downscale variant from another IMG overwriting
                # a higher-res original. The previous comparison of
                # raw-RGBA bytes vs compressed PNG bytes was meaningless.
                if os.path.isfile(png_path):
                    ew, eh = _read_png_dimensions(png_path)
                    if ew >= tex.width and eh >= tex.height:
                        result['skips'].append(
                            ('dedup', name, entry_name,
                             f"existing {ew}x{eh} >= new {tex.width}x{tex.height}"))
                        continue

                try:
                    with prof.stage('_write_png'):
                        _write_png(png_path, tex.pixels, tex.width, tex.height)
                    result['tex_count'] += 1
                except Exception as e:
                    result['errors'].append(f"{entry_name}/{name}: {e}")
                    result['skips'].append(
                        ('write_error', name, entry_name, str(e)))
            return result

        def _aggregate(fut):
            """Main thread: fold one finished future's result into the
            shared counters / logs. Surfaces a worker crash to the error
            log instead of silently dropping it."""
            try:
                res = fut.result()
            except Exception as e:
                _log_err(f"worker crashed: {e}")
                return
            self._tex_count += res['tex_count']
            for msg in res['errors']:
                _log_err(msg)
            for skip in res['skips']:
                _log_skip(*skip)

        # Worker count — start conservative (4). Bumping to 8 is safe too
        # but diminishing returns above that since IMG reads are serial.
        workers = min(os.cpu_count() or 4, 4)

        for ip in self._img_paths:
            try:
                with ImgReader(ip) as img:
                    with prof.stage('extract_all_to (DFF+COL)', note=os.path.basename(ip)):
                        counts = img.extract_all_to(
                            cache_dir,
                            extensions={'.dff', '.col'},
                            skip_existing=True)
                    self._dff_count += counts['dff']
                    self._col_count += counts['col']
                    self._skipped += counts['skipped']

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
                        for entry in img.entries:
                            low = entry.name.lower()
                            if not low.endswith('.txd'):
                                continue
                            if needed_txds is not None and low[:-4] not in needed_txds:
                                # Region filter excluded this TXD — log
                                # at archive level so the user can see if
                                # their region pick was too narrow.
                                _log_skip('archive_filtered', '*', entry.name,
                                          f"region={self._region}")
                                continue

                            with prof.stage('img.read (TXD bytes)'):
                                txd_data = img.read(entry.name)
                            if not txd_data:
                                _log_skip('parse_error', '*', entry.name,
                                          "empty read")
                                continue

                            pending.append(
                                pool.submit(_process_txd, entry.name, txd_data))
                            yield  # let modal tick between submits

                        # Drain — aggregate each future as it completes,
                        # yielding so the UI keeps updating every ~50 ms.
                        # Progress advances as the main thread observes each
                        # finished future (replaces the old done-callback).
                        while pending:
                            still = []
                            for fut in pending:
                                if fut.done():
                                    _aggregate(fut)
                                    self._txd_progress += 1
                                else:
                                    still.append(fut)
                            pending = still
                            if pending:
                                _t.sleep(0.01)
                            yield
                    finally:
                        pool.shutdown(wait=False)
                        self._pool = None
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

        if prof.enabled:
            prof.print_report()
            prof.save_log(os.path.join(cache_dir, '_profile.log'))

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
    «Импорт всех моделей» работать и без IPL (по одному IDE)."""
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


def _rescue_textures_from_img(img_path, img_files, tmpdir, extract_file, import_txd):
    """Дотянуть текстуры ИЗ САМОГО IMG для материалов, у которых имя текстуры
    (dff_texture_name) есть, а картинки нет. Нужный .txd ищется по СОДЕРЖИМОМУ
    (индекс имён из IMG, scan_img — без декода пикселей), БЕЗ IDE: IPL/DFF
    достаточно. Импортируется минимальный набор TXD (greedy set-cover),
    import_txd привязывает картинки к материалам по имени. Возвращает число
    подгруженных TXD."""
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
    # 2. Индекс texture→txd из IMG (только имена, кэш по размеру архива —
    #    повторные импорты не пересканируют весь gta3.img).
    idx = _get_img_texture_index(img_path)
    if not idx:
        return 0
    txd_provides = {}
    for tn in missing:
        for txd in idx.get(tn, ()):
            txd_provides.setdefault(txd, set()).add(tn)
    # 3. Greedy set-cover: минимум TXD, покрывающих все missing.
    remaining = set(missing)
    chosen = []
    while remaining and txd_provides:
        best = max(txd_provides, key=lambda t: len(txd_provides[t] & remaining))
        cover = txd_provides[best] & remaining
        if not cover:
            break
        chosen.append(best)
        remaining -= cover
        txd_provides.pop(best, None)
    # 4. Импортировать выбранные TXD из IMG (привязка по имени).
    loaded = 0
    for txd in chosen:
        real = img_files.get((txd + '.txd').lower())
        if not real:
            continue
        data = extract_file(img_path, real)
        if not data:
            continue
        p = os.path.join(tmpdir, txd + '.txd')
        try:
            with open(p, 'wb') as f:
                f.write(data)
            import_txd(filepath=p)
            loaded += 1
        except Exception:
            pass
    return loaded


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

        # Auto-detect game from the IMG archive's format (VER2 magic →
        # SA, sibling .dir present → VC fallback). Auto-flips scene
        # game on fresh scenes, otherwise warns about mismatch so the
        # user can manually switch the GTA Tools tab.
        try:
            from ..core import game_versions as gv
            detected = gv.detect_game_from_img(img_path)
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

        if use_gta_dat and game_root and os.path.isdir(game_root):
            from ..core.gta_dat import find_all_resources
            info = find_all_resources(game_root)

            for p in info.ide_paths:
                if os.path.isfile(p):
                    _load_ide_into(p)

            for p in info.ipl_paths:
                if os.path.isfile(p):
                    try:
                        ipl = read_ipl(p)
                    except Exception:
                        continue
                    # lod_index указывает В СВОЙ файл — сдвигаем на смещение.
                    _base = len(instances)
                    for _k, _inst in enumerate(ipl.instances):
                        _li = getattr(_inst, 'lod_index', -1)
                        if _li is not None and _li >= 0:
                            _inst.lod_index = _li + _base
                        inst_src[_base + _k] = (p, _base)
                        instances.append(_inst)

            # Also read binary IPL from IMG (stream files)
            img_dir = read_directory(img_path)
            for e in img_dir:
                if e.name.lower().endswith('.ipl'):
                    try:
                        ipl_data = extract_file(img_path, e.name)
                        if ipl_data and ipl_data[:4] == b'bnry':
                            ipl = read_ipl.__wrapped__(ipl_data) if hasattr(read_ipl, '__wrapped__') else None
                            if ipl is None:
                                from ..core.ipl import _read_binary_ipl
                                ipl_parsed = _read_binary_ipl(ipl_data)
                                instances.extend(ipl_parsed.instances)
                    except Exception:
                        pass
        else:
            if ide_path and os.path.isfile(ide_path):
                _load_ide_into(ide_path)
            elif game_root and os.path.isdir(game_root):
                # Авто-IDE: IDE не выбран, но задана папка с IDE — читаем ВСЕ
                # .ide из неё (корень игры → по gta.dat, иначе рекурсивный скан).
                # Модель находится по имени из IPL; IDE лишь даёт TXD/дальность/
                # флаги, лишние определения просто не участвуют.
                from ..core.gta_dat import list_ide_files
                for p in list_ide_files(game_root):
                    if os.path.isfile(p):
                        _load_ide_into(p)

            # Мультивыбор IPL: сливаем инстансы из всех выбранных .ipl. lod_index
            # указывает В СВОЙ IPL, поэтому при слиянии сдвигаем его на смещение
            # инстансов этого файла — иначе LOD-привязка уедет.
            for _ip in _ipl_paths_for_import(scene.inu_settings):
                try:
                    _ipl = read_ipl(_ip)
                except Exception:
                    continue
                _base = len(instances)
                for _inst in _ipl.instances:
                    _li = getattr(_inst, 'lod_index', -1)
                    if _li is not None and _li >= 0:
                        try:
                            _inst.lod_index = _li + _base
                        except Exception:
                            pass
                    inst_src[len(instances)] = (_ip, _base)
                    instances.append(_inst)

        # Подгрузить найденные «Найти IDE» — тогда txd_name/дальность/флаги
        # проставятся для ВСЕХ моделей IPL (кастомная карта часто разложена по
        # нескольким IDE). Уже загруженные из выбранного IDE имеют приоритет.
        _found_ides = [p for p in
                       (scene.get('gtatools_found_ides', '') or '').split('\n')
                       if p and os.path.isfile(p)]
        for _p in _found_ides:
            _load_ide_into(_p)

        # «Только по IDE»: без IPL расставлять негде — импортируем КАЖДУЮ
        # определённую в IDE модель раз, сеткой. Так одна кнопка «Импорт всех
        # моделей» работает и по IPL (с расстановкой), и по IDE (галерея).
        if not instances and ide_models:
            instances = _instances_from_ide(ide_models)
            inst_src = {}

        if not instances:
            self._final = ('ERROR', T("Укажите IPL или IDE файл"))
            return
        self._total = len(instances)

        # Индекс имя→(архив, реальное_имя): основной IMG + найденные «Найти IMG».
        # Модели кастомной карты часто разложены по нескольким .img (maps/
        # RESOURCES) — тянем каждую из архива, где она реально лежит. Найденные
        # архивы имеют приоритет (кастомная версия перекрывает стоковую).
        _found_imgs = [p for p in
                       (context.scene.get('gtatools_found_imgs', '') or '').split('\n')
                       if p and os.path.isfile(p)]
        img_index = {}
        for _p in [img_path] + _found_imgs:
            if not _p or not os.path.isfile(_p):
                continue
            try:
                for e in read_directory(_p):
                    img_index[e.name.lower()] = (_p, e.name)
            except Exception:
                continue
        # img_files — плоский {имя: реальное_имя} для совместимости (rescue).
        img_files = {k: v[1] for k, v in img_index.items()}

        def _get_or_create_collection(name):
            col = bpy.data.collections.get(name)
            if not col:
                col = bpy.data.collections.new(name)
                context.scene.collection.children.link(col)
            return col

        dff_collection = _get_or_create_collection("Map_DFF")
        lod_collection = _get_or_create_collection("Map_LOD")
        col_collection = _get_or_create_collection("Map_COL")

        imported_count = 0
        skipped_count = 0
        skip_lod_count = 0      # пропущено как LOD (Skip LOD включён)
        skip_noimg_count = 0    # <модель>.dff не найден в выбранном IMG
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
        scene_placed = {}
        for _o in context.scene.objects:
            if _o.type != 'MESH' or not hasattr(_o, 'inu'):
                continue
            _mid = int(_o.inu.model_id)
            if _mid <= 0:
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
                model_name = inst.model_name
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
                    _groups = scene_placed.get(inst.model_id)
                    if _groups:
                        _scene_src = _groups[0][2]

                if _scene_src is None and dff_filename.lower() not in img_index:
                    skipped_count += 1
                    skip_noimg_count += 1
                    if len(_noimg_sample) < 5:
                        _noimg_sample.append(model_name)
                    continue

                if model_name in imported_models or _scene_src is not None:
                    src_list = imported_models.get(model_name) or _scene_src
                    new_objects = []
                    for src_obj in src_list:
                        new_obj = src_obj.copy()
                        new_obj.data = src_obj.data  # linked duplicate
                        target_collection.objects.link(new_obj)
                        new_objects.append(new_obj)
                    if _scene_src is not None:
                        reused_count += 1
                        # Копия объекта из сцены тащит его IPL-метки; два
                        # объекта с одним ipl_uuid ломают upsert в Add to IPL.
                        for new_obj in new_objects:
                            if hasattr(new_obj, 'inu'):
                                new_obj.inu.ipl_uuid = ""
                                new_obj.inu.ipl_target_file = ""
                                new_obj.inu.ipl_last_model_id = 0
                        imported_models[model_name] = new_objects
                else:
                    _di = img_index[dff_filename.lower()]
                    dff_data = extract_file(_di[0], _di[1])
                    if not dff_data:
                        errors.append(f"{model_name}: DFF extract failed")
                        continue

                    dff_path = os.path.join(tmpdir, dff_filename)
                    with open(dff_path, 'wb') as f:
                        f.write(dff_data)

                    try:
                        before = set(context.scene.objects)
                        inu_import_dff(filepath=dff_path, context=context)
                        after = set(context.scene.objects)
                        new_objects = list(after - before)

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

                        col_filename = model_name + '.col'
                        if col_filename.lower() in img_index:
                            _ci = img_index[col_filename.lower()]
                            col_data = extract_file(_ci[0], _ci[1])
                            if col_data:
                                col_path = os.path.join(tmpdir, col_filename)
                                with open(col_path, 'wb') as f:
                                    f.write(col_data)
                                try:
                                    from .col_import import import_col as inu_import_col
                                    before_col = set(context.scene.objects)
                                    inu_import_col(filepath=col_path, context=context)
                                    after_col = set(context.scene.objects)
                                    col_objects = list(after_col - before_col)
                                    col_pos = (inst.pos_x, inst.pos_y, inst.pos_z)
                                    col_rot = Quaternion((inst.rot_w, inst.rot_x, inst.rot_y, inst.rot_z)).conjugated()
                                    _sfx_col = getattr(scene.inu_settings, 'gtatools_suffix_col', '_COL')
                                    _pfx_col = getattr(scene.inu_settings, 'gtatools_prefix_col', '')
                                    for co in col_objects:
                                        for c in list(co.users_collection):
                                            c.objects.unlink(co)
                                        col_collection.objects.link(co)
                                        co.location = col_pos
                                        co.rotation_mode = 'QUATERNION'
                                        co.rotation_quaternion = col_rot
                                        from ..core.ipl import strip_lod_marker
                                        base_col = strip_lod_marker(model_name)
                                        if _sfx_col:
                                            co.name = base_col + _sfx_col
                                        elif _pfx_col:
                                            co.name = _pfx_col + base_col
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
                    if obj.type == 'MESH':
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
                                    obj.inu.ide_last_draw_distance = obj.inu.draw_distance
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
                _main = next((o for o in new_objects if o.type == 'MESH'), None)
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
            # чей txd_name не в выбранном IDE), добираем прямо из архива.
            _rescue_textures_from_img(img_path, img_files, tmpdir,
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
            if reasons:
                msg += " (" + ", ".join(reasons) + ")"
        if errors:
            msg += f", {T('ошибок:')} {len(errors)}"
            for e in errors[:5]:
                print(f"[Map Import] {e}")
        # Диагностика в консоль: сколько файлов реально в IMG и примеры имён,
        # которых там не нашлось (для «нет DFF в IMG»).
        if skip_noimg_count:
            print(f"[IMG import] файлов в архиве: {len(img_files)}; "
                  f"не найдено DFF (примеры): {_noimg_sample}")
        self._final = ('INFO', msg)
        return


class GTATOOLS_OT_remove_from_img(bpy.types.Operator):
    """Удалить DFF/TXD/COL выделенных моделей из IMG архива"""
    bl_idname = "gtatools.remove_from_img"
    bl_label = "INU: Remove from IMG"
    bl_options = {'REGISTER'}

    # Переопределение архива (пусто → gtatools_img_path). Для 🗑 в боксе —
    # удалять из РОДНОГО IMG модели.
    target_img: StringProperty(default="", options={'HIDDEN'})

    def execute(self, context):
        from ..core.img import remove_file
        from ..tools.model_utils import get_model_type

        img_path = bpy.path.abspath(
            self.target_img or context.scene.inu_settings.gtatools_img_path)
        if not img_path or not os.path.isfile(img_path):
            self.report({'ERROR'}, T("Укажите путь к .img архиву"))
            return {'CANCELLED'}

        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        removed = []
        for obj in objs:
            mt, base = get_model_type(obj)
            if not base:
                continue

            if mt == 'DFF':
                if remove_file(img_path, base + '.dff'):
                    removed.append(base + '.dff')
                if remove_file(img_path, base + '.txd'):
                    removed.append(base + '.txd')
            elif mt == 'LOD':
                fname = 'LOD' + base + '.dff'
                if remove_file(img_path, fname):
                    removed.append(fname)
            elif mt == 'COL':
                if remove_file(img_path, base + '.col'):
                    removed.append(base + '.col')

        if removed:
            _refresh_img_entries(context.scene, img_path)
            self.report({'INFO'}, f"IMG: {T('удалено')} {', '.join(removed)}")
            # Status-bar reminder shows the *latest* report — make sure
            # the rebuild hint is the one users see. The list of removed
            # files stays in the report log for click-through.
            self.report(
                {'INFO'},
                T("Rebuild Archive в IMG-туле — иначе игра подтянет старую запись"))
        else:
            self.report({'WARNING'}, T("Файлы не найдены в IMG"))
        return {'FINISHED'}


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
        seen = set()
        uniq = []
        for p in img_paths:
            k = os.path.normcase(os.path.abspath(p))
            if k not in seen:
                seen.add(k)
                uniq.append(p)
        if not uniq:
            self.report({'ERROR'},
                        T("Нет IMG: укажи архив или папку игры"))
            return {'CANCELLED'}

        # dff-имя (в нижнем регистре) → путь к архиву (первое совпадение).
        name_to_img = {}
        for p in uniq:
            try:
                for e in read_directory(p):
                    nm = e.name.lower()
                    if nm.endswith('.dff'):
                        name_to_img.setdefault(nm, p)
            except Exception:
                continue

        found = lost = 0
        for o in objs:
            _mt, base = get_model_type(o)
            if not base:
                base = o.name
            src = name_to_img.get((base + '.dff').lower())
            if src:
                o.inu.img_target_file = src
                found += 1
            else:
                o.inu.img_target_file = ''
                lost += 1
        self.report({'INFO'},
                    T("Проверка IMG: найдено {0}, не в архивах {1}").format(
                        found, lost))
        return {'FINISHED'}


class GTATOOLS_OT_rebuild_img(bpy.types.Operator):
    """Перестроить (компактировать) IMG-архив: убрать мёртвое место,
    оставшееся от перезаписей моделей (replace добавляет данные в конец,
    старый блок не освобождается). Файл заменяется атомарно."""
    bl_idname = "gtatools.rebuild_img"
    bl_label = "INU: Rebuild IMG"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        s = getattr(context.scene, 'inu_settings', None)
        return bool(getattr(s, 'gtatools_img_path', '') if s else '')

    def execute(self, context):
        s = context.scene.inu_settings
        img_path = bpy.path.abspath(getattr(s, 'gtatools_img_path', '') or '')
        if not img_path or not os.path.isfile(img_path):
            self.report({'ERROR'}, T("Укажите существующий .img файл"))
            return {'CANCELLED'}
        try:
            from ..core.img import rebuild_img
            stats = rebuild_img(img_path)
        except Exception as e:
            self.report({'ERROR'}, f"Rebuild error: {e}")
            return {'CANCELLED'}
        saved_mb = stats['saved'] / (1024.0 * 1024.0)
        self.report({'INFO'}, T(
            "IMG перестроен: {0} записей, освобождено {1:.1f} МБ").format(
                stats['entries'], saved_mb))
        try:
            bpy.ops.gtatools.refresh_img_list()
        except Exception:
            pass
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
        for _ip in ipl_paths:
            try:
                want |= {(inst.model_name or '').lower() + '.dff'
                         for inst in read_ipl(_ip).instances if inst.model_name}
            except Exception:
                pass
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
    # Переопределение целевого IMG (пусто → gtatools_img_path). Позволяет
    # «Экспорт модели в IMG» слать в конкретный архив, не трогая основной путь.
    target_img: StringProperty(default="", options={'HIDDEN'})
    rebuild_after: BoolProperty(
        name=T("Пересобрать после экспорта"),
        description=T("После записи сжать (компактнуть) IMG-архив — убрать мёртвое место от старых версий моделей"),
        default=False,
    )

    def _own_img(self, context):
        """Родной IMG модели — img_target_file первой выделенной модели."""
        from ..tools.model_utils import find_all_selected_model_groups
        try:
            for _base, models in find_all_selected_model_groups().items():
                src = models['DFF'] or models['LOD']
                tf = getattr(getattr(src, 'inu', None), 'img_target_file', '') if src else ''
                if tf:
                    return tf
        except Exception:
            pass
        return ''

    def _target_img_path(self, context):
        # Цель берём из выпадающего списка диалога (scene-проперти
        # gtatools_export_img_target): конкретный архив, либо SELF →
        # родной IMG модели, либо общий путь gtatools_img_path.
        scn = context.scene
        choice = getattr(scn.inu_settings, 'gtatools_export_img_target', 'SELF')
        if choice and choice != 'SELF':
            return bpy.path.abspath(choice)
        own = self._own_img(context)
        if own:
            return bpy.path.abspath(own)
        if self.target_img:
            return bpy.path.abspath(self.target_img)
        return bpy.path.abspath(scn.inu_settings.gtatools_img_path)

    def invoke(self, context, event):
        from ..tools.model_utils import (
            find_all_selected_model_groups, find_related_models)
        from ..scene_settings import _export_img_target_items

        groups = find_all_selected_model_groups()
        if not groups:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        # Предвыбор в списке того IMG-архива, из которого пришла модель
        # (img_target_file). Если он есть среди .img папки игры — выбираем
        # его пунктом, иначе 'SELF' (родной IMG модели / общий путь).
        own_raw = self._own_img(context)
        if own_raw:
            own_n = os.path.normcase(os.path.normpath(bpy.path.abspath(own_raw)))
            target_val = 'SELF'
            for it in _export_img_target_items(None, context):
                if it[0] == 'SELF':
                    continue
                if os.path.normcase(os.path.normpath(bpy.path.abspath(it[0]))) == own_n:
                    target_val = it[0]
                    break
            try:
                context.scene.inu_settings.gtatools_export_img_target = target_val
            except Exception:
                pass

        img_path = self._target_img_path(context)
        if not img_path or not os.path.isfile(img_path):
            self.report({'ERROR'}, T("Укажите путь к .img архиву"))
            return {'CANCELLED'}

        # Pre-fill the dialog's shared-TXD widgets from the scene-level
        # unified toggle. Users configure once in the Unified Export
        # panel ("Общий TXD" + name); the dialog remembers that state
        # without them having to tick it again here.
        self.shared_txd = bool(getattr(
            context.scene, 'gtatools_export_all_txd_shared', False))
        self.shared_txd_name = getattr(
            context.scene, 'gtatools_export_all_txd_shared_name', 'textures') or 'textures'

        # Populate the WindowManager TXD plan collection. Pre-fill each row
        # with obj.inu.txd_name if set, otherwise fall back to base_name —
        # that matches the game's default "model and its TXD share a name".
        wm = context.window_manager
        wm.gtatools_txd_export_plan.clear()
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
            entry.lod_found = bool(lod_obj)
            entry.col_found = bool(col_obj)
            entry.lod_name = lod_obj.name if lod_obj else ""
            entry.col_name = col_obj.name if col_obj else ""
            entry.inc_lod = True
            entry.inc_col = True
        wm.gtatools_txd_export_plan_index = 0

        return wm.invoke_props_dialog(self, width=460)

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        scn = context.scene

        # Выбор целевого IMG-архива. По умолчанию — родной IMG модели
        # (предвыбран в invoke). Список: «Родной IMG модели» + все .img
        # из папки игры.
        layout.prop(scn.inu_settings, "gtatools_export_img_target",
                    text=T("IMG архив"))
        info = layout.box()
        info.label(text=f"{T('IMG:')} {os.path.basename(self._target_img_path(context))}",
                   **inu_icon(safe_icon('PACKAGE')))
        info.label(text=f"{T('Моделей:')} {len(wm.gtatools_txd_export_plan)}", **inu_icon(safe_icon('INFO')))

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
        # отступом — LOD и COL, каждая со своей галочкой. LOD/COL по
        # умолчанию выключены. Если LOD/COL нет в сцене — пометка «заглушка»
        # (LOD = копия основной модели, COL = пустая габаритная).
        layout.label(text=T("Что экспортировать:"))
        for entry in wm.gtatools_txd_export_plan:
            mb = layout.box().column(align=True)
            r = mb.row(align=True)
            r.prop(entry, "include", text="")
            rs = r.row(align=True)
            rs.active = entry.include
            rs.label(text="DFF: " + (entry.model_name or "?"),
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
            rs2.label(
                text=("LOD: " + entry.lod_name) if entry.lod_found
                else T("LOD: основная модель (заглушка)"),
                **inu_icon(safe_icon('MOD_DECIM')))
            # COL (с отступом).
            r3 = mb.row(align=True)
            r3.separator(factor=2.5)
            r3.prop(entry, "inc_col", text="")
            rs3 = r3.row(align=True)
            rs3.active = entry.inc_col
            rs3.label(
                text=("COL: " + entry.col_name) if entry.col_found
                else T("COL: пустая заглушка"),
                **inu_icon(safe_icon('MESH_CUBE')))

        layout.separator()
        layout.prop(self, "rebuild_after",
                    **inu_icon(safe_icon('FILE_REFRESH')))

    def execute(self, context):
        from ..core.img import ImgWriter
        from ..core.dff import GTA_SA_VERSION
        from ..core.col import write_col
        from ..tools.model_utils import find_all_selected_model_groups
        from ..tools.txd_export import export_txd
        from .dff_export import build_dff_clump
        from .col_export import build_col_model, export_col_library, audit_col

        img_path = self._target_img_path(context)
        if not img_path or not os.path.isfile(img_path):
            self.report({'ERROR'}, T("Укажите путь к .img архиву"))
            return {'CANCELLED'}

        model_groups = find_all_selected_model_groups()
        if not model_groups:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        # Что экспортировать теперь решают ПОЭЛЕМЕНТНЫЕ галочки диалога
        # (иерархия DFF → LOD/COL по каждой модели), а не глобальные тумблеры.
        # DFF+TXD идут по `include`; LOD по `inc_lod` (нет LOD в сцене → копия
        # основной модели); COL по `inc_col` (нет COL → пустая габаритная).
        col_library = bool(getattr(context.scene.inu_settings, 'gtatools_export_all_col_library', False))
        col_library_name = getattr(context.scene.inu_settings, 'gtatools_export_all_col_library_name', '') or 'collision'
        backend = getattr(context.scene.inu_settings, 'gtatools_dxt_backend', 'numpy')

        wm = context.window_manager
        plan_by_name = {}
        for entry in wm.gtatools_txd_export_plan:
            plan_by_name[entry.model_name] = entry

        def _plan_entry(base):
            return plan_by_name.get(base)

        def _is_included(base):
            # DFF (и TXD) модели включены.
            e = _plan_entry(base)
            return e.include if e is not None else True

        def _inc_lod(base):
            e = _plan_entry(base)
            return bool(e.inc_lod) if e is not None else False

        def _inc_col(base):
            e = _plan_entry(base)
            return bool(e.inc_col) if e is not None else False

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

        def _col_src(base, models):
            # Объект-источник COL (или None → пустая габаритная заглушка).
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

        # Propagate the edited TXD name back to obj.inu.txd_name so later
        # IDE/IPL writes pick up the same value.
        for base_name, models in model_groups.items():
            if not _is_included(base_name):
                continue
            new_txd = _txd_for(base_name)
            for mt in ('DFF', 'LOD'):
                obj = models[mt]
                if obj is not None and hasattr(obj, 'inu'):
                    obj.inu.txd_name = new_txd

        results = []
        # Счётчики для сводки в статус-баре: сколько DFF/LOD/COL/TXD реально
        # записано в архив (успешные writer.add), помимо списка файлов.
        n_dff = n_lod = n_col = n_txd = 0

        # Library COL bypasses the per-group COL loop: one multi-entry .col
        # is written once and stuffed into the archive under a shared name.
        # Собираем только те COL, что реально найдены и включены (inc_col).
        library_col_objects = []
        write_col_per_group = True
        if col_library:
            write_col_per_group = False
            for _base, _models in model_groups.items():
                if _inc_col(_base):
                    _cs = _col_src(_base, _models)
                    if _cs is not None:
                        library_col_objects.append(_cs)

        # Pick the DFF RW version + IMG archive version once for this
        # whole bulk export — scene's gtatools_game drives III/VC/SA
        # dispatch (RW 3.3/3.5/3.6 for DFF, COL v1/v2/v3, IMG VER1/VER2).
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
        # group, one tick per bucket, plus the optional library COL)
        # gives a meaningful live progress.
        included_groups = [(b, m) for b, m in model_groups.items() if _want_group(b)]
        total_steps = 0
        for _base, _m in included_groups:
            if _inc_lod(_base): total_steps += 1
            if _is_included(_base) and _m['DFF']: total_steps += 1
            if write_col_per_group and _inc_col(_base): total_steps += 1
        total_steps += len({_txd_for(b) for b, m in included_groups
                            if _is_included(b) and (m['DFF'] or m['LOD'])})
        if col_library and library_col_objects:
            total_steps += 1
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

        # IMG archive version: SA writes VER2 (single .img), III/VC
        # write VER1 (split .dir + .img). Read game off the scene via
        # GameProfile.img_version — keeps the existing op signature
        # untouched while still routing III/VC users to the right
        # archive layout.
        from ..core import game_versions as gv
        _img_version = gv.profile_for(
            gv.game_of_scene(context.scene)).img_version

        # #3: GTA SA IMG directory name field is 24 bytes, but the game reads
        # it as a C-string and force-terminates name[23]='\0' (CdDirectory) —
        # so the USABLE max is 23 chars: exactly-24 loses its last char (.dff
        # → .df) and no longer matches the IDE/IPL reference → invisible
        # model. Note the LOD name is 'LOD'+base+'.dff' (= base + 7 chars),
        # so it overflows first. Validate up front and refuse rather than
        # write a broken archive. (Same 23+NUL pattern as map_lint.py.)
        _NAME_MAX = 23
        _too_long = []
        for _bn, _models in model_groups.items():
            if not _want_group(_bn):
                continue
            _names = []
            if _is_included(_bn) and _models['DFF']:
                _names.append(_bn + '.dff')
            if _inc_lod(_bn):
                _names.append('LOD' + _bn + '.dff')
            if write_col_per_group and _inc_col(_bn):
                _names.append(_bn + '.col')
            if _is_included(_bn) and (_models['DFF'] or _models['LOD']):
                _names.append(_txd_for(_bn) + '.txd')
            for _nm in _names:
                if len(_nm.encode('ascii', errors='replace')) > _NAME_MAX:
                    _too_long.append(_nm)
        if _too_long:
            self.report({'ERROR'}, T(
                "Имя для IMG длиннее 23 символов — обрежется и не совпадёт "
                "с IDE/IPL: {0}. Укороти имя модели.").format(
                    ", ".join(_too_long[:5]) + ("…" if len(_too_long) > 5 else "")))
            return {'CANCELLED'}

        try:
            with tempfile.TemporaryDirectory() as tmpdir, ImgWriter(img_path, version=_img_version) as writer:
                # Bucket DFF/LOD objects by their resolved TXD name so every
                # bucket produces exactly one .txd containing merged textures.
                txd_buckets = defaultdict(list)
                encode_jobs: list = []  # (filename, callable_returning_bytes, label)

                for base_name, models in model_groups.items():
                    if not _want_group(base_name):
                        continue

                    if _inc_lod(base_name):
                        lod_name = 'LOD' + base_name
                        # Источник LOD: найденный в сцене LOD, иначе — копия
                        # основной модели (заглушка) под LOD-именем.
                        lod_obj = _lod_src(base_name, models)
                        if lod_obj is None:
                            results.append(f"{lod_name}.dff: нет геометрии-источника")
                        else:
                            try:
                                clump = build_dff_clump([lod_obj], version=dff_rw_version, col_model_name=lod_name)
                                if dff_target_platform == 'MOBILE':
                                    for g in clump.geometries:
                                        if not g.raw_native_data_plg:
                                            g.is_native_ogl = True
                                    clump.is_mobile = True
                                encode_jobs.append((lod_name + '.dff', clump.to_bytes, f"{lod_name}.dff"))
                            except Exception as e:
                                results.append(f"{lod_name}.dff error: {e}")
                                _tick(f"{lod_name}.dff")

                    if _is_included(base_name) and models['DFF']:
                        try:
                            dff_objs = [models['DFF']]
                            for child in models['DFF'].children:
                                if child.type == 'EMPTY' and getattr(child, 'inu', None) and child.inu.type == '2DFX':
                                    dff_objs.append(child)
                            clump = build_dff_clump(dff_objs, version=dff_rw_version, col_model_name=base_name)
                            if dff_target_platform == 'MOBILE':
                                for g in clump.geometries:
                                    if not g.raw_native_data_plg:
                                        g.is_native_ogl = True
                                clump.is_mobile = True
                            encode_jobs.append((base_name + '.dff', clump.to_bytes, f"{base_name}.dff"))
                        except Exception as e:
                            results.append(f"{base_name}.dff error: {e}")
                            _tick(f"{base_name}.dff")

                    if write_col_per_group and _inc_col(base_name):
                        try:
                            col_obj = _col_src(base_name, models)
                            is_empty = col_obj is None   # нет COL → заглушка
                            col_src = [col_obj] if col_obj else []
                            # Empty COL → measure bounds off the visual model so
                            # GTA doesn't cull it (zero sphere = disappears).
                            _bref = None
                            if is_empty:
                                _vis = models['DFF'] or models['LOD']
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
                            encode_jobs.append((base_name + '.col', (lambda m=col_model: write_col([m], target_game=col_target_game)), f"{base_name}.col"))
                        except Exception as e:
                            results.append(f"{base_name}.col error: {e}")
                            _tick(f"{base_name}.col")

                    if _is_included(base_name) and (models['DFF'] or models['LOD']):
                        bucket_name = _txd_for(base_name)
                        for mt in ('DFF', 'LOD'):
                            if models[mt] is not None:
                                txd_buckets[bucket_name].append(models[mt])

                if encode_jobs:
                    enc_workers = min(os.cpu_count() or 4, 4)
                    with ThreadPoolExecutor(max_workers=enc_workers) as enc_pool:
                        futures = [(filename, label, enc_pool.submit(encoder)) for filename, encoder, label in encode_jobs]
                        for filename, label, fut in futures:
                            try:
                                data = fut.result()
                                status = writer.add(filename, data)
                                results.append(f"{filename} {status}")
                                _low = filename.lower()
                                if _low.endswith('.col'):
                                    n_col += 1
                                elif _low.endswith('.dff') and filename.startswith('LOD'):
                                    n_lod += 1
                                elif _low.endswith('.dff'):
                                    n_dff += 1
                            except Exception as e:
                                results.append(f"{filename} error: {e}")
                            _tick(label)

                if txd_buckets:
                    for txd_name, sources in txd_buckets.items():
                        if not sources:
                            continue
                        txd_path = os.path.join(tmpdir, txd_name + '.txd')
                        prev_active = context.view_layer.objects.active
                        prev_selected = [o for o in context.selected_objects]
                        try:
                            bpy.ops.object.select_all(action='DESELECT')
                            for src in sources:
                                src.select_set(True)
                            context.view_layer.objects.active = sources[0]
                            result, msg, _ = export_txd(txd_path, context, True, backend=backend)
                            if result == {'FINISHED'}:
                                with open(txd_path, 'rb') as f:
                                    status = writer.add(txd_name + '.txd', f.read())
                                results.append(f"{txd_name}.txd {status} ({len(sources)} models)")
                                n_txd += 1
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

                if col_library and library_col_objects:
                    lib_filename = f"{col_library_name}.col"
                    original_locations = {}
                    try:
                        lib_path = os.path.join(tmpdir, lib_filename)
                        for obj in library_col_objects:
                            original_locations[obj.name] = obj.location.copy()
                            obj.location = (0, 0, 0)
                        count = export_col_library(lib_path, library_col_objects, version=col_version, empty=False)
                        with open(lib_path, 'rb') as f:
                            status = writer.add(lib_filename, f.read())
                        results.append(f"{lib_filename} {status} ({count} records)")
                        n_col += count
                    except Exception as e:
                        results.append(f"{col_library_name}.col error: {e}")
                    finally:
                        for obj in library_col_objects:
                            if obj.name in original_locations:
                                obj.location = original_locations[obj.name]
                    _tick(lib_filename)

                # Пулы движка: игра грузит ВСЕГО ≤255 отдельных .col-файлов и
                # ≤10150 COL-моделей (CColModel). Аддон не знает всю игру, но
                # предупреждает, если сам этот экспорт упирается в лимит —
                # тогда стоит объединить коллизии в один library .col.
                _n_col_files = sum(1 for _fn, _e, _l in encode_jobs
                                   if _fn.lower().endswith('.col'))
                if col_library and library_col_objects:
                    _n_col_files += 1
                if _n_col_files > 255:
                    results.append(T(
                        "⚠ .col-файлов за экспорт: {0} — движок грузит ≤255 "
                        "всего. Объедини коллизии в один library .col.").format(
                            _n_col_files))
                if n_col > 10150:
                    results.append(T(
                        "⚠ COL-моделей: {0} — лимит движка 10150 (CColModel).")
                        .format(n_col))
        except PermissionError:
            # .img заблокирован (чаще всего запущена игра, которая держит
            # архив открытым). Не роняем оператор трейсбеком — показываем
            # понятное предупреждение внизу и мягко отменяем экспорт.
            self.report({'WARNING'}, T(
                "Файл .img занят — закрой игру перед экспортом: {0}").format(
                    os.path.basename(img_path)))
            return {'CANCELLED'}
        finally:
            # Always reset UI progress/status, even on unexpected error.
            wm.progress_end()
            context.workspace.status_text_set(None)

        from .. import _append_export_report
        # Пересборка (компактирование) архива сразу после экспорта — по галочке.
        if self.rebuild_after:
            try:
                from ..core.img import rebuild_img
                _st = rebuild_img(img_path)
                _mb = _st['saved'] / (1024.0 * 1024.0)
                results.append(f"rebuild: {_st['entries']} записей, -{_mb:.1f} МБ")
            except Exception as e:
                results.append(f"rebuild error: {e}")
        _refresh_img_entries(context.scene, img_path)
        try:
            report_path = os.path.join(os.path.dirname(img_path), "_export_report.txt")
            rows = [f"IMG: {img_path}"]
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
            # Common pitfall ("новый DFF не появляется в игре"): the
            # archive directory updates but external IMG editors / game
            # caches may keep showing the old entry until a Rebuild
            # Archive pass. Status-bar shows the *latest* report — make
            # this the visible one; the file list above stays accessible
            # via the report-log click-through.
            if not self.rebuild_after:
                self.report(
                    {'INFO'},
                    T("Rebuild Archive в IMG-туле — иначе игра подтянет старую запись"))
        else:
            self.report({'WARNING'}, T("IMG: нет результатов экспорта"))
        return {'FINISHED'}


