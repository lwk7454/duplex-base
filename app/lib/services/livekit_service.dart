import 'package:livekit_client/livekit_client.dart';

class LiveKitService {
  Room? _room;

  bool get isConnected => _room?.connectionState == ConnectionState.connected;

  Future<void> connect(String url, String token) async {
    _room = Room(
      roomOptions: const RoomOptions(),
    );

    // Listen to room events
    _room!.events.on((RoomConnectedEvent event) {
      print('Room connected');
    });

    _room!.events.on((RoomDisconnectedEvent event) {
      print('Room disconnected: ${event.reason}');
    });

    _room!.events.on((ParticipantConnectedEvent event) {
      print('Participant connected: ${event.participant.identity}');
    });

    _room!.events.on((ParticipantDisconnectedEvent event) {
      print('Participant disconnected: ${event.participant.identity}');
    });

    await _room!.connect(url, token);
  }

  Future<void> disconnect() async {
    await _room?.disconnect();
    _room = null;
  }

  Room? get room => _room;
}
