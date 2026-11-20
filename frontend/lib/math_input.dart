/// Champ de saisie mathématique : MathLive (clavier virtuel, fractions, racines…) sur le web, qui produit du
/// LaTeX ; simple champ texte ailleurs.
library;

export 'math_input_stub.dart' if (dart.library.js_interop) 'math_input_web.dart';
