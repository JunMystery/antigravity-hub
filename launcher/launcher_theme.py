# -*- coding: utf-8 -*-
"""
Module định nghĩa kiểu dáng giao diện QSS (Catppuccin Mocha Dark Theme) cho Antigravity Launcher.
"""

LAUNCHER_QSS = """
QMainWindow {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
    color: #cdd6f4;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton:disabled {
    background-color: #181825;
    color: #6c7086;
    border-color: #313244;
}
QPushButton#btn_launch {
    background-color: #2980b9;
    color: #ffffff;
    font-weight: bold;
    font-size: 14px;
    padding: 10px;
    border-radius: 6px;
    border: none;
}
QPushButton#btn_launch:hover {
    background-color: #3498db;
}
QPushButton#btn_launch:disabled {
    background-color: #313244;
    color: #6c7086;
}
QPushButton#btn_launch_app {
    background-color: #2980b9;
    color: #ffffff;
    font-weight: bold;
    font-size: 13px;
    padding: 10px;
    border-radius: 6px;
    border: none;
}
QPushButton#btn_launch_app:hover {
    background-color: #3498db;
}
QPushButton#btn_launch_app:disabled {
    background-color: #313244;
    color: #6c7086;
}
QPushButton#btn_launch_ide {
    background-color: #7287fd;
    color: #ffffff;
    font-weight: bold;
    font-size: 13px;
    padding: 10px;
    border-radius: 6px;
    border: none;
}
QPushButton#btn_launch_ide:hover {
    background-color: #8839ef;
}
QPushButton#btn_launch_ide:disabled {
    background-color: #313244;
    color: #6c7086;
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
QTableWidget {
    background-color: #181825;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 6px;
    selection-background-color: #45475a;
}
QHeaderView::section {
    background-color: #313244;
    color: #cdd6f4;
    padding: 4px;
    border: 1px solid #45475a;
    font-weight: bold;
}
QComboBox, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 10px;
    font-weight: bold;
}
"""

def apply_launcher_style(app):
    """Áp dụng kiểu giao diện hiện đại đồng nhất qua QSS."""
    app.setStyleSheet(LAUNCHER_QSS)
