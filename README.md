# Pokémon GO Shiny Rate Targets

Find which Pokémon currently have boosted shiny rates that you **don't already own**.

## Setup

```bash
pip install pandas
```

## Usage

```bash
python scripts/shinyrates.py --owned path/to/owned.json
```

### `--owned` (required)

A JSON file containing a list of Pokémon IDs you already have as shinies:

```json
[1, 4, 7, 25, 133, 150]
```

### `--family` (optional)

Path to the family CSV. Defaults to `app/data/pokemon_family.csv`.

### `--rates-url` (optional)

Override the shiny rates API endpoint. Defaults to `https://shinyrates.com/data/rate`.

## Example

```bash
$ python scripts/shinyrates.py --owned my_shinies.json

403: Shinx | 1/62 | sample 184529
613: Cubchoo | 1/85 | sample 93412
177: Natu | 1/128 | sample 241083
```

Output is sorted by highest shiny rate first. Pokémon whose **entire evolution family** you already own are excluded.

## How it works

1. Fetches live shiny rates from [shinyrates.com](https://shinyrates.com)
2. Loads your owned IDs and the Pokémon family tree
3. Filters out families you already have a shiny for
4. Prints remaining targets sorted by best shiny rate
