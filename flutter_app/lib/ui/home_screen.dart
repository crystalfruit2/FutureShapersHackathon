import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models.dart';
import 'theme.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          _Header(app: app),
          const SizedBox(height: 20),
          _StatusHero(app: app),
          const SectionLabel('Zones'),
          _ZoneCard(
            icon: Icons.egg_outlined,
            name: 'Poultry hall',
            status: _hallStatus(app.tel),
            rows: [
              _m('Ammonia', app.tel.has('nh3') ? '${app.tel.v('nh3').round()} ppm' : '—',
                  sim: app.tel.sim('nh3')),
              _m('Temperature',
                  app.tel.has('t1') ? '${app.tel.v('t1').round()}° / ${app.tel.v('t2').round()}°' : '—'),
              _m('Humidity', app.tel.has('hum') ? '${app.tel.v('hum').round()}%' : '—'),
            ],
          ),
          const SizedBox(height: 10),
          _ZoneCard(
            icon: Icons.layers_outlined,
            name: 'Manure pit',
            status: _pitStatus(app.tel),
            banner: app.tel.v('gas') >= 700
                ? 'DO NOT ENTER — gas hazard. Most manure-gas victims are would-be rescuers.'
                : null,
            rows: [
              _m('Methane', '${app.tel.v('gas').round()} / 1023',
                  sim: app.tel.sim('gas')),
              _m('Gas valve', app.tel.v('relay', 1) == 1 ? 'Open' : 'CLOSED',
                  emphasized: app.tel.v('relay', 1) != 1),
              _m('Exhaust fan', app.tel.v('fan') == 1 ? 'Running' : 'Off'),
            ],
          ),
          const SizedBox(height: 10),
          _ZoneCard(
            icon: Icons.inventory_2_outlined,
            name: 'Feed & water store',
            status: _storeStatus(app.tel),
            rows: [
              _m('Water level', app.tel.has('water') ? '${app.tel.v('water').round()} / 1023' : '—'),
              _m('Flame', app.tel.v('flame') == 0 ? 'None' : 'DETECTED',
                  sim: app.tel.sim('flame'), emphasized: app.tel.v('flame') != 0),
            ],
          ),
          const SizedBox(height: 10),
          _ZoneCard(
            icon: Icons.dns_outlined,
            name: 'Control room',
            status: app.tel.v('tamp') == 1 ? T.danger : T.ok,
            rows: [
              _m('Cabinet', app.tel.v('tamp') == 1 ? 'OPEN' : 'Closed',
                  emphasized: app.tel.v('tamp') == 1),
              _m('Vent flap', app.tel.v('vent') == 1 ? 'Open' : 'Shut'),
            ],
          ),
          const SectionLabel('Energy'),
          Panel(
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${app.tel.v('saved_pct').round()}%',
                      style: const TextStyle(
                          fontSize: 34, fontWeight: FontWeight.w600, color: T.ok)),
                  const SizedBox(height: 2),
                  Text('power saved vs always-on ventilation',
                      style: Theme.of(context).textTheme.bodySmall),
                ]),
              ),
              const Icon(Icons.bolt_outlined, color: T.sub, size: 28),
            ]),
          ),
        ],
      ),
    );
  }

  Color _hallStatus(Telemetry t) =>
      t.v('nh3') >= 25 ? T.warn : (t.v('t1') >= 32 ? T.warn : T.ok);
  Color _pitStatus(Telemetry t) =>
      t.v('gas') >= 700 ? T.danger : (t.v('gas') >= 450 ? T.warn : T.ok);
  Color _storeStatus(Telemetry t) => t.v('flame') != 0
      ? T.danger
      : (t.has('water') && t.v('water') < 200 ? T.warn : T.ok);
}

class _Header extends StatelessWidget {
  final AppState app;
  const _Header({required this.app});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Row(children: [
          Text('Bio Guard', style: Theme.of(context).textTheme.headlineMedium),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: T.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: T.hairline),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              StatusDot(app.connected ? T.ok : T.warn, size: 7),
              const SizedBox(width: 6),
              Text(app.usingBridge ? (app.connected ? 'Live' : 'Offline') : 'Demo',
                  style: Theme.of(context).textTheme.bodySmall),
            ]),
          ),
        ]),
      );
}

class _StatusHero extends StatelessWidget {
  final AppState app;
  const _StatusHero({required this.app});

  @override
  Widget build(BuildContext context) {
    final (color, title, caption) = switch (app.mode) {
      FarmMode.day => (T.ok, 'All systems normal', '4 zones monitored · daytime mode'),
      FarmMode.night => (T.accent, 'Armed for the night',
          'Perimeter and sound watch active'),
      FarmMode.emergency => (T.danger, 'EMERGENCY', 'Automatic protections engaged'),
      FarmMode.lockdown => (T.warn, 'Locked down',
          'Repeated wrong PINs — enter PIN at the panel'),
      FarmMode.unknown => (T.sub, 'Connecting…', 'Waiting for the farm node'),
    };
    return Panel(
      borderColor: app.mode == FarmMode.emergency ? T.danger : null,
      child: Row(children: [
        StatusDot(color, size: 12),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 2),
            Text(caption, style: Theme.of(context).textTheme.bodySmall),
          ]),
        ),
      ]),
    );
  }
}

class _Metric {
  final String label, value;
  final bool sim, emphasized;
  const _Metric(this.label, this.value, this.sim, this.emphasized);
}

_Metric _m(String label, String value, {bool sim = false, bool emphasized = false}) =>
    _Metric(label, value, sim, emphasized);

class _ZoneCard extends StatelessWidget {
  final IconData icon;
  final String name;
  final Color status;
  final List<_Metric> rows;
  final String? banner;
  const _ZoneCard(
      {required this.icon, required this.name, required this.status,
       required this.rows, this.banner});

  @override
  Widget build(BuildContext context) {
    return Panel(
      borderColor: status == T.danger ? T.danger.withValues(alpha: 0.7) : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 20, color: T.sub),
          const SizedBox(width: 10),
          Text(name, style: Theme.of(context).textTheme.titleMedium),
          const Spacer(),
          StatusDot(status),
        ]),
        const SizedBox(height: 12),
        for (final r in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(children: [
              Text(r.label, style: Theme.of(context).textTheme.bodySmall),
              if (r.sim) const SimBadge(),
              const Spacer(),
              Text(r.value,
                  style: TextStyle(
                      fontSize: 15,
                      fontWeight: r.emphasized ? FontWeight.w700 : FontWeight.w500,
                      color: r.emphasized ? T.danger : T.text)),
            ]),
          ),
        if (banner != null) ...[
          const SizedBox(height: 6),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: T.danger.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(children: [
              const Icon(Icons.dangerous_outlined, color: T.danger, size: 18),
              const SizedBox(width: 8),
              Expanded(
                child: Text(banner!,
                    style: const TextStyle(
                        color: T.danger, fontSize: 13, fontWeight: FontWeight.w600)),
              ),
            ]),
          ),
        ],
      ]),
    );
  }
}
