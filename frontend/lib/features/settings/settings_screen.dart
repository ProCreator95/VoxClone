import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants/app_constants.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/theme_mode_provider.dart';
import '../../core/widgets/settings_section.dart';
import '../../core/widgets/shell_content.dart';
import 'settings_provider.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _apiUrlController;

  @override
  void initState() {
    super.initState();
    _apiUrlController = TextEditingController();
  }

  @override
  void dispose() {
    _apiUrlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final apiUrl = ref.watch(apiBaseUrlProvider);
    final themeMode = ref.watch(themeModeProvider);

    if (_apiUrlController.text != apiUrl) {
      _apiUrlController.text = apiUrl;
    }

    return ShellContent(
      title: 'Settings',
      subtitle: 'Configure server connection, appearance, and data preferences.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SettingsSection(
            title: 'Server',
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Backend API URL', style: theme.textTheme.labelMedium),
                  const SizedBox(height: AppSpacing.sm),
                  TextField(
                    controller: _apiUrlController,
                    decoration: const InputDecoration(
                      hintText: 'http://10.0.2.2:8000',
                      prefixIcon: Icon(Icons.link_rounded),
                    ),
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                    onSubmitted: (value) => ref
                        .read(apiBaseUrlProvider.notifier)
                        .setApiBaseUrl(value),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Used in a future milestone to connect to the VoxClone '
                    'FastAPI backend. Android emulator: 10.0.2.2 · iOS sim: localhost',
                    style: theme.textTheme.bodySmall,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton.tonal(
                      onPressed: () => ref
                          .read(apiBaseUrlProvider.notifier)
                          .setApiBaseUrl(_apiUrlController.text),
                      child: const Text('Save URL'),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          SettingsSection(
            title: 'Appearance',
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: SegmentedButton<ThemeMode>(
                segments: const [
                  ButtonSegment(
                    value: ThemeMode.system,
                    label: Text('System'),
                    icon: Icon(Icons.brightness_auto_rounded, size: 18),
                  ),
                  ButtonSegment(
                    value: ThemeMode.light,
                    label: Text('Light'),
                    icon: Icon(Icons.light_mode_outlined, size: 18),
                  ),
                  ButtonSegment(
                    value: ThemeMode.dark,
                    label: Text('Dark'),
                    icon: Icon(Icons.dark_mode_outlined, size: 18),
                  ),
                ],
                selected: {themeMode},
                onSelectionChanged: (selection) {
                  ref.read(themeModeProvider.notifier).setThemeMode(
                        selection.first,
                      );
                },
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          SettingsSection(
            title: 'Data & Retention',
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  InfoCallout(
                    message: AppConstants.retentionNoticeBody,
                    icon: Icons.schedule_rounded,
                    tint: AppColors.warning,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Row(
                    children: [
                      Text(
                        'Current default retention',
                        style: theme.textTheme.labelMedium,
                      ),
                      const Spacer(),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.sm,
                          vertical: AppSpacing.xxs,
                        ),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primaryContainer,
                          borderRadius:
                              BorderRadius.circular(AppSpacing.chipRadius),
                        ),
                        child: Text(
                          '${AppConstants.outputRetentionDays} days',
                          style: theme.textTheme.labelLarge?.copyWith(
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          Center(
            child: Text(
              'Version ${AppConstants.appVersion}',
              style: theme.textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}
