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
  check_in_date: string;
  check_out_date: string;
  status: ReservationStatus;
  total_amount: string | null;
  currency: string;
  guests_count: number;
  primary_guest_name: string;
};

type MeResponse = {
  id: number;
  username: string;
  email: string;
  is_superuser: boolean;
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

export default function Home() {
  const router = useRouter();

  const [me, setMe] = useState<MeResponse | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");

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
  const summary = useMemo(() => {
    const arrivalsToday = reservations.filter((item) => item.check_in_date === today).length;
    const departuresToday = reservations.filter((item) => item.check_out_date === today).length;
    const checkedInCount = reservations.filter((item) => item.status === "checked_in").length;
    return { arrivalsToday, departuresToday, checkedInCount };
  }, [reservations, today]);

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
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Današnji pregled</p>
            
            

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-brand-gold/25 bg-brand-gold/10 p-4">
                <p className="text-sm text-brand-cream/80">Dolasci danas</p>
                <p className="mt-2 text-3xl font-semibold">{summary.arrivalsToday}</p>
              </div>
              <div className="rounded-xl border border-brand-gold/25 bg-brand-gold/10 p-4">
                <p className="text-sm text-brand-cream/80">Odlasci danas</p>
                <p className="mt-2 text-3xl font-semibold">{summary.departuresToday}</p>
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
            <span className="text-sm text-brand-cream/70">Ukupno: {reservations.length}</span>
          </div>

          {!authReady && <p className="mt-4 text-brand-cream/80">Provjera autentifikacije...</p>}
          {authReady && loading && <p className="mt-4 text-brand-cream/80">Učitavanje podataka...</p>}
          {error && <p className="mt-4 text-red-300">Greška: {error}</p>}
          {!loading && !error && reservations.length === 0 && (
            <p className="mt-4 text-brand-cream/80">Nema rezultata za zadane filtere.</p>
          )}

          {!loading && !error && reservations.length > 0 && (
            <ul className="mt-4 space-y-3">
              {reservations.map((item) => (
                <li key={item.id}>
                  <Link
                    href={`/reservations/${item.id}`}
                    className="block w-full rounded-xl border border-brand-gold/20 bg-black/30 p-4 text-left transition hover:border-brand-gold/55 hover:bg-brand-gold/10"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-sm text-brand-cream/70">
                          {item.external_id} • {item.room_name}
                        </p>
                        <p className="mt-1 text-base font-medium">
                          {item.primary_guest_name || "Bez glavnog gosta"} ({item.guests_count})
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
              ))}
            </ul>
          )}
        </section>
      </section>
    </main>
  );
}
