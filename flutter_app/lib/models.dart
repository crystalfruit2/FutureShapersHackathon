/// Protocol + zone models.
/// The wire protocol stays FLAT (firmware contract: gas, nh3, t1, ...).
/// The app model is ZONE-SCOPED: keys like "hall.temp". BridgeDataSource and
/// FakeDataSource map flat wire keys onto zones via [flatToZone].
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

/// zone ids -> display names (order = display order on the Farm page)
const zoneNames = {
  'hall': 'Poultry hall',
  'field': 'Field',
  'stor': 'Storage room',
  'ctrl': 'Control room',
};

/// metric ids -> (label, unit). Booleans render as yes/no chips.
const metricDefs = {
  'nh3': ('Ammonia', ' ppm'),
  'temp': ('Temperature', '°'),
  'hum': ('Humidity', '%'),
  'gas': ('Methane', ''),
  'water': ('Water supply', '%'),
  'food': ('Food supply', '%'),
  'sound': ('Sound activity', ''),
  'light': ('Light', ''),
  'motion': ('Motion anomaly', ''),
  'fire': ('Fire detection', ''),
};

/// which metrics each zone shows, per Alp's layout (25.08)
const zoneMetrics = {
  'hall': ['nh3', 'temp', 'hum', 'gas', 'water', 'food', 'sound', 'light', 'motion', 'fire'],
  'field': ['nh3', 'temp', 'hum', 'gas', 'sound', 'light', 'motion', 'fire'],
  'stor': ['nh3', 'temp', 'hum', 'gas', 'light', 'motion', 'fire'],
  'ctrl': ['nh3', 'temp', 'gas', 'sound', 'light', 'motion', 'fire'],
};

/// flat firmware/wire key -> zone-scoped app key
const flatToZone = {
  'nh3': 'hall.nh3', 't1': 'hall.temp', 't2': 'hall.temp2', 'hum': 'hall.hum',
  'gas': 'hall.gas', 'water': 'hall.water', 'food': 'hall.food',
  'light': 'hall.light', 'snd': 'hall.sound',
  'mot': 'field.motion', 'flame': 'stor.fire', 'tamp': 'ctrl.motion',
};

class Anomaly {
  final String zone, metric, message;
  final bool critical;
  const Anomaly(this.zone, this.metric, this.message, this.critical);
}

/// Thresholds -> anomaly message; null = normal.
Anomaly? checkMetric(String zone, String metric, double v) {
  final zn = zoneNames[zone] ?? zone;
  return switch (metric) {
    'nh3' when v >= 25 => Anomaly(zone, metric, 'Ammonia high in $zn (${v.round()} ppm)', v >= 50),
    'gas' when v >= 450 => Anomaly(zone, metric, 'Methane ${v >= 700 ? "CRITICAL" : "rising"} in $zn', v >= 700),
    'temp' when v >= 32 => Anomaly(zone, metric, 'Overheating in $zn (${v.round()}°)', v >= 38),
    'temp' when v <= 2 => Anomaly(zone, metric, 'Freezing risk in $zn (${v.round()}°)', v <= -3),
    'water' when v < 20 => Anomaly(zone, metric, 'Water supply low in $zn (${v.round()}%)', v < 8),
    'food' when v < 20 => Anomaly(zone, metric, 'Food supply low in $zn (${v.round()}%)', v < 8),
    'motion' when v >= 1 => Anomaly(zone, metric, 'Motion anomaly in $zn', false),
    'fire' when v >= 1 => Anomaly(zone, metric, 'FIRE detected in $zn', true),
    'sound' when v >= 1 => Anomaly(zone, metric, 'Unusual sound in $zn', false),
    _ => null,
  };
}

class Telemetry {
  final Map<String, Chan> ch; // zone-scoped keys + system keys (fan/relay/vent/saved_pct)
  const Telemetry(this.ch);
  double v(String k, [double def = 0]) => ch[k]?.value ?? def;
  bool sim(String k) => ch[k]?.simulated ?? false;
  bool has(String k) => ch.containsKey(k);
  Chan? zoneMetric(String zone, String metric) => ch['$zone.$metric'];

  List<Anomaly> anomalies() {
    final out = <Anomaly>[];
    for (final z in zoneMetrics.keys) {
      for (final m in zoneMetrics[z]!) {
        final c = ch['$z.$m'];
        if (c == null) continue;
        final a = checkMetric(z, m, c.value);
        if (a != null) out.add(a);
      }
    }
    out.sort((a, b) => (b.critical ? 1 : 0) - (a.critical ? 1 : 0));
    return out;
  }

  /// Wire telemetry (flat) -> zone-scoped. Unknown keys pass through untouched.
  factory Telemetry.fromWire(Map<String, ({double v, bool sim})> flat) => Telemetry({
        for (final e in flat.entries)
          flatToZone[e.key] ?? e.key: Chan(e.value.v, simulated: e.value.sim)
      });
}

enum Severity { info, warn, alert, emerg, sec }

class StrajerEvent {
  final String raw;
  final String time;
  final Severity sev;
  final DateTime at;
  StrajerEvent(this.raw, this.time, this.sev, {DateTime? at}) : at = at ?? DateTime.now();

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
  final String what, val, min, chain;
  const AuditRecord(this.slot, this.what, this.val, this.min, this.chain);
  factory AuditRecord.fromBridge(Map<String, dynamic> r) => AuditRecord(
      r['slot'] as int, '${r['what']}', '${r['val']}', '${r['min']}', '${r['chain']}');
}
