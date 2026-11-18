import 'dart:async';
import 'dart:ui';

import 'package:cupertino_ui/cupertino_ui.dart';
import 'package:flutter/foundation.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:viethome_frontend/models/dashboard_snapshot.dart';
import 'package:viethome_frontend/models/smart_device.dart';
import 'package:viethome_frontend/services/home_api.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  static const Color _blueActive = Color(0xFF2196F3);
  static const Color _greenOnline = Color(0xFF00E676);
  static const Color _cyan = Color(0xFF00E5FF);
  static const String _defaultBackendUrl = 'http://127.0.0.1:8000';

  final HomeApi _homeApi = HomeApi();
  String _backendBaseUrl = _defaultBackendUrl;
  final TextEditingController _serverAddressController =
      TextEditingController(text: _defaultBackendUrl);

  bool _serverConnected = false;
  bool _isSavingServer = false;
  int _selectedTab = 0;
  String _lastAction = 'Chưa có thao tác';
  Timer? _statusTimer;

  final List<String> _activityHistory = [];
  final Set<String> _pendingDevices = {};
  List<SmartDevice> _devices = [];
  double? _temperature;
  double? _humidity;

  @override
  void initState() {
    super.initState();
    _loadServerAddress();
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    _serverAddressController.dispose();
    _homeApi.close();
    super.dispose();
  }

  Future<void> _loadServerAddress() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _backendBaseUrl = prefs.getString('backend_base_url') ??
          _backendBaseUrl;
    } catch (error) {
      debugPrint('Cannot load saved server URL: $error');
    }
    _serverAddressController.text = _backendBaseUrl;
    if (!mounted) return;
    await _fetchStatusAndUpdate();
    _statusTimer ??= Timer.periodic(const Duration(seconds: 5), (_) => _fetchStatusAndUpdate());
  }

  String _buildServerUrl() {
    final rawAddress = _serverAddressController.text.trim();
    if (rawAddress.isEmpty) throw const FormatException('Bạn chưa nhập địa chỉ Server.');
    final normalized = rawAddress.contains('://') ? rawAddress : 'http://$rawAddress';
    final parsed = Uri.tryParse(normalized);
    if (parsed == null || parsed.host.isEmpty || !parsed.hasAuthority) {
      throw const FormatException('Địa chỉ Server không hợp lệ.');
    }
    if (parsed.scheme != 'http' && parsed.scheme != 'https') {
      throw const FormatException('Server chỉ hỗ trợ địa chỉ HTTP hoặc HTTPS.');
    }
    final port = parsed.hasPort ? parsed.port : 8000;
    if (port < 1 || port > 65535) {
      throw const FormatException('Cổng phải nằm trong khoảng 1–65535.');
    }
    return Uri(scheme: parsed.scheme, host: parsed.host, port: port).toString();
  }

  Future<void> _saveServerAddress() async {
    String address;
    try {
      address = _buildServerUrl();
    } on FormatException catch (error) {
      _showErrorSnackBar(error.message);
      return;
    }
    setState(() => _isSavingServer = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('backend_base_url', address);
      if (!mounted) return;
      setState(() => _backendBaseUrl = address);
      await _fetchStatusAndUpdate();
      if (_serverConnected) {
        _showSuccessSnackBar('Đã lưu và kết nối Server thành công.');
      } else {
        _showErrorSnackBar('Đã lưu địa chỉ, nhưng chưa kết nối được Server.');
      }
    } catch (error) {
      _showErrorSnackBar('Không thể lưu địa chỉ Server: $error');
    } finally {
      if (mounted) setState(() => _isSavingServer = false);
    }
  }

  Future<void> _fetchStatusAndUpdate({bool reportErrors = false}) async {
    try {
      final DashboardSnapshot dashboard = await _homeApi.fetchDashboard(_backendBaseUrl);
      if (!mounted) return;
      setState(() {
        _serverConnected = true;
        _devices = dashboard.devices;
        _temperature = dashboard.temperature;
        _humidity = dashboard.humidity;
        _lastAction = dashboard.lastAction ?? 'Chưa có thao tác';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _serverConnected = false);
      if (reportErrors) {
        _showErrorSnackBar('Không thể cập nhật dữ liệu: $error');
      }
    }
  }

  Future<void> _toggleDeviceManually(SmartDevice device, bool value) async {
    if (_pendingDevices.contains(device.deviceId)) return;
    setState(() => _pendingDevices.add(device.deviceId));
    try {
      final updated = await _homeApi.setDeviceState(
        baseUrl: _backendBaseUrl,
        deviceId: device.deviceId,
        isOn: value,
      );
      if (!mounted) return;
      setState(() {
        _devices = _devices
            .map((current) => current.deviceId == updated.deviceId ? updated : current)
            .toList(growable: false);
      });
      _addActivity('${_actionLabel(device, updated.isOn)} ${device.name}');
      await _fetchStatusAndUpdate();
    } catch (error) {
      if (mounted) {
        setState(() => _serverConnected = false);
        _showErrorSnackBar('Không gửi được lệnh: $error');
      }
    } finally {
      if (mounted) setState(() => _pendingDevices.remove(device.deviceId));
    }
  }

  String _actionLabel(SmartDevice device, bool isOn) {
    if (device.deviceId == 'door') return isOn ? 'Mở' : 'Đóng';
    return isOn ? 'Bật' : 'Tắt';
  }

  void _addActivity(String message) {
    if (!mounted) return;
    final now = DateTime.now();
    final time = '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
    setState(() {
      _activityHistory.insert(0, '$time  •  $message');
      if (_activityHistory.length > 30) _activityHistory.removeLast();
    });
  }

  void _showErrorSnackBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: const Color(0xFF8F303C), content: Text(message)));
  }

  void _showSuccessSnackBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: const Color(0xFF176B50), content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final isSettingsPage = _selectedTab == 3;

    return Scaffold(
      extendBody: true,
      body: Stack(
        fit: StackFit.expand,
        children: [
          const _AbstractDarkBackground(),
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1200),
              child: IndexedStack(
                index: _selectedTab,
                children: <Widget>[
                  _buildDashboardPage(),
                  SafeArea(bottom: false, child: _buildHistoryPage()),
                  SafeArea(bottom: false, child: _buildStatisticsPage()),
                  SafeArea(bottom: false, child: _buildSettingsPage()),
                ],
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: isSettingsPage ? null : _buildBottomNavigationBar(),
    );
  }

  Widget _buildDashboardPage() {
    final topInset = MediaQuery.of(context).padding.top;
    final heroHeight = topInset + 270;

    return RefreshIndicator(
      color: _cyan,
      backgroundColor: const Color(0xFF14203A),
      edgeOffset: topInset,
      onRefresh: _fetchStatusAndUpdate,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 120),
        physics: const BouncingScrollPhysics(
          parent: AlwaysScrollableScrollPhysics(),
        ),
        children: [
          // Ảnh ngôi nhà tràn lên sát mép trên, tiêu đề nằm đè lên ảnh,
          // bảng cảm biến đè lên phần mờ dần ở đáy ảnh.
          Stack(
            children: [
              _buildHeroImageBanner(heroHeight),
              Padding(
                padding: EdgeInsets.fromLTRB(20, topInset + 10, 12, 0),
                child: _buildTopHeaderBar(),
              ),
              Padding(
                padding: EdgeInsets.only(top: heroHeight - 46),
                child: _buildSensorGlassPanel(),
              ),
            ],
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildSectionTitle('Thiết bị trong nhà', Icons.home_filled),
                const SizedBox(height: 12),
                _buildDeviceGrid(),
                const SizedBox(height: 14),
                _buildVoiceControlPanel(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopHeaderBar() {
    const textShadow = [Shadow(color: Colors.black87, blurRadius: 10)];
    return Row(
      children: [
        SizedBox(
          width: 58,
          height: 52,
          child: Stack(
            children: [
              Align(
                alignment: Alignment.bottomLeft,
                child: Icon(
                  Icons.home_outlined,
                  color: _blueActive,
                  size: 46,
                  shadows: [Shadow(color: _blueActive.withValues(alpha: 0.9), blurRadius: 16)],
                ),
              ),
              Align(
                alignment: Alignment.topRight,
                child: Icon(
                  Icons.wifi_rounded,
                  color: _cyan,
                  size: 18,
                  shadows: [Shadow(color: _cyan.withValues(alpha: 0.9), blurRadius: 10)],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 12),
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Smart Home',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                  letterSpacing: 0.3,
                  shadows: textShadow,
                ),
              ),
              Text(
                'Ngôi nhà thông minh của bạn',
                style: TextStyle(fontSize: 13, color: Colors.white, shadows: textShadow),
              ),
            ],
          ),
        ),
        IconButton(
          onPressed: () => setState(() => _selectedTab = 3),
          icon: const Icon(Icons.settings, color: Colors.white, size: 28, shadows: textShadow),
        ),
      ],
    );
  }

  Widget _buildHeroImageBanner(double height) {
    const Color fadeColor = Color(0xFF040A18);

    return SizedBox(
      height: height,
      width: double.infinity,
      child: Stack(
        fit: StackFit.expand,
        children: [
          // Ảnh phủ toàn bộ khu vực đầu trang, kể cả phía sau thanh tiêu đề.
          // Không để lộ nền cũ ở phía trên nên sẽ không còn đường ranh hai màu.
          Image.asset(
            'assets/images/smart_home_house.jpg',
            fit: BoxFit.cover,
            alignment: Alignment.center,
            errorBuilder: (context, error, stackTrace) {
              return const DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Color(0xFF071A3B), fadeColor],
                  ),
                ),
              );
            },
          ),
          // Lớp phủ mỏng giúp chữ/icon dễ đọc; chỉ phần đáy mới mờ hẳn
          // về đúng màu nền của ứng dụng để hòa với nội dung bên dưới.
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0x33020817),
                  Color(0x10020817),
                  Color(0x66020817),
                  fadeColor,
                ],
                stops: [0.0, 0.48, 0.78, 1.0],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSensorGlassPanel() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: _GlassPanel(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 6),
        borderRadius: 22,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            _SensorItem(
              icon: Icons.thermostat_rounded,
              iconColor: const Color(0xFFFFB74D),
              value: _formatMeasurement(_temperature, 1, '°C'),
              label: 'Nhiệt độ',
            ),
            _SensorItem(
              icon: Icons.water_drop_rounded,
              iconColor: const Color(0xFF4FC3F7),
              value: _formatMeasurement(_humidity, 0, '%'),
              label: 'Độ ẩm',
            ),
            Container(width: 1, height: 40, color: Colors.white24),
            Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        color: _serverConnected ? _greenOnline : Colors.redAccent,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: (_serverConnected ? _greenOnline : Colors.redAccent).withValues(alpha: 0.5),
                            blurRadius: 6,
                            spreadRadius: 1,
                          )
                        ],
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      _serverConnected ? 'Online' : 'Offline',
                      style: TextStyle(
                        color: _serverConnected ? _greenOnline : Colors.redAccent,
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                const Text('Trạng thái', style: TextStyle(color: Colors.white70, fontSize: 12)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, color: _blueActive, size: 24),
        const SizedBox(width: 10),
        Text(title, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildDeviceGrid() {
    if (_devices.isEmpty) {
      return const _GlassPanel(
        child: Center(
          child: Text('Chưa có thiết bị từ máy chủ.', style: TextStyle(color: Colors.white60)),
        ),
      );
    }

    return GridView.builder(
      shrinkWrap: true,
      padding: EdgeInsets.zero,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _devices.length,
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 300,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        childAspectRatio: 1.4,
      ),
      itemBuilder: (context, index) {
        final device = _devices[index];
        return SmartDeviceCard(
          name: device.name,
          room: device.room,
          icon: _iconFor(device),
          isActive: device.isOn,
          activeColor: _colorFor(device),
          onChanged: _pendingDevices.contains(device.deviceId)
              ? null
              : (value) => _toggleDeviceManually(device, value),
        );
      },
    );
  }

  Widget _buildVoiceControlPanel() {
    return const _GlassPanel(
      padding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
      borderRadius: 22,
      child: Row(
        children: [
          Icon(Icons.mic_off_rounded, color: Colors.white54, size: 32),
          SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Điều khiển giọng nói chưa khả dụng',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                ),
                SizedBox(height: 4),
                Text(
                  'STT/TTS chưa được triển khai trong giai đoạn này.',
                  style: TextStyle(fontSize: 12, color: Colors.white70),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  IconData _iconFor(SmartDevice device) {
    return switch (device.deviceId) {
      'light' => Icons.lightbulb_rounded,
      'door' => Icons.door_front_door_rounded,
      'light_bed' => Icons.bed_rounded,
      'fan' => Icons.toys_rounded,
      _ => Icons.devices_other_rounded,
    };
  }

  Color _colorFor(SmartDevice device) {
    return switch (device.deviceId) {
      'light' || 'light_bed' => const Color(0xFFFFCA28),
      'door' => const Color(0xFFFF9800),
      'fan' => const Color(0xFF29B6F6),
      _ => _cyan,
    };
  }

  String _formatMeasurement(double? value, int fractionDigits, String unit) {
    if (value == null) return '—';
    return '${value.toStringAsFixed(fractionDigits)}$unit';
  }

  Widget _buildBottomNavigationBar() {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(26),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
            child: Container(
              height: 66,
              decoration: BoxDecoration(
                color: const Color(0xFF0D162B).withValues(alpha: 0.85),
                borderRadius: BorderRadius.circular(26),
                border: Border.all(color: Colors.white.withValues(alpha: 0.12), width: 1),
              ),
              child: Row(
                children: [
                  _buildNavItem(0, Icons.home_rounded, 'Trang chủ'),
                  _buildNavItem(1, Icons.history_rounded, 'Lịch sử'),
                  _buildNavItem(2, Icons.bar_chart_rounded, 'Thống kê'),
                  _buildNavItem(3, Icons.settings_rounded, 'Cài đặt'),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem(int index, IconData icon, String label) {
    final isSelected = _selectedTab == index;
    final color = isSelected ? _blueActive : Colors.white60;
    return Expanded(
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => setState(() => _selectedTab = index),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              color: color,
              size: 26,
              shadows: isSelected ? [Shadow(color: _blueActive.withValues(alpha: 0.7), blurRadius: 10)] : null,
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 11.5,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHistoryPage() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 110),
      physics: const BouncingScrollPhysics(),
      children: [
        const Text('Lịch sử', style: TextStyle(fontSize: 25, fontWeight: FontWeight.bold)),
        const SizedBox(height: 5),
        const Text('Các thao tác điều khiển gần đây', style: TextStyle(color: Colors.white70)),
        const SizedBox(height: 20),
        _GlassPanel(
          child: _activityHistory.isEmpty
              ? const Padding(
                  padding: EdgeInsets.symmetric(vertical: 24),
                  child: Center(
                    child: Column(
                      children: [
                        Icon(Icons.history_rounded, size: 42, color: Colors.white38),
                        SizedBox(height: 10),
                        Text('Chưa có thao tác nào', style: TextStyle(color: Colors.white60)),
                      ],
                    ),
                  ),
                )
              : Column(
                  children: _activityHistory.map((entry) {
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.check_circle_outline_rounded, color: _cyan, size: 20),
                          const SizedBox(width: 11),
                          Expanded(child: Text(entry, style: const TextStyle(color: Colors.white, height: 1.35))),
                        ],
                      ),
                    );
                  }).toList(),
                ),
        ),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: () => _fetchStatusAndUpdate(reportErrors: true),
          icon: const Icon(Icons.refresh_rounded),
          label: const Text('Cập nhật trạng thái'),
          style: OutlinedButton.styleFrom(
            foregroundColor: _cyan,
            side: BorderSide(color: _cyan.withValues(alpha: 0.55)),
            padding: const EdgeInsets.symmetric(vertical: 13),
          ),
        ),
      ],
    );
  }

  Widget _buildStatisticsPage() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 104),
      physics: const BouncingScrollPhysics(),
      children: [
        const Text('Tổng quan', style: TextStyle(fontSize: 25, fontWeight: FontWeight.bold)),
        const SizedBox(height: 5),
        const Text('Trạng thái hiện tại của ngôi nhà', style: TextStyle(color: Colors.white70)),
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: _StatCard(
                icon: Icons.thermostat_rounded,
                label: 'Nhiệt độ',
                value: _formatMeasurement(_temperature, 1, '°C'),
                color: const Color(0xFFFF9B72),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _StatCard(
                icon: Icons.water_drop_rounded,
                label: 'Độ ẩm',
                value: _formatMeasurement(_humidity, 1, '%'),
                color: _cyan,
              ),
            ),
          ],
        ),
        const SizedBox(height: 18),
        _GlassPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Thiết bị', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              if (_devices.isEmpty)
                const Text('Chưa có thiết bị từ máy chủ.', style: TextStyle(color: Colors.white60))
              else
                ..._devices.map((device) {
                  final isDoor = device.deviceId == 'door';
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 9),
                    child: Row(
                      children: [
                        Icon(_iconFor(device), color: _colorFor(device), size: 23),
                        const SizedBox(width: 12),
                        Expanded(child: Text(device.name)),
                        Text(
                          isDoor
                              ? (device.isOn ? 'Đang mở' : 'Đã đóng')
                              : (device.isOn ? 'Đang bật' : 'Đã tắt'),
                          style: TextStyle(
                            color: device.isOn ? _greenOnline : Colors.white60,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  );
                }),
            ],
          ),
        ),
        const SizedBox(height: 18),
        _GlassPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Hoạt động gần nhất', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
              const SizedBox(height: 10),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.history_rounded, color: _cyan),
                  const SizedBox(width: 10),
                  Expanded(child: Text(_lastAction, style: const TextStyle(color: Colors.white70))),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        OutlinedButton.icon(
          onPressed: () => _fetchStatusAndUpdate(reportErrors: true),
          icon: const Icon(Icons.refresh_rounded),
          label: const Text('Cập nhật trạng thái'),
          style: OutlinedButton.styleFrom(
            foregroundColor: _cyan,
            side: BorderSide(color: _cyan.withValues(alpha: 0.6)),
            padding: const EdgeInsets.symmetric(vertical: 13),
          ),
        ),
      ],
    );
  }

  Widget _buildSettingsPage() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      physics: const BouncingScrollPhysics(),
      children: [
        Row(
          children: [
            IconButton(
              onPressed: () => setState(() => _selectedTab = 0),
              icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white),
              tooltip: 'Quay lại',
            ),
            const Expanded(
              child: Center(
                child: Text('Cài đặt', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
              ),
            ),
            IconButton(
              onPressed: () => setState(() => _selectedTab = 0),
              icon: const Icon(Icons.home_outlined, color: _cyan, size: 27),
              tooltip: 'Trang chủ',
            ),
          ],
        ),
        const SizedBox(height: 24),
        _GlassPanel(
          padding: const EdgeInsets.all(18),
          borderRadius: 24,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.wifi_rounded, color: _cyan, size: 40),
                  SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Địa chỉ backend', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                        SizedBox(height: 4),
                        Text(
                          'Nhập địa chỉ máy tính chạy VietHome-AI API',
                          style: TextStyle(fontSize: 12, color: Colors.white70),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _serverAddressController,
                keyboardType: TextInputType.url,
                style: const TextStyle(color: Colors.white, fontSize: 15),
                decoration: InputDecoration(
                  hintText: 'http://127.0.0.1:8000',
                  hintStyle: const TextStyle(color: Colors.white38, fontSize: 14),
                  filled: true,
                  fillColor: const Color(0x990A1530),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.17)),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: _cyan, width: 1.3),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton.icon(
                  onPressed: _isSavingServer ? null : _saveServerAddress,
                  icon: _isSavingServer
                      ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.save_rounded, size: 22),
                  label: const Text('Lưu', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  style: FilledButton.styleFrom(
                    backgroundColor: _blueActive,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        _GlassPanel(
          padding: const EdgeInsets.all(18),
          borderRadius: 24,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.info_rounded, color: _cyan, size: 26),
                  SizedBox(width: 12),
                  Text('Thông tin ứng dụng', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 16),
              _infoRow('Phiên bản', 'v1.0.0'),
              const SizedBox(height: 10),
              _infoRow('Nhà phát triển', 'Smart Home Team'),
              const SizedBox(height: 10),
              _infoRow(
                'Trạng thái kết nối',
                _serverConnected ? 'Online' : 'Offline',
                valueColor: _serverConnected ? _greenOnline : Colors.orangeAccent,
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        _GlassPanel(
          padding: const EdgeInsets.all(18),
          borderRadius: 24,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.help_rounded, color: _cyan, size: 26),
                  SizedBox(width: 12),
                  Text('Hỗ trợ', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 12),
              _supportRow('Hướng dẫn sử dụng', _showHelpDialog),
              _supportRow('Liên hệ', _showContactDialog),
            ],
          ),
        ),
        if (!kIsWeb) ...[
          const SizedBox(height: 22),
          SizedBox(
            height: 52,
            child: OutlinedButton.icon(
              onPressed: SystemNavigator.pop,
              icon: const Icon(Icons.logout_rounded, color: Color(0xFFFF696F)),
              label: const Text('Thoát ứng dụng', style: TextStyle(color: Color(0xFFFF696F), fontSize: 16)),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: Color(0x886A344A)),
                backgroundColor: const Color(0x332F1728),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _supportRow(String title, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 4),
        child: Row(
          children: [
            Expanded(child: Text(title, style: const TextStyle(fontSize: 14, color: Colors.white))),
            const Icon(Icons.chevron_right_rounded, color: Colors.white54, size: 24),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value, {Color? valueColor}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: Colors.white70, fontSize: 13)),
        Text(value, style: TextStyle(color: valueColor ?? Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
      ],
    );
  }

  void _showHelpDialog() {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF172746),
        title: const Text('Hướng dẫn sử dụng'),
        content: const Text(
          '1. Kết nối điện thoại và máy tính cùng mạng Wi-Fi.\n'
          '2. Chạy VietHome-AI API trên máy tính.\n'
          '3. Nhập địa chỉ máy tính và cổng backend (mặc định 8000) trong Cài đặt.\n'
          '4. Nhấn Lưu, sau đó sử dụng các nút trên trang tổng quan để điều khiển thiết bị.\n'
          'Điều khiển giọng nói chưa khả dụng trong giai đoạn này.',
          style: TextStyle(height: 1.5),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Đóng'))],
      ),
    );
  }

  void _showContactDialog() {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF172746),
        title: const Text('Liên hệ'),
        content: const Text('Smart Home Team\nỨng dụng điều khiển nhà thông minh trong mạng nội bộ.'),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Đóng'))],
      ),
    );
  }
}

class _SensorItem extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String value;
  final String label;

  const _SensorItem({required this.icon, required this.iconColor, required this.value, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          icon,
          color: iconColor,
          size: 34,
          shadows: [Shadow(color: iconColor.withValues(alpha: 0.6), blurRadius: 10)],
        ),
        const SizedBox(width: 6),
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Colors.white)),
            const SizedBox(height: 2),
            Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
          ],
        ),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _StatCard({required this.icon, required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 27),
          const SizedBox(height: 13),
          Text(value, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
        ],
      ),
    );
  }
}

class SmartDeviceCard extends StatelessWidget {
  final String name;
  final String room;
  final IconData icon;
  final bool isActive;
  final Color activeColor;
  final ValueChanged<bool>? onChanged;

  const SmartDeviceCard({
    super.key,
    required this.name,
    required this.room,
    required this.icon,
    required this.isActive,
    required this.activeColor,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
      borderRadius: 20,
      active: isActive,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Icon luôn giữ màu riêng của thiết bị, chỉ phát sáng khi đang bật.
              Icon(
                icon,
                color: activeColor,
                size: 36,
                shadows: isActive
                    ? [Shadow(color: activeColor.withValues(alpha: 0.8), blurRadius: 14)]
                    : null,
              ),
              Transform.scale(
                scale: 0.8,
                alignment: Alignment.topRight,
                child: CupertinoSwitch(
                  value: isActive,
                  onChanged: onChanged,
                  activeTrackColor: const Color(0xFF2196F3),
                  inactiveTrackColor: const Color(0xFF4A5568),
                ),
              ),
            ],
          ),
          const Spacer(),
          Text(
            name,
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Colors.white),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Row(
            children: [
              Expanded(
                child: Text(
                  room,
                  style: const TextStyle(fontSize: 12, color: Colors.white70),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Icon(Icons.arrow_forward_ios_rounded, color: Colors.white70, size: 13),
            ],
          ),
        ],
      ),
    );
  }
}

class _AbstractDarkBackground extends StatelessWidget {
  const _AbstractDarkBackground();

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF040A18),
      child: Stack(
        children: [
          Positioned(
            top: -100,
            right: -100,
            child: Container(
              width: 400,
              height: 400,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [const Color(0xFF00E5FF).withValues(alpha: 0.15), Colors.transparent],
                ),
              ),
            ),
          ),
          Positioned(
            bottom: -50,
            left: -100,
            child: Container(
              width: 350,
              height: 350,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [const Color(0xFF1E88E5).withValues(alpha: 0.15), Colors.transparent],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _GlassPanel extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final bool active;

  const _GlassPanel({
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius = 18,
    this.active = false,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: active ? const Color(0xFF19325B).withValues(alpha: 0.6) : const Color(0xFF111C33).withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(
              color: active ? const Color(0xFF1E88E5).withValues(alpha: 0.5) : Colors.white.withValues(alpha: 0.08),
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.2),
                blurRadius: 20,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: child,
        ),
      ),
    );
  }
}
