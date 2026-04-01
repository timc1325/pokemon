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


def get_shiny_targets(
    merged: pd.DataFrame, rates_df: pd.DataFrame
) -> pd.DataFrame:
    owned_ids = set(merged.loc[merged["shundo"], "pokemon_id"])
    owned_families = set(merged.loc[merged["pokemon_id"].isin(owned_ids), "family_id"])
    targets = merged.merge(rates_df, on="pokemon_id", how="inner")
    targets = targets[~targets["family_id"].isin(owned_families)].copy()
    targets = targets.sort_values(
        ["shiny_rate_value", "sample_size"], ascending=[False, False]
    ).reset_index(drop=True)
    return targets


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
        f'<span style="background:{bg};color:{fg};padding:2px 6px;'
        f'border-radius:4px;font-size:11px;margin:1px;'
        f'display:inline-block;">{label}</span>'
    )


def render_summary(df: pd.DataFrame) -> None:
    total = len(df)
    shundo = int(df["shundo"].sum())
    lucky = int(df["lucky"].sum())
    not_shundo = total - shundo
    released = int(df["released"].sum()) if "released" in df.columns else total
    st.markdown(
        f'<div style="display:flex;gap:24px;font-size:13px;padding:4px 0;">'
        f'<span><b>Showing:</b> {total}</span>'
        f'<span><b>Shundo:</b> {shundo}</span>'
        f'<span><b>Not Shundo:</b> {not_shundo}</span>'
        f'<span><b>Lucky:</b> {lucky}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_card(
    row: pd.Series, toggle_tag: str | None, collection_df: pd.DataFrame
) -> None:
    badges: list[str] = []
    if row["shundo"]:
        badges.append(badge("🌟 Shundo", "#9C27B0"))
    if row["lucky"]:
        badges.append(badge("🍀 Lucky", "#FF9800"))
    if not row.get("tradeable", True):
        badges.append(badge("🚫 Untradeable", "#757575"))

    badge_str = (
        " ".join(badges) if badges
        else '<span style="color:#999;font-size:11px;">—</span>'
    )

    image_url = row.get("image_url", "")
    if pd.isna(image_url) or not image_url:
        image_url = FALLBACK_IMAGE

    border = "2px solid #4CAF50" if toggle_tag and row.get(toggle_tag, False) else "1px solid #e0e0e0"

    st.markdown(
        f"""
        <div style="border:{border};border-radius:8px;padding:6px;
                    text-align:center;min-height:150px;background:#fafafa;">
            <img src="{image_url}" width="56" height="56"
                 style="object-fit:contain;"
                 onerror="this.src='{FALLBACK_IMAGE}'" loading="lazy">
            <div style="font-weight:bold;margin-top:3px;font-size:12px;">{row['name']}</div>
            <div style="color:#666;font-size:10px;">#{row['pokemon_id']}</div>
            <div style="margin-top:4px;line-height:1.6;">{badge_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    show_toggle = toggle_tag and (
        toggle_tag != "lucky" or row.get("tradeable", True)
    )
    if show_toggle:
        pid = int(row["pokemon_id"])
        current = bool(row.get(toggle_tag, False))
        icon = "✓" if current else "✗"
        if st.button(
            f"{icon} {toggle_tag.title()}",
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
    if st.button("🔄 Refresh Rates", key="refresh_shiny_rates"):
        st.session_state.pop("shiny_rates_df", None)
        st.rerun()

    rates_df = fetch_shiny_rates()
    if rates_df is None:
        st.warning("Could not fetch live shiny rates from shinyrates.com")
        return

    targets = get_shiny_targets(merged, rates_df)
    if targets.empty:
        st.success("You have shundos for every family with live boosted rates!")
        return

    st.markdown(
        f'<div style="font-size:13px;padding:4px 0;margin-bottom:8px;">'
        f'<b>{len(targets)}</b> shiny targets you don\'t have yet, '
        f'sorted by highest shiny rate'
        f'</div>',
        unsafe_allow_html=True,
    )

    for i in range(0, len(targets), CARDS_PER_ROW):
        cols = st.columns(CARDS_PER_ROW)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(targets):
                row = targets.iloc[idx]
                with col:
                    image_url = row.get("image_url", "")
                    if pd.isna(image_url) or not image_url:
                        image_url = FALLBACK_IMAGE
                    rate_str = row["rate"]
                    sample = row["sample_size"]
                    rate_val = row["shiny_rate_value"]
                    if rate_val >= 1 / 100:
                        rate_color = "#4CAF50"
                    elif rate_val >= 1 / 300:
                        rate_color = "#FF9800"
                    elif rate_val >= 1 / 500:
                        rate_color = "#2196F3"
                    else:
                        rate_color = "#9E9E9E"
                    st.markdown(
                        f"""
                        <div style="border:2px solid {rate_color};border-radius:8px;
                                    padding:6px;text-align:center;min-height:170px;
                                    background:#fafafa;">
                            <img src="{image_url}" width="56" height="56"
                                 style="object-fit:contain;"
                                 onerror="this.src='{FALLBACK_IMAGE}'" loading="lazy">
                            <div style="font-weight:bold;margin-top:3px;font-size:12px;">
                                {row['name']}</div>
                            <div style="color:#666;font-size:10px;">#{row['pokemon_id']}</div>
                            <div style="margin-top:4px;">
                                {badge(rate_str, rate_color)}
                            </div>
                            <div style="color:#999;font-size:9px;margin-top:2px;">
                                sample: {sample:,}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar_filters(merged: pd.DataFrame):
    st.sidebar.title("Filters")
    search = st.sidebar.text_input("Search by name")

    filter_tags = st.sidebar.multiselect("Filter tags", FILTER_TAGS, default=["Released"])

    gen_options = ["All"] + [f"Gen {i}" for i in range(1, 10)]
    gen_opt = st.sidebar.selectbox("Generation", gen_options)

    sort_opt = st.sidebar.selectbox("Sort", SORT_OPTIONS)

    root_only = st.sidebar.checkbox("Show only root representatives")
    show_family = st.sidebar.checkbox("Show all family members")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Toggle Mode")
    toggle_options = ["Off", "Shundo", "Lucky"]
    toggle_mode = st.sidebar.selectbox("Click cards to toggle", toggle_options)
    toggle_tag = None if toggle_mode == "Off" else toggle_mode.lower()

    return search, filter_tags, gen_opt, sort_opt, root_only, show_family, toggle_tag


def render_sidebar_editor(merged: pd.DataFrame, collection_df: pd.DataFrame):
    st.sidebar.markdown("---")
    st.sidebar.subheader("Edit Pokémon")

    options = merged.sort_values("pokemon_id").apply(
        lambda r: f"#{r['pokemon_id']} {r['name']}", axis=1
    ).tolist()

    selected = st.sidebar.selectbox("Select Pokémon", options, key="edit_select")
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
            st.caption("🚫 Untradeable — cannot be lucky")
        submitted = st.form_submit_button("💾 Save")

    if submitted:
        idx = collection_df[collection_df["pokemon_id"] == pokemon_id].index[0]
        collection_df.at[idx, "shundo"] = shundo
        collection_df.at[idx, "lucky"] = lucky
        save_collection(collection_df)
        st.sidebar.success(f"Saved #{pokemon_id}!")
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
        "📥 Export filtered CSV", csv_data, "filtered_pokemon.csv", "text/csv"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(
        page_title="Pokémon GO Tracker", layout="wide", page_icon="🎮"
    )
    pokemon_df = load_pokemon()
    collection_df = load_collection()
    collection_df = ensure_collection_complete(pokemon_df, collection_df)
    merged = merge_data(pokemon_df, collection_df)

    tab_collection, tab_shiny = st.tabs(["📦 Collection", "🔥 Live Shiny Rates"])

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
                if st.button("◀", disabled=st.session_state.page <= 1, use_container_width=True):
                    st.session_state.page -= 1
                    st.rerun()
            with c2:
                st.markdown(
                    f'<div style="text-align:center;font-size:13px;padding:8px 0;">'
                    f'{page_start}–{page_end} of {len(filtered)} '
                    f'({st.session_state.page}/{total_pages})</div>',
                    unsafe_allow_html=True,
                )
            with c3:
                if st.button("▶", disabled=st.session_state.page >= total_pages, use_container_width=True):
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
