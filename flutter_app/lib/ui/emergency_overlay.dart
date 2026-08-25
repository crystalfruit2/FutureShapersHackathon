import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models.dart';
import 'theme.dart';

/// Full-screen takeover while an emergency is unacknowledged.
/// This IS the 3AM demo moment — phone lights up in the farmer's hand.
class EmergencyOverlay extends StatelessWidget {
  const EmergencyOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final gasEmerg = app.tel.v('gas') >= 700;
    final headline = gasEmerg
        ? 'Methane critical\nin the manure pit'
        : app.tel.v('flame') != 0
            ? 'Flame detected\nin the feed store'
            : 'Emergency at the farm';
    return Material(
      color: T.emergBg,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const SizedBox(height: 24),
            const Icon(Icons.emergency_outlined, color: T.danger, size: 48),
            const SizedBox(height: 20),
            Text(headline,
                style: const TextStyle(
                    fontSize: 32, fontWeight: FontWeight.w700,
                    color: Colors.white, height: 1.15, letterSpacing: -0.5)),
            const SizedBox(height: 10),
            const Text('The node acted on its own — you were asleep, it was not.',
                style: TextStyle(fontSize: 15, color: Color(0xFFE0B4B0))),
            const SizedBox(height: 28),
            const _Done('Gas valve closed'),
            const _Done('Exhaust fans purging'),
            const _Done('Vent flaps opened'),
            const _Done('Site siren sounding'),
            const SizedBox(height: 20),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: T.danger.withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: T.danger),
              ),
              child: const Row(children: [
                Icon(Icons.dangerous_outlined, color: Colors.white),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                      'DO NOT enter the pit to check on animals.\nMost manure-gas victims are rescuers.',
                      style: TextStyle(
                          color: Colors.white, fontWeight: FontWeight.w600, height: 1.3)),
                ),
              ]),
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: T.emergBg,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
                onPressed: () => context.read<AppState>().ackEmergency(),
                child: const Text('I understand — show me the farm',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class _Done extends StatelessWidget {
  final String text;
  const _Done(this.text);
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(children: [
          const Icon(Icons.check_circle, color: T.ok, size: 20),
          const SizedBox(width: 10),
          Text(text, style: const TextStyle(color: Colors.white, fontSize: 16)),
        ]),
      );
}

/// Purple toast for cyber events (replay attack rejected etc.) — a demo star.
class SecToast extends StatelessWidget {
  final StrajerEvent event;
  const SecToast({super.key, required this.event});

  @override
  Widget build(BuildContext context) {
    final label = humanEvent(event.parts.length > 1 ? event.parts[1] : event.raw);
    return Positioned(
      left: 16, right: 16, bottom: 84,
      child: Material(
        color: Colors.transparent,
        child: Dismissible(
          key: ValueKey(event.raw + event.time),
          onDismissed: (_) => context.read<AppState>().clearSecToast(),
          child: GestureDetector(
            onTap: () => context.read<AppState>().clearSecToast(),
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: T.surface2,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: T.cyber),
              ),
              child: Row(children: [
                const Icon(Icons.shield_outlined, color: T.cyber, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(label,
                        style: const TextStyle(
                            color: T.text, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 2),
                    Text(event.raw,
                        style: const TextStyle(
                            fontSize: 11, color: T.sub, fontFamily: 'Menlo')),
                  ]),
                ),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
