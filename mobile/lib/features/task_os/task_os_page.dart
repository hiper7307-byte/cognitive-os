import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/build_info.dart';
import 'llm_panel.dart';
import 'task_os_controller.dart';

class TaskOsPage extends StatefulWidget {
  const TaskOsPage({super.key});

  @override
  State<TaskOsPage> createState() => _TaskOsPageState();
}

class _TaskOsPageState extends State<TaskOsPage> {
  final TextEditingController _taskController = TextEditingController();
  final TextEditingController _memoryQueryController = TextEditingController();

  @override
  void initState() {
    super.initState();
    Future.microtask(() => context.read<TaskOsController>().refreshRecentMemory());
  }

  @override
  void dispose() {
    _taskController.dispose();
    _memoryQueryController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<TaskOsController>(
      builder: (context, controller, _) {
        return Scaffold(
          appBar: AppBar(
            title: const Text('AI OS / Agent Platform'),
            actions: [
              Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: Text(
                    'v${BuildInfo.version}',
                    style: const TextStyle(fontSize: 12),
                  ),
                ),
              ),
              IconButton(
                onPressed: controller.isBusy ? null : () => controller.refreshRecentMemory(),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          body: Column(
            children: [
              if (controller.isBusy) const LinearProgressIndicator(minHeight: 2),
              if (controller.error.isNotEmpty)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  color: Colors.red.withOpacity(0.1),
                  child: Text(
                    controller.error,
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.only(bottom: 12),
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        children: [
                          TextField(
                            controller: _taskController,
                            minLines: 1,
                            maxLines: 3,
                            decoration: const InputDecoration(
                              labelText: 'Task input',
                              hintText: 'e.g. save note build vector retrieval by friday',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Expanded(
                                child: ElevatedButton(
                                  onPressed: controller.isBusy
                                      ? null
                                      : () async {
                                          final text = _taskController.text.trim();
                                          if (text.isEmpty) return;
                                          await controller.sendTask(text);
                                        },
                                  child: const Text('Run /task'),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _memoryQueryController,
                            minLines: 1,
                            maxLines: 2,
                            decoration: const InputDecoration(
                              labelText: 'Memory query',
                              hintText: 'Search semantic/episodic/procedural memory',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Expanded(
                                child: OutlinedButton(
                                  onPressed: controller.isBusy
                                      ? null
                                      : () async {
                                          final q = _memoryQueryController.text.trim();
                                          if (q.isEmpty) return;
                                          await controller.queryMemory(q);
                                        },
                                  child: const Text('Run /memory/query'),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const LlmPanel(),
                    if (controller.lastTaskResponse != null)
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: _TaskResultCard(
                          taskId: controller.lastTaskResponse!.taskId,
                          intent: controller.lastTaskResponse!.intent,
                          ok: controller.lastTaskResponse!.ok,
                          message: controller.lastTaskResponse!.message,
                          data: controller.lastTaskResponse!.data,
                        ),
                      ),
                    const SizedBox(height: 8),
                    if (controller.memoryItems.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 32),
                        child: Center(child: Text('No memory items')),
                      )
                    else
                      ...controller.memoryItems.map(
                        (m) => Card(
                          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          child: ListTile(
                            title: Text(
                              m.content,
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              'id=${m.id} • ${m.memoryType} • ${m.createdAt}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _TaskResultCard extends StatelessWidget {
  final String taskId;
  final String intent;
  final bool ok;
  final String message;
  final Map<String, dynamic> data;

  const _TaskResultCard({
    required this.taskId,
    required this.intent,
    required this.ok,
    required this.message,
    required this.data,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: DefaultTextStyle(
          style: Theme.of(context).textTheme.bodyMedium ?? const TextStyle(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('task_id: $taskId'),
              Text('intent: $intent'),
              Text('ok: $ok'),
              Text('message: $message'),
              Text(
                'data: $data',
                softWrap: true,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
