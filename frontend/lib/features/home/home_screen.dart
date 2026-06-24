import 'package:flutter/material.dart';

import '../../core/constants/app_constants.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/widgets/settings_section.dart';
import '../../core/widgets/shell_content.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  static const _mvpCapabilities = [
    'Generate Subtitles (SRT, VTT, TXT)',
    'Generate Karaoke videos',
    'Enhance Audio (noise reduction)',
    'Separate Vocals & Music stems',
    'Download processed outputs',
  ];

  static const _roadmapHighlights = [
    'Phase 10 — Authentication & user accounts',
    'Phase 11 — Billing & subscription tiers',
    'Phase 12 — Creator Tools (recorder, karaoke studio, media editors)',
    'Phase 13 — Voice cloning experiments (local PoC)',
    'Phase 14 — Hetzner production deployment',
    'Phase 15 — Roman Urdu & translation',
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ShellContent(
      title: 'Welcome back',
      subtitle:
          'VoxClone is your offline AI media studio — process video and audio '
          'locally with whisper.cpp, Demucs, and DeepFilterNet.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _OverviewCard(theme: theme),
          const SizedBox(height: AppSpacing.lg),
          SettingsSection(
            title: 'Current MVP capabilities',
            child: Column(
              children: [
                for (var i = 0; i < _mvpCapabilities.length; i++) ...[
                  if (i > 0) Divider(height: 1, color: theme.colorScheme.outline),
                  ListTile(
                    leading: const Icon(
                      Icons.check_rounded,
                      color: AppColors.success,
                      size: AppSpacing.iconSizeSm,
                    ),
                    title: Text(_mvpCapabilities[i]),
                    dense: true,
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          SettingsSection(
            title: 'Recent jobs',
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                children: [
                  Icon(
                    Icons.work_outline_rounded,
                    size: 40,
                    color: theme.colorScheme.onSurfaceVariant
                        .withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'No recent jobs yet',
                    style: theme.textTheme.titleSmall,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Job history will appear here once API integration is complete.',
                    style: theme.textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          InfoCallout(
            message: AppConstants.retentionNoticeBody,
            icon: Icons.schedule_rounded,
            tint: AppColors.warning,
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              _RetentionBadge(theme: theme),
              const SizedBox(width: AppSpacing.sm),
              Text(
                'Default retention period',
                style: theme.textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          SettingsSection(
            title: 'Roadmap',
            child: Column(
              children: [
                for (var i = 0; i < _roadmapHighlights.length; i++) ...[
                  if (i > 0) Divider(height: 1, color: theme.colorScheme.outline),
                  ListTile(
                    leading: Icon(
                      Icons.arrow_forward_rounded,
                      size: AppSpacing.iconSizeSm,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                    title: Text(
                      _roadmapHighlights[i],
                      style: theme.textTheme.bodyMedium,
                    ),
                    dense: true,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _OverviewCard extends StatelessWidget {
  const _OverviewCard({required this.theme});

  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.indigo.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
        border: Border.all(
          color: AppColors.indigo.withValues(alpha: 0.15),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.auto_awesome_rounded,
                color: AppColors.indigo,
              ),
              const SizedBox(width: AppSpacing.sm),
              Text(AppConstants.appName, style: theme.textTheme.titleLarge),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            AppConstants.appTagline,
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            'Use the sidebar to navigate core features. Creator tools, media '
            'editors, authentication, and billing are planned for upcoming phases.',
            style: theme.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _RetentionBadge extends StatelessWidget {
  const _RetentionBadge({required this.theme});

  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xxs,
      ),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppSpacing.chipRadius),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
      ),
      child: Text(
        '${AppConstants.outputRetentionDays} days',
        style: theme.textTheme.labelLarge?.copyWith(
          color: AppColors.warning,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
