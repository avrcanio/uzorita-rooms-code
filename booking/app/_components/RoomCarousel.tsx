"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Photo = {
  id: number;
  url: string;
  url_small?: string;
  caption?: string;
  sort_order?: number;
};

function toHttps(u: string): string {
  return (u || "").replace("http://rooms.uzorita.hr/", "https://rooms.uzorita.hr/");
}

export function RoomCarousel({
  photos,
  altBase,
  intervalMs = 5000,
}: {
  photos: Photo[];
  altBase: string;
  intervalMs?: number;
}) {
  const items = useMemo(() => {
    const xs = (photos || []).slice().sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
    return xs.filter((p) => (p?.url || "").trim());
  }, [photos]);

  const [activeIdx, setActiveIdx] = useState(0);
  const pausedRef = useRef(false);
  const bumpRef = useRef(0);

  useEffect(() => {
    setActiveIdx(0);
  }, [items.length]);

  useEffect(() => {
    if (items.length <= 1) return;
    const id = window.setInterval(() => {
      if (pausedRef.current) return;
      setActiveIdx((i) => (i + 1) % items.length);
    }, Math.max(1000, intervalMs));
    return () => window.clearInterval(id);
  }, [items.length, intervalMs, bumpRef.current]);

  if (!items.length) return null;

  const active = items[Math.min(activeIdx, items.length - 1)];
  const activeUrl = toHttps(active.url);

  return (
    <div
      onMouseEnter={() => {
        pausedRef.current = true;
      }}
      onMouseLeave={() => {
        pausedRef.current = false;
      }}
    >
      <div
        style={{
          borderRadius: "14px",
          overflow: "hidden",
          border: "1px solid rgba(24, 22, 21, 0.12)",
          background: "rgba(255, 255, 255, 0.6)",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={active.id}
          src={activeUrl}
          alt={active.caption?.trim() || altBase}
          loading="eager"
          style={{ width: "100%", height: "420px", objectFit: "cover", display: "block" }}
        />
      </div>

      {items.length > 1 ? (
        <div style={{ marginTop: "0.85rem", display: "flex", gap: "0.6rem", overflowX: "auto", paddingBottom: "0.1rem" }}>
          {items.map((p, idx) => {
            const thumb = toHttps((p.url_small || p.url) as string);
            const isActive = idx === activeIdx;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setActiveIdx(idx);
                  // Force interval effect to restart from the new selection.
                  bumpRef.current += 1;
                }}
                aria-label={`Photo ${idx + 1}`}
                title={p.caption?.trim() || `Photo ${idx + 1}`}
                style={{
                  border: isActive ? "2px solid rgba(46, 122, 120, 0.85)" : "1px solid rgba(24, 22, 21, 0.16)",
                  background: "rgba(255, 255, 255, 0.7)",
                  borderRadius: "12px",
                  padding: "0.2rem",
                  cursor: "pointer",
                  flex: "0 0 auto",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={thumb}
                  alt=""
                  loading="lazy"
                  style={{
                    width: "84px",
                    height: "60px",
                    objectFit: "cover",
                    display: "block",
                    borderRadius: "10px",
                  }}
                />
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

