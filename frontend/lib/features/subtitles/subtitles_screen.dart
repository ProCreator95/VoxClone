import 'package:flutter/material.dart';

import '../../core/widgets/placeholder_feature_screen.dart';

class SubtitlesScreen extends PlaceholderFeatureScreen {
  const SubtitlesScreen({super.key})
      : super(
          title: 'Generate Subtitles',
          description:
              'Upload media and generate SRT, VTT, and transcript files '
              'using whisper.cpp transcription.',
          icon: Icons.subtitles_outlined,
        );
}
