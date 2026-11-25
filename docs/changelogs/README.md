# Antigravity Hub Changelogs

This directory contains release notes and detailed technical changelogs for each version of **Antigravity Hub**.

---

## Versioning Policy

Antigravity Hub follows [Semantic Versioning 2.0.0](https://semver.org/):
- **MAJOR (`x.0.0`)**: Incompatible API or architectural breaking changes.
- **MINOR (`0.x.0`)**: Backwards-compatible new features, protocol enhancements, or major UI additions.
- **PATCH (`0.0.x`)**: Backwards-compatible bug fixes, audit remediations, or performance optimizations.

---

## Release History

| Version | Release Date | Highlights | Changelog Link |
|---|---|---|---|
| **v0.2.0** | 2026-11-25 | Dashboard inline account pinning with strict failover lock, dedicated Model Rules view (multi-model `patterns` + `contains`/`exact`/`regex`, ordered multi-account pools, parallel model discovery, route tester), atomic `.tmp`/`.bak` persistence, `CONFIG_DIR/certs/` Root CA migration, and `--stop-proxy` setup hardening. | [v0.2.0 Changelog](./v0.2.0.md) |
| **v0.1.4** | 2026-11-18 | Concurrent agent hang & timeout/abort-loop remediation: budget-aware TTFB failover (`25s -> 22s -> remaining`), 120s thinking window, 15s idle socket eviction & pool purge, hop-by-hop header stripping, pre-header abort rotation, and Dashboard startup fix. | [v0.1.4 Changelog](./v0.1.4.md) |
| **v0.1.3** | 2026-11-18 | Universal plain-JSON Backup & Restore engine (.zip archive with Replace/Merge modes & cross-OS path remapping), removal of machine-bound encryption/keyring, 9Router importer decommission, and Settings View scroll/height GUI fix. | [v0.1.3 Changelog](./v0.1.3.md) |
| **v0.1.2** | 2026-11-16 | Automated Root CA & Combined Trust Bundle (`ca-bundle.crt`), 5-step automated installation pipeline, native 9router account migration, zero-freeze Windows UX optimizations, and auto-closing OAuth tabs. | [v0.1.2 Changelog](./v0.1.2.md) |
| **v0.1.1** | 2026-11-16 | Token Metrics Bar (Sent/Received/Cached full numbers), Streamlined 3-column Activity Table, Model Extraction, Dedicated Sidebar Logs View, Real-Time Proxy Timestamps, and Independent `token_metrics.json`. | [v0.1.1 Changelog](./v0.1.1.md) |
| **v0.1.0** | 2026-11-16 | Official Rebranding to Antigravity Hub, Quota Progress Bar with dynamic color gradients, Reset Timers, Priority Micro-Steppers, System Tray integration, and Keyring AES-256-GCM Envelope Encryption. | [v0.1.0 Changelog](./v0.1.0.md) |
