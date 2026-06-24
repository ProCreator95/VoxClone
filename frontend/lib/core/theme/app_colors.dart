import 'package:flutter/material.dart';

/// Centralized color palette — premium SaaS aesthetic.
///
/// Deep navy / indigo primaries, muted accents, soft semantic colors.
abstract final class AppColors {
  // ── Brand primaries ───────────────────────────────────────────────────────
  static const Color navy = Color(0xFF1A2332);
  static const Color indigo = Color(0xFF2D3A5C);
  static const Color slateBlue = Color(0xFF4A5568);

  // ── Accents ───────────────────────────────────────────────────────────────
  static const Color mutedBlue = Color(0xFF5B7DB1);
  static const Color mutedTeal = Color(0xFF5B8A9A);

  // ── Semantic ──────────────────────────────────────────────────────────────
  static const Color success = Color(0xFF5C9E6E);
  static const Color warning = Color(0xFFD4A853);
  static const Color error = Color(0xFFC45C5C);

  // ── Light surfaces ────────────────────────────────────────────────────────
  static const Color lightBackground = Color(0xFFF7F8FA);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightSurfaceVariant = Color(0xFFF0F2F5);
  static const Color lightBorder = Color(0xFFE2E5EB);
  static const Color lightTextPrimary = Color(0xFF1A1F2E);
  static const Color lightTextSecondary = Color(0xFF6B7280);
  static const Color lightTextTertiary = Color(0xFF9CA3AF);

  // ── Dark surfaces ─────────────────────────────────────────────────────────
  static const Color darkBackground = Color(0xFF0F1419);
  static const Color darkSurface = Color(0xFF1A2332);
  static const Color darkSurfaceVariant = Color(0xFF242D3D);
  static const Color darkBorder = Color(0xFF2E3A4D);
  static const Color darkTextPrimary = Color(0xFFF1F3F5);
  static const Color darkTextSecondary = Color(0xFFA0AABB);
  static const Color darkTextTertiary = Color(0xFF6B7280);

  // ── Card accents (feature icons) ──────────────────────────────────────────
  static const Color cardSubtitles = Color(0xFF5B7DB1);
  static const Color cardKaraoke = Color(0xFF6B5B95);
  static const Color cardEnhance = Color(0xFF5B8A9A);
  static const Color cardVocals = Color(0xFF7B6B8A);
  static const Color cardMusic = Color(0xFF5A7A6B);
  static const Color cardDownloads = Color(0xFF4A6FA5);
  static const Color cardSettings = Color(0xFF4A5568);
}
