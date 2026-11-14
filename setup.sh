#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  Antigravity Launcher & Micro-Proxy - Linux/macOS Setup"
echo "============================================================"
echo ""

if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 chưa được cài đặt. Vui lòng cài đặt python3."
    exit 1
fi

if ! command -v node &>/dev/null; then
    echo "[ERROR] Node.js chưa được cài đặt. Vui lòng cài đặt nodejs (LTS)."
    exit 1
fi

echo "[1/3] Cài đặt các thư viện Python (PyQt6, requests)..."
pip install --break-system-packages -r requirements.txt || pip install -r requirements.txt

echo ""
echo "[2/3] Cài đặt phụ thuộc npm cho Micro-Proxy..."
cd proxy
npm install
cd ..

chmod +x launch.sh launcher/main.py bin/antigravity-launcher 2>/dev/null || true

echo ""
echo "[3/3] Tự động tạo Shortcut trên Desktop..."
python3 launcher/main.py --create-shortcut || true

echo ""
echo "============================================================"
echo "  [OK] Cài đặt hoàn tất!"
echo "  Khởi chạy ứng dụng bằng Shortcut Desktop hoặc lệnh: ./launch.sh"
echo "============================================================"
