import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/about/about_screen.dart';
import '../../features/account/account_screen.dart';
import '../../features/billing/billing_screen.dart';
import '../../features/creator/karaoke_recording_studio_screen.dart';
import '../../features/creator/voice_recorder_studio_screen.dart';
import '../../features/downloads/downloads_screen.dart';
import '../../features/enhancement/enhancement_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/karaoke/karaoke_screen.dart';
import '../../features/media/media_tools_screens.dart';
import '../../features/separation/separate_music_screen.dart';
import '../../features/separation/separate_vocals_screen.dart';
import '../../features/settings/settings_screen.dart';
import '../../features/subtitles/subtitles_screen.dart';
import '../widgets/app_shell.dart';

final GlobalKey<NavigatorState> rootNavigatorKey = GlobalKey<NavigatorState>();

GoRouter createAppRouter() {
  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: '/home',
    redirect: (context, state) {
      final path = state.uri.path;
      if (path == '/' || path == '/dashboard') return '/home';
      return null;
    },
    routes: [
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(
            path: '/home',
            name: 'home',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const HomeScreen(),
            ),
          ),
          GoRoute(
            path: '/subtitles',
            name: 'subtitles',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const SubtitlesScreen(),
            ),
          ),
          GoRoute(
            path: '/karaoke',
            name: 'karaoke',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const KaraokeScreen(),
            ),
          ),
          GoRoute(
            path: '/enhance',
            name: 'enhance',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const EnhancementScreen(),
            ),
          ),
          GoRoute(
            path: '/separate-vocals',
            name: 'separate-vocals',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const SeparateVocalsScreen(),
            ),
          ),
          GoRoute(
            path: '/separate-music',
            name: 'separate-music',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const SeparateMusicScreen(),
            ),
          ),
          GoRoute(
            path: '/downloads',
            name: 'downloads',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const DownloadsScreen(),
            ),
          ),
          GoRoute(
            path: '/creator/voice-recorder',
            name: 'voice-recorder',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: VoiceRecorderStudioScreen(),
            ),
          ),
          GoRoute(
            path: '/creator/karaoke-recording',
            name: 'karaoke-recording',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const KaraokeRecordingStudioScreen(),
            ),
          ),
          GoRoute(
            path: '/media/audio-cutter',
            name: 'audio-cutter',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const AudioCutterScreen(),
            ),
          ),
          GoRoute(
            path: '/media/audio-joiner',
            name: 'audio-joiner',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const AudioJoinerScreen(),
            ),
          ),
          GoRoute(
            path: '/media/video-cutter',
            name: 'video-cutter',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const VideoCutterScreen(),
            ),
          ),
          GoRoute(
            path: '/media/video-joiner',
            name: 'video-joiner',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const VideoJoinerScreen(),
            ),
          ),
          GoRoute(
            path: '/account',
            name: 'account',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const AccountScreen(),
            ),
          ),
          GoRoute(
            path: '/billing',
            name: 'billing',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const BillingScreen(),
            ),
          ),
          GoRoute(
            path: '/settings',
            name: 'settings',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const SettingsScreen(),
            ),
          ),
          GoRoute(
            path: '/about',
            name: 'about',
            pageBuilder: (context, state) => _noTransitionPage(
              state: state,
              child: const AboutScreen(),
            ),
          ),
        ],
      ),
    ],
  );
}

CustomTransitionPage<void> _noTransitionPage({
  required GoRouterState state,
  required Widget child,
}) {
  return CustomTransitionPage<void>(
    key: state.pageKey,
    child: child,
    transitionDuration: Duration.zero,
    reverseTransitionDuration: Duration.zero,
    transitionsBuilder: (context, animation, secondaryAnimation, child) =>
        child,
  );
}
