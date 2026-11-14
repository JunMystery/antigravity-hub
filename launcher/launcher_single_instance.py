# -*- coding: utf-8 -*-
"""
Module đảm bảo chỉ có duy nhất 1 tiến trình Antigravity Launcher chạy tại một thời điểm (Single Instance).
Hỗ trợ kích hoạt cửa sổ hiện tại khi người dùng nhấp lại vào Desktop Shortcut.
"""

import sys
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "antigravity_launcher_single_instance_lock"

def set_windows_app_id():
    """Gán AppUserModelID chuẩn trên Windows để gom nhóm Taskbar chính xác."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("antigravity-launcher")
        except Exception:
            pass

def check_single_instance(activate_callback=None):
    """
    Kiểm tra xem đã có tiến trình Launcher nào đang chạy không.
    - Đã chạy: gửi thông điệp 'ACTIVATE' và trả về (False, None).
    - Chưa chạy: khởi động QLocalServer lắng nghe và trả về (True, server).
    """
    set_windows_app_id()

    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(300):
        socket.write(b"ACTIVATE\n")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return False, None

    server = QLocalServer()
    server.removeServer(SERVER_NAME)
    if server.listen(SERVER_NAME):
        if activate_callback:
            server.newConnection.connect(lambda: _handle_new_connection(server, activate_callback))
        return True, server
    return True, None

def setup_single_instance_listener(server, activate_callback):
    """Gắn callback kích hoạt cửa sổ khi nhận được kết nối mới."""
    if server and activate_callback:
        server.newConnection.connect(lambda: _handle_new_connection(server, activate_callback))

def _handle_new_connection(server, activate_callback):
    """Xử lý tín hiệu kích hoạt từ tiến trình shortcut mới."""
    while server.hasPendingConnections():
        client = server.nextPendingConnection()
        if client:
            if client.waitForReadyRead(300):
                cmd = client.readAll().data().decode("utf-8", errors="ignore").strip()
                if "ACTIVATE" in cmd and activate_callback:
                    activate_callback()
            else:
                if activate_callback:
                    activate_callback()
            client.disconnectFromServer()
