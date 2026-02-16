import Link from "next/link";
import { cookies, headers } from "next/headers";
import { Shell } from "../_components/Shell";
import { getPublicAvailability, getPublicRooms } from "../../lib/api";
import { parseSearchParams } from "../../lib/query";
import { pickLang, t } from "../../lib/i18n";

export default async function SearchPage(props: { searchParams: Promise<Record<string, string | string[]>> }) {
  const searchParams = await props.searchParams;
  const q = parseSearchParams(searchParams);

  // Rooms are already available via public API. Availability/pricing comes next.
  const cookieStore = await cookies();
  const headerStore = await headers();
  const cookieLang = cookieStore.get("booking_lang")?.value ?? null;
  const acceptLanguage = headerStore.get("accept-language");
  const lang = pickLang({
    queryLang: typeof searchParams.lang === "string" ? searchParams.lang : null,
    cookieLang,
    acceptLanguage,
    fallback: "hr",
  });
  const tr = t(lang);

  const roomTypes = await getPublicRooms({ lang });
  let availability;
  try {
    availability = await getPublicAvailability({
      checkin: q.checkin,
      checkout: q.checkout,
      adults: q.adults,
      children: q.children,
    });
  } catch {
    availability = {
      checkin: q.checkin,
      checkout: q.checkout,
      nights: 0,
      adults: q.adults,
      children: q.children,
      rooms: roomTypes.map((rt) => ({
        room_id: rt.id,
        room_code: rt.code,
        room_type_id: rt.id,
        room_type_code: rt.code,
        available: false,
        capacity: 0,
        can_host_party: false,
        pricing: { currency: "EUR", accommodation_total: null as string | null },
      })),
      combos: [],
    };
  }
  const roomTypeById = new Map(roomTypes.map((r) => [r.id, r]));
  const sortedRooms = [...availability.rooms].sort((a, b) => {
    const ap = Number.parseFloat(a.pricing?.accommodation_total ?? "");
    const bp = Number.parseFloat(b.pricing?.accommodation_total ?? "");
    const aNum = Number.isFinite(ap);
    const bNum = Number.isFinite(bp);
    if (aNum && bNum && ap !== bp) return ap - bp;
    if (aNum !== bNum) return aNum ? -1 : 1;
    return a.room_code.localeCompare(b.room_code);
  });

  return (
    <Shell active="search" lang={lang}>
      <section className="container" style={{ padding: "0.75rem 0 1.25rem" }}>
        <div className="card" style={{ padding: "1.25rem" }}>
          <form action="/search" method="get" style={{ display: "flex", gap: "0.8rem", flexWrap: "wrap", alignItems: "end" }}>
            <div>
              <div className="label">{tr.dates}</div>
              <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", alignItems: "center", marginTop: "0.2rem" }}>
                <input
                  type="date"
                  name="checkin"
                  defaultValue={q.checkin}
                  className="input"
                  style={{ minWidth: "160px" }}
                  required
                />
                <span style={{ color: "var(--muted)", fontWeight: 700 }}>→</span>
                <input
                  type="date"
                  name="checkout"
                  defaultValue={q.checkout}
                  className="input"
                  style={{ minWidth: "160px" }}
                  required
                />
              </div>
            </div>
            <div>
              <div className="label">{tr.guests}</div>
              <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.2rem" }}>
                <input
                  type="number"
                  name="adults"
                  defaultValue={q.adults}
                  min={1}
                  max={10}
                  className="input"
                  style={{ width: "92px" }}
                  aria-label={tr.adults}
                  required
                />
                <input
                  type="number"
                  name="children"
                  defaultValue={q.children}
                  min={0}
                  max={10}
                  className="input"
                  style={{ width: "92px" }}
                  aria-label={tr.children}
                  required
                />
              </div>
            </div>
            <div style={{ marginLeft: "auto" }}>
              <input type="hidden" name="lang" value={lang} />
              <button type="submit" className="btn btn-primary">
                {lang === "en" ? "Search" : "Pretrazi"}
              </button>
            </div>
          </form>
        </div>
      </section>

      <section className="container" style={{ paddingBottom: "1rem" }}>
        <div className="card" style={{ padding: "1.25rem" }}>
          <div style={{ fontWeight: 900 }}>{lang === "en" ? "Recommended combos" : "Preporucene kombinacije (combo)"}</div>
          {!availability.combos.length ? (
            <div style={{ marginTop: "0.45rem", color: "var(--muted)" }}>
              {lang === "en" ? "No combo recommendation for selected dates." : "Nema combo preporuka za odabrane datume."}
            </div>
          ) : (
            <div style={{ marginTop: "0.75rem", display: "grid", gap: "0.65rem" }}>
              {availability.combos.map((combo) => (
                <div
                  key={combo.code}
                  style={{
                    border: "1px solid rgba(24, 22, 21, 0.1)",
                    borderRadius: "12px",
                    padding: "0.7rem 0.8rem",
                    background: "rgba(255,255,255,0.55)",
                  }}
                >
                  <div style={{ fontWeight: 800 }}>
                    {combo.code.toUpperCase()} · {combo.rooms_count} {lang === "en" ? "room(s)" : "soba"}
                  </div>
                  <div style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
                    {combo.allocation
                      .map((a) => `${a.room_code} (${a.adults}${lang === "en" ? "A" : "O"} + ${a.children}${lang === "en" ? "C" : "D"})`)
                      .join(" • ")}
                  </div>
                  <div style={{ marginTop: "0.25rem", fontWeight: 700 }}>
                    {lang === "en" ? "Total" : "Ukupno"}: {combo.pricing.accommodation_total} {combo.pricing.currency}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="container" style={{ paddingBottom: "1.5rem" }}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sortedRooms.map((room) => {
            const roomType = roomTypeById.get(room.room_type_id);
            const href = roomType
              ? `/rooms/${roomType.slug}?checkin=${encodeURIComponent(q.checkin)}&checkout=${encodeURIComponent(
              q.checkout
            )}&adults=${encodeURIComponent(String(q.adults))}&children=${encodeURIComponent(
                  String(q.children)
                )}&lang=${encodeURIComponent(lang)}`
              : "#";
            const total = room.pricing?.accommodation_total;
            const cardMuted = !room.available || !room.can_host_party;

            return (
              <div
                key={room.room_id}
                className="card"
                style={{ padding: "1.25rem", opacity: cardMuted ? 0.65 : 1, borderStyle: room.available ? "solid" : "dashed" }}
              >
                {roomType?.primary_photo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={roomType.primary_photo_url.replace("http://rooms.uzorita.hr/", "https://rooms.uzorita.hr/")}
                    alt={roomType.name}
                    loading="lazy"
                    style={{
                      width: "100%",
                      height: "190px",
                      objectFit: "cover",
                      borderRadius: "14px",
                      border: "1px solid rgba(24, 22, 21, 0.1)",
                      marginBottom: "0.9rem",
                      display: "block",
                    }}
                  />
                ) : null}

                <div style={{ display: "flex", gap: "1rem", alignItems: "baseline", flexWrap: "wrap" }}>
                  <div style={{ fontFamily: "var(--font-fraunces)", fontSize: "1.35rem" }}>
                    {roomType?.name || room.room_type_code} ({room.room_code})
                  </div>
                  <div style={{ color: "var(--muted)", fontWeight: 700 }}>{roomType?.beds || room.room_type_code}</div>
                </div>

                <div style={{ marginTop: "0.55rem", color: "var(--muted)" }}>
                  {roomType?.subtitle || (roomType?.highlights?.length ? roomType.highlights.join(" • ") : "")}
                </div>

                <div style={{ marginTop: "0.55rem", display: "flex", gap: "0.8rem", flexWrap: "wrap", alignItems: "center" }}>
                  <div
                    style={{
                      fontSize: "0.85rem",
                      fontWeight: 800,
                      color: room.available && room.can_host_party ? "#0f7a38" : "#8f3f3f",
                    }}
                  >
                    {room.available && room.can_host_party
                      ? lang === "en"
                        ? "Available"
                        : "Dostupno"
                      : lang === "en"
                      ? "Unavailable"
                      : "Nedostupno"}
                  </div>
                  <div style={{ color: "var(--muted)", fontSize: "0.92rem" }}>
                    {lang === "en" ? "Total accommodation" : "Smjestaj ukupno"}:{" "}
                    <strong>
                      {total ? `${total} ${room.pricing.currency}` : lang === "en" ? "N/A" : "N/A"}
                    </strong>
                  </div>
                </div>

                <div style={{ marginTop: "0.9rem", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                  <Link
                    href={href}
                    className="btn btn-primary"
                    style={{
                      textDecoration: "none",
                      pointerEvents: roomType && room.available && room.can_host_party ? "auto" : "none",
                      opacity: roomType && room.available && room.can_host_party ? 1 : 0.5,
                    }}
                    aria-disabled={!(roomType && room.available && room.can_host_party)}
                  >
                    {lang === "en" ? "View room" : "Pogledaj sobu"}
                  </Link>
                  <button className="btn" disabled type="button" title={tr.hold_disabled_hint}>
                    {tr.hold}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

    </Shell>
  );
}
