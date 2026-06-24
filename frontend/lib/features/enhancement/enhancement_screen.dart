import 'package:flutter/material.dart';

import '../../core/widgets/placeholder_feature_screen.dart';

class EnhancementScreen extends PlaceholderFeatureScreen {
  const EnhancementScreen({super.key})
      : super(
          title: 'Enhance Audio',
          description:
              'Remove background noise and improve clarity using '
              'DeepFilterNet AI enhancement.',
          icon: Icons.graphic_eq_rounded,
        );
}
