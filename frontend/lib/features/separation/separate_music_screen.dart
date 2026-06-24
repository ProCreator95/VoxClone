import 'package:flutter/material.dart';

import '../../core/widgets/placeholder_feature_screen.dart';

class SeparateMusicScreen extends PlaceholderFeatureScreen {
  const SeparateMusicScreen({super.key})
      : super(
          title: 'Separate Music',
          description:
              'Extract the instrumental stem from your track. Both vocal '
              'and music stems are created during separation.',
          icon: Icons.music_note_outlined,
        );
}
