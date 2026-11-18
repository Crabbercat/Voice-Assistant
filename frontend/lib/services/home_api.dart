import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/dashboard_snapshot.dart';
import '../models/smart_device.dart';

class HomeApiException implements Exception {
  const HomeApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class HomeApi {
  HomeApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<DashboardSnapshot> fetchDashboard(String baseUrl) async {
    final response = await _client
        .get(Uri.parse('$baseUrl/dashboard'))
        .timeout(const Duration(seconds: 4));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HomeApiException('Máy chủ trả về lỗi ${response.statusCode}.');
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw const HomeApiException('Dữ liệu tổng quan từ máy chủ không hợp lệ.');
    }
    return DashboardSnapshot.fromJson(decoded);
  }

  Future<SmartDevice> setDeviceState({
    required String baseUrl,
    required String deviceId,
    required bool isOn,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/devices/$deviceId/state'),
          headers: const {'content-type': 'application/json'},
          body: jsonEncode({'is_on': isOn}),
        )
        .timeout(const Duration(seconds: 5));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HomeApiException('Máy chủ không thực hiện được lệnh (${response.statusCode}).');
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw const HomeApiException('Phản hồi điều khiển từ máy chủ không hợp lệ.');
    }
    return SmartDevice.fromJson(decoded);
  }

  void close() => _client.close();
}
