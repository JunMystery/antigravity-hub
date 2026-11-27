# -*- coding: utf-8 -*-
"""
Widget chọn và sắp xếp nhanh thứ tự ưu tiên danh sách tài khoản đích cho một Model Rule.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from launcher_i18n import tr
from launcher_order_widget import OrderCellWidget
from launcher_item_list_dialog import wrap_cell_widgets


def _make_compact_btn(text: str, slot) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet("padding: 2px 8px;")
    btn.clicked.connect(slot)
    return btn


class RuleAccountPicker(QWidget):
    """Khối chọn nhiều tài khoản (gồm cả Deactive) và đổi nhanh thứ tự ưu tiên."""

    accounts_changed = pyqtSignal(bool)

    def __init__(self, accounts: list, rule: dict = None, preset_account: dict = None, parent=None):
        super().__init__(parent)
        self._accounts = list(accounts or [])
        self._rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(QLabel(tr("model_rules.accounts_hint")))
        header.addStretch(1)
        self.btn_acc_all = _make_compact_btn(tr("model_rules.btn_select_all"), lambda: self.select_accounts("all"))
        self.btn_acc_active = _make_compact_btn(tr("model_rules.btn_select_active"), lambda: self.select_accounts("active"))
        self.btn_acc_none = _make_compact_btn(tr("model_rules.btn_select_none"), lambda: self.select_accounts("none"))
        for btn in (self.btn_acc_all, self.btn_acc_active, self.btn_acc_none):
            header.addWidget(btn)
        layout.addLayout(header)

        self.table_accounts = QTableWidget(0, 3)
        self.list_accounts = self.table_accounts  # Backwards-compat attribute alias
        self.table_accounts.setHorizontalHeaderLabels([
            tr("model_rules.col_priority"), tr("model_rules.enabled"), tr("model_rules.col_account")
        ])
        self.table_accounts.verticalHeader().setVisible(False)
        self.table_accounts.verticalHeader().setDefaultSectionSize(40)
        self.table_accounts.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_accounts.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_accounts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = self.table_accounts.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_accounts.setColumnWidth(0, 72)
        self.table_accounts.setColumnWidth(1, 46)

        self._init_rows(rule or {}, preset_account)
        self._render_table()
        layout.addWidget(self.table_accounts, 1)

    def _init_rows(self, rule: dict, preset_account: dict = None):
        selected_refs = list(rule.get("accounts") or [])
        if not selected_refs and (rule.get("account_id") or rule.get("account_email")):
            selected_refs = [{"id": rule.get("account_id", ""), "email": rule.get("account_email", "")}]
        if not selected_refs and preset_account and (preset_account.get("id") or preset_account.get("email")):
            selected_refs = [preset_account]

        selected_order = []
        remaining = list(self._accounts)
        for ref in selected_refs:
            rem_next = []
            ref_email = str(ref.get("email") or "").lower()
            ref_id = str(ref.get("id") or "").lower()
            for acc in remaining:
                if (ref_email and acc["email"].lower() == ref_email) or (ref_id and acc["id"].lower() == ref_id):
                    selected_order.append((acc, True))
                else:
                    rem_next.append(acc)
            remaining = rem_next

        self._rows = [
            {
                "id": acc["id"],
                "email": acc["email"],
                "enabled": acc.get("enabled", True) is not False,
                "checked": is_checked,
            }
            for acc, is_checked in selected_order + [(acc, False) for acc in remaining]
        ]

    def _render_table(self, select_row: int = None):
        total = len(self._rows)
        self.table_accounts.setUpdatesEnabled(False)
        try:
            self.table_accounts.setRowCount(0)
            for idx, entry in enumerate(self._rows):
                row = self.table_accounts.rowCount()
                self.table_accounts.insertRow(row)

                ord_widget = OrderCellWidget(
                    pid=str(idx),
                    order_num=idx + 1,
                    is_first=(idx == 0),
                    is_last=(idx == total - 1),
                    on_step_callback=lambda p, d: self.move_account(d, int(p)),
                    on_edit_callback=lambda p, v: self.reorder_account_to(int(p), v),
                    parent=self.table_accounts
                )
                self.table_accounts.setCellWidget(row, 0, ord_widget)

                chk = QCheckBox()
                chk.setChecked(bool(entry["checked"]))
                chk.toggled.connect(lambda state, i=idx: self._on_check_toggled(i, state))
                self.table_accounts.setCellWidget(row, 1, wrap_cell_widgets([chk], center=True, margins=(2, 0, 2, 0)))

                suffix = "" if entry["enabled"] else f" [{tr('model_rules.status_deactive')}]"
                self.table_accounts.setItem(row, 2, QTableWidgetItem(f"{entry['email']}{suffix}"))

            if select_row is not None and 0 <= select_row < total:
                self.table_accounts.selectRow(select_row)
        finally:
            self.table_accounts.setUpdatesEnabled(True)

    def _on_check_toggled(self, idx: int, state: bool):
        if 0 <= idx < len(self._rows):
            self._rows[idx]["checked"] = bool(state)
            self.accounts_changed.emit(True)

    def get_selected_accounts(self) -> list:
        return [
            {"id": entry["id"], "email": entry["email"]}
            for entry in self._rows
            if entry["checked"]
        ]

    def select_accounts(self, mode: str):
        for entry in self._rows:
            entry["checked"] = True if mode == "all" else (entry["enabled"] if mode == "active" else False)
        self._render_table()
        self.accounts_changed.emit(True)

    def move_account(self, delta: int, row: int = None):
        cur = self.table_accounts.currentRow() if row is None else row
        target = cur + delta
        if cur < 0 or target < 0 or target >= len(self._rows):
            return
        self._rows[cur], self._rows[target] = self._rows[target], self._rows[cur]
        self._render_table(select_row=target)
        self.accounts_changed.emit(False)

    def reorder_account_to(self, idx: int, new_order: int):
        if 0 <= idx < len(self._rows):
            target = max(0, min(int(new_order) - 1, len(self._rows) - 1))
            entry = self._rows.pop(idx)
            self._rows.insert(target, entry)
            self._render_table(select_row=target)
            self.accounts_changed.emit(False)
