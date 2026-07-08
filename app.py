from __future__ import annotations

import base64
from datetime import datetime

import pandas as pd
import streamlit as st

from label_pdf import LabelItem, LabelSheetSettings, SYMBOL_LABELS, build_label_pdf, validate_layout


PAGE_FORMATS_MM = {
    "A4": (210.0, 297.0),
    "Letter": (215.9, 279.4),
    "Personnalise": (210.0, 297.0),
}

DEFAULT_ROWS = [
    {"Qte": 16, "Symbole": "Resistance", "Texte": "10k", "Valeur": "", "Note": ""},
    {"Qte": 16, "Symbole": "Condensateur", "Texte": "100n", "Valeur": "", "Note": ""},
    {"Qte": 24, "Symbole": "M3", "Texte": "", "Valeur": "", "Note": ""},
]

SYMBOL_BANK_GROUPS = {
    "Electronique": [
        "resistor",
        "capacitor",
        "electrolytic",
        "diode",
        "led",
        "transistor_npn",
        "ground",
        "switch",
        "inductor",
        "ic",
        "battery",
        "fuse",
    ],
    "Vis": [
        "screw_m1_6",
        "screw_m2",
        "screw_m2_5",
        "screw_m3",
        "screw_m4",
        "screw_m5",
        "screw_m6",
        "screw_m8",
    ],
}


def main() -> None:
    st.set_page_config(page_title="Editeur d'etiquettes", page_icon="label", layout="wide")
    _inject_css()

    _ensure_editor_state()

    settings = _sidebar_settings()

    st.title("Editeur d'etiquettes atelier")

    editor_col, preview_col = st.columns([1.08, 0.92], gap="large")
    with editor_col:
        _symbol_bank()
        st.subheader("Etiquettes")
        edited = st.data_editor(
            pd.DataFrame(st.session_state.rows),
            key="labels_editor",
            hide_index=True,
            num_rows="dynamic",
            width="stretch",
            column_config={
                "Qte": st.column_config.NumberColumn("Qte", min_value=0, max_value=500, step=1, width="small"),
                "Symbole": st.column_config.SelectboxColumn(
                    "Symbole",
                    options=list(_label_to_symbol().keys()),
                    width="medium",
                ),
                "Texte": st.column_config.TextColumn("Texte", width="medium"),
                "Valeur": st.column_config.TextColumn("Valeur", width="medium"),
                "Note": st.column_config.TextColumn("Note", width="large"),
            },
        )
        st.session_state.rows = _dataframe_to_rows(edited)

        items = _rows_to_items(st.session_state.rows)
        errors = validate_layout(settings)
        total_labels = sum(item.quantity for item in items)
        page_count = max(1, (settings.skip_slots + total_labels + settings.capacity_per_page - 1) // settings.capacity_per_page)

        metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
        metric_col_1.metric("Etiquettes", total_labels)
        metric_col_2.metric("Par page", settings.capacity_per_page)
        metric_col_3.metric("Pages PDF", page_count)

        if errors:
            for error in errors:
                st.error(error)

        pdf_bytes = b""
        if items and not errors:
            pdf_bytes = build_label_pdf(items, settings)

        st.download_button(
            "Telecharger le PDF",
            data=pdf_bytes,
            file_name=f"etiquettes_atelier_{datetime.now():%Y%m%d_%H%M}.pdf",
            mime="application/pdf",
            type="primary",
            icon=":material/download:",
            width="stretch",
            disabled=not pdf_bytes,
        )

    with preview_col:
        st.subheader("Apercu PDF")
        if pdf_bytes:
            st.iframe(_pdf_data_url(pdf_bytes), height=_preview_height(settings), width="stretch")
        else:
            st.info("Aucun PDF a afficher.")


def _sidebar_settings() -> LabelSheetSettings:
    st.sidebar.header("Format")
    paper = st.sidebar.selectbox("Papier", list(PAGE_FORMATS_MM.keys()), index=0)
    default_width, default_height = PAGE_FORMATS_MM[paper]

    if paper == "Personnalise":
        page_width = st.sidebar.number_input("Largeur page (mm)", min_value=20.0, max_value=500.0, value=default_width, step=1.0)
        page_height = st.sidebar.number_input("Hauteur page (mm)", min_value=20.0, max_value=700.0, value=default_height, step=1.0)
    else:
        page_width, page_height = default_width, default_height

    label_width = st.sidebar.number_input("Largeur etiquette (mm)", min_value=5.0, max_value=200.0, value=12.5, step=0.5)
    label_height = st.sidebar.number_input("Hauteur etiquette (mm)", min_value=5.0, max_value=100.0, value=10.0, step=0.5)

    columns = st.sidebar.number_input("Colonnes", min_value=1, max_value=50, value=16, step=1)
    rows = st.sidebar.number_input("Lignes", min_value=1, max_value=80, value=29, step=1)

    margin_left = st.sidebar.number_input("Marge gauche (mm)", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
    margin_top = st.sidebar.number_input("Marge haute (mm)", min_value=0.0, max_value=100.0, value=3.5, step=0.5)
    gap_x = st.sidebar.number_input("Espace horizontal (mm)", min_value=0.0, max_value=50.0, value=0.0, step=0.1)
    gap_y = st.sidebar.number_input("Espace vertical (mm)", min_value=0.0, max_value=50.0, value=0.0, step=0.1)

    capacity = int(columns * rows)
    skip_slots = st.sidebar.number_input("Cases deja utilisees", min_value=0, max_value=max(0, capacity - 1), value=0, step=1)

    st.sidebar.header("Style")
    show_border = st.sidebar.checkbox("Contour", value=True)
    cut_marks = st.sidebar.checkbox("Reperes de coupe", value=True)
    font_scale = st.sidebar.slider("Taille du texte", min_value=0.75, max_value=1.35, value=1.0, step=0.05)

    return LabelSheetSettings(
        page_width_mm=float(page_width),
        page_height_mm=float(page_height),
        label_width_mm=float(label_width),
        label_height_mm=float(label_height),
        columns=int(columns),
        rows=int(rows),
        margin_left_mm=float(margin_left),
        margin_top_mm=float(margin_top),
        gap_x_mm=float(gap_x),
        gap_y_mm=float(gap_y),
        skip_slots=int(skip_slots),
        show_border=show_border,
        cut_marks=cut_marks,
        font_scale=float(font_scale),
    )


def _symbol_bank() -> None:
    st.subheader("Banque de symboles")
    tabs = st.tabs(list(SYMBOL_BANK_GROUPS.keys()))
    for tab, (group_name, symbols) in zip(tabs, SYMBOL_BANK_GROUPS.items()):
        with tab:
            column_count = 4 if group_name == "Vis" else 3
            _symbol_button_grid(symbols, column_count)


def _symbol_button_grid(symbols: list[str], column_count: int) -> None:
    for start in range(0, len(symbols), column_count):
        columns = st.columns(column_count)
        for column, symbol in zip(columns, symbols[start : start + column_count]):
            label = SYMBOL_LABELS[symbol]
            with column:
                if st.button(label, key=f"bank_{symbol}", width="stretch"):
                    _append_symbol_row(symbol)


def _append_symbol_row(symbol: str) -> None:
    rows = list(st.session_state.rows)
    rows.append(
        {
            "Qte": 1,
            "Symbole": SYMBOL_LABELS[symbol],
            "Texte": "",
            "Valeur": "",
            "Note": "",
        }
    )
    st.session_state.rows = rows
    st.session_state.pop("labels_editor", None)


def _ensure_editor_state() -> None:
    if "rows" not in st.session_state:
        st.session_state.rows = [row.copy() for row in DEFAULT_ROWS]


def _dataframe_to_rows(data: pd.DataFrame) -> list[dict[str, object]]:
    return data.fillna("").to_dict("records")


def _rows_to_items(rows: list[dict[str, object]]) -> list[LabelItem]:
    mapping = _label_to_symbol()
    items: list[LabelItem] = []
    for row in rows:
        quantity = int(row.get("Qte") or 0)
        symbol = mapping.get(str(row.get("Symbole") or "Aucun"), "none")
        text = str(row.get("Texte") or "").strip()
        value = str(row.get("Valeur") or "").strip()
        note = str(row.get("Note") or "").strip()
        if quantity <= 0:
            continue
        if symbol == "none" and not any([text, value, note]):
            continue
        items.append(
            LabelItem(
                quantity=quantity,
                symbol=symbol,
                text=text,
                value=value,
                note=note,
            )
        )
    return items


def _label_to_symbol() -> dict[str, str]:
    return {label: key for key, label in SYMBOL_LABELS.items()}


def _preview_height(settings: LabelSheetSettings) -> int:
    ratio = settings.page_height_mm / max(settings.page_width_mm, 1)
    return int(min(760, max(420, 520 * ratio)))


def _pdf_data_url(pdf_bytes: bytes) -> str:
    encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")
    return f"data:application/pdf;base64,{encoded_pdf}#toolbar=0&navpanes=0&view=FitH"


def _inject_css() -> None:
    st.markdown(
        """
        <style>
            :root {
                color-scheme: dark;
            }
            html,
            body,
            .stApp,
            [data-testid="stApp"],
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"],
            [data-testid="stMainBlockContainer"],
            section.main,
            .main {
                background: #11100f !important;
                color: #f4f1ea !important;
            }
            .block-container {
                background: transparent !important;
                color: #f4f1ea !important;
            }
            h1, h2, h3 {
                letter-spacing: 0;
                color: #f4f1ea !important;
            }
            p, label, span, div {
                border-color: #3b352f;
            }
            [data-testid="stSidebar"] {
                background: #171512 !important;
                border-right: 1px solid #3b352f !important;
            }
            [data-testid="stSidebar"] * {
                color: #f4f1ea !important;
            }
            [data-testid="stHeader"] {
                background: rgba(17, 16, 15, 0.92) !important;
                border-bottom: 1px solid rgba(59, 53, 47, 0.65) !important;
            }
            [data-testid="stToolbar"] {
                color: #a9a29a !important;
            }
            .stTabs [data-baseweb="tab-list"] {
                gap: 0.35rem;
                border-bottom: 1px solid #3b352f;
            }
            .stTabs [data-baseweb="tab"] {
                background: #1c1a18 !important;
                border: 1px solid #3b352f !important;
                border-bottom: 0 !important;
                border-radius: 8px 8px 0 0;
                color: #d8d1c8 !important;
                min-height: 2.35rem;
            }
            .stTabs [aria-selected="true"] {
                background: #24201c !important;
                color: #2dd4bf !important;
            }
            [data-testid="stMetric"],
            [data-testid="stMetric"] > div {
                background: #1c1a18 !important;
                border: 1px solid #3b352f !important;
                border-radius: 8px;
                padding: 0.75rem 0.85rem;
            }
            [data-testid="stMetric"] * {
                color: #f4f1ea !important;
            }
            [data-testid="stMetricLabel"] * {
                color: #b9b1a6 !important;
            }
            .stButton button {
                min-height: 2.35rem;
                border-radius: 8px;
                border: 1px solid #4a423a !important;
                background: #24201c !important;
                color: #f4f1ea !important;
                font-weight: 650;
            }
            .stButton button:hover {
                border-color: #2dd4bf !important;
                color: #ccfbf1 !important;
                background: #26352f !important;
            }
            .stDownloadButton button {
                min-height: 2.75rem;
                border-radius: 8px;
                border: 1px solid #2dd4bf !important;
                background: #0f766e !important;
                color: #f7fffd !important;
                font-weight: 700;
            }
            .stDownloadButton button:hover {
                border-color: #5eead4 !important;
                background: #115e59 !important;
                color: #ffffff !important;
            }
            .stDownloadButton button:disabled {
                border-color: #3b352f !important;
                background: #1c1a18 !important;
                color: #746d66 !important;
            }
            div[data-testid="stDataFrame"] {
                border: 1px solid #3b352f !important;
                border-radius: 8px;
                overflow: hidden;
            }
            [data-testid="stVerticalBlock"],
            [data-testid="stHorizontalBlock"] {
                background: transparent !important;
            }
            iframe {
                background: #11100f !important;
                border-radius: 8px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
