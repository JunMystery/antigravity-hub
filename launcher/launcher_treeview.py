# -*- coding: utf-8 -*-
"""
Module quản lý bảng danh sách tài khoản (QTableWidget) và hiển thị Quota cho Launcher (PyQt6).
Phân tách logic cập nhật và reorder sang launcher_treeview_updater.
"""

import os
import json
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QHBoxLayout, QPushButton, QAbstractItemView
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QBrush

import launcher_storage
from launcher_i18n import tr
from launcher_quota_runner import refresh_single_row_quota
from launcher_order_widget import OrderCellWidget
from launcher_quota_widget import QuotaCellWidget
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
    table.setColumnCount(7)
    table.setHorizontalHeaderLabels([
        tr("col.order"), tr("col.active"), tr("col.email"),
        tr("col.5h"), tr("col.weekly"), tr("col.argon"), tr("col.quota")
    ])
    hdr = table.horizontalHeader()
    hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(0, 64)
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(3, 108)
    hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(4, 108)
    hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(5, 108)
    hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(46)
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
        tr("col.5h"), tr("col.weekly"), tr("col.argon"), tr("col.quota")
    ])
    if hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setToolTip(tr("tooltip.refresh_all"))
    if hasattr(win, "btn_auto"):
        auto_on = win.auto_refresh_enabled
        win.btn_auto.setText(f"Auto: {'ON' if auto_on else 'OFF'}")
        win.btn_auto.setToolTip(tr("tooltip.auto_on") if auto_on else tr("tooltip.auto_off"))
        bg = "#27ae60" if auto_on else "#c0392b"
        win.btn_auto.setStyleSheet(f"background-color: {bg}; color: #ffffff; font-weight: bold;")

def resolve_active_profile_id(win, profiles: list) -> str:
    """Xác định profile_id của tài khoản đang được dùng thực tế."""
    if not profiles:
        return ""
    settings = getattr(win, "data", {}).get("settings", {})
    auto_rot = bool(settings.get("auto_rotation_enabled", True))
    active_id = (settings.get("active_account_id", "") or "").strip()

    live_email = (getattr(win, "_live_active_email", "") or "").strip().lower()
    if not live_email:
        status_path = os.path.join(launcher_storage.CONFIG_DIR, "live_status.json")
        if os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    st = json.load(f)
                cand = (st.get("account_email") or "").strip().lower()
                if cand and cand not in ("--", "proxy đã dừng", "san sang"):
                    live_email = cand
            except Exception:
                pass

    id_by_email = {
        (p.get("email") or p.get("name") or "").strip().lower(): p.get("id", "")
        for p in profiles if p.get("id")
    }
    valid_ids = {p.get("id", "") for p in profiles if p.get("id")}

    if auto_rot and live_email and live_email in id_by_email:
        return id_by_email[live_email]
    if active_id and active_id in valid_ids:
        return active_id
    if live_email and live_email in id_by_email:
        return id_by_email[live_email]
    first_enabled = next((p.get("id", "") for p in profiles if p.get("enabled", True) and p.get("id")), "")
    return first_enabled or profiles[0].get("id", "")


def _apply_email_active_style(item: QTableWidgetItem, email_val: str, is_active: bool):
    """Đánh dấu trực quan tài khoản đang được dùng trên cột Email."""
    item.setText(f"● {email_val}" if is_active else email_val)
    font = item.font()
    font.setBold(is_active)
    item.setFont(font)
    item.setForeground(QBrush(QColor("#a6e3a1" if is_active else "#cdd6f4")))


def select_active_profile_row(win):
    """Chọn và đánh dấu đúng hàng tài khoản đang được dùng trong bảng Tài khoản."""
    table = getattr(win, "treeview", None)
    if not table or table.rowCount() == 0:
        return
    profiles = getattr(win, "data", {}).get("profiles", [])
    active_pid = resolve_active_profile_id(win, profiles)
    if not active_pid:
        return
    email_map = {p.get("id"): (p.get("email") or p.get("name") or "Account") for p in profiles}
    target_row = -1
    for row_idx in range(table.rowCount()):
        item_ord = table.item(row_idx, 0)
        pid = item_ord.data(Qt.ItemDataRole.UserRole) if item_ord else None
        is_active = (pid == active_pid)
        item_email = table.item(row_idx, 2)
        if item_email:
            _apply_email_active_style(item_email, email_map.get(pid, item_email.text().lstrip("● ")), is_active)
        if is_active:
            target_row = row_idx
    if target_row >= 0:
        table.selectRow(target_row)
        item_email = table.item(target_row, 2)
        if item_email:
            table.scrollToItem(item_email)


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
        active_pid = resolve_active_profile_id(win, profiles)
        effective_select_id = select_id or active_pid
        target_row = 0

        for row_idx, p in enumerate(profiles):
            pid = p.get("id")
            if effective_select_id and pid == effective_select_id:
                target_row = row_idx

            # 0: Order (Cell Widget với Micro-Stepper ▲/▼)
            item_order = QTableWidgetItem()
            item_order.setData(Qt.ItemDataRole.UserRole, pid)
            item_order.setSizeHint(QSize(68, 24))
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

            # 2: Email (Chỉ đọc, đánh dấu ● xanh nếu là tài khoản đang dùng)
            email_val = p.get("email") or p.get("name") or "Account"
            item_email = QTableWidgetItem()
            item_email.setData(Qt.ItemDataRole.UserRole, pid)
            item_email.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            _apply_email_active_style(item_email, email_val, pid == active_pid)
            table.setItem(row_idx, 2, item_email)

            # 3: 5h Quota (Thanh Gradient + % trắng + Reset in HH:MM)
            q5_text = p.get("quota_5h") or tr("quota.not_scanned")
            q5_val = p.get("quota_5h_val", 0)
            q5_valid = p.get("quota_5h_valid", False)
            q5_reset = p.get("quota_5h_reset", "")
            cell_q5 = QuotaCellWidget(q5_val, q5_text, q5_valid, q5_reset, parent=table)
            table.setCellWidget(row_idx, 3, cell_q5)

            # 4: Weekly Quota (Thanh Gradient + % trắng + Reset in HH:MM / Xd Yh)
            qw_text = p.get("quota_weekly") or tr("quota.not_scanned")
            qw_val = p.get("quota_weekly_val", 0)
            qw_valid = p.get("quota_weekly_valid", False)
            qw_reset = p.get("quota_weekly_reset", "")
            cell_qw = QuotaCellWidget(qw_val, qw_text, qw_valid, qw_reset, parent=table)
            table.setCellWidget(row_idx, 4, cell_qw)

            # 5: Argon Weekly Quota (Gemini 4 Argon Weekly Limit)
            qa_text = p.get("quota_argon") or tr("quota.not_scanned")
            qa_val = p.get("quota_argon_val", 0)
            qa_valid = p.get("quota_argon_valid", False)
            qa_reset = p.get("quota_argon_reset", "")
            cell_qa = QuotaCellWidget(qa_val, qa_text, qa_valid, qa_reset, parent=table)
            table.setCellWidget(row_idx, 5, cell_qa)

            # 6: Single Refresh Button
            btn_row_ref = QPushButton("⟳")
            btn_row_ref.setFixedSize(28, 26)
            btn_row_ref.setStyleSheet("padding: 0px; font-size: 13px; font-weight: bold;")
            btn_row_ref.setToolTip(tr("tooltip.refresh_all"))
            btn_row_ref.clicked.connect(lambda _, prof_id=pid: refresh_single_row_quota(win, prof_id))
            btn_cell = QWidget()
            btn_layout = QHBoxLayout(btn_cell)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.addWidget(btn_row_ref)
            table.setCellWidget(row_idx, 6, btn_cell)

        if total > 0:
            table.selectRow(target_row)
            item_target = table.item(target_row, 2)
            if item_target:
                table.scrollToItem(item_target)
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
