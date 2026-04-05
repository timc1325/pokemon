"use client";

import { useState, useEffect, useMemo } from "react";
import { User } from "firebase/auth";
import { useCollection } from "@/hooks/useCollection";
import { Pokemon, ToggleMode } from "@/lib/types";
import { applyFilters } from "@/lib/pokemon";
import {
  CARDS_PER_PAGE,
  FILTER_TAGS,
  SORT_OPTIONS,
  GENERATIONS,
} from "@/lib/constants";
import Navbar from "./Navbar";
import PokemonCard from "./PokemonCard";
import ShinyRates from "./ShinyRates";

interface AppShellProps {
  user: User;
}

export default function AppShell({ user }: AppShellProps) {
  const { collection, loading: collLoading, toggle } = useCollection(user.uid);

  const [pokemon, setPokemon] = useState<Pokemon[]>([]);
  const [releasedIds, setReleasedIds] = useState<Set<number>>(new Set());
  const [dataLoading, setDataLoading] = useState(true);

  const [tab, setTab] = useState<"collection" | "rates">("collection");
  const [search, setSearch] = useState("");
  const [filterTags, setFilterTags] = useState<string[]>(["Released"]);
  const [generation, setGeneration] = useState("All");
  const [sortOption, setSortOption] = useState("Pokédex Order");
  const [toggleMode, setToggleMode] = useState<ToggleMode>("off");
  const [rootOnly, setRootOnly] = useState(false);
  const [showFamily, setShowFamily] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    Promise.all([
      fetch("/pokemon.json").then((r) => r.json()),
      fetch("/api/released").then((r) => r.json()),
    ]).then(([pkmn, released]) => {
      setPokemon(pkmn);
      setReleasedIds(new Set(released as number[]));
      setDataLoading(false);
    });
  }, []);

  const filtered = useMemo(
    () =>
      applyFilters(
        pokemon,
        collection,
        releasedIds,
        search,
        filterTags,
        generation,
        sortOption,
        rootOnly,
        showFamily
      ),
    [
      pokemon,
      collection,
      releasedIds,
      search,
      filterTags,
      generation,
      sortOption,
      rootOnly,
      showFamily,
    ]
  );

  const totalPages = Math.max(1, Math.ceil(filtered.length / CARDS_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * CARDS_PER_PAGE;
  const pageEnd = Math.min(safePage * CARDS_PER_PAGE, filtered.length);
  const pageItems = filtered.slice(pageStart, pageEnd);

  const shundoCount = useMemo(
    () =>
      pokemon.filter((p) => collection[p.id]?.shundo).length,
    [pokemon, collection]
  );
  const luckyCount = useMemo(
    () =>
      pokemon.filter((p) => collection[p.id]?.lucky).length,
    [pokemon, collection]
  );

  useEffect(() => {
    setPage(1);
  }, [search, filterTags, generation, sortOption, rootOnly, showFamily]);

  const toggleFilter = (tag: string) => {
    setFilterTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  if (dataLoading || collLoading) {
    return (
      <div className="min-h-screen">
        <Navbar user={user} />
        <div className="flex items-center justify-center h-64">
          <div className="text-[#6a6a8a] text-sm">Loading collection…</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Navbar user={user} />

      {/* Tabs */}
      <div className="flex gap-1 px-4 sm:px-6 pt-4">
        {(["collection", "rates"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-[0.1em] rounded-t-lg transition-colors ${
              tab === t
                ? "bg-white/[0.04] text-[#d0d0e4] border border-white/[0.06] border-b-transparent"
                : "text-[#4a4a6a] hover:text-[#8a8aaa]"
            }`}
          >
            {t === "collection" ? "Collection" : "Live Rates"}
          </button>
        ))}
      </div>

      <div className="border-t border-white/[0.04]" />

      {tab === "collection" ? (
        <div className="px-4 sm:px-6 py-4 space-y-4">
          {/* Controls Row 1 */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search Pokémon…"
              className="col-span-2 sm:col-span-1 px-3 py-2 rounded-lg text-xs
                bg-white/[0.03] border border-white/[0.06] text-[#d0d0e4]
                placeholder-[#3a3a54] outline-none focus:border-purple-500/30"
            />
            <select
              value={generation}
              onChange={(e) => setGeneration(e.target.value)}
              className="px-3 py-2 rounded-lg text-xs bg-white/[0.03] border border-white/[0.06]
                text-[#d0d0e4] outline-none appearance-none cursor-pointer"
            >
              {GENERATIONS.map((g) => (
                <option key={g} value={g} className="bg-[#16161e]">
                  {g}
                </option>
              ))}
            </select>
            <select
              value={sortOption}
              onChange={(e) => setSortOption(e.target.value)}
              className="px-3 py-2 rounded-lg text-xs bg-white/[0.03] border border-white/[0.06]
                text-[#d0d0e4] outline-none appearance-none cursor-pointer"
            >
              {SORT_OPTIONS.map((s) => (
                <option key={s} value={s} className="bg-[#16161e]">
                  {s}
                </option>
              ))}
            </select>
            <select
              value={toggleMode}
              onChange={(e) => setToggleMode(e.target.value as ToggleMode)}
              className="px-3 py-2 rounded-lg text-xs bg-white/[0.03] border border-white/[0.06]
                text-[#d0d0e4] outline-none appearance-none cursor-pointer"
            >
              <option value="off" className="bg-[#16161e]">Toggle: Off</option>
              <option value="shundo" className="bg-[#16161e]">Toggle: Shundo</option>
              <option value="lucky" className="bg-[#16161e]">Toggle: Lucky</option>
            </select>
          </div>

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
            <label className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] text-[#4a4a6a] cursor-pointer">
              <input
                type="checkbox"
                checked={rootOnly}
                onChange={(e) => setRootOnly(e.target.checked)}
                className="accent-purple-500 w-3 h-3"
              />
              Root only
            </label>
            <label className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] text-[#4a4a6a] cursor-pointer">
              <input
                type="checkbox"
                checked={showFamily}
                onChange={(e) => setShowFamily(e.target.checked)}
                className="accent-purple-500 w-3 h-3"
              />
              Full family
            </label>
          </div>

          {/* Stats + Pagination */}
          <div className="flex items-end justify-between">
            <div className="flex gap-8">
              <div>
                <div className="text-xl font-bold text-[#e0e0f0] leading-none">
                  {filtered.length}
                </div>
                <div className="text-[8px] font-semibold uppercase tracking-[0.12em] text-[#2e2e42] mt-1">
                  Showing
                </div>
              </div>
              <div>
                <div className="text-xl font-bold text-[#e0e0f0] leading-none">
                  {shundoCount}
                </div>
                <div className="text-[8px] font-semibold uppercase tracking-[0.12em] text-[#2e2e42] mt-1">
                  Shundo
                </div>
              </div>
              <div>
                <div className="text-xl font-bold text-[#e0e0f0] leading-none">
                  {luckyCount}
                </div>
                <div className="text-[8px] font-semibold uppercase tracking-[0.12em] text-[#2e2e42] mt-1">
                  Lucky
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="px-2.5 py-1 rounded-md text-xs text-[#6a6a8a] bg-white/[0.03]
                  border border-white/[0.06] disabled:opacity-30 hover:bg-white/[0.06] transition-colors"
              >
                ‹
              </button>
              <span className="text-[10px] text-[#4a4a6a] tabular-nums min-w-[80px] text-center">
                {pageStart + 1}–{pageEnd} of {filtered.length}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="px-2.5 py-1 rounded-md text-xs text-[#6a6a8a] bg-white/[0.03]
                  border border-white/[0.06] disabled:opacity-30 hover:bg-white/[0.06] transition-colors"
              >
                ›
              </button>
            </div>
          </div>

          {/* Grid */}
          <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
            {pageItems.map((p) => (
              <PokemonCard
                key={p.id}
                pokemon={p}
                collection={collection}
                toggleMode={toggleMode}
                onToggle={toggle}
              />
            ))}
          </div>

          {/* Bottom pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="px-3 py-1.5 rounded-md text-xs text-[#6a6a8a] bg-white/[0.03]
                  border border-white/[0.06] disabled:opacity-30 hover:bg-white/[0.06] transition-colors"
              >
                ← Previous
              </button>
              <span className="px-3 py-1.5 text-[10px] text-[#4a4a6a] tabular-nums flex items-center">
                Page {safePage} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="px-3 py-1.5 rounded-md text-xs text-[#6a6a8a] bg-white/[0.03]
                  border border-white/[0.06] disabled:opacity-30 hover:bg-white/[0.06] transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </div>
      ) : (
        <ShinyRates pokemon={pokemon} collection={collection} releasedIds={releasedIds} />
      )}
    </div>
  );
}
