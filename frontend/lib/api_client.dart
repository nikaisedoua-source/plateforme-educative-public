import 'dart:convert';

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
