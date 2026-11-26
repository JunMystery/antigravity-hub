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
    QCheckBox, QPushButton, QSpinBox, QMessageBox
)
from PyQt6.QtCore import pyqtSignal

from launcher_i18n import tr
from launcher_model_discovery import (
    collect_available_accounts, fetch_all_accounts_models, get_rule_patterns_py
)
from launcher_model_selector import MultiModelSelector
from launcher_rule_account_picker import RuleAccountPicker


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

        self.row_rr_reqs = QWidget()
        rr_layout = QHBoxLayout(self.row_rr_reqs)
        rr_layout.setContentsMargins(0, 0, 0, 0)
        rr_layout.setSpacing(8)
        self.spin_req_per_account = QSpinBox()
        self.spin_req_per_account.setRange(0, 500)
        self.spin_req_per_account.setSpecialValueText(tr("model_rules.inherit_global"))
        try:
            saved_reqs = max(0, int(self._rule.get("requests_per_account") or 0))
        except (TypeError, ValueError):
            saved_reqs = 0
        self.spin_req_per_account.setValue(saved_reqs)
        rr_layout.addWidget(QLabel(tr("model_rules.req_per_account")))
        rr_layout.addWidget(self.spin_req_per_account)
        rr_layout.addStretch(1)
        layout.addWidget(self.row_rr_reqs)
        self.combo_strategy.currentIndexChanged.connect(self._sync_strategy_controls)
        self._sync_strategy_controls()

        self.account_picker = RuleAccountPicker(self._accounts, self._rule, preset_account, parent=self)
        self.list_accounts = self.account_picker.list_accounts
        self.account_picker.accounts_changed.connect(self._on_accounts_changed)
        layout.addWidget(self.account_picker, 1)

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

    def _sync_strategy_controls(self):
        self.row_rr_reqs.setVisible(self.combo_strategy.currentData() == "round_robin")

    def _get_selected_accounts(self) -> list:
        return self.account_picker.get_selected_accounts()

    def _select_accounts(self, mode: str):
        self.account_picker.select_accounts(mode)

    def _move_account(self, delta: int):
        self.account_picker.move_account(delta)

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

        strategy = self.combo_strategy.currentData() or "priority"
        req_per_account = int(self.spin_req_per_account.value()) if strategy == "round_robin" else 0
        self._result_rule = {
            "id": str(self._rule.get("id") or f"rule_{uuid.uuid4().hex[:8]}"),
            "name": self.edit_name.text().strip(),
            "pattern": patterns[0],
            "patterns": patterns,
            "match_type": match_type,
            "strategy": strategy,
            "requests_per_account": req_per_account,
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
