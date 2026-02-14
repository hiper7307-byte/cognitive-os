import 'package:flutter/material.dart';
import 'consumer_page.dart';
import 'cognitive_page.dart';
import 'operator_page.dart';

class DashboardShell extends StatefulWidget {
  const DashboardShell({super.key});

  @override
  State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell> {
  int _index = 0;

  final _pages = const [
    ConsumerPage(),
    CognitivePage(),
    OperatorPage(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            backgroundColor: const Color(0xFF11161F),
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            labelType: NavigationRailLabelType.all,
            destinations: const [
              NavigationRailDestination(
                icon: Icon(Icons.chat_bubble_outline),
                label: Text('Consumer'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.psychology),
                label: Text('Cognitive'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.settings),
                label: Text('Operator'),
              ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: _pages[_index]),
        ],
      ),
    );
  }
}
