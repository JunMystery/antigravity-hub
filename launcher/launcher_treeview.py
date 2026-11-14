# -*- coding: utf-8 -*-
"""
Helper module cho bảng điều khiển TreeView của Antigravity Launcher.
Cung cấp các hàm định dạng Toggle Switch đồ họa, Quota indicator, thiết lập TreeView và thao tác dữ liệu hàng.
"""

import math
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf

from launcher_quota import get_quota_pill_pixbuf
from launcher_i18n import tr

_SWITCH_CACHE = {}

def get_toggle_switch_pixbuf(is_enabled: bool) -> GdkPixbuf.Pixbuf:
    """Tạo hoặc lấy từ cache Pixbuf Toggle Switch tròn (ON xanh lá, OFF xám)."""
    key = bool(is_enabled)
    if key in _SWITCH_CACHE:
        return _SWITCH_CACHE[key]

    w, h = 44, 22
    r = h / 2.0
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)

    # 1. Rãnh nền bo tròn
    cr.arc(r, r, r - 1, math.pi / 2, 3 * math.pi / 2)
    cr.arc(w - r, r, r - 1, -math.pi / 2, math.pi / 2)
    cr.close_path()

    if is_enabled:
        cr.set_source_rgb(0.18, 0.80, 0.44)  # Xanh #2ecc71
    else:
        cr.set_source_rgb(0.45, 0.48, 0.52)  # Xám trung tính
    cr.fill()

    # 2. Nút gạt tròn trắng
    thumb_r = r - 2.5
    cx = (w - r) if is_enabled else r
    cr.arc(cx, r, thumb_r, 0, 2 * math.pi)
    cr.set_source_rgb(1.0, 1.0, 1.0)
    cr.fill()

    raw = bytearray(surface.get_data())
    raw[0::4], raw[2::4] = raw[2::4], raw[0::4]
    pb = GdkPixbuf.Pixbuf.new_from_data(
        bytes(raw), GdkPixbuf.Colorspace.RGB, True, 8, w, h, surface.get_stride()
    )
    _SWITCH_CACHE[key] = pb
    return pb

def get_quota_btn_label(loading: bool = False) -> str:
    """Trả về nhãn indicator cho nút refresh Quota inline."""
    if loading:
        return "[...]"
    return "[⟳]"

def setup_treeview(win):
    """Khởi tạo ListStore 17 cột, cấu hình TreeView và các cột hiển thị."""
    win.liststore = Gtk.ListStore(
        str, str, bool, str, str, str,
        GdkPixbuf.Pixbuf, GdkPixbuf.Pixbuf,
        int, str, int, str, bool, bool, str,
        str, GdkPixbuf.Pixbuf
    )
    treeview = Gtk.TreeView(model=win.liststore)
    treeview.set_headers_visible(True)
    treeview.set_enable_search(False)
    treeview.connect("row-activated", win.on_row_activated)

    # Column 0: Nút kéo hàng riêng biệt (Drag Handle ⠿)
    renderer_drag = Gtk.CellRendererText()
    renderer_drag.set_property("xalign", 0.5)
    win.col_drag = Gtk.TreeViewColumn("⠿", renderer_drag, text=0)
    win.col_drag.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
    win.col_drag.set_fixed_width(36)
    win.col_drag.set_resizable(False)
    win.col_drag.set_alignment(0.5)
    treeview.append_column(win.col_drag)

    # Column 1: Thứ tự ưu tiên Round Robin (TT)
    renderer_order = Gtk.CellRendererText()
    renderer_order.set_property("editable", True)
    renderer_order.set_property("xalign", 0.5)
    renderer_order.connect("editing-started", win.on_order_editing_started)
    renderer_order.connect("editing-canceled", win.on_order_editing_canceled)
    renderer_order.connect("edited", win.on_order_edited)
    win.col_order = Gtk.TreeViewColumn(tr("col.order"), renderer_order, text=1)
    win.col_order.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
    win.col_order.set_fixed_width(45)
    win.col_order.set_resizable(False)
    win.col_order.set_alignment(0.5)
    treeview.append_column(win.col_order)

    # Column 2: Toggle Switch Active (Pixbuf 1 chạm)
    renderer_active = Gtk.CellRendererPixbuf()
    renderer_active.set_property("xalign", 0.5)
    renderer_active.set_property("yalign", 0.5)
    win.col_active = Gtk.TreeViewColumn(tr("col.active"), renderer_active, pixbuf=16)
    win.col_active.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
    win.col_active.set_fixed_width(65)
    win.col_active.set_resizable(False)
    win.col_active.set_alignment(0.5)
    treeview.append_column(win.col_active)

    # Column 3: Tài khoản Email
    win.col_email = Gtk.TreeViewColumn(tr("col.email"), Gtk.CellRendererText(), text=3)
    win.col_email.set_min_width(200)
    win.col_email.set_resizable(True)
    treeview.append_column(win.col_email)

    # Column 4: Quota 5 Hrs
    renderer_q5 = Gtk.CellRendererPixbuf()
    renderer_q5.set_property("xalign", 0.5)
    renderer_q5.set_property("yalign", 0.5)
    win.col_q5 = Gtk.TreeViewColumn(tr("col.5h"), renderer_q5, pixbuf=6)
    win.col_q5.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
    win.col_q5.set_fixed_width(120)
    win.col_q5.set_resizable(False)
    win.col_q5.set_alignment(0.5)
    treeview.append_column(win.col_q5)

    # Column 5: Quota Weekly
    renderer_qw = Gtk.CellRendererPixbuf()
    renderer_qw.set_property("xalign", 0.5)
    renderer_qw.set_property("yalign", 0.5)
    win.col_qw = Gtk.TreeViewColumn(tr("col.weekly"), renderer_qw, pixbuf=7)
    win.col_qw.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
    win.col_qw.set_fixed_width(120)
    win.col_qw.set_resizable(False)
    win.col_qw.set_alignment(0.5)
    treeview.append_column(win.col_qw)

    # Column 6: Custom Header Widget (Quota Toggle Auto + ⟳ Làm mới toàn bộ)
    renderer_quota_btn = Gtk.CellRendererText()
    renderer_quota_btn.set_property("xalign", 0.5)
    win.col_quota_refresh = Gtk.TreeViewColumn("", renderer_quota_btn, text=15)
    win.col_quota_refresh.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
    win.col_quota_refresh.set_fixed_width(90)
    win.col_quota_refresh.set_resizable(False)
    win.col_quota_refresh.set_alignment(0.5)

    header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
    header_box.set_halign(Gtk.Align.CENTER)

    win.btn_title_quota = Gtk.Button()
    win.btn_title_quota.get_style_context().add_class("btn-header-flat")
    win.lbl_title_quota = Gtk.Label()
    win.lbl_title_quota.set_markup(f"<span color='#e74c3c'><b>{tr('col.quota')}</b></span>")
    win.btn_title_quota.add(win.lbl_title_quota)
    win.btn_title_quota.set_tooltip_text(tr("tooltip.auto_off"))
    win.btn_title_quota.connect("clicked", win.on_toggle_auto_quota)
    header_box.pack_start(win.btn_title_quota, False, False, 0)

    win.btn_refresh_all = Gtk.Button.new_with_label("⟳")
    win.btn_refresh_all.get_style_context().add_class("btn-header-flat")
    win.btn_refresh_all.set_tooltip_text(tr("tooltip.refresh_all"))
    win.btn_refresh_all.connect("clicked", win.on_refresh_all_quota)
    header_box.pack_start(win.btn_refresh_all, False, False, 0)

    header_box.show_all()
    win.col_quota_refresh.set_widget(header_box)
    treeview.append_column(win.col_quota_refresh)

    # Setup Drag and Drop
    dnd_targets = [Gtk.TargetEntry.new("text/plain", Gtk.TargetFlags.SAME_WIDGET, 0)]
    treeview.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK, dnd_targets, Gdk.DragAction.MOVE)
    treeview.enable_model_drag_dest(dnd_targets, Gdk.DragAction.MOVE)
    treeview.connect("button-press-event", win.on_treeview_button_press)
    treeview.connect("key-press-event", win.on_treeview_key_press)
    treeview.connect("drag-data-get", win.on_drag_data_get)
    treeview.connect("drag-data-received", win.on_drag_data_received)

    return treeview

def update_treeview_headers(win):
    """Cập nhật lại tiêu đề các cột và tooltip khi đổi ngôn ngữ."""
    win.col_order.set_title(tr("col.order"))
    win.col_active.set_title(tr("col.active"))
    win.col_email.set_title(tr("col.email"))
    win.col_q5.set_title(tr("col.5h"))
    win.col_qw.set_title(tr("col.weekly"))

    is_on = getattr(win, "is_auto_quota_on", False)
    color = "#2ecc71" if is_on else "#e74c3c"
    win.lbl_title_quota.set_markup(f"<span color='{color}'><b>{tr('col.quota')}</b></span>")
    win.btn_title_quota.set_tooltip_text(tr("tooltip.auto_on" if is_on else "tooltip.auto_off"))
    win.btn_refresh_all.set_tooltip_text(tr("tooltip.refresh_all"))

def populate_treeview(win, select_id=None):
    """Nạp lại danh sách profiles vào ListStore và chọn dòng chỉ định."""
    win.liststore.clear()
    profiles = win.data.get("profiles", [])
    selected_iter = None
    enabled_count = 0

    for idx, p in enumerate(profiles):
        is_enabled = p.get("enabled", True)
        if is_enabled:
            enabled_count += 1
        order_num = p.get("order", idx + 1)
        email = p.get("email") or p.get("name") or ""
        q5_val = p.get("quota_5h_val", 0)
        q5_text = p.get("quota_5h", "--")
        q5_valid = p.get("quota_5h_valid", False) if q5_text not in ("--", "Lỗi", "N/A") else False
        qw_val = p.get("quota_weekly_val", 0)
        qw_text = p.get("quota_weekly", "--")
        qw_valid = p.get("quota_weekly_valid", False) if qw_text not in ("--", "Lỗi", "N/A") else False

        tree_iter = win.liststore.append([
            "⠿", str(order_num), is_enabled, email, p.get("data_dir", ""), p.get("created_at", ""),
            get_quota_pill_pixbuf(q5_val, q5_valid) if q5_valid else None,
            get_quota_pill_pixbuf(qw_val, qw_valid) if qw_valid else None,
            q5_val, q5_text, qw_val, qw_text, q5_valid, qw_valid,
            p.get("id", ""), get_quota_btn_label(loading=False), get_toggle_switch_pixbuf(is_enabled)
        ])
        if select_id and (p.get("id") == select_id or p.get("email") == select_id):
            selected_iter = tree_iter

    total = len(profiles)
    reqs = win.data.get("settings", {}).get("requests_per_account", 1)
    if total == 0:
        win.lbl_info.set_markup(tr("info.empty"))
        win.btn_launch.set_sensitive(False)
        win.btn_del.set_sensitive(False)
    else:
        win.lbl_info.set_markup(tr("info.summary", enabled=enabled_count, total=total, reqs=reqs))
        win.btn_launch.set_sensitive(True)
        win.btn_del.set_sensitive(True)
        selection = win.treeview.get_selection()
        if selected_iter:
            selection.select_iter(selected_iter)
        elif len(win.liststore) > 0:
            selection.select_path(Gtk.TreePath.new_first())

def get_selected_profile(win):
    """Lấy dữ liệu profile của dòng đang được chọn trong TreeView."""
    model, tree_iter = win.treeview.get_selection().get_selected()
    if tree_iter:
        return {
            "order": model.get_value(tree_iter, 1),
            "enabled": model.get_value(tree_iter, 2),
            "email": model.get_value(tree_iter, 3),
            "name": model.get_value(tree_iter, 3),
            "data_dir": model.get_value(tree_iter, 4),
            "created_at": model.get_value(tree_iter, 5),
            "quota_5h_val": model.get_value(tree_iter, 8),
            "quota_5h": model.get_value(tree_iter, 9),
            "quota_weekly_val": model.get_value(tree_iter, 10),
            "quota_weekly": model.get_value(tree_iter, 11),
            "id": model.get_value(tree_iter, 14)
        }
    return None

def update_row_quota_display(win, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid):
    """Cập nhật các giá trị Quota trên giao diện hàng của TreeView."""
    q5_pb = get_quota_pill_pixbuf(q5_val, q5_valid) if q5_valid else None
    qw_pb = get_quota_pill_pixbuf(qw_val, qw_valid) if qw_valid else None
    for row in win.liststore:
        if row[14] == profile_id or row[3] == profile_id:
            row[6], row[7], row[8], row[9], row[10], row[11], row[12], row[13] = (
                q5_pb, qw_pb, q5_val, q5_text, qw_val, qw_text, q5_valid, qw_valid
            )
            break
