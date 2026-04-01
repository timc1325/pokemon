import argparse
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

DEFAULT_OWNED_PATH = None  # No default; pass --owned path to a JSON list of owned IDs
DEFAULT_FAMILY_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "pokemon_family.csv"
DEFAULT_RATES_URL = "https://shinyrates.com/data/rate"
USER_AGENT = "Mozilla/5.0"


def load_owned_ids(owned_path: Path) -> set[int]:
    with owned_path.open() as f:
        owned_ids = json.load(f)
    return {int(pokemon_id) for pokemon_id in owned_ids}


def load_family_table(family_path: Path) -> pd.DataFrame:
    df = pd.read_csv(family_path)
    df["pokemon_id"] = df["pokemon_id"].astype(int)
    df["family_id"] = df["family_id"].astype(int)
    return df[["pokemon_id", "name", "family_id", "evolves_from_id"]]


def fetch_live_shiny_rates(rates_url: str) -> pd.DataFrame:
    request = Request(rates_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        data = json.load(response)

    df = pd.DataFrame(data)
    df["pokemon_id"] = df["id"].astype(int)
    df["sample_size"] = df["total"].str.replace(",", "", regex=False).astype(int)
    df["shiny_rate_value"] = df["rate"].map(parse_rate_value)
    return df[["pokemon_id", "name", "rate", "sample_size", "shiny_rate_value"]]


def parse_rate_value(rate_text: str) -> float:
    normalized = rate_text.strip().lower().replace(" ", "").replace(",", "")
    fraction_match = re.fullmatch(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", normalized)
    if fraction_match:
        numerator = float(fraction_match.group(1))
        denominator = float(fraction_match.group(2))
        if denominator == 0:
            return 0.0
        return numerator / denominator

    percent_match = re.fullmatch(r"(\d+(?:\.\d+)?)%", normalized)
    if percent_match:
        return float(percent_match.group(1)) / 100

    raise ValueError(f"Unsupported shiny rate format: {rate_text}")


def get_live_targets(owned_ids: set[int], family_df: pd.DataFrame, rates_df: pd.DataFrame) -> pd.DataFrame:
    owned_family_ids = set(family_df.loc[family_df["pokemon_id"].isin(owned_ids), "family_id"])

    merged = rates_df.merge(family_df, on="pokemon_id", how="inner", suffixes=("_live", "_family"))
    targets = merged.loc[~merged["family_id"].isin(owned_family_ids)].copy()
    targets = targets.sort_values(["shiny_rate_value", "sample_size", "pokemon_id"], ascending=[False, False, True])
    targets = targets.reset_index(drop=True)
    return targets[["pokemon_id", "name_live", "rate", "sample_size", "family_id"]].rename(columns={"name_live": "name"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owned", type=Path, required=True, help="Path to JSON list of owned Pokémon IDs")
    parser.add_argument("--family", type=Path, default=DEFAULT_FAMILY_PATH)
    parser.add_argument("--rates-url", default=DEFAULT_RATES_URL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    owned_ids = load_owned_ids(args.owned)
    family_df = load_family_table(args.family)
    rates_df = fetch_live_shiny_rates(args.rates_url)
    targets = get_live_targets(owned_ids, family_df, rates_df)

    if targets.empty:
        print("No live shiny rate targets remain after filtering owned families.")
        return

    for row in targets.itertuples(index=False):
        print(f"{row.pokemon_id}: {row.name} | {row.rate} | sample {row.sample_size}")


if __name__ == "__main__":
    main()
