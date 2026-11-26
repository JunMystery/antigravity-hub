# -*- coding: utf-8 -*-
"""
Hộp thoại xem danh sách chi tiết có tìm kiếm nhanh, dùng chung cho:
Available Models, Model Patterns và Target Accounts trên trang Model Rules.
"""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton
)
from PyQt6.QtCore import Qt

from launcher_i18n import tr
from launcher_model_discovery import get_rule_patterns_py
from launcher_model_rule_formatter import (
    format_count_label, format_rule_strategy_cell, build_rule_account_display_lines
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
            self.lbl_subtitle.setWordWrap(True)
            self.lbl_subtitle.setStyleSheet("color: #a6adc8; font-size: 12px;")
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


def open_rule_accounts_dialog(parent, rule: dict, available_accounts: list):
    """Mở hộp thoại danh sách Tài khoản đích theo đúng thứ tự ưu tiên của quy tắc."""
    pats = get_rule_patterns_py(rule)
    lines = build_rule_account_display_lines(rule, available_accounts)
    count_lbl = format_count_label(len(lines), "model_rules.count_accounts_one", "model_rules.count_accounts")
    strategy = format_rule_strategy_cell(rule)
    if (rule or {}).get("fallback_to_global"):
        strategy = f"{strategy} · {tr('model_rules.badge_fallback_short')}"
    dlg = ItemListDetailDialog(
        title=tr("model_rules.dialog_rule_accounts_title", name=_rule_display_name(rule, pats)),
        items=lines,
        subtitle=tr("model_rules.dialog_rule_accounts_sub", count=count_lbl, strategy=strategy),
        parent=parent
    )
    dlg.exec()


def wrap_cell_widgets(widgets, center: bool = False) -> QWidget:
    """Đóng gói danh sách widget nhỏ nằm gọn trong một ô bảng."""
    box = QWidget()
    hl = QHBoxLayout(box)
    hl.setContentsMargins(4, 2, 4, 2)
    hl.setSpacing(4)
    if center:
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    for w in widgets:
        hl.addWidget(w)
    return box


def make_detail_button(text: str, tooltip: str, slot) -> QPushButton:
    """Tạo nút bấm compact trong ô bảng để mở hộp thoại xem danh sách chi tiết."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tooltip)
    btn.setStyleSheet(
        "QPushButton { text-align: left; padding: 3px 10px; background-color: #24273a; "
        "border: 1px solid #363a4f; border-radius: 5px; color: #cdd6f4; } "
        "QPushButton:hover { background-color: #313244; border-color: #89b4fa; }"
    )
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
