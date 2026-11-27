# -*- coding: utf-8 -*-
"""
Định nghĩa bảng màu Catppuccin Mocha (Dark) / Catppuccin Latte (Light) và bộ sinh QSS tập trung.
"""

DARK_PALETTE = {
    "bg_base": "#1e1e2e",
    "bg_mantle": "#181825",
    "bg_crust": "#11111b",
    "bg_table": "#181825",
    "bg_table_alt": "#1e1e2e",
    "bg_header": "#24273a",
    "bg_card": "#24273a",
    "bg_metric_card": "#181825",
    "bg_surface": "#313244",
    "bg_surface_hover": "#45475a",
    "bg_surface_active": "#585b70",
    "bg_nav_hover": "#24273a",
    "bg_nav_active_hover": "#363a4f",
    "bg_input": "#181825",
    "border": "#313244",
    "border_card": "#363a4f",
    "border_strong": "#45475a",
    "gridline": "#24273a",
    "text": "#cdd6f4",
    "text_sub": "#a6adc8",
    "text_secondary": "#bac2de",
    "text_muted": "#6c7086",
    "accent": "#89b4fa",
    "accent_hover": "#b4befe",
    "accent_text": "#11111b",
    "accent_ide": "#cba6f7",
    "accent_turn": "#b4befe",
    "green": "#a6e3a1",
    "red": "#f38ba8",
    "red_hover": "#eba0ac",
    "yellow": "#f9e2af",
    "peach": "#fab387",
    "danger_bg": "rgba(243, 139, 168, 0.15)",
    "danger_hover": "rgba(243, 139, 168, 0.25)",
    "toggle_on_track": "#a6e3a1",
    "toggle_off_track": "#45475a",
    "toggle_on_thumb": "#1e1e2e",
    "toggle_off_thumb": "#cdd6f4",
    "quota_track": (49, 50, 68, 180),
    "quota_text": "#ffffff",
    "tok_in": "#f97316",
    "tok_out": "#22c55e",
    "tok_cached": "#f59e0b",
    "tok_slash": "#6c7086",
    "tok_muted": "#585b70",
    "badge_alpha": "0.18",
}

LIGHT_PALETTE = {
    "bg_base": "#eff1f5",
    "bg_mantle": "#e6e9ef",
    "bg_crust": "#f8f9fc",
    "bg_table": "#ffffff",
    "bg_table_alt": "#f5f7fa",
    "bg_header": "#e6e9ef",
    "bg_card": "#ffffff",
    "bg_metric_card": "#ffffff",
    "bg_surface": "#dce0e8",
    "bg_surface_hover": "#ccd0da",
    "bg_surface_active": "#bcc0cc",
    "bg_nav_hover": "#dce0e8",
    "bg_nav_active_hover": "#ccd0da",
    "bg_input": "#ffffff",
    "border": "#ccd0da",
    "border_card": "#ccd0da",
    "border_strong": "#bcc0cc",
    "gridline": "#e6e9ef",
    "text": "#4c4f69",
    "text_sub": "#6c6f85",
    "text_secondary": "#5c5f77",
    "text_muted": "#8c8fa1",
    "accent": "#1e66f5",
    "accent_hover": "#3b7cf7",
    "accent_text": "#ffffff",
    "accent_ide": "#8839ef",
    "accent_turn": "#7287fd",
    "green": "#40a02b",
    "red": "#d20f39",
    "red_hover": "#e64553",
    "yellow": "#df8e1d",
    "peach": "#fe640b",
    "danger_bg": "rgba(210, 15, 57, 0.10)",
    "danger_hover": "rgba(210, 15, 57, 0.18)",
    "toggle_on_track": "#40a02b",
    "toggle_off_track": "#bcc0cc",
    "toggle_on_thumb": "#ffffff",
    "toggle_off_thumb": "#ffffff",
    "quota_track": (204, 208, 218, 220),
    "quota_text": "#4c4f69",
    "tok_in": "#ea580c",
    "tok_out": "#16a34a",
    "tok_cached": "#b45309",
    "tok_slash": "#8c8fa1",
    "tok_muted": "#9ca0b0",
    "badge_alpha": "0.14",
}


def build_qss(p: dict) -> str:
    """Sinh chuỗi QSS hoàn chỉnh từ bảng màu semantic p."""
    return f"""
QMainWindow, QDialog, QMessageBox, QStackedWidget {{
    background-color: {p['bg_base']};
    color: {p['text']};
}}
QWidget {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
    color: {p['text']};
}}
QWidget#dashboard_view, QWidget#accounts_view, QWidget#model_rules_view,
QWidget#logs_view, QWidget#settings_view {{
    background-color: {p['bg_base']};
    color: {p['text']};
}}
QWidget#sidebar_nav {{
    background-color: {p['bg_mantle']};
    border-right: 1px solid {p['border']};
}}
QLabel#sidebar_logo_lockup {{
    background: transparent;
    border: none;
    padding: 2px 4px;
    color: {p['text']};
    font-size: 13px;
    font-weight: bold;
}}
QFrame#sidebar_sep {{
    color: {p['border']};
    border: none;
    border-top: 1px solid {p['border']};
    max-height: 1px;
}}
QLabel#sidebar_caption, QLabel#sidebar_footer {{
    color: {p['text_muted']};
    font-size: 10px;
}}
QLabel#sidebar_footer {{
    font-weight: 500;
}}
QPushButton[nav_btn="true"] {{
    background-color: transparent;
    color: {p['text_sub']};
    font-weight: 500;
    border: none;
    border-radius: 6px;
    text-align: left;
    padding-left: 15px;
    font-size: 13px;
}}
QPushButton[nav_btn="true"]:hover {{
    background-color: {p['bg_nav_hover']};
    color: {p['text']};
}}
QPushButton[nav_btn="true"][active="true"] {{
    background-color: {p['bg_surface']};
    color: {p['accent']};
    font-weight: bold;
    border: none;
    border-left: 3px solid {p['accent']};
    border-radius: 6px;
    text-align: left;
    padding-left: 12px;
    font-size: 13px;
}}
QPushButton[nav_btn="true"][active="true"]:hover {{
    background-color: {p['bg_nav_active_hover']};
}}
QFrame#compact_status_bar {{
    background-color: {p['bg_card']};
    border: 1px solid {p['border_card']};
    border-radius: 8px;
}}
QFrame#status_divider {{
    color: {p['border']};
    border: none;
    border-left: 1px solid {p['border']};
}}
QLabel#status_title, QLabel#metric_title {{
    color: {p['text_sub']};
    font-size: 11px;
    font-weight: 500;
}}
QLabel#status_sub, QLabel#metric_sub {{
    color: {p['text_muted']};
    font-size: 10px;
}}
QLabel#section_title {{
    color: {p['text']};
    font-size: 12px;
    font-weight: bold;
}}
QLabel#lbl_muted {{
    color: {p['text_sub']};
    font-size: 12px;
}}
QLabel#setting_title {{
    color: {p['text']};
    font-size: 12px;
    font-weight: 500;
}}
QLabel#setting_desc {{
    color: {p['text_muted']};
    font-size: 11px;
}}
QFrame#metric_card {{
    background-color: {p['bg_card']};
    border: 1px solid {p['border_card']};
    border-radius: 8px;
    padding: 4px;
}}
QFrame#token_metric_card {{
    background-color: {p['bg_metric_card']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 4px 10px;
}}
QPushButton {{
    background-color: {p['bg_surface']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {p['bg_surface_hover']};
    border-color: {p['bg_surface_active']};
}}
QPushButton:disabled {{
    background-color: {p['bg_mantle']};
    color: {p['text_muted']};
    border-color: {p['border']};
}}
QPushButton#btn_primary {{
    background-color: {p['accent']};
    color: {p['accent_text']};
    border: 1px solid {p['accent']};
    font-weight: bold;
}}
QPushButton#btn_primary:hover {{
    background-color: {p['accent_hover']};
}}
QPushButton#btn_danger {{
    background-color: {p['red']};
    color: {p['accent_text']};
    border: 1px solid {p['red']};
    font-weight: bold;
}}
QPushButton#btn_danger:hover {{
    background-color: {p['red_hover']};
    border-color: {p['red_hover']};
}}
QPushButton#btn_auto[auto_state="on"] {{
    background-color: {p['green']};
    color: {p['accent_text']};
    border: 1px solid {p['green']};
    font-weight: bold;
}}
QPushButton#btn_auto[auto_state="on"]:hover {{
    background-color: {p['accent']};
    border-color: {p['accent']};
}}
QPushButton#btn_auto[auto_state="off"] {{
    background-color: {p['red']};
    color: {p['accent_text']};
    border: 1px solid {p['red']};
    font-weight: bold;
}}
QPushButton#btn_auto[auto_state="off"]:hover {{
    background-color: {p['red_hover']};
    border-color: {p['red_hover']};
}}
QPushButton#btn_danger_outline {{
    background-color: {p['danger_bg']};
    color: {p['red']};
    border: 1px solid {p['red']};
    border-radius: 6px;
    padding: 6px 12px;
}}
QPushButton#btn_danger_outline:hover {{
    background-color: {p['danger_hover']};
}}
QPushButton#btn_detail {{
    text-align: left;
    padding: 3px 10px;
    background-color: {p['bg_card']};
    border: 1px solid {p['border_card']};
    border-radius: 5px;
    color: {p['text']};
}}
QPushButton#btn_detail:hover {{
    background-color: {p['bg_surface']};
    border-color: {p['accent']};
}}
QPushButton#btn_launch_app, QPushButton#btn_launch_ide {{
    background-color: {p['bg_card']};
    color: {p['text']};
    border: 1px solid {p['border_card']};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btn_launch_app:hover {{
    background-color: {p['bg_surface']};
    border-color: {p['accent']};
}}
QPushButton#btn_launch_ide:hover {{
    background-color: {p['bg_surface']};
    border-color: {p['accent_ide']};
}}
QPushButton#btn_launch_app:disabled, QPushButton#btn_launch_ide:disabled {{
    background-color: {p['bg_mantle']};
    border-color: {p['border']};
    color: {p['text_muted']};
}}
QPushButton#btn_proxy_next, QPushButton#btn_proxy_toggle {{
    background-color: {p['bg_surface']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    padding: 4px 12px;
    font-weight: 500;
}}
QPushButton#btn_proxy_next:hover, QPushButton#btn_proxy_toggle:hover {{
    background-color: {p['bg_surface_hover']};
    border-color: {p['bg_surface_active']};
}}
QPushButton#btn_proxy_next:disabled, QPushButton#btn_proxy_toggle:disabled {{
    background-color: {p['bg_mantle']};
    color: {p['text_muted']};
    border-color: {p['border']};
}}
QPushButton#btn_settings {{
    background-color: {p['bg_surface']};
    color: {p['text']};
    font-size: 14px;
    border: 1px solid {p['border_strong']};
    border-radius: 4px;
    padding: 2px 6px;
}}
QPushButton#btn_settings:hover {{
    background-color: {p['bg_surface_hover']};
}}
QPushButton[tf_btn="true"] {{
    background-color: {p['bg_surface']};
    color: {p['text']};
    border: none;
    border-radius: 4px;
    padding: 2px 10px;
    font-size: 11px;
}}
QPushButton[tf_btn="true"]:hover {{
    background-color: {p['bg_surface_hover']};
}}
QPushButton[tf_btn="true"][active="true"] {{
    background-color: {p['accent']};
    color: {p['accent_text']};
    font-weight: bold;
}}
QLineEdit#order_edit_num {{
    background-color: transparent;
    color: {p['text']};
    border: 1px solid transparent;
    border-radius: 3px;
    font-weight: bold;
    font-size: 12px;
    padding: 0px 2px;
    min-height: 18px;
}}
QLineEdit#order_edit_num:hover, QLineEdit#order_edit_num:focus {{
    background-color: {p['bg_surface']};
    border: 1px solid {p['accent']};
}}
QPushButton#order_step_btn {{
    background-color: {p['bg_surface']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    border-radius: 2px;
    font-size: 7px;
    font-weight: bold;
    padding: 0px;
    margin: 0px;
}}
QPushButton#order_step_btn:hover {{
    background-color: {p['bg_surface_hover']};
    color: {p['accent']};
}}
QPushButton#order_step_btn:disabled {{
    background-color: {p['bg_mantle']};
    color: {p['text_muted']};
    border-color: {p['border']};
}}
QComboBox#combo_dashboard_account {{
    background-color: {p['bg_card']};
    color: {p['text']};
    border: 1px solid {p['border_card']};
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 500;
}}
QComboBox#combo_dashboard_account:hover {{
    border-color: {p['accent']};
}}
QTabWidget::pane {{
    border: 1px solid {p['border']};
    background-color: {p['bg_mantle']};
    border-radius: 6px;
}}
QTabBar::tab {{
    background-color: {p['bg_mantle']};
    color: {p['text_sub']};
    padding: 6px 14px;
    margin-right: 4px;
    border: 1px solid {p['border']};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background-color: {p['bg_base']};
    color: {p['accent']};
    font-weight: bold;
    border-color: {p['border_strong']};
    border-bottom: 2px solid {p['accent']};
}}
QTabBar::tab:hover:!selected {{
    background-color: {p['bg_card']};
    color: {p['text']};
}}
QTableWidget, QListWidget {{
    background-color: {p['bg_table']};
    alternate-background-color: {p['bg_table_alt']};
    color: {p['text']};
    gridline-color: {p['gridline']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    selection-background-color: {p['bg_surface']};
    selection-color: {p['accent']};
}}
QTableWidget::item, QListWidget::item {{
    padding: 4px 8px;
    border-bottom: 1px solid {p['gridline']};
}}
QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {p['bg_surface']};
    color: {p['accent']};
}}
QHeaderView {{
    background-color: {p['bg_header']};
    border: none;
}}
QHeaderView::section {{
    background-color: {p['bg_header']};
    color: {p['text_sub']};
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid {p['border']};
    font-size: 11px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background-color: {p['bg_header']};
    border: none;
}}
QPlainTextEdit {{
    background-color: {p['bg_crust']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 8px;
    color: {p['text']};
}}
QMenu {{
    background-color: {p['bg_card']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {p['bg_surface']};
    color: {p['accent']};
}}
QMenu::separator {{
    height: 1px;
    background-color: {p['border']};
    margin: 4px 8px;
}}
QFrame[frameShape="4"] {{
    color: {p['border']};
    border: none;
    border-top: 1px solid {p['border']};
    max-height: 1px;
}}
QMessageBox QPushButton {{
    min-width: 72px;
}}
QToolTip {{
    background-color: {p['bg_card']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    padding: 4px 8px;
}}
QCheckBox {{
    color: {p['text']};
    spacing: 6px;
}}
QScrollBar:vertical {{
    background-color: {p['bg_mantle']};
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {p['border_strong']};
    min-height: 20px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {p['bg_surface_active']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background-color: {p['bg_mantle']};
    height: 8px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background-color: {p['border_strong']};
    min-width: 20px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {p['bg_surface_active']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QComboBox, QSpinBox {{
    background-color: {p['bg_surface']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    border-radius: 4px;
    padding: 4px 8px;
}}
QComboBox:hover, QSpinBox:hover {{
    border-color: {p['accent']};
}}
QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled {{
    background-color: {p['bg_mantle']};
    color: {p['text_muted']};
    border-color: {p['border']};
}}
QLineEdit {{
    background-color: {p['bg_input']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 20px;
}}
QLineEdit:focus {{
    border-color: {p['accent']};
}}
QScrollArea, QWidget#settings_scroll_content {{
    background-color: {p['bg_base']};
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {p['bg_mantle']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    selection-background-color: {p['bg_surface']};
    selection-color: {p['accent']};
    padding: 4px;
}}
QGroupBox {{
    border: 1px solid {p['border_strong']};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {p['text']};
}}
"""
