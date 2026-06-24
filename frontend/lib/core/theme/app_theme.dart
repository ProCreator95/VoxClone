import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_colors.dart';
import 'app_spacing.dart';
import 'app_typography.dart';

/// Material 3 light and dark themes with centralized palette.
abstract final class AppTheme {
  static ThemeData get light => _buildTheme(
        brightness: Brightness.light,
        background: AppColors.lightBackground,
        surface: AppColors.lightSurface,
        surfaceVariant: AppColors.lightSurfaceVariant,
        border: AppColors.lightBorder,
        textTheme: AppTypography.lightTextTheme,
      );

  static ThemeData get dark => _buildTheme(
        brightness: Brightness.dark,
        background: AppColors.darkBackground,
        surface: AppColors.darkSurface,
        surfaceVariant: AppColors.darkSurfaceVariant,
        border: AppColors.darkBorder,
        textTheme: AppTypography.darkTextTheme,
      );

  static ThemeData _buildTheme({
    required Brightness brightness,
    required Color background,
    required Color surface,
    required Color surfaceVariant,
    required Color border,
    required TextTheme textTheme,
  }) {
    final isLight = brightness == Brightness.light;
    final primary = isLight ? AppColors.indigo : AppColors.mutedBlue;
    final onPrimary = Colors.white;
    final scheme = ColorScheme(
      brightness: brightness,
      primary: primary,
      onPrimary: onPrimary,
      primaryContainer: isLight
          ? AppColors.lightSurfaceVariant
          : AppColors.darkSurfaceVariant,
      onPrimaryContainer: textTheme.titleMedium?.color ?? primary,
      secondary: AppColors.mutedTeal,
      onSecondary: Colors.white,
      secondaryContainer: isLight
          ? const Color(0xFFE8F0F2)
          : const Color(0xFF1E3338),
      onSecondaryContainer: textTheme.bodyMedium?.color ?? primary,
      tertiary: AppColors.slateBlue,
      onTertiary: Colors.white,
      error: AppColors.error,
      onError: Colors.white,
      surface: surface,
      onSurface: textTheme.bodyLarge?.color ?? primary,
      onSurfaceVariant: textTheme.bodyMedium?.color ?? primary,
      outline: border,
      outlineVariant: border.withValues(alpha: 0.6),
      shadow: Colors.black.withValues(alpha: isLight ? 0.06 : 0.3),
      scrim: Colors.black54,
      inverseSurface: isLight ? AppColors.darkSurface : AppColors.lightSurface,
      onInverseSurface: isLight
          ? AppColors.darkTextPrimary
          : AppColors.lightTextPrimary,
      inversePrimary: AppColors.mutedBlue,
      surfaceTint: primary,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: background,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        backgroundColor: background,
        foregroundColor: textTheme.titleLarge?.color,
        systemOverlayStyle: isLight
            ? SystemUiOverlayStyle.dark
            : SystemUiOverlayStyle.light,
        titleTextStyle: textTheme.titleLarge,
      ),
      cardTheme: CardThemeData(
        elevation: AppSpacing.cardElevation,
        color: surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
          side: BorderSide(color: border, width: AppSpacing.cardBorderWidth),
        ),
        margin: EdgeInsets.zero,
      ),
      dividerTheme: DividerThemeData(color: border, thickness: 1, space: 1),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceVariant,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.buttonRadius),
          borderSide: BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.buttonRadius),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.buttonRadius),
          borderSide: BorderSide(color: primary, width: 1.5),
        ),
        hintStyle: textTheme.bodyMedium,
        labelStyle: textTheme.labelMedium,
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          visualDensity: VisualDensity.compact,
          padding: WidgetStateProperty.all(
            const EdgeInsets.symmetric(
              horizontal: AppSpacing.sm,
              vertical: AppSpacing.xs,
            ),
          ),
        ),
      ),
      listTileTheme: ListTileThemeData(
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.xxs,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.buttonRadius),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.buttonRadius),
        ),
      ),
    );
  }
}
