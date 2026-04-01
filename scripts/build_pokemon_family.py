import pandas as pd
from pathlib import Path

SPECIES_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species.csv"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "pokemon_family.csv"

def build_family_table(output_path=DEFAULT_OUTPUT_PATH):
    # Load species table
    species = pd.read_csv(SPECIES_URL)

    # Keep only the columns needed for your tracker
    df = species[[
        "id",
        "identifier",
        "evolution_chain_id",
        "evolves_from_species_id"
    ]].copy()

    df = df.rename(columns={
        "id": "pokemon_id",
        "identifier": "name",
        "evolution_chain_id": "family_id",
        "evolves_from_species_id": "evolves_from_id"
    })

    # Nice formatting
    df["name"] = df["name"].str.replace("-", " ", regex=False).str.title()

    # Optional: sort for readability
    df = df.sort_values(["family_id", "pokemon_id"]).reset_index(drop=True)

    output_path = Path(output_path)
    df.to_csv(output_path, index=False)
    return df

if __name__ == "__main__":
    df = build_family_table()
    print(df.head(20))
    print(f"\nSaved {len(df)} rows to {DEFAULT_OUTPUT_PATH}")