#!/usr/bin/env bash
# Script cài đặt tự động Antigravity Launcher & Micro-Proxy
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TARGET_BIN_DIR="${HOME}/.local/bin"

echo "=== Cài đặt Antigravity Launcher & Micro-Proxy ==="

# 1. Kiểm tra môi trường yêu cầu
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] Cần cài đặt python3 trước."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[ERROR] Cần cài đặt nodejs (v18+) trước."; exit 1; }

# 2. Cài đặt dependencies cho Micro-Proxy
echo "[1/3] Cài đặt dependencies cho Micro-Proxy (Node.js)..."
cd "${SCRIPT_DIR}/proxy"
if [ -f "package.json" ]; then
    npm install --silent --no-audit --no-fund || npm install
fi

# 3. Tạo thư mục cấu hình chuẩn
echo "[2/3] Khởi tạo thư mục cấu hình ~/.config/antigravity-launcher..."
mkdir -p "${HOME}/.config/antigravity-launcher"
mkdir -p "${HOME}/.config/Antigravity-Profiles"
mkdir -p "${TARGET_BIN_DIR}"

# 4. Tạo liên kết biểu tượng (Symlink)
echo "[3/3] Tạo symlink antigravity-launcher vào ${TARGET_BIN_DIR}..."
chmod +x "${SCRIPT_DIR}/bin/antigravity-launcher"
ln -sf "${SCRIPT_DIR}/bin/antigravity-launcher" "${TARGET_BIN_DIR}/antigravity-launcher"

echo ""
echo "=== Cài đặt hoàn tất! ==="
echo "Bạn có thể khởi chạy bằng lệnh: antigravity-launcher"
echo "Hoặc chạy trực tiếp: ${SCRIPT_DIR}/bin/antigravity-launcher"
