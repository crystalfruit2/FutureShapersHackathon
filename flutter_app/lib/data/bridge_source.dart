/// Live source: connects to the Flask bridge on the laptop
/// (dashboard/app.py — serial <-> SSE/HTTP). Auto-reconnects with backoff.
library;

import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models.dart';
import 'source.dart';

class BridgeDataSource implements StrajerDataSource {
  final String baseUrl; // e.g. http://192.168.1.20:5001
  BridgeDataSource(this.baseUrl);

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
        // SSE: lines "data: {json}\n\n"
        await for (final line in res.stream
            .transform(utf8.decoder)
            .transform(const LineSplitter())) {
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

  void _handle(Map<String, dynamic> m) {
    switch (m['type']) {
      case 'tel':
        _ctrl.add(TelMsg(Telemetry.fromBridge(m['tel'] as Map<String, dynamic>)));
      case 'state':
        _ctrl.add(ModeMsg(modeFrom(m['mode'] as String)));
      case 'event':
        _ctrl.add(EventMsg(StrajerEvent.fromBridge(m['event'] as Map<String, dynamic>)));
      case 'log':
        _ctrl.add(AuditMsg([
          for (final r in (m['log'] as List))
            AuditRecord.fromBridge(r as Map<String, dynamic>)
        ]));
      case 'hello':
        final st = m['state'] as Map<String, dynamic>?;
        if (st?['mode'] != null) _ctrl.add(ModeMsg(modeFrom('${st!['mode']}')));
        if (st?['tel'] is Map && (st!['tel'] as Map).isNotEmpty) {
          _ctrl.add(TelMsg(Telemetry.fromBridge(st['tel'] as Map<String, dynamic>)));
        }
        for (final e in (m['events'] as List? ?? [])) {
          _ctrl.add(EventMsg(
              StrajerEvent.fromBridge(e as Map<String, dynamic>),
              history: true));
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
      _ctrl.add(ConnMsg(false, 'Command failed — $e'));
    }
  }

  @override
  Future<void> command(String action) => _post('/cmd', {'action': action});

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
