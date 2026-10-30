# Release Notes

This page summarizes what's new and fixed in each version.

## [0.14.0] - 2026-10-30

Clearer errors when a notification is too long to deliver. 📬

### 🔄 Improvements

- Notifications with an overly long message now fail immediately with a clear error, instead of being silently dropped by the notification service
- When a notification is rejected, the logs now explain why

### ⚠️ Points d'attention

- Notification messages are limited to 32,768 characters. Services sending long reports should put the full report in the attachment and keep the message itself short.

## [0.13.1] - 2026-10-30

A small fix to keep report notifications flowing. 🛠️

### 🐛 Fixes

- Fixed notifications with an attached report (e.g. warnings) being rejected by the notification service

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
