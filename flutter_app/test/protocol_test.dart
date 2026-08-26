// Guards the app<->bridge protocol contract (see repo README).
import 'package:flutter_test/flutter_test.dart';
import 'package:strajer_app/models.dart';

void main() {
  test('telemetry parses bridge JSON incl. SIM flag', () {
    final t = Telemetry.fromWire({
      'gas': (v: 512, sim: false),
      'nh3': (v: 12.0, sim: true),
    });
    expect(t.v('hall.gas'), 512);      // flat wire key 'gas' maps to hall.gas
    expect(t.sim('hall.nh3'), true);
    expect(t.sim('hall.gas'), false);
    expect(t.v('missing', -1), -1);
  });

  test('event parses EVT line and severity', () {
    final e = StrajerEvent.fromBridge(
        {'raw': 'EVT|123|pit|GAS_CRITICAL|900|EMERG', 't': '03:00:01', 'sev': 'EMERG'});
    expect(e.sev, Severity.emerg);
    expect(e.zone, 'pit');
    expect(e.type, 'GAS_CRITICAL');
  });

  test('SEC event maps to sec severity', () {
    final e = StrajerEvent.fromBridge(
        {'raw': 'SEC|REPLAY_REJECTED|STALE_COUNTER', 't': '', 'sev': 'SEC'});
    expect(e.sev, Severity.sec);
  });

  test('AI analyst line parses: zone, kind and farmer copy', () {
    // AI|<kind>|<zone>|<what>|<message>|<sev> — emitted by the bridge, not the firmware
    const raw = 'AI|PREDICT|pit|GAS|CH4 rising +240/min to critical in 1m29s|ALERT';
    final e = StrajerEvent.fromBridge({'raw': raw, 't': '03:00:01', 'sev': 'ALERT'});
    expect(e.sev, Severity.alert);
    expect(e.zone, 'pit');
    expect(e.parts[1], 'PREDICT');
    // the feed titles AI events with parts[4] — it is already human copy
    expect(e.parts[4], 'CH4 rising +240/min to critical in 1m29s');
  });

  test('risk block parses from the AI snapshot', () {
    final r = RiskState.fromBridge({
      'learning': false,
      'progress': 1,
      'risk': {
        'score': 0.61,
        'level': 'ELEVATED',
        'sev': 'WARN',
        'eta': '3m53s',
        'eta_label': 'CH4',
        'action': 'ventilate the pit and check for a combustion source',
        'drivers': [
          {'k': 'gas', 'label': 'CH4', 'zone': 'pit',
           'pct': 61, 'detail': 'CH4 rising — critical in 3m53s'},
        ],
      },
    });
    expect(r, isNotNull);
    expect(r!.level, 'ELEVATED');
    expect(r.score, 0.61);
    expect(r.eta, '3m53s');
    expect(r.drivers.single.label, 'CH4');
    // an old bridge without the block must not crash the app
    expect(RiskState.fromBridge({'learning': true}), isNull);
  });

  test('modes map from bridge strings', () {
    expect(modeFrom('EMERGENCY'), FarmMode.emergency);
    expect(modeFrom('DAY'), FarmMode.day);
    expect(modeFrom('???'), FarmMode.unknown);
  });
}
