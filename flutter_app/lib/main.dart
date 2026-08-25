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
          HapticFeedback.heavyImpact();
        }
      case EventMsg():
        events.insert(0, m.event);
        if (events.length > 200) events.removeLast();
        if (!m.history) {
          if (m.event.sev == Severity.emerg) {
            emergencyAcked = false;
            HapticFeedback.heavyImpact();
            SystemSound.play(SystemSoundType.alert);
          } else if (m.event.sev == Severity.alert) {
            HapticFeedback.mediumImpact();
          } else if (m.event.sev == Severity.sec) {
            lastSec = m.event;
            HapticFeedback.selectionClick();
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
    notifyListeners();
  }

  void clearSecToast() {
    lastSec = null;
    notifyListeners();
  }

  Future<void> command(String a) async => _source?.command(a);
  Future<void> simulate(String n, num v) async => _source?.simulate(n, v);
  Future<void> replayAttack() async => _source?.replayAttack();

  @override
  void dispose() {
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
          EventsScreen(),
          ControlsScreen(),
        ]),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (i) => setState(() => _tab = i),
          backgroundColor: T.surface,
          indicatorColor: T.surface2,
          height: 64,
          destinations: const [
            NavigationDestination(icon: Icon(Icons.grid_view_rounded), label: 'Farm'),
            NavigationDestination(icon: Icon(Icons.receipt_long_outlined), label: 'Activity'),
            NavigationDestination(icon: Icon(Icons.tune_rounded), label: 'Controls'),
          ],
        ),
      ),
      if (emergencyActive) const EmergencyOverlay(),
      if (app.lastSec != null) SecToast(event: app.lastSec!),
    ]);
  }
}
