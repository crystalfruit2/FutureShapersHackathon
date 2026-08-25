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
                  child: SegmentedButton<FarmMode>(
                    segments: const [
                      ButtonSegment(
                          value: FarmMode.day,
                          label: Text('Day'),
                          icon: Icon(Icons.wb_sunny_outlined, size: 18)),
                      ButtonSegment(
                          value: FarmMode.night,
                          label: Text('Night watch'),
                          icon: Icon(Icons.nightlight_outlined, size: 18)),
                    ],
                    selected: {
                      app.mode == FarmMode.night ? FarmMode.night : FarmMode.day
                    },
                    onSelectionChanged: (s) {
                      if (s.first == FarmMode.night) {
                        app.command('ARM');
                      } else {
                        _askPin(context, app); // disarming needs the user PIN
                      }
                    },
                    style: ButtonStyle(
                      side: WidgetStatePropertyAll(
                          BorderSide(color: T.hairline)),
                    ),
                  ),
                ),
              ]),
              const SizedBox(height: 14),
              Row(children: [
                Expanded(
                  child: _Toggle(
                    label: 'Exhaust fan',
                    icon: Icons.air,
                    on: app.tel.v('fan') == 1,
                    onChanged: (v) => app.command(v ? 'FAN_ON' : 'FAN_OFF'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _Toggle(
                    label: 'Vent flap',
                    icon: Icons.hvac_outlined,
                    on: app.tel.v('vent') == 1,
                    onChanged: (_) => app.command('VENT'),
                  ),
                ),
              ]),
            ]),
          ),
          const SectionLabel('Security'),
          Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
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

void _askPin(BuildContext context, AppState app) {
  showModalBottomSheet(
    context: context,
    backgroundColor: T.surface,
    shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => ChangeNotifierProvider.value(value: app, child: const _PinSheet()),
  );
}

/// 4-button PIN pad — deliberately the same four keys as the physical
/// panel's resistor-ladder pad ("authentication & access layers").
class _PinSheet extends StatefulWidget {
  const _PinSheet();
  @override
  State<_PinSheet> createState() => _PinSheetState();
}

class _PinSheetState extends State<_PinSheet> {
  final _digits = <int>[];
  String? _error;

  void _tap(int d) {
    if (_digits.length >= 4) return;
    setState(() => _digits.add(d));
    if (_digits.length == 4) {
      final r = context.read<AppState>().tryDisarm(List.of(_digits));
      switch (r) {
        case PinResult.ok:
          Navigator.pop(context);
        case PinResult.wrong:
          setState(() { _digits.clear(); _error = 'Wrong PIN'; });
        case PinResult.locked:
          setState(() { _digits.clear(); _error = 'Locked out — try again in 30 s'; });
      }
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(24, 20, 24, 40),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('Enter PIN to disarm', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text('Same code as the control-room panel',
              style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 18),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            for (var i = 0; i < 4; i++)
              Container(
                width: 14, height: 14,
                margin: const EdgeInsets.symmetric(horizontal: 7),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: i < _digits.length ? T.accent : Colors.transparent,
                  border: Border.all(color: i < _digits.length ? T.accent : T.hairline, width: 1.5),
                ),
              ),
          ]),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!, style: const TextStyle(color: T.danger, fontSize: 13, fontWeight: FontWeight.w600)),
          ],
          const SizedBox(height: 18),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            for (var d = 1; d <= 4; d++)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6),
                child: SizedBox(
                  width: 64, height: 64,
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                        shape: const CircleBorder(),
                        side: const BorderSide(color: T.hairline),
                        foregroundColor: T.text),
                    onPressed: () => _tap(d),
                    child: Text('$d', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
                  ),
                ),
              ),
          ]),
        ]),
      );
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
