# -*- coding: utf-8 -*-
"""
Quản lý chủ đề giao diện System / Dark (Catppuccin Mocha) / Light (Catppuccin Latte)
và đồng bộ thanh tiêu đề Windows Dark/Light cho Antigravity Launcher.
"""

import sys
import ctypes
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QObject, QEvent
from PyQt6.QtGui import QPalette, QColor

from launcher_theme_qss import DARK_PALETTE, LIGHT_PALETTE, build_qss

THEME_MODES = ("system", "dark", "light")
LAUNCHER_QSS = build_qss(DARK_PALETTE)
_LIGHT_QSS = build_qss(LIGHT_PALETTE)

_current_mode = "dark"
_active_theme = "dark"


def detect_system_theme() -> str:
    """Xác định giao diện sáng/tối hiện tại của hệ điều hành."""
    app = QApplication.instance()
    if app is not None and hasattr(app, "styleHints"):
        hints = app.styleHints()
        if hasattr(hints, "colorScheme"):
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Light:
                return "light"
            if scheme == Qt.ColorScheme.Dark:
                return "dark"

    if sys.platform == "win32":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if int(val) == 1 else "dark"
        except Exception:
            pass
    return "dark"


def resolve_theme(mode: str = None) -> str:
    """Quy đổi mode cấu hình ('system'|'dark'|'light') thành 'dark' hoặc 'light'."""
    norm = str(mode or "dark").strip().lower()
    if norm == "light":
        return "light"
    if norm == "system":
        return detect_system_theme()
    return "dark"


def get_theme_mode() -> str:
    """Trả về chế độ người dùng đang chọn ('system', 'dark' hoặc 'light')."""
    return _current_mode


def get_active_theme() -> str:
    """Trả về giao diện thực tế đang hiển thị ('dark' hoặc 'light')."""
    return _active_theme


def get_palette(theme: str = None) -> dict:
    """Trả về từ điển màu theo giao diện ('dark' hoặc 'light')."""
    target = theme if theme in ("dark", "light") else _active_theme
    return LIGHT_PALETTE if target == "light" else DARK_PALETTE


def repolish_widget(widget: QWidget) -> None:
    """Cập nhật lại style của widget sau khi thay đổi dynamic property."""
    if widget is None:
        return
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


def build_qt_palette(p: dict) -> QPalette:
    """Xây dựng QPalette đồng bộ cho mọi dialog, placeholder và widget chuẩn Qt."""
    pal = QPalette()
    bg_base = QColor(p["bg_base"])
    bg_input = QColor(p["bg_input"])
    bg_alt = QColor(p["bg_table_alt"])
    bg_surface = QColor(p["bg_surface"])
    text = QColor(p["text"])
    text_muted = QColor(p["text_muted"])
    accent = QColor(p["accent"])
    accent_text = QColor(p["accent_text"])
    card = QColor(p["bg_card"])
    border = QColor(p["border"])

    for role, col in (
        (QPalette.ColorRole.Window, bg_base),
        (QPalette.ColorRole.WindowText, text),
        (QPalette.ColorRole.Base, bg_input),
        (QPalette.ColorRole.AlternateBase, bg_alt),
        (QPalette.ColorRole.Text, text),
        (QPalette.ColorRole.PlaceholderText, text_muted),
        (QPalette.ColorRole.Button, bg_surface),
        (QPalette.ColorRole.ButtonText, text),
        (QPalette.ColorRole.Highlight, accent),
        (QPalette.ColorRole.HighlightedText, accent_text),
        (QPalette.ColorRole.Mid, border),
        (QPalette.ColorRole.ToolTipBase, card),
        (QPalette.ColorRole.ToolTipText, text),
    ):
        pal.setColor(role, col)
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, text_muted)
    return pal


class _TitlebarThemeFilter(QObject):
    """Tự động đồng bộ thanh tiêu đề Dark/Light cho mọi QDialog/QMessageBox khi hiển thị."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
            apply_window_titlebar_theme(obj)
        return False


def _ensure_titlebar_filter(app) -> None:
    if app is None or getattr(app, "_titlebar_filter", None) is not None:
        return
    flt = _TitlebarThemeFilter(app)
    app._titlebar_filter = flt
    app.installEventFilter(flt)


def set_semantic_text(label, text: str, color_key: str = "accent", bold: bool = False) -> None:
    """Gán văn bản trạng thái kèm khóa màu semantic để tự đổi màu khi chuyển Theme."""
    if label is None:
        return
    label.setProperty("_semantic_text", str(text))
    label.setProperty("_semantic_color_key", str(color_key or "accent"))
    label.setProperty("_semantic_bold", bool(bold))
    label.setProperty("_semantic_rendered", None)
    refresh_semantic_label(label)


def refresh_semantic_label(label) -> None:
    """Cập nhật màu văn bản semantic của QLabel nếu nội dung chưa bị ghi đè bởi plain text."""
    if label is None:
        return
    color_key = label.property("_semantic_color_key")
    if not color_key:
        return
    rendered = label.property("_semantic_rendered")
    if rendered is not None and label.text() != rendered:
        for prop in ("_semantic_text", "_semantic_color_key", "_semantic_bold", "_semantic_rendered"):
            label.setProperty(prop, None)
        return
    color = get_palette().get(str(color_key), get_palette()["accent"])
    raw_text = str(label.property("_semantic_text") or "")
    span = f"<span style='color:{color};'>{raw_text}</span>"
    html = f"<b>{span}</b>" if label.property("_semantic_bold") else span
    label.setProperty("_semantic_rendered", html)
    label.setText(html)


def apply_launcher_style(app, mode: str = None) -> str:
    """Áp dụng QSS tương ứng lên QApplication theo mode (mặc định giữ mode hiện tại)."""
    global _current_mode, _active_theme
    norm_mode = str(mode if mode is not None else _current_mode).strip().lower()
    if norm_mode not in THEME_MODES:
        norm_mode = "dark"
    _current_mode = norm_mode
    _active_theme = resolve_theme(norm_mode)
    if app is not None:
        app.setPalette(build_qt_palette(get_palette(_active_theme)))
        _ensure_titlebar_filter(app)
        app.setStyleSheet(_LIGHT_QSS if _active_theme == "light" else LAUNCHER_QSS)
    return _active_theme


def apply_window_titlebar_theme(win, resolved_theme: str = None) -> bool:
    """Đồng bộ màu thanh tiêu đề cửa sổ Windows (Dark/Light) qua DWM."""
    if sys.platform != "win32" or win is None:
        return False
    app = QApplication.instance()
    if app is not None and app.platformName() == "offscreen":
        return False
    try:
        hwnd = int(win.winId())
        if not hwnd:
            return False
        is_dark = 1 if (resolved_theme or _active_theme) == "dark" else 0
        val = ctypes.c_int(is_dark)
        dwmapi = ctypes.windll.dwmapi
        for attr in (20, 19):
            if dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                return True
    except Exception:
        return False
    return False


def apply_theme_to_window(win, mode: str = None) -> str:
    """Áp dụng theme toàn diện cho cửa sổ chính và đồng bộ mọi view con."""
    app = QApplication.instance()
    resolved = apply_launcher_style(app, mode)
    apply_window_titlebar_theme(win, resolved)
    if app is not None:
        for top_w in app.topLevelWidgets():
            if top_w is not win and top_w.isWindow():
                apply_window_titlebar_theme(top_w, resolved)
    if win is None:
        return resolved

    if hasattr(win, "sidebar") and hasattr(win.sidebar, "update_theme"):
        win.sidebar.update_theme()
    if hasattr(win, "view_dashboard") and hasattr(win.view_dashboard, "refresh_theme"):
        win.view_dashboard.refresh_theme()
    if hasattr(win, "view_logs") and hasattr(win.view_logs, "refresh_theme"):
        win.view_logs.refresh_theme()
    if hasattr(win, "view_accounts") and hasattr(win.view_accounts, "refresh_theme"):
        win.view_accounts.refresh_theme()
    elif hasattr(win, "treeview") and win.treeview is not None:
        win.treeview.viewport().update()
    if hasattr(win, "view_model_rules") and hasattr(win.view_model_rules, "refresh_view"):
        win.view_model_rules.refresh_view()
    if hasattr(win, "view_settings") and hasattr(win.view_settings, "refresh_theme"):
        win.view_settings.refresh_theme()
    if hasattr(win, "tray") and hasattr(win.tray, "menu"):
        repolish_widget(win.tray.menu)

    if isinstance(win, QWidget):
        for child in win.findChildren(QWidget):
            if type(child).__name__ in ("ToggleSwitch", "QuotaCellWidget", "QuotaProgressBar", "MetricCard", "BadgeLabel"):
                if hasattr(child, "refresh_theme"):
                    child.refresh_theme()
                else:
                    child.update()
            elif child.property("_semantic_color_key"):
                refresh_semantic_label(child)
        win.update()
    return resolved


def bind_system_theme_listener(win) -> None:
    """Lắng nghe thay đổi giao diện hệ điều hành để cập nhật khi ở chế độ System."""
    app = QApplication.instance()
    if app is None or not hasattr(app, "styleHints"):
        return
    hints = app.styleHints()
    if not hasattr(hints, "colorSchemeChanged"):
        return
    if getattr(win, "_theme_listener_bound", False):
        return
    win._theme_listener_bound = True

    def _on_scheme_changed(_scheme=None):
        if get_theme_mode() == "system":
            apply_theme_to_window(win, "system")

    hints.colorSchemeChanged.connect(_on_scheme_changed)
