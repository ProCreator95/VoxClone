# VoxClone Flutter App

Mobile client for the [VoxClone](../) offline AI media processing platform.

**Phase 9 · Milestone M1 + UI refactor** — Premium SaaS application shell with sidebar navigation, theme system, and placeholder screens. No API integration yet.

## Prerequisites

- Flutter 3.41+ (stable channel)
- Android Studio / Xcode for device emulators

## Quick start

```bash
cd frontend
flutter pub get
flutter run
```

## Navigation

The app uses a **professional SaaS shell**:

| Viewport | Navigation |
|----------|------------|
| Desktop (≥1024px) | Fixed left sidebar (280px) |
| Tablet (768–1023px) | Compact sidebar (240px) |
| Mobile (<768px) | Hamburger drawer |

### Routes

| Path | Screen |
|------|--------|
| `/home` | Welcome, MVP overview, retention notice, roadmap |
| `/subtitles` … `/downloads` | Core feature placeholders |
| `/creator/voice-recorder` | Voice Recorder Studio (Phase 12) |
| `/creator/karaoke-recording` | Karaoke Recording Studio (Phase 12) |
| `/media/*` | Media tool placeholders (Phase 12) |
| `/account` | Account placeholder (Phase 10) |
| `/billing` | Billing placeholder (Phase 11) |
| `/settings` | API URL, theme, retention |
| `/about` | Product info |

Legacy `/` and `/dashboard` redirect to `/home`.

## Project structure

```
frontend/lib/
├── main.dart
├── app.dart
├── core/
│   ├── constants/app_constants.dart
│   ├── theme/                    # AppColors, AppSpacing, AppTypography, AppTheme
│   ├── routing/
│   │   ├── app_router.dart       # go_router + ShellRoute
│   │   └── navigation_config.dart
│   ├── networking/networking.dart
│   └── widgets/
│       ├── app_shell.dart        # Sidebar + drawer layout
│       ├── app_sidebar.dart
│       ├── shell_content.dart
│       ├── phased_placeholder_screen.dart
│       └── ...
└── features/
    ├── home/home_screen.dart
    ├── subtitles/ … enhancement/ … separation/ … downloads/
    ├── creator/                  # Voice recorder, karaoke recording
    ├── media/                    # Audio/video cutter & joiner
    ├── account/ · billing/
    └── settings/ · about/
```

## Configuration

Policy values live in `AppConstants` — never hard-code retention in widgets:

```dart
AppConstants.outputRetentionDays  // default: 10
AppConstants.retentionNoticeBody
AppConstants.defaultApiBaseUrl
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `flutter_riverpod` | Theme + settings state |
| `go_router` | Shell routing |
| `google_fonts` | Inter typography |
| `shared_preferences` | Persist theme + API URL |

## Related docs

- [Phase 9 Design](../docs/reports/PHASE9_FLUTTER_FRONTEND_MVP_DESIGN.md)
- [Project Snapshot](../docs/context/PROJECT_SNAPSHOT_2026_06_22.md)

## Milestone roadmap

| Milestone | Status |
|-----------|--------|
| M1 — Scaffold + premium UI shell | ✅ Complete |
| M2 — Upload + media | Planned |
| M3 — Job submission | Planned |
| M4 — Progress polling | Planned |
| M5 — Downloads | Planned |
