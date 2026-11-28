import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/dashboard_snapshot.dart';
import '../models/device_bulk_result.dart';
import '../models/device_state_result.dart';
import '../models/voice_command_result.dart';
import '../models/voice_response_result.dart';

class HomeApiException implements Exception {
  const HomeApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class HomeApi {
  HomeApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  int _requestCounter = 0;

  String _newRequestId() {
    final timestamp = DateTime.now().microsecondsSinceEpoch;
    return '$timestamp-${_requestCounter++}';
  }

  Future<DashboardSnapshot> fetchDashboard(String baseUrl) async {
    final response = await _client
        .get(Uri.parse('$baseUrl/dashboard'))
        .timeout(const Duration(seconds: 4));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HomeApiException('Máy chủ trả về lỗi ${response.statusCode}.');
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw const HomeApiException(
          'Dữ liệu tổng quan từ máy chủ không hợp lệ.');
    }
    return DashboardSnapshot.fromJson(decoded);
  }

  Future<DeviceStateResult> setDeviceState({
    required String baseUrl,
    required String deviceId,
    required bool isOn,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/devices/$deviceId/state'),
          headers: {
            'content-type': 'application/json',
            'X-Request-ID': _newRequestId(),
          },
          body: jsonEncode({'is_on': isOn}),
        )
        .timeout(const Duration(seconds: 5));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HomeApiException(
          'Máy chủ không thực hiện được lệnh (${response.statusCode}).');
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw const HomeApiException(
          'Phản hồi điều khiển từ máy chủ không hợp lệ.');
    }
    return DeviceStateResult.fromJson(decoded);
  }

  Future<DeviceBulkResult> setAllDeviceStates({
    required String baseUrl,
    required bool isOn,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/devices/state/all'),
          headers: {
            'content-type': 'application/json',
            'X-Request-ID': _newRequestId(),
          },
          body: jsonEncode({'is_on': isOn}),
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HomeApiException(
        'Máy chủ không điều khiển được tất cả thiết bị '
        '(${response.statusCode}).',
      );
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw const HomeApiException(
        'Phản hồi điều khiển hàng loạt không hợp lệ.',
      );
    }
    return DeviceBulkResult.fromJson(decoded);
  }

  Future<VoiceResponseResult> requestSensorSpeech({
    required String baseUrl,
    required String sensor,
  }) async {
    if (!const {'temperature', 'humidity', 'summary'}.contains(sensor)) {
      throw ArgumentError.value(sensor, 'sensor', 'Unsupported sensor type.');
    }
    final response = await _client.post(
      Uri.parse('$baseUrl/api/voice/response/sensors/$sensor'),
      headers: {'X-Request-ID': _newRequestId()},
    ).timeout(const Duration(seconds: 30));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HomeApiException(
        'Máy chủ không tạo được phản hồi giọng nói '
        '(${response.statusCode}).',
      );
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw const HomeApiException(
        'Phản hồi cảm biến bằng giọng nói không hợp lệ.',
      );
    }
    return VoiceResponseResult.fromJson(decoded);
  }

  Future<VoiceCommandResult> processTextCommand({
    required String baseUrl,
    required String text,
    required bool execute,
    String? requestId,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/voice/process'),
          headers: const {'content-type': 'application/json'},
          body: jsonEncode({
            'text': text,
            'execute': execute,
            'request_id': requestId ?? _newRequestId(),
          }),
        )
        .timeout(const Duration(seconds: 5));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HomeApiException(
        'Máy chủ không xử lý được câu lệnh (${response.statusCode}).',
      );
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw const HomeApiException('Phản hồi xử lý câu lệnh không hợp lệ.');
    }
    return VoiceCommandResult.fromJson(decoded);
  }

  void close() => _client.close();
}
