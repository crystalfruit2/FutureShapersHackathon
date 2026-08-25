/// Design tokens — one restrained dark system, iOS-native feel.
/// System font (SF Pro on iOS). One semantic color set, no gradients.
library;

import 'package:flutter/material.dart';

abstract final class T {
  // neutrals
  static const bg = Color(0xFF0F1113);
  static const surface = Color(0xFF16191C);
  static const surface2 = Color(0xFF1D2125);
  static const hairline = Color(0xFF2A2F34);
  static const text = Color(0xFFECEFF1);
  static const sub = Color(0xFF98A1A8);
  // semantics
  static const ok = Color(0xFF30D158);
  static const warn = Color(0xFFFFB020);
  static const danger = Color(0xFFFF453A);
  static const cyber = Color(0xFFBF5AF2);
  static const accent = Color(0xFF0A84FF);

  static const emergBg = Color(0xFF1C0B0B);

  static ThemeData theme() => ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: bg,
        colorScheme: const ColorScheme.dark(
          primary: accent,
          surface: surface,
          error: danger,
        ),
        splashFactory: NoSplash.splashFactory,
        segmentedButtonTheme: SegmentedButtonThemeData(
          style: ButtonStyle(
            backgroundColor: WidgetStateProperty.resolveWith((st) =>
                st.contains(WidgetState.selected) ? surface2 : Colors.transparent),
            foregroundColor: WidgetStateProperty.resolveWith((st) =>
                st.contains(WidgetState.selected) ? text : sub),
            iconColor: WidgetStateProperty.resolveWith((st) =>
                st.contains(WidgetState.selected) ? accent : sub),
            side: const WidgetStatePropertyAll(BorderSide(color: hairline)),
          ),
        ),
        dividerColor: hairline,
        textTheme: const TextTheme(
          headlineMedium: TextStyle(
              fontSize: 26, fontWeight: FontWeight.w600, color: text, letterSpacing: -0.5),
          titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: text),
          bodyMedium: TextStyle(fontSize: 15, color: text, height: 1.35),
          bodySmall: TextStyle(fontSize: 13, color: sub, height: 1.3),
          labelSmall: TextStyle(
              fontSize: 11.5, color: sub, fontWeight: FontWeight.w600, letterSpacing: 0.8),
        ),
      );
}

/// Section label: small caps, quiet.
class SectionLabel extends StatelessWidget {
  final String text;
  const SectionLabel(this.text, {super.key});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 22, 4, 8),
        child: Text(text.toUpperCase(), style: Theme.of(context).textTheme.labelSmall),
      );
}

/// Standard card: surface, hairline border, 16 radius. No shadows.
class Panel extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final Color? borderColor;
  const Panel({super.key, required this.child,
      this.padding = const EdgeInsets.all(16), this.borderColor});
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: padding,
        decoration: BoxDecoration(
          color: T.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: borderColor ?? T.hairline),
        ),
        child: child,
      );
}

class StatusDot extends StatelessWidget {
  final Color color;
  final double size;
  const StatusDot(this.color, {super.key, this.size = 10});
  @override
  Widget build(BuildContext context) => Container(
      width: size, height: size,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle));
}

class SimBadge extends StatelessWidget {
  const SimBadge({super.key});
  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(left: 6),
        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
        decoration: BoxDecoration(
          border: Border.all(color: T.cyber.withValues(alpha: 0.6)),
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Text('SIM',
            style: TextStyle(fontSize: 9, color: T.cyber, fontWeight: FontWeight.w700)),
      );
}

/// Human copy for protocol event types — the farmer never reads EVT| lines.
String humanEvent(String type) => switch (type) {
      'GAS_CRITICAL' => 'Methane critical in the poultry hall',
      'GAS_HIGH' => 'Methane rising in the poultry hall',
      'GAS_CLEARED' => 'Air is clear again',
      'FLAME_DETECTED' => 'Fire detected in the storage room',
      'INTRUDER' => 'Movement detected in the field',
      'CABINET_OPENED' => 'Control cabinet was opened',
      'DISTRESS_SOUND' => 'Unusual noise in the poultry hall',
      'WATER_LOW' => 'Drinking water running low',
      'WATER_REFILLED' => 'Water supply refilled',
      'FOOD_REFILLED' => 'Food supply refilled',
      'PIN_OK_DISARMED' => 'Alarm disarmed with PIN',
      'PIN_FAIL' => 'Wrong PIN entered at the panel',
      'BRUTE_FORCE_LOCKDOWN' => 'Repeated wrong PINs — system locked down',
      'REPLAY_REJECTED' => 'Spoofed command blocked — replay attack',
      'CMD_REJECTED' => 'Unauthenticated command blocked',
      'SENSOR_MISMATCH' => 'Temperature sensors disagree — possible tampering',
      'EVACUATE_DO_NOT_ENTER' => 'Do not enter the manure pit',
      'BOOT_STATE_RESTORED' => 'Node restarted — secure state restored',
      _ => type,
    };
