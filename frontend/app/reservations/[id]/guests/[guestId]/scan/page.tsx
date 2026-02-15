"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

type MeResponse = {
  id: number;
  username: string;
};

type Guest = {
  id: number;
  first_name: string;
  last_name: string;
};

type Reservation = {
  id: number;
  external_id: string;
  room_name: string;
};

type BlinkIdResultCallback = (result: Record<string, unknown>) => void;
type BlinkIdErrorCallback = (error: unknown) => void;

type BlinkIdScannerInstance = {
  destroy: () => Promise<void> | void;
  addOnResultCallback: (callback: BlinkIdResultCallback) => void;
  addOnErrorCallback?: (callback: BlinkIdErrorCallback) => void;
};

function getCsrfTokenFromCookie(): string {
  return (
    document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1] || ""
  );
}

function mrzDateToIso(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  if (!/^\d{6}$/.test(value)) return "";
  const yy = Number(value.slice(0, 2));
  const mm = value.slice(2, 4);
  const dd = value.slice(4, 6);
  const year = yy <= 30 ? 2000 + yy : 1900 + yy;
  return `${year}-${mm}-${dd}`;
}

export default function GuestScanPage() {
  const params = useParams<{ id: string; guestId: string }>();
  const router = useRouter();

  const reservationId = params.id;
  const guestId = params.guestId;

  const [authReady, setAuthReady] = useState(false);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [reservation, setReservation] = useState<Reservation | null>(null);
  const [guest, setGuest] = useState<Guest | null>(null);
  const [loading, setLoading] = useState(true);

  const [scanLoading, setScanLoading] = useState(false);
  const [scanActive, setScanActive] = useState(false);
  const [scanOverlayOpen, setScanOverlayOpen] = useState(false);
  const [scanStatus, setScanStatus] = useState("");
  const [scanError, setScanError] = useState("");

  const scannerHostRef = useRef<HTMLDivElement | null>(null);
  const scannerInstanceRef = useRef<BlinkIdScannerInstance | null>(null);
  const resultHandledRef = useRef(false);

  const returnToGuestPage = useCallback(() => {
    router.replace(`/reservations/${reservationId}/guests/${guestId}`);
  }, [router, reservationId, guestId]);

  const cleanupScanner = useCallback(async () => {
    try {
      await scannerInstanceRef.current?.destroy?.();
    } catch {}
    scannerInstanceRef.current = null;
    setScanActive(false);
    setScanOverlayOpen(false);
  }, []);

  const waitForNextFrame = () =>
    new Promise<void>((resolve) => {
      // Make sure React commits DOM changes (overlay + scanner host) before initializing the SDK.
      setTimeout(() => requestAnimationFrame(() => resolve()), 0);
    });

  useEffect(() => {
    return () => {
      cleanupScanner();
    };
  }, [cleanupScanner]);

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
          router.replace(`/login?next=/reservations/${reservationId}/guests/${guestId}/scan`);
          return;
        }
        if (!response.ok) throw new Error("Auth error");
        const data = (await response.json()) as MeResponse;
        setMe(data);
        setAuthReady(true);
      } catch {
        if (controller.signal.aborted) return;
        router.replace(`/login?next=/reservations/${reservationId}/guests/${guestId}/scan`);
      }
    };

    checkAuth();
    return () => controller.abort();
  }, [router, reservationId, guestId]);

  useEffect(() => {
    if (!authReady) return;
    const controller = new AbortController();

    const loadData = async () => {
      setLoading(true);
      try {
        const [reservationResponse, guestResponse] = await Promise.all([
          fetch(`/api/reception/reservations/${reservationId}/`, {
            signal: controller.signal,
            credentials: "include",
            headers: { Accept: "application/json" },
          }),
          fetch(`/api/reception/reservations/${reservationId}/guests/${guestId}/`, {
            signal: controller.signal,
            credentials: "include",
            headers: { Accept: "application/json" },
          }),
        ]);
        if (!reservationResponse.ok || !guestResponse.ok) {
          throw new Error("Ne mogu učitati podatke.");
        }
        setReservation((await reservationResponse.json()) as Reservation);
        setGuest((await guestResponse.json()) as Guest);
      } catch {
        router.replace(`/reservations/${reservationId}/guests/${guestId}`);
      } finally {
        setLoading(false);
      }
    };

    loadData();
    return () => controller.abort();
  }, [authReady, reservationId, guestId, router]);

  const parseTextField = (value: unknown): string => {
    if (!value || typeof value !== "object") return "";
    const typed = value as Record<string, unknown>;
    const langs = ["latin", "cyrillic", "arabic", "greek"] as const;
    for (const lang of langs) {
      const langValue = typed[lang] as Record<string, unknown> | undefined;
      if (langValue?.value && typeof langValue.value === "string") {
        return langValue.value.trim();
      }
    }
    if (typeof typed.value === "string") return typed.value.trim();
    return "";
  };

  const extractDeepValue = (source: unknown, keys: string[], maxDepth = 6): unknown => {
    if (maxDepth < 0 || source == null) return undefined;
    if (Array.isArray(source)) {
      for (const item of source) {
        const value = extractDeepValue(item, keys, maxDepth - 1);
        if (value !== undefined && value !== null) return value;
      }
      return undefined;
    }
    if (typeof source !== "object") return undefined;
    const record = source as Record<string, unknown>;
    for (const key of keys) {
      if (record[key] !== undefined && record[key] !== null) return record[key];
    }
    for (const nested of Object.values(record)) {
      const value = extractDeepValue(nested, keys, maxDepth - 1);
      if (value !== undefined && value !== null) return value;
    }
    return undefined;
  };

  const parseDatePartsToIso = (value: unknown): string => {
    if (!value || typeof value !== "object") return "";
    const typed = value as Record<string, unknown>;
    const year = Number(typed.year || 0);
    const month = Number(typed.month || 0);
    const day = Number(typed.day || 0);
    if (!year || !month || !day) return "";
    return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  };

  const buildSuggestedFieldsFromBlinkIdResult = (result: Record<string, unknown>) => {
    const toText = (value: unknown): string => {
      if (typeof value === "string") return value.trim();
      if (typeof value === "number") return String(value);
      return parseTextField(value);
    };

    const firstName = toText(extractDeepValue(result, ["firstName", "givenName"]));
    const lastName = toText(extractDeepValue(result, ["lastName", "surname", "familyName"]));
    const documentNumber = toText(
      extractDeepValue(result, ["documentNumber", "identityCardNumber", "idNumber", "personalIdNumber", "number"]),
    );
    const nationality = toText(extractDeepValue(result, ["isoAlpha2CountryCode", "nationality", "citizenship"]))
      .toUpperCase()
      .slice(0, 2);
    const dateOfBirth =
      parseDatePartsToIso(extractDeepValue(result, ["dateOfBirth", "birthDate"])) ||
      mrzDateToIso(toText(extractDeepValue(result, ["dateOfBirth", "birthDate"])));

    return {
      first_name: firstName,
      last_name: lastName,
      document_number: documentNumber,
      nationality: nationality,
      date_of_birth: dateOfBirth,
    };
  };

  const submitOcrToBackend = async (payload: Record<string, unknown>) => {
    await fetch("/api/auth/csrf/", { credentials: "include" });
    const csrfToken = getCsrfTokenFromCookie();

    const response = await fetch(`/api/reception/reservations/${reservationId}/guests/${guestId}/ocr/`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({
        provider: "microblink",
        raw_payload: payload,
        suggested_fields:
          (payload.suggested_fields as Record<string, unknown> | undefined) ||
          (payload.suggestedFields as Record<string, unknown> | undefined) ||
          {},
        duration_ms:
          (payload.duration_ms as number | undefined) ||
          (payload.durationMs as number | undefined) ||
          null,
      }),
    });

    const data = (await response.json().catch(() => ({}))) as {
      ocr_status?: "ok" | "failed";
      error?: string;
      detail?: string;
    };

    if (!response.ok || data.ocr_status !== "ok") {
      throw new Error(data.error || data.detail || "OCR nije uspješno spremljen.");
    }
  };

  const startScan = async () => {
    setScanLoading(true);
    setScanError("");
    setScanStatus("Učitavanje BlinkID...");
    resultHandledRef.current = false;

    try {
      await cleanupScanner();
      setScanOverlayOpen(true);
      await waitForNextFrame();

      const { createBlinkId } = await import("@microblink/blinkid");

      const licenseKey = (process.env.NEXT_PUBLIC_MICROBLINK_LICENSE_KEY || "").trim();
      if (!licenseKey) throw new Error("Nedostaje NEXT_PUBLIC_MICROBLINK_LICENSE_KEY.");
      if (!scannerHostRef.current) throw new Error("Scanner host nije inicijaliziran.");

      const configuredResources = (process.env.NEXT_PUBLIC_MICROBLINK_RESOURCES || "").trim() || "/resources";
      const resourcesLocation = new URL(configuredResources, window.location.origin).toString();

      const scanner = (await createBlinkId({
        targetNode: scannerHostRef.current,
        licenseKey,
        resourcesLocation,
        scanningMode: "automatic",
      })) as BlinkIdScannerInstance;

      scannerInstanceRef.current = scanner;
      setScanActive(true);
      setScanStatus("Skeniranje aktivno. Prikaži prednju pa zadnju stranu dokumenta.");

      scanner.addOnResultCallback(async (result: Record<string, unknown>) => {
        if (resultHandledRef.current) return;
        resultHandledRef.current = true;

        const rawResult = JSON.parse(JSON.stringify(result)) as Record<string, unknown>;
        const suggestedFields = buildSuggestedFieldsFromBlinkIdResult(rawResult);
        const payload = {
          raw_payload: rawResult,
          suggested_fields: suggestedFields,
          duration_ms: null,
        };

        setScanStatus("Dokument očitan. Spremam u backend...");
        await submitOcrToBackend(payload);
        setScanStatus("Spremljeno. Povratak na detalje gosta...");
        await cleanupScanner();
        returnToGuestPage();
      });

      scanner.addOnErrorCallback?.((errorInfo: unknown) => {
        if (resultHandledRef.current) return;
        setScanError(
          errorInfo instanceof Error
            ? errorInfo.message
            : "Greška tijekom skeniranja. Provjeri dozvolu kamere i licencu.",
        );
      });
    } catch (errorScan) {
      setScanError(errorScan instanceof Error ? errorScan.message : "Greška prilikom skeniranja.");
      setScanStatus("");
      setScanOverlayOpen(false);
    } finally {
      setScanLoading(false);
    }
  };

  return (
    <main className="relative min-h-screen min-h-[100dvh] overflow-x-hidden bg-brand-ink pb-24 text-brand-cream">
      <div className="pointer-events-none absolute inset-0 brand-grid opacity-30" />
      <div className="mx-auto w-full max-w-3xl px-5 py-8 sm:px-8">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/reservations/${reservationId}/guests/${guestId}`}
            className="inline-flex items-center rounded-full border border-brand-gold/40 bg-brand-gold/15 px-4 py-2 text-sm hover:bg-brand-gold/25"
          >
            Natrag na gosta
          </Link>
          <div className="rounded-full border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm">
            {me ? `Korisnik: ${me.username}` : "Provjera prijave..."}
          </div>
        </div>

        <section className="mt-4 rounded-2xl border border-brand-gold/30 bg-black/35 p-5 backdrop-blur-sm sm:p-7">
          {loading && <p>Učitavanje podataka...</p>}
          {!loading && (
            <>
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Skeniranje dokumenta</p>
              <h1 className="mt-2 text-2xl font-semibold">
                {guest ? `${guest.first_name} ${guest.last_name}` : `Gost #${guestId}`}
              </h1>
              <p className="mt-1 text-sm text-brand-cream/70">
                {reservation ? `${reservation.external_id} • ${reservation.room_name}` : `Rezervacija #${reservationId}`}
              </p>

              <div className="mt-4 rounded-xl border border-brand-gold/30 bg-black/40 p-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={startScan}
                    disabled={scanLoading || scanActive}
                    className="rounded-xl border border-brand-gold/40 bg-brand-gold/20 px-4 py-2 text-sm font-medium disabled:opacity-50"
                  >
                    {scanLoading ? "Pokrećem skener..." : "Pokreni skeniranje"}
                  </button>
                  <button
                    type="button"
                    onClick={cleanupScanner}
                    disabled={!scanActive}
                    className="rounded-xl border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm disabled:opacity-50"
                  >
                    Zaustavi
                  </button>
                </div>

                {scanStatus && <p className="mt-3 text-sm text-brand-gold">{scanStatus}</p>}
                {scanError && <p className="mt-3 text-sm text-red-300">{scanError}</p>}
                <p className="mt-3 text-xs text-brand-cream/70">
                  Na iPhoneu skener se otvara preko cijelog ekrana (da se ne reže gumb za pokretanje).
                </p>

              </div>
            </>
          )}
        </section>
      </div>

      {scanOverlayOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/95 text-brand-cream"
          role="dialog"
          aria-modal="true"
        >
          <div className="flex h-[100dvh] flex-col pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
            <div className="flex items-center justify-between gap-3 border-b border-brand-gold/20 bg-black/70 px-4 py-3 backdrop-blur-sm">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {guest ? `${guest.first_name} ${guest.last_name}` : `Gost #${guestId}`}
                </p>
                <p className="truncate text-xs text-brand-cream/70">Microblink skener</p>
              </div>
              <button
                type="button"
                onClick={cleanupScanner}
                className="shrink-0 rounded-xl border border-brand-gold/40 bg-black/40 px-3 py-2 text-sm"
              >
                Zatvori
              </button>
            </div>

            <div className="flex-1">
              <div
                ref={scannerHostRef}
                className="h-full w-full overflow-hidden bg-black"
              />
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
