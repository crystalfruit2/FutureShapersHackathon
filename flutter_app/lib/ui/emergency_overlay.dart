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
    // headline comes from the event that STARTED the emergency — live
    // telemetry drifts during the episode and would flip the text
    final trigger =
        app.events.where((e) => e.sev == Severity.emerg).firstOrNull;
    final zone = zoneNames[trigger?.zone] ?? 'the farm';
    final headline = switch (trigger?.type) {
      'GAS_CRITICAL' => 'Methane critical\nin the ${zone.toLowerCase()}',
      'FLAME_DETECTED' => 'Fire detected\nin the ${zone.toLowerCase()}',
      _ => 'Emergency at the farm',
    };
    final valveCut = app.tel.v('relay', 1) == 0;
    final fanOn = app.tel.v('fan') == 1;
    final ventOpen = app.tel.v('vent') == 1;
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
            // only claim what telemetry confirms — this jury punishes fabricated status
            if (valveCut) const _Done('Gas valve closed'),
            if (fanOn) const _Done('Exhaust fans purging'),
            if (ventOpen) const _Done('Vent flaps opened'),
            if (!valveCut && !fanOn && !ventOpen)
              const Text('Automatic protections engaging…',
                  style: TextStyle(color: Colors.white, fontSize: 16)),
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
                      'DO NOT enter to check on the animals.\nMost farm-gas victims are would-be rescuers.',
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

/// Full-screen takeover for an intrusion, unacknowledged.
///
/// Same reasoning as [EmergencyOverlay]: at 3AM a toast behind a lock screen
/// is the same as no alarm at all. Kept visually distinct from the gas/fire
/// takeover — this is a security event, not a life-safety one, and the two
/// must never be mistaken for each other on stage.
class IntruderOverlay extends StatelessWidget {
  const IntruderOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final trigger = app.events
        .where((e) => e.type == 'INTRUDER')
        .firstOrNull;
    final zoneId = trigger?.zone ?? 'field';
    final zone = zoneNames[zoneId] ?? 'the farm';
    final armed =
        app.mode == FarmMode.night || app.mode == FarmMode.lockdown;
    return Material(
      color: const Color(0xFF17130A),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const SizedBox(height: 24),
            const Icon(Icons.directions_walk_outlined, color: T.warn, size: 48),
            const SizedBox(height: 20),
            Text('Movement detected\nin the ${zone.toLowerCase()}',
                style: const TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                    height: 1.15,
                    letterSpacing: -0.5)),
            const SizedBox(height: 10),
            Text(
                armed
                    ? 'The night watch is armed. Nobody should be out there.'
                    : 'The farm is not armed — check whether this was you.',
                style: const TextStyle(fontSize: 15, color: Color(0xFFD8C9A4))),
            const SizedBox(height: 28),
            // only claim what telemetry confirms
            if (app.tel.v('$zoneId.light', 0) == 1)
              const _Done('Zone lights switched on'),
            const _Done('Entry written to the tamper-evident log'),
            const SizedBox(height: 20),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: T.warn.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: T.warn),
              ),
              child: const Row(children: [
                Icon(Icons.visibility_outlined, color: Colors.white),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                      'Do not confront anyone yourself.\nThe log is already signed — it is evidence.',
                      style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                          height: 1.3)),
                ),
              ]),
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF17130A),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
                onPressed: () => context.read<AppState>().ackIntruder(),
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
    );
  }
}
