import LoginForm from "./login-form";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const params = await searchParams;
  const nextPath = params.next && params.next.startsWith("/") ? params.next : "/";

  return (
    <main className="relative min-h-screen overflow-hidden bg-brand-ink text-brand-cream">
      <div className="pointer-events-none absolute inset-0 brand-grid opacity-30" />
      <div className="mx-auto flex min-h-screen w-full max-w-md items-center px-5 py-8">
        <section className="w-full rounded-2xl border border-brand-gold/30 bg-black/35 p-6 backdrop-blur-sm">
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-brand-gold">Uzorita Luxury Rooms</p>
          <h1 className="mt-2 text-2xl font-semibold">Prijava recepcije</h1>
          <p className="mt-2 text-sm text-brand-cream/80">
            Prijavite se sa postojećim Django korisnikom.
          </p>

          <LoginForm nextPath={nextPath} />
        </section>
      </div>
    </main>
  );
}
