import 'dart:async';
import 'dart:convert';
import 'dart:ui';

import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'fan_blades_icon.dart';

class FanSpeedCard extends StatefulWidget {
  final String baseUrl;
  final String name;
  final String room;
  final bool initialIsOn;
  final VoidCallback? onStateChanged;

  const FanSpeedCard({
    super.key,
    required this.baseUrl,
    this.name = 'Quạt phòng ngủ',
    this.room = 'Phòng ngủ',
    this.initialIsOn = false,
    this.onStateChanged,
  });

  @override
  State<FanSpeedCard> createState() => _FanSpeedCardState();
}

class _FanSpeedCardState extends State<FanSpeedCard> {
  final http.Client _client = http.Client();

  static const Color blue = Color(0xFF2196F3);
  static const Color cyan = Color(0xFF29B6F6);

  Timer? _timer;
  int? _level;
  int _revision = 0;
  bool _sending = false;
  bool _reading = false;

  String get _apiUrl {
    final base = widget.baseUrl.replaceAll(
      RegExp(r'/+$'),
      '',
    );
    return '$base/devices/fan/speed';
  }

  @override
  void initState() {
    super.initState();

    _getSpeed();

    _timer = Timer.periodic(
      const Duration(seconds: 5),
      (_) => _getSpeed(),
    );
  }

  @override
  void didUpdateWidget(covariant FanSpeedCard oldWidget) {
    super.didUpdateWidget(oldWidget);

    if (oldWidget.baseUrl != widget.baseUrl) {
      _revision++;
      _level = null;
      _getSpeed();
    }
  }

  Future<void> _getSpeed() async {
    if (_reading || _sending) return;

    _reading = true;
    final revision = _revision;
    final url = _apiUrl;

    try {
      final response =
          await _client.get(Uri.parse(url)).timeout(const Duration(seconds: 4));

      if (response.statusCode != 200) {
        throw Exception('HTTP ${response.statusCode}');
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;

      final newLevel = (data['speed_level'] as num).toInt();

      if (newLevel < 0 || newLevel > 3) {
        throw const FormatException(
          'Invalid fan speed level',
        );
      }

      if (!mounted || _sending || revision != _revision) {
        return;
      }

      setState(() {
        _level = newLevel;
      });
    } catch (error) {
      debugPrint('Fan status error: $error');
    } finally {
      _reading = false;
    }
  }

  Future<void> _setSpeed(int newLevel) async {
    if (_sending || newLevel < 0 || newLevel > 3) {
      return;
    }

    final oldLevel = _level;
    final revision = ++_revision;
    final url = _apiUrl;

    setState(() {
      _level = newLevel;
      _sending = true;
    });

    try {
      final response = await _client
          .post(
            Uri.parse(url),
            headers: {
              'Content-Type': 'application/json',
            },
            body: jsonEncode({
              'level': newLevel,
            }),
          )
          .timeout(const Duration(seconds: 5));

      if (response.statusCode != 200) {
        throw Exception('HTTP ${response.statusCode}');
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;

      final confirmedLevel = (data['speed_level'] as num).toInt();

      if (confirmedLevel < 0 || confirmedLevel > 3) {
        throw const FormatException(
          'Invalid fan speed level',
        );
      }

      if (!mounted || revision != _revision) return;

      setState(() {
        _level = confirmedLevel;
      });

      widget.onStateChanged?.call();
    } catch (error) {
      if (!mounted || revision != _revision) return;

      setState(() {
        _level = oldLevel;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Không điều khiển được quạt: $error',
          ),
          backgroundColor: const Color(0xFF8F303C),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _sending = false;
        });
      }
    }
  }

  Widget _speedButton(int speed) {
    final selected = _level == speed;

    return Expanded(
      child: Padding(
        padding: EdgeInsets.only(
          right: speed == 3 ? 0 : 5,
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(10),
            onTap: _sending ? null : () => _setSpeed(speed),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              height: 35,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: selected ? blue : const Color(0xFF243550),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: selected
                      ? const Color(0xFF64C9FF)
                      : const Color(0xFF3B5276),
                  width: selected ? 1.4 : 0.8,
                ),
                boxShadow: selected
                    ? [
                        BoxShadow(
                          color: blue.withValues(alpha: 0.35),
                          blurRadius: 8,
                        ),
                      ]
                    : null,
              ),
              child: Text(
                '$speed',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 17,
                  fontWeight: selected ? FontWeight.bold : FontWeight.w600,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    _client.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isOn = _level == null ? widget.initialIsOn : _level! > 0;

    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: 15,
          sigmaY: 15,
        ),
        child: Container(
          padding: const EdgeInsets.fromLTRB(
            14,
            12,
            12,
            12,
          ),
          decoration: BoxDecoration(
            color: isOn
                ? const Color(0xFF19325B).withValues(alpha: 0.6)
                : const Color(0xFF111C33).withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isOn
                  ? blue.withValues(alpha: 0.5)
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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const FanBladesIcon(
                    size: 49,
                    color: cyan,
                  ),
                  Transform.scale(
                    scale: 0.8,
                    alignment: Alignment.topRight,
                    child: CupertinoSwitch(
                      value: isOn,
                      onChanged: _sending
                          ? null
                          : (value) => _setSpeed(
                                value ? 1 : 0,
                              ),
                      activeTrackColor: blue,
                      inactiveTrackColor: const Color(0xFF4A5568),
                    ),
                  ),
                ],
              ),
              const Spacer(),
              Text(
                widget.name,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 17,
                  height: 1.15,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      widget.room,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                        color: Color(0xFFB9C5D8),
                      ),
                    ),
                  ),
                  const SizedBox(width: 3),
                  Text(
                    _level == null
                        ? '--'
                        : _level == 0
                            ? 'Đã tắt'
                            : 'Cấp $_level',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: isOn ? cyan : Colors.white60,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 9),
              Row(
                children: [
                  _speedButton(1),
                  _speedButton(2),
                  _speedButton(3),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
