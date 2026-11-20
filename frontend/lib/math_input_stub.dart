import 'package:material_ui/material_ui.dart';

/// Repli hors web : l'élève écrit le résultat au clavier (ex. 5/2, x = 4).
class MathInput extends StatelessWidget {
  const MathInput({super.key, this.initial = '', required this.onChanged, this.onSubmit, this.enabled = true});
  final String initial;
  final ValueChanged<String> onChanged;
  final VoidCallback? onSubmit;
  final bool enabled;

  @override
  Widget build(BuildContext context) => TextFormField(
    initialValue: initial,
    enabled: enabled,
    onChanged: onChanged,
    onFieldSubmitted: (_) => onSubmit?.call(),
    decoration: const InputDecoration(hintText: 'Ma réponse (ex. 5/2, x = 4)'),
  );
}
