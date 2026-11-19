# Phase P03: Kiểm thử tự động & Nghiệm thu Regression

## 1. Phase Metadata

| Field | Value |
| :--- | :--- |
| **Phase ID** | `P03` |
| **Parent Task ID** | `TASK-20261119-001` |
| **Master Plan** | `../TASK_TOGGLE_ROUND_ROBIN_SWITCH_ACCOUNT.md` |
| **Status** | ✅ Done |
| **Depends on** | `P01`, `P02` (bắt buộc `P01` và `P02` đã `✅ Done`) |
| **Lifecycle Owner** | Worker |

---

## 2. Target File Impact (Trích xuất từ Section 4 Master)

| Action | File path | Target Symbol/Area | Reason | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| Edit | `tests/test_proxy_rotation.py` | `TestProxyRoundRobinRotation` | Bổ sung unit test Node.js cho `selectAccount`, `handleCommand("select")`, giữ tài khoản qua `loadState()`, `auto_rotation_enabled=false`, và OAuth `select_account` | `Confirmed` |
| Create | `tests/test_account_mode_switch.py` | `TestAccountModeAndSwitcher` | Tạo test PyQt6 headless cô lập temp config kiểm thử toggle Round Robin 2 chiều, dropdown/nút chọn tài khoản, `_launch_target`, i18n và regression 6 cột | `Confirmed` |

---

## 3. Tasks Breakdown

- [x] **Task P03.1**: Bổ sung test Proxy Node.js vào `tests/test_proxy_rotation.py`
  - File: `tests/test_proxy_rotation.py`
  - Chi tiết: Dùng `run_node()` bổ sung 4 test case mới phủ `T-001` đến `T-004`:
    1. `test_manual_select_account_command`: Gọi `handleCommand("select", mockRes, writeStatus, { target: "user2@test.com" })` trả `200`, `getCurrentAccount()` đổi sang `user2@test.com`, `currentAccRequestsServed === 0`, xóa cooldown `unhealthyUntil`; gọi với target không tồn tại `"missing@test.com"` trả `404` và giữ nguyên tài khoản hiện tại.
    2. `test_load_state_preserves_selected_account_after_reorder`: Khi `profiles.json` đổi thứ tự `order`, gọi `loadState()` không làm nhảy sang tài khoản khác; khi `settings.active_account_id` đổi từ ngoài, `loadState()` chuyển khớp theo `id` / `email` của profile.
    3. `test_auto_rotation_disabled_keeps_pinned_account`: Khi `settings.auto_rotation_enabled === false` (`rotationPaused = true`), gọi `allocateAccountForRequest()` 5 lần liên tiếp với `requestsPerAccount = 1` vẫn trả về cùng 1 tài khoản.
    4. `test_oauth_url_includes_select_account_prompt`: Gọi `buildGoogleAuthUrl(...)` và assert URL chứa `prompt=select_account+consent`.

- [x] **Task P03.2**: Tạo bộ test PyQt6 headless cô lập `tests/test_account_mode_switch.py`
  - File: `tests/test_account_mode_switch.py`
  - Chi tiết:
    1. Dùng `tempfile.TemporaryDirectory()` và patch đường dẫn `PROFILES_FILE` / `ACCOUNTS_FILE` / `CONFIG_DIR` + mock `ensure_proxy_running`, `handle_hide_on_launch`, `on_refresh_all_quota`, `prune_logs`, `create_desktop_shortcut` để tránh đụng file `%APPDATA%` thật hoặc bị treo bởi modal `hide_on_launch="ask"`.
    2. Kiểm thử các kịch bản phủ `T-005`, `T-006`, `T-007`:
       - Toggle `toggle_round_robin` OFF ↔ ON lưu đúng `auto_rotation_enabled`, khóa/mở `spin_reqs`, gửi `pause`/`resume`, đồng bộ 2 chiều khi bấm `btn_toggle_proxy`, và **không** làm đổi `round_robin_enabled` (Auto Refresh Quota).
       - Chọn tài khoản từ `combo_active_account` (Dashboard) và `btn_use_account` (Tài khoản), xác minh lưu `active_account_id`, gọi `send_proxy_cmd("select", {"target": ...})`.
       - Edge case: bấm `btn_use_account` trên tài khoản đang tắt `enabled=False` tự động bật `enabled=True` + gửi `reload` + `select`; danh sách rỗng không crash.
       - Kiểm tra `_launch_target` truyền đúng `data_dir` của tài khoản trong `active_account_id` vào `launch_profile`.
       - Kiểm tra regression `treeview.columnCount() == 6` và `retranslate_ui()` chuyển đổi nhãn mới đầy đủ EN ↔ VI.

- [x] **Task P03.3**: Chạy toàn bộ Verification & Chuẩn bị sạch nhánh PR cho tác giả
  - File: `tests/test_proxy_rotation.py`, `tests/test_account_mode_switch.py`
  - Chi tiết:
    1. Chạy lần lượt các lệnh test sau:
       ```powershell
       python -m py_compile launcher/*.py
       python -m unittest discover -s tests -p "test_proxy_rotation.py"
       python -m unittest discover -s tests -p "test_account_mode_switch.py"
       python -m unittest discover -s tests -p "test_backup.py"
       ```
    2. Kiểm tra `git status` xác nhận đang ở nhánh `feature/toggle-round-robin-account-switch` và khi chuẩn bị commit để push lên mở PR với tác giả (`JunMystery/antigravity-hub`), **chỉ** stage các file code & test (`proxy/`, `launcher/`, `tests/`), **không** commit thư mục `planning/`.

---

## 4. Conditional Quality Gates (Cấp Phase)

- **Security Gate**: `Passed` — Đã kiểm tra OAuth URL (`prompt=select_account+consent`) & `select` input validation (`200`/`404`) trong `T-002` và `T-004`.
- **Data Gate**: `Passed` — Đã kiểm tra đọc/ghi `profiles.json` & tương thích Backup/Restore qua `test_backup.py` (5/5 OK).
- **Accessibility Gate**: `Passed` — Đã kiểm tra `retranslate_ui()` EN/VI, tooltip và trạng thái disable/enable widget trong `T-005`, `T-007`.
- **Compatibility Gate**: `Passed` — Đã kiểm tra `columnCount() == 6`, Auto Quota độc lập và không phá vỡ API cũ của Proxy.

---

## 5. Phase Rollback (Cục bộ)

- Hoàn tác thay đổi test bằng lệnh:
  ```powershell
  git checkout -- tests/test_proxy_rotation.py
  Remove-Item -ErrorAction SilentlyContinue tests/test_account_mode_switch.py
  ```

---

## 6. Phase Verification & DoD Checklist

- **Pre-check (Phase DoR)**:
  - [x] Phase `P01` và `P02` đã đạt trạng thái `✅ Done`.
  - [x] Đã xác minh tồn tại `tests/test_proxy_rotation.py` và `tests/test_backup.py`.
- **Execution Verification (Mapped Test Checks)**:
  - Check ID: `T-001`, `T-002`, `T-003`, `T-004`, `T-005`, `T-006`, `T-007` (Map Section 7 Master).
  - Lệnh kiểm tra:
    ```powershell
    python -m unittest discover -s tests -p "test_proxy_rotation.py"
    python -m unittest discover -s tests -p "test_account_mode_switch.py"
    python -m unittest discover -s tests -p "test_backup.py"
    ```
  - Kết quả kỳ vọng: Tất cả test cases ở cả 3 suite PASS 100%, không có test bị skip ngoài ý muốn.
- **Post-check (Phase DoD)**:
  - [x] 100% Tasks (`P03.1`–`P03.3`) đã hoàn thành (`[x]`).
  - [x] Toàn bộ lệnh verification pass sau lần chỉnh sửa cuối cùng (11 + 3 + 5 = 19/19 OK; bổ sung `test_proxy_hang_remediation.py` 8/8, `test_activity_logs.py` 9/9, `test_log_manager.py` 5/5 OK).
  - [x] Đã đồng bộ cập nhật `Status` của Phase `P03` thành `✅ Done` và đánh dấu `AC-1`–`AC-7`, Section 10 DoD trong Master Plan thành `Pass`.
