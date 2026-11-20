import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:plateforme_educative_frontend/api_client.dart';
import 'package:plateforme_educative_frontend/memory_admin.dart';

http.Response _json(Object body, [int status = 200]) => http.Response.bytes(
  utf8.encode(jsonEncode(body)),
  status,
  headers: {'content-type': 'application/json'},
);

Map<String, dynamic> _card(String status) => {
  'id': 7,
  'document_id': 2,
  'page_number': 4,
  'exercise_id': null,
  'card_type': 'definition',
  'question': 'Définir : médiatrice DEMO',
  'answer': 'Droite perpendiculaire au segment en son milieu DEMO',
  'hint': null,
  'original_text': 'texte DEMO',
  'numeric_tolerance': null,
  'difficulty': 1,
  'grade_id': 1,
  'track_ids': [],
  'subject_id': 3,
  'chapter_id': status == 'extracted' ? null : 11,
  'status': status,
  'is_published': false,
  'is_archived': false,
  'created_at': '2026-11-20T00:00:00Z',
  'validated_at': null,
};

void main() {
  testWidgets('l’admin rattache une carte à un chapitre, la valide et règle la répétition espacée', (tester) async {
    final writes = <http.Request>[];
    var card = _card('extracted');
    final api = ApiClient(
      baseUrl: 'http://api.test',
      client: MockClient((request) async {
        final path = request.url.path;
        if (request.method != 'GET') writes.add(request);
        if (path == '/api/v1/admin/grades') {
          return _json([
            {'id': 1, 'cycle_id': null, 'code': 'CM2', 'name': 'CM2 DEMO', 'sort_order': 0},
          ]);
        }
        if (path == '/api/v1/admin/subjects') {
          return _json([
            {'id': 3, 'code': 'MATH', 'name': 'Maths DEMO', 'sort_order': 0},
          ]);
        }
        if (path == '/api/v1/admin/chapters') {
          return _json([
            {'id': 11, 'grade_id': 1, 'subject_id': 3, 'title': 'Géométrie DEMO', 'sort_order': 0},
          ]);
        }
        if (path == '/api/v1/library/documents') {
          return _json([
            {'id': 2, 'title': 'Manuel DEMO'},
          ]);
        }
        if (path == '/api/v1/memory/flashcards') return _json([card]);
        if (path == '/api/v1/memory/flashcards/7') {
          card = {..._card('transformed'), ...jsonDecode(request.body) as Map<String, dynamic>};
          return _json(card);
        }
        if (path == '/api/v1/memory/flashcards/7/action') {
          card = {...card, 'status': 'validated'};
          return _json(card);
        }
        if (path == '/api/v1/memory/methods') {
          return _json([
            {
              'id': 1, 'code': 'feynman', 'name': 'Méthode Feynman', 'category': 'comprehension',
              'summary': 'Expliquer une notion avec des mots simples.', 'principle': null, 'steps': [],
              'status': 'draft', 'sort_order': 0, 'examples': [],
            },
          ]);
        }
        if (path == '/api/v1/memory/settings/spaced-repetition') {
          final settings = request.method == 'PUT'
              ? jsonDecode(request.body)
              : {
                  'learning_steps_days': [1.0, 3.0], 'relearn_minutes': 10, 'min_ease': 1.3,
                  'max_interval_days': 180, 'mastery_interval_days': 21, 'new_cards_per_day': 20,
                };
          return _json(settings as Object);
        }
        return _json([]);
      }),
    );
    tester.view.physicalSize = const Size(1400, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(MaterialApp(home: MemoryAdmin(api: api, onSignOut: () {})));
    await tester.pumpAndSettle();

    expect(find.text('Définir : médiatrice DEMO'), findsOneWidget);
    expect(find.textContaining('chapitre à préciser'), findsOneWidget);
    expect(find.textContaining('Source : Manuel DEMO, p. 4'), findsOneWidget);

    await tester.tap(find.text('Définir : médiatrice DEMO'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('chap-1-3')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Géométrie DEMO').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Enregistrer'));
    await tester.pumpAndSettle();
    expect(jsonDecode(writes.last.body)['chapter_id'], 11);

    await tester.tap(find.text('Valider'));
    await tester.pumpAndSettle();
    expect(writes.last.url.path, '/api/v1/memory/flashcards/7/action');
    expect(jsonDecode(writes.last.body), {'action': 'validate'});
    expect(find.text('Publier'), findsOneWidget);

    await tester.tap(find.text('Fermer'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Géométrie DEMO'), findsOneWidget);

    await tester.tap(find.text('Méthodes'));
    await tester.pumpAndSettle();
    expect(find.text('Méthode Feynman'), findsOneWidget);
    expect(find.text('Brouillon'), findsOneWidget);

    await tester.tap(find.text('Répétition espacée'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Premiers intervalles (jours)'), '1, 3, 7');
    await tester.tap(find.text('Enregistrer').last);
    await tester.pumpAndSettle();
    final saved = jsonDecode(writes.last.body) as Map<String, dynamic>;
    expect(saved['learning_steps_days'], [1, 3, 7]);
    expect(saved['new_cards_per_day'], 20);
  });
}
