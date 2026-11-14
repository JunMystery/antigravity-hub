# Antigravity Profile Launcher & Micro-Proxy (Cross-Platform)

Hệ thống quản lý Profile và Micro-Proxy luân chuyển Round Robin đa tài khoản dành cho Google Antigravity IDE (Gemini Cloud Code). Hỗ trợ đầy đủ đa nền tảng **Windows** và **Linux** với giao diện **PyQt6** hiện đại.

---

## 1. Tính Năng Nổi Bật

- **Đa nền tảng thực sự (Windows & Linux)**: Sử dụng PyQt6 thống nhất, loại bỏ sự phụ thuộc vào thư viện GTK3 phức tạp trên Windows. Người dùng chỉ cần cài đặt bằng `pip`.
- **Quản lý đa tài khoản Google**: Thêm và liên kết không giới hạn tài khoản Google qua luồng xác thực Google OAuth 2.0 PKCE tự động.
- **Micro-Proxy Round Robin tự động**:
  - Tự động luân chuyển tài khoản theo ngưỡng request tùy chỉnh (`requests_per_account`).
  - **Dedicated Per-Account HTTPS Agent**: Mỗi tài khoản sở hữu socket pool độc lập, cô lập 100% kết nối, ngăn ngừa rò rỉ session giữa các tài khoản.
  - **Chống treo / nuốt request**: Xử lý stream an toàn, tự động ngắt và báo lỗi khi Google Cloud AI timeout hoặc gặp sự cố mạng, giải phóng client IDE ngay lập tức.
  - **Tự động phục hồi lỗi (Auto-Failover)**: Tự động cấp mới token khi gặp HTTP 401, tự động chuyển tài khoản kế tiếp khi gặp quota 429, 403 hoặc 404.
  - **Lưu lượt xoay vòng bền vững**: Lưu chính xác tài khoản đang dùng dở (`rotator_state.json`), mở lại launcher tiếp tục đúng lượt mà không dồn quota vào tài khoản đầu tiên.
- **Giám sát Quota Gemini**:
  - Hiển thị quota 5 giờ và hàng tuần dạng trực quan.
  - Tích hợp Toggle Switch bật/tắt tự động làm mới (5 phút) ngay trên thanh Quota.
  - Hỗ trợ làm mới Quota cho toàn bộ tài khoản hoặc từng tài khoản đơn lẻ.
- **Hỗ trợ đa ngôn ngữ (i18n)**: Chuyển đổi linh hoạt giữa Tiếng Việt (VI) và Tiếng Anh (EN) tức thì qua Dropdown Box ở thanh tiêu đề.

---

## 2. Cấu Trúc Thư Mục Dự Án

```
antigravity-launcher/
├── launcher/                       # Mã nguồn Launcher GUI & CLI (Python PyQt6)
│   ├── main.py                     # Entrypoint Python
│   ├── launcher_window.py          # Cửa sổ chính PyQt6
│   ├── launcher_layout.py          # Bố cục giao diện & QSS styling
│   ├── launcher_treeview.py        # Bảng danh sách tài khoản & Quota
│   ├── launcher_storage.py         # Quản lý cấu hình & đường dẫn đa nền tảng
│   ├── launcher_proxy.py           # Quản lý tiến trình proxy (taskkill / killpg)
│   ├── launcher_quota.py           # Bộ tạo đồ họa Quota Pill PyQt6
│   ├── launcher_quota_fetcher.py   # Truy vấn quota Google Cloud
│   ├── launcher_quota_runner.py    # Điều phối quét quota ngầm
│   ├── launcher_monitor.py         # Khung giám sát live monitor
│   ├── launcher_oauth.py           # Đăng nhập Google OAuth PKCE
│   ├── launcher_cli.py             # Giao diện dòng lệnh (CLI)
│   ├── launcher_i18n.py            # Hệ thống đa ngôn ngữ
│   └── locales/
│       ├── en.json                 # Từ điển tiếng Anh
│       └── vi.json                 # Từ điển tiếng Việt
├── proxy/                          # Mã nguồn Micro-Proxy độc lập (Node.js)
│   ├── index.js                    # Entrypoint proxy & TLS MITM
│   ├── chat_handler.js             # Xử lý streaming & failover
│   ├── account_rotator.js          # Quản lý xoay vòng & lưu trạng thái
│   ├── agent_pool.js               # Dedicated per-account agent pool
│   ├── token_manager.js            # Quản lý access token & refresh
│   ├── oauth_handler.js            # Xử lý callback OAuth
│   ├── oauth_flow.js               # Trao đổi mã code lấy token
│   ├── cert_provider.js            # Khởi tạo chứng chỉ SSL nội bộ
│   ├── package.json
│   └── certs/
├── setup.bat                       # Script cài đặt tự động cho Windows
├── launch.bat                      # Script khởi chạy nhanh cho Windows
├── setup.sh                        # Script cài đặt tự động cho Linux
├── launch.sh                       # Script khởi chạy nhanh cho Linux
├── requirements.txt                # Thư viện Python yêu cầu (PyQt6, requests)
└── README.md                       # Tài liệu hướng dẫn
```

---

## 3. Cài Đặt & Khởi Chạy

### Yêu cầu tiên quyết:
- **Python**: Phiên bản 3.8 trở lên.
- **Node.js**: Phiên bản 18 LTS trở lên.

### Trên Windows:
1. Nhấp đúp vào tệp **`setup.bat`** để tự động kiểm tra môi trường và cài đặt các thư viện Python, Node.js.
2. Nhấp đúp vào tệp **`launch.bat`** để khởi chạy Launcher.

### Trên Linux:
1. Mở terminal và chạy lệnh cài đặt:
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

Launcher cung cấp đầy đủ các tùy chọn CLI để quản trị tự động:

```bash
# Xem trợ giúp dòng lệnh
python launcher/main.py --help

# Liệt kê danh sách tài khoản
python launcher/main.py --list

# Đăng nhập thêm tài khoản Google mới
python launcher/main.py --add-google

# Làm mới Quota cho toàn bộ tài khoản
python launcher/main.py --refresh-quota

# Đặt ngưỡng chuyển đổi tài khoản (ví dụ 5 request / tài khoản)
python launcher/main.py --requests-per-account 5

# Bật/Tắt tham gia Round Robin cho tài khoản
python launcher/main.py --toggle <ACCOUNT_EMAIL_OR_ID>

# Khởi chạy Antigravity IDE với tài khoản chỉ định
python launcher/main.py --launch <ACCOUNT_EMAIL_OR_ID>
```

---

## 5. Chính Sách Bảo Mật & Dữ Liệu Cá Nhân

- Repository này tuân thủ nguyên tắc **Bare-Bone**: Hoàn toàn **KHÔNG** chứa bất kỳ thông tin tài khoản, token đăng nhập, khóa bảo mật SSL hay dữ liệu người dùng nào.
- Khi người dùng đăng nhập tài khoản Google của chính họ, toàn bộ token và thông tin profile được lưu trữ an toàn tại thư mục cấu hình cục bộ của người dùng (`%APPDATA%\antigravity-launcher\` trên Windows hoặc `~/.config/antigravity-launcher/` trên Linux).
- Chứng chỉ SSL CA dùng cho Micro-Proxy được tự động sinh ngẫu nhiên trên máy của mỗi người dùng trong lần khởi động đầu tiên, đảm bảo an toàn tuyệt đối.
