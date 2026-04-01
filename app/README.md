# Pokémon GO Collection Tracker

A Streamlit app for tracking your Pokémon GO collection — shundo and lucky status — with Google Sheets as the backend.

## Folder Structure

```
app/
├── app.py               # Streamlit app (reads/writes Google Sheets)
├── generate_data.py     # Regenerate pokemon.csv from pokemon_family.csv
├── requirements.txt
├── README.md
├── .streamlit/
│   └── secrets.toml.example
└── data/
    ├── pokemon.csv          # Static Pokémon data (committed to repo)
    └── pokemon_family.csv   # Source data from PokeAPI
```

## Install

```bash
pip install -r requirements.txt
```

## Run locally

```bash
streamlit run app.py
```

Requires `.streamlit/secrets.toml` with Google Sheets credentials (see `secrets.toml.example`).

## Data

### `pokemon.csv` (local, static)

| Column | Description |
|---|---|
| `pokemon_id` | National Pokédex number |
| `name` | Display name |
| `root_id` | Base family member ID |
| `root_name` | Base family member name |
| `family_id` | Evolution chain ID |
| `generation` | Game generation (1–9) |
| `image_url` | Official artwork URL |
| `tradeable` | Whether this Pokémon can be traded |

### Collection (Google Sheets)

| Column | Description |
|---|---|
| `pokemon_id` | National Pokédex number |
| `shundo` | Shiny + perfect IVs |
| `lucky` | Lucky trade status |

## Editing

- **Sidebar editor**: Select a Pokémon, toggle shundo/lucky, save
- **Toggle mode**: Click cards directly to flip tags on/off
- All changes persist to Google Sheets immediately

## Regenerating pokemon.csv

If new Pokémon are added to PokeAPI:

```bash
python scripts/build_pokemon_family.py   # Refresh pokemon_family.csv
python app/generate_data.py              # Rebuild pokemon.csv
```
