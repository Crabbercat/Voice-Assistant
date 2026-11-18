class SmartDevice {
  const SmartDevice({
    required this.deviceId,
    required this.name,
    required this.room,
    required this.isOn,
  });

  final String deviceId;
  final String name;
  final String room;
  final bool isOn;

  factory SmartDevice.fromJson(Map<String, dynamic> json) {
    final deviceId = json['device_id'];
    final name = json['name'];
    final isOn = json['is_on'];

    if (deviceId is! String || name is! String || isOn is! bool) {
      throw const FormatException('Dữ liệu thiết bị từ máy chủ không hợp lệ.');
    }

    return SmartDevice(
      deviceId: deviceId,
      name: name,
      room: json['room'] is String ? json['room'] as String : 'Nhà',
      isOn: isOn,
    );
  }
}
