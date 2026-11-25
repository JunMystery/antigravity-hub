# -*- coding: utf-8 -*-
"""
Hộp thoại thiết lập chi tiết một Quy tắc Model (ModelRuleEditorDialog).
Chọn Tài khoản đích trước, sau đó tự động hiển thị / Query danh sách Model hỗ trợ,
bảo toàn tick chọn khi lọc tìm kiếm và cảnh báo các tài khoản không hỗ trợ model.
"""

import re
import uuid
import threading
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QPushButton, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from launcher_i18n import tr
from launcher_model_discovery import (
    collect_available_accounts, fetch_all_accounts_models, get_rule_patterns_py
)
from launcher_model_selector import MultiModelSelector


def _make_compact_btn(text: str, slot, fixed_size: tuple = None) -> QPushButton:
    btn = QPushButton(text)
    if fixed_size:
        btn.setFixedSize(fixed_size[0], fixed_size[1])
        btn.setStyleSheet("padding: 0px;")
    else:
        btn.setStyleSheet("padding: 2px 8px;")
    btn.clicked.connect(slot)
    return btn


class ModelRuleEditorDialog(QDialog):
    """Hộp thoại tạo/chỉnh sửa quy tắc định tuyến Model chuyên sâu."""

    query_completed = pyqtSignal(list)

    def __init__(
        self, win, parent=None, rule: dict = None, preset_model: str = "",
        preset_models: list = None, extra_models: list = None,
        preset_account: dict = None, scanned_cache: dict = None
    ):
        q_parent = parent if isinstance(parent, QWidget) else (win if isinstance(win, QWidget) else None)
        super().__init__(q_parent)
        self.win = win
        self._rule = dict(rule or {})
        self._is_alive = True
        self.setWindowTitle(tr("model_rules.editor_title"))
        self.setMinimumSize(580, 640)

        self._accounts = collect_available_accounts(win.data)
        self._acc_by_email = {str(a.get("email") or "").lower(): a for a in self._accounts if a.get("email")}
        self._scan_cache = {str(k).lower(): dict(v) for k, v in (scanned_cache or {}).items() if k}
        self._querying_emails = set()
        self._result_rule = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        self.edit_name = QLineEdit(str(self._rule.get("name") or ""))
        self.edit_name.setPlaceholderText(tr("model_rules.name_placeholder"))
        self.chk_enabled = QCheckBox(tr("model_rules.enabled"))
        self.chk_enabled.setChecked(self._rule.get("enabled", True) is not False)
        top_row.addWidget(QLabel(tr("model_rules.rule_name")))
        top_row.addWidget(self.edit_name, 1)
        top_row.addWidget(self.chk_enabled)
        layout.addLayout(top_row)

        opts_row = QHBoxLayout()
        self.combo_match_type = QComboBox()
        self.combo_match_type.addItem(tr("model_rules.match_contains"), "contains")
        self.combo_match_type.addItem(tr("model_rules.match_exact"), "exact")
        self.combo_match_type.addItem(tr("model_rules.match_regex"), "regex")
        idx_m = self.combo_match_type.findData(str(self._rule.get("match_type") or "contains").lower())
        self.combo_match_type.setCurrentIndex(max(0, idx_m))

        self.combo_strategy = QComboBox()
        self.combo_strategy.addItem(tr("model_rules.strategy_priority"), "priority")
        self.combo_strategy.addItem(tr("model_rules.strategy_round_robin"), "round_robin")
        idx_s = self.combo_strategy.findData(str(self._rule.get("strategy") or "priority").lower())
        self.combo_strategy.setCurrentIndex(max(0, idx_s))

        opts_row.addWidget(QLabel(tr("model_rules.col_match_type")))
        opts_row.addWidget(self.combo_match_type, 1)
        opts_row.addWidget(QLabel(tr("model_rules.col_strategy")))
        opts_row.addWidget(self.combo_strategy, 1)
        layout.addLayout(opts_row)

        acc_header = QHBoxLayout()
        acc_header.addWidget(QLabel(tr("model_rules.accounts_hint")))
        acc_header.addStretch(1)
        self.btn_acc_all = _make_compact_btn(tr("model_rules.btn_select_all"), lambda: self._select_accounts("all"))
        self.btn_acc_active = _make_compact_btn(tr("model_rules.btn_select_active"), lambda: self._select_accounts("active"))
        self.btn_acc_none = _make_compact_btn(tr("model_rules.btn_select_none"), lambda: self._select_accounts("none"))
        self.btn_acc_up = _make_compact_btn("▲", lambda: self._move_account(-1), (28, 24))
        self.btn_acc_down = _make_compact_btn("▼", lambda: self._move_account(1), (28, 24))
        for btn in (self.btn_acc_all, self.btn_acc_active, self.btn_acc_none, self.btn_acc_up, self.btn_acc_down):
            acc_header.addWidget(btn)
        layout.addLayout(acc_header)

        self.list_accounts = QListWidget()
        self._populate_account_list(preset_account)
        self.list_accounts.itemChanged.connect(lambda _: self._on_accounts_changed(auto_query=True))
        layout.addWidget(self.list_accounts, 1)

        if preset_account and preset_models and str(preset_account.get("email") or "").strip():
            p_email = str(preset_account["email"]).strip()
            self._scan_cache.setdefault(p_email.lower(), {"id": preset_account.get("id", ""), "email": p_email, "ok": True, "models": list(preset_models)})

        rule_patterns = get_rule_patterns_py(self._rule)
        initial_patterns = list(rule_patterns)
        if not initial_patterns:
            if preset_model:
                initial_patterns = [preset_model]
            elif preset_models:
                initial_patterns = [preset_models[0]]
        self.model_selector = MultiModelSelector(
            initial_patterns=initial_patterns,
            saved_patterns=rule_patterns,
            parent=self
        )
        self.model_selector.query_requested.connect(self.query_selected_accounts)
        layout.addWidget(self.model_selector, 1)

        self.chk_fallback = QCheckBox(tr("model_rules.fallback_global_opt"))
        self.chk_fallback.setChecked(bool(self._rule.get("fallback_to_global", False)))
        layout.addWidget(self.chk_fallback)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_cancel = QPushButton(tr("btn.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton(tr("model_rules.btn_save"))
        self.btn_save.setObjectName("btn_primary")
        self.btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

        self.query_completed.connect(self._on_query_finished)
        self._on_accounts_changed(auto_query=True)

    def done(self, result: int):
        self._is_alive = False
        super().done(result)

    def _populate_account_list(self, preset_account: dict = None):
        selected_refs = list(self._rule.get("accounts") or [])
        if not selected_refs and (self._rule.get("account_id") or self._rule.get("account_email")):
            selected_refs = [{"id": self._rule.get("account_id", ""), "email": self._rule.get("account_email", "")}]
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

    def _get_selected_accounts(self) -> list:
        return [
            self.list_accounts.item(idx).data(Qt.ItemDataRole.UserRole)
            for idx in range(self.list_accounts.count())
            if self.list_accounts.item(idx).checkState() == Qt.CheckState.Checked
        ]

    def _select_accounts(self, mode: str):
        self.list_accounts.blockSignals(True)
        try:
            for idx in range(self.list_accounts.count()):
                item = self.list_accounts.item(idx)
                is_active = bool(item.data(Qt.ItemDataRole.UserRole + 1))
                checked = True if mode == "all" else (is_active if mode == "active" else False)
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        finally:
            self.list_accounts.blockSignals(False)
        self._on_accounts_changed(auto_query=True)

    def _move_account(self, delta: int):
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
        self._on_accounts_changed(auto_query=False)

    def _on_accounts_changed(self, auto_query: bool = True):
        selected = self._get_selected_accounts()
        self.model_selector.refresh_models(selected, self._scan_cache)
        if not auto_query or not selected:
            return
        uncached = [
            acc for acc in selected
            if str(acc.get("email") or "").lower() not in self._scan_cache
            and str(acc.get("email") or "").lower() not in self._querying_emails
        ]
        if uncached:
            self._start_query_accounts(uncached)

    def query_selected_accounts(self):
        selected = self._get_selected_accounts()
        if selected:
            self._start_query_accounts(selected)

    def _start_query_accounts(self, target_refs: list):
        full_targets = []
        for ref in target_refs:
            email_key = str(ref.get("email") or "").lower()
            if not email_key or email_key in self._querying_emails:
                continue
            self._querying_emails.add(email_key)
            full_targets.append(self._acc_by_email.get(email_key, ref))
        if not full_targets:
            return
        self.model_selector.set_querying(True)
        threading.Thread(
            target=lambda: self.query_completed.emit(fetch_all_accounts_models(full_targets)),
            daemon=True
        ).start()

    def _on_query_finished(self, results: list):
        for entry in (results or []):
            email_key = str(entry.get("email") or "").lower()
            self._querying_emails.discard(email_key)
            if email_key:
                self._scan_cache[email_key] = entry
        if not self._is_alive:
            return
        self.model_selector.set_querying(bool(self._querying_emails))
        self.model_selector.refresh_models(self._get_selected_accounts(), self._scan_cache)

    def _on_save(self):
        selected = self._get_selected_accounts()
        if not selected:
            QMessageBox.warning(self, tr("model_rules.warning_title"), tr("model_rules.err_no_account"))
            return

        patterns = self.model_selector.get_selected_patterns()
        if not patterns:
            QMessageBox.warning(self, tr("model_rules.warning_title"), tr("model_rules.err_empty_pattern"))
            return
        match_type = self.combo_match_type.currentData() or "contains"
        if match_type == "regex":
            for pat in patterns:
                try:
                    re.compile(pat)
                except re.error:
                    QMessageBox.warning(
                        self, tr("model_rules.warning_title"),
                        tr("model_rules.err_invalid_regex", pattern=pat)
                    )
                    return

        self._result_rule = {
            "id": str(self._rule.get("id") or f"rule_{uuid.uuid4().hex[:8]}"),
            "name": self.edit_name.text().strip(),
            "pattern": patterns[0],
            "patterns": patterns,
            "match_type": match_type,
            "strategy": self.combo_strategy.currentData() or "priority",
            "fallback_to_global": self.chk_fallback.isChecked(),
            "accounts": selected,
            "account_id": selected[0]["id"],
            "account_email": selected[0]["email"],
            "enabled": self.chk_enabled.isChecked()
        }
        self.accept()

    def get_rule(self) -> dict:
        return dict(self._result_rule) if self._result_rule else {}

    def get_scan_cache(self) -> dict:
        return dict(self._scan_cache)
