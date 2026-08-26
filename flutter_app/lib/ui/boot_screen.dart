/// Boot gate — the first 1.5 s of the app.
///
/// Two jobs, both for the stage: kill the white flash between the iOS launch
/// image and the first frame, and hold the shell back until the demo source
/// has produced telemetry, so the Farm tab never appears empty in front of a
/// jury. Falls through on a timeout — a slow source must never block launch.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../main.dart' show AppState;
import 'theme.dart';

/// Shows [BootScreen], then crossfades to [child] once the app has data.
class BootGate extends StatefulWidget {
  final Widget child;
  const BootGate({super.key, required this.child});

  /// Splash stays up at least this long even if data is instant — below this
  /// it reads as a glitch rather than a boot.
  static const minHold = Duration(milliseconds: 1500);

  /// Hard ceiling: no data by now and we launch anyway.
  static const maxHold = Duration(milliseconds: 3500);

  @override
  State<BootGate> createState() => _BootGateState();
}

class _BootGateState extends State<BootGate> {
  bool _ready = false;
  bool _minHoldPassed = false;
  bool _gone = false; // splash faded out and dropped from the tree

  static const _fade = Duration(milliseconds: 380);

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
    // populated by the time the splash fades off it. A Stack (not a switcher)
    // so both layers get the full screen, never a shrink-wrapped column.
    return Stack(
      fit: StackFit.expand,
      children: [
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
      ],
    );
  }
}

/// The splash itself. Same tokens as every other surface: one dark ground,
/// hairline borders, no gradients, no mascot.
class BootScreen extends StatefulWidget {
  final String status;
  const BootScreen({super.key, required this.status});

  @override
  State<BootScreen> createState() => _BootScreenState();
}

class _BootScreenState extends State<BootScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  )..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Scaffold(
      backgroundColor: T.bg,
      body: SafeArea(
        child: SizedBox(
          width: double.infinity,
          child: Column(
            children: [
              const Spacer(flex: 3),
              _Mark(pulse: _c),
              const SizedBox(height: 26),
              Text(
                'BioGuard',
                style: t.headlineMedium?.copyWith(
                  fontSize: 30,
                  letterSpacing: -0.8,
                ),
              ),
              const SizedBox(height: 6),
              Text('Ferma Străjer · Știuca, jud. Timiș', style: t.bodySmall),
              const SizedBox(height: 34),
              _Progress(_c),
              const SizedBox(height: 14),
              SizedBox(
                height: 18,
                child: Text(
                  widget.status,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                  style: t.labelSmall,
                ),
              ),
              const Spacer(flex: 4),
              Text('AUTONOMOUS FARM SAFETY', style: t.labelSmall),
              const SizedBox(height: 18),
            ],
          ),
        ),
      ),
    );
  }
}

/// 64 pt panel-square with the sensor glyph — echoes [Panel]'s geometry so the
/// splash and the app read as one system.
class _Mark extends StatelessWidget {
  final Animation<double> pulse;
  const _Mark({required this.pulse});

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: pulse,
    builder: (_, child) {
      // one slow breath per cycle, ±8 % on the ring only
      final a = 0.35 + 0.45 * (1 - (pulse.value * 2 - 1).abs());
      return Container(
        width: 64,
        height: 64,
        decoration: BoxDecoration(
          color: T.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: T.accent.withValues(alpha: a)),
        ),
        child: child,
      );
    },
    child: const Icon(Icons.sensors_rounded, color: T.accent, size: 30),
  );
}

/// 140 pt hairline track with a shuttling accent segment. Indeterminate on
/// purpose — we are waiting on a sensor stream, not a download.
class _Progress extends StatelessWidget {
  final Animation<double> c;
  const _Progress(this.c);

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 140,
    height: 2,
    child: ClipRRect(
      borderRadius: BorderRadius.circular(1),
      child: Stack(
        children: [
          Container(color: T.hairline),
          AnimatedBuilder(
            animation: c,
            builder: (context, _) {
              final v = Curves.easeInOut.transform(c.value);
              return Align(
                alignment: Alignment(-1 + 2 * v, 0),
                child: Container(width: 44, color: T.accent),
              );
            },
          ),
        ],
      ),
    ),
  );
}
