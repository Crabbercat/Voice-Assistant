import 'smart_device.dart';
import 'voice_response_result.dart';

class DeviceStateResult {
  const DeviceStateResult({
    required this.device,
    this.voiceResponse,
  });

  final SmartDevice device;
  final VoiceResponseResult? voiceResponse;

  factory DeviceStateResult.fromJson(Map<String, dynamic> json) {
    final response = json['voice_response'];
    return DeviceStateResult(
      device: SmartDevice.fromJson(json),
      voiceResponse: response is Map<String, dynamic>
          ? VoiceResponseResult.fromJson(response)
          : null,
    );
  }
}
