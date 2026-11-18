import 'package:material_ui/material_ui.dart';

import 'screens/home_page.dart';

void main() {
  runApp(const SmartHomeApp());
}

class SmartHomeApp extends StatelessWidget {
  const SmartHomeApp({super.key});

  static const Color backgroundDark = Color(0xFF030712);
  static const Color primaryBlue = Color(0xFF1E88E5);
  static const Color accentCyan = Color(0xFF00E5FF);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VietHome-AI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        scaffoldBackgroundColor: backgroundDark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: primaryBlue,
          brightness: Brightness.dark,
          primary: primaryBlue,
          secondary: accentCyan,
          surface: const Color(0xFF0B1426),
        ),
        snackBarTheme: SnackBarThemeData(
          behavior: SnackBarBehavior.floating,
          backgroundColor: const Color(0xFF192946),
          contentTextStyle: const TextStyle(color: Colors.white),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      home: const HomePage(),
    );
  }
}
