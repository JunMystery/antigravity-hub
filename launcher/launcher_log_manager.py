# -*- coding: utf-8 -*-
"""
Module quản lý nhật ký (Log Management & Retention) cho Antigravity Launcher.
Hỗ trợ đọc đường dẫn log, xóa log an toàn, cấu hình thời gian lưu giữ (7/30/90 ngày),
dọn dẹp log quá hạn (Pruning) và trích xuất cấu trúc [MAIN] vs [SUBAGENT].
"""

import os
import re
import time
from typing import List, Dict, Any

from launcher_storage import CONFIG_DIR, load_data, save_data

DEFAULT_RETENTION_DAYS = 30
LOG_FILE = os.path.join(CONFIG_DIR, "proxy.log")
LOGS_DIR = os.path.join(CONFIG_DIR, "logs")

LOG_ENTRY_PATTERN = re.compile(
    r"(?:\[(?P<ts>[^\]]+)\]\s+)?\[ROUND-ROBIN #(?P<req>\d+)\]\s+(?P<tag>\[MAIN\]|\[SUBAGENT\])\s+(?P<details>.*)",
    re.IGNORECASE
)

def get_log_path() -> str:
    """Trả về đường dẫn tuyệt đối đến tệp proxy.log."""
    return LOG_FILE

def clear_log() -> bool:
    """Xóa trắng nội dung tệp proxy.log an toàn."""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.truncate(0)
        return True
    except Exception:
        return False

def get_retention_days() -> int:
    """Đọc cấu hình số ngày lưu trữ log (mặc định 30 ngày)."""
    data = load_data()
    return int(data.get("settings", {}).get("log_retention_days", DEFAULT_RETENTION_DAYS))

def set_retention_days(days: int) -> None:
    """Lưu cấu hình số ngày lưu trữ log vào profiles.json."""
    data = load_data()
    data.setdefault("settings", {})["log_retention_days"] = int(days)
    save_data(data)

def prune_logs(retention_days: int = None) -> int:
    """Xóa các tệp log luân phiên trong thư mục logs cũ hơn số ngày chỉ định."""
    if retention_days is None:
        retention_days = get_retention_days()

    cutoff_ts = time.time() - (retention_days * 86400)
    pruned_count = 0

    if os.path.isdir(LOGS_DIR):
        for entry in os.scandir(LOGS_DIR):
            if entry.is_file() and entry.name.startswith("proxy") and entry.name.endswith(".log"):
                try:
                    if entry.stat().st_mtime < cutoff_ts:
                        os.remove(entry.path)
                        pruned_count += 1
                except OSError:
                    pass

    return pruned_count

def parse_log_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """Phân tích các dòng log thành danh sách đối tượng có cấu trúc."""
    parsed: List[Dict[str, Any]] = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue

        match = LOG_ENTRY_PATTERN.search(cleaned)
        if match:
            req_num = int(match.group("req")) if match.group("req") else None
            raw_tag = match.group("tag").upper()
            tag = "SUBAGENT" if "SUBAGENT" in raw_tag else "MAIN"
            details = match.group("details").strip()
            ts = match.group("ts") or time.strftime("%H:%M:%S")
            parsed.append({"req": req_num, "tag": tag, "details": details, "timestamp": ts, "raw": cleaned})
        elif "[SUBAGENT]" in cleaned.upper():
            parsed.append({"req": None, "tag": "SUBAGENT", "details": cleaned, "timestamp": time.strftime("%H:%M:%S"), "raw": cleaned})
        elif "[MAIN]" in cleaned.upper():
            parsed.append({"req": None, "tag": "MAIN", "details": cleaned, "timestamp": time.strftime("%H:%M:%S"), "raw": cleaned})
        else:
            parsed.append({"req": None, "tag": "GENERAL", "details": cleaned, "timestamp": time.strftime("%H:%M:%S"), "raw": cleaned})
    return parsed
