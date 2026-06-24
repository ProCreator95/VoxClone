import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import 'settings_section.dart';
import 'shell_content.dart';

/// Reusable placeholder for future-phase features.
class PhasedPlaceholderScreen extends StatelessWidget {
  const PhasedPlaceholderScreen({
    super.key,
    required this.title,
    required this.phaseLabel,
    required this.description,
    this.icon = Icons.construction_outlined,
    this.plannedFeatures = const [],
    this.extraSections = const [],
    this.disabledActions = const [],
  });

  final String title;
  final String phaseLabel;
  final String description;
  final IconData icon;
  final List<String> plannedFeatures;
  final List<Widget> extraSections;
  final List<({String label, IconData icon})> disabledActions;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ShellContent(
      title: title,
      subtitle: description,
      actions: [
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.sm,
            vertical: AppSpacing.xs,
          ),
          decoration: BoxDecoration(
            color: AppColors.warning.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(AppSpacing.chipRadius),
            border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
          ),
          child: Text(
            phaseLabel,
            style: theme.textTheme.labelSmall?.copyWith(
              color: AppColors.warning,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: theme.colorScheme.primaryContainer,
                borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
              ),
              child: Icon(icon, size: 32, color: theme.colorScheme.primary),
            ),
          ),
          const SizedBox(height: AppSpacing.xl),
          if (plannedFeatures.isNotEmpty) ...[
            SettingsSection(
              title: 'Planned capabilities',
              child: Column(
                children: [
                  for (var i = 0; i < plannedFeatures.length; i++) ...[
                    if (i > 0)
                      Divider(height: 1, color: theme.colorScheme.outline),
                    ListTile(
                      leading: Icon(
                        Icons.check_circle_outline_rounded,
                        size: AppSpacing.iconSizeSm,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                      title: Text(
                        plannedFeatures[i],
                        style: theme.textTheme.bodyMedium,
                      ),
                      dense: true,
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
          ],
          ...extraSections,
          if (disabledActions.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                for (final action in disabledActions)
                  FilledButton.icon(
                    onPressed: null,
                    icon: Icon(action.icon, size: 18),
                    label: Text(action.label),
                  ),
              ],
            ),
          ],
          const SizedBox(height: AppSpacing.lg),
          InfoCallout(
            message: 'No implementation yet — arriving in $phaseLabel.',
            icon: Icons.schedule_rounded,
            tint: AppColors.mutedBlue,
          ),
        ],
      ),
    );
  }
}
