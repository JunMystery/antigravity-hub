#!/usr/bin/env bash
# Script cài đặt tự động Antigravity Launcher & Micro-Proxy
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TARGET_BIN_DIR="${HOME}/.local/bin"

echo "=== Cài đặt Antigravity Launcher & Micro-Proxy ==="

# 1. Kiểm tra môi trường yêu cầu
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] Cần cài đặt python3 trước."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[ERROR] Cần cài đặt nodejs (v18+) trước."; exit 1; }

# 2. Cài đặt dependencies cho Micro-Proxy và Python Launcher
echo "[1/6] Cài đặt dependencies cho Micro-Proxy (Node.js)..."
cd "${SCRIPT_DIR}/proxy"
if [ -f "package.json" ]; then
    npm install --silent --no-audit --no-fund || npm install
fi
cd "${SCRIPT_DIR}"

echo "[2/6] Cài đặt phụ thuộc Python (PyQt6, requests, cryptography, keyring)..."
pip install --break-system-packages -r "${SCRIPT_DIR}/requirements.txt" 2>/dev/null || pip install -r "${SCRIPT_DIR}/requirements.txt" 2>/dev/null || true

# 3. Tạo thư mục cấu hình chuẩn
echo "[3/6] Khởi tạo thư mục cấu hình ~/.config/antigravity-launcher..."
mkdir -p "${HOME}/.config/antigravity-launcher"
mkdir -p "${HOME}/.config/Antigravity-Profiles"
mkdir -p "${TARGET_BIN_DIR}"

# 4. Khởi tạo và cài đặt chứng chỉ Root CA
echo "[4/6] Khởi tạo và cài đặt chứng chỉ Root CA vào hệ thống..."
python3 "${SCRIPT_DIR}/launcher/main.py" --install-cert || true

# 5. Kiểm tra và tự động nhập tài khoản từ 9router (nếu có)
echo "[5/6] Kiểm tra và tự động nhập tài khoản từ 9router (nếu có)..."
python3 "${SCRIPT_DIR}/launcher/main.py" --import-9router || true

# 6. Tạo liên kết biểu tượng (Symlink) & Shortcut Desktop
echo "[6/6] Tạo symlink và Shortcut Desktop..."
chmod +x "${SCRIPT_DIR}/bin/antigravity-launcher" "${SCRIPT_DIR}/launch.sh"
ln -sf "${SCRIPT_DIR}/bin/antigravity-launcher" "${TARGET_BIN_DIR}/antigravity-launcher"
python3 "${SCRIPT_DIR}/launcher/main.py" --create-shortcut || true

echo ""
echo "=== Cài đặt hoàn tất! ==="
echo "Bạn có thể khởi chạy bằng:"
echo "  1. Shortcut trên màn hình Desktop: 'Antigravity Launcher'"
echo "  2. Lệnh terminal: antigravity-launcher"
echo "  3. Hoặc chạy trực tiếp: ./launch.sh"
