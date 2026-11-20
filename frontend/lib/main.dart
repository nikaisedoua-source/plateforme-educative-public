import 'package:material_ui/material_ui.dart';

import 'api_client.dart';
import 'auth_page.dart';
import 'theme.dart';

void main() {
  runApp(PlateformeApp());
}

class PlateformeApp extends StatelessWidget {
  PlateformeApp({super.key, ApiClient? apiClient})
    : apiClient = apiClient ?? ApiClient();

  final ApiClient apiClient;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Plateforme éducative',
      debugShowCheckedModeBanner: false,
      theme: Brand.theme(Brightness.light),
      darkTheme: Brand.theme(Brightness.dark),
      home: AuthPage(api: apiClient),
    );
  }
}
