import 'package:flutter/material.dart';
import '../../data/api/ai_os_api.dart';

class LlmPanel extends StatefulWidget {
  const LlmPanel({super.key});

  @override
  State<LlmPanel> createState() => _LlmPanelState();
}

class _LlmPanelState extends State<LlmPanel> {
  final TextEditingController _controller = TextEditingController();
  final AiOsApi _api = AiOsApi();

  String _output = '';
  bool _busy = false;

  Future<void> _run() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _busy) return;

    setState(() {
      _busy = true;
      _output = '';
    });

    try {
      await for (final token in _api.streamLlm(message: text)) {
        setState(() {
          _output += token;
        });
      }
    } catch (e) {
      setState(() {
        _output = 'Error: $e';
      });
    } finally {
      setState(() {
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            TextField(
              controller: _controller,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: 'Ask Cognitive OS (Streaming)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _busy ? null : _run,
              child: Text(_busy ? 'Streaming...' : 'Stream LLM'),
            ),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.black87,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                _output,
                style: const TextStyle(
                  color: Colors.greenAccent,
                  fontFamily: 'monospace',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
