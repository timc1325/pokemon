import { Pokemon, UserCollection } from "./types";

export function getImageUrl(id: number): string {
  return `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${id}.png`;
}

export function getFallbackUrl(id: number): string {
  return `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${id}.png`;
}

export function applyFilters(
  pokemon: Pokemon[],
  collection: UserCollection,
  releasedIds: Set<number>,
  search: string,
  filterTags: string[],
  generation: string,
  sortOption: string,
  rootOnly: boolean,
  showFamily: boolean
): Pokemon[] {
  let filtered = [...pokemon];

  if (search) {
    const q = search.toLowerCase();
    const matched = filtered.filter((p) =>
      p.name.toLowerCase().includes(q)
    );
    if (showFamily && matched.length > 0) {
      const families = new Set(matched.map((p) => p.familyId));
      filtered = filtered.filter((p) => families.has(p.familyId));
    } else {
      filtered = matched;
    }
  }

  for (const tag of filterTags) {
    switch (tag) {
      case "Released":
        filtered = filtered.filter((p) => releasedIds.has(p.id));
        break;
      case "Not Released":
        filtered = filtered.filter((p) => !releasedIds.has(p.id));
        break;
      case "Shundo":
        filtered = filtered.filter((p) => collection[p.id]?.shundo);
        break;
      case "Not Shundo":
        filtered = filtered.filter((p) => !collection[p.id]?.shundo);
        break;
      case "Lucky":
        filtered = filtered.filter((p) => collection[p.id]?.lucky);
        break;
      case "Not Lucky":
        filtered = filtered.filter((p) => !collection[p.id]?.lucky);
        break;
      case "Tradeable":
        filtered = filtered.filter((p) => p.tradeable);
        break;
      case "Untradeable":
        filtered = filtered.filter((p) => !p.tradeable);
        break;
      case "Legendary":
        filtered = filtered.filter((p) => p.legendary);
        break;
      case "Not Legendary":
        filtered = filtered.filter((p) => !p.legendary);
        break;
    }
  }

  if (generation !== "All") {
    const gen = parseInt(generation.split(" ")[1]);
    filtered = filtered.filter((p) => p.generation === gen);
  }

  if (rootOnly) {
    filtered = filtered.filter((p) => p.id === p.rootId);
  }

  switch (sortOption) {
    case "Alphabetical":
      filtered.sort((a, b) => a.name.localeCompare(b.name));
      break;
    case "Shundo First":
      filtered.sort((a, b) => {
        const diff =
          (collection[b.id]?.shundo ? 1 : 0) -
          (collection[a.id]?.shundo ? 1 : 0);
        return diff || a.id - b.id;
      });
      break;
    case "Lucky First":
      filtered.sort((a, b) => {
        const diff =
          (collection[b.id]?.lucky ? 1 : 0) -
          (collection[a.id]?.lucky ? 1 : 0);
        return diff || a.id - b.id;
      });
      break;
    case "Legendary First":
      filtered.sort((a, b) => {
        const diff = (b.legendary ? 1 : 0) - (a.legendary ? 1 : 0);
        return diff || a.id - b.id;
      });
      break;
    default:
      filtered.sort((a, b) => a.id - b.id);
  }

  return filtered;
}
