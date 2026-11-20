import 'package:material_ui/material_ui.dart';

import 'api_client.dart';
import 'parcours_picker.dart';
import 'theme.dart';

class StudentHomePage extends StatefulWidget {
  const StudentHomePage({
    super.key,
    required this.api,
    required this.user,
    required this.onSignOut,
  });

  final ApiClient api;
  final Map<String, dynamic> user;
  final VoidCallback onSignOut;

  @override
  State<StudentHomePage> createState() => _StudentHomePageState();
}

class _StudentHomePageState extends State<StudentHomePage> {
  int _tab = 0;
  late Map<String, dynamic> _user = widget.user;
  Map<String, List<Map<String, dynamic>>>? _catalog;
  ParcoursSelection _draft = const ParcoursSelection();
  final _parcoursForm = GlobalKey<FormState>();
  bool _editingParcours = false;
  bool _saving = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _loadCatalog();
  }

  Map<String, dynamic> get _profile => _user['profile'] is Map
      ? Map<String, dynamic>.from(_user['profile'] as Map)
      : const {};

  ParcoursSelection get _current => ParcoursSelection(
    gradeId: _profile['grade_id'] as int?,
    trackId: _profile['track_id'] as int?,
    classId: _profile['class_id'] as int?,
  );

  Future<void> _loadCatalog() async {
    try {
      final catalog = await widget.api.catalog();
      if (mounted) setState(() => _catalog = catalog);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _message = exception.message);
    }
  }

  Future<void> _submitParcours() async {
    final gradeId = _draft.gradeId;
    final valid = _parcoursForm.currentState?.validate() ?? false;
    if (!valid || gradeId == null) return;
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.api.requestEnrollment(
        gradeId: gradeId,
        trackId: _draft.trackId,
        classId: _draft.classId,
      );
      final user = await widget.api.currentUser();
      if (!mounted) return;
      setState(() {
        _user = user;
        _editingParcours = false;
        _message =
            'Demande envoyée. L’administrateur doit confirmer votre parcours.';
      });
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        widget.onSignOut();
        return;
      }
      if (mounted) setState(() => _message = exception.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  static const _statusLabels = {
    'none': 'Aucun parcours choisi',
    'pending': 'En attente de validation par l’administrateur',
    'approved': 'Parcours validé',
    'rejected': 'Demande refusée : choisissez à nouveau votre parcours',
  };

  Color _statusColor(String status) => switch (status) {
    'approved' => Brand.mint,
    'rejected' => Brand.coral,
    'pending' => const Color(0xFFB45309),
    _ => Brand.muted,
  };

  Widget _parcoursCard() {
    final status = _profile['enrollment_status']?.toString() ?? 'none';
    final catalog = _catalog;
    return ChunkCard(
      key: const ValueKey('student.parcours'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Mon parcours',
            style: TextStyle(fontWeight: FontWeight.w900, fontSize: 18),
          ),
          const SizedBox(height: 8),
          Text(
            catalog == null ? '…' : describeParcours(catalog, _current),
            style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
          ),
          const SizedBox(height: 4),
          Text(
            _statusLabels[status] ?? status,
            key: const ValueKey('student.parcours.status'),
            style: TextStyle(
              color: _statusColor(status),
              fontWeight: FontWeight.w800,
            ),
          ),
          if (_message != null) ...[
            const SizedBox(height: 8),
            Text(_message!, style: const TextStyle(color: Color(0xFF606B80))),
          ],
          const SizedBox(height: 14),
          if (_editingParcours && catalog != null)
            Form(
              key: _parcoursForm,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ParcoursPicker(
                    catalog: catalog,
                    value: _draft,
                    allowNoGrade: false,
                    onChanged: (value) => setState(() => _draft = value),
                  ),
                  const SizedBox(height: 14),
                  Wrap(
                    spacing: 10,
                    children: [
                      PressButton(
                        label: _saving ? '…' : 'Envoyer la demande',
                        primary: true,
                        onPressed:
                            _saving || (catalog['grades'] ?? const []).isEmpty
                            ? null
                            : _submitParcours,
                      ),
                      PressButton(
                        label: 'Annuler',
                        primary: false,
                        onPressed: _saving
                            ? null
                            : () => setState(() => _editingParcours = false),
                      ),
                    ],
                  ),
                ],
              ),
            )
          else
            PressButton(
              key: const ValueKey('student.parcours.edit'),
              label: status == 'none'
                  ? 'Choisir mon parcours'
                  : 'Modifier mon parcours',
              primary: status == 'none' || status == 'rejected',
              onPressed: catalog == null
                  ? null
                  : () => setState(() {
                      _draft = _current;
                      _editingParcours = true;
                      _message = null;
                    }),
            ),
        ],
      ),
    );
  }

  static const List<String> _tabs = [
    'Accueil',
    'Matières',
    'Exercices',
    'Flash',
    'Mémoriser',
    'Classement',
    'Progrès',
    'Profil',
  ];

  @override
  Widget build(BuildContext context) {
    final pseudo = _profile['pseudo']?.toString();
    final greeting = (pseudo == null || pseudo.isEmpty)
        ? 'Votre espace élève'
        : 'Bonjour, $pseudo';

    return Scaffold(
      appBar: AppBar(
        title: Text(_tabs[_tab]),
        actions: [
          PressButton(
            label: 'Déconnexion',
            primary: false,
            onPressed: widget.onSignOut,
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: PageFrame(
        title: greeting,
        trailing: _tab == 0 ? const DemoTag() : null,
        children: [
          if (_tab == 0) ..._accueil(),
          if (_tab == 1) ..._matieres(),
          if (_tab == 2) ..._exercices(),
          if (_tab == 3) ..._flash(),
          if (_tab == 4) ..._memorisation(),
          if (_tab == 5) ..._classement(),
          if (_tab == 6) ..._progression(),
          if (_tab == 7) ..._profil(),
        ],
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: Palette.of(context).surface,
          border: Border.all(color: Palette.of(context).border, width: 2),
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(20),
            topRight: Radius.circular(20),
          ),
          boxShadow: [
            BoxShadow(
              color: Palette.of(context).shadow,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 70,
            child: Row(
              children: [
                for (var i = 0; i < _tabs.length; i++)
                  Expanded(
                    child: PressButton(
                      label: _tabs[i],
                      primary: _tab == i,
                      onPressed: () => setState(() => _tab = i),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _accueil() {
    return [
      ChunkCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                DemoTag(),
                SizedBox(width: 8),
                Text(
                  'Espace élève',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'Prêt à progresser ?',
              style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            const Text(
              'Les activités scolaires apparaîtront ici lorsque l’administrateur aura importé des documents, extrait des exercices et les aura validés.',
              style: TextStyle(color: Color(0xFF606B80)),
            ),
            const SizedBox(height: 16),
            const Text(
              'Aucun contenu scolaire n’est affiché pour le moment.',
              style: TextStyle(fontWeight: FontWeight.w800, color: Brand.muted),
            ),
          ],
        ),
      ),
      const SizedBox(height: 16),
      _parcoursCard(),
      const SizedBox(height: 16),
      const Text(
        'Ce contenu provient exclusivement des documents fournis et validés par l’administrateur. Aucun exercice n’est inventé.',
        style: TextStyle(fontSize: 13, color: Color(0xFF69758A)),
      ),
    ];
  }

  List<Widget> _matieres() {
    return [
      const Text(
        'Les matières apparaîtront ici après leur création par l’administrateur.',
        style: TextStyle(color: Color(0xFF606B80)),
      ),
      const SizedBox(height: 16),
      const Text(
        'Aucune matière configurée pour le moment.',
        style: TextStyle(fontWeight: FontWeight.w800, color: Brand.muted),
      ),
    ];
  }

  List<Widget> _exercices() {
    return [
      const Text(
        'Les exercices apparaîtront ici après leur extraction et validation.',
        style: TextStyle(color: Color(0xFF606B80)),
      ),
      const SizedBox(height: 16),
      const Text(
        'Aucun exercice disponible pour le moment.',
        style: TextStyle(fontWeight: FontWeight.w800, color: Brand.muted),
      ),
    ];
  }

  List<Widget> _flash() {
    return [
      const Text(
        'Les cartes mémoire apparaîtront ici après leur création à partir des documents validés.',
        style: TextStyle(color: Color(0xFF606B80)),
      ),
      const SizedBox(height: 16),
      const Text(
        'Aucune carte mémoire pour le moment.',
        style: TextStyle(fontWeight: FontWeight.w800, color: Brand.muted),
      ),
    ];
  }

  List<Widget> _memorisation() {
    return [
      const Text(
        'Les méthodes de mémorisation apparaîtront ici.',
        style: TextStyle(color: Color(0xFF606B80)),
      ),
      const SizedBox(height: 16),
      const Text(
        'Aucune méthode disponible pour le moment.',
        style: TextStyle(fontWeight: FontWeight.w800, color: Brand.muted),
      ),
    ];
  }

  List<Widget> _classement() {
    return [
      const Text(
        'Les classements apparaîtront ici après vos premières activités.',
        style: TextStyle(color: Color(0xFF606B80)),
      ),
      const SizedBox(height: 16),
      const Text(
        'Aucun score pour le moment.',
        style: TextStyle(fontWeight: FontWeight.w800, color: Brand.muted),
      ),
    ];
  }

  List<Widget> _progression() {
    return [
      const Text(
        'Votre progression apparaîtra ici après vos premières activités.',
        style: TextStyle(color: Color(0xFF606B80)),
      ),
      const SizedBox(height: 16),
      const Text(
        'Aucune donnée de progression pour le moment.',
        style: TextStyle(fontWeight: FontWeight.w800, color: Brand.muted),
      ),
    ];
  }

  List<Widget> _profil() {
    return [
      Text(
        'Pseudo : ${_profile['pseudo'] ?? ''}',
        style: const TextStyle(fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 8),
      Text(
        'Compte : ${_user['email'] ?? ''}',
        style: const TextStyle(color: Color(0xFF606B80)),
      ),
      const SizedBox(height: 16),
      _parcoursCard(),
    ];
  }
}
