# Antigravity Hub

[![Version](https://img.shields.io/badge/Version-v0.1.3-blue.svg)](docs/changelogs/v0.1.3.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg)]()

A dedicated multi-account manager and local transparent micro-proxy engineered specifically for Google's Antigravity ecosystem: **Antigravity 2.0 (Desktop Application)** and **Antigravity IDE (VS Code Code Editor)**. It enables seamless Google account rotation, real-time quota tracking, and subagent session affinity without relying on generic third-party gateway layers.

---

## 🖥️ Supported Client Surfaces

Antigravity provides two official user surfaces, both natively supported by this launcher and micro-proxy:

- **Antigravity 2.0 (Desktop Application)**: Google's standalone desktop application designed for agent orchestration, conversational chat canvases, background automation (cron/timers), and multi-turn subagent delegation.
- **Antigravity IDE (Code Editor)**: The standalone AI-first development environment (built on VS Code) featuring in-editor predictive code completions (Antigravity Tab), inline instructions (<kbd>Ctrl</kbd>+<kbd>I</kbd>), code lenses, and collaborative pair-programming agents.

---

## 📦 Quick Installation

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

---

## 🎯 Why a Dedicated Micro-Proxy? (vs. Third-Party Gateways like 9Router)

Third-party AI gateways and multi-provider routers (such as **9Router** or commercial proxy endpoints) are designed as universal abstraction layers supporting 40+ upstream providers. While useful for cross-provider fallback, using generic third-party gateways with Antigravity introduces key technical limitations:

1. **Format & Payload Transformation**:
   - Generic gateways like 9Router translate API formats (e.g., mapping between OpenAI, Claude, and Gemini schemas) and apply prompt modifications or token compression (e.g., RTK).
   - Antigravity 2.0 and Antigravity IDE rely on Google's proprietary Cloud Code PA RPC protocol (`daily-cloudcode-pa.googleapis.com` / `cloudcode-pa.googleapis.com`). Format translation can strip critical headers, alter parameter structures, or cause unexpected serialization failures.
2. **Subagent Hard-Lock & Rapid Quota Exhaustion in 9Router**:
   - In 9Router, whenever Gemini spawns subagents (such as Codebase Researchers, Test Runners, or Background Workers), 9Router **hard-locks all subagent requests onto the single account that requested the spawn**.
   - As a result, all heavy, token-intensive subagent loops continuously hammer that single parent account without rotating, burning through its quota in minutes while other accounts in your pool sit completely idle.
   - When that single account exhausts its quota, the entire subagent workflow crashes or stalls.
3. **Throttling & Intermediate Latency**:
   - Relaying traffic through third-party multi-provider translation pipelines adds latency and exposes requests to third-party rate limits, unexpected bandwidth throttling, and connection drops during long Server-Sent Events (SSE) reasoning chains.

**Antigravity Micro-Proxy** solves this by running a specialized, local proxy (`127.0.0.1:20130`) designed exclusively for Google's native protocols with Dual-Track Subagent Allocation.

---

## ⚡ Core Technical Pillars

### 1. Zero-Mutation Native Request Pass-Through
- **Untouched Protocol Fidelity**: Forwards authentic client HTTP requests and protobuf/JSON structures directly to Google's official Cloud Code endpoints without modification.
- **Zero Schema Conversion**: Does not decode or wrap requests into synthetic formats, ensuring 100% compatibility with official Gemini models and tool-calling features.

### 2. Direct Google Connection & High-Speed Local Rotation
- **Direct-to-Google Communication**: Connects directly from your machine to Google Frontend (GFE) using dedicated per-account socket pools (`keepAlive: 15s`). No intermediate relays or third-party speed caps.
- **Intelligent Round-Robin & Auto-Failover**: Rotates active Google accounts locally based on configured request thresholds (`requests_per_account`). If an account exhausts quota (HTTP 429) or hits an authorization error (HTTP 403), the proxy immediately fails over to the next available account without dropping the user query.
- **Extended Thinking SSE Support**: Tailored for long reasoning models (Gemini 2.0 Flash Thinking) with a 120-second time-to-first-byte (TTFB) timeout and a 45-second sliding window between SSE chunks.

### 3. Dual-Track Subagent Routing (Anti-Quota Exhaustion)
- **Automatic Account Rotation for New Subagents**: Unlike 9Router which traps all subagents on the spawning account, Antigravity assigns every newly spawned subagent to a **fresh account** from the pool (`allocateSubagentAccount`). This prevents intense subagent background workloads from exhausting the user's primary account quota.
- **Intra-Task Context Pinning (Prompt Caching)**: Within each subagent's active task lifecycle (< 60s idle), successive turns remain pinned to that allocated account to leverage Google Gemini's Prompt Caching and maintain conversation coherence.
- **Main Editor Isolation**: Keeps interactive editor chat strictly isolated from background agent workloads.

### 4. Real-Time Token Analytics & Independent Persistence
- **Zero-Latency Passive Sniffing**: Sniffs authentic Google `usageMetadata` (`Sent`, `Received`, `Cached`) directly from stream chunks without buffering or delaying client responses.
- **Interactive Dashboard Metrics Bar**: View aggregated token counts across **24 Hours**, **7 Days**, **30 Days**, and **All Time** with exact 15-digit number display across 3 compact cards (`Sent`, `Received`, `Cached`).
- **Independent Storage (`token_metrics.json`)**: Token statistics are stored in structured hourly time-series buckets independent of `proxy.log`, ensuring that clearing or pruning logs preserves accumulated statistics 100%.
- **Streamlined Dashboard Activity**: Real-time 3-column recent requests panel (`Model | In / Out | When`) with authentic Gemini model name extraction (`[MODEL: <name>]`).
- **Dedicated Sidebar Logs View**: Independent 5-column structured log viewer (`Time | Thread | Action/Model | Account | Tokens`) with lightweight native rendering, instant text search, real-time timestamps, and direct raw log file opening.

---

## 📊 Comparison: Antigravity Micro-Proxy vs. Third-Party Gateways

| Technical Capability | Antigravity Micro-Proxy (This Project) | Third-Party Gateways (e.g., 9Router) |
|---|:---:|:---:|
| **Architecture Scope** | Dedicated specifically for Antigravity 2.0 & Antigravity IDE | Generic router for 40+ multi-model providers |
| **Request Handling** | **Zero-mutation pass-through** (Authentic legacy Google protocol) | API format translation, prompt alteration, token compression |
| **Subagent Allocation** | **Dual-Track Round-Robin**: Assigns fresh accounts to new subagents, preventing single-account quota exhaustion | **Spawning-Account Hard Lock**: Traps all subagents on parent account, causing rapid quota burnout |
| **Subagent Prompt Caching** | **Yes** (Pins account within subagent task lifecycle < 60s) | No intra-task affinity control |
| **Connection Path** | **Direct Local-to-Google** (`127.0.0.1` -> Google Frontend) | Through multi-provider translation pipeline |
| **Bandwidth / Throughput** | **Unrestricted** (Direct local socket pool) | Subject to gateway processing overhead & provider limits |
| **Extended Thinking Support** | **Yes** (Optimized 120s TTFB + 45s SSE sliding window) | Variable; often timeouts on prolonged thinking models |
| **Credential Storage** | **Local Plain JSON (`0600`)** with Portable Cross-OS `.zip` Backup | Plaintext config files / SQLite |

---

## 💻 CLI Quick Reference

Manage accounts and settings directly from the terminal:

```bash
# Display CLI help
python3 launcher/main.py --help

# List accounts with status and quotas
python3 launcher/main.py --list

# Backup accounts and settings to a .zip archive
python3 launcher/main.py --backup [optional_output_path]

# Restore accounts and settings from a .zip archive (mode: replace | merge)
python3 launcher/main.py --restore <backup_file.zip> [--restore-mode replace|merge]

# Install and trust Root CA certificate in OS Trust Store
python3 launcher/main.py --install-cert

# Add a Google account via OAuth PKCE
python3 launcher/main.py --add-google

# Refresh quotas across all active accounts
python3 launcher/main.py --refresh-quota

# Configure rotation threshold (e.g., 10 requests per account)
python3 launcher/main.py --requests-per-account 10

# Enable or disable an account
python3 launcher/main.py --toggle <ACCOUNT_EMAIL_OR_ID>

# Launch Antigravity 2.0 (App) or Antigravity IDE with active proxy
python3 launcher/main.py --launch
```

---

## 🔒 Security & Privacy

- **Local Plain JSON Storage**: OAuth tokens are stored locally in plain JSON (`accounts.json` with owner-only `0600` permissions on Unix) for full cross-machine and cross-OS backup portability.
- **Loopback Isolation**: Local micro-proxy TLS certificates are bound strictly to `127.0.0.1:20130`.
- **Zero Data Collection**: No telemetry, analytics, or user prompts are ever collected or sent to external servers.

---

## 📜 Release Changelogs

Detailed release notes and migration guides are documented in the [Changelogs Directory](./docs/changelogs/README.md):
- [v0.1.3 Changelog](./docs/changelogs/v0.1.3.md): Universal plain-JSON Backup & Restore engine with cross-OS path remapping, removal of machine-bound encryption/keyring, 9Router importer decommission, and Settings View scroll/row-height GUI fixes.
- [v0.1.2 Changelog](./docs/changelogs/v0.1.2.md): Automated Root CA & Combined Trust Bundle (`ca-bundle.crt`), 5-step automated installation pipeline, native 9router account migration, zero-freeze Windows UX optimizations, and auto-closing OAuth tabs.
- [v0.1.1 Changelog](./docs/changelogs/v0.1.1.md): Token Metrics Bar (Sent/Received/Cached full numbers), Streamlined 3-column Activity Table, Model Extraction, Dedicated Sidebar Logs View, Real-Time Proxy Timestamps, and Independent `token_metrics.json`.
- [v0.1.0 Changelog](./docs/changelogs/v0.1.0.md): Antigravity Hub Rebranding, Quota Progress Bars, Reset Timers, Priority Steppers, System Tray.

---

## 📄 License

Distributed under the MIT License. Copyright © 2026 JunMystery.
