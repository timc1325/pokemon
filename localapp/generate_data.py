"""Generate localapp data files from the parent project's pokemon_family.csv and shundo.json."""

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAMILY_CSV = PROJECT_ROOT / "data" / "pokemon_family.csv"
SHUNDO_JSON = PROJECT_ROOT / "data" / "shundo.json"
LOCAL_DATA_DIR = Path(__file__).resolve().parent / "data"

IMAGE_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/PokeAPI/sprites"
    "/master/sprites/pokemon/other/official-artwork/{}.png"
)

UNTRADEABLE_IDS = {
    151,   # Mew
    251,   # Celebi
    385,   # Jirachi
    386,   # Deoxys
    492,   # Shaymin
    494,   # Victini
    647,   # Keldeo
    648,   # Meloetta
    720,   # Hoopa
    802,   # Marshadow
    893,   # Zarude
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

    out_path = LOCAL_DATA_DIR / "pokemon.csv"
    pokemon_df.to_csv(out_path, index=False)
    print(f"Wrote {len(pokemon_df)} rows to {out_path}")
    return pokemon_df


def generate_collection_csv(pokemon_df: pd.DataFrame) -> pd.DataFrame:
    shundo_roots: set[int] = set()
    if SHUNDO_JSON.exists():
        with open(SHUNDO_JSON) as f:
            shundo_roots = {int(i) for i in json.load(f)}

    shundo_family_ids = set(
        pokemon_df.loc[pokemon_df["root_id"].isin(shundo_roots), "pokemon_id"]
    )

    existing_lucky: dict[int, bool] = {}
    out_path = LOCAL_DATA_DIR / "collection.csv"
    if out_path.exists():
        old = pd.read_csv(out_path)
        if "lucky" in old.columns:
            existing_lucky = dict(zip(old["pokemon_id"], old["lucky"].astype(bool)))

    rows = []
    for pid in sorted(pokemon_df["pokemon_id"].tolist()):
        rows.append({
            "pokemon_id": pid,
            "shundo": pid in shundo_family_ids,
            "lucky": existing_lucky.get(pid, False),
        })

    collection_df = pd.DataFrame(rows)
    collection_df.to_csv(out_path, index=False)
    shundo_count = int(collection_df["shundo"].sum())
    print(f"Wrote {len(collection_df)} rows to {out_path} ({shundo_count} shundos, {len(shundo_roots)} roots)")
    return collection_df


def main() -> None:
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    pokemon_df = generate_pokemon_csv()
    generate_collection_csv(pokemon_df)


if __name__ == "__main__":
    main()
