import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({String? baseUrl, http.Client? client})
    : baseUrl =
          (baseUrl ??
                  const String.fromEnvironment(
                    'API_BASE_URL',
                    defaultValue: 'http://localhost:8000',
                  ))
              .replaceAll(RegExp(r'/+$'), ''),
      _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;
  String? _accessToken;

  static const _adminResources = {
    'cycles',
    'grades',
    'tracks',
    'classes',
    'subjects',
    'chapters',
  };

  bool get isAuthenticated => _accessToken != null;

  Future<void> register({
    required String email,
    required String password,
    required String pseudo,
    int? gradeId,
    int? trackId,
    int? classId,
  }) async {
    await _request(
      'POST',
      '/api/v1/auth/register',
      body: {
        'email': email,
        'password': password,
        'pseudo': pseudo,
        'grade_id': ?gradeId,
        'track_id': ?trackId,
        'class_id': ?classId,
      },
    );
  }

  /// Référentiels publics (niveaux, séries/spécialités, classes) pour choisir son parcours.
  Future<Map<String, List<Map<String, dynamic>>>> catalog() async {
    final result = await _request('GET', '/api/v1/catalog');
    if (result is! Map) {
      throw const ApiException('Réponse de référentiels invalide.');
    }
    List<Map<String, dynamic>> list(String key) =>
        (result[key] is List ? result[key] as List : const [])
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList(growable: false);
    return {
      'cycles': list('cycles'),
      'grades': list('grades'),
      'tracks': list('tracks'),
      'classes': list('classes'),
    };
  }

  /// L'élève demande à rejoindre ou changer de parcours (validation admin ensuite).
  Future<Map<String, dynamic>> requestEnrollment({
    required int gradeId,
    int? trackId,
    int? classId,
  }) async {
    final result = await _request(
      'POST',
      '/api/v1/auth/me/enrollment',
      body: {
        'grade_id': gradeId,
        'track_id': ?trackId,
        'class_id': ?classId,
      },
      authenticated: true,
    );
    if (result is! Map) {
      throw const ApiException('Réponse de parcours invalide.');
    }
    return Map<String, dynamic>.from(result);
  }

  Future<List<Map<String, dynamic>>> listEnrollments({String? status}) async {
    final query = status == null ? '' : '?status=$status';
    final result = await _request(
      'GET',
      '/api/v1/admin/enrollments$query',
      authenticated: true,
    );
    if (result is! List) {
      throw const ApiException('Réponse de liste invalide.');
    }
    return result
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> decideEnrollment({
    required int userId,
    required bool approve,
  }) async {
    final result = await _request(
      'POST',
      '/api/v1/admin/enrollments/$userId/decision',
      body: {'decision': approve ? 'approve' : 'reject'},
      authenticated: true,
    );
    if (result is! Map) {
      throw const ApiException('Réponse de décision invalide.');
    }
    return Map<String, dynamic>.from(result);
  }

  Future<void> login({required String email, required String password}) async {
    final result = await _request(
      'POST',
      '/api/v1/auth/login',
      body: {'email': email, 'password': password},
    );
    if (result is! Map || result['access_token'] is! String) {
      throw const ApiException('Réponse de connexion invalide.');
    }
    _accessToken = result['access_token'] as String;
  }

  Future<Map<String, dynamic>> currentUser() async {
    final result = await _request(
      'GET',
      '/api/v1/auth/me',
      authenticated: true,
    );
    if (result is! Map) {
      throw const ApiException('Réponse de profil invalide.');
    }
    return Map<String, dynamic>.from(result);
  }

  Future<List<Map<String, dynamic>>> listAdmin(String resource) async {
    final result = await _request(
      'GET',
      '/api/v1/admin/${_resourcePath(resource)}',
      authenticated: true,
    );
    if (result is! List) {
      throw const ApiException('Réponse de liste invalide.');
    }
    return result
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> createAdmin(
    String resource,
    Map<String, Object?> values,
  ) async {
    final result = await _request(
      'POST',
      '/api/v1/admin/${_resourcePath(resource)}',
      body: values,
      authenticated: true,
    );
    if (result is! Map) {
      throw const ApiException('Réponse de création invalide.');
    }
    return Map<String, dynamic>.from(result);
  }

  /// --- Bibliothèque documentaire (administrateur) ---

  List<Map<String, dynamic>> _list(dynamic result) {
    if (result is! List) throw const ApiException('Réponse de liste invalide.');
    return result
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  Map<String, dynamic> _map(dynamic result) {
    if (result is! Map) throw const ApiException('Réponse invalide.');
    return Map<String, dynamic>.from(result);
  }

  String _query(Map<String, Object?> params) {
    final kept = {
      for (final entry in params.entries)
        if (entry.value != null && entry.value.toString().isNotEmpty)
          entry.key: entry.value.toString(),
    };
    return kept.isEmpty ? '' : '?${Uri(queryParameters: kept).query}';
  }

  Future<Map<String, dynamic>> uploadDocument({
    required List<int> bytes,
    required String filename,
    String kind = 'autre',
    int? gradeId,
    int? subjectId,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/v1/library/documents'),
    );
    if (_accessToken != null) {
      request.headers['Authorization'] = 'Bearer $_accessToken';
    }
    request.fields['kind'] = kind;
    if (gradeId != null) request.fields['grade_id'] = '$gradeId';
    if (subjectId != null) request.fields['subject_id'] = '$subjectId';
    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: filename),
    );
    late final http.Response response;
    try {
      response = await http.Response.fromStream(
        await request.send().timeout(const Duration(minutes: 10)),
      );
    } on Exception {
      throw ApiException('Envoi impossible vers $baseUrl.');
    }
    final decoded = _decodeBody(response);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        _errorMessage(decoded, response.statusCode),
        statusCode: response.statusCode,
      );
    }
    return _map(decoded);
  }

  Future<List<Map<String, dynamic>>> listDocuments({
    String? search,
    String? status,
  }) async => _list(
    await _request(
      'GET',
      '/api/v1/library/documents${_query({'q': search, 'status': status})}',
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> getDocument(int id) async => _map(
    await _request('GET', '/api/v1/library/documents/$id', authenticated: true),
  );

  Future<Map<String, dynamic>> updateDocument(
    int id,
    Map<String, Object?> values,
  ) async => _map(
    await _request(
      'PATCH',
      '/api/v1/library/documents/$id',
      body: values,
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> identifyDocument(int id) async => _map(
    await _request(
      'GET',
      '/api/v1/library/documents/$id/identify',
      authenticated: true,
    ),
  );

  Future<void> extractDocument(int id) async => _request(
    'POST',
    '/api/v1/library/documents/$id/extract',
    authenticated: true,
  );

  Future<List<Map<String, dynamic>>> listPages(int id) async => _list(
    await _request(
      'GET',
      '/api/v1/library/documents/$id/pages',
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> segmentDocument(
    int id, {
    int? correctionDocumentId,
    bool replace = false,
  }) async => _map(
    await _request(
      'POST',
      '/api/v1/library/documents/$id/segment${_query({'correction_document_id': correctionDocumentId, 'replace': replace ? 'true' : null})}',
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> archiveDocument(int id) async => _map(
    await _request(
      'POST',
      '/api/v1/library/documents/$id/archive',
      authenticated: true,
    ),
  );

  Future<List<Map<String, dynamic>>> listExercises({
    int? documentId,
    String? status,
    int? subjectId,
    bool? published,
  }) async => _list(
    await _request(
      'GET',
      '/api/v1/library/exercises${_query({'document_id': documentId, 'status': status, 'subject_id': subjectId, 'published': published})}',
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> getCorrectionAccess() async =>
      _map(await _request('GET', '/api/v1/library/settings/correction-access', authenticated: true));

  Future<Map<String, dynamic>> setCorrectionAccess(String mode, int attempts) async => _map(
    await _request(
      'PUT',
      '/api/v1/library/settings/correction-access',
      authenticated: true,
      body: {'mode': mode, 'attempts': attempts},
    ),
  );

  // ------------------------------------------------------------------ espace élève

  Future<List<Map<String, dynamic>>> studentSubjects() async =>
      _list(await _request('GET', '/api/v1/student/subjects', authenticated: true));

  Future<List<Map<String, dynamic>>> studentExercises({int? subjectId, int? chapterId}) async => _list(
    await _request(
      'GET',
      '/api/v1/student/exercises${_query({'subject_id': subjectId, 'chapter_id': chapterId})}',
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> studentExercise(int id) async =>
      _map(await _request('GET', '/api/v1/student/exercises/$id', authenticated: true));

  Future<Map<String, dynamic>> submitAttempt(int id, {String? answer, List<int>? optionIds}) async => _map(
    await _request(
      'POST',
      '/api/v1/student/exercises/$id/attempts',
      authenticated: true,
      body: {'answer_text': ?answer, 'option_ids': ?optionIds},
    ),
  );

  Future<Map<String, dynamic>> studentCorrection(int id) async =>
      _map(await _request('GET', '/api/v1/student/exercises/$id/correction', authenticated: true));

  /// Texte avec formules LaTeX → HTML sûr (texte échappé + MathML).
  Future<Map<String, dynamic>> renderMath(String text) async => _map(
    await _request('POST', '/api/v1/math/render', authenticated: true, body: {'text': text}),
  );

  Future<Map<String, dynamic>> createExerciseManually({
    required int documentId,
    required int page,
    required String title,
    required String statement,
  }) async => _map(
    await _request(
      'POST',
      '/api/v1/library/exercises',
      authenticated: true,
      body: {
        'document_id': documentId,
        'page_start': page,
        'title': title,
        'statement': statement,
      },
    ),
  );

  Future<Map<String, dynamic>> getExercise(int id) async => _map(
    await _request('GET', '/api/v1/library/exercises/$id', authenticated: true),
  );

  Future<Map<String, dynamic>> updateExercise(
    int id,
    Map<String, Object?> values,
  ) async => _map(
    await _request(
      'PATCH',
      '/api/v1/library/exercises/$id',
      body: values,
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> exerciseAction(
    int id,
    String action, {
    String? comment,
  }) async => _map(
    await _request(
      'POST',
      '/api/v1/library/exercises/$id/action',
      body: {'action': action, 'comment': ?comment},
      authenticated: true,
    ),
  );

  Future<void> deleteExercise(int id) async => _request(
    'DELETE',
    '/api/v1/library/exercises/$id',
    authenticated: true,
  );

  Future<Map<String, dynamic>> saveCorrection(
    int exerciseId,
    Map<String, Object?> values,
  ) async => _map(
    await _request(
      'PUT',
      '/api/v1/library/exercises/$exerciseId/correction',
      body: values,
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> decideCorrection(
    int exerciseId,
    String decision,
  ) async => _map(
    await _request(
      'POST',
      '/api/v1/library/exercises/$exerciseId/correction/$decision',
      authenticated: true,
    ),
  );

  Future<Map<String, dynamic>> addPageCapture(int exerciseId, int page) async =>
      _map(
        await _request(
          'POST',
          '/api/v1/library/exercises/$exerciseId/assets/page?page_number=$page',
          authenticated: true,
        ),
      );

  Future<void> deleteAsset(int assetId) async => _request(
    'DELETE',
    '/api/v1/library/assets/$assetId',
    authenticated: true,
  );

  Future<List<Map<String, dynamic>>> auditLog({
    String? entityType,
    int? entityId,
  }) async => _list(
    await _request(
      'GET',
      '/api/v1/library/audit${_query({'entity_type': entityType, 'entity_id': entityId})}',
      authenticated: true,
    ),
  );

  /// Image protégée (aperçu de page, figure) : téléchargée avec le jeton.
  Future<Uint8List> fetchBytes(String path) async {
    final http.Response response;
    try {
      response = await _client.get(
        Uri.parse('$baseUrl$path'),
        headers: {
          if (_accessToken != null) 'Authorization': 'Bearer $_accessToken',
        },
      );
    } on Exception {
      throw ApiException('Serveur injoignable à $baseUrl.');
    }
    if (response.statusCode != 200) {
      throw ApiException(
        _errorMessage(_decodeBody(response), response.statusCode),
        statusCode: response.statusCode,
      );
    }
    return response.bodyBytes;
  }

  void logout() => _accessToken = null;

  String _resourcePath(String resource) {
    if (!_adminResources.contains(resource)) {
      throw ArgumentError.value(
        resource,
        'resource',
        'Ressource admin inconnue',
      );
    }
    return resource;
  }

  dynamic _decodeBody(http.Response response) {
    if (response.bodyBytes.isEmpty) return null;
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      return null;
    }
  }

  Future<dynamic> _request(
    String method,
    String path, {
    Object? body,
    bool authenticated = false,
  }) async {
    final headers = <String, String>{
      'Accept': 'application/json',
      if (body != null) 'Content-Type': 'application/json',
      if (authenticated && _accessToken != null)
        'Authorization': 'Bearer $_accessToken',
    };
    final uri = Uri.parse('$baseUrl$path');
    final encodedBody = body == null ? null : jsonEncode(body);

    late final http.Response response;
    try {
      switch (method) {
        case 'GET':
          response = await _client.get(uri, headers: headers);
          break;
        case 'POST':
          response = await _client.post(
            uri,
            headers: headers,
            body: encodedBody,
          );
          break;
        case 'PUT':
          response = await _client.put(uri, headers: headers, body: encodedBody);
          break;
        case 'PATCH':
          response = await _client.patch(
            uri,
            headers: headers,
            body: encodedBody,
          );
          break;
        case 'DELETE':
          response = await _client.delete(uri, headers: headers);
          break;
        default:
          throw ArgumentError.value(method, 'method', 'Méthode HTTP inconnue');
      }
    } on Exception {
      throw ApiException(
        'Serveur injoignable à $baseUrl. Vérifiez que l’API est démarrée.',
      );
    }

    final decoded = _decodeBody(response);

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        _errorMessage(decoded, response.statusCode),
        statusCode: response.statusCode,
      );
    }
    return decoded;
  }

  String _errorMessage(dynamic response, int statusCode) {
    final detail = response is Map ? response['detail'] : null;
    if (detail is String && detail.isNotEmpty) return detail;
    if (detail is List) {
      final messages = detail
          .map((item) {
            if (item is Map) {
              final message = item['msg']?.toString() ?? item.toString();
              final location = item['loc'];
              if (location is List && location.length > 1) {
                return '${location.skip(1).join('.')}: $message';
              }
              return message;
            }
            return item.toString();
          })
          .join('\n');
      if (messages.isNotEmpty) return messages;
    }
    return 'La requête a échoué (HTTP $statusCode).';
  }
}
