"""Generate localapp data files from the parent project's pokemon_family.csv and shundo.json.

Usage:
    python localapp/generate_data.py

- pokemon.csv is written to localapp/data/ (committed to repo).
- collection data is synced to Google Sheets (single source of truth).
  Requires localapp/.streamlit/secrets.toml with sheet_id and gcp_service_account.
"""

import json
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAMILY_CSV = PROJECT_ROOT / "data" / "pokemon_family.csv"
SHUNDO_JSON = PROJECT_ROOT / "data" / "shundo.json"
LOCAL_DATA_DIR = Path(__file__).resolve().parent / "data"

IMAGE_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/PokeAPI/sprites"
    "/master/sprites/pokemon/other/official-artwork/{}.png"
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

    out_path = LOCAL_DATA_DIR / "pokemon.csv"
    pokemon_df.to_csv(out_path, index=False)
    print(f"Wrote {len(pokemon_df)} rows to {out_path}")
    return pokemon_df


GSHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SECRETS_TOML = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
SERVICE_ACCOUNT_JSON = next(PROJECT_ROOT.glob("*.json"), None)


def _get_sheet_id() -> str:
    """Read sheet_id from secrets.toml."""
    import re
    text = SECRETS_TOML.read_text()
    m = re.search(r'sheet_id\s*=\s*"([^"]+)"', text)
    if not m:
        raise RuntimeError("sheet_id not found in secrets.toml")
    return m.group(1)


def _get_worksheet():
    if not SERVICE_ACCOUNT_JSON or not SERVICE_ACCOUNT_JSON.exists():
        raise RuntimeError("No service account JSON key found in project root")
    creds_info = json.loads(SERVICE_ACCOUNT_JSON.read_text())
    creds = Credentials.from_service_account_info(creds_info, scopes=GSHEETS_SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(_get_sheet_id())
    try:
        return spreadsheet.worksheet("collection")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="collection", rows=1100, cols=3)
        ws.update("A1:C1", [["pokemon_id", "shundo", "lucky"]])
        return ws


def _read_collection_from_sheets() -> dict[int, dict]:
    """Read existing collection from Google Sheets. Returns {pokemon_id: {shundo, lucky}}."""
    try:
        ws = _get_worksheet()
        records = ws.get_all_records()
        result = {}
        for r in records:
            pid = int(r["pokemon_id"])
            result[pid] = {
                "shundo": str(r.get("shundo", "FALSE")).upper() in ("TRUE", "1"),
                "lucky": str(r.get("lucky", "FALSE")).upper() in ("TRUE", "1"),
            }
        return result
    except Exception as e:
        print(f"Warning: Could not read from Sheets: {e}")
        return {}


def _write_collection_to_sheets(collection_df: pd.DataFrame) -> None:
    ws = _get_worksheet()
    ws.clear()
    header = ["pokemon_id", "shundo", "lucky"]
    rows = collection_df[header].values.tolist()
    ws.update(f"A1:C{len(rows) + 1}", [header] + rows)


def sync_collection(pokemon_df: pd.DataFrame) -> pd.DataFrame:
    """Sync collection to Google Sheets: update shundo from shundo.json, preserve lucky."""
    shundo_roots: set[int] = set()
    if SHUNDO_JSON.exists():
        with open(SHUNDO_JSON) as f:
            shundo_roots = {int(i) for i in json.load(f)}

    shundo_family_ids = set(
        pokemon_df.loc[pokemon_df["root_id"].isin(shundo_roots), "pokemon_id"]
    )

    existing = _read_collection_from_sheets()

    rows = []
    for pid in sorted(pokemon_df["pokemon_id"].tolist()):
        rows.append({
            "pokemon_id": pid,
            "shundo": pid in shundo_family_ids,
            "lucky": existing.get(pid, {}).get("lucky", False),
        })

    collection_df = pd.DataFrame(rows)
    _write_collection_to_sheets(collection_df)
    shundo_count = int(collection_df["shundo"].sum())
    print(f"Synced {len(collection_df)} rows to Google Sheets ({shundo_count} shundos, {len(shundo_roots)} roots)")
    return collection_df


def main() -> None:
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    pokemon_df = generate_pokemon_csv()
    sync_collection(pokemon_df)


if __name__ == "__main__":
    main()
