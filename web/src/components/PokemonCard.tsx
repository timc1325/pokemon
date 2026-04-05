"use client";

import { Pokemon, UserCollection, ToggleMode } from "@/lib/types";
import { getImageUrl, getFallbackUrl } from "@/lib/pokemon";
import { FALLBACK_IMAGE } from "@/lib/constants";

interface PokemonCardProps {
  pokemon: Pokemon;
  collection: UserCollection;
  toggleMode: ToggleMode;
  onToggle: (pokemonId: number, field: "shundo" | "lucky") => void;
}

export default function PokemonCard({
  pokemon,
  collection,
  toggleMode,
  onToggle,
}: PokemonCardProps) {
  const entry = collection[pokemon.id] || { shundo: false, lucky: false };
  const isActive =
    toggleMode !== "off" && entry[toggleMode as "shundo" | "lucky"];

  const canToggle =
    toggleMode !== "off" &&
    (toggleMode !== "lucky" || pokemon.tradeable);

  const handleClick = () => {
    if (canToggle) {
      onToggle(pokemon.id, toggleMode as "shundo" | "lucky");
    }
  };

  return (
    <div
      onClick={handleClick}
      className={`
        rounded-[10px] p-3 pb-2 text-center transition-all duration-200
        border min-h-[110px] flex flex-col items-center
        ${canToggle ? "cursor-pointer" : ""}
        ${
          isActive
            ? "border-purple-500/25 bg-purple-500/[0.05] shadow-[0_0_20px_rgba(124,92,252,0.06)]"
            : "border-white/[0.025] bg-white/[0.018] hover:bg-white/[0.04] hover:border-white/[0.06]"
        }
        hover:-translate-y-0.5 hover:shadow-lg
      `}
    >
      <img
        src={getImageUrl(pokemon.id)}
        alt={pokemon.name}
        width={48}
        height={48}
        className="object-contain drop-shadow-[0_3px_8px_rgba(0,0,0,0.4)] transition-transform hover:scale-105"
        loading="lazy"
        onError={(e) => {
          const img = e.target as HTMLImageElement;
          const fb = getFallbackUrl(pokemon.id);
          if (img.src !== fb && img.src !== FALLBACK_IMAGE) {
            img.src = fb;
            img.onerror = () => {
              img.src = FALLBACK_IMAGE;
            };
          }
        }}
      />
      <div className="mt-1.5 text-[10px] font-semibold text-[#d0d0e4] leading-tight">
        {pokemon.name}
      </div>
      <div className="mt-0.5 text-[8.5px] font-medium text-[#2e2e42]">
        #{pokemon.id}
      </div>
      <div className="mt-1 min-h-[14px] leading-[1.8] flex flex-wrap justify-center gap-0.5">
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
        {!pokemon.tradeable && (
          <span className="inline-block text-[7px] font-semibold tracking-wide px-1.5 py-px rounded-sm uppercase bg-white/[0.04] text-[#404058]">
            Untradeable
          </span>
        )}
        {pokemon.legendary && (
          <span className="inline-block text-[7px] font-semibold tracking-wide px-1.5 py-px rounded-sm uppercase bg-yellow-500/[0.12] text-[#e0c050]">
            Legendary
          </span>
        )}
      </div>
      {canToggle && (
        <div
          className={`mt-1.5 w-full text-[9px] font-medium py-1 rounded-md transition-colors ${
            isActive
              ? "bg-purple-500/20 text-purple-300"
              : "bg-white/[0.03] text-[#4a4a6a] hover:bg-white/[0.06]"
          }`}
        >
          {isActive ? "✓" : "○"} {toggleMode === "shundo" ? "Shundo" : "Lucky"}
        </div>
      )}
    </div>
  );
}
