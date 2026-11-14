# -*- coding: utf-8 -*-
"""
Module xây dựng cấu trúc giao diện (Layout) và CSS cho Antigravity Launcher Window.
"""

import os
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf

from launcher_storage import APP_ICON
from launcher_treeview import setup_treeview
from launcher_monitor import build_monitor_frame
from launcher_i18n import tr, SUPPORTED_LANGUAGES, get_current_language

def apply_launcher_css():
    """Tải và áp dụng các quy tắc CSS tùy biến cho ứng dụng."""
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(b"""
        .btn-launch-big {
            background-color: #2980b9;
            color: #ffffff;
            font-weight: bold;
            font-size: 15px;
            padding: 10px 20px;
            border-radius: 6px;
        }
        .btn-launch-big:hover {
            background-color: #3498db;
        }
        .btn-header-flat {
            background: none;
            border: none;
            box-shadow: none;
            padding: 1px 4px;
            margin: 0;
            min-height: 0;
            min-width: 0;
        }
        .btn-header-flat:hover {
            background-color: rgba(255, 255, 255, 0.12);
            border-radius: 4px;
        }
    """)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

def build_launcher_layout(win):
    """Xây dựng toàn bộ các thành phần widget chính cho Launcher Window."""
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    vbox.set_margin_top(15)
    vbox.set_margin_bottom(15)
    vbox.set_margin_start(16)
    vbox.set_margin_end(16)
    win.add(vbox)

    # Header Box (Icon, Title, Subtitle, Language Dropdown)
    header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    icon_img = Gtk.Image.new_from_icon_name("system-users", Gtk.IconSize.DIALOG)
    if os.path.exists(APP_ICON):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(APP_ICON, 36, 36, True)
            icon_img = Gtk.Image.new_from_pixbuf(pixbuf)
        except Exception:
            pass
    header_box.pack_start(icon_img, False, False, 0)

    title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    win.title_lbl = Gtk.Label()
    win.title_lbl.set_markup(f"<b><span size='large'>{tr('app.title')}</span></b>")
    win.title_lbl.set_xalign(0)
    win.sub_lbl = Gtk.Label(label=tr("app.subtitle"))
    win.sub_lbl.set_xalign(0)
    title_box.pack_start(win.title_lbl, False, False, 0)
    title_box.pack_start(win.sub_lbl, False, False, 0)
    header_box.pack_start(title_box, True, True, 0)

    # Drop Down Box chọn ngôn ngữ ở góc phải trên cùng
    lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    lang_box.set_valign(Gtk.Align.CENTER)
    win.combo_lang = Gtk.ComboBoxText()
    for code, name in SUPPORTED_LANGUAGES:
        win.combo_lang.append(code, name)
    win.combo_lang.set_active_id(get_current_language())
    win.combo_lang.connect("changed", win.on_language_changed)
    lang_box.pack_end(win.combo_lang, False, False, 0)
    header_box.pack_end(lang_box, False, False, 0)

    vbox.pack_start(header_box, False, False, 0)

    # Action Bar (Thêm, Xóa - Tinh gọn tối đa)
    act_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    win.btn_add = Gtk.Button.new_with_mnemonic(tr("btn.add"))
    win.btn_add.connect("clicked", win.on_add_account)
    act_bar.pack_start(win.btn_add, False, False, 0)

    win.btn_del = Gtk.Button.new_with_mnemonic(tr("btn.delete"))
    win.btn_del.connect("clicked", win.on_delete_account)
    act_bar.pack_start(win.btn_del, False, False, 0)

    vbox.pack_start(act_bar, False, False, 0)

    # Scrolled Window & TreeView
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
    scrolled.set_vexpand(True)

    win.treeview = setup_treeview(win)
    scrolled.add(win.treeview)
    vbox.pack_start(scrolled, True, True, 0)

    win.lbl_info = Gtk.Label()
    win.lbl_info.set_xalign(0)
    vbox.pack_start(win.lbl_info, False, False, 0)

    # Monitor Frame
    vbox.pack_start(build_monitor_frame(win), False, False, 2)

    # Options Box
    sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    vbox.pack_start(sep, False, False, 2)

    opt_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    rr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
    win.rr_info = Gtk.Label()
    win.rr_info.set_markup(tr("opt.mode"))
    rr_box.pack_start(win.rr_info, False, False, 0)

    spin_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    win.spin_lbl = Gtk.Label(label=tr("opt.req_per_acc"))
    spin_box.pack_start(win.spin_lbl, False, False, 0)

    cur_reqs = win.data.get("settings", {}).get("requests_per_account", 1)
    adj = Gtk.Adjustment(value=cur_reqs, lower=1, upper=500, step_increment=1)
    win.spin_reqs = Gtk.SpinButton(adjustment=adj, numeric=True)
    win.spin_reqs.set_value(cur_reqs)
    win.spin_reqs.connect("value-changed", win.on_spin_changed)
    spin_box.pack_start(win.spin_reqs, False, False, 0)

    rr_box.pack_end(spin_box, False, False, 0)
    opt_vbox.pack_start(rr_box, False, False, 0)
    vbox.pack_start(opt_vbox, False, False, 0)

def retranslate_layout(win):
    """Làm mới toàn bộ nhãn tĩnh trên layout khi đổi ngôn ngữ."""
    win.set_title(tr("app.title"))
    win.title_lbl.set_markup(f"<b><span size='large'>{tr('app.title')}</span></b>")
    win.sub_lbl.set_text(tr("app.subtitle"))
    win.btn_add.set_label(tr("btn.add"))
    win.btn_del.set_label(tr("btn.delete"))
    win.rr_info.set_markup(tr("opt.mode"))
    win.spin_lbl.set_text(tr("opt.req_per_acc"))
