import 'package:flutter/material.dart';

import '../../core/widgets/placeholder_feature_screen.dart';

class SeparateVocalsScreen extends PlaceholderFeatureScreen {
  const SeparateVocalsScreen({super.key})
      : super(
          title: 'Separate Vocals',
          description:
              'Isolate vocals from your track using Demucs source '
              'separation. Output is a high-quality WAV stem.',
          icon: Icons.mic_external_on_outlined,
        );
}
