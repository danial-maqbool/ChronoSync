import React, { useEffect, useState, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  Clock3,
  LayoutDashboard,
  Inbox,
  CalendarDays,
  FolderOpen,
  Tags,
  SlidersHorizontal,
  CheckCircle2,
  History,
  Settings as SettingsIcon,
  Search,
  Plus,
  ArrowUpRight,
  ArrowRight,
  Upload,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Bell,
  ShieldCheck,
  Command,
  FileText,
  X,
  Check,
  AlertTriangle,
  Link2,
  RefreshCw,
  Trash2,
  Pin,
  Menu,
  Download,
  Calendar,
  Filter,
  Sparkles,
} from "lucide-react";
import type { Event, Source, Workspace, Tag, Settings, Rule } from "./types";
import {
  api,
  dateLabel,
  dayKey,
  importanceOrder,
  isInbox,
  reminderLabel,
  upcomingGroup,
} from "./utils";
import "./style.css";
import { ProjectsView } from "./projects";
import { ExtractionAnalytics, RuleConflictNotice } from "./analytics";
import { AccountGate, AccountActions, useAccount } from "./auth";

const navigation = [
  ["Dashboard", LayoutDashboard],
  ["Event Inbox", Inbox],
  ["Upcoming", Clock3],
  ["Calendar", CalendarDays],
  ["Sources", FolderOpen],
  ["Tags", Tags],
  ["Rules", SlidersHorizontal],
  ["Projects", FolderOpen],
  ["Completed", CheckCircle2],
  ["Audit History", History],
  ["Settings", SettingsIcon],
  ["Trash", Trash2],
] as const;
function App() {
  const account = useAccount();
  const [data, setData] = useState<Workspace | null>(null),
    [page, setPage] = useState("Dashboard"),
    [selected, setSelected] = useState<string | null>(null),
    [modal, setModal] = useState(""),
    [query, setQuery] = useState(""),
    [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [busy, setBusy] = useState(false),
    [mobile, setMobile] = useState(false),
    [source, setSource] = useState<Source | null>(null),
    [filter, setFilter] = useState({
      importance: "",
      tag: "",
      status: "",
      type: "",
      source: "",
      sync: "",
      confidence: "",
      from: "",
      to: "",
    }),
    [checked, setChecked] = useState<string[]>([]),
    [edit, setEdit] = useState<Event | null>(null),
    [calendarMode, setCalendarMode] = useState("Month"),
    [calendarDate, setCalendarDate] = useState(new Date()),
    [colorBy, setColorBy] = useState("Importance"),
    [sort, setSort] = useState("Date");
  const searchRef = useRef<HTMLInputElement>(null);
  const [instances, setInstances] = useState<Event[]>([]);
  useEffect(() => {
    if (page !== "Calendar") return;
    const a = new Date(
      calendarDate.getFullYear(),
      calendarDate.getMonth() - 1,
      1,
    ).toISOString();
    const b = new Date(
      calendarDate.getFullYear(),
      calendarDate.getMonth() + 2,
      1,
    ).toISOString();
    api<Event[]>(
      "/calendar/occurrences?start=" +
        encodeURIComponent(a) +
        "&end=" +
        encodeURIComponent(b),
    )
      .then(setInstances)
      .catch((e) => setError(e.message));
  }, [page, calendarDate, data]);
  async function refresh() {
    setData(await api<Workspace>("/workspace"));
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    const timer = setInterval(() => refresh().catch(() => {}), 30000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setModal((m) => (m === "command" ? "" : "command"));
        return;
      }
      if (e.key === "Escape") {
        setModal("");
        setSelected(null);
        setSource(null);
        return;
      }
      if (
        (e.target as HTMLElement).closest(
          "input,textarea,select,[contenteditable]",
        )
      )
        return;
      if (e.key === "n") {
        setEdit(null);
        setModal("event");
      }
      if (e.key === "i") setPage("Event Inbox");
      if (e.key === "t") {
        setPage("Upcoming");
        setFilter((f) => ({
          ...f,
          from: dayKey(
            new Date().toISOString(),
            data?.settings.timezone || "Asia/Karachi",
          ),
          to: dayKey(
            new Date().toISOString(),
            data?.settings.timezone || "Asia/Karachi",
          ),
        }));
      }
      if (e.key === "/") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [data?.settings.timezone]);
  async function run(fn: () => Promise<unknown>, message = "Saved") {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
      setToast(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function action(
    e: Event,
    actionName: string,
    extra: Record<string, unknown> = {},
  ) {
    return run(
      () =>
        api("/events/" + e.id + "/action", { action: actionName, ...extra }),
      "Event updated",
    );
  }
  function go(name: string) {
    setPage(name);
    setSelected(null);
    setMobile(false);
    setChecked([]);
    setQuery("");
    setFilter({
      importance: "",
      tag: "",
      status: "",
      type: "",
      source: "",
      sync: "",
      confidence: "",
      from: "",
      to: "",
    });
  }
  if (!data)
    return (
      <div className="boot">
        <Clock3 size={40} />
        <h1>ChronoSync</h1>
        <p>{error || "Opening your workspace…"}</p>
        <button onClick={() => refresh()}>Retry connection</button>
      </div>
    );
  const zone = data!.settings.timezone,
    live = data!.events.filter((e) => !e.deleted),
    inbox = live.filter((e) => isInbox(e.status)),
    active = live
      .filter((e) => ["CONFIRMED", "SYNCED", "SNOOZED"].includes(e.status))
      .map((e) => (e.next_occurrence ? { ...e, ...e.next_occurrence } : e)),
    today = dayKey(new Date().toISOString(), zone),
    event = data!.events.find((e) => e.id === selected);
  const filtered = (
    page === "Event Inbox"
      ? inbox
      : page === "Completed"
        ? live.filter((e) => e.status === "COMPLETED")
        : page === "Trash"
          ? data!.events.filter((e) => e.deleted)
          : page === "Upcoming" || page === "Calendar"
            ? active
            : live
  )
    .filter(
      (e) =>
        (!query ||
          JSON.stringify([
            e.title,
            e.description,
            e.people,
            e.tags,
            e.sources,
            e.location,
          ])
            .toLowerCase()
            .includes(query.toLowerCase())) &&
        (!filter.importance || e.importance === filter.importance) &&
        (!filter.tag || e.tags.includes(filter.tag)) &&
        (!filter.status || e.status === filter.status) &&
        (!filter.type || e.type === filter.type) &&
        (!filter.source ||
          e.sources.some((s) => s.source_id === filter.source)) &&
        (!filter.sync || e.sync_state === filter.sync) &&
        (!filter.confidence || e.confidence >= Number(filter.confidence)) &&
        (!filter.from || (e.start && dayKey(e.start, zone) >= filter.from)) &&
        (!filter.to || (e.start && dayKey(e.start, zone) <= filter.to)),
    )
    .sort(
      (a, b) =>
        Number(b.pinned) - Number(a.pinned) ||
        (sort === "Importance"
          ? importanceOrder.indexOf(a.importance) -
            importanceOrder.indexOf(b.importance)
          : sort === "Title"
            ? a.title.localeCompare(b.title)
            : (a.start || "z").localeCompare(b.start || "z")),
    );
  const badge = (e: Event) => (
    <span className={"badge " + e.importance.toLowerCase()}>
      <i />
      {e.importance}
    </span>
  );
  const tag = (name: string) => (
    <span
      key={name}
      className="tag"
      style={
        {
          "--tag-color":
            data!.tags.find((t) => t.name === name)?.color || "#557e72",
        } as React.CSSProperties
      }
    >
      {name}
    </span>
  );
  function eventRow(e: Event, selectable = false) {
    return (
      <div
        className={"event-row " + (selected === e.id ? "selected" : "")}
        key={e.id}
      >
        {selectable && (
          <input
            aria-label={"Select " + e.title}
            type="checkbox"
            checked={checked.includes(e.id)}
            onChange={(ev) =>
              setChecked(
                ev.target.checked
                  ? [...checked, e.id]
                  : checked.filter((id) => id !== e.id),
              )
            }
          />
        )}
        <button className="event-row-main" onClick={() => setSelected(e.id)}>
          <span className={"importance-line " + e.importance.toLowerCase()} />
          <div className="event-day">
            <strong>
              {e.start
                ? new Intl.DateTimeFormat("en", {
                    timeZone: zone,
                    day: "2-digit",
                  }).format(new Date(e.start))
                : "?"}
            </strong>
            <small>
              {e.start
                ? new Intl.DateTimeFormat("en", {
                    timeZone: zone,
                    month: "short",
                  }).format(new Date(e.start))
                : "REVIEW"}
            </small>
          </div>
          <div className="event-info">
            <strong>
              {e.pinned && <Pin size={12} />} {e.title}
            </strong>
            <span>
              {e.all_day
                ? "All day · time unspecified"
                : dateLabel(e.start, zone, true)}{" "}
              <b>·</b> {e.type}
            </span>
            <div className="tags-line">{e.tags.slice(0, 3).map(tag)}</div>
          </div>
          <div className="event-row-end">
            {badge(e)}
            <small className={e.sync_state === "SYNCED" ? "synced" : ""}>
              {e.sync_state === "SYNCED" ? (
                <CheckCircle2 size={12} />
              ) : (
                <Clock3 size={12} />
              )}{" "}
              {e.sync_state === "SYNCED"
                ? `Synced · ${e.provider}`
                : isInbox(e.status)
                  ? "Awaiting review"
                  : e.sync_state.replaceAll("_", " ").toLowerCase()}
            </small>
          </div>
          <ChevronRight size={16} />
        </button>
      </div>
    );
  }
  function filters() {
    return (
      <>
        <div className="filters">
          <div className="filter-control">
            <Filter size={14} />
            <select
              aria-label="Importance filter"
              value={filter.importance}
              onChange={(e) =>
                setFilter({ ...filter, importance: e.target.value })
              }
            >
              <option value="">All importance</option>
              {importanceOrder.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </div>
          <select
            aria-label="Tag filter"
            value={filter.tag}
            onChange={(e) => setFilter({ ...filter, tag: e.target.value })}
          >
            <option value="">All tags</option>
            {data!.tags
              .filter((t) => !t.deleted)
              .map((t) => (
                <option key={t.id}>{t.name}</option>
              ))}
          </select>
          <select
            aria-label="Type filter"
            value={filter.type}
            onChange={(e) => setFilter({ ...filter, type: e.target.value })}
          >
            <option value="">All types</option>
            {data!.settings.event_types.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <details>
            <summary>More filters</summary>
            <div className="advanced-filters">
              <label>
                From
                <input
                  type="date"
                  value={filter.from}
                  onChange={(e) =>
                    setFilter({ ...filter, from: e.target.value })
                  }
                />
              </label>
              <label>
                Through
                <input
                  type="date"
                  value={filter.to}
                  onChange={(e) => setFilter({ ...filter, to: e.target.value })}
                />
              </label>
              <label>
                Source
                <select
                  value={filter.source}
                  onChange={(e) =>
                    setFilter({ ...filter, source: e.target.value })
                  }
                >
                  <option value="">All sources</option>
                  {data!.sources.map((s) => (
                    <option value={s.id} key={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Sync
                <select
                  value={filter.sync}
                  onChange={(e) =>
                    setFilter({ ...filter, sync: e.target.value })
                  }
                >
                  <option value="">Any sync state</option>
                  {[
                    "NOT_SYNCED",
                    "SYNCED",
                    "OUT_OF_SYNC",
                    "SYNC_ERROR",
                    "CALENDAR_MISSING",
                  ].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
              <label>
                Minimum confidence
                <select
                  value={filter.confidence}
                  onChange={(e) =>
                    setFilter({ ...filter, confidence: e.target.value })
                  }
                >
                  <option value="">Any confidence</option>
                  <option value="0.9">90%</option>
                  <option value="0.7">70%</option>
                </select>
              </label>
            </div>
          </details>
          <select
            aria-label="Saved views"
            defaultValue=""
            onChange={(e) => {
              const view = data!.saved_views.find(
                (v) => v.id === e.target.value,
              );
              if (view) {
                setFilter(view.filters as typeof filter);
                setQuery(view.filters.query || "");
              }
            }}
          >
            <option value="">Saved views</option>
            {data!.saved_views.map((v) => (
              <option value={v.id} key={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <button className="text-btn" onClick={() => setModal("view")}>
            Save view
          </button>
          <span className="spacer" />
          <small>{filtered.length} events</small>
          <select
            aria-label="Sort events"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            {["Date", "Importance", "Title"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </div>
      </>
    );
  }
  function empty(
    title = "A little space in your schedule",
    description = "Import a source or capture a message to get started.",
  ) {
    return (
      <div className="empty">
        <CalendarDays size={34} />
        <h3>{title}</h3>
        <p>{description}</p>
        <button onClick={() => setModal("capture")}>
          Quick capture <ArrowRight size={14} />
        </button>
      </div>
    );
  }
  function details(e: Event, inline = false) {
    return (
      <div className={inline ? "preview" : "drawer"}>
        <div className="drawer-heading">
          <span>EVENT DETAILS</span>
          <button
            aria-label="Close event details"
            className="icon-btn"
            onClick={() => setSelected(null)}
          >
            <X size={20} />
          </button>
        </div>
        <div className="detail-content">
          <div className="detail-badges">
            {badge(e)}
            <span className="tag">{e.type}</span>
          </div>
          <h2>{e.title}</h2>
          <p className="detail-date">
            <CalendarDays size={18} />
            {dateLabel(e.start, zone, !e.all_day)}
          </p>
          <div className="tags-line">{e.tags.map(tag)}</div>
          <div className="detail-actions">
            <button
              className="primary"
              disabled={busy}
              onClick={() => action(e, "approve")}
            >
              Approve
            </button>
            <button
              onClick={() => {
                setEdit(e);
                setModal("event");
              }}
            >
              Edit
            </button>
            <button aria-label="Pin event" onClick={() => action(e, "pin")}>
              <Pin size={15} />
            </button>
          </div>
          {e.change_kind && (
            <div className="notice warning">
              <strong>
                {e.change_kind === "CANCEL"
                  ? "Cancellation proposed"
                  : "Reschedule proposed"}
              </strong>
              <p>Review the related event and confirm this change.</p>
              <select id="change-target" defaultValue={e.related_ids[0] || ""}>
                <option value="">Choose related event</option>
                {live
                  .filter((x) => x.id !== e.id && !x.change_kind)
                  .map((x) => (
                    <option value={x.id} key={x.id}>
                      {x.title} · {dateLabel(x.start, zone)}
                    </option>
                  ))}
              </select>
              <label className="checkbox">
                <input type="checkbox" id="change-calendar" />
                Also update or delete the calendar copy
              </label>
              <button
                onClick={() =>
                  action(e, "apply_change", {
                    confirm: true,
                    target_id: (
                      document.getElementById(
                        "change-target",
                      ) as HTMLSelectElement
                    ).value,
                    calendar: (
                      document.getElementById(
                        "change-calendar",
                      ) as HTMLInputElement
                    ).checked,
                  })
                }
              >
                Confirm change
              </button>
            </div>
          )}
          {!!e.duplicate_ids?.length && (
            <div className="notice warning">
              <strong>Possible duplicate</strong>
              {e.duplicate_ids.map((id) => (
                <p key={id}>
                  {data!.events.find((x) => x.id === id)?.title}
                  <button onClick={() => action(e, "merge", { target_id: id })}>
                    Merge evidence
                  </button>
                </p>
              ))}
              <button onClick={() => action(e, "keep_both")}>
                Keep both as separate events
              </button>
            </div>
          )}
          {!!e.conflicts?.length && (
            <section>
              <h4>
                <AlertTriangle size={15} /> Calendar conflicts
              </h4>
              {e.conflicts.map((c) => (
                <div className="notice warning" key={c.id}>
                  <strong>{c.title}</strong>
                  <p>
                    {c.severity.replaceAll("_", " ")} ·{" "}
                    {dateLabel(c.start, zone, true)}
                  </p>
                </div>
              ))}
              <button onClick={() => action(e, "sync", { confirm: true })}>
                Keep both & sync approved event
              </button>
            </section>
          )}
          <section>
            <h4>
              <FileText size={15} /> Source evidence
            </h4>
            {e.sources.length ? (
              e.sources.map((s, i) => (
                <div key={i} className="evidence">
                  <button
                    onClick={() =>
                      setSource(
                        data!.sources.find((x) => x.id === s.source_id) || null,
                      )
                    }
                  >
                    <FileText size={14} />
                    {s.name}
                    <ArrowUpRight size={14} />
                  </button>
                  <blockquote>{s.evidence}</blockquote>
                  <small>
                    {[
                      s.segment.page ? "Page " + s.segment.page : "",
                      s.segment.paragraph
                        ? "Paragraph " + s.segment.paragraph
                        : "",
                      s.segment.speaker || s.segment.sender || "",
                      s.segment.start_timestamp || s.segment.timestamp || "",
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                </div>
              ))
            ) : (
              <p className="muted">Manually created event.</p>
            )}
          </section>
          <section>
            <h4>
              <Clock3 size={15} /> How this date was resolved
            </h4>
            <div className="resolution">
              <small>REFERENCE</small>
              <p>
                {e.resolution?.reference_kind || "Manual entry"}
                <br />
                {e.resolution?.reference_datetime || ""}
              </p>
              {e.resolution?.explanation?.map((s, i) => (
                <p key={i}>{s}</p>
              ))}
              {e.resolution?.warnings?.map((w, i) => (
                <div className="notice warning" key={i}>
                  {w}
                </div>
              ))}
              <small>CONFIDENCE</small>
              <div className="confidence-track">
                <i style={{ width: e.confidence * 100 + "%" }} />
              </div>
              <span>
                {Math.round(e.confidence * 100)}% · {e.confidence_label}
              </span>
            </div>
          </section>
          <section>
            <h4>
              <Bell size={15} /> Reminders
            </h4>
            <div className="tags-line">
              {e.reminders.map((n) => (
                <span className="tag" key={n}>
                  {reminderLabel(n)} before
                </span>
              ))}
            </div>
            {e.snoozed_until && (
              <p>Snoozed until {dateLabel(e.snoozed_until, zone, true)}</p>
            )}
            <div className="button-row">
              <button
                onClick={() => action(e, "snooze", { snooze_minutes: 60 })}
              >
                Snooze 1h
              </button>
              <button
                onClick={() => action(e, "snooze", { snooze_minutes: 1440 })}
              >
                Tomorrow
              </button>
              <button
                onClick={() => action(e, "snooze", { snooze_minutes: 4320 })}
              >
                3 days
              </button>
            </div>
          </section>
          <section>
            <h4>
              <Link2 size={15} /> Calendar
            </h4>
            <p>
              {e.sync_state.replaceAll("_", " ")}{" "}
              {e.provider && "· " + e.provider}
            </p>
            {e.sync_error && <p className="notice warning">{e.sync_error}</p>}
            <div className="button-row">
              <button onClick={() => action(e, "sync")}>
                Sync approved event
              </button>
              {e.external_id && (
                <button onClick={() => action(e, "reconcile")}>
                  Check external changes
                </button>
              )}
              {["OUT_OF_SYNC", "CALENDAR_MISSING"].includes(e.sync_state) && (
                <button
                  onClick={() => action(e, "reconcile", { confirm: true })}
                >
                  Accept calendar state
                </button>
              )}
            </div>
          </section>
          <section>
            <h4>Related events & attachments</h4>
            {e.related_ids?.map((id) => (
              <button key={id} onClick={() => setSelected(id)}>
                {data!.events.find((x) => x.id === id)?.title || id}
              </button>
            ))}
            {e.attachments?.map((a, i) => (
              <p key={i}>
                {a.url ? (
                  <a href={a.url} target="_blank" rel="noreferrer">
                    {a.url}
                  </a>
                ) : (
                  a.note
                )}
              </p>
            ))}
            <form
              onSubmit={(ev) => {
                ev.preventDefault();
                const f = new FormData(ev.currentTarget);
                run(
                  () =>
                    api("/events/" + e.id + "/attachments", {
                      source_id: f.get("source_id") || undefined,
                      url: f.get("url") || undefined,
                      note: f.get("note") || undefined,
                    }),
                  "Source attached",
                );
              }}
            >
              <label>
                Attach imported source
                <select name="source_id">
                  <option value="">Choose source</option>
                  {data!.sources
                    .filter((s) => s.processing_status === "COMPLETE")
                    .map((s) => (
                      <option value={s.id} key={s.id}>
                        {s.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Or attach a URL
                <input name="url" type="url" />
              </label>
              <label>
                Or attach a note
                <input name="note" />
              </label>
              <button>Attach to event</button>
            </form>
          </section>
          <section>
            <h4>Notes & location</h4>
            <p>{e.notes || "No private notes"}</p>
            <p>
              {e.location || "No location"} {e.people?.join(", ")}
            </p>
          </section>
          <section>
            <h4>
              <History size={15} /> History
            </h4>
            {[...e.history].reverse().map((h, i) => (
              <div className="history-item" key={i}>
                <i />
                <div>
                  {h.action}
                  <small>{dateLabel(h.at, zone, true)}</small>
                </div>
              </div>
            ))}
          </section>
          <div className="detail-actions wrap">
            <button onClick={() => action(e, "complete")}>Complete</button>
            <button onClick={() => action(e, "archive")}>Archive</button>
            <button onClick={() => action(e, "reject")}>Reject</button>
            <button className="danger" onClick={() => setModal("delete")}>
              Delete
            </button>
            {e.deleted && (
              <button onClick={() => action(e, "restore")}>Restore</button>
            )}
          </div>
        </div>
      </div>
    );
  }
  const title =
    page === "Dashboard"
      ? "A clearer view of what’s next."
      : page === "Event Inbox"
        ? "A little review. A lot of clarity."
        : page === "Upcoming"
          ? "Make room for what matters."
          : page === "Calendar"
            ? "Your commitments, connected."
            : page;
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <a className="brand" onClick={() => go("Dashboard")}>
          <span className="brand-icon">
            <Clock3 size={23} />
          </span>
          ChronoSync<span className="brand-dot">®</span>
        </a>
        <div className="workspace-switch">
          <span className="avatar">D</span>
          <div>
            Personal workspace<small>Local · Private by default</small>
          </div>
          <ChevronRight size={14} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {navigation.map(([name, Icon], i) => (
            <React.Fragment key={name}>
              {i === 7 && <div className="nav-divider" />}
              <button
                aria-label={name}
                className={page === name ? "active" : ""}
                onClick={() => go(name)}
              >
                <Icon size={18} />
                <span>{name}</span>
                {name === "Event Inbox" && inbox.length > 0 && (
                  <b>{inbox.length}</b>
                )}
              </button>
            </React.Fragment>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="private-note">
            <ShieldCheck size={19} />
            <div>
              Your data stays yours
              <small>
                {account.cloud
                  ? "Private cloud · AI disabled"
                  : "Local processing only"}
              </small>
            </div>
          </div>
          <button
            className="command-shortcut"
            onClick={() => setModal("command")}
          >
            <Command size={15} /> Command menu <kbd>Ctrl K</kbd>
          </button>
          <div className="profile">
            <span className="avatar">
              {account.user?.username[0].toUpperCase() || "D"}
            </span>
            <div>
              {account.user?.username || "Danial"}’s workspace
              <small>Personal edition</small>
            </div>
            <MoreHorizontal size={18} />
          </div>
          <AccountActions />
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="mobile-menu icon-btn"
            onClick={() => setMobile(!mobile)}
            aria-label="Toggle navigation"
          >
            <Menu />
          </button>
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <strong>{page}</strong>
          </div>
          <div className="top-search">
            <Search size={16} />
            <input
              ref={searchRef}
              aria-label="Search workspace"
              placeholder="Search anything…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (page === "Dashboard") setPage("Search");
              }}
            />
            <kbd>/</kbd>
          </div>
          <button className="capture-btn" onClick={() => setModal("capture")}>
            <Plus size={16} />
            Quick capture
          </button>
          <button
            className="notification-btn icon-btn"
            aria-label="Notifications"
            onClick={() => setModal("notifications")}
          >
            <Bell size={18} />
            {data.notifications.some((n) => !n.read) && <i />}
          </button>
          <span className="top-avatar">D</span>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {page === "Dashboard"
                  ? new Intl.DateTimeFormat("en-GB", {
                      weekday: "long",
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                      timeZone: zone,
                    })
                      .format(new Date())
                      .toUpperCase()
                  : "YOUR PERSONAL TIME WORKSPACE"}
              </div>
              <h1>{title}</h1>
              <p>
                {page === "Dashboard"
                  ? "Turn scattered information into a schedule you can trust."
                  : page === "Event Inbox"
                    ? "Check the evidence, fine-tune the details, then make it official."
                    : "Everything you need, with the context that matters."}
              </p>
            </div>
            <div className="heading-actions">
              <button onClick={() => setModal("import")}>
                <Upload size={15} />
                Import sources
              </button>
              <button
                className="primary"
                onClick={() => {
                  setEdit(null);
                  setModal("event");
                }}
              >
                <Plus size={16} />
                Add event
              </button>
            </div>
          </div>
          {error && (
            <div role="alert" className="error-banner">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button
                className="icon-btn"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <X size={16} />
              </button>
            </div>
          )}
          {page === "Dashboard" && (
            <>
              <div className="stats-grid">
                {[
                  {
                    name: "Today",
                    count: active.filter(
                      (e) => e.start && dayKey(e.start, zone) === today,
                    ).length,
                    caption: "On your agenda",
                    icon: CalendarDays,
                    color: "green",
                    click: () => {
                      go("Upcoming");
                      setFilter((f) => ({ ...f, from: today, to: today }));
                    },
                  },
                  {
                    name: "This week",
                    count: active.filter(
                      (e) =>
                        e.start &&
                        ["Today", "Tomorrow", "This week"].includes(
                          upcomingGroup(e.start, zone),
                        ),
                    ).length,
                    caption: "A little planning goes a long way",
                    icon: Clock3,
                    color: "blue",
                    click: () => go("Upcoming"),
                  },
                  {
                    name: "High priority",
                    count: active.filter((e) =>
                      ["HIGH", "CRITICAL"].includes(e.importance),
                    ).length,
                    caption: "Worth keeping an eye on",
                    icon: Pin,
                    color: "orange",
                    click: () => {
                      go("Upcoming");
                      setSort("Importance");
                    },
                  },
                  {
                    name: "Needs review",
                    count: inbox.length,
                    caption: "Ready for your decision",
                    icon: Inbox,
                    color: "purple",
                    click: () => go("Event Inbox"),
                  },
                ].map((s) => (
                  <button className="stat-card" key={s.name} onClick={s.click}>
                    <div>
                      <span>{s.name}</span>
                      <span className={"stat-icon " + s.color}>
                        <s.icon size={18} />
                      </span>
                    </div>
                    <strong>{s.count.toString().padStart(2, "0")}</strong>
                    <small>
                      {s.caption}
                      <ArrowUpRight size={14} />
                    </small>
                  </button>
                ))}
              </div>
              <div className="dashboard-columns">
                <div>
                  <div className="attention-banner">
                    <span className="attention-icon">
                      <Sparkles size={23} />
                    </span>
                    <div>
                      <strong>A moment of review. Peace of mind.</strong>
                      <p>
                        {inbox.length
                          ? `${inbox.length} extracted events are waiting in your inbox.`
                          : "Bring in a document. We’ll help you find what’s next."}
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        inbox.length ? go("Event Inbox") : setModal("capture")
                      }
                    >
                      {inbox.length ? "Review inbox" : "Get started"}
                      <ArrowRight size={16} />
                    </button>
                  </div>
                  <section className="panel timeline-panel">
                    <div className="panel-heading">
                      <div>
                        <h2>
                          On the horizon{" "}
                          <span className="count-pill">{active.length}</span>
                        </h2>
                        <p>Your upcoming commitments, all in one place.</p>
                      </div>
                      <button
                        className="text-btn"
                        onClick={() => go("Upcoming")}
                      >
                        View all <ArrowUpRight size={14} />
                      </button>
                    </div>
                    {active.length
                      ? [...active]
                          .sort((a, b) =>
                            (a.start || "").localeCompare(b.start || ""),
                          )
                          .slice(0, 5)
                          .map((e) => eventRow(e))
                      : empty()}
                    <button
                      className="panel-footer"
                      onClick={() => go("Calendar")}
                    >
                      <CalendarDays size={15} /> Open your calendar{" "}
                      <ArrowRight size={15} />
                    </button>
                  </section>
                  <section className="panel recent-panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Fresh from your sources</h2>
                        <p>Newly discovered. Ready to be reviewed.</p>
                      </div>
                      <button
                        className="text-btn"
                        onClick={() => go("Event Inbox")}
                      >
                        View inbox <ArrowUpRight size={14} />
                      </button>
                    </div>
                    {inbox.length ? (
                      inbox
                        .slice(-3)
                        .reverse()
                        .map((e) => (
                          <button
                            className="recent-item"
                            key={e.id}
                            onClick={() => setSelected(e.id)}
                          >
                            <div className="file-icon">
                              <FileText size={18} />
                            </div>
                            <div>
                              <strong>{e.title}</strong>
                              <small>
                                {e.sources[0]?.name} ·{" "}
                                {dateLabel(e.start, zone)}
                              </small>
                            </div>
                            <span className="confidence-pill">
                              {Math.round(e.confidence * 100)}% confidence
                            </span>
                            <ChevronRight size={15} />
                          </button>
                        ))
                    ) : (
                      <div className="small-empty">
                        Your inbox is all caught up.
                      </div>
                    )}
                  </section>
                </div>
                <div>
                  <section className="capture-panel">
                    <span className="mini-label">
                      <Plus size={14} /> QUICK CAPTURE
                    </span>
                    <h2>
                      It starts with
                      <br />a sentence.
                    </h2>
                    <p>
                      A message, a thought, a deadline.
                      <br />
                      Drop it here. We’ll find the when.
                    </p>
                    <textarea
                      id="dashboard-capture"
                      aria-label="Quick capture text"
                      placeholder={"“Team meeting next Wednesday\nat 2 PM…”"}
                    />
                    <div className="capture-footer">
                      <small>
                        <ShieldCheck size={12} />{" "}
                        {account.cloud
                          ? "Processed on your private server"
                          : "Processed locally"}
                      </small>
                      <button
                        onClick={() =>
                          run(async () => {
                            const el = document.getElementById(
                              "dashboard-capture",
                            ) as HTMLTextAreaElement;
                            if (!el.value.trim())
                              throw new Error("Paste a message first");
                            await api("/extraction/capture", {
                              text: el.value,
                            });
                            el.value = "";
                            go("Event Inbox");
                          }, "Candidates prepared")
                        }
                      >
                        Find events <ArrowRight size={14} />
                      </button>
                    </div>
                  </section>
                  <section className="panel importance-panel">
                    <div className="panel-heading">
                      <h2>What matters most</h2>
                      <SlidersHorizontal size={16} />
                    </div>
                    <p className="muted">A balanced look at your priorities.</p>
                    <div className="importance-bar">
                      {importanceOrder.map((level) => (
                        <i
                          className={level.toLowerCase()}
                          key={level}
                          style={{
                            flex: Math.max(
                              1,
                              live.filter((e) => e.importance === level).length,
                            ),
                          }}
                        />
                      ))}
                    </div>
                    {importanceOrder.map((level) => (
                      <button
                        key={level}
                        className="importance-legend"
                        onClick={() => {
                          go("Search");
                          setFilter((f) => ({ ...f, importance: level }));
                        }}
                      >
                        <span className={"dot " + level.toLowerCase()} />
                        <span>{level[0] + level.slice(1).toLowerCase()}</span>
                        <b>
                          {live.filter((e) => e.importance === level).length}
                        </b>
                      </button>
                    ))}
                  </section>
                  <section className="source-summary">
                    <div>
                      <FolderOpen size={19} />
                      <strong>
                        {data!.sources.length} sources, connected.
                      </strong>
                    </div>
                    <p>
                      Every event has a story.
                      <br />
                      The original evidence is always nearby.
                    </p>
                    <button className="text-btn" onClick={() => go("Sources")}>
                      Explore your sources <ArrowUpRight size={14} />
                    </button>
                  </section>
                </div>
              </div>
            </>
          )}
          {["Event Inbox", "Upcoming", "Completed", "Trash", "Search"].includes(
            page,
          ) && (
            <>
              <div className="panel">
                {filters()}
                {!!checked.length && (
                  <div className="bulk-bar">
                    <strong>{checked.length} selected</strong>
                    {["approve", "reject", "sync"].map((a) => (
                      <button
                        key={a}
                        disabled={busy}
                        onClick={() =>
                          run(async () => {
                            for (const id of checked)
                              await api("/events/" + id + "/action", {
                                action: a,
                              });
                            setChecked([]);
                          }, "Bulk action completed")
                        }
                      >
                        {a} selected
                      </button>
                    ))}
                    <button onClick={() => setModal("bulk")}>
                      Tags & importance
                    </button>
                  </div>
                )}
                <div className={page === "Event Inbox" ? "inbox-split" : ""}>
                  <div>
                    {filtered.length
                      ? page === "Upcoming"
                        ? [
                            "Overdue / past",
                            "Today",
                            "Tomorrow",
                            "This week",
                            "Next week",
                            "Later",
                          ].map((group) => {
                            const es = filtered.filter(
                              (e) => upcomingGroup(e.start, zone) === group,
                            );
                            return es.length ? (
                              <div key={group}>
                                <div className="group-label">
                                  {group}
                                  <span>{es.length}</span>
                                </div>
                                {es.map((e) => eventRow(e, true))}
                              </div>
                            ) : null;
                          })
                        : filtered.map((e) => eventRow(e, true))
                      : empty(
                          page === "Event Inbox"
                            ? "Your inbox is clear"
                            : "No events in this view",
                          "Try another filter, import a source, or add an event.",
                        )}
                  </div>
                  {page === "Event Inbox" &&
                    (event ? (
                      details(event, true)
                    ) : (
                      <div className="preview empty">
                        <FileText size={32} />
                        <h3>The details make the difference.</h3>
                        <p>
                          Select a candidate to see its source evidence
                          <br />
                          and how the date was resolved.
                        </p>
                      </div>
                    ))}
                </div>
              </div>
            </>
          )}
          {page === "Calendar" && (
            <section className="panel">
              <div className="calendar-toolbar">
                <div className="button-row">
                  <button
                    className="icon-btn"
                    aria-label="Previous period"
                    onClick={() =>
                      setCalendarDate(
                        new Date(
                          calendarDate.getFullYear(),
                          calendarDate.getMonth() -
                            (calendarMode === "Month" ? 1 : 0),
                          calendarDate.getDate() -
                            (calendarMode === "Week"
                              ? 7
                              : calendarMode === "Day"
                                ? 1
                                : 0),
                        ),
                      )
                    }
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <h2>
                    {calendarDate.toLocaleDateString("en-GB", {
                      month: "long",
                      year: "numeric",
                    })}
                  </h2>
                  <button
                    className="icon-btn"
                    aria-label="Next period"
                    onClick={() =>
                      setCalendarDate(
                        new Date(
                          calendarDate.getFullYear(),
                          calendarDate.getMonth() +
                            (calendarMode === "Month" ? 1 : 0),
                          calendarDate.getDate() +
                            (calendarMode === "Week"
                              ? 7
                              : calendarMode === "Day"
                                ? 1
                                : 0),
                        ),
                      )
                    }
                  >
                    <ChevronRight size={18} />
                  </button>
                  <button onClick={() => setCalendarDate(new Date())}>
                    Today
                  </button>
                </div>
                <div className="button-row">
                  <select
                    aria-label="Calendar color"
                    value={colorBy}
                    onChange={(e) => setColorBy(e.target.value)}
                  >
                    <option>Importance</option>
                    <option>Tag</option>
                  </select>
                  <select
                    aria-label="Calendar view"
                    value={calendarMode}
                    onChange={(e) => setCalendarMode(e.target.value)}
                  >
                    {["Month", "Week", "Day", "Agenda"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </div>
              </div>
              {calendarMode === "Agenda" ? (
                filtered.map((e) => eventRow(e))
              ) : (
                <div
                  className={
                    "calendar-grid " + (calendarMode === "Day" ? "day" : "")
                  }
                >
                  {(calendarMode === "Day"
                    ? ["Day"]
                    : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                  ).map((d) => (
                    <div className="weekday" key={d}>
                      {d}
                    </div>
                  ))}
                  {Array.from(
                    {
                      length:
                        calendarMode === "Month"
                          ? 42
                          : calendarMode === "Week"
                            ? 7
                            : 1,
                    },
                    (_, i) => {
                      const d = new Date(calendarDate);
                      if (calendarMode === "Month") {
                        d.setDate(1);
                        d.setDate(d.getDate() - ((d.getDay() + 6) % 7) + i);
                      } else if (calendarMode === "Week")
                        d.setDate(d.getDate() - ((d.getDay() + 6) % 7) + i);
                      const key =
                        d.getFullYear() +
                        "-" +
                        String(d.getMonth() + 1).padStart(2, "0") +
                        "-" +
                        String(d.getDate()).padStart(2, "0");
                      return (
                        <div
                          className={
                            "calendar-cell " +
                            (d.getMonth() !== calendarDate.getMonth()
                              ? "outside"
                              : "")
                          }
                          key={i}
                        >
                          <span className={key === today ? "today" : ""}>
                            {d.getDate()}
                          </span>
                          {instances
                            .filter(
                              (e) => e.start && dayKey(e.start, zone) === key,
                            )
                            .map((e) => (
                              <button
                                className={
                                  "calendar-event " + e.importance.toLowerCase()
                                }
                                style={
                                  colorBy === "Tag"
                                    ? {
                                        background: data!.tags.find(
                                          (t) => t.name === e.tags[0],
                                        )?.color,
                                        color: "white",
                                      }
                                    : undefined
                                }
                                key={e.id + e.start}
                                onClick={() => setSelected(e.id)}
                              >
                                {e.title}
                                <small>
                                  {e.all_day
                                    ? "All day"
                                    : dateLabel(e.start, zone, true)}
                                </small>
                              </button>
                            ))}
                        </div>
                      );
                    },
                  )}
                </div>
              )}
            </section>
          )}
          {page === "Sources" && (
            <>
              <div
                className="drop-zone"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const form = new FormData();
                  Array.from(e.dataTransfer.files).forEach((f) =>
                    form.append("files", f),
                  );
                  run(() => api("/sources/import", form), "Sources processed");
                }}
              >
                <Upload size={27} />
                <h3>A place for everything with a date.</h3>
                <p>Drop PDF, DOCX, transcripts, emails or chat exports here.</p>
                <button onClick={() => setModal("import")}>Browse files</button>
                <small>
                  Up to 20 MB per file · 50 files per batch ·{" "}
                  {account.cloud
                    ? "Private cloud processing"
                    : "Local processing"}
                </small>
              </div>
              <div className="panel">
                <div className="panel-heading">
                  <h2>Source library</h2>
                  <button
                    onClick={() =>
                      run(() => api("/demo"), "Synthetic demo sources loaded")
                    }
                  >
                    Load synthetic demo
                  </button>
                </div>
                {data!.sources.length
                  ? data!.sources.map((s) => (
                      <button
                        className="source-row"
                        key={s.id}
                        onClick={() => setSource(s)}
                      >
                        <div className="file-icon">
                          <FileText size={20} />
                        </div>
                        <div>
                          <strong>{s.name}</strong>
                          <small>
                            {s.type?.toUpperCase()} ·{" "}
                            {s.text_length.toLocaleString()} characters ·
                            Imported {dateLabel(s.created_at, zone)}
                          </small>
                        </div>
                        <span
                          className={
                            "tag " +
                            (s.processing_status === "ERROR" ? "critical" : "")
                          }
                        >
                          {s.processing_status === "COMPLETE"
                            ? s.event_count + " events found"
                            : s.processing_status}
                        </span>
                        <ChevronRight size={17} />
                      </button>
                    ))
                  : empty("Your source library starts here")}
              </div>
            </>
          )}
          {page === "Tags" && (
            <>
              <div className="section-toolbar">
                <p className="muted">
                  Bring your commitments together with a little color.
                </p>
                <button className="primary" onClick={() => setModal("tag")}>
                  <Plus size={15} />
                  Create tag
                </button>
              </div>
              <div className="tag-grid">
                {data!.tags
                  .filter((t) => !t.deleted)
                  .map((t) => (
                    <div className="tag-card" key={t.id}>
                      <span
                        className="tag-card-icon"
                        style={{ background: t.color + "18", color: t.color }}
                      >
                        <Tags size={22} />
                      </span>
                      <button
                        className="text-btn"
                        onClick={() => {
                          go("Search");
                          setFilter((f) => ({ ...f, tag: t.name }));
                        }}
                      >
                        <h2>{t.name}</h2>
                        <ArrowUpRight size={16} />
                      </button>
                      <p>
                        {live.filter((e) => e.tags.includes(t.name)).length}{" "}
                        events {t.archived ? "· Archived" : ""}
                      </p>
                      <div className="button-row">
                        <button
                          onClick={() => {
                            setModal("tag:" + t.id);
                          }}
                        >
                          Edit
                        </button>
                        <button
                          onClick={() =>
                            run(
                              () => api("/tags/" + t.id, undefined, "DELETE"),
                              "Tag removed; events retained",
                            )
                          }
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
              </div>
            </>
          )}
          {page === "Rules" && (
            <>
              <div className="section-toolbar">
                <p className="muted">
                  Your preferences, applied to every new extraction. Higher
                  priority numbers apply last.
                </p>
                <button className="primary" onClick={() => setModal("rule")}>
                  <Plus size={15} />
                  Create rule
                </button>
              </div>
              <div className="panel">
                {data.rules.length
                  ? data.rules.map((r) => (
                      <div className="rule-row" key={r.id}>
                        <span className="rule-number">{r.priority}</span>
                        <div>
                          <h3>{r.name}</h3>
                          <p>
                            If{" "}
                            {Object.entries(r.conditions)
                              .map(([k, v]) => `${k} contains “${v}”`)
                              .join(" and ")}{" "}
                            → {JSON.stringify(r.actions)}
                          </p>
                        </div>
                        <span className="tag">
                          {r.enabled ? "Active" : "Disabled"}
                        </span>
                        <button onClick={() => setModal("rule:" + r.id)}>
                          Edit
                        </button>
                        <button
                          onClick={() =>
                            run(() =>
                              api("/rules/" + r.id, undefined, "DELETE"),
                            )
                          }
                        >
                          Disable
                        </button>
                      </div>
                    ))
                  : empty(
                      "A small rule. One less decision.",
                      "Automatically assign tags, importance and reminders to matching events.",
                    )}
              </div>
            </>
          )}
          {page === "Projects" && (
            <ProjectsView
              projects={data.projects}
              events={live}
              open={setSelected}
              run={run}
            />
          )}
          {modal === "view" && (
            <Modal title="Save this view" close={() => setModal("")}>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  run(async () => {
                    await api("/views", {
                      name: f.get("name"),
                      filters: { ...filter, query },
                    });
                    setModal("");
                  });
                }}
              >
                <label>
                  View name
                  <input
                    name="name"
                    required
                    placeholder="University deadlines"
                  />
                </label>
                <button className="primary full">Save current filters</button>
              </form>
            </Modal>
          )}
          {page === "Audit History" && (
            <div className="panel">
              <div className="panel-heading">
                <h2>A clear record of every change</h2>
                <History size={18} />
              </div>
              {data.audit.map((a) => (
                <div className="audit-row" key={a.id}>
                  <span className="history-dot" />
                  <div>
                    <strong>{a.action}</strong>
                    <small>
                      {a.event_id
                        ? data!.events.find((e) => e.id === a.event_id)?.title
                        : "Workspace activity"}
                    </small>
                  </div>
                  <time>{dateLabel(a.created_at, zone, true)}</time>
                </div>
              ))}
            </div>
          )}
          {page === "Settings" && (
            <SettingsView
              settings={data!.settings}
              run={run}
              tags={data!.tags}
            />
          )}
          {page === "Dashboard" && (
            <ExtractionAnalytics events={data.events} sources={data.sources} />
          )}
          {page === "Rules" && <RuleConflictNotice rules={data.rules} />}
          <footer className="page-footer">
            <span>
              <ShieldCheck size={13} />{" "}
              {account.cloud
                ? "Private account. Evidence-backed. Yours."
                : "Local-first. Evidence-backed. Yours."}
            </span>
            <span>
              ChronoSync <i /> {zone}
            </span>
          </footer>
        </main>
      </div>
      {selected && event && page !== "Event Inbox" && (
        <div className="drawer-overlay" onClick={() => setSelected(null)}>
          <div onClick={(e) => e.stopPropagation()}>{details(event)}</div>
        </div>
      )}
      {source && (
        <Modal title="Source evidence" close={() => setSource(null)} wide>
          <div className="source-view">
            <span className="tag">{source.type?.toUpperCase()}</span>
            <h2>{source.name}</h2>
            <p>
              {source.processing_status} · {source.event_count} candidate events
              · {source.text_length} characters
            </p>
            {source.error && (
              <div className="notice warning">{source.error}</div>
            )}
            <small>
              Source date:{" "}
              {source.source_timestamp ||
                "Uses segment timestamp or import fallback"}
            </small>
            {!!source.removed_event_ids?.length && (
              <p className="notice warning">
                {source.removed_event_ids.length} events from the previous
                version are absent. No events were automatically deleted.
              </p>
            )}
            {source.segments.map((s, i) => (
              <div className="source-segment" key={i}>
                <small>
                  {s.page ? "PAGE " + s.page : "SEGMENT " + (i + 1)} {s.speaker}{" "}
                  {s.timestamp}
                </small>
                <pre>{s.text}</pre>
              </div>
            ))}
            <details>
              <summary>Checksum & provenance</summary>
              <code>{source.checksum}</code>
              <p>Imported {source.created_at}</p>
            </details>
            <button
              className="danger"
              onClick={() =>
                run(async () => {
                  await api("/sources/" + source.id, undefined, "DELETE");
                  setSource(null);
                }, "Source text removed; event descriptions retained")
              }
            >
              Delete stored source text
            </button>
          </div>
        </Modal>
      )}
      {(modal === "capture" || modal === "import") && (
        <Modal
          title={modal === "capture" ? "Quick capture" : "Import sources"}
          close={() => setModal("")}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              run(async () => {
                if (modal === "capture")
                  await api("/extraction/capture", {
                    name: f.get("name"),
                    text: f.get("text"),
                    source_timestamp: f.get("source_timestamp")
                      ? new Date(
                          String(f.get("source_timestamp")),
                        ).toISOString()
                      : null,
                  });
                else await api("/sources/import", f);
                setModal("");
                go("Event Inbox");
              }, "Source processed");
            }}
          >
            <p className="muted">
              Keep the context. Give relative dates the right starting point.
            </p>
            {modal === "capture" ? (
              <>
                <label>
                  Source name
                  <input name="name" defaultValue="Pasted message" required />
                </label>
                <label>
                  Message
                  <textarea
                    name="text"
                    placeholder="Meeting tomorrow at 4 PM…"
                    required
                    rows={6}
                  />
                </label>
              </>
            ) : (
              <label>
                Files
                <input
                  type="file"
                  name="files"
                  multiple
                  required
                  accept=".pdf,.docx,.txt,.md,.html,.srt,.vtt,.eml,.msg,.json,.csv"
                />
              </label>
            )}
            <label>
              Source date & time (optional)
              <input name="source_timestamp" type="datetime-local" />
            </label>
            <p className="form-hint">
              Message and email timestamps take precedence. Otherwise the source
              date above is used; import time is the final fallback.
            </p>
            <button className="primary full" disabled={busy}>
              {busy
                ? "Reading and resolving events…"
                : modal === "capture"
                  ? "Find events"
                  : "Import & find events"}
              <ArrowRight size={16} />
            </button>
          </form>
        </Modal>
      )}
      {modal === "event" && (
        <Modal
          title={edit ? "Edit event" : "Add an event"}
          close={() => setModal("")}
          wide
        >
          <EventForm
            event={edit}
            settings={data!.settings}
            tags={data!.tags}
            busy={busy}
            save={(body, both) =>
              run(async () => {
                await api(
                  "/events" + (edit ? "/" + edit.id + "?calendar=" + both : ""),
                  body,
                  edit ? "PUT" : "POST",
                );
                setModal("");
              }, "Event saved")
            }
          />
        </Modal>
      )}
      {(modal === "tag" || modal.startsWith("tag:")) && (
        <Modal title="Make it your own" close={() => setModal("")}>
          <TagForm
            tag={data!.tags.find((t) => t.id === modal.split(":")[1])}
            save={(body, id) =>
              run(async () => {
                await api(
                  "/tags" + (id ? "/" + id : ""),
                  body,
                  id ? "PUT" : "POST",
                );
                setModal("");
              })
            }
          />
        </Modal>
      )}
      {(modal === "rule" || modal.startsWith("rule:")) && (
        <Modal title="Create a little less work" close={() => setModal("")}>
          <RuleForm
            rule={data.rules.find((r) => r.id === modal.split(":")[1])}
            save={(body, id) =>
              run(async () => {
                await api(
                  "/rules" + (id ? "/" + id : ""),
                  body,
                  id ? "PUT" : "POST",
                );
                setModal("");
              })
            }
          />
        </Modal>
      )}
      {modal === "delete" && event && (
        <Modal title="Delete this event?" close={() => setModal("")}>
          <p>{event.title} will move to Trash and can be restored.</p>
          <button
            className="full"
            onClick={() => {
              action(event, "delete", { confirm: true, calendar: false });
              setModal("");
            }}
          >
            Delete from ChronoSync only
          </button>
          {event.external_id && (
            <button
              className="danger full"
              onClick={() => {
                action(event, "delete", { confirm: true, calendar: true });
                setModal("");
              }}
            >
              Delete from ChronoSync and calendar
            </button>
          )}
        </Modal>
      )}
      {modal === "notifications" && (
        <Modal title="Your notification center" close={() => setModal("")}>
          {data.notifications.length ? (
            data.notifications.map((n) => (
              <button
                className="notification-item"
                key={n.id}
                onClick={() => {
                  run(() => api("/notifications/" + n.id + "/read"));
                  if (n.event_id) setSelected(n.event_id);
                  setModal("");
                }}
              >
                <Bell size={16} />
                <div>
                  <strong>{n.title}</strong>
                  <small>{dateLabel(n.created_at, zone, true)}</small>
                </div>
                {!n.read && <span className="unread-dot" />}
              </button>
            ))
          ) : (
            <p className="muted">You’re all caught up.</p>
          )}
        </Modal>
      )}
      {modal === "command" && (
        <Modal title="Where would you like to go?" close={() => setModal("")}>
          <div className="command-list">
            {[
              "Quick capture",
              "Add event",
              "Import sources",
              "View today",
              "Critical events",
              "Sync calendar",
              "Create tag",
              ...navigation.map(([n]) => n),
            ].map((n, i) => (
              <button
                key={i}
                onClick={() => {
                  setModal("");
                  if (n === "Quick capture") setModal("capture");
                  else if (n === "Add event") {
                    setEdit(null);
                    setModal("event");
                  } else if (n === "Import sources") setModal("import");
                  else if (n === "Create tag") setModal("tag");
                  else if (n === "View today") {
                    go("Upcoming");
                    setFilter((f) => ({ ...f, from: today, to: today }));
                  } else if (n === "Critical events") {
                    go("Search");
                    setFilter((f) => ({ ...f, importance: "CRITICAL" }));
                  } else if (n === "Sync calendar") go("Settings");
                  else go(n);
                }}
              >
                <ArrowRight size={14} />
                {n}
              </button>
            ))}
          </div>
        </Modal>
      )}
      {modal === "bulk" && (
        <Modal title="Update selected events" close={() => setModal("")}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              run(async () => {
                for (const id of checked) {
                  const ev = data!.events.find((x) => x.id === id)!;
                  await api(
                    "/events/" + id + "?calendar=false",
                    {
                      ...editable(ev),
                      importance: f.get("importance") || ev.importance,
                      tags: f.get("tag")
                        ? [...new Set([...ev.tags, String(f.get("tag"))])]
                        : ev.tags,
                    },
                    "PUT",
                  );
                }
                setModal("");
                setChecked([]);
              });
            }}
          >
            <label>
              Importance
              <select name="importance">
                <option value="">Keep current</option>
                {importanceOrder.map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Add tag
              <select name="tag">
                <option value="">No change</option>
                {data!.tags.map((t) => (
                  <option key={t.id}>{t.name}</option>
                ))}
              </select>
            </label>
            <button className="primary full">Update selected events</button>
          </form>
        </Modal>
      )}
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={17} />
          {toast}
        </div>
      )}
      {busy && (
        <div className="working-indicator">
          <RefreshCw size={14} className="spin" />
          Working…
        </div>
      )}
    </div>
  );
}

function Modal({
  title,
  close,
  children,
  wide = false,
}: {
  title: string;
  close: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const old = document.activeElement as HTMLElement;
    ref.current?.querySelector<HTMLElement>("input,button,textarea")?.focus();
    return () => old?.focus();
  }, []);
  return (
    <div className="modal-overlay" onClick={close}>
      <div
        ref={ref}
        className={"modal " + (wide ? "wide" : "")}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") close();
          if (e.key === "Tab") {
            const items = Array.from(
              ref.current!.querySelectorAll<HTMLElement>(
                "button,input,textarea,select,a[href]",
              ),
            ).filter((el) => !(el as HTMLButtonElement).disabled);
            if (e.shiftKey && document.activeElement === items[0]) {
              e.preventDefault();
              items.at(-1)?.focus();
            } else if (!e.shiftKey && document.activeElement === items.at(-1)) {
              e.preventDefault();
              items[0]?.focus();
            }
          }
        }}
      >
        <div className="modal-header">
          <h2>{title}</h2>
          <button
            className="icon-btn"
            aria-label="Close dialog"
            onClick={close}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
function editable(e: Event) {
  return Object.fromEntries(
    [
      "title",
      "description",
      "start",
      "end",
      "timezone",
      "recurrence_timezone",
      "all_day",
      "type",
      "importance",
      "tags",
      "reminders",
      "location",
      "notes",
      "people",
      "organization",
      "rrule",
      "pinned",
      "projects",
      "related_ids",
    ].map((k) => [k, e[k as keyof Event]]),
  );
}
function EventForm({
  event: e,
  settings,
  tags,
  busy,
  save,
}: {
  event: Event | null;
  settings: Settings;
  tags: Tag[];
  busy: boolean;
  save: (body: unknown, both: boolean) => void;
}) {
  function local(value: string | null | undefined) {
    if (!value) return "";
    const d = new Date(value);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  }
  return (
    <form
      onSubmit={(ev) => {
        ev.preventDefault();
        const f = new FormData(ev.currentTarget);
        save(
          {
            ...(e ? editable(e) : {}),
            title: f.get("title"),
            start: new Date(String(f.get("start"))).toISOString(),
            end: new Date(String(f.get("end"))).toISOString(),
            timezone: f.get("timezone"),
            all_day: f.get("all_day") === "on",
            type: f.get("type"),
            importance: f.get("importance"),
            tags: f.getAll("tags"),
            reminders: String(f.get("reminders"))
              .split(",")
              .filter((v) => v.trim())
              .map(Number),
            location: f.get("location"),
            notes: f.get("notes"),
            description: f.get("description"),
            rrule: f.get("rrule") || null,
            projects: String(f.get("projects") || "")
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean),
            related_ids: String(f.get("related_ids") || "")
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean),
          },
          f.get("calendar") === "on",
        );
      }}
    >
      <label>
        Event title
        <input name="title" required defaultValue={e?.title} />
      </label>
      <div className="form-grid">
        <label>
          Start
          <input
            type="datetime-local"
            name="start"
            required
            defaultValue={local(e?.start)}
          />
        </label>
        <label>
          End
          <input
            type="datetime-local"
            name="end"
            required
            defaultValue={local(e?.end)}
          />
        </label>
      </div>
      <p className="form-hint">
        Date/time inputs use this laptop’s timezone:{" "}
        {Intl.DateTimeFormat().resolvedOptions().timeZone}. Stored with explicit
        offsets.
      </p>
      <div className="form-grid">
        <label>
          Display timezone
          <input
            name="timezone"
            defaultValue={e?.timezone || settings.timezone}
            required
          />
        </label>
        <label>
          Event type
          <select name="type" defaultValue={e?.type || "Meeting"}>
            {settings.event_types.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Importance
          <select name="importance" defaultValue={e?.importance || "MEDIUM"}>
            {importanceOrder.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Reminder minutes before
          <input
            name="reminders"
            defaultValue={(e?.reminders || [1440, 60]).join(",")}
          />
        </label>
      </div>
      <label className="checkbox">
        <input type="checkbox" name="all_day" defaultChecked={e?.all_day} />
        All-day representation (use midnight to next midnight)
      </label>
      <label>
        Tags
        <select name="tags" multiple defaultValue={e?.tags || []}>
          {tags
            .filter((t) => !t.deleted)
            .map((t) => (
              <option key={t.id}>{t.name}</option>
            ))}
        </select>
      </label>
      <div className="form-grid">
        <label>
          Location
          <input name="location" defaultValue={e?.location} />
        </label>
        <label>
          Recurrence RRULE
          <input
            name="rrule"
            placeholder="FREQ=WEEKLY;BYDAY=MO"
            defaultValue={e?.rrule || ""}
          />
        </label>
      </div>
      <label>
        Description
        <textarea name="description" defaultValue={e?.description} rows={2} />
      </label>
      <div className="form-grid">
        <label>
          Project names (comma separated)
          <input name="projects" defaultValue={e?.projects?.join(", ")} />
        </label>
        <label>
          Related event IDs (comma separated)
          <input name="related_ids" defaultValue={e?.related_ids?.join(", ")} />
        </label>
      </div>
      <label>
        Private notes
        <textarea name="notes" defaultValue={e?.notes} rows={2} />
      </label>
      {e?.external_id && (
        <label className="checkbox">
          <input name="calendar" type="checkbox" defaultChecked />
          Update app and calendar (uncheck for app only)
        </label>
      )}
      <button disabled={busy} className="primary full">
        {busy ? "Saving…" : "Save event"}
        <Check size={16} />
      </button>
    </form>
  );
}
function TagForm({
  tag,
  save,
}: {
  tag?: Tag;
  save: (body: unknown, id?: string) => void;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        save(
          {
            name: f.get("name"),
            color: f.get("color"),
            archived: f.get("archived") === "on",
          },
          tag?.id,
        );
      }}
    >
      <label>
        Tag name
        <input name="name" required defaultValue={tag?.name} />
      </label>
      <label>
        Color
        <input
          type="color"
          name="color"
          defaultValue={tag?.color || "#517d70"}
        />
      </label>
      <label className="checkbox">
        <input type="checkbox" name="archived" defaultChecked={tag?.archived} />
        Archive tag
      </label>
      <button className="primary full">Save tag</button>
    </form>
  );
}
function RuleForm({
  rule,
  save,
}: {
  rule?: Rule;
  save: (body: unknown, id?: string) => void;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        const actions: Record<string, unknown> = {};
        if (f.get("importance")) actions.importance = f.get("importance");
        if (f.get("tag")) actions.tags = [f.get("tag")];
        if (f.get("reminders"))
          actions.reminders = String(f.get("reminders")).split(",").map(Number);
        save(
          {
            name: f.get("name"),
            priority: Number(f.get("priority")),
            enabled: true,
            conditions: { [String(f.get("field"))]: f.get("value") },
            actions,
          },
          rule?.id,
        );
      }}
    >
      <label>
        Rule name
        <input name="name" required defaultValue={rule?.name} />
      </label>
      <div className="form-grid">
        <label>
          If
          <select
            name="field"
            defaultValue={Object.keys(rule?.conditions || {})[0] || "contains"}
          >
            <option value="contains">Event text contains</option>
            <option value="type">Event type contains</option>
            <option value="tags">Tags contain</option>
            <option value="source">Source name contains</option>
          </select>
        </label>
        <label>
          Value
          <input
            name="value"
            required
            defaultValue={Object.values(rule?.conditions || {})[0]}
          />
        </label>
      </div>
      <label>
        Set importance
        <select
          name="importance"
          defaultValue={String(rule?.actions.importance || "")}
        >
          <option value="">No change</option>
          {importanceOrder.map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </label>
      <label>
        Add tag
        <input
          name="tag"
          defaultValue={(rule?.actions.tags as string[])?.[0]}
        />
      </label>
      <label>
        Reminder offsets (minutes)
        <input
          name="reminders"
          defaultValue={(rule?.actions.reminders as number[])?.join(",")}
        />
      </label>
      <label>
        Priority
        <input
          type="number"
          name="priority"
          defaultValue={rule?.priority || 0}
        />
      </label>
      <button className="primary full">Save rule</button>
    </form>
  );
}
function SettingsView({
  settings: s,
  run,
}: {
  settings: Settings;
  tags: Tag[];
  run: (fn: () => Promise<unknown>, message?: string) => Promise<void>;
}) {
  const [connection, setConnection] = useState("");
  const account = useAccount();
  return (
    <div className="settings-grid">
      <section className="panel settings-panel">
        <h2>Make time work your way.</h2>
        <p className="muted">The defaults behind every date and reminder.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            run(
              () =>
                api(
                  "/settings",
                  {
                    timezone: f.get("timezone"),
                    date_order: f.get("date_order"),
                    eod: f.get("eod") || null,
                    cob: f.get("cob") || null,
                    default_deadline_time:
                      f.get("default_deadline_time") || null,
                    duration: Number(f.get("duration")),
                    buffer: Number(f.get("buffer")),
                  },
                  "PUT",
                ),
              "Date preferences saved",
            );
          }}
        >
          <label>
            Timezone
            <input name="timezone" defaultValue={s.timezone} />
          </label>
          <label>
            Numeric date order
            <select name="date_order" defaultValue={s.date_order}>
              <option value="DMY">DD/MM/YYYY</option>
              <option value="MDY">MM/DD/YYYY</option>
            </select>
          </label>
          <div className="form-grid">
            <label>
              End of day (EOD)
              <input name="eod" type="time" defaultValue={s.eod || ""} />
            </label>
            <label>
              Close of business (COB)
              <input name="cob" type="time" defaultValue={s.cob || ""} />
            </label>
            <label>
              Default deadline time
              <input
                name="default_deadline_time"
                type="time"
                defaultValue={s.default_deadline_time || ""}
              />
            </label>
            <label>
              Event duration (minutes)
              <input
                name="duration"
                type="number"
                min="1"
                max="1440"
                defaultValue={s.duration}
              />
            </label>
          </div>
          <label>
            Travel / meeting buffer (minutes)
            <input
              name="buffer"
              type="number"
              min="0"
              max="1440"
              defaultValue={s.buffer}
            />
          </label>
          <button className="primary">Save preferences</button>
        </form>
      </section>
      <div>
        <section className="panel settings-panel">
          <h2>
            <Link2 size={18} /> Calendar connection
          </h2>
          <p className="muted">Review first. Synchronize when you’re ready.</p>
          <label>
            Provider
            <select
              value={s.provider}
              onChange={(e) =>
                run(() => api("/settings", { provider: e.target.value }, "PUT"))
              }
            >
              <option value="mock">Mock calendar · local testing</option>
              {!account.cloud && (
                <option value="outlook">Microsoft Outlook Desktop</option>
              )}
            </select>
          </label>
          <div className="notice">
            <ShieldCheck size={17} />
            <span>Manual approval required. No invitations are sent.</span>
          </div>
          <button
            onClick={() =>
              run(async () => {
                const r = await api<{ connected: boolean; error?: string }>(
                  "/calendar/test?name=" + s.provider,
                );
                setConnection(
                  r.connected
                    ? "Connected. Read-only connection test passed."
                    : r.error || "Unavailable",
                );
              }, "Connection checked")
            }
          >
            Test calendar connection
          </button>
          {connection && <p className="notice">{connection}</p>}
          <p className="form-hint">
            {account.cloud
              ? "Export ICS files to your phone calendar for reminders. Free hosting sleeps when idle; server reminders do not run while it is asleep. Desktop Outlook cannot connect from this hosted app."
              : "Classic Outlook + pywin32 required for direct integration. Outlook supports one native reminder; recurring events can be exported as ICS."}
          </p>
          <a className="button-link" href="/api/export/ics">
            <Download size={15} />
            Export approved events as ICS
          </a>
        </section>
        <section className="panel settings-panel">
          <h2>
            <ShieldCheck size={18} /> Private by design
          </h2>
          <p>
            {account.cloud
              ? "Your documents and calendar data are stored in your private cloud account, separately from other accounts."
              : "Your documents and calendar data stay on this laptop."}
          </p>
          <div className="privacy-status">
            <span className="dot low" />
            {account.cloud
              ? "Hosted processing · AI disabled"
              : "Local processing only"}
          </div>
          <p className="form-hint">
            External AI is disabled. Source evidence never leaves the app for AI
            processing. Clipboard access is explicit paste only.
          </p>
        </section>
        <section className="panel settings-panel">
          <h2>Take your data with you</h2>
          <div className="button-row wrap">
            {["ics", "csv", "json", "xlsx", "settings"].map((f) => (
              <a className="button-link" href={"/api/export/" + f} key={f}>
                <Download size={14} />
                {f.toUpperCase()}
              </a>
            ))}
          </div>
          <p className="form-hint">
            Exports may contain private event text. Save them somewhere safe.
          </p>
        </section>
      </div>
      <section className="panel settings-panel">
        <h2>Reminder profiles</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            run(() =>
              api(
                "/settings",
                {
                  reminder_profiles: Object.fromEntries(
                    importanceOrder.map((k) => [
                      k,
                      String(f.get(k))
                        .split(",")
                        .filter((v) => v.trim())
                        .map(Number),
                    ]),
                  ),
                },
                "PUT",
              ),
            );
          }}
        >
          {importanceOrder.map((k) => (
            <label key={k}>
              {k} · minutes before
              <input name={k} defaultValue={s.reminder_profiles[k].join(",")} />
            </label>
          ))}
          <button className="primary">Save reminder profiles</button>
        </form>
      </section>
      <section className="panel settings-panel">
        <h2>Custom event types</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            run(() =>
              api(
                "/settings",
                {
                  event_types: String(f.get("types"))
                    .split(",")
                    .map((v) => v.trim())
                    .filter(Boolean),
                },
                "PUT",
              ),
            );
          }}
        >
          <label>
            Comma-separated types
            <textarea
              name="types"
              rows={6}
              defaultValue={s.event_types.join(", ")}
            />
          </label>
          <button className="primary">Save event types</button>
        </form>
      </section>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AccountGate>
      <App />
    </AccountGate>
  </React.StrictMode>,
);
