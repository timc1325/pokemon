# Pokémon GO Collection Tracker

A local Streamlit app for visually tracking your Pokémon GO collection — shiny, hundo, shundo, lucky — with family-level coverage.

## Folder Structure

```
localapp/
├── app.py               # Streamlit GUI
├── generate_data.py     # Regenerate data from parent project files
├── requirements.txt
├── README.md
└── data/
    ├── pokemon.csv      # Master Pokémon table (id, name, root, generation, image)
    └── collection.csv   # Your collection state (owned, shiny, hundo, lucky)
```

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Data Files

### `pokemon.csv`

| Column | Description |
|---|---|
| `pokemon_id` | National Pokédex number |
| `name` | Display name |
| `root_id` | Pokédex ID of the base family member |
| `root_name` | Name of the base family member |
| `family_id` | Evolution chain ID |
| `generation` | Game generation (1–9) |
| `image_url` | Official artwork URL |

### `collection.csv`

| Column | Description |
|---|---|
| `pokemon_id` | National Pokédex number |
| `owned` | Whether you have this Pokémon |
| `shiny` | Whether you have it shiny |
| `hundo` | Whether it has perfect IVs |
| `lucky` | Whether it is lucky |

`shundo` is computed automatically as `shiny AND hundo`.

## Family Coverage

If you own **any** Pokémon in a family, the entire family is marked as "Family Covered".

For example, owning Bulbasaur marks Ivysaur and Venusaur as family-covered. This does **not** change their individual `owned` status — it only adds a coverage indicator.

## Editing

Use the **Edit Pokémon** section in the sidebar:

1. Select a Pokémon from the dropdown
2. Toggle owned / shiny / hundo / lucky
3. Click **Save**

Changes are written directly to `collection.csv`.

## Regenerating Data

If the parent project's `data/pokemon_family.csv` or `data/shundo.json` change, regenerate localapp data:

```bash
python generate_data.py
```

This overwrites `data/pokemon.csv` and `data/collection.csv`.

## Extending

- Add new Pokémon by updating `pokemon.csv` (or regenerating via `generate_data.py`)
- Missing IDs are auto-initialized in `collection.csv` on app startup
- Add new columns to `collection.csv` as needed and update `app.py` accordingly
