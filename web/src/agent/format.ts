// Wall times in the reader's own zone (ADR-0004, Two clocks), to the minute: the registry keeps the seconds.
const WALL = new Intl.DateTimeFormat("es", {
  dateStyle: "medium",
  timeStyle: "short",
});
const CLOCK = new Intl.DateTimeFormat("es", { timeStyle: "medium" });
const EXACT = new Intl.DateTimeFormat("es", {
  dateStyle: "medium",
  timeStyle: "medium",
});

export function wallTime(iso: string): string {
  return WALL.format(new Date(iso));
}

// The registry's clock, to the second: there order and latency are the point.
export function exactTime(iso: string): string {
  return EXACT.format(new Date(iso));
}

export function clockTime(at: Date): string {
  return CLOCK.format(at);
}
