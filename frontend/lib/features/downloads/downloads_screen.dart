import 'package:flutter/material.dart';

import '../../core/widgets/placeholder_feature_screen.dart';

class DownloadsScreen extends PlaceholderFeatureScreen {
  const DownloadsScreen({super.key})
      : super(
          title: 'Downloads',
          description:
              'Browse, download, and share your processed outputs. '
              'Expiry warnings will appear based on the retention policy.',
          icon: Icons.download_rounded,
        );
}
