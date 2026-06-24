import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/constants/app_constants.dart';
import '../../core/theme/theme_mode_provider.dart';

final apiBaseUrlProvider =
    StateNotifierProvider<ApiBaseUrlNotifier, String>((ref) {
  return ApiBaseUrlNotifier(ref.watch(sharedPreferencesProvider));
});

class ApiBaseUrlNotifier extends StateNotifier<String> {
  ApiBaseUrlNotifier(this._prefs)
      : super(
          _prefs.getString(AppConstants.apiBaseUrlPrefsKey) ??
              AppConstants.defaultApiBaseUrl,
        );

  final SharedPreferences _prefs;

  Future<void> setApiBaseUrl(String url) async {
    final trimmed = url.trim().replaceAll(RegExp(r'/+$'), '');
    state = trimmed.isEmpty ? AppConstants.defaultApiBaseUrl : trimmed;
    await _prefs.setString(AppConstants.apiBaseUrlPrefsKey, state);
  }
}
