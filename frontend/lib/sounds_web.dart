import 'package:web/web.dart' as web;

/// Note jouée par un oscillateur : fréquence (Hz), départ et durée (s), forme d'onde.
class Note {
  const Note(this.frequency, this.start, this.duration, {this.wave = 'sine'});
  final double frequency, start, duration;
  final String wave;
}

web.AudioContext? _context;

void play(List<Note> notes, double volume) {
  try {
    final context = _context ??= web.AudioContext();
    if (context.state == 'suspended') context.resume();
    final now = context.currentTime;
    for (final note in notes) {
      final start = now + note.start;
      final end = start + note.duration;
      final oscillator = context.createOscillator()
        ..type = note.wave
        ..frequency.setValueAtTime(note.frequency, start);
      final gain = context.createGain();
      gain.gain
        ..setValueAtTime(0.0001, start)
        ..exponentialRampToValueAtTime(volume, start + 0.015)
        ..exponentialRampToValueAtTime(0.0001, end);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator
        ..start(start)
        ..stop(end + 0.02);
    }
  } catch (_) {
    // Son indisponible (navigateur restreint) : on continue en silence.
  }
}

String? readPref(String key) {
  try {
    return web.window.localStorage.getItem(key);
  } catch (_) {
    return null;
  }
}

void writePref(String key, String value) {
  try {
    web.window.localStorage.setItem(key, value);
  } catch (_) {}
}
