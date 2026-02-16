import type { MetadataRoute } from "next";

import { getPublicRooms } from "../lib/api";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://booking.uzorita.hr").replace(/\/+$/, "");

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const entries: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/?lang=hr`, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/?lang=en`, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/search?lang=hr`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/search?lang=en`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
  ];

  const langs = ["hr", "en"] as const;
  const seen = new Set<string>();

  for (const lang of langs) {
    try {
      const rooms = await getPublicRooms({ lang });
      for (const room of rooms) {
        const key = `${room.slug}:${lang}`;
        if (seen.has(key)) continue;
        seen.add(key);
        entries.push({
          url: `${SITE_URL}/rooms/${encodeURIComponent(room.slug)}?lang=${lang}`,
          lastModified: now,
          changeFrequency: "weekly",
          priority: 0.8,
        });
      }
    } catch {
      // Keep sitemap available even if the upstream API is temporarily unavailable.
    }
  }

  return entries;
}
