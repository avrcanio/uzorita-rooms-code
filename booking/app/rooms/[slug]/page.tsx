import type { Metadata } from "next";
import Link from "next/link";
import { cookies, headers } from "next/headers";
import { Shell } from "../../_components/Shell";
import { RoomCarousel } from "../../_components/RoomCarousel";
import { getPublicAvailability, getPublicProperty, getPublicRoomCalendar, getPublicRooms, type PublicRoom } from "../../../lib/api";
import { normalizeLang, pickLang, t } from "../../../lib/i18n";
import { parseSearchParams } from "../../../lib/query";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://booking.uzorita.hr").replace(/\/+$/, "");

function normalizeImageUrl(url: string): string {
  return (url || "").replace("http://rooms.uzorita.hr/", "https://rooms.uzorita.hr/");
}

function roomDescription(room: PublicRoom, lang: "hr" | "en"): string {
  const base = room.subtitle || room.beds || (room.highlights || []).join(", ");
  if (base) return base;
  return lang === "en" ? "Room details at Uzorita Luxury Rooms." : "Detalji sobe u Uzorita Luxury Rooms.";
}

function roomUrl(slug: string, lang: "hr" | "en"): string {
  return `${SITE_URL}/rooms/${encodeURIComponent(slug)}?lang=${encodeURIComponent(lang)}`;
}

function pickLangFromSearchParams(sp: Record<string, string | string[]>): "hr" | "en" {
  const raw = typeof sp.lang === "string" ? sp.lang : null;
  return normalizeLang(raw) ?? "en";
}

function addMonths(ym: string, diff: number): string {
  const m = /^(\d{4})-(\d{2})$/.exec(ym);
  if (!m) return ym;
  const y = Number.parseInt(m[1], 10);
  const mm = Number.parseInt(m[2], 10);
  const d = new Date(Date.UTC(y, mm - 1 + diff, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function monthNum(ym: string): number {
  const m = /^(\d{4})-(\d{2})$/.exec(ym);
  if (!m) return 0;
  return Number.parseInt(m[1], 10) * 12 + Number.parseInt(m[2], 10);
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[]>>;
}): Promise<Metadata> {
  const { slug } = await params;
  const sp = await searchParams;
  const lang = pickLangFromSearchParams(sp);
  const rooms = await getPublicRooms({ lang });
  const room = rooms.find((r) => r.slug === slug);

  if (!room) {
    return {
      title: lang === "en" ? "Room not found | Uzorita Luxury Rooms" : "Soba nije pronadena | Uzorita Luxury Rooms",
      description: lang === "en" ? "Requested room could not be found." : "Tražena soba nije pronađena.",
      robots: { index: false, follow: false },
    };
  }

  const title = `${room.name} | Uzorita Luxury Rooms`;
  const description = roomDescription(room, lang);
  const canonical = roomUrl(room.slug, lang);
  const ogImage = normalizeImageUrl(room.primary_photo_url || room.photos?.[0]?.url || "");

  return {
    title,
    description,
    alternates: {
      canonical,
      languages: {
        hr: roomUrl(room.slug, "hr"),
        en: roomUrl(room.slug, "en"),
      },
    },
    openGraph: {
      title,
      description,
      url: canonical,
      type: "website",
      images: ogImage ? [{ url: ogImage, alt: room.name }] : undefined,
    },
    twitter: {
      card: ogImage ? "summary_large_image" : "summary",
      title,
      description,
      images: ogImage ? [ogImage] : undefined,
    },
  };
}

export default async function RoomPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[]>>;
}) {
  const { slug } = await params;

  const sp = await searchParams;
  const q = parseSearchParams(sp);
  const now = new Date();
  const currentYear = now.getUTCFullYear();
  const currentMonth = now.getUTCMonth() + 1;
  const monthParam = typeof sp.month === "string" ? sp.month : "";
  const legacyMonth = typeof sp.month === "string" ? Number.parseInt(sp.month, 10) : NaN;
  const legacyYear = typeof sp.year === "string" ? Number.parseInt(sp.year, 10) : NaN;
  const defaultCalMonth = `${currentYear}-${String(currentMonth).padStart(2, "0")}`;
  const requestedCalMonth =
    /^\d{4}-\d{2}$/.test(monthParam)
      ? monthParam
      : Number.isFinite(legacyMonth) && Number.isFinite(legacyYear) && legacyMonth >= 1 && legacyMonth <= 12
      ? `${legacyYear}-${String(legacyMonth).padStart(2, "0")}`
      : defaultCalMonth;
  const calMonth = monthNum(requestedCalMonth) < monthNum(defaultCalMonth) ? defaultCalMonth : requestedCalMonth;
  const prevMonth = addMonths(calMonth, -1);
  const nextMonth = addMonths(calMonth, 1);
  const canGoPrev = monthNum(calMonth) > monthNum(defaultCalMonth);
  const checkin = `${calMonth}-01`;
  const checkoutDate = new Date(`${checkin}T00:00:00Z`);
  checkoutDate.setUTCDate(checkoutDate.getUTCDate() + 1);
  const checkout = checkoutDate.toISOString().slice(0, 10);
  const cookieStore = await cookies();
  const headerStore = await headers();
  const cookieLang = cookieStore.get("booking_lang")?.value ?? null;
  const acceptLanguage = headerStore.get("accept-language");
  const lang = pickLang({
    queryLang: typeof sp.lang === "string" ? sp.lang : null,
    cookieLang,
    acceptLanguage,
    fallback: "hr",
  });
  const tr = t(lang);

  const rooms = await getPublicRooms({ lang });
  const property = await getPublicProperty({ lang });
  const room = rooms.find((r) => r.slug === slug);
  let roomCalendars: Array<{ roomId: number; roomCode: string; days: Array<{ date: string; available: boolean; nightly: string | null; currency: string }> }> =
    [];
  if (room) {
    try {
      const availability = await getPublicAvailability({
        checkin,
        checkout,
        adults: q.adults,
        children: q.children,
      });
      const physicalRooms = availability.rooms.filter((r) => r.room_type_id === room.id);
      const calendars = await Promise.all(
        physicalRooms.map(async (pr) => {
          try {
            const cal = await getPublicRoomCalendar({
              roomId: pr.room_id,
              month: calMonth,
              adults: q.adults,
              children: q.children,
            });
            return {
              roomId: cal.room_id,
              roomCode: cal.room_code,
              days: cal.days.map((d) => ({
                date: d.date,
                available: d.available,
                nightly: d.pricing?.accommodation_nightly ?? null,
                currency: d.pricing?.currency ?? "EUR",
              })),
            };
          } catch {
            return null;
          }
        })
      );
      roomCalendars = calendars.filter(Boolean) as Array<{
        roomId: number;
        roomCode: string;
        days: Array<{ date: string; available: boolean; nightly: string | null; currency: string }>;
      }>;
    } catch {
      roomCalendars = [];
    }
  }
  const roomPageUrl = room ? roomUrl(room.slug, lang) : `${SITE_URL}/rooms/${encodeURIComponent(slug)}?lang=${encodeURIComponent(lang)}`;

  const roomImages = room
    ? Array.from(
        new Set(
          [room.primary_photo_url, ...(room.photos || []).map((p) => p.url)]
            .map(normalizeImageUrl)
            .filter(Boolean)
        )
      )
    : [];

  const schema =
    room && property
      ? {
          "@context": "https://schema.org",
          "@graph": [
            {
              "@type": "LodgingBusiness",
              "@id": `${SITE_URL}#lodging`,
              name: property.name || "Uzorita Luxury Rooms",
              url: SITE_URL,
              telephone: property.whatsapp_phone || undefined,
              address: property.address
                ? {
                    "@type": "PostalAddress",
                    streetAddress: property.address,
                  }
                : undefined,
              geo:
                property.latitude && property.longitude
                  ? {
                      "@type": "GeoCoordinates",
                      latitude: String(property.latitude),
                      longitude: String(property.longitude),
                    }
                  : undefined,
            },
            {
              "@type": "HotelRoom",
              "@id": `${roomPageUrl}#room`,
              name: room.name,
              description: roomDescription(room, lang),
              url: roomPageUrl,
              bed: room.beds || undefined,
              image: roomImages.length ? roomImages : undefined,
              isPartOf: { "@id": `${SITE_URL}#lodging` },
              amenityFeature: [...(room.highlights || []), ...(room.amenities || [])].map((a) => ({
                "@type": "LocationFeatureSpecification",
                name: a,
                value: true,
              })),
            },
          ],
        }
      : null;

  return (
    <Shell active="room" lang={lang}>
      <section className="container" style={{ padding: "0.75rem 0 2rem" }}>
        <div style={{ marginBottom: "0.9rem" }}>
          <Link href={`/search?lang=${encodeURIComponent(lang)}`} className="btn" style={{ textDecoration: "none" }}>
            {tr.back_to_search}
          </Link>
        </div>

        <div className="card" style={{ padding: "1.5rem" }}>
          <h1
            style={{
              margin: 0,
              fontFamily: "var(--font-fraunces)",
              letterSpacing: "-0.02em",
              fontSize: "2rem",
            }}
          >
            {room?.name ?? tr.room}
          </h1>
          <p style={{ margin: "0.55rem 0 0", color: "var(--muted)" }}>
            {room ? room.subtitle || room.beds : tr.unknown_slug}
          </p>
          {schema ? (
            <script
              type="application/ld+json"
              dangerouslySetInnerHTML={{
                __html: JSON.stringify(schema),
              }}
            />
          ) : null}

          <div style={{ marginTop: "1rem", display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: "1rem" }}>
            {room?.photos?.length ? (
              <div className="card" style={{ padding: "1rem", gridColumn: "span 12" }}>
                <div>
                  <RoomCarousel photos={room.photos} altBase={room.name} intervalMs={5000} />
                </div>
              </div>
            ) : null}

            <div className="card" style={{ padding: "1rem", gridColumn: "span 12" }}>
              <div className="label">{tr.dates}</div>
              <div style={{ marginTop: "0.35rem", display: "flex", gap: "0.55rem", alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontWeight: 900 }}>{calMonth}</span>
                {canGoPrev ? (
                  <Link
                    href={`/rooms/${encodeURIComponent(slug)}?month=${encodeURIComponent(prevMonth)}&adults=${encodeURIComponent(
                      String(q.adults)
                    )}&children=${encodeURIComponent(String(q.children))}&lang=${encodeURIComponent(lang)}`}
                    className="btn"
                    style={{ textDecoration: "none" }}
                  >
                    {lang === "en" ? "Previous month" : "Prosli mjesec"}
                  </Link>
                ) : (
                  <button className="btn" type="button" disabled>
                    {lang === "en" ? "Previous month" : "Prosli mjesec"}
                  </button>
                )}
                <Link
                  href={`/rooms/${encodeURIComponent(slug)}?month=${encodeURIComponent(nextMonth)}&adults=${encodeURIComponent(
                    String(q.adults)
                  )}&children=${encodeURIComponent(String(q.children))}&lang=${encodeURIComponent(lang)}`}
                  className="btn btn-primary"
                  style={{ textDecoration: "none" }}
                >
                  {lang === "en" ? "Next month" : "Sljedeci mjesec"}
                </Link>
              </div>
            </div>
            <div className="card" style={{ padding: "1rem", gridColumn: "span 12" }}>
              <div style={{ fontWeight: 900 }}>{tr.calendar_2m}</div>
              {!roomCalendars.length ? (
                <div style={{ marginTop: "0.45rem", color: "var(--muted)" }}>
                  {lang === "en" ? "Calendar currently unavailable." : "Kalendar trenutno nije dostupan."}
                </div>
              ) : (
                <div style={{ marginTop: "0.75rem", display: "grid", gap: "0.9rem" }}>
                  {roomCalendars.map((cal) => (
                    <div
                      key={cal.roomId}
                      style={{
                        border: "1px solid rgba(24, 22, 21, 0.12)",
                        borderRadius: "12px",
                        padding: "0.7rem",
                        background: "rgba(255,255,255,0.55)",
                      }}
                    >
                      <div style={{ fontWeight: 800 }}>
                        {lang === "en" ? "Room" : "Soba"} {cal.roomCode} · {calMonth}
                      </div>
                      <div
                        style={{
                          marginTop: "0.55rem",
                          display: "grid",
                          gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
                          gap: "0.35rem",
                        }}
                      >
                        {cal.days.map((d) => {
                          const dayNum = d.date.slice(-2);
                          return (
                            <div
                              key={`${cal.roomId}-${d.date}`}
                              title={`${d.date} · ${
                                d.available
                                  ? lang === "en"
                                    ? "Available"
                                    : "Dostupno"
                                  : lang === "en"
                                  ? "Booked"
                                  : "Zauzeto"
                              }${d.nightly ? ` · ${d.nightly} ${d.currency}` : ""}`}
                              style={{
                                borderRadius: "8px",
                                padding: "0.35rem 0.25rem",
                                textAlign: "center",
                                fontSize: "0.78rem",
                                background: d.available ? "rgba(20,130,70,0.12)" : "rgba(170,45,45,0.12)",
                                border: `1px solid ${d.available ? "rgba(20,130,70,0.35)" : "rgba(170,45,45,0.35)"}`,
                              }}
                            >
                              <div style={{ fontWeight: 800 }}>{dayNum}</div>
                              <div style={{ marginTop: "0.08rem", fontSize: "0.64rem", color: "var(--muted)" }}>
                                {d.nightly ? `${d.nightly}` : "-"}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        </div>
      </section>
    </Shell>
  );
}
