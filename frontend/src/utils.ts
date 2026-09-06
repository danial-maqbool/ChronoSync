export const importanceOrder = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"];
export function dateLabel(
  value: string | null,
  zone = "Asia/Karachi",
  time = false,
) {
  if (!value) return "Date needs review";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: zone,
    day: "numeric",
    month: "short",
    ...(time ? { hour: "numeric", minute: "2-digit" } : {}),
  }).format(new Date(value));
}
export function dayKey(value: string, zone: string) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}
export function isInbox(status: string) {
  return ["PROPOSED", "NEEDS_REVIEW"].includes(status);
}
export function reminderLabel(n: number) {
  return n >= 1440 ? `${n / 1440}d` : n >= 60 ? `${n / 60}h` : `${n}m`;
}
export function upcomingGroup(
  value: string | null,
  zone: string,
  now = new Date(),
) {
  if (!value) return "Needs review";
  const today = dayKey(now.toISOString(), zone);
  const target = dayKey(value, zone);
  const delta = Math.round((Date.parse(target) - Date.parse(today)) / 86400000);
  if (delta < 0) return "Overdue / past";
  if (delta === 0) return "Today";
  if (delta === 1) return "Tomorrow";
  const left = 7 - ((new Date(today + "T12:00:00Z").getUTCDay() + 6) % 7);
  if (delta < left) return "This week";
  if (delta < left + 7) return "Next week";
  return "Later";
}
export async function api<T = unknown>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const options: RequestInit = { method: method || (body ? "POST" : "GET") };
  if (body instanceof FormData) options.body = body;
  else if (body) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }
  const r = await fetch("/api" + path, options);
  if (!r.ok) {
    if (r.status === 401 && !path.startsWith("/auth/"))
      window.dispatchEvent(new Event("chronosync-signed-out"));
    const data = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return r.json();
}
