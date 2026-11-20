import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:plateforme_educative_frontend/admin_dashboard.dart';
import 'package:plateforme_educative_frontend/api_client.dart';
import 'package:plateforme_educative_frontend/main.dart';

void main() {
  testWidgets('connexion bascule vers le formulaire d’inscription',
      (tester) async {
    final api = ApiClient(
      client: MockClient((_) async => http.Response('{}', 500)),
    );
    await tester.pumpWidget(PlateformeApp(apiClient: api));

    expect(find.text('Bienvenue'), findsOneWidget);
    expect(find.byKey(const ValueKey('auth.email')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const ValueKey('auth.toggle')));
    await tester.tap(find.byKey(const ValueKey('auth.toggle')));
    await tester.pumpAndSettle();

    expect(find.text('Créer un compte élève'), findsOneWidget);
    expect(find.byKey(const ValueKey('register.pseudo')), findsOneWidget);
    expect(find.byKey(const ValueKey('register.confirm')), findsOneWidget);
  });

  testWidgets(
      'l’espace admin affiche un état vide sans inventer de référentiels',
      (tester) async {
    final api = ApiClient(
      client: MockClient((_) async => http.Response('[]', 200)),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: AdminDashboard(api: api, onSignOut: () {}),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Administration'), findsOneWidget);
    expect(find.text('Créer un élément'), findsOneWidget);
    expect(
        find.text('Aucun élément enregistré pour le moment.'), findsOneWidget);
  });

  test('inscription envoie uniquement les champs attendus au backend',
      () async {
    late http.Request request;
    final api = ApiClient(
      baseUrl: 'http://api.test',
      client: MockClient((incoming) async {
        request = incoming;
        return http.Response('{}', 201);
      }),
    );

    await api.register(
      email: 'eleve@example.test',
      password: 'un-mot-de-passe-long',
      pseudo: 'Eleve Demo',
    );

    expect(request.method, 'POST');
    expect(request.url.path, '/api/v1/auth/register');
    expect(jsonDecode(request.body), {
      'email': 'eleve@example.test',
      'password': 'un-mot-de-passe-long',
      'pseudo': 'Eleve Demo',
    });
  });

  test('le jeton Bearer accompagne le profil et les appels admin', () async {
    final requests = <http.Request>[];
    final api = ApiClient(
      baseUrl: 'http://api.test',
      client: MockClient((request) async {
        requests.add(request);
        if (request.url.path.endsWith('/auth/login')) {
          return http.Response('{"access_token":"test-token"}', 200);
        }
        if (request.url.path.endsWith('/auth/me')) {
          return http.Response(
            '{"id":1,"email":"admin@example.test","role":"admin","is_active":true}',
            200,
          );
        }
        if (request.url.path.endsWith('/admin/cycles')) {
          return http.Response('[]', 200);
        }
        return http.Response('{"detail":"introuvable"}', 404);
      }),
    );

    await api.login(email: 'admin@example.test', password: 'mot-de-passe');
    final user = await api.currentUser();
    final cycles = await api.listAdmin('cycles');

    expect(api.isAuthenticated, isTrue);
    expect(user['role'], 'admin');
    expect(cycles, isEmpty);
    for (final request in requests.skip(1)) {
      final authorization = request.headers.entries
          .where((entry) => entry.key.toLowerCase() == 'authorization')
          .map((entry) => entry.value)
          .single;
      expect(authorization, 'Bearer test-token');
    }
    api.logout();
    expect(api.isAuthenticated, isFalse);
  });
}
