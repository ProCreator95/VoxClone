import 'package:flutter/material.dart';

import '../../core/widgets/placeholder_feature_screen.dart';

class KaraokeScreen extends PlaceholderFeatureScreen {
  const KaraokeScreen({super.key})
      : super(
          title: 'Generate Karaoke',
          description:
              'Create word-level highlighted karaoke videos with multiple '
              'output modes including instrumental backing.',
          icon: Icons.lyrics_outlined,
        );
}
