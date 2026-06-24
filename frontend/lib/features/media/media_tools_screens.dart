import 'package:flutter/material.dart';

import '../../core/widgets/phased_placeholder_screen.dart';

class AudioCutterScreen extends PhasedPlaceholderScreen {
  const AudioCutterScreen({super.key})
      : super(
          title: 'Audio Cutter',
          phaseLabel: 'Phase 12',
          description:
              'Trim and split audio files with precise waveform selection.',
          icon: Icons.content_cut_rounded,
          plannedFeatures: const [
            'Upload audio files',
            'Visual waveform editor',
            'Set in/out points',
            'Split at markers',
            'Export trimmed WAV / MP3',
            'Non-destructive preview',
          ],
        );
}

class AudioJoinerScreen extends PhasedPlaceholderScreen {
  const AudioJoinerScreen({super.key})
      : super(
          title: 'Audio Joiner',
          phaseLabel: 'Phase 12',
          description: 'Combine multiple audio clips into a single track.',
          icon: Icons.merge_type_rounded,
          plannedFeatures: const [
            'Upload multiple audio files',
            'Drag to reorder clips',
            'Crossfade between segments',
            'Normalize volume levels',
            'Export merged WAV / MP3',
          ],
        );
}

class VideoCutterScreen extends PhasedPlaceholderScreen {
  const VideoCutterScreen({super.key})
      : super(
          title: 'Video Cutter',
          phaseLabel: 'Phase 12',
          description: 'Trim video files without re-encoding when possible.',
          icon: Icons.movie_creation_outlined,
          plannedFeatures: const [
            'Upload video files',
            'Timeline scrubber',
            'Set start/end timestamps',
            'Preview before export',
            'Export trimmed MP4',
          ],
        );
}

class VideoJoinerScreen extends PhasedPlaceholderScreen {
  const VideoJoinerScreen({super.key})
      : super(
          title: 'Video Joiner',
          phaseLabel: 'Phase 12',
          description: 'Merge multiple video clips into one continuous file.',
          icon: Icons.video_library_outlined,
          plannedFeatures: const [
            'Upload multiple video files',
            'Reorder clips on timeline',
            'Match resolution and frame rate',
            'Export merged MP4',
          ],
        );
}
