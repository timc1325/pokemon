"use client";

import { useState, useEffect, useMemo } from "react";
import { Pokemon, UserCollection, ShinyRateEntry } from "@/lib/types";
import { getImageUrl, getFallbackUrl } from "@/lib/pokemon";
import { FALLBACK_IMAGE, FILTER_TAGS } from "@/lib/constants";

interface ShinyRatesProps {
  pokemon: Pokemon[];
  collection: UserCollection;
  releasedIds: Set<number>;
}

export default function ShinyRates({
  pokemon,
  collection,
  releasedIds,
}: ShinyRatesProps) {
  const [rates, setRates] = useState<ShinyRateEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTags, setFilterTags] = useState<string[]>(["Not Shundo"]);

  useEffect(() => {
    fetch("/api/shiny-rates")
      .then((r) => r.json())
      .then((data: ShinyRateEntry[]) => {
        setRates(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const pokemonMap = useMemo(() => {
    const map = new Map<number, Pokemon>();
    pokemon.forEach((p) => map.set(p.id, p));
    return map;
  }, [pokemon]);

  const filtered = useMemo(() => {
    let merged = rates
      .map((r) => ({
        ...r,
        pokemon: pokemonMap.get(r.pokemonId),
      }))
      .filter((r) => r.pokemon != null);

    for (const tag of filterTags) {
      switch (tag) {
        case "Released":
          merged = merged.filter((r) => releasedIds.has(r.pokemonId));
          break;
        case "Not Released":
          merged = merged.filter((r) => !releasedIds.has(r.pokemonId));
          break;
        case "Shundo":
          merged = merged.filter((r) => collection[r.pokemonId]?.shundo);
          break;
        case "Not Shundo":
          merged = merged.filter((r) => !collection[r.pokemonId]?.shundo);
          break;
        case "Lucky":
          merged = merged.filter((r) => collection[r.pokemonId]?.lucky);
          break;
        case "Not Lucky":
          merged = merged.filter((r) => !collection[r.pokemonId]?.lucky);
          break;
        case "Tradeable":
          merged = merged.filter((r) => r.pokemon!.tradeable);
          break;
        case "Untradeable":
          merged = merged.filter((r) => !r.pokemon!.tradeable);
          break;
        case "Legendary":
          merged = merged.filter((r) => r.pokemon!.legendary);
          break;
        case "Not Legendary":
          merged = merged.filter((r) => !r.pokemon!.legendary);
          break;
      }
    }

    return merged.sort((a, b) => b.rateValue - a.rateValue);
  }, [rates, pokemonMap, collection, releasedIds, filterTags]);

  const toggleFilter = (tag: string) => {
    setFilterTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="text-[#6a6a8a] text-sm">Loading shiny rates…</div>
      </div>
    );
  }

  return (
    <div className="px-4 sm:px-6 py-4 space-y-4">
      {/* Filter chips */}
      <div className="flex flex-wrap gap-1.5">
        {FILTER_TAGS.map((tag) => (
          <button
            key={tag}
            onClick={() => toggleFilter(tag)}
            className={`px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors border ${
              filterTags.includes(tag)
                ? "bg-purple-500/20 text-purple-300 border-purple-500/30"
                : "bg-white/[0.02] text-[#4a4a6a] border-white/[0.04] hover:bg-white/[0.05]"
            }`}
          >
            {tag}
          </button>
        ))}
      </div>

      <div className="text-[10px] text-[#4a4a6a] font-medium">
        <b className="text-[#6a6a8a]">{filtered.length}</b> with live rates
      </div>

      {/* Rate cards grid */}
      <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
        {filtered.map((r) => {
          const p = r.pokemon!;
          const entry = collection[p.id] || { shundo: false, lucky: false };
          const isGreen = r.sampleSize >= 500 && r.rateValue >= 0.001;
          const isBlue =
            !isGreen && r.sampleSize * r.rateValue > 1 && r.rateValue >= 0.001;
          const accentColor = isGreen
            ? "rgba(16,185,129,0.25)"
            : isBlue
            ? "rgba(59,130,246,0.25)"
            : "rgba(255,255,255,0.025)";

          return (
            <div
              key={p.id}
              className="rounded-[10px] p-3 pb-2 text-center transition-all duration-200
                border border-white/[0.025] bg-white/[0.018] min-h-[120px]
                hover:bg-white/[0.04] hover:-translate-y-0.5 hover:shadow-lg"
              style={{ borderColor: accentColor }}
            >
              <img
                src={getImageUrl(p.id)}
                alt={p.name}
                width={44}
                height={44}
                className="mx-auto object-contain drop-shadow-[0_3px_8px_rgba(0,0,0,0.4)]"
                loading="lazy"
                onError={(e) => {
                  const img = e.target as HTMLImageElement;
                  const fb = getFallbackUrl(p.id);
                  if (img.src !== fb && img.src !== FALLBACK_IMAGE) {
                    img.src = fb;
                    img.onerror = () => {
                      img.src = FALLBACK_IMAGE;
                    };
                  }
                }}
              />
              <div className="mt-1.5 text-[10px] font-semibold text-[#d0d0e4] leading-tight">
                {p.name}
              </div>
              <div className="mt-0.5 text-[8.5px] font-medium text-[#2e2e42]">
                #{p.id}
              </div>
              <div className="mt-1 leading-[1.8] flex flex-wrap justify-center gap-0.5">
                <span
                  className="inline-block text-[7px] font-bold tracking-wide px-1.5 py-px rounded-sm uppercase"
                  style={{
                    background: accentColor,
                    color: isGreen
                      ? "#10b981"
                      : isBlue
                      ? "#3b82f6"
                      : "#6a6a8a",
                  }}
                >
                  {r.rate}
                </span>
                {entry.shundo && (
                  <span className="inline-block text-[7px] font-semibold tracking-wide px-1.5 py-px rounded-sm uppercase bg-purple-500/15 text-[#a090ff]">
                    Shundo
                  </span>
                )}
                {entry.lucky && (
                  <span className="inline-block text-[7px] font-semibold tracking-wide px-1.5 py-px rounded-sm uppercase bg-amber-500/15 text-[#ffc060]">
                    Lucky
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-[8px] text-[#222236] tracking-wide">
                n={r.sampleSize.toLocaleString()}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
