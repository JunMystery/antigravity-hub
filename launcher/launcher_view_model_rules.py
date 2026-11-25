# -*- coding: utf-8 -*-
"""
Trang quản lý Quy tắc Model chuyên sâu (ModelRulesView) trên Sidebar.
Hỗ trợ sắp xếp thứ tự ưu tiên, gán nhiều tài khoản (kể cả Deactive), kiểm thử nhanh,
và quét song song model khả dụng trên toàn bộ tài khoản.
"""

import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from launcher_i18n import tr
from launcher_storage import save_data
from launcher_monitor import send_proxy_cmd
from launcher_model_discovery import (
    collect_available_accounts, discover_models_from_logs,
    fetch_all_accounts_models, get_rule_patterns_py, simulate_model_route
)
from launcher_model_rule_editor import ModelRuleEditorDialog


def _wrap_cell_widgets(widgets, center=False):
    box = QWidget()
    hl = QHBoxLayout(box)
    hl.setContentsMargins(4, 2, 4, 2)
    hl.setSpacing(4)
    if center:
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    for w in widgets:
        hl.addWidget(w)
    return box


def _build_table(col_modes, col_widths=None):
    tbl = QTableWidget(0, len(col_modes))
    tbl.verticalHeader().setVisible(False)
    tbl.verticalHeader().setDefaultSectionSize(44)
    tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    hdr = tbl.horizontalHeader()
    for col, mode in enumerate(col_modes):
        hdr.setSectionResizeMode(col, mode)
    for col, width in (col_widths or {}).items():
        tbl.setColumnWidth(col, width)
    return tbl


def _make_btn(text, slot, width=None, compact=False):
    btn = QPushButton(text)
    if width:
        btn.setFixedSize(width[0], width[1])
        btn.setStyleSheet("padding: 0px;")
    elif compact:
        btn.setStyleSheet("padding: 2px 8px;")
    btn.clicked.connect(slot)
    return btn


class ModelRulesView(QWidget):
    """Màn hình chính cấu hình và kiểm thử quy tắc định tuyến theo Model."""

    scan_completed = pyqtSignal(list)

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win
        self.setObjectName("model_rules_view")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self._scanned_accounts = []
        self._scan_cache = {}
        self._is_scanning = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.btn_scan_all = _make_btn("", self.start_scan_all_accounts)
        self.btn_add_rule = _make_btn("", lambda: self.open_rule_editor())
        self.btn_add_rule.setObjectName("btn_primary")
        header.addWidget(self.lbl_title)
        header.addStretch(1)
        header.addWidget(self.btn_scan_all)
        header.addWidget(self.btn_add_rule)
        layout.addLayout(header)

        tester_row = QHBoxLayout()
        self.lbl_test_title = QLabel()
        self.combo_test_model = QComboBox()
        self.combo_test_model.setEditable(True)
        self.combo_test_model.lineEdit().returnPressed.connect(self.run_quick_test)
        self.btn_test_route = _make_btn("", self.run_quick_test)
        tester_row.addWidget(self.lbl_test_title)
        tester_row.addWidget(self.combo_test_model, 1)
        tester_row.addWidget(self.btn_test_route)
        layout.addLayout(tester_row)

        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setWordWrap(True)
        layout.addWidget(self.lbl_test_result)

        self.tbl_rules = _build_table((
            QHeaderView.ResizeMode.Fixed, QHeaderView.ResizeMode.Fixed,
            QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.Fixed,
        ), {0: 74, 1: 56, 6: 140})
        layout.addWidget(self.tbl_rules, 2)

        self.lbl_scan_title = QLabel()
        self.lbl_scan_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.lbl_scan_title)

        self.tbl_scan = _build_table((
            QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.Fixed,
        ), {3: 120})
        layout.addWidget(self.tbl_scan, 1)

        self.scan_completed.connect(self._on_scan_finished)
        self.retranslate_ui()

    def _get_rules(self) -> list:
        settings = self.win.data.setdefault("settings", {})
        rules = settings.get("model_rules")
        if not isinstance(rules, list):
            rules = []
            settings["model_rules"] = rules
        return rules

    def _persist_and_reload(self):
        save_data(self.win.data)
        send_proxy_cmd(self.win, "reload")
        self.refresh_view()

    def _collect_all_known_models(self) -> list:
        seen = set()
        merged = []
        for entry in self._scanned_accounts:
            for m in entry.get("models", []):
                if m and m.lower() not in seen:
                    seen.add(m.lower())
                    merged.append(m)
        for m in discover_models_from_logs():
            if m and m.lower() not in seen:
                seen.add(m.lower())
                merged.append(m)
        return merged

    def refresh_view(self):
        rules = self._get_rules()
        self.tbl_rules.setRowCount(0)
        for idx, rule in enumerate(rules):
            row = self.tbl_rules.rowCount()
            self.tbl_rules.insertRow(row)

            btn_up = _make_btn("▲", lambda _, i=idx: self.move_rule(i, -1), (26, 24))
            btn_up.setEnabled(idx > 0)
            btn_dn = _make_btn("▼", lambda _, i=idx: self.move_rule(i, 1), (26, 24))
            btn_dn.setEnabled(idx < len(rules) - 1)
            self.tbl_rules.setCellWidget(row, 0, _wrap_cell_widgets([btn_up, btn_dn]))

            chk = QCheckBox()
            chk.setChecked(rule.get("enabled", True) is not False)
            chk.toggled.connect(lambda state, i=idx: self.toggle_rule(i, state))
            self.tbl_rules.setCellWidget(row, 1, _wrap_cell_widgets([chk], center=True))

            pats = get_rule_patterns_py(rule)
            pat_sum = ", ".join(pats[:2]) + (f" (+{len(pats) - 2})" if len(pats) > 2 else "")
            custom_name = str(rule.get("name") or "").strip()
            auto_legacy = f"{pats[0]} (+{len(pats) - 1})" if len(pats) > 1 else (pats[0] if pats else "")
            show_pat = pat_sum if (not custom_name or custom_name in (pat_sum, auto_legacy)) else f"{custom_name} ({pat_sum})"
            pat_item = QTableWidgetItem(show_pat)
            pat_item.setToolTip((f"{custom_name}\n" if custom_name else "") + "\n".join(pats))
            self.tbl_rules.setItem(row, 2, pat_item)
            mtype = str(rule.get("match_type") or "contains").lower()
            self.tbl_rules.setItem(row, 3, QTableWidgetItem(tr(f"model_rules.match_{mtype}")))
            strat = str(rule.get("strategy") or "priority").lower()
            self.tbl_rules.setItem(row, 4, QTableWidgetItem(tr("model_rules.strategy_round_robin" if strat == "round_robin" else "model_rules.strategy_priority")))
            accs = rule.get("accounts") or ([{"email": rule.get("account_email", "")}] if rule.get("account_email") else [])
            acc_emails = [a.get("email") or a.get("id") or "" for a in accs if a.get("email") or a.get("id")]
            acc_sum = ", ".join(acc_emails[:2]) + (f" (+{len(acc_emails) - 2})" if len(acc_emails) > 2 else "")
            fb_suffix = f" | {tr('model_rules.badge_fallback')}" if rule.get("fallback_to_global") else ""
            acc_item = QTableWidgetItem(f"{acc_sum}{fb_suffix}")
            acc_item.setToolTip(", ".join(acc_emails))
            self.tbl_rules.setItem(row, 5, acc_item)

            btn_edit = _make_btn(tr("model_rules.btn_edit"), lambda _, i=idx: self.open_rule_editor(edit_idx=i), compact=True)
            btn_del = _make_btn(tr("btn.delete").replace("_", ""), lambda _, i=idx: self.delete_rule(i), compact=True)
            self.tbl_rules.setCellWidget(row, 6, _wrap_cell_widgets([btn_edit, btn_del]))

        cur_txt = self.combo_test_model.currentText()
        self.combo_test_model.blockSignals(True)
        self.combo_test_model.clear()
        self.combo_test_model.addItems(self._collect_all_known_models())
        self.combo_test_model.setCurrentText(cur_txt)
        self.combo_test_model.blockSignals(False)

    def add_or_update_rule(self, rule: dict, edit_idx: int = None):
        rules = self._get_rules()
        if edit_idx is not None and 0 <= edit_idx < len(rules):
            rules[edit_idx] = rule
        else:
            rules.append(rule)
        self._persist_and_reload()

    def move_rule(self, idx: int, delta: int):
        rules, target = self._get_rules(), idx + delta
        if 0 <= idx < len(rules) and 0 <= target < len(rules):
            rules[idx], rules[target] = rules[target], rules[idx]
            self._persist_and_reload()

    def toggle_rule(self, idx: int, checked: bool):
        rules = self._get_rules()
        if 0 <= idx < len(rules):
            rules[idx]["enabled"] = bool(checked)
            self._persist_and_reload()

    def delete_rule(self, idx: int):
        rules = self._get_rules()
        if 0 <= idx < len(rules):
            rules.pop(idx)
            self._persist_and_reload()

    def open_rule_editor(self, edit_idx: int = None, preset_model: str = "", preset_models: list = None, preset_account: dict = None):
        rules = self._get_rules()
        existing = rules[edit_idx] if (edit_idx is not None and 0 <= edit_idx < len(rules)) else None
        dlg = ModelRuleEditorDialog(self.win, self, rule=existing, preset_model=preset_model, preset_models=preset_models, extra_models=self._collect_all_known_models(), preset_account=preset_account, scanned_cache=self._scan_cache)
        accepted = bool(dlg.exec())
        self._scan_cache.update(dlg.get_scan_cache())
        if accepted and dlg.get_rule():
            self.add_or_update_rule(dlg.get_rule(), edit_idx=edit_idx)

    def run_quick_test(self, model_text: str = None):
        target = (model_text if isinstance(model_text, str) else self.combo_test_model.currentText()).strip()
        if not target:
            self.lbl_test_result.setText("")
            return
        res = simulate_model_route(target, self._get_rules(), collect_available_accounts(self.win.data))
        accs = ", ".join(a.get("email", "") for a in res.get("accounts", [])) or tr("model_rules.no_target")
        msg = (
            tr("model_rules.test_matched", rule=res.get("rule_name", ""), match_type=tr(f"model_rules.match_{res.get('match_type', 'contains')}"), accounts=accs)
            if res.get("matched") else tr("model_rules.test_unmatched", accounts=accs)
        )
        self.lbl_test_result.setText(msg)
        return res

    def start_scan_all_accounts(self):
        if self._is_scanning:
            return
        accounts = collect_available_accounts(self.win.data)
        self._is_scanning = True
        self.btn_scan_all.setEnabled(False)
        self.btn_scan_all.setText(tr("model_rules.scanning"))
        threading.Thread(target=lambda: self.scan_completed.emit(fetch_all_accounts_models(accounts)), daemon=True).start()

    def _on_scan_finished(self, results: list):
        self._is_scanning = False
        self._scanned_accounts = results or []
        for entry in self._scanned_accounts:
            if entry.get("email"):
                self._scan_cache[str(entry["email"]).lower()] = entry
        self.btn_scan_all.setEnabled(True)
        self.btn_scan_all.setText(tr("model_rules.btn_scan_all"))
        self.tbl_scan.setRowCount(0)
        for entry in self._scanned_accounts:
            row = self.tbl_scan.rowCount()
            self.tbl_scan.insertRow(row)
            self.tbl_scan.setItem(row, 0, QTableWidgetItem(entry.get("email", "")))
            self.tbl_scan.setItem(row, 1, QTableWidgetItem(tr("model_rules.status_active") if entry.get("enabled", True) else tr("model_rules.status_deactive")))
            models = entry.get("models") or []
            self.tbl_scan.setItem(row, 2, QTableWidgetItem(", ".join(models) if models else (entry.get("error") or tr("model_rules.scan_empty"))))
            acc_ref = {"id": entry.get("id", ""), "email": entry.get("email", "")}
            btn_make = _make_btn(tr("model_rules.btn_create_from_scan"), lambda _, ms=list(models), acc=acc_ref: self.open_rule_editor(preset_models=ms, preset_account=acc), compact=True)
            btn_make.setEnabled(bool(models or acc_ref["email"]))
            self.tbl_scan.setCellWidget(row, 3, btn_make)
        self.refresh_view()

    def retranslate_ui(self):
        self.lbl_title.setText(tr("model_rules.page_title"))
        self.btn_scan_all.setText(tr("model_rules.scanning") if self._is_scanning else tr("model_rules.btn_scan_all"))
        self.btn_add_rule.setText(tr("model_rules.btn_add"))
        self.lbl_test_title.setText(tr("model_rules.test_label"))
        self.combo_test_model.lineEdit().setPlaceholderText(tr("model_rules.test_placeholder"))
        self.btn_test_route.setText(tr("model_rules.btn_test"))
        self.lbl_scan_title.setText(tr("model_rules.scan_title"))
        self.tbl_rules.setHorizontalHeaderLabels([tr("model_rules.col_priority"), tr("model_rules.enabled"), tr("model_rules.col_pattern"), tr("model_rules.col_match_type"), tr("model_rules.col_strategy"), tr("model_rules.col_account"), tr("model_rules.col_actions")])
        self.tbl_scan.setHorizontalHeaderLabels([tr("model_rules.col_account"), tr("monitor.col_status"), tr("model_rules.col_models"), tr("model_rules.col_actions")])
        self.refresh_view()
