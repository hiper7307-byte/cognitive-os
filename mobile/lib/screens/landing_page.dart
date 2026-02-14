import 'package:flutter/material.dart';

class LandingPage extends StatelessWidget {
  const LandingPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 64, vertical: 48),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          Text(
            'Cognitive OS',
            style: TextStyle(fontSize: 42, fontWeight: FontWeight.bold),
          ),
          SizedBox(height: 16),
          Text(
            'Personal Cognitive Infrastructure.\nMemory. Identity. Arbitration. Execution.',
            style: TextStyle(fontSize: 18),
          ),
          SizedBox(height: 32),
          Text(
            'Built for operators who require persistent reasoning,\nstructured memory, and meta-evaluation.',
            style: TextStyle(fontSize: 16),
          ),
        ],
      ),
    );
  }
}
