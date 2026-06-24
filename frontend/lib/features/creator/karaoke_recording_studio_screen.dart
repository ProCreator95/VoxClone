import 'package:flutter/material.dart';

import '../../core/widgets/phased_placeholder_screen.dart';

class KaraokeRecordingStudioScreen extends PhasedPlaceholderScreen {
  const KaraokeRecordingStudioScreen({super.key})
      : super(
          title: 'Karaoke Recording Studio',
          phaseLabel: 'Phase 12',
          description:
              'Record vocals over karaoke backing tracks with live monitoring '
              'and export options for creators.',
          icon: Icons.library_music_outlined,
          plannedFeatures: const [
            'Upload karaoke audio',
            'Upload karaoke video',
            'Record vocals while playback runs',
            'Live monitoring',
            'Download vocal track',
            'Download mixed output',
            'Download final video',
          ],
        );
}
