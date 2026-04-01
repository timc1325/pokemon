import json
import re
import urllib.request
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
POKEMON_PATH = DATA_DIR / "pokemon.csv"

RELEASED_API_URL = "https://pogoapi.net/api/v1/released_pokemon.json"
SHINY_RATES_URL = "https://shinyrates.com/data/rate"

CARDS_PER_ROW = 8
CARDS_PER_PAGE = 80

FALLBACK_IMAGE = (
    "https://raw.githubusercontent.com/PokeAPI/sprites"
    "/master/sprites/pokemon/0.png"
)

FILTER_TAGS = [
    "Released", "Not Released", "Shundo", "Not Shundo", "Lucky", "Not Lucky",
    "Tradeable", "Untradeable",
]

SORT_OPTIONS = [
    "Pokédex Order", "Alphabetical", "Shundo First", "Lucky First",
]

GSHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


def inject_css():
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
    <style>
    :root {
        --bg-main: #08080e;
        --bg-panel: #11111b;
        --bg-input: #151523;
        --text-primary: #d8d8e8;
        --text-secondary: #a7a7bf;
        --text-muted: #8a8aa5;
        --border-soft: rgba(255,255,255,0.07);
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, [data-testid="stToolbar"],
    [data-testid="stDecoration"], [data-testid="stStatusWidget"],
    .viewerBadge_container__r5tak { display: none !important; }
    header[data-testid="stHeader"] { background: transparent !important; }

    /* ── Base ── */
    html, body, [data-testid="stAppViewContainer"],
    [data-testid="stApp"], .main, .stApp {
        background-color: var(--bg-main) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    .block-container { padding: 1.2rem 2rem 1rem; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] > div:first-child {
        background: var(--bg-panel) !important;
        border-right: 1px solid var(--border-soft);
    }
    [data-testid="stSidebar"] * {
        font-family: 'Inter', sans-serif !important;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {
        font-size: 10px !important; font-weight: 600 !important;
        color: var(--text-secondary) !important;
        letter-spacing: 0.14em; text-transform: uppercase;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
        font-size: 10px !important; font-weight: 600 !important;
        color: var(--text-secondary) !important;
        letter-spacing: 0.1em; text-transform: uppercase;
    }
    section[data-testid="stSidebar"] hr {
        border: none; border-top: 1px solid rgba(255,255,255,0.03);
        margin: 14px 0;
    }
    [data-testid="stSidebar"] label {
        color: var(--text-secondary) !important; font-size: 11px !important;
        font-weight: 500 !important; letter-spacing: 0.02em;
    }

    /* ── All inputs dark ── */
    input, textarea {
        background-color: var(--bg-input) !important;
        border-color: var(--border-soft) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        border-radius: 8px !important;
        caret-color: #7c5cfc !important;
    }
    input::placeholder { color: var(--text-muted) !important; }
    [data-baseweb="select"] > div {
        background-color: var(--bg-input) !important;
        border-color: var(--border-soft) !important;
        color: var(--text-primary) !important;
        border-radius: 8px !important;
    }
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"], [role="listbox"] {
        background-color: #12121e !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
    }
    [data-baseweb="menu"] li { color: var(--text-primary) !important; }
    [data-baseweb="menu"] li:hover {
        background: rgba(124,92,252,0.08) !important;
    }
    [data-baseweb="tag"] {
        background: rgba(124,92,252,0.1) !important;
        border-radius: 4px !important; color: #c5baff !important;
    }
    /* Keep multiselect internal search input invisible */
    [data-testid="stMultiSelect"] input {
        background: transparent !important;
        border: none !important; border-radius: 0 !important;
        box-shadow: none !important;
    }
    label { color: var(--text-secondary) !important; font-size: 11px !important; }

    /* ── Checkbox ── */
    [data-testid="stCheckbox"] label span {
        color: var(--text-secondary) !important; font-size: 12px !important;
    }
    [data-testid="stCheckbox"] label span[data-testid="stMarkdownContainer"] p {
        color: var(--text-secondary) !important;
    }

    /* ── Tabs → segmented control ── */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.015); border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.03);
        padding: 3px; gap: 2px; display: inline-flex;
        border-bottom: none !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif; font-size: 11px;
        font-weight: 500; color: var(--text-secondary); padding: 8px 24px;
        background: transparent; letter-spacing: 0.08em;
        text-transform: uppercase; border-radius: 6px;
    }
    .stTabs [aria-selected="true"] {
        color: #d0d0e4 !important; font-weight: 600;
        background: rgba(255,255,255,0.05) !important;
    }
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* ── Buttons ── */
    .stButton > button {
        font-family: 'Inter', sans-serif !important;
        border-radius: 6px; font-size: 11px; font-weight: 500;
        border: 1px solid var(--border-soft);
        background: rgba(255,255,255,0.03); color: var(--text-primary);
        padding: 6px 16px; letter-spacing: 0.02em;
        transition: all 0.2s ease; box-shadow: none !important;
    }
    .stButton > button:hover {
        background: rgba(255,255,255,0.05);
        border-color: rgba(255,255,255,0.1); color: #f2f2ff;
    }
    .stButton > button[kind="primary"] {
        background: rgba(124,92,252,0.7); color: #fff;
        border-color: rgba(124,92,252,0.5);
    }
    .stButton > button[kind="primary"]:hover {
        background: rgba(124,92,252,0.9);
    }

    /* ── Download button ── */
    .stDownloadButton > button {
        font-family: 'Inter', sans-serif !important;
        background: rgba(255,255,255,0.03) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-soft) !important;
    }

    /* ── Form ── */
    [data-testid="stForm"] {
        background: transparent !important;
        border: 1px solid rgba(255,255,255,0.03) !important;
        border-radius: 8px !important;
    }

    /* ── Collection cards ── */
    .pk-card {
        background: rgba(255,255,255,0.018); border-radius: 10px;
        padding: 12px 6px 8px; text-align: center; min-height: 110px;
        border: 1px solid rgba(255,255,255,0.025);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    .pk-card:hover {
        background: rgba(255,255,255,0.04);
        border-color: rgba(255,255,255,0.06);
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .pk-card.pk-active {
        border-color: rgba(124,92,252,0.25);
        background: rgba(124,92,252,0.05);
        box-shadow: 0 0 20px rgba(124,92,252,0.06);
    }
    .pk-card img {
        width: 48px; height: 48px; object-fit: contain;
        filter: drop-shadow(0 3px 8px rgba(0,0,0,0.4));
        transition: transform 0.3s ease;
    }
    .pk-card:hover img { transform: scale(1.08); }
    .pk-name {
        font-family: 'Inter', sans-serif; font-weight: 600;
        font-size: 10px; color: #d0d0e4; margin-top: 5px;
        line-height: 1.3;
    }
    .pk-id {
        font-family: 'Inter', sans-serif; font-size: 8.5px;
        color: var(--text-muted); margin-top: 1px; font-weight: 500;
    }
    .pk-badges { margin-top: 4px; min-height: 14px; line-height: 1.8; }
    .pk-badge {
        display: inline-block; font-size: 7px; font-weight: 600;
        letter-spacing: 0.05em; padding: 1px 5px; border-radius: 3px;
        margin: 1px; text-transform: uppercase;
        font-family: 'Inter', sans-serif;
    }

    /* ── Rate cards ── */
    .rate-card {
        background: rgba(255,255,255,0.018); border-radius: 10px;
        padding: 12px 6px 8px; text-align: center; min-height: 120px;
        border: 1px solid rgba(255,255,255,0.025);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    .rate-card:hover {
        background: rgba(255,255,255,0.04);
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .rate-card img {
        width: 44px; height: 44px; object-fit: contain;
        filter: drop-shadow(0 3px 8px rgba(0,0,0,0.4));
        transition: transform 0.3s ease;
    }
    .rate-card:hover img { transform: scale(1.08); }
    .rate-name {
        font-family: 'Inter', sans-serif; font-weight: 600;
        font-size: 10px; color: #d0d0e4; margin-top: 5px;
    }
    .rate-id {
        font-family: 'Inter', sans-serif; font-size: 8.5px;
        color: var(--text-muted); margin-top: 1px;
    }
    .rate-badges { margin-top: 4px; line-height: 1.8; }
    .rate-sample {
        font-family: 'Inter', sans-serif; font-size: 8px;
        color: var(--text-muted); margin-top: 2px; letter-spacing: 0.02em;
    }

    /* ── Hero stats ── */
    .hero-stats {
        display: flex; gap: 32px; padding: 8px 0 12px;
        align-items: flex-end;
    }
    .hero-stat { display: flex; flex-direction: column; }
    .hero-val {
        font-family: 'Inter', sans-serif; font-size: 22px;
        font-weight: 700; color: #e0e0f0; line-height: 1;
        letter-spacing: -0.02em;
    }
    .hero-label {
        font-family: 'Inter', sans-serif; font-size: 8px;
        font-weight: 600; color: var(--text-secondary); text-transform: uppercase;
        letter-spacing: 0.12em; margin-top: 4px;
    }

    /* ── Page nav ── */
    .page-info {
        font-family: 'Inter', sans-serif; text-align: center;
        font-size: 11px; color: var(--text-secondary); padding: 8px 0;
        font-weight: 500; letter-spacing: 0.02em;
    }

    /* ── Count label ── */
    .count-label {
        font-family: 'Inter', sans-serif; font-size: 11px;
        color: var(--text-secondary); padding: 6px 0;
    }
    .count-label b { color: #d0d0e4; font-weight: 600; }

    /* ── Brand header ── */
    .brand {
        font-family: 'Inter', sans-serif; padding: 0 0 12px;
    }
    .brand-title {
        font-size: 20px; font-weight: 700; color: #e8e8f4;
        letter-spacing: -0.02em;
    }
    .brand-sub {
        font-size: 10px; color: var(--text-secondary); margin-left: 12px;
        letter-spacing: 0.12em; text-transform: uppercase;
        font-weight: 500;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.04); border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255,255,255,0.08);
    }

    /* ── Alerts ── */
    [data-testid="stAlert"] {
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid var(--border-soft) !important;
        color: var(--text-primary) !important; border-radius: 8px !important;
    }

    /* ── Mobile responsive ── */
    @media (max-width: 768px) {
        .block-container { padding: 0.5rem 0.6rem 0.5rem; }

        /* Card grid rows (5+ children): force 4 per row */
        [data-testid="stHorizontalBlock"]:has(> :nth-child(5)) {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 4px !important;
        }
        [data-testid="stHorizontalBlock"]:has(> :nth-child(5)) > [data-testid="stColumn"] {
            flex: 0 0 calc(25% - 3px) !important;
            max-width: calc(25% - 3px) !important;
            min-width: 0 !important;
        }

        /* Ultra-compact cards */
        .pk-card {
            padding: 8px 3px 5px; min-height: 72px;
            border-radius: 8px;
        }
        .pk-card img { width: 34px; height: 34px; }
        .pk-card:hover { transform: none; box-shadow: none; }
        .pk-card:hover img { transform: none; }
        .pk-name { font-size: 8px; margin-top: 3px; }
        .pk-id { font-size: 7px; }
        .pk-badges { margin-top: 2px; min-height: 10px; line-height: 1.5; }
        .pk-badge { font-size: 6px; padding: 1px 3px; }

        .rate-card {
            padding: 8px 3px 5px; min-height: 80px;
            border-radius: 8px;
        }
        .rate-card img { width: 30px; height: 30px; }
        .rate-card:hover { transform: none; box-shadow: none; }
        .rate-card:hover img { transform: none; }
        .rate-name { font-size: 8px; margin-top: 3px; }
        .rate-id { font-size: 7px; }
        .rate-badges { margin-top: 2px; line-height: 1.5; }
        .rate-sample { font-size: 6px; }

        /* Compact stats */
        .hero-stats { gap: 20px; padding: 4px 0 8px; }
        .hero-val { font-size: 18px; }
        .hero-label { font-size: 7px; margin-top: 2px; }

        /* Compact brand */
        .brand { padding: 0 0 6px; }
        .brand-title { font-size: 15px; }
        .brand-sub { font-size: 8px; margin-left: 8px; }

        /* Compact tabs */
        .stTabs [data-baseweb="tab"] {
            padding: 6px 14px; font-size: 9px;
        }

        /* Compact nav/labels */
        .page-info { font-size: 9px; }
        .count-label { font-size: 9px; }

        /* Smaller buttons */
        .stButton > button { font-size: 9px; padding: 3px 8px; }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _get_gsheet_client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=GSHEETS_SCOPES
    )
    return gspread.authorize(creds)


def _get_worksheet():
    client = _get_gsheet_client()
    spreadsheet = client.open_by_key(st.secrets["sheet_id"])
    try:
        return spreadsheet.worksheet("collection")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="collection", rows=1100, cols=3)
        ws.update("A1:C1", [["pokemon_id", "shundo", "lucky"]])
        return ws


def load_pokemon() -> pd.DataFrame:
    df = pd.read_csv(POKEMON_PATH)
    expected = {"pokemon_id", "name", "root_id", "root_name", "image_url"}
    missing = expected - set(df.columns)
    if missing:
        st.error(f"pokemon.csv is missing columns: {missing}")
        st.stop()
    return df


def load_collection() -> pd.DataFrame:
    if "collection_df" in st.session_state:
        return st.session_state["collection_df"]
    try:
        ws = _get_worksheet()
        records = ws.get_all_records()
        if not records:
            df = pd.DataFrame(columns=["pokemon_id", "shundo", "lucky"])
        else:
            df = pd.DataFrame(records)
            df["pokemon_id"] = df["pokemon_id"].astype(int)
            for col in ["shundo", "lucky"]:
                df[col] = df[col].astype(str).str.upper().isin(["TRUE", "1"])
        st.session_state["collection_df"] = df
        return df
    except Exception as e:
        st.error(f"Failed to load collection from Google Sheets: {e}")
        st.stop()


def save_collection(df: pd.DataFrame) -> None:
    try:
        ws = _get_worksheet()
        ws.clear()
        header = ["pokemon_id", "shundo", "lucky"]
        rows = df[["pokemon_id", "shundo", "lucky"]].values.tolist()
        ws.update(f"A1:C{len(rows) + 1}", [header] + rows)
        st.session_state["collection_df"] = df  # update cache
    except Exception as e:
        st.error(f"Failed to save to Google Sheets: {e}")


def ensure_collection_complete(
    pokemon_df: pd.DataFrame, collection_df: pd.DataFrame
) -> pd.DataFrame:
    all_ids = set(pokemon_df["pokemon_id"])
    existing_ids = set(collection_df["pokemon_id"])
    missing_ids = all_ids - existing_ids
    if not missing_ids:
        return collection_df
    new_rows = pd.DataFrame({
        "pokemon_id": sorted(missing_ids),
        "shundo": False,
        "lucky": False,
    })
    collection_df = pd.concat([collection_df, new_rows], ignore_index=True)
    collection_df = collection_df.sort_values("pokemon_id").reset_index(drop=True)
    save_collection(collection_df)
    return collection_df


def fetch_released_ids() -> set[int]:
    if "released_ids" in st.session_state:
        return st.session_state["released_ids"]
    try:
        req = urllib.request.Request(
            RELEASED_API_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        ids = {int(k) for k in data}
        st.session_state["released_ids"] = ids
        return ids
    except Exception:
        return set()


def _parse_rate_value(rate_text: str) -> float:
    normalized = rate_text.strip().lower().replace(" ", "").replace(",", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", normalized)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        return num / den if den else 0.0
    m = re.fullmatch(r"(\d+(?:\.\d+)?)%", normalized)
    if m:
        return float(m.group(1)) / 100
    return 0.0


def fetch_shiny_rates() -> pd.DataFrame | None:
    if "shiny_rates_df" in st.session_state:
        return st.session_state["shiny_rates_df"]
    try:
        req = urllib.request.Request(
            SHINY_RATES_URL,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        df = pd.DataFrame(data)
        df["pokemon_id"] = df["id"].astype(int)
        df["sample_size"] = df["total"].str.replace(",", "", regex=False).astype(int)
        df["shiny_rate_value"] = df["rate"].map(_parse_rate_value)
        df = df[["pokemon_id", "rate", "sample_size", "shiny_rate_value"]]
        st.session_state["shiny_rates_df"] = df
        return df
    except Exception:
        return None


def get_shiny_rates_merged(
    merged: pd.DataFrame, rates_df: pd.DataFrame
) -> pd.DataFrame:
    result = merged.merge(rates_df, on="pokemon_id", how="inner")
    result = result.sort_values(
        ["shiny_rate_value", "sample_size"], ascending=[False, False]
    ).reset_index(drop=True)
    return result


def merge_data(
    pokemon_df: pd.DataFrame, collection_df: pd.DataFrame
) -> pd.DataFrame:
    df = pokemon_df.merge(collection_df, on="pokemon_id", how="left")
    for col in ["shundo", "lucky"]:
        df[col] = df[col].fillna(False).astype(bool)
    released_ids = fetch_released_ids()
    df["released"] = df["pokemon_id"].isin(released_ids) if released_ids else True
    return df


# ---------------------------------------------------------------------------
# Filtering & sorting
# ---------------------------------------------------------------------------


def apply_filters(
    df: pd.DataFrame,
    search: str,
    filter_tags: list[str],
    gen_opt: str,
    sort_opt: str,
    root_only: bool,
    show_family: bool = False,
) -> pd.DataFrame:
    filtered = df.copy()

    if search:
        matched = filtered[
            filtered["name"].str.contains(search, case=False, na=False)
        ]
        if show_family and not matched.empty:
            matched_families = set(matched["family_id"])
            filtered = filtered[filtered["family_id"].isin(matched_families)]
        else:
            filtered = matched

    mask_map = {
        "Released": ("released", False),
        "Not Released": ("released", True),
        "Shundo": ("shundo", False),
        "Not Shundo": ("shundo", True),
        "Lucky": ("lucky", False),
        "Not Lucky": ("lucky", True),
        "Tradeable": ("tradeable", False),
        "Untradeable": ("tradeable", True),
    }
    for tag in filter_tags:
        if tag in mask_map:
            col, negate = mask_map[tag]
            filtered = filtered[~filtered[col] if negate else filtered[col]]

    if gen_opt != "All":
        gen_num = int(gen_opt.split()[-1])
        filtered = filtered[filtered["generation"] == gen_num]

    if root_only:
        filtered = filtered[filtered["pokemon_id"] == filtered["root_id"]]

    sort_map = {
        "Pokédex Order": (["pokemon_id"], [True]),
        "Alphabetical": (["name"], [True]),
        "Shundo First": (["shundo", "pokemon_id"], [False, True]),
        "Lucky First": (["lucky", "pokemon_id"], [False, True]),
    }
    cols, asc = sort_map.get(sort_opt, (["pokemon_id"], [True]))
    filtered = filtered.sort_values(cols, ascending=asc)
    return filtered.reset_index(drop=True)


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------


def badge(label: str, bg: str, fg: str = "#fff") -> str:
    return (
        f'<span class="pk-badge" style="background:{bg};color:{fg};">'
        f'{label}</span>'
    )


def render_stats(df: pd.DataFrame) -> None:
    total = len(df)
    shundo = int(df["shundo"].sum())
    lucky = int(df["lucky"].sum())
    st.markdown(
        f'<div class="hero-stats">'
        f'<div class="hero-stat"><span class="hero-val">{total}</span>'
        f'<span class="hero-label">Showing</span></div>'
        f'<div class="hero-stat"><span class="hero-val">{shundo}</span>'
        f'<span class="hero-label">Shundo</span></div>'
        f'<div class="hero-stat"><span class="hero-val">{lucky}</span>'
        f'<span class="hero-label">Lucky</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_card(
    row: pd.Series, toggle_tag: str | None, collection_df: pd.DataFrame
) -> None:
    parts: list[str] = []
    if row["shundo"]:
        parts.append(badge("Shundo", "rgba(124,92,252,0.15)", "#a090ff"))
    if row["lucky"]:
        parts.append(badge("Lucky", "rgba(240,160,48,0.15)", "#ffc060"))
    if not row.get("tradeable", True):
        parts.append(badge("Untradeable", "rgba(255,255,255,0.04)", "#404058"))

    badge_html = " ".join(parts)

    image_url = row.get("image_url", "")
    if pd.isna(image_url) or not image_url:
        image_url = FALLBACK_IMAGE

    active = "pk-active" if toggle_tag and row.get(toggle_tag, False) else ""

    st.markdown(
        f'<div class="pk-card {active}">'
        f'<img src="{image_url}" '
        f'onerror="this.src=\'{FALLBACK_IMAGE}\'" loading="lazy">'
        f'<div class="pk-name">{row["name"]}</div>'
        f'<div class="pk-id">#{row["pokemon_id"]}</div>'
        f'<div class="pk-badges">{badge_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    show_toggle = toggle_tag and (
        toggle_tag != "lucky" or row.get("tradeable", True)
    )
    if show_toggle:
        pid = int(row["pokemon_id"])
        current = bool(row.get(toggle_tag, False))
        if st.button(
            f"{'✓' if current else '○'} {toggle_tag.title()}",
            key=f"toggle_{pid}",
            use_container_width=True,
            type="primary" if current else "secondary",
        ):
            idx = collection_df[collection_df["pokemon_id"] == pid].index[0]
            collection_df.at[idx, toggle_tag] = not current
            save_collection(collection_df)
            st.rerun()


def render_grid(
    df: pd.DataFrame, page: int, toggle_tag: str | None, collection_df: pd.DataFrame
) -> None:
    start = page * CARDS_PER_PAGE
    end = min(start + CARDS_PER_PAGE, len(df))
    page_df = df.iloc[start:end]

    for i in range(0, len(page_df), CARDS_PER_ROW):
        cols = st.columns(CARDS_PER_ROW)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(page_df):
                with col:
                    render_card(page_df.iloc[idx], toggle_tag, collection_df)


def render_shiny_rates(merged: pd.DataFrame) -> None:
    col_refresh, col_filter = st.columns([1, 3])
    with col_refresh:
        if st.button("Refresh", key="refresh_shiny_rates"):
            st.session_state.pop("shiny_rates_df", None)
            st.rerun()
    with col_filter:
        shiny_filter_tags = st.multiselect(
            "Filter", FILTER_TAGS, default=["Not Shundo"], key="shiny_rate_filters"
        )

    rates_df = fetch_shiny_rates()
    if rates_df is None:
        st.warning("Could not fetch live shiny rates.")
        return

    all_rates = get_shiny_rates_merged(merged, rates_df)
    if all_rates.empty:
        st.info("No live shiny rate data available.")
        return

    filtered = all_rates.copy()
    mask_map = {
        "Released": ("released", False),
        "Not Released": ("released", True),
        "Shundo": ("shundo", False),
        "Not Shundo": ("shundo", True),
        "Lucky": ("lucky", False),
        "Not Lucky": ("lucky", True),
        "Tradeable": ("tradeable", False),
        "Untradeable": ("tradeable", True),
    }
    for tag in shiny_filter_tags:
        if tag in mask_map:
            col, negate = mask_map[tag]
            if col in filtered.columns:
                filtered = filtered[~filtered[col] if negate else filtered[col]]

    st.markdown(
        f'<div class="count-label"><b>{len(filtered)}</b> with live rates</div>',
        unsafe_allow_html=True,
    )

    _GLOW = {
        "#10b981": "rgba(16,185,129,0.10)",
        "#f59e0b": "rgba(245,158,11,0.10)",
        "#3b82f6": "rgba(59,130,246,0.10)",
        "#2a2a40": "none",
    }

    for i in range(0, len(filtered), CARDS_PER_ROW):
        cols = st.columns(CARDS_PER_ROW)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(filtered):
                row = filtered.iloc[idx]
                with col:
                    image_url = row.get("image_url", "")
                    if pd.isna(image_url) or not image_url:
                        image_url = FALLBACK_IMAGE
                    rate_val = row["shiny_rate_value"]
                    if rate_val >= 1 / 100:
                        accent = "#10b981"
                    elif rate_val >= 1 / 300:
                        accent = "#f59e0b"
                    elif rate_val >= 1 / 500:
                        accent = "#3b82f6"
                    else:
                        accent = "#2a2a40"
                    badges_html = badge(row["rate"], accent)
                    if row.get("shundo", False):
                        badges_html += " " + badge("✦", "rgba(124,92,252,0.15)", "#a090ff")
                    if row.get("lucky", False):
                        badges_html += " " + badge("✦", "rgba(240,160,48,0.15)", "#ffc060")
                    glow = _GLOW.get(accent, "none")
                    shadow = f"box-shadow:0 -4px 20px {glow};" if glow != "none" else ""
                    st.markdown(
                        f'<div class="rate-card" style="border-top:2px solid {accent};{shadow}">'
                        f'<img src="{image_url}" '
                        f'onerror="this.src=\'{FALLBACK_IMAGE}\'" loading="lazy">'
                        f'<div class="rate-name">{row["name"]}</div>'
                        f'<div class="rate-id">#{row["pokemon_id"]}</div>'
                        f'<div class="rate-badges">{badges_html}</div>'
                        f'<div class="rate-sample">n={row["sample_size"]:,}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_controls():
    c_search, c_gen, c_sort = st.columns([3, 1, 1])
    with c_search:
        search = st.text_input(
            "search", placeholder="Search Pokémon…",
            label_visibility="collapsed",
        )
    gen_options = ["All"] + [f"Gen {i}" for i in range(1, 10)]
    with c_gen:
        gen_opt = st.selectbox("gen", gen_options, label_visibility="collapsed")
    with c_sort:
        sort_opt = st.selectbox("sort", SORT_OPTIONS, label_visibility="collapsed")

    c_tags, c_opts = st.columns([3, 1])
    with c_tags:
        filter_tags = st.multiselect(
            "Filter", FILTER_TAGS, default=["Released"],
        )
    with c_opts:
        root_only = st.checkbox("Root only")
        show_family = st.checkbox("Full family")

    return search, filter_tags, gen_opt, sort_opt, root_only, show_family


def render_sidebar_settings():
    st.sidebar.title("Settings")
    st.sidebar.subheader("Toggle Mode")
    toggle_options = ["Off", "Shundo", "Lucky"]
    toggle_mode = st.sidebar.selectbox(
        "Click cards to toggle", toggle_options,
    )
    toggle_tag = None if toggle_mode == "Off" else toggle_mode.lower()
    return toggle_tag


def render_sidebar_editor(merged: pd.DataFrame, collection_df: pd.DataFrame):
    st.sidebar.markdown("---")
    st.sidebar.subheader("Edit")

    options = merged.sort_values("pokemon_id").apply(
        lambda r: f"#{r['pokemon_id']} {r['name']}", axis=1
    ).tolist()

    selected = st.sidebar.selectbox("Pokémon", options, key="edit_select")
    pokemon_id = int(selected.split()[0].lstrip("#"))
    current = collection_df[collection_df["pokemon_id"] == pokemon_id].iloc[0]

    tradeable_col = merged.loc[merged["pokemon_id"] == pokemon_id, "tradeable"] if "tradeable" in merged.columns else None
    is_tradeable = bool(tradeable_col.iloc[0]) if tradeable_col is not None else True

    with st.sidebar.form("edit_form"):
        shundo = st.checkbox("Shundo", value=bool(current["shundo"]))
        if is_tradeable:
            lucky = st.checkbox("Lucky", value=bool(current["lucky"]))
        else:
            lucky = bool(current["lucky"])
            st.caption("Untradeable — cannot be lucky")
        submitted = st.form_submit_button("Save")

    if submitted:
        idx = collection_df[collection_df["pokemon_id"] == pokemon_id].index[0]
        collection_df.at[idx, "shundo"] = shundo
        collection_df.at[idx, "lucky"] = lucky
        save_collection(collection_df)
        st.sidebar.success(f"Saved #{pokemon_id}")
        st.rerun()


def render_sidebar_export(filtered: pd.DataFrame):
    st.sidebar.markdown("---")
    export_cols = [
        "pokemon_id", "name", "root_name", "generation",
        "shundo", "lucky",
    ]
    export_df = filtered[[c for c in export_cols if c in filtered.columns]]
    csv_data = export_df.to_csv(index=False)
    st.sidebar.download_button(
        "Export CSV", csv_data, "filtered_pokemon.csv", "text/csv"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(
        page_title="Pokémon GO",
        layout="wide",
        page_icon="🎮",
        initial_sidebar_state="collapsed",
    )
    inject_css()

    pokemon_df = load_pokemon()
    collection_df = load_collection()
    collection_df = ensure_collection_complete(pokemon_df, collection_df)
    merged = merge_data(pokemon_df, collection_df)

    # Sidebar — secondary controls (collapsed by default)
    toggle_tag = render_sidebar_settings()
    render_sidebar_editor(merged, collection_df)

    # Brand header
    st.markdown(
        '<div class="brand">'
        '<span class="brand-title">Pokémon GO</span>'
        '<span class="brand-sub">Collection Tracker</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    tab_collection, tab_shiny = st.tabs(["Collection", "Live Rates"])

    with tab_collection:
        search, filter_tags, gen_opt, sort_opt, root_only, show_family = render_controls()
        filtered = apply_filters(
            merged, search, filter_tags, gen_opt, sort_opt, root_only, show_family,
        )

        total_pages = max(1, -(-len(filtered) // CARDS_PER_PAGE))

        if "page" not in st.session_state:
            st.session_state.page = 1
        st.session_state.page = min(st.session_state.page, total_pages)

        page_start = (st.session_state.page - 1) * CARDS_PER_PAGE + 1
        page_end = min(st.session_state.page * CARDS_PER_PAGE, len(filtered))

        col_stats, col_nav = st.columns([3, 2])
        with col_stats:
            render_stats(filtered)
        with col_nav:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if st.button("‹", disabled=st.session_state.page <= 1, use_container_width=True):
                    st.session_state.page -= 1
                    st.rerun()
            with c2:
                st.markdown(
                    f'<div class="page-info">'
                    f'{page_start}–{page_end} of {len(filtered)}</div>',
                    unsafe_allow_html=True,
                )
            with c3:
                if st.button("›", disabled=st.session_state.page >= total_pages, use_container_width=True):
                    st.session_state.page += 1
                    st.rerun()

        render_grid(filtered, st.session_state.page - 1, toggle_tag, collection_df)

    with tab_shiny:
        render_shiny_rates(merged)

    render_sidebar_export(filtered)


if __name__ == "__main__":
    main()
