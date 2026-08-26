/// Fleet tab — every farm, one model.
///
/// The other tabs answer "what is my barn doing right now". This one answers
/// the question a second customer creates: what does one farm's data become
/// once it sits next to everyone else's? Three answers, in order of how much
/// the cloud actually earns them:
///
///   * a farm's 6-hour incident risk, from a model trained on the whole fleet
///     rather than on that farm's own short history
///   * WHY it scored that way — the model's per-feature contributions, so the
///     number is arguable rather than oracular
///   * correlated distress across neighbouring farms, which no single farm
///     can observe about itself
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../data/cloud_source.dart';
import '../main.dart';
import 'theme.dart';

class FleetScreen extends StatefulWidget {
  const FleetScreen({super.key});
  @override
  State<FleetScreen> createState() => _FleetScreenState();
}

class _FleetScreenState extends State<FleetScreen> {
  FleetSnapshot? _snap;
  String? _error;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    if (_loading) return;
    setState(() => _loading = true);
    final url = context.read<AppState>().bridgeUrl;
    try {
      final s = await FleetService(url).load();
      if (mounted) setState(() { _snap = s; _error = null; });
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _snap;
    return Scaffold(
      backgroundColor: T.bg,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          backgroundColor: T.surface,
          color: T.accent,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
            children: [
              _header(s),
              if (_error != null && s == null) _errorPanel(),
              if (s != null) ...[
                const SectionLabel('Fleet'),
                _summary(s),
                if (s.regions.isNotEmpty) ...[
                  const SectionLabel('Regional biosecurity'),
                  for (final r in s.regions) _regionCard(r),
                ],
                const SectionLabel('Farms'),
                for (final f in s.farms) _farmCard(f),
                const SectionLabel('Model'),
                _modelCard(s),
              ] else if (_error == null)
                const Padding(
                  padding: EdgeInsets.only(top: 60),
                  child: Center(
                      child: CircularProgressIndicator(color: T.accent)),
                ),
            ],
          ),
        ),
      ),
    );
  }

  // ── chrome ─────────────────────────────────────────────────────────────
  Widget _header(FleetSnapshot? s) => Padding(
        padding: const EdgeInsets.only(top: 8, bottom: 4),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Fleet', style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 2),
              Text(
                s == null
                    ? FleetService.initDetail
                    : 'via ${s.source} · ${s.farms.length} farms · '
                        '${_n(s.animals)} animals',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ]),
          ),
          IconButton(
            onPressed: _loading ? null : _load,
            icon: _loading
                ? const SizedBox(
                    width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: T.sub))
                : const Icon(Icons.refresh_rounded, color: T.sub),
          ),
        ]),
      );

  Widget _errorPanel() => Padding(
        padding: const EdgeInsets.only(top: 16),
        child: Panel(
          borderColor: T.warn.withValues(alpha: 0.5),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Row(children: [
              Icon(Icons.cloud_off_rounded, color: T.warn, size: 18),
              SizedBox(width: 8),
              Text('Fleet unavailable',
                  style: TextStyle(fontWeight: FontWeight.w600, color: T.text)),
            ]),
            const SizedBox(height: 8),
            Text(
              'Neither Firestore nor the bridge answered. The farm tabs are '
              'unaffected — they read the node directly.\n\n$_error',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ]),
        ),
      );

  // ── fleet summary ──────────────────────────────────────────────────────
  Widget _summary(FleetSnapshot s) => Panel(
        child: Row(children: [
          _stat('Farms', '${s.farms.length}', T.text),
          _stat('At risk', '${s.atRisk}', s.atRisk > 0 ? T.danger : T.ok),
          _stat('Alerts 24 h', '${s.alerts24}',
              s.alerts24 > 0 ? T.warn : T.ok),
          _stat('Samples', _n((s.summary['samples'] as num?)?.toInt() ?? 0),
              T.text),
        ]),
      );

  Widget _stat(String label, String value, Color c) => Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label.toUpperCase(),
              style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 5),
          Text(value,
              style: TextStyle(
                  fontSize: 21, fontWeight: FontWeight.w700, color: c,
                  fontFeatures: const [FontFeature.tabularFigures()])),
        ]),
      );

  // ── the cross-farm finding ─────────────────────────────────────────────
  Widget _regionCard(RegionSignal r) {
    final c = r.severity == 'ALERT' ? T.danger : T.warn;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Panel(
        borderColor: c.withValues(alpha: 0.55),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(Icons.hub_rounded, color: c, size: 17),
            const SizedBox(width: 8),
            Expanded(
              child: Text('${r.region} — ${r.severity.toLowerCase()}',
                  style: TextStyle(
                      fontWeight: FontWeight.w700, color: c, fontSize: 15)),
            ),
          ]),
          const SizedBox(height: 8),
          Text(r.text, style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: 8),
          Text(r.names.join('  ·  '),
              style: Theme.of(context).textTheme.bodySmall),
        ]),
      ),
    );
  }

  // ── one farm ───────────────────────────────────────────────────────────
  Color _riskColor(double r) =>
      r >= 45 ? T.danger : (r >= 20 ? T.warn : T.ok);

  Widget _farmCard(FleetFarm f) {
    final c = _riskColor(f.risk);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Panel(
        borderColor: f.risk >= 45 ? c.withValues(alpha: 0.5) : null,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    if (f.isLiveNode) ...[
                      const StatusDot(T.ok, size: 7),
                      const SizedBox(width: 6),
                    ],
                    Flexible(
                      child: Text(f.name,
                          style: const TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w600,
                              color: T.text)),
                    ),
                  ]),
                  const SizedBox(height: 3),
                  Text('${f.region} · ${f.species} · ${_n(f.herd)} head',
                      style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(f.risk < 1 ? '<1%' : '${f.risk.round()}%',
                  style: TextStyle(
                      fontSize: 24, fontWeight: FontWeight.w700, color: c,
                      height: 1,
                      fontFeatures: const [FontFeature.tabularFigures()])),
              const SizedBox(height: 3),
              Text('6 H RISK',
                  style: Theme.of(context).textTheme.labelSmall),
            ]),
          ]),
          const SizedBox(height: 11),
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: (f.risk / 100).clamp(0.0, 1.0),
              minHeight: 4,
              backgroundColor: T.surface2,
              valueColor: AlwaysStoppedAnimation(c),
            ),
          ),
          if (f.live.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: [
              _chip('NH₃', f.live['nh3'], ' ppm'),
              _chip('Temp', f.live['temp'], '°'),
              _chip('Hum', f.live['hum'], '%'),
              _chip('CH₄', f.live['gas'], '', dp: 0),
              _chip('Water', f.live['water'], '%', dp: 0),
              _chip('Feed', f.live['food'], '%', dp: 0),
            ].whereType<Widget>().toList()),
          ],
          if (f.drivers.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text.rich(
              TextSpan(children: [
                TextSpan(text: 'Driven by  ',
                    style: Theme.of(context).textTheme.bodySmall),
                for (var i = 0; i < f.drivers.length; i++) ...[
                  if (i > 0)
                    TextSpan(text: '  ·  ',
                        style: Theme.of(context).textTheme.bodySmall),
                  TextSpan(
                      text: f.drivers[i].factor,
                      style: const TextStyle(
                          fontSize: 13, color: T.text,
                          fontWeight: FontWeight.w600)),
                  TextSpan(text: ' ${f.drivers[i].share}%',
                      style: Theme.of(context).textTheme.bodySmall),
                ],
              ]),
            ),
          ],
          for (final x in f.forecast.take(2)) ...[
            const SizedBox(height: 8),
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(Icons.trending_up_rounded, size: 15,
                  color: x.etaH == 0 ? T.danger : T.warn),
              const SizedBox(width: 7),
              Expanded(
                child: Text('${x.metric.toUpperCase()} ${x.text}',
                    style: TextStyle(
                        fontSize: 13,
                        color: x.etaH == 0 ? T.danger : T.warn)),
              ),
            ]),
          ],
          if (f.markers.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final m in f.markers)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                  decoration: BoxDecoration(
                    border: Border.all(color: T.hairline),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(m.replaceAll('_', ' ').toLowerCase(),
                      style: const TextStyle(fontSize: 10.5, color: T.sub)),
                ),
            ]),
          ],
        ]),
      ),
    );
  }

  Widget? _chip(String label, double? v, String unit, {int dp = 1}) {
    if (v == null) return null;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: T.surface2,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: T.hairline),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 2),
        Text('${v.toStringAsFixed(dp)}$unit',
            style: const TextStyle(
                fontSize: 14, fontWeight: FontWeight.w600, color: T.text,
                fontFeatures: [FontFeature.tabularFigures()])),
      ]),
    );
  }

  // ── model provenance ───────────────────────────────────────────────────
  Widget _modelCard(FleetSnapshot s) {
    final m = s.model;
    if (m.isEmpty) {
      return Panel(
        child: Text('No fleet model has been trained yet.',
            style: Theme.of(context).textTheme.bodySmall),
      );
    }
    String g(String k) => '${m[k] ?? '—'}';
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(
          'Logistic regression over ${g('features')} channel features, trained '
          'on ${_n((m['samples'] as num?)?.toInt() ?? 0)} windows pooled from '
          'every farm. Predicts an alert-grade incident '
          '${g('horizon_h')} hours ahead.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 12),
        for (final r in [
          ('Trained', g('trained_at')),
          ('Incidents learned from', g('incidents')),
          ('Base incident rate', '${g('base_rate')} %'),
          ('Training AUC', g('auc')),
        ])
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(children: [
              Expanded(
                  child: Text(r.$1,
                      style: Theme.of(context).textTheme.bodySmall)),
              Text(r.$2,
                  style: const TextStyle(
                      fontSize: 13, color: T.text,
                      fontFeatures: [FontFeature.tabularFigures()])),
            ]),
          ),
      ]),
    );
  }

  static String _n(int v) {
    final s = v.toString();
    final b = StringBuffer();
    for (var i = 0; i < s.length; i++) {
      if (i > 0 && (s.length - i) % 3 == 0) b.write(',');
      b.write(s[i]);
    }
    return b.toString();
  }
}
