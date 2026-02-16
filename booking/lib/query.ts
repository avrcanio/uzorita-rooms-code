export type AvailabilityQuery = {
  checkin: string;
  checkout: string;
  adults: number;
  children: number;
};

function first(v: string | string[] | undefined): string | undefined {
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

function clampInt(v: string | undefined, fallback: number, min: number, max: number): number {
  const n = Number.parseInt(v ?? "", 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}

function todayIso(): string {
  // Good enough for defaults; server-side rendering time is fine here.
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return todayIso();
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function isIsoDate(s: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(s);
}

export function parseSearchParams(sp: Record<string, string | string[]>): AvailabilityQuery {
  const rawCheckin = first(sp.checkin);
  const rawCheckout = first(sp.checkout);
  const today = todayIso();
  const checkin = rawCheckin && isIsoDate(rawCheckin) ? rawCheckin : today;
  let checkout = rawCheckout && isIsoDate(rawCheckout) ? rawCheckout : addDaysIso(checkin, 1);
  if (checkout <= checkin) {
    checkout = addDaysIso(checkin, 1);
  }
  const adults = clampInt(first(sp.adults), 2, 1, 10);
  const children = clampInt(first(sp.children), 0, 0, 10);
  return { checkin, checkout, adults, children };
}
