"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type ReservationStatus = "expected" | "checked_in" | "checked_out" | "canceled";

type Reservation = {
  id: number;
  external_id: string;
  room_name: string;
  room: number | null;
  check_in_date: string;
  check_out_date: string;
  status: ReservationStatus;
  total_amount: string | null;
  currency: string;
  guests_count: number;
  primary_guest_name: string;
  primary_guest_nationality_iso2: string;
};

type MeResponse = {
  id: number;
  username: string;
  email: string;
  is_superuser: boolean;
};

type Room = {
  id: number;
  code: string;
  room_type: number;
  room_type_name: string;
  is_active: boolean;
};

const statusOptions: Array<{ value: string; label: string }> = [
  { value: "", label: "Svi statusi" },
  { value: "expected", label: "Očekuje dolazak" },
  { value: "checked_in", label: "Prijavljen" },
  { value: "checked_out", label: "Odjavljen" },
  { value: "canceled", label: "Otkazan" },
];

const statusLabel: Record<ReservationStatus, string> = {
  expected: "Očekuje dolazak",
  checked_in: "Prijavljen",
  checked_out: "Odjavljen",
  canceled: "Otkazan",
};

function flagIconClass(iso2?: string | null): string | null {
  const cc = (iso2 || "").trim().toLowerCase();
  if (!/^[a-z]{2}$/.test(cc)) return null;
  return `fi fi-${cc}`;
}

type OverviewMode = "today" | "week" | "month" | "all";

function addDaysIso(iso: string, deltaDays: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + deltaDays);
  return d.toISOString().slice(0, 10);
}

function startOfMonthIso(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(1);
  return d.toISOString().slice(0, 10);
}

function addMonthsIso(iso: string, deltaMonths: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + deltaMonths);
  return d.toISOString().slice(0, 10);
}

function startOfIsoWeekIso(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  // JS: Sunday=0 .. Saturday=6. ISO Monday start.
  const day = d.getUTCDay();
  const diff = (day + 6) % 7; // Mon->0 ... Sun->6
  d.setUTCDate(d.getUTCDate() - diff);
  return d.toISOString().slice(0, 10);
}

function isoWeekYearAndNumber(iso: string): { weekYear: number; week: number } {
  const d = new Date(`${iso}T00:00:00Z`);
  // ISO week based on Thursday.
  const day = (d.getUTCDay() + 6) % 7; // Mon=0..Sun=6
  d.setUTCDate(d.getUTCDate() - day + 3); // Thursday
  const weekYear = d.getUTCFullYear();
  const firstThursday = new Date(Date.UTC(weekYear, 0, 4));
  const firstDay = (firstThursday.getUTCDay() + 6) % 7;
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDay + 3);
  const diffMs = d.getTime() - firstThursday.getTime();
  const week = 1 + Math.round(diffMs / (7 * 24 * 60 * 60 * 1000));
  return { weekYear, week };
}

function monthLabelHr(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  const raw = new Intl.DateTimeFormat("hr-HR", { month: "long", year: "numeric" }).format(d);
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export default function Home() {
  const router = useRouter();

  const [me, setMe] = useState<MeResponse | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const [rooms, setRooms] = useState<Room[]>([]);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [roomFilter, setRoomFilter] = useState<"all" | "unassigned" | number>("all");
  const [overviewMode, setOverviewMode] = useState<OverviewMode>("today");

  useEffect(() => {
    const controller = new AbortController();

    const checkAuth = async () => {
      try {
        const response = await fetch("/api/auth/me/", {
          signal: controller.signal,
          credentials: "include",
          headers: { Accept: "application/json" },
        });

        if (response.status === 401 || response.status === 403) {
          router.replace("/login?next=/");
          return;
        }

        if (!response.ok) {
          throw new Error(`Auth greška (${response.status})`);
        }

        const data = (await response.json()) as MeResponse;
        setMe(data);
        setAuthReady(true);
      } catch {
        if (controller.signal.aborted) return;
        router.replace("/login?next=/");
      }
    };

    checkAuth();
    return () => controller.abort();
  }, [router]);

  const lang = useMemo(() => (typeof document === "undefined" ? "en" : document.documentElement.lang || "en"), []);

  useEffect(() => {
    if (!authReady) return;

    const controller = new AbortController();
    const loadRooms = async () => {
      try {
        const response = await fetch(`/api/rooms/rooms/?lang=${encodeURIComponent(lang)}`, {
          signal: controller.signal,
          credentials: "include",
          headers: { Accept: "application/json" },
        });

        if (response.status === 401 || response.status === 403) {
          router.replace("/login?next=/");
          return;
        }

        if (!response.ok) return;
        const data = (await response.json()) as Room[];
        setRooms(data);
      } catch {
        // Non-fatal: timeline works without room metadata.
      }
    };

    loadRooms();
    return () => controller.abort();
  }, [authReady, router, lang]);

  useEffect(() => {
    if (!authReady) return;

    const controller = new AbortController();

    const fetchReservations = async () => {
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams();
        if (status) params.set("status", status);
        if (search.trim()) params.set("search", search.trim());
        const query = params.toString();

        const response = await fetch(`/api/reception/reservations/${query ? `?${query}` : ""}`, {
          signal: controller.signal,
          credentials: "include",
          headers: { Accept: "application/json" },
        });

        if (response.status === 401 || response.status === 403) {
          router.replace("/login?next=/");
          return;
        }

        if (!response.ok) {
          throw new Error(`API greška (${response.status})`);
        }

        const data = (await response.json()) as Reservation[];
        setReservations(data);
      } catch (fetchError) {
        if (controller.signal.aborted) return;
        setError(fetchError instanceof Error ? fetchError.message : "Greška pri učitavanju.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    fetchReservations();
    return () => controller.abort();
  }, [authReady, status, search, router]);

  const roomById = useMemo(() => {
    const mapped: Record<number, Room> = {};
    for (const r of rooms) mapped[r.id] = r;
    return mapped;
  }, [rooms]);

  const roomChipStyle = (code: string | null | undefined) => {
    const c = (code || "").toUpperCase();
    if (c === "K1") return "border-amber-300/40 bg-amber-300/10 text-amber-50";
    if (c === "K2") return "border-sky-300/40 bg-sky-300/10 text-sky-50";
    if (c === "D1") return "border-emerald-300/40 bg-emerald-300/10 text-emerald-50";
    if (c === "T1") return "border-rose-300/40 bg-rose-300/10 text-rose-50";
    return "border-brand-gold/35 bg-brand-gold/10 text-brand-cream";
  };

  const filteredReservations = useMemo(() => {
    if (roomFilter === "all") return reservations;
    if (roomFilter === "unassigned") return reservations.filter((r) => !r.room);
    return reservations.filter((r) => r.room === roomFilter);
  }, [reservations, roomFilter]);

  const logout = async () => {
    try {
      await fetch("/api/auth/csrf/", { credentials: "include" });
      const csrfToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1];

      await fetch("/api/auth/logout/", {
        method: "POST",
        credentials: "include",
        headers: {
          "X-CSRFToken": csrfToken || "",
        },
      });
    } finally {
      router.replace("/login?next=/");
    }
  };

  const today = new Date().toISOString().slice(0, 10);

  const period = useMemo(() => {
    if (overviewMode === "all") {
      return { start: "0001-01-01", end: "9999-12-31", label: "Prikaz: sve" };
    }
    if (overviewMode === "today") {
      const start = today;
      const end = addDaysIso(today, 1);
      return { start, end, label: "Današnji pregled" };
    }
    if (overviewMode === "week") {
      const start = startOfIsoWeekIso(today);
      const end = addDaysIso(start, 7);
      return { start, end, label: "Pregled: ovaj tjedan" };
    }
    const start = startOfMonthIso(today);
    const end = startOfMonthIso(addMonthsIso(start, 1));
    return { start, end, label: "Pregled: ovaj mjesec" };
  }, [overviewMode, today]);

  const defaultOpenMonthKey = useMemo(() => {
    return overviewMode === "all" ? today.slice(0, 7) : period.start.slice(0, 7);
  }, [overviewMode, today, period.start]);

  const upcomingLowerBound = useMemo(() => {
    // "Nadolazece" always means from today onwards (even if the selected period starts earlier).
    if (overviewMode === "all") return period.start;
    return today > period.start ? today : period.start;
  }, [overviewMode, today, period.start]);

  const upcomingInPeriod = useMemo(() => {
    return filteredReservations
      .filter((item) => item.check_in_date >= upcomingLowerBound && item.check_in_date < period.end)
      .sort((a, b) => (a.check_in_date !== b.check_in_date ? a.check_in_date.localeCompare(b.check_in_date) : a.id - b.id));
  }, [filteredReservations, upcomingLowerBound, period.end]);

  const summary = useMemo(() => {
    const arrivals = upcomingInPeriod.length;
    const departures = filteredReservations.filter(
      (item) => item.check_out_date >= upcomingLowerBound && item.check_out_date < period.end,
    ).length;
    const checkedInCount = filteredReservations.filter(
      (item) => item.status === "checked_in" && item.check_in_date <= today && item.check_out_date > today,
    ).length;
    return { arrivals, departures, checkedInCount };
  }, [filteredReservations, upcomingInPeriod.length, upcomingLowerBound, period.end, today]);

  const groupedUpcoming = useMemo(() => {
    const monthMap = new Map<
      string,
      { monthKey: string; monthStartIso: string; weeks: Map<string, { weekYear: number; week: number; items: Reservation[] }> }
    >();

    for (const item of upcomingInPeriod) {
      const monthKey = item.check_in_date.slice(0, 7); // YYYY-MM
      const monthStartIso = `${monthKey}-01`;
      if (!monthMap.has(monthKey)) monthMap.set(monthKey, { monthKey, monthStartIso, weeks: new Map() });
      const month = monthMap.get(monthKey)!;

      const { weekYear, week } = isoWeekYearAndNumber(item.check_in_date);
      const weekKey = `${weekYear}-W${String(week).padStart(2, "0")}`;
      if (!month.weeks.has(weekKey)) month.weeks.set(weekKey, { weekYear, week, items: [] });
      month.weeks.get(weekKey)!.items.push(item);
    }

    const months = Array.from(monthMap.values()).sort((a, b) => a.monthKey.localeCompare(b.monthKey));
    return months.map((m) => ({
      monthKey: m.monthKey,
      monthStartIso: m.monthStartIso,
      weeks: Array.from(m.weeks.values()).sort((a, b) => (a.weekYear !== b.weekYear ? a.weekYear - b.weekYear : a.week - b.week)),
    }));
  }, [upcomingInPeriod]);

  return (
    <main className="relative min-h-screen overflow-hidden bg-brand-ink text-brand-cream">
      <div className="pointer-events-none absolute inset-0 brand-grid opacity-30" />
      <div className="pointer-events-none absolute -top-28 -right-20 h-72 w-72 rounded-full bg-brand-gold/25 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-16 h-64 w-64 rounded-full bg-brand-gold/20 blur-3xl" />

      <section className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-5 py-8 sm:px-8 lg:px-10">
        <header className="rounded-2xl border border-brand-gold/30 bg-black/35 p-5 backdrop-blur-sm sm:p-7">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="rounded-xl border border-brand-gold/40 bg-brand-gold/10 p-2">
                <Image
                  src="/kapa.png"
                  alt="Uzorita logo"
                  width={74}
                  height={74}
                  priority
                  className="h-[56px] w-auto sm:h-[70px]"
                />
              </div>
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.24em] text-brand-gold">Uzorita Rooms</p>
                <h1 className="text-2xl font-semibold leading-tight sm:text-3xl">Recepcija i timeline</h1>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="rounded-full border border-brand-gold/40 bg-brand-gold/15 px-4 py-2 text-sm">
                {me ? `Korisnik: ${me.username}` : "Provjera prijave..."}
              </div>
              <button
                type="button"
                onClick={logout}
                className="rounded-full border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm hover:bg-brand-gold/20"
              >
                Odjava
              </button>
            </div>
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-2xl border border-brand-gold/25 bg-black/35 p-5 sm:p-7">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">{period.label}</p>
              <select
	                value={overviewMode}
	                onChange={(event) => setOverviewMode(event.target.value as OverviewMode)}
	                className="rounded-xl border border-brand-gold/30 bg-black/40 px-3 py-2 text-sm text-brand-cream outline-none focus:border-brand-gold"
	                aria-label="Odabir pregleda"
	              >
	                <option value="all" className="bg-zinc-900">
	                  Prikaz: sve
	                </option>
	                <option value="today" className="bg-zinc-900">
	                  Današnji pregled
	                </option>
	                <option value="week" className="bg-zinc-900">
	                  Pregled: ovaj tjedan
	                </option>
	                <option value="month" className="bg-zinc-900">
	                  Pregled: ovaj mjesec
	                </option>
	              </select>
	            </div>
	
	            <div className="mt-6 grid gap-3 sm:grid-cols-3">
	              <div className="rounded-xl border border-brand-gold/25 bg-brand-gold/10 p-4">
	                <p className="text-sm text-brand-cream/80">Dolasci</p>
	                <p className="mt-2 text-3xl font-semibold">{summary.arrivals}</p>
	              </div>
	              <div className="rounded-xl border border-brand-gold/25 bg-brand-gold/10 p-4">
	                <p className="text-sm text-brand-cream/80">Odlasci</p>
	                <p className="mt-2 text-3xl font-semibold">{summary.departures}</p>
	              </div>
	              <div className="rounded-xl border border-brand-gold/25 bg-brand-gold/10 p-4">
	                <p className="text-sm text-brand-cream/80">Trenutno prijavljeni</p>
	                <p className="mt-2 text-3xl font-semibold">{summary.checkedInCount}</p>
	              </div>
	            </div>
	          </section>

          <section className="rounded-2xl border border-brand-gold/25 bg-black/35 p-5 sm:p-7">
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Filteri</p>
            <div className="mt-4 grid gap-3">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm text-brand-cream outline-none focus:border-brand-gold"
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value} className="bg-zinc-900">
                    {option.label}
                  </option>
                ))}
              </select>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Pretraga: gost, soba, rezervacija..."
                className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm text-brand-cream outline-none placeholder:text-brand-cream/50 focus:border-brand-gold"
              />
            </div>
          </section>
        </div>

        <section className="rounded-2xl border border-brand-gold/25 bg-black/35 p-5 sm:p-7">
          <div className="flex items-center justify-between gap-4">
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Timeline rezervacija</p>
            <div className="flex items-center gap-3">
              <Link
                href="/calendar/rooms"
                className="rounded-full border border-brand-gold/40 bg-brand-gold/15 px-4 py-2 text-sm hover:bg-brand-gold/25"
              >
                Kalendar soba
              </Link>
              <span className="text-sm text-brand-cream/70">
                Prikazano: {upcomingInPeriod.length} / {filteredReservations.length}
                {roomFilter === "all" ? "" : ` / ${reservations.length}`}
              </span>
            </div>
          </div>

          {authReady && rooms.length > 0 && (
            <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
              <button
                type="button"
                onClick={() => setRoomFilter("all")}
                className={[
                  "whitespace-nowrap rounded-full border px-4 py-2 text-sm",
                  roomFilter === "all"
                    ? "border-brand-gold/55 bg-brand-gold/20"
                    : "border-brand-gold/25 bg-black/30 hover:bg-brand-gold/10",
                ].join(" ")}
              >
                Sve sobe
              </button>
              {rooms.map((room) => (
                <button
                  key={room.id}
                  type="button"
                  onClick={() => setRoomFilter(room.id)}
                  className={[
                    "whitespace-nowrap rounded-full border px-4 py-2 text-sm",
                    roomChipStyle(room.code),
                    roomFilter === room.id ? "ring-2 ring-brand-gold/35" : "hover:bg-black/40",
                  ].join(" ")}
                  title={room.room_type_name}
                >
                  {room.code}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setRoomFilter("unassigned")}
                className={[
                  "whitespace-nowrap rounded-full border px-4 py-2 text-sm",
                  roomFilter === "unassigned"
                    ? "border-brand-gold/55 bg-brand-gold/20"
                    : "border-brand-gold/25 bg-black/30 hover:bg-brand-gold/10",
                ].join(" ")}
              >
                Bez sobe
              </button>
            </div>
          )}

          {!authReady && <p className="mt-4 text-brand-cream/80">Provjera autentifikacije...</p>}
          {authReady && loading && <p className="mt-4 text-brand-cream/80">Učitavanje podataka...</p>}
          {error && <p className="mt-4 text-red-300">Greška: {error}</p>}
	          {!loading && !error && upcomingInPeriod.length === 0 && (
	            <p className="mt-4 text-brand-cream/80">Nema rezultata za zadane filtere.</p>
	          )}
	
	          {!loading && !error && upcomingInPeriod.length > 0 && (
	            <div className="mt-4 space-y-3">
	              {groupedUpcoming.map((month) => (
	                <details
	                  key={month.monthKey}
	                  className="rounded-xl border border-brand-gold/20 bg-black/25"
	                  open={month.monthKey === defaultOpenMonthKey}
	                >
	                  <summary className="cursor-pointer select-none px-4 py-3 text-sm text-brand-cream/85">
	                    <span className="font-mono text-xs uppercase tracking-[0.18em] text-brand-gold">
	                      {monthLabelHr(month.monthStartIso)}
	                    </span>
	                  </summary>
	                  <div className="space-y-3 px-4 pb-4">
	                    {month.weeks.map((w) => {
	                      const weekStart = startOfIsoWeekIso(w.items[0]?.check_in_date || month.monthStartIso);
	                      const weekEnd = addDaysIso(weekStart, 7);
	                      return (
	                        <details
	                          key={`${w.weekYear}-${w.week}`}
	                          className="rounded-xl border border-brand-gold/20 bg-black/20"
	                          open={overviewMode === "today" || overviewMode === "week"}
	                        >
	                          <summary className="cursor-pointer select-none px-4 py-3 text-sm text-brand-cream/80">
	                            <div className="flex items-center justify-between gap-4">
	                              <span className="font-mono text-xs text-brand-gold">
	                                Tjedan {String(w.week).padStart(2, "0")} / {w.weekYear}
	                              </span>
	                              <span className="text-xs text-brand-cream/60">
	                                {weekStart} → {weekEnd}
	                              </span>
	                            </div>
	                          </summary>
	                          <ul className="space-y-3 px-4 pb-4">
	                            {w.items.map((item) => {
	                              const roomCode = item.room ? roomById[item.room]?.code : null;
	                              const flag = flagIconClass(item.primary_guest_nationality_iso2);
	                              return (
	                                <li key={item.id}>
	                                  <Link
	                                    href={`/reservations/${item.id}`}
	                                    className="block w-full rounded-xl border border-brand-gold/20 bg-black/30 p-4 text-left transition hover:border-brand-gold/55 hover:bg-brand-gold/10"
	                                  >
	                                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
	                                      <div>
		                                        <p className="flex flex-wrap items-center gap-2 text-sm text-brand-cream/70">
		                                          <span
		                                            className={[
		                                              "rounded-full border px-2 py-0.5 text-[11px] font-medium",
		                                              roomChipStyle(roomCode),
		                                            ].join(" ")}
		                                            title={roomCode ? `Soba ${roomCode}` : "Bez dodijeljene sobe"}
		                                          >
		                                            {roomCode || "—"}
		                                          </span>
		                                          <span className="font-mono">{item.external_id}</span>
		                                          <span>•</span>
		                                          <span className="truncate">{item.room_name}</span>
		                                        </p>
	                                        <p className="mt-1 flex flex-wrap items-center gap-2 text-base font-medium">
		                                          {flag && (
		                                            <span
		                                              aria-hidden="true"
		                                              className={[
		                                                flag,
		                                                "inline-block h-4 w-6 shrink-0 rounded-sm ring-1 ring-black/25",
		                                              ].join(" ")}
		                                              title={item.primary_guest_nationality_iso2}
		                                            />
		                                          )}
		                                          <span>
		                                            {item.primary_guest_name || "Bez glavnog gosta"} ({item.guests_count})
		                                          </span>
		                                        </p>
	                                        <p className="mt-1 text-sm text-brand-cream/70">
	                                          {item.check_in_date} → {item.check_out_date}
	                                        </p>
	                                      </div>
		                                      <div className="text-right">
		                                        <p className="font-mono text-xs text-brand-gold">{statusLabel[item.status]}</p>
		                                        <p className="mt-1 text-sm">
		                                          {item.total_amount ? `${item.total_amount} ${item.currency}` : "-"}
		                                        </p>
		                                      </div>
	                                    </div>
	                                  </Link>
	                                </li>
	                              );
	                            })}
	                          </ul>
	                        </details>
	                      );
	                    })}
	                  </div>
	                </details>
	              ))}
	            </div>
	          )}
	        </section>
      </section>
    </main>
  );
}
