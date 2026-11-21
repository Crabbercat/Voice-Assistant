import 'dart:math' as math;

import 'package:flutter/widgets.dart';

class FanBladesIcon extends StatelessWidget {
  final double size;
  final Color color;

  const FanBladesIcon({
    super.key,
    this.size = 46,
    this.color = const Color(0xFF29B6F6),
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _FanBladesPainter(color),
      ),
    );
  }
}

class _FanBladesPainter extends CustomPainter {
  final Color color;

  const _FanBladesPainter(this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final radius = size.shortestSide / 2;

    canvas.translate(size.width / 2, size.height / 2);

    final bladePaint = Paint()
      ..color = color
      ..style = PaintingStyle.fill
      ..isAntiAlias = true;

    for (int i = 0; i < 3; i++) {
      canvas.save();
      canvas.rotate(i * 2 * math.pi / 3);

      final blade = Path()
        ..moveTo(-0.08 * radius, -0.12 * radius)
        ..cubicTo(
          0.30 * radius,
          -0.18 * radius,
          0.56 * radius,
          -0.58 * radius,
          0.43 * radius,
          -0.87 * radius,
        )
        ..cubicTo(
          0.13 * radius,
          -1.02 * radius,
          -0.26 * radius,
          -0.73 * radius,
          -0.19 * radius,
          -0.15 * radius,
        )
        ..close();

      canvas.drawPath(blade, bladePaint);
      canvas.restore();
    }

    canvas.drawCircle(
      Offset.zero,
      radius * 0.17,
      Paint()..color = const Color(0xFF19325B),
    );

    canvas.drawCircle(
      Offset.zero,
      radius * 0.08,
      bladePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _FanBladesPainter oldDelegate) {
    return oldDelegate.color != color;
  }
}
