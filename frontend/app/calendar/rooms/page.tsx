"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

type MeResponse = {
  id: number;
  username: string;
};

type Room = {
  id: number;
  code: string;
  room_type: number;
  room_type_name: string;
  is_active: boolean;
};

type ReservationStatus = "expected" | "checked_in" | "checked_out" | "canceled";

type RoomReservation = {
  id: number;
  external_id: string;
  check_in_date: string;
  check_out_date: string;
  status: ReservationStatus;
  room_name: string;
  primary_guest_name: string;
  primary_guest_nationality_iso2: string;
};

function flagIconClass(iso2?: string | null): string | null {
  const cc = (iso2 || "").trim().toLowerCase();
  if (!/^[a-z]{2}$/.test(cc)) return null;
  return `fi fi-${cc}`;
}

function getCsrfTokenFromCookie(): string {
  return (
    document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1] || ""
  );
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, deltaDays: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + deltaDays);
  return d.toISOString().slice(0, 10);
}

function addMonthsIso(iso: string, deltaMonths: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + deltaMonths);
  return d.toISOString().slice(0, 10);
}

function startOfMonthIso(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(1);
  return d.toISOString().slice(0, 10);
}

function daysBetweenIso(startIso: string, endIso: string): number {
  const a = new Date(`${startIso}T00:00:00Z`).getTime();
  const b = new Date(`${endIso}T00:00:00Z`).getTime();
  return Math.round((b - a) / (24 * 60 * 60 * 1000));
}

function maxIso(a: string, b: string): string {
  return a >= b ? a : b;
}

function minIso(a: string, b: string): string {
  return a <= b ? a : b;
}

function weekdayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  // hr-HR short weekday comes without dot; keep it robust and strip punctuation anyway.
  return new Intl.DateTimeFormat("hr-HR", { weekday: "short" })
    .format(d)
    .replace(/[.,]/g, "")
    .trim();
}

function dayMonthLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  // Render "05 06." (day month + trailing dot).
  const raw = new Intl.DateTimeFormat("hr-HR", { day: "2-digit", month: "2-digit" }).format(d);
  const cleaned = raw.replace(/[.]/g, "").replace(/\s+/g, " ").trim();
  return `${cleaned}.`;
}

const statusStyle: Record<
  ReservationStatus,
  { label: string; className: string }
> = {
  expected: {
    label: "Očekuje",
    className: "border-brand-gold/40 bg-brand-gold/15 text-brand-cream",
  },
  checked_in: {
    label: "Prijavljen",
    className: "border-emerald-400/40 bg-emerald-400/15 text-emerald-50",
  },
  checked_out: {
    label: "Odjavljen",
    className: "border-sky-400/40 bg-sky-400/15 text-sky-50",
  },
  canceled: {
    label: "Otkazan",
    className: "border-red-400/40 bg-red-400/15 text-red-50",
  },
};

export default function RoomsCalendarPage() {
  const router = useRouter();

  const [me, setMe] = useState<MeResponse | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const [rooms, setRooms] = useState<Room[]>([]);
  const [calendarByRoom, setCalendarByRoom] = useState<Record<number, RoomReservation[]>>({});
  const [activeRoomId, setActiveRoomId] = useState<number | null>(null);

  const [dateFrom, setDateFrom] = useState(() => isoToday());
  const [dateTo, setDateTo] = useState(() => addDaysIso(isoToday(), 14));

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const lang = useMemo(() => (typeof document === "undefined" ? "en" : document.documentElement.lang || "en"), []);

  const [monthPickerOpen, setMonthPickerOpen] = useState(false);
  const [monthPickerYear, setMonthPickerYear] = useState<number>(() => new Date().getUTCFullYear());

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
          router.replace("/login?next=/calendar/rooms");
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
        router.replace("/login?next=/calendar/rooms");
      }
    };

    checkAuth();
    return () => controller.abort();
  }, [router]);

  const loadCalendar = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError("");

      try {
        const roomsResponse = await fetch(`/api/rooms/rooms/?lang=${encodeURIComponent(lang)}`, {
          signal,
          credentials: "include",
          headers: { Accept: "application/json" },
        });

        if (roomsResponse.status === 401 || roomsResponse.status === 403) {
          router.replace("/login?next=/calendar/rooms");
          return;
        }

        if (!roomsResponse.ok) {
          throw new Error(`Rooms API greška (${roomsResponse.status})`);
        }

        const roomsData = (await roomsResponse.json()) as Room[];
        setRooms(roomsData);

        const params = new URLSearchParams();
        if (dateFrom) params.set("from", dateFrom);
        if (dateTo) params.set("to", dateTo);
        const query = params.toString();

        const calendars = await Promise.all(
          roomsData.map(async (room) => {
            const response = await fetch(
              `/api/rooms/rooms/${room.id}/calendar/${query ? `?${query}` : ""}`,
              {
                signal,
                credentials: "include",
                headers: { Accept: "application/json" },
              },
            );

            if (!response.ok) {
              throw new Error(`Kalendar greška za sobu ${room.code} (${response.status})`);
            }

            const data = (await response.json()) as RoomReservation[];
            return [room.id, data] as const;
          }),
        );

        const mapped: Record<number, RoomReservation[]> = {};
        for (const [roomId, items] of calendars) mapped[roomId] = items;
        setCalendarByRoom(mapped);
      } catch (fetchError) {
        if (signal.aborted) return;
        setError(fetchError instanceof Error ? fetchError.message : "Greška pri učitavanju kalendara.");
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [router, dateFrom, dateTo, lang],
  );

  useEffect(() => {
    if (!authReady) return;
    const controller = new AbortController();
    loadCalendar(controller.signal);
    return () => controller.abort();
  }, [authReady, loadCalendar]);

  const refresh = () => {
    const controller = new AbortController();
    loadCalendar(controller.signal);
  };

  const monthLabel = useMemo(() => {
    if (!dateFrom) return "";
    const d = new Date(`${dateFrom}T00:00:00Z`);
    return new Intl.DateTimeFormat("hr-HR", { month: "long", year: "numeric" }).format(d);
  }, [dateFrom]);

  const openMonthPicker = () => {
    const d = dateFrom ? new Date(`${dateFrom}T00:00:00Z`) : new Date();
    setMonthPickerYear(d.getUTCFullYear());
    setMonthPickerOpen(true);
  };

  const goToMonth = (deltaMonths: number) => {
    if (!dateFrom) return;
    const nextStart = startOfMonthIso(addMonthsIso(dateFrom, deltaMonths));
    setDateFrom(nextStart);
    setDateTo(startOfMonthIso(addMonthsIso(nextStart, 1)));
  };

  const pickMonth = (monthIndex: number) => {
    const start = new Date(Date.UTC(monthPickerYear, monthIndex, 1)).toISOString().slice(0, 10);
    const nextStart = startOfMonthIso(start);
    setDateFrom(nextStart);
    setDateTo(startOfMonthIso(addMonthsIso(nextStart, 1)));
    setMonthPickerOpen(false);
  };

  const monthOptions = useMemo(() => {
    const fmt = new Intl.DateTimeFormat("hr-HR", { month: "long" });
    return Array.from({ length: 12 }, (_, idx) => {
      const label = fmt.format(new Date(Date.UTC(monthPickerYear, idx, 1)));
      return { idx, label: label.charAt(0).toUpperCase() + label.slice(1) };
    });
  }, [monthPickerYear]);

  useEffect(() => {
    if (!monthPickerOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMonthPickerOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [monthPickerOpen]);

  const logout = async () => {
    try {
      await fetch("/api/auth/csrf/", { credentials: "include" });
      const csrfToken = getCsrfTokenFromCookie();

      await fetch("/api/auth/logout/", {
        method: "POST",
        credentials: "include",
        headers: {
          "X-CSRFToken": csrfToken,
        },
      });
    } finally {
      router.replace("/login?next=/calendar/rooms");
    }
  };

  const days = useMemo(() => {
    if (!dateFrom || !dateTo) return [];
    const n = Math.max(0, daysBetweenIso(dateFrom, dateTo));
    return Array.from({ length: n }, (_, idx) => addDaysIso(dateFrom, idx));
  }, [dateFrom, dateTo]);

  const gridTemplateColumns = useMemo(() => {
    const dayCols = days.length;
    // 240px for room label + 64px per day.
    return `240px repeat(${dayCols}, 64px)`;
  }, [days.length]);

  const gridBackgroundStyle = useMemo(() => {
    // Draw day column separators without rendering 30+ extra DOM nodes per room row.
    // Keep in sync with gridTemplateColumns (240px label + 64px per day).
    const labelWidthPx = 240;
    const dayWidthPx = 64;
    return {
      backgroundImage: [
        // Day separators (1px at the end of each 64px column)
        "repeating-linear-gradient(to right, transparent 0, transparent 63px, rgba(212,175,55,0.10) 63px, rgba(212,175,55,0.10) 64px)",
        // Start of the day grid area (skip label column)
        "linear-gradient(to right, transparent, transparent)",
      ].join(","),
      backgroundPosition: `${labelWidthPx}px 0, 0 0`,
      backgroundSize: `${dayWidthPx}px 100%, 100% 100%`,
      backgroundRepeat: "repeat, no-repeat",
    } as const;
  }, []);

  const mobileGridTemplateColumns = useMemo(() => {
    return `repeat(${days.length}, 64px)`;
  }, [days.length]);

  const mobileGridBackgroundStyle = useMemo(() => {
    const dayWidthPx = 64;
    return {
      backgroundImage:
        "repeating-linear-gradient(to right, transparent 0px, transparent 63px, rgba(212,175,55,0.10) 63px, rgba(212,175,55,0.10) 64px)",
      backgroundPosition: "0 0",
      backgroundSize: `${dayWidthPx}px 100%`,
      backgroundRepeat: "repeat",
    } as const;
  }, []);

  useEffect(() => {
    if (!activeRoomId && rooms.length) setActiveRoomId(rooms[0].id);
  }, [activeRoomId, rooms]);

  const activeRoom = useMemo(() => {
    if (!activeRoomId) return null;
    return rooms.find((r) => r.id === activeRoomId) || null;
  }, [activeRoomId, rooms]);

  const mobileRooms = useMemo(() => {
    return rooms
      .map((room) => ({
        room,
        count: (calendarByRoom[room.id] || []).length,
      }))
      .filter((item) => item.count > 0);
  }, [rooms, calendarByRoom]);

  useEffect(() => {
    // Mobile UX: only show rooms with reservations in period; keep activeRoomId consistent.
    if (!mobileRooms.length) {
      setActiveRoomId(null);
      return;
    }
    if (!activeRoomId || !mobileRooms.some((x) => x.room.id === activeRoomId)) {
      setActiveRoomId(mobileRooms[0].room.id);
    }
  }, [activeRoomId, mobileRooms]);

  const activeItems = useMemo(() => {
    if (!activeRoomId) return [];
    return calendarByRoom[activeRoomId] || [];
  }, [activeRoomId, calendarByRoom]);

  const goRoom = (delta: number) => {
    if (!rooms.length) return;
    const idx = rooms.findIndex((r) => r.id === activeRoomId);
    const nextIdx = idx === -1 ? 0 : (idx + delta + rooms.length) % rooms.length;
    setActiveRoomId(rooms[nextIdx].id);
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-brand-ink pb-10 text-brand-cream">
      <div className="pointer-events-none absolute inset-0 brand-grid opacity-30" />
      <div className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:px-10">
        <header className="rounded-2xl border border-brand-gold/30 bg-black/35 p-5 backdrop-blur-sm sm:p-7">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.24em] text-brand-gold">Kalendar soba</p>
              <h1 className="text-2xl font-semibold leading-tight sm:text-3xl">Dodijeljene sobe po datumu</h1>
              <p className="mt-1 text-sm text-brand-cream/70">
                Interval je poluotvoren: od <span className="font-mono">{dateFrom}</span> do{" "}
                <span className="font-mono">{dateTo}</span>.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href="/"
                className="rounded-full border border-brand-gold/40 bg-brand-gold/15 px-4 py-2 text-sm hover:bg-brand-gold/25"
              >
                Timeline
              </Link>
              <div className="rounded-full border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm">
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

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-2">
                <span className="text-sm text-brand-cream/70">Od</span>
                <input
                  value={dateFrom}
                  type="date"
                  onChange={(event) => setDateFrom(event.target.value)}
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm text-brand-cream/70">Do</span>
                <input
                  value={dateTo}
                  type="date"
                  onChange={(event) => setDateTo(event.target.value)}
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
              </label>
            </div>

	            <div className="flex flex-wrap items-center gap-2">
	              <button
	                type="button"
	                onClick={() => goToMonth(-1)}
	                className="rounded-xl border border-brand-gold/40 bg-black/40 px-4 py-3 text-sm hover:bg-brand-gold/15"
	              >
	                Prethodni mjesec
	              </button>
	              <button
	                type="button"
	                onClick={openMonthPicker}
	                className="rounded-xl border border-brand-gold/25 bg-black/30 px-4 py-3 text-sm text-brand-cream/80 hover:bg-brand-gold/10"
	              >
	                {monthLabel}
	              </button>	              
	              <button
	                type="button"
	                onClick={() => goToMonth(1)}
	                className="rounded-xl border border-brand-gold/40 bg-black/40 px-4 py-3 text-sm hover:bg-brand-gold/15"
	              >
	                Sljedeći mjesec
	              </button>
                <button
	                type="button"
	                onClick={refresh}
	                className="rounded-xl border border-brand-gold/40 bg-black/40 px-4 py-3 text-sm hover:bg-brand-gold/15"
	              >
	                Osvježi
	              </button>
	            </div>
	          </div>
	        </header>

        {monthPickerOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-5 backdrop-blur-sm"
            onClick={() => setMonthPickerOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-label="Odabir mjeseca"
          >
            <div
              className="w-full max-w-lg rounded-2xl border border-brand-gold/25 bg-black/90 p-5 shadow-[0_30px_120px_rgba(0,0,0,0.55)]"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setMonthPickerYear((y) => y - 1)}
                  className="rounded-xl border border-brand-gold/40 bg-black/40 px-3 py-2 text-sm hover:bg-brand-gold/15"
                >
                  ←
                </button>
                <div className="text-center">
                  <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Godina</p>
                  <p className="mt-1 text-xl font-semibold text-brand-cream">{monthPickerYear}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setMonthPickerYear((y) => y + 1)}
                  className="rounded-xl border border-brand-gold/40 bg-black/40 px-3 py-2 text-sm hover:bg-brand-gold/15"
                >
                  →
                </button>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
                {monthOptions.map((m) => (
                  <button
                    key={m.idx}
                    type="button"
                    onClick={() => pickMonth(m.idx)}
                    className="rounded-xl border border-brand-gold/25 bg-black/40 px-4 py-3 text-sm text-brand-cream/90 hover:bg-brand-gold/10"
                  >
                    {m.label}
                  </button>
                ))}
              </div>

              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  onClick={() => setMonthPickerOpen(false)}
                  className="rounded-xl border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm hover:bg-brand-gold/15"
                >
                  Zatvori
                </button>
              </div>
            </div>
          </div>
        )}
	
	        <section className="mt-6 rounded-2xl border border-brand-gold/25 bg-black/35 p-5 backdrop-blur-sm sm:p-7">
	          {!authReady && <p className="text-brand-cream/80">Provjera autentifikacije...</p>}
	          {authReady && loading && <p className="text-brand-cream/80">Učitavanje kalendara...</p>}
          {error && <p className="text-red-300">Greška: {error}</p>}

          {!loading && !error && days.length === 0 && (
            <p className="text-brand-cream/80">Odaberi valjani raspon datuma (Do mora biti nakon Od).</p>
          )}

          {!loading && !error && days.length > 0 && (
            <div className="overflow-x-auto">
              <div className="min-w-max">
                {/* Mobile: show one room at a time with room header above the date strip */}
                <div className="sm:hidden">
                  <div className="sticky top-0 z-40 -mx-5 border-b border-brand-gold/25 bg-black/85 backdrop-blur-sm">
                    <div className="px-5 pt-3 pb-3">
                      <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Odabir sobe</p>
                      <div className="mt-2 grid gap-2">
                        {mobileRooms.length === 0 && (
                          <div className="rounded-xl border border-brand-gold/20 bg-black/40 px-4 py-3 text-sm text-brand-cream/70">
                            Nema rezervacija u odabranom periodu.
                          </div>
                        )}
                        {mobileRooms.map(({ room, count }) => {
                          const isActive = room.id === activeRoomId;
                          return (
                            <button
                              key={room.id}
                              type="button"
                              onClick={() => setActiveRoomId(room.id)}
                              className={[
                                "flex w-full items-start justify-between gap-3 rounded-xl border px-4 py-3 text-left",
                                isActive
                                  ? "border-brand-gold/45 bg-brand-gold/10"
                                  : "border-brand-gold/20 bg-black/40",
                              ].join(" ")}
                            >
                              <div className="min-w-0">
                                <div className="flex items-baseline gap-2">
                                  <span className="font-mono text-sm text-brand-cream">{room.code}</span>
                                  <span className="rounded-full border border-brand-gold/25 bg-black/30 px-2 py-0.5 text-[11px] text-brand-cream/70">
                                    {count} rez.
                                  </span>
                                </div>
                                <div className="mt-1 line-clamp-2 text-sm text-brand-cream/80">
                                  {room.room_type_name}
                                </div>
                              </div>
                              <span className="mt-0.5 text-sm text-brand-cream/60">{isActive ? "✓" : ""}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <div className="min-w-max px-5 pb-2">
                        <div className="grid items-stretch gap-0" style={{ gridTemplateColumns: mobileGridTemplateColumns }}>
                          {days.map((d) => (
                            <div key={d} className="px-2 text-center">
                              <span className="block text-[11px] text-brand-cream/70">{weekdayLabel(d)}</span>
                              <span className="block text-[11px] text-brand-cream/70">{dayMonthLabel(d)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 overflow-x-auto">
                    <div className="min-w-max">
                      <div
                        className="grid gap-0 rounded-xl border border-brand-gold/20 bg-black/30"
                        style={{ gridTemplateColumns: mobileGridTemplateColumns, ...mobileGridBackgroundStyle }}
                      >
                        {activeItems.map((res) => {
                          const clippedStart = maxIso(res.check_in_date, dateFrom);
                          const clippedEnd = minIso(res.check_out_date, dateTo);
                          const startIdx = Math.max(0, daysBetweenIso(dateFrom, clippedStart));
                          const endIdx = Math.max(0, daysBetweenIso(dateFrom, clippedEnd));

                          const colStart = 1 + startIdx;
                          const colEnd = 1 + endIdx;
                          if (colEnd <= colStart) return null;

                          const style = statusStyle[res.status] || statusStyle.expected;
                          const title = `${res.external_id}\n${res.primary_guest_name || "(no guest)"}\n${res.check_in_date} -> ${res.check_out_date}`;
                          const flag = flagIconClass(res.primary_guest_nationality_iso2);

                          return (
                            <Link
                              key={res.id}
                              href={`/reservations/${res.id}`}
                              title={title}
                              className={[
                                "relative z-20 mx-1 my-2 flex h-[48px] items-center justify-between gap-2 overflow-hidden rounded-lg border px-3 text-xs",
                                "shadow-[0_10px_40px_rgba(0,0,0,0.35)]",
                                style.className,
                              ].join(" ")}
                              style={{
                                gridColumnStart: colStart,
                                gridColumnEnd: colEnd,
                                gridRowStart: 1,
                                gridRowEnd: 2,
                                alignSelf: "center",
                              }}
                            >
                              <span className="truncate font-mono">{res.external_id}</span>
                              <span className="flex min-w-0 items-center justify-end gap-2">
                                {flag && (
                                  <span
                                    aria-hidden="true"
                                    className={[
                                      flag,
                                      "inline-block h-3.5 w-5 shrink-0 rounded-sm ring-1 ring-black/25",
                                    ].join(" ")}
                                    title={res.primary_guest_nationality_iso2}
                                  />
                                )}
                                <span className="truncate text-[11px] text-brand-cream/80">
                                  {res.primary_guest_name || style.label}
                                </span>
                              </span>
                            </Link>
                          );
                        })}
                        {activeItems.length === 0 && (
                          <div className="col-span-full px-4 py-4 text-sm text-brand-cream/70">
                            Nema rezervacija u odabranom periodu.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Desktop: multi-room grid */}
                <div className="hidden sm:block">
                  <div
                    className="grid items-stretch gap-0 border-b border-brand-gold/25 pb-2"
                    style={{ gridTemplateColumns }}
                  >
                    <div className="sticky left-0 z-10 flex items-end bg-black/35 pr-4">
                      <span className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Soba</span>
                    </div>
                    {days.map((d) => (
                      <div key={d} className="px-2 text-center">
                        <span className="block text-[11px] text-brand-cream/70">{weekdayLabel(d)}</span>
                        <span className="block text-[11px] text-brand-cream/70">{dayMonthLabel(d)}</span>
                      </div>
                    ))}
                  </div>

                  <div className="mt-3 grid gap-3">
                    {rooms.map((room) => {
                      const items = calendarByRoom[room.id] || [];

                      return (
                        <div
                          key={room.id}
                          className="grid gap-0 rounded-xl border border-brand-gold/20 bg-black/30"
                          style={{ gridTemplateColumns, ...gridBackgroundStyle }}
                        >
                          <div className="sticky left-0 z-10 flex flex-col justify-center gap-1 border-r border-brand-gold/20 bg-black/35 px-4 py-4">
                            <div className="flex items-baseline justify-between gap-2">
                              <span className="font-mono text-sm text-brand-cream">{room.code}</span>
                              <div className="flex items-center gap-2">
                                <span className="rounded-full border border-brand-gold/25 bg-black/30 px-2 py-0.5 text-[11px] text-brand-cream/70">
                                  {items.length} rez.
                                </span>
                                <span className="text-xs text-brand-cream/60">#{room.id}</span>
                              </div>
                            </div>
                            <div className="text-sm text-brand-cream/80">{room.room_type_name}</div>
                          </div>

                          {items.map((res) => {
                            const clippedStart = maxIso(res.check_in_date, dateFrom);
                            const clippedEnd = minIso(res.check_out_date, dateTo);
                            const startIdx = Math.max(0, daysBetweenIso(dateFrom, clippedStart));
                            const endIdx = Math.max(0, daysBetweenIso(dateFrom, clippedEnd));

                            const colStart = 2 + startIdx;
                            const colEnd = 2 + endIdx;
                            if (colEnd <= colStart) return null;

                            const style = statusStyle[res.status] || statusStyle.expected;
                            const title = `${res.external_id}\n${res.primary_guest_name || "(no guest)"}\n${res.check_in_date} -> ${res.check_out_date}`;
                            const flag = flagIconClass(res.primary_guest_nationality_iso2);

                            return (
                              <Link
                                key={res.id}
                                href={`/reservations/${res.id}`}
                                title={title}
                                className={[
                                  "relative z-20 mx-1 my-2 flex h-[48px] items-center justify-between gap-2 overflow-hidden rounded-lg border px-3 text-xs",
                                  "shadow-[0_10px_40px_rgba(0,0,0,0.35)]",
                                  style.className,
                                ].join(" ")}
                                style={{
                                  gridColumnStart: colStart,
                                  gridColumnEnd: colEnd,
                                  gridRowStart: 1,
                                  gridRowEnd: 2,
                                  alignSelf: "center",
                                }}
                              >
                                <span className="truncate font-mono">{res.external_id}</span>
                                <span className="flex min-w-0 items-center justify-end gap-2">
                                  {flag && (
                                    <span
                                      aria-hidden="true"
                                      className={[
                                        flag,
                                        "inline-block h-3.5 w-5 shrink-0 rounded-sm ring-1 ring-black/25",
                                      ].join(" ")}
                                      title={res.primary_guest_nationality_iso2}
                                    />
                                  )}
                                  <span className="truncate text-[11px] text-brand-cream/80">
                                    {res.primary_guest_name || style.label}
                                  </span>
                                </span>
                              </Link>
                            );
                          })}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
