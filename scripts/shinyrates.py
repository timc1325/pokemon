import argparse
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAMILY_PATH = PROJECT_ROOT / "app" / "data" / "pokemon_family.csv"
SECRETS_TOML = PROJECT_ROOT / "app" / ".streamlit" / "secrets.toml"
SERVICE_ACCOUNT_JSON = next(PROJECT_ROOT.glob("*.json"), None)
DEFAULT_RATES_URL = "https://shinyrates.com/data/rate"
GSHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
USER_AGENT = "Mozilla/5.0"


def _get_sheet_id() -> str:
    text = SECRETS_TOML.read_text()
    m = re.search(r'sheet_id\s*=\s*"([^"]+)"', text)
    if not m:
        raise RuntimeError("sheet_id not found in secrets.toml")
    return m.group(1)


def load_owned_ids_from_sheets() -> set[int]:
    """Read shundo Pokémon IDs from Google Sheets collection."""
    if not SERVICE_ACCOUNT_JSON or not SERVICE_ACCOUNT_JSON.exists():
        raise RuntimeError("No service account JSON key found in project root")
    creds_info = json.loads(SERVICE_ACCOUNT_JSON.read_text())
    creds = Credentials.from_service_account_info(creds_info, scopes=GSHEETS_SCOPES)
    client = gspread.authorize(creds)
    ws = client.open_by_key(_get_sheet_id()).worksheet("collection")
    records = ws.get_all_records()
    return {
        int(r["pokemon_id"]) for r in records
        if str(r.get("shundo", "FALSE")).upper() in ("TRUE", "1")
    }


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
    parser.add_argument("--owned", type=Path, default=None, help="Path to JSON list of owned IDs (default: read from Google Sheets)")
    parser.add_argument("--family", type=Path, default=DEFAULT_FAMILY_PATH)
    parser.add_argument("--rates-url", default=DEFAULT_RATES_URL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.owned:
        owned_ids = load_owned_ids(args.owned)
        print(f"Loaded {len(owned_ids)} owned IDs from {args.owned}")
    else:
        owned_ids = load_owned_ids_from_sheets()
        print(f"Loaded {len(owned_ids)} shundo IDs from Google Sheets")
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
