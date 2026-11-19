# -*- coding: utf-8 -*-
"""
Module định nghĩa kiểu dáng giao diện QSS (Catppuccin Mocha Dark Theme) cho Antigravity Launcher.
"""

LAUNCHER_QSS = """
QMainWindow, QStackedWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
    color: #cdd6f4;
}
QWidget#dashboard_view, QWidget#accounts_view, QWidget#settings_view {
    background-color: #1e1e2e;
}
QWidget#sidebar_nav {
    background-color: #181825;
    border-right: 1px solid #313244;
}
QFrame#compact_status_bar {
    background-color: #24273a;
    border: 1px solid #363a4f;
    border-radius: 8px;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}
QPushButton:disabled {
    background-color: #181825;
    color: #6c7086;
    border-color: #313244;
}
QPushButton#btn_launch_app {
    background-color: #89b4fa;
    color: #11111b;
    font-weight: bold;
    font-size: 13px;
    padding: 6px 14px;
    border-radius: 6px;
    border: none;
}
QPushButton#btn_launch_app:hover {
    background-color: #b4befe;
}
QPushButton#btn_launch_app:disabled {
    background-color: #313244;
    color: #6c7086;
}
QPushButton#btn_launch_ide {
    background-color: #cba6f7;
    color: #11111b;
    font-weight: bold;
    font-size: 13px;
    padding: 6px 14px;
    border-radius: 6px;
    border: none;
}
QPushButton#btn_launch_ide:hover {
    background-color: #f5c2e7;
}
QPushButton#btn_launch_ide:disabled {
    background-color: #313244;
    color: #6c7086;
}
QPushButton#btn_proxy_next, QPushButton#btn_proxy_toggle {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}
QPushButton#btn_proxy_next:hover, QPushButton#btn_proxy_toggle:hover {
    background-color: #45475a;
    border-color: #585b70;
}
QPushButton#btn_proxy_next:disabled, QPushButton#btn_proxy_toggle:disabled {
    background-color: #181825;
    color: #6c7086;
    border-color: #313244;
}
QPushButton#btn_use_account {
    background-color: #24273a;
    color: #89b4fa;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
}
QPushButton#btn_use_account:hover {
    background-color: #313244;
    border-color: #89b4fa;
}
QPushButton#btn_use_account:disabled {
    background-color: #181825;
    color: #6c7086;
    border-color: #313244;
}
QLabel#lbl_active_acc {
    color: #a6adc8;
    font-size: 12px;
    font-weight: 600;
}
QComboBox#combo_active_account {
    background-color: #24273a;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: 500;
}
QComboBox#combo_active_account:hover {
    border-color: #89b4fa;
}
QComboBox#combo_active_account:disabled {
    background-color: #181825;
    color: #6c7086;
    border-color: #313244;
}
QPushButton#btn_settings {
    background-color: #313244;
    color: #cdd6f4;
    font-size: 14px;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 2px 6px;
}
QPushButton#btn_settings:hover {
    background-color: #45475a;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #181825;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 6px 14px;
    margin-right: 4px;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
    font-size: 12px;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #89b4fa;
    font-weight: bold;
    border-color: #45475a;
    border-bottom: 2px solid #89b4fa;
}
QTabBar::tab:hover:!selected {
    background-color: #24273a;
    color: #cdd6f4;
}
QTableWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #24273a;
    border: 1px solid #313244;
    border-radius: 6px;
    selection-background-color: #313244;
    selection-color: #89b4fa;
}
QTableWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #24273a;
}
QTableWidget::item:selected {
    background-color: #313244;
    color: #89b4fa;
}
QHeaderView::section {
    background-color: #1e1e2e;
    color: #a6adc8;
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid #313244;
    font-size: 11px;
    font-weight: 600;
}
QScrollBar:vertical {
    background-color: #181825;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: #181825;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background-color: #45475a;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QComboBox, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 20px;
}
QLineEdit:focus {
    border-color: #89b4fa;
}
QScrollArea, QWidget#settings_scroll_content {
    background-color: #1e1e2e;
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    selection-background-color: #313244;
    selection-color: #89b4fa;
    padding: 4px;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #cdd6f4;
}
"""

def apply_launcher_style(app):
    """Áp dụng kiểu giao diện hiện đại đồng nhất qua QSS."""
    app.setStyleSheet(LAUNCHER_QSS)
