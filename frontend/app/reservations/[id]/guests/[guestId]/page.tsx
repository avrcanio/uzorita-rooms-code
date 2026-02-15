"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type TouchEvent } from "react";

type ReservationStatus = "expected" | "checked_in" | "checked_out" | "canceled";

type Guest = {
  id: number;
  reservation: number;
  first_name: string;
  last_name: string;
  email?: string;
  date_of_birth: string | null;
  sex?: string;
  address?: string;
  date_of_issue?: string | null;
  date_of_expiry?: string | null;
  issuing_authority?: string;
  personal_id_number?: string;
  document_additional_number?: string;
  additional_personal_id_number?: string;
  document_code?: string;
  document_type?: string;
  document_country?: string;
  document_country_iso2?: string;
  document_country_iso3?: string;
  document_country_numeric?: string;
  mrz_raw_text?: string;
  mrz_verified?: boolean | null;
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
};

type MeResponse = {
  id: number;
  username: string;
};

type WizardForm = {
  first_name: string;
  last_name: string;
  email: string;
  date_of_birth: string;
  nationality: string;
  document_number: string;
  sex: string;
  address: string;
  date_of_issue: string;
  date_of_expiry: string;
  issuing_authority: string;
  personal_id_number: string;
  document_additional_number: string;
  additional_personal_id_number: string;
  document_code: string;
  document_type: string;
  document_country: string;
  document_country_iso2: string;
  document_country_iso3: string;
  document_country_numeric: string;
  mrz_raw_text: string;
  mrz_verified: boolean | null;
  is_primary: boolean;
};

function getCsrfTokenFromCookie(): string {
  return (
    document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1] || ""
  );
}

export default function GuestDetailsPage() {
  const params = useParams<{ id: string; guestId: string }>();
  const router = useRouter();

  const reservationId = params.id;
  const guestId = params.guestId;

  const [me, setMe] = useState<MeResponse | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const [reservation, setReservation] = useState<Reservation | null>(null);
  const [guest, setGuest] = useState<Guest | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState<WizardForm>({
    first_name: "",
    last_name: "",
    email: "",
    date_of_birth: "",
    nationality: "",
    document_number: "",
    sex: "",
    address: "",
    date_of_issue: "",
    date_of_expiry: "",
    issuing_authority: "",
    personal_id_number: "",
    document_additional_number: "",
    additional_personal_id_number: "",
    document_code: "",
    document_type: "",
    document_country: "",
    document_country_iso2: "",
    document_country_iso3: "",
    document_country_numeric: "",
    mrz_raw_text: "",
    mrz_verified: null,
    is_primary: false,
  });

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
          router.replace(`/login?next=/reservations/${reservationId}/guests/${guestId}`);
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
        router.replace(`/login?next=/reservations/${reservationId}/guests/${guestId}`);
      }
    };

    checkAuth();
    return () => controller.abort();
  }, [router, reservationId, guestId]);

  const loadData = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError("");

      try {
        const [reservationResponse, guestResponse] = await Promise.all([
          fetch(`/api/reception/reservations/${reservationId}/`, {
            signal,
            credentials: "include",
            headers: { Accept: "application/json" },
          }),
          fetch(`/api/reception/reservations/${reservationId}/guests/${guestId}/`, {
            signal,
            credentials: "include",
            headers: { Accept: "application/json" },
          }),
        ]);

        if (
          reservationResponse.status === 401 ||
          reservationResponse.status === 403 ||
          guestResponse.status === 401 ||
          guestResponse.status === 403
        ) {
          router.replace(`/login?next=/reservations/${reservationId}/guests/${guestId}`);
          return;
        }

        if (!reservationResponse.ok || !guestResponse.ok) {
          throw new Error("Ne mogu učitati podatke gosta.");
        }

        const reservationData = (await reservationResponse.json()) as Reservation;
        const guestData = (await guestResponse.json()) as Guest;

        setReservation(reservationData);
        setGuest(guestData);

        setForm({
          first_name: guestData.first_name || "",
          last_name: guestData.last_name || "",
          email: guestData.email || "",
          date_of_birth: guestData.date_of_birth || "",
          nationality: guestData.nationality || "",
          document_number: guestData.document_number || "",
          sex: guestData.sex || "",
          address: guestData.address || "",
          date_of_issue: guestData.date_of_issue || "",
          date_of_expiry: guestData.date_of_expiry || "",
          issuing_authority: guestData.issuing_authority || "",
          personal_id_number: guestData.personal_id_number || "",
          document_additional_number: guestData.document_additional_number || "",
          additional_personal_id_number: guestData.additional_personal_id_number || "",
          document_code: guestData.document_code || "",
          document_type: guestData.document_type || "",
          document_country: guestData.document_country || "",
          document_country_iso2: guestData.document_country_iso2 || "",
          document_country_iso3: guestData.document_country_iso3 || "",
          document_country_numeric: guestData.document_country_numeric || "",
          mrz_raw_text: guestData.mrz_raw_text || "",
          mrz_verified:
            typeof guestData.mrz_verified === "boolean" ? guestData.mrz_verified : null,
          is_primary: Boolean(guestData.is_primary),
        });
      } catch (fetchError) {
        if (signal.aborted) return;
        setError(fetchError instanceof Error ? fetchError.message : "Greška pri učitavanju gosta.");
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [reservationId, guestId, router],
  );

  useEffect(() => {
    if (!authReady) return;
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, [authReady, loadData]);

  const handleBack = useCallback(() => {
    router.push(`/reservations/${reservationId}`);
  }, [router, reservationId]);

  const handleRefresh = () => {
    const controller = new AbortController();
    loadData(controller.signal);
  };

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
      router.replace(`/login?next=/reservations/${reservationId}/guests/${guestId}`);
    }
  };

  const saveGuestData = async (payload: WizardForm, successMessage = "Podaci gosta su spremljeni.") => {
    setSaving(true);
    setSaveError("");
    setSaveMessage("");

    try {
      await fetch("/api/auth/csrf/", { credentials: "include" });
      const csrfToken = getCsrfTokenFromCookie();

      const response = await fetch(`/api/reception/reservations/${reservationId}/guests/${guestId}/`, {
        method: "PATCH",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
          Accept: "application/json",
        },
        body: JSON.stringify({
          ...payload,
          email: payload.email.trim(),
          date_of_birth: payload.date_of_birth || null,
          date_of_issue: payload.date_of_issue || null,
          date_of_expiry: payload.date_of_expiry || null,
          nationality: payload.nationality.trim().toUpperCase(),
          document_country_iso2: payload.document_country_iso2.trim().toUpperCase(),
          document_country_iso3: payload.document_country_iso3.trim().toUpperCase(),
        }),
      });

      if (response.status === 401 || response.status === 403) {
        router.replace(`/login?next=/reservations/${reservationId}/guests/${guestId}`);
        return;
      }

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(data.detail || `Spremanje nije uspjelo (${response.status})`);
      }

      const updatedGuest = (await response.json()) as Guest;
      setGuest(updatedGuest);
      setForm({
        first_name: updatedGuest.first_name || "",
        last_name: updatedGuest.last_name || "",
        email: updatedGuest.email || "",
        date_of_birth: updatedGuest.date_of_birth || "",
        nationality: updatedGuest.nationality || "",
        document_number: updatedGuest.document_number || "",
        sex: updatedGuest.sex || "",
        address: updatedGuest.address || "",
        date_of_issue: updatedGuest.date_of_issue || "",
        date_of_expiry: updatedGuest.date_of_expiry || "",
        issuing_authority: updatedGuest.issuing_authority || "",
        personal_id_number: updatedGuest.personal_id_number || "",
        document_additional_number: updatedGuest.document_additional_number || "",
        additional_personal_id_number: updatedGuest.additional_personal_id_number || "",
        document_code: updatedGuest.document_code || "",
        document_type: updatedGuest.document_type || "",
        document_country: updatedGuest.document_country || "",
        document_country_iso2: updatedGuest.document_country_iso2 || "",
        document_country_iso3: updatedGuest.document_country_iso3 || "",
        document_country_numeric: updatedGuest.document_country_numeric || "",
        mrz_raw_text: updatedGuest.mrz_raw_text || "",
        mrz_verified:
          typeof updatedGuest.mrz_verified === "boolean" ? updatedGuest.mrz_verified : null,
        is_primary: Boolean(updatedGuest.is_primary),
      });
      setSaveMessage(successMessage);
    } catch (saveErr) {
      setSaveError(saveErr instanceof Error ? saveErr.message : "Spremanje nije uspjelo.");
    } finally {
      setSaving(false);
    }
  };

  const saveGuest = async () => {
    await saveGuestData({
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      email: form.email.trim(),
      date_of_birth: form.date_of_birth || "",
      nationality: form.nationality.trim().toUpperCase(),
      document_number: form.document_number.trim(),
      sex: form.sex.trim(),
      address: form.address,
      date_of_issue: form.date_of_issue || "",
      date_of_expiry: form.date_of_expiry || "",
      issuing_authority: form.issuing_authority.trim(),
      personal_id_number: form.personal_id_number.trim(),
      document_additional_number: form.document_additional_number.trim(),
      additional_personal_id_number: form.additional_personal_id_number.trim(),
      document_code: form.document_code.trim().toUpperCase(),
      document_type: form.document_type.trim(),
      document_country: form.document_country.trim(),
      document_country_iso2: form.document_country_iso2.trim().toUpperCase(),
      document_country_iso3: form.document_country_iso3.trim().toUpperCase(),
      document_country_numeric: form.document_country_numeric.trim(),
      mrz_raw_text: form.mrz_raw_text,
      mrz_verified: form.mrz_verified,
      is_primary: form.is_primary,
    });
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
            href={`/reservations/${reservationId}`}
            className="inline-flex items-center rounded-full border border-brand-gold/40 bg-brand-gold/15 px-4 py-2 text-sm hover:bg-brand-gold/25"
          >
            Natrag na rezervaciju
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
          {authReady && loading && <p>Učitavanje podataka gosta...</p>}
          {error && <p className="text-red-300">Greška: {error}</p>}

          {!loading && !error && guest && (
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Detalji gosta</p>
              <h1 className="mt-2 text-2xl font-semibold">
                {guest.first_name} {guest.last_name}
              </h1>
              <p className="mt-1 text-sm text-brand-cream/70">
                {reservation ? `${reservation.external_id} • ${reservation.room_name}` : `Rezervacija #${reservationId}`}
              </p>
              <div className="mt-3">
                <Link
                  href={`/reservations/${reservationId}/guests/${guestId}/scan`}
                  className="inline-flex items-center rounded-xl border border-brand-gold/40 bg-brand-gold/20 px-4 py-2 text-sm font-medium hover:bg-brand-gold/30"
                >
                  Skeniraj dokument
                </Link>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <input
                  value={form.first_name}
                  onChange={(event) => setForm((prev) => ({ ...prev, first_name: event.target.value }))}
                  placeholder="Ime"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.last_name}
                  onChange={(event) => setForm((prev) => ({ ...prev, last_name: event.target.value }))}
                  placeholder="Prezime"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.email}
                  type="email"
                  inputMode="email"
                  onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                  placeholder="Email"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold sm:col-span-2"
                />
                <input
                  value={form.date_of_birth}
                  type="date"
                  onChange={(event) => setForm((prev) => ({ ...prev, date_of_birth: event.target.value }))}
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.nationality}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, nationality: event.target.value.toUpperCase() }))
                  }
                  placeholder="Državljanstvo (npr. HR)"
                  maxLength={2}
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm uppercase outline-none focus:border-brand-gold"
                />
                <input
                  value={form.document_number}
                  onChange={(event) => setForm((prev) => ({ ...prev, document_number: event.target.value }))}
                  placeholder="Broj dokumenta"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.personal_id_number}
                  onChange={(event) => setForm((prev) => ({ ...prev, personal_id_number: event.target.value }))}
                  placeholder="OIB / Personal ID"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.sex}
                  onChange={(event) => setForm((prev) => ({ ...prev, sex: event.target.value }))}
                  placeholder="Spol"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.issuing_authority}
                  onChange={(event) => setForm((prev) => ({ ...prev, issuing_authority: event.target.value }))}
                  placeholder="Izdavatelj dokumenta"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.date_of_issue}
                  type="date"
                  onChange={(event) => setForm((prev) => ({ ...prev, date_of_issue: event.target.value }))}
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.date_of_expiry}
                  type="date"
                  onChange={(event) => setForm((prev) => ({ ...prev, date_of_expiry: event.target.value }))}
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.document_additional_number}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, document_additional_number: event.target.value }))
                  }
                  placeholder="Dodatni broj dokumenta"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.additional_personal_id_number}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, additional_personal_id_number: event.target.value }))
                  }
                  placeholder="Dodatni osobni broj"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.document_code}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, document_code: event.target.value.toUpperCase() }))
                  }
                  placeholder="Kod dokumenta (npr. IO)"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm uppercase outline-none focus:border-brand-gold"
                />
                <input
                  value={form.document_type}
                  onChange={(event) => setForm((prev) => ({ ...prev, document_type: event.target.value }))}
                  placeholder="Tip dokumenta"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.document_country}
                  onChange={(event) => setForm((prev) => ({ ...prev, document_country: event.target.value }))}
                  placeholder="Država dokumenta"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <input
                  value={form.document_country_iso2}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, document_country_iso2: event.target.value.toUpperCase() }))
                  }
                  placeholder="ISO2 (npr. HR)"
                  maxLength={2}
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm uppercase outline-none focus:border-brand-gold"
                />
                <input
                  value={form.document_country_iso3}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, document_country_iso3: event.target.value.toUpperCase() }))
                  }
                  placeholder="ISO3 (npr. HRV)"
                  maxLength={3}
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm uppercase outline-none focus:border-brand-gold"
                />
                <input
                  value={form.document_country_numeric}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, document_country_numeric: event.target.value }))
                  }
                  placeholder="ISO numeric"
                  className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
                />
                <label className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm sm:col-span-2">
                  <span className="mb-2 block text-brand-cream/80">Adresa</span>
                  <textarea
                    value={form.address}
                    onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))}
                    rows={3}
                    className="w-full rounded-lg border border-brand-gold/30 bg-black/50 px-3 py-2 text-sm outline-none focus:border-brand-gold"
                  />
                </label>
                <label className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm sm:col-span-2">
                  <span className="mb-2 block text-brand-cream/80">MRZ verified</span>
                  <select
                    value={
                      form.mrz_verified === null
                        ? "unknown"
                        : form.mrz_verified
                          ? "true"
                          : "false"
                    }
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        mrz_verified:
                          event.target.value === "unknown"
                            ? null
                            : event.target.value === "true",
                      }))
                    }
                    className="w-full rounded-lg border border-brand-gold/30 bg-black/50 px-3 py-2 text-sm outline-none focus:border-brand-gold"
                  >
                    <option value="unknown">Nepoznato</option>
                    <option value="true">Da</option>
                    <option value="false">Ne</option>
                  </select>
                </label>
                <label className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm sm:col-span-2">
                  <span className="mb-2 block text-brand-cream/80">MRZ sirovi tekst</span>
                  <textarea
                    value={form.mrz_raw_text}
                    onChange={(event) => setForm((prev) => ({ ...prev, mrz_raw_text: event.target.value }))}
                    rows={4}
                    className="w-full rounded-lg border border-brand-gold/30 bg-black/50 px-3 py-2 text-sm outline-none focus:border-brand-gold"
                  />
                </label>
                <label className="flex items-center gap-2 rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm sm:col-span-2">
                  <input
                    type="checkbox"
                    checked={form.is_primary}
                    onChange={(event) => setForm((prev) => ({ ...prev, is_primary: event.target.checked }))}
                  />
                  Postavi kao glavnog gosta
                </label>
              </div>

              {saveError && <p className="mt-4 text-red-300">{saveError}</p>}
              {saveMessage && <p className="mt-4 text-green-300">{saveMessage}</p>}

              <div className="mt-5 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleBack}
                  disabled={saving}
                  className="rounded-xl border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm disabled:opacity-50"
                >
                  Natrag
                </button>
                <button
                  type="button"
                  onClick={saveGuest}
                  disabled={saving}
                  className="rounded-xl border border-brand-gold/40 bg-brand-gold/20 px-4 py-2 text-sm font-medium disabled:opacity-50"
                >
                  {saving ? "Spremam..." : "Spremi podatke"}
                </button>
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
