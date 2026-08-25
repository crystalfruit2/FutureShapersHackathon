/// Pure-Dart port of the Flask fake generator — lets the whole app run with
/// zero hardware and zero network. Thresholds mirror the firmware plan:
/// gas >= 700 -> EMERGENCY (valve cut, purge), < 400 -> auto-clear.
library;

import 'dart:async';
import 'dart:math';
import '../models.dart';
import 'source.dart';

class FakeDataSource implements StrajerDataSource {
  final _ctrl = StreamController<SourceMsg>.broadcast();
  final _rng = Random();
  Timer? _timer;

  final Map<String, double> _v = {
    'gas': 120, 'nh3': 8, 'flame': 0, 't1': 24, 't2': 24, 'hum': 55,
    'water': 620, 'mot': 0, 'snd': 0, 'tamp': 0,
    'fan': 0, 'relay': 1, 'vent': 0,
  };
  final Set<String> _sim = {'nh3', 'flame'};
  FarmMode _mode = FarmMode.day;
  double _fanOnSec = 0, _totalSec = 0;

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

  void _setMode(FarmMode m) {
    if (m == _mode) return;
    _mode = m;
    _ctrl.add(ModeMsg(m));
  }

  @override
  void start() {
    _ctrl.add(ConnMsg(true, 'Demo mode — generated data'));
    _ctrl.add(ModeMsg(_mode));
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
  }

  void _tick() {
    // gentle sensor noise
    if (!_sim.contains('gas')) {
      _v['gas'] = max(80, _v['gas']! + _rng.nextInt(31) - 15);
    }
    _v['t1'] = 24 + _rng.nextInt(3) - 1.0;
    _v['t2'] = _v['t1']! + (_rng.nextInt(3) == 0 ? 1 : 0);
    _v['hum'] = 55 + _rng.nextInt(5) - 2.0;

    // firmware rules
    if (_v['gas']! >= 700 && _mode != FarmMode.emergency) {
      _v['relay'] = 0; _v['fan'] = 1; _v['vent'] = 1;
      _setMode(FarmMode.emergency);
      _emitEvent('pit', 'GAS_CRITICAL', _v['gas']!.round(), Severity.emerg);
    } else if (_v['gas']! < 400 && _mode == FarmMode.emergency) {
      _v['relay'] = 1;
      _setMode(FarmMode.day);
      _emitEvent('pit', 'GAS_CLEARED', _v['gas']!.round(), Severity.info);
    }
    if (_v['flame']! > 0 && _mode != FarmMode.emergency) {
      _setMode(FarmMode.emergency);
      _emitEvent('store', 'FLAME_DETECTED', 1, Severity.emerg);
    }
    if (_v['mot']! > 0 && _mode == FarmMode.night) {
      _emitEvent('perim', 'INTRUDER', 1, Severity.alert);
      _v['mot'] = 0;
    }
    if (_v['nh3']! >= 25) _v['fan'] = 1;

    _totalSec++;
    if (_v['fan']! > 0) _fanOnSec++;
    final saved = _totalSec == 0 ? 0 : (100 - _fanOnSec * 100 / _totalSec).round();

    _ctrl.add(TelMsg(Telemetry({
      for (final e in _v.entries)
        e.key: Chan(e.value, simulated: _sim.contains(e.key)),
      'saved_pct': Chan(saved.toDouble()),
    })));
  }

  int _ctr = 0;

  @override
  Future<void> command(String action) async {
    _ctr++;
    switch (action) {
      case 'ARM': _setMode(FarmMode.night);
      case 'DISARM': _setMode(FarmMode.day);
      case 'FAN_ON': _v['fan'] = 1;
      case 'FAN_OFF': _v['fan'] = 0;
      case 'VENT': _v['vent'] = _v['vent'] == 1 ? 0 : 1;
      case 'DUMPLOG':
        _ctrl.add(AuditMsg([
          const AuditRecord(0, 'BOOT', '0', '0', 'OK'),
          const AuditRecord(1, 'MODE', '1', '2', 'OK'),
          const AuditRecord(2, 'GAS', '225', '14', 'OK'),
          const AuditRecord(3, 'CMD_REJECT', '1', '15', 'OK'),
        ]));
    }
  }

  @override
  Future<void> simulate(String name, num value) async {
    _v[name] = value.toDouble();
    _sim.add(name);
  }

  @override
  Future<void> replayAttack() async {
    // stale counter re-sent -> firmware rejects. Same theatre as the bridge.
    _ctrl.add(EventMsg(StrajerEvent(
        'SEC|REPLAY_REJECTED|STALE_COUNTER|ctr=$_ctr', _now, Severity.sec)));
  }

  @override
  void dispose() {
    _timer?.cancel();
    _ctrl.close();
  }
}
