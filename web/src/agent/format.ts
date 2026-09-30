// The console's two clocks (ADR-0004, Two clocks): wall times in the reader's own zone, and the bank's frozen date as
// it was published, which no zone shifts.
const WALL = new Intl.DateTimeFormat("es", {
  dateStyle: "medium",
  timeStyle: "medium",
});
const CLOCK = new Intl.DateTimeFormat("es", { timeStyle: "medium" });
const BANK = new Intl.DateTimeFormat("es", {
  dateStyle: "long",
  timeZone: "UTC",
});

export function wallTime(iso: string): string {
  return WALL.format(new Date(iso));
}

export function clockTime(at: Date): string {
  return CLOCK.format(at);
}

export function bankDate(date: string): string {
  return BANK.format(new Date(`${date}T00:00:00Z`));
}
