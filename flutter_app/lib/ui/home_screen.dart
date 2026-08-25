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
    final anomalies = app.tel.anomalies();
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          _Header(app: app),
          const SizedBox(height: 14),
          if (anomalies.isNotEmpty) _AnomalyBanner(anomalies: anomalies),
          if (anomalies.isEmpty) _AllQuiet(app: app),
          const SizedBox(height: 10),
          _FlockCalm(app: app),
          const SectionLabel('Zones'),
          for (final z in zoneMetrics.keys) ...[
            _ZoneCard(zone: z, app: app),
            const SizedBox(height: 10),
          ],
          const SectionLabel('Energy'),
          Panel(
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                    Text('${app.tel.v('saved_pct').round()}%',
                        style: const TextStyle(
                            fontSize: 34, fontWeight: FontWeight.w600, color: T.ok)),
                    const SizedBox(width: 12),
                    Padding(
                      padding: const EdgeInsets.only(bottom: 5),
                      child: Text(
                          '≈ ${(app.tel.v('saved_pct') / 100 * 1440 * 0.8).round()} lei/month',
                          style: const TextStyle(
                              fontSize: 17, fontWeight: FontWeight.w600, color: T.text)),
                    ),
                  ]),
                  const SizedBox(height: 2),
                  Text('power saved vs always-on ventilation',
                      style: Theme.of(context).textTheme.bodySmall),
                  Text('at farm scale: 2 kW ventilation · 0.80 lei/kWh',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(fontSize: 10.5)),
                ]),
              ),
              const Icon(Icons.bolt_outlined, color: T.sub, size: 28),
            ]),
          ),
        ],
      ),
    );
  }
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

/// Red popup at the top whenever anything is off-normal.
class _AnomalyBanner extends StatelessWidget {
  final List<Anomaly> anomalies;
  const _AnomalyBanner({required this.anomalies});

  @override
  Widget build(BuildContext context) {
    final critical = anomalies.any((a) => a.critical);
    final color = critical ? T.danger : T.warn;
    return Panel(
      borderColor: color,
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(critical ? Icons.emergency_outlined : Icons.warning_amber_outlined,
              color: color, size: 20),
          const SizedBox(width: 8),
          Text(critical ? 'Attention required' : 'Off-normal readings',
              style: TextStyle(
                  color: color, fontWeight: FontWeight.w700, fontSize: 15)),
          const Spacer(),
          Text('${anomalies.length}',
              style: TextStyle(color: color, fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 8),
        for (final a in anomalies.take(3))
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text('•  ${a.message}',
                style: TextStyle(
                    color: a.critical ? T.danger : T.text, fontSize: 14)),
          ),
        if (anomalies.length > 3)
          Text('and ${anomalies.length - 3} more…',
              style: Theme.of(context).textTheme.bodySmall),
      ]),
    );
  }
}

class _AllQuiet extends StatelessWidget {
  final AppState app;
  const _AllQuiet({required this.app});
  @override
  Widget build(BuildContext context) {
    final (title, caption) = switch (app.mode) {
      FarmMode.night => ('Armed for the night', 'Perimeter and sound watch active'),
      FarmMode.lockdown => ('Locked down', 'Enter PIN at the panel'),
      _ => ('All systems normal', '${zoneNames.length} zones monitored'),
    };
    return Panel(
      child: Row(children: [
        const StatusDot(T.ok, size: 12),
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

/// Welfare read derived from sensors nothing else surfaces together:
/// hall sound activity + motion. Cheap signal, real farmer value.
class _FlockCalm extends StatelessWidget {
  final AppState app;
  const _FlockCalm({required this.app});

  @override
  Widget build(BuildContext context) {
    final noisy = app.tel.v('hall.sound') >= 1;
    final moving =
        app.tel.v('hall.motion') >= 1 || app.tel.v('field.motion') >= 1;
    final (label, caption, color, icon) = switch ((noisy, moving)) {
      (true, true) => ('Flock distressed',
          'Noise and movement together — check the hall',
          T.danger, Icons.notifications_active_outlined),
      (true, false) => ('Flock restless',
          'Unusual sound activity in the hall', T.warn, Icons.graphic_eq),
      (false, true) => ('Flock stirring',
          'Movement without noise — likely normal', T.warn,
          Icons.directions_walk_outlined),
      (false, false) => ('Flock calm',
          'Sound and movement inside the normal band', T.ok,
          Icons.spa_outlined),
    };
    return Panel(
      child: Row(children: [
        Icon(icon, size: 20, color: color),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label,
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(color: color)),
            const SizedBox(height: 2),
            Text(caption, style: Theme.of(context).textTheme.bodySmall),
          ]),
        ),
      ]),
    );
  }
}

const _zoneIcons = {
  'hall': Icons.egg_outlined,
  'field': Icons.grass_outlined,
  'stor': Icons.inventory_2_outlined,
  'ctrl': Icons.dns_outlined,
};

class _ZoneCard extends StatelessWidget {
  final String zone;
  final AppState app;
  const _ZoneCard({required this.zone, required this.app});

  @override
  Widget build(BuildContext context) {
    final metrics = zoneMetrics[zone]!;
    Color worst = T.ok;
    for (final m in metrics) {
      final c = app.tel.zoneMetric(zone, m);
      if (c == null) continue;
      final a = checkMetric(zone, m, c.value);
      if (a != null) worst = a.critical ? T.danger : (worst == T.danger ? worst : T.warn);
    }
    return Panel(
      borderColor: worst == T.danger ? T.danger.withValues(alpha: 0.7) : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(_zoneIcons[zone], size: 20, color: T.sub),
          const SizedBox(width: 10),
          Text(zoneNames[zone]!, style: Theme.of(context).textTheme.titleMedium),
          const Spacer(),
          StatusDot(worst),
        ]),
        const SizedBox(height: 12),
        // two-column metric grid
        LayoutBuilder(builder: (context, box) {
          final colW = (box.maxWidth - 12) / 2;
          return Wrap(spacing: 12, runSpacing: 8, children: [
            for (final m in metrics)
              SizedBox(width: colW, child: _MetricRow(zone: zone, metric: m, app: app)),
          ]);
        }),
      ]),
    );
  }
}

class _MetricRow extends StatelessWidget {
  final String zone, metric;
  final AppState app;
  const _MetricRow({required this.zone, required this.metric, required this.app});

  @override
  Widget build(BuildContext context) {
    final c = app.tel.zoneMetric(zone, metric);
    final (label, unit) = metricDefs[metric]!;
    final anomaly = c == null ? null : checkMetric(zone, metric, c.value);
    Widget value;
    if (c == null) {
      value = const Text('—', style: TextStyle(color: T.sub, fontSize: 14));
    } else if (metric == 'motion' || metric == 'fire') {
      final yes = c.value >= 1;
      value = Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
        decoration: BoxDecoration(
          color: yes ? T.danger.withValues(alpha: 0.15) : Colors.transparent,
          border: Border.all(color: yes ? T.danger : T.hairline),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(yes ? 'YES' : 'no',
            style: TextStyle(
                fontSize: 12,
                fontWeight: yes ? FontWeight.w700 : FontWeight.w500,
                color: yes ? T.danger : T.sub)),
      );
    } else if (metric == 'light') {
      value = Text(c.value >= 1 ? 'On' : 'Off',
          style: TextStyle(fontSize: 14, color: c.value >= 1 ? T.text : T.sub));
    } else if (metric == 'sound') {
      value = Text(c.value >= 1 ? 'Active' : 'Quiet',
          style: TextStyle(
              fontSize: 14, color: c.value >= 1 ? T.warn : T.sub));
    } else if (metric == 'gas') {
      final pct = (c.value / 700 * 100).round();
      value = Text('$pct% of alarm',
          style: TextStyle(
              fontSize: 14,
              fontWeight: anomaly != null ? FontWeight.w700 : FontWeight.w500,
              color: anomaly == null ? T.text : (anomaly.critical ? T.danger : T.warn)));
    } else {
      value = Text('${c.value.round()}$unit',
          style: TextStyle(
              fontSize: 14,
              fontWeight: anomaly != null ? FontWeight.w700 : FontWeight.w500,
              color: anomaly == null ? T.text : (anomaly.critical ? T.danger : T.warn)));
    }
    return Row(children: [
      Expanded(
        child: Row(children: [
          Flexible(
            child: Text(label,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall),
          ),
          if (c?.simulated ?? false) const SimBadge(),
        ]),
      ),
      value,
    ]);
  }
}
