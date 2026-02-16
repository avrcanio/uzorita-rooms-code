export type RoomInfo = {
  id: string;
  slug: string;
  name: string;
  capacityLabel: string;
  summary: string;
};

export const ROOMS: RoomInfo[] = [
  {
    id: "r1",
    slug: "kapa",
    name: "Kapa",
    capacityLabel: "2 osobe",
    summary: "Topla, mirna soba za dvoje. Direktno bookanje bez iznenadenja.",
  },
  {
    id: "r2",
    slug: "maslina",
    name: "Maslina",
    capacityLabel: "2–3 osobe",
    summary: "Za par ili malu obitelj. Fokus na komforu i svjetlu.",
  },
  {
    id: "r3",
    slug: "bura",
    name: "Bura",
    capacityLabel: "2 osobe",
    summary: "Cist, brz, prozracan vibe. Idealno za kratke boravke.",
  },
  {
    id: "r4",
    slug: "sol",
    name: "Sol",
    capacityLabel: "2–4 osobe",
    summary: "Vise prostora, fleksibilno za obitelj ili prijatelje.",
  },
  {
    id: "r5",
    slug: "val",
    name: "Val",
    capacityLabel: "2 osobe",
    summary: "Mirno mjesto za reset. Minimalno, ali sve sto treba.",
  },
];

export function getRoomBySlug(slug: string): RoomInfo | undefined {
  return ROOMS.find((r) => r.slug === slug);
}

