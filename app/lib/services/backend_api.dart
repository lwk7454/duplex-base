import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/session.dart';

class BackendApi {
  final String baseUrl;
  final http.Client _client;

  BackendApi({
    this.baseUrl = 'http://192.168.50.230:8021',
    http.Client? client,
  }) : _client = client ?? http.Client();

  Future<bool> checkHealth() async {
    try {
      final response = await _client.get(Uri.parse('$baseUrl/health'));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<ModesResponse> getModes() async {
    final response = await _client.get(Uri.parse('$baseUrl/modes'));
    if (response.statusCode == 200) {
      return ModesResponse.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('Failed to load modes');
    }
  }

  Future<SessionResponse> createSession(SessionRequest request) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/sessions'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(request.toJson()),
    );

    if (response.statusCode == 200) {
      return SessionResponse.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('Failed to create session: ${response.statusCode}');
    }
  }

  Future<void> stopSession(String roomName) async {
    final response = await _client.delete(Uri.parse('$baseUrl/sessions/$roomName'));
    if (response.statusCode != 200) {
      throw Exception('Failed to stop session: ${response.statusCode}');
    }
  }

  void dispose() {
    _client.close();
  }
}
