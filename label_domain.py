from __future__ import annotations

import json
import math
import tomllib
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from label_pdf import LabelItem, LabelSheetSettings, SYMBOL_LABELS


CONFIG_PATH = Path(__file__).with_name("config.toml")
AUTOSAVE_PATH = Path(__file__).with_name(".tmp") / "autosave.json"
AUTOSAVE_VERSION = 1
SAVED_PAGES_PATH = Path(__file__).with_name(".tmp") / "saved_pages.json"
SAVED_PAGES_VERSION = 1

PAGE_FORMATS_MM = {
    "A4": (210.0, 297.0),
    "Letter": (215.9, 279.4),
    "Personnalise": (210.0, 297.0),
}

EDITOR_COLUMNS = ["Qte", "Symbole", "Texte", "Valeur", "Note"]

SYMBOL_BANK_GROUPS = {
    "Passifs": [
        "resistor",
        "potentiometer",
        "trimmer",
        "capacitor",
        "component_ceramic_capacitor",
        "component_film_capacitor",
        "electrolytic",
        "component_tantalum_capacitor",
        "inductor",
        "component_ferrite_bead",
        "component_crystal",
        "component_resonator",
    ],
    "Opto / capteurs": [
        "component_photoresistor",
        "component_ntc",
        "component_ptc",
        "component_photodiode",
        "led",
        "component_rgb_led",
        "component_ir_led",
        "component_optocoupler",
    ],
    "Diodes": [
        "diode",
        "component_zener",
        "component_schottky",
        "component_tvs",
        "component_bridge_rectifier",
        "led",
        "component_photodiode",
    ],
    "Transistors": [
        "transistor_npn",
        "component_pnp",
        "component_mosfet_n",
        "component_mosfet_p",
        "component_jfet",
        "component_scr",
        "component_triac",
        "component_optocoupler",
    ],
    "Commutation": [
        "switch",
        "component_push_button",
        "component_dip_switch",
        "component_relay",
        "component_reed_relay",
        "component_reed_switch",
        "component_buzzer",
        "component_speaker",
        "component_motor",
        "component_servo",
    ],
    "Alim / protection": [
        "battery",
        "fuse",
        "component_polyfuse",
        "component_regulator",
        "component_ldo",
        "component_dc_dc",
        "component_varistor",
        "component_tvs",
        "component_bridge_rectifier",
        "ground",
    ],
    "CI / logique": [
        "ic",
        "component_ic_socket",
        "component_op_amp",
        "component_logic_gate",
        "component_555",
        "component_microcontroller",
        "component_eeprom",
    ],
    "Connecteurs": [
        "connector_header",
        "connector_dupont",
        "connector_jst",
        "connector_terminal",
        "connector_barrel_jack",
        "connector_usb_c",
        "connector_micro_usb",
        "connector_mini_usb",
        "connector_audio_jack",
    ],
    "Vis": [
        "screw_m1_6",
        "screw_m1_6_con",
        "screw_m2",
        "screw_m2_con",
        "screw_m2_5",
        "screw_m2_5_con",
        "screw_m3",
        "screw_m3_con",
        "screw_m4",
        "screw_m4_con",
        "screw_m5",
        "screw_m5_con",
        "screw_m6",
        "screw_m6_con",
        "screw_m8",
        "screw_m8_con",
    ],
    "Grandes etiquettes": [
        "module_arduino",
        "module_arduino_nano",
        "module_arduino_uno",
        "module_esp32",
        "module_esp8266",
        "programmer_isp",
        "programmer_usbasp",
        "programmer_stlink",
        "programmer_ch341a",
        "programmer_ftdi",
    ],
}

FALLBACK_DEFAULT_ROWS = [
    {"Qte": 1, "Symbole": "Resistance", "Texte": "10k", "Valeur": "", "Note": ""},
    {"Qte": 1, "Symbole": "Condensateur", "Texte": "100n", "Valeur": "", "Note": ""},
    {"Qte": 1, "Symbole": "M3", "Texte": "", "Valeur": "", "Note": ""},
]


@dataclass(frozen=True)
class PageDefaults:
    format: str
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class LabelDefaults:
    width_mm: float
    height_mm: float
    gap_x_mm: float
    gap_y_mm: float


@dataclass(frozen=True)
class MarginDefaults:
    top_mm: float
    right_mm: float
    bottom_mm: float
    left_mm: float


@dataclass(frozen=True)
class StyleDefaults:
    show_border: bool
    cut_marks: bool
    font_scale: float


@dataclass(frozen=True)
class AppDefaults:
    page: PageDefaults
    labels: LabelDefaults
    margins: MarginDefaults
    style: StyleDefaults
    skip_slots: int
    default_rows: list[dict[str, object]]


@dataclass(frozen=True)
class AutoLayout:
    settings: LabelSheetSettings
    margin_right_mm: float
    margin_bottom_mm: float
    base_margins: MarginDefaults
    used_width_mm: float
    used_height_mm: float
    extra_width_mm: float
    extra_height_mm: float


@dataclass(frozen=True)
class AutosaveDraft:
    rows: list[dict[str, object]]
    settings: dict[str, object]


def load_app_defaults(path: Path = CONFIG_PATH) -> AppDefaults:
    with path.open("rb") as config_file:
        raw = tomllib.load(config_file)

    page = raw.get("page", {})
    labels = raw.get("labels", {})
    margins = raw.get("margins", {})
    style = raw.get("style", {})
    defaults = raw.get("defaults", {})
    default_rows = raw.get("default_rows") or FALLBACK_DEFAULT_ROWS

    page_format = str(page.get("format", "A4"))
    default_page_width, default_page_height = PAGE_FORMATS_MM.get(page_format, PAGE_FORMATS_MM["A4"])

    return AppDefaults(
        page=PageDefaults(
            format=page_format,
            width_mm=_float_value(page.get("width_mm"), default_page_width),
            height_mm=_float_value(page.get("height_mm"), default_page_height),
        ),
        labels=LabelDefaults(
            width_mm=_float_value(labels.get("width_mm"), 12.5),
            height_mm=_float_value(labels.get("height_mm"), 10.0),
            gap_x_mm=_float_value(labels.get("gap_x_mm"), 0.0),
            gap_y_mm=_float_value(labels.get("gap_y_mm"), 0.0),
        ),
        margins=MarginDefaults(
            top_mm=_float_value(margins.get("top_mm"), 10.0),
            right_mm=_float_value(margins.get("right_mm"), 10.0),
            bottom_mm=_float_value(margins.get("bottom_mm"), 10.0),
            left_mm=_float_value(margins.get("left_mm"), 10.0),
        ),
        style=StyleDefaults(
            show_border=_bool_value(style.get("show_border"), True),
            cut_marks=_bool_value(style.get("cut_marks"), True),
            font_scale=_float_value(style.get("font_scale"), 1.0),
        ),
        skip_slots=_int_value(defaults.get("skip_slots"), 0),
        default_rows=[normalize_row(row) for row in default_rows],
    )


def load_autosave_draft(defaults: AppDefaults, path: Path = AUTOSAVE_PATH) -> AutosaveDraft:
    raw = _read_autosave(path)
    rows = raw.get("rows") if isinstance(raw, dict) else None
    settings = raw.get("settings") if isinstance(raw, dict) else None

    return AutosaveDraft(
        rows=(
            [normalize_row(row) for row in rows if isinstance(row, dict)]
            if isinstance(rows, list)
            else defaults.default_rows
        ),
        settings=dict(settings) if isinstance(settings, dict) else {},
    )


def save_autosave_draft(
    rows: list[dict[str, object]],
    settings: dict[str, object],
    path: Path = AUTOSAVE_PATH,
) -> None:
    payload = {
        "version": AUTOSAVE_VERSION,
        "rows": [normalize_row(row) for row in rows],
        "settings": dict(settings),
    }
    try:
        _write_json_payload(payload, path)
    except OSError:
        return


def list_saved_pages(path: Path = SAVED_PAGES_PATH) -> list[str]:
    return sorted(_saved_page_entries(path).keys(), key=str.casefold)


def save_named_page(
    title: str,
    rows: list[dict[str, object]],
    settings: dict[str, object],
    path: Path = SAVED_PAGES_PATH,
) -> str:
    clean_title = _clean_page_title(title)
    if not clean_title:
        raise ValueError("Le titre de sauvegarde est obligatoire.")

    entries = _saved_page_entries(path)
    entries[clean_title] = {
        "title": clean_title,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "rows": [normalize_row(row) for row in rows],
        "settings": dict(settings),
    }
    payload = {
        "version": SAVED_PAGES_VERSION,
        "pages": {
            title: entries[title]
            for title in sorted(entries, key=str.casefold)
        },
    }
    _write_json_payload(payload, path)
    return clean_title


def load_named_page(
    title: str,
    defaults: AppDefaults,
    path: Path = SAVED_PAGES_PATH,
) -> AutosaveDraft | None:
    page = _saved_page_entries(path).get(_clean_page_title(title))
    if not isinstance(page, dict):
        return None

    rows = page.get("rows")
    settings = page.get("settings")
    return AutosaveDraft(
        rows=(
            [normalize_row(row) for row in rows if isinstance(row, dict)]
            if isinstance(rows, list)
            else defaults.default_rows
        ),
        settings=dict(settings) if isinstance(settings, dict) else {},
    )


def compute_auto_layout(
    *,
    page_width_mm: float,
    page_height_mm: float,
    label_width_mm: float,
    label_height_mm: float,
    margins: MarginDefaults,
    gap_x_mm: float,
    gap_y_mm: float,
    skip_slots: int,
    show_border: bool,
    cut_marks: bool,
    font_scale: float,
) -> AutoLayout:
    columns, used_width, margin_left, margin_right, extra_width = _fit_axis(
        total_mm=page_width_mm,
        start_margin_mm=margins.left_mm,
        end_margin_mm=margins.right_mm,
        item_mm=label_width_mm,
        gap_mm=gap_x_mm,
        label="largeur",
    )
    rows, used_height, margin_top, margin_bottom, extra_height = _fit_axis(
        total_mm=page_height_mm,
        start_margin_mm=margins.top_mm,
        end_margin_mm=margins.bottom_mm,
        item_mm=label_height_mm,
        gap_mm=gap_y_mm,
        label="hauteur",
    )

    capacity = columns * rows
    bounded_skip_slots = min(max(0, int(skip_slots)), max(0, capacity - 1))
    settings_values = {
        "page_width_mm": float(page_width_mm),
        "page_height_mm": float(page_height_mm),
        "label_width_mm": float(label_width_mm),
        "label_height_mm": float(label_height_mm),
        "columns": int(columns),
        "rows": int(rows),
        "margin_left_mm": margin_left,
        "margin_top_mm": margin_top,
        "gap_x_mm": float(gap_x_mm),
        "gap_y_mm": float(gap_y_mm),
        "skip_slots": bounded_skip_slots,
        "show_border": bool(show_border),
        "cut_marks": bool(cut_marks),
        "font_scale": float(font_scale),
        "margin_right_mm": margin_right,
        "margin_bottom_mm": margin_bottom,
    }
    supported_settings = {field.name for field in fields(LabelSheetSettings)}
    settings = LabelSheetSettings(
        **{
            key: value
            for key, value in settings_values.items()
            if key in supported_settings
        }
    )

    return AutoLayout(
        settings=settings,
        margin_right_mm=margin_right,
        margin_bottom_mm=margin_bottom,
        base_margins=margins,
        used_width_mm=used_width,
        used_height_mm=used_height,
        extra_width_mm=extra_width,
        extra_height_mm=extra_height,
    )


def default_rows_as_dataframe(defaults: AppDefaults) -> pd.DataFrame:
    return rows_to_dataframe(defaults.default_rows)


def rows_to_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    return normalize_editor_dataframe(pd.DataFrame([normalize_row(row) for row in rows]))


def normalize_editor_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    normalized = data.copy()
    for column in EDITOR_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    normalized = normalized[EDITOR_COLUMNS].fillna("")
    normalized["Qte"] = normalized["Qte"].apply(normalize_quantity)
    for column in ["Symbole", "Texte", "Valeur", "Note"]:
        normalized[column] = normalized[column].astype(str)
    return normalized.reset_index(drop=True)


def normalize_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "Qte": normalize_quantity(_row_value(row, "Qte", "qte", "quantity", default=1)),
        "Symbole": str(_row_value(row, "Symbole", "symbole", "symbol", default="")),
        "Texte": str(_row_value(row, "Texte", "texte", "text", default="")),
        "Valeur": str(_row_value(row, "Valeur", "valeur", "value", default="")),
        "Note": str(_row_value(row, "Note", "note", default="")),
    }


def normalize_quantity(value: object) -> int:
    try:
        if value == "":
            return 1
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 1


def dataframe_to_rows(data: pd.DataFrame) -> list[dict[str, object]]:
    return normalize_editor_dataframe(data).to_dict("records")


def delete_rows(rows: list[dict[str, object]], row_indices: list[int]) -> list[dict[str, object]]:
    indices_to_delete = {int(index) for index in row_indices}
    return [
        normalize_row(row)
        for index, row in enumerate(rows)
        if index not in indices_to_delete
    ]


def rows_to_items(rows: list[dict[str, object]]) -> list[LabelItem]:
    mapping = label_to_symbol()
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


def label_to_symbol() -> dict[str, str]:
    return {label: key for key, label in SYMBOL_LABELS.items()}


def _fit_axis(
    *,
    total_mm: float,
    start_margin_mm: float,
    end_margin_mm: float,
    item_mm: float,
    gap_mm: float,
    label: str,
) -> tuple[int, float, float, float, float]:
    values = {
        f"{label} page": total_mm,
        f"{label} etiquette": item_mm,
        f"marge debut {label}": start_margin_mm,
        f"marge fin {label}": end_margin_mm,
        f"espacement {label}": gap_mm,
    }
    for value_label, value in values.items():
        if value < 0:
            raise ValueError(f"La valeur '{value_label}' ne peut pas etre negative.")

    if total_mm <= 0 or item_mm <= 0:
        raise ValueError(f"La {label} de page et d'etiquette doit etre superieure a 0.")

    available_mm = total_mm - start_margin_mm - end_margin_mm
    if available_mm < item_mm - 0.001:
        raise ValueError(
            f"Aucune etiquette complete ne tient en {label} avec ces marges "
            f"({available_mm:.1f} mm disponibles pour {item_mm:.1f} mm)."
        )

    count = int(math.floor((available_mm + gap_mm + 0.001) / (item_mm + gap_mm)))
    count = max(1, count)
    used_mm = count * item_mm + max(0, count - 1) * gap_mm
    extra_mm = max(0.0, available_mm - used_mm)

    return (
        count,
        round(used_mm, 4),
        round(start_margin_mm + extra_mm / 2, 4),
        round(end_margin_mm + extra_mm / 2, 4),
        round(extra_mm, 4),
    )


def _float_value(value: Any, default: float) -> float:
    try:
        return float(default if value is None else value)
    except (TypeError, ValueError):
        return float(default)


def _int_value(value: Any, default: int) -> int:
    try:
        return int(default if value is None else value)
    except (TypeError, ValueError):
        return int(default)


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _row_value(row: dict[str, object], *keys: str, default: object) -> object:
    for key in keys:
        if key in row:
            return row[key]
    return default


def _read_autosave(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_saved_pages(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _saved_page_entries(path: Path) -> dict[str, dict[str, Any]]:
    raw = _read_saved_pages(path)
    pages = raw.get("pages") if isinstance(raw, dict) else None
    if not isinstance(pages, dict):
        return {}

    entries: dict[str, dict[str, Any]] = {}
    for key, value in pages.items():
        title = _clean_page_title(key)
        if title and isinstance(value, dict):
            entries[title] = value
    return entries


def _clean_page_title(title: object) -> str:
    return " ".join(str(title or "").strip().split())


def _write_json_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)
