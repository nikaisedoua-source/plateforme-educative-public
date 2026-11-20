import 'package:material_ui/material_ui.dart';

import 'api_client.dart';
import 'parcours_picker.dart' show trackKindLabels;

class AdminDashboard extends StatefulWidget {
  const AdminDashboard({super.key, required this.api, required this.onSignOut});

  final ApiClient api;
  final VoidCallback onSignOut;

  @override
  State<AdminDashboard> createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  static const _labels = [
    'Cycles',
    'Niveaux',
    'Séries et spécialités',
    'Classes',
    'Matières',
    'Chapitres',
    'Inscriptions',
  ];
  static const _resources = [
    'cycles',
    'grades',
    'tracks',
    'classes',
    'subjects',
    'chapters',
    'enrollments',
  ];
  static const _icons = [
    Icons.account_tree_outlined,
    Icons.school_outlined,
    Icons.alt_route_rounded,
    Icons.groups_outlined,
    Icons.menu_book_outlined,
    Icons.topic_outlined,
    Icons.how_to_reg_outlined,
  ];

  String get _resource => _resources[_selected];

  final _formKeys = List.generate(
    _resources.length,
    (_) => GlobalKey<FormState>(),
  );
  final _trackCode = TextEditingController();
  final _trackName = TextEditingController();
  final _trackOrder = TextEditingController(text: '0');
  final _cycleCode = TextEditingController();
  final _cycleName = TextEditingController();
  final _gradeCode = TextEditingController();
  final _gradeName = TextEditingController();
  final _gradeOrder = TextEditingController(text: '0');
  final _className = TextEditingController();
  final _academicYear = TextEditingController();
  final _subjectCode = TextEditingController();
  final _subjectName = TextEditingController();
  final _chapterTitle = TextEditingController();
  final _chapterOrder = TextEditingController(text: '0');

  List<Map<String, dynamic>> _cycles = [];
  List<Map<String, dynamic>> _grades = [];
  List<Map<String, dynamic>> _classes = [];
  List<Map<String, dynamic>> _subjects = [];
  List<Map<String, dynamic>> _chapters = [];
  List<Map<String, dynamic>> _tracks = [];
  List<Map<String, dynamic>> _enrollments = [];
  String _enrollmentFilter = 'pending';
  int? _trackGradeId;
  String? _trackKind;
  int? _cycleId;
  int? _classGradeId;
  int? _chapterGradeId;
  int? _chapterSubjectId;
  int _selected = 0;
  bool _loading = true;
  bool _saving = false;
  String? _loadError;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    _trackCode.dispose();
    _trackName.dispose();
    _trackOrder.dispose();
    _cycleCode.dispose();
    _cycleName.dispose();
    _gradeCode.dispose();
    _gradeName.dispose();
    _gradeOrder.dispose();
    _className.dispose();
    _academicYear.dispose();
    _subjectCode.dispose();
    _subjectName.dispose();
    _chapterTitle.dispose();
    _chapterOrder.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final results = await Future.wait([
        widget.api.listAdmin('cycles'),
        widget.api.listAdmin('grades'),
        widget.api.listAdmin('classes'),
        widget.api.listAdmin('subjects'),
        widget.api.listAdmin('chapters'),
        widget.api.listAdmin('tracks'),
        widget.api.listEnrollments(
          status: _enrollmentFilter == 'all' ? null : _enrollmentFilter,
        ),
      ]);
      if (!mounted) return;
      setState(() {
        _cycles = results[0];
        _grades = results[1];
        _classes = results[2];
        _subjects = results[3];
        _chapters = results[4];
        _tracks = results[5];
        _enrollments = results[6];
        if (!_grades.any((item) => item['id'] == _trackGradeId)) {
          _trackGradeId = null;
        }
        if (!_cycles.any((item) => item['id'] == _cycleId)) _cycleId = null;
        if (!_grades.any((item) => item['id'] == _classGradeId)) {
          _classGradeId = null;
        }
        if (!_grades.any((item) => item['id'] == _chapterGradeId)) {
          _chapterGradeId = null;
        }
        if (!_subjects.any((item) => item['id'] == _chapterSubjectId)) {
          _chapterSubjectId = null;
        }
        _loading = false;
      });
    } on ApiException catch (exception) {
      if (!mounted) return;
      if (exception.statusCode == 401 || exception.statusCode == 403) {
        widget.api.logout();
        widget.onSignOut();
        return;
      }
      setState(() {
        _loadError = exception.message;
        _loading = false;
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          _loadError = 'Impossible de charger les référentiels.';
          _loading = false;
        });
      }
    }
  }

  Future<void> _createSelected() async {
    if (!(_formKeys[_selected].currentState?.validate() ?? false)) return;
    late final Map<String, Object?> values;
    switch (_resource) {
      case 'cycles':
        values = {
          'code': _cycleCode.text.trim(),
          'name': _cycleName.text.trim(),
        };
        break;
      case 'grades':
        values = {
          'code': _gradeCode.text.trim(),
          'name': _gradeName.text.trim(),
          'cycle_id': _cycleId,
          'sort_order': int.parse(_gradeOrder.text.trim()),
        };
        break;
      case 'tracks':
        values = {
          'grade_id': _trackGradeId,
          'code': _trackCode.text.trim(),
          'name': _trackName.text.trim(),
          'kind': _trackKind,
          'sort_order': int.parse(_trackOrder.text.trim()),
        };
        break;
      case 'classes':
        values = {
          'grade_id': _classGradeId,
          'name': _className.text.trim(),
          'academic_year': _academicYear.text.trim(),
        };
        break;
      case 'subjects':
        values = {
          'code': _subjectCode.text.trim(),
          'name': _subjectName.text.trim(),
        };
        break;
      case 'chapters':
        values = {
          'grade_id': _chapterGradeId,
          'subject_id': _chapterSubjectId,
          'title': _chapterTitle.text.trim(),
          'sort_order': int.parse(_chapterOrder.text.trim()),
        };
        break;
      default:
        return;
    }

    setState(() => _saving = true);
    try {
      await widget.api.createAdmin(_resource, values);
      _clearCurrentFields();
      await _reload();
      if (mounted) _showMessage('${_labels[_selected]} : élément créé.');
    } on ApiException catch (exception) {
      if (!mounted) return;
      if (exception.statusCode == 401 || exception.statusCode == 403) {
        widget.api.logout();
        widget.onSignOut();
        return;
      }
      _showMessage(exception.message, isError: true);
    } catch (_) {
      if (mounted) {
        _showMessage(
          'La création a échoué. Vérifiez les champs.',
          isError: true,
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _clearCurrentFields() {
    switch (_resource) {
      case 'cycles':
        _cycleCode.clear();
        _cycleName.clear();
        break;
      case 'grades':
        _gradeCode.clear();
        _gradeName.clear();
        _gradeOrder.text = '0';
        break;
      case 'tracks':
        _trackCode.clear();
        _trackName.clear();
        _trackOrder.text = '0';
        break;
      case 'classes':
        _className.clear();
        _academicYear.clear();
        break;
      case 'subjects':
        _subjectCode.clear();
        _subjectName.clear();
        break;
      case 'chapters':
        _chapterTitle.clear();
        _chapterOrder.text = '0';
        break;
    }
    _formKeys[_selected].currentState?.reset();
  }

  void _showMessage(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? const Color(0xFFB42318) : null,
      ),
    );
  }

  String? _required(String? value, String label, {int min = 1, int max = 160}) {
    final text = value?.trim() ?? '';
    if (text.length < min) return '$label : saisie obligatoire.';
    if (text.length > max) return '$label : $max caractères maximum.';
    return null;
  }

  String? _codeValidator(String? value) {
    final text = value?.trim() ?? '';
    final required = _required(text, 'Code', min: 2, max: 40);
    if (required != null) return required;
    if (!RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(text)) {
      return 'Lettres non accentuées, chiffres, tirets ou underscores.';
    }
    return null;
  }

  String? _orderValidator(String? value) {
    final parsed = int.tryParse(value?.trim() ?? '');
    if (parsed == null || parsed < 0) {
      return 'Saisissez un entier positif ou nul.';
    }
    return null;
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required String? Function(String?) validator,
    String? hint,
    TextInputType? keyboardType,
    Key? key,
  }) {
    return SizedBox(
      width: 290,
      child: TextFormField(
        key: key,
        controller: controller,
        keyboardType: keyboardType,
        validator: validator,
        decoration: InputDecoration(labelText: label, hintText: hint),
      ),
    );
  }

  Widget _selector({
    required String label,
    required List<Map<String, dynamic>> options,
    required int? selected,
    required ValueChanged<int?> onChanged,
    required String Function(Map<String, dynamic>) optionLabel,
  }) {
    return SizedBox(
      width: 290,
      child: DropdownButtonFormField<int>(
        initialValue: options.any((item) => item['id'] == selected)
            ? selected
            : null,
        decoration: InputDecoration(labelText: label),
        hint: Text(
          options.isEmpty ? 'Aucun élément disponible' : 'Sélectionner',
        ),
        items: options
            .map(
              (item) => DropdownMenuItem<int>(
                value: item['id'] as int,
                child: Text(optionLabel(item), overflow: TextOverflow.ellipsis),
              ),
            )
            .toList(),
        onChanged: options.isEmpty ? null : onChanged,
        validator: (value) => value == null ? 'Sélection obligatoire.' : null,
      ),
    );
  }

  Widget _optionalCycleSelector() {
    return SizedBox(
      width: 290,
      child: DropdownButtonFormField<int?>(
        initialValue: _cycleId,
        decoration: const InputDecoration(labelText: 'Cycle (facultatif)'),
        items: [
          const DropdownMenuItem<int?>(value: null, child: Text('Sans cycle')),
          ..._cycles.map(
            (item) => DropdownMenuItem<int?>(
              value: item['id'] as int,
              child: Text(
                item['name'] as String,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ),
        ],
        onChanged: (value) => setState(() => _cycleId = value),
      ),
    );
  }

  Widget _formFields() {
    switch (_resource) {
      case 'cycles':
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: [
            _field(
              controller: _cycleCode,
              label: 'Code du cycle',
              hint: 'Ex. COLLEGE',
              validator: _codeValidator,
            ),
            _field(
              controller: _cycleName,
              label: 'Nom du cycle',
              validator: (value) => _required(value, 'Nom', min: 2, max: 100),
            ),
          ],
        );
      case 'grades':
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: [
            _field(
              controller: _gradeCode,
              label: 'Code du niveau',
              validator: _codeValidator,
            ),
            _field(
              controller: _gradeName,
              label: 'Nom du niveau',
              validator: (value) => _required(value, 'Nom', max: 100),
            ),
            _optionalCycleSelector(),
            _field(
              controller: _gradeOrder,
              label: 'Ordre d’affichage',
              keyboardType: TextInputType.number,
              validator: _orderValidator,
            ),
          ],
        );
      case 'tracks':
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: [
            _selector(
              label: 'Niveau',
              options: _grades,
              selected: _trackGradeId,
              onChanged: (value) => setState(() => _trackGradeId = value),
              optionLabel: (item) => '${item['name']} · ${item['code']}',
            ),
            SizedBox(
              width: 290,
              child: DropdownButtonFormField<String>(
                initialValue: _trackKind,
                decoration: const InputDecoration(labelText: 'Type'),
                items: [
                  for (final entry in trackKindLabels.entries)
                    DropdownMenuItem(
                      value: entry.key,
                      child: Text(entry.value),
                    ),
                ],
                onChanged: (value) => setState(() => _trackKind = value),
                validator: (value) =>
                    value == null ? 'Sélection obligatoire.' : null,
              ),
            ),
            _field(
              controller: _trackCode,
              label: 'Code',
              hint: 'Ex. 1RE-STMG',
              validator: _codeValidator,
            ),
            _field(
              controller: _trackName,
              label: 'Intitulé',
              hint: 'Ex. STMG',
              validator: (value) => _required(value, 'Intitulé', max: 120),
            ),
            _field(
              controller: _trackOrder,
              label: 'Ordre d’affichage',
              keyboardType: TextInputType.number,
              validator: _orderValidator,
            ),
          ],
        );
      case 'classes':
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: [
            _selector(
              label: 'Niveau',
              options: _grades,
              selected: _classGradeId,
              onChanged: (value) => setState(() => _classGradeId = value),
              optionLabel: (item) => '${item['name']} · ${item['code']}',
            ),
            _field(
              controller: _className,
              label: 'Nom de la classe',
              validator: (value) =>
                  _required(value, 'Nom de la classe', max: 80),
            ),
            _field(
              controller: _academicYear,
              label: 'Année scolaire',
              hint: 'AAAA-AAAA',
              validator: (value) {
                if (!RegExp(r'^\d{4}-\d{4}$').hasMatch(value?.trim() ?? '')) {
                  return 'Format attendu : AAAA-AAAA.';
                }
                return null;
              },
            ),
          ],
        );
      case 'subjects':
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: [
            _field(
              controller: _subjectCode,
              label: 'Code de la matière',
              validator: _codeValidator,
            ),
            _field(
              controller: _subjectName,
              label: 'Nom de la matière',
              validator: (value) => _required(value, 'Nom', max: 100),
            ),
          ],
        );
      case 'chapters':
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: [
            _selector(
              label: 'Niveau',
              options: _grades,
              selected: _chapterGradeId,
              onChanged: (value) => setState(() => _chapterGradeId = value),
              optionLabel: (item) => '${item['name']} · ${item['code']}',
            ),
            _selector(
              label: 'Matière',
              options: _subjects,
              selected: _chapterSubjectId,
              onChanged: (value) => setState(() => _chapterSubjectId = value),
              optionLabel: (item) => item['name'] as String,
            ),
            _field(
              controller: _chapterTitle,
              label: 'Titre du chapitre',
              validator: (value) => _required(value, 'Titre', max: 160),
            ),
            _field(
              controller: _chapterOrder,
              label: 'Ordre d’affichage',
              keyboardType: TextInputType.number,
              validator: _orderValidator,
            ),
          ],
        );
      default:
        return const SizedBox.shrink();
    }
  }

  List<Map<String, dynamic>> _selectedRecords() {
    switch (_resource) {
      case 'cycles':
        return _cycles;
      case 'grades':
        return _grades;
      case 'classes':
        return _classes;
      case 'subjects':
        return _subjects;
      case 'chapters':
        return _chapters;
      case 'tracks':
        return _tracks;
      default:
        return const [];
    }
  }

  String _recordTitle(Map<String, dynamic> item) {
    switch (_resource) {
      case 'cycles':
      case 'grades':
      case 'classes':
      case 'subjects':
      case 'tracks':
        return item['name']?.toString() ?? '';
      case 'chapters':
        return item['title']?.toString() ?? '';
      default:
        return '';
    }
  }

  String _nameOf(
    List<Map<String, dynamic>> items,
    Object? id, {
    String field = 'name',
  }) {
    for (final item in items) {
      if (item['id'] == id) return item[field]?.toString() ?? '#$id';
    }
    return id == null ? 'non défini' : '#$id';
  }

  String _recordSubtitle(Map<String, dynamic> item) {
    switch (_resource) {
      case 'cycles':
        return 'Code : ${item['code']}';
      case 'grades':
        return 'Code : ${item['code']} · Cycle : ${_nameOf(_cycles, item['cycle_id'])}';
      case 'tracks':
        return '${trackKindLabels[item['kind']] ?? item['kind']} · Niveau : ${_nameOf(_grades, item['grade_id'])} · Code : ${item['code']}';
      case 'classes':
        return 'Niveau : ${_nameOf(_grades, item['grade_id'])} · Année ${item['academic_year']}';
      case 'subjects':
        return 'Code : ${item['code']}';
      case 'chapters':
        return 'Niveau : ${_nameOf(_grades, item['grade_id'])} · Matière : ${_nameOf(_subjects, item['subject_id'])}';
      default:
        return '';
    }
  }

  String _description() {
    switch (_resource) {
      case 'cycles':
        return 'Configurez les cycles de formation utilisés par les niveaux.';
      case 'grades':
        return 'Les niveaux sont configurables ici et peuvent être rattachés à un cycle.';
      case 'tracks':
        return 'Séries, spécialités, options ou filières rattachées à un niveau (ex. 1re STMG, BTS SIO option SLAM).';
      case 'classes':
        return 'Une classe est liée à un niveau et à une année scolaire.';
      case 'subjects':
        return 'Ajoutez les matières qui pourront ensuite être associées aux chapitres.';
      case 'chapters':
        return 'Chaque chapitre est associé à un niveau et à une matière.';
      default:
        return '';
    }
  }

  Widget _panel() {
    if (_resource == 'enrollments') return _enrollmentsPanel();
    final records = _selectedRecords();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 900),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _labels[_selected],
                style: Theme.of(context).textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 6),
              Text(
                _description(),
                style: const TextStyle(color: Color(0xFF606B80)),
              ),
              const SizedBox(height: 20),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Form(
                    key: _formKeys[_selected],
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Créer un élément',
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 18),
                        _formFields(),
                        const SizedBox(height: 18),
                        FilledButton.icon(
                          key: const ValueKey('admin.create'),
                          onPressed: _saving || _loading
                              ? null
                              : _createSelected,
                          icon: _saving
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                )
                              : const Icon(Icons.add_rounded),
                          label: Text(
                            'Créer ${_labels[_selected].toLowerCase()}',
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Éléments enregistrés (${records.length})',
                              style: Theme.of(context).textTheme.titleLarge
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                          ),
                          IconButton(
                            tooltip: 'Actualiser la liste',
                            onPressed: _loading ? null : _reload,
                            icon: const Icon(Icons.refresh_rounded),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      if (_loading && records.isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(16),
                          child: Center(child: CircularProgressIndicator()),
                        )
                      else if (records.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 16),
                          child: Text(
                            'Aucun élément enregistré pour le moment.',
                          ),
                        )
                      else
                        ...records.map(
                          (item) => ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: CircleAvatar(
                              backgroundColor: const Color(0xFFE9EEFF),
                              foregroundColor: const Color(0xFF3158D5),
                              child: Text('#${item['id']}'),
                            ),
                            title: Text(_recordTitle(item)),
                            subtitle: Text(_recordSubtitle(item)),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'Ces référentiels sont enregistrés côté serveur. Aucun contenu de cours ou exercice n’est créé dans cette phase.',
                style: TextStyle(
                  color: Color(0xFF69758A),
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _decide(Map<String, dynamic> enrollment, bool approve) async {
    setState(() => _saving = true);
    try {
      await widget.api.decideEnrollment(
        userId: enrollment['user_id'] as int,
        approve: approve,
      );
      await _reload();
      if (mounted) {
        _showMessage(
          approve
              ? 'Parcours de ${enrollment['pseudo']} validé.'
              : 'Demande de ${enrollment['pseudo']} refusée.',
        );
      }
    } on ApiException catch (exception) {
      if (!mounted) return;
      if (exception.statusCode == 401 || exception.statusCode == 403) {
        widget.api.logout();
        widget.onSignOut();
        return;
      }
      _showMessage(exception.message, isError: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  static const _enrollmentStatusLabels = {
    'pending': 'En attente',
    'approved': 'Validé',
    'rejected': 'Refusé',
  };

  Widget _enrollmentsPanel() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 900),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Inscriptions',
                style: Theme.of(context).textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 6),
              const Text(
                'Les élèves choisissent leur parcours ; vous confirmez leur affectation pour éviter les erreurs et les inscriptions frauduleuses.',
                style: TextStyle(color: Color(0xFF606B80)),
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                children: [
                  for (final entry in const {
                    'pending': 'En attente',
                    'approved': 'Validées',
                    'rejected': 'Refusées',
                    'all': 'Toutes',
                  }.entries)
                    ChoiceChip(
                      key: ValueKey('enrollments.filter.${entry.key}'),
                      label: Text(entry.value),
                      selected: _enrollmentFilter == entry.key,
                      onSelected: (_) {
                        setState(() => _enrollmentFilter = entry.key);
                        _reload();
                      },
                    ),
                ],
              ),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: _enrollments.isEmpty
                      ? const Text('Aucune demande dans cette catégorie.')
                      : Column(
                          children: [
                            for (final enrollment in _enrollments)
                              ListTile(
                                key: ValueKey(
                                  'enrollment.${enrollment['user_id']}',
                                ),
                                contentPadding: EdgeInsets.zero,
                                leading: const CircleAvatar(
                                  backgroundColor: Color(0xFFE9EEFF),
                                  foregroundColor: Color(0xFF3158D5),
                                  child: Icon(Icons.person_outline_rounded),
                                ),
                                title: Text(
                                  enrollment['pseudo']?.toString() ?? '',
                                ),
                                subtitle: Text(
                                  [
                                    _nameOf(_grades, enrollment['grade_id']),
                                    if (enrollment['track_id'] != null)
                                      _nameOf(_tracks, enrollment['track_id']),
                                    enrollment['class_id'] == null
                                        ? 'classe non précisée'
                                        : _nameOf(
                                            _classes,
                                            enrollment['class_id'],
                                          ),
                                    _enrollmentStatusLabels[enrollment['enrollment_status']] ??
                                        enrollment['enrollment_status']
                                            .toString(),
                                  ].join(' · '),
                                ),
                                trailing:
                                    enrollment['enrollment_status'] == 'pending'
                                    ? Wrap(
                                        spacing: 8,
                                        children: [
                                          OutlinedButton(
                                            onPressed: _saving
                                                ? null
                                                : () => _decide(
                                                    enrollment,
                                                    false,
                                                  ),
                                            child: const Text('Refuser'),
                                          ),
                                          FilledButton(
                                            key: ValueKey(
                                              'enrollment.approve.${enrollment['user_id']}',
                                            ),
                                            onPressed: _saving
                                                ? null
                                                : () =>
                                                      _decide(enrollment, true),
                                            child: const Text('Valider'),
                                          ),
                                        ],
                                      )
                                    : null,
                              ),
                          ],
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _compactNavigation() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          for (var index = 0; index < _labels.length; index++)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                selected: _selected == index,
                avatar: Icon(_icons[index], size: 18),
                label: Text(_labels[index]),
                onSelected: (_) => setState(() => _selected = index),
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Administration'),
        actions: [
          IconButton(
            tooltip: 'Actualiser les référentiels',
            onPressed: _loading ? null : _reload,
            icon: const Icon(Icons.refresh_rounded),
          ),
          TextButton.icon(
            onPressed: widget.onSignOut,
            icon: const Icon(Icons.logout_rounded),
            label: const Text('Déconnexion'),
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= 980;
          final content = wide
              ? Row(
                  children: [
                    NavigationRail(
                      extended: true,
                      selectedIndex: _selected,
                      onDestinationSelected: (index) =>
                          setState(() => _selected = index),
                      destinations: [
                        for (var index = 0; index < _labels.length; index++)
                          NavigationRailDestination(
                            icon: Icon(_icons[index]),
                            label: Text(_labels[index]),
                          ),
                      ],
                    ),
                    const VerticalDivider(width: 1),
                    Expanded(child: _panel()),
                  ],
                )
              : Column(
                  children: [
                    _compactNavigation(),
                    Expanded(child: _panel()),
                  ],
                );
          return Column(
            children: [
              if (_loading) const LinearProgressIndicator(minHeight: 2),
              if (_loadError != null)
                MaterialBanner(
                  content: Text(_loadError!),
                  leading: const Icon(Icons.error_outline_rounded),
                  actions: [
                    TextButton(
                      onPressed: _reload,
                      child: const Text('Réessayer'),
                    ),
                  ],
                ),
              Expanded(child: content),
            ],
          );
        },
      ),
    );
  }
}
