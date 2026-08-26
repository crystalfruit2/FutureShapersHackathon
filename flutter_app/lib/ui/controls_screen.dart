import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models.dart';
import 'theme.dart';

class ControlsScreen extends StatefulWidget {
  const ControlsScreen({super.key});
  @override
  State<ControlsScreen> createState() => _ControlsScreenState();
}

class _ControlsScreenState extends State<ControlsScreen> {
  double _gas = 120, _nh3 = 8;

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
                  'admin' => 'Full control — protected commands are PIN-signed.',
                  'operator' =>
                    'Runs the farm day-to-day, but cannot switch safety gear off mid-incident and cannot push firmware.',
                  _ =>
                    'Read-only. Controls are disabled here AND the bridge rejects anything this role sends.',
                },
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ]),
          ),
          AbsorbPointer(
            absorbing: app.role == 'viewer',
            child: Opacity(
              opacity: app.role == 'viewer' ? 0.45 : 1.0,
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
          const SectionLabel('Demo director'),
          Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('One tap = one rehearsed pitch scene. The operator taps, the narrator talks.',
                  style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 10),
              Row(children: [
                for (final (n, label) in [(1, 'Control'), (2, 'Energy'), (3, 'Security'), (4, 'Gas + cyber')]) ...[
                  Expanded(
                    child: OutlinedButton(
                      style: OutlinedButton.styleFrom(
                          foregroundColor: app.sceneRunning ? T.sub : T.text,
                          side: const BorderSide(color: T.hairline),
                          padding: const EdgeInsets.symmetric(vertical: 10)),
                      onPressed: app.sceneRunning ? null : () => app.runScene(n),
                      child: Column(children: [
                        Text('$n', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                        Text(label, style: const TextStyle(fontSize: 10.5)),
                      ]),
                    ),
                  ),
                  if (n < 4) const SizedBox(width: 8),
                ],
              ]),
              if (app.sceneRunning) ...[
                const SizedBox(height: 10),
                Row(children: [
                  const SizedBox(width: 14, height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2, color: T.accent)),
                  const SizedBox(width: 8),
                  Text('Scene running…', style: Theme.of(context).textTheme.bodySmall),
                ]),
              ],
            ]),
          ),
          const SectionLabel('Farm'),
          Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(
                  child: _Toggle(
                    label: 'Light',
                    icon: Icons.lightbulb_outlined,
                    on: app.tel.v('hall.light') == 1,
                    onChanged: (v) => app.command(v ? 'LIGHT_ON' : 'LIGHT_OFF'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _Toggle(
                    label: 'Fan',
                    icon: Icons.wind_power_outlined,
                    on: app.tel.v('cfan') == 1,
                    onChanged: (v) => app.command(v ? 'CFAN_ON' : 'CFAN_OFF'),
                  ),
                ),
              ]),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                  child: _Toggle(
                    label: 'Vent flap',
                    icon: Icons.hvac_outlined,
                    on: app.tel.v('vent') == 1,
                    onChanged: (_) => app.command('VENT'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _Toggle(
                    label: 'Exhaust fan',
                    icon: Icons.air,
                    on: app.tel.v('fan') == 1,
                    onChanged: (v) => app.command(v ? 'FAN_ON' : 'FAN_OFF'),
                  ),
                ),
              ]),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                  child: _RefillTile(
                    label: 'Water refill',
                    icon: Icons.water_drop_outlined,
                    level: app.tel.v('hall.water'),
                    onTap: () => app.command('REFILL_WATER'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _RefillTile(
                    label: 'Food refill',
                    icon: Icons.rice_bowl_outlined,
                    level: app.tel.v('hall.food'),
                    onTap: () => app.command('REFILL_FOOD'),
                  ),
                ),
              ]),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                  child: _Toggle(
                    label: 'Sprinkler',
                    icon: Icons.shower_outlined,
                    on: app.tel.v('spr') == 1,
                    onChanged: (v) =>
                        app.command(v ? 'SPRINKLER_ON' : 'SPRINKLER_OFF'),
                  ),
                ),
                const SizedBox(width: 10),
                const Expanded(child: SizedBox()),
              ]),
            ]),
          ),
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
              _SliderRow(
                label: 'Methane (pit)',
                value: _gas, max: 1023,
                display: _gas.round().toString(),
                onChanged: (v) => setState(() => _gas = v),
                onChangeEnd: (v) => app.simulate('gas', v.round()),
              ),
              _SliderRow(
                label: 'Ammonia (hall)',
                value: _nh3, max: 80,
                display: '${_nh3.round()} ppm',
                onChanged: (v) => setState(() => _nh3 = v),
                onChangeEnd: (v) => app.simulate('nh3', v.round()),
              ),
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

class _SliderRow extends StatelessWidget {
  final String label, display;
  final double value, max;
  final ValueChanged<double> onChanged, onChangeEnd;
  const _SliderRow(
      {required this.label, required this.value, required this.max,
       required this.display, required this.onChanged, required this.onChangeEnd});

  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(label, style: Theme.of(context).textTheme.bodyMedium),
          const Spacer(),
          Text(display, style: Theme.of(context).textTheme.bodySmall),
        ]),
        Slider(
          value: value.clamp(0, max), max: max,
          activeColor: T.cyber,
          onChanged: onChanged, onChangeEnd: onChangeEnd,
        ),
      ]);
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
class PinDialog extends StatefulWidget {
  const PinDialog({super.key});
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
    switch (app.tryDisarm(digits.cast<int>())) {
      case PinResult.ok:
        Navigator.of(context).pop();
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
        title: const Text('Disarm night watch', style: TextStyle(fontSize: 17)),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
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
            hintText: 'http://192.168.1.20:5001',
            enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: T.hairline)),
            focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: T.accent)),
          ),
          onSubmitted: (v) => app.useBridge(v.trim()),
        ),
      ]),
    );
  }
}
