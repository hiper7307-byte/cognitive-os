import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/task_os/task_os_controller.dart';

class CognitiveDashboard extends StatelessWidget {
  const CognitiveDashboard({super.key});

  @override
  Widget build(BuildContext context) {
    final ctrl = context.watch<TaskOsController>();

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Cognitive Memory Overview',
            style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: ListView.builder(
              itemCount: ctrl.memoryItems.length,
              itemBuilder: (context, index) {
                final m = ctrl.memoryItems[index];
                return Card(
                  child: ListTile(
                    title: Text(m.content),
                    subtitle: Text(
                      '${m.memoryType} • ${m.createdAt}',
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
