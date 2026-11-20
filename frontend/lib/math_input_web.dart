import 'dart:js_interop';
import 'dart:js_interop_unsafe';

import 'package:material_ui/material_ui.dart';
import 'package:web/web.dart' as web;

import 'theme.dart';

/// `<math-field>` de MathLive (copié dans web/mathlive, fonctionne sans internet). La valeur est du LaTeX,
/// envoyée telle quelle au serveur qui la compare au résultat du corrigé.
class MathInput extends StatefulWidget {
  const MathInput({super.key, this.initial = '', required this.onChanged, this.onSubmit, this.enabled = true});
  final String initial;
  final ValueChanged<String> onChanged;
  final VoidCallback? onSubmit;
  final bool enabled;

  @override
  State<MathInput> createState() => _MathInputState();
}

class _MathInputState extends State<MathInput> {
  web.HTMLElement? _field;
  web.ResizeObserver? _observer;
  double _height = 62;

  @override
  void didUpdateWidget(MathInput old) {
    super.didUpdateWidget(old);
    final field = _field;
    if (field != null && old.enabled != widget.enabled) {
      field.setProperty('readOnly'.toJS, (!widget.enabled).toJS);
    }
  }

  @override
  void dispose() {
    _observer?.disconnect();
    super.dispose();
  }

  void _created(Object element) {
    final host = element as web.HTMLDivElement;
    host.style
      ..width = '100%'
      ..overflow = 'visible';
    final dark = Theme.of(context).brightness == Brightness.dark;
    final p = Palette.of(context);
    String css(Color c) => 'rgb(${(c.r * 255).round()}, ${(c.g * 255).round()}, ${(c.b * 255).round()})';
    final field = web.document.createElement('math-field') as web.HTMLElement;
    field.setAttribute('math-virtual-keyboard-policy', 'auto');
    field.setAttribute('aria-label', 'Zone de réponse mathématique');
    field.style
      ..width = '100%'
      ..boxSizing = 'border-box'
      ..fontSize = '24px'
      ..padding = '8px 12px'
      ..borderRadius = '14px'
      ..border = '1.5px solid ${css(p.border)}'
      ..background = css(p.soft)
      ..color = css(p.ink)
      ..setProperty('--caret-color', css(Brand.blue))
      ..setProperty('--selection-background-color', dark ? '#3b4a8a' : '#dfe6ff')
      ..setProperty('--contains-highlight-background-color', 'transparent');
    field.setProperty('value'.toJS, widget.initial.toJS);
    if (!widget.enabled) field.setProperty('readOnly'.toJS, true.toJS);
    field.addEventListener(
      'input',
      ((web.Event _) => widget.onChanged((field.getProperty<JSString?>('value'.toJS))?.toDart ?? '')).toJS,
    );
    field.addEventListener('change', ((web.Event _) => widget.onSubmit?.call()).toJS);
    field.addEventListener(
      'focus',
      ((web.Event _) => field.style.border = '2px solid ${css(Brand.blue)}').toJS,
    );
    field.addEventListener(
      'blur',
      ((web.Event _) => field.style.border = '1.5px solid ${css(p.border)}').toJS,
    );
    host.append(field);
    _field = field;
    _observer = web.ResizeObserver(
      ((JSArray<web.ResizeObserverEntry> _, web.ResizeObserver _) {
        final height = field.getBoundingClientRect().height + 2;
        if (mounted && (height - _height).abs() > 1) setState(() => _height = height);
      }).toJS,
    )..observe(field);
  }

  @override
  Widget build(BuildContext context) => SizedBox(
    height: _height,
    child: HtmlElementView.fromTagName(tagName: 'div', onElementCreated: _created),
  );
}
