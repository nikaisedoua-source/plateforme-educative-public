import 'package:material_ui/material_ui.dart';

import 'sounds_stub.dart' if (dart.library.js_interop) 'sounds_web.dart' as engine;

/// Sons doux générés par le navigateur (aucun fichier, aucune connexion) : volume faible par défaut,
/// un bouton pour couper, choix mémorisé sur l'appareil.
class Sounds {
  static const _key = 'plateforme.sons';
  static final ValueNotifier<bool> enabled = ValueNotifier(engine.readPref(_key) != 'off');

  static void toggle() {
    enabled.value = !enabled.value;
    engine.writePref(_key, enabled.value ? 'on' : 'off');
    if (enabled.value) success();
  }

  static void _play(List<engine.Note> notes, {double volume = .06}) {
    if (enabled.value) engine.play(notes, volume);
  }

  /// Clic discret.
  static void tap() => _play(const [engine.Note(880, 0, .05)], volume: .018);

  /// Bonne réponse : petit accord montant.
  static void success() => _play(const [
    engine.Note(523.25, 0, .32, wave: 'triangle'),
    engine.Note(659.25, .08, .32, wave: 'triangle'),
    engine.Note(783.99, .16, .45, wave: 'triangle'),
  ]);

  /// Réponse à revoir : deux notes descendantes, sans dureté.
  static void gentleError() => _play(const [engine.Note(392, 0, .2), engine.Note(329.63, .12, .3)], volume: .05);

  /// Carte retournée.
  static void flip() => _play(const [engine.Note(600, 0, .09), engine.Note(900, .05, .1)], volume: .03);

  /// Réponse envoyée (sans verdict automatique).
  static void sent() => _play(const [engine.Note(659.25, 0, .15), engine.Note(880, .09, .2)], volume: .04);

  /// Objectif atteint : arpège.
  static void levelUp() => _play(const [
    engine.Note(523.25, 0, .3, wave: 'triangle'),
    engine.Note(659.25, .1, .3, wave: 'triangle'),
    engine.Note(783.99, .2, .3, wave: 'triangle'),
    engine.Note(1046.5, .3, .6, wave: 'triangle'),
  ], volume: .07);
}

/// Bouton haut-parleur : coupe ou remet les sons.
class SoundToggle extends StatelessWidget {
  const SoundToggle({super.key});

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<bool>(
    valueListenable: Sounds.enabled,
    builder: (_, on, _) => IconButton(
      tooltip: on ? 'Couper les sons' : 'Activer les sons',
      onPressed: Sounds.toggle,
      icon: Icon(on ? Icons.volume_up_rounded : Icons.volume_off_rounded),
    ),
  );
}
