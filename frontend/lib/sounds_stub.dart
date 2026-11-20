/// Hors navigateur : pas de son, préférences non mémorisées.
class Note {
  const Note(this.frequency, this.start, this.duration, {this.wave = 'sine'});
  final double frequency, start, duration;
  final String wave;
}

void play(List<Note> notes, double volume) {}

String? readPref(String key) => null;

void writePref(String key, String value) {}
