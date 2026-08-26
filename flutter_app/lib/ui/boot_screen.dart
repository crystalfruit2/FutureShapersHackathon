/// Boot gate — the first seconds of the app.
///
/// Two jobs, both for the stage: cover the gap between the iOS launch image
/// and the first Flutter frame, and hold the shell back until the demo source
/// has produced telemetry, so the Farm tab never appears empty in front of a
/// jury. Falls through on a timeout — a slow source must never block launch.
///
/// The look is deliberately the pixel language of the attract loop, not the
/// instrument-dark language of the app: the wordmark here is the very sprite
/// `attract/sprites/wordmark.png` the pitch video opens on, so the phone picks
/// up exactly where the screen left off. The app itself stays dark and quiet.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../main.dart' show AppState;

/// Splash-only palette. Deliberately NOT in [T] — nothing else in the app is
/// allowed to drift into these colours.
abstract final class _P {
  static const parchment = Color(0xFFF2E5C0);
  static const tile = Color(0xFFEDE1BB);
  static const crop = Color(0xFFE8DAAF);
  static const ink = Color(0xFF1A1512);
  static const brown = Color(0xFF6C4214);
  static const gold = Color(0xFFC9A227);
  static const empty = Color(0xFFDCD8CE);
  static const card = Color(0xFFFDFBF4);
}

const _mono = 'Menlo';
const _monoFallback = ['Courier New', 'Courier', 'monospace'];

/// Shows [BootScreen] over the shell, then fades it off once the app has data.
class BootGate extends StatefulWidget {
  final Widget child;
  const BootGate({super.key, required this.child});

  /// Splash stays up at least this long even if data is instant — below this
  /// it reads as a glitch rather than a boot.
  static const minHold = Duration(milliseconds: 2600);

  /// Hard ceiling: no data by now and we launch anyway.
  static const maxHold = Duration(milliseconds: 5000);

  @override
  State<BootGate> createState() => _BootGateState();
}

class _BootGateState extends State<BootGate> {
  bool _ready = false;
  bool _minHoldPassed = false;
  bool _gone = false; // splash faded out and dropped from the tree

  // long enough that parchment → near-black does not read as a flash
  static const _fade = Duration(milliseconds: 520);

  @override
  void initState() {
    super.initState();
    Future.delayed(BootGate.minHold, () {
      if (mounted) setState(() => _minHoldPassed = true);
    });
    Future.delayed(BootGate.maxHold, () {
      if (mounted) setState(() => _ready = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final hasData = app.tel.ch.isNotEmpty;
    final show = !(_ready || (_minHoldPassed && hasData));

    // The shell builds underneath from the first frame — it is warm and fully
    // populated by the time the splash lifts off it.
    return Stack(fit: StackFit.expand, children: [
      widget.child,
      if (!_gone)
        IgnorePointer(
          child: AnimatedOpacity(
            opacity: show ? 1 : 0,
            duration: _fade,
            curve: Curves.easeInOut,
            onEnd: () {
              if (!show && mounted) setState(() => _gone = true);
            },
            child: BootScreen(status: app.connDetail),
          ),
        ),
    ]);
  }
}

class BootScreen extends StatefulWidget {
  /// The live source description, shown once the bar is full.
  final String status;
  const BootScreen({super.key, required this.status});

  @override
  State<BootScreen> createState() => _BootScreenState();
}

class _BootScreenState extends State<BootScreen>
    with SingleTickerProviderStateMixin {
  static const _cells = 10;

  /// One line per pair of cells. The cyber line is not decoration — the
  /// signed command chain is the thing the pitch is built on.
  static const _phases = [
    'Waking sensors…',
    'Initializing farm grid…',
    'Linking zones…',
    'Verifying command chain…',
    'Farm online.',
  ];

  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: BootGate.minHold,
  )..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // parchment ground needs dark status-bar glyphs, or the clock vanishes
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.dark.copyWith(
        statusBarColor: Colors.transparent,
        statusBarBrightness: Brightness.light, // iOS: light background
        statusBarIconBrightness: Brightness.dark, // Android
      ),
      child: Scaffold(
        backgroundColor: _P.parchment,
        body: SizedBox.expand(
          child: CustomPaint(
            painter: _FieldPainter(),
            child: SafeArea(
              child: Stack(children: [
                Center(
                  child: AnimatedBuilder(
                    animation: _c,
                    builder: (context, _) {
                      final filled = (_c.value * _cells).floor().clamp(0, _cells);
                      final phase =
                          _phases[(filled ~/ 2).clamp(0, _phases.length - 1)];
                      final done = filled >= _cells;
                      return Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const _IconCard(),
                          const SizedBox(height: 30),
                          Image.asset('assets/splash/wordmark.png',
                              width: 236, filterQuality: FilterQuality.none),
                          const SizedBox(height: 36),
                          _SegmentBar(filled: filled, cells: _cells),
                          const SizedBox(height: 16),
                          SizedBox(
                            height: 18,
                            child: Text(
                              done ? widget.status : phase,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                fontFamily: _mono,
                                fontFamilyFallback: _monoFallback,
                                fontSize: 13,
                                color: _P.brown,
                                letterSpacing: 0.2,
                              ),
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                ),
                const Positioned(right: 18, bottom: 16, child: _VersionBadge()),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

/// The app icon in a bordered card with a hard offset shadow — the same
/// chunky-outline treatment as the segmented bar, so the two read as one kit.
class _IconCard extends StatelessWidget {
  const _IconCard();

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 168,
        height: 168,
        child: Stack(children: [
          Positioned(
            left: 7,
            top: 7,
            child: Container(
              width: 161,
              height: 161,
              decoration: BoxDecoration(
                color: _P.ink,
                borderRadius: BorderRadius.circular(22),
              ),
            ),
          ),
          Container(
            width: 161,
            height: 161,
            decoration: BoxDecoration(
              color: _P.card,
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: _P.ink, width: 5),
            ),
            padding: const EdgeInsets.all(9),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(13),
              // nearest-neighbour: this is pixel art, it must not be smoothed
              child: Image.asset('assets/icon/icon.png',
                  filterQuality: FilterQuality.none, fit: BoxFit.cover),
            ),
          ),
        ]),
      );
}

/// Ten chunky cells in a hard-outlined track. Discrete, not a smooth sweep —
/// a smooth bar would read as a web spinner, this reads as a machine booting.
class _SegmentBar extends StatelessWidget {
  final int filled;
  final int cells;
  const _SegmentBar({required this.filled, required this.cells});

  @override
  Widget build(BuildContext context) {
    final w = math.min(320.0, MediaQuery.sizeOf(context).width - 56);
    return Container(
      width: w,
      height: 46,
      decoration: BoxDecoration(
        color: _P.card,
        border: Border.all(color: _P.ink, width: 4),
      ),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: List.generate(cells * 2 - 1, (i) {
          if (i.isOdd) return const SizedBox(width: 3);
          final on = i ~/ 2 < filled;
          return Expanded(
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 140),
              color: on ? _P.gold : _P.empty,
            ),
          );
        }),
      ),
    );
  }
}

class _VersionBadge extends StatelessWidget {
  const _VersionBadge();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(10, 5, 10, 5),
        decoration: BoxDecoration(
          color: _P.parchment,
          border: Border.all(color: _P.ink, width: 3),
        ),
        child: const Text('v1.0-DEMO',
            style: TextStyle(
              fontFamily: _mono,
              fontFamilyFallback: _monoFallback,
              fontSize: 12,
              color: _P.brown,
              letterSpacing: 0.5,
            )),
      );
}

/// Faded top-down tilled field: a 26 px grid with a sparse, deterministic
/// scatter of crop marks. Painted rather than shipped as an image so it tiles
/// at any screen size and costs nothing to download.
class _FieldPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = _P.parchment);

    const step = 26.0;
    final line = Paint()
      ..color = _P.tile
      ..strokeWidth = 1;
    for (double x = 0; x < size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), line);
    }
    for (double y = 0; y < size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), line);
    }

    // seeded so the field is identical on every launch — no shimmer between
    // rebuilds, and screenshots of the splash are reproducible
    final rnd = math.Random(7);
    final crop = Paint()..color = _P.crop;
    final cols = (size.width / step).ceil();
    final rows = (size.height / step).ceil();
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        if (rnd.nextInt(9) != 0) continue;
        final ox = c * step + 8;
        final oy = r * step + 8;
        canvas.drawRect(Rect.fromLTWH(ox + 3, oy, 3, 9), crop);
        canvas.drawRect(Rect.fromLTWH(ox, oy + 6, 9, 3), crop);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _FieldPainter oldDelegate) => false;
}
