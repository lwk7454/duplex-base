import 'package:flutter/material.dart';
import 'dart:math' as math;

class WaveformPainter extends CustomPainter {
  final List<double> amplitudes;
  final Color color;
  final double animationValue;

  WaveformPainter({
    required this.amplitudes,
    required this.color,
    required this.animationValue,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke;

    final path = Path();
    final width = size.width;
    final height = size.height;
    final centerY = height / 2;

    if (amplitudes.isEmpty) {
      // Draw flat line when no audio
      canvas.drawLine(
        Offset(0, centerY),
        Offset(width, centerY),
        paint,
      );
      return;
    }

    final step = width / (amplitudes.length - 1);
    final animatedIndex = (amplitudes.length * animationValue).floor();

    for (int i = 0; i < amplitudes.length && i <= animatedIndex; i++) {
      final x = i * step;
      final amplitude = amplitudes[i] * (1 - animationValue * 0.3); // Decay effect
      final y = centerY + (amplitude * height / 2);

      if (i == 0) {
        path.moveTo(x, y);
      } else {
        // Smooth curve using quadratic bezier
        final prevX = (i - 1) * step;
        final prevAmplitude = amplitudes[i - 1] * (1 - animationValue * 0.3);
        final prevY = centerY + (prevAmplitude * height / 2);

        final cpX = (prevX + x) / 2;
        path.quadraticBezierTo(cpX, prevY, cpX, y);
        path.lineTo(x, y);
      }
    }

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(WaveformPainter oldDelegate) {
    return oldDelegate.animationValue != animationValue ||
        oldDelegate.amplitudes != amplitudes;
  }
}

class WaveformWidget extends StatefulWidget {
  final List<double> amplitudes;
  final Color? color;

  const WaveformWidget({
    super.key,
    required this.amplitudes,
    this.color,
  });

  @override
  State<WaveformWidget> createState() => _WaveformWidgetState();
}

class _WaveformWidgetState extends State<WaveformWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 100),
    );
    _controller.forward();
  }

  @override
  void didUpdateWidget(WaveformWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.amplitudes != widget.amplitudes) {
      _controller.reset();
      _controller.forward();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return CustomPaint(
          size: const Size(double.infinity, 100),
          painter: WaveformPainter(
            amplitudes: widget.amplitudes,
            color: widget.color ?? Theme.of(context).colorScheme.primary,
            animationValue: _controller.value,
          ),
        );
      },
    );
  }
}
