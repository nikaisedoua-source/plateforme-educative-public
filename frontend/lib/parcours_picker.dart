import 'package:material_ui/material_ui.dart';

/// Parcours choisi par l'élève : niveau, puis série/spécialité et classe facultatives.
class ParcoursSelection {
  const ParcoursSelection({this.gradeId, this.trackId, this.classId});

  final int? gradeId;
  final int? trackId;
  final int? classId;

  bool get isEmpty => gradeId == null;
}

/// Libellés lisibles d'un parcours à partir du catalogue public.
String describeParcours(
  Map<String, List<Map<String, dynamic>>> catalog,
  ParcoursSelection selection,
) {
  String? nameOf(String key, int? id, {String field = 'name'}) {
    if (id == null) return null;
    for (final item in catalog[key] ?? const <Map<String, dynamic>>[]) {
      if (item['id'] == id) return item[field]?.toString();
    }
    return null;
  }

  final parts = [
    nameOf('grades', selection.gradeId),
    nameOf('tracks', selection.trackId),
    nameOf('classes', selection.classId),
  ].whereType<String>().toList();
  return parts.isEmpty ? 'Aucun parcours choisi' : parts.join(' · ');
}

const trackKindLabels = {
  'serie': 'Série',
  'specialite': 'Spécialité',
  'option': 'Option',
  'filiere': 'Filière',
};

/// Trois listes déroulantes enchaînées : le choix du niveau filtre les séries et les classes.
class ParcoursPicker extends StatelessWidget {
  const ParcoursPicker({
    super.key,
    required this.catalog,
    required this.value,
    required this.onChanged,
    this.allowNoGrade = true,
  });

  final Map<String, List<Map<String, dynamic>>> catalog;
  final ParcoursSelection value;
  final ValueChanged<ParcoursSelection> onChanged;

  /// À l'inscription, l'élève peut choisir plus tard ; dans le profil, le niveau est obligatoire.
  final bool allowNoGrade;

  List<Map<String, dynamic>> _forGrade(String key) => (catalog[key] ?? const [])
      .where((item) => item['grade_id'] == value.gradeId)
      .toList(growable: false);

  @override
  Widget build(BuildContext context) {
    final grades = catalog['grades'] ?? const <Map<String, dynamic>>[];
    if (grades.isEmpty) {
      return const Text(
        'Aucun niveau n’est encore configuré par l’administrateur. Vous pourrez choisir votre parcours plus tard, depuis votre profil.',
        style: TextStyle(color: Color(0xFF606B80), height: 1.4),
      );
    }
    final tracks = _forGrade('tracks');
    final classes = _forGrade('classes');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DropdownButtonFormField<int?>(
          key: const ValueKey('parcours.grade'),
          initialValue: value.gradeId,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Niveau'),
          items: [
            if (allowNoGrade)
              const DropdownMenuItem<int?>(
                value: null,
                child: Text('Je choisirai plus tard'),
              ),
            for (final grade in grades)
              DropdownMenuItem<int?>(
                value: grade['id'] as int,
                child: Text(
                  grade['name'].toString(),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
          validator: (selected) => !allowNoGrade && selected == null
              ? 'Choisissez votre niveau.'
              : null,
          onChanged: (gradeId) =>
              onChanged(ParcoursSelection(gradeId: gradeId)),
        ),
        if (value.gradeId != null && tracks.isNotEmpty) ...[
          const SizedBox(height: 12),
          DropdownButtonFormField<int?>(
            // La clé change avec le niveau pour réinitialiser la liste.
            key: ValueKey('parcours.track.${value.gradeId}'),
            initialValue: value.trackId,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Série, spécialité ou option (facultatif)',
            ),
            items: [
              const DropdownMenuItem<int?>(value: null, child: Text('Aucune')),
              for (final track in tracks)
                DropdownMenuItem<int?>(
                  value: track['id'] as int,
                  child: Text(
                    '${trackKindLabels[track['kind']] ?? ''} · ${track['name']}',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
            onChanged: (trackId) => onChanged(
              ParcoursSelection(
                gradeId: value.gradeId,
                trackId: trackId,
                classId: value.classId,
              ),
            ),
          ),
        ],
        if (value.gradeId != null && classes.isNotEmpty) ...[
          const SizedBox(height: 12),
          DropdownButtonFormField<int?>(
            key: ValueKey('parcours.class.${value.gradeId}'),
            initialValue: value.classId,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Classe (facultatif)'),
            items: [
              const DropdownMenuItem<int?>(
                value: null,
                child: Text('Je ne sais pas encore'),
              ),
              for (final classGroup in classes)
                DropdownMenuItem<int?>(
                  value: classGroup['id'] as int,
                  child: Text(
                    '${classGroup['name']} (${classGroup['academic_year']})',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
            onChanged: (classId) => onChanged(
              ParcoursSelection(
                gradeId: value.gradeId,
                trackId: value.trackId,
                classId: classId,
              ),
            ),
          ),
        ],
      ],
    );
  }
}
