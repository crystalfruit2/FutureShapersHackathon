/// Trend line chart styled after the team's reference design:
/// dark panel, small-caps header, yellow + blue lines, legend dots.
library;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import '../data/demo_series.dart';
import 'theme.dart';

const chartYellow = Color(0xFFFFD60A);
const chartBlue = Color(0xFF4DA3FF);

class TrendSeries {
  final String label;
  final Color color;
  final List<Point> points;
  final bool dashed;
  const TrendSeries(this.label, this.color, this.points, {this.dashed = false});
}

class TrendChart extends StatelessWidget {
  final String title;
  final List<TrendSeries> series;
  final String Function(DateTime) xLabel;
  final double height;
  const TrendChart(
      {super.key, required this.title, required this.series,
       required this.xLabel, this.height = 190});

  @override
  Widget build(BuildContext context) {
    if (series.isEmpty || series.every((s) => s.points.length < 2)) {
      return Panel(child: Text('No data yet', style: Theme.of(context).textTheme.bodySmall));
    }
    double t0 = double.infinity, t1 = -double.infinity;
    double minY = double.infinity, maxY = -double.infinity;
    for (final s in series) {
      for (final p in s.points) {
        final x = p.t.millisecondsSinceEpoch.toDouble();
        if (x < t0) t0 = x;
        if (x > t1) t1 = x;
        if (p.v < minY) minY = p.v;
        if (p.v > maxY) maxY = p.v;
      }
    }
    final pad = (maxY - minY) * 0.25 + 1;
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(letterSpacing: 1.1)),
        const SizedBox(height: 14),
        SizedBox(
          height: height,
          child: LineChart(LineChartData(
            minX: t0, maxX: t1, minY: minY - pad, maxY: maxY + pad,
            gridData: FlGridData(
              show: true, drawVerticalLine: false,
              horizontalInterval: ((maxY - minY + 2 * pad) / 4).clamp(0.1, double.infinity),
              getDrawingHorizontalLine: (v) =>
                  const FlLine(color: T.hairline, strokeWidth: 0.6),
            ),
            titlesData: FlTitlesData(
              topTitles: const AxisTitles(),
              rightTitles: const AxisTitles(),
              leftTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true, reservedSize: 34,
                  interval: ((maxY - minY + 2 * pad) / 4).clamp(1, double.infinity),
                  getTitlesWidget: (v, meta) => v >= meta.max
                      ? const SizedBox.shrink()
                      : Text(v.round().toString(),
                          style: const TextStyle(color: T.sub, fontSize: 10)),
                ),
              ),
              bottomTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true, reservedSize: 22,
                  interval: ((t1 - t0) / 4).clamp(1, double.infinity),
                  getTitlesWidget: (v, meta) {
                    if (v <= t0 || v >= t1) return const SizedBox.shrink();
                    return Text(
                        xLabel(DateTime.fromMillisecondsSinceEpoch(v.round())),
                        style: const TextStyle(color: T.sub, fontSize: 10));
                  },
                ),
              ),
            ),
            borderData: FlBorderData(show: false),
            lineTouchData: const LineTouchData(enabled: false),
            lineBarsData: [
              for (final s in series)
                LineChartBarData(
                  spots: [
                    for (final p in s.points)
                      FlSpot(p.t.millisecondsSinceEpoch.toDouble(), p.v)
                  ],
                  color: s.color,
                  barWidth: 2.4,
                  isCurved: true,
                  curveSmoothness: 0.25,
                  preventCurveOverShooting: true,
                  dotData: const FlDotData(show: false),
                  dashArray: s.dashed ? [6, 5] : null,
                ),
            ],
          )),
        ),
        const SizedBox(height: 12),
        Wrap(spacing: 18, runSpacing: 6, children: [
          for (final s in series)
            Row(mainAxisSize: MainAxisSize.min, children: [
              if (s.dashed)
                Row(mainAxisSize: MainAxisSize.min, children: [
                  for (var i = 0; i < 3; i++)
                    Container(width: 4, height: 3.5,
                        margin: const EdgeInsets.only(right: 2),
                        decoration: BoxDecoration(
                            color: s.color,
                            borderRadius: BorderRadius.circular(2))),
                ])
              else
                Container(width: 14, height: 3.5,
                    decoration: BoxDecoration(
                        color: s.color, borderRadius: BorderRadius.circular(2))),
              const SizedBox(width: 6),
              Text(s.label, style: Theme.of(context).textTheme.bodySmall),
            ]),
        ]),
      ]),
    );
  }
}
