# Antigravity Hub

v0.2.1 | [MIT License](https://opensource.org/licenses/MIT)

Multi-account manager and local transparent micro-proxy (`127.0.0.1:20130`) for **Antigravity 2.0 (Desktop)** and **Antigravity IDE**. Supports Google account rotation, inline pinning, multi-model routing rules, real-time quota tracking, and subagent session isolation.

---

## Quick Installation

### Windows
```cmd
git clone https://github.com/JunMystery/antigravity-hub.git
cd antigravity-hub
setup.bat
launch.bat
```

### Linux
```bash
git clone https://github.com/JunMystery/antigravity-hub.git
cd antigravity-hub
chmod +x setup.sh launch.sh
./setup.sh
./launch.sh
```

Setup scripts automatically stop any background Micro-Proxy before updating dependencies and certificates so existing settings and logs remain intact.

---

## Key Features

- **Direct Pass-Through Proxy**: Forwards native Google Cloud Code requests directly on port `20130` with per-account socket pools and resilient handling for long-thinking SSE streams.
- **Round-Robin & Inline Account Pinning**: Rotates active Google accounts by request threshold with automatic failover on quota or auth errors, or pins traffic continuously to any account (including Deactive accounts) from the Dashboard status bar.
- **Model Rules (Multi-Model & Multi-Account)**: Dedicated **Model Rules** view with account-scoped model querying, multi-model selection (`contains`, `exact`, `regex`), unsupported-account indicators, ordered multi-account pools (`priority` or `round_robin` with per-rule or global-inherited `requests_per_account`), persisted rule rotation state, cyclic failover, global fallback control, and precedence over Dashboard Pause/Pin.
- **Dual-Track Subagent Routing**: Assigns newly spawned subagents to separate accounts with intra-task affinity to avoid exhausting the primary account quota.
- **Token Analytics & Logs**: Tracks `Sent`, `Received`, and `Cached` tokens across 24H / 7D / 30D / All Time independently of `proxy.log`, alongside a searchable Logs view.

---

## CLI Quick Reference

```bash
python3 launcher/main.py --help
python3 launcher/main.py --list
python3 launcher/main.py --add-google
python3 launcher/main.py --refresh-quota
python3 launcher/main.py --requests-per-account 10
python3 launcher/main.py --toggle <ACCOUNT_EMAIL_OR_ID>
python3 launcher/main.py --backup [optional_output_path]
python3 launcher/main.py --restore <backup_file.zip> [--restore-mode replace|merge]
python3 launcher/main.py --install-cert
python3 launcher/main.py --stop-proxy
python3 launcher/main.py --launch
```

---

## Persistence & Security

- **Protected User Data Directory**: Accounts, settings, token metrics, and Root CA certificates live outside the repository in `%APPDATA%\antigravity-launcher` (Windows) or `~/.config/antigravity-launcher` (Linux) with atomic `.tmp`/`.bak` writes and portable `.zip` backup/restore.
- **Loopback Isolation**: Local TLS interception binds strictly to `127.0.0.1:20130`.
- **Zero Data Collection**: No external telemetry or analytics.

---

## License

Distributed under the MIT License. Copyright © 2026 JunMystery.
