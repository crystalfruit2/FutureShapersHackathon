/// Live source: connects to the Flask bridge on the laptop
/// (dashboard/app.py — serial <-> SSE/HTTP). Auto-reconnects with backoff.
library;

import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models.dart';
import 'source.dart';

class BridgeDataSource implements StrajerDataSource {
  final String baseUrl; // e.g. http://192.168.4.9:5001
  BridgeDataSource(String url) : baseUrl = normalise(url);

  /// A trailing slash pasted from a browser bar produced "…//stream", which
  /// the bridge answers with a 404 and the app reported as "Failed to fetch"
  /// — an unreadable error for a typo. Normalise once, here, so no caller can
  /// reintroduce it.
  static String normalise(String url) {
    var u = url.trim();
    if (u.isEmpty) return u;
    if (!u.startsWith('http://') && !u.startsWith('https://')) u = 'http://$u';
    while (u.endsWith('/')) {
      u = u.substring(0, u.length - 1);
    }
    return u;
  }

  final _ctrl = StreamController<SourceMsg>.broadcast();
  http.Client? _client;
  bool _disposed = false;
  int _backoffSec = 1;

  @override
  Stream<SourceMsg> get messages => _ctrl.stream;

  @override
  void start() => _connect();

  Future<void> _connect() async {
    while (!_disposed) {
      try {
        _client = http.Client();
        final req = http.Request('GET', Uri.parse('$baseUrl/stream'));
        final res = await _client!.send(req).timeout(const Duration(seconds: 8));
        if (res.statusCode != 200) throw Exception('HTTP ${res.statusCode}');
        _ctrl.add(ConnMsg(true, 'Connected to farm node'));
        _backoffSec = 1;
        // SSE: lines "data: {json}\n\n". The bridge ticks ~1 Hz, so >12 s of
        // silence means the link is dead even if TCP never noticed — force
        // the reconnect path instead of freezing on stale "Live" data.
        await for (final line in res.stream
            .transform(utf8.decoder)
            .transform(const LineSplitter())
            .timeout(const Duration(seconds: 12))) {
          if (!line.startsWith('data: ')) continue;
          _handle(jsonDecode(line.substring(6)) as Map<String, dynamic>);
        }
        throw Exception('stream ended');
      } catch (e) {
        if (_disposed) return;
        _ctrl.add(ConnMsg(false, 'Reconnecting — $e'));
        await Future.delayed(Duration(seconds: _backoffSec));
        _backoffSec = _backoffSec >= 8 ? 8 : _backoffSec * 2;
      } finally {
        _client?.close();
      }
    }
  }

  Telemetry _telFromBridge(Map<String, dynamic> tel) => Telemetry.fromWire({
        for (final e in tel.entries)
          e.key: (
            v: ((e.value as Map)['v'] as num).toDouble(),
            sim: (e.value as Map)['sim'] == true
          )
      });

  void _handle(Map<String, dynamic> m) {
    switch (m['type']) {
      case 'tel':
        _ctrl.add(TelMsg(_telFromBridge(m['tel'] as Map<String, dynamic>)));
      case 'state':
        _ctrl.add(ModeMsg(modeFrom(m['mode'] as String)));
      case 'event':
        _ctrl.add(EventMsg(StrajerEvent.fromBridge(m['event'] as Map<String, dynamic>)));
      case 'ai':
        final risk = RiskState.fromBridge(m['ai'] as Map<String, dynamic>);
        if (risk != null) _ctrl.add(AiMsg(risk));
      case 'esp':
        _ctrl.add(BoardMsg.fromBridge(m));
      case 'log':
        _ctrl.add(AuditMsg([
          for (final r in (m['log'] as List))
            AuditRecord.fromBridge(r as Map<String, dynamic>)
        ]));
      case 'hello':
        final st = m['state'] as Map<String, dynamic>?;
        if (st?['mode'] != null) _ctrl.add(ModeMsg(modeFrom('${st!['mode']}')));
        if (st?['tel'] is Map && (st!['tel'] as Map).isNotEmpty) {
          _ctrl.add(TelMsg(_telFromBridge(st['tel'] as Map<String, dynamic>)));
        }
        for (final e in (m['events'] as List? ?? [])) {
          _ctrl.add(EventMsg(
              StrajerEvent.fromBridge(e as Map<String, dynamic>),
              history: true));
        }
        if (m['ai'] is Map<String, dynamic>) {
          final helloRisk =
              RiskState.fromBridge(m['ai'] as Map<String, dynamic>);
          if (helloRisk != null) _ctrl.add(AiMsg(helloRisk));
        }
        if (m['esp'] is Map<String, dynamic>) {
          _ctrl.add(BoardMsg.fromBridge(m['esp'] as Map<String, dynamic>));
        }
    }
  }

  Future<void> _post(String path, Map<String, dynamic> body) async {
    try {
      await http
          .post(Uri.parse('$baseUrl$path'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode(body))
          .timeout(const Duration(seconds: 5));
    } catch (e) {
      // a failed POST is not a dead stream — report it as an event, not as
      // connection state (one Wi-Fi hiccup must not flag the app "Offline")
      final n = DateTime.now();
      String p(int x) => x.toString().padLeft(2, '0');
      _ctrl.add(EventMsg(StrajerEvent('DASH|COMMAND_FAILED|retry',
          '${p(n.hour)}:${p(n.minute)}:${p(n.second)}', Severity.warn)));
    }
  }

  @override
  Future<void> command(String action, {String role = 'admin', String pin = ''}) =>
      _post('/cmd', {'action': action, 'role': role, 'pin': pin});

  @override
  Future<void> simulate(String name, num value) =>
      _post('/sim', {'name': name, 'value': value});

  @override
  Future<void> replayAttack() => _post('/attack', {});

  @override
  void dispose() {
    _disposed = true;
    _client?.close();
    _ctrl.close();
  }
}
