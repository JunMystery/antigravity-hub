# Phase P02: Nâng cấp PyQt6 Launcher UI (Toggle Round Robin & Account Switcher)

## 1. Phase Metadata

| Field | Value |
| :--- | :--- |
| **Phase ID** | `P02` |
| **Parent Task ID** | `TASK-20261119-001` |
| **Master Plan** | `../TASK_TOGGLE_ROUND_ROBIN_SWITCH_ACCOUNT.md` |
| **Status** | ✅ Done |
| **Depends on** | `P01` (bắt buộc `P01` đã `✅ Done`) |
| **Lifecycle Owner** | Worker |

---

## 2. Target File Impact (Trích xuất từ Section 4 Master)

| Action | File path | Target Symbol/Area | Reason | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| Edit | `launcher/launcher_storage.py` | `load_data` | Thêm default `auto_rotation_enabled: True` & `active_account_id: ""`; giữ nguyên `round_robin_enabled` cho Auto Quota | `Confirmed` |
| Edit | `launcher/launcher_monitor.py` | `send_proxy_cmd` | Hỗ trợ truyền `params: dict` (encode query string và ghi payload vào `CMD_FILE`) | `Confirmed` |
| Edit | `launcher/launcher_view_accounts.py` | `AccountsView`, `retranslate_ui` | Thêm nút `btn_use_account` (Action Bar) và `ToggleSwitch` `toggle_round_robin` (Bottom Bar), giữ nguyên bảng 6 cột | `Confirmed` |
| Edit | `launcher/launcher_view_dashboard.py` | `DashboardView`, `update_dashboard`, `retranslate_ui` | Thêm dropdown `combo_active_account` chọn đích danh TK trên Dashboard và đồng bộ với `live_status.json` | `Confirmed` |
| Edit | `launcher/launcher_window.py` | `LauncherWindow` | Xử lý bật/tắt Round Robin 2 chiều, chọn TK active, đồng bộ selector và sửa `_launch_target` dùng `active_account_id` | `Confirmed` |
| Edit | `launcher/launcher_oauth.py` | `start_google_oauth_flow` | Cập nhật selector tài khoản active sau khi đăng nhập thêm tài khoản Google | `Confirmed` |
| Edit | `launcher/launcher_theme.py` | `LAUNCHER_QSS` | Định nghĩa QSS tách riêng cho `#combo_active_account`, `#btn_use_account`, `#lbl_active_acc` | `Confirmed` |
| Edit | `launcher/locales/vi.json` | i18n VI | Bổ sung key tiếng Việt cho toggle Round Robin, nút Chọn dùng và dropdown Dashboard | `Confirmed` |
| Edit | `launcher/locales/en.json` | i18n EN | Bổ sung key tiếng Anh tương ứng | `Confirmed` |
| Edit | `launcher/launcher_i18n.py` | `_FALLBACK_DEFAULTS` | Bổ sung key fallback VI/EN cho các nhãn mới | `Confirmed` |

---

## 3. Tasks Breakdown

- [x] **Task P02.1**: Bổ sung cài đặt mặc định `auto_rotation_enabled` và `active_account_id` trong `launcher_storage.py`
  - File: `launcher/launcher_storage.py`
  - Chi tiết: Trong `load_data()` (tất cả 3 nhánh: tạo mới, load file, fallback `except`), thêm `"auto_rotation_enabled": True` và `"active_account_id": ""`. Tuyệt đối không sửa ý nghĩa của `"round_robin_enabled"` (đang dùng cho Auto Refresh Quota).
  - Code snippet minh họa:
    ```python
    data["settings"].setdefault("auto_rotation_enabled", True)
    data["settings"].setdefault("active_account_id", "")
    ```

- [x] **Task P02.2**: Mở rộng `send_proxy_cmd()` hỗ trợ tham số `params`
  - File: `launcher/launcher_monitor.py`
  - Chi tiết: Import `urllib.parse`, nâng cấp `send_proxy_cmd(win, cmd: str, params: dict = None) -> bool` để encode query parameters vào `/_proxy_action` và merge `params` vào JSON ghi ra `CMD_FILE` khi Proxy chưa phản hồi HTTP.
  - Code snippet minh họa:
    ```python
    def send_proxy_cmd(win, cmd: str, params: dict = None) -> bool:
        """Gửi lệnh điều khiển trực tiếp tới Micro-Proxy qua HTTP hoặc tệp trung gian."""
        query = {"cmd": cmd}
        if isinstance(params, dict):
            for k, v in params.items():
                if v is not None and v != "":
                    query[k] = v

        sent = False
        try:
            qs = urllib.parse.urlencode(query)
            url = f"http://127.0.0.1:{PROXY_PORT}/_proxy_action?{qs}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=0.25) as resp:
                if resp.status == 200:
                    sent = True
        except Exception:
            sent = False

        if not sent:
            try:
                payload = dict(query)
                payload["ts"] = time.time()
                with open(CMD_FILE, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
            except Exception:
                pass
        return sent
    ```

- [x] **Task P02.3**: Cập nhật `AccountsView` thêm nút `Chọn dùng` và công tắc `ToggleSwitch` tắt/bật Round Robin
  - File: `launcher/launcher_view_accounts.py`
  - Chi tiết:
    1. Action Bar: thêm `self.btn_use_account = QPushButton(tr("btn.use_account"))`, đặt `setObjectName("btn_use_account")`, tooltip `tr("tooltip.use_account")`, nối `clicked` → `self.win.on_use_selected_account`, gán `self.win.btn_use_account = self.btn_use_account`. Giữ nguyên bảng `treeview` **6 cột**.
    2. Bottom Bar (`opt_bar`): import `ToggleSwitch` từ `launcher_toggle_switch`, thêm `self.toggle_round_robin = ToggleSwitch(checked=auto_rot, parent=self)` (`setObjectName("toggle_round_robin")`) trước `self.rr_info`, nối `toggled` → `self.win.on_toggle_round_robin`. Cập nhật `self.spin_reqs.setEnabled(auto_rot)` và nhãn `self.rr_info` theo trạng thái bật/tắt (`tr("opt.mode")` vs `tr("opt.mode_fixed")`). Gán `self.win.toggle_round_robin = self.toggle_round_robin`.
    3. Cập nhật `retranslate_ui()` cho `btn_use_account`, `toggle_round_robin` tooltip và `rr_info`.
  - Code snippet minh họa:
    ```python
    self.btn_use_account = QPushButton(tr("btn.use_account"))
    self.btn_use_account.setObjectName("btn_use_account")
    self.btn_use_account.setToolTip(tr("tooltip.use_account"))
    self.btn_use_account.clicked.connect(self.win.on_use_selected_account)
    act_bar.addWidget(self.btn_use_account)
    ```
    ```python
    auto_rot = self.win.data.get("settings", {}).get("auto_rotation_enabled", True)
    self.toggle_round_robin = ToggleSwitch(checked=auto_rot, parent=self)
    self.toggle_round_robin.setObjectName("toggle_round_robin")
    self.toggle_round_robin.setToolTip(
        tr("tooltip.toggle_round_robin_on") if auto_rot else tr("tooltip.toggle_round_robin_off")
    )
    self.toggle_round_robin.toggled.connect(self.win.on_toggle_round_robin)
    opt_bar.addWidget(self.toggle_round_robin)

    self.rr_info = QLabel(tr("opt.mode") if auto_rot else tr("opt.mode_fixed"))
    opt_bar.addWidget(self.rr_info)
    ```

- [x] **Task P02.4**: Cập nhật `DashboardView` thêm Dropdown chọn nhanh tài khoản đang dùng
  - File: `launcher/launcher_view_dashboard.py`
  - Chi tiết:
    1. Import `QComboBox`, `QSizePolicy` (đã có `QSizePolicy`). Tạo hàng điều khiển gọn ngay dưới `status_bar`: `self.lbl_active_acc = QLabel(tr("dashboard.active_account_label"))` (`setObjectName("lbl_active_acc")`) và `self.combo_active_account = QComboBox()` (`setObjectName("combo_active_account")`, `setFixedHeight(30)`), nối `currentIndexChanged` → `self.win.on_dashboard_account_changed`. Gắn `self.win.combo_active_account = self.combo_active_account`.
    2. Cập nhật `retranslate_ui()` đổi text `lbl_active_acc` (giữ nguyên toàn bộ text/objectName của `btn_launch_app`, `btn_launch_ide`, `btn_next`, `btn_toggle_proxy`).
    3. Trong `update_dashboard()`: khi đọc được `acc` (`account_email`) hợp lệ từ `live_status.json`, đồng bộ selection hiển thị của `combo_active_account` (dùng `blockSignals(True/False)` để tránh kích hoạt lại sự kiện đổi tài khoản).
  - Code snippet minh họa:
    ```python
    acc_switch_bar = QHBoxLayout()
    acc_switch_bar.setSpacing(8)
    self.lbl_active_acc = QLabel(tr("dashboard.active_account_label"))
    self.lbl_active_acc.setObjectName("lbl_active_acc")
    acc_switch_bar.addWidget(self.lbl_active_acc)

    self.combo_active_account = QComboBox()
    self.combo_active_account.setObjectName("combo_active_account")
    self.combo_active_account.setFixedHeight(30)
    self.combo_active_account.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.combo_active_account.currentIndexChanged.connect(self.win.on_dashboard_account_changed)
    acc_switch_bar.addWidget(self.combo_active_account, 1)
    layout.addLayout(acc_switch_bar)
    ```

- [x] **Task P02.5**: Triển khai điều phối 2 chiều & chọn profile launch trong `LauncherWindow` và `launcher_oauth.py`
  - File: `launcher/launcher_window.py`, `launcher/launcher_oauth.py`
  - Chi tiết:
    1. Thêm `on_toggle_round_robin(self, enabled: bool)`: lưu `settings["auto_rotation_enabled"] = bool(enabled)`, cập nhật `spin_reqs.setEnabled(enabled)`, nhãn `rr_info`, tooltip `toggle_round_robin`, gửi `send_proxy_cmd(self, "resume" if enabled else "pause")` nếu proxy đang chạy, gọi `update_live_monitor()`.
    2. Cập nhật `on_toggle_proxy_btn(self)`: khi proxy đang chạy, gửi `toggle_pause`, đọc trạng thái mới (hoặc đảo từ `auto_rotation_enabled` hiện tại) để đồng bộ ngược lại `toggle_round_robin` (với `blockSignals(True)`), `spin_reqs`, `rr_info` và lưu `profiles.json`.
    3. Thêm `_sync_active_account_ui(self)` nạp danh sách `profiles` vào `combo_active_account` (hiển thị `email` kèm trạng thái `[OFF]` nếu đang disable, `userData = profile.get("id")`), chọn đúng item theo `settings["active_account_id"]`.
    4. Thêm `on_select_active_account(self, profile_id: str)`:
       - Tìm `profile` khớp `profile_id`; nếu `not profile` thì thoát an toàn.
       - Nếu `not profile.get("enabled", True)`: bật `profile["enabled"] = True` và lưu + gửi `send_proxy_cmd(self, "reload")` trước.
       - Lưu `settings["active_account_id"] = profile.get("id")`, gọi `send_proxy_cmd(self, "select", {"target": profile.get("email") or profile.get("id")})`, đồng bộ selection trên bảng `treeview` và `combo_active_account`, cập nhật `lbl_info`.
    5. Thêm `on_use_selected_account(self)` (lấy `self._get_selected()` rồi gọi `on_select_active_account`) và `on_dashboard_account_changed(self, idx)` (lấy `combo_active_account.itemData(idx)` rồi gọi `on_select_active_account`).
    6. Cập nhật `_launch_target`: tìm `active_id = self.data.get("settings", {}).get("active_account_id")`, ưu tiên profile khớp `active_id`, fallback `self._get_selected()`, rồi `profiles[0]`.
    7. Gọi `self._sync_active_account_ui()` trong `_refresh_list()`, `on_account_toggled()`, `on_delete_account()`, và gọi trong `launcher/launcher_oauth.py` sau `parent_window._refresh_list()` (khi thêm tài khoản xong, nếu chưa có `active_account_id` hoặc người dùng vừa thêm tài khoản mới thì cập nhật UI selector).

- [x] **Task P02.6**: Bổ sung QSS tách riêng và khóa ngôn ngữ song ngữ VI/EN
  - File: `launcher/launcher_theme.py`, `launcher/locales/vi.json`, `launcher/locales/en.json`, `launcher/launcher_i18n.py`
  - Chi tiết:
    1. Trong `launcher_theme.py`, thêm rule QSS cho `QComboBox#combo_active_account`, `QPushButton#btn_use_account`, `QLabel#lbl_active_acc` theo bảng màu Catppuccin Mocha (`#24273a`, `#313244`, `#45475a`, `#89b4fa`, `#cdd6f4`).
    2. Trong `vi.json`, `en.json`, `launcher_i18n.py`, bổ sung đủ các key mới:
       - `opt.mode_fixed`
       - `tooltip.toggle_round_robin_on`, `tooltip.toggle_round_robin_off`
       - `btn.use_account`, `tooltip.use_account`
       - `dashboard.active_account_label`, `dashboard.no_active_account`
       - `msg.account_switched`

---

## 4. Conditional Quality Gates (Cấp Phase)

- **Security Gate**: `Not applicable` — UI desktop cục bộ, không lưu thông tin nhạy cảm mới.
- **Data Gate**: `Passed` — Cài đặt mới (`auto_rotation_enabled`, `active_account_id`) đều có giá trị mặc định an toàn trong `load_data()`, tương thích file backup cũ khi Restore.
- **Accessibility Gate**: `Passed` — Nút và dropdown mới có chiều cao >= 28–30px, tooltip mô tả rõ bằng VI/EN, contrast chuẩn Dark Theme, hỗ trợ `retranslate_ui()`.
- **Compatibility Gate**: `Passed` — Bảo toàn 100% bảng 6 cột (`columnCount() == 6`) và không thay đổi key `round_robin_enabled` của Auto Quota.

---

## 5. Phase Rollback (Cục bộ)

- Hoàn tác toàn bộ chỉnh sửa của Phase P02 bằng lệnh:
  ```powershell
  git checkout -- launcher/
  ```

---

## 6. Phase Verification & DoD Checklist

- **Pre-check (Phase DoR)**:
  - [x] Phase `P01` đạt trạng thái `✅ Done`.
  - [x] Đã xác minh tồn tại toàn bộ 10 target files trong `launcher/`.
- **Execution Verification (Mapped Test Checks)**:
  - Check ID: `T-005`, `T-006`, `T-007` (Map Section 7 Master).
  - Lệnh kiểm tra nhanh syntax sau khi edit Phase P02:
    ```powershell
    python -m py_compile launcher/*.py
    ```
  - Chạy bộ test GUI đầy đủ ở Phase `P03`.
- **Post-check (Phase DoD)**:
  - [x] 100% Tasks (`P02.1`–`P02.6`) đã hoàn thành (`[x]`).
  - [x] `py_compile` pass 0 lỗi, không có inline style mới ngoài `launcher_theme.py`.
  - [x] Đã đồng bộ cập nhật `Status` của Phase `P02` tại Section 6 Master Plan thành `✅ Done`.
