import 'package:flutter/foundation.dart';

import '../../data/api/ai_os_api.dart';
import '../../data/models/task_models.dart';

class TaskOsController extends ChangeNotifier {
  final AiOsApi _api;

  TaskOsController({AiOsApi? api}) : _api = api ?? AiOsApi();

  bool _isBusy = false;
  String _error = '';
  TaskResponse? _lastTaskResponse;
  List<MemoryItem> _memoryItems = <MemoryItem>[];

  bool get isBusy => _isBusy;
  String get error => _error;
  TaskResponse? get lastTaskResponse => _lastTaskResponse;
  List<MemoryItem> get memoryItems => List<MemoryItem>.unmodifiable(_memoryItems);

  Future<void> sendTask(String text) async {
    if (_isBusy) return;
    _setBusy(true);
    _setError('');

    try {
      final response = await _api.runTask(text);
      _lastTaskResponse = response;
      notifyListeners();
      await refreshRecentMemory();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setBusy(false);
    }
  }

  Future<void> refreshRecentMemory({String? memoryType, int limit = 50}) async {
    if (_isBusy) return;
    _setBusy(true);
    _setError('');

    try {
      final response = await _api.recentMemory(memoryType: memoryType, limit: limit);
      _memoryItems = response.results;
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setBusy(false);
    }
  }

  Future<void> queryMemory(String query, {List<String>? types, int limit = 20}) async {
    if (_isBusy) return;
    _setBusy(true);
    _setError('');

    try {
      final response = await _api.queryMemory(query: query, types: types, limit: limit);
      _memoryItems = response.results;
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setBusy(false);
    }
  }

  void _setBusy(bool value) {
    _isBusy = value;
    notifyListeners();
  }

  void _setError(String value) {
    _error = value;
    notifyListeners();
  }

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }
}
