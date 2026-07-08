from __future__ import annotations

import base64
from datetime import datetime

import pandas as pd
import streamlit as st

from label_domain import (
    AppDefaults,
    AutoLayout,
    MarginDefaults,
    PAGE_FORMATS_MM,
    SYMBOL_BANK_GROUPS,
    compute_auto_layout,
    dataframe_to_rows,
    default_rows_as_dataframe,
    label_to_symbol,
    load_app_defaults,
    normalize_editor_dataframe,
    normalize_row,
    rows_to_dataframe,
    rows_to_items,
)
from label_pdf import LabelSheetSettings, SYMBOL_LABELS, build_label_pdf, validate_layout


APP_DEFAULTS = load_app_defaults()


def main() -> None:
    st.set_page_config(page_title="Editeur d'etiquettes", page_icon="label", layout="wide")
    _inject_css()

    _ensure_editor_state(APP_DEFAULTS)

    layout = _sidebar_settings(APP_DEFAULTS)
    settings = layout.settings

    st.title("Editeur d'etiquettes atelier")

    editor_col, preview_col = st.columns([1.08, 0.92], gap="large")
    with editor_col:
        _symbol_bank()
        st.subheader("Etiquettes")
        editor_key = _editor_key()
        edited = st.data_editor(
            st.session_state.labels_df,
            key=editor_key,
            on_change=_commit_editor_changes,
            args=(editor_key,),
            hide_index=True,
            num_rows="dynamic",
            width="stretch",
            column_config={
                "Qte": st.column_config.NumberColumn(
                    "Qte",
                    min_value=0,
                    max_value=500,
                    step=1,
                    default=1,
                    width="small",
                ),
                "Symbole": st.column_config.SelectboxColumn(
                    "Symbole",
                    options=list(label_to_symbol().keys()),
                    width="medium",
                ),
                "Texte": st.column_config.TextColumn("Texte", width="medium"),
                "Valeur": st.column_config.TextColumn("Valeur", width="medium"),
                "Note": st.column_config.TextColumn("Note", width="large"),
            },
        )
        current_rows = dataframe_to_rows(edited)

        items = rows_to_items(current_rows)
        errors = validate_layout(settings)
        total_labels = sum(item.quantity for item in items)
        page_count = max(1, (settings.skip_slots + total_labels + settings.capacity_per_page - 1) // settings.capacity_per_page)

        metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
        metric_col_1.metric("Etiquettes", total_labels)
        metric_col_2.metric("Par page", settings.capacity_per_page)
        metric_col_3.metric("Pages PDF", page_count)
        st.caption(
            "Grille calculee : "
            f"{settings.columns} colonnes x {settings.rows} lignes, "
            f"marges finales {settings.margin_left_mm:g} / {layout.margin_right_mm:g} / "
            f"{settings.margin_top_mm:g} / {layout.margin_bottom_mm:g} mm."
        )

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


def _sidebar_settings(defaults: AppDefaults) -> AutoLayout:
    st.sidebar.header("Format")
    paper_options = list(PAGE_FORMATS_MM.keys())
    paper_index = paper_options.index(defaults.page.format) if defaults.page.format in paper_options else 0
    paper = st.sidebar.selectbox("Papier", paper_options, index=paper_index)
    default_width, default_height = PAGE_FORMATS_MM[paper]

    if paper == "Personnalise":
        page_width = st.sidebar.number_input(
            "Largeur page (mm)",
            min_value=20.0,
            max_value=500.0,
            value=defaults.page.width_mm,
            step=1.0,
        )
        page_height = st.sidebar.number_input(
            "Hauteur page (mm)",
            min_value=20.0,
            max_value=700.0,
            value=defaults.page.height_mm,
            step=1.0,
        )
    else:
        page_width, page_height = default_width, default_height

    st.sidebar.header("Etiquettes")
    label_width = st.sidebar.number_input(
        "Largeur etiquette (mm)",
        min_value=5.0,
        max_value=200.0,
        value=defaults.labels.width_mm,
        step=0.5,
    )
    label_height = st.sidebar.number_input(
        "Hauteur etiquette (mm)",
        min_value=5.0,
        max_value=100.0,
        value=defaults.labels.height_mm,
        step=0.5,
    )
    gap_x = st.sidebar.number_input(
        "Espace horizontal (mm)",
        min_value=0.0,
        max_value=50.0,
        value=defaults.labels.gap_x_mm,
        step=0.1,
    )
    gap_y = st.sidebar.number_input(
        "Espace vertical (mm)",
        min_value=0.0,
        max_value=50.0,
        value=defaults.labels.gap_y_mm,
        step=0.1,
    )

    st.sidebar.header("Marges minimales")
    margin_top = st.sidebar.number_input(
        "Marge haute (mm)",
        min_value=0.0,
        max_value=100.0,
        value=defaults.margins.top_mm,
        step=0.5,
    )
    margin_right = st.sidebar.number_input(
        "Marge droite (mm)",
        min_value=0.0,
        max_value=100.0,
        value=defaults.margins.right_mm,
        step=0.5,
    )
    margin_bottom = st.sidebar.number_input(
        "Marge basse (mm)",
        min_value=0.0,
        max_value=100.0,
        value=defaults.margins.bottom_mm,
        step=0.5,
    )
    margin_left = st.sidebar.number_input(
        "Marge gauche (mm)",
        min_value=0.0,
        max_value=100.0,
        value=defaults.margins.left_mm,
        step=0.5,
    )

    margins = MarginDefaults(
        top_mm=float(margin_top),
        right_mm=float(margin_right),
        bottom_mm=float(margin_bottom),
        left_mm=float(margin_left),
    )
    preview_layout = _compute_layout_or_default(
        defaults=defaults,
        page_width=float(page_width),
        page_height=float(page_height),
        label_width=float(label_width),
        label_height=float(label_height),
        margins=margins,
        gap_x=float(gap_x),
        gap_y=float(gap_y),
        skip_slots=defaults.skip_slots,
        show_border=defaults.style.show_border,
        cut_marks=defaults.style.cut_marks,
        font_scale=defaults.style.font_scale,
    )

    st.sidebar.header("Grille")
    st.sidebar.write(f"{preview_layout.settings.columns} colonnes x {preview_layout.settings.rows} lignes")
    st.sidebar.caption(
        "Marges finales : "
        f"gauche {preview_layout.settings.margin_left_mm:g} mm, "
        f"droite {preview_layout.margin_right_mm:g} mm, "
        f"haute {preview_layout.settings.margin_top_mm:g} mm, "
        f"basse {preview_layout.margin_bottom_mm:g} mm."
    )
    skip_slots = st.sidebar.number_input(
        "Cases deja utilisees",
        min_value=0,
        max_value=max(0, preview_layout.settings.capacity_per_page - 1),
        value=min(defaults.skip_slots, max(0, preview_layout.settings.capacity_per_page - 1)),
        step=1,
    )

    st.sidebar.header("Style")
    show_border = st.sidebar.checkbox("Contour", value=defaults.style.show_border)
    cut_marks = st.sidebar.checkbox("Reperes de coupe", value=defaults.style.cut_marks)
    font_scale = st.sidebar.slider(
        "Taille du texte",
        min_value=0.75,
        max_value=1.35,
        value=defaults.style.font_scale,
        step=0.05,
    )

    return _compute_layout_or_default(
        defaults=defaults,
        page_width=float(page_width),
        page_height=float(page_height),
        label_width=float(label_width),
        label_height=float(label_height),
        margins=margins,
        gap_x=float(gap_x),
        gap_y=float(gap_y),
        skip_slots=int(skip_slots),
        show_border=show_border,
        cut_marks=cut_marks,
        font_scale=float(font_scale),
        show_error=False,
    )


def _compute_layout_or_default(
    *,
    defaults: AppDefaults,
    page_width: float,
    page_height: float,
    label_width: float,
    label_height: float,
    margins: MarginDefaults,
    gap_x: float,
    gap_y: float,
    skip_slots: int,
    show_border: bool,
    cut_marks: bool,
    font_scale: float,
    show_error: bool = True,
) -> AutoLayout:
    try:
        return compute_auto_layout(
            page_width_mm=page_width,
            page_height_mm=page_height,
            label_width_mm=label_width,
            label_height_mm=label_height,
            margins=margins,
            gap_x_mm=gap_x,
            gap_y_mm=gap_y,
            skip_slots=skip_slots,
            show_border=show_border,
            cut_marks=cut_marks,
            font_scale=font_scale,
        )
    except ValueError as error:
        if show_error:
            st.sidebar.error(str(error))
        return compute_auto_layout(
            page_width_mm=defaults.page.width_mm,
            page_height_mm=defaults.page.height_mm,
            label_width_mm=defaults.labels.width_mm,
            label_height_mm=defaults.labels.height_mm,
            margins=defaults.margins,
            gap_x_mm=defaults.labels.gap_x_mm,
            gap_y_mm=defaults.labels.gap_y_mm,
            skip_slots=0,
            show_border=defaults.style.show_border,
            cut_marks=defaults.style.cut_marks,
            font_scale=defaults.style.font_scale,
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
    current_df = _current_editor_dataframe()
    rows = dataframe_to_rows(current_df)
    rows.append(
        {
            "Qte": 1,
            "Symbole": SYMBOL_LABELS[symbol],
            "Texte": "",
            "Valeur": "",
            "Note": "",
        }
    )
    st.session_state.labels_df = rows_to_dataframe(rows)
    _reset_editor_widget()


def _ensure_editor_state(defaults: AppDefaults) -> None:
    if "labels_df" not in st.session_state:
        st.session_state.labels_df = default_rows_as_dataframe(defaults)
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0


def _editor_key() -> str:
    return f"labels_editor_{st.session_state.editor_version}"


def _reset_editor_widget() -> None:
    st.session_state.editor_version += 1


def _commit_editor_changes(editor_key: str) -> None:
    st.session_state.labels_df = _current_editor_dataframe(editor_key)
    _reset_editor_widget()


def _current_editor_dataframe(editor_key: str | None = None) -> pd.DataFrame:
    base_df = st.session_state.labels_df.copy()
    editor_state = st.session_state.get(editor_key or _editor_key())
    if not isinstance(editor_state, dict):
        return normalize_editor_dataframe(base_df)

    edited_rows = editor_state.get("edited_rows") or {}
    for row_index, changes in edited_rows.items():
        row_position = int(row_index)
        if row_position >= len(base_df):
            continue
        for column_name, value in changes.items():
            if column_name in base_df.columns:
                base_df.at[base_df.index[row_position], column_name] = "" if value is None else value

    deleted_rows = sorted((int(row) for row in editor_state.get("deleted_rows") or []), reverse=True)
    for row_position in deleted_rows:
        if row_position < len(base_df):
            base_df = base_df.drop(base_df.index[row_position])

    added_rows = editor_state.get("added_rows") or []
    if added_rows:
        additions = [normalize_row(row) for row in added_rows]
        base_df = pd.concat([base_df, pd.DataFrame(additions)], ignore_index=True)

    return normalize_editor_dataframe(base_df)


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
