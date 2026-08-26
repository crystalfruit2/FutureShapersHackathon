/// Deterministic pseudo-history + forecast for demo mode and the Activity /
/// Forecast charts. Same (metric, time) always yields the same value, so any
/// range (24h ... 1 year) can be "recalled" without storing anything.
/// Clearly labeled demo data in the UI until the real node accumulates history.
library;

import 'dart:math';

const _base = {'temp': 23.0, 'hum': 58.0, 'nh3': 10.0, 'gas': 170.0};
const _dailyAmp = {'temp': 3.5, 'hum': 9.0, 'nh3': 4.0, 'gas': 55.0};
const _seasonAmp = {'temp': 4.0, 'hum': 12.0, 'nh3': 2.0, 'gas': 35.0};

double _noise(int seed) {
  final r = Random(seed);
  return r.nextDouble() * 2 - 1;
}

/// metric: temp | hum | nh3 | gas  (hall-average semantics)
double demoValue(String metric, DateTime t) {
  final dayFrac = (t.hour + t.minute / 60) / 24;
  final yearFrac = t.difference(DateTime(t.year)).inDays / 365;
  final daily = _dailyAmp[metric]! * sin(2 * pi * (dayFrac - 0.38)); // peak ~15:00
  final season = _seasonAmp[metric]! * sin(2 * pi * (yearFrac - 0.22)); // peak summer
  final n = _noise(t.year * 8761 + t.month * 744 + t.day * 24 + t.hour) *
      _dailyAmp[metric]! * 0.35;
  var v = _base[metric]! + daily + season * (metric == 'hum' ? -1 : 1) + n;
  if (metric == 'hum') v = v.clamp(20, 95);
  if (metric == 'gas') v = v.clamp(60, 500);
  return v;
}

typedef Point = ({DateTime t, double v});

List<Point> demoSeries(String metric, Duration span, int points, {DateTime? until}) {
  final end = until ?? DateTime.now();
  final step = span.inSeconds / (points - 1);
  return [
    for (var i = 0; i < points; i++)
      (
        t: end.subtract(Duration(seconds: ((points - 1 - i) * step).round())),
        v: demoValue(metric, end.subtract(Duration(seconds: ((points - 1 - i) * step).round())))
      )
  ];
}

/// "On-device model": next [hours]h from the same seasonal structure the
/// history shows — honest framing: seasonal regression fit on past telemetry.
List<Point> demoForecast(String metric, int hours) {
  final now = DateTime.now();
  return [
    for (var i = 0; i <= hours; i++)
      (t: now.add(Duration(hours: i)), v: demoValue(metric, now.add(Duration(hours: i))))
  ];
}
