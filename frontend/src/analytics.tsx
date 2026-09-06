import type { Event, Source, Rule } from "./types";

export function ExtractionAnalytics({
  events,
  sources,
}: {
  events: Event[];
  sources: Source[];
}) {
  const extracted = events.filter((e) => e.sources.length > 0);
  const count = (predicate: (e: Event) => boolean) =>
    extracted.filter(predicate).length;
  const reviewed = count(
    (e) =>
      e.history.some((h) => h.action === "Event Approve") ||
      e.status === "ARCHIVED",
  );
  const percentage = (n: number, base = extracted.length) =>
    base ? Math.round((n / base) * 100) + "%" : "—";
  const rows = [
    [
      "Events extracted",
      sources.reduce((n, s) => n + s.event_count, 0).toString(),
    ],
    [
      "Approval rate",
      percentage(
        count((e) => e.history.some((h) => h.action === "Event Approve")),
        reviewed,
      ),
    ],
    [
      "Rejection rate",
      percentage(
        count((e) => e.history.some((h) => h.action === "Event Reject")),
        reviewed,
      ),
    ],
    [
      "Manual correction rate",
      percentage(
        count((e) => e.history.some((h) => h.action === "Event Edited")),
      ),
    ],
    ["Calendar sync rate", percentage(count((e) => e.sync_state === "SYNCED"))],
    ["Duplicate evidence rate", percentage(count((e) => e.sources.length > 1))],
    [
      "Reschedule detections",
      count((e) => e.change_kind === "RESCHEDULE").toString(),
    ],
  ];
  return (
    <section className="panel settings-panel">
      <h2>From information to intention.</h2>
      <p className="muted">
        Extraction analytics. Rates describe the current workspace; they are not
        estimates of parser accuracy.
      </p>
      <div className="analytics-grid">
        {rows.map(([label, value]) => (
          <div key={label}>
            <strong>{value}</strong>
            <small>{label}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

export function RuleConflictNotice({ rules }: { rules: Rule[] }) {
  const conflicts: string[] = [];
  const active = rules.filter((r) => r.enabled);
  for (let i = 0; i < active.length; i++)
    for (let j = i + 1; j < active.length; j++) {
      const a = active[i],
        b = active[j];
      const fields = Object.keys(a.actions).filter(
        (k) =>
          k !== "tags" &&
          k in b.actions &&
          JSON.stringify(a.actions[k]) !== JSON.stringify(b.actions[k]),
      );
      if (fields.length)
        conflicts.push(
          `${a.name} and ${b.name} assign different ${fields.join(", ")} values. If both match, priority ${Math.max(a.priority, b.priority)} applies last.`,
        );
    }
  return conflicts.length ? (
    <div className="notice warning">
      <strong>Potential rule overrides</strong>
      {conflicts.map((s, i) => (
        <p key={i}>{s}</p>
      ))}
    </div>
  ) : null;
}
