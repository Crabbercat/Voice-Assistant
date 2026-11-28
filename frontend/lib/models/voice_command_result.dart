import 'voice_response_result.dart';

class VoiceCommandResult {
  const VoiceCommandResult({
    required this.accepted,
    required this.reason,
    required this.recognizedText,
    required this.message,
    required this.executionStatus,
    this.intent,
    this.action,
    this.deviceId,
    this.confidence,
    this.execution,
    this.voiceResponse,
  });

  final bool accepted;
  final String reason;
  final String recognizedText;
  final String message;
  final String executionStatus;
  final String? intent;
  final String? action;
  final String? deviceId;
  final double? confidence;
  final Map<String, dynamic>? execution;
  final VoiceResponseResult? voiceResponse;

  factory VoiceCommandResult.fromJson(Map<String, dynamic> json) {
    final response = json['voice_response'];
    return VoiceCommandResult(
      accepted: json['accepted'] as bool,
      reason: json['reason'] as String,
      recognizedText: json['recognized_text'] as String,
      message: json['message'] as String,
      executionStatus: json['execution_status'] as String,
      intent: json['intent'] as String?,
      action: json['action'] as String?,
      deviceId: json['device_id'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      execution: json['execution'] as Map<String, dynamic>?,
      voiceResponse: response is Map<String, dynamic>
          ? VoiceResponseResult.fromJson(response)
          : null,
    );
  }
}
