import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/widgets/phased_placeholder_screen.dart';
import '../../core/widgets/settings_section.dart';

class VoiceRecorderStudioScreen extends PhasedPlaceholderScreen {
  VoiceRecorderStudioScreen({super.key})
      : super(
          title: 'Voice Recorder Studio',
          phaseLabel: 'Phase 12',
          description:
              'Record, enhance, and export studio-quality audio for podcasts, '
              'voiceovers, and future voice-cloning training samples.',
          icon: Icons.mic_rounded,
          plannedFeatures: const [
            'Record microphone audio',
            'Noise reduction',
            'Reverb',
            'Echo',
            'Compression',
            'EQ presets',
            'Podcast mode',
            'Radio voice mode',
            'Vocal enhancement',
            'Save recordings',
            'Export WAV',
            'Export MP3',
          ],
          extraSections: [
            SettingsSection(
              title: 'Future feature',
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.record_voice_over_outlined,
                      size: AppSpacing.iconSizeSm,
                      color: AppColors.mutedTeal,
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    const Expanded(
                      child: Text(
                        'Practice Voice Cloning — users will record training '
                        'samples and store voice profiles for future cloning '
                        'experiments (Phase 13).',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
}
