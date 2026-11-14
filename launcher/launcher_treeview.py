# -*- coding: utf-8 -*-
"""
Module quản lý bảng danh sách tài khoản (QTableWidget) và hiển thị Quota cho Launcher (PyQt6).
"""

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QHBoxLayout, QCheckBox, QPushButton, QLabel, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from launcher_i18n import tr
from launcher_quota_runner import refresh_single_row_quota

def get_quota_color(val: float, is_valid: bool) -> str:
    """Trả về mã màu hiển thị dựa trên tỉ lệ Quota còn lại."""
    if not is_valid:
        return "#f38ba8"
    if val >= 50.0:
        return "#a6e3a1"
    if val >= 20.0:
        return "#f9e2af"
    return "#f38ba8"

def setup_treeview(win):
    """Khởi tạo bảng hiển thị danh sách tài khoản và thanh điều khiển Quota."""
    # Thanh điều khiển Quota nhanh đặt ngay trên bảng
    quota_bar = QHBoxLayout()
    quota_bar.setContentsMargins(0, 0, 0, 2)
    quota_bar.setSpacing(8)

    quota_bar.addStretch(1)

    win.btn_auto = QPushButton()
    win.btn_auto.setFixedHeight(28)
    win.btn_auto.clicked.connect(win.on_toggle_auto_quota)
    quota_bar.addWidget(win.btn_auto)

    win.btn_refresh_all = QPushButton("⟳")
    win.btn_refresh_all.setToolTip(tr("tooltip.refresh_all"))
    win.btn_refresh_all.setFixedHeight(28)
    win.btn_refresh_all.clicked.connect(win.on_refresh_all_quota)
    quota_bar.addWidget(win.btn_refresh_all)

    win.table_container.addLayout(quota_bar)

    # Bảng QTableWidget
    table = QTableWidget(win)
    table.setColumnCount(6)
    table.setHorizontalHeaderLabels([
        tr("col.order"), tr("col.active"), tr("col.email"),
        tr("col.5h"), tr("col.weekly"), tr("col.quota")
    ])
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(True)
    table.itemDoubleClicked.connect(win.on_row_double_clicked)

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
        if auto_on:
            win.btn_auto.setStyleSheet("background-color: #27ae60; color: #ffffff; font-weight: bold;")
        else:
            win.btn_auto.setStyleSheet("background-color: #c0392b; color: #ffffff; font-weight: bold;")

def populate_treeview(win, select_id=None):
    """Nạp danh sách profiles vào QTableWidget."""
    table = win.treeview
    table.setRowCount(0)
    profiles = win.data.get("profiles", [])

    total = len(profiles)
    enabled_count = sum(1 for p in profiles if p.get("enabled", True))
    reqs_val = win.data.get("settings", {}).get("requests_per_account", 1)

    if total == 0:
        win.lbl_info.setText(tr("info.empty"))
        win.btn_launch.setEnabled(False)
        return

    win.lbl_info.setText(f"Tài khoản: <b>{enabled_count}/{total}</b> Active | <b>{reqs_val}</b> req/acc")
    win.btn_launch.setEnabled(enabled_count > 0)

    table.setRowCount(total)
    target_row = 0

    for row_idx, p in enumerate(profiles):
        pid = p.get("id")
        if select_id and pid == select_id:
            target_row = row_idx

        # 0: Order
        item_order = QTableWidgetItem(str(p.get("order", row_idx + 1)))
        item_order.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_order.setData(Qt.ItemDataRole.UserRole, pid)
        table.setItem(row_idx, 0, item_order)

        # 1: Active Checkbox
        cell_widget = QWidget()
        chk_layout = QHBoxLayout(cell_widget)
        chk_layout.setContentsMargins(0, 0, 0, 0)
        chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk = QCheckBox()
        chk.setChecked(p.get("enabled", True))
        chk.toggled.connect(lambda checked, prof_id=pid: win.on_account_toggled(prof_id, checked))
        chk_layout.addWidget(chk)
        table.setCellWidget(row_idx, 1, cell_widget)

        # 2: Email
        item_email = QTableWidgetItem(p.get("name") or p.get("email") or "Account")
        item_email.setData(Qt.ItemDataRole.UserRole, pid)
        table.setItem(row_idx, 2, item_email)

        # 3: 5h Quota
        q5_text = p.get("quota_5h", "Chưa quét")
        item_q5 = QTableWidgetItem(q5_text)
        item_q5.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        c5 = get_quota_color(p.get("quota_5h_val", 0), p.get("quota_5h_valid", False))
        item_q5.setForeground(QColor(c5))
        table.setItem(row_idx, 3, item_q5)

        # 4: Weekly Quota
        qw_text = p.get("quota_weekly", "Chưa quét")
        item_qw = QTableWidgetItem(qw_text)
        item_qw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        cw = get_quota_color(p.get("quota_weekly_val", 0), p.get("quota_weekly_valid", False))
        item_qw.setForeground(QColor(cw))
        table.setItem(row_idx, 4, item_qw)

        # 5: Single Refresh Button
        btn_row_ref = QPushButton("⟳")
        btn_row_ref.setFixedSize(28, 24)
        btn_row_ref.clicked.connect(lambda _, prof_id=pid: refresh_single_row_quota(win, prof_id))
        btn_cell = QWidget()
        btn_layout = QHBoxLayout(btn_cell)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(btn_row_ref)
        table.setCellWidget(row_idx, 5, btn_cell)

    if total > 0:
        table.selectRow(target_row)

def get_selected_profile(win):
    """Lấy thông tin profile tại hàng đang được chọn."""
    table = win.treeview
    selected_rows = table.selectionModel().selectedRows()
    if not selected_rows:
        return None
    row_idx = selected_rows[0].row()
    item = table.item(row_idx, 0)
    if not item:
        return None
    pid = item.data(Qt.ItemDataRole.UserRole)
    for p in win.data.get("profiles", []):
        if p.get("id") == pid:
            return p
    return None

def mark_all_rows_refreshing(win):
    """Đánh dấu tất cả các hàng trong bảng đang trong trạng thái quét Quota."""
    if not hasattr(win, "treeview") or not win.treeview:
        return
    table = win.treeview
    pending_color = QColor("#89b4fa")
    for row in range(table.rowCount()):
        item_q5 = table.item(row, 3)
        if item_q5:
            item_q5.setText("Đang quét...")
            item_q5.setForeground(pending_color)
        item_qw = table.item(row, 4)
        if item_qw:
            item_qw.setText("Đang quét...")
            item_qw.setForeground(pending_color)

def mark_single_row_refreshing(win, profile_id):
    """Đánh dấu một hàng cụ thể đang trong trạng thái quét Quota."""
    if not hasattr(win, "treeview") or not win.treeview:
        return
    table = win.treeview
    pending_color = QColor("#89b4fa")
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole) == profile_id:
            item_q5 = table.item(row, 3)
            if item_q5:
                item_q5.setText("Đang quét...")
                item_q5.setForeground(pending_color)
            item_qw = table.item(row, 4)
            if item_qw:
                item_qw.setText("Đang quét...")
                item_qw.setForeground(pending_color)
            break

def update_row_quota_display(win, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid):
    """Cập nhật hiển thị Quota cho một hàng theo profile_id."""
    table = win.treeview
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole) == profile_id:
            item_q5 = table.item(row, 3)
            if item_q5:
                item_q5.setText(q5_text)
                item_q5.setForeground(QColor(get_quota_color(q5_val, q5_valid)))

            item_qw = table.item(row, 4)
            if item_qw:
                item_qw.setText(qw_text)
                item_qw.setForeground(QColor(get_quota_color(qw_val, qw_valid)))
            break
