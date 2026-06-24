import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:voxclone_app/app.dart';
import 'package:voxclone_app/core/constants/app_constants.dart';
import 'package:voxclone_app/core/theme/theme_mode_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('Home screen renders welcome and MVP capabilities', (tester) async {
    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
        ],
        child: const VoxCloneApp(),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text(AppConstants.appName), findsWidgets);
    expect(find.text('CURRENT MVP CAPABILITIES'), findsOneWidget);
    expect(find.textContaining('${AppConstants.outputRetentionDays} days'),
        findsWidgets);
  });
}
