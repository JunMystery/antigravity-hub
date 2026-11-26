# -*- coding: utf-8 -*-
"""
Hàm định dạng nội dung các cột hiển thị cho bảng Quy tắc Model.
"""

from launcher_i18n import tr
from launcher_model_discovery import get_rule_patterns_py


def format_count_label(count: int, one_key: str, many_key: str) -> str:
    """Định dạng nhãn đếm số lượng hỗ trợ số ít/số nhiều theo ngôn ngữ."""
    return tr(one_key if count == 1 else many_key, count=count)


def _rule_account_emails(rule: dict) -> list[str]:
    accs = rule.get("accounts") or ([{"email": rule.get("account_email", "")}] if rule.get("account_email") else [])
    return [str(a.get("email") or a.get("id") or "").strip() for a in accs if a.get("email") or a.get("id")]


def format_rule_pattern_cell(rule: dict) -> tuple[str, str]:
    """Trả về (nhãn compact, tooltip) cho cột Mẫu Model."""
    pats = sorted(get_rule_patterns_py(rule), key=str.lower)
    count_lbl = format_count_label(len(pats), "model_rules.count_models_one", "model_rules.count_models")
    custom_name = str(rule.get("name") or "").strip()
    auto_legacy = f"{pats[0]} (+{len(pats) - 1})" if len(pats) > 1 else (pats[0] if pats else "")
    has_custom = bool(custom_name and custom_name != auto_legacy)
    if has_custom:
        display = f"{custom_name} ({count_lbl})"
    elif len(pats) == 1:
        display = pats[0]
    else:
        display = count_lbl
    mtype = str(rule.get("match_type") or "contains").lower()
    match_line = f"{tr('model_rules.col_match_type')}: {tr(f'model_rules.match_{mtype}')}"
    preview = "\n".join(pats[:10]) + (f"\n+{len(pats) - 10}..." if len(pats) > 10 else "")
    header = f"{custom_name}\n{match_line}" if has_custom else match_line
    return display, f"{header}\n{preview}\n\n{tr('model_rules.click_for_details')}".strip()


def format_rule_strategy_cell(rule: dict, compact: bool = False) -> str:
    """Trả về nhãn chiến lược kèm ngưỡng xoay vòng (riêng hoặc theo tổng)."""
    strat = str(rule.get("strategy") or "priority").lower()
    suffix = "_short" if compact else ""
    if strat != "round_robin":
        return tr(f"model_rules.strategy_priority{suffix}")
    try:
        reqs = int(rule.get("requests_per_account") or 0)
    except (TypeError, ValueError):
        reqs = 0
    if reqs > 0:
        return tr(f"model_rules.strategy_rr_custom{suffix}", reqs=reqs)
    return tr(f"model_rules.strategy_rr_global{suffix}")


def format_rule_accounts_cell(rule: dict) -> tuple[str, str]:
    """Trả về (nhãn compact, tooltip) cho cột Tài khoản đích."""
    acc_emails = _rule_account_emails(rule)
    count_lbl = format_count_label(len(acc_emails), "model_rules.count_accounts_one", "model_rules.count_accounts")
    fb_suffix = f" · {tr('model_rules.badge_fallback_short')}" if rule.get("fallback_to_global") else ""
    preview = "\n".join(acc_emails[:10]) + (f"\n+{len(acc_emails) - 10}..." if len(acc_emails) > 10 else "")
    return f"{count_lbl}{fb_suffix}", f"{preview}\n\n{tr('model_rules.click_for_details')}".strip()


def build_rule_account_display_lines(rule: dict, available_accounts: list) -> list[str]:
    """Tạo danh sách dòng tài khoản giữ nguyên thứ tự ưu tiên kèm trạng thái Active/Deactive."""
    acc_state = {}
    for acc in (available_accounts or []):
        enabled = acc.get("enabled", True) is not False
        if acc.get("email"):
            acc_state[str(acc["email"]).lower()] = enabled
        if acc.get("id"):
            acc_state[str(acc["id"]).lower()] = enabled

    lines = []
    for idx, email in enumerate(_rule_account_emails(rule or {}), start=1):
        enabled = acc_state.get(email.lower(), True)
        status = tr("model_rules.status_active") if enabled else tr("model_rules.status_deactive")
        lines.append(f"#{idx}  {email}  [{status}]")
    return lines
