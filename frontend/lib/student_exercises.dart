import 'package:material_ui/material_ui.dart';

import 'api_client.dart';
import 'auth_image.dart';
import 'math_input.dart';
import 'math_view.dart';
import 'sounds.dart';
import 'theme.dart';
import 'writing_pad.dart';

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
const _levelColors = {1: Brand.mint, 2: Brand.sun, 3: Brand.coral};

/// Matières et chapitres disponibles pour l'élève (son niveau et sa série uniquement).
class StudentSubjectsView extends StatefulWidget {
  const StudentSubjectsView({super.key, required this.api});
  final ApiClient api;

  @override
  State<StudentSubjectsView> createState() => _StudentSubjectsViewState();
}

class _StudentSubjectsViewState extends State<StudentSubjectsView> {
  late Future<List<Map<String, dynamic>>> _subjects = widget.api.studentSubjects();

  static const _palette = [Brand.blue, Brand.mint, Brand.lilac, Brand.coral, Brand.sky, Brand.sun];

  void _open(BuildContext context, String title, {int? subjectId, int? chapterId}) {
    Navigator.of(context)
        .push(MaterialPageRoute<void>(
          builder: (_) => Scaffold(
            appBar: AppBar(title: Text(title), actions: const [SoundToggle()]),
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
          for (var i = 0; i < subjects.length; i++) ...[
            Rise(
              delay: Duration(milliseconds: 60 * i),
              child: _subjectCard(context, subjects[i], _palette[i % _palette.length]),
            ),
            const SizedBox(height: 16),
          ],
        ],
      );
    },
  );

  Widget _subjectCard(BuildContext context, Map<String, dynamic> subject, Color color) => ChunkCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 14,
              height: 40,
              decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(99)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text('${subject['name']}',
                  style: const TextStyle(fontFamily: Brand.display, fontSize: 22, fontWeight: FontWeight.w800)),
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
            contentPadding: const EdgeInsets.symmetric(horizontal: 8),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            title: Text('${chapter['title']}', style: const TextStyle(fontWeight: FontWeight.w700)),
            trailing: Pill('${chapter['exercise_count']} exercice(s)'),
            onTap: () => _open(context, '${chapter['title']}', chapterId: chapter['id'] as int),
          ),
      ],
    ),
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
      final solved = items.where((item) => item['solved'] == true).length;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(child: AnimBar(value: solved / items.length)),
              const SizedBox(width: 12),
              Text('$solved / ${items.length} réussi(s)', style: const TextStyle(fontWeight: FontWeight.w800)),
            ],
          ),
          const SizedBox(height: 16),
          for (var i = 0; i < items.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Rise(delay: Duration(milliseconds: 30 * (i < 12 ? i : 12)), child: _tile(context, items[i])),
            ),
        ],
      );
    },
  );

  Widget _tile(BuildContext context, Map<String, dynamic> item) {
    final solved = item['solved'] == true;
    final started = (item['attempts'] as int) > 0;
    final level = item['difficulty'] as int?;
    return ChunkCard(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
      color: solved ? Brand.mint.withValues(alpha: .10) : null,
      child: ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(
          solved
              ? Icons.check_circle_rounded
              : started
              ? Icons.timelapse_rounded
              : Icons.circle_outlined,
          color: solved ? Brand.mint : (started ? Brand.sun : Brand.muted),
          size: 30,
        ),
        title: Text('${item['title']}', style: const TextStyle(fontWeight: FontWeight.w800)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              Pill(_types[item['exercise_type']] ?? '${item['exercise_type']}'),
              if (level != null)
                Pill(_levels[level] ?? '', color: (_levelColors[level] ?? Brand.soft).withValues(alpha: .22)),
              Pill('${item['points']} pt'),
            ],
          ),
        ),
        trailing: const Icon(Icons.chevron_right_rounded),
        onTap: () => Navigator.of(context)
            .push(MaterialPageRoute<void>(
              builder: (_) => StudentExercisePage(api: widget.api, exerciseId: item['id'] as int),
            ))
            .then((_) {
              if (mounted) setState(() { _items = _load(); });
            }),
      ),
    );
  }
}

/// Un exercice : énoncé mis en forme (ou image d'origine si la réécriture est douteuse), une réponse par
/// question, les démonstrations facultatives, et en bas un seul lien vers la correction.
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
  final Set<int> _chosen = {};
  final _answer = TextEditingController();
  String _latex = '';
  bool _busy = false;
  bool? _showOriginal; // null : ouvert d'office quand l'énoncé renvoie à une figure
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
  bool get _mathAnswer => const {'numerique', 'a_completer'}.contains(_exercise?['exercise_type']);

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.api.submitAttempt(
        widget.exerciseId,
        answer: _withOptions ? null : (_mathAnswer ? _latex : _answer.text),
        optionIds: _withOptions ? _chosen.toList() : null,
      );
      final exercise = await widget.api.studentExercise(widget.exerciseId);
      if (!mounted) return;
      setState(() {
        _result = result;
        _exercise = exercise;
      });
      _feedback(result['result'] as String?, result['after_correction'] == true);
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _feedback(String? result, bool afterCorrection) {
    if (result == 'correct') {
      Sounds.success();
      if (!afterCorrection) celebrate(context);
    } else if (result == 'incorrect' || result == 'partial') {
      Sounds.gentleError();
    } else {
      Sounds.sent();
    }
  }

  Future<void> _openCorrection() async {
    final e = _exercise!;
    Sounds.flip();
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => CorrectionPage(api: widget.api, exerciseId: widget.exerciseId, title: '${e['title']}'),
    ));
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final e = _exercise;
    return Scaffold(
      appBar: AppBar(title: Text(e == null ? 'Exercice' : '${e['title']}'), actions: const [SoundToggle()]),
      body: e == null
          ? Center(child: _error == null ? const CircularProgressIndicator() : _Info(_error!))
          : PageFrame(
              title: '${e['title']}',
              children: [
                _tags(e),
                _statementCard(e),
                if ((e['questions'] as List).isNotEmpty) ..._questions(e) else _answerCard(e),
                _correctionLink(e),
              ],
            ),
    );
  }

  Widget _tags(Map<String, dynamic> e) {
    final level = e['difficulty'] as int?;
    final tries = (e['history'] as List).length;
    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: [
        Pill(_types[e['exercise_type']] ?? '${e['exercise_type']}', icon: Icons.edit_note_rounded),
        if (level != null)
          Pill(_levels[level] ?? '', color: (_levelColors[level] ?? Brand.soft).withValues(alpha: .25)),
        Pill('${e['points']} pt', icon: Icons.star_rounded, color: Brand.sun.withValues(alpha: .35)),
        if (tries > 0) Pill('$tries essai(s)', icon: Icons.history_rounded),
      ],
    );
  }

  Widget _statementCard(Map<String, dynamic> e) {
    final hasOriginal = (e['original_pages'] as List).isNotEmpty;
    final originalFirst = e['original_first'] == true;
    final rewritten = e['rewrite_status'] == 'ok' || e['rewrite_status'] == 'doubtful';
    final original = AuthImage(api: widget.api, path: '/api/v1/student/exercises/${e['id']}/original.png');
    final showOriginal = _showOriginal ?? '${e['statement']}'.contains('[figure]');
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Row(
            children: [
              Icon(Icons.menu_book_rounded, color: Brand.blue),
              SizedBox(width: 8),
              Text('Énoncé', style: TextStyle(fontFamily: Brand.display, fontSize: 20, fontWeight: FontWeight.w800)),
            ],
          ),
          const SizedBox(height: 12),
          if (originalFirst) ...[
            ClipRRect(borderRadius: BorderRadius.circular(14), child: original),
            const SizedBox(height: 6),
            const Text('Énoncé tel qu’il figure dans le document.', style: TextStyle(color: Brand.muted, fontSize: 13)),
            if (rewritten)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('Version mise en forme (à vérifier avec l’original)',
                    style: TextStyle(fontWeight: FontWeight.w700)),
                children: [MathView(api: widget.api, text: '${e['statement']}', fontSize: 17)],
              )
            else
              MathView(api: widget.api, text: '${e['statement']}', fontSize: 17),
          ] else ...[
            MathView(api: widget.api, text: '${e['statement']}', fontSize: 17),
            if (hasOriginal)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => setState(() => _showOriginal = !showOriginal),
                  icon: Icon(showOriginal ? Icons.expand_less_rounded : Icons.image_outlined),
                  label: Text(showOriginal ? 'Masquer l’original' : 'Voir l’énoncé d’origine'),
                ),
              ),
            if (showOriginal) ClipRRect(borderRadius: BorderRadius.circular(14), child: original),
          ],
          for (final asset in (e['assets'] as List).cast<Map>()) ...[
            const SizedBox(height: 12),
            AuthImage(api: widget.api, path: '/api/v1/student/assets/${asset['id']}'),
            if (asset['caption'] != null) Text('${asset['caption']}', style: const TextStyle(color: Brand.muted)),
          ],
          const SizedBox(height: 12),
          Text('Source : ${e['source']}', style: const TextStyle(fontSize: 13, color: Brand.muted)),
        ],
      ),
    );
  }

  List<Widget> _questions(Map<String, dynamic> e) {
    final questions = (e['questions'] as List).cast<Map<String, dynamic>>();
    final proofs = questions.where((q) => q['kind'] == 'proof').length;
    return [
      Text(
        proofs > 0
            ? 'Réponds aux questions que tu peux : donne au moins les résultats. '
                  'Les démonstrations sont facultatives.'
            : 'Réponds question par question : ton résultat est vérifié tout de suite.',
        style: const TextStyle(color: Brand.muted, fontWeight: FontWeight.w700),
      ),
      for (final question in questions)
        QuestionCard(
          key: ValueKey('question-${question['id']}'),
          api: widget.api,
          question: question,
          correctionViewed: e['correction_viewed'] == true,
          onAnswered: _load,
        ),
    ];
  }

  Widget _answerCard(Map<String, dynamic> e) {
    final result = _result;
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Ma réponse', style: TextStyle(fontFamily: Brand.display, fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          if (_withOptions)
            for (final option in (e['options'] as List).cast<Map>())
              CheckboxListTile(
                value: _chosen.contains(option['id']),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                onChanged: (on) => setState(
                  () => on == true ? _chosen.add(option['id'] as int) : _chosen.remove(option['id']),
                ),
                title: Row(
                  children: [
                    Text('${option['label']}. ', style: const TextStyle(fontWeight: FontWeight.w800)),
                    Expanded(child: MathView(api: widget.api, text: '${option['text']}')),
                  ],
                ),
              )
          else if (_mathAnswer)
            MathInput(onChanged: (value) => _latex = value, onSubmit: _busy ? null : _submit)
          else
            WritingPad(api: widget.api, controller: _answer),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: PressButton(
              label: _busy ? '…' : 'Valider ma réponse',
              icon: Icons.check_rounded,
              primary: true,
              onPressed: _busy ? null : _submit,
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: Brand.bad, fontWeight: FontWeight.w700)),
          ],
          if (result != null) ...[
            const SizedBox(height: 12),
            ResultBox(
              ok: result['result'] == 'correct',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${result['message']} (${_score(result['score'])} / ${result['max_score']})',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                  if (result['after_correction'] == true)
                    const Text('Réponse donnée après la correction : elle ne compte pas comme réussie.',
                        style: TextStyle(color: Brand.muted)),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _correctionLink(Map<String, dynamic> e) {
    final available = e['correction_available'] == true;
    return Center(
      child: Column(
        children: [
          TextButton.icon(
            onPressed: available ? _openCorrection : null,
            icon: Icon(available ? Icons.lock_open_rounded : Icons.lock_outline_rounded),
            label: const Text('Voir la correction',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, decoration: TextDecoration.underline)),
          ),
          if (!available)
            Text('${e['correction_rule']}', textAlign: TextAlign.center, style: const TextStyle(color: Brand.muted)),
        ],
      ),
    );
  }
}

/// Une question : « résultat » (clavier mathématique, vérifié par le serveur) ou « démonstration »
/// (facultative, rédigée librement, auto-évaluée après lecture de la correction).
class QuestionCard extends StatefulWidget {
  const QuestionCard({
    super.key,
    required this.api,
    required this.question,
    required this.correctionViewed,
    required this.onAnswered,
  });
  final ApiClient api;
  final Map<String, dynamic> question;
  final bool correctionViewed;
  final Future<void> Function() onAnswered;

  @override
  State<QuestionCard> createState() => _QuestionCardState();
}

class _QuestionCardState extends State<QuestionCard> {
  late String _latex = '${widget.question['last_answer'] ?? ''}';
  late final _text = TextEditingController(
    text: widget.question['kind'] == 'proof' ? '${widget.question['last_answer'] ?? ''}' : '',
  );
  late String? _status = widget.question['last_result'] as String?;
  late bool _writing = widget.question['kind'] != 'proof' || widget.question['last_answer'] != null;
  // Réponse en mots (« AHB est un triangle … ») : champ texte ; calcul : clavier mathématique.
  late bool _plain = _looksVerbal('${widget.question['text']}');
  late final _plainText = TextEditingController(text: _plain ? '${widget.question['last_answer'] ?? ''}' : '');
  String? _message;
  bool _busy = false;

  bool get _proof => widget.question['kind'] == 'proof';
  bool get _checkable => widget.question['checkable'] == true;

  @override
  void dispose() {
    _text.dispose();
    _plainText.dispose();
    super.dispose();
  }

  Future<void> _send({String? selfCheck}) async {
    final answer = _proof ? _text.text.trim() : (_plain ? _plainText.text.trim() : _latex.trim());
    if (selfCheck == null && answer.isEmpty) {
      setState(() => _message = 'Écris ta réponse avant de l’envoyer.');
      return;
    }
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final result = await widget.api.answerQuestion(
        widget.question['id'] as int,
        answer: selfCheck == null ? answer : null,
        selfCheck: selfCheck,
      );
      if (!mounted) return;
      final verdict = result['result'] as String;
      setState(() {
        _status = verdict;
        _message = '${result['message']}';
      });
      switch (verdict) {
        case 'correct' || 'self_ok':
          Sounds.success();
          if (result['after_correction'] != true) celebrate(context, label: verdict == 'correct' ? 'Juste !' : 'Bravo !');
        case 'incorrect':
          Sounds.gentleError();
        default:
          Sounds.sent();
      }
      await widget.onAnswered();
    } catch (error) {
      if (mounted) setState(() => _message = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    final q = widget.question;
    final color = _proof ? Brand.lilac : Brand.blue;
    final selfGraded = _proof || !_checkable;
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(color: color.withValues(alpha: .16), shape: BoxShape.circle),
                child: Text('${q['label']}',
                    style: TextStyle(fontFamily: Brand.display, fontWeight: FontWeight.w800, color: color, fontSize: 16)),
              ),
              const SizedBox(width: 10),
              Pill(
                _proof ? 'Démonstration · facultative' : (_checkable ? 'Résultat · vérifié' : 'Résultat'),
                color: color.withValues(alpha: .16),
                textColor: color,
              ),
              const Spacer(),
              if (_status != null) _statusIcon(_status!),
            ],
          ),
          const SizedBox(height: 10),
          MathView(api: widget.api, text: '${q['text']}', fontSize: 17),
          const SizedBox(height: 12),
          if (_proof && !_writing)
            Align(
              alignment: Alignment.centerLeft,
              child: PressButton(
                label: 'Rédiger ma démonstration',
                icon: Icons.draw_rounded,
                onPressed: () => setState(() => _writing = true),
              ),
            )
          else ...[
            if (_proof)
              WritingPad(api: widget.api, controller: _text, hint: 'Rédige ta démonstration étape par étape…')
            else if (_plain)
              TextField(
                controller: _plainText,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.done,
                onSubmitted: _busy ? null : (_) => _send(),
                decoration: const InputDecoration(hintText: 'Écris ta réponse…'),
              )
            else
              MathInput(
                initial: _latex,
                onChanged: (value) => _latex = value,
                onSubmit: _busy ? null : () => _send(),
              ),
            if (!_proof)
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: () => setState(() => _plain = !_plain),
                  icon: Icon(_plain ? Icons.functions_rounded : Icons.text_fields_rounded, size: 18),
                  label: Text(_plain ? 'Clavier mathématique' : 'Répondre en texte'),
                ),
              ),
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerLeft,
              child: PressButton(
                label: _busy ? '…' : (_checkable ? 'Vérifier' : 'Enregistrer ma réponse'),
                icon: _checkable ? Icons.check_rounded : Icons.save_rounded,
                primary: true,
                onPressed: _busy ? null : () => _send(),
              ),
            ),
          ],
          if (_message != null) ...[
            const SizedBox(height: 10),
            ResultBox(
              ok: _status == 'correct' || _status == 'self_ok' || _status == 'submitted',
              child: Text(_message!, style: const TextStyle(fontWeight: FontWeight.w700)),
            ),
          ],
          if (selfGraded && widget.correctionViewed && (_status == 'submitted' || _proof)) ...[
            const SizedBox(height: 12),
            Text('Après lecture de la correction, comment était ta réponse ?',
                style: TextStyle(color: p.muted, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                PressButton(
                  label: 'J’avais juste',
                  icon: Icons.thumb_up_alt_rounded,
                  color: Brand.mint.withValues(alpha: .22),
                  onPressed: _busy ? null : () => _send(selfCheck: 'self_ok'),
                ),
                PressButton(
                  label: 'À retravailler',
                  icon: Icons.replay_rounded,
                  color: Brand.coral.withValues(alpha: .22),
                  onPressed: _busy ? null : () => _send(selfCheck: 'self_review'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _statusIcon(String status) => switch (status) {
    'correct' || 'self_ok' => const Icon(Icons.check_circle_rounded, color: Brand.mint),
    'incorrect' || 'self_review' => const Icon(Icons.replay_circle_filled_rounded, color: Brand.coral),
    _ => const Icon(Icons.mark_email_read_rounded, color: Brand.sky),
  };
}

/// Page de correction, ouverte depuis le lien en bas de l'exercice.
class CorrectionPage extends StatefulWidget {
  const CorrectionPage({super.key, required this.api, required this.exerciseId, required this.title});
  final ApiClient api;
  final int exerciseId;
  final String title;

  @override
  State<CorrectionPage> createState() => _CorrectionPageState();
}

class _CorrectionPageState extends State<CorrectionPage> {
  late final Future<Map<String, dynamic>> _correction = widget.api.studentCorrection(widget.exerciseId);

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text('Correction · ${widget.title}'), actions: const [SoundToggle()]),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _correction,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: _Info(_errorText(snapshot.error)));
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final c = snapshot.data!;
        final answers = ((c['question_answers'] as Map?) ?? const {}).cast<String, dynamic>();
        final body = c['text_latex'] ?? c['steps'];
        return PageFrame(
          title: 'Correction',
          children: [
            if (answers.isNotEmpty)
              ChunkCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Résultats attendus',
                        style: TextStyle(fontFamily: Brand.display, fontSize: 20, fontWeight: FontWeight.w800)),
                    const SizedBox(height: 8),
                    for (final entry in answers.entries)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Pill('Question ${entry.key}'),
                            const SizedBox(width: 10),
                            Expanded(child: MathView(api: widget.api, text: '\$${entry.value}\$')),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            if (c['expected_answer'] != null || c['final_answer'] != null)
              ChunkCard(
                color: Brand.mint.withValues(alpha: .10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Réponse', style: TextStyle(fontWeight: FontWeight.w800)),
                    MathView(api: widget.api, text: '${c['final_answer'] ?? c['expected_answer']}'),
                  ],
                ),
              ),
            if (body != null)
              ChunkCard(child: MathView(api: widget.api, text: '$body', fontSize: 17)),
            if (c['source'] != null)
              Text('Source : ${c['source']}', style: const TextStyle(fontSize: 13, color: Brand.muted)),
            const Text(
              'Relis ta réponse, puis reviens à l’exercice pour dire si tu avais juste : '
              'une réponse donnée après la correction ne compte pas comme réussie.',
              style: TextStyle(color: Brand.muted),
            ),
          ],
        );
      },
    ),
  );
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

/// Vrai quand la question attend des mots plutôt qu'un calcul : ni chiffre, ni signe de calcul, ni LaTeX.
bool _looksVerbal(String text) => !RegExp(r'[0-9=+×÷^√$\\]').hasMatch(text);
