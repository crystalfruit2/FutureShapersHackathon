import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/bridge_source.dart';
import '../data/source.dart';
import '../main.dart';
import '../models.dart';
import 'theme.dart';

class ControlsScreen extends StatefulWidget {
  const ControlsScreen({super.key});
  @override
  State<ControlsScreen> createState() => _ControlsScreenState();
}

class _ControlsScreenState extends State<ControlsScreen> {
  /// Every remote actuator command goes through here. Outside the auth window
  /// it proves the operator first; inside it, it just runs. Guarding at the
  /// single call site rather than inside AppState.command keeps the firmware's
  /// own autonomous actions (a flame emergency opening the sprinkler) free of
  /// a human gate they must never wait on.
  Future<void> _guarded(AppState app, String cmd) async {
    if (!app.authorized) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (_) => const PinDialog(purpose: PinPurpose.control),
      );
      if (ok != true) return;
    }
    app.command(cmd);
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          Text('Controls', style: Theme.of(context).textTheme.headlineMedium),
          const SectionLabel('Access'),
          Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'admin', label: Text('Admin')),
                  ButtonSegment(value: 'operator', label: Text('Operator')),
                  ButtonSegment(value: 'viewer', label: Text('Viewer')),
                ],
                selected: {app.role},
                showSelectedIcon: false,
                onSelectionChanged: (s) => app.setRole(s.first),
              ),
              const SizedBox(height: 8),
              Text(
                switch (app.role) {
                  'admin' =>
                    'The only role that may change anything remotely — and every '
                        'change is PIN-proven and signed.',
                  'operator' =>
                    'Reads the farm and runs the bench. Remote actuator control is '
                        'closed to this role, here AND at the bridge.',
                  _ =>
                    'Read-only. Controls are disabled here AND the bridge rejects '
                        'anything this role sends.',
                },
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ]),
          ),
          // Remote change is an admin action, full stop. Operator and viewer
          // read the farm; only admin reaches the actuators, and even admin
          // proves the PIN first.
          AbsorbPointer(
            absorbing: app.role != 'admin',
            child: Opacity(
              opacity: app.role != 'admin' ? 0.45 : 1.0,
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
          const SectionLabel('Remote action'),
          Panel(child: const _AuthBar()),
          const SizedBox(height: 14),
          for (final room in _rooms) ...[
            _RoomPanel(room: room, guard: _guarded),
            const SizedBox(height: 12),
          ],
          const SectionLabel('Security'),
          Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: Icon(
                        app.mode == FarmMode.night || app.mode == FarmMode.lockdown
                            ? Icons.lock_open_outlined
                            : Icons.shield_moon_outlined,
                        size: 18),
                    label: Text(
                        app.mode == FarmMode.night || app.mode == FarmMode.lockdown
                            ? 'Disarm — PIN'
                            : 'Arm night watch'),
                    style: OutlinedButton.styleFrom(
                        foregroundColor:
                            app.mode == FarmMode.night ? T.warn : T.text,
                        side: BorderSide(
                            color: app.mode == FarmMode.night
                                ? T.warn
                                : T.hairline),
                        padding: const EdgeInsets.symmetric(vertical: 12)),
                    onPressed: () {
                      if (app.mode == FarmMode.night ||
                          app.mode == FarmMode.lockdown) {
                        showDialog(
                            context: context,
                            builder: (_) => const PinDialog());
                      } else {
                        app.command('ARM');
                      }
                    },
                  ),
                ),
              ]),
              const SizedBox(height: 12),
              Text('Every command is signed with a rolling counter. Try to spoof one:',
                  style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.gpp_bad_outlined, size: 18),
                    label: const Text('Replay attack'),
                    style: OutlinedButton.styleFrom(
                        foregroundColor: T.cyber,
                        side: const BorderSide(color: T.cyber),
                        padding: const EdgeInsets.symmetric(vertical: 12)),
                    onPressed: app.replayAttack,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.link_outlined, size: 18),
                    label: const Text('Verify log'),
                    style: OutlinedButton.styleFrom(
                        foregroundColor: T.text,
                        side: const BorderSide(color: T.hairline),
                        padding: const EdgeInsets.symmetric(vertical: 12)),
                    onPressed: () => app.command('DUMPLOG'),
                  ),
                ),
              ]),
              if (app.audit.isNotEmpty) ...[
                const SizedBox(height: 14),
                Text('Tamper-evident audit chain (on-device EEPROM):',
                    style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 8),
                for (final r in app.audit.where((r) => r.chain != 'EMPTY'))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(children: [
                      Icon(
                          r.chain == 'OK'
                              ? Icons.link
                              : Icons.link_off,
                          size: 16,
                          color: r.chain == 'OK' ? T.ok : T.danger),
                      const SizedBox(width: 8),
                      Text('#${r.slot}  ${humanEvent(r.what)}',
                          style: Theme.of(context).textTheme.bodyMedium),
                      const Spacer(),
                      Text(r.chain,
                          style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: r.chain == 'OK' ? T.ok : T.danger)),
                    ]),
                  ),
              ],
            ]),
          ),
                  ]),
            ),
          ),
          const SectionLabel('Simulation bench · demo only'),
          Panel(
            borderColor: T.cyber.withValues(alpha: 0.35),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Stand-ins for the sensors this kit does not include — injected into the node exactly like real readings.',
                  style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 10),
              const SizedBox(height: 4),
              Row(children: [
                Expanded(
                  child: _BenchButton('Flame in store',
                      Icons.local_fire_department_outlined,
                      () => app.simulate('flame', 1)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _BenchButton('Intruder', Icons.directions_walk_outlined,
                      () => app.simulate('mot', 1)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _BenchButton('Clear', Icons.restart_alt_outlined, () {
                    app.simulate('flame', 0);
                    app.simulate('mot', 0);
                  }),
                ),
              ]),
            ]),
          ),
          const SectionLabel('Connection'),
          _ConnectionPanel(app: app),
        ],
      ),
    );
  }
}



/// What each room can actually be driven from the phone.
///
/// Deliberately not symmetric: the farm has ONE sprinkler and it hangs in the
/// storage room, one circulation fan and one vent flap in the poultry hall.
/// Showing a sprinkler tile under every room would be a nicer grid and a lie,
/// and this jury reads the telemetry.
class _Room {
  final String id, name;
  final IconData icon;
  final List<_Act> acts;
  const _Room(this.id, this.name, this.icon, this.acts);
}

/// One actuator: how it is labelled, how its state is read, what it sends.
class _Act {
  final String label;
  final IconData icon;

  /// Telemetry channel that reports the real state.
  final String channel;

  /// Command verb; the room id is appended for anything but the poultry hall,
  /// which keeps the legacy bare verb the bridge and firmware already speak.
  final String onCmd, offCmd;

  /// Momentary tiles (refills) send [onCmd] and show a level instead of a switch.
  final bool momentary;
  const _Act(this.label, this.icon, this.channel, this.onCmd, this.offCmd,
      {this.momentary = false});
}

const _rooms = [
  _Room('hall', 'Poultry hall', Icons.warehouse_outlined, [
    _Act('Light', Icons.lightbulb_outlined, 'hall.light', 'LIGHT_ON', 'LIGHT_OFF'),
    _Act('Circulation fan', Icons.wind_power_outlined, 'cfan', 'CFAN_ON', 'CFAN_OFF'),
    _Act('Vent flap', Icons.hvac_outlined, 'vent', 'VENT', 'VENT'),
    _Act('Exhaust fan', Icons.air, 'fan', 'FAN_ON', 'FAN_OFF'),
    _Act('Water refill', Icons.water_drop_outlined, 'hall.water', 'REFILL_WATER', '',
        momentary: true),
    _Act('Food refill', Icons.rice_bowl_outlined, 'hall.food', 'REFILL_FOOD', '',
        momentary: true),
  ]),
  _Room('field', 'Field', Icons.grass_outlined, [
    _Act('Light', Icons.lightbulb_outlined, 'field.light', 'LIGHT_ON', 'LIGHT_OFF'),
  ]),
  _Room('stor', 'Storage room', Icons.inventory_2_outlined, [
    _Act('Light', Icons.lightbulb_outlined, 'stor.light', 'LIGHT_ON', 'LIGHT_OFF'),
    _Act('Sprinkler', Icons.shower_outlined, 'spr', 'SPRINKLER_ON', 'SPRINKLER_OFF'),
  ]),
  _Room('ctrl', 'Control room', Icons.developer_board_outlined, [
    _Act('Light', Icons.lightbulb_outlined, 'ctrl.light', 'LIGHT_ON', 'LIGHT_OFF'),
  ]),
];

typedef _Guard = Future<void> Function(AppState app, String cmd);

class _RoomPanel extends StatelessWidget {
  final _Room room;
  final _Guard guard;
  const _RoomPanel({required this.room, required this.guard});

  /// Only genuinely per-room gear (the lights) is addressed by zone. The farm
  /// owns ONE exhaust fan, ONE vent flap, ONE sprinkler — those keep the bare
  /// verb the bridge and firmware already speak, so Live mode does not break
  /// on a token nobody parses.
  String _cmd(_Act a, String verb) =>
      a.channel.startsWith('${room.id}.') && room.id != 'hall'
          ? '$verb|${room.id}'
          : verb;

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final tiles = <Widget>[];
    for (final a in room.acts) {
      tiles.add(a.momentary
          ? _RefillTile(
              label: a.label,
              icon: a.icon,
              level: app.tel.v(a.channel),
              onTap: () => guard(app, _cmd(a, a.onCmd)),
            )
          : _Toggle(
              label: a.label,
              icon: a.icon,
              on: app.tel.v(a.channel) == 1,
              onChanged: (v) => guard(app, _cmd(a, v ? a.onCmd : a.offCmd)),
            ));
    }
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(room.icon, size: 16, color: T.sub),
          const SizedBox(width: 8),
          Text(room.name, style: Theme.of(context).textTheme.titleMedium),
        ]),
        const SizedBox(height: 12),
        // two per row, last odd tile keeps its half rather than stretching
        for (var i = 0; i < tiles.length; i += 2) ...[
          Row(children: [
            Expanded(child: tiles[i]),
            const SizedBox(width: 10),
            Expanded(
                child: i + 1 < tiles.length ? tiles[i + 1] : const SizedBox()),
          ]),
          if (i + 2 < tiles.length) const SizedBox(height: 10),
        ],
      ]),
    );
  }
}

class _RefillTile extends StatelessWidget {
  final String label;
  final IconData icon;
  final double level;
  final VoidCallback onTap;
  const _RefillTile(
      {required this.label, required this.icon, required this.level,
       required this.onTap});

  @override
  Widget build(BuildContext context) {
    final low = level < 20;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: low ? T.warn : T.hairline),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, size: 20, color: low ? T.warn : T.sub),
          const SizedBox(height: 8),
          Text(label, style: Theme.of(context).textTheme.bodyMedium),
          Text('${level.round()}% · tap to refill',
              style: TextStyle(
                  fontSize: 13, color: low ? T.warn : T.sub,
                  fontWeight: FontWeight.w600)),
        ]),
      ),
    );
  }
}

class _Toggle extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool on;
  final ValueChanged<bool> onChanged;
  const _Toggle(
      {required this.label, required this.icon, required this.on,
       required this.onChanged});

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: () => onChanged(!on),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: on ? T.surface2 : Colors.transparent,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: on ? T.accent : T.hairline),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(icon, size: 20, color: on ? T.accent : T.sub),
            const SizedBox(height: 8),
            Text(label, style: Theme.of(context).textTheme.bodyMedium),
            Text(on ? 'On' : 'Off',
                style: TextStyle(
                    fontSize: 13, color: on ? T.accent : T.sub,
                    fontWeight: FontWeight.w600)),
          ]),
        ),
      );
}

class _BenchButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onTap;
  const _BenchButton(this.label, this.icon, this.onTap);
  @override
  Widget build(BuildContext context) => OutlinedButton(
        style: OutlinedButton.styleFrom(
            foregroundColor: T.text,
            side: const BorderSide(color: T.hairline),
            padding: const EdgeInsets.symmetric(vertical: 10)),
        onPressed: onTap,
        child: Column(children: [
          Icon(icon, size: 18, color: T.sub),
          const SizedBox(height: 4),
          Text(label,
              style: const TextStyle(fontSize: 11.5), textAlign: TextAlign.center),
        ]),
      );
}

/// Disarming needs the user PIN (arming does not) — the app-side auth layer
/// that AppState.tryDisarm already implements: 3 misses -> 30 s lockout.
/// What a proven PIN buys.
enum PinPurpose {
  /// Lift the night watch.
  disarm,

  /// Open the remote-control window for [AppState.authWindow].
  control,
}

class PinDialog extends StatefulWidget {
  final PinPurpose purpose;
  const PinDialog({super.key, this.purpose = PinPurpose.disarm});
  @override
  State<PinDialog> createState() => _PinDialogState();
}

class _PinDialogState extends State<PinDialog> {
  final _ctrl = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _submit() {
    final app = context.read<AppState>();
    final digits =
        _ctrl.text.trim().split('').map(int.tryParse).toList();
    if (digits.length != 4 || digits.any((d) => d == null)) {
      setState(() => _error = 'Enter the 4-digit PIN');
      return;
    }
    final d = digits.cast<int>();
    final result = switch (widget.purpose) {
      PinPurpose.disarm => app.tryDisarm(d),
      PinPurpose.control => app.authorizeControl(d),
    };
    switch (result) {
      case PinResult.ok:
        Navigator.of(context).pop(true);
      case PinResult.wrong:
        setState(() {
          _error = 'Wrong PIN (${app.pinFails}/3)';
          _ctrl.clear();
        });
      case PinResult.locked:
        setState(() {
          _error = 'Too many attempts — locked for 30 s';
          _ctrl.clear();
        });
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        backgroundColor: T.surface,
        title: Text(
            widget.purpose == PinPurpose.disarm
                ? 'Disarm night watch'
                : 'Unlock remote control',
            style: const TextStyle(fontSize: 17)),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          if (widget.purpose == PinPurpose.control) ...[
            Text(
                'Stays unlocked for ${AppState.authWindow.inSeconds} s, then '
                'asks again before the next command.',
                style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 12),
          ],
          TextField(
            controller: _ctrl,
            autofocus: true,
            obscureText: true,
            maxLength: 4,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            style: const TextStyle(
                fontSize: 22, letterSpacing: 12, fontFamily: 'Menlo'),
            decoration: InputDecoration(
              counterText: '',
              hintText: '····',
              enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: T.hairline)),
              focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: T.accent)),
            ),
            onSubmitted: (_) => _submit(),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!,
                style: const TextStyle(color: T.danger, fontSize: 13)),
          ],
        ]),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel')),
          FilledButton(onPressed: _submit, child: const Text('Disarm')),
        ],
      );
}

class _ConnectionPanel extends StatefulWidget {
  final AppState app;
  const _ConnectionPanel({required this.app});
  @override
  State<_ConnectionPanel> createState() => _ConnectionPanelState();
}

class _ConnectionPanelState extends State<_ConnectionPanel> {
  late final _url = TextEditingController(text: widget.app.bridgeUrl);

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final app = widget.app;
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          StatusDot(app.connected ? T.ok : T.warn, size: 8),
          const SizedBox(width: 8),
          Expanded(
              child: Text(app.connDetail,
                  style: Theme.of(context).textTheme.bodySmall)),
        ]),
        const SizedBox(height: 12),
        SegmentedButton<bool>(
          segments: const [
            ButtonSegment(value: false, label: Text('Demo data')),
            ButtonSegment(value: true, label: Text('Live farm node')),
          ],
          selected: {app.usingBridge},
          onSelectionChanged: (s) =>
              s.first ? app.useBridge(_url.text.trim()) : app.useFake(),
          style: ButtonStyle(
              side: WidgetStatePropertyAll(BorderSide(color: T.hairline))),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _url,
          style: const TextStyle(fontSize: 14, fontFamily: 'Menlo'),
          decoration: InputDecoration(
            labelText: 'Bridge address (laptop)',
            labelStyle: const TextStyle(color: T.sub, fontSize: 13),
            hintText: 'http://192.168.4.2:5001',
            enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: T.hairline)),
            focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: T.accent)),
          ),
          onSubmitted: (v) => app.useBridge(v.trim()),
        ),
        if (kIsWeb)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: () {
                // The page was served by the bridge, so its own origin is the
                // bridge — one tap out of any wrong address (the sensor
                // board's IP is a tempting, and wrong, thing to paste here).
                _url.text = BridgeDataSource.normalise(Uri.base.origin);
                app.useBridge(_url.text);
              },
              style: TextButton.styleFrom(
                  foregroundColor: T.accent,
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  minimumSize: Size.zero),
              child: const Text('Use the laptop serving this page'),
            ),
          ),
        const SizedBox(height: 8),
        _BoardCard(board: app.board),
      ]),
    );
  }
}

/// What the physical ESP32 sensor board is actually saying, verbatim. The
/// bridge converts raw ADC counts server-side, so the honest thing to show an
/// engineer is both halves: the board's own JSON and what we made of it.
class _BoardCard extends StatelessWidget {
  final BoardMsg? board;
  const _BoardCard({required this.board});

  @override
  Widget build(BuildContext context) {
    final b = board;
    final ok = b?.connected == true;
    final raw = (b?.raw.isNotEmpty ?? false)
        ? const JsonEncoder.withIndent('  ').convert(b!.raw)
        : (b == null
            ? 'bridge has no sensor board configured (start it with --esp)'
            : 'no reply from ${b.url}');
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: T.hairline),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          StatusDot(ok ? T.ok : T.sub, size: 8),
          const SizedBox(width: 8),
          Text('Sensor board${ok ? ' — live' : ''}',
              style: Theme.of(context).textTheme.bodySmall),
        ]),
        const SizedBox(height: 8),
        Text(raw,
            style: const TextStyle(
                fontFamily: 'Menlo', fontSize: 12, color: T.accent)),
        if (b != null && b.converted.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
              'bridge converts → '
              '${b.converted.entries.map((e) => '${e.key}=${e.value}').join(' · ')}',
              style: const TextStyle(fontSize: 12, color: T.sub)),
        ],
        if (b != null && b.pinned.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(
              '${b.pinned.join(', ')} held by a simulator pin — '
              'the board is ignored there until it is released',
              style: const TextStyle(fontSize: 12, color: T.warn)),
        ],
      ]),
    );
  }
}


/// Lock state of remote control, at the head of the Farm panel. Visible state
/// matters here: an operator must be able to see, before reaching for a
/// switch, whether the next tap will act or ask.
class _AuthBar extends StatelessWidget {
  const _AuthBar();

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final open = app.authorized;
    final left = app.authSecondsLeft;
    final color = open ? T.ok : T.sub;
    return Row(children: [
      Icon(open ? Icons.lock_open_rounded : Icons.lock_outline_rounded,
          size: 16, color: color),
      const SizedBox(width: 8),
      Expanded(
        child: Text(
          open
              ? 'Remote control unlocked · ${left}s'
              : 'Remote control locked — PIN before the next command',
          style: Theme.of(context)
              .textTheme
              .bodySmall
              ?.copyWith(color: color),
        ),
      ),
      if (open)
        TextButton(
          onPressed: app.lockControl,
          style: TextButton.styleFrom(
              foregroundColor: T.sub,
              minimumSize: Size.zero,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap),
          child: const Text('Lock now', style: TextStyle(fontSize: 12)),
        ),
    ]);
  }
}
