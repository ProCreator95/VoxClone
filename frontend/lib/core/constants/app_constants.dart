/// Centralized application constants.
///
/// Retention period and other policy values must be referenced from here —
/// do not hard-code them in UI widgets.
abstract final class AppConstants {
  static const String appName = 'VoxClone';
  static const String appVersion = '0.1.0-mvp';
  static const String appTagline = 'Offline AI Media Studio';

  /// Default output retention period (days). Matches planned backend
  /// `OUTPUT_RETENTION_DAYS` — configurable via build flags in future milestones.
  static const int outputRetentionDays = 10;

  static const String retentionNoticeBody =
      'Generated files are retained for a limited period and may be '
      'automatically deleted after the configured retention window expires.';

  /// Default backend API base URL (no trailing slash).
  static const String defaultApiBaseUrl = 'http://10.0.2.2:8000';

  static const String apiBaseUrlPrefsKey = 'api_base_url';
  static const String themeModePrefsKey = 'theme_mode';
}
