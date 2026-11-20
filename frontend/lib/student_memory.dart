import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import 'api_client.dart';
import 'math_input.dart';
import 'math_view.dart';
import 'sounds.dart';
import 'student_exercises.dart';
import 'theme.dart';

const _cardTypes = {
  'question': 'Question',
  'definition': 'Définition',
  'formule': 'Formule',
  'vrai_faux': 'Vrai ou faux',
  'a_completer': 'À compléter',
  'numerique': 'Calcul',
};
const _mastery = {
  'a_revoir': ('À revoir', Brand.coral),
  'nouveau': ('Nouvelles', Brand.sky),
  'en_cours': ('En cours', Brand.sun),
  'maitrise': ('Maîtrisées', Brand.mint),
};

String _errorText(Object? error) => error is ApiException ? error.message : 'Erreur : $error';

/// Révisions flash : programme du jour (cartes arrivées à échéance, puis nouvelles cartes) avec répétition
/// espacée. Les cartes de calcul, vrai/faux et à compléter sont corrigées par le serveur ; les autres sont
/// auto-évaluées après avoir vu la réponse.
class FlashView extends StatefulWidget {
  const FlashView({super.key, required this.api});
  final ApiClient api;

  @override
  State<FlashView> createState() => _FlashViewState();
}

class _FlashViewState extends State<FlashView> {
  late Future<Map<String, dynamic>> _program = widget.api.revisionsToday();
  List<Map<String, dynamic>>? _queue;

  void _reload() => setState(() {
    _queue = null;
    _program = widget.api.revisionsToday();
  });

  Future<void> _freeSession() async {
    try {
      final items = await widget.api.revisionSession(limit: 20);
      if (!mounted) return;
      if (items.isEmpty) {
        snack(context, 'Aucune carte mémoire pour votre niveau et votre série pour le moment.');
        return;
      }
      setState(() => _queue = items);
    } catch (error) {
      if (mounted) snack(context, _errorText(error));
    }
  }

  @override
  Widget build(BuildContext context) {
    final queue = _queue;
    if (queue != null) {
      return FlashSession(api: widget.api, items: queue, onFinished: _reload);
    }
    return FutureBuilder<Map<String, dynamic>>(
      future: _program,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Text(_errorText(snapshot.error));
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final program = snapshot.data!;
        final stats = (program['stats'] as Map).cast<String, dynamic>();
        final due = (program['due'] as List).cast<Map<String, dynamic>>();
        final fresh = (program['new'] as List).cast<Map<String, dynamic>>();
        final today = [...due, ...fresh];
        final byMastery = ((stats['by_mastery'] as Map?) ?? const {}).cast<String, dynamic>();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ChunkCard(
              child: Row(
                children: [
                  RingProgress(done: math.min(70, (stats['reviews_last_7_days'] as int?) ?? 0), total: 70),
                  const SizedBox(width: 20),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          today.isEmpty ? 'Tout est à jour !' : '${today.length} carte(s) à réviser aujourd’hui',
                          style: const TextStyle(fontFamily: Brand.display, fontSize: 24, fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${due.length} à revoir · ${fresh.length} nouvelle(s) · '
                          'objectif de la semaine : 70 révisions (10 par jour)',
                          style: const TextStyle(color: Brand.muted),
                        ),
                        const SizedBox(height: 14),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: [
                            if (today.isNotEmpty)
                              PressButton(
                                label: 'Commencer',
                                icon: Icons.play_arrow_rounded,
                                primary: true,
                                big: true,
                                onPressed: () => setState(() => _queue = today),
                              ),
                            PressButton(label: 'Séance libre', icon: Icons.shuffle_rounded, onPressed: _freeSession),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                for (final entry in _mastery.entries)
                  StatTile(
                    icon: Icons.style_rounded,
                    color: entry.value.$2,
                    value: (byMastery[entry.key] as int?) ?? (entry.key == 'nouveau' ? stats['new_available'] as int? ?? 0 : 0),
                    label: entry.value.$1,
                  ),
              ],
            ),
            const SizedBox(height: 16),
            const Text(
              'Une carte bien sue revient de plus en plus tard (1 jour, 3 jours, une semaine…) ; une carte ratée '
              'revient vite. Les cartes viennent uniquement des documents de votre niveau et de votre série.',
              style: TextStyle(color: Brand.muted),
            ),
          ],
        );
      },
    );
  }
}

/// Une séance : les cartes une par une, retournées avec un effet doux.
class FlashSession extends StatefulWidget {
  const FlashSession({super.key, required this.api, required this.items, required this.onFinished});
  final ApiClient api;
  final List<Map<String, dynamic>> items;
  final VoidCallback onFinished;

  @override
  State<FlashSession> createState() => _FlashSessionState();
}

class _FlashSessionState extends State<FlashSession> {
  int _index = 0;
  int _known = 0;
  bool _flipped = false;
  bool _showHint = false;
  bool _busy = false;
  String _answer = '';
  final _text = TextEditingController();
  Map<String, dynamic>? _back; // réponse (et verdict pour les cartes corrigées par le serveur)
  String? _error;

  Map<String, dynamic> get _item => widget.items[_index];
  bool get _done => _index >= widget.items.length;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _reveal() async {
    setState(() => _busy = true);
    try {
      final answer = await widget.api.flashcardAnswer(_item['item_id'] as int);
      if (!mounted) return;
      Sounds.flip();
      setState(() {
        _back = answer;
        _flipped = true;
      });
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _check(String answer) async {
    if (answer.trim().isEmpty) {
      setState(() => _error = 'Écris ta réponse.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.api.reviewFlashcard(_item['item_id'] as int, answerText: answer);
      if (!mounted) return;
      final ok = result['result'] == 'correct';
      ok ? Sounds.success() : Sounds.gentleError();
      if (ok) _known++;
      setState(() {
        _back = result;
        _flipped = true;
      });
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _rate(int rating) async {
    setState(() => _busy = true);
    try {
      await widget.api.reviewFlashcard(_item['item_id'] as int, rating: rating);
      if (rating >= 2) {
        _known++;
        Sounds.success();
      } else {
        Sounds.tap();
      }
      _next();
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _next() {
    setState(() {
      _index++;
      _flipped = false;
      _showHint = false;
      _back = null;
      _answer = '';
      _error = null;
      _text.clear();
    });
    if (_done) {
      Sounds.levelUp();
      celebrate(context, label: 'Séance finie !');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_done) {
      return ChunkCard(
        child: Column(
          children: [
            const Icon(Icons.emoji_events_rounded, size: 64, color: Brand.sun),
            const SizedBox(height: 8),
            const Text('Bravo, séance terminée !',
                style: TextStyle(fontFamily: Brand.display, fontSize: 28, fontWeight: FontWeight.w800)),
            Text('$_known carte(s) sue(s) sur ${widget.items.length}.', style: const TextStyle(color: Brand.muted)),
            const SizedBox(height: 16),
            PressButton(label: 'Retour au programme', primary: true, onPressed: widget.onFinished),
          ],
        ),
      );
    }
    final item = _item;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(child: AnimBar(value: _index / widget.items.length)),
            const SizedBox(width: 12),
            Text('${_index + 1} / ${widget.items.length}', style: const TextStyle(fontWeight: FontWeight.w800)),
            IconButton(tooltip: 'Arrêter la séance', onPressed: widget.onFinished, icon: const Icon(Icons.close_rounded)),
          ],
        ),
        const SizedBox(height: 14),
        _FlipCard(
          key: ValueKey('card-$_index'),
          flipped: _flipped,
          front: _front(item),
          back: _flipped ? _backSide(item) : const SizedBox.shrink(),
        ),
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: const TextStyle(color: Brand.bad, fontWeight: FontWeight.w700)),
        ],
        const SizedBox(height: 14),
        _actions(item),
      ],
    );
  }

  Widget _front(Map<String, dynamic> item) {
    final isExercise = item['item_type'] == 'exercise';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Pill(isExercise ? 'Exercice à refaire' : (_cardTypes[item['card_type']] ?? 'Carte'),
            color: Brand.lilac.withValues(alpha: .18), textColor: Brand.lilac),
        const SizedBox(height: 14),
        MathView(api: widget.api, text: '${item['title']}', fontSize: 20),
        if (item['hint'] != null) ...[
          const SizedBox(height: 10),
          if (_showHint)
            Text('Indice : ${item['hint']}', style: const TextStyle(color: Brand.muted, fontStyle: FontStyle.italic))
          else
            TextButton.icon(
              onPressed: () => setState(() => _showHint = true),
              icon: const Icon(Icons.lightbulb_outline_rounded),
              label: const Text('Indice'),
            ),
        ],
      ],
    );
  }

  Widget _backSide(Map<String, dynamic> item) {
    final back = _back ?? const {};
    final verdict = back['result'];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (verdict != null)
          Pill(verdict == 'correct' ? 'Juste !' : 'Pas encore',
              color: (verdict == 'correct' ? Brand.mint : Brand.coral).withValues(alpha: .2),
              icon: verdict == 'correct' ? Icons.check_rounded : Icons.replay_rounded),
        const SizedBox(height: 10),
        const Text('Réponse', style: TextStyle(color: Brand.muted, fontWeight: FontWeight.w800)),
        MathView(api: widget.api, text: '${back['answer'] ?? ''}', fontSize: 19),
        const SizedBox(height: 10),
        Text('Source : ${back['source'] ?? ''}', style: const TextStyle(fontSize: 13, color: Brand.muted)),
        if (back['interval_days'] != null)
          Text('Prochaine révision dans ${_days(back['interval_days'] as num)}.',
              style: const TextStyle(fontSize: 13, color: Brand.muted)),
      ],
    );
  }

  static String _days(num days) {
    if (days < 1) return 'quelques minutes';
    final rounded = days.round();
    return rounded == 1 ? '1 jour' : '$rounded jours';
  }

  Widget _actions(Map<String, dynamic> item) {
    if (item['item_type'] == 'exercise') {
      return Wrap(spacing: 10, children: [
        PressButton(
          label: 'Ouvrir l’exercice',
          primary: true,
          onPressed: () => Navigator.of(context)
              .push(MaterialPageRoute<void>(
                builder: (_) => StudentExercisePage(api: widget.api, exerciseId: item['item_id'] as int),
              ))
              .then((_) => _next()),
        ),
        PressButton(label: 'Passer', onPressed: _next),
      ]);
    }
    if (_flipped) {
      if (item['self_graded'] == true) {
        const ratings = [
          (0, 'À revoir', Brand.coral),
          (1, 'Difficile', Brand.sun),
          (2, 'Bien', Brand.sky),
          (3, 'Facile', Brand.mint),
        ];
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Tu la connaissais ?', style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final (value, label, color) in ratings)
                PressButton(
                  label: label,
                  color: color.withValues(alpha: .25),
                  onPressed: _busy ? null : () => _rate(value),
                ),
            ]),
          ],
        );
      }
      return PressButton(label: 'Carte suivante', icon: Icons.arrow_forward_rounded, primary: true, onPressed: _next);
    }
    if (item['self_graded'] == true) {
      return PressButton(
        label: _busy ? '…' : 'Voir la réponse',
        icon: Icons.flip_rounded,
        primary: true,
        onPressed: _busy ? null : _reveal,
      );
    }
    return switch (item['card_type']) {
      'vrai_faux' => Wrap(spacing: 10, children: [
        PressButton(label: 'Vrai', color: Brand.mint.withValues(alpha: .25), onPressed: _busy ? null : () => _check('Vrai')),
        PressButton(label: 'Faux', color: Brand.coral.withValues(alpha: .25), onPressed: _busy ? null : () => _check('Faux')),
      ]),
      'numerique' => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          MathInput(key: ValueKey('math-$_index'), onChanged: (v) => _answer = v, onSubmit: () => _check(_answer)),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerLeft,
            child: PressButton(label: 'Vérifier', primary: true, onPressed: _busy ? null : () => _check(_answer)),
          ),
        ],
      ),
      _ => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _text,
            decoration: const InputDecoration(hintText: 'Ta réponse'),
            onSubmitted: (_) => _check(_text.text),
          ),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerLeft,
            child: PressButton(label: 'Vérifier', primary: true, onPressed: _busy ? null : () => _check(_text.text)),
          ),
        ],
      ),
    };
  }
}

/// Carte qui se retourne : on écrase la largeur jusqu'à zéro puis on l'ouvre sur l'autre face (fonctionne avec
/// les formules affichées par le navigateur).
class _FlipCard extends StatelessWidget {
  const _FlipCard({super.key, required this.flipped, required this.front, required this.back});
  final bool flipped;
  final Widget front, back;

  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
    tween: Tween(begin: 0, end: flipped ? 1 : 0),
    duration: calmMotion(context) ? Duration.zero : const Duration(milliseconds: 420),
    curve: Curves.easeInOutCubic,
    builder: (context, t, _) {
      final showBack = t >= .5;
      final squash = (math.cos(t * math.pi)).abs().clamp(.02, 1.0);
      return Transform(
        alignment: Alignment.center,
        transform: Matrix4.diagonal3Values(squash, 1, 1),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 220),
          child: ChunkCard(
            color: showBack ? Brand.mint.withValues(alpha: .08) : null,
            padding: const EdgeInsets.all(28),
            child: showBack ? back : front,
          ),
        ),
      );
    },
  );
}

/// Méthodes de mémorisation approuvées, avec des exemples tirés des documents de l'élève.
class MethodsView extends StatefulWidget {
  const MethodsView({super.key, required this.api});
  final ApiClient api;

  @override
  State<MethodsView> createState() => _MethodsViewState();
}

class _MethodsViewState extends State<MethodsView> {
  late final Future<List<Map<String, dynamic>>> _methods = widget.api.studentMethods();

  static const _categories = {
    'rappel': ('Se tester', Icons.quiz_rounded, Brand.blue),
    'comprehension': ('Comprendre', Icons.psychology_rounded, Brand.lilac),
    'mnemotechnique': ('Astuces de mémoire', Icons.auto_awesome_rounded, Brand.sun),
    'organisation': ('S’organiser', Icons.event_note_rounded, Brand.mint),
  };

  @override
  Widget build(BuildContext context) => FutureBuilder<List<Map<String, dynamic>>>(
    future: _methods,
    builder: (context, snapshot) {
      if (snapshot.hasError) return Text(_errorText(snapshot.error));
      if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
      final methods = snapshot.data!;
      if (methods.isEmpty) {
        return const Text('Aucune méthode approuvée pour le moment.',
            style: TextStyle(fontWeight: FontWeight.w800, color: Brand.muted));
      }
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < methods.length; i++) ...[
            Rise(delay: Duration(milliseconds: 50 * math.min(i, 8)), child: _method(methods[i])),
            const SizedBox(height: 14),
          ],
        ],
      );
    },
  );

  Widget _method(Map<String, dynamic> method) {
    final (label, icon, color) = _categories[method['category']] ?? ('Méthode', Icons.lightbulb_rounded, Brand.blue);
    final steps = (method['steps'] as List).cast<String>();
    final examples = (method['examples'] as List).cast<Map>();
    return ChunkCard(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 6),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        shape: const Border(),
        leading: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(color: color.withValues(alpha: .16), borderRadius: BorderRadius.circular(14)),
          child: Icon(icon, color: color),
        ),
        title: Text('${method['name']}', style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17)),
        subtitle: Text('$label · ${method['summary']}'),
        childrenPadding: const EdgeInsets.only(bottom: 14),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (method['principle'] != null) Text('${method['principle']}', style: const TextStyle(height: 1.5)),
          const SizedBox(height: 10),
          for (var i = 0; i < steps.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    radius: 12,
                    backgroundColor: color.withValues(alpha: .2),
                    child: Text('${i + 1}', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: color)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: Text(steps[i])),
                ],
              ),
            ),
          if (examples.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('Exemples tirés de tes documents', style: TextStyle(fontWeight: FontWeight.w800)),
            for (final example in examples)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text('• ${example['note']} (${example['source']})'),
              ),
          ],
        ],
      ),
    );
  }
}

/// Accueil : rappel doux des révisions du jour.
class TodayRevisionCard extends StatelessWidget {
  const TodayRevisionCard({super.key, required this.api, required this.onOpen});
  final ApiClient api;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
    future: api.revisionsToday(),
    builder: (context, snapshot) {
      final program = snapshot.data;
      final count = program == null ? null : (program['due'] as List).length + (program['new'] as List).length;
      return ChunkCard(
        color: Brand.peach.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? .12 : .7),
        child: Row(
          children: [
            const Icon(Icons.local_fire_department_rounded, size: 44, color: Brand.coral),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Révisions du jour',
                      style: TextStyle(fontFamily: Brand.display, fontSize: 20, fontWeight: FontWeight.w800)),
                  Text(
                    count == null
                        ? '…'
                        : count == 0
                        ? 'Tout est à jour, bravo ! Tu peux faire une séance libre.'
                        : '$count carte(s) t’attendent : quelques minutes suffisent.',
                    style: const TextStyle(color: Brand.muted),
                  ),
                ],
              ),
            ),
            PressButton(label: 'Réviser', primary: true, onPressed: onOpen),
          ],
        ),
      );
    },
  );
}
