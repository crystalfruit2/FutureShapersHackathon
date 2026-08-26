/// Swappable data-source layer. The UI only ever talks to [AppState]
/// (see main.dart); AppState consumes one of these sources.
library;

import '../models.dart';

/// Typed messages a source pushes up — one per bridge SSE message type.
sealed class SourceMsg {}

class TelMsg extends SourceMsg {
  final Telemetry tel;
  TelMsg(this.tel);
}

class ModeMsg extends SourceMsg {
  final FarmMode mode;
  ModeMsg(this.mode);
}

class EventMsg extends SourceMsg {
  final StrajerEvent event;
  final bool history; // true = replayed backlog, don't fire alarms
  EventMsg(this.event, {this.history = false});
}

class AuditMsg extends SourceMsg {
  final List<AuditRecord> log;
  AuditMsg(this.log);
}

class AiMsg extends SourceMsg {
  final RiskState risk;
  AiMsg(this.risk);
}

/// State of the physical ESP32 sensor board behind the bridge: what it
/// literally served on its last poll, what the bridge converted that into,
/// and which channels a SIM pin is holding away from it. The app shows this
/// verbatim so "is the hardware actually feeding us?" is answerable from the
/// phone, without SSHing into the laptop.
class BoardMsg extends SourceMsg {
  final bool connected;
  final String url;
  final Map<String, dynamic> raw;
  final Map<String, dynamic> converted;
  final List<String> live;
  final List<String> pinned;
  BoardMsg({
    required this.connected,
    required this.url,
    required this.raw,
    required this.converted,
    required this.live,
    required this.pinned,
  });

  static BoardMsg fromBridge(Map<String, dynamic> m) => BoardMsg(
        connected: m['connected'] == true,
        url: '${m['url'] ?? ''}',
        raw: Map<String, dynamic>.from(m['raw'] as Map? ?? {}),
        converted: Map<String, dynamic>.from(m['converted'] as Map? ?? {}),
        live: [for (final c in (m['channels'] as List? ?? [])) '$c'],
        pinned: [for (final c in (m['pinned'] as List? ?? [])) '$c'],
      );
}

class ConnMsg extends SourceMsg {
  final bool connected;
  final String detail;
  ConnMsg(this.connected, this.detail);
}

abstract class StrajerDataSource {
  Stream<SourceMsg> get messages;
  // ARM DISARM FAN_ON FAN_OFF VENT DUMPLOG … — role+pin ride along so the
  // bridge (the enforcement point) can apply RBAC and its PIN gate.
  Future<void> command(String action, {String role = 'admin', String pin = ''});
  Future<void> simulate(String name, num value); // SIM| injection
  Future<void> replayAttack(); // the cyber-demo button
  void start();
  void dispose();
}
