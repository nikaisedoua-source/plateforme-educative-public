import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:plateforme_educative_frontend/admin_dashboard.dart';
import 'package:plateforme_educative_frontend/api_client.dart';
import 'package:plateforme_educative_frontend/main.dart';
import 'package:plateforme_educative_frontend/student_home.dart';

const _catalog = {
  'cycles': [],
  'grades': [
    {'id': 1, 'cycle_id': null, 'code': '1RE', 'name': '1re DEMO', 'sort_order': 0},
  ],
  'tracks': [
    {'id': 5, 'grade_id': 1, 'code': 'STMG-DEMO', 'name': 'STMG DEMO', 'kind': 'serie', 'sort_order': 0},
  ],
  'classes': [
    {'id': 9, 'grade_id': 1, 'name': '1re A DEMO', 'academic_year': '2026-2027'},
  ],
};

http.Response _json(Object body, [int status = 200]) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json'},
    );

void main() {
  test('l’inscription transmet le parcours choisi', () async {
    late http.Request request;
    final api = ApiClient(
      baseUrl: 'http://api.test',
      client: MockClient((incoming) async {
        request = incoming;
        return _json({}, 201);
      }),
    );
    await api.register(
      email: 'eleve@example.test',
      password: 'un-mot-de-passe-long',
      pseudo: 'Eleve Demo',
      gradeId: 1,
      trackId: 5,
      classId: 9,
    );
    expect(jsonDecode(request.body), {
      'email': 'eleve@example.test',
      'password': 'un-mot-de-passe-long',
      'pseudo': 'Eleve Demo',
      'grade_id': 1,
      'track_id': 5,
      'class_id': 9,
    });
  });

  testWidgets('le formulaire d’inscription propose les niveaux du catalogue', (tester) async {
    final api = ApiClient(
      client: MockClient((request) async =>
          request.url.path == '/api/v1/catalog' ? _json(_catalog) : _json({}, 500)),
    );
    await tester.pumpWidget(PlateformeApp(apiClient: api));
    await tester.ensureVisible(find.byKey(const ValueKey('auth.toggle')));
    await tester.tap(find.byKey(const ValueKey('auth.toggle')));
    await tester.pumpAndSettle();

    expect(find.text('Mon parcours'), findsOneWidget);
    expect(find.byKey(const ValueKey('parcours.grade')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const ValueKey('parcours.grade')));
    await tester.tap(find.byKey(const ValueKey('parcours.grade')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('1re DEMO').last);
    await tester.pumpAndSettle();

    // Le choix du niveau fait apparaître ses séries et ses classes.
    expect(find.byKey(const ValueKey('parcours.track.1')), findsOneWidget);
    expect(find.byKey(const ValueKey('parcours.class.1')), findsOneWidget);
  });

  testWidgets('l’élève voit que son parcours attend la validation', (tester) async {
    final api = ApiClient(
      client: MockClient((request) async => _json(_catalog)),
    );
    await tester.pumpWidget(MaterialApp(
      home: StudentHomePage(
        api: api,
        onSignOut: () {},
        user: const {
          'email': 'eleve@example.test',
          'role': 'student',
          'profile': {
            'pseudo': 'EleveDEMO',
            'grade_id': 1,
            'track_id': 5,
            'class_id': 9,
            'enrollment_status': 'pending',
          },
        },
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('1re DEMO · STMG DEMO · 1re A DEMO'), findsOneWidget);
    expect(find.text('En attente de validation par l’administrateur'), findsOneWidget);
  });

  testWidgets('l’admin valide une demande de parcours', (tester) async {
    final decisions = <http.Request>[];
    final api = ApiClient(
      baseUrl: 'http://api.test',
      client: MockClient((request) async {
        final path = request.url.path;
        if (path.endsWith('/decision')) {
          decisions.add(request);
          return _json({});
        }
        if (path == '/api/v1/admin/enrollments') {
          return _json(decisions.isEmpty
              ? [
                  {
                    'user_id': 3,
                    'pseudo': 'EleveDEMO',
                    'grade_id': 1,
                    'track_id': 5,
                    'class_id': 9,
                    'enrollment_status': 'pending',
                    'enrollment_requested_at': null,
                    'enrollment_reviewed_at': null,
                  },
                ]
              : []);
        }
        if (path == '/api/v1/admin/grades') return _json(_catalog['grades']!);
        if (path == '/api/v1/admin/tracks') return _json(_catalog['tracks']!);
        if (path == '/api/v1/admin/classes') return _json(_catalog['classes']!);
        return _json([]);
      }),
    );
    tester.view.physicalSize = const Size(1400, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(MaterialApp(home: AdminDashboard(api: api, onSignOut: () {})));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Inscriptions'));
    await tester.pumpAndSettle();

    expect(find.text('EleveDEMO'), findsOneWidget);
    expect(find.textContaining('1re DEMO · STMG DEMO · 1re A DEMO'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('enrollment.approve.3')));
    await tester.pumpAndSettle();

    expect(decisions, hasLength(1));
    expect(decisions.single.url.path, '/api/v1/admin/enrollments/3/decision');
    expect(jsonDecode(decisions.single.body), {'decision': 'approve'});
    expect(find.text('Aucune demande dans cette catégorie.'), findsOneWidget);
  });
}
