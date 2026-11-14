# Antigravity Profile Launcher & Micro-Proxy

Hệ thống quản lý Profile và Micro-Proxy luân chuyển Round Robin đa tài khoản dành cho Google Antigravity IDE (Gemini Cloud Code).

---

## 1. Giới Thiệu & Tính Năng Nổi Bật

- **Quản lý đa tài khoản Google**: Thêm và liên kết không giới hạn tài khoản Google qua luồng xác thực Google OAuth 2.0 PKCE tự động và độc lập.
- **Micro-Proxy Round Robin tự động**:
  - Tự động luân chuyển tài khoản theo ngưỡng request tùy chỉnh (`requests_per_account`).
  - Cơ chế **Dedicated Per-Account HTTPS Agent**: Mỗi tài khoản sở hữu socket pool độc lập, cô lập 100% kết nối, ngăn ngừa rò rỉ session hoặc lẫn lộn dữ liệu giữa các tài khoản.
  - **Chống treo / nuốt request**: Xử lý stream an toàn, tự động ngắt và báo lỗi khi Google Cloud AI timeout hoặc gặp sự cố mạng, giải phóng client IDE ngay lập tức.
  - **Tự động phục hồi lỗi (Auto-Failover)**: Tự động cấp mới token khi gặp HTTP 401, tự động chuyển tài khoản kế tiếp khi gặp quota 429, 403 hoặc 404.
  - **Lưu lượt xoay vòng bền vững**: Lưu chính xác tài khoản đang dùng dở (`rotator_state.json`), mở lại launcher tiếp tục đúng lượt mà không dồn quota vào tài khoản đầu tiên.
- **Giám sát Quota Gemini**:
  - Hiển thị quota 5 giờ và hàng tuần dạng trực quan (Pill Pixbuf).
  - Tích hợp Toggle Switch bật/tắt tự động làm mới (5 phút) ngay trên tiêu đề cột Quota.
  - Hỗ trợ làm mới Quota cho toàn bộ tài khoản hoặc từng tài khoản đơn lẻ.
- **Hỗ trợ đa ngôn ngữ (i18n)**: Chuyển đổi linh hoạt giữa Tiếng Việt (VI) và Tiếng Anh (EN) tức thì qua Dropdown Box ở thanh tiêu đề mà không cần khởi động lại.

---

## 2. Cấu Trúc Thư Mục Dự Án

```
antigravity-launcher/
├── bin/
│   └── antigravity-launcher        # Entrypoint script khởi chạy
├── launcher/                       # Mã nguồn Launcher GUI & CLI (Python GTK3)
│   ├── main.py                     # Entrypoint Python
│   ├── launcher_window.py          # Cửa sổ chính GTK3
│   ├── launcher_layout.py          # Bố cục giao diện & CSS
│   ├── launcher_treeview.py        # Bảng danh sách tài khoản & Toggle Switch
│   ├── launcher_storage.py         # Quản lý cấu hình & đường dẫn động
│   ├── launcher_proxy.py           # Quản lý tiến trình proxy
│   ├── launcher_quota.py           # Bộ tạo đồ họa Quota Pill
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
│       └── .gitkeep
├── install.sh                      # Script cài đặt tự động 1 lệnh
├── requirements.txt                # Thư viện Python yêu cầu
└── README.md                       # Tài liệu hướng dẫn
```

---

## 3. Yêu Cầu Môi Trường

- **Hệ điều hành**: Linux (Ubuntu, Debian, Fedora, Arch Linux, v.v.).
- **Python**: Phiên bản 3.8 trở lên kèm `python3-gi`, `gir1.2-gtk-3.0`, `python3-cairo`.
- **Node.js**: Phiên bản 18 trở lên kèm `npm`.

### Cài đặt gói phụ thuộc trên Ubuntu / Debian:
```bash
sudo apt update
sudo apt install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 nodejs npm
```

### Cài đặt gói phụ thuộc trên Fedora:
```bash
sudo dnf install -y python3 python3-gobject gtk3 cairo-gobject nodejs npm
```

### Cài đặt gói phụ thuộc trên Arch Linux:
```bash
sudo pacman -S python python-gobject gtk3 python-cairo nodejs npm
```

---

## 4. Cài Đặt & Khởi Chạy

### Cách 1: Cài đặt tự động qua `install.sh`
```bash
git clone <URL_REPO_CUA_BAN> antigravity-launcher
cd antigravity-launcher
chmod +x install.sh
./install.sh
```

Sau khi cài đặt, bạn có thể khởi chạy bất kỳ lúc nào bằng lệnh:
```bash
antigravity-launcher
```

### Cách 2: Khởi chạy trực tiếp từ thư mục mã nguồn
```bash
# Cài đặt thư viện Node.js cho Micro-Proxy
cd proxy && npm install && cd ..

# Khởi chạy giao diện GUI
./bin/antigravity-launcher
```

---

## 5. Thao Tác Dòng Lệnh (CLI)

Launcher cung cấp đầy đủ các tùy chọn CLI để quản trị tự động:

```bash
# Xem trợ giúp dòng lệnh
antigravity-launcher --help

# Liệt kê danh sách tài khoản
antigravity-launcher --list

# Đăng nhập thêm tài khoản Google mới
antigravity-launcher --add-google

# Làm mới Quota cho toàn bộ tài khoản
antigravity-launcher --refresh-quota

# Đặt ngưỡng chuyển đổi tài khoản (ví dụ 5 request / tài khoản)
antigravity-launcher --requests-per-account 5

# Bật/Tắt tham gia Round Robin cho tài khoản
antigravity-launcher --toggle <ACCOUNT_EMAIL_OR_ID>

# Khởi chạy Antigravity IDE với tài khoản chỉ định
antigravity-launcher --launch <ACCOUNT_EMAIL_OR_ID>
```

---

## 6. Chính Sách Bảo Mật & Dữ Liệu Cá Nhân

- Repository này tuân thủ nguyên tắc **Bare-Bone**: Hoàn toàn **KHÔNG** chứa bất kỳ thông tin tài khoản, token đăng nhập, khóa bảo mật SSL hay dữ liệu người dùng nào.
- Khi người dùng đăng nhập tài khoản Google của chính họ, toàn bộ token và thông tin profile được lưu trữ cục bộ tại thư mục cấu hình cá nhân `~/.config/antigravity-launcher/` trên máy người dùng và được loại trừ trong `.gitignore`.
- Chứng chỉ SSL CA dùng cho Micro-Proxy được tự động sinh ngẫu nhiên trên máy của mỗi người dùng trong lần khởi động đầu tiên, đảm bảo an toàn tuyệt đối.
