import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/config.dart';
import 'features/task_os/task_os_controller.dart';
import 'ui/app_shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AiOsApp());
}

class AiOsApp extends StatelessWidget {
  const AiOsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => TaskOsController(),
      child: MaterialApp(
        title: 'Cognitive OS',
        debugShowCheckedModeBanner: false,
        themeMode: ThemeMode.dark,
        darkTheme: ThemeData(
          brightness: Brightness.dark,
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF0B0F14),
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFF5B8CFF),
            secondary: Color(0xFF00C2A8),
            surface: Color(0xFF121821),
          ),
        ),
        initialRoute: '/',
        routes: {
          '/': (_) => const AppShell(),
        },
      ),
    );
  }
}
