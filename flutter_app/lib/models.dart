/// Protocol models — mirror of what the Flask bridge emits over SSE.
/// Bridge JSON message types: hello / tel / state / event / log.
library;

enum FarmMode { day, night, emergency, lockdown, unknown }

FarmMode modeFrom(String s) => switch (s) {
      'DAY' => FarmMode.day,
      'NIGHT' => FarmMode.night,
      'EMERGENCY' => FarmMode.emergency,
      'LOCKDOWN' => FarmMode.lockdown,
      _ => FarmMode.unknown,
    };

class Chan {
  final double value;
  final bool simulated;
  const Chan(this.value, {this.simulated = false});
}

/// Telemetry snapshot: channel name -> value. Keys as in firmware TEL| line:
/// gas nh3 flame t1 t2 hum water mot snd tamp fan relay vent saved_pct
class Telemetry {
  final Map<String, Chan> ch;
  const Telemetry(this.ch);
  double v(String k, [double def = 0]) => ch[k]?.value ?? def;
  bool sim(String k) => ch[k]?.simulated ?? false;
  bool has(String k) => ch.containsKey(k);

  factory Telemetry.fromBridge(Map<String, dynamic> tel) => Telemetry({
        for (final e in tel.entries)
          e.key: Chan(((e.value as Map)['v'] as num).toDouble(),
              simulated: (e.value as Map)['sim'] == true)
      });
}

enum Severity { info, warn, alert, emerg, sec }

class StrajerEvent {
  final String raw; // full protocol line, e.g. EVT|123|pit|GAS_CRITICAL|900|EMERG
  final String time; // HH:MM:SS
  final Severity sev;
  const StrajerEvent(this.raw, this.time, this.sev);

  /// EVT|ms|zone|type|value|sev  → parts; non-EVT lines have fewer parts.
  List<String> get parts => raw.split('|');
  String get zone => parts.length > 2 ? parts[2] : '';
  String get type => parts.length > 3 ? parts[3] : parts.last;

  factory StrajerEvent.fromBridge(Map<String, dynamic> e) {
    final sev = switch (e['sev']) {
      'EMERG' => Severity.emerg,
      'ALERT' => Severity.alert,
      'WARN' => Severity.warn,
      'SEC' => Severity.sec,
      _ => Severity.info,
    };
    return StrajerEvent(e['raw'] as String, e['t'] as String? ?? '', sev);
  }
}

class AuditRecord {
  final int slot;
  final String what, val, min, chain; // chain: OK | BROKEN | EMPTY
  const AuditRecord(this.slot, this.what, this.val, this.min, this.chain);
  factory AuditRecord.fromBridge(Map<String, dynamic> r) => AuditRecord(
      r['slot'] as int, '${r['what']}', '${r['val']}', '${r['min']}', '${r['chain']}');
}
