# -*- coding: utf-8 -*-
"""
View Quản lý Tài khoản (Accounts View) cho Antigravity Launcher.
Bao gồm bảng danh sách tài khoản, hiển thị Quota, thêm/xóa tài khoản,
thay đổi thứ tự ưu tiên (Reordering) và cấu hình xoay vòng (Round-Robin).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QFrame
)
from PyQt6.QtCore import Qt

from launcher_i18n import tr
from launcher_treeview import setup_treeview, populate_treeview, update_treeview_headers

class AccountsView(QWidget):
    """View chuyên trách quản lý hồ sơ tài khoản và hạn mức sử dụng Quota."""

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win
        self.setObjectName("accounts_view")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # 1. Action Bar: Thêm, Xóa, Tự động Quota, Quét tất cả
        act_bar = QHBoxLayout()
        act_bar.setSpacing(8)

        self.btn_add = QPushButton(tr("btn.add").replace("_", "&"))
        self.btn_add.clicked.connect(self.win.on_add_account)
        act_bar.addWidget(self.btn_add)

        self.btn_del = QPushButton(tr("btn.delete").replace("_", "&"))
        self.btn_del.clicked.connect(self.win.on_delete_account)
        act_bar.addWidget(self.btn_del)

        act_bar.addStretch(1)

        self.btn_auto = QPushButton()
        self.btn_auto.setFixedHeight(28)
        self.btn_auto.clicked.connect(self.win.on_toggle_auto_quota)
        act_bar.addWidget(self.btn_auto)

        self.btn_refresh_all = QPushButton("⟳")
        self.btn_refresh_all.setObjectName("btn_refresh_all")
        self.btn_refresh_all.setToolTip(tr("tooltip.refresh_all"))
        self.btn_refresh_all.setFixedSize(36, 28)
        self.btn_refresh_all.setStyleSheet("padding: 0px; font-size: 13px;")
        self.btn_refresh_all.clicked.connect(self.win.on_refresh_all_quota)
        act_bar.addWidget(self.btn_refresh_all)

        layout.addLayout(act_bar)

        # 2. Bảng danh sách tài khoản (Treeview / Table container)
        self.table_container = QVBoxLayout()
        layout.addLayout(self.table_container, 1)

        # 3. Dòng thông tin tóm tắt
        self.lbl_info = QLabel()
        layout.addWidget(self.lbl_info)

        # 4. Thanh cài đặt xoay vòng Round-Robin
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        opt_bar = QHBoxLayout()
        self.rr_info = QLabel(tr("opt.mode"))
        opt_bar.addWidget(self.rr_info)
        opt_bar.addStretch(1)

        self.spin_lbl = QLabel(tr("opt.req_per_acc"))
        opt_bar.addWidget(self.spin_lbl)

        cur_reqs = self.win.data.get("settings", {}).get("requests_per_account", 1)
        self.spin_reqs = QSpinBox()
        self.spin_reqs.setRange(1, 500)
        self.spin_reqs.setValue(cur_reqs)
        self.spin_reqs.valueChanged.connect(self.win.on_spin_changed)
        opt_bar.addWidget(self.spin_reqs)

        layout.addLayout(opt_bar)

        # Gán tham chiếu đồng bộ sang Window để tương thích tuyệt đối với các hàm runner
        self.win.table_container = self.table_container
        self.win.btn_add = self.btn_add
        self.win.btn_del = self.btn_del
        self.win.btn_auto = self.btn_auto
        self.win.btn_refresh_all = self.btn_refresh_all
        self.win.lbl_info = self.lbl_info
        self.win.spin_reqs = self.spin_reqs
        self.win.rr_info = self.rr_info
        self.win.spin_lbl = self.spin_lbl

        # Khởi tạo bảng tài khoản
        self.treeview = setup_treeview(self.win)
        self.win.treeview = self.treeview

    def refresh_list(self, select_id=None):
        """Làm mới dữ liệu hiển thị trên bảng tài khoản."""
        populate_treeview(self.win, select_id=select_id)

    def retranslate_ui(self):
        """Cập nhật ngôn ngữ các nhãn trong view."""
        self.btn_add.setText(tr("btn.add").replace("_", "&"))
        self.btn_del.setText(tr("btn.delete").replace("_", "&"))
        self.btn_refresh_all.setToolTip(tr("tooltip.refresh_all"))
        self.rr_info.setText(tr("opt.mode"))
        self.spin_lbl.setText(tr("opt.req_per_acc"))
        update_treeview_headers(self.win)
