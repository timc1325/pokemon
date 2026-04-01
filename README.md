# Pokémon GO Shiny Rate Targets

Find which Pokémon currently have boosted shiny rates that you **don't already own**.

## Setup

```bash
pip install pandas gspread google-auth
```

## Usage

```bash
python scripts/shinyrates.py
```

By default, reads your shundo collection from **Google Sheets** (requires the service account JSON key in the project root and `app/.streamlit/secrets.toml`).

### Options

| Flag | Description |
|------|-------------|
| `--owned PATH` | Override: use a local JSON file instead of Google Sheets |
| `--family PATH` | Path to family CSV (default: `app/data/pokemon_family.csv`) |
| `--rates-url URL` | Override shiny rates API endpoint |

## Example

```bash
$ python scripts/shinyrates.py

Loaded 386 shundo IDs from Google Sheets
403: Shinx | 1/62 | sample 184529
613: Cubchoo | 1/85 | sample 93412
177: Natu | 1/128 | sample 241083
```

Output is sorted by highest shiny rate first. Pokémon whose **entire evolution family** you already own are excluded.

## How it works

1. Reads your shundo IDs from Google Sheets (or a local JSON file)
2. Fetches live shiny rates from [shinyrates.com](https://shinyrates.com)
3. Filters out families you already have a shundo for
4. Prints remaining targets sorted by best shiny rate
