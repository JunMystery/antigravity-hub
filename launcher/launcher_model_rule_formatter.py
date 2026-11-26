# -*- coding: utf-8 -*-
"""
Hàm định dạng nội dung các cột hiển thị cho bảng Quy tắc Model.
"""

from launcher_i18n import tr
from launcher_model_discovery import get_rule_patterns_py


def format_rule_pattern_cell(rule: dict) -> tuple[str, str]:
    """Trả về (nhãn hiển thị, tooltip) cho cột Mẫu Model."""
    pats = get_rule_patterns_py(rule)
    pat_sum = ", ".join(pats[:2]) + (f" (+{len(pats) - 2})" if len(pats) > 2 else "")
    custom_name = str(rule.get("name") or "").strip()
    auto_legacy = f"{pats[0]} (+{len(pats) - 1})" if len(pats) > 1 else (pats[0] if pats else "")
    display = pat_sum if (not custom_name or custom_name in (pat_sum, auto_legacy)) else f"{custom_name} ({pat_sum})"
    tooltip = (f"{custom_name}\n" if custom_name else "") + "\n".join(pats)
    return display, tooltip


def format_rule_strategy_cell(rule: dict) -> str:
    """Trả về nhãn chiến lược kèm ngưỡng xoay vòng (riêng hoặc theo tổng)."""
    strat = str(rule.get("strategy") or "priority").lower()
    if strat != "round_robin":
        return tr("model_rules.strategy_priority")
    try:
        reqs = int(rule.get("requests_per_account") or 0)
    except (TypeError, ValueError):
        reqs = 0
    if reqs > 0:
        return tr("model_rules.strategy_rr_custom", reqs=reqs)
    return tr("model_rules.strategy_rr_global")


def format_rule_accounts_cell(rule: dict) -> tuple[str, str]:
    """Trả về (nhãn hiển thị, tooltip) cho cột Tài khoản đích."""
    accs = rule.get("accounts") or ([{"email": rule.get("account_email", "")}] if rule.get("account_email") else [])
    acc_emails = [a.get("email") or a.get("id") or "" for a in accs if a.get("email") or a.get("id")]
    acc_sum = ", ".join(acc_emails[:2]) + (f" (+{len(acc_emails) - 2})" if len(acc_emails) > 2 else "")
    fb_suffix = f" | {tr('model_rules.badge_fallback')}" if rule.get("fallback_to_global") else ""
    return f"{acc_sum}{fb_suffix}", ", ".join(acc_emails)
