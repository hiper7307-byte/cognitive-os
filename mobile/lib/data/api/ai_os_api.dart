import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import '../../core/config.dart';
import '../../core/user_identity.dart';
import '../models/task_models.dart';

class AiOsApi {
  final http.Client _client;

  AiOsApi({http.Client? client}) : _client = client ?? http.Client();

  Uri _uri(String path) => Uri.parse('${AppConfig.apiBaseUrl}$path');

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'X-User-Id': UserIdentity.getUserId(),
      };

  // =========================
  // TASK
  // =========================

  Future<TaskResponse> runTask(String text) async {
    final req = TaskRequest(text: text);

    final res = await _client.post(
      _uri('/task'),
      headers: _headers,
      body: jsonEncode(req.toJson()),
    );

    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('runTask failed: ${res.statusCode} ${res.body}');
    }

    final body = jsonDecode(res.body) as Map<String, dynamic>;
    return TaskResponse.fromJson(body);
  }

  // =========================
  // MEMORY
  // =========================

  Future<MemoryQueryResponse> recentMemory({
    String? memoryType,
    int limit = 50,
  }) async {
    final qp = <String, String>{
      'limit': '$limit',
      if (memoryType != null && memoryType.isNotEmpty)
        'memory_type': memoryType,
    };

    final uri = _uri('/memory/recent').replace(queryParameters: qp);

    final res = await _client.get(
      uri,
      headers: {
        'X-User-Id': UserIdentity.getUserId(),
      },
    );

    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('recentMemory failed: ${res.statusCode} ${res.body}');
    }

    final body = jsonDecode(res.body) as Map<String, dynamic>;
    return MemoryQueryResponse.fromJson(body);
  }

  Future<MemoryQueryResponse> queryMemory({
    required String query,
    List<String>? types,
    int limit = 20,
  }) async {
    final payload = <String, dynamic>{
      'query': query,
      'types': types,
      'limit': limit,
    };

    final res = await _client.post(
      _uri('/memory/query'),
      headers: _headers,
      body: jsonEncode(payload),
    );

    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('queryMemory failed: ${res.statusCode} ${res.body}');
    }

    final body = jsonDecode(res.body) as Map<String, dynamic>;
    return MemoryQueryResponse.fromJson(body);
  }

  // =========================
  // LLM (Non-stream)
  // =========================

  Future<LlmChatResponse> llmChat({
    required String message,
    bool useMemory = true,
    int memoryLimit = 8,
  }) async {
    final payload = <String, dynamic>{
      'message': message,
      'use_memory': useMemory,
      'memory_limit': memoryLimit,
    };

    final res = await _client.post(
      _uri('/llm/chat'),
      headers: _headers,
      body: jsonEncode(payload),
    );

    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('llmChat failed: ${res.statusCode} ${res.body}');
    }

    final body = jsonDecode(res.body) as Map<String, dynamic>;
    return LlmChatResponse.fromJson(body);
  }

  // =========================
  // STREAMING LLM
  // =========================

  Stream<String> streamLlm({
    required String message,
    bool useMemory = true,
    int memoryLimit = 8,
  }) async* {
    final request = http.Request(
      'POST',
      _uri('/llm/stream'),
    );

    request.headers.addAll(_headers);

    request.body = jsonEncode({
      'message': message,
      'use_memory': useMemory,
      'memory_limit': memoryLimit,
    });

    final response = await _client.send(request);

    if (response.statusCode != 200) {
      throw Exception('Streaming failed: ${response.statusCode}');
    }

    final stream = response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter());

    await for (final line in stream) {
      if (line.startsWith('data:')) {
        final payload = line.substring(5).trim();

        if (payload.contains('"done"')) break;

        final decoded = jsonDecode(payload);
        if (decoded['token'] != null) {
          yield decoded['token'];
        }
      }
    }
  }

  // =========================
  // STREAMING AGENT V2
  // =========================

  Stream<Map<String, dynamic>> streamAgent({
    required String prompt,
  }) async* {
    final request = http.Request(
      'POST',
      _uri('/agent/v2/stream'),
    );

    request.headers.addAll(_headers);

    request.body = jsonEncode({
      'prompt': prompt,
      'max_iterations': 8,
      'allow_tools': true,
      'timeout_ms': 30000,
    });

    final response = await _client.send(request);

    if (response.statusCode != 200) {
      throw Exception('Agent streaming failed: ${response.statusCode}');
    }

    final stream = response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter());

    await for (final line in stream) {
      if (line.startsWith('data:')) {
        final payload = line.substring(5).trim();

        if (payload.contains('"done"')) break;

        yield jsonDecode(payload);
      }
    }
  }

  void dispose() {
    _client.close();
  }
}
