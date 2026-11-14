# -*- coding: utf-8 -*-
"""
Module quản lý bảng danh sách tài khoản (QTableWidget) và hiển thị Quota cho Launcher (PyQt6).
Phân tách logic cập nhật và reorder sang launcher_treeview_updater.
"""

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QHBoxLayout, QPushButton, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from launcher_i18n import tr
from launcher_quota_runner import refresh_single_row_quota
from launcher_order_widget import OrderCellWidget
from launcher_toggle_switch import ToggleSwitch

from launcher_treeview_updater import (
    get_quota_color,
    mark_all_rows_refreshing,
    mark_single_row_refreshing,
    update_refreshing_spinners,
    update_row_quota_display,
    move_profile_step as _move_profile_step_base,
    reorder_profile_to as _reorder_profile_to_base
)

def move_profile_step(win, pid: str, delta: int):
    """Di chuyển tài khoản lên hoặc xuống 1 nấc."""
    _move_profile_step_base(win, pid, delta, populate_treeview)

def reorder_profile_to(win, pid: str, new_val: int):
    """Di chuyển tài khoản đến vị trí thứ tự chỉ định."""
    _reorder_profile_to_base(win, pid, new_val, populate_treeview)

def setup_treeview(win):
    """Khởi tạo bảng hiển thị danh sách tài khoản."""
    table = QTableWidget(win)
    table.setColumnCount(6)
    table.setHorizontalHeaderLabels([
        tr("col.order"), tr("col.active"), tr("col.email"),
        tr("col.5h"), tr("col.weekly"), tr("col.quota")
    ])
    hdr = table.horizontalHeader()
    for col in range(6):
        hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch if col == 2 else QHeaderView.ResizeMode.ResizeToContents)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(True)

    win.table_container.addWidget(table, 1)
    win.treeview = table
    update_treeview_headers(win)
    return table

def update_treeview_headers(win):
    """Cập nhật tiêu đề các cột và trạng thái nút Auto Quota khi đổi ngôn ngữ."""
    if not hasattr(win, "treeview") or not win.treeview:
        return
    win.treeview.setHorizontalHeaderLabels([
        tr("col.order"), tr("col.active"), tr("col.email"),
        tr("col.5h"), tr("col.weekly"), tr("col.quota")
    ])
    if hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setToolTip(tr("tooltip.refresh_all"))
    if hasattr(win, "btn_auto"):
        auto_on = win.auto_refresh_enabled
        win.btn_auto.setText(f"Auto: {'ON' if auto_on else 'OFF'}")
        win.btn_auto.setToolTip(tr("tooltip.auto_on") if auto_on else tr("tooltip.auto_off"))
        bg = "#27ae60" if auto_on else "#c0392b"
        win.btn_auto.setStyleSheet(f"background-color: {bg}; color: #ffffff; font-weight: bold;")

def populate_treeview(win, select_id=None):
    """Nạp danh sách profiles vào QTableWidget."""
    win.is_updating_table = True
    try:
        table = win.treeview
        table.setRowCount(0)
        profiles = win.data.get("profiles", [])

        total = len(profiles)
        enabled_count = sum(1 for p in profiles if p.get("enabled", True))
        reqs_val = win.data.get("settings", {}).get("requests_per_account", 1)

        if total == 0:
            win.lbl_info.setText(tr("info.empty"))
            for b in (getattr(win, "btn_launch_app", None), getattr(win, "btn_launch_ide", None)):
                if b:
                    b.setEnabled(False)
            return

        win.lbl_info.setText(tr("info.summary").format(enabled=enabled_count, total=total, reqs=reqs_val))
        can_run = enabled_count > 0
        for b in (getattr(win, "btn_launch_app", None), getattr(win, "btn_launch_ide", None)):
            if b:
                b.setEnabled(can_run)

        table.setRowCount(total)
        target_row = 0

        for row_idx, p in enumerate(profiles):
            pid = p.get("id")
            if select_id and pid == select_id:
                target_row = row_idx

            # 0: Order (Cell Widget với Micro-Stepper ▲/▼)
            item_order = QTableWidgetItem()
            item_order.setData(Qt.ItemDataRole.UserRole, pid)
            table.setItem(row_idx, 0, item_order)

            is_first = (row_idx == 0)
            is_last = (row_idx == total - 1)
            ord_widget = OrderCellWidget(
                pid=pid,
                order_num=p.get("order", row_idx + 1),
                is_first=is_first,
                is_last=is_last,
                on_step_callback=lambda p_id, delta: move_profile_step(win, p_id, delta),
                on_edit_callback=lambda p_id, new_val: reorder_profile_to(win, p_id, new_val),
                parent=table
            )
            table.setCellWidget(row_idx, 0, ord_widget)

            # 1: Active Toggle Switch
            cell_widget = QWidget()
            chk_layout = QHBoxLayout(cell_widget)
            chk_layout.setContentsMargins(4, 0, 4, 0)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            switch = ToggleSwitch(checked=p.get("enabled", True), parent=cell_widget)
            switch.toggled.connect(lambda checked, prof_id=pid: win.on_account_toggled(prof_id, checked))
            chk_layout.addWidget(switch)
            table.setCellWidget(row_idx, 1, cell_widget)

            # 2: Email (Chỉ đọc, luôn ưu tiên hiển thị địa chỉ email thực tế)
            email_val = p.get("email") or p.get("name") or "Account"
            item_email = QTableWidgetItem(email_val)
            item_email.setData(Qt.ItemDataRole.UserRole, pid)
            item_email.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row_idx, 2, item_email)

            # 3: 5h Quota (Chỉ đọc)
            q5_text = p.get("quota_5h") or tr("quota.not_scanned")
            item_q5 = QTableWidgetItem(q5_text)
            item_q5.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cq5 = get_quota_color(p.get("quota_5h_val", 0), p.get("quota_5h_valid", False))
            item_q5.setForeground(QColor(cq5))
            item_q5.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row_idx, 3, item_q5)

            # 4: Weekly Quota (Chỉ đọc)
            qw_text = p.get("quota_weekly") or tr("quota.not_scanned")
            item_qw = QTableWidgetItem(qw_text)
            item_qw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cw = get_quota_color(p.get("quota_weekly_val", 0), p.get("quota_weekly_valid", False))
            item_qw.setForeground(QColor(cw))
            item_qw.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row_idx, 4, item_qw)

            # 5: Single Refresh Button
            btn_row_ref = QPushButton("⟳")
            btn_row_ref.setFixedSize(28, 24)
            btn_row_ref.setStyleSheet("padding: 0px; font-size: 13px; font-weight: bold;")
            btn_row_ref.setToolTip(tr("tooltip.refresh_all"))
            btn_row_ref.clicked.connect(lambda _, prof_id=pid: refresh_single_row_quota(win, prof_id))
            btn_cell = QWidget()
            btn_layout = QHBoxLayout(btn_cell)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.addWidget(btn_row_ref)
            table.setCellWidget(row_idx, 5, btn_cell)

        if total > 0:
            table.selectRow(target_row)
    finally:
        win.is_updating_table = False

def get_selected_profile(win):
    """Lấy thông tin profile tại hàng đang được chọn."""
    table = win.treeview
    selected_rows = table.selectionModel().selectedRows()
    if not selected_rows:
        return None
    item = table.item(selected_rows[0].row(), 0)
    pid = item.data(Qt.ItemDataRole.UserRole) if item else None
    return next((p for p in win.data.get("profiles", []) if p.get("id") == pid), None)
