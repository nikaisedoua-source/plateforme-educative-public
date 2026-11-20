// Bibliothèque documentaire (Phase 2) — version web.
// Import → extraction → découpage → relecture → validation → publication.
import 'dart:async';
import 'dart:js_interop';
import 'dart:typed_data';

import 'package:material_ui/material_ui.dart';
import 'package:web/web.dart' as web;

import 'api_client.dart';
import 'theme.dart';

const documentStatusLabels = {
  'imported': 'Importé',
  'processing': 'Extraction en cours',
  'extracted': 'Texte extrait',
  'failed': 'Échec',
  'archived': 'Archivé',
};

const contentStatusLabels = {
  'extracted': 'Original extrait',
  'transformed': 'Transformé',
  'pending_validation': 'En attente de validation',
  'validated': 'Validé',
  'rejected': 'Rejeté',
};

const documentKinds = {
  'manuel': 'Manuel / cours',
  'fiche': 'Fiche',
  'exercices': 'Exercices',
  'devoir': 'Devoir',
  'examen': 'Examen / annale',
  'corrige': 'Corrigé',
  'revision': 'Révision',
  'methode': 'Méthode',
  'autre': 'Autre',
};

const exerciseTypes = {
  'libre': 'Réponse libre',
  'qcm': 'QCM',
  'vrai_faux': 'Vrai / faux',
  'a_completer': 'À compléter',
  'numerique': 'Réponse numérique',
  'probleme': 'Problème',
  'etude_de_cas': 'Étude de cas',
};

Color _statusColor(String? status) => switch (status) {
  'validated' || 'extracted_doc' => Brand.mint,
  'pending_validation' || 'processing' => Brand.sun,
  'rejected' || 'failed' => Brand.coral,
  'transformed' => Brand.blue,
  _ => Brand.soft,
};

class StatusPill extends StatelessWidget {
  const StatusPill(this.label, {super.key, this.color});
  final String label;
  final Color? color;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
    decoration: BoxDecoration(
      color: (color ?? Brand.soft).withValues(alpha: 0.25),
      borderRadius: BorderRadius.circular(99),
      border: Border.all(color: color ?? Brand.muted, width: 1.5),
    ),
    child: Text(
      label,
      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
    ),
  );
}

/// Référentiels (niveaux, matières, chapitres) chargés une fois pour les listes déroulantes.
class Refs {
  Refs(this.grades, this.subjects, this.chapters);
  final List<Map<String, dynamic>> grades, subjects, chapters;

  static Future<Refs> load(ApiClient api) async {
    final results = await Future.wait([
      api.listAdmin('grades'),
      api.listAdmin('subjects'),
      api.listAdmin('chapters'),
    ]);
    return Refs(results[0], results[1], results[2]);
  }

  String name(List<Map<String, dynamic>> items, Object? id, [String key = 'name']) {
    for (final item in items) {
      if (item['id'] == id) return '${item[key]}';
    }
    return '—';
  }

  String grade(Object? id) => name(grades, id);
  String subject(Object? id) => name(subjects, id);
  String chapter(Object? id) => name(chapters, id, 'title');
}

/// Image servie par l'API avec le jeton (aperçu de page, figure recadrée).
class AuthImage extends StatefulWidget {
  const AuthImage({super.key, required this.api, required this.path, this.height});
  final ApiClient api;
  final String path;
  final double? height;

  @override
  State<AuthImage> createState() => _AuthImageState();
}

class _AuthImageState extends State<AuthImage> {
  late Future<Uint8List> _bytes = widget.api.fetchBytes(widget.path);

  @override
  void didUpdateWidget(AuthImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.path != widget.path) _bytes = widget.api.fetchBytes(widget.path);
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Uint8List>(
    future: _bytes,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return SizedBox(
          height: widget.height ?? 120,
          child: Center(child: Text('Aperçu indisponible : ${snapshot.error}')),
        );
      }
      if (!snapshot.hasData) {
        return SizedBox(
          height: widget.height ?? 120,
          child: const Center(child: CircularProgressIndicator()),
        );
      }
      return Image.memory(
        snapshot.data!,
        height: widget.height,
        fit: BoxFit.contain,
        gaplessPlayback: true,
      );
    },
  );
}

Future<({String name, Uint8List bytes})?> pickFile() async {
  final input = web.HTMLInputElement()
    ..type = 'file'
    ..accept = '.pdf,.docx,.doc,.txt,.png,.jpg,.jpeg';
  final completer = Completer<web.File?>();
  input.onchange = ((web.Event _) {
    final files = input.files;
    completer.complete(files != null && files.length > 0 ? files.item(0) : null);
  }).toJS;
  input.click();
  final file = await completer.future;
  if (file == null) return null;
  final buffer = await file.arrayBuffer().toDart;
  return (name: file.name, bytes: buffer.toDart.asUint8List());
}

void showMessage(BuildContext context, String message, {bool error = false}) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(message),
      backgroundColor: error ? Brand.bad : Brand.good,
    ),
  );
}

// ---------------------------------------------------------------------------
// Écran principal
// ---------------------------------------------------------------------------

class LibraryAdmin extends StatefulWidget {
  const LibraryAdmin({super.key, required this.api, required this.onSignOut});
  final ApiClient api;
  final VoidCallback onSignOut;

  @override
  State<LibraryAdmin> createState() => _LibraryAdminState();
}

class _LibraryAdminState extends State<LibraryAdmin> {
  Refs? _refs;
  List<Map<String, dynamic>> _documents = [];
  List<Map<String, dynamic>> _exercises = [];
  String _search = '';
  String? _exerciseStatus = 'pending_validation';
  String? _error;
  bool _busy = false;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _guard(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
      _error = null;
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        widget.api.logout();
        widget.onSignOut();
        return;
      }
      _error = exception.message;
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _reload() => _guard(() async {
    _refs ??= await Refs.load(widget.api);
    await _loadDocuments();
    _exercises = await widget.api.listExercises(status: _exerciseStatus);
  });

  Future<void> _loadDocuments() async {
    _documents = await widget.api.listDocuments(search: _search);
    final processing = _documents.any((d) => d['status'] == 'processing');
    _poll?.cancel();
    if (processing) {
      _poll = Timer(const Duration(seconds: 2), () async {
        if (!mounted) return;
        try {
          await _loadDocuments();
          if (mounted) setState(() {});
        } on ApiException catch (_) {}
      });
    }
  }

  Future<void> _upload() async {
    final picked = await pickFile();
    if (picked == null || !mounted) return;
    await _guard(() async {
      final document = await widget.api.uploadDocument(
        bytes: picked.bytes,
        filename: picked.name,
      );
      await widget.api.extractDocument(document['id'] as int);
      await _loadDocuments();
      if (mounted) {
        showMessage(context, 'Document importé, extraction lancée : ${picked.name}');
      }
    });
  }

  void _openDocument(Map<String, dynamic> document) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DocumentDetailPage(
          api: widget.api,
          refs: _refs!,
          documentId: document['id'] as int,
          documents: _documents,
        ),
      ),
    );
    _reload();
  }

  void _openExercise(int id) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ExerciseEditorPage(api: widget.api, refs: _refs!, exerciseId: id),
      ),
    );
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Bibliothèque documentaire'),
          actions: [
            IconButton(
              tooltip: 'Actualiser',
              onPressed: _busy ? null : _reload,
              icon: const Icon(Icons.refresh_rounded),
            ),
            TextButton.icon(
              onPressed: widget.onSignOut,
              icon: const Icon(Icons.logout_rounded),
              label: const Text('Déconnexion'),
            ),
            const SizedBox(width: 12),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Documents'),
              Tab(text: 'Exercices à relire'),
            ],
          ),
        ),
        body: Column(
          children: [
            if (_busy) const LinearProgressIndicator(minHeight: 3),
            if (_error != null)
              MaterialBanner(
                content: Text(_error!),
                backgroundColor: Brand.coral.withValues(alpha: 0.15),
                actions: [
                  TextButton(
                    onPressed: () => setState(() => _error = null),
                    child: const Text('Fermer'),
                  ),
                ],
              ),
            Expanded(
              child: _refs == null
                  ? const Center(child: CircularProgressIndicator())
                  : TabBarView(children: [_documentsTab(), _exercisesTab()]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _documentsTab() {
    final refs = _refs!;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            PressButton(
              label: 'Importer un document',
              primary: true,
              onPressed: _busy ? null : _upload,
            ),
            SizedBox(
              width: 320,
              child: TextField(
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search_rounded),
                  hintText: 'Rechercher un titre ou un nom de fichier',
                ),
                onSubmitted: (value) {
                  _search = value.trim();
                  _guard(_loadDocuments);
                },
              ),
            ),
            Text('${_documents.length} document(s)'),
          ],
        ),
        const SizedBox(height: 8),
        const Text(
          'Formats : PDF, DOCX, DOC, TXT, PNG, JPG. Les pages scannées passent par la '
          'reconnaissance de texte (OCR). Rien n’est publié sans validation.',
        ),
        const SizedBox(height: 16),
        if (_documents.isEmpty)
          const ChunkCard(child: Text('Aucun document pour le moment.')),
        for (final document in _documents)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Card(
              child: ListTile(
                onTap: () => _openDocument(document),
                leading: const Icon(Icons.description_rounded),
                title: Text(
                  '${document['title']}',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${document['original_filename']} · '
                      '${documentKinds[document['kind']] ?? document['kind']} · '
                      '${refs.subject(document['subject_id'])} · ${refs.grade(document['grade_id'])} · '
                      '${document['page_count']} page(s)',
                    ),
                    if (document['status'] == 'processing') ...[
                      const SizedBox(height: 6),
                      LinearProgressIndicator(
                        value: (document['page_count'] as int) > 0
                            ? (document['pages_done'] as int) / (document['page_count'] as int)
                            : null,
                      ),
                      Text('Page ${document['pages_done']} / ${document['page_count']}'),
                    ],
                    if (document['extraction_error'] != null)
                      Text(
                        '${document['extraction_error']}',
                        style: const TextStyle(color: Brand.bad),
                      ),
                  ],
                ),
                trailing: StatusPill(
                  documentStatusLabels[document['status']] ?? '${document['status']}',
                  color: document['status'] == 'extracted'
                      ? Brand.mint
                      : _statusColor(document['status'] as String?),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _exercisesTab() {
    final filters = <String?, String>{null: 'Tous', ...contentStatusLabels};
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final entry in filters.entries)
              ChoiceChip(
                label: Text(entry.value),
                selected: _exerciseStatus == entry.key,
                onSelected: (_) {
                  _exerciseStatus = entry.key;
                  _reload();
                },
              ),
          ],
        ),
        const SizedBox(height: 16),
        if (_exercises.isEmpty)
          const ChunkCard(child: Text('Aucun exercice dans cette catégorie.')),
        for (final exercise in _exercises) _exerciseTile(exercise),
      ],
    );
  }

  Widget _exerciseTile(Map<String, dynamic> exercise) {
    final refs = _refs!;
    final document = _documents.where((d) => d['id'] == exercise['document_id']);
    return Card(
      child: ListTile(
        onTap: () => _openExercise(exercise['id'] as int),
        title: Text('${exercise['title']}'),
        subtitle: Text(
          '${document.isEmpty ? 'Document ${exercise['document_id']}' : document.first['title']} · '
          'p. ${exercise['page_start']}–${exercise['page_end']} · '
          '${refs.subject(exercise['subject_id'])} · ${refs.chapter(exercise['chapter_id'])}',
        ),
        trailing: Wrap(
          spacing: 6,
          children: [
            if (exercise['is_published'] == true) const StatusPill('Publié', color: Brand.mint),
            StatusPill(
              contentStatusLabels[exercise['status']] ?? '${exercise['status']}',
              color: _statusColor(exercise['status'] as String?),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Fiche document : classement, pages (original ↔ texte extrait), découpage
// ---------------------------------------------------------------------------

class ClassificationFields extends StatelessWidget {
  const ClassificationFields({
    super.key,
    required this.refs,
    required this.gradeId,
    required this.subjectId,
    required this.chapterId,
    required this.onChanged,
  });
  final Refs refs;
  final int? gradeId, subjectId, chapterId;
  final void Function(int? grade, int? subject, int? chapter) onChanged;

  @override
  Widget build(BuildContext context) {
    final chapters = refs.chapters
        .where(
          (c) =>
              (gradeId == null || c['grade_id'] == gradeId) &&
              (subjectId == null || c['subject_id'] == subjectId),
        )
        .toList();
    DropdownMenuItem<int?> none() =>
        const DropdownMenuItem<int?>(value: null, child: Text('— non classé —'));
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        SizedBox(
          width: 200,
          child: DropdownButtonFormField<int?>(
            initialValue: gradeId,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Niveau'),
            items: [
              none(),
              for (final g in refs.grades)
                DropdownMenuItem(value: g['id'] as int, child: Text('${g['name']}')),
            ],
            onChanged: (value) => onChanged(value, subjectId, null),
          ),
        ),
        SizedBox(
          width: 220,
          child: DropdownButtonFormField<int?>(
            initialValue: subjectId,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Matière'),
            items: [
              none(),
              for (final s in refs.subjects)
                DropdownMenuItem(value: s['id'] as int, child: Text('${s['name']}')),
            ],
            onChanged: (value) => onChanged(gradeId, value, null),
          ),
        ),
        SizedBox(
          width: 320,
          child: DropdownButtonFormField<int?>(
            key: ValueKey('chap-$gradeId-$subjectId'),
            initialValue: chapters.any((c) => c['id'] == chapterId) ? chapterId : null,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Chapitre'),
            items: [
              none(),
              for (final c in chapters)
                DropdownMenuItem(value: c['id'] as int, child: Text('${c['title']}')),
            ],
            onChanged: (value) {
              final chapter = refs.chapters.where((c) => c['id'] == value);
              if (chapter.isEmpty) return onChanged(gradeId, subjectId, null);
              onChanged(
                chapter.first['grade_id'] as int?,
                chapter.first['subject_id'] as int?,
                value,
              );
            },
          ),
        ),
      ],
    );
  }
}

class DocumentDetailPage extends StatefulWidget {
  const DocumentDetailPage({
    super.key,
    required this.api,
    required this.refs,
    required this.documentId,
    required this.documents,
  });
  final ApiClient api;
  final Refs refs;
  final int documentId;
  final List<Map<String, dynamic>> documents;

  @override
  State<DocumentDetailPage> createState() => _DocumentDetailPageState();
}

class _DocumentDetailPageState extends State<DocumentDetailPage> {
  Map<String, dynamic>? _document;
  List<Map<String, dynamic>> _pages = [];
  List<Map<String, dynamic>> _exercises = [];
  final _title = TextEditingController();
  String _kind = 'autre';
  int? _grade, _subject, _chapter;
  int _page = 1;
  bool _busy = false;
  String? _suggestion;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _poll?.cancel();
    _title.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action, [String? success]) async {
    setState(() => _busy = true);
    try {
      await action();
      if (mounted && success != null) showMessage(context, success);
    } on ApiException catch (exception) {
      if (mounted) showMessage(context, exception.message, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _load() => _run(() async {
    final document = await widget.api.getDocument(widget.documentId);
    _document = document;
    _title.text = '${document['title']}';
    _kind = '${document['kind']}';
    _grade = document['grade_id'] as int?;
    _subject = document['subject_id'] as int?;
    _chapter = document['chapter_id'] as int?;
    _pages = await widget.api.listPages(widget.documentId);
    _exercises = await widget.api.listExercises(documentId: widget.documentId);
    _poll?.cancel();
    if (document['status'] == 'processing') {
      _poll = Timer(const Duration(seconds: 2), () {
        if (mounted) _load();
      });
    }
  });

  Future<void> _save() => _run(() async {
    _document = await widget.api.updateDocument(widget.documentId, {
      'title': _title.text.trim(),
      'kind': _kind,
      'grade_id': _grade,
      'subject_id': _subject,
      'chapter_id': _chapter,
    });
  }, 'Classement enregistré.');

  Future<void> _identify() => _run(() async {
    final guess = await widget.api.identifyDocument(widget.documentId);
    int? find(List<Map<String, dynamic>> items, Object? label) {
      if (label == null) return null;
      String norm(Object? v) => '$v'.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
      for (final item in items) {
        if (norm(item['name']) == norm(label) || norm(item['code']) == norm(label)) {
          return item['id'] as int;
        }
      }
      return null;
    }

    setState(() {
      if (guess['title'] != null) _title.text = '${guess['title']}';
      if (guess['kind'] != null) _kind = '${guess['kind']}';
      _grade = find(widget.refs.grades, guess['grade']) ?? _grade;
      _subject = find(widget.refs.subjects, guess['subject']) ?? _subject;
      _suggestion =
          'Proposition lue dans le document : ${guess['title'] ?? '—'} · '
          '${guess['grade'] ?? 'niveau ?'} · ${guess['subject'] ?? 'matière ?'} · '
          '${documentKinds[guess['kind']] ?? 'type ?'}. Vérifiez puis enregistrez.';
    });
  });

  Future<void> _segment() async {
    bool replace = _exercises.isNotEmpty;
    int? correction;
    final others = widget.documents
        .where((d) => d['id'] != widget.documentId && d['status'] == 'extracted')
        .toList();
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocal) => AlertDialog(
          title: const Text('Découper en exercices'),
          content: SizedBox(
            width: 460,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Les titres « Exercice N », « Problème », « Situation d’évaluation »… '
                  'délimitent les exercices. Les sections « Corrigé » sont associées par numéro. '
                  'Les figures sont capturées automatiquement.',
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<int?>(
                  initialValue: correction,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Corrigé dans un autre document (facultatif)'),
                  items: [
                    const DropdownMenuItem<int?>(value: null, child: Text('— aucun —')),
                    for (final d in others)
                      DropdownMenuItem(value: d['id'] as int, child: Text('${d['title']}')),
                  ],
                  onChanged: (value) => setLocal(() => correction = value),
                ),
                if (_exercises.isNotEmpty)
                  CheckboxListTile(
                    value: replace,
                    onChanged: (value) => setLocal(() => replace = value ?? false),
                    title: const Text('Refaire le découpage (les exercices validés sont conservés)'),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Annuler')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Découper')),
          ],
        ),
      ),
    );
    if (ok != true) return;
    await _run(() async {
      final report = await widget.api.segmentDocument(
        widget.documentId,
        correctionDocumentId: correction,
        replace: replace,
      );
      _exercises = await widget.api.listExercises(documentId: widget.documentId);
      if (mounted) {
        showMessage(
          context,
          '${report['exercises_created']} exercice(s) créé(s), '
          '${report['corrections_found']} corrigé(s) associé(s).',
        );
      }
    });
  }

  void _openExercise(int id) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ExerciseEditorPage(api: widget.api, refs: widget.refs, exerciseId: id),
      ),
    );
    _load();
  }

  Future<void> _createManual() async {
    final page = _pages.where((p) => p['page_number'] == _page);
    final text = page.isEmpty ? '' : '${page.first['text']}';
    await _run(() async {
      final created = await widget.api.createExerciseManually(
        documentId: widget.documentId,
        page: _page,
        title: 'Exercice — page $_page',
        statement: text.isEmpty ? '(à recopier depuis la page $_page)' : text,
      );
      _openExercise(created['id'] as int);
    });
  }

  @override
  Widget build(BuildContext context) {
    final document = _document;
    return Scaffold(
      appBar: AppBar(title: Text(document == null ? 'Document' : '${document['title']}')),
      body: document == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (_busy) const LinearProgressIndicator(minHeight: 3),
                _header(document),
                const SizedBox(height: 16),
                _classification(),
                const SizedBox(height: 16),
                _pagesViewer(document),
                const SizedBox(height: 16),
                _exerciseList(),
              ],
            ),
    );
  }

  Widget _header(Map<String, dynamic> document) {
    final status = '${document['status']}';
    return ChunkCard(
      child: Wrap(
        spacing: 12,
        runSpacing: 12,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          StatusPill(documentStatusLabels[status] ?? status,
              color: status == 'extracted' ? Brand.mint : _statusColor(status)),
          Text('${document['original_filename']} · ${document['page_count']} page(s)'),
          if (status == 'processing')
            SizedBox(
              width: 200,
              child: LinearProgressIndicator(
                value: (document['page_count'] as int) > 0
                    ? (document['pages_done'] as int) / (document['page_count'] as int)
                    : null,
              ),
            ),
          if (document['extraction_error'] != null)
            Text('${document['extraction_error']}', style: const TextStyle(color: Brand.bad)),
          FilledButton.tonalIcon(
            onPressed: _busy || status == 'processing'
                ? null
                : () => _run(() async {
                    await widget.api.extractDocument(widget.documentId);
                    await _load();
                  }, 'Extraction lancée.'),
            icon: const Icon(Icons.text_snippet_rounded),
            label: Text(status == 'imported' ? 'Extraire le texte' : 'Ré-extraire'),
          ),
          FilledButton.icon(
            onPressed: _busy || status != 'extracted' ? null : _segment,
            icon: const Icon(Icons.content_cut_rounded),
            label: const Text('Découper en exercices'),
          ),
          OutlinedButton.icon(
            onPressed: _busy || status == 'archived'
                ? null
                : () => _run(() async {
                    await widget.api.archiveDocument(widget.documentId);
                    await _load();
                  }, 'Document archivé (exercices dépubliés).'),
            icon: const Icon(Icons.archive_rounded),
            label: const Text('Archiver'),
          ),
        ],
      ),
    );
  }

  Widget _classification() => ChunkCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Classement', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            SizedBox(
              width: 420,
              child: TextField(controller: _title, decoration: const InputDecoration(labelText: 'Titre')),
            ),
            SizedBox(
              width: 200,
              child: DropdownButtonFormField<String>(
                key: ValueKey('kind-$_kind'),
                initialValue: _kind,
                decoration: const InputDecoration(labelText: 'Type'),
                items: [
                  for (final entry in documentKinds.entries)
                    DropdownMenuItem(value: entry.key, child: Text(entry.value)),
                ],
                onChanged: (value) => setState(() => _kind = value ?? 'autre'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        ClassificationFields(
          key: ValueKey('cls-$_grade-$_subject-$_chapter'),
          refs: widget.refs,
          gradeId: _grade,
          subjectId: _subject,
          chapterId: _chapter,
          onChanged: (g, s, c) => setState(() {
            _grade = g;
            _subject = s;
            _chapter = c;
          }),
        ),
        if (_suggestion != null) ...[
          const SizedBox(height: 8),
          Text(_suggestion!, style: const TextStyle(fontStyle: FontStyle.italic)),
        ],
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          children: [
            FilledButton(onPressed: _busy ? null : _save, child: const Text('Enregistrer')),
            OutlinedButton.icon(
              onPressed: _busy || _pages.isEmpty ? null : _identify,
              icon: const Icon(Icons.auto_fix_high_rounded),
              label: const Text('Proposer d’après le contenu'),
            ),
          ],
        ),
      ],
    ),
  );

  Widget _pagesViewer(Map<String, dynamic> document) {
    final total = document['page_count'] as int;
    if (total == 0) return const SizedBox.shrink();
    final page = _pages.where((p) => p['page_number'] == _page);
    final previewable = document['mime_type'] == 'application/pdf' ||
        '${document['mime_type']}'.startsWith('image/');
    final image = previewable
        ? AuthImage(
            api: widget.api,
            path: '/api/v1/library/documents/${widget.documentId}/pages/$_page/image',
            height: 640,
          )
        : const Text('Aperçu de l’original disponible pour les PDF et les images.');
    final text = page.isEmpty
        ? const Text('Page non encore extraite.')
        : Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              StatusPill(switch (page.first['method']) {
                'ocr' => 'Texte reconnu par OCR — à vérifier',
                'empty' => 'Aucun texte détecté',
                _ => 'Texte natif du document',
              }),
              const SizedBox(height: 8),
              SelectableText('${page.first['text']}'),
            ],
          );
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('Original ↔ texte extrait',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
              ),
              IconButton(
                onPressed: _page > 1 ? () => setState(() => _page--) : null,
                icon: const Icon(Icons.chevron_left_rounded),
              ),
              Text('Page $_page / $total'),
              IconButton(
                onPressed: _page < total ? () => setState(() => _page++) : null,
                icon: const Icon(Icons.chevron_right_rounded),
              ),
              TextButton.icon(
                onPressed: _busy || page.isEmpty ? null : _createManual,
                icon: const Icon(Icons.add_rounded),
                label: const Text('Créer un exercice depuis cette page'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, constraints) => constraints.maxWidth > 900
                ? Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: image),
                      const SizedBox(width: 16),
                      Expanded(child: text),
                    ],
                  )
                : Column(children: [image, const SizedBox(height: 16), text]),
          ),
        ],
      ),
    );
  }

  Widget _exerciseList() => ChunkCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Exercices extraits (${_exercises.length})',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        if (_exercises.isEmpty)
          const Text('Aucun exercice : lancez le découpage ou créez-en un depuis une page.'),
        for (final exercise in _exercises)
          ListTile(
            onTap: () => _openExercise(exercise['id'] as int),
            title: Text('${exercise['title']}'),
            subtitle: Text(
              'p. ${exercise['page_start']}–${exercise['page_end']} · '
              '${(exercise['assets'] as List).length} capture(s) · '
              '${exercise['correction'] == null ? 'sans corrigé' : 'corrigé associé'}',
            ),
            trailing: Wrap(
              spacing: 6,
              children: [
                if (exercise['is_published'] == true) const StatusPill('Publié', color: Brand.mint),
                StatusPill(
                  contentStatusLabels[exercise['status']] ?? '${exercise['status']}',
                  color: _statusColor(exercise['status'] as String?),
                ),
              ],
            ),
          ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------
// Éditeur d'exercice : original intact, version retravaillée, corrigé, validation
// ---------------------------------------------------------------------------

class ExerciseEditorPage extends StatefulWidget {
  const ExerciseEditorPage({super.key, required this.api, required this.refs, required this.exerciseId});
  final ApiClient api;
  final Refs refs;
  final int exerciseId;

  @override
  State<ExerciseEditorPage> createState() => _ExerciseEditorPageState();
}

class _OptionRow {
  _OptionRow(String label, String text, this.correct)
    : label = TextEditingController(text: label),
      text = TextEditingController(text: text);
  final TextEditingController label, text;
  bool correct;
}

class _ExerciseEditorPageState extends State<ExerciseEditorPage> {
  Map<String, dynamic>? _exercise;
  List<Map<String, dynamic>> _history = [];
  final _title = TextEditingController();
  final _statement = TextEditingController();
  final _expected = TextEditingController();
  final _tolerance = TextEditingController();
  final _points = TextEditingController();
  final _final = TextEditingController();
  final _steps = TextEditingController();
  final _rubric = TextEditingController();
  final _sourcePage = TextEditingController();
  final _capturePage = TextEditingController();
  String _type = 'libre';
  int _difficulty = 2;
  int? _grade, _subject, _chapter;
  List<_OptionRow> _options = [];
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _run(Future<void> Function() action, [String? success]) async {
    setState(() => _busy = true);
    try {
      await action();
      if (mounted && success != null) showMessage(context, success);
    } on ApiException catch (exception) {
      if (mounted) showMessage(context, exception.message, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _fill(Map<String, dynamic> e) {
    _exercise = e;
    _title.text = '${e['title']}';
    _statement.text = '${e['statement']}';
    _expected.text = '${e['expected_answer'] ?? ''}';
    _tolerance.text = e['numeric_tolerance'] == null ? '' : '${e['numeric_tolerance']}';
    _points.text = '${e['points']}';
    _type = '${e['exercise_type']}';
    _difficulty = e['difficulty'] as int;
    _grade = e['grade_id'] as int?;
    _subject = e['subject_id'] as int?;
    _chapter = e['chapter_id'] as int?;
    _options = [
      for (final o in (e['options'] as List).cast<Map>())
        _OptionRow('${o['label']}', '${o['text']}', o['is_correct'] == true),
    ];
    final correction = e['correction'] as Map?;
    _final.text = '${correction?['final_answer'] ?? ''}';
    _steps.text = '${correction?['steps'] ?? ''}';
    _rubric.text = '${correction?['rubric'] ?? ''}';
    _sourcePage.text = '${correction?['source_page'] ?? e['page_start']}';
    _capturePage.text = '${e['page_start']}';
  }

  Future<void> _load() => _run(() async {
    _fill(await widget.api.getExercise(widget.exerciseId));
    _history = await widget.api.auditLog(entityType: 'exercise', entityId: widget.exerciseId);
  });

  Future<void> _save() => _run(() async {
    final withOptions = _type == 'qcm' || _type == 'vrai_faux';
    _fill(await widget.api.updateExercise(widget.exerciseId, {
      'title': _title.text.trim(),
      'statement': _statement.text,
      'exercise_type': _type,
      'difficulty': _difficulty,
      'expected_answer': _expected.text.trim().isEmpty ? null : _expected.text.trim(),
      'numeric_tolerance': double.tryParse(_tolerance.text.replaceAll(',', '.')),
      'points': int.tryParse(_points.text) ?? 1,
      'grade_id': _grade,
      'subject_id': _subject,
      'chapter_id': _chapter,
      if (withOptions)
        'options': [
          for (final o in _options)
            if (o.text.text.trim().isNotEmpty)
              {'label': o.label.text.trim(), 'text': o.text.text.trim(), 'is_correct': o.correct},
        ],
    }));
    _history = await widget.api.auditLog(entityType: 'exercise', entityId: widget.exerciseId);
  }, 'Exercice enregistré (statut : transformé, à revalider).');

  Future<void> _action(String action, String success) => _run(() async {
    _fill(await widget.api.exerciseAction(widget.exerciseId, action));
    _history = await widget.api.auditLog(entityType: 'exercise', entityId: widget.exerciseId);
  }, success);

  Future<void> _saveCorrection() => _run(() async {
    await widget.api.saveCorrection(widget.exerciseId, {
      'final_answer': _final.text.trim().isEmpty ? null : _final.text.trim(),
      'steps': _steps.text.trim().isEmpty ? null : _steps.text.trim(),
      'rubric': _rubric.text.trim().isEmpty ? null : _rubric.text.trim(),
      'source_document_id':
          (_exercise!['correction'] as Map?)?['source_document_id'] ?? _exercise!['document_id'],
      'source_page': int.tryParse(_sourcePage.text),
    });
    _fill(await widget.api.getExercise(widget.exerciseId));
  }, 'Corrigé enregistré.');

  @override
  Widget build(BuildContext context) {
    final e = _exercise;
    return Scaffold(
      appBar: AppBar(title: Text(e == null ? 'Exercice' : '${e['title']}')),
      body: e == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (_busy) const LinearProgressIndicator(minHeight: 3),
                _statusBar(e),
                const SizedBox(height: 16),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final left = _original(e);
                    final right = _editor();
                    return constraints.maxWidth > 1000
                        ? Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(child: left),
                              const SizedBox(width: 16),
                              Expanded(child: right),
                            ],
                          )
                        : Column(children: [left, const SizedBox(height: 16), right]);
                  },
                ),
                const SizedBox(height: 16),
                _correction(e),
                const SizedBox(height: 16),
                _historyCard(),
              ],
            ),
    );
  }

  Widget _statusBar(Map<String, dynamic> e) {
    final status = '${e['status']}';
    final published = e['is_published'] == true;
    final archived = e['is_archived'] == true;
    return ChunkCard(
      child: Wrap(
        spacing: 10,
        runSpacing: 10,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          StatusPill(contentStatusLabels[status] ?? status, color: _statusColor(status)),
          if (published) const StatusPill('Publié', color: Brand.mint),
          if (archived) const StatusPill('Archivé'),
          Text('Source : document ${e['document_id']}, p. ${e['page_start']}–${e['page_end']}'
              '${e['source_number'] == null ? '' : ', n° ${e['source_number']}'}'),
          if (status != 'validated' && status != 'pending_validation')
            OutlinedButton(
              onPressed: _busy ? null : () => _action('submit', 'Soumis à validation.'),
              child: const Text('Soumettre'),
            ),
          if (status != 'validated')
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: Brand.good),
              onPressed: _busy ? null : () => _action('validate', 'Exercice validé.'),
              child: const Text('Valider'),
            ),
          if (status != 'rejected' && status != 'validated')
            OutlinedButton(
              onPressed: _busy ? null : () => _action('reject', 'Exercice rejeté.'),
              child: const Text('Rejeter'),
            ),
          if (status == 'validated' && !published && !archived)
            FilledButton(
              onPressed: _busy ? null : () => _action('publish', 'Exercice publié pour les élèves.'),
              child: const Text('Publier'),
            ),
          if (published)
            OutlinedButton(
              onPressed: _busy ? null : () => _action('unpublish', 'Exercice dépublié.'),
              child: const Text('Dépublier'),
            ),
          OutlinedButton(
            onPressed: _busy
                ? null
                : () => _action(archived ? 'restore' : 'archive', archived ? 'Restauré.' : 'Archivé.'),
            child: Text(archived ? 'Restaurer' : 'Archiver'),
          ),
          if (status != 'validated' && e['published_at'] == null)
            TextButton(
              style: TextButton.styleFrom(foregroundColor: Brand.bad),
              onPressed: _busy
                  ? null
                  : () => _run(() async {
                      await widget.api.deleteExercise(widget.exerciseId);
                      if (mounted) Navigator.of(context).pop();
                    }, 'Exercice supprimé (mauvais découpage).'),
              child: const Text('Supprimer'),
            ),
        ],
      ),
    );
  }

  Widget _original(Map<String, dynamic> e) {
    final assets = (e['assets'] as List).cast<Map>();
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Texte original (jamais modifié)',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          SelectableText('${e['original_text']}'),
          const SizedBox(height: 16),
          Text('Captures (${assets.length})', style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          for (final asset in assets)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text('${asset['caption'] ?? asset['kind']}')),
                      IconButton(
                        tooltip: 'Retirer cette capture',
                        onPressed: _busy
                            ? null
                            : () => _run(() async {
                                await widget.api.deleteAsset(asset['id'] as int);
                                _fill(await widget.api.getExercise(widget.exerciseId));
                              }),
                        icon: const Icon(Icons.delete_outline_rounded),
                      ),
                    ],
                  ),
                  AuthImage(
                    api: widget.api,
                    path: '/api/v1/library/assets/${asset['id']}',
                    height: asset['kind'] == 'page' ? 520 : 260,
                  ),
                ],
              ),
            ),
          Row(
            children: [
              SizedBox(
                width: 90,
                child: TextField(
                  controller: _capturePage,
                  decoration: const InputDecoration(labelText: 'Page'),
                ),
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                onPressed: _busy
                    ? null
                    : () => _run(() async {
                        final page = int.tryParse(_capturePage.text);
                        if (page == null) return;
                        _fill(await widget.api.addPageCapture(widget.exerciseId, page));
                      }, 'Capture de page ajoutée.'),
                icon: const Icon(Icons.add_photo_alternate_rounded),
                label: const Text('Ajouter la capture de la page'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _editor() {
    final withOptions = _type == 'qcm' || _type == 'vrai_faux';
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Version proposée aux élèves',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 12),
          TextField(controller: _title, decoration: const InputDecoration(labelText: 'Titre')),
          const SizedBox(height: 12),
          TextField(
            controller: _statement,
            minLines: 6,
            maxLines: 18,
            decoration: const InputDecoration(
              labelText: 'Énoncé',
              helperText: 'Formules : \$x^2\$, \\frac{a}{b} ; tableaux : | a | b |',
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              SizedBox(
                width: 220,
                child: DropdownButtonFormField<String>(
                  initialValue: _type,
                  decoration: const InputDecoration(labelText: 'Type'),
                  items: [
                    for (final entry in exerciseTypes.entries)
                      DropdownMenuItem(value: entry.key, child: Text(entry.value)),
                  ],
                  onChanged: (value) => setState(() {
                    _type = value ?? 'libre';
                    if (_type == 'vrai_faux' && _options.isEmpty) {
                      _options = [_OptionRow('V', 'Vrai', false), _OptionRow('F', 'Faux', false)];
                    }
                  }),
                ),
              ),
              SegmentedButton<int>(
                segments: const [
                  ButtonSegment(value: 1, label: Text('Facile')),
                  ButtonSegment(value: 2, label: Text('Moyen')),
                  ButtonSegment(value: 3, label: Text('Difficile')),
                ],
                selected: {_difficulty},
                onSelectionChanged: (value) => setState(() => _difficulty = value.first),
              ),
              SizedBox(
                width: 100,
                child: TextField(controller: _points, decoration: const InputDecoration(labelText: 'Points')),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (!withOptions)
            TextField(
              controller: _expected,
              decoration: const InputDecoration(
                labelText: 'Réponse attendue (facultatif, sert à la correction automatique)',
              ),
            ),
          if (_type == 'numerique') ...[
            const SizedBox(height: 12),
            SizedBox(
              width: 220,
              child: TextField(
                controller: _tolerance,
                decoration: const InputDecoration(labelText: 'Tolérance (ex. 0,01)'),
              ),
            ),
          ],
          if (withOptions) ...[
            const Text('Propositions (cocher la ou les bonnes réponses)'),
            for (final option in _options)
              Row(
                children: [
                  Checkbox(
                    value: option.correct,
                    onChanged: (value) => setState(() => option.correct = value ?? false),
                  ),
                  SizedBox(width: 60, child: TextField(controller: option.label)),
                  const SizedBox(width: 8),
                  Expanded(child: TextField(controller: option.text)),
                  IconButton(
                    onPressed: () => setState(() => _options.remove(option)),
                    icon: const Icon(Icons.close_rounded),
                  ),
                ],
              ),
            TextButton.icon(
              onPressed: () => setState(
                () => _options.add(_OptionRow(String.fromCharCode(65 + _options.length), '', false)),
              ),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Ajouter une proposition'),
            ),
          ],
          const SizedBox(height: 12),
          ClassificationFields(
            key: ValueKey('ex-$_grade-$_subject-$_chapter'),
            refs: widget.refs,
            gradeId: _grade,
            subjectId: _subject,
            chapterId: _chapter,
            onChanged: (g, s, c) => setState(() {
              _grade = g;
              _subject = s;
              _chapter = c;
            }),
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _busy ? null : _save, child: const Text('Enregistrer les modifications')),
        ],
      ),
    );
  }

  Widget _correction(Map<String, dynamic> e) {
    final correction = e['correction'] as Map?;
    return ChunkCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('Corrigé', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
              ),
              if (correction != null)
                StatusPill(
                  contentStatusLabels[correction['status']] ?? '${correction['status']}',
                  color: _statusColor(correction['status'] as String?),
                ),
            ],
          ),
          if (correction == null)
            const Text('Aucun corrigé trouvé dans les documents : à saisir depuis un corrigé fourni.'),
          if (correction != null && '${correction['original_text']}'.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Texte du corrigé d’origine (document ${correction['source_document_id']}, '
                'p. ${correction['source_page'] ?? '?'})'),
            SelectableText('${correction['original_text']}'),
          ],
          const SizedBox(height: 12),
          TextField(controller: _final, decoration: const InputDecoration(labelText: 'Réponse finale')),
          const SizedBox(height: 12),
          TextField(
            controller: _steps,
            minLines: 3,
            maxLines: 12,
            decoration: const InputDecoration(labelText: 'Étapes de résolution'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _rubric,
            minLines: 2,
            maxLines: 6,
            decoration: const InputDecoration(labelText: 'Barème / critères'),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: 200,
            child: TextField(
              controller: _sourcePage,
              decoration: const InputDecoration(labelText: 'Page du corrigé source'),
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            children: [
              FilledButton(
                onPressed: _busy ? null : _saveCorrection,
                child: const Text('Enregistrer le corrigé'),
              ),
              if (correction != null && correction['status'] != 'validated')
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: Brand.good),
                  onPressed: _busy
                      ? null
                      : () => _run(() async {
                          await widget.api.decideCorrection(widget.exerciseId, 'validate');
                          _fill(await widget.api.getExercise(widget.exerciseId));
                        }, 'Corrigé validé.'),
                  child: const Text('Valider le corrigé'),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _historyCard() => ChunkCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Historique', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        if (_history.isEmpty) const Text('Aucune action enregistrée.'),
        for (final entry in _history)
          Text('${'${entry['created_at']}'.replaceFirst('T', ' ').split('.').first} · '
              '${entry['action']}${entry['actor_id'] == null ? ' (import automatique)' : ''}'),
      ],
    ),
  );
}
