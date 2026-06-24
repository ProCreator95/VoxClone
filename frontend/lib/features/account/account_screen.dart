import 'package:flutter/material.dart';

import '../../core/widgets/phased_placeholder_screen.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const PhasedPlaceholderScreen(
      title: 'Account',
      phaseLabel: 'Phase 10',
      description: 'Authentication arriving in Phase 10.',
      icon: Icons.person_outline_rounded,
      disabledActions: [
        (label: 'Sign In', icon: Icons.login_rounded),
        (label: 'Create Account', icon: Icons.person_add_outlined),
      ],
    );
  }
}
