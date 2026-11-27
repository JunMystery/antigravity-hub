# -*- coding: utf-8 -*-
"""
Trang quản lý Quy tắc Model chuyên sâu (ModelRulesView) trên Sidebar.
Hỗ trợ sắp xếp thứ tự ưu tiên, gán nhiều tài khoản (kể cả Deactive), kiểm thử nhanh,
và quét song song model khả dụng trên toàn bộ tài khoản.
"""

import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal

from launcher_i18n import tr
from launcher_storage import save_data
from launcher_monitor import send_proxy_cmd
from launcher_toggle_switch import ToggleSwitch
from launcher_order_widget import OrderCellWidget
from launcher_model_discovery import (
    collect_available_accounts, discover_models_from_logs,
    fetch_all_accounts_models, simulate_model_route
)
from launcher_model_rule_editor import ModelRuleEditorDialog
from launcher_model_rule_formatter import (
    format_count_label, format_rule_pattern_cell,
    format_rule_strategy_cell, format_rule_accounts_cell
)
from launcher_item_list_dialog import (
    make_action_button, make_detail_button, wrap_cell_widgets, bind_row_context_menu,
    open_available_models_dialog, open_rule_patterns_dialog, open_rule_accounts_dialog
)


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
        self.btn_scan_all = make_action_button("", self.start_scan_all_accounts)
        self.btn_add_rule = make_action_button("", lambda: self.open_rule_editor())
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
        self.btn_test_route = make_action_button("", self.run_quick_test)
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
            QHeaderView.ResizeMode.Stretch,
        ), {0: 72, 1: 56})
        self.tbl_rules.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_rules.viewport().customContextMenuRequested.connect(self._show_rule_context_menu)
        layout.addWidget(self.tbl_rules, 2)

        self.lbl_scan_title = QLabel()
        self.lbl_scan_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.lbl_scan_title)

        self.tbl_scan = _build_table((
            QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.Fixed,
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
        return sorted(merged, key=str.lower)

    def refresh_view(self):
        rules = self._get_rules()
        self.tbl_rules.setRowCount(0)
        for idx, rule in enumerate(rules):
            row = self.tbl_rules.rowCount()
            self.tbl_rules.insertRow(row)

            ord_widget = OrderCellWidget(
                pid=str(idx),
                order_num=idx + 1,
                is_first=(idx == 0),
                is_last=(idx == len(rules) - 1),
                on_step_callback=lambda p, d: self.move_rule(int(p), d),
                on_edit_callback=lambda p, v: self.reorder_rule_to(int(p), v),
                parent=self.tbl_rules
            )
            self.tbl_rules.setCellWidget(row, 0, ord_widget)

            sw = ToggleSwitch(checked=rule.get("enabled", True) is not False)
            sw.toggled.connect(lambda state, i=idx: self.toggle_rule(i, state))
            sw_wrap = wrap_cell_widgets([sw], center=True, margins=(4, 0, 4, 0))
            self.tbl_rules.setCellWidget(row, 1, sw_wrap)

            pat_text, pat_tip = format_rule_pattern_cell(rule)
            btn_pat = make_detail_button(pat_text, pat_tip, lambda _, r=rule: open_rule_patterns_dialog(self, r))
            pat_wrap = wrap_cell_widgets([btn_pat])
            self.tbl_rules.setCellWidget(row, 2, pat_wrap)
            self.tbl_rules.setItem(row, 3, QTableWidgetItem(format_rule_strategy_cell(rule, compact=True)))
            acc_text, acc_tip = format_rule_accounts_cell(rule)
            btn_acc = make_detail_button(
                acc_text, acc_tip,
                lambda _, r=rule: open_rule_accounts_dialog(
                    self, r, collect_available_accounts(self.win.data), on_reordered=self._persist_and_reload
                )
            )
            acc_wrap = wrap_cell_widgets([btn_acc])
            self.tbl_rules.setCellWidget(row, 4, acc_wrap)
            for cell_w in (ord_widget, sw_wrap, pat_wrap, acc_wrap):
                bind_row_context_menu(cell_w, lambda gpos, r=row: self._open_rule_menu_at(r, gpos))

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

    def reorder_rule_to(self, idx: int, new_order: int):
        rules = self._get_rules()
        if 0 <= idx < len(rules):
            target = rules.pop(idx)
            rules.insert(max(0, min(int(new_order) - 1, len(rules))), target)
            self._persist_and_reload()

    def toggle_rule(self, idx: int, checked: bool):
        rules = self._get_rules()
        if 0 <= idx < len(rules):
            rules[idx]["enabled"] = bool(checked)
            self._persist_and_reload()

    def _build_rule_context_menu(self, idx: int) -> QMenu:
        menu = QMenu(self)
        act_edit = menu.addAction(tr("model_rules.btn_edit"))
        act_edit.triggered.connect(lambda: self.open_rule_editor(edit_idx=idx))
        act_del = menu.addAction(tr("btn.delete").replace("_", ""))
        act_del.triggered.connect(lambda: self.delete_rule(idx))
        return menu

    def _open_rule_menu_at(self, row: int, global_pos):
        if 0 <= row < len(self._get_rules()):
            self._build_rule_context_menu(row).exec(global_pos)

    def _show_rule_context_menu(self, pos):
        self._open_rule_menu_at(self.tbl_rules.rowAt(pos.y()), self.tbl_rules.viewport().mapToGlobal(pos))

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
        self._render_scan_table()
        self.refresh_view()

    def _render_scan_table(self):
        self.tbl_scan.setRowCount(0)
        for entry in self._scanned_accounts:
            row = self.tbl_scan.rowCount()
            self.tbl_scan.insertRow(row)
            self.tbl_scan.setItem(row, 0, QTableWidgetItem(entry.get("email", "")))
            self.tbl_scan.setItem(row, 1, QTableWidgetItem(tr("model_rules.status_active") if entry.get("enabled", True) else tr("model_rules.status_deactive")))
            models = sorted(entry.get("models") or [], key=str.lower)
            entry["models"] = models
            if models:
                cnt_txt = format_count_label(len(models), "model_rules.count_models_one", "model_rules.count_models")
                btn_models = make_detail_button(
                    cnt_txt, tr("model_rules.click_for_details"),
                    lambda _, em=entry.get("email", ""), ms=list(models): open_available_models_dialog(self, em, ms)
                )
                self.tbl_scan.setCellWidget(row, 2, wrap_cell_widgets([btn_models]))
            else:
                self.tbl_scan.setItem(row, 2, QTableWidgetItem(entry.get("error") or tr("model_rules.scan_empty")))
            acc_ref = {"id": entry.get("id", ""), "email": entry.get("email", "")}
            btn_make = make_action_button(tr("model_rules.btn_create_from_scan"), lambda _, ms=list(models), acc=acc_ref: self.open_rule_editor(preset_models=ms, preset_account=acc), compact=True)
            btn_make.setEnabled(bool(models or acc_ref["email"]))
            self.tbl_scan.setCellWidget(row, 3, btn_make)

    def retranslate_ui(self):
        self.lbl_title.setText(tr("model_rules.page_title"))
        self.btn_scan_all.setText(tr("model_rules.scanning") if self._is_scanning else tr("model_rules.btn_scan_all"))
        self.btn_add_rule.setText(tr("model_rules.btn_add"))
        self.lbl_test_title.setText(tr("model_rules.test_label"))
        self.combo_test_model.lineEdit().setPlaceholderText(tr("model_rules.test_placeholder"))
        self.btn_test_route.setText(tr("model_rules.btn_test"))
        self.lbl_scan_title.setText(tr("model_rules.scan_title"))
        self.tbl_rules.setHorizontalHeaderLabels([tr("model_rules.col_priority"), tr("model_rules.enabled"), tr("model_rules.col_pattern"), tr("model_rules.col_strategy"), tr("model_rules.col_account")])
        self.tbl_scan.setHorizontalHeaderLabels([tr("model_rules.col_account"), tr("monitor.col_status"), tr("model_rules.col_models"), tr("model_rules.col_actions")])
        if self._scanned_accounts:
            self._render_scan_table()
        self.refresh_view()
