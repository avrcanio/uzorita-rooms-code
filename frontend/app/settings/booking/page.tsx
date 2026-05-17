"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

type MeResponse = { id: number; username: string };

type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "needs_2fa"
  | "needs_human"
  | "connected"
  | "expired"
  | "error";

type ConnectionPayload = {
  status: ConnectionStatus;
  hotel_id: string;
  storage_version: number;
  last_ok_at: string | null;
  last_connect_at: string | null;
  last_error: string;
  enabled: boolean;
  connect_mode: string;
  has_session: boolean;
  auto_connect_allowed: boolean;
  auto_connect_message: string;
  vnc_start_allowed?: boolean;
  vnc_start_message?: string;
  verify_2fa_allowed?: boolean;
  verify_2fa_message?: string;
  vnc_active?: boolean;
  vnc_url?: string | null;
  active_job_id?: number | null;
  vnc_enabled?: boolean;
  tailscale_exit_node?: string | null;
  tailscale_exit_node_enabled?: boolean;
};

type TaskPollResponse = {
  task_id: string;
  ready: boolean;
  connection?: ConnectionPayload;
};

function getCsrfTokenFromCookie(): string {
  return (
    document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1] || ""
  );
}

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  disconnected: "Nije povezano",
  connecting: "Povezivanje…",
  needs_2fa: "Potreban SMS kod",
  needs_human: "Potreban ručni korak (CAPTCHA)",
  connected: "Povezano",
  expired: "Sesija istekla",
  error: "Greška",
};

function statusBadgeClass(status: ConnectionStatus): string {
  if (status === "connected") return "border-emerald-400/50 bg-emerald-950/40 text-emerald-200";
  if (status === "needs_2fa" || status === "needs_human") {
    return "border-amber-400/50 bg-amber-950/40 text-amber-200";
  }
  if (status === "connecting") return "border-sky-400/50 bg-sky-950/40 text-sky-200";
  if (status === "expired" || status === "error") return "border-red-400/50 bg-red-950/40 text-red-200";
  return "border-brand-gold/40 bg-black/40 text-brand-cream/80";
}

type StorageStatePayload = {
  cookies?: unknown[];
  origins?: unknown[];
  storage_state?: StorageStatePayload;
};

function normalizeStorageState(raw: unknown): StorageStatePayload {
  if (raw === null || typeof raw !== "object") {
    throw new Error("JSON mora biti objekt s poljem cookies (Playwright storage_state).");
  }
  if (Array.isArray(raw)) {
    return { cookies: raw, origins: [] };
  }
  const obj = raw as StorageStatePayload;
  if (obj.storage_state && typeof obj.storage_state === "object") {
    return normalizeStorageState(obj.storage_state);
  }
  if (Array.isArray(obj.cookies) || Array.isArray(obj.origins)) {
    return {
      cookies: Array.isArray(obj.cookies) ? obj.cookies : [],
      origins: Array.isArray(obj.origins) ? obj.origins : [],
    };
  }
  throw new Error(
    "Očekivan Playwright storage_state: { \"cookies\": [...], \"origins\": [] }. Zalijepi cijeli export ili samo cookies array.",
  );
}

function parsePastedJson(text: string): StorageStatePayload {
  const trimmed = text.trim();
  if (!trimmed) {
    throw new Error("Polje je prazno.");
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("Nevaljan JSON — provjeri zareze i navodnike.");
  }
  return normalizeStorageState(parsed);
}

async function pollTask(
  pollPath: string,
  taskId: string,
  onUpdate: (conn: ConnectionPayload) => void,
  signal: AbortSignal,
): Promise<void> {
  for (let i = 0; i < 90; i += 1) {
    if (signal.aborted) return;
    const response = await fetch(`${pollPath}${taskId}/`, {
      credentials: "include",
      headers: { Accept: "application/json" },
      signal,
    });
    if (!response.ok) throw new Error(`Poll greška (${response.status})`);
    const data = (await response.json()) as TaskPollResponse;
    if (data.connection) onUpdate(data.connection);
    if (data.ready) return;
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("Operacija traje predugo — osvježite stranicu.");
}

export default function BookingSettingsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollAbortRef = useRef<AbortController | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [connection, setConnection] = useState<ConnectionPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [twoFaCode, setTwoFaCode] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [pasteError, setPasteError] = useState("");
  const [vncContinuing, setVncContinuing] = useState(false);

  const fetchConnection = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch("/api/reception/booking-extranet/connection/", {
      credentials: "include",
      headers: { Accept: "application/json" },
      signal,
    });
    if (response.status === 401 || response.status === 403) {
      router.replace("/login?next=/settings/booking");
      return;
    }
    if (!response.ok) throw new Error(`Status greška (${response.status})`);
    setConnection((await response.json()) as ConnectionPayload);
  }, [router]);

  useEffect(() => {
    if (!connection || !["needs_human", "connecting"].includes(connection.status)) return undefined;
    const controller = new AbortController();
    const interval = window.setInterval(() => {
      void fetchConnection(controller.signal);
    }, 3000);
    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [connection?.status, fetchConnection]);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const meRes = await fetch("/api/auth/me/", {
          signal: controller.signal,
          credentials: "include",
          headers: { Accept: "application/json" },
        });
        if (meRes.status === 401 || meRes.status === 403) {
          router.replace("/login?next=/settings/booking");
          return;
        }
        if (!meRes.ok) throw new Error(`Auth (${meRes.status})`);
        setMe((await meRes.json()) as MeResponse);
        await fetchConnection(controller.signal);
        setAuthReady(true);
      } catch {
        if (!controller.signal.aborted) router.replace("/login?next=/settings/booking");
      }
    })();
    return () => controller.abort();
  }, [router, fetchConnection]);

  const apiPost = async (path: string, body?: FormData | object) => {
    await fetch("/api/auth/csrf/", { credentials: "include" });
    const csrf = getCsrfTokenFromCookie();
    const isForm = body instanceof FormData;
    const response = await fetch(path, {
      method: "POST",
      credentials: "include",
      headers: isForm
        ? { "X-CSRFToken": csrf }
        : { "X-CSRFToken": csrf, "Content-Type": "application/json" },
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    });
    if (response.status === 401 || response.status === 403) {
      router.replace("/login?next=/settings/booking");
      return null;
    }
    const data = await response.json();
    if (!response.ok) {
      throw new Error(
        typeof data === "object" && data !== null && "detail" in data
          ? String(data.detail)
          : `Zahtjev nije uspio (${response.status})`,
      );
    }
    return data;
  };

  const runWithPoll = async (startPath: string, pollPath: string, body?: FormData | object) => {
    pollAbortRef.current?.abort();
    const controller = new AbortController();
    pollAbortRef.current = controller;
    setLoading(true);
    setError("");
    try {
      const started = await apiPost(startPath, body);
      if (!started) return;
      const taskId = (started as { task_id?: string }).task_id;
      if (started.connection) setConnection(started.connection as ConnectionPayload);
      if (taskId) await pollTask(pollPath, taskId, setConnection, controller.signal);
      await fetchConnection();
    } catch (exc) {
      if (!controller.signal.aborted) {
        setError(exc instanceof Error ? exc.message : "Operacija nije uspjela.");
      }
    } finally {
      setLoading(false);
    }
  };

  const importStorageState = async (state: StorageStatePayload) => {
    setLoading(true);
    setError("");
    setPasteError("");
    try {
      const data = await apiPost("/api/reception/booking-extranet/connection/import-state/", {
        storage_state: state,
      });
      if (data) setConnection(data as ConnectionPayload);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setPasteText("");
      setPasteOpen(false);
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : "Uvoz sesije nije uspio.";
      if (pasteOpen) setPasteError(message);
      else setError(message);
    } finally {
      setLoading(false);
    }
  };

  const importSessionFromFile = async () => {
    if (!selectedFile) return;
    setError("");
    try {
      const text = await selectedFile.text();
      const state = parsePastedJson(text);
      await importStorageState(state);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Uvoz sesije nije uspio.");
    }
  };

  const importSessionFromPaste = () => {
    try {
      const state = parsePastedJson(pasteText);
      void importStorageState(state);
    } catch (exc) {
      setPasteError(exc instanceof Error ? exc.message : "Nevaljan JSON.");
    }
  };

  const logout = async () => {
    try {
      await fetch("/api/auth/csrf/", { credentials: "include" });
      await fetch("/api/auth/logout/", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRFToken": getCsrfTokenFromCookie() },
      });
    } finally {
      router.replace("/login?next=/settings/booking");
    }
  };

  const postVncPrepare = async () => {
    setLoading(true);
    setError("");
    try {
      await fetch("/api/auth/csrf/", { credentials: "include" });
      const csrf = getCsrfTokenFromCookie();
      const response = await fetch("/api/reception/booking-extranet/vnc/prepare/", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRFToken": csrf },
      });
      const data = (await response.json()) as ConnectionPayload;
      if (!response.ok) {
        throw new Error(
          typeof data === "object" && data !== null && "detail" in data
            ? String((data as { detail?: string }).detail)
            : "VNC nije uspio.",
        );
      }
      setConnection(data);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "VNC nije uspio.");
    } finally {
      setLoading(false);
    }
  };

  const postVncContinue = async () => {
    setVncContinuing(true);
    setError("");
    try {
      await fetch("/api/auth/csrf/", { credentials: "include" });
      const csrf = getCsrfTokenFromCookie();
      const response = await fetch("/api/reception/booking-extranet/vnc/continue/", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRFToken": csrf },
      });
      const data = (await response.json()) as {
        detail?: string;
        connection?: ConnectionPayload;
        status?: string;
      };
      if (data.connection) setConnection(data.connection);
      if (!response.ok) {
        throw new Error(data.detail || `Nastavi nije uspjelo (${response.status}).`);
      }
      await fetchConnection();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Nastavi nije uspjelo.");
    } finally {
      setVncContinuing(false);
    }
  };

  const showVnc = Boolean(connection?.vnc_active && connection?.vnc_url);

  const showSaveFromVncHint =
    connection &&
    connection.tailscale_exit_node_enabled &&
    ["expired", "error", "connecting", "needs_human", "disconnected"].includes(connection.status) &&
    !showVnc;

  const showImport =
    connection &&
    ["disconnected", "needs_human", "needs_2fa", "expired", "error"].includes(connection.status) &&
    !showVnc;

  return (
    <main className="relative min-h-screen overflow-hidden bg-brand-ink text-brand-cream">
      <div className="pointer-events-none absolute inset-0 brand-grid opacity-30" />
      <div className="pointer-events-none absolute -top-28 -right-20 h-72 w-72 rounded-full bg-brand-gold/25 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-16 h-64 w-64 rounded-full bg-brand-gold/20 blur-3xl" />
      <section className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-5 py-8 sm:px-8 lg:px-10">
        <header className="rounded-2xl border border-brand-gold/30 bg-black/35 p-5 backdrop-blur-sm sm:p-7">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="rounded-xl border border-brand-gold/40 bg-brand-gold/10 p-2">
                <Image src="/kapa.png" alt="Uzorita logo" width={74} height={74} priority className="h-[56px] w-auto sm:h-[70px]" />
              </div>
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.24em] text-brand-gold">Uzorita Luxury Rooms</p>
                <h1 className="text-2xl font-semibold leading-tight sm:text-3xl">Booking extranet</h1>
                {me ? <p className="mt-1 text-sm text-brand-cream/60">Korisnik: {me.username}</p> : null}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link href="/" className="rounded-full border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm hover:bg-brand-gold/20">Timeline</Link>
              <Link href="/import" className="rounded-full border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm hover:bg-brand-gold/20">Import</Link>
              <button type="button" onClick={logout} className="rounded-full border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm hover:bg-brand-gold/20">Odjava</button>
            </div>
          </div>
        </header>

        {!authReady && <p className="text-brand-cream/80">Provjera autentifikacije…</p>}

        {authReady && connection && (
          <>
            <section className="rounded-2xl border border-brand-gold/25 bg-black/35 p-5 sm:p-7">
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Status veze</p>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <span className={`rounded-full border px-3 py-1 text-sm font-medium ${statusBadgeClass(connection.status)}`}>
                  {STATUS_LABELS[connection.status]}
                </span>
                <span className="text-sm text-brand-cream/60">Hotel {connection.hotel_id || "—"}</span>
              </div>
              <dl className="mt-4 grid gap-2 text-sm text-brand-cream/75 sm:grid-cols-2">
                <div>
                  <dt className="text-brand-cream/50">Zadnji OK</dt>
                  <dd>{connection.last_ok_at ? new Date(connection.last_ok_at).toLocaleString("hr-HR") : "—"}</dd>
                </div>
                <div>
                  <dt className="text-brand-cream/50">Način</dt>
                  <dd>
                    {connection.connect_mode === "automatic"
                      ? "Automatski"
                      : connection.tailscale_exit_node_enabled
                        ? "VNC (Tailscale)"
                        : "Ručni uvoz sesije"}
                  </dd>
                </div>
                <div>
                  <dt className="text-brand-cream/50">Sesija</dt>
                  <dd>{connection.has_session ? "Na disku" : "Nema"}</dd>
                </div>
                {connection.tailscale_exit_node_enabled && connection.tailscale_exit_node ? (
                  <div>
                    <dt className="text-brand-cream/50">Tailscale egress</dt>
                    <dd className="font-mono text-xs">{connection.tailscale_exit_node}</dd>
                  </div>
                ) : null}
              </dl>
              {connection.last_error && connection.status !== "connected" ? (
                <p className="mt-3 text-sm text-amber-200/90">{connection.last_error}</p>
              ) : null}
              {connection.status === "expired" && connection.tailscale_exit_node_enabled ? (
                <p className="mt-3 text-sm text-sky-200/90">
                  Ako u VNC prozoru već vidite Booking extranet (home), prijava je uspjela — kliknite{" "}
                  <strong className="font-medium">Spremi sesiju</strong> ispod (ne mora pisati „Povezano” dok ne
                  spremite).
                </p>
              ) : null}
              {!connection.enabled ? (
                <p className="mt-3 text-sm text-red-300">BOOKING_EXTRANET_ENABLED nije uključen na serveru.</p>
              ) : null}
            </section>

            {connection.vnc_enabled &&
            !showVnc &&
            ["disconnected", "expired", "error"].includes(connection.status) && (
              <section className="rounded-2xl border border-sky-400/35 bg-black/35 p-5 sm:p-7">
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Prijava preko VNC</p>
                {connection.tailscale_exit_node_enabled ? (
                  <p className="mt-2 text-sm text-brand-cream/80">
                    Pokrenite prijavu na serveru (promet ide preko Tailscale exit nodea{" "}
                    <span className="font-mono text-brand-gold">{connection.tailscale_exit_node}</span>). Kad Booking
                    traži CAPTCHA, riješite je u prozoru ispod i kliknite Nastavi.
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-amber-200/90">
                    Za VNC prijavu na serveru postavite{" "}
                    <code className="text-brand-gold">TAILSCALE_EXIT_NODE</code> u backend{" "}
                    <code className="text-brand-gold">.env</code> i restartajte{" "}
                    <code className="text-brand-gold">uzorita-django</code>.
                  </p>
                )}
                {connection.vnc_start_message && connection.vnc_start_allowed === false ? (
                  <p className="mt-2 text-sm text-amber-200/90">{connection.vnc_start_message}</p>
                ) : null}
                <button
                  type="button"
                  disabled={
                    loading ||
                    connection.status === "connecting" ||
                    connection.vnc_start_allowed === false
                  }
                  onClick={() =>
                    runWithPoll(
                      "/api/reception/booking-extranet/connection/start/",
                      "/api/reception/booking-extranet/connection/start/",
                    )
                  }
                  className="mt-4 rounded-full border border-sky-400/50 bg-sky-950/50 px-5 py-2 text-sm font-medium hover:bg-sky-900/40 disabled:opacity-50"
                >
                  Pokreni prijavu (VNC)
                </button>
              </section>
            )}

            {showSaveFromVncHint ? (
              <section className="rounded-2xl border border-emerald-400/40 bg-emerald-950/20 p-5 sm:p-7">
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-200">Spremi sesiju iz VNC</p>
                <p className="mt-2 text-sm text-brand-cream/85">
                  Vidite li u VNC-u već prijavljeni extranet (stranica home)? Kliknite{" "}
                  <strong className="font-medium text-brand-cream">Spremi sesiju</strong> — status „Sesija istekla”
                  nestaje nakon spremanja.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => void postVncPrepare()}
                    className="rounded-full border border-sky-400/50 bg-sky-950/50 px-5 py-2 text-sm font-medium hover:bg-sky-900/40 disabled:opacity-50"
                  >
                    Otvori VNC prozor
                  </button>
                  <button
                    type="button"
                    disabled={loading || vncContinuing}
                    onClick={() => void postVncContinue()}
                    className="rounded-full border border-emerald-400/50 bg-emerald-900/40 px-5 py-2 text-sm font-medium disabled:opacity-50"
                  >
                    {vncContinuing ? "Spremanje…" : "Spremi sesiju"}
                  </button>
                </div>
              </section>
            ) : null}

            {showVnc ? (
              <section className="relative z-10 rounded-2xl border border-amber-400/40 bg-black/35 p-5 sm:p-7">
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">VNC browser</p>
                <p className="mt-2 text-sm text-brand-cream/80">
                  Kad vidite Booking extranet (npr. home), kliknite{" "}
                  <strong className="font-medium text-brand-cream">Spremi sesiju</strong>. CAPTCHA riješite u prozoru
                  prije toga ako se pojavi.
                </p>
                <p className="mt-1 text-xs text-brand-cream/55">
                  Ako piše „Connecting” ili „connection is closed”, kliknite Osvježi status ili Otvori VNC u novom
                  prozoru.
                </p>
                <iframe
                  key={connection.vnc_url}
                  src={connection.vnc_url!}
                  title="Booking CAPTCHA"
                  className="relative z-0 mt-4 h-[min(70vh,720px)] w-full rounded-xl border border-brand-gold/30 bg-black"
                />
                <div className="relative z-20 mt-4 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={loading || vncContinuing}
                    onClick={() => void postVncContinue()}
                    className="rounded-full border border-brand-gold/50 bg-brand-gold/25 px-5 py-2 text-sm font-medium disabled:opacity-50"
                  >
                    {vncContinuing ? "Spremanje…" : "Spremi sesiju"}
                  </button>
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => void fetchConnection()}
                    className="rounded-full border border-brand-gold/40 px-4 py-2 text-sm hover:bg-brand-gold/15 disabled:opacity-50"
                  >
                    Osvježi status
                  </button>
                  <a
                    href={
                      connection.vnc_url!.startsWith("http")
                        ? connection.vnc_url!
                        : `${typeof window !== "undefined" ? window.location.origin : ""}${connection.vnc_url!}`
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-full border border-brand-gold/40 px-4 py-2 text-sm text-brand-cream/90 hover:bg-brand-gold/15"
                  >
                    Otvori VNC u novom prozoru
                  </a>
                </div>
              </section>
            ) : null}

            {showImport && (
              <section className="rounded-2xl border border-brand-gold/25 bg-black/35 p-5 sm:p-7">
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Spremi sesiju</p>
                <p className="mt-2 text-sm text-brand-cream/75">Nakon prijave na Booking extranetu zalijepite Playwright export ili učitajte datoteku.</p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setPasteError("");
                      setPasteOpen(true);
                    }}
                    className="rounded-full border border-brand-gold/50 bg-brand-gold/25 px-5 py-2 text-sm font-medium hover:bg-brand-gold/35"
                  >
                    Zalijepi JSON
                  </button>
                  <label className="cursor-pointer rounded-full border border-brand-gold/50 bg-brand-gold/20 px-5 py-2 text-sm hover:bg-brand-gold/30">
                    Učitaj datoteku
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".json,application/json"
                      className="hidden"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                    />
                  </label>
                  {selectedFile ? <span className="text-sm text-brand-cream/70">{selectedFile.name}</span> : null}
                  <button
                    type="button"
                    disabled={loading || !selectedFile}
                    onClick={importSessionFromFile}
                    className="rounded-full border border-brand-gold/50 bg-brand-gold/25 px-5 py-2 text-sm font-medium disabled:opacity-50"
                  >
                    Spremi datoteku
                  </button>
                </div>
              </section>
            )}

            {pasteOpen && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
                role="dialog"
                aria-modal="true"
                aria-labelledby="paste-json-title"
                onClick={() => {
                  if (!loading) setPasteOpen(false);
                }}
              >
                <div
                  className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl border border-brand-gold/35 bg-brand-ink shadow-xl"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center justify-between border-b border-brand-gold/20 px-5 py-4">
                    <h2 id="paste-json-title" className="text-lg font-semibold">
                      Zalijepi storage_state JSON
                    </h2>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => setPasteOpen(false)}
                      className="rounded-full px-3 py-1 text-sm text-brand-cream/70 hover:bg-black/40 hover:text-brand-cream"
                      aria-label="Zatvori"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-5">
                    <p className="text-sm text-brand-cream/75">
                      Zalijepite cijeli Playwright <code className="text-brand-gold">storage_state.json</code> ili
                      samo <code className="text-brand-gold">cookies</code> array.
                    </p>
                    <textarea
                      value={pasteText}
                      onChange={(e) => {
                        setPasteText(e.target.value);
                        setPasteError("");
                      }}
                      placeholder='{"cookies": [...], "origins": []}'
                      spellCheck={false}
                      className="min-h-[220px] flex-1 resize-y rounded-xl border border-brand-gold/30 bg-black/40 p-4 font-mono text-xs leading-relaxed text-brand-cream"
                    />
                    {pasteError ? (
                      <p className="rounded-xl border border-red-400/40 bg-red-950/40 px-4 py-2 text-sm text-red-200">
                        {pasteError}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap justify-end gap-2 border-t border-brand-gold/20 px-5 py-4">
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => setPasteOpen(false)}
                      className="rounded-full border border-brand-gold/40 px-5 py-2 text-sm hover:bg-black/40 disabled:opacity-50"
                    >
                      Odustani
                    </button>
                    <button
                      type="button"
                      disabled={loading || !pasteText.trim()}
                      onClick={importSessionFromPaste}
                      className="rounded-full border border-brand-gold/50 bg-brand-gold/25 px-5 py-2 text-sm font-medium disabled:opacity-50"
                    >
                      Spremi sesiju
                    </button>
                  </div>
                </div>
              </div>
            )}

            {connection.status === "needs_2fa" && (
              <section className="rounded-2xl border border-red-400/40 bg-red-950/25 p-5 sm:p-7">
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-red-200">SMS limit / 2FA</p>
                <p className="mt-2 text-sm text-red-100/90">
                  Booking je vjerojatno privremeno prestao slati SMS jer je bilo previše pokušaja prijave s IP-a
                  servera. <strong className="font-medium">Ne pokrećite ponovno VNC prijavu.</strong>
                </p>
                <p className="mt-2 text-sm text-brand-cream/80">
                  Pričekajte 24–48 h bez novih pokušaja, ili se prijavite na laptopu i uvezite{" "}
                  <code className="text-brand-gold">storage_state.json</code> u odjeljku Spremi sesiju.
                </p>
                {connection.verify_2fa_message && connection.verify_2fa_allowed === false ? (
                  <p className="mt-2 text-sm text-amber-200/90">{connection.verify_2fa_message}</p>
                ) : null}
                {connection.verify_2fa_allowed === false ? null : (
                <div className="mt-3 flex flex-wrap gap-2">
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={twoFaCode}
                    onChange={(e) => setTwoFaCode(e.target.value)}
                    placeholder="Verifikacijski kod"
                    className="rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-2 text-sm"
                  />
                  <button
                    type="button"
                    disabled={loading || !twoFaCode.trim()}
                    onClick={() =>
                      runWithPoll(
                        "/api/reception/booking-extranet/connection/verify-2fa/",
                        "/api/reception/booking-extranet/connection/start/",
                        { code: twoFaCode.trim() },
                      )
                    }
                    className="rounded-full border border-brand-gold/50 bg-brand-gold/25 px-5 py-2 text-sm disabled:opacity-50"
                  >
                    Pošalji kod
                  </button>
                </div>
                )}
              </section>
            )}

            {connection.connect_mode === "automatic" && (
              <section className="rounded-2xl border border-brand-gold/25 bg-black/35 p-5 sm:p-7">
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Automatski pokušaj</p>
                <p className="mt-2 text-sm text-amber-200/90">Česti pokušaji povećavaju CAPTCHA. Preporuka: human_assisted.</p>
                {!connection.auto_connect_allowed && connection.auto_connect_message ? (
                  <p className="mt-2 text-sm text-brand-cream/70">{connection.auto_connect_message}</p>
                ) : null}
                <button
                  type="button"
                  disabled={loading || !connection.auto_connect_allowed}
                  onClick={() =>
                    runWithPoll(
                      "/api/reception/booking-extranet/connection/start/",
                      "/api/reception/booking-extranet/connection/start/",
                    )
                  }
                  className="mt-4 rounded-full border border-brand-gold/50 bg-brand-gold/25 px-5 py-2 text-sm disabled:opacity-50"
                >
                  Pokušaj automatski
                </button>
              </section>
            )}

            <section className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={loading}
                onClick={() =>
                  runWithPoll(
                    "/api/reception/booking-extranet/connection/check/",
                    "/api/reception/booking-extranet/connection/check/",
                  )
                }
                className="rounded-full border border-brand-gold/40 px-4 py-2 text-sm hover:bg-brand-gold/15 disabled:opacity-50"
              >
                Provjeri sesiju
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={async () => {
                  setLoading(true);
                  setError("");
                  try {
                    const data = await apiPost("/api/reception/booking-extranet/connection/disconnect/");
                    if (data) setConnection(data as ConnectionPayload);
                  } catch (exc) {
                    setError(exc instanceof Error ? exc.message : "Odspajanje nije uspjelo.");
                  } finally {
                    setLoading(false);
                  }
                }}
                className="rounded-full border border-red-400/40 px-4 py-2 text-sm text-red-200 hover:bg-red-950/30 disabled:opacity-50"
              >
                Odspoji
              </button>
            </section>

            {error ? <p className="rounded-xl border border-red-400/40 bg-red-950/40 px-4 py-3 text-red-200">{error}</p> : null}
          </>
        )}
      </section>
    </main>
  );
}
