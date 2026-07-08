from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from label_pdf import LabelItem, LabelSheetSettings, SYMBOL_LABELS, TEXT_SYMBOLS, build_label_pdf, validate_layout


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

    if "rows" not in st.session_state:
        st.session_state.rows = DEFAULT_ROWS

    settings = _sidebar_settings()

    st.title("Editeur d'etiquettes atelier")

    editor_col, preview_col = st.columns([1.08, 0.92], gap="large")
    with editor_col:
        _symbol_bank()
        st.subheader("Etiquettes")
        edited = st.data_editor(
            pd.DataFrame(st.session_state.rows),
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
        st.session_state.rows = edited.fillna("").to_dict("records")

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
        st.subheader("Apercu")
        st.iframe(_preview_html(items, settings), height=_preview_height(settings), width="stretch")


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
    st.session_state.rows.append(
        {
            "Qte": 1,
            "Symbole": SYMBOL_LABELS[symbol],
            "Texte": "",
            "Valeur": "",
            "Note": "",
        }
    )


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


def _preview_html(items: list[LabelItem], settings: LabelSheetSettings) -> str:
    labels = _expanded_preview_items(items)
    page_w = settings.page_width_mm
    page_h = settings.page_height_mm
    label_w = settings.label_width_mm
    label_h = settings.label_height_mm

    slots: list[LabelItem | None] = [None] * settings.skip_slots + labels
    slots = slots[: settings.capacity_per_page]

    cells: list[str] = []
    for slot_index, item in enumerate(slots):
        if item is None:
            continue
        row = slot_index // settings.columns
        col = slot_index % settings.columns
        left = (settings.margin_left_mm + col * (settings.label_width_mm + settings.gap_x_mm)) / page_w * 100
        top = (settings.margin_top_mm + row * (settings.label_height_mm + settings.gap_y_mm)) / page_h * 100
        width = label_w / page_w * 100
        height = label_h / page_h * 100
        has_symbol = item.symbol != "none"
        has_text = bool(item.text or item.value or item.note)
        classes = ["label"]
        if has_symbol and not has_text:
            classes.append("symbol-only")
        elif not has_symbol:
            classes.append("text-only")

        symbol_html = f'<div class="symbol">{_symbol_svg(item.symbol)}</div>' if has_symbol else ""
        copy_html = ""
        if has_text:
            copy_html = f"""
                <div class="copy">
                    <strong>{escape(item.text)}</strong>
                    <span>{escape(item.value)}</span>
                    <small>{escape(item.note)}</small>
                </div>
            """
        cells.append(
            f"""
            <div class="{' '.join(classes)}" style="left:{left:.4f}%;top:{top:.4f}%;width:{width:.4f}%;height:{height:.4f}%;">
                {symbol_html}
                {copy_html}
            </div>
            """
        )

    empty_state = "<div class='empty'>Aucune etiquette</div>" if not cells else ""
    border = "1px solid #98a2b3" if settings.show_border else "1px dashed #d0d5dd"

    return f"""
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8" />
        <style>
            :root {{
                color-scheme: light;
                font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}
            body {{
                margin: 0;
                background: #f6f7f9;
                color: #111827;
            }}
            .sheet {{
                position: relative;
                width: min(100%, 620px);
                aspect-ratio: {page_w} / {page_h};
                margin: 0 auto;
                background: #ffffff;
                border: 1px solid #d0d5dd;
                box-shadow: 0 18px 50px rgba(17, 24, 39, 0.12);
                overflow: hidden;
            }}
            .label {{
                position: absolute;
                display: grid;
                grid-template-columns: minmax(10px, 30%) minmax(0, 1fr);
                align-items: center;
                gap: 4%;
                border: {border};
                padding: 4%;
                box-sizing: border-box;
                background: #fff;
            }}
            .label.text-only {{
                grid-template-columns: minmax(0, 1fr);
            }}
            .label.symbol-only {{
                grid-template-columns: minmax(0, 1fr);
                place-items: center;
                padding: 5%;
            }}
            .label.symbol-only .symbol {{
                width: 82%;
                height: 82%;
                display: grid;
                place-items: center;
            }}
            .symbol svg {{
                display: block;
                width: 100%;
                height: 100%;
                color: #111827;
            }}
            .copy {{
                min-width: 0;
                display: flex;
                flex-direction: column;
                line-height: 1.08;
                overflow: hidden;
            }}
            strong, span, small {{
                display: block;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            strong {{
                font-size: clamp(7px, 1.2vw, 13px);
            }}
            span {{
                margin-top: 2px;
                font-size: clamp(6px, 1vw, 11px);
            }}
            small {{
                margin-top: 2px;
                color: #667085;
                font-size: clamp(5px, 0.85vw, 9px);
            }}
            .empty {{
                position: absolute;
                inset: 0;
                display: grid;
                place-items: center;
                color: #667085;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="sheet">{empty_state}{''.join(cells)}</div>
    </body>
    </html>
    """


def _expanded_preview_items(items: list[LabelItem]) -> list[LabelItem]:
    expanded: list[LabelItem] = []
    for item in items:
        expanded.extend([item] * max(0, item.quantity))
        if len(expanded) >= 120:
            break
    return expanded


def _symbol_svg(symbol: str) -> str:
    if symbol in TEXT_SYMBOLS:
        label = escape(TEXT_SYMBOLS[symbol])
        return f"""
        <svg viewBox="0 0 56 56" aria-hidden="true">
            <text x="28" y="30" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="22" font-weight="800" fill="currentColor">{label}</text>
        </svg>
        """

    strokes = {
        "none": "",
        "resistor": '<polyline points="5,25 10,25 14,12 20,38 26,12 32,38 38,12 44,38 48,25 55,25" />',
        "capacitor": '<path d="M5 25h20M25 8v34M35 8v34M35 25h20" />',
        "electrolytic": '<path d="M5 25h20M25 8v34M35 8v34M35 25h20" /><text x="13" y="16" font-size="13" font-family="Arial" font-weight="700">+</text>',
        "diode": '<path d="M5 25h14M39 25h16M19 10v30l20-15zM40 9v32" />',
        "led": '<path d="M5 25h14M39 25h16M19 10v30l20-15zM40 9v32M37 6l12-12M49-6l-3 10M49-6l-10 3M28 6l12-12M40-6l-3 10M40-6l-10 3" />',
        "transistor_npn": '<circle cx="28" cy="28" r="21" /><path d="M7 28h16M23 13v30M23 19l20-12M23 37l20 12M43 49l-6-10M43 49l-11-1" />',
        "ground": '<path d="M28 5v22M12 27h32M17 35h22M22 43h12" />',
        "switch": '<path d="M5 28h12M39 28h12M21 25l20-12" /><circle cx="19" cy="28" r="3" /><circle cx="37" cy="28" r="3" />',
        "inductor": '<path d="M4 28h8M12 28a6 6 0 0 1 12 0M24 28a6 6 0 0 1 12 0M36 28a6 6 0 0 1 12 0M48 28h4" />',
        "ic": '<rect x="15" y="9" width="28" height="36" rx="2" /><path d="M6 16h9M6 26h9M6 36h9M43 16h9M43 26h9M43 36h9" /><circle cx="22" cy="17" r="2" />',
        "battery": '<path d="M5 28h12M17 10v36M27 18v20M27 28h9M36 10v36M46 18v20M46 28h9" />',
        "fuse": '<path d="M5 28h12M39 28h12M17 17h22v22H17zM22 28h12" />',
    }
    return f"""
    <svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        {strokes.get(symbol, strokes["none"])}
    </svg>
    """


def _inject_css() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background: #f6f7f9;
            }
            h1, h2, h3 {
                letter-spacing: 0;
            }
            [data-testid="stSidebar"] {
                border-right: 1px solid #e4e7ec;
            }
            div[data-testid="stMetric"] {
                background: #ffffff;
                border: 1px solid #e4e7ec;
                border-radius: 8px;
                padding: 0.75rem 0.85rem;
            }
            .stDownloadButton button {
                min-height: 2.75rem;
                border-radius: 8px;
                border: 1px solid #0f766e;
                background: #0f766e;
                color: #ffffff;
                font-weight: 700;
            }
            .stDownloadButton button:disabled {
                border-color: #d0d5dd;
                background: #eaecf0;
                color: #667085;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
