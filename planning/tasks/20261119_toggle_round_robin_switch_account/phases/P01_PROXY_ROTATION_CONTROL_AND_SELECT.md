# Phase P01: Nâng cấp Micro-Proxy Node.js (Select Account, Fixed Mode & OAuth Select)

## 1. Phase Metadata

| Field | Value |
| :--- | :--- |
| **Phase ID** | `P01` |
| **Parent Task ID** | `TASK-20261119-001` |
| **Master Plan** | `../TASK_TOGGLE_ROUND_ROBIN_SWITCH_ACCOUNT.md` |
| **Status** | ✅ Done |
| **Depends on** | `None` |
| **Lifecycle Owner** | Worker |

---

## 2. Target File Impact (Trích xuất từ Section 4 Master)

| Action | File path | Target Symbol/Area | Reason | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| Edit | `proxy/account_rotator.js` | `AccountRotator`, `loadState`, `selectAccount`, `handleCommand` | Hỗ trợ lệnh `select`, bảo toàn tài khoản đang ghim qua chu kỳ reload 5s, đồng bộ `auto_rotation_enabled` không gây race condition | `Confirmed` |
| Edit | `proxy/index.js` | `checkCmdFile`, `/_proxy_action` | Truyền thêm tham số `target` từ query string và `proxy_cmd.json` vào `rotator.handleCommand` | `Confirmed` |
| Edit | `proxy/oauth_flow.js` | `buildGoogleAuthUrl` | Đổi `prompt: "consent"` → `"select_account consent"` để trình duyệt luôn hiện bộ chọn tài khoản Google | `Confirmed` |

---

## 3. Tasks Breakdown

- [x] **Task P01.1**: Thêm phương thức `selectAccount(target)` và nhánh `cmd === "select"` trong `AccountRotator`
  - File: `proxy/account_rotator.js`
  - Chi tiết:
    1. Trong `constructor(config)` (sau dòng 30), khởi tạo snapshot chống ghi đè trạng thái khi đọc đĩa:
       - `this._lastProfilesAutoRotation = undefined;`
       - `this._lastProfilesActiveId = undefined;`
    2. Thêm hàm `selectAccount(target)` tìm tài khoản trong `this.accounts` khớp `a.id` hoặc `(a.email || a.name)` (so khớp không phân biệt hoa thường), cập nhật `this.accountIndex = idx`, `this.currentAccRequestsServed = 0`, xóa `acc.unhealthyUntil = 0`, lưu `saveRotatorState()`, và trả về `acc` (hoặc `null` nếu không khớp).
    3. Mở rộng chữ ký `handleCommand(cmd, httpRes, writeLiveStatus, payload = {})` thêm nhánh `cmd === "select"` xử lý `payload?.target` (trả HTTP `200` khi thành công, `404` nếu không tìm thấy).
  - Code snippet minh họa:
    ```js
    selectAccount(target) {
      if (!target || !Array.isArray(this.accounts) || this.accounts.length === 0) return null;
      const needle = String(target).trim().toLowerCase();
      const idx = this.accounts.findIndex((a) => {
        const matchId = a.id && String(a.id).toLowerCase() === needle;
        const matchEmail = a.email && a.email.toLowerCase() === needle;
        const matchName = a.name && a.name.toLowerCase() === needle;
        return matchId || matchEmail || matchName;
      });
      if (idx === -1) return null;

      this.accountIndex = idx;
      this.currentAccRequestsServed = 0;
      this.accounts[idx].unhealthyUntil = 0;
      this.saveRotatorState();
      return this.accounts[idx];
    }
    ```
    ```js
    if (cmd === "select") {
      const target = payload?.target || "";
      const selected = this.selectAccount(target);
      if (!selected) {
        if (httpRes) {
          httpRes.writeHead(404, { "Content-Type": "application/json" });
          httpRes.end(JSON.stringify({ success: false, error: "Account not found or disabled" }));
        }
        return;
      }
      console.log(`[ROUND-ROBIN] Chon thu cong tai khoan: [${selected.email}]`);
      writeLiveStatus({
        active: false, timestamp: Date.now(), account_email: selected.email || "UNKNOWN",
        account_name: selected.name || selected.email || "UNKNOWN", current_req: this.currentAccRequestsServed,
        requests_per_account: this.requestsPerAccount, total_requests: this.requestCount,
        endpoint: "manual_select", method: "SELECT", status: this.rotationPaused ? "paused" : "standby",
        paused: this.rotationPaused
      });
      if (httpRes) {
        httpRes.writeHead(200, { "Content-Type": "application/json" });
        httpRes.end(JSON.stringify({
          success: true, id: selected.id || "", email: selected.email || "", paused: this.rotationPaused
        }));
      }
      return;
    }
    ```

- [x] **Task P01.2**: Bảo toàn tài khoản đang ghim & đồng bộ `auto_rotation_enabled` trong `loadState()`
  - File: `proxy/account_rotator.js`
  - Chi tiết:
    1. Trước khi gán `this.accounts = valid`, lưu lại `const prevAcc = this.isRestored ? this.accounts[this.accountIndex] : null;`.
    2. Khi đọc `profiles.json` (`cfg`), trích xuất thêm:
       - `cfgAutoRot`: `cfg.settings?.auto_rotation_enabled` (boolean nếu tồn tại).
       - `cfgActiveId`: `cfg.settings?.active_account_id` (chuỗi nếu tồn tại) và ánh xạ chéo từ `cfg.profiles` lấy `cfgActiveEmail` (vì `profiles.json` lưu `id` dạng slug còn `accounts.json` lưu `id` dạng UUID).
    3. Chỉ đồng bộ `this.rotationPaused = !cfgAutoRot` khi `typeof cfgAutoRot === "boolean" && cfgAutoRot !== this._lastProfilesAutoRotation` để tránh ghi đè nút `Tạm dừng`/`Tiếp tục` ở chu kỳ reload 5s.
    4. Sau khi gán `this.accounts = valid` và `this.isRestored === true`, tìm lại đúng index theo thứ tự ưu tiên:
       - Nếu `cfgActiveId && cfgActiveId !== this._lastProfilesActiveId`: ưu tiên tìm theo `cfgActiveId` hoặc `cfgActiveEmail`.
       - Ngược lại nếu có `prevAcc`: tìm lại `prevAcc` theo `id`/`email` trong `valid`.
       - Fallback cuối cùng mới dùng `this.accountIndex % this.accounts.length`.
  - Code snippet minh họa:
    ```js
    let cfgAutoRot;
    let cfgActiveTarget = "";
    let cfgActiveEmail = "";
    // ... trong try đọc cfg từ PROFILES_FILE:
    if (typeof cfg.settings?.auto_rotation_enabled === "boolean") {
      cfgAutoRot = cfg.settings.auto_rotation_enabled;
    }
    if (typeof cfg.settings?.active_account_id === "string") {
      cfgActiveTarget = cfg.settings.active_account_id.trim();
      const matchedProf = (cfg.profiles || []).find(
        (p) => (p.id || "").toLowerCase() === cfgActiveTarget.toLowerCase()
      );
      cfgActiveEmail = (matchedProf?.email || "").toLowerCase();
    }
    ```
    ```js
    const prevAcc = this.isRestored ? this.accounts[this.accountIndex] : null;
    if (valid.length > 0) {
      // ... giữ nguyên logic cooldownMap & gán this.accounts = valid
      if (!this.isRestored) {
        this.restoreRotatorState();
        if (typeof cfgAutoRot === "boolean") {
          this.rotationPaused = !cfgAutoRot;
          this._lastProfilesAutoRotation = cfgAutoRot;
        }
        if (cfgActiveTarget || cfgActiveEmail) {
          const initIdx = this.accounts.findIndex((a) =>
            (cfgActiveTarget && String(a.id || "").toLowerCase() === cfgActiveTarget.toLowerCase()) ||
            (cfgActiveEmail && (a.email || "").toLowerCase() === cfgActiveEmail)
          );
          if (initIdx !== -1) this.accountIndex = initIdx;
          this._lastProfilesActiveId = cfgActiveTarget;
        }
        this.isRestored = true;
      } else {
        if (typeof cfgAutoRot === "boolean" && cfgAutoRot !== this._lastProfilesAutoRotation) {
          this.rotationPaused = !cfgAutoRot;
          this._lastProfilesAutoRotation = cfgAutoRot;
        }
        let nextIdx = -1;
        if (cfgActiveTarget && cfgActiveTarget !== this._lastProfilesActiveId) {
          nextIdx = this.accounts.findIndex((a) =>
            String(a.id || "").toLowerCase() === cfgActiveTarget.toLowerCase() ||
            (cfgActiveEmail && (a.email || "").toLowerCase() === cfgActiveEmail)
          );
          this._lastProfilesActiveId = cfgActiveTarget;
        }
        if (nextIdx === -1 && prevAcc) {
          nextIdx = this.accounts.findIndex((a) => isSameAccount(a, prevAcc));
        }
        this.accountIndex = nextIdx !== -1 ? nextIdx : (this.accountIndex % this.accounts.length);
      }
      agentPool.cleanupDeadAgents(valid);
    }
    ```

- [x] **Task P01.3**: Truyền tham số `target` tại `/_proxy_action` và `checkCmdFile()`
  - File: `proxy/index.js`
  - Chi tiết:
    1. Trong `checkCmdFile()` (dòng 210): truyền `cmdObj` làm tham số thứ 4 cho `rotator.handleCommand(cmdObj.cmd, null, writeLiveStatus, cmdObj)`.
    2. Trong HTTP server handler `/_proxy_action` (dòng 224–227): lấy `const target = parsedUrl.searchParams.get("target") || "";` và truyền `{ target }` vào `rotator.handleCommand(cmd, res, writeLiveStatus, { target })`.
  - Code snippet minh họa:
    ```js
    if (cmdObj.cmd) rotator.handleCommand(cmdObj.cmd, null, writeLiveStatus, cmdObj);
    ```
    ```js
    if (parsedUrl.pathname === "/_proxy_action") {
      const cmd = parsedUrl.searchParams.get("cmd");
      const target = parsedUrl.searchParams.get("target") || "";
      rotator.handleCommand(cmd, res, writeLiveStatus, { target });
      return;
    }
    ```

- [x] **Task P01.4**: Bật bộ chọn tài khoản Google trên màn hình OAuth
  - File: `proxy/oauth_flow.js`
  - Chi tiết: Trong `buildGoogleAuthUrl()` (dòng 31), đổi `prompt: "consent"` thành `prompt: "select_account consent"` để người dùng có thể chọn hoặc chuyển sang tài khoản Gmail khác ngay cả khi trình duyệt đã lưu sẵn phiên đăng nhập.
  - Code snippet minh họa:
    ```js
    const params = new URLSearchParams({
      client_id: config.GOOGLE_CLIENT_ID,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: SCOPES.join(" "),
      code_challenge: codeChallenge,
      code_challenge_method: "S256",
      state,
      access_type: "offline",
      prompt: "select_account consent"
    });
    ```

---

## 4. Conditional Quality Gates (Cấp Phase)

- **Security Gate**: `Passed` — Tham số `target` chỉ dùng để so khớp chuỗi in-memory (`findIndex`) và lọc qua `URLSearchParams`, không thực thi shell hay render raw HTML chưa escape.
- **Data Gate**: `Not applicable` — Không thay đổi schema lưu trữ của `accounts.json`.
- **Accessibility Gate**: `Not applicable` — Phase này thuộc tầng Proxy Node.js.
- **Compatibility Gate**: `Passed` — Đã xác nhận giữ nguyên contract 100% cho các command cũ (`reload`, `next`, `pause`, `resume`, `toggle_pause`) và 7/7 test cũ + 4/4 test mới trong `tests/test_proxy_rotation.py` đều PASS.

---

## 5. Phase Rollback (Cục bộ)

- Hoàn tác riêng các file của Phase P01 bằng lệnh:
  ```powershell
  git checkout -- proxy/account_rotator.js proxy/index.js proxy/oauth_flow.js
  ```

---

## 6. Phase Verification & DoD Checklist

- **Pre-check (Phase DoR)**:
  - [x] `Depends on` (`None`) thỏa mãn.
  - [x] Đã xác minh tồn tại 3 target files: `proxy/account_rotator.js`, `proxy/index.js`, `proxy/oauth_flow.js`.
- **Execution Verification (Mapped Test Checks)**:
  - Check ID: `T-001`, `T-002`, `T-003`, `T-004` (Map Section 7 Master).
  - Lệnh kiểm tra:
    ```powershell
    python -m unittest discover -s tests -p "test_proxy_rotation.py"
    ```
  - Kết quả kỳ vọng: Toàn bộ test cũ (7/7) và các test mới cho `selectAccount`, `loadState()`, `rotationPaused` & `buildGoogleAuthUrl` đều PASS (`OK`).
- **Post-check (Phase DoD)**:
  - [x] 100% Tasks (`P01.1`–`P01.4`) đã hoàn thành (`[x]`).
  - [x] Lệnh verification thực tế pass 100% sau chỉnh sửa cuối cùng (11/11 PASS).
  - [x] Đã đồng bộ cập nhật `Status` của Phase `P01` tại Section 6 Master Plan thành `✅ Done`.
