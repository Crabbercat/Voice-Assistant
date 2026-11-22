import 'dart:async';
import 'dart:ui';

import 'package:flutter/cupertino.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:viethome_frontend/models/dashboard_snapshot.dart';
import 'package:viethome_frontend/models/smart_device.dart';
import 'package:viethome_frontend/services/home_api.dart';

import '../widgets/fan_blades_icon.dart';
import '../widgets/fan_speed_card.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  static const Color _blue = Color(0xFF2196F3);
  static const Color _cyan = Color(0xFF00E5FF);
  static const Color _green = Color(0xFF00E676);
  static const Color _secondaryText = Color(0xFFB9C5D8);

  static const String _defaultUrl = 'http://127.0.0.1:8000';

  final HomeApi _homeApi = HomeApi();
  final TextEditingController _serverController =
      TextEditingController(text: _defaultUrl);

  String _backendBaseUrl = _defaultUrl;
  String _lastAction = 'Chưa có thao tác';

  bool _serverConnected = false;
  bool _savingServer = false;
  bool _readingDashboard = false;

  int _failedRequests = 0;
  int _selectedTab = 0;

  Timer? _statusTimer;

  double? _temperature;
  double? _humidity;

  List<SmartDevice> _devices = [];

  final List<String> _history = [];
  final Set<String> _pendingDevices = {};
  final Map<String, bool> _optimisticStates = {};

  @override
  void initState() {
    super.initState();
    _loadServerAddress();
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    _serverController.dispose();
    _homeApi.close();
    super.dispose();
  }

  Future<void> _loadServerAddress() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _backendBaseUrl = prefs.getString('backend_base_url') ?? _defaultUrl;
    } catch (error) {
      debugPrint('Load server error: $error');
    }

    if (!mounted) return;

    _serverController.text = _backendBaseUrl;

    await _fetchDashboard();

    if (!mounted) return;

    _statusTimer ??= Timer.periodic(
      const Duration(seconds: 1),
      (_) => _fetchDashboard(),
    );
  }

  String _normalizeServerUrl() {
    final raw = _serverController.text.trim();

    if (raw.isEmpty) {
      throw const FormatException('Chưa nhập địa chỉ Server.');
    }

    final normalized = raw.contains('://') ? raw : 'http://$raw';

    final uri = Uri.tryParse(normalized);

    if (uri == null ||
        uri.host.isEmpty ||
        !uri.hasAuthority ||
        (uri.scheme != 'http' && uri.scheme != 'https')) {
      throw const FormatException(
        'Địa chỉ Server không hợp lệ.',
      );
    }

    final port = uri.hasPort ? uri.port : 8000;

    if (port < 1 || port > 65535) {
      throw const FormatException('Cổng không hợp lệ.');
    }

    return Uri(
      scheme: uri.scheme,
      host: uri.host,
      port: port,
    ).toString();
  }

  Future<void> _saveServer() async {
    String address;

    try {
      address = _normalizeServerUrl();
    } on FormatException catch (error) {
      _showMessage(error.message, isError: true);
      return;
    }

    setState(() => _savingServer = true);

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('backend_base_url', address);

      if (!mounted) return;

      setState(() {
        _backendBaseUrl = address;
        _serverConnected = false;
        _failedRequests = 0;
        _devices = [];
        _temperature = null;
        _humidity = null;
      });

      await _fetchDashboard();

      if (!mounted) return;

      _showMessage(
        _serverConnected
            ? 'Đã kết nối Server thành công.'
            : 'Đã lưu địa chỉ. Đang kiểm tra kết nối.',
        isError: !_serverConnected,
      );
    } catch (error) {
      _showMessage(
        'Không thể lưu Server: $error',
        isError: true,
      );
    } finally {
      if (mounted) {
        setState(() => _savingServer = false);
      }
    }
  }

  Future<void> _fetchDashboard({
    bool reportErrors = false,
  }) async {
    if (_readingDashboard || _pendingDevices.isNotEmpty) {
      return;
    }

    _readingDashboard = true;
    final requestUrl = _backendBaseUrl;

    try {
      final DashboardSnapshot dashboard =
          await _homeApi.fetchDashboard(requestUrl);

      if (!mounted || requestUrl != _backendBaseUrl) {
        return;
      }

      _failedRequests = 0;

      setState(() {
        _serverConnected = true;
        _devices = dashboard.devices;
        _temperature = dashboard.temperature;
        _humidity = dashboard.humidity;
        _lastAction = dashboard.lastAction ?? 'Chưa có thao tác';
      });
    } catch (error) {
      if (!mounted || requestUrl != _backendBaseUrl) {
        return;
      }

      _failedRequests++;

      if (_failedRequests >= 3 && _serverConnected) {
        setState(() => _serverConnected = false);
      }

      if (reportErrors) {
        _showMessage(
          'Không thể cập nhật: $error',
          isError: true,
        );
      }
    } finally {
      _readingDashboard = false;
    }
  }

  Future<void> _toggleDevice(
    SmartDevice device,
    bool isOn,
  ) async {
    if (_pendingDevices.contains(device.deviceId)) {
      return;
    }

    final requestUrl = _backendBaseUrl;

    setState(() {
      _pendingDevices.add(device.deviceId);
      _optimisticStates[device.deviceId] = isOn;
    });

    try {
      final updated = await _homeApi.setDeviceState(
        baseUrl: requestUrl,
        deviceId: device.deviceId,
        isOn: isOn,
      );

      if (!mounted || requestUrl != _backendBaseUrl) {
        return;
      }

      setState(() {
        _devices = _devices
            .map(
              (item) => item.deviceId == updated.deviceId ? updated : item,
            )
            .toList(growable: false);
      });

      final action = device.deviceId == 'door'
          ? (updated.isOn ? 'Mở' : 'Đóng')
          : (updated.isOn ? 'Bật' : 'Tắt');

      _addHistory('$action ${device.name}');
    } catch (error) {
      if (mounted) {
        _showMessage(
          'Không gửi được lệnh: $error',
          isError: true,
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _pendingDevices.remove(device.deviceId);
          _optimisticStates.remove(device.deviceId);
        });

        _fetchDashboard();
      }
    }
  }

  void _addHistory(String action) {
    final now = DateTime.now();
    final time = '${now.hour.toString().padLeft(2, '0')}:'
        '${now.minute.toString().padLeft(2, '0')}';

    if (!mounted) return;

    setState(() {
      _history.insert(0, '$time  •  $action');
      if (_history.length > 30) {
        _history.removeLast();
      }
    });
  }

  void _showMessage(
    String message, {
    bool isError = false,
  }) {
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor:
            isError ? const Color(0xFF8F303C) : const Color(0xFF176B50),
        content: Text(message),
      ),
    );
  }

  String _formatValue(
    double? value,
    int decimals,
    String suffix,
  ) {
    if (value == null) return '—';
    return '${value.toStringAsFixed(decimals)}$suffix';
  }

  IconData _deviceIcon(SmartDevice device) {
    return switch (device.deviceId) {
      'light' => Icons.lightbulb_rounded,
      'door' => Icons.door_front_door_rounded,
      'light_bed' => Icons.nightlight_round,
      'fan' => Icons.air_rounded,
      _ => Icons.devices_other_rounded,
    };
  }

  Color _deviceColor(SmartDevice device) {
    return switch (device.deviceId) {
      'light' || 'light_bed' => const Color(0xFFFFCA28),
      'door' => const Color(0xFFFF9800),
      'fan' => const Color(0xFF29B6F6),
      _ => _cyan,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBody: true,
      body: Stack(
        fit: StackFit.expand,
        children: [
          const _DarkBackground(),
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1200),
              child: IndexedStack(
                index: _selectedTab,
                children: [
                  _buildDashboardPage(),
                  SafeArea(
                    bottom: false,
                    child: _buildHistoryPage(),
                  ),
                  SafeArea(
                    bottom: false,
                    child: _buildStatisticsPage(),
                  ),
                  SafeArea(
                    bottom: false,
                    child: _buildSettingsPage(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: _selectedTab == 3 ? null : _buildNavigationBar(),
    );
  }

  Widget _buildDashboardPage() {
    final topInset = MediaQuery.of(context).padding.top;
    final heroHeight = topInset + 270;

    return RefreshIndicator(
      color: _cyan,
      backgroundColor: const Color(0xFF14203A),
      edgeOffset: topInset,
      onRefresh: _fetchDashboard,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 120),
        physics: const BouncingScrollPhysics(
          parent: AlwaysScrollableScrollPhysics(),
        ),
        children: [
          Stack(
            children: [
              _buildHeroBanner(heroHeight),
              Padding(
                padding: EdgeInsets.fromLTRB(
                  20,
                  topInset + 10,
                  12,
                  0,
                ),
                child: _buildHeader(),
              ),
              Padding(
                padding: EdgeInsets.only(
                  top: heroHeight - 46,
                ),
                child: _buildSensorPanel(),
              ),
            ],
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              16,
              18,
              16,
              0,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _sectionTitle(
                  'Thiết bị trong nhà',
                  Icons.home_filled,
                ),
                const SizedBox(height: 14),
                _buildDeviceGrid(),
                const SizedBox(height: 16),
                _buildVoicePanel(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
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
                  color: _blue,
                  size: 46,
                  shadows: [
                    Shadow(
                      color: _blue.withValues(alpha: 0.8),
                      blurRadius: 16,
                    ),
                  ],
                ),
              ),
              const Align(
                alignment: Alignment.topRight,
                child: Icon(
                  Icons.wifi_rounded,
                  color: _cyan,
                  size: 18,
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
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                'Ngôi nhà thông minh của bạn',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
        IconButton(
          onPressed: () => setState(() => _selectedTab = 3),
          icon: const Icon(
            Icons.settings,
            color: Colors.white,
            size: 28,
          ),
        ),
      ],
    );
  }

  Widget _buildHeroBanner(double height) {
    const fadeColor = Color(0xFF040A18);

    return SizedBox(
      width: double.infinity,
      height: height,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset(
            'assets/images/smart_home_house.jpg',
            fit: BoxFit.cover,
            errorBuilder: (context, error, stackTrace) {
              return const ColoredBox(
                color: Color(0xFF071A3B),
              );
            },
          ),
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
                stops: [0, 0.48, 0.78, 1],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSensorPanel() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: _GlassPanel(
        padding: const EdgeInsets.symmetric(
          horizontal: 7,
          vertical: 14,
        ),
        borderRadius: 22,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            _SensorItem(
              icon: Icons.thermostat_rounded,
              color: const Color(0xFFFFB74D),
              value: _formatValue(_temperature, 1, '°C'),
              label: 'Nhiệt độ',
            ),
            _SensorItem(
              icon: Icons.water_drop_rounded,
              color: const Color(0xFF4FC3F7),
              value: _formatValue(_humidity, 0, '%'),
              label: 'Độ ẩm',
            ),
            Container(
              width: 1,
              height: 40,
              color: Colors.white24,
            ),
            Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 9,
                      height: 9,
                      decoration: BoxDecoration(
                        color: _serverConnected ? _green : Colors.redAccent,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      _serverConnected ? 'Online' : 'Offline',
                      style: TextStyle(
                        color: _serverConnected ? _green : Colors.redAccent,
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                const Text(
                  'Trạng thái',
                  style: TextStyle(
                    color: _secondaryText,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(
    String title,
    IconData icon,
  ) {
    return Row(
      children: [
        Icon(icon, color: _blue, size: 26),
        const SizedBox(width: 10),
        Text(
          title,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildDeviceGrid() {
    if (_devices.isEmpty) {
      return const _GlassPanel(
        child: Center(
          child: Text(
            'Chưa có thiết bị từ máy chủ.',
            style: TextStyle(color: _secondaryText),
          ),
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
        mainAxisExtent: 205,
      ),
      itemBuilder: (context, index) {
        final device = _devices[index];

        if (device.deviceId == 'fan') {
          return FanSpeedCard(
            key: const ValueKey('fan-speed-card'),
            baseUrl: _backendBaseUrl,
            name: device.name,
            room: device.room,
            initialIsOn: device.isOn,
            onStateChanged: _fetchDashboard,
          );
        }

        return SmartDeviceCard(
          name: device.name,
          room: device.room,
          icon: _deviceIcon(device),
          isActive: _optimisticStates[device.deviceId] ?? device.isOn,
          activeColor: _deviceColor(device),
          onChanged: _pendingDevices.contains(device.deviceId)
              ? null
              : (value) => _toggleDevice(device, value),
        );
      },
    );
  }

  Widget _buildVoicePanel() {
    return const _GlassPanel(
      padding: EdgeInsets.symmetric(
        horizontal: 16,
        vertical: 18,
      ),
      borderRadius: 22,
      child: Row(
        children: [
          Icon(
            Icons.mic_off_rounded,
            color: Colors.white54,
            size: 32,
          ),
          SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Điều khiển giọng nói chưa khả dụng',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                SizedBox(height: 5),
                Text(
                  'STT/TTS chưa được triển khai.',
                  style: TextStyle(
                    color: _secondaryText,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavigationBar() {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(26),
          child: BackdropFilter(
            filter: ImageFilter.blur(
              sigmaX: 20,
              sigmaY: 20,
            ),
            child: Container(
              height: 66,
              decoration: BoxDecoration(
                color: const Color(0xFF0D162B).withValues(alpha: 0.85),
                borderRadius: BorderRadius.circular(26),
                border: Border.all(
                  color: Colors.white.withValues(alpha: 0.12),
                ),
              ),
              child: Row(
                children: [
                  _navItem(0, Icons.home_rounded, 'Trang chủ'),
                  _navItem(1, Icons.history_rounded, 'Lịch sử'),
                  _navItem(2, Icons.bar_chart_rounded, 'Thống kê'),
                  _navItem(3, Icons.settings_rounded, 'Cài đặt'),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _navItem(
    int index,
    IconData icon,
    String label,
  ) {
    final selected = _selectedTab == index;
    final color = selected ? _blue : Colors.white60;

    return Expanded(
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => setState(() => _selectedTab = index),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 26, color: color),
            const SizedBox(height: 3),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 11.5,
                fontWeight: selected ? FontWeight.bold : FontWeight.w500,
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
        const Text(
          'Lịch sử',
          style: TextStyle(
            color: Colors.white,
            fontSize: 27,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 6),
        const Text(
          'Các thao tác điều khiển gần đây',
          style: TextStyle(
            color: _secondaryText,
            fontSize: 15,
          ),
        ),
        const SizedBox(height: 20),
        _GlassPanel(
          child: _history.isEmpty
              ? const Padding(
                  padding: EdgeInsets.symmetric(vertical: 24),
                  child: Center(
                    child: Text(
                      'Chưa có thao tác nào',
                      style: TextStyle(
                        color: _secondaryText,
                        fontSize: 15,
                      ),
                    ),
                  ),
                )
              : Column(
                  children: _history.map((item) {
                    return Padding(
                      padding: const EdgeInsets.symmetric(
                        vertical: 10,
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.check_circle_outline_rounded,
                            color: _cyan,
                            size: 22,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              item,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 14,
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                ),
        ),
        const SizedBox(height: 16),
        _refreshButton(),
      ],
    );
  }

  Widget _buildStatisticsPage() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 104),
      physics: const BouncingScrollPhysics(),
      children: [
        const Text(
          'Tổng quan',
          style: TextStyle(
            color: Colors.white,
            fontSize: 27,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 6),
        const Text(
          'Trạng thái hiện tại của ngôi nhà',
          style: TextStyle(
            color: _secondaryText,
            fontSize: 15,
          ),
        ),
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: _StatCard(
                icon: Icons.thermostat_rounded,
                label: 'Nhiệt độ',
                value: _formatValue(_temperature, 1, '°C'),
                color: const Color(0xFFFF9B72),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _StatCard(
                icon: Icons.water_drop_rounded,
                label: 'Độ ẩm',
                value: _formatValue(_humidity, 1, '%'),
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
              const Text(
                'Thiết bị',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 14),
              if (_devices.isEmpty)
                const Text(
                  'Chưa có thiết bị từ máy chủ.',
                  style: TextStyle(color: _secondaryText),
                )
              else
                ..._devices.map((device) {
                  final isOn = device.isOn;
                  final isDoor = device.deviceId == 'door';

                  return Padding(
                    padding: const EdgeInsets.symmetric(
                      vertical: 10,
                    ),
                    child: Row(
                      children: [
                        device.deviceId == 'fan'
                            ? const FanBladesIcon(size: 30)
                            : Icon(
                                _deviceIcon(device),
                                color: _deviceColor(device),
                                size: 30,
                              ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            device.name,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        Text(
                          isDoor
                              ? (isOn ? 'Đang mở' : 'Đã đóng')
                              : (isOn ? 'Đang bật' : 'Đã tắt'),
                          style: TextStyle(
                            color: isOn ? _green : _secondaryText,
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
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
              const Text(
                'Hoạt động gần nhất',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                _lastAction,
                style: const TextStyle(
                  color: _secondaryText,
                  fontSize: 15,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _refreshButton(),
      ],
    );
  }

  Widget _refreshButton() {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: OutlinedButton.icon(
        onPressed: () => _fetchDashboard(reportErrors: true),
        icon: const Icon(Icons.refresh_rounded),
        label: const Text(
          'Cập nhật trạng thái',
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
        style: OutlinedButton.styleFrom(
          foregroundColor: _cyan,
          side: BorderSide(
            color: _cyan.withValues(alpha: 0.55),
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
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
              icon: const Icon(
                Icons.arrow_back_ios_new_rounded,
                color: Colors.white,
              ),
            ),
            const Expanded(
              child: Center(
                child: Text(
                  'Cài đặt',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
            IconButton(
              onPressed: () => setState(() => _selectedTab = 0),
              icon: const Icon(
                Icons.home_outlined,
                color: _cyan,
                size: 28,
              ),
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
                  Icon(
                    Icons.wifi_rounded,
                    color: _cyan,
                    size: 38,
                  ),
                  SizedBox(width: 14),
                  Expanded(
                    child: Text(
                      'Địa chỉ backend',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 19,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              const Text(
                'Nhập địa chỉ IP Raspberry Pi để điều khiển thiết bị.',
                style: TextStyle(
                  color: _secondaryText,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                height: 56,
                child: TextField(
                  controller: _serverController,
                  maxLines: 1,
                  expands: false,
                  keyboardType: TextInputType.url,
                  textInputAction: TextInputAction.done,
                  cursorColor: _cyan,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                  ),
                  decoration: InputDecoration(
                    hintText: 'http://192.168.1.100:8000',
                    hintStyle: const TextStyle(
                      color: Color(0xFF8494AD),
                      fontSize: 14,
                    ),
                    filled: true,
                    fillColor: const Color(0xFF101E35),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 15,
                      vertical: 15,
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(
                        color: Color(0xFF344867),
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(
                        color: _cyan,
                        width: 1.5,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              SizedBox(
                height: 52,
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _savingServer ? null : _saveServer,
                  icon: _savingServer
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.save_rounded),
                  label: const Text(
                    'Lưu',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  style: FilledButton.styleFrom(
                    backgroundColor: _blue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        _GlassPanel(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Thông tin ứng dụng',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              _infoRow('Phiên bản', 'v1.0.0'),
              const SizedBox(height: 12),
              _infoRow('Nhà phát triển', 'Smart Home Team'),
              const SizedBox(height: 12),
              _infoRow(
                'Trạng thái kết nối',
                _serverConnected ? 'Online' : 'Offline',
                color: _serverConnected ? _green : Colors.orangeAccent,
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        _GlassPanel(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Hỗ trợ',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              _supportRow(
                'Hướng dẫn sử dụng',
                _showHelpDialog,
              ),
              _supportRow(
                'Liên hệ',
                _showContactDialog,
              ),
            ],
          ),
        ),
        if (!kIsWeb) ...[
          const SizedBox(height: 22),
          SizedBox(
            height: 50,
            child: OutlinedButton.icon(
              onPressed: SystemNavigator.pop,
              icon: const Icon(
                Icons.logout_rounded,
                color: Color(0xFFFF696F),
              ),
              label: const Text(
                'Thoát ứng dụng',
                style: TextStyle(
                  color: Color(0xFFFF696F),
                ),
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _infoRow(
    String label,
    String value, {
    Color? color,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: _secondaryText,
            fontSize: 13,
          ),
        ),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.end,
            style: TextStyle(
              color: color ?? Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }

  Widget _supportRow(
    String label,
    VoidCallback onTap,
  ) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                ),
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              color: _secondaryText,
            ),
          ],
        ),
      ),
    );
  }

  void _showHelpDialog() {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: const Color(0xFF172746),
        title: const Text(
          'Hướng dẫn sử dụng',
          style: TextStyle(color: Colors.white),
        ),
        content: const Text(
          '1. Kết nối điện thoại với mạng có thể truy cập Raspberry Pi.\n'
          '2. Chạy backend FastAPI trên Raspberry Pi.\n'
          '3. Nhập địa chỉ IP và cổng 8000 trong Cài đặt.\n'
          '4. Nhấn Lưu và điều khiển thiết bị.',
          style: TextStyle(
            color: Colors.white,
            height: 1.5,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Đóng'),
          ),
        ],
      ),
    );
  }

  void _showContactDialog() {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: const Color(0xFF172746),
        title: const Text(
          'Liên hệ',
          style: TextStyle(color: Colors.white),
        ),
        content: const Text(
          'Smart Home Team\n'
          'Ứng dụng điều khiển nhà thông minh trong mạng nội bộ.',
          style: TextStyle(color: Colors.white),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Đóng'),
          ),
        ],
      ),
    );
  }
}

class _SensorItem extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String value;
  final String label;

  const _SensorItem({
    required this.icon,
    required this.color,
    required this.value,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          icon,
          size: 32,
          color: color,
        ),
        const SizedBox(width: 5),
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 15,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: const TextStyle(
                color: Color(0xFFB9C5D8),
                fontSize: 11,
              ),
            ),
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

  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 36),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              color: Color(0xFFB9C5D8),
              fontSize: 15,
              fontWeight: FontWeight.w500,
            ),
          ),
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
      padding: const EdgeInsets.fromLTRB(14, 14, 12, 14),
      borderRadius: 20,
      active: isActive,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                icon,
                color: activeColor,
                size: 49,
                shadows: isActive
                    ? [
                        Shadow(
                          color: activeColor.withValues(
                            alpha: 0.75,
                          ),
                          blurRadius: 15,
                        ),
                      ]
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
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 17,
              height: 1.2,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 5),
          Row(
            children: [
              Expanded(
                child: Text(
                  room,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xFFB9C5D8),
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const Icon(
                Icons.arrow_forward_ios_rounded,
                color: Colors.white60,
                size: 14,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _DarkBackground extends StatelessWidget {
  const _DarkBackground();

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
                  colors: [
                    const Color(0xFF00E5FF).withValues(alpha: 0.15),
                    Colors.transparent,
                  ],
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
                  colors: [
                    const Color(0xFF1E88E5).withValues(alpha: 0.15),
                    Colors.transparent,
                  ],
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
        filter: ImageFilter.blur(
          sigmaX: 15,
          sigmaY: 15,
        ),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: active
                ? const Color(0xFF19325B).withValues(alpha: 0.6)
                : const Color(0xFF111C33).withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(
              color: active
                  ? const Color(0xFF1E88E5).withValues(alpha: 0.5)
                  : Colors.white.withValues(alpha: 0.08),
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
