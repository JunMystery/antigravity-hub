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
from launcher_storage import CACHE_TTL, CLIENT_ID, CLIENT_SECRET, USER_AGENT

def get_ssl_context():
    """Tạo SSL Context tương thích cao cho truy vấn Google API."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return ssl._create_unverified_context()

def fetch_single_account_quota(acc: dict, force: bool = False, cached_info: dict = None) -> tuple:
    """
    Truy vấn Quota 5h và Quota Weekly của Gemini qua Google Cloud Code API.
    Áp dụng Cache TTL 3 phút (180s) để chống spam request.
    Trả về: (q5_val: int, q5_text: str, q5_valid: bool, qw_val: int, qw_text: str, qw_valid: bool)
    """
    now = time.time()
    if not force and cached_info:
        last_ts = cached_info.get("quota_timestamp", 0)
        if now - last_ts < CACHE_TTL:
            return (
                cached_info.get("quota_5h_val", 0),
                cached_info.get("quota_5h", "--"),
                cached_info.get("quota_5h_valid", False),
                cached_info.get("quota_weekly_val", 0),
                cached_info.get("quota_weekly", "--"),
                cached_info.get("quota_weekly_valid", False)
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
        return 0, "N/A", False, 0, "N/A", False

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

        frac_5h = None
        frac_weekly = None
        has_5h_bucket = False

        for g in qdata.get("groups", []):
            if "gemini" in g.get("displayName", "").lower():
                for b in g.get("buckets", []):
                    w = b.get("window", "").lower()
                    bid = b.get("bucketId", "").lower()
                    f = b.get("remainingFraction")
                    if w == "5h" or "5h" in bid:
                        has_5h_bucket = True
                        frac_5h = f
                    elif w == "weekly" or "weekly" in bid:
                        frac_weekly = f

        if has_5h_bucket and frac_5h is not None:
            q5_val = max(0, min(100, round(frac_5h * 100)))
            q5_text = f"{q5_val}%"
            q5_valid = True
        else:
            q5_val = 0
            q5_text = "--"
            q5_valid = False

        if frac_weekly is not None:
            qw_val = max(0, min(100, round(frac_weekly * 100)))
            qw_text = f"{qw_val}%"
            qw_valid = True
        else:
            qw_val = 0
            qw_text = "N/A"
            qw_valid = False

        return q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid
    except Exception:
        return 0, "Lỗi", False, 0, "Lỗi", False
