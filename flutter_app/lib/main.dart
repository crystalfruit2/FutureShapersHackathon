import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'data/bridge_source.dart';
import 'data/fake_source.dart';
import 'data/source.dart';
import 'models.dart';
import 'ui/controls_screen.dart';
import 'ui/forecast_screen.dart';
import 'ui/emergency_overlay.dart';
import 'ui/events_screen.dart';
import 'ui/home_screen.dart';
import 'ui/theme.dart';

void main() => runApp(const StrajerApp());

/// Single app-wide state. UI listens to this; it consumes whichever
/// StrajerDataSource is active (demo generator or the laptop bridge).
class AppState extends ChangeNotifier {
  StrajerDataSource? _source;
  StreamSubscription? _sub;

  FarmMode mode = FarmMode.unknown;
  Telemetry tel = const Telemetry({});
  final List<StrajerEvent> events = [];
  List<AuditRecord> audit = [];
  bool connected = false;
  String connDetail = 'Starting…';
  bool usingBridge = false;
  String bridgeUrl = 'http://192.168.1.20:5001';
  bool emergencyAcked = false;
  bool sceneRunning = false;
  int pinFails = 0;
  DateTime? pinLockUntil;
  String _ackedEmergKey = ''; // zone+type that was acknowledged
  DateTime _lastEmergSound = DateTime.fromMillisecondsSinceEpoch(0);
  Timer? _secTimer;
  StrajerEvent? lastSec; // latest cyber event, for the toast

  AppState() {
    _restorePrefs();
  }

  Future<void> _restorePrefs() async {
    final p = await SharedPreferences.getInstance();
    bridgeUrl = p.getString('bridgeUrl') ?? bridgeUrl;
    useFake(); // always boot into demo data; user switches to live in Controls
  }

  void _attach(StrajerDataSource s) {
    _sub?.cancel();
    _source?.dispose();
    _source = s;
    events.clear();
    audit = [];
    tel = const Telemetry({});
    mode = FarmMode.unknown;
    _sub = s.messages.listen(_onMsg);
    s.start();
    notifyListeners();
  }

  void useFake() {
    usingBridge = false;
    _attach(FakeDataSource());
  }

  Future<void> useBridge(String url) async {
    usingBridge = true;
    bridgeUrl = url;
    final p = await SharedPreferences.getInstance();
    await p.setString('bridgeUrl', url);
    _attach(BridgeDataSource(url));
  }

  void _onMsg(SourceMsg m) {
    switch (m) {
      case TelMsg():
        tel = m.tel;
      case ModeMsg():
        final was = mode;
        mode = m.mode;
        if (mode == FarmMode.emergency && was != FarmMode.emergency) {
          emergencyAcked = false;
          _ackedEmergKey = '';
          HapticFeedback.heavyImpact();
        }
      case EventMsg():
        events.insert(0, m.event);
        if (events.length > 400) events.removeLast();
        if (!m.history) {
          if (m.event.sev == Severity.emerg) {
            // a NEW kind of emergency re-raises the acked overlay; the same
            // one re-emitted does not (that was the can't-exit bug)
            final key = '${m.event.zone}|${m.event.type}';
            if (key != _ackedEmergKey) emergencyAcked = false;
            if (DateTime.now().difference(_lastEmergSound).inSeconds >= 10) {
              _lastEmergSound = DateTime.now();
              HapticFeedback.heavyImpact();
              SystemSound.play(SystemSoundType.alert);
            }
          } else if (m.event.sev == Severity.alert) {
            HapticFeedback.mediumImpact();
          } else if (m.event.sev == Severity.sec) {
            lastSec = m.event;
            HapticFeedback.selectionClick();
            _secTimer?.cancel();
            _secTimer = Timer(const Duration(seconds: 6), clearSecToast);
          }
        }
      case AuditMsg():
        audit = m.log;
      case ConnMsg():
        connected = m.connected;
        connDetail = m.detail;
    }
    notifyListeners();
  }

  void ackEmergency() {
    emergencyAcked = true;
    final lastEmerg =
        events.where((e) => e.sev == Severity.emerg).firstOrNull;
    _ackedEmergKey =
        lastEmerg == null ? '' : '${lastEmerg.zone}|${lastEmerg.type}';
    notifyListeners();
  }

  void clearSecToast() {
    lastSec = null;
    notifyListeners();
  }

  Future<void> command(String a) async => _source?.command(a);

  String get _timeNow {
    final n = DateTime.now();
    String p(int x) => x.toString().padLeft(2, '0');
    return '${p(n.hour)}:${p(n.minute)}:${p(n.second)}';
  }

  void _localEvent(String raw, Severity sev) {
    events.insert(0, StrajerEvent(raw, _timeNow, sev));
    notifyListeners();
  }

  /// App-side auth layer: disarming needs the user PIN (arming does not).
  /// PIN mirrors the panel code. 3 misses -> 30 s local lockout.
  static const _pin = [1, 3, 2, 4];
  PinResult tryDisarm(List<int> digits) {
    if (pinLockUntil != null && DateTime.now().isBefore(pinLockUntil!)) {
      return PinResult.locked;
    }
    if (digits.length == 4 &&
        List.generate(4, (i) => digits[i] == _pin[i]).every((x) => x)) {
      pinFails = 0;
      pinLockUntil = null;
      command('DISARM');
      _localEvent('EVT|0|ctrl|PIN_OK_DISARMED|0|INFO', Severity.info);
      return PinResult.ok;
    }
    pinFails++;
    _localEvent('EVT|0|ctrl|PIN_FAIL|$pinFails|WARN', Severity.warn);
    if (pinFails >= 3) {
      pinLockUntil = DateTime.now().add(const Duration(seconds: 30));
      pinFails = 0;
      _localEvent('SEC|APP_PIN_LOCKOUT|30s', Severity.sec);
      return PinResult.locked;
    }
    return PinResult.wrong;
  }

  /// Demo director: one tap = one rehearsed pitch scene, correct timing.
  /// Works identically in Demo and Live mode (routes through the source).
  Future<void> runScene(int n) async {
    if (sceneRunning) return;
    sceneRunning = true;
    notifyListeners();
    Future<void> wait(int s) => Future.delayed(Duration(seconds: s));
    try {
      switch (n) {
        case 1: // central control: mode round-trip
          await command('ARM');
          await wait(3);
          await command('DISARM');
          await wait(2);
          await command('VENT');
        case 2: // energy: ammonia rise -> auto ventilation -> recover
          await simulate('nh3', 32);
          await wait(6);
          await simulate('nh3', 8);
          await wait(3);
          await command('FAN_OFF');
        case 3: // security: night watch -> intruder
          await command('ARM');
          await wait(2);
          await simulate('mot', 1);
          await wait(4);
          await simulate('mot', 0);
        case 4: // life safety + cyber: gas emergency -> recover -> attack -> audit
          for (final v in [300, 500, 750, 900]) {
            await simulate('gas', v);
            await wait(2);
          }
          await wait(4);
          for (final v in [500, 300, 150]) {
            await simulate('gas', v);
            await wait(2);
          }
          await replayAttack();
          await wait(2);
          await command('DUMPLOG');
      }
    } finally {
      sceneRunning = false;
      notifyListeners();
    }
  }
  Future<void> simulate(String n, num v) async => _source?.simulate(n, v);
  Future<void> replayAttack() async => _source?.replayAttack();

  @override
  void dispose() {
    _secTimer?.cancel();
    _sub?.cancel();
    _source?.dispose();
    super.dispose();
  }
}

class StrajerApp extends StatelessWidget {
  const StrajerApp({super.key});
  @override
  Widget build(BuildContext context) => ChangeNotifierProvider(
        create: (_) => AppState(),
        child: MaterialApp(
          title: 'Bio Guard',
          debugShowCheckedModeBanner: false,
          theme: T.theme(),
          home: const Shell(),
        ),
      );
}

class Shell extends StatefulWidget {
  const Shell({super.key});
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final emergencyActive =
        app.mode == FarmMode.emergency && !app.emergencyAcked;
    return Stack(children: [
      Scaffold(
        body: IndexedStack(index: _tab, children: const [
          HomeScreen(),
          ControlsScreen(),
          EventsScreen(),
          ForecastScreen(),
        ]),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (i) => setState(() => _tab = i),
          backgroundColor: T.surface,
          indicatorColor: T.surface2,
          height: 64,
          destinations: const [
            NavigationDestination(icon: Icon(Icons.grid_view_rounded), label: 'Farm'),
            NavigationDestination(icon: Icon(Icons.tune_rounded), label: 'Controls'),
            NavigationDestination(icon: Icon(Icons.query_stats_rounded), label: 'Activity'),
            NavigationDestination(icon: Icon(Icons.online_prediction_rounded), label: 'Forecast'),
          ],
        ),
      ),
      if (emergencyActive) const EmergencyOverlay(),
      if (app.lastSec != null) SecToast(event: app.lastSec!),
    ]);
  }
}

enum PinResult { ok, wrong, locked }
