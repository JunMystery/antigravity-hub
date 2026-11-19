# -*- coding: utf-8 -*-
"""
Module quản lý cập nhật trạng thái hiển thị Quota, hoạt ảnh xoay (Spinners)
và thao tác điều chỉnh thứ tự (Reorder) tài khoản trong bảng Launcher.
"""

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from launcher_storage import save_data

def get_quota_color(val: float, is_valid: bool) -> str:
    """Trả về mã màu hiển thị dựa trên tỉ lệ Quota còn lại."""
    if not is_valid or val < 20.0:
        return "#f38ba8"
    return "#a6e3a1" if val >= 50.0 else "#f9e2af"

def _set_row_spinner(table, row: int, char: str, color: QColor):
    refresh_col = max(5, table.columnCount() - 1)
    for col in range(3, refresh_col):
        widget = table.cellWidget(row, col)
        if widget and hasattr(widget, "set_spinner"):
            widget.set_spinner(char, color)
        else:
            item = table.item(row, col)
            if item:
                item.setText(char)
                if color:
                    item.setForeground(color)
    cell = table.cellWidget(row, refresh_col)
    btn = cell.findChild(QPushButton) if cell else None
    if btn:
        btn.setText(char)
        btn.setEnabled(False)

def mark_all_rows_refreshing(win, spinner_char="⠋"):
    """Đánh dấu tất cả các hàng trong bảng đang trong trạng thái quét Quota bằng Busy icon."""
    if not hasattr(win, "treeview") or not win.treeview:
        return
    table = win.treeview
    pending_color = QColor("#89b4fa")
    if not hasattr(win, "refreshing_profile_ids"):
        win.refreshing_profile_ids = set()
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole):
            win.refreshing_profile_ids.add(item.data(Qt.ItemDataRole.UserRole))
        _set_row_spinner(table, row, spinner_char, pending_color)

def mark_single_row_refreshing(win, profile_id, spinner_char="⠋"):
    """Đánh dấu một hàng cụ thể đang trong trạng thái quét Quota bằng Busy icon."""
    if not hasattr(win, "treeview") or not win.treeview:
        return
    table = win.treeview
    pending_color = QColor("#89b4fa")
    if not hasattr(win, "refreshing_profile_ids"):
        win.refreshing_profile_ids = set()
    win.refreshing_profile_ids.add(profile_id)
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole) == profile_id:
            _set_row_spinner(table, row, spinner_char, pending_color)
            break

def update_refreshing_spinners(win, spinner_char):
    """Cập nhật frame Busy icon tiếp theo cho các hàng đang quét."""
    if not hasattr(win, "treeview") or not win.treeview:
        return
    table = win.treeview
    pending_pids = getattr(win, "refreshing_profile_ids", set())
    if not pending_pids:
        return
    pending_color = QColor("#89b4fa")
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole) in pending_pids:
            _set_row_spinner(table, row, spinner_char, pending_color)

def _update_quota_cell(table, row: int, col: int, val, text: str, is_valid: bool, reset_text: str = ""):
    widget = table.cellWidget(row, col)
    if widget and hasattr(widget, "set_quota"):
        widget.set_quota(val, text, is_valid, reset_text)
    else:
        item = table.item(row, col)
        if item:
            item.setText(text)
            item.setForeground(QColor(get_quota_color(val, is_valid)))


def update_row_quota_display(
    win, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid,
    q5_reset="", qw_reset="", qa_val=0, qa_text="--", qa_valid=False, qa_reset=""
):
    """Cập nhật hiển thị Quota cho một hàng theo profile_id."""
    if hasattr(win, "refreshing_profile_ids"):
        win.refreshing_profile_ids.discard(profile_id)
    table = win.treeview
    refresh_col = max(5, table.columnCount() - 1)
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole) == profile_id:
            _update_quota_cell(table, row, 3, q5_val, q5_text, q5_valid, q5_reset)
            _update_quota_cell(table, row, 4, qw_val, qw_text, qw_valid, qw_reset)
            if table.columnCount() >= 7:
                _update_quota_cell(table, row, 5, qa_val, qa_text, qa_valid, qa_reset)

            cell = table.cellWidget(row, refresh_col)
            btn = cell.findChild(QPushButton) if cell else None
            if btn:
                btn.setText("⟳")
                btn.setEnabled(True)
            break

def move_profile_step(win, pid: str, delta: int, populate_fn=None):
    """Di chuyển tài khoản lên hoặc xuống 1 nấc (swap với phần tử liền kề)."""
    profiles = win.data.get("profiles", [])
    idx = next((i for i, p in enumerate(profiles) if p.get("id") == pid), None)
    if idx is None or idx + delta < 0 or idx + delta >= len(profiles):
        return
    win.is_editing_order = True
    try:
        profiles[idx], profiles[idx + delta] = profiles[idx + delta], profiles[idx]
        for i, p in enumerate(profiles):
            p["order"] = i + 1
        save_data(win.data)
        if populate_fn:
            populate_fn(win, select_id=pid)
    finally:
        win.is_editing_order = False

def reorder_profile_to(win, pid: str, new_val: int, populate_fn=None):
    """Di chuyển tài khoản đến vị trí thứ tự chỉ định."""
    profiles = win.data.get("profiles", [])
    target_idx = next((i for i, p in enumerate(profiles) if p.get("id") == pid), None)
    if target_idx is None:
        return
    win.is_editing_order = True
    try:
        target = profiles.pop(target_idx)
        profiles.insert(max(0, min(new_val - 1, len(profiles))), target)
        for idx, p in enumerate(profiles):
            p["order"] = idx + 1
        save_data(win.data)
        if populate_fn:
            populate_fn(win, select_id=pid)
    finally:
        win.is_editing_order = False
