export interface Pokemon {
  id: number;
  name: string;
  rootId: number;
  rootName: string;
  familyId: number;
  generation: number;
  imageUrl: string;
  tradeable: boolean;
  legendary: boolean;
}

export interface CollectionEntry {
  shundo: boolean;
  lucky: boolean;
}

export interface UserCollection {
  [pokemonId: string]: CollectionEntry;
}

export interface ShinyRateEntry {
  pokemonId: number;
  name: string;
  rate: string;
  rateValue: number;
  sampleSize: number;
}

export type ToggleMode = "off" | "shundo" | "lucky";
