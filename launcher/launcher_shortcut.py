# -*- coding: utf-8 -*-
"""
Module tự động tạo Desktop Shortcut cho Antigravity Launcher trên Linux và Windows.
"""

import os
import sys
import shutil
import subprocess

from launcher_storage import BASE_DIR, APP_ICON, find_app_icon

def get_desktop_dir() -> str:
    """Xác định đường dẫn thư mục Desktop của người dùng."""
    if sys.platform == "win32":
        return os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
    # Linux: kiểm tra xdg-user-dir DESKTOP hoặc fallback ~/Desktop
    try:
        res = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, check=True)
        out = res.stdout.strip()
        if out and os.path.exists(out):
            return out
    except Exception:
        pass
    return os.path.expanduser("~/Desktop")

def create_desktop_shortcut() -> bool:
    """Tự động tạo shortcut trên Desktop và App Menu tương thích đa nền tảng."""
    desktop_dir = get_desktop_dir()
    os.makedirs(desktop_dir, exist_ok=True)

    if sys.platform == "win32":
        return _create_windows_shortcut(desktop_dir)
    return _create_linux_shortcut(desktop_dir)

def _create_linux_shortcut(desktop_dir: str) -> bool:
    """Tạo tệp .desktop trên Linux."""
    launch_script = os.path.join(BASE_DIR, "launch.sh")
    try:
        os.chmod(launch_script, 0o755)
    except Exception:
        pass
    icon_path = find_app_icon(preferred_ext="png")
    if os.path.exists(icon_path):
        try:
            sys_icon_dir = os.path.expanduser("~/.local/share/icons/hicolor/512x512/apps")
            os.makedirs(sys_icon_dir, exist_ok=True)
            shutil.copy2(icon_path, os.path.join(sys_icon_dir, "antigravity-launcher.png"))
        except Exception:
            pass

    content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Antigravity Launcher
Comment=Antigravity Profile Launcher & Round Robin Coordinator
Exec="{launch_script}"
Icon={icon_path}
Terminal=false
StartupNotify=true
Categories=Development;IDE;
StartupWMClass=antigravity-launcher
"""

    # Xóa tệp cũ viết hoa nếu tồn tại để tránh xung đột
    old_desktop_file = os.path.join(desktop_dir, "Antigravity-Launcher.desktop")
    if os.path.exists(old_desktop_file):
        try:
            os.remove(old_desktop_file)
        except Exception:
            pass
    old_app_menu = os.path.expanduser("~/.local/share/applications/Antigravity-Launcher.desktop")
    if os.path.exists(old_app_menu):
        try:
            os.remove(old_app_menu)
        except Exception:
            pass

    targets = [
        os.path.join(desktop_dir, "antigravity-launcher.desktop"),
        os.path.expanduser("~/.local/share/applications/antigravity-launcher.desktop")
    ]

    success = False
    for path in targets:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(path, 0o755)
            # Đánh dấu tin cậy nếu có gio (GNOME/Cinnamon/MATE)
            if "Desktop" in path:
                try:
                    subprocess.run(["gio", "set", path, "metadata::trusted", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            success = True
        except Exception:
            pass

    # Cập nhật cache ứng dụng của desktop environment (GNOME/KDE)
    try:
        app_menu_dir = os.path.expanduser("~/.local/share/applications")
        subprocess.run(["update-desktop-database", app_menu_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    return success

def _create_windows_shortcut(desktop_dir: str) -> bool:
    """Tạo tệp .lnk trên Windows bằng PowerShell."""
    from launcher_storage import APP_BINARY
    shortcut_path = os.path.join(desktop_dir, "Antigravity Launcher.lnk")
    target_bat = os.path.join(BASE_DIR, "launch.bat")

    # Trên Windows, ưu tiên tệp .ico từ assets để hiển thị sắc nét đa độ phân giải
    icon_path = find_app_icon(preferred_ext="ico")

    sc_clean = shortcut_path.replace("'", "''")
    tb_clean = target_bat.replace("'", "''")
    bd_clean = BASE_DIR.replace("'", "''")
    ic_clean = icon_path.replace("'", "''")

    ps_cmd = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{sc_clean}')
$s.TargetPath = '{tb_clean}'
$s.WorkingDirectory = '{bd_clean}'
$s.IconLocation = '{ic_clean}'
$s.Description = 'Antigravity Profile Launcher'
$s.Save()
"""
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False
