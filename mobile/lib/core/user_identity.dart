import 'dart:html' as html;
import 'package:uuid/uuid.dart';

class UserIdentity {
  static const _storageKey = 'ai_os_user_id';
  static final _uuid = const Uuid();

  static String getUserId() {
    final existing = html.window.localStorage[_storageKey];
    if (existing != null && existing.isNotEmpty) {
      return existing;
    }

    final newId = _uuid.v4();
    html.window.localStorage[_storageKey] = newId;
    return newId;
  }
}
