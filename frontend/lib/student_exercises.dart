import 'package:material_ui/material_ui.dart';

import 'api_client.dart';
import 'auth_image.dart';
import 'math_view.dart';
import 'theme.dart';

const _types = {
  'libre': 'Réponse rédigée',
  'qcm': 'QCM',
  'vrai_faux': 'Vrai ou faux',
  'a_completer': 'À compléter',
  'numerique': 'Calcul',
  'probleme': 'Problème',
  'etude_de_cas': 'Étude de cas',
};
const _levels = {1: 'Facile', 2: 'Moyen', 3: 'Difficile'};

/// Matières et chapitres disponibles pour l'élève (son niveau et sa série uniquement).
class StudentSubjectsView extends StatefulWidget {
  const StudentSubjectsView({super.key, required this.api});
  final ApiClient api;

  @override
  State<StudentSubjectsView> createState() => _StudentSubjectsViewState();
}

class _StudentSubjectsViewState extends State<StudentSubjectsView> {
  late Future<List<Map<String, dynamic>>> _subjects = widget.api.studentSubjects();

  void _open(BuildContext context, String title, {int? subjectId, int? chapterId}) {
    Navigator.of(context)
        .push(MaterialPageRoute<void>(
          builder: (_) => Scaffold(
            appBar: AppBar(title: Text(title)),
            body: PageFrame(
              title: title,
              children: [StudentExerciseList(api: widget.api, subjectId: subjectId, chapterId: chapterId)],
            ),
          ),
        ))
        .then((_) => setState(() => _subjects = widget.api.studentSubjects()));
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<List<Map<String, dynamic>>>(
    future: _subjects,
    builder: (context, snapshot) {
      if (snapshot.hasError) return _Info(_errorText(snapshot.error));
      if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
      final subjects = snapshot.data!;
      if (subjects.isEmpty) {
        return const _Info('Aucun exercice publié pour votre niveau et votre série pour le moment.');
      }
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final subject in subjects) ...[
            ChunkCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text('${subject['name']}',
                            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
                      ),
                      PressButton(
                        label: 'Tous (${subject['exercise_count']})',
                        primary: true,
                        onPressed: () => _open(context, '${subject['name']}', subjectId: subject['id'] as int),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  for (final chapter in (subject['chapters'] as List).cast<Map>())
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text('${chapter['title']}'),
                      trailing: Text('${chapter['exercise_count']} exercice(s)'),
                      onTap: () => _open(context, '${chapter['title']}', chapterId: chapter['id'] as int),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
        ],
      );
    },
  );
}

/// Liste d'exercices (avec l'état de l'élève : essais, réussite).
class StudentExerciseList extends StatefulWidget {
  const StudentExerciseList({super.key, required this.api, this.subjectId, this.chapterId});
  final ApiClient api;
  final int? subjectId, chapterId;

  @override
  State<StudentExerciseList> createState() => _StudentExerciseListState();
}

class _StudentExerciseListState extends State<StudentExerciseList> {
  late Future<List<Map<String, dynamic>>> _items = _load();

  Future<List<Map<String, dynamic>>> _load() =>
      widget.api.studentExercises(subjectId: widget.subjectId, chapterId: widget.chapterId);

  @override
  Widget build(BuildContext context) => FutureBuilder<List<Map<String, dynamic>>>(
    future: _items,
    builder: (context, snapshot) {
      if (snapshot.hasError) return _Info(_errorText(snapshot.error));
      if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
      final items = snapshot.data!;
      if (items.isEmpty) return const _Info('Aucun exercice disponible ici pour le moment.');
      return Column(
        children: [
          for (final item in items)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ChunkCard(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                color: item['solved'] == true ? const Color(0xFFE6F7EF) : null,
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    item['solved'] == true
                        ? Icons.check_circle_rounded
                        : (item['attempts'] as int) > 0
                        ? Icons.pending_rounded
                        : Icons.radio_button_unchecked_rounded,
                    color: item['solved'] == true ? Brand.good : Brand.muted,
                  ),
                  title: Text('${item['title']}', style: const TextStyle(fontWeight: FontWeight.w800)),
                  subtitle: Text(
                    '${_types[item['exercise_type']] ?? item['exercise_type']} · '
                    '${_levels[item['difficulty']] ?? ''} · ${item['points']} pt · '
                    '${item['attempts']} essai(s)',
                  ),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => Navigator.of(context)
                      .push(MaterialPageRoute<void>(
                        builder: (_) => StudentExercisePage(api: widget.api, exerciseId: item['id'] as int),
                      ))
                      .then((_) => setState(() => _items = _load())),
                ),
              ),
            ),
        ],
      );
    },
  );
}

/// Un exercice : énoncé (formules, figures), réponse corrigée par le serveur, puis corrigé selon la règle.
class StudentExercisePage extends StatefulWidget {
  const StudentExercisePage({super.key, required this.api, required this.exerciseId});
  final ApiClient api;
  final int exerciseId;

  @override
  State<StudentExercisePage> createState() => _StudentExercisePageState();
}

class _StudentExercisePageState extends State<StudentExercisePage> {
  Map<String, dynamic>? _exercise;
  Map<String, dynamic>? _result;
  Map<String, dynamic>? _correction;
  final Set<int> _chosen = {};
  final _answer = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _answer.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final exercise = await widget.api.studentExercise(widget.exerciseId);
      if (mounted) setState(() => _exercise = exercise);
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    }
  }

  bool get _withOptions => const {'qcm', 'vrai_faux'}.contains(_exercise?['exercise_type']);

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.api.submitAttempt(
        widget.exerciseId,
        answer: _withOptions ? null : _answer.text,
        optionIds: _withOptions ? _chosen.toList() : null,
      );
      final exercise = await widget.api.studentExercise(widget.exerciseId);
      if (mounted) {
        setState(() {
          _result = result;
          _exercise = exercise;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _showCorrection() async {
    setState(() => _busy = true);
    try {
      final correction = await widget.api.studentCorrection(widget.exerciseId);
      if (mounted) setState(() => _correction = correction);
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final e = _exercise;
    return Scaffold(
      appBar: AppBar(title: Text(e == null ? 'Exercice' : '${e['title']}')),
      body: e == null
          ? Center(child: _error == null ? const CircularProgressIndicator() : _Info(_error!))
          : PageFrame(
              title: '${e['title']}',
              children: [
                Text(
                  '${_types[e['exercise_type']] ?? ''} · ${_levels[e['difficulty']] ?? ''} · ${e['points']} pt',
                  style: const TextStyle(color: Brand.muted, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 16),
                ChunkCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      MathView(api: widget.api, text: '${e['statement']}', fontSize: 17),
                      for (final asset in (e['assets'] as List).cast<Map>()) ...[
                        const SizedBox(height: 12),
                        AuthImage(api: widget.api, path: '/api/v1/student/assets/${asset['id']}'),
                        if (asset['caption'] != null)
                          Text('${asset['caption']}', style: const TextStyle(color: Brand.muted)),
                      ],
                      const SizedBox(height: 12),
                      Text('Source : ${e['source']}',
                          style: const TextStyle(fontSize: 13, color: Color(0xFF69758A))),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                _answerCard(e),
                const SizedBox(height: 16),
                _correctionCard(e),
              ],
            ),
    );
  }

  Widget _answerCard(Map<String, dynamic> e) {
    final result = _result;
    final correctIds = ((_correction?['correct_option_ids'] as List?) ?? const []).cast<int>();
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Ma réponse', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          if (_withOptions)
            for (final option in (e['options'] as List).cast<Map>())
              CheckboxListTile(
                value: _chosen.contains(option['id']),
                onChanged: (on) => setState(
                  () => on == true ? _chosen.add(option['id'] as int) : _chosen.remove(option['id']),
                ),
                title: Row(
                  children: [
                    Text('${option['label']}. ', style: const TextStyle(fontWeight: FontWeight.w800)),
                    Expanded(child: MathView(api: widget.api, text: '${option['text']}')),
                  ],
                ),
                secondary: correctIds.contains(option['id'])
                    ? const Icon(Icons.check_rounded, color: Brand.good)
                    : null,
              )
          else
            TextField(
              controller: _answer,
              minLines: e['exercise_type'] == 'numerique' || e['exercise_type'] == 'a_completer' ? 1 : 4,
              maxLines: 12,
              decoration: InputDecoration(
                labelText: e['exercise_type'] == 'numerique' ? 'Résultat (ex. 2,5 ou 5/2)' : 'Votre réponse',
              ),
            ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: PressButton(label: _busy ? '…' : 'Valider ma réponse', primary: true, onPressed: _busy ? null : _submit),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: Brand.bad, fontWeight: FontWeight.w700)),
          ],
          if (result != null) ...[
            const SizedBox(height: 12),
            Text(
              '${result['message']} (${_score(result['score'])} / ${result['max_score']})',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w900,
                color: switch (result['result']) {
                  'correct' => Brand.good,
                  'incorrect' => Brand.bad,
                  _ => Brand.muted,
                },
              ),
            ),
            if (result['after_correction'] == true)
              const Text('Réponse donnée après le corrigé : elle ne compte pas comme réussie.',
                  style: TextStyle(color: Brand.muted)),
          ],
          if ((e['history'] as List).isNotEmpty) ...[
            const SizedBox(height: 12),
            Text('Essais : ${(e['history'] as List).length} · meilleur score : ${_score(e['best_score'])}',
                style: const TextStyle(color: Brand.muted)),
          ],
        ],
      ),
    );
  }

  Widget _correctionCard(Map<String, dynamic> e) {
    final correction = _correction;
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Corrigé', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
          const SizedBox(height: 6),
          Text('${e['correction_rule']}', style: const TextStyle(color: Brand.muted)),
          const SizedBox(height: 12),
          if (correction == null)
            Align(
              alignment: Alignment.centerLeft,
              child: PressButton(
                label: 'Voir le corrigé',
                onPressed: e['correction_available'] == true && !_busy ? _showCorrection : null,
              ),
            )
          else ...[
            if (correction['expected_answer'] != null) ...[
              const Text('Réponse attendue', style: TextStyle(fontWeight: FontWeight.w800)),
              MathView(api: widget.api, text: '${correction['expected_answer']}'),
              const SizedBox(height: 8),
            ],
            if (correction['final_answer'] != null) ...[
              const Text('Résultat', style: TextStyle(fontWeight: FontWeight.w800)),
              MathView(api: widget.api, text: '${correction['final_answer']}'),
              const SizedBox(height: 8),
            ],
            if (correction['steps'] != null) MathView(api: widget.api, text: '${correction['steps']}'),
            if (correction['source'] != null)
              Text('Source : ${correction['source']}',
                  style: const TextStyle(fontSize: 13, color: Color(0xFF69758A))),
          ],
        ],
      ),
    );
  }
}

String _score(Object? value) {
  if (value == null) return '—';
  final number = (value as num).toDouble();
  return number == number.roundToDouble() ? number.toInt().toString() : number.toStringAsFixed(2);
}

String _errorText(Object? error) => error is ApiException ? error.message : 'Erreur : $error';

class _Info extends StatelessWidget {
  const _Info(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 16),
    child: Text(text, style: const TextStyle(fontWeight: FontWeight.w800, color: Brand.muted)),
  );
}
