// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'session.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

SessionRequest _$SessionRequestFromJson(Map<String, dynamic> json) =>
    SessionRequest(
      mode: json['mode'] as String,
      customPrompt: json['customPrompt'] as String?,
    );

Map<String, dynamic> _$SessionRequestToJson(SessionRequest instance) =>
    <String, dynamic>{
      'mode': instance.mode,
      'customPrompt': instance.customPrompt,
    };

SessionResponse _$SessionResponseFromJson(Map<String, dynamic> json) =>
    SessionResponse(
      roomName: json['roomName'] as String,
      url: json['url'] as String,
      token: json['token'] as String,
      mode: json['mode'] as String,
      tutorIdentity: json['tutorIdentity'] as String,
    );

Map<String, dynamic> _$SessionResponseToJson(SessionResponse instance) =>
    <String, dynamic>{
      'roomName': instance.roomName,
      'url': instance.url,
      'token': instance.token,
      'mode': instance.mode,
      'tutorIdentity': instance.tutorIdentity,
    };

TutorMode _$TutorModeFromJson(Map<String, dynamic> json) => TutorMode(
  id: json['id'] as String,
  label: json['label'] as String,
  description: json['description'] as String,
);

Map<String, dynamic> _$TutorModeToJson(TutorMode instance) => <String, dynamic>{
  'id': instance.id,
  'label': instance.label,
  'description': instance.description,
};

ModesResponse _$ModesResponseFromJson(Map<String, dynamic> json) =>
    ModesResponse(
      modes: (json['modes'] as List<dynamic>)
          .map((e) => TutorMode.fromJson(e as Map<String, dynamic>))
          .toList(),
    );

Map<String, dynamic> _$ModesResponseToJson(ModesResponse instance) =>
    <String, dynamic>{'modes': instance.modes};
