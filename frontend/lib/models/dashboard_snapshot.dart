import 'smart_device.dart';

class DashboardSnapshot {
  const DashboardSnapshot({
    required this.devices,
    required this.temperature,
    required this.humidity,
    required this.lastAction,
  });

  final List<SmartDevice> devices;
  final double? temperature;
  final double? humidity;
  final String? lastAction;

  factory DashboardSnapshot.fromJson(Map<String, dynamic> json) {
    final devicesJson = json['devices'];
    final sensorsJson = json['sensors'];
    if (devicesJson is! List || sensorsJson is! Map<String, dynamic>) {
      throw const FormatException('Dữ liệu tổng quan từ máy chủ không hợp lệ.');
    }

    return DashboardSnapshot(
      devices: devicesJson.map((device) {
        if (device is! Map<String, dynamic>) {
          throw const FormatException('Dữ liệu thiết bị từ máy chủ không hợp lệ.');
        }
        return SmartDevice.fromJson(device);
      }).toList(growable: false),
      temperature: _readMeasurement(sensorsJson['temperature']),
      humidity: _readMeasurement(sensorsJson['humidity']),
      lastAction: json['last_action'] is String ? json['last_action'] as String : null,
    );
  }

  static double? _readMeasurement(Object? value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    throw const FormatException('Dữ liệu cảm biến từ máy chủ không hợp lệ.');
  }
}
