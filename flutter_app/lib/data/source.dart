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

class ConnMsg extends SourceMsg {
  final bool connected;
  final String detail;
  ConnMsg(this.connected, this.detail);
}

abstract class StrajerDataSource {
  Stream<SourceMsg> get messages;
  Future<void> command(String action); // ARM DISARM FAN_ON FAN_OFF VENT DUMPLOG
  Future<void> simulate(String name, num value); // SIM| injection
  Future<void> replayAttack(); // the cyber-demo button
  void start();
  void dispose();
}
