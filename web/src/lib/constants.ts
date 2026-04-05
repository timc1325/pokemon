export const CARDS_PER_PAGE = 80;

export const FALLBACK_IMAGE =
  "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/0.png";

export const FILTER_TAGS = [
  "Released",
  "Not Released",
  "Shundo",
  "Not Shundo",
  "Lucky",
  "Not Lucky",
  "Tradeable",
  "Untradeable",
  "Legendary",
  "Not Legendary",
] as const;

export const SORT_OPTIONS = [
  "Pokédex Order",
  "Alphabetical",
  "Shundo First",
  "Lucky First",
  "Legendary First",
] as const;

export const GENERATIONS = [
  "All",
  ...Array.from({ length: 9 }, (_, i) => `Gen ${i + 1}`),
];
