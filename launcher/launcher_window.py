# -*- coding: utf-8 -*-
"""
Module cửa sổ chính giao diện GTK3 (LauncherWindow) cho Antigravity Launcher.
"""

import os
import sys
import signal
import atexit
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GLib

from launcher_storage import (
    APP_ICON, MANUAL_COOLDOWN, load_data, save_data, delete_account_completely
)
from launcher_proxy import (
    ensure_proxy_running, stop_proxy, stop_all_launched_apps,
    launch_profile, is_proxy_running
)
from launcher_treeview import (
    get_toggle_switch_pixbuf, populate_treeview,
    get_selected_profile, update_row_quota_display, update_treeview_headers
)
from launcher_monitor import update_monitor_view, send_proxy_cmd
from launcher_oauth import start_google_oauth_flow
from launcher_layout import (
    apply_launcher_css, build_launcher_layout, retranslate_layout
)
from launcher_i18n import tr, set_language, get_current_language
import launcher_quota_runner as quota_runner

class LauncherWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title=tr("app.title"))
        self.set_default_size(840, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        if os.path.exists(APP_ICON):
            self.set_icon_from_file(APP_ICON)

        self.data = load_data()
        lang = self.data.get("settings", {}).get("language", "vi")
        set_language(lang)

        self.cooldown_remaining = 0
        self.can_drag = False
        self.is_editing_order = False
        self.is_auto_quota_on = False
        self.auto_quota_timer_id = None

        apply_launcher_css()
        build_launcher_layout(self)
        self._refresh_list()

        GLib.timeout_add(300, self.update_live_monitor)
        ensure_proxy_running()

    def on_language_changed(self, combo):
        lang_code = combo.get_active_id()
        if lang_code and lang_code != get_current_language():
            set_language(lang_code)
            self.data.setdefault("settings", {})
            self.data["settings"]["language"] = lang_code
            save_data(self.data)
            self.retranslate_ui()

    def retranslate_ui(self):
        retranslate_layout(self)
        update_treeview_headers(self)
        self._refresh_list()
        self.update_live_monitor()

    def reorder_profile(self, from_idx: int, to_idx: int):
        profiles = self.data.get("profiles", [])
        if not profiles or from_idx == to_idx or from_idx < 0 or from_idx >= len(profiles):
            return
        to_idx = max(0, min(to_idx, len(profiles) - 1))
        moved = profiles.pop(from_idx)
        profiles.insert(to_idx, moved)
        for i, p in enumerate(profiles):
            p["order"] = i + 1
        self.data["profiles"] = profiles
        save_data(self.data)
        self._refresh_list(select_id=moved.get("id"))

    def on_order_editing_started(self, cell, editable, path):
        self.is_editing_order = True

    def on_order_editing_canceled(self, cell):
        self.is_editing_order = False

    def on_order_edited(self, widget, path, new_text):
        self.is_editing_order = False
        try:
            new_order = int(new_text.strip())
        except ValueError:
            return
        profiles = self.data.get("profiles", [])
        if not profiles:
            return
        from_idx = int(path)
        to_idx = max(0, min(new_order - 1, len(profiles) - 1))
        if from_idx != to_idx:
            self.reorder_profile(from_idx, to_idx)

    def on_treeview_button_press(self, widget, event):
        if event.button == 1:
            pos = widget.get_path_at_pos(int(event.x), int(event.y))
            if pos:
                path, col, _, _ = pos
                if col == self.col_drag:
                    self.can_drag = True
                    return False
                if col == self.col_active:
                    self.on_account_toggled(None, path.to_string())
                    return True
                if col == self.col_quota_refresh:
                    self.on_refresh_single_row_quota(path.to_string())
                    return True
        self.can_drag = False
        return False

    def on_treeview_key_press(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname in ("Delete", "KP_Delete"):
            self.on_delete_account(None)
            return True
        return False

    def on_drag_data_get(self, widget, context, selection_data, info, timestamp):
        if not self.can_drag:
            return
        model, tree_iter = widget.get_selection().get_selected()
        if tree_iter:
            selection_data.set_text(str(model.get_path(tree_iter).get_indices()[0]), -1)

    def on_drag_data_received(self, widget, context, x, y, selection_data, info, timestamp):
        if not self.can_drag:
            context.finish(False, False, timestamp)
            return
        self.can_drag = False
        drop_info = widget.get_dest_row_at_pos(x, y)
        src_text = selection_data.get_text()
        if src_text is not None and drop_info is not None:
            try:
                src_idx = int(src_text)
                dest_path, pos = drop_info
                dest_idx = dest_path.get_indices()[0]
                if pos in (Gtk.TreeViewDropPosition.AFTER, Gtk.TreeViewDropPosition.INTO_OR_AFTER):
                    dest_idx = min(len(self.data.get("profiles", [])) - 1, dest_idx)
                self.reorder_profile(src_idx, dest_idx)
                context.finish(True, False, timestamp)
                return
            except Exception:
                pass
        context.finish(False, False, timestamp)

    def _refresh_list(self, select_id=None):
        populate_treeview(self, select_id)

    def _get_selected(self):
        return get_selected_profile(self)

    def _update_row_quota(self, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid):
        update_row_quota_display(self, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid)

    def start_refresh_cooldown(self, seconds=MANUAL_COOLDOWN):
        quota_runner.start_refresh_cooldown(self, seconds)

    def on_refresh_single_row_quota(self, path_str):
        quota_runner.refresh_single_row_quota(self, path_str)

    def on_refresh_all_quota(self, widget=None):
        quota_runner.refresh_all_quota(self, widget)

    def auto_refresh_quota(self):
        return quota_runner.auto_refresh_quota(self)

    def on_toggle_auto_quota(self, widget=None):
        self.is_auto_quota_on = not self.is_auto_quota_on
        if self.is_auto_quota_on:
            self.lbl_title_quota.set_markup(f"<span color='#2ecc71'><b>{tr('col.quota')}</b></span>")
            self.btn_title_quota.set_tooltip_text(tr("tooltip.auto_on"))
            if not self.auto_quota_timer_id:
                self.auto_refresh_quota()
                self.auto_quota_timer_id = GLib.timeout_add_seconds(300, self.auto_refresh_quota)
        else:
            self.lbl_title_quota.set_markup(f"<span color='#e74c3c'><b>{tr('col.quota')}</b></span>")
            self.btn_title_quota.set_tooltip_text(tr("tooltip.auto_off"))
            if self.auto_quota_timer_id:
                GLib.source_remove(self.auto_quota_timer_id)
                self.auto_quota_timer_id = None

    def on_account_toggled(self, widget, path):
        new_val = not self.liststore[path][2]
        self.liststore[path][2] = new_val
        self.liststore[path][16] = get_toggle_switch_pixbuf(new_val)
        acc_email, acc_id = self.liststore[path][3], self.liststore[path][14]
        for p in self.data.get("profiles", []):
            if p.get("id") == acc_id or (p.get("email") and p.get("email") == acc_email):
                p["enabled"] = new_val
                break
        save_data(self.data)
        total = len(self.data.get("profiles", []))
        enabled_count = sum(1 for p in self.data.get("profiles", []) if p.get("enabled", True))
        reqs = self.data.get("settings", {}).get("requests_per_account", 1)
        self.lbl_info.set_markup(tr("info.summary", enabled=enabled_count, total=total, reqs=reqs))

    def on_spin_changed(self, widget):
        val = int(widget.get_value())
        self.data.setdefault("settings", {})
        self.data["settings"]["requests_per_account"] = val
        save_data(self.data)
        total = len(self.data.get("profiles", []))
        enabled_count = sum(1 for p in self.data.get("profiles", []) if p.get("enabled", True))
        self.lbl_info.set_markup(tr("info.summary", enabled=enabled_count, total=total, reqs=val))

    def on_manual_next_account(self, widget):
        self.btn_next_account.set_sensitive(False)
        send_proxy_cmd(self, "next")
        GLib.timeout_add(300, lambda: (self.btn_next_account.set_sensitive(True), self.update_live_monitor(), False)[-1])

    def on_toggle_proxy_btn(self, widget):
        if is_proxy_running():
            stop_proxy()
        else:
            ensure_proxy_running()
        self.update_live_monitor()

    def on_window_destroy(self, widget):
        stop_all_launched_apps()
        stop_proxy()
        Gtk.main_quit()

    def update_live_monitor(self):
        return update_monitor_view(self)

    def on_add_account(self, widget):
        start_google_oauth_flow(self)

    def on_delete_account(self, widget):
        selected = self._get_selected()
        if not selected:
            return
        acc_label = selected.get("email") or selected.get("name") or "tài khoản"
        msg_dialog = Gtk.MessageDialog(
            parent=self, flags=Gtk.DialogFlags.MODAL, type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO, message_format=tr("dialog.delete_title", label=acc_label)
        )
        msg_dialog.format_secondary_text(tr("dialog.delete_warning"))
        response = msg_dialog.run()
        msg_dialog.destroy()
        if response == Gtk.ResponseType.YES:
            self.data = delete_account_completely(selected)
            self._refresh_list()
            self.lbl_info.set_markup(tr("dialog.deleted_msg", label=acc_label))

    def on_row_activated(self, treeview, path, column):
        if column != self.col_email:
            return
        self.on_launch_clicked(None)

    def on_launch_clicked(self, widget):
        selected = self._get_selected()
        if selected:
            ensure_proxy_running()
            self.update_live_monitor()
            launch_profile(selected["data_dir"], use_proxy=True)

def run_gui():
    def handle_signal(sig, frame):
        stop_all_launched_apps()
        stop_proxy()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    except Exception:
        pass

    atexit.register(stop_all_launched_apps)
    atexit.register(stop_proxy)

    win = LauncherWindow()
    win.show_all()
    Gtk.main()
