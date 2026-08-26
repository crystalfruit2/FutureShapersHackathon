// Guards the remote-control auth window: a PIN unlocks actuator commands for
// AppState.authWindow, then the next command must prove the operator again.
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:strajer_app/main.dart';

// AppState is a process-lifetime singleton in the app: its async prefs
// restore lands after any dispose() a test could call, so these cases exercise
// it undisposed rather than fighting that.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('starts locked', () {
    final app = AppState();
    expect(app.authorized, false);
    expect(app.authSecondsLeft, 0);
  });

  test('correct PIN opens the window, lockControl closes it', () {
    final app = AppState();
    expect(app.authorizeControl([1, 3, 2, 4]), PinResult.ok);
    expect(app.authorized, true);
    // whole window minus the tick we spent proving it
    expect(app.authSecondsLeft, greaterThan(AppState.authWindow.inSeconds - 3));
    expect(app.authSecondsLeft, lessThanOrEqualTo(AppState.authWindow.inSeconds));

    app.lockControl();
    expect(app.authorized, false);
    expect(app.authSecondsLeft, 0);
  });

  test('wrong PIN never opens the window, and 3 misses lock the pad out', () {
    final app = AppState();
    expect(app.authorizeControl([9, 9, 9, 9]), PinResult.wrong);
    expect(app.authorized, false);
    expect(app.authorizeControl([1, 3, 2, 5]), PinResult.wrong);
    expect(app.authorized, false);
    expect(app.authorizeControl([0, 0, 0, 0]), PinResult.locked);
    expect(app.pinLockedOut, true);
    // even the right PIN is refused while the lockout runs
    expect(app.authorizeControl([1, 3, 2, 4]), PinResult.locked);
    expect(app.authorized, false);
  });

  test('a short PIN is not accepted', () {
    final app = AppState();
    expect(app.authorizeControl([1, 3, 2]), PinResult.wrong);
    expect(app.authorized, false);
  });

  test('disarming also opens the control window', () {
    final app = AppState();
    expect(app.tryDisarm([1, 3, 2, 4]), PinResult.ok);
    expect(app.authorized, true);
  });

  // The bench "Intruder" button must raise the same full-screen takeover the
  // flame path gets — including when the farm was never armed, which is how it
  // will be pressed on stage.
  test('injected motion raises the intruder takeover, ack clears it', () async {
    final app = AppState();
    await Future.delayed(const Duration(milliseconds: 100)); // demo source boots
    expect(app.intruderActive, false);

    await app.command('DISARM'); // explicitly NOT armed
    app.simulate('mot', 1);
    await Future.delayed(const Duration(milliseconds: 2500)); // one demo tick

    expect(app.intruderActive, true,
        reason: 'bench intrusion must take the screen over even unarmed');
    expect(app.events.any((e) => e.type == 'INTRUDER'), true);

    app.ackIntruder();
    expect(app.intruderActive, false);
  });
}
