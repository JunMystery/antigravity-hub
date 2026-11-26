# -*- coding: utf-8 -*-
import ctypes
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER_DIR = os.path.join(ROOT_DIR, "launcher")
if LAUNCHER_DIR not in sys.path:
    sys.path.insert(0, LAUNCHER_DIR)

import launcher_browser_close


class TestOAuthAutoClose(unittest.TestCase):
    def test_oauth_success_title_markers_vi_en_and_error_page(self):
        code = """
        const { renderHtml } = require("./proxy/oauth_handler");
        const viOk = renderHtml("Đăng nhập thành công!", "<b>a@b.com</b>", true, "vi");
        const enOk = renderHtml("Login Successful!", "<b>a@b.com</b>", true, "en");
        const errHtml = renderHtml("Ủy quyền thất bại", "err", false, "vi");
        console.log(JSON.stringify({ viOk, enOk, errHtml }));
        """
        res = subprocess.run(["node", "-e", code], cwd=ROOT_DIR, capture_output=True, text=True, check=True)
        out = json.loads(res.stdout.strip().splitlines()[-1])

        self.assertIn("<title>Antigravity Hub - Đăng nhập thành công!</title>", out["viOk"])
        self.assertIn("<title>Antigravity Hub - Login Successful!</title>", out["enOk"])
        self.assertIn('id="oauth-hint"', out["viOk"])
        self.assertIn('id="btn-close-tab"', out["enOk"])
        self.assertIn("Ctrl+W", out["enOk"])
        self.assertNotIn("Antigravity Hub - Đăng nhập thành công!", out["errHtml"])

    def test_is_oauth_success_window_title_matching(self):
        self.assertTrue(launcher_browser_close.is_oauth_success_window_title(
            "Antigravity Hub - Đăng nhập thành công! - Google Chrome"
        ))
        self.assertTrue(launcher_browser_close.is_oauth_success_window_title(
            "Antigravity Hub - Login Successful! - Microsoft Edge"
        ))
        self.assertTrue(launcher_browser_close.is_oauth_success_window_title(
            "Antigravity Hub - Login Successful! - Mozilla Firefox"
        ))
        self.assertFalse(launcher_browser_close.is_oauth_success_window_title("Antigravity Hub"))
        self.assertFalse(launcher_browser_close.is_oauth_success_window_title("Visual Studio Code"))
        self.assertFalse(launcher_browser_close.is_oauth_success_window_title(""))

    def test_try_close_guards_title_and_modifiers(self):
        with patch.object(launcher_browser_close.sys, "platform", "win32"), \
             patch.object(launcher_browser_close, "get_foreground_window_title", return_value="Antigravity Hub - Login Successful! - Chrome"), \
             patch.object(launcher_browser_close, "has_blocking_modifiers", return_value=False), \
             patch.object(launcher_browser_close, "send_ctrl_w", return_value=True) as mock_send:
            self.assertTrue(launcher_browser_close.try_close_oauth_browser_tab())
            mock_send.assert_called_once()

        with patch.object(launcher_browser_close.sys, "platform", "win32"), \
             patch.object(launcher_browser_close, "get_foreground_window_title", return_value="YouTube - Google Chrome"), \
             patch.object(launcher_browser_close, "has_blocking_modifiers", return_value=False), \
             patch.object(launcher_browser_close, "send_ctrl_w", return_value=True) as mock_send:
            self.assertFalse(launcher_browser_close.try_close_oauth_browser_tab())
            mock_send.assert_not_called()

        with patch.object(launcher_browser_close.sys, "platform", "win32"), \
             patch.object(launcher_browser_close, "get_foreground_window_title", return_value="Antigravity Hub - Đăng nhập thành công! - Chrome"), \
             patch.object(launcher_browser_close, "has_blocking_modifiers", return_value=True), \
             patch.object(launcher_browser_close, "send_ctrl_w", return_value=True) as mock_send:
            self.assertFalse(launcher_browser_close.try_close_oauth_browser_tab())
            mock_send.assert_not_called()

    def test_win32_input_struct_size(self):
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(launcher_browser_close.INPUT), expected)


if __name__ == "__main__":
    unittest.main()
