export type Lang = "hr" | "en";

const SUPPORTED: Lang[] = ["hr", "en"];

export function normalizeLang(raw: string | undefined | null): Lang | null {
  const v = (raw || "").trim().toLowerCase();
  if (!v) return null;
  const short = v.split("-", 1)[0] as Lang;
  return (SUPPORTED as string[]).includes(short) ? (short as Lang) : null;
}

export function pickLang(opts: {
  queryLang?: string | null;
  cookieLang?: string | null;
  acceptLanguage?: string | null;
  fallback?: Lang;
}): Lang {
  const fallback = opts.fallback ?? "hr";
  const q = normalizeLang(opts.queryLang);
  if (q) return q;
  const c = normalizeLang(opts.cookieLang);
  if (c) return c;
  const h = (opts.acceptLanguage || "").split(",")[0];
  const a = normalizeLang(h);
  if (a) return a;
  return fallback;
}

export function t(lang: Lang) {
  const hr = {
    home: "Pocetna",
    search: "Pretraga",
    back_to_search: "Nazad na pretragu",
    change: "Promijeni",
    dates: "Datumi",
    guests: "Gosti",
    adults: "odrasli",
    children: "djeca",
    room: "Soba",
    unknown_slug: "Nepoznat slug.",
    calendar_2m: "Kalendar (2 mjeseca)",
    photos: "Fotografije",
    api_public: "API (Public)",
    api_public_blurb_1: "Endpointi su sada dokumentirani u OpenAPI i vide se u api/docs pod tagom Public.",
    api_public_blurb_2:
      "Dodano u public_views.py: opisi (summary/description), operationId, parametri ?lang= i header Accept-Language.",
    api_public_blurb_3: "Provjera na schemi: GET /api/public/rooms/ i GET /api/public/rooms/{id}/.",
    api_public_blurb_4: "Mozes otvoriti https://rooms.uzorita.hr/api/docs/ i filtrirati po tagu Public.",
    hold: "Drzi (HOLD)",
    hold_disabled_hint: "HOLD dolazi nakon availability API-ja.",
  };

  const en = {
    home: "Home",
    search: "Search",
    back_to_search: "Back to search",
    change: "Change",
    dates: "Dates",
    guests: "Guests",
    adults: "adults",
    children: "children",
    room: "Room",
    unknown_slug: "Unknown slug.",
    calendar_2m: "Calendar (2 months)",
    photos: "Photos",
    api_public: "API (Public)",
    api_public_blurb_1: "Endpoints are documented in OpenAPI and visible in api/docs under the Public tag.",
    api_public_blurb_2:
      "Added in public_views.py: summary/description, operationId, ?lang= and Accept-Language header parameters.",
    api_public_blurb_3: "Check schema: GET /api/public/rooms/ and GET /api/public/rooms/{id}/.",
    api_public_blurb_4: "Open https://rooms.uzorita.hr/api/docs/ and filter by Public tag.",
    hold: "Hold (HOLD)",
    hold_disabled_hint: "HOLD comes after the availability API.",
  };

  return lang === "en" ? en : hr;
}

