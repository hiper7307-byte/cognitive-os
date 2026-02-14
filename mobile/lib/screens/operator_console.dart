import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/task_os/task_os_controller.dart';

class OperatorConsole extends StatefulWidget {
  const OperatorConsole({super.key});

  @override
  State<OperatorConsole> createState() => _OperatorConsoleState();
}

class _OperatorConsoleState extends State<OperatorConsole> {
  final TextEditingController _memoryQuery = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final ctrl = context.watch<TaskOsController>();

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const Text(
            'Operator Console',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _memoryQuery,
            decoration: const InputDecoration(
              hintText: 'Direct memory query',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          ElevatedButton(
            onPressed: ctrl.isBusy
                ? null
                : () async {
                    final q = _memoryQuery.text.trim();
                    if (q.isEmpty) return;
                    await ctrl.queryMemory(q);
                  },
            child: const Text('Query Memory'),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: ListView(
              children: ctrl.memoryItems
                  .map(
                    (m) => ListTile(
                      title: Text(m.content),
                      subtitle: Text(m.id.toString()),
                    ),
                  )
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }
}
