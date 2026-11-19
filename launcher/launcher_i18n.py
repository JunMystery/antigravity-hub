# -*- coding: utf-8 -*-
"""
Module quốc tế hóa (i18n) cho Antigravity Launcher.
Hỗ trợ nạp từ điển JSON mở rộng, chuyển đổi ngôn ngữ EN / VI và thế chỗ placeholder an toàn.
"""

import os
import json

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")

SUPPORTED_LANGUAGES = [
    ("vi", "Tiếng Việt"),
    ("en", "English")
]

_TRANSLATIONS = {}
_CURRENT_LANG = "vi"

# Fallback nhúng an toàn phòng khi tệp JSON bị xóa hoặc lỗi truy cập
_FALLBACK_DEFAULTS = {
    "vi": {
        "app.title": "Antigravity Hub",
        "app.subtitle": "Quản lý Profile & Quota",
        "btn.add": "_Thêm",
        "btn.delete": "_Xóa",
        "btn.use_account": "Chọn dùng",
        "btn.launch": "Khởi động",
        "col.order": "TT",
        "col.active": "Active",
        "col.email": "Email",
        "col.5h": "5h",
        "col.weekly": "Tuần",
        "col.argon": "Argon (Tuần)",
        "col.quota": "Quota",
        "col.time": "Thời gian",
        "col.details": "Chi tiết Request",
        "nav.dashboard": "Dashboard",
        "nav.accounts": "Tài khoản",
        "nav.settings": "Cài đặt",
        "monitor.col_status": "Trạng thái",
        "monitor.col_acc": "Tài khoản",
        "monitor.col_turn": "Lượt",
        "monitor.col_total": "Tổng",
        "info.summary": "Tài khoản: <b>{enabled}/{total}</b> Active | <b>{reqs}</b> req/acc",
        "info.empty": "<i>Chưa có tài khoản. Nhấn <b>+ Thêm</b>.</i>",
        "opt.mode": "<b>Chế độ:</b> Round Robin (Port 20130)",
        "opt.mode_fixed": "<b>Chế độ:</b> Cố định 1 tài khoản (Tắt xoay vòng)",
        "opt.req_per_acc": "Req / acc:",
        "tooltip.auto_on": "Tự động làm mới (5 phút): Đang BẬT - Nhấp để TẮT",
        "tooltip.auto_off": "Tự động làm mới (5 phút): Đang TẮT - Nhấp để BẬT",
        "tooltip.toggle_round_robin_on": "Tự động xoay vòng Round Robin: Đang BẬT - Nhấp để TẮT (cố định tài khoản)",
        "tooltip.toggle_round_robin_off": "Tự động xoay vòng Round Robin: Đang TẮT - Nhấp để BẬT lại",
        "tooltip.use_account": "Chuyển Proxy và profile khởi chạy sang tài khoản đang chọn",
        "tooltip.refresh_all": "Làm mới Quota toàn bộ tài khoản (Cooldown 30s)",
        "dashboard.active_account_label": "Tài khoản dùng:",
        "dashboard.no_active_account": "Chưa có tài khoản",
        "msg.account_switched": "<b><span color='#89b4fa'>[CHUYỂN]</span></b> Đã chọn dùng tài khoản <b>{label}</b>.",
        "dialog.delete_title": "Xác nhận xóa tài khoản '{label}'?",
        "dialog.delete_warning": "Cảnh báo: Hành động này sẽ xóa hoàn toàn profile, thu hồi token và xóa dữ liệu trên đĩa.\n\nBạn có chắc chắn muốn xóa không?",
        "dialog.deleted_msg": "<b><span color='#e74c3c'>[ĐÃ XÓA]</span></b> Đã xóa hoàn toàn tài khoản <b>{label}</b> và dữ liệu."
    },
    "en": {
        "app.title": "Antigravity Hub",
        "app.subtitle": "Profile & Quota Manager",
        "btn.add": "_Add",
        "btn.delete": "_Delete",
        "btn.use_account": "Use Account",
        "btn.launch": "Launch",
        "col.order": "No.",
        "col.active": "Active",
        "col.email": "Email",
        "col.5h": "5h",
        "col.weekly": "Weekly",
        "col.argon": "Argon (Weekly)",
        "col.quota": "Quota",
        "col.time": "Time",
        "col.details": "Request Details",
        "nav.dashboard": "Dashboard",
        "nav.accounts": "Accounts",
        "nav.settings": "Settings",
        "monitor.col_status": "Status",
        "monitor.col_acc": "Account",
        "monitor.col_turn": "Turn",
        "monitor.col_total": "Total",
        "info.summary": "Accounts: <b>{enabled}/{total}</b> Active | <b>{reqs}</b> req/acc",
        "info.empty": "<i>No accounts. Click <b>+ Add</b>.</i>",
        "opt.mode": "<b>Mode:</b> Round Robin (Port 20130)",
        "opt.mode_fixed": "<b>Mode:</b> Fixed Single Account (Rotation Off)",
        "opt.req_per_acc": "Req / acc:",
        "tooltip.auto_on": "Auto-refresh (5 min): ON - Click to TURN OFF",
        "tooltip.auto_off": "Auto-refresh (5 min): OFF - Click to TURN ON",
        "tooltip.toggle_round_robin_on": "Round Robin auto-rotation: ON - Click to TURN OFF (pin account)",
        "tooltip.toggle_round_robin_off": "Round Robin auto-rotation: OFF - Click to TURN ON",
        "tooltip.use_account": "Switch Proxy and launch profile to the selected account",
        "tooltip.refresh_all": "Refresh all accounts Quota (Cooldown 30s)",
        "dashboard.active_account_label": "Active Account:",
        "dashboard.no_active_account": "No accounts available",
        "msg.account_switched": "<b><span color='#89b4fa'>[SWITCHED]</span></b> Switched active account to <b>{label}</b>.",
        "dialog.delete_title": "Delete account '{label}'?",
        "dialog.delete_warning": "Warning: This permanently deletes profile, token credentials, and disk data.\n\nAre you sure?",
        "dialog.deleted_msg": "<b><span color='#e74c3c'>[DELETED]</span></b> Account <b>{label}</b> has been completely removed."
    }
}

def load_locales():
    """Tải toàn bộ các tệp JSON trong thư mục locales/ vào bộ nhớ cache."""
    global _TRANSLATIONS
    _TRANSLATIONS = {}
    for code, _ in SUPPORTED_LANGUAGES:
        _TRANSLATIONS[code] = dict(_FALLBACK_DEFAULTS.get(code, {}))

    if os.path.exists(LOCALES_DIR) and os.path.isdir(LOCALES_DIR):
        for fname in os.listdir(LOCALES_DIR):
            if fname.endswith(".json"):
                lang_code = os.path.splitext(fname)[0].lower()
                fpath = os.path.join(LOCALES_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    _TRANSLATIONS.setdefault(lang_code, {})
                    _TRANSLATIONS[lang_code].update(data)
                except Exception as err:
                    print(f"[i18n] Lỗi đọc tệp ngôn ngữ {fname}: {err}")

load_locales()

def get_current_language() -> str:
    """Trả về mã ngôn ngữ đang hoạt động (ví dụ 'vi' hoặc 'en')."""
    return _CURRENT_LANG

def set_language(lang_code: str):
    """Thiết lập ngôn ngữ đang hoạt động."""
    global _CURRENT_LANG
    lang_code = (lang_code or "vi").lower()
    if lang_code in _TRANSLATIONS:
        _CURRENT_LANG = lang_code
    elif lang_code.startswith("en"):
        _CURRENT_LANG = "en"
    else:
        _CURRENT_LANG = "vi"

def tr(key: str, **kwargs) -> str:
    """
    Tra cứu chuỗi dịch thuật theo mã ngôn ngữ hiện tại và thế chỗ placeholder an toàn.
    Ví dụ: tr("info.summary", enabled=2, total=5, reqs=1)
    """
    lang_dict = _TRANSLATIONS.get(_CURRENT_LANG, {})
    template = lang_dict.get(key)
    if template is None:
        template = _TRANSLATIONS.get("en", {}).get(key, key)

    if not kwargs:
        return template

    try:
        return template.format(**kwargs)
    except Exception:
        # Fallback an toàn nếu thiếu key format hoặc sai kiểu dữ liệu
        res = template
        for k, v in kwargs.items():
            res = res.replace(f"{{{k}}}", str(v))
        return res
