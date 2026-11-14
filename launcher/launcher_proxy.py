# -*- coding: utf-8 -*-
"""
Module quản lý tiến trình Micro-Proxy Round Robin và khởi chạy Antigravity IDE.
"""

import os
import sys
import time
import json
import socket
import signal
import subprocess
from launcher_storage import (
    CONFIG_DIR, PROXY_PORT, PROXY_SCRIPT, PID_FILE,
    LAUNCHED_APPS_FILE, ROOT_CA, PROXY_PAC, APP_BINARY,
    get_app_binary, get_ide_binary
)

LAUNCHED_PIDS = []

def is_proxy_running(port=PROXY_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.08)
        return s.connect_ex(("127.0.0.1", port)) == 0

def stop_proxy():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        except Exception:
            pass
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/F", "/IM", "node.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    else:
        try:
            subprocess.run(["fuser", "-k", f"{PROXY_PORT}/tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        try:
            subprocess.run(["pkill", "-f", "antigravity-token-proxy/index.js"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    status_file = os.path.join(CONFIG_DIR, "live_status.json")
    try:
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump({
                "active": False,
                "timestamp": int(time.time() * 1000),
                "account_email": "Proxy đã dừng",
                "account_name": "Proxy đã dừng",
                "current_req": 0,
                "requests_per_account": 1,
                "total_requests": 0,
                "endpoint": "",
                "method": "",
                "status": "stopped"
            }, f)
    except Exception:
        pass

def ensure_proxy_running():
    if not is_proxy_running():
        if os.path.exists(PROXY_SCRIPT):
            log_file_path = os.path.join(CONFIG_DIR, "proxy.log")
            try:
                log_f = open(log_file_path, "a", encoding="utf-8")
            except Exception:
                log_f = subprocess.DEVNULL

            kwargs = {"stdout": log_f, "stderr": subprocess.STDOUT}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True

            proc = subprocess.Popen(["node", PROXY_SCRIPT], **kwargs)
            try:
                with open(PID_FILE, "w") as f:
                    f.write(str(proc.pid))
            except Exception:
                pass

            for _ in range(25):
                time.sleep(0.1)
                if is_proxy_running():
                    break

def register_launched_pid(pid: int):
    global LAUNCHED_PIDS
    if pid not in LAUNCHED_PIDS:
        LAUNCHED_PIDS.append(pid)
    try:
        current = []
        if os.path.exists(LAUNCHED_APPS_FILE):
            with open(LAUNCHED_APPS_FILE, "r") as f:
                current = json.load(f)
        if pid not in current:
            current.append(pid)
        with open(LAUNCHED_APPS_FILE, "w") as f:
            json.dump(current, f)
    except Exception:
        pass

def stop_all_launched_apps():
    global LAUNCHED_PIDS
    pids_to_kill = set(LAUNCHED_PIDS)
    if os.path.exists(LAUNCHED_APPS_FILE):
        try:
            with open(LAUNCHED_APPS_FILE, "r") as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    pids_to_kill.update(saved)
        except Exception:
            pass

    if sys.platform == "win32":
        for pid in pids_to_kill:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    else:
        for pid in pids_to_kill:
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass

        if pids_to_kill:
            time.sleep(0.2)

        for pid in pids_to_kill:
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

        try:
            subprocess.run(
                ["pkill", "-f", "Antigravity-Profiles"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    LAUNCHED_PIDS = []
    try:
        if os.path.exists(LAUNCHED_APPS_FILE):
            os.remove(LAUNCHED_APPS_FILE)
    except OSError:
        pass

def launch_profile(data_dir: str, target: str = "app", use_proxy: bool = True) -> bool:
    if isinstance(target, bool):
        use_proxy = target
        target = "app"

    os.makedirs(data_dir, exist_ok=True)
    env = os.environ.copy()

    user_data = os.path.join(data_dir, "Antigravity")
    os.makedirs(user_data, exist_ok=True)
    if sys.platform != "win32":
        env["XDG_CONFIG_HOME"] = data_dir

    bin_path = get_ide_binary() if target == "ide" else get_app_binary()
    if not bin_path or not os.path.exists(bin_path):
        bin_path = APP_BINARY if target != "ide" else None
        if not bin_path or not os.path.exists(bin_path):
            print(f"Không tìm thấy binary cho target '{target}'", file=sys.stderr)
            return False

    cmd = [bin_path, f"--user-data-dir={user_data}"]
    if sys.platform != "win32":
        cmd.append("--password-store=basic")

    if use_proxy:
        ensure_proxy_running()
        if os.path.exists(ROOT_CA):
            env["NODE_EXTRA_CA_CERTS"] = ROOT_CA
            env["SSL_CERT_FILE"] = ROOT_CA
            env["REQUESTS_CA_BUNDLE"] = ROOT_CA

        proxy_url = f"http://127.0.0.1:{PROXY_PORT}"
        env["HTTPS_PROXY"] = proxy_url
        env["HTTP_PROXY"] = proxy_url
        env["https_proxy"] = proxy_url
        env["http_proxy"] = proxy_url
        env["ALL_PROXY"] = proxy_url
        env["all_proxy"] = proxy_url
        env["NO_PROXY"] = "localhost,127.0.0.1"
        env["no_proxy"] = "localhost,127.0.0.1"

        cmd.insert(1, "--ignore-certificate-errors")
        cmd.insert(1, f"--proxy-pac-script={PROXY_PAC}")

    try:
        kwargs = {"env": env, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **kwargs)
        register_launched_pid(proc.pid)
        return True
    except Exception as e:
        print(f"Lỗi khởi chạy: {e}", file=sys.stderr)
        return False
