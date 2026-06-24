import 'package:flutter/material.dart';

/// Sidebar / drawer navigation model.
class NavItem {
  const NavItem({
    required this.label,
    required this.icon,
    required this.path,
    this.enabled = true,
    this.badge,
  });

  final String label;
  final IconData icon;
  final String path;
  final bool enabled;
  final String? badge;
}

class NavSection {
  const NavSection({this.label, required this.items});

  final String? label;
  final List<NavItem> items;
}

/// Application navigation tree — single source for sidebar and drawer.
abstract final class NavigationConfig {
  static const double sidebarWidthDesktop = 280;
  static const double sidebarWidthTablet = 240;
  static const double mobileBreakpoint = 768;

  static const homePath = '/home';

  static const sections = <NavSection>[
    NavSection(
      items: [
        NavItem(
          label: 'Home',
          icon: Icons.home_outlined,
          path: '/home',
        ),
      ],
    ),
    NavSection(
      label: 'Core Features',
      items: [
        NavItem(
          label: 'Generate Subtitles',
          icon: Icons.subtitles_outlined,
          path: '/subtitles',
        ),
        NavItem(
          label: 'Generate Karaoke',
          icon: Icons.lyrics_outlined,
          path: '/karaoke',
        ),
        NavItem(
          label: 'Enhance Audio',
          icon: Icons.graphic_eq_rounded,
          path: '/enhance',
        ),
        NavItem(
          label: 'Separate Vocals',
          icon: Icons.mic_external_on_outlined,
          path: '/separate-vocals',
        ),
        NavItem(
          label: 'Separate Music',
          icon: Icons.music_note_outlined,
          path: '/separate-music',
        ),
        NavItem(
          label: 'Downloads',
          icon: Icons.download_rounded,
          path: '/downloads',
        ),
      ],
    ),
    NavSection(
      label: 'Creator Tools',
      items: [
        NavItem(
          label: 'Voice Recorder Studio',
          icon: Icons.mic_rounded,
          path: '/creator/voice-recorder',
          badge: 'Soon',
        ),
        NavItem(
          label: 'Karaoke Recording Studio',
          icon: Icons.library_music_outlined,
          path: '/creator/karaoke-recording',
          badge: 'Soon',
        ),
      ],
    ),
    NavSection(
      label: 'Media Tools',
      items: [
        NavItem(
          label: 'Audio Cutter',
          icon: Icons.content_cut_rounded,
          path: '/media/audio-cutter',
          badge: 'Soon',
        ),
        NavItem(
          label: 'Audio Joiner',
          icon: Icons.merge_type_rounded,
          path: '/media/audio-joiner',
          badge: 'Soon',
        ),
        NavItem(
          label: 'Video Cutter',
          icon: Icons.movie_creation_outlined,
          path: '/media/video-cutter',
          badge: 'Soon',
        ),
        NavItem(
          label: 'Video Joiner',
          icon: Icons.video_library_outlined,
          path: '/media/video-joiner',
          badge: 'Soon',
        ),
      ],
    ),
    NavSection(
      label: 'Account',
      items: [
        NavItem(
          label: 'Account',
          icon: Icons.person_outline_rounded,
          path: '/account',
          badge: 'Phase 10',
        ),
        NavItem(
          label: 'Billing',
          icon: Icons.credit_card_outlined,
          path: '/billing',
          badge: 'Phase 11',
        ),
      ],
    ),
    NavSection(
      label: 'System',
      items: [
        NavItem(
          label: 'Settings',
          icon: Icons.settings_outlined,
          path: '/settings',
        ),
        NavItem(
          label: 'About',
          icon: Icons.info_outline_rounded,
          path: '/about',
        ),
      ],
    ),
  ];

  static String? titleForPath(String path) {
    for (final section in sections) {
      for (final item in section.items) {
        if (item.path == path) return item.label;
      }
    }
    return null;
  }
}
