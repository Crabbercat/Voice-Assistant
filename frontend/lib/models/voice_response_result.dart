class VoiceResponseResult {
  const VoiceResponseResult({
    required this.requestId,
    required this.status,
    required this.responseMode,
    required this.audioPlayed,
    this.responseKey,
    this.text,
    this.audioPath,
    this.error,
    this.data,
  });

  final String requestId;
  final String status;
  final String responseMode;
  final bool audioPlayed;
  final String? responseKey;
  final String? text;
  final String? audioPath;
  final String? error;
  final Map<String, dynamic>? data;

  factory VoiceResponseResult.fromJson(Map<String, dynamic> json) {
    return VoiceResponseResult(
      requestId: json['request_id'] as String,
      status: json['status'] as String,
      responseMode: json['response_mode'] as String,
      audioPlayed: json['audio_played'] as bool,
      responseKey: json['response_key'] as String?,
      text: json['text'] as String?,
      audioPath: json['audio_path'] as String?,
      error: json['error'] as String?,
      data: json['data'] as Map<String, dynamic>?,
    );
  }
}
