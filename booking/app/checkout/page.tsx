import Link from "next/link";
import { Shell } from "../_components/Shell";

export default async function CheckoutPage(props: { searchParams: Promise<Record<string, string | string[]>> }) {
  const sp = await props.searchParams;
  const hold = typeof sp.hold === "string" ? sp.hold : "";

  return (
    <Shell>
      <section className="container" style={{ padding: "0.75rem 0 2.5rem" }}>
        <div className="card" style={{ padding: "1.5rem" }}>
          <h1 style={{ margin: 0, fontFamily: "var(--font-fraunces)", fontSize: "2rem" }}>Checkout</h1>

          {!hold ? (
            <div style={{ marginTop: "1rem" }}>
              <p style={{ margin: 0, color: "var(--muted)" }}>
                Ova stranica se otvara samo s <code>hold</code> tokenom.
              </p>
              <div style={{ marginTop: "1rem" }}>
                <Link href="/search" className="btn btn-primary" style={{ textDecoration: "none" }}>
                  Idi na pretragu
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: "1rem" }}>
              <div className="label">HOLD</div>
              <div style={{ fontWeight: 900, wordBreak: "break-all" }}>{hold}</div>
              <p style={{ margin: "0.75rem 0 0", color: "var(--muted)" }}>
                Placeholder za snapshot i formu: <code>GET /public/holds/{"{hold_token}"}</code>.
              </p>
            </div>
          )}
        </div>
      </section>
    </Shell>
  );
}
