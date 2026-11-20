// Administration de la mémorisation (Phase 4) : cartes de révision, méthodes d'apprentissage, répétition espacée.
// Les cartes viennent des documents ; l'administrateur les relit, les rattache au parcours (niveau, séries jamais
// mélangées, matière, chapitre), les valide puis les publie. Les méthodes du cahier des charges sont rédigées
// ici avant d'être validées pour les élèves.
import 'package:material_ui/material_ui.dart';

import 'api_client.dart';
import 'math_view.dart';
import 'theme.dart';

const _cardStatus = {
  'extracted': 'Extraite',
  'transformed': 'Modifiée',
  'pending_validation': 'À valider',
  'validated': 'Validée',
  'rejected': 'Rejetée',
};

const _cardTypes = {
  'question': 'Question',
  'definition': 'Définition',
  'formule': 'Formule',
  'vrai_faux': 'Vrai / faux',
  'a_completer': 'À compléter',
  'numerique': 'Numérique',
};

const _methodCategories = {
  'rappel': 'Rappel',
  'comprehension': 'Compréhension',
  'mnemotechnique': 'Mnémotechnique',
  'organisation': 'Organisation',
};

Color _statusColor(String? status) => switch (status) {
  'validated' => Brand.mint,
  'pending_validation' => Brand.sun,
  'rejected' => Brand.coral,
  'transformed' => Brand.blue,
  _ => Brand.muted,
};

void _message(BuildContext context, String text, {bool error = false}) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(text), backgroundColor: error ? Brand.bad : Brand.good),
  );
}

class _Pill extends StatelessWidget {
  const _Pill(this.label, this.color);
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.18),
      borderRadius: BorderRadius.circular(99),
      border: Border.all(color: color, width: 1.2),
    ),
    child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
  );
}

/// Référentiels chargés une fois (niveaux, séries, matières, chapitres, documents).
class _Refs {
  _Refs(this.grades, this.tracks, this.subjects, this.chapters, this.documents);
  final List<Map<String, dynamic>> grades, tracks, subjects, chapters, documents;

  static Future<_Refs> load(ApiClient api) async {
    final r = await Future.wait([
      api.listAdmin('grades'),
      api.listAdmin('tracks'),
      api.listAdmin('subjects'),
      api.listAdmin('chapters'),
      api.listDocuments(),
    ]);
    return _Refs(r[0], r[1], r[2], r[3], r[4]);
  }

  String _name(List<Map<String, dynamic>> items, Object? id, [String key = 'name']) {
    for (final item in items) {
      if (item['id'] == id) return '${item[key]}';
    }
    return '—';
  }

  String grade(Object? id) => _name(grades, id);
  String subject(Object? id) => _name(subjects, id);
  String chapter(Object? id) => _name(chapters, id, 'title');
  String document(Object? id) => _name(documents, id, 'title');
  String series(Object? ids) {
    final list = (ids as List?)?.cast<int>() ?? const <int>[];
    return list.isEmpty ? '' : list.map((id) => _name(tracks, id)).join(', ');
  }
}

class MemoryAdmin extends StatefulWidget {
  const MemoryAdmin({super.key, required this.api, required this.onSignOut});

  final ApiClient api;
  final VoidCallback onSignOut;

  @override
  State<MemoryAdmin> createState() => _MemoryAdminState();
}

class _MemoryAdminState extends State<MemoryAdmin> {
  late final Future<_Refs> _refs = _Refs.load(widget.api);

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Mémorisation'),
          leading: IconButton(
            tooltip: 'Retour',
            onPressed: () => Navigator.of(context).maybePop(),
            icon: const Icon(Icons.arrow_back_rounded),
          ),
          actions: [
            TextButton.icon(
              onPressed: widget.onSignOut,
              icon: const Icon(Icons.logout_rounded),
              label: const Text('Déconnexion'),
            ),
            const SizedBox(width: 12),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.style_rounded), text: 'Cartes'),
              Tab(icon: Icon(Icons.psychology_rounded), text: 'Méthodes'),
              Tab(icon: Icon(Icons.event_repeat_rounded), text: 'Répétition espacée'),
            ],
          ),
        ),
        body: FutureBuilder<_Refs>(
          future: _refs,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Center(child: Text('Chargement impossible : ${snapshot.error}'));
            }
            final refs = snapshot.data;
            if (refs == null) return const Center(child: CircularProgressIndicator());
            return TabBarView(
              children: [
                _CardsTab(api: widget.api, refs: refs),
                _MethodsTab(api: widget.api),
                _SpacedTab(api: widget.api),
              ],
            );
          },
        ),
      ),
    );
  }
}

// --------------------------------------------------------------------------- cartes

class _CardsTab extends StatefulWidget {
  const _CardsTab({required this.api, required this.refs});
  final ApiClient api;
  final _Refs refs;

  @override
  State<_CardsTab> createState() => _CardsTabState();
}

class _CardsTabState extends State<_CardsTab> with AutomaticKeepAliveClientMixin {
  String? _status = 'extracted';
  int? _document;
  final _cards = <Map<String, dynamic>>[];
  bool _busy = false, _more = true;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  Future<void> _load({bool reset = false}) async {
    setState(() => _busy = true);
    try {
      final page = await widget.api.listFlashcards(
        status: _status,
        documentId: _document,
        offset: reset ? 0 : _cards.length,
      );
      setState(() {
        if (reset) _cards.clear();
        _cards.addAll(page);
        _more = page.length == 200;
      });
    } on ApiException catch (e) {
      if (mounted) _message(context, e.message, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _replace(Map<String, dynamic> card) {
    final index = _cards.indexWhere((c) => c['id'] == card['id']);
    if (index >= 0) setState(() => _cards[index] = card);
  }

  Future<void> _open(Map<String, dynamic> card) async {
    final updated = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _CardDialog(api: widget.api, refs: widget.refs, card: card),
    );
    if (updated != null) _replace(updated);
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final documents = widget.refs.documents;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Wrap(
            spacing: 12,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 220,
                child: DropdownButtonFormField<String?>(
                  initialValue: _status,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Statut'),
                  items: [
                    const DropdownMenuItem(value: null, child: Text('Tous')),
                    for (final e in _cardStatus.entries) DropdownMenuItem(value: e.key, child: Text(e.value)),
                  ],
                  onChanged: (value) {
                    _status = value;
                    _load(reset: true);
                  },
                ),
              ),
              SizedBox(
                width: 360,
                child: DropdownButtonFormField<int?>(
                  initialValue: _document,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Document source'),
                  items: [
                    const DropdownMenuItem(value: null, child: Text('Tous les documents')),
                    for (final d in documents)
                      DropdownMenuItem(
                        value: d['id'] as int,
                        child: Text('${d['title']}', overflow: TextOverflow.ellipsis),
                      ),
                  ],
                  onChanged: (value) {
                    _document = value;
                    _load(reset: true);
                  },
                ),
              ),
              Text('${_cards.length}${_more ? '+' : ''} carte(s)', style: const TextStyle(color: Brand.muted)),
              if (_busy) const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2)),
            ],
          ),
        ),
        Expanded(
          child: _cards.isEmpty && !_busy
              ? const Center(child: Text('Aucune carte pour ce filtre.'))
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  itemCount: _cards.length + (_more ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index == _cards.length) {
                      return Center(
                        child: TextButton.icon(
                          onPressed: _busy ? null : _load,
                          icon: const Icon(Icons.expand_more_rounded),
                          label: const Text('Afficher plus'),
                        ),
                      );
                    }
                    return _cardTile(_cards[index]);
                  },
                ),
        ),
      ],
    );
  }

  Widget _cardTile(Map<String, dynamic> card) {
    final refs = widget.refs;
    final series = refs.series(card['track_ids']);
    final place = [
      refs.grade(card['grade_id']),
      if (series.isNotEmpty) series,
      refs.subject(card['subject_id']),
      card['chapter_id'] == null ? 'chapitre à préciser' : refs.chapter(card['chapter_id']),
    ].join(' · ');
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _open(card),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: [
                  _Pill(_cardStatus[card['status']] ?? '${card['status']}', _statusColor('${card['status']}')),
                  _Pill(_cardTypes[card['card_type']] ?? '${card['card_type']}', Brand.lilac),
                  if (card['is_published'] == true) const _Pill('Publiée', Brand.mint),
                  if (card['is_archived'] == true) const _Pill('Archivée', Brand.muted),
                ],
              ),
              const SizedBox(height: 8),
              Text('${card['question']}', maxLines: 3, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              Text('→ ${card['answer']}', maxLines: 2, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 6),
              Text(
                '$place\nSource : ${refs.document(card['document_id'])}'
                '${card['page_number'] == null ? '' : ', p. ${card['page_number']}'}',
                style: const TextStyle(color: Brand.muted, fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CardDialog extends StatefulWidget {
  const _CardDialog({required this.api, required this.refs, required this.card});
  final ApiClient api;
  final _Refs refs;
  final Map<String, dynamic> card;

  @override
  State<_CardDialog> createState() => _CardDialogState();
}

class _CardDialogState extends State<_CardDialog> {
  late Map<String, dynamic> _card = widget.card;
  late final _question = TextEditingController(text: '${_card['question']}');
  late final _answer = TextEditingController(text: '${_card['answer']}');
  late final _hint = TextEditingController(text: '${_card['hint'] ?? ''}');
  late String _type = '${_card['card_type']}';
  late int _difficulty = (_card['difficulty'] as int?) ?? 1;
  late int? _grade = _card['grade_id'] as int?;
  late int? _subject = _card['subject_id'] as int?;
  late int? _chapter = _card['chapter_id'] as int?;
  late List<int> _tracks = ((_card['track_ids'] as List?) ?? const []).cast<int>();
  bool _busy = false, _changed = false;

  @override
  void dispose() {
    _question.dispose();
    _answer.dispose();
    _hint.dispose();
    super.dispose();
  }

  Future<void> _run(Future<Map<String, dynamic>> Function() action, String success) async {
    setState(() => _busy = true);
    try {
      final card = await action();
      setState(() {
        _card = card;
        _changed = true;
      });
      if (mounted) _message(context, success);
    } on ApiException catch (e) {
      if (mounted) _message(context, e.message, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() => _run(
    () => widget.api.updateFlashcard(_card['id'] as int, {
      'question': _question.text.trim(),
      'answer': _answer.text.trim(),
      'hint': _hint.text.trim().isEmpty ? null : _hint.text.trim(),
      'card_type': _type,
      'difficulty': _difficulty,
      'grade_id': _grade,
      'track_ids': _tracks,
      'subject_id': _subject,
      'chapter_id': _chapter,
    }),
    'Carte enregistrée',
  );

  Future<void> _act(String action, String success) =>
      _run(() => widget.api.flashcardAction(_card['id'] as int, action), success);

  @override
  Widget build(BuildContext context) {
    final refs = widget.refs;
    final tracks = refs.tracks.where((t) => t['grade_id'] == _grade).toList();
    final chapters = refs.chapters
        .where((c) => c['grade_id'] == _grade && c['subject_id'] == _subject)
        .toList();
    final status = '${_card['status']}';
    final published = _card['is_published'] == true, archived = _card['is_archived'] == true;
    return AlertDialog(
      title: Row(
        children: [
          Expanded(child: Text('Carte n° ${_card['id']}')),
          _Pill(_cardStatus[status] ?? status, _statusColor(status)),
        ],
      ),
      content: SizedBox(
        width: 720,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Source : ${refs.document(_card['document_id'])}'
                '${_card['page_number'] == null ? '' : ', page ${_card['page_number']}'}',
                style: const TextStyle(color: Brand.muted),
              ),
              if ('${_card['original_text']}'.trim().isNotEmpty) ...[
                const SizedBox(height: 8),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Texte original du document'),
                  children: [SelectableText('${_card['original_text']}')],
                ),
              ],
              const SizedBox(height: 8),
              TextField(
                controller: _question,
                minLines: 2,
                maxLines: 6,
                decoration: const InputDecoration(labelText: 'Question (LaTeX entre \$…\$)'),
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 6),
              MathView(api: widget.api, text: _question.text, fontSize: 15),
              const SizedBox(height: 12),
              TextField(
                controller: _answer,
                minLines: 1,
                maxLines: 6,
                decoration: const InputDecoration(labelText: 'Réponse'),
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 6),
              MathView(api: widget.api, text: _answer.text, fontSize: 15),
              const SizedBox(height: 12),
              TextField(controller: _hint, decoration: const InputDecoration(labelText: 'Indice (facultatif)')),
              const SizedBox(height: 12),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  SizedBox(
                    width: 200,
                    child: DropdownButtonFormField<String>(
                      initialValue: _cardTypes.containsKey(_type) ? _type : 'question',
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Type'),
                      items: [
                        for (final e in _cardTypes.entries) DropdownMenuItem(value: e.key, child: Text(e.value)),
                      ],
                      onChanged: (v) => setState(() => _type = v ?? _type),
                    ),
                  ),
                  SizedBox(
                    width: 160,
                    child: DropdownButtonFormField<int>(
                      initialValue: _difficulty,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Difficulté'),
                      items: const [
                        DropdownMenuItem(value: 1, child: Text('1 · facile')),
                        DropdownMenuItem(value: 2, child: Text('2 · moyen')),
                        DropdownMenuItem(value: 3, child: Text('3 · difficile')),
                      ],
                      onChanged: (v) => setState(() => _difficulty = v ?? _difficulty),
                    ),
                  ),
                  SizedBox(
                    width: 200,
                    child: DropdownButtonFormField<int?>(
                      initialValue: _grade,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Niveau'),
                      items: [
                        for (final g in refs.grades)
                          DropdownMenuItem(value: g['id'] as int, child: Text('${g['name']}')),
                      ],
                      onChanged: (v) => setState(() {
                        _grade = v;
                        _tracks = [];
                        _chapter = null;
                      }),
                    ),
                  ),
                  SizedBox(
                    width: 240,
                    child: DropdownButtonFormField<int?>(
                      initialValue: _subject,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Matière'),
                      items: [
                        for (final s in refs.subjects)
                          DropdownMenuItem(value: s['id'] as int, child: Text('${s['name']}')),
                      ],
                      onChanged: (v) => setState(() {
                        _subject = v;
                        _chapter = null;
                      }),
                    ),
                  ),
                  SizedBox(
                    width: 460,
                    child: DropdownButtonFormField<int?>(
                      key: ValueKey('chap-$_grade-$_subject'),
                      initialValue: chapters.any((c) => c['id'] == _chapter) ? _chapter : null,
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: 'Chapitre',
                        helperText: chapters.isEmpty ? 'Aucun chapitre pour ce niveau et cette matière' : null,
                      ),
                      items: [
                        for (final c in chapters)
                          DropdownMenuItem(value: c['id'] as int, child: Text('${c['title']}')),
                      ],
                      onChanged: (v) => setState(() => _chapter = v),
                    ),
                  ),
                ],
              ),
              if (tracks.isNotEmpty) ...[
                const SizedBox(height: 12),
                const Text('Séries visées (jamais mélangées entre niveaux)', style: TextStyle(color: Brand.muted)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final t in tracks)
                      FilterChip(
                        label: Text('${t['name']}'),
                        selected: _tracks.contains(t['id']),
                        onSelected: (on) => setState(() {
                          _tracks = on
                              ? [..._tracks, t['id'] as int]
                              : _tracks.where((id) => id != t['id']).toList();
                        }),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
      actionsOverflowButtonSpacing: 8,
      actions: [
        TextButton(
          onPressed: _busy ? null : () => Navigator.of(context).pop(_changed ? _card : null),
          child: const Text('Fermer'),
        ),
        if (!archived && status != 'rejected')
          TextButton(onPressed: _busy ? null : () => _act('reject', 'Carte rejetée'), child: const Text('Rejeter')),
        archived
            ? TextButton(onPressed: _busy ? null : () => _act('restore', 'Carte restaurée'), child: const Text('Restaurer'))
            : TextButton(onPressed: _busy ? null : () => _act('archive', 'Carte archivée'), child: const Text('Archiver')),
        OutlinedButton(onPressed: _busy ? null : _save, child: const Text('Enregistrer')),
        if (status != 'validated')
          FilledButton(onPressed: _busy ? null : () => _act('validate', 'Carte validée'), child: const Text('Valider')),
        if (status == 'validated' && !archived)
          FilledButton(
            onPressed: _busy
                ? null
                : () => published
                    ? _act('unpublish', 'Carte retirée des élèves')
                    : _act('publish', 'Carte publiée pour les élèves'),
            child: Text(published ? 'Retirer' : 'Publier'),
          ),
      ],
    );
  }
}

// --------------------------------------------------------------------------- méthodes

class _MethodsTab extends StatefulWidget {
  const _MethodsTab({required this.api});
  final ApiClient api;

  @override
  State<_MethodsTab> createState() => _MethodsTabState();
}

class _MethodsTabState extends State<_MethodsTab> with AutomaticKeepAliveClientMixin {
  List<Map<String, dynamic>>? _methods;
  String? _error;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final methods = await widget.api.listMethods();
      setState(() => _methods = methods);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    }
  }

  Future<void> _open(Map<String, dynamic> method) async {
    final updated = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _MethodDialog(api: widget.api, method: method),
    );
    if (updated != null) {
      setState(() {
        final index = _methods!.indexWhere((m) => m['id'] == updated['id']);
        if (index >= 0) _methods![index] = updated;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    if (_error != null) return Center(child: Text(_error!));
    final methods = _methods;
    if (methods == null) return const Center(child: CircularProgressIndicator());
    final validated = methods.where((m) => m['status'] == 'validated').length;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          '$validated méthode(s) validée(s) sur ${methods.length}. Seules les méthodes validées sont proposées aux '
          'élèves ; le principe et les étapes sont rédigés ici à partir des documents.',
          style: const TextStyle(color: Brand.muted),
        ),
        const SizedBox(height: 12),
        for (final category in _methodCategories.entries) ...[
          Padding(
            padding: const EdgeInsets.only(top: 12, bottom: 6),
            child: Text(category.value, style: Theme.of(context).textTheme.titleMedium),
          ),
          for (final m in methods.where((m) => m['category'] == category.key))
            Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                onTap: () => _open(m),
                title: Text('${m['name']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(
                  [
                    if ('${m['summary'] ?? ''}'.isNotEmpty) '${m['summary']}',
                    '${(m['steps'] as List?)?.length ?? 0} étape(s) · ${(m['examples'] as List?)?.length ?? 0} exemple(s)',
                  ].join('\n'),
                ),
                trailing: m['status'] == 'validated'
                    ? const _Pill('Validée', Brand.mint)
                    : const _Pill('Brouillon', Brand.muted),
              ),
            ),
        ],
      ],
    );
  }
}

class _MethodDialog extends StatefulWidget {
  const _MethodDialog({required this.api, required this.method});
  final ApiClient api;
  final Map<String, dynamic> method;

  @override
  State<_MethodDialog> createState() => _MethodDialogState();
}

class _MethodDialogState extends State<_MethodDialog> {
  late Map<String, dynamic> _method = widget.method;
  late final _name = TextEditingController(text: '${_method['name']}');
  late final _summary = TextEditingController(text: '${_method['summary'] ?? ''}');
  late final _principle = TextEditingController(text: '${_method['principle'] ?? ''}');
  late final _steps = TextEditingController(text: ((_method['steps'] as List?) ?? const []).join('\n'));
  bool _busy = false, _changed = false;

  @override
  void dispose() {
    for (final c in [_name, _summary, _principle, _steps]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _run(Future<Map<String, dynamic>> Function() action, String success) async {
    setState(() => _busy = true);
    try {
      final method = await action();
      setState(() {
        _method = method;
        _changed = true;
      });
      if (mounted) _message(context, success);
    } on ApiException catch (e) {
      if (mounted) _message(context, e.message, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() => _run(
    () => widget.api.updateMethod(_method['id'] as int, {
      'name': _name.text.trim(),
      'summary': _summary.text.trim(),
      'principle': _principle.text.trim().isEmpty ? null : _principle.text.trim(),
      'steps': _steps.text.split('\n').map((s) => s.trim()).where((s) => s.isNotEmpty).toList(),
    }),
    'Méthode enregistrée',
  );

  @override
  Widget build(BuildContext context) {
    final validated = _method['status'] == 'validated';
    final examples = (_method['examples'] as List?) ?? const [];
    return AlertDialog(
      title: Row(
        children: [
          Expanded(child: Text('${_method['name']}')),
          validated ? const _Pill('Validée', Brand.mint) : const _Pill('Brouillon', Brand.muted),
        ],
      ),
      content: SizedBox(
        width: 680,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(controller: _name, decoration: const InputDecoration(labelText: 'Nom')),
              const SizedBox(height: 12),
              TextField(
                controller: _summary,
                maxLines: 2,
                decoration: const InputDecoration(labelText: 'En une phrase (cahier des charges)'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _principle,
                minLines: 3,
                maxLines: 8,
                decoration: const InputDecoration(labelText: 'Principe'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _steps,
                minLines: 3,
                maxLines: 12,
                decoration: const InputDecoration(labelText: 'Étapes (une par ligne)'),
              ),
              if (examples.isNotEmpty) ...[
                const SizedBox(height: 12),
                const Text('Exemples tirés des documents', style: TextStyle(fontWeight: FontWeight.w700)),
                for (final e in examples.cast<Map<String, dynamic>>())
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text('• ${e['note']}  (${e['source']})'),
                  ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _busy ? null : () => Navigator.of(context).pop(_changed ? _method : null),
          child: const Text('Fermer'),
        ),
        OutlinedButton(onPressed: _busy ? null : _save, child: const Text('Enregistrer')),
        FilledButton(
          onPressed: _busy
              ? null
              : () => _run(
                  () => widget.api.methodAction(_method['id'] as int, validated ? 'unvalidate' : 'validate'),
                  validated ? 'Méthode retirée des élèves' : 'Méthode validée pour les élèves',
                ),
          child: Text(validated ? 'Retirer la validation' : 'Valider'),
        ),
      ],
    );
  }
}

// --------------------------------------------------------------------------- répétition espacée

class _SpacedTab extends StatefulWidget {
  const _SpacedTab({required this.api});
  final ApiClient api;

  @override
  State<_SpacedTab> createState() => _SpacedTabState();
}

class _SpacedTabState extends State<_SpacedTab> with AutomaticKeepAliveClientMixin {
  final _steps = TextEditingController();
  final _relearn = TextEditingController();
  final _minEase = TextEditingController();
  final _maxInterval = TextEditingController();
  final _mastery = TextEditingController();
  final _newPerDay = TextEditingController();
  bool _loaded = false, _busy = false;
  String? _error;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final c in [_steps, _relearn, _minEase, _maxInterval, _mastery, _newPerDay]) {
      c.dispose();
    }
    super.dispose();
  }

  String _num(Object? v) {
    if (v is double && v == v.roundToDouble()) return v.toInt().toString();
    return '$v';
  }

  void _fill(Map<String, dynamic> s) {
    _steps.text = ((s['learning_steps_days'] as List?) ?? const []).map(_num).join(', ');
    _relearn.text = _num(s['relearn_minutes']);
    _minEase.text = _num(s['min_ease']);
    _maxInterval.text = _num(s['max_interval_days']);
    _mastery.text = _num(s['mastery_interval_days']);
    _newPerDay.text = _num(s['new_cards_per_day']);
  }

  Future<void> _load() async {
    try {
      _fill(await widget.api.spacedSettings());
      setState(() => _loaded = true);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    }
  }

  Future<void> _save() async {
    double? d(String s) => double.tryParse(s.trim().replaceAll(',', '.'));
    int? i(String s) => int.tryParse(s.trim());
    final steps = _steps.text.split(RegExp(r'[;\s]+|,\s+')).where((s) => s.isNotEmpty).map(d).toList();
    if (steps.isEmpty || steps.contains(null)) {
      _message(context, 'Premiers intervalles : des nombres de jours séparés par des virgules', error: true);
      return;
    }
    final values = {
      'learning_steps_days': steps,
      'relearn_minutes': i(_relearn.text),
      'min_ease': d(_minEase.text),
      'max_interval_days': i(_maxInterval.text),
      'mastery_interval_days': i(_mastery.text),
      'new_cards_per_day': i(_newPerDay.text),
    };
    if (values.values.contains(null)) {
      _message(context, 'Chaque réglage doit être un nombre', error: true);
      return;
    }
    setState(() => _busy = true);
    try {
      _fill(await widget.api.saveSpacedSettings(values));
      if (mounted) _message(context, 'Réglages enregistrés');
    } on ApiException catch (e) {
      if (mounted) _message(context, e.message, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _field(TextEditingController controller, String label, String help) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: TextField(
      controller: controller,
      decoration: InputDecoration(labelText: label, helperText: help, helperMaxLines: 2),
    ),
  );

  @override
  Widget build(BuildContext context) {
    super.build(context);
    if (_error != null) return Center(child: Text(_error!));
    if (!_loaded) return const Center(child: CircularProgressIndicator());
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Align(
        alignment: Alignment.topLeft,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Ces réglages s\'appliquent à toutes les révisions des élèves (cartes et exercices).',
                style: TextStyle(color: Brand.muted),
              ),
              const SizedBox(height: 16),
              _field(_steps, 'Premiers intervalles (jours)', 'Croissants, séparés par des virgules. Ex. : 1, 3, 7'),
              _field(_relearn, 'Nouvel essai après une erreur (minutes)', 'Entre 1 et 1440'),
              _field(_minEase, 'Facilité minimale', 'Entre 1,1 et 2,5 : plus bas = la carte revient plus souvent'),
              _field(_maxInterval, 'Intervalle maximal (jours)', 'Entre 7 et 3650'),
              _field(_mastery, 'Carte maîtrisée à partir de (jours)', 'Intervalle au-delà duquel la notion est acquise'),
              _field(_newPerDay, 'Nouvelles cartes par jour', 'Entre 0 et 200 par élève'),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.icon(
                  onPressed: _busy ? null : _save,
                  icon: const Icon(Icons.save_rounded),
                  label: const Text('Enregistrer'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
