# Antigravity Profile Launcher & Micro-Proxy (Cross-Platform)

Hệ thống quản lý Profile và Transparent Micro-Proxy luân chuyển Round Robin đa tài khoản dành cho **Antigravity App (Agentic 2.0)** và **Antigravity IDE (Gemini Cloud Code)**. Hỗ trợ đầy đủ đa nền tảng **Windows** và **Linux** với giao diện **PyQt6** hiện đại theo bảng màu **Catppuccin Mocha Dark**.

---

## 1. Tính Năng Nổi Bật

### 1.1. Giao Diện Người Dùng Hiện Đại (PyQt6 & Catppuccin Mocha)
- **Kiến trúc điều hướng Sidebar (3 Chuyên mục)**:
  - **Dashboard**: Thanh trạng thái liền khối (CompactStatusBar), nút khởi chạy nhanh phân nhóm màu sắc rõ ràng (`Khởi chạy App (2.0)` xanh pastel, `Khởi chạy IDE` tím pastel), điều khiển luân chuyển Proxy (`Kế tiếp`, `Tạm dừng/Tiếp tục`) và luồng hoạt động trực tiếp (Live Activity Stream).
  - **Tài khoản (Accounts)**: Quản lý danh sách tài khoản Google, công tắc Bật/Tắt (iOS Toggle Switch), điều chỉnh thứ tự ưu tiên (Micro-Stepper ▲/▼ kèm nhập trực tiếp), giám sát hạn mức Quota (5h / Tuần) với hiệu ứng Braille góc vuông (`⠋`, `⠙`, `⠴`, `⠦`), và chế độ tự động quét định kỳ (Auto: ON/OFF - 5 phút).
  - **Cài đặt (Settings)**: Tự động dò tìm hoặc duyệt chọn đường dẫn App/IDE, tạo Shortcut Desktop, mở nhanh thư mục dữ liệu hệ thống, cấu hình thời gian lưu giữ log (7, 30, 90 ngày) tự động dọn dẹp và nút xóa trắng log an toàn.
- **Header Liền Khối 3 Phân Vùng Tinh Tế**: Gộp trạng thái kết nối, địa chỉ email tài khoản đang hoạt động và số lượt phục vụ vào một khối duy nhất, loại bỏ hiện tượng nhảy kích thước thẻ khi email thay đổi độ dài.
- **Bảng Nhật Ký Hoạt Động Tinh Gọn (Activity Stream)**: Hiển thị 1 bảng duy nhất, duy trì 20 request HTTP thật gần nhất (`POST streamGenerateContent → email`, `Refresh Token → email [OK]`), tự động lọc bỏ các banner và dòng kẻ phân cách hệ thống.
- **Hỗ trợ Đa Ngôn ngữ (i18n)**: Chuyển đổi linh hoạt và tức thì giữa Tiếng Việt (VI) và Tiếng Anh (EN) qua Dropdown Box ở góc dưới Sidebar.

### 1.2. Micro-Proxy Round Robin Độc Lập (Port 20130)
- **Tự động luân chuyển tài khoản**: Luân chuyển tài khoản mượt mà theo ngưỡng cấu hình (`requests_per_account`), tự động lưu vết trạng thái xoay vòng vào `rotator_state.json` và nối tiếp chính xác lượt phục vụ khi khởi động lại (`[ROTATOR-RESTORE]`).
- **Dedicated Per-Account HTTPS Agent Pool**: Mỗi tài khoản sở hữu socket pool độc lập, cô lập kết nối 100%, tái sử dụng socket qua `keepAlive: 15s`, ngăn ngừa hoàn toàn hiện tượng rò rỉ session giữa các tài khoản.
- **Hỗ trợ Mô hình Suy luận Chuyên sâu (Extended Thinking)**: Tối ưu Time-To-First-Byte (TTFB) timeout lên đến 120 giây và sliding window 45 giây giữa các chunk SSE, loại bỏ tình trạng ngắt kết nối sớm khi Gemini 2.0 Flash Thinking / Extended Thinking tính toán chuỗi suy luận dài.
- **Tự Động Phục Hồi Lỗi (Auto-Failover) & Anti-Thundering Herd**:
  - Tự động cấp mới Token khi gặp HTTP 401; cơ chế deduplication ngăn chặn các request song song gửi đồng thời dẫn đến lỗi `invalid_grant`.
  - Tự động chuyển tài khoản tiếp theo khi tài khoản hiện tại cạn quota (HTTP 429) hoặc lỗi quyền (HTTP 403).
- **Tuân thủ Chuẩn HTTP RFC 7230 §3.3.2 / RFC 9112 §6.1**: Tự động dọn dẹp tiêu đề `transfer-encoding` khi request đã có `content-length`, ngăn ngừa lỗi HTTP 400 Bad Request từ Google Frontend (GFE).

### 1.3. Bảo Mật & Mã Hóa Dữ Liệu Đa Tầng
- **Envelope Encryption AES-256-GCM**: Toàn bộ Access Token và Refresh Token được mã hóa an toàn với tiền tố `enc:v2:`.
- **Tích hợp OS Keyring & Fallback Machine-GUID**: Tự động lưu khóa mã hóa vào hệ thống bảo mật phần cứng OS Keyring (Linux Secret Service / Windows Credential Manager). Khi chạy trong môi trường không có GUI keyring (headless/server), hệ thống tự động fallback sang khóa máy tính duy nhất (Machine-GUID PBKDF2 với 100.000 vòng lặp).

---

## 2. Cấu Trúc Thư Mục Dự Án

```
antigravity-launcher/
├── launcher/                           # Mã nguồn Launcher GUI & CLI (Python PyQt6)
│   ├── main.py                         # Entrypoint ứng dụng Python
│   ├── launcher_window.py              # Cửa sổ chính điều phối Sidebar & Views
│   ├── launcher_sidebar.py             # Thanh điều hướng Sidebar hiện đại
│   ├── launcher_view_dashboard.py      # View Tổng quan: Trạng thái & Live Activity Stream
│   ├── launcher_view_accounts.py       # View Quản lý Tài khoản & Quota
│   ├── launcher_view_settings.py       # View Cài đặt: Đường dẫn, Log retention & Shortcut
│   ├── launcher_widget.py              # Thành phần UI dùng chung (CompactStatusBar, NavButton, SettingRow)
│   ├── launcher_activity_widget.py     # Bảng nhật ký hoạt động tinh gọn 1 bảng (20 requests cap)
│   ├── launcher_treeview.py            # Quản lý bảng danh sách tài khoản
│   ├── launcher_treeview_updater.py    # Điều phối cập nhật Quota, reorder & spinner
│   ├── launcher_order_widget.py        # Widget ô thứ tự tích hợp Micro-Stepper ▲/▼
│   ├── launcher_toggle_switch.py       # Công tắc Bật/Tắt tròn chuẩn iOS (ToggleSwitch)
│   ├── launcher_theme.py               # Bảng phong cách QSS Catppuccin Mocha Dark
│   ├── launcher_storage.py             # Quản lý lưu trữ profiles, accounts và cấu hình
│   ├── launcher_paths.py               # Quản lý đường dẫn đa nền tảng & chứng chỉ Root CA
│   ├── launcher_crypto.py              # Mã hóa AES-256-GCM & cơ chế Envelope v2
│   ├── launcher_keyring.py             # Tích hợp OS Keyring & fallback Machine-GUID
│   ├── launcher_log_manager.py         # Quản lý nhật ký, retention (7/30/90 ngày) & pruning
│   ├── launcher_proxy.py               # Quản lý vòng đời tiến trình Node.js proxy
│   ├── launcher_quota_fetcher.py       # Truy vấn hạn mức Quota từ Google Cloud AI API
│   ├── launcher_quota_runner.py        # Quét Quota ngầm đa luồng & animation Braille góc vuông
│   ├── launcher_oauth.py               # Luồng đăng nhập Google OAuth 2.0 PKCE
│   ├── launcher_cli.py                 # Giao diện dòng lệnh CLI quản trị tự động
│   ├── launcher_shortcut.py            # Tạo Shortcut Desktop đa nền tảng
│   ├── launcher_i18n.py                # Hệ thống dịch thuật & bản địa hóa ngôn ngữ
│   └── locales/
│       ├── en.json                     # Từ điển bản ngữ Tiếng Anh
│       └── vi.json                     # Từ điển bản ngữ Tiếng Việt
├── proxy/                              # Mã nguồn Micro-Proxy độc lập (Node.js)
│   ├── index.js                        # Master listener (Port 20130), PAC routing & TLS MITM
│   ├── chat_handler.js                 # Chuyển tiếp request, xử lý SSE stream & failover
│   ├── chat_payload_helper.js          # Phân loại endpoint, chuẩn hóa payload & project ID
│   ├── account_rotator.js              # Thuật toán Round-Robin, tính toán lượt & hạn mức
│   ├── rotator_persistence.js          # Lưu trữ bền vững trạng thái con trỏ xoay vòng
│   ├── session_affinity.js             # Quản lý Subagent & sticky session binding
│   ├── agent_pool.js                   # Dedicated per-account HTTPS Agent pool
│   ├── socket_cleanup.js               # Xử lý đóng socket an toàn & chống unhandled stream error
│   ├── token_manager.js                # Tự động refresh token, chống thundering herd
│   ├── cert_provider.js                # Khởi tạo chứng chỉ Root CA & Leaf đầy đủ TLS chain
│   ├── package.json
│   └── certs/                         # Thư mục lưu trữ chứng chỉ SSL cục bộ
├── tests/                              # Bộ kiểm thử tự động (42 Unit Tests)
│   ├── test_crypto.py                  # Kiểm tra mã hóa AES-256 & OS Keyring
│   ├── test_log_manager.py             # Kiểm tra log retention, pruning & parsing
│   ├── test_activity_logs.py           # Kiểm tra bảng activity stream & 20-item cap
│   ├── test_quota_display.py           # Kiểm tra hiển thị Quota & Braille square animation
│   ├── test_remediations.py            # Kiểm tra các bản vá proxy & token refresh
│   └── test_view_navigation.py         # Kiểm tra điều hướng Sidebar, Settings & Views
├── setup.bat                           # Script cài đặt tự động cho Windows
├── launch.bat                          # Script khởi chạy nhanh cho Windows
├── setup.sh                            # Script cài đặt tự động cho Linux
├── launch.sh                           # Script khởi chạy nhanh cho Linux
├── requirements.txt                    # Thư viện Python phụ thuộc (PyQt6, requests, cryptography, keyring)
├── AUDIT_REPORT.md                     # Báo cáo kiểm định kỹ thuật chuyên sâu
└── README.md                           # Tài liệu hướng dẫn sử dụng
```

---

## 3. Cài Đặt & Khởi Chạy

### Yêu cầu hệ thống:
- **Python**: Phiên bản 3.10 trở lên.
- **Node.js**: Phiên bản 18 LTS trở lên.

### Trên Windows:
1. Nhấp đúp vào tệp **`setup.bat`** để tự động cài đặt các gói phụ thuộc Python và Node.js.
2. Nhấp đúp vào tệp **`launch.bat`** để mở Launcher.

### Trên Linux:
1. Cấp quyền thực thi và cài đặt:
   ```bash
   chmod +x setup.sh launch.sh
   ./setup.sh
   ```
2. Khởi chạy Launcher:
   ```bash
   ./launch.sh
   ```

---

## 4. Thao Tác Dòng Lệnh (CLI)

Launcher hỗ trợ đầy đủ các lệnh CLI để quản lý mà không cần mở giao diện đồ họa:

```bash
# Xem trợ giúp dòng lệnh
python3 launcher/main.py --help

# Liệt kê danh sách tài khoản kèm trạng thái và quota
python3 launcher/main.py --list

# Đăng nhập thêm tài khoản Google mới qua OAuth PKCE
python3 launcher/main.py --add-google

# Quét và cập nhật Quota toàn bộ tài khoản
python3 launcher/main.py --refresh-quota

# Đặt ngưỡng chuyển đổi tài khoản (ví dụ 10 request / tài khoản)
python3 launcher/main.py --requests-per-account 10

# Bật hoặc Tắt tham gia xoay vòng cho một tài khoản
python3 launcher/main.py --toggle <ACCOUNT_EMAIL_OR_ID>

# Khởi chạy Antigravity App (2.0) hoặc IDE với cấu hình proxy
python3 launcher/main.py --launch <ACCOUNT_EMAIL_OR_ID>
```

---

## 5. Kiểm Thử Hệ Thống (Automated Testing)

Dự án tích hợp bộ kiểm thử tự động toàn diện bao phủ toàn bộ chức năng từ mã hóa, proxy đến giao diện PyQt6:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```
*Kết quả: 42/42 tests PASS 100%.*

---

## 6. Chính Sách Bảo Mật & Dữ Liệu

- **Nguyên tắc Bare-Bone**: Mã nguồn repository hoàn toàn **KHÔNG** chứa bất kỳ token, cookie, khóa riêng tư hay thông tin cá nhân nào.
- **Lưu trữ Cục bộ Bảo mật**: Thông tin tài khoản được lưu trữ tại thư mục cục bộ của người dùng (`%APPDATA%\antigravity-launcher\` trên Windows hoặc `~/.config/antigravity-launcher/` trên Linux) với phân quyền truy cập nghiêm ngặt (`0o600`).
- **Mã hóa Khóa phần cứng**: Token luôn được mã hóa hai lớp trước khi ghi xuống đĩa, bảo vệ an toàn ngay cả khi tệp cấu hình bị sao chép trái phép.

