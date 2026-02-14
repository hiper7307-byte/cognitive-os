class TaskRequest {
  final String text;

  TaskRequest({required this.text});

  Map<String, dynamic> toJson() {
    return {'text': text};
  }
}

class TaskResponse {
  final String taskId;
  final String intent;
  final bool ok;
  final String message;
  final Map<String, dynamic> data;

  TaskResponse({
    required this.taskId,
    required this.intent,
    required this.ok,
    required this.message,
    required this.data,
  });

  factory TaskResponse.fromJson(Map<String, dynamic> json) {
    return TaskResponse(
      taskId: (json['task_id'] ?? '').toString(),
      intent: (json['intent'] ?? '').toString(),
      ok: json['ok'] == true,
      message: (json['message'] ?? '').toString(),
      data: (json['data'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{},
    );
  }
}

class MemoryItem {
  final int id;
  final String memoryType;
  final String content;
  final Map<String, dynamic> metadata;
  final String? sourceTaskId;
  final String createdAt;
  final String updatedAt;

  MemoryItem({
    required this.id,
    required this.memoryType,
    required this.content,
    required this.metadata,
    required this.sourceTaskId,
    required this.createdAt,
    required this.updatedAt,
  });

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: (json['id'] as num?)?.toInt() ?? 0,
      memoryType: (json['memory_type'] ?? '').toString(),
      content: (json['content'] ?? '').toString(),
      metadata: (json['metadata'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{},
      sourceTaskId: json['source_task_id']?.toString(),
      createdAt: (json['created_at'] ?? '').toString(),
      updatedAt: (json['updated_at'] ?? '').toString(),
    );
  }
}

class MemoryQueryResponse {
  final bool ok;
  final int count;
  final List<MemoryItem> results;

  MemoryQueryResponse({
    required this.ok,
    required this.count,
    required this.results,
  });

  factory MemoryQueryResponse.fromJson(Map<String, dynamic> json) {
    final list = (json['results'] as List?) ?? <dynamic>[];
    return MemoryQueryResponse(
      ok: json['ok'] == true,
      count: (json['count'] as num?)?.toInt() ?? 0,
      results: list
          .whereType<Map>()
          .map((e) => MemoryItem.fromJson(e.cast<String, dynamic>()))
          .toList(),
    );
  }
}

class LlmChatResponse {
  final bool ok;
  final String taskId;
  final String message;
  final int memoryUsed;

  LlmChatResponse({
    required this.ok,
    required this.taskId,
    required this.message,
    required this.memoryUsed,
  });

  factory LlmChatResponse.fromJson(Map<String, dynamic> json) {
    return LlmChatResponse(
      ok: json['ok'] == true,
      taskId: (json['task_id'] ?? '').toString(),
      message: (json['message'] ?? '').toString(),
      memoryUsed: (json['memory_used'] as num?)?.toInt() ?? 0,
    );
  }
}
