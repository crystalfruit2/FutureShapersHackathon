import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models.dart';
import 'theme.dart';

class EventsScreen extends StatelessWidget {
  const EventsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return SafeArea(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Text('Activity', style: Theme.of(context).textTheme.headlineMedium),
        ),
        Expanded(
          child: app.events.isEmpty
              ? Center(
                  child: Text('Nothing yet — the farm is quiet.',
                      style: Theme.of(context).textTheme.bodySmall))
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  itemCount: app.events.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 8),
                  itemBuilder: (_, i) => _EventTile(e: app.events[i]),
                ),
        ),
      ]),
    );
  }
}

class _EventTile extends StatelessWidget {
  final StrajerEvent e;
  const _EventTile({required this.e});

  @override
  Widget build(BuildContext context) {
    final (color, icon) = switch (e.sev) {
      Severity.emerg => (T.danger, Icons.emergency_outlined),
      Severity.alert => (T.danger, Icons.notification_important_outlined),
      Severity.warn => (T.warn, Icons.warning_amber_outlined),
      Severity.sec => (T.cyber, Icons.shield_outlined),
      Severity.info => (T.sub, Icons.check_circle_outline),
    };
    final title = e.raw.startsWith('SEC|')
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
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 3),
            Text(e.raw,
                style: const TextStyle(
                    fontSize: 11, color: T.sub, fontFamily: 'Menlo')),
          ]),
        ),
        const SizedBox(width: 8),
        Text(e.time, style: Theme.of(context).textTheme.bodySmall),
      ]),
    );
  }
}
