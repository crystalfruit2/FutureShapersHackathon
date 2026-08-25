/// Forecast: on-device seasonal model over farm telemetry (next 24h inside),
/// cross-checked against the official Open-Meteo forecast for the farm's
/// location (outside). Open-Meteo is free and keyless.
library;

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../data/demo_series.dart';
import 'theme.dart';
import 'trend_chart.dart';

/// Turns the outside forecast into a farm decision — "demo the decision,
/// not the plumbing".
class _Advice {
  final IconData icon;
  final Color color;
  final String title, body;
  const _Advice(this.icon, this.color, this.title, this.body);
}

_Advice _adviceFrom(List<Point>? outTemp) {
  final src = outTemp ?? demoForecast('temp', 24);
  var peak = src.first, low = src.first;
  for (final p in src) {
    if (p.v > peak.v) peak = p;
    if (p.v < low.v) low = p;
  }
  String hh(DateTime t) => '${t.hour.toString().padLeft(2, '0')}:00';
  if (peak.v >= 30) {
    return _Advice(Icons.thermostat_outlined, T.warn,
        'Pre-cool the hall tonight',
        'Outside peaks at ${peak.v.round()}° around ${hh(peak.t)}. Ventilating '
        'with the ${low.v.round()}° air around ${hh(low.t)} is estimated cheaper and safer '
        'than fighting the heat at the peak.');
  }
  if (low.v <= 2) {
    return _Advice(Icons.ac_unit_outlined, T.accent,
        'Frost risk — protect the water line',
        'Outside drops to ${low.v.round()}° around ${hh(low.t)}. Check drinker-line '
        'heating before the night shift ends.');
  }
  return _Advice(Icons.check_circle_outline, T.ok,
      'No pre-emptive action needed',
      'Outside stays between ${low.v.round()}° and ${peak.v.round()}° for the next 24 h. '
      'Normal ventilation program is sufficient.');
}

class ForecastScreen extends StatefulWidget {
  const ForecastScreen({super.key});
  @override
  State<ForecastScreen> createState() => _ForecastScreenState();
}

class _ForecastScreenState extends State<ForecastScreen> {
  List<Point>? _outTemp, _outHum;
  String _weatherStatus = 'Loading official forecast…';

  @override
  void initState() {
    super.initState();
    _fetchWeather();
  }

  Future<void> _fetchWeather() async {
    setState(() => _weatherStatus = 'Loading official forecast…');
    try {
      // Bucharest — swap coords for the farm's real location
      final r = await http
          .get(Uri.parse('https://api.open-meteo.com/v1/forecast'
              '?latitude=44.43&longitude=26.10&timezone=auto'
              '&hourly=temperature_2m,relative_humidity_2m&forecast_days=2'))
          .timeout(const Duration(seconds: 10));
      final j = jsonDecode(r.body) as Map<String, dynamic>;
      final times = (j['hourly']['time'] as List).cast<String>();
      final temps = (j['hourly']['temperature_2m'] as List).cast<num>();
      final hums = (j['hourly']['relative_humidity_2m'] as List).cast<num>();
      final now = DateTime.now();
      final tOut = <Point>[], hOut = <Point>[];
      for (var i = 0; i < times.length; i++) {
        final t = DateTime.parse(times[i]);
        if (t.isAfter(now.subtract(const Duration(hours: 1))) &&
            t.isBefore(now.add(const Duration(hours: 25)))) {
          tOut.add((t: t, v: temps[i].toDouble()));
          hOut.add((t: t, v: hums[i].toDouble()));
        }
      }
      if (!mounted) return;
      setState(() {
        _outTemp = tOut;
        _outHum = hOut;
        _weatherStatus = 'Open-Meteo · Bucharest · next 24h';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _weatherStatus = 'Official forecast unavailable (offline?) — showing farm model only');
    }
  }

  String _xLabel(DateTime t) => '${t.hour.toString().padLeft(2, '0')}:00';

  @override
  Widget build(BuildContext context) {
    final inTempPast = demoSeries('temp', const Duration(hours: 12), 24);
    final inTempNext = demoForecast('temp', 24);
    final inHumNext = demoForecast('hum', 24);
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          Row(children: [
            Text('Forecast', style: Theme.of(context).textTheme.headlineMedium),
            const Spacer(),
            IconButton(
              icon: const Icon(Icons.refresh_rounded, color: T.sub),
              onPressed: _fetchWeather,
            ),
          ]),
          const SizedBox(height: 4),
          Text('What the next 24 hours look like inside the farm, next to the '
              'official outside forecast for the same hours.',
              style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 14),
          Builder(builder: (context) {
            final a = _adviceFrom(_outTemp);
            return Panel(
              borderColor: a.color.withValues(alpha: 0.6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(a.icon, color: a.color, size: 24),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(a.title,
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(color: a.color)),
                    const SizedBox(height: 4),
                    Text(a.body, style: Theme.of(context).textTheme.bodyMedium),
                    if (_outTemp == null)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text('based on demo pattern — official forecast unavailable',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(fontSize: 10.5)),
                      ),
                  ]),
                ),
              ]),
            );
          }),
          const SectionLabel('Inside — poultry hall'),
          TrendChart(
            title: 'Temperature °C — last 12h + predicted next 24h',
            xLabel: _xLabel,
            series: [
              TrendSeries('Measured', chartYellow, inTempPast),
              TrendSeries('Predicted (demo pattern)', chartYellow, inTempNext,
                  dashed: true),
            ],
          ),
          const SizedBox(height: 10),
          TrendChart(
            title: 'Humidity % — predicted next 24h',
            xLabel: _xLabel,
            height: 150,
            series: [
              TrendSeries('Predicted (demo pattern)', chartBlue, inHumNext,
                  dashed: true),
            ],
          ),
          const SectionLabel('Outside — official weather'),
          if (_outTemp != null)
            TrendChart(
              title: 'Open-Meteo forecast — next 24h',
              xLabel: _xLabel,
              series: [
                TrendSeries('Outside temp °C', chartYellow, _outTemp!),
                TrendSeries('Outside humidity %', chartBlue, _outHum!),
              ],
            )
          else
            Panel(child: Text(_weatherStatus, style: Theme.of(context).textTheme.bodySmall)),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Text(
                'Honest print: the inside prediction is currently a demo seasonal pattern — a real model needs telemetry history the node hasn\'t collected yet. The outside forecast is live Open-Meteo data. '
                'Why this page exists: a heatwave forecast at 14:00 tomorrow means pre-cooling the hall tonight — cheaper and safer than reacting at 14:00.\n$_weatherStatus',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(fontSize: 11)),
          ),
        ],
      ),
    );
  }
}
