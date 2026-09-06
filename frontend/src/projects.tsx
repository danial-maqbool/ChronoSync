import { useState } from "react";
import type { Event, Tag } from "./types";
import { api, dateLabel } from "./utils";
export function ProjectsView({
  projects,
  events,
  open,
  run,
}: {
  projects: Tag[];
  events: Event[];
  open: (id: string) => void;
  run: (fn: () => Promise<unknown>, message?: string) => Promise<void>;
}) {
  const [selected, setSelected] = useState("");
  const p = projects.find((x) => x.id === selected);
  return (
    <>
      <div className="settings-grid">
        <section className="panel settings-panel">
          <h2>Keep the bigger picture in view.</h2>
          <p className="muted">
            Group application deadlines, interviews, reviews and follow-ups into
            a shared timeline.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              run(
                () =>
                  api("/projects", { name: f.get("name"), color: "#517d70" }),
                "Project created",
              );
            }}
          >
            <label>
              New project name
              <input name="name" required />
            </label>
            <button className="primary">Create project</button>
          </form>
        </section>
        <section className="panel settings-panel">
          <h2>Projects</h2>
          {projects.map((project) => (
            <button
              className="source-row"
              key={project.id}
              onClick={() => setSelected(project.id)}
            >
              <strong>{project.name}</strong>
              <small>
                {
                  events.filter((e) => e.projects?.includes(project.name))
                    .length
                }{" "}
                events
              </small>
            </button>
          ))}
        </section>
      </div>
      {p && (
        <section className="panel settings-panel">
          <h2>{p.name}</h2>
          <form
            onSubmit={(ev) => {
              ev.preventDefault();
              const f = new FormData(ev.currentTarget);
              const e = events.find((x) => x.id === f.get("event"))!;
              const body = Object.fromEntries(
                [
                  "title",
                  "description",
                  "start",
                  "end",
                  "timezone",
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
              body.projects = [...new Set([...(e.projects || []), p.name])];
              run(
                () => api("/events/" + e.id + "?calendar=false", body, "PUT"),
                "Added to project",
              );
            }}
          >
            <label>
              Add event to project
              <select name="event" required>
                {events
                  .filter((e) => !e.projects?.includes(p.name))
                  .map((e) => (
                    <option value={e.id} key={e.id}>
                      {e.title}
                    </option>
                  ))}
              </select>
            </label>
            <button>Add event</button>
          </form>
          {events
            .filter((e) => e.projects?.includes(p.name))
            .sort((a, b) => (a.start || "z").localeCompare(b.start || "z"))
            .map((e) => (
              <button
                className="source-row"
                key={e.id}
                onClick={() => open(e.id)}
              >
                <strong>{e.title}</strong>
                <span className="tag">{dateLabel(e.start, e.timezone)}</span>
                <span className="tag">{e.status}</span>
              </button>
            ))}
        </section>
      )}
    </>
  );
}
