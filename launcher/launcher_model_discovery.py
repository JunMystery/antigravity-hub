# -*- coding: utf-8 -*-
"""
Module khám phá danh sách Model AI khả dụng từ nhật ký Proxy và API tài khoản Google.
"""

import os
import re
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any

from launcher_storage import load_accounts, CLIENT_ID, CLIENT_SECRET, USER_AGENT
from launcher_log_manager import get_log_path, read_tail_lines
from launcher_quota_fetcher import get_ssl_context


def collect_available_accounts(win_data: dict) -> List[Dict[str, Any]]:
    """Tổng hợp toàn bộ tài khoản có token hợp lệ (bao gồm cả tài khoản đang Deactive)."""
    accounts = load_accounts()
    token_by_email = {}
    token_by_id = {}
    for acc in accounts:
        if not (acc.get("accessToken") or acc.get("refreshToken")):
            continue
        email = (acc.get("email") or acc.get("name") or "").strip().lower()
        acc_id = str(acc.get("id") or "").strip().lower()
        if email:
            token_by_email[email] = acc
        if acc_id:
            token_by_id[acc_id] = acc

    result = []
    seen_emails = set()
    for prof in (win_data or {}).get("profiles", []):
        email = (prof.get("email") or prof.get("name") or "").strip()
        lower_email = email.lower()
        prof_id = str(prof.get("id") or "").strip().lower()
        acc = token_by_email.get(lower_email) or token_by_id.get(prof_id)
        if not acc:
            continue
        real_email = acc.get("email") or email
        seen_emails.add(real_email.lower())
        result.append({
            "id": str(acc.get("id") or prof.get("id") or ""),
            "email": real_email,
            "name": acc.get("name") or prof.get("name") or real_email,
            "enabled": prof.get("enabled", True) is not False,
            "account": acc
        })

    for acc in accounts:
        if not (acc.get("accessToken") or acc.get("refreshToken")):
            continue
        email = (acc.get("email") or acc.get("name") or "").strip()
        if not email or email.lower() in seen_emails:
            continue
        seen_emails.add(email.lower())
        result.append({
            "id": str(acc.get("id") or ""),
            "email": email,
            "name": acc.get("name") or email,
            "enabled": True,
            "account": acc
        })
    return result


def discover_models_from_logs(max_lines: int = 2000) -> List[str]:
    """Quét tệp proxy.log để lấy danh sách model đã từng đi qua Proxy (mới nhất trước)."""
    log_path = get_log_path()
    if not os.path.exists(log_path):
        return []
    models = []
    seen = set()
    try:
        lines = read_tail_lines(log_path, max_lines=max_lines)
        for line in reversed(lines):
            m = re.search(r"\[MODEL:\s*([^\]]+)\]", line)
            if m:
                name = m.group(1).strip()
                key = name.lower()
                if name and key not in seen:
                    seen.add(key)
                    models.append(name)
    except Exception:
        pass
    return sorted(models, key=str.lower)


def _refresh_access_token(acc: dict, ssl_ctx) -> str:
    token = acc.get("accessToken", "")
    ref_token = acc.get("refreshToken", "")
    if not ref_token:
        return token
    try:
        data = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": ref_token,
            "grant_type": "refresh_token"
        }).encode("utf-8")
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=7) as res:
            res_data = json.loads(res.read().decode())
            return res_data.get("access_token", token)
    except Exception:
        return token


def _extract_model_ids_from_payload(payload: Any) -> List[str]:
    found = []
    if isinstance(payload, dict):
        models_node = payload.get("models") or payload.get("availableModels")
        if isinstance(models_node, dict):
            found.extend(str(k) for k in models_node.keys() if k)
        elif isinstance(models_node, list):
            for item in models_node:
                if isinstance(item, str):
                    found.append(item)
                elif isinstance(item, dict):
                    mid = item.get("model") or item.get("modelId") or item.get("id") or item.get("name")
                    if mid:
                        found.append(str(mid))
        for g in payload.get("groups", []) or []:
            if isinstance(g, dict):
                g_name = g.get("displayName") or g.get("groupId")
                if g_name:
                    found.append(str(g_name))
                for b in g.get("buckets", []) or []:
                    if isinstance(b, dict):
                        bid = b.get("modelId") or b.get("model")
                        if bid:
                            found.append(str(bid))
    seen = set()
    clean = []
    for m in found:
        norm = m.replace("models/", "").strip()
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            clean.append(norm)
    return sorted(clean, key=str.lower)


def fetch_account_models(acc: dict) -> Dict[str, Any]:
    """Truy vấn danh sách model khả dụng cho một tài khoản qua Cloud Code API."""
    if not acc:
        return {"ok": False, "models": [], "error": "Missing account"}
    ssl_ctx = get_ssl_context()
    token = _refresh_access_token(acc, ssl_ctx)
    if not token:
        return {"ok": False, "models": [], "error": "No token"}

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "X-Client-Name": "antigravity",
        "X-Client-Version": "2.24.0"
    }
    project_id = acc.get("projectId") or "aicode-consumers"
    collected = []
    errors = []

    for endpoint in ("fetchAvailableModels", "retrieveUserQuotaSummary"):
        url = f"https://daily-cloudcode-pa.googleapis.com/v1internal:{endpoint}"
        try:
            body = json.dumps({"project": project_id} if project_id else {}).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as res:
                data = json.loads(res.read().decode())
                for m in _extract_model_ids_from_payload(data):
                    if m not in collected:
                        collected.append(m)
        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")

    return {"ok": len(collected) > 0, "models": sorted(collected, key=str.lower), "error": "; ".join(errors)}


def fetch_all_accounts_models(accounts_list: List[Dict[str, Any]], max_workers: int = 6) -> List[Dict[str, Any]]:
    """Quét song song danh sách model khả dụng cho toàn bộ tài khoản."""
    from concurrent.futures import ThreadPoolExecutor

    if not accounts_list:
        return []

    def _scan_one(entry: Dict[str, Any]) -> Dict[str, Any]:
        acc_obj = entry.get("account") if isinstance(entry.get("account"), dict) else entry
        res = fetch_account_models(acc_obj)
        return {
            "id": str(entry.get("id") or ""),
            "email": str(entry.get("email") or ""),
            "name": str(entry.get("name") or entry.get("email") or ""),
            "enabled": entry.get("enabled", True) is not False,
            "ok": bool(res.get("ok")),
            "models": list(res.get("models") or []),
            "error": str(res.get("error") or "")
        }

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(accounts_list)))) as pool:
        return list(pool.map(_scan_one, accounts_list))


def get_rule_patterns_py(rule: dict) -> List[str]:
    if not isinstance(rule, dict):
        return []
    raw = rule.get("patterns")
    raw_list = raw if isinstance(raw, list) and raw else ([rule.get("pattern")] if rule.get("pattern") else [])
    seen = set()
    patterns = []
    for item in raw_list:
        val = str(item or "").strip()
        if val and val.lower() not in seen:
            seen.add(val.lower())
            patterns.append(val)
    return patterns


def _matches_single_py(model_name: str, pat: str, mtype: str) -> bool:
    if mtype == "exact":
        return model_name.lower() == pat.lower()
    if mtype == "regex":
        try:
            return bool(re.search(pat, model_name, re.IGNORECASE))
        except re.error:
            return False
    return pat.lower() in model_name.lower()


def _does_rule_match_py(model_name: str, rule: dict) -> bool:
    if not model_name or not isinstance(rule, dict) or rule.get("enabled", True) is False:
        return False
    patterns = get_rule_patterns_py(rule)
    if not patterns:
        return False
    mtype = str(rule.get("match_type") or "contains").lower()
    return any(_matches_single_py(model_name, pat, mtype) for pat in patterns)


def _resolve_rule_accounts_py(rule: dict, available_accounts: List[dict]) -> List[dict]:
    refs = rule.get("accounts") if isinstance(rule.get("accounts"), list) and rule.get("accounts") else []
    if not refs and (rule.get("account_id") or rule.get("account_email")):
        refs = [{"id": rule.get("account_id", ""), "email": rule.get("account_email", "")}]
    by_email = {str(a.get("email") or "").lower(): a for a in available_accounts if a.get("email")}
    by_id = {str(a.get("id") or "").lower(): a for a in available_accounts if a.get("id")}
    resolved = []
    seen = set()
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        acc = by_email.get(str(ref.get("email") or "").lower()) or by_id.get(str(ref.get("id") or "").lower())
        if acc and acc.get("enabled", True) is not False:
            key = (str(acc.get("id") or ""), str(acc.get("email") or "").lower())
            if key not in seen:
                seen.add(key)
                resolved.append(acc)
    return resolved


def simulate_model_route(model_name: str, rules: List[dict], available_accounts: List[dict], pinned_email: str = "") -> Dict[str, Any]:
    """Mô phỏng luồng định tuyến để kiểm tra nhanh trên UI: tên model -> quy tắc & tài khoản đích."""
    target = (model_name or "").strip()
    if not target:
        return {"matched": False, "source": "none", "accounts": []}

    for rule in (rules or []):
        if not _does_rule_match_py(target, rule):
            continue
        pool = _resolve_rule_accounts_py(rule, available_accounts or [])
        if pool:
            patterns = get_rule_patterns_py(rule)
            default_name = (
                f"{patterns[0]} (+{len(patterns) - 1})" if len(patterns) > 1
                else (patterns[0] if patterns else "")
            )
            return {
                "matched": True,
                "source": "model_rule",
                "rule_name": rule.get("name") or default_name,
                "pattern": patterns[0] if patterns else "",
                "patterns": patterns,
                "match_type": str(rule.get("match_type") or "contains").lower(),
                "strategy": str(rule.get("strategy") or "priority").lower(),
                "fallback_to_global": bool(rule.get("fallback_to_global")),
                "accounts": pool
            }

    if pinned_email:
        pinned = [a for a in (available_accounts or []) if str(a.get("email") or "").lower() == pinned_email.lower()]
        return {"matched": False, "source": "pinned", "accounts": pinned}

    active = [a for a in (available_accounts or []) if a.get("enabled", True) is not False]
    return {"matched": False, "source": "round_robin", "accounts": active}

