# INU_tools.ops.floater.iii
#
# IdeIplImgFloater — mirror of GTATOOLS_PT_ide_ipl_panel (panels.py).
# Three boxed sections stacked vertically:
#   * IDE box  — Add / Del / Import / Export
#   * IPL box  — Add / Del / Import / Export
#                + full-width "Секции IPL" Import/Export row
#                + full-width "Заменить Empty" row
#   * IMG box  — three independent toggles (Skip LOD / TXD / COL)
#                bound to scene.inu_settings props, then full-width
#                Import / Export / Remove from IMG ops.

import bpy

from ...ui import layout_rules as LR
from . import theme as TH
from . import gpu_shaders as GS
from . import text_atlas as TA
from . import widgets as WG
from . import base as B


def _invoke_op_from_npanel(context, op_id: str):
    """Invoke ``op_id`` (e.g. ``gtatools.link_sync``) as if the user
    clicked the equivalent N-panel button.

    Synchronous, no timer — runs inside the floater's click event
    handler with a live ``bpy.context`` and a region override that
    pretends to come from a 3D-View N-panel (``UI`` region).  This
    makes Blender route ``self.report({'INFO'}, ...)`` through the
    same visibility path a real N-panel click uses.
    """
    live = bpy.context
    target_window = None
    target_area = None
    target_region = None
    for window in live.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for region in area.regions:
                if region.type == 'UI':
                    target_window = window
                    target_area = area
                    target_region = region
                    break
            if target_region is not None:
                break
        if target_region is not None:
            break

    parts = op_id.split('.')
    op = bpy.ops
    for p in parts:
        op = getattr(op, p)

    B._floater_dispatch_active = True
    try:
        if target_region is not None:
            with live.temp_override(
                    window=target_window,
                    area=target_area,
                    region=target_region):
                op('INVOKE_DEFAULT')
        else:
            op('INVOKE_DEFAULT')
    except Exception as ex:
        print(f"[IDE/IPL Floater] {op_id} failed: {ex}")
    finally:
        B._floater_dispatch_active = False


# Padding between the section box's outline and its inner content.
# Asymmetric: top is tight (header читается ближе к верхней рамке),
# bottom + sides шире — даёт «дышать» нижнему ряду кнопок и не
# даёт текстам прилипать к боковым граням.
_BOX_PAD_TOP = 1
_BOX_PAD_BOT = 5
_BOX_PAD_X   = 5

# Adjacent buttons inside a fused cluster overlap by 1 px so their
# outlines merge into a single shared 1-px divider line — same trick
# native `row.prop_enum` uses, encapsulated in `WG._enum_row_rects`.
_FUSED_OVERLAP = 1


class IdeIplImgFloater(B.Floater):
    """N-panel IDE/IPL/IMG mirror — full action surface for working
    with existing GTA-SA files."""

    def __init__(self):
        super().__init__(
            name='iii',
            title='IDE / IPL / IMG',
            prop_names={
                'visible':   'inu_floater_iii_visible',
                'collapsed': 'inu_floater_iii_collapsed',
                'locked':    'inu_floater_iii_locked',
                'workspace': 'inu_floater_iii_workspace',
                'x':         'inu_floater_iii_x',
                'y':         'inu_floater_iii_y',
            },
            default_pos=(640, 400),
            # Wider than the 220 default — IDE+IPL columns need ~140-150 px
            # each so the icon+label buttons don't crowd the box edges,
            # and the IMG box's "Импорт из IMG" / "Экспорт в IMG" /
            # "Удалить из IMG" labels have room to breathe.
            width=310,
        )
        self.title_icon = 'file_folder'

    # ── Heights ─────────────────────────────────────────────────────

    # Compact text-label row height used for counts + status lines
    # inside each box.  Smaller than full buttons since they're
    # read-only display, not clickable.
    _LABEL_H = 14

    def _ide_ipl_box_h(self):
        # 3 button rows + 2 label rows (file counts + per-object status).
        # Header is separated by `_BTN_GAP` from the action cluster;
        # the 2-row action cluster itself uses 1-px vertical overlap;
        # label rows sit below the action cluster with a small gap.
        return (3 * TH._BUTTON_H
                + self._LABEL_H + 2                  # path row под заголовком
                + WG._BTN_GAP                        # path → row1
                + (-_FUSED_OVERLAP)                  # row1 ↔ row2 overlap
                + 4                                  # row2 → counts label
                + 2 * self._LABEL_H + 2              # counts + status + gap
                + _BOX_PAD_TOP + _BOX_PAD_BOT)

    def _img_box_h(self):
        # 4 inner rows: header, 3-toggle row, Import+Export pair, Remove.
        # Internal rows fused via overlap (4 rows = 3 overlaps of 1 px).
        return (4 * TH._BUTTON_H - 3 * _FUSED_OVERLAP
                + self._LABEL_H + 4                  # path row под заголовком
                + _BOX_PAD_TOP + _BOX_PAD_BOT)

    def compute_body_height(self, context):
        # Outer blocks (IDE/IPL pair, Sync/Unlink/Verify row,
        # Секции IPL, Заменить Empty, IMG) фузятся overlap'ом тоже —
        # единый вертикальный кластер без 18-px gap'ов.
        return (
            self._ide_ipl_box_h()
            - _FUSED_OVERLAP + TH._BUTTON_H   # Sync/Unlink/Verify row
            - _FUSED_OVERLAP + TH._BUTTON_H   # "Секции IPL" row
            - _FUSED_OVERLAP + TH._BUTTON_H   # "Заменить Empty" row
            - _FUSED_OVERLAP + self._img_box_h()
        )

    # ── Layout ──────────────────────────────────────────────────────

    def extend_body_layout(self, context, L):
        x, w = L['x'], L['w']
        top_y = L['body_top_y']
        inner_x = x + TH._PAD
        inner_w = w - 2 * TH._PAD

        # ── Side-by-side IDE | IPL boxes ──
        # Боксы прижаты друг к другу через 1-px overlap, как fused
        # button pair: правый край IDE и левый край IPL рисуют одну и ту же
        # пиксельную линию → визуально это единый бокс с 1-px разделителем
        # посередине, без двойной обводки.
        ide_ipl_h = self._ide_ipl_box_h()
        ide_ipl_y = top_y - ide_ipl_h
        col_gap = -_FUSED_OVERLAP
        col_w = (inner_w - col_gap) // 2
        L['ide_box_rect'] = (inner_x, ide_ipl_y, col_w, ide_ipl_h)
        L['ipl_box_rect'] = (inner_x + col_w + col_gap, ide_ipl_y, col_w, ide_ipl_h)

        # Each box: header row at top (separate), then a 2×2 fused
        # action cluster (Add/Del on top, Import/Export below).
        # Inside the cluster every adjacent pair overlaps by 1 px so
        # outlines fuse into single dividers. Corner masks (set in
        # draw_body) round only the cluster's 4 outer corners.
        def _layout_box_rows(box_rect):
            bx, by, bw, bh = box_rect
            ix = bx + _BOX_PAD_X
            iw = bw - 2 * _BOX_PAD_X
            header_y = by + bh - _BOX_PAD_TOP - TH._BUTTON_H
            # Короткий путь к файлу — сразу под заголовком.
            path_y = header_y - 2 - self._LABEL_H
            # Path → row1: regular gap (independent groups visually).
            row1_y = path_y - WG._BTN_GAP - TH._BUTTON_H
            # row1 ↔ row2: 1-px vertical overlap so the two action rows
            # read as one fused 2×2 cluster.
            row2_y = row1_y - TH._BUTTON_H + _FUSED_OVERLAP
            # Counts + status — two compact text-only rows below the
            # action cluster.  4-px gap separates them from the
            # buttons (they're informational, not interactive).
            counts_y = row2_y - 4 - self._LABEL_H
            status_y = counts_y - 2 - self._LABEL_H
            r1_l, r1_r = WG._enum_row_rects((ix, row1_y, iw, TH._BUTTON_H), 2)
            r2_l, r2_r = WG._enum_row_rects((ix, row2_y, iw, TH._BUTTON_H), 2)
            return {
                'header': (ix, header_y, iw, TH._BUTTON_H),
                'path': (ix, path_y, iw, self._LABEL_H),
                'r1_l': r1_l, 'r1_r': r1_r,
                'r2_l': r2_l, 'r2_r': r2_r,
                'counts': (ix, counts_y, iw, self._LABEL_H),
                'status': (ix, status_y, iw, self._LABEL_H),
            }

        ide_r = _layout_box_rows(L['ide_box_rect'])
        L['ide_header_rect'] = ide_r['header']
        L['ide_path_rect']   = ide_r['path']
        L['ide_add_rect']    = ide_r['r1_l']
        L['ide_del_rect']    = ide_r['r1_r']
        L['ide_import_rect'] = ide_r['r2_l']
        L['ide_export_rect'] = ide_r['r2_r']
        L['ide_counts_rect'] = ide_r['counts']
        L['ide_status_rect'] = ide_r['status']

        ipl_r = _layout_box_rows(L['ipl_box_rect'])
        L['ipl_header_rect'] = ipl_r['header']
        L['ipl_path_rect']   = ipl_r['path']
        L['ipl_add_rect']    = ipl_r['r1_l']
        L['ipl_del_rect']    = ipl_r['r1_r']
        L['ipl_import_rect'] = ipl_r['r2_l']
        L['ipl_export_rect'] = ipl_r['r2_r']
        L['ipl_counts_rect'] = ipl_r['counts']
        L['ipl_status_rect'] = ipl_r['status']

        # ── Unified Sync / Unlink / Verify row (works on both IDE+IPL) ──
        # Прижата к IDE/IPL коробкам через 1-px overlap.
        link_y = ide_ipl_y + _FUSED_OVERLAP - TH._BUTTON_H
        (L['link_sync_rect'],
         L['link_unlink_rect'],
         L['link_verify_rect']) = WG._enum_row_rects(
            (inner_x, link_y, inner_w, TH._BUTTON_H), 3)

        # ── Full-width "Секции IPL" Import / Export — fused pair ──
        sec_y = link_y + _FUSED_OVERLAP - TH._BUTTON_H
        L['sec_import_rect'], L['sec_export_rect'] = WG._enum_row_rects(
            (inner_x, sec_y, inner_w, TH._BUTTON_H), 2)

        # ── Full-width "Заменить Empty" row ──
        rep_y = sec_y + _FUSED_OVERLAP - TH._BUTTON_H
        L['replace_empty_rect'] = (inner_x, rep_y, inner_w, TH._BUTTON_H)

        # ── IMG box ── также fused с предыдущими.
        img_h = self._img_box_h()
        img_y = rep_y + _FUSED_OVERLAP - img_h
        L['img_box_rect'] = (inner_x, img_y, inner_w, img_h)
        ix = inner_x + _BOX_PAD_X
        iw = inner_w - 2 * _BOX_PAD_X

        img_header_y = img_y + img_h - _BOX_PAD_TOP - TH._BUTTON_H
        # Короткий путь к .img — под заголовком.
        img_path_y = img_header_y - 2 - self._LABEL_H
        L['img_path_rect'] = (ix, img_path_y, iw, self._LABEL_H)
        # Path → toggle row, toggle → Import, Import → Export,
        # Export → Remove — все через 1-px overlap, без 18-px gap.
        toggle_y = img_path_y - TH._BUTTON_H
        L['img_header_rect'] = (ix, img_header_y, iw, TH._BUTTON_H)

        # 3-toggle row — fused via `_enum_row_rects`.
        (L['skip_lod_rect'],
         L['txd_rect'],
         L['col_rect']) = WG._enum_row_rects(
            (ix, toggle_y, iw, TH._BUTTON_H), 3)

        # Import + Export — fused pair в одной строке (раньше шли
        # столбиком), затем Remove — full-width под ними.
        imp_exp_y = toggle_y + _FUSED_OVERLAP - TH._BUTTON_H
        L['img_import_rect'], L['img_export_rect'] = WG._enum_row_rects(
            (ix, imp_exp_y, iw, TH._BUTTON_H), 2)
        rem_y = imp_exp_y + _FUSED_OVERLAP - TH._BUTTON_H
        L['img_remove_rect'] = (ix, rem_y, iw, TH._BUTTON_H)

    # ── Draw ────────────────────────────────────────────────────────

    # ── Label helpers (read-only info inside IDE / IPL boxes) ──

    def _draw_label_line(self, rect, text, icon_name=None,
                         color=None):
        """Compact single-line label with optional left-icon.
        Used for counts and status — read-only, no hit testing."""
        if rect is None or not text:
            return
        x, y, w, h = rect
        ix = x + 4
        # Иконка слева — крупнее (как в N-панели), а не зажата в 12 px.
        icon_w = 0
        if icon_name:
            icon_size = max(12, min(16, h - 1))
            iy = y + (h - icon_size) // 2
            GS._draw_icon((ix, iy, icon_size, icon_size),
                          icon_name, tint=(color or TH._C_TEXT))
            ix += icon_size + 3
            icon_w = icon_size + 3
        # Compute max text width that fits, truncate with ellipsis
        # so long IDE/IPL paths don't overflow the column.
        avail = max(0, w - 8 - icon_w)
        tw, th = TA._text_dims(text)
        if tw > avail:
            # naive char-trim — TA._text_dims is per-string, so iterate.
            while text and TA._text_dims(text + "…")[0] > avail:
                text = text[:-1]
            text = text + "…" if text else ""
        ty = y + (h - th) // 2
        # Белый (как в N-панели), а не тусклый _C_LABEL.
        TA._text(int(ix), int(ty), text, color or TH._C_TEXT)

    @staticmethod
    def _short_path(p):
        """Короткий путь — последние 2 сегмента (как в N-панели:
        Props_obj\\GR_props.ide)."""
        import os
        p = bpy.path.abspath(p or '')
        if not p:
            return ''
        parts = p.replace('/', os.sep).rstrip(os.sep).split(os.sep)
        parts = [s for s in parts if s]
        return os.sep.join(parts[-2:]) if len(parts) >= 2 else (
            parts[-1] if parts else '')

    def _draw_path(self, context, rect, prop):
        """Строка с коротким путём к IDE/IPL/IMG файлу (белым, под
        заголовком бокса). Пусто — «Файл не выбран»."""
        if rect is None:
            return
        raw = getattr(context.scene.inu_settings, prop, '') or ''
        short = self._short_path(raw)
        self._draw_label_line(rect, short or "Файл не выбран",
                              icon_name='text')

    def _draw_ide_counts(self, context, rect):
        scn = context.scene
        path = bpy.path.abspath(scn.inu_settings.gtatools_ide_path)
        import os
        if not (path and os.path.isfile(path)):
            return
        try:
            from ...core.ide import read_ide
            ide = read_ide(path)
            parts = []
            if ide.objects: parts.append(f"objs: {len(ide.objects)}")
            if ide.anims:   parts.append(f"anim: {len(ide.anims)}")
            if ide.cars:    parts.append(f"cars: {len(ide.cars)}")
            if ide.peds:    parts.append(f"peds: {len(ide.peds)}")
            if ide.txdps:   parts.append(f"txdp: {len(ide.txdps)}")
            if parts:
                self._draw_label_line(rect, ", ".join(parts),
                                      icon_name='info')
        except Exception:
            pass

    def _draw_ipl_counts(self, context, rect):
        scn = context.scene
        path = bpy.path.abspath(scn.inu_settings.gtatools_ipl_path)
        import os
        if not (path and os.path.isfile(path)):
            return
        try:
            from ...core.ipl import read_ipl
            ipl = read_ipl(path)
            parts = []
            if ipl.instances: parts.append(f"inst: {len(ipl.instances)}")
            if ipl.culls:     parts.append(f"cull: {len(ipl.culls)}")
            if ipl.garages:   parts.append(f"grge: {len(ipl.garages)}")
            if ipl.enexs:     parts.append(f"enex: {len(ipl.enexs)}")
            if ipl.pickups:   parts.append(f"pick: {len(ipl.pickups)}")
            if ipl.cars:      parts.append(f"cars: {len(ipl.cars)}")
            if ipl.jumps:     parts.append(f"jump: {len(ipl.jumps)}")
            if ipl.auzos:     parts.append(f"auzo: {len(ipl.auzos)}")
            if ipl.occls:     parts.append(f"occl: {len(ipl.occls)}")
            if ipl.zones:     parts.append(f"zone: {len(ipl.zones)}")
            if parts:
                self._draw_label_line(rect, ", ".join(parts),
                                      icon_name='info')
        except Exception:
            pass

    def _draw_ide_status(self, context, rect):
        # Тот же статус, что в N-панели (сравнение с тем, что уйдёт в файл).
        from ... import T
        from ..map_link import ide_status
        ao = context.active_object
        if ao is None or ao.type != 'MESH' or not hasattr(ao, 'inu'):
            return
        text, arg, icon, _id_changed = ide_status(ao)
        self._draw_label_line(rect, T(text).format(arg),
                              icon_name=icon.lower())

    def _draw_ipl_status(self, context, rect):
        from ... import T
        from ..map_link import ipl_status, panel_main
        ao = context.active_object
        if ao is None or ao.type != 'MESH' or not hasattr(ao, 'inu'):
            return
        # Меш модели из нескольких мешей — статус её главного меша.
        text, arg, icon = ipl_status(panel_main(ao))
        self._draw_label_line(rect, T(text).format(arg),
                              icon_name=icon.lower())

    def _draw_section_header(self, rect, label, icon_name):
        """Section header inside a `_draw_box`: icon at left edge, label
        next to it. Same `_C_TEXT` colour as the action buttons below —
        раньше использовался dim `_C_LABEL`, из-за чего текст читался
        как «неактивный»."""
        x, y, w, h = rect
        icon_size = LR.icon_size()
        icon_x = x + 4
        icon_y = y + (h - icon_size) // 2
        GS._draw_icon((icon_x, icon_y, icon_size, icon_size),
                      icon_name, tint=TH._C_TEXT)
        tw, th = TA._text_dims(label)
        tx = icon_x + icon_size + 4
        ty = y + (h - th) // 2
        TA._text(int(tx), int(ty), label, TH._C_TEXT)

    def draw_body(self, context, L):
        st = self.state
        h = st.hover_button

        # ── IDE box ──
        # Force-English labels mirror the N-panel (panels.py uses
        # `translate=False` for these): "Add"/"Del"/"Import"/"Export"
        # are universally readable, and the localised forms
        # ("Добавить"/"Импорт"/"Экспорт") expand wide enough to overflow
        # the narrow side-by-side columns.
        #
        # The 4 action buttons form a fused 2×2 cluster — only the
        # outer 4 corners (TL on add, TR on del, BL on import, BR on
        # export) are rounded; the rest = CORNER_NONE so the inner
        # cross divider is a single 1-px line.
        # IDE box — слева вверху общего fused-блока: TL свободен,
        # TR прилегает к IPL через 1-px overlap, BL/BR прилегают к
        # Секции IPL ниже.
        WG._draw_box(L['ide_box_rect'], corner_mask=GS.CORNER_TL)
        self._draw_section_header(L['ide_header_rect'], "IDE", 'text')
        self._draw_path(context, L.get('ide_path_rect'), 'gtatools_ide_path')
        WG._draw_button(L['ide_add_rect'], "Add",
                        hovered=(h == 'ide_add'), icon='add',
                        translate=False, corner_mask=GS.CORNER_TL)
        WG._draw_button(L['ide_del_rect'], "Del",
                        hovered=(h == 'ide_del'), icon='remove',
                        translate=False, corner_mask=GS.CORNER_TR)
        WG._draw_button(L['ide_import_rect'], "Import",
                        hovered=(h == 'ide_import'), icon='import',
                        translate=False, corner_mask=GS.CORNER_BL)
        WG._draw_button(L['ide_export_rect'], "Export",
                        hovered=(h == 'ide_export'), icon='export',
                        translate=False, corner_mask=GS.CORNER_BR)

        # IPL box — справа вверху: TR свободен, TL прилегает к IDE,
        # BL/BR прилегают к Секции IPL ниже.
        WG._draw_box(L['ipl_box_rect'], corner_mask=GS.CORNER_TR)
        self._draw_section_header(L['ipl_header_rect'], "IPL", 'empty_axis')
        self._draw_path(context, L.get('ipl_path_rect'), 'gtatools_ipl_path')
        WG._draw_button(L['ipl_add_rect'], "Add",
                        hovered=(h == 'ipl_add'), icon='add',
                        translate=False, corner_mask=GS.CORNER_TL)
        WG._draw_button(L['ipl_del_rect'], "Del",
                        hovered=(h == 'ipl_del'), icon='remove',
                        translate=False, corner_mask=GS.CORNER_TR)
        WG._draw_button(L['ipl_import_rect'], "Import",
                        hovered=(h == 'ipl_import'), icon='import',
                        translate=False, corner_mask=GS.CORNER_BL)
        WG._draw_button(L['ipl_export_rect'], "Export",
                        hovered=(h == 'ipl_export'), icon='export',
                        translate=False, corner_mask=GS.CORNER_BR)

        # ── Counts + status labels (read-only, inside each box) ──
        # Mirror panels.py: file counts on top row, active-object
        # link status on the bottom row.  Read-only — no hover/click.
        self._draw_ide_counts(context, L.get('ide_counts_rect'))
        self._draw_ide_status(context, L.get('ide_status_rect'))
        self._draw_ipl_counts(context, L.get('ipl_counts_rect'))
        self._draw_ipl_status(context, L.get('ipl_status_rect'))

        # ── Sync / Unlink / Verify row — unified link tracking ──
        # Single fused 3-button strip that drives both IDE and IPL
        # via the wrapper operators in ops/ide_ipl.py.  ``translate=
        # False`` keeps the labels literally English; without it
        # Blender's built-in i18n rewrites them to localised forms
        # ("Синхронизация" / "Отсоединить") which clash with how the
        # rest of the link-tracking workflow is labelled in INU.
        WG._draw_button(L['link_sync_rect'], "Sync",
                        hovered=(h == 'link_sync'), icon='file_refresh',
                        translate=False, corner_mask=GS.CORNER_NONE)
        WG._draw_button(L['link_unlink_rect'], "Unlink",
                        hovered=(h == 'link_unlink'), icon='unlinked',
                        translate=False, corner_mask=GS.CORNER_NONE)
        WG._draw_button(L['link_verify_rect'], "Verify",
                        hovered=(h == 'link_verify'), icon='checkmark',
                        translate=False, corner_mask=GS.CORNER_NONE)

        # Секции IPL pair и Заменить Empty — все сидят в едином fused
        # столбце между IDE/IPL коробками сверху и IMG коробкой снизу.
        # Никакая сторона свободной не остаётся, поэтому CORNER_NONE
        # на всех — никаких лишних скруглений рядом с соседями.
        WG._draw_button(L['sec_import_rect'], "Секции IPL",
                        hovered=(h == 'sec_import'), icon='import',
                        corner_mask=GS.CORNER_NONE)
        WG._draw_button(L['sec_export_rect'], "Секции IPL",
                        hovered=(h == 'sec_export'), icon='export',
                        corner_mask=GS.CORNER_NONE)
        WG._draw_button(L['replace_empty_rect'], "Заменить Empty",
                        hovered=(h == 'replace_empty'), icon='mesh_data',
                        corner_mask=GS.CORNER_NONE)

        # ── IMG box ── TL/TR прилегают к "Заменить Empty" через overlap,
        # поэтому скругляем только BL/BR.
        WG._draw_box(L['img_box_rect'], corner_mask=GS.CORNER_BOTTOM)
        self._draw_section_header(L['img_header_rect'], "IMG", 'package')
        self._draw_path(context, L.get('img_path_rect'), 'gtatools_img_path')

        settings = context.scene.inu_settings
        skip_lod = bool(getattr(settings, 'gtatools_img_skip_lod', False))
        load_txd = bool(getattr(settings, 'gtatools_img_load_txd', False))
        load_col = bool(getattr(settings, 'gtatools_map_load_col', False))
        # 3-toggle row: TL/TR свободны у крайних (под ними нет кнопок,
        # сверху только header-label без рамки), BL/BR прилегают к
        # Import/Export ряду ниже.
        WG._draw_button(L['skip_lod_rect'], "Skip LOD",
                        hovered=(h == 'skip_lod'), pressed=skip_lod,
                        corner_mask=GS.CORNER_TL)
        WG._draw_button(L['txd_rect'], "TXD",
                        hovered=(h == 'txd'), pressed=load_txd,
                        corner_mask=GS.CORNER_NONE)
        WG._draw_button(L['col_rect'], "COL",
                        hovered=(h == 'col'), pressed=load_col,
                        corner_mask=GS.CORNER_TR)

        # Import/Export — зажаты между toggle row сверху и Remove снизу,
        # все 4 угла прилегают к соседям → CORNER_NONE.
        WG._draw_button(L['img_import_rect'], "Импорт из IMG",
                        hovered=(h == 'img_import'), icon='import',
                        corner_mask=GS.CORNER_NONE)
        WG._draw_button(L['img_export_rect'], "Экспорт в IMG",
                        hovered=(h == 'img_export'), icon='export',
                        corner_mask=GS.CORNER_NONE)
        # Remove — нижняя кнопка кластера: TL/TR прилегают к Import/Export,
        # BL/BR оставляем скруглёнными (внутренний нижний край IMG-бокса).
        WG._draw_button(L['img_remove_rect'], "Удалить из IMG",
                        hovered=(h == 'img_remove'), icon='remove',
                        corner_mask=GS.CORNER_BOTTOM)

    # ── Events ──────────────────────────────────────────────────────

    _HOVER_TARGETS = [
        ('ide_add',       'ide_add_rect'),
        ('ide_del',       'ide_del_rect'),
        ('ide_import',    'ide_import_rect'),
        ('ide_export',    'ide_export_rect'),
        ('ipl_add',       'ipl_add_rect'),
        ('ipl_del',       'ipl_del_rect'),
        ('ipl_import',    'ipl_import_rect'),
        ('ipl_export',    'ipl_export_rect'),
        ('link_sync',     'link_sync_rect'),
        ('link_unlink',   'link_unlink_rect'),
        ('link_verify',   'link_verify_rect'),
        ('sec_import',    'sec_import_rect'),
        ('sec_export',    'sec_export_rect'),
        ('replace_empty', 'replace_empty_rect'),
        ('skip_lod',      'skip_lod_rect'),
        ('txd',           'txd_rect'),
        ('col',           'col_rect'),
        ('img_import',    'img_import_rect'),
        ('img_export',    'img_export_rect'),
        ('img_remove',    'img_remove_rect'),
    ]

    def handle_body_mousemove(self, context, L, mx, my):
        st = self.state
        was = st.hover_button
        st.hover_button = None
        for key, rect_name in self._HOVER_TARGETS:
            r = L.get(rect_name)
            if r and B._hit(mx, my, *r):
                st.hover_button = key
                break
        return was != st.hover_button

    # Click targets that just fire an operator with no kwargs. Keys
    # match `_HOVER_TARGETS` so the same key drives hover + press, and
    # the toggle targets below override the three IMG-filter keys.
    _BUTTON_OPS = {
        'ide_add':       "gtatools.upsert_ide",
        'ide_del':       "gtatools.remove_ide",
        'ide_import':    "gtatools.import_ide",
        'ide_export':    "gtatools.export_ide",
        'ipl_add':       "gtatools.upsert_ipl",
        'ipl_del':       "gtatools.remove_ipl",
        'ipl_import':    "gtatools.import_ipl",
        'ipl_export':    "gtatools.export_ipl",
        'link_sync':     "gtatools.link_sync",
        'link_unlink':   "gtatools.link_unlink",
        'link_verify':   "gtatools.link_verify",
        'sec_import':    "gtatools.import_ipl_sections",
        'sec_export':    "gtatools.export_ipl_sections",
        'replace_empty': "gtatools.replace_ipl_placeholders",
        'img_import':    "gtatools.import_from_img",
        'img_export':    "gtatools.export_to_img",
        'img_remove':    "gtatools.remove_from_img",
    }

    _TOGGLE_PROPS = {
        'skip_lod': 'gtatools_img_skip_lod',
        'txd':      'gtatools_img_load_txd',
        'col':      'gtatools_map_load_col',
    }

    def handle_body_press(self, context, L, mx, my):
        # Toggle props first — they share the rect-name pattern with
        # operator buttons but need a different action.
        for key, prop_name in self._TOGGLE_PROPS.items():
            r = L.get(f'{key}_rect')
            if r and B._hit(mx, my, *r):
                try:
                    settings = context.scene.inu_settings
                    cur = bool(getattr(settings, prop_name, False))
                    setattr(settings, prop_name, not cur)
                    B._push_undo(f"INU: {prop_name} → {not cur}")
                except Exception as e:
                    print(f"[INU Floater] toggle {prop_name} failed: {e}")
                return True

        # Operator buttons.
        for key, op_id in self._BUTTON_OPS.items():
            r = L.get(f'{key}_rect')
            if r and B._hit(mx, my, *r):
                if key.startswith('link_'):
                    # Force-route through the N-panel's UI region —
                    # operators invoked there get their self.report()
                    # surfaced to Blender's visible status feedback the
                    # same way a real N-panel button click does.  The
                    # default ``_invoke_operator`` timer path lands in
                    # the modal's own region context where reports go
                    # only to the Info log, never the popup.
                    _invoke_op_from_npanel(context, op_id)
                else:
                    B._invoke_operator(op_id, {})
                return True

        return False
