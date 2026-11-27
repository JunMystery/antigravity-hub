# -*- coding: utf-8 -*-
"""
Hộp thoại xem danh sách chi tiết và sắp xếp nhanh tài khoản cho trang Quy tắc Model.
"""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt

from launcher_i18n import tr
from launcher_model_discovery import get_rule_patterns_py
from launcher_model_rule_formatter import (
    format_count_label, format_rule_strategy_cell, _rule_account_emails
)
from launcher_order_widget import OrderCellWidget


def bind_row_context_menu(widget: QWidget, on_menu_at) -> None:
    """Gắn menu chuột phải lên widget ô bảng và toàn bộ widget con bên trong."""
    if widget is None or not callable(on_menu_at):
        return
    for target in [widget] + list(widget.findChildren(QWidget)):
        target.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        target.customContextMenuRequested.connect(
            lambda pos, t=target, cb=on_menu_at: cb(t.mapToGlobal(pos))
        )


class ItemListDetailDialog(QDialog):
    """Hộp thoại hiển thị danh sách chỉ đọc kèm ô lọc nhanh và nút Đóng."""

    def __init__(self, title: str, items: list, subtitle: str = "", parent=None):
        q_parent = parent if isinstance(parent, QWidget) else None
        super().__init__(q_parent)
        self.setWindowTitle(title)
        self.setMinimumSize(420, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        if subtitle:
            self.lbl_subtitle = QLabel(subtitle)
            self.lbl_subtitle.setObjectName("lbl_muted")
            self.lbl_subtitle.setWordWrap(True)
            layout.addWidget(self.lbl_subtitle)
        else:
            self.lbl_subtitle = None

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText(tr("model_rules.dialog_search_placeholder"))
        self.edit_search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.edit_search)

        self.list_items = QListWidget()
        self.list_items.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        self.list_items.setAlternatingRowColors(True)
        for raw in (items or []):
            text = str(raw or "").strip()
            if text:
                self.list_items.addItem(QListWidgetItem(text))
        layout.addWidget(self.list_items, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.clicked.connect(self.accept)
        footer.addWidget(self.btn_close)
        layout.addLayout(footer)

    def _apply_filter(self, _text: str = ""):
        needle = self.edit_search.text().strip().lower()
        for idx in range(self.list_items.count()):
            item = self.list_items.item(idx)
            item.setHidden(bool(needle and needle not in item.text().lower()))


class RuleAccountsPriorityDialog(QDialog):
    """Hộp thoại xem và sửa nhanh thứ tự ưu tiên tài khoản đích trong một quy tắc."""

    def __init__(self, title: str, rule: dict, available_accounts: list, subtitle: str = "", on_reordered=None, parent=None):
        q_parent = parent if isinstance(parent, QWidget) else None
        super().__init__(q_parent)
        self._rule = rule if isinstance(rule, dict) else {}
        self._on_reordered = on_reordered
        self._acc_state = self._build_account_state_map(available_accounts)
        self._ensure_rule_accounts_list()

        self.setWindowTitle(title)
        self.setMinimumSize(480, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        if subtitle:
            self.lbl_subtitle = QLabel(subtitle)
            self.lbl_subtitle.setObjectName("lbl_muted")
            self.lbl_subtitle.setWordWrap(True)
            layout.addWidget(self.lbl_subtitle)
        else:
            self.lbl_subtitle = None

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText(tr("model_rules.dialog_search_placeholder"))
        self.edit_search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.edit_search)

        self.tbl_accounts = QTableWidget(0, 3)
        self.tbl_accounts.setHorizontalHeaderLabels([
            tr("model_rules.col_priority"), tr("model_rules.col_account"), tr("model_rules.col_status")
        ])
        self.tbl_accounts.verticalHeader().setVisible(False)
        self.tbl_accounts.verticalHeader().setDefaultSectionSize(42)
        self.tbl_accounts.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tbl_accounts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_accounts.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hdr = self.tbl_accounts.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_accounts.setColumnWidth(0, 72)
        layout.addWidget(self.tbl_accounts, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.clicked.connect(self.accept)
        footer.addWidget(self.btn_close)
        layout.addLayout(footer)

        self._render_rows()

    def _build_account_state_map(self, available_accounts: list) -> dict:
        acc_state = {}
        for acc in (available_accounts or []):
            enabled = acc.get("enabled", True) is not False
            if acc.get("email"):
                acc_state[str(acc["email"]).lower()] = enabled
            if acc.get("id"):
                acc_state[str(acc["id"]).lower()] = enabled
        return acc_state

    def _ensure_rule_accounts_list(self) -> list:
        accs = self._rule.get("accounts")
        if isinstance(accs, list) and accs:
            return accs
        if self._rule.get("account_email") or self._rule.get("account_id"):
            accs = [{"id": self._rule.get("account_id", ""), "email": self._rule.get("account_email", "")}]
        else:
            accs = []
        self._rule["accounts"] = accs
        return accs

    def _sync_primary_fields(self, accs: list):
        if accs:
            self._rule["account_id"] = str(accs[0].get("id") or "")
            self._rule["account_email"] = str(accs[0].get("email") or accs[0].get("id") or "")
        else:
            self._rule["account_id"] = ""
            self._rule["account_email"] = ""

    def _render_rows(self):
        accs = self._ensure_rule_accounts_list()
        total = len(accs)
        self.tbl_accounts.setUpdatesEnabled(False)
        try:
            self.tbl_accounts.setRowCount(0)
            for idx, ref in enumerate(accs):
                row = self.tbl_accounts.rowCount()
                self.tbl_accounts.insertRow(row)
                ord_widget = OrderCellWidget(
                    pid=str(idx),
                    order_num=idx + 1,
                    is_first=(idx == 0),
                    is_last=(idx == total - 1),
                    on_step_callback=lambda p, d: self.move_account(int(p), d),
                    on_edit_callback=lambda p, v: self.reorder_account_to(int(p), v),
                    parent=self.tbl_accounts
                )
                self.tbl_accounts.setCellWidget(row, 0, ord_widget)
                label = str(ref.get("email") or ref.get("id") or "").strip()
                self.tbl_accounts.setItem(row, 1, QTableWidgetItem(label))
                enabled = self._acc_state.get(label.lower(), True)
                status = tr("model_rules.status_active") if enabled else tr("model_rules.status_deactive")
                self.tbl_accounts.setItem(row, 2, QTableWidgetItem(status))
        finally:
            self.tbl_accounts.setUpdatesEnabled(True)
        self._apply_filter()

    def _apply_filter(self, _text: str = ""):
        needle = self.edit_search.text().strip().lower()
        for row in range(self.tbl_accounts.rowCount()):
            item = self.tbl_accounts.item(row, 1)
            text = item.text().lower() if item else ""
            self.tbl_accounts.setRowHidden(row, bool(needle and needle not in text))

    def move_account(self, idx: int, delta: int):
        accs = self._ensure_rule_accounts_list()
        target = idx + delta
        if 0 <= idx < len(accs) and 0 <= target < len(accs):
            accs[idx], accs[target] = accs[target], accs[idx]
            self._sync_primary_fields(accs)
            self._render_rows()
            if callable(self._on_reordered):
                self._on_reordered()

    def reorder_account_to(self, idx: int, new_order: int):
        accs = self._ensure_rule_accounts_list()
        if 0 <= idx < len(accs):
            item = accs.pop(idx)
            accs.insert(max(0, min(int(new_order) - 1, len(accs))), item)
            self._sync_primary_fields(accs)
            self._render_rows()
            if callable(self._on_reordered):
                self._on_reordered()


def _rule_display_name(rule: dict, pats: list) -> str:
    custom = str((rule or {}).get("name") or "").strip()
    if custom:
        return custom
    return pats[0] if pats else "-"


def open_available_models_dialog(parent, email: str, models: list):
    """Mở hộp thoại danh sách Model khả dụng (sắp xếp A-Z) cho một tài khoản."""
    sorted_models = sorted((str(m) for m in (models or []) if str(m).strip()), key=str.lower)
    count_lbl = format_count_label(len(sorted_models), "model_rules.count_models_one", "model_rules.count_models")
    dlg = ItemListDetailDialog(
        title=tr("model_rules.dialog_avail_models_title", email=email or "-"),
        items=sorted_models,
        subtitle=count_lbl,
        parent=parent
    )
    dlg.exec()


def open_rule_patterns_dialog(parent, rule: dict):
    """Mở hộp thoại danh sách Model Pattern (sắp xếp A-Z) của một quy tắc."""
    pats = sorted(get_rule_patterns_py(rule), key=str.lower)
    mtype = str((rule or {}).get("match_type") or "contains").lower()
    count_lbl = format_count_label(len(pats), "model_rules.count_models_one", "model_rules.count_models")
    dlg = ItemListDetailDialog(
        title=tr("model_rules.dialog_rule_models_title", name=_rule_display_name(rule, pats)),
        items=pats,
        subtitle=tr("model_rules.dialog_rule_models_sub", count=count_lbl, match_type=tr(f"model_rules.match_{mtype}")),
        parent=parent
    )
    dlg.exec()


def open_rule_accounts_dialog(parent, rule: dict, available_accounts: list, on_reordered=None):
    """Mở hộp thoại danh sách Tài khoản đích cho phép xem và sửa nhanh thứ tự ưu tiên."""
    pats = get_rule_patterns_py(rule)
    count = len(_rule_account_emails(rule or {}))
    count_lbl = format_count_label(count, "model_rules.count_accounts_one", "model_rules.count_accounts")
    strategy = format_rule_strategy_cell(rule)
    if (rule or {}).get("fallback_to_global"):
        strategy = f"{strategy} · {tr('model_rules.badge_fallback_short')}"
    dlg = RuleAccountsPriorityDialog(
        title=tr("model_rules.dialog_rule_accounts_title", name=_rule_display_name(rule, pats)),
        rule=rule,
        available_accounts=available_accounts,
        subtitle=tr("model_rules.dialog_rule_accounts_sub", count=count_lbl, strategy=strategy),
        on_reordered=on_reordered,
        parent=parent
    )
    dlg.exec()


def wrap_cell_widgets(widgets, center: bool = False, margins: tuple = (4, 2, 4, 2)) -> QWidget:
    """Đóng gói danh sách widget nhỏ nằm gọn trong một ô bảng."""
    box = QWidget()
    hl = QHBoxLayout(box)
    hl.setContentsMargins(*margins)
    hl.setSpacing(4)
    if center:
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    for w in widgets:
        hl.addWidget(w)
    return box


def make_detail_button(text: str, tooltip: str, slot) -> QPushButton:
    """Tạo nút bấm compact trong ô bảng để mở hộp thoại xem danh sách chi tiết."""
    btn = QPushButton(text)
    btn.setObjectName("btn_detail")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tooltip)
    btn.clicked.connect(slot)
    return btn


def make_action_button(text: str, slot, width=None, compact: bool = False) -> QPushButton:
    """Tạo nút thao tác chuẩn hóa kích thước cho các bảng Quy tắc Model."""
    btn = QPushButton(text)
    if width:
        btn.setFixedSize(width[0], width[1])
        btn.setStyleSheet("padding: 0px;")
    elif compact:
        btn.setStyleSheet("padding: 2px 8px;")
    btn.clicked.connect(slot)
    return btn
