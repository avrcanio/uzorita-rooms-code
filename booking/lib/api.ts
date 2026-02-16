export type PublicRoomPhoto = {
  id: number;
  url: string;
  url_small?: string;
  caption: string;
  sort_order: number;
};

export type PublicRoom = {
  id: number;
  code: string;
  slug: string;
  name: string;
  subtitle: string;
  beds: string;
  highlights: string[];
  views: string[];
  amenities: string[];
  primary_photo_url: string;
  photos: PublicRoomPhoto[];
  size_m2: number | null;
};

export type SurroundingItem = { name: string; distance_m: number };
export type PrimaryRoomPhoto = {
  room_type_id: number;
  room_type_code: string;
  room_type_slug: string;
  url: string;
};

export type PublicProperty = {
  id: number;
  code: string;
  name: string;
  about: string;
  company_info: string;
  neighborhood: string;
  most_popular_facilities: string[];
  surroundings: Record<string, SurroundingItem[]>;
  address: string;
  primary_room_photos: PrimaryRoomPhoto[];
  latitude: string | null;
  longitude: string | null;
  whatsapp_phone: string;
  google_analytics_measurement_id: string;
  google_maps_place_id: string;
  google_maps_url: string;
  google_maps_embed_url: string;
};

export type PublicAvailabilityRoom = {
  room_id: number;
  room_code: string;
  room_type_id: number;
  room_type_code: string;
  available: boolean;
  capacity: number;
  can_host_party: boolean;
  pricing: {
    currency: string;
    accommodation_total: string | null;
  };
};

export type PublicAvailabilityCombo = {
  code: string;
  rooms_count: number;
  allocation: Array<{
    room_id: number;
    room_code: string;
    adults: number;
    children: number;
  }>;
  pricing: {
    currency: string;
    accommodation_total: string | null;
  };
};

export type PublicAvailability = {
  checkin: string;
  checkout: string;
  nights: number;
  adults: number;
  children: number;
  rooms: PublicAvailabilityRoom[];
  combos: PublicAvailabilityCombo[];
};

export type PublicRoomCalendarDay = {
  date: string;
  available: boolean;
  pricing: {
    currency: string;
    accommodation_nightly: string | null;
  };
};

export type PublicRoomCalendar = {
  room_id: number;
  room_code: string;
  month: string;
  adults: number;
  children: number;
  days: PublicRoomCalendarDay[];
};

function apiBase(): string {
  const raw = (process.env.NEXT_PUBLIC_API_BASE || "").trim();
  return raw ? raw.replace(/\/+$/, "") : "https://rooms.uzorita.hr/api";
}

export async function getPublicRooms(opts?: { lang?: string }): Promise<PublicRoom[]> {
  const base = apiBase();
  const url = new URL(`${base}/public/rooms/`);
  if (opts?.lang) url.searchParams.set("lang", opts.lang);

  const res = await fetch(url.toString(), {
    // Availability/pricing will be dynamic later; keep this fresh for now.
    cache: "no-store",
    headers: { accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`public rooms fetch failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as PublicRoom[];
}

export async function getPublicProperty(opts?: { lang?: string }): Promise<PublicProperty> {
  const base = apiBase();
  const url = new URL(`${base}/public/property/`);
  if (opts?.lang) url.searchParams.set("lang", opts.lang);

  const res = await fetch(url.toString(), {
    cache: "no-store",
    headers: { accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`public property fetch failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as PublicProperty;
}

export async function getPublicAvailability(opts: {
  checkin: string;
  checkout: string;
  adults: number;
  children?: number;
}): Promise<PublicAvailability> {
  const base = apiBase();
  const url = new URL(`${base}/public/availability/`);
  url.searchParams.set("checkin", opts.checkin);
  url.searchParams.set("checkout", opts.checkout);
  url.searchParams.set("adults", String(opts.adults));
  url.searchParams.set("children", String(opts.children ?? 0));

  const res = await fetch(url.toString(), {
    cache: "no-store",
    headers: { accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`public availability fetch failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as PublicAvailability;
}

export async function getPublicRoomCalendar(opts: {
  roomId: number;
  month: string; // YYYY-MM
  adults?: number;
  children?: number;
}): Promise<PublicRoomCalendar> {
  const base = apiBase();
  const url = new URL(`${base}/public/rooms/${opts.roomId}/calendar/`);
  url.searchParams.set("month", opts.month);
  url.searchParams.set("adults", String(opts.adults ?? 2));
  url.searchParams.set("children", String(opts.children ?? 0));

  const res = await fetch(url.toString(), {
    cache: "no-store",
    headers: { accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`public room calendar fetch failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as PublicRoomCalendar;
}
