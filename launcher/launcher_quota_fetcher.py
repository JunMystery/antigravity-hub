# -*- coding: utf-8 -*-
"""
Module truy vấn Quota Gemini qua Google Cloud Code API cho Antigravity Launcher (PyQt6).
Hỗ trợ cơ chế SSL linh hoạt chống lỗi SSLCertVerificationError trên Python 3.14 / Linux / Windows.
"""

import ssl
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from launcher_storage import CACHE_TTL, CLIENT_ID, CLIENT_SECRET, USER_AGENT

def format_reset_time(iso_str: str) -> str:
    """
    Chuyển đổi timestamp ISO 8601 (UTC) thành chuỗi đếm ngược:
    - Nếu >= 24h: 'Reset in Xd Yh'
    - Nếu < 24h: 'Reset in HH:MM'
    - Nếu đã qua thời gian reset: 'Resetting...'
    """
    if not iso_str:
        return ""
    try:
        clean_iso = iso_str.replace("Z", "+00:00")
        target_dt = datetime.fromisoformat(clean_iso)
        now_dt = datetime.now(timezone.utc)
        diff_sec = int((target_dt - now_dt).total_seconds())

        if diff_sec <= 0:
            return "Resetting..."

        hours = diff_sec // 3600
        mins = (diff_sec % 3600) // 60

        if hours >= 24:
            days = hours // 24
            rem_hours = hours % 24
            return f"Reset in {days}d {rem_hours}h"

        return f"Reset in {hours:02d}:{mins:02d}"
    except Exception:
        return ""

def get_ssl_context():
    """Tạo SSL Context tương thích cao cho truy vấn Google API."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return ssl._create_unverified_context()

def _format_bucket_quota(bucket: dict | None, missing_text: str = "--") -> tuple:
    """Chuyển đổi một bucket quota từ Google API thành bộ (val, text, is_valid, reset_str)."""
    if not bucket:
        return 0, missing_text, False, ""
    frac = bucket.get("remainingFraction")
    if frac is None:
        return 0, missing_text, False, ""
    val = max(0, min(100, round(frac * 100)))
    raw_reset = bucket.get("resetTime")
    reset_str = format_reset_time(raw_reset) if raw_reset else ""
    return val, f"{val}%", True, reset_str


def parse_quota_summary(qdata: dict) -> tuple:
    """
    Bóc tách Quota 5h, Weekly (Gemini Models) và Argon Weekly (Gemini 4 Argon) từ retrieveUserQuotaSummary.
    Trả về 12-tuple: (q5_v, q5_t, q5_ok, q5_r, qw_v, qw_t, qw_ok, qw_r, qa_v, qa_t, qa_ok, qa_r).
    """
    bucket_5h = None
    bucket_weekly = None
    bucket_argon_weekly = None

    for g in qdata.get("groups", []):
        g_name = (g.get("displayName") or "").lower()
        buckets = g.get("buckets", [])
        is_argon_group = "argon" in g_name or any("argon" in (b.get("bucketId") or "").lower() for b in buckets)
        is_gemini_group = ("gemini" in g_name) and not is_argon_group

        if is_argon_group:
            for b in buckets:
                w = (b.get("window") or "").lower()
                bid = (b.get("bucketId") or "").lower()
                if w == "weekly" or "weekly" in bid:
                    bucket_argon_weekly = b
        elif is_gemini_group:
            for b in buckets:
                w = (b.get("window") or "").lower()
                bid = (b.get("bucketId") or "").lower()
                if w == "5h" or "5h" in bid:
                    bucket_5h = b
                elif w == "weekly" or "weekly" in bid:
                    bucket_weekly = b

    q5_val, q5_text, q5_valid, q5_reset = _format_bucket_quota(bucket_5h, missing_text="--")
    qw_val, qw_text, qw_valid, qw_reset = _format_bucket_quota(bucket_weekly, missing_text="N/A")
    qa_val, qa_text, qa_valid, qa_reset = _format_bucket_quota(bucket_argon_weekly, missing_text="--")
    return (
        q5_val, q5_text, q5_valid, q5_reset,
        qw_val, qw_text, qw_valid, qw_reset,
        qa_val, qa_text, qa_valid, qa_reset,
    )


def fetch_single_account_quota(acc: dict, force: bool = False, cached_info: dict = None) -> tuple:
    """
    Truy vấn Quota 5h, Weekly và Argon Weekly của Gemini qua Google Cloud Code API.
    Áp dụng Cache TTL 3 phút (180s) để chống spam request.
    Trả về 12-tuple: (q5_val, q5_text, q5_valid, q5_reset, qw_val, qw_text, qw_valid, qw_reset, qa_val, qa_text, qa_valid, qa_reset).
    """
    now = time.time()
    if not force and cached_info and "quota_argon_valid" in cached_info:
        last_ts = cached_info.get("quota_timestamp", 0)
        if now - last_ts < CACHE_TTL:
            return (
                cached_info.get("quota_5h_val", 0),
                cached_info.get("quota_5h", "--"),
                cached_info.get("quota_5h_valid", False),
                cached_info.get("quota_5h_reset", ""),
                cached_info.get("quota_weekly_val", 0),
                cached_info.get("quota_weekly", "--"),
                cached_info.get("quota_weekly_valid", False),
                cached_info.get("quota_weekly_reset", ""),
                cached_info.get("quota_argon_val", 0),
                cached_info.get("quota_argon", "--"),
                cached_info.get("quota_argon_valid", False),
                cached_info.get("quota_argon_reset", ""),
            )

    token = acc.get("accessToken", "")
    ref_token = acc.get("refreshToken", "")
    ssl_ctx = get_ssl_context()

    # 1. Refresh Access Token nếu có refresh_token
    if ref_token:
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
                token = res_data.get("access_token", token)
        except Exception:
            pass

    if not token:
        return 0, "N/A", False, "", 0, "N/A", False, "", 0, "N/A", False, ""

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json"
    }

    # 2. Truy vấn cloudaicompanionProject qua loadCodeAssist
    project_id = acc.get("projectId")
    try:
        body = json.dumps({"metadata": {"ideType": 9, "platform": 3, "pluginType": 2}, "mode": 1}).encode("utf-8")
        req = urllib.request.Request("https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist", data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=7) as res:
            pdata = json.loads(res.read().decode())
            project_id = pdata.get("cloudaicompanionProject") or project_id
    except Exception:
        pass

    # 3. Lấy Quota Summary chi tiết
    try:
        qheaders = dict(headers)
        qheaders["X-Client-Name"] = "antigravity"
        qheaders["X-Client-Version"] = "2.24.0"
        qbody = json.dumps({"project": project_id} if project_id else {}).encode("utf-8")
        qreq = urllib.request.Request("https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary", data=qbody, headers=qheaders, method="POST")
        with urllib.request.urlopen(qreq, context=ssl_ctx, timeout=7) as res:
            qdata = json.loads(res.read().decode())

        return parse_quota_summary(qdata)
    except Exception:
        return 0, "Lỗi", False, "", 0, "Lỗi", False, "", 0, "Lỗi", False, ""
