import 'package:material_ui/material_ui.dart';

import 'api_client.dart';

/// Repli hors web : texte brut (les formules restent lisibles en LaTeX).
class MathView extends StatelessWidget {
  const MathView({super.key, required this.api, required this.text, this.fontSize = 16});
  final ApiClient api;
  final String text;
  final double fontSize;

  @override
  Widget build(BuildContext context) => SelectableText(text, style: TextStyle(fontSize: fontSize));
}
