import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/session.dart';
import '../services/backend_api.dart';
import '../services/livekit_service.dart';

final backendApiProvider = Provider<BackendApi>((ref) {
  return BackendApi();
});

final livekitServiceProvider = Provider<LiveKitService>((ref) {
  return LiveKitService();
});

final sessionStateProvider = StateNotifierProvider<SessionNotifier, SessionState>((ref) {
  final api = ref.watch(backendApiProvider);
  final livekit = ref.watch(livekitServiceProvider);
  return SessionNotifier(api, livekit);
});

class SessionNotifier extends StateNotifier<SessionState> {
  final BackendApi _api;
  final LiveKitService _livekit;

  SessionNotifier(this._api, this._livekit) : super(SessionState.initial());

  Future<void> createSession(String mode) async {
    state = SessionState.loading();
    try {
      final response = await _api.createSession(SessionRequest(mode: mode));
      await _livekit.connect(response.url, response.token);
      state = SessionState.connected(response);
    } catch (e) {
      state = SessionState.error(e.toString());
    }
  }

  Future<void> stopSession() async {
    final current = state;
    if (current is SessionConnected) {
      try {
        await _api.stopSession(current.session.roomName);
      } catch (_) {}
    }
    await _livekit.disconnect();
    state = SessionState.initial();
  }

  @override
  void dispose() {
    _livekit.disconnect();
    super.dispose();
  }
}

sealed class SessionState {
  const SessionState();

  factory SessionState.initial() => SessionInitial();
  factory SessionState.loading() => SessionLoading();
  factory SessionState.connected(SessionResponse session) => SessionConnected(session);
  factory SessionState.error(String message) => SessionError(message);
}

class SessionInitial extends SessionState {
  const SessionInitial();
}

class SessionLoading extends SessionState {
  const SessionLoading();
}

class SessionConnected extends SessionState {
  final SessionResponse session;
  SessionConnected(this.session);
}

class SessionError extends SessionState {
  final String message;
  SessionError(this.message);
}
