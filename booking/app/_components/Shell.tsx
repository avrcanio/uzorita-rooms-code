import Link from "next/link";
import type { Lang } from "../../lib/i18n";
import { t } from "../../lib/i18n";

export function Shell({
  children,
  active,
  lang = "hr",
}: {
  children: React.ReactNode;
  active?: "home" | "search" | "room";
  lang?: Lang;
}) {
  const tr = t(lang);
  const homeHref = lang ? `/?lang=${encodeURIComponent(lang)}` : "/";
  const searchHref = lang ? `/search?lang=${encodeURIComponent(lang)}` : "/search";
  const showHomeBtn = active !== "home" && active !== "search" && active !== "room";
  const showSearchBtn = active !== "home" && active !== "search" && active !== "room";

  return (
    <div>
      <header style={{ padding: "1.25rem 0" }}>
        <div className="container" style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <Link
            href={homeHref}
            style={{
              display: "inline-flex",
              alignItems: "baseline",
              gap: "0.6rem",
              textDecoration: "none",
              color: "inherit",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-fraunces)",
                fontSize: "1.4rem",
                letterSpacing: "-0.02em",
              }}
            >
              Uzorita Luxury Rooms
            </span>
          </Link>
          <nav style={{ marginLeft: "auto", display: "flex", gap: "0.6rem" }}>
            {showHomeBtn ? (
              <Link
                href={homeHref}
                className="btn"
                style={{
                  textDecoration: "none",
                }}
              >
                {tr.home}
              </Link>
            ) : null}
            {showSearchBtn ? (
              <Link
                href={searchHref}
                className="btn"
                style={{
                  textDecoration: "none",
                }}
              >
                {tr.search}
              </Link>
            ) : null}
            <div
              className="card"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.25rem",
                padding: "0.2rem",
                borderRadius: "14px",
              }}
            >
              <Link
                href={`${active === "search" ? "/search" : "/"}?lang=hr`}
                className="btn"
                style={{
                  textDecoration: "none",
                  padding: "0.55rem 0.7rem",
                  borderRadius: "12px",
                  borderColor: lang === "hr" ? "rgba(192, 107, 43, 0.35)" : "rgba(24, 22, 21, 0.10)",
                }}
              >
                HR
              </Link>
              <Link
                href={`${active === "search" ? "/search" : "/"}?lang=en`}
                className="btn"
                style={{
                  textDecoration: "none",
                  padding: "0.55rem 0.7rem",
                  borderRadius: "12px",
                  borderColor: lang === "en" ? "rgba(192, 107, 43, 0.35)" : "rgba(24, 22, 21, 0.10)",
                }}
              >
                EN
              </Link>
            </div>
          </nav>
        </div>
      </header>
      <main>{children}</main>
      <footer style={{ padding: "2rem 0 3rem" }}>
        <div className="container" style={{ color: "var(--muted)", fontSize: "0.95rem" }}>
          <span>Uzorita Luxury Rooms</span>
        </div>
      </footer>
    </div>
  );
}
