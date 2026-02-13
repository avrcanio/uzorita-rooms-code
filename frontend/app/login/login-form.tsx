"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

type Props = {
  nextPath: string;
};

export default function LoginForm({ nextPath }: Props) {
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const csrfResponse = await fetch("/api/auth/csrf/", {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!csrfResponse.ok) {
        throw new Error("Ne mogu dohvatiti CSRF token.");
      }
      const csrfData = (await csrfResponse.json()) as { csrfToken: string };

      const response = await fetch("/api/auth/login/", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfData.csrfToken,
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(data.detail || `Greška prijave (${response.status})`);
      }

      router.replace(nextPath);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Prijava nije uspjela.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="mt-5 space-y-3">
      <input
        value={username}
        onChange={(event) => setUsername(event.target.value)}
        placeholder="Korisničko ime"
        autoComplete="username"
        className="w-full rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
        required
      />
      <input
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        placeholder="Lozinka"
        type="password"
        autoComplete="current-password"
        className="w-full rounded-xl border border-brand-gold/30 bg-black/40 px-4 py-3 text-sm outline-none focus:border-brand-gold"
        required
      />

      {error && <p className="text-sm text-red-300">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-xl border border-brand-gold/40 bg-brand-gold/20 px-4 py-3 text-sm font-medium disabled:opacity-60"
      >
        {loading ? "Prijava..." : "Prijavi se"}
      </button>
    </form>
  );
}
