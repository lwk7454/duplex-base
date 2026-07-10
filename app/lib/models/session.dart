import 'package:json_annotation/json_annotation.dart';

part 'session.g.dart';

@JsonSerializable()
class SessionRequest {
  final String mode;
  final String? customPrompt;

  SessionRequest({
    required this.mode,
    this.customPrompt,
  });

  factory SessionRequest.fromJson(Map<String, dynamic> json) =>
      _$SessionRequestFromJson(json);

  Map<String, dynamic> toJson() => _$SessionRequestToJson(this);
}

@JsonSerializable()
class SessionResponse {
  final String roomName;
  final String url;
  final String token;
  final String mode;
  @JsonKey(name: 'tutorIdentity')
  final String tutorIdentity;

  SessionResponse({
    required this.roomName,
    required this.url,
    required this.token,
    required this.mode,
    required this.tutorIdentity,
  });

  factory SessionResponse.fromJson(Map<String, dynamic> json) =>
      _$SessionResponseFromJson(json);

  Map<String, dynamic> toJson() => _$SessionResponseToJson(this);
}

@JsonSerializable()
class TutorMode {
  final String id;
  final String label;
  final String description;

  TutorMode({
    required this.id,
    required this.label,
    required this.description,
  });

  factory TutorMode.fromJson(Map<String, dynamic> json) =>
      _$TutorModeFromJson(json);

  Map<String, dynamic> toJson() => _$TutorModeToJson(this);
}

@JsonSerializable()
class ModesResponse {
  final List<TutorMode> modes;

  ModesResponse({required this.modes});

  factory ModesResponse.fromJson(Map<String, dynamic> json) =>
      _$ModesResponseFromJson(json);

  Map<String, dynamic> toJson() => _$ModesResponseToJson(this);
}
