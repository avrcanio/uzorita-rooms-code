import type { AvailabilityQuery } from "./query";
import { ROOMS } from "./rooms";

export function mockAvailability(query: AvailabilityQuery) {
  // Deterministic-ish placeholder so the UI isn't boring.
  const seed = `${query.checkin}:${query.checkout}:${query.adults}:${query.children}`;
  const flip = (i: number) => (seed.length + i) % 3 !== 0;

  return {
    query,
    rooms: ROOMS.map((r, idx) => ({
      ...r,
      available: flip(idx),
      pricing: {
        accommodation_total: 0,
      },
    })),
    combos: [],
  };
}

