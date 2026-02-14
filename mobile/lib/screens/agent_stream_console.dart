import 'package:flutter/material.dart';
import '../data/api/ai_os_api.dart';

class AgentStreamConsole extends StatefulWidget {
  const AgentStreamConsole({super.key});

  @override
  State<AgentStreamConsole> createState() => _AgentStreamConsoleState();
}

class _AgentStreamConsoleState extends State<AgentStreamConsole> {
  final TextEditingController _controller = TextEditingController();
  final AiOsApi _api = AiOsApi();

  final List<String> _events = [];
  bool _busy = false;

  Future<void> _run() async {
    final prompt = _controller.text.trim();
    if (prompt.isEmpty || _busy) return;

    setState(() {
      _busy = true;
      _events.clear();
    });

    await for (final event in _api.streamAgent(prompt: prompt)) {
      setState(() {
        _events.add(event.toString());
      });
    }

    setState(() {
      _busy = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(title: const Text('Agent V2 Stream')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            TextField(
              controller: _controller,
              decoration: const InputDecoration(
                hintText: 'Run agent with tools...',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _busy ? null : _run,
              child: const Text('Run Agent Stream'),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.builder(
                itemCount: _events.length,
                itemBuilder: (_, i) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Text(
                    _events[i],
                    style: const TextStyle(
                      color: Colors.greenAccent,
                      fontFamily: 'monospace',
                    ),
                  ),
                ),
              ),
            )
          ],
        ),
      ),
    );
  }
}
