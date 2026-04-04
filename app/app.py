import json
import re
import urllib.request
from pathlib import Path

import altair as alt
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

# Live Rates — shared accents (card borders/badges and bar chart tiers)
LIVE_RATE_GREEN = "#10b981"
LIVE_RATE_BLUE = "#3b82f6"

# Live Rates bar chart: best-odds only, short list for readability
BAR_CHART_MIN_PROB = 1 / 250  # show at least ~1 in 250 or better
BAR_CHART_TOP_N = 42
BAR_CHART_LARGE_SAMPLE_Q = 0.90
BAR_CHART_LARGE_SAMPLE_MIN_N = 8_000
CHART_BG = "#08080e"
CHART_GRID = "#ffffff0d"
CHART_MUTED = "#3d3d52"  # bar “standard” fill + card border when not green/blue tier
CHART_ACCENT_HI_N = LIVE_RATE_GREEN  # large sample — same green as best card tier
CHART_ACCENT_NP = LIVE_RATE_BLUE  # >1 expected shiny — same blue as card 1/500+ tier

# jsDelivr serves the same PokeAPI sprite repo with better availability than
# raw.githubusercontent.com (fewer timeouts / rate limits when loading many images).
_SPRITES_CDN = (
    "https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master/sprites/pokemon"
)

FALLBACK_IMAGE = f"{_SPRITES_CDN}/0.png"


def _cdn_artwork_url(pokemon_id: int) -> str:
    return f"{_SPRITES_CDN}/other/official-artwork/{int(pokemon_id)}.png"


def _cdn_default_sprite_url(pokemon_id: int) -> str:
    return f"{_SPRITES_CDN}/{int(pokemon_id)}.png"


def _img_fallback_onerror(secondary_url: str, final_url: str) -> str:
    """Chained client-side fallback when the primary sprite URL fails."""

    def _js_single_quoted(url: str) -> str:
        return url.replace("\\", "\\\\").replace("'", "\\'")

    s2, s3 = _js_single_quoted(secondary_url), _js_single_quoted(final_url)
    return (
        "this.onerror=null;"
        f"if(!this.dataset.imgfb){{this.dataset.imgfb='1';this.src='{s2}';}}"
        f"else{{this.src='{s3}'}}"
    )


def pokemon_img_html(pokemon_id: int) -> str:
    pid = int(pokemon_id)
    primary = _cdn_artwork_url(pid)
    secondary = _cdn_default_sprite_url(pid)
    onerr = _img_fallback_onerror(secondary, FALLBACK_IMAGE)
    return (
        f'<img src="{primary}" alt="" width="96" height="96" '
        f'decoding="async" loading="lazy" '
        f'onerror="{onerr}"'
        ">"
    )

FILTER_TAGS = [
    "Released", "Not Released", "Shundo", "Not Shundo", "Lucky", "Not Lucky",
    "Tradeable", "Untradeable", "Legendary", "Not Legendary",
]

SORT_OPTIONS = [
    "Pokédex Order", "Alphabetical", "Shundo First", "Lucky First", "Legendary First",
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

    /* ── Rate cards (Live Rates) — same base fill as bar chart / --bg-main ── */
    .rate-card {
        background: var(--bg-main) !important; border-radius: 10px;
        padding: 12px 6px 8px; text-align: center; min-height: 120px;
        border: 1px solid rgba(255,255,255,0.025);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    .rate-card:hover {
        background: var(--bg-main) !important;
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
        display: block; line-height: 1.35;
        overflow-wrap: anywhere; word-break: break-word;
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
            overflow: visible !important;
        }
        /* Avoid clipping the bottom of custom HTML cards (e.g. rate n= line) */
        [data-testid="stHorizontalBlock"]:has(> :nth-child(5)) > [data-testid="stColumn"] > div {
            overflow: visible !important;
        }
        [data-testid="stHorizontalBlock"]:has(> :nth-child(5)) [data-testid="stMarkdownContainer"] {
            overflow: visible !important;
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
            padding: 8px 2px 12px; min-height: min-content;
            border-radius: 8px;
            overflow: visible;
            box-sizing: border-box;
        }
        .rate-card img { width: 30px; height: 30px; }
        .rate-card:hover { transform: none; box-shadow: none; }
        .rate-card:hover img { transform: none; }
        .rate-name { font-size: 8px; margin-top: 3px; line-height: 1.25; }
        .rate-id { font-size: 7px; }
        .rate-badges {
            margin-top: 2px; line-height: 1.45;
            max-width: 100%; overflow-wrap: anywhere;
        }
        .rate-sample {
            font-size: 6px; margin-top: 4px; padding-bottom: 2px;
            line-height: 1.35;
        }

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


@st.cache_data(show_spinner=False)
def load_pokemon(_csv_mtime: float) -> pd.DataFrame:
    _ = _csv_mtime  # cache invalidates when pokemon.csv changes on disk
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


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_released_ids_cached() -> frozenset[int]:
    req = urllib.request.Request(
        RELEASED_API_URL, headers={"User-Agent": "Mozilla/5.0"}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    return frozenset(int(k) for k in data)


def fetch_released_ids() -> set[int]:
    try:
        return set(_fetch_released_ids_cached())
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


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_shiny_rates_cached() -> pd.DataFrame:
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
    return df[["pokemon_id", "rate", "sample_size", "shiny_rate_value"]]


def fetch_shiny_rates() -> pd.DataFrame | None:
    try:
        return _fetch_shiny_rates_cached()
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
    if "tradeable" not in df.columns:
        df["tradeable"] = True
    if "legendary" not in df.columns:
        df["legendary"] = False
    df["tradeable"] = df["tradeable"].fillna(True).astype(bool)
    df["legendary"] = df["legendary"].fillna(False).astype(bool)
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
    filtered = df

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
        "Legendary": ("legendary", False),
        "Not Legendary": ("legendary", True),
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
        "Legendary First": (["legendary", "pokemon_id"], [False, True]),
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
    if row.get("legendary", False):
        parts.append(badge("Legendary", "rgba(255,215,0,0.12)", "#e0c050"))

    badge_html = " ".join(parts)

    active = "pk-active" if toggle_tag and row.get(toggle_tag, False) else ""

    st.markdown(
        f'<div class="pk-card {active}">'
        f'{pokemon_img_html(int(row["pokemon_id"]))}'
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


def _live_rate_bar_threshold(filtered: pd.DataFrame) -> float | None:
    """Same n threshold as the bar chart (quantile on top-N list by rate)."""
    elig = filtered[filtered["shiny_rate_value"] >= BAR_CHART_MIN_PROB].copy()
    if elig.empty:
        return None
    top = elig.sort_values("shiny_rate_value", ascending=False).head(BAR_CHART_TOP_N)
    q_thr = float(top["sample_size"].quantile(BAR_CHART_LARGE_SAMPLE_Q))
    return max(q_thr, float(BAR_CHART_LARGE_SAMPLE_MIN_N), 1.0)


def _live_rate_bar_accent(
    rate_val: float, sample_size: float, thr: float | None
) -> str:
    """Border/badge color: matches bar chart tiers (green / blue / muted)."""
    if thr is None or float(rate_val) < BAR_CHART_MIN_PROB:
        return CHART_MUTED
    n, p = float(sample_size), float(rate_val)
    if n >= thr:
        return LIVE_RATE_GREEN
    if n * p > 1:
        return LIVE_RATE_BLUE
    return CHART_MUTED


def _render_shiny_rate_cards(filtered: pd.DataFrame) -> None:
    thr = _live_rate_bar_threshold(filtered)
    _GLOW = {
        LIVE_RATE_GREEN: "rgba(16,185,129,0.10)",
        LIVE_RATE_BLUE: "rgba(59,130,246,0.10)",
        CHART_MUTED: "none",
    }

    for i in range(0, len(filtered), CARDS_PER_ROW):
        cols = st.columns(CARDS_PER_ROW)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(filtered):
                row = filtered.iloc[idx]
                with col:
                    accent = _live_rate_bar_accent(
                        row["shiny_rate_value"], row["sample_size"], thr
                    )
                    badges_html = badge(row["rate"], accent)
                    glow = _GLOW.get(accent, "none")
                    shadow = f"box-shadow:0 -4px 20px {glow};" if glow != "none" else ""
                    st.markdown(
                        f'<div class="rate-card" style="border-top:2px solid {accent};{shadow}">'
                        f'{pokemon_img_html(int(row["pokemon_id"]))}'
                        f'<div class="rate-name">{row["name"]}</div>'
                        f'<div class="rate-id">#{row["pokemon_id"]}</div>'
                        f'<div class="rate-badges">{badges_html}</div>'
                        f'<div class="rate-sample">n={row["sample_size"]:,}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


def _render_shiny_rate_bar_chart(filtered: pd.DataFrame) -> None:
    """Short list of best reported rates; icons + bars on app background colors."""
    thr = _live_rate_bar_threshold(filtered)
    if thr is None:
        st.info(
            f"No Pokémon in this filter with rate ≥ **1 in {round(1 / BAR_CHART_MIN_PROB)}** "
            "on the live list. Loosen filters or use **Cards**."
        )
        return

    elig = filtered[filtered["shiny_rate_value"] >= BAR_CHART_MIN_PROB].copy()
    elig = elig.sort_values("shiny_rate_value", ascending=False).head(BAR_CHART_TOP_N)

    chart_df = elig.copy()
    chart_df["bar_label"] = (
        "#" + chart_df["pokemon_id"].astype(int).astype(str) + " " + chart_df["name"].astype(str)
    )
    chart_df["sprite_url"] = chart_df["pokemon_id"].astype(int).map(_cdn_default_sprite_url)
    chart_df["icon_x"] = 0.0

    lo = f"Standard (n < {thr:,.0f})"
    hi = f"Large sample (n ≥ {thr:,.0f})"
    hi_np = ">1 expected shiny"
    mask_teal = chart_df["sample_size"] >= thr
    mask_np = chart_df["sample_size"] * chart_df["shiny_rate_value"] > 1
    # Green (large n) first; blue only if not green and n×p > 1; else standard.
    chart_df["bar_tier"] = lo
    chart_df.loc[mask_np & ~mask_teal, "bar_tier"] = hi_np
    chart_df.loc[mask_teal, "bar_tier"] = hi

    # Custom Y order: list bar_label from best to worst rate so highest odds are at the top.
    bar_labels_y_order = (
        chart_df.sort_values("shiny_rate_value", ascending=False)["bar_label"].tolist()
    )

    row_step = 20
    h = int(max(220, len(chart_df) * row_step + 56))
    y_icons = alt.Y(
        "bar_label:N",
        axis=None,
        sort=bar_labels_y_order,
        title=None,
    )
    y_bars = alt.Y(
        "bar_label:N",
        axis=alt.Axis(
            domainColor=CHART_GRID,
            labelColor="#d8d8e8",
            tickColor=CHART_GRID,
            grid=False,
            labelFontSize=12,
            labelLimit=200,
            title=None,
        ),
        sort=bar_labels_y_order,
        title=None,
    )

    color_scale = alt.Scale(
        domain=[lo, hi, hi_np],
        range=[CHART_MUTED, CHART_ACCENT_HI_N, CHART_ACCENT_NP],
    )

    tooltip = [
        alt.Tooltip("name:N", title="Pokémon"),
        alt.Tooltip("pokemon_id:Q", title="ID"),
        alt.Tooltip("rate:N", title="Reported rate"),
        alt.Tooltip("shiny_rate_value:Q", title="Probability", format=".3%"),
        alt.Tooltip("sample_size:Q", title="Sample n", format=","),
    ]

    icon_chart = (
        alt.Chart(chart_df)
        .mark_image(width=36, height=36)
        .encode(
            x=alt.X(
                "icon_x:Q",
                axis=None,
                scale=alt.Scale(domain=[-0.5, 0.5], range=[0, 52], nice=False, zero=False),
            ),
            y=y_icons,
            url="sprite_url:N",
            tooltip=tooltip,
        )
        .properties(width=56, height=h)
    )

    bar_chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusEnd=4, height=14)
        .encode(
            x=alt.X(
                "shiny_rate_value:Q",
                title=None,
                axis=alt.Axis(
                    format=".2%",
                    grid=True,
                    domainColor=CHART_GRID,
                    gridColor=CHART_GRID,
                    tickColor=CHART_GRID,
                    labelColor="#a7a7bf",
                    titleColor="#a7a7bf",
                    titlePadding=8,
                    title="Chance (live estimate)",
                ),
            ),
            y=y_bars,
            color=alt.Color(
                "bar_tier:N",
                scale=color_scale,
                legend=alt.Legend(
                    orient="top",
                    title=None,
                    labelColor="#d8d8e8",
                    symbolType="square",
                ),
            ),
            tooltip=tooltip,
        )
        .properties(height=h)
    )

    chart = (
        (icon_chart | bar_chart)
        .resolve_scale(y="shared")
        .configure(background=CHART_BG)
        .configure_view(fill=CHART_BG, stroke=None)
        .configure_concat(spacing=6)
    )

    # theme=None: skip Streamlit’s Vega theme merge each rerun (can reduce chart flash).
    st.altair_chart(chart, use_container_width=True, theme=None)
    st.caption(
        f"Sorted **best → worst** shiny chance (top to bottom). Up to **{BAR_CHART_TOP_N}** species "
        f"with rate **≥ 1/{round(1 / BAR_CHART_MIN_PROB)}** after filters (**{len(chart_df)}** shown). "
        f"Colors match **Cards**: **green** = large n (≥ **{thr:,.0f}**); **blue** = **>1 expected shiny** "
        f"if not green."
    )


def render_shiny_rates(merged: pd.DataFrame) -> None:
    col_refresh, col_view, col_filter = st.columns([1, 2, 3])
    with col_refresh:
        if st.button("Refresh", key="refresh_shiny_rates"):
            _fetch_shiny_rates_cached.clear()
            st.rerun()
    with col_view:
        view_mode = st.radio(
            "View",
            ["Cards", "Bar chart"],
            index=1,
            horizontal=True,
            label_visibility="collapsed",
            key="shiny_rates_view",
        )
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
        "Legendary": ("legendary", False),
        "Not Legendary": ("legendary", True),
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

    if view_mode == "Bar chart":
        _render_shiny_rate_bar_chart(filtered)
    else:
        _render_shiny_rate_cards(filtered)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_controls():
    c_search, c_gen, c_sort, c_toggle = st.columns([3, 1, 1, 1])
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
    with c_toggle:
        toggle_options = ["Toggle: Off", "Toggle: Shundo", "Toggle: Lucky"]
        toggle_mode = st.selectbox("toggle", toggle_options, label_visibility="collapsed")
        toggle_tag = None if toggle_mode == "Toggle: Off" else toggle_mode.split(": ")[1].lower()

    c_tags, c_opts = st.columns([3, 1])
    with c_tags:
        filter_tags = st.multiselect(
            "Filter", FILTER_TAGS, default=["Released"],
        )
    with c_opts:
        root_only = st.checkbox("Root only")
        show_family = st.checkbox("Full family")

    return search, filter_tags, gen_opt, sort_opt, root_only, show_family, toggle_tag


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

    pokemon_df = load_pokemon(POKEMON_PATH.stat().st_mtime)
    collection_df = load_collection()
    collection_df = ensure_collection_complete(pokemon_df, collection_df)
    merged = merge_data(pokemon_df, collection_df)

    # Sidebar — secondary controls (collapsed by default)
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
        search, filter_tags, gen_opt, sort_opt, root_only, show_family, toggle_tag = render_controls()
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
