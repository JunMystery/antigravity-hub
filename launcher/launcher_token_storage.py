# -*- coding: utf-8 -*-
"""
Module quản lý lưu trữ và tổng hợp dữ liệu Token Metrics (launcher_token_storage.py).
Lưu trữ độc lập với proxy.log, gom nhóm theo khung giờ (24h, 7D, 30D, All time).
"""

import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from launcher_storage import CONFIG_DIR

TOKEN_METRICS_FILE = os.path.join(CONFIG_DIR, "token_metrics.json")


def get_token_metrics_path() -> str:
    """Trả về đường dẫn tệp token_metrics.json."""
    return TOKEN_METRICS_FILE


def load_token_metrics(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Đọc dữ liệu token từ file JSON độc lập."""
    target_path = file_path or TOKEN_METRICS_FILE
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "lifetime" not in data:
                        data["lifetime"] = {"sent": 0, "received": 0, "cached": 0, "total": 0, "requests": 0}
                    if "hourly" not in data:
                        data["hourly"] = {}
                    return data
        except Exception:
            pass
    return {
        "lifetime": {"sent": 0, "received": 0, "cached": 0, "total": 0, "requests": 0},
        "hourly": {}
    }


def format_full_number(count: int) -> str:
    """Định dạng số token đầy đủ có dấu phẩy phân cách hàng nghìn (vd: 12,345,678,901,234)."""
    if not count or count <= 0:
        return "0"
    return f"{count:,}"

def format_token_count(count: int) -> str:
    """Định dạng số token rút gọn trực quan (vd: 1.25K, 45.8M, 1B, 1.5T, 1Q, 1Qi)."""
    if count <= 0:
        return "0"
    scales = [
        (1_000_000_000_000_000_000, "Qi"),
        (1_000_000_000_000_000, "Q"),
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "K"),
    ]
    for threshold, unit in scales:
        if count >= threshold:
            val = count / threshold
            formatted = f"{val:.3f}".rstrip("0").rstrip(".")
            return f"{formatted}{unit}"
    return str(count)


def get_aggregated_tokens(
    timeframe: str = "24h",
    metrics_data: Optional[Dict[str, Any]] = None,
    now_dt: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Tổng hợp số liệu token theo khung thời gian: '24h', '7d', '30d', 'all'.
    Trả về dict gồm: sent, received, cached, total, requests, cache_ratio.
    """
    data = metrics_data if metrics_data is not None else load_token_metrics()
    tf = (timeframe or "24h").lower()

    if tf == "all":
        life = data.get("lifetime", {})
        s = life.get("sent", 0)
        r = life.get("received", 0)
        c = life.get("cached", 0)
        t = life.get("total", s + r)
        n = life.get("requests", 0)
        ratio = round((c / (s + c) * 100), 1) if (s + c) > 0 else 0.0
        return {"sent": s, "received": r, "cached": c, "total": t, "requests": n, "cache_ratio": ratio}

    delta_map = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    cutoff_delta = delta_map.get(tf, timedelta(hours=24))
    now = now_dt or datetime.now(timezone.utc)
    cutoff = now - cutoff_delta

    sent_total = 0
    recv_total = 0
    cached_total = 0
    total_tokens = 0
    req_count = 0

    hourly = data.get("hourly", {})
    for dt_str, bucket in hourly.items():
        try:
            # Chuẩn ISO: 2026-11-16T11:00:00Z
            clean_str = dt_str.replace("Z", "+00:00")
            b_dt = datetime.fromisoformat(clean_str)
            if b_dt.tzinfo is None:
                b_dt = b_dt.replace(tzinfo=timezone.utc)
            if b_dt >= cutoff:
                sent_total += bucket.get("s", 0)
                recv_total += bucket.get("r", 0)
                cached_total += bucket.get("c", 0)
                total_tokens += bucket.get("t", bucket.get("s", 0) + bucket.get("r", 0))
                req_count += bucket.get("n", 0)
        except Exception:
            continue

    ratio = round((cached_total / (sent_total + cached_total) * 100), 1) if (sent_total + cached_total) > 0 else 0.0
    return {
        "sent": sent_total, "received": recv_total, "cached": cached_total,
        "total": total_tokens, "requests": req_count, "cache_ratio": ratio
    }
