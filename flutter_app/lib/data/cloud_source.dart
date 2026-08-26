/// Fleet (Tier-3) data layer — the cloud half of the app.
///
/// The other three tabs talk to ONE farm through the bridge. This one talks to
/// every farm through Firestore, which is a different question with a
/// different failure mode, so it gets its own repository rather than another
/// [StrajerDataSource].
///
/// Two interchangeable backends, chosen at runtime:
///
///   FirestoreFleetRepo  reads Firestore directly. This is the real story:
///                       the phone needs mobile data, not the demo laptop.
///   BridgeFleetRepo     reads the bridge's /cloud/api/fleet. Same JSON shape,
///                       works offline on the venue LAN.
///
/// [FleetService] prefers Firestore and silently falls back. That fallback is
/// not defensive padding — the app is served BY the bridge at /app/, and a
/// venue where Firebase is unreachable is a venue where the Fleet tab has to
/// keep working anyway.
library;

import 'dart:async';
import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:http/http.dart' as http;

import '../firebase_options.dart';

// ── models ───────────────────────────────────────────────────────────────
class RiskDriver {
  final String factor;
  final int share;
  final double value;
  const RiskDriver(this.factor, this.share, this.value);
  factory RiskDriver.fromMap(Map m) => RiskDriver('${m['factor']}',
      (m['share'] as num?)?.round() ?? 0, (m['value'] as num?)?.toDouble() ?? 0);
}

class FleetForecast {
  final String metric, text, state;
  final double etaH;
  const FleetForecast(this.metric, this.text, this.state, this.etaH);
  factory FleetForecast.fromMap(Map m) => FleetForecast(
      '${m['metric']}', '${m['text']}', '${m['state'] ?? ''}',
      (m['eta_h'] as num?)?.toDouble() ?? 0);
}

class FleetFarm {
  final String id, name, region, town, species, plan, mode, owner;
  final int herd, alerts24, samples;
  final double risk;
  final bool isLiveNode;
  final Map<String, double> live;
  final List<RiskDriver> drivers;
  final List<FleetForecast> forecast;
  final List<String> markers;

  const FleetFarm({
    required this.id, required this.name, required this.region,
    required this.town, required this.species, required this.plan,
    required this.mode, required this.owner, required this.herd,
    required this.alerts24, required this.samples, required this.risk,
    required this.isLiveNode, required this.live, required this.drivers,
    required this.forecast, required this.markers,
  });

  /// One parser for both backends. The bridge serves the same field names the
  /// farm document uses, so a shape change can't desync the two paths.
  factory FleetFarm.fromMap(String id, Map m) {
    List<T> list<T>(String k, T Function(Map) f) =>
        ((m[k] as List?) ?? const []).whereType<Map>().map(f).toList();
    return FleetFarm(
      id: id,
      name: '${m['name'] ?? id}',
      region: '${m['region'] ?? '—'}',
      town: '${m['town'] ?? ''}',
      species: '${m['species'] ?? ''}',
      plan: '${m['plan'] ?? '—'}',
      mode: '${m['mode'] ?? '—'}',
      owner: '${m['owner'] ?? ''}',
      herd: (m['herd'] as num?)?.round() ?? 0,
      alerts24: (m['alerts_24h'] as num?)?.round() ?? 0,
      samples: (m['samples'] as num?)?.round() ?? 0,
      // the bridge computes `risk`; the stored farm doc carries `risk_pct`
      risk: ((m['risk'] ?? m['risk_pct']) as num?)?.toDouble() ?? 0,
      isLiveNode: m['is_live_node'] == true,
      live: {
        for (final e in ((m['live'] as Map?) ?? const {}).entries)
          if (e.value is num) '${e.key}': (e.value as num).toDouble()
      },
      drivers: list('drivers', RiskDriver.fromMap).isNotEmpty
          ? list('drivers', RiskDriver.fromMap)
          : list('risk_drivers', RiskDriver.fromMap),
      forecast: list('forecast', FleetForecast.fromMap),
      markers: ((m['markers'] as List?) ?? const []).map((e) => '$e').toList(),
    );
  }
}

class RegionSignal {
  final String region, severity, text;
  final List<String> names;
  const RegionSignal(this.region, this.severity, this.text, this.names);
  factory RegionSignal.fromMap(Map m) => RegionSignal(
      '${m['region']}', '${m['severity'] ?? 'WARN'}', '${m['text']}',
      ((m['names'] as List?) ?? const []).map((e) => '$e').toList());
}

class FleetSnapshot {
  final List<FleetFarm> farms;
  final List<RegionSignal> regions;
  final Map<String, dynamic> summary, model;
  final String source; // "Firestore" | "Bridge"
  const FleetSnapshot(this.farms, this.regions, this.summary, this.model,
      this.source);

  int get atRisk => farms.where((f) => f.risk >= 35).length;
  int get animals =>
      farms.fold<int>(0, (a, f) => a + f.herd);
  int get alerts24 => farms.fold<int>(0, (a, f) => a + f.alerts24);
}

// ── backends ─────────────────────────────────────────────────────────────
abstract class FleetRepo {
  Future<FleetSnapshot> load();
}

class BridgeFleetRepo implements FleetRepo {
  final String baseUrl;
  BridgeFleetRepo(this.baseUrl);

  @override
  Future<FleetSnapshot> load() async {
    final r = await http
        .get(Uri.parse('$baseUrl/cloud/api/fleet'))
        .timeout(const Duration(seconds: 8));
    if (r.statusCode != 200) throw Exception('bridge HTTP ${r.statusCode}');
    final j = jsonDecode(r.body) as Map<String, dynamic>;
    return FleetSnapshot(
      [for (final f in (j['farms'] as List? ?? []))
        FleetFarm.fromMap('${(f as Map)['_id']}', f)],
      [for (final s in (j['regions'] as List? ?? []))
        RegionSignal.fromMap(s as Map)],
      (j['summary'] as Map?)?.cast<String, dynamic>() ?? {},
      (j['model'] as Map?)?.cast<String, dynamic>() ?? {},
      'Bridge',
    );
  }
}

class FirestoreFleetRepo implements FleetRepo {
  final FirebaseFirestore db;
  FirestoreFleetRepo(this.db);

  @override
  Future<FleetSnapshot> load() async {
    final farms = await db.collection('farms').get()
        .timeout(const Duration(seconds: 10));
    final regions = await db.doc('fleet/regions').get();
    final summary = await db.doc('fleet/summary').get();
    final model = await db.doc('fleet/model').get();
    return FleetSnapshot(
      [for (final d in farms.docs) FleetFarm.fromMap(d.id, d.data())]
        ..sort((a, b) => b.risk.compareTo(a.risk)),
      [for (final s in ((regions.data()?['signals'] as List?) ?? const []))
        RegionSignal.fromMap(s as Map)],
      summary.data() ?? {},
      model.data() ?? {},
      'Firestore',
    );
  }
}

// ── the service the UI actually talks to ─────────────────────────────────
class FleetService {
  final String bridgeUrl;
  FleetService(this.bridgeUrl);

  static bool _initTried = false;
  static bool _firebaseReady = false;
  static String initDetail = 'not initialised';

  /// Bring Firebase up once per process. Never throws: a missing config or a
  /// dead network downgrades the Fleet tab to the bridge, it does not take
  /// the app down with it.
  static Future<void> ensureFirebase() async {
    if (_initTried) return;
    _initTried = true;
    if (!DefaultFirebaseOptions.configured) {
      initDetail = 'no Firebase config compiled in — using bridge';
      return;
    }
    try {
      await Firebase.initializeApp(
          options: DefaultFirebaseOptions.currentPlatform);
      _firebaseReady = true;
      initDetail = 'connected to ${DefaultFirebaseOptions.projectId}';
    } catch (e) {
      initDetail = 'Firebase init failed ($e) — using bridge';
    }
  }

  Future<FleetSnapshot> load() async {
    await ensureFirebase();
    if (_firebaseReady) {
      try {
        return await FirestoreFleetRepo(FirebaseFirestore.instance).load();
      } catch (e) {
        initDetail = 'Firestore read failed ($e) — using bridge';
      }
    }
    return BridgeFleetRepo(bridgeUrl).load();
  }
}
