import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/demo_series.dart';
import '../main.dart';
import '../models.dart';
import 'theme.dart';
import 'trend_chart.dart';

enum _Range { h24, d7, m1, m3, y1 }

const _rangeLabels = {
  _Range.h24: '24h', _Range.d7: '7d', _Range.m1: '1m',
  _Range.m3: '3m', _Range.y1: '1y',
};
const _rangeSpans = {
  _Range.h24: Duration(hours: 24), _Range.d7: Duration(days: 7),
  _Range.m1: Duration(days: 30), _Range.m3: Duration(days: 90),
  _Range.y1: Duration(days: 365),
};

class EventsScreen extends StatefulWidget {
  const EventsScreen({super.key});
  @override
  State<EventsScreen> createState() => _EventsScreenState();
}

class _EventsScreenState extends State<EventsScreen> {
  _Range _range = _Range.h24;

  String _xLabel(DateTime t) => switch (_range) {
        _Range.h24 => '${t.hour.toString().padLeft(2, '0')}:00',
        _Range.d7 => const ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][t.weekday - 1],
        _Range.m1 || _Range.m3 => '${t.day}.${t.month}',
        _Range.y1 => const ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][t.month - 1],
      };

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final span = _rangeSpans[_range]!;
    // quantize to the minute so 1 Hz telemetry rebuilds reuse identical chart
    // data (fl_chart animates on data change — sub-minute drift = visible wobble)
    final now = DateTime.now();
    final until = DateTime(now.year, now.month, now.day, now.hour, now.minute);
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          Text('Activity', style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(children: [
              for (final r in _Range.values)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(_rangeLabels[r]!),
                    selected: _range == r,
                    onSelected: (_) => setState(() => _range = r),
                    showCheckmark: false,
                    labelStyle: TextStyle(
                        fontSize: 13,
                        color: _range == r ? T.text : T.sub,
                        fontWeight: _range == r ? FontWeight.w600 : FontWeight.w400),
                    selectedColor: T.surface2,
                    backgroundColor: Colors.transparent,
                    side: BorderSide(color: _range == r ? T.accent : T.hairline),
                  ),
                ),
            ]),
          ),
          const SizedBox(height: 12),
          TrendChart(
            title: 'Sensor telemetry trend lines (last ${_rangeLabels[_range]})',
            xLabel: _xLabel,
            series: [
              TrendSeries('Zone temp average (°C)', chartYellow,
                  demoSeries('temp', span, 48, until: until)),
              TrendSeries('Hall humidity (%)', chartBlue,
                  demoSeries('hum', span, 48, until: until)),
            ],
          ),
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Text(
                app.usingBridge
                    ? 'Trend history is demo data until the node accumulates logs.'
                    : 'Demo data — deterministic generated history.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(fontSize: 11)),
          ),
          const SizedBox(height: 12),
          _StatRow(app: app, until: until),
          const SectionLabel('Incident and override log'),
          if (app.events.isEmpty)
            Panel(
                child: Text('Nothing yet — the farm is quiet.',
                    style: Theme.of(context).textTheme.bodySmall))
          else
            for (final e in app.events.take(60)) ...[
              _EventTile(e: e),
              const SizedBox(height: 8),
            ],
        ],
      ),
    );
  }
}

String _detail(StrajerEvent e) {
  if (e.raw.startsWith('SEC|')) return 'Cyber defense · command refused';
  final zone = zoneNames[e.zone] ?? (e.zone.isEmpty ? '' : e.zone);
  final val = e.parts.length > 4 ? e.parts[4] : '';
  return [if (zone.isNotEmpty) zone, if (val.isNotEmpty && val != '0') 'value $val']
      .join(' · ');
}

/// Compact stat tiles — echoes the reference design's right-hand column.
class _StatRow extends StatelessWidget {
  final AppState app;
  final DateTime until;
  const _StatRow({required this.app, required this.until});

  @override
  Widget build(BuildContext context) {
    final weekEvents = app.events.length;
    final tempNow = demoSeries('temp', const Duration(days: 7), 8, until: until);
    final avgThis = tempNow.skip(4).map((p) => p.v).reduce((a, b) => a + b) / 4;
    final avgLast = tempNow.take(4).map((p) => p.v).reduce((a, b) => a + b) / 4;
    Widget tile(String label, String value, {Color color = T.text, String? sub}) =>
        Expanded(
          child: Panel(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(label.toUpperCase(),
                  style: Theme.of(context)
                      .textTheme
                      .labelSmall
                      ?.copyWith(fontSize: 9.5)),
              const SizedBox(height: 6),
              Text(value,
                  style: TextStyle(
                      fontSize: 20, fontWeight: FontWeight.w700, color: color)),
              if (sub != null)
                Text(sub, style: Theme.of(context).textTheme.bodySmall?.copyWith(fontSize: 10)),
            ]),
          ),
        );
    return Row(children: [
      tile('Events', '$weekEvents', sub: 'this session'),
      const SizedBox(width: 10),
      tile('Avg temp', '${avgThis.round()}°',
          sub: 'vs ${avgLast.round()}° last wk',
          color: avgThis > avgLast ? T.warn : T.ok),
      const SizedBox(width: 10),
      tile('Cyber blocks',
          '${app.events.where((e) => e.sev == Severity.sec).length}',
          color: T.cyber, sub: 'refused commands'),
    ]);
  }
}

class _EventTile extends StatelessWidget {
  final StrajerEvent e;
  const _EventTile({required this.e});

  @override
  Widget build(BuildContext context) {
    final isAi = e.raw.startsWith('AI|');
    final (color, icon) = switch (e.sev) {
      Severity.emerg => (T.danger, Icons.emergency_outlined),
      Severity.alert => (T.danger, Icons.notification_important_outlined),
      Severity.warn => (T.warn, Icons.warning_amber_outlined),
      Severity.sec => (T.cyber, Icons.shield_outlined),
      Severity.info => (T.sub, Icons.check_circle_outline),
    };
    // Analyst findings (AI|kind|zone|what|message|sev) already carry farmer copy.
    final title = isAi && e.parts.length > 4
        ? e.parts[4]
        : e.raw.startsWith('SEC|')
            ? humanEvent(e.parts[1])
            : humanEvent(e.type);
    return Panel(
      padding: const EdgeInsets.all(12),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          width: 34, height: 34,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(isAi ? Icons.insights_outlined : icon, size: 18, color: color),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 3),
            Text(_detail(e), style: Theme.of(context).textTheme.bodySmall),
          ]),
        ),
        const SizedBox(width: 8),
        Text(e.time, style: Theme.of(context).textTheme.bodySmall),
      ]),
    );
  }
}
