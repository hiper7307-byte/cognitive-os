import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/task_os/task_os_controller.dart';

class ConsumerMode extends StatefulWidget {
  const ConsumerMode({super.key});

  @override
  State<ConsumerMode> createState() => _ConsumerModeState();
}

class _ConsumerModeState extends State<ConsumerMode> {
  final TextEditingController _controller = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final ctrl = context.watch<TaskOsController>();

    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const Text(
            'Ask your Cognitive OS',
            style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _controller,
            minLines: 1,
            maxLines: 3,
            decoration: const InputDecoration(
              hintText: 'What would you like to execute?',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: ctrl.isBusy
                ? null
                : () async {
                    final text = _controller.text.trim();
                    if (text.isEmpty) return;
                    await ctrl.sendTask(text);
                  },
            child: const Text('Execute'),
          ),
          const SizedBox(height: 32),
          if (ctrl.lastTaskResponse != null)
            Expanded(
              child: SingleChildScrollView(
                child: _ResultBlock(
                  ok: ctrl.lastTaskResponse!.ok,
                  message: ctrl.lastTaskResponse!.message,
                  data: ctrl.lastTaskResponse!.data,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ResultBlock extends StatelessWidget {
  final bool ok;
  final String message;
  final Map<String, dynamic> data;

  const _ResultBlock({
    required this.ok,
    required this.message,
    required this.data,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF121821),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            ok ? 'Success' : 'Failure',
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: ok ? Colors.green : Colors.red,
            ),
          ),
          const SizedBox(height: 12),
          if (message.isNotEmpty) Text(message),
          const SizedBox(height: 12),
          Text(
            const JsonEncoder.withIndent('  ').convert(data),
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }
}
