import Link from "next/link";
import { Shell } from "../_components/Shell";

export default async function ConfirmationPage(props: { searchParams: Promise<Record<string, string | string[]>> }) {
  const sp = await props.searchParams;
  const code = typeof sp.code === "string" ? sp.code : "";

  return (
    <Shell>
      <section className="container" style={{ padding: "0.75rem 0 2.5rem" }}>
        <div className="card" style={{ padding: "1.5rem" }}>
          <h1 style={{ margin: 0, fontFamily: "var(--font-fraunces)", fontSize: "2rem" }}>Potvrda</h1>
          {!code ? (
            <div style={{ marginTop: "1rem" }}>
              <p style={{ margin: 0, color: "var(--muted)" }}>
                Fali <code>code</code> parametar.
              </p>
              <div style={{ marginTop: "1rem" }}>
                <Link href="/" className="btn btn-primary" style={{ textDecoration: "none" }}>
                  Pocetna
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: "1rem" }}>
              <div className="label">Booking code</div>
              <div style={{ fontWeight: 900 }}>{code}</div>
              <p style={{ margin: "0.75rem 0 0", color: "var(--muted)" }}>
                Placeholder za public-safe prikaz + polling.
              </p>
            </div>
          )}
        </div>
      </section>
    </Shell>
  );
}

