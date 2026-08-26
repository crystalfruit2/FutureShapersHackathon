/// Demo generator — now zone-scoped. Wire-compat: simulate() still accepts the
/// FLAT names the firmware understands (gas, nh3, flame, mot) and maps them in.
library;

import 'dart:async';
import 'dart:math';
import '../models.dart';
import 'demo_series.dart';
import 'source.dart';

class FakeDataSource implements StrajerDataSource {
  final _ctrl = StreamController<SourceMsg>.broadcast();
  final _rng = Random();
  Timer? _timer;

  final Map<String, double> _v = {};
  final Set<String> _sim = {}; // only marks channels the USER injected
  FarmMode _mode = FarmMode.day;
  FarmMode _modeBeforeEmergency = FarmMode.day;
  double _fanOnSec = 0, _totalSec = 0;
  double _fan = 0, _relay = 1, _vent = 0, _cfan = 0, _spr = 0;

  FakeDataSource() {
    final now = DateTime.now();
    for (final z in zoneMetrics.keys) {
      for (final m in zoneMetrics[z]!) {
        _v['$z.$m'] = switch (m) {
          'temp' => demoValue('temp', now) + (z == 'field' ? -3 : 0),
          'hum' => demoValue('hum', now),
          'nh3' => z == 'hall' ? 8 : 2,
          'gas' => z == 'hall' ? 150 : 90,
          'water' => 72,
          'food' => 58,
          _ => 0, // sound/light/motion/fire booleans start quiet
        };
      }
    }
    _v['stor.light'] = 0;
    _v['ctrl.light'] = 0;
    _v['hall.light'] = 1;
    _v['field.light'] = 1;
  }

  @override
  Stream<SourceMsg> get messages => _ctrl.stream;

  String get _now {
    final n = DateTime.now();
    String p(int x) => x.toString().padLeft(2, '0');
    return '${p(n.hour)}:${p(n.minute)}:${p(n.second)}';
  }

  void _emitEvent(String zone, String type, num val, Severity sev) =>
      _ctrl.add(EventMsg(StrajerEvent(
          'EVT|${DateTime.now().millisecondsSinceEpoch % 100000}|$zone|$type|$val|${sev.name.toUpperCase()}',
          _now, sev)));

  // leaving emergency via a mode command must release the actuators too,
  // or the valve cut / sprinkler latch forever (the tick's recovery branch
  // only runs while mode is still emergency)
  void _exitEmergency() {
    if (_mode == FarmMode.emergency) {
      _relay = 1;
      _spr = 0;
    }
  }

  void _setMode(FarmMode m) {
    if (m == _mode) return;
    _mode = m;
    _ctrl.add(ModeMsg(m));
  }

  @override
  void start() {
    _ctrl.add(ConnMsg(true, 'Demo mode — generated data'));
    _ctrl.add(ModeMsg(_mode));
    // seed a plausible recent history so the incident log isn't empty at boot
    // (history:true -> rendered in the log, fires no alarms)
    final seeds = [
      ('EVT|0|hall|GAS_HIGH|480|WARN', '05:12'),
      ('EVT|0|hall|WATER_LOW|18|WARN', '06:40'),
      ('SEC|REPLAY_REJECTED|STALE_COUNTER', '09:03'),
      ('EVT|0|ctrl|PIN_OK_DISARMED|0|INFO', '09:04'),
    ];
    for (final (raw, t) in seeds) {
      final sev = raw.startsWith('SEC')
          ? Severity.sec
          : raw.endsWith('WARN')
              ? Severity.warn
              : Severity.info;
      _ctrl.add(EventMsg(StrajerEvent(raw, t, sev), history: true));
    }
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
  }

  void _tick() {
    final now = DateTime.now();
    // drift the ambient metrics around the deterministic demo curves
    for (final z in zoneMetrics.keys) {
      _drift('$z.temp', demoValue('temp', now) + (z == 'field' ? -3 : 0), 0.4);
      if (zoneMetrics[z]!.contains('hum')) _drift('$z.hum', demoValue('hum', now), 0.8);
      if (!_sim.contains('$z.nh3')) _drift('$z.nh3', z == 'hall' ? 9 : 2, 0.5);
      if (!_sim.contains('$z.gas')) _drift('$z.gas', z == 'hall' ? 150 : 90, 6);
    }
    _drift('hall.water', 72, 0.3);
    _drift('hall.food', 58, 0.2);

    // rules (mirror firmware intent)
    final gasMax = zoneMetrics.keys.map((z) => _v['$z.gas'] ?? 0).reduce(max);
    final anyFire = zoneMetrics.keys.any((z) => (_v['$z.fire'] ?? 0) >= 1);
    if ((gasMax >= 700 || anyFire) && _mode != FarmMode.emergency) {
      _relay = 0; _fan = 1; _vent = 1;
      if (anyFire) _spr = 1; // sprinkler auto-fires on flame
      _modeBeforeEmergency = _mode;
      _setMode(FarmMode.emergency);
      _emitEvent(anyFire ? 'stor' : 'hall', anyFire ? 'FLAME_DETECTED' : 'GAS_CRITICAL',
          anyFire ? 1 : gasMax.round(), Severity.emerg);
    } else if (gasMax < 400 && !anyFire && _mode == FarmMode.emergency) {
      _relay = 1; _spr = 0;
      _setMode(_modeBeforeEmergency); // a night-armed farm stays armed
      _emitEvent('hall', 'GAS_CLEARED', gasMax.round(), Severity.info);
    }
    if ((_v['field.motion'] ?? 0) >= 1 && _mode == FarmMode.night) {
      _emitEvent('field', 'INTRUDER', 1, Severity.alert);
      _v['field.motion'] = 0;
    }
    if ((_v['hall.nh3'] ?? 0) >= 25) _fan = 1;
    // storage/control lights follow motion ("light goes on when somebody enters")
    _v['stor.light'] = (_v['stor.motion'] ?? 0) >= 1 ? 1 : 0;
    _v['ctrl.light'] = (_v['ctrl.motion'] ?? 0) >= 1 ? 1 : 0;

    _totalSec++;
    if (_fan > 0) _fanOnSec++;
    _pushTel();
  }

  void _pushTel() {
    final saved = _totalSec == 0 ? 0 : (100 - _fanOnSec * 100 / _totalSec).round();
    _ctrl.add(TelMsg(Telemetry({
      for (final e in _v.entries) e.key: Chan(e.value, simulated: _sim.contains(e.key)),
      'fan': Chan(_fan), 'relay': Chan(_relay), 'vent': Chan(_vent),
      'cfan': Chan(_cfan), 'spr': Chan(_spr),
      'saved_pct': Chan(saved.toDouble()),
    })));
  }

  void _drift(String k, double target, double step) {
    final cur = _v[k] ?? target;
    _v[k] = cur + (target - cur) * 0.05 + (_rng.nextDouble() * 2 - 1) * step;
  }

  int _ctr = 0;

  @override
  Future<void> command(String action, {String role = 'admin', String pin = ''}) async {
    // offline demo generator: no auth surface here — RBAC/PIN/lockdown live
    // on the bridge, which Live mode exercises for real
    _ctr++;
    switch (action) {
      case 'ARM': _exitEmergency(); _setMode(FarmMode.night);
      case 'DISARM': _exitEmergency(); _setMode(FarmMode.day);
      case 'FAN_ON': _fan = 1;
      case 'FAN_OFF': _fan = 0;
      case 'VENT': _vent = _vent == 1 ? 0 : 1;
      case 'CFAN_ON': _cfan = 1;
      case 'CFAN_OFF': _cfan = 0;
      case 'LIGHT_ON': _v['hall.light'] = 1;
      case 'LIGHT_OFF': _v['hall.light'] = 0;
      case 'SPRINKLER_ON': _spr = 1;
      case 'SPRINKLER_OFF': _spr = 0;
      case 'REFILL_WATER':
        _v['hall.water'] = 100;
        _emitEvent('hall', 'WATER_REFILLED', 100, Severity.info);
      case 'REFILL_FOOD':
        _v['hall.food'] = 100;
        _emitEvent('hall', 'FOOD_REFILLED', 100, Severity.info);
      case 'DUMPLOG':
        _ctrl.add(AuditMsg([
          const AuditRecord(0, 'BOOT', '0', '0', 'OK'),
          const AuditRecord(1, 'MODE', '1', '2', 'OK'),
          const AuditRecord(2, 'GAS', '225', '14', 'OK'),
          const AuditRecord(3, 'CMD_REJECT', '1', '15', 'OK'),
        ]));
    }
    _pushTel(); // reflect actuator changes immediately, not on the next tick
  }

  @override
  Future<void> simulate(String name, num value) async {
    final key = flatToZone[name] ?? name; // accept flat wire names AND zone keys
    _v[key] = value.toDouble();
    _sim.add(key);
  }

  @override
  Future<void> replayAttack() async {
    _ctrl.add(EventMsg(StrajerEvent(
        'SEC|REPLAY_REJECTED|STALE_COUNTER|ctr=$_ctr', _now, Severity.sec)));
  }

  @override
  void dispose() {
    _timer?.cancel();
    _ctrl.close();
  }
}
