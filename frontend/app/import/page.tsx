"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

type MeResponse = { id: number; username: string };

type FileImportError = { external_id: string; error: string };

type FileImportResult = {
  filename: string;
  total: number;
  created: number;
  updated: number;
  skipped: number;
  errors: FileImportError[];
};

type ImportSummary = {
  files: number;
  total: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
};

type ImportResponse = {
  summary: ImportSummary;
  files: FileImportResult[];
  dry_run: boolean;
};

function getCsrfTokenFromCookie(): string {
  return (
    document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1] || ""
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const BLOCKED_EXPORT_EXTENSIONS = [".xlsx", ".xlsm", ".csv", ".txt", ".pdf", ".zip", ".doc", ".docx"];

/** Booking.com često sprema export kao "Prijava" bez .xls ekstenzije. */
function isLikelyBookingExportFile(file: File): boolean {
  const name = file.name.trim();
  const lower = name.toLowerCase();
  if (lower.endsWith(".xls")) return true;
  if (BLOCKED_EXPORT_EXTENSIONS.some((ext) => lower.endsWith(ext))) return false;
  return !name.includes(".");
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-brand-gold/20 bg-black/30 px-3 py-2">
      <p className="text-xs text-brand-cream/60">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

function ImportFileRow({
  file,
  expanded,
  onToggle,
}: {
  file: FileImportResult;
  expanded: boolean;
  onToggle: () => void;
}) {
  const errCount = file.errors.length;
  return (
    <>
      <tr className="border-b border-brand-gold/10">
        <td className="py-3 pr-4 font-medium">{file.filename}</td>
        <td className="py-3 pr-4">{file.total}</td>
        <td className="py-3 pr-4">{file.created}</td>
        <td className="py-3 pr-4">{file.updated}</td>
        <td className="py-3 pr-4">{file.skipped}</td>
        <td className="py-3">
          {errCount > 0 ? (
            <button type="button" onClick={onToggle} className="text-red-300 underline hover:no-underline">
              {errCount} {expanded ? "▲" : "▼"}
            </button>
          ) : (
            "—"
          )}
        </td>
      </tr>
      {expanded && errCount > 0 && (
        <tr>
          <td colSpan={6} className="pb-3">
            <ul className="rounded-lg bg-red-950/30 px-3 py-2 text-xs text-red-200">
              {file.errors.map((err, i) => (
                <li key={`${err.external_id}-${i}`}>
                  {err.external_id ? `${err.external_id}: ` : ""}
                  {err.error}
                </li>
              ))}
            </ul>
          </td>
        </tr>
      )}
    </>
  );
}

function ImportResults({
  result,
  expandedFiles,
  toggleExpanded,
}: {
  result: ImportResponse;
  expandedFiles: Set<string>;
  toggleExpanded: (filename: string) => void;
}) {
  const { summary, dry_run: dryRun } = result;
  return (
    <section className="rounded-2xl border border-brand-gold/25 bg-black/35 p-5 sm:p-7">
      <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">
        {dryRun ? "Pregled (dry-run)" : "Rezultat importa"}
      </p>
      <ResultsStatsGrid summary={summary} />
      {summary.errors > 0 && <p className="mt-3 text-sm text-red-300">Greške po redu: {summary.errors}</p>}
      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead>
            <tr className="border-b border-brand-gold/20 text-brand-cream/60">
              <th className="py-2 pr-4">Datoteka</th>
              <th className="py-2 pr-4">Redaka</th>
              <th className="py-2 pr-4">Novo</th>
              <th className="py-2 pr-4">Ažur.</th>
              <th className="py-2 pr-4">Presk.</th>
              <th className="py-2">Greške</th>
            </tr>
          </thead>
          <tbody>
            {result.files.map((file) => (
              <ImportFileRow
                key={file.filename}
                file={file}
                expanded={expandedFiles.has(file.filename)}
                onToggle={() => toggleExpanded(file.filename)}
              />
            ))}
          </tbody>
        </table>
      </div>
      {!dryRun && (
        <p className="mt-4 text-sm text-brand-cream/70">
          <Link href="/" className="text-brand-gold underline hover:no-underline">
            Natrag na timeline
          </Link>{" "}
          za pregled ažuriranih rezervacija.
        </p>
      )}
    </section>
  );
}

function ResultsStatsGrid({ summary }: { summary: ImportSummary }) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
      <Stat label="Datoteke" value={summary.files} />
      <Stat label="Redaka" value={summary.total} />
      <Stat label="Novo" value={summary.created} />
      <Stat label="Ažurirano" value={summary.updated} />
      <Stat label="Preskočeno" value={summary.skipped} />
    </div>
  );
}

export default function ImportPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dryRun, setDryRun] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ImportResponse | null>(null);
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());

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
          router.replace("/login?next=/import");
          return;
        }
        if (!response.ok) throw new Error(`Auth greška (${response.status})`);
        setMe((await response.json()) as MeResponse);
        setAuthReady(true);
      } catch {
        if (!controller.signal.aborted) router.replace("/login?next=/import");
      }
    };
    checkAuth();
    return () => controller.abort();
  }, [router]);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const rejected = Array.from(incoming).filter((f) => !isLikelyBookingExportFile(f));
    const list = Array.from(incoming).filter((f) => isLikelyBookingExportFile(f));
    if (list.length === 0) {
      setError(
        rejected.length
          ? `Nepodržan format (${rejected.map((f) => f.name).join(", ")}). Koristite Booking .xls export (npr. datoteka "Prijava" bez ekstenzije ili Prijava.xls).`
          : "Odaberite Booking export (.xls ili datoteka bez ekstenzije, npr. Prijava).",
      );
      return;
    }
    setError("");
    setResult(null);
    setSelectedFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const merged = [...prev];
      for (const file of list) {
        const key = `${file.name}:${file.size}`;
        if (!seen.has(key)) {
          seen.add(key);
          merged.push(file);
        }
      }
      return merged;
    });
  }, []);

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
    setResult(null);
  };

  const clearFiles = () => {
    setSelectedFiles([]);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const runImport = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      await fetch("/api/auth/csrf/", { credentials: "include" });
      const csrfToken = getCsrfTokenFromCookie();
      const formData = new FormData();
      for (const file of selectedFiles) formData.append("files", file);
      if (dryRun) formData.append("dry_run", "true");
      const response = await fetch("/api/reception/booking-xls-import/", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });
      if (response.status === 401 || response.status === 403) {
        router.replace("/login?next=/import");
        return;
      }
      const data = (await response.json()) as ImportResponse | { detail?: string; files?: string[] };
      if (!response.ok) {
        const detail =
          typeof data === "object" && data !== null && "detail" in data
            ? String(data.detail)
            : typeof data === "object" && data !== null && "files" in data && Array.isArray(data.files)
              ? data.files.join(" ")
              : `Import greška (${response.status})`;
        throw new Error(detail);
      }
      setResult(data as ImportResponse);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Import nije uspio.");
    } finally {
      setUploading(false);
    }
  };

  const toggleExpanded = (filename: string) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
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
      router.replace("/login?next=/import");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-brand-ink text-brand-cream">
      <div className="pointer-events-none absolute inset-0 brand-grid opacity-30" />
      <div className="pointer-events-none absolute -top-28 -right-20 h-72 w-72 rounded-full bg-brand-gold/25 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-16 h-64 w-64 rounded-full bg-brand-gold/20 blur-3xl" />
      <section className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-5 py-8 sm:px-8 lg:px-10">
        <header className="rounded-2xl border border-brand-gold/30 bg-black/35 p-5 backdrop-blur-sm sm:p-7">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="rounded-xl border border-brand-gold/40 bg-brand-gold/10 p-2">
                <Image src="/kapa.png" alt="Uzorita logo" width={74} height={74} priority className="h-[56px] w-auto sm:h-[70px]" />
              </div>
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.24em] text-brand-gold">Uzorita Luxury Rooms</p>
                <h1 className="text-2xl font-semibold leading-tight sm:text-3xl">Import Booking XLS</h1>
                {me ? <p className="mt-1 text-sm text-brand-cream/60">Korisnik: {me.username}</p> : null}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link href="/" className="rounded-full border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm hover:bg-brand-gold/20">Timeline</Link>
              <button type="button" onClick={logout} className="rounded-full border border-brand-gold/40 bg-black/40 px-4 py-2 text-sm hover:bg-brand-gold/20">Odjava</button>
            </div>
          </div>
        </header>
        {!authReady && <p className="text-brand-cream/80">Provjera autentifikacije...</p>}
        {authReady && (
          <>
            <section className="rounded-2xl border border-brand-gold/25 bg-black/35 p-5 sm:p-7">
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Booking XLS import</p>
              <p className="mt-2 text-sm text-brand-cream/75">
                Uvezite Booking.com export: <code className="text-brand-gold">.xls</code> ili datoteku bez ekstenzije (npr.{" "}
                <code className="text-brand-gold">Prijava</code>).
              </p>
              <div
                className={[
                  "mt-6 flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 transition-colors",
                  dragOver ? "border-brand-gold bg-brand-gold/10" : "border-brand-gold/35 bg-black/25",
                ].join(" ")}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
                }}
              >
                <p className="text-center text-sm text-brand-cream/80">Povucite Booking export ovdje ili</p>
                <label className="cursor-pointer rounded-full border border-brand-gold/50 bg-brand-gold/20 px-5 py-2 text-sm hover:bg-brand-gold/30">
                  Odaberite datoteke
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xls,application/vnd.ms-excel,*"
                    multiple
                    className="hidden"
                    onChange={(e) => { if (e.target.files?.length) addFiles(e.target.files); }}
                  />
                </label>
              </div>
              {selectedFiles.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {selectedFiles.map((file, index) => (
                    <li key={`${file.name}-${file.size}`} className="flex items-center justify-between gap-3 rounded-xl border border-brand-gold/20 bg-black/30 px-4 py-3 text-sm">
                      <span className="truncate">{file.name}</span>
                      <span className="shrink-0 text-brand-cream/60">{formatBytes(file.size)}</span>
                      <button type="button" onClick={() => removeFile(index)} className="shrink-0 rounded-full border border-brand-gold/30 px-3 py-1 text-xs hover:bg-brand-gold/15">Ukloni</button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} className="rounded border-brand-gold/40" />
                  Samo pregled (dry-run, bez zapisa u bazu)
                </label>
                <div className="flex flex-wrap gap-2">
                  {selectedFiles.length > 0 && (
                    <button type="button" onClick={clearFiles} disabled={uploading} className="rounded-full border border-brand-gold/30 px-4 py-2 text-sm hover:bg-black/40 disabled:opacity-50">Očisti</button>
                  )}
                  <button type="button" onClick={runImport} disabled={uploading || selectedFiles.length === 0} className="rounded-full border border-brand-gold/50 bg-brand-gold/25 px-6 py-2 text-sm font-medium hover:bg-brand-gold/35 disabled:opacity-50">
                    {uploading ? "Uvoz..." : dryRun ? "Pregledaj" : "Uvezi"}
                  </button>
                </div>
              </div>
            </section>
            {error && <p className="rounded-xl border border-red-400/40 bg-red-950/40 px-4 py-3 text-red-200">{error}</p>}
            {result && <ImportResults result={result} expandedFiles={expandedFiles} toggleExpanded={toggleExpanded} />}
          </>
        )}
      </section>
    </main>
  );
}
