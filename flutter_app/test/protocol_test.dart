// Guards the app<->bridge protocol contract (see repo README).
import 'package:flutter_test/flutter_test.dart';
import 'package:strajer_app/models.dart';

void main() {
  test('telemetry parses bridge JSON incl. SIM flag', () {
    final t = Telemetry.fromBridge({
      'gas': {'v': 512, 'sim': false},
      'nh3': {'v': 12.0, 'sim': true},
    });
    expect(t.v('gas'), 512);
    expect(t.sim('nh3'), true);
    expect(t.sim('gas'), false);
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

  test('modes map from bridge strings', () {
    expect(modeFrom('EMERGENCY'), FarmMode.emergency);
    expect(modeFrom('DAY'), FarmMode.day);
    expect(modeFrom('???'), FarmMode.unknown);
  });
}
