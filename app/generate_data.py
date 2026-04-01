"""Generate pokemon.csv from the parent project's pokemon_family.csv.

Usage:
    python app/generate_data.py

- pokemon.csv is written to app/data/ (committed to repo).
- Collection data lives in Google Sheets (managed through the app).
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
FAMILY_CSV = DATA_DIR / "pokemon_family.csv"

IMAGE_URL_TEMPLATE = (
    "https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master/sprites/pokemon"
    "/other/official-artwork/{}.png"
)

UNTRADEABLE_IDS = {
    # Confirmed untradeable mythicals in Pokémon GO
    151,   # Mew
    251,   # Celebi
    385,   # Jirachi
    386,   # Deoxys
    491,   # Darkrai
    492,   # Shaymin
    494,   # Victini
    647,   # Keldeo
    648,   # Meloetta
    649,   # Genesect
    719,   # Diancie
    720,   # Hoopa
    802,   # Marshadow
    893,   # Zarude
    # Confirmed untradeable legendary
    718,   # Zygarde (obtained via Routes, cannot be traded)
    # Unreleased mythicals (will be untradeable when released)
    489,   # Phione
    490,   # Manaphy
    493,   # Arceus
    721,   # Volcanion
    801,   # Magearna
    807,   # Zeraora
    # Note: Meltan (808) and Melmetal (809) are mythical but TRADEABLE
}

GEN_BOUNDARIES = [
    (151, 1), (251, 2), (386, 3), (493, 4), (649, 5),
    (721, 6), (809, 7), (905, 8), (1025, 9),
]


def get_generation(pokemon_id: int) -> int:
    for max_id, gen in GEN_BOUNDARIES:
        if pokemon_id <= max_id:
            return gen
    return 9


def generate_pokemon_csv() -> pd.DataFrame:
    family_df = pd.read_csv(FAMILY_CSV)
    family_df["pokemon_id"] = family_df["pokemon_id"].astype(int)
    family_df["family_id"] = family_df["family_id"].astype(int)

    roots = (
        family_df[family_df["evolves_from_id"].isna()]
        .sort_values("pokemon_id")
        .drop_duplicates("family_id", keep="first")
        [["pokemon_id", "name", "family_id"]]
        .rename(columns={"pokemon_id": "root_id", "name": "root_name"})
    )

    pokemon_df = family_df.merge(roots, on="family_id", how="left")
    pokemon_df["generation"] = pokemon_df["pokemon_id"].map(get_generation)
    pokemon_df["image_url"] = pokemon_df["pokemon_id"].apply(
        lambda pid: IMAGE_URL_TEMPLATE.format(pid)
    )
    pokemon_df["tradeable"] = ~pokemon_df["pokemon_id"].isin(UNTRADEABLE_IDS)

    pokemon_df = pokemon_df[[
        "pokemon_id", "name", "root_id", "root_name", "family_id", "generation", "image_url", "tradeable"
    ]]
    pokemon_df = pokemon_df.sort_values("pokemon_id").reset_index(drop=True)

    out_path = DATA_DIR / "pokemon.csv"
    pokemon_df.to_csv(out_path, index=False)
    print(f"Wrote {len(pokemon_df)} rows to {out_path}")
    return pokemon_df


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    generate_pokemon_csv()


if __name__ == "__main__":
    main()
