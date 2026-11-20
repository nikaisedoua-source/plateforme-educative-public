import 'dart:async';
import 'dart:js_interop';

import 'package:material_ui/material_ui.dart';
import 'package:web/web.dart' as web;

import 'api_client.dart';
import 'theme.dart';

/// Texte + formules : le serveur renvoie du HTML sûr (texte échappé + MathML) que le navigateur
/// dessine nativement, sans connexion internet ni police à télécharger.
class MathView extends StatefulWidget {
  const MathView({super.key, required this.api, required this.text, this.fontSize = 16});
  final ApiClient api;
  final String text;
  final double fontSize;

  @override
  State<MathView> createState() => _MathViewState();
}

class _MathViewState extends State<MathView> {
  static final Map<String, Map<String, dynamic>> _cache = {};
  Map<String, dynamic>? _result;
  double _height = 24;
  web.HTMLDivElement? _content;
  web.ResizeObserver? _observer;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _render();
  }

  @override
  void didUpdateWidget(MathView old) {
    super.didUpdateWidget(old);
    if (old.text != widget.text) {
      _debounce?.cancel();
      _debounce = Timer(const Duration(milliseconds: 350), _render);
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _observer?.disconnect();
    super.dispose();
  }

  Future<void> _render() async {
    final text = widget.text;
    try {
      final result = _cache[text] ??= await widget.api.renderMath(text);
      if (!mounted || text != widget.text) return;
      setState(() => _result = result);
      _apply();
    } catch (_) {
      if (mounted) setState(() => _result = {'html': null, 'errors': const [], 'has_math': false});
    }
  }

  void _apply() {
    final content = _content;
    final html = _result?['html'];
    if (content == null || html is! String) return;
    content.innerHTML = html.toJS;
  }

  static String _css(Color c) => 'rgb(${(c.r * 255).round()}, ${(c.g * 255).round()}, ${(c.b * 255).round()})';

  void _created(Object element) {
    final host = element as web.HTMLDivElement;
    host.style
      ..overflow = 'hidden'
      ..width = '100%';
    final content = web.document.createElement('div') as web.HTMLDivElement;
    content.style
      ..fontSize = '${widget.fontSize}px'
      ..lineHeight = '1.7'
      ..fontFamily = 'Nunito, system-ui, -apple-system, "Segoe UI", sans-serif'
      ..color = _css(Palette.of(context).ink)
      ..whiteSpace = 'normal'
      ..overflowWrap = 'anywhere';
    host.append(content);
    _content = content;
    _observer = web.ResizeObserver(
      ((JSArray<web.ResizeObserverEntry> entries, web.ResizeObserver _) {
        final height = content.getBoundingClientRect().height + 4;
        if (mounted && (height - _height).abs() > 1) setState(() => _height = height);
      }).toJS,
    )..observe(content);
    _apply();
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    if (result != null && result['html'] == null) {
      return SelectableText(widget.text, style: TextStyle(fontSize: widget.fontSize));
    }
    final errors = (result?['errors'] as List?) ?? const [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          height: _height,
          child: HtmlElementView.fromTagName(tagName: 'div', onElementCreated: _created),
        ),
        if (errors.isNotEmpty)
          Text('Formule à corriger : ${errors.join(' ; ')}',
              style: const TextStyle(color: Colors.deepOrange, fontSize: 13)),
      ],
    );
  }
}
