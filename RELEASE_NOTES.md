# Release Notes

This page summarizes what's new and fixed in each version.

## [0.3.1] - 2026-08-18

### 🐛 Fixes

- Fixed an issue where monitoring status checks could hang indefinitely against certain Gatus setups

## [0.3.0] - 2026-08-17

### ✨ What's new

- New monitoring client for checking service status and uptime

## [0.2.0] - 2026-08-17

### ✨ What's new

- DataHub client can now request specific fields (for eager-loading
  relations) and delete items

## [0.1.0] - 2026-08-17

First release of `relay` — a shared toolkit of lightweight clients for internal services. 🎉

### ✨ What's new

- Ready-to-use clients for GitHub, DataHub, notifications, and bucket management, all built on a common, reliable HTTP transport with automatic retries
- A shared JSON logging helper for consistent logs across services
