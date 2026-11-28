import 'voice_response_result.dart';

class DeviceBulkResult {
  const DeviceBulkResult({
    required this.success,
    required this.partial,
    required this.isOn,
    required this.resultCount,
    this.voiceResponse,
  });

  final bool success;
  final bool partial;
  final bool isOn;
  final int resultCount;
  final VoiceResponseResult? voiceResponse;

  factory DeviceBulkResult.fromJson(Map<String, dynamic> json) {
    final results = json['results'];
    final response = json['voice_response'];
    if (results is! List) {
      throw const FormatException('Kết quả điều khiển hàng loạt không hợp lệ.');
    }

    return DeviceBulkResult(
      success: json['success'] as bool,
      partial: json['partial'] as bool,
      isOn: json['is_on'] as bool,
      resultCount: results.length,
      voiceResponse: response is Map<String, dynamic>
          ? VoiceResponseResult.fromJson(response)
          : null,
    );
  }
}
