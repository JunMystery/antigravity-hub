# -*- coding: utf-8 -*-
"""
Widget chọn và sắp xếp thứ tự danh sách tài khoản đích cho một Model Rule.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal

from launcher_i18n import tr


def _make_compact_btn(text: str, slot, fixed_size: tuple = None) -> QPushButton:
    btn = QPushButton(text)
    if fixed_size:
        btn.setFixedSize(fixed_size[0], fixed_size[1])
        btn.setStyleSheet("padding: 0px;")
    else:
        btn.setStyleSheet("padding: 2px 8px;")
    btn.clicked.connect(slot)
    return btn


class RuleAccountPicker(QWidget):
    """Khối chọn nhiều tài khoản (gồm cả Deactive) và đổi thứ tự ưu tiên."""

    accounts_changed = pyqtSignal(bool)

    def __init__(self, accounts: list, rule: dict = None, preset_account: dict = None, parent=None):
        super().__init__(parent)
        self._accounts = list(accounts or [])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(QLabel(tr("model_rules.accounts_hint")))
        header.addStretch(1)
        self.btn_acc_all = _make_compact_btn(tr("model_rules.btn_select_all"), lambda: self.select_accounts("all"))
        self.btn_acc_active = _make_compact_btn(tr("model_rules.btn_select_active"), lambda: self.select_accounts("active"))
        self.btn_acc_none = _make_compact_btn(tr("model_rules.btn_select_none"), lambda: self.select_accounts("none"))
        self.btn_acc_up = _make_compact_btn("▲", lambda: self.move_account(-1), (28, 24))
        self.btn_acc_down = _make_compact_btn("▼", lambda: self.move_account(1), (28, 24))
        for btn in (self.btn_acc_all, self.btn_acc_active, self.btn_acc_none, self.btn_acc_up, self.btn_acc_down):
            header.addWidget(btn)
        layout.addLayout(header)

        self.list_accounts = QListWidget()
        self._populate(rule or {}, preset_account)
        self.list_accounts.itemChanged.connect(lambda _: self.accounts_changed.emit(True))
        layout.addWidget(self.list_accounts, 1)

    def _populate(self, rule: dict, preset_account: dict = None):
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

        for acc, is_checked in selected_order + [(acc, False) for acc in remaining]:
            suffix = "" if acc.get("enabled", True) else f" [{tr('model_rules.status_deactive')}]"
            item = QListWidgetItem(f"{acc['email']}{suffix}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, {"id": acc["id"], "email": acc["email"]})
            item.setData(Qt.ItemDataRole.UserRole + 1, acc.get("enabled", True) is not False)
            self.list_accounts.addItem(item)

    def get_selected_accounts(self) -> list:
        return [
            self.list_accounts.item(idx).data(Qt.ItemDataRole.UserRole)
            for idx in range(self.list_accounts.count())
            if self.list_accounts.item(idx).checkState() == Qt.CheckState.Checked
        ]

    def select_accounts(self, mode: str):
        self.list_accounts.blockSignals(True)
        try:
            for idx in range(self.list_accounts.count()):
                item = self.list_accounts.item(idx)
                is_active = bool(item.data(Qt.ItemDataRole.UserRole + 1))
                checked = True if mode == "all" else (is_active if mode == "active" else False)
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        finally:
            self.list_accounts.blockSignals(False)
        self.accounts_changed.emit(True)

    def move_account(self, delta: int):
        row = self.list_accounts.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.list_accounts.count():
            return
        self.list_accounts.blockSignals(True)
        try:
            item = self.list_accounts.takeItem(row)
            self.list_accounts.insertItem(target, item)
            self.list_accounts.setCurrentRow(target)
        finally:
            self.list_accounts.blockSignals(False)
        self.accounts_changed.emit(False)
