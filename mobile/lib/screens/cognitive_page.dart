import 'package:flutter/material.dart';
import '../data/api/ai_os_api.dart';

class CognitivePage extends StatefulWidget {
  const CognitivePage({super.key});

  @override
  State<CognitivePage> createState() => _CognitivePageState();
}

class _CognitivePageState extends State<CognitivePage> {
  final TextEditingController _controller = TextEditingController();
  final AiOsApi _api = AiOsApi();

  final List<String> _timeline = [];
  bool _busy = false;

  Future<void> _run() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _busy) return;

    setState(() {
      _busy = true;
      _timeline.clear();
    });

    await for (final event in _api.streamAgent(prompt: text)) {
      setState(() {
        _timeline.add(event.toString());
      });
    }

    setState(() {
      _busy = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Cognitive Execution Timeline',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _controller,
            decoration: const InputDecoration(
              hintText: 'Run full agent with tools...',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: _busy ? null : _run,
            child: const Text('Run Agent'),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: ListView.builder(
              itemCount: _timeline.length,
              itemBuilder: (_, i) => Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    _timeline[i],
                    style: const TextStyle(fontFamily: 'monospace'),
                  ),
                ),
              ),
            ),
          )
        ],
      ),
    );
  }
}
