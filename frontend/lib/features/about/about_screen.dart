import 'package:flutter/material.dart';

import '../../core/constants/app_constants.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/widgets/settings_section.dart';
import '../../core/widgets/shell_content.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  static const _mvpFeatures = [
    _FeatureItem(Icons.subtitles_outlined, 'Subtitles'),
    _FeatureItem(Icons.lyrics_outlined, 'Karaoke'),
    _FeatureItem(Icons.graphic_eq_rounded, 'Audio Enhancement'),
    _FeatureItem(Icons.mic_external_on_outlined, 'Vocal Separation'),
    _FeatureItem(Icons.music_note_outlined, 'Music Separation'),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ShellContent(
      title: 'About',
      subtitle: AppConstants.appTagline,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: AppColors.indigo.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
            ),
            child: const Icon(
              Icons.auto_awesome_rounded,
              size: 36,
              color: AppColors.indigo,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Text(AppConstants.appName, style: theme.textTheme.headlineSmall),
          const SizedBox(height: AppSpacing.xl),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Current MVP Features',
              style: theme.textTheme.titleSmall,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Container(
            width: double.infinity,
            decoration: BoxDecoration(
              color: theme.colorScheme.surface,
              borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
              border: Border.all(color: theme.colorScheme.outline),
            ),
            child: Column(
              children: [
                for (var i = 0; i < _mvpFeatures.length; i++) ...[
                  if (i > 0)
                    Divider(height: 1, color: theme.colorScheme.outline),
                  ListTile(
                    leading: Icon(
                      _mvpFeatures[i].icon,
                      color: AppColors.mutedBlue,
                    ),
                    title: Text(_mvpFeatures[i].label),
                    dense: true,
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          InfoCallout(
            message:
                'Urdu Support (Experimental) — Urdu transcription is available '
                'via the API but is not production-grade. Quality may vary.',
            icon: Icons.translate_rounded,
            tint: AppColors.warning,
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            'Voice cloning remains experimental until GPU-backed infrastructure '
            'is justified commercially.',
            style: theme.textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.xl),
          Text(
            'Version ${AppConstants.appVersion}',
            style: theme.textTheme.labelMedium,
          ),
          const SizedBox(height: AppSpacing.xxs),
          Text(
            '© ${DateTime.now().year} VoxClone',
            style: theme.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _FeatureItem {
  const _FeatureItem(this.icon, this.label);

  final IconData icon;
  final String label;
}
