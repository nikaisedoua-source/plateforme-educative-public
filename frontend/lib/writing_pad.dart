import 'package:material_ui/material_ui.dart';

import 'api_client.dart';
import 'math_input.dart';
import 'math_view.dart';
import 'theme.dart';

/// Espace de rédaction : texte libre, formules saisies au clavier mathématique et insérées entre $…$,
/// symboles et mots de liaison en un clic, aperçu mis en forme en direct.
class WritingPad extends StatefulWidget {
  const WritingPad({super.key, required this.api, required this.controller, this.hint = 'Rédige ta réponse…'});
  final ApiClient api;
  final TextEditingController controller;
  final String hint;

  @override
  State<WritingPad> createState() => _WritingPadState();
}

class _WritingPadState extends State<WritingPad> {
  static const _symbols = <String, String>{
    '⇒': r'$\Rightarrow$',
    '⇔': r'$\Leftrightarrow$',
    '∈ ℝ': r'$\in \mathbb{R}$',
    '≤': r'$\leq$',
    '≥': r'$\geq$',
    '≠': r'$\neq$',
    '∞': r'$\infty$',
  };
  static const _words = ['Donc ', 'Or ', 'D’où ', 'Par conséquent, ', 'On en déduit que ', 'Soit '];

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_changed);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_changed);
    super.dispose();
  }

  void _changed() => setState(() {});

  void _insert(String text) {
    final c = widget.controller;
    final selection = c.selection;
    final start = selection.isValid ? selection.start : c.text.length;
    final end = selection.isValid ? selection.end : c.text.length;
    final before = c.text.substring(0, start);
    final spaced = before.isEmpty || before.endsWith(' ') || before.endsWith('\n') ? text : ' $text';
    c.value = TextEditingValue(
      text: before + spaced + c.text.substring(end),
      selection: TextSelection.collapsed(offset: start + spaced.length),
    );
  }

  Future<void> _formula() async {
    var latex = '';
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Écrire une formule'),
        content: SizedBox(
          width: 560,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Utilise le clavier mathématique (fractions, puissances, racines…).',
                  style: TextStyle(color: Brand.muted)),
              const SizedBox(height: 12),
              MathInput(onChanged: (value) => latex = value, onSubmit: () => Navigator.of(context).pop(latex)),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Annuler')),
          PressButton(label: 'Insérer', primary: true, onPressed: () => Navigator.of(context).pop(latex)),
        ],
      ),
    );
    if (result != null && result.trim().isNotEmpty) _insert('\$${result.trim()}\$ ');
  }

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    final text = widget.controller.text;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 6,
          runSpacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            PressButton(label: 'Formule', icon: Icons.functions_rounded, primary: true, onPressed: _formula),
            for (final entry in _symbols.entries)
              ActionChip(label: Text(entry.key), onPressed: () => _insert('${entry.value} ')),
            for (final word in _words) ActionChip(label: Text(word.trim()), onPressed: () => _insert(word)),
          ],
        ),
        const SizedBox(height: 10),
        TextField(
          controller: widget.controller,
          minLines: 5,
          maxLines: 18,
          style: const TextStyle(fontSize: 16, height: 1.5),
          decoration: InputDecoration(hintText: widget.hint),
        ),
        if (text.contains(r'$')) ...[
          const SizedBox(height: 10),
          Text('Aperçu', style: TextStyle(color: p.muted, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              border: Border.all(color: p.border),
              borderRadius: BorderRadius.circular(14),
            ),
            child: MathView(api: widget.api, text: text),
          ),
        ],
      ],
    );
  }
}
