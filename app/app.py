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
        """
    <style>
    /* ── Base ── */
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] { background: #f9fafb; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {
        font-size: 13px; font-weight: 700; color: #374151;
        letter-spacing: 0.06em; text-transform: uppercase;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
        font-size: 11px; font-weight: 700; color: #9ca3af;
        text-transform: uppercase; letter-spacing: 0.06em;
    }
    section[data-testid="stSidebar"] hr {
        border: none; border-top: 1px solid #f0f0f0; margin: 14px 0;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0; border-bottom: 1px solid #edf0f2; background: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 13px; font-weight: 500; color: #9ca3af;
        padding: 10px 24px; background: transparent;
    }
    .stTabs [aria-selected="true"] { color: #1a1a2e; font-weight: 600; }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 6px; font-size: 11px; font-weight: 500;
        border: 1px solid #e5e7eb; background: #fff; color: #6b7280;
        padding: 4px 14px; transition: all 0.15s ease;
        box-shadow: none;
    }
    .stButton > button:hover {
        background: #f9fafb; border-color: #d1d5db; color: #374151;
    }
    .stButton > button[kind="primary"] {
        background: #374151; color: #fff; border-color: #374151;
    }
    .stButton > button[kind="primary"]:hover {
        background: #1f2937; border-color: #1f2937;
    }

    /* ── Cards ── */
    .pk-card {
        background: #f9fafb; border-radius: 10px; padding: 16px 8px 12px;
        text-align: center; min-height: 140px; border: 1px solid transparent;
        transition: background 0.15s ease, border-color 0.15s ease;
    }
    .pk-card:hover { background: #f3f4f6; }
    .pk-card.pk-active { border-color: #8b5cf6; background: #faf5ff; }
    .pk-card img { width: 56px; height: 56px; object-fit: contain; }
    .pk-name {
        font-weight: 600; font-size: 11.5px; color: #1a1a2e;
        margin-top: 6px; line-height: 1.3;
    }
    .pk-id { font-size: 10px; color: #b0b8c1; margin-top: 2px; }
    .pk-badges { margin-top: 5px; min-height: 18px; line-height: 1.8; }
    .pk-badge {
        display: inline-block; font-size: 9px; font-weight: 600;
        letter-spacing: 0.02em; padding: 1px 6px; border-radius: 3px;
        margin: 1px;
    }

    /* ── Rate cards ── */
    .rate-card {
        background: #f9fafb; border-radius: 10px; padding: 16px 8px 12px;
        text-align: center; min-height: 155px;
        transition: background 0.15s ease;
    }
    .rate-card:hover { background: #f3f4f6; }
    .rate-card img { width: 52px; height: 52px; object-fit: contain; }
    .rate-name {
        font-weight: 600; font-size: 11.5px; color: #1a1a2e;
        margin-top: 6px; line-height: 1.3;
    }
    .rate-id { font-size: 10px; color: #b0b8c1; margin-top: 2px; }
    .rate-badges { margin-top: 6px; line-height: 1.8; }
    .rate-sample { font-size: 9px; color: #c4c9d0; margin-top: 3px; }

    /* ── Summary bar ── */
    .summary-bar {
        display: flex; gap: 20px; font-size: 12px; color: #9ca3af;
        padding: 4px 0; align-items: baseline;
    }
    .summary-bar .s-label { font-weight: 500; }
    .summary-bar .s-val { color: #374151; font-weight: 600; margin-left: 4px; }

    /* ── Page nav ── */
    .page-info {
        text-align: center; font-size: 12px; color: #9ca3af;
        padding: 8px 0; font-weight: 500;
    }

    /* ── Count label ── */
    .count-label { font-size: 12px; color: #9ca3af; padding: 4px 0; }
    .count-label b { color: #374151; font-weight: 600; }

    /* ── Multiselect tags ── */
    [data-baseweb="tag"] { border-radius: 4px !important; }
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


def render_summary(df: pd.DataFrame) -> None:
    total = len(df)
    shundo = int(df["shundo"].sum())
    lucky = int(df["lucky"].sum())
    st.markdown(
        f'<div class="summary-bar">'
        f'<span><span class="s-label">Showing</span><span class="s-val">{total}</span></span>'
        f'<span><span class="s-label">Shundo</span><span class="s-val">{shundo}</span></span>'
        f'<span><span class="s-label">Lucky</span><span class="s-val">{lucky}</span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_card(
    row: pd.Series, toggle_tag: str | None, collection_df: pd.DataFrame
) -> None:
    parts: list[str] = []
    if row["shundo"]:
        parts.append(badge("Shundo", "#8b5cf6"))
    if row["lucky"]:
        parts.append(badge("Lucky", "#f59e0b"))
    if not row.get("tradeable", True):
        parts.append(badge("Untradeable", "#d1d5db", "#6b7280"))

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
        f'<div class="count-label"><b>{len(filtered)}</b> Pokémon with live rates</div>',
        unsafe_allow_html=True,
    )

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
                        accent = "#d1d5db"
                    badges_html = badge(row["rate"], accent)
                    if row.get("shundo", False):
                        badges_html += " " + badge("✦", "#8b5cf6")
                    if row.get("lucky", False):
                        badges_html += " " + badge("✦", "#f59e0b")
                    st.markdown(
                        f'<div class="rate-card" style="border-top:3px solid {accent};">'
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


def render_sidebar_filters(merged: pd.DataFrame):
    st.sidebar.title("Filters")
    search = st.sidebar.text_input("Search", placeholder="Pokémon name…")

    filter_tags = st.sidebar.multiselect("Tags", FILTER_TAGS, default=["Released"])

    c1, c2 = st.sidebar.columns(2)
    gen_options = ["All"] + [f"Gen {i}" for i in range(1, 10)]
    gen_opt = c1.selectbox("Generation", gen_options)
    sort_opt = c2.selectbox("Sort", SORT_OPTIONS)

    root_only = st.sidebar.checkbox("Root representatives only")
    show_family = st.sidebar.checkbox("Expand to full family")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Toggle Mode")
    toggle_options = ["Off", "Shundo", "Lucky"]
    toggle_mode = st.sidebar.selectbox("Click cards to toggle", toggle_options)
    toggle_tag = None if toggle_mode == "Off" else toggle_mode.lower()

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
        page_title="Pokémon GO Tracker", layout="wide", page_icon="🎮"
    )
    inject_css()

    pokemon_df = load_pokemon()
    collection_df = load_collection()
    collection_df = ensure_collection_complete(pokemon_df, collection_df)
    merged = merge_data(pokemon_df, collection_df)

    tab_collection, tab_shiny = st.tabs(["Collection", "Live Shiny Rates"])

    with tab_collection:
        search, filter_tags, gen_opt, sort_opt, root_only, show_family, toggle_tag = render_sidebar_filters(merged)
        filtered = apply_filters(merged, search, filter_tags, gen_opt, sort_opt, root_only, show_family)

        total_pages = max(1, -(-len(filtered) // CARDS_PER_PAGE))

        if "page" not in st.session_state:
            st.session_state.page = 1
        st.session_state.page = min(st.session_state.page, total_pages)

        page_start = (st.session_state.page - 1) * CARDS_PER_PAGE + 1
        page_end = min(st.session_state.page * CARDS_PER_PAGE, len(filtered))

        col_summary, col_nav = st.columns([3, 2])
        with col_summary:
            render_summary(filtered)
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
        page = st.session_state.page - 1

        render_grid(filtered, page, toggle_tag, collection_df)

    with tab_shiny:
        render_shiny_rates(merged)

    render_sidebar_editor(merged, collection_df)
    render_sidebar_export(filtered)


if __name__ == "__main__":
    main()
