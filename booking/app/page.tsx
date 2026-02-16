import Link from "next/link";
import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { Shell } from "./_components/Shell";
import { getPublicProperty } from "../lib/api";
import { pickLang } from "../lib/i18n";

export const metadata: Metadata = {
  verification: {
    google: "nCQgFhyDPB6_YnAb-Pb2sNHSfGBrWDVqeGnk9N4GPHI",
  },
};

export default async function HomePage() {
  const cookieStore = await cookies();
  const headerStore = await headers();
  const cookieLang = cookieStore.get("booking_lang")?.value ?? null;
  const acceptLanguage = headerStore.get("accept-language");
  const lang = pickLang({ cookieLang, acceptLanguage, fallback: "hr" });
  const property = await getPublicProperty({ lang });

  const title = lang === "en" ? "About this property" : "O objektu";

  const whatsappDigits = (property.whatsapp_phone || "").replace(/[^\d]/g, "");
  const whatsappUrl = whatsappDigits ? `https://wa.me/${whatsappDigits}` : "";

  type FacilityKey =
    | "non_smoking"
    | "airport_shuttle"
    | "restaurant"
    | "wifi"
    | "parking"
    | "family"
    | "terrace"
    | "bar"
    | "breakfast"
    | "generic";

  const facilityKeyForLabel = (label: string): FacilityKey => {
    const s = (label || "").toLowerCase();
    if (s.includes("wifi")) return "wifi";
    if (s.includes("park")) return "parking";
    if (s.includes("restoran") || s.includes("restaurant")) return "restaurant";
    if (s.includes("terasa") || s.includes("terrace")) return "terrace";
    if (s.includes("doruc") || s.includes("breakfast")) return "breakfast";
    if (s.includes("obitelj") || s.includes("family")) return "family";
    if (s.includes("zracn") || s.includes("airport") || s.includes("shuttle")) return "airport_shuttle";
    // Avoid false positives like "dobar" -> contains "bar".
    if (s.trim() === "bar" || s.includes("cafe/bar") || s.includes("café/bar")) return "bar";
    if (s.includes("nepus") || s.includes("non-smoking") || (s.includes("non") && s.includes("smoking")))
      return "non_smoking";
    return "generic";
  };

  const Icon = ({ k }: { k: FacilityKey }) => {
    const common = {
      width: 26,
      height: 26,
      viewBox: "0 0 24 24",
      fill: "none",
      xmlns: "http://www.w3.org/2000/svg",
      style: { display: "block" as const },
    };
    const stroke = { stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

    switch (k) {
      case "wifi":
        return (
          <svg {...common}>
            <path {...stroke} d="M5 10.5c4.7-4 9.3-4 14 0" />
            <path {...stroke} d="M7.8 13.4c2.9-2.5 5.5-2.5 8.4 0" />
            <path {...stroke} d="M10.6 16.2c1.4-1.2 1.4-1.2 2.8 0" />
            <path {...stroke} d="M12 19.2h0" />
          </svg>
        );
      case "parking":
        return (
          <svg {...common}>
            <path {...stroke} d="M7 21V3h6a4.5 4.5 0 0 1 0 9H7" />
            <path {...stroke} d="M5.5 21h6" />
          </svg>
        );
      case "restaurant":
        return (
          <svg {...common}>
            <path {...stroke} d="M7 3v9" />
            <path {...stroke} d="M5 3v4a2 2 0 0 0 4 0V3" />
            <path {...stroke} d="M16 3v18" />
            <path {...stroke} d="M16 3c2 0 3 1.5 3 4v3h-3" />
          </svg>
        );
      case "airport_shuttle":
        return (
          <svg {...common}>
            <path {...stroke} d="M12 3v10" />
            <path {...stroke} d="M8.5 6.5 12 3l3.5 3.5" />
            <path {...stroke} d="M5 13h14" />
            <path {...stroke} d="M7 13l-2 6" />
            <path {...stroke} d="M17 13l2 6" />
            <path {...stroke} d="M8 19h8" />
          </svg>
        );
      case "terrace":
        return (
          <svg {...common}>
            <path {...stroke} d="M12 2v7" />
            <path {...stroke} d="M6 9c2-2 10-2 12 0" />
            <path {...stroke} d="M4 21V11h16v10" />
            <path {...stroke} d="M9 21v-4h6v4" />
          </svg>
        );
      case "bar":
        return (
          <svg {...common}>
            <path {...stroke} d="M6 3h12l-4.5 7v4.5a2.5 2.5 0 0 1-5 0V10L6 3z" />
            <path {...stroke} d="M10 21h4" />
          </svg>
        );
      case "breakfast":
        return (
          <svg {...common}>
            {/* Fork */}
            <path {...stroke} d="M7 3v7" />
            <path {...stroke} d="M5.5 3v4a1.5 1.5 0 0 0 3 0V3" />
            <path {...stroke} d="M7 10v11" />
            {/* Knife */}
            <path {...stroke} d="M16 3v18" />
            <path {...stroke} d="M16 3c2.2 0 3.5 1.6 3.5 4.5V11H16" />
          </svg>
        );
      case "family":
        return (
          <svg {...common}>
            <path {...stroke} d="M8 8a2 2 0 1 0 0.001 0" />
            <path {...stroke} d="M16 8a2 2 0 1 0 0.001 0" />
            <path {...stroke} d="M6 21v-4a3 3 0 0 1 3-3h0" />
            <path {...stroke} d="M18 21v-4a3 3 0 0 0-3-3h0" />
            <path {...stroke} d="M10 21v-5a2 2 0 0 1 4 0v5" />
          </svg>
        );
      case "non_smoking":
        return (
          <svg {...common}>
            <path {...stroke} d="M6 16h10" />
            <path {...stroke} d="M16 16h2" />
            <path {...stroke} d="M7 12c0-2 2-2 2-4" />
            <path {...stroke} d="M3.5 20.5 20.5 3.5" />
          </svg>
        );
      default:
        return (
          <svg {...common}>
            <path {...stroke} d="M12 3v18" />
            <path {...stroke} d="M3 12h18" />
          </svg>
        );
    }
  };

  const formatDistance = (m: number): string => {
    if (!Number.isFinite(m)) return "";
    if (m >= 1000) {
      const km = m / 1000;
      const rounded = Math.round(km * 10) / 10;
      return `${rounded} km`;
    }
    return `${m} m`;
  };

  const renderAboutParagraph = (text: string, idx: number) => {
    const trimmed = (text || "").trim();
    if (!trimmed) return null;
    const colon = trimmed.indexOf(":");
    if (colon > 0 && colon < 42) {
      const head = trimmed.slice(0, colon).trim();
      const rest = trimmed.slice(colon + 1).trim();
      return (
        <p key={idx} style={{ margin: idx === 0 ? 0 : "0.85rem 0 0", color: "var(--muted)", lineHeight: 1.6 }}>
          <strong style={{ color: "var(--ink)" }}>{head}:</strong> {rest}
        </p>
      );
    }
    return (
      <p key={idx} style={{ margin: idx === 0 ? 0 : "0.85rem 0 0", color: "var(--muted)", lineHeight: 1.6 }}>
        {trimmed}
      </p>
    );
  };

  return (
    <Shell active="home" lang={lang}>
      {whatsappUrl ? (
        <a
          href={whatsappUrl}
          target="_blank"
          rel="noreferrer"
          aria-label={lang === "en" ? "Chat on WhatsApp" : "Javi se na WhatsApp"}
          title={property.whatsapp_phone}
          style={{
            position: "fixed",
            right: "18px",
            bottom: "18px",
            zIndex: 50,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "54px",
            height: "54px",
            borderRadius: "999px",
            border: "1px solid rgba(24, 22, 21, 0.18)",
            background: "linear-gradient(180deg, rgba(46, 122, 120, 0.95), rgba(30, 98, 96, 0.95))",
            color: "#fffaf2",
            textDecoration: "none",
            boxShadow: "0 18px 44px rgba(0,0,0,0.18)",
          }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M20.5 11.7c0 4.7-3.8 8.5-8.5 8.5-1.4 0-2.8-.3-4-.9L3.5 20.5l1.2-4.2c-.7-1.2-1.1-2.7-1.1-4.3 0-4.7 3.8-8.5 8.5-8.5s8.4 3.8 8.4 8.2Z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M9.4 8.6c.3-.6.6-.7 1.1-.7h.6c.2 0 .4.1.5.4l.7 1.7c.1.2 0 .4-.1.6l-.4.5c-.1.2-.1.4 0 .6.4.9 1.2 1.7 2.1 2.1.2.1.4.1.6 0l.5-.4c.2-.1.4-.2.6-.1l1.7.7c.3.1.4.3.4.5v.6c0 .5-.1.8-.7 1.1-.4.2-1 .3-1.4.2-2.2-.5-4.8-3.1-5.3-5.3-.1-.4 0-1 .2-1.4Z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </a>
      ) : null}

      <section className="container" style={{ padding: "1.5rem 0 2.5rem" }}>
        <div className="card" style={{ padding: "2rem" }}>
          <h1
            style={{
              margin: 0,
              fontFamily: "var(--font-fraunces)",
              fontSize: "clamp(2rem, 3.2vw, 3rem)",
              letterSpacing: "-0.03em",
            }}
          >
            {lang === "en"
              ? "Book direct, without bouncing between platforms."
              : "Rezerviraj direktno, bez prebacivanja izmedu platformi."}
          </h1>
          <p style={{ margin: "0.9rem 0 0", color: "var(--muted)", fontSize: "1.05rem" }}>
            {lang === "en"
              ? "Pick your dates to see availability for all rooms, plus recommended combos for larger groups."
              : "Odaberi datume i vidjet ces dostupnost svih soba, plus preporucene kombinacije za vece grupe."}
          </p>

          <div style={{ marginTop: "1.5rem" }}>
            <Link
              href={`/search?lang=${encodeURIComponent(lang)}`}
              className="btn btn-primary"
              style={{ textDecoration: "none" }}
            >
              {lang === "en" ? "Start searching" : "Kreni s pretragom"}
            </Link>
          </div>
        </div>
      </section>

      <section className="container" style={{ paddingBottom: "1.25rem" }}>
        <div className="card" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0, fontFamily: "var(--font-fraunces)", fontSize: "1.6rem", letterSpacing: "-0.02em" }}>
              {title}
            </h2>
            <div style={{ marginLeft: "auto", color: "var(--muted)", fontWeight: 800 }}>
              {property.name}
            </div>
          </div>

          <div style={{ marginTop: "0.9rem" }}>
            {(property.about || "").split("\n\n").map(renderAboutParagraph)}
          </div>

          <div style={{ marginTop: "1.25rem", display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: "1rem" }}>
            <div className="card" style={{ padding: "1.1rem", gridColumn: "span 12" }}>
              <div style={{ fontWeight: 900 }}>{lang === "en" ? "Address" : "Adresa"}</div>
              <div style={{ marginTop: "0.45rem", color: "var(--muted)" }}>{property.address}</div>
              <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
            {property.google_maps_url ? (
              <a
                href={property.google_maps_url}
                target="_blank"
                rel="noreferrer"
                aria-label={lang === "en" ? "Open in Google Maps" : "Otvori u Google Maps"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "44px",
                  height: "44px",
                  borderRadius: "14px",
                  border: "1px solid rgba(24, 22, 21, 0.12)",
                  background: "rgba(255, 255, 255, 0.65)",
                  boxShadow: "0 10px 24px rgba(0,0,0,0.08)",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/google-maps-launcher.png"
                  alt="Google Maps"
                  width={28}
                  height={28}
                  style={{ display: "block", width: "28px", height: "28px" }}
                />
              </a>
            ) : null}
            {whatsappUrl ? (
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noreferrer"
                title={property.whatsapp_phone}
                aria-label={lang === "en" ? "Chat on WhatsApp" : "Javi se na WhatsApp"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "44px",
                  height: "44px",
                  borderRadius: "14px",
                  border: "1px solid rgba(24, 22, 21, 0.12)",
                  background: "rgba(255, 255, 255, 0.65)",
                  boxShadow: "0 10px 24px rgba(0,0,0,0.08)",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/whatsapp-launcher.png"
                  alt="WhatsApp"
                  width={28}
                  height={28}
                  style={{ display: "block", width: "28px", height: "28px" }}
                />
              </a>
            ) : null}
          </div>
        </div>

        {property.primary_room_photos?.length ? (
          <div className="card" style={{ padding: "1rem", gridColumn: "span 12" }}>
            <div style={{ fontWeight: 900 }}>{lang === "en" ? "Rooms Preview" : "Pregled soba"}</div>
            <div
              style={{
                marginTop: "0.75rem",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "0.75rem",
              }}
            >
              {property.primary_room_photos.map((p) => (
                <Link
                  key={`${p.room_type_id}:${p.url}`}
                  href={`/rooms/${encodeURIComponent(p.room_type_slug)}?lang=${encodeURIComponent(lang)}`}
                  style={{ textDecoration: "none", color: "inherit" }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={(p.url || "").replace("http://rooms.uzorita.hr/", "https://rooms.uzorita.hr/")}
                    alt={p.room_type_code}
                    loading="lazy"
                    style={{
                      width: "100%",
                      height: "130px",
                      objectFit: "cover",
                      borderRadius: "12px",
                      border: "1px solid rgba(24, 22, 21, 0.1)",
                      display: "block",
                    }}
                  />
                </Link>
              ))}
            </div>
          </div>
        ) : null}

        {property.google_maps_embed_url ? (
              <div className="card" style={{ padding: "0.9rem", gridColumn: "span 12" }}>
                <div style={{ fontWeight: 900, padding: "0.2rem 0.25rem 0.75rem" }}>
                  {lang === "en" ? "Location" : "Lokacija"}
                </div>
                <div
                  style={{
                    borderRadius: "14px",
                    overflow: "hidden",
                    border: "1px solid rgba(24, 22, 21, 0.12)",
                    background: "rgba(255, 255, 255, 0.6)",
                  }}
                >
                  <iframe
                    src={property.google_maps_embed_url}
                    title="Google Maps"
                    loading="lazy"
                    referrerPolicy="no-referrer-when-downgrade"
                    style={{ width: "100%", height: "360px", border: 0, display: "block" }}
                    allowFullScreen
                  />
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <section className="container" style={{ paddingBottom: "1.25rem" }}>
        <div className="card" style={{ padding: "1.5rem" }}>
          <h2 style={{ margin: 0, fontFamily: "var(--font-fraunces)", fontSize: "1.6rem", letterSpacing: "-0.02em" }}>
            {lang === "en" ? "Most popular facilities" : "Najpopularniji sadrzaji"}
          </h2>
          <div
            style={{
              marginTop: "1rem",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              gap: "0.85rem",
            }}
          >
            {(property.most_popular_facilities || []).map((label) => {
              const k = facilityKeyForLabel(label);
              return (
                <div
                  key={label}
                  className="card"
                  style={{
                    padding: "0.85rem 0.8rem",
                    borderRadius: "16px",
                    display: "grid",
                    justifyItems: "center",
                    gap: "0.45rem",
                    textAlign: "center",
                    background: "rgba(255, 255, 255, 0.65)",
                  }}
                  aria-label={label}
                  title={label}
                >
                  <div style={{ color: "var(--accent-2)" }}>
                    <Icon k={k} />
                  </div>
                  <div style={{ fontSize: "0.8rem", lineHeight: 1.2, color: "var(--muted)", fontWeight: 800 }}>
                    {label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="container" style={{ paddingBottom: "1.25rem" }}>
        <div className="card" style={{ padding: "1.5rem" }}>
          <h2 style={{ margin: 0, fontFamily: "var(--font-fraunces)", fontSize: "1.6rem", letterSpacing: "-0.02em" }}>
            {lang === "en" ? "Property information" : "Informacije o objektu"}
          </h2>
          <div style={{ marginTop: "0.9rem", color: "var(--muted)", lineHeight: 1.6 }}>
            {property.company_info ? <p style={{ margin: 0 }}>{property.company_info}</p> : null}
            {property.neighborhood ? <p style={{ margin: "0.85rem 0 0" }}>{property.neighborhood}</p> : null}
          </div>
        </div>
      </section>

      <section className="container" style={{ paddingBottom: "1.5rem" }}>
        <div className="card" style={{ padding: "1.5rem" }}>
          <h2 style={{ margin: 0, fontFamily: "var(--font-fraunces)", fontSize: "1.6rem", letterSpacing: "-0.02em" }}>
            {lang === "en" ? "Property surroundings" : "Okolica objekta"}
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4" style={{ marginTop: "1rem" }}>
            {[
              { key: "top_attractions", label: lang === "en" ? "Top attractions" : "Znamenitosti" },
              { key: "natural_beauty", label: lang === "en" ? "Natural beauty" : "Priroda" },
              { key: "public_transport", label: lang === "en" ? "Public transport" : "Javni prijevoz" },
              { key: "restaurants_cafes", label: lang === "en" ? "Restaurants & cafes" : "Restorani i kafici" },
              { key: "beaches", label: lang === "en" ? "Beaches" : "Plaze" },
              { key: "closest_airports", label: lang === "en" ? "Closest airports" : "Najblizi aerodromi" },
            ].map(({ key, label }) => {
              const items = property.surroundings?.[key] || [];
              if (!items.length) return null;
              return (
                <div key={key} className="card" style={{ padding: "1rem" }}>
                  <div style={{ fontWeight: 900 }}>{label}</div>
                  <div style={{ marginTop: "0.65rem", display: "grid", gap: "0.5rem" }}>
                    {items.map((it) => (
                      <div key={`${key}:${it.name}`} style={{ display: "flex", gap: "0.75rem" }}>
                        <div style={{ flex: 1, color: "var(--muted)" }}>{it.name}</div>
                        <div style={{ fontWeight: 900, color: "var(--ink)" }}>{formatDistance(it.distance_m)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="container" style={{ paddingBottom: "1.5rem" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: "1rem" }}>
          <div className="card" style={{ padding: "1.25rem", gridColumn: "span 12" }}>
            <div className="label">{lang === "en" ? "Note" : "Napomena"}</div>
            <div style={{ marginTop: "0.35rem" }}>
              {lang === "en" ? (
                <>
                  Checkout only works with a <code>hold</code> token (anti-overbooking).
                </>
              ) : (
                <>
                  Checkout stranica radi samo s <code>hold</code> tokenom (anti-overbooking).
                </>
              )}
            </div>
          </div>
        </div>
      </section>
    </Shell>
  );
}
