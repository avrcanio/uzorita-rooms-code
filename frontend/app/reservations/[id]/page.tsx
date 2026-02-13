"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type TouchEvent } from "react";

type ReservationStatus = "expected" | "checked_in" | "checked_out" | "canceled";

type Guest = {
  id: number;
  first_name: string;
  last_name: string;
  is_primary: boolean;
  nationality?: string;
  document_number?: string;
};

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
  guests: Guest[];
};

type MeResponse = {
  id: number;
  username: string;
};

const statusLabel: Record<ReservationStatus, string> = {
  expected: "Očekuje dolazak",
  checked_in: "Prijavljen",
  checked_out: "Odjavljen",
  canceled: "Otkazan",
};

export default function ReservationDetailsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [me, setMe] = useState<MeResponse | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const [reservation, setReservation] = useState<Reservation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [touchStartY, setTouchStartY] = useState<number | null>(null);

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
          router.replace(`/login?next=/reservations/${id}`);
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
        router.replace(`/login?next=/reservations/${id}`);
      }
    };

    checkAuth();
    return () => controller.abort();
  }, [router, id]);

  const handleBack = useCallback(() => {
    if (window.history.length > 1) {
      router.back();
      return;
    }
    router.push("/");
  }, [router]);

  const loadReservation = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`/api/reception/reservations/${id}/`, {
          signal,
          credentials: "include",
          headers: { Accept: "application/json" },
        });

        if (response.status === 401 || response.status === 403) {
          router.replace(`/login?next=/reservations/${id}`);
          return;
        }

        if (!response.ok) {
          throw new Error(`Detalj API greška (${response.status})`);
        }

        const data = (await response.json()) as Reservation;
        setReservation(data);
      } catch (fetchError) {
        if (signal.aborted) return;
        setError(fetchError instanceof Error ? fetchError.message : "Greška pri učitavanju detalja.");
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [id, router],
  );

  useEffect(() => {
    if (!authReady) return;
    const controller = new AbortController();
    loadReservation(controller.signal);
    return () => controller.abort();
  }, [authReady, loadReservation]);

  const handleRefresh = () => {
    const controller = new AbortController();
    loadReservation(controller.signal);
  };

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
      router.replace(`/login?next=/reservations/${id}`);
    }
  };

  const onTouchStart = (event: TouchEvent<HTMLElement>) => {
    const touch = event.changedTouches[0];
    setTouchStartX(touch.clientX);
    setTouchStartY(touch.clientY);
  };

  const onTouchEnd = (event: TouchEvent<HTMLElement>) => {
    if (touchStartX === null || touchStartY === null) return;

    const touch = event.changedTouches[0];
    const deltaX = touch.clientX - touchStartX;
    const deltaY = Math.abs(touch.clientY - touchStartY);

    const isLeftEdgeGesture = touchStartX <= 40;
    if (isLeftEdgeGesture && deltaX > 90 && deltaY < 60) {
      handleBack();
    }

    setTouchStartX(null);
    setTouchStartY(null);
  };

  return (
    <main
      className="relative min-h-screen overflow-hidden bg-brand-ink pb-24 text-brand-cream sm:pb-0"
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      <div className="pointer-events-none absolute inset-0 brand-grid opacity-30" />
      <div className="mx-auto w-full max-w-4xl px-5 py-8 sm:px-8 lg:px-10">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/"
            className="inline-flex items-center rounded-full border border-brand-gold/40 bg-brand-gold/15 px-4 py-2 text-sm hover:bg-brand-gold/25"
          >
            Natrag na timeline
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

        <section className="mt-4 rounded-2xl border border-brand-gold/30 bg-black/35 p-5 backdrop-blur-sm sm:p-7">
          {!authReady && <p>Provjera autentifikacije...</p>}
          {authReady && loading && <p>Učitavanje detalja...</p>}
          {error && <p className="text-red-300">Greška: {error}</p>}

          {!loading && !error && reservation && (
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Detalj rezervacije</p>
              <h1 className="mt-2 text-2xl font-semibold">{reservation.external_id}</h1>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-brand-gold/20 bg-black/30 p-4">
                  <p className="text-sm text-brand-cream/70">Soba</p>
                  <p className="mt-1 font-medium">{reservation.room_name}</p>
                </div>
                <div className="rounded-xl border border-brand-gold/20 bg-black/30 p-4">
                  <p className="text-sm text-brand-cream/70">Status</p>
                  <p className="mt-1 font-medium">{statusLabel[reservation.status]}</p>
                </div>
                <div className="rounded-xl border border-brand-gold/20 bg-black/30 p-4">
                  <p className="text-sm text-brand-cream/70">Check-in</p>
                  <p className="mt-1 font-medium">{reservation.check_in_date}</p>
                </div>
                <div className="rounded-xl border border-brand-gold/20 bg-black/30 p-4">
                  <p className="text-sm text-brand-cream/70">Check-out</p>
                  <p className="mt-1 font-medium">{reservation.check_out_date}</p>
                </div>
                <div className="rounded-xl border border-brand-gold/20 bg-black/30 p-4 sm:col-span-2">
                  <p className="text-sm text-brand-cream/70">Iznos</p>
                  <p className="mt-1 font-medium">
                    {reservation.total_amount ? `${reservation.total_amount} ${reservation.currency}` : "-"}
                  </p>
                </div>
              </div>

              <div className="mt-5">
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">
                  Gosti ({reservation.guests_count})
                </p>
                <ul className="mt-3 space-y-2">
                  {reservation.guests.map((guest) => (
                    <li key={guest.id}>
                      <Link
                        href={`/reservations/${reservation.id}/guests/${guest.id}`}
                        className="block rounded-xl border border-brand-gold/20 bg-black/30 p-4 transition hover:border-brand-gold/55 hover:bg-brand-gold/10"
                      >
                        <p className="font-medium">
                          {guest.first_name} {guest.last_name}
                        </p>
                        <p className="mt-1 text-sm text-brand-cream/70">
                          {guest.is_primary ? "Glavni gost" : "Prateći gost"}
                        </p>
                        <p className="mt-1 text-sm text-brand-cream/70">
                          {guest.nationality || "-"} • {guest.document_number || "-"}
                        </p>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </section>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-brand-gold/30 bg-black/80 p-3 backdrop-blur-sm sm:hidden">
        <div className="mx-auto flex max-w-4xl gap-3">
          <button
            type="button"
            onClick={handleBack}
            className="flex-1 rounded-xl border border-brand-gold/40 bg-brand-gold/15 px-4 py-3 text-sm font-medium"
          >
            Natrag
          </button>
          <button
            type="button"
            onClick={handleRefresh}
            className="flex-1 rounded-xl border border-brand-gold/40 bg-black/40 px-4 py-3 text-sm font-medium"
          >
            Osvježi
          </button>
        </div>
      </div>
    </main>
  );
}
