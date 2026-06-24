import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/widgets/settings_section.dart';
import '../../core/widgets/shell_content.dart';

class BillingScreen extends StatelessWidget {
  const BillingScreen({super.key});

  static const _premiumCapabilities = [
    'Faster processing',
    'Priority queue',
    'Larger upload limits',
    'Future voice-cloning credits',
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ShellContent(
      title: 'Billing',
      subtitle: 'Billing arriving in Phase 11.',
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
            'Phase 11',
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
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpacing.lg),
            decoration: BoxDecoration(
              color: theme.colorScheme.surface,
              borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
              border: Border.all(color: theme.colorScheme.outline),
              boxShadow: [
                BoxShadow(
                  color: theme.colorScheme.shadow,
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Free Preview', style: theme.textTheme.titleMedium),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.sm,
                        vertical: AppSpacing.xxs,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.success.withValues(alpha: 0.12),
                        borderRadius:
                            BorderRadius.circular(AppSpacing.chipRadius),
                      ),
                      child: Text(
                        'Current plan',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: AppColors.success,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  'Explore all MVP features during the preview period. '
                  'No payment integration in this release.',
                  style: theme.textTheme.bodyMedium,
                ),
                const SizedBox(height: AppSpacing.md),
                FilledButton(
                  onPressed: null,
                  child: const Text('Upgrade — Phase 11'),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          SettingsSection(
            title: 'Future premium capabilities',
            child: Column(
              children: [
                for (var i = 0; i < _premiumCapabilities.length; i++) ...[
                  if (i > 0)
                    Divider(height: 1, color: theme.colorScheme.outline),
                  ListTile(
                    leading: Icon(
                      Icons.star_outline_rounded,
                      size: AppSpacing.iconSizeSm,
                      color: AppColors.mutedTeal,
                    ),
                    title: Text(_premiumCapabilities[i]),
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
