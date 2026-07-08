from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


SYMBOL_LABELS = {
    "none": "Aucun",
    "resistor": "Resistance",
    "capacitor": "Condensateur",
    "electrolytic": "Condensateur polarise",
    "diode": "Diode",
    "led": "LED",
    "transistor_npn": "Transistor NPN",
    "ground": "Masse",
    "switch": "Interrupteur",
    "inductor": "Inductance",
    "ic": "Circuit integre",
    "battery": "Pile",
    "fuse": "Fusible",
}


@dataclass(frozen=True)
class LabelItem:
    quantity: int
    symbol: str
    text: str
    value: str = ""
    note: str = ""


@dataclass(frozen=True)
class LabelSheetSettings:
    page_width_mm: float
    page_height_mm: float
    label_width_mm: float
    label_height_mm: float
    columns: int
    rows: int
    margin_left_mm: float
    margin_top_mm: float
    gap_x_mm: float
    gap_y_mm: float
    skip_slots: int = 0
    show_border: bool = True
    cut_marks: bool = True
    font_scale: float = 1.0

    @property
    def capacity_per_page(self) -> int:
        return max(1, self.columns * self.rows)


def validate_layout(settings: LabelSheetSettings) -> list[str]:
    errors: list[str] = []

    if settings.columns < 1 or settings.rows < 1:
        errors.append("Le nombre de lignes et de colonnes doit etre au moins 1.")

    numeric_fields = {
        "largeur de page": settings.page_width_mm,
        "hauteur de page": settings.page_height_mm,
        "largeur d'etiquette": settings.label_width_mm,
        "hauteur d'etiquette": settings.label_height_mm,
        "marge gauche": settings.margin_left_mm,
        "marge haute": settings.margin_top_mm,
        "espace horizontal": settings.gap_x_mm,
        "espace vertical": settings.gap_y_mm,
    }
    for label, value in numeric_fields.items():
        if value < 0:
            errors.append(f"La valeur '{label}' ne peut pas etre negative.")

    used_width = (
        settings.margin_left_mm
        + settings.columns * settings.label_width_mm
        + max(0, settings.columns - 1) * settings.gap_x_mm
    )
    used_height = (
        settings.margin_top_mm
        + settings.rows * settings.label_height_mm
        + max(0, settings.rows - 1) * settings.gap_y_mm
    )

    if used_width > settings.page_width_mm + 0.05:
        errors.append(
            f"La grille depasse la page en largeur ({used_width:.1f} mm sur {settings.page_width_mm:.1f} mm)."
        )
    if used_height > settings.page_height_mm + 0.05:
        errors.append(
            f"La grille depasse la page en hauteur ({used_height:.1f} mm sur {settings.page_height_mm:.1f} mm)."
        )

    return errors


def build_label_pdf(items: Iterable[LabelItem], settings: LabelSheetSettings) -> bytes:
    layout_errors = validate_layout(settings)
    if layout_errors:
        raise ValueError(" ".join(layout_errors))

    labels = _expand_items(items)
    slots: list[LabelItem | None] = [None] * max(0, settings.skip_slots) + labels

    buffer = BytesIO()
    page_width = settings.page_width_mm * mm
    page_height = settings.page_height_mm * mm
    pdf = canvas.Canvas(buffer, pagesize=(page_width, page_height), pageCompression=1)
    pdf.setTitle("Etiquettes atelier electronique")
    pdf.setAuthor("Editeur d'etiquettes")

    if not slots:
        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    for slot_index, item in enumerate(slots):
        page_slot = slot_index % settings.capacity_per_page
        if slot_index and page_slot == 0:
            pdf.showPage()

        if item is None:
            continue

        row = page_slot // settings.columns
        col = page_slot % settings.columns

        x = (settings.margin_left_mm + col * (settings.label_width_mm + settings.gap_x_mm)) * mm
        top_y = page_height - (
            settings.margin_top_mm + row * (settings.label_height_mm + settings.gap_y_mm)
        ) * mm
        y = top_y - settings.label_height_mm * mm

        _draw_label(
            pdf,
            x,
            y,
            settings.label_width_mm * mm,
            settings.label_height_mm * mm,
            item,
            settings,
        )

    pdf.save()
    return buffer.getvalue()


def _expand_items(items: Iterable[LabelItem]) -> list[LabelItem]:
    labels: list[LabelItem] = []
    for item in items:
        quantity = max(0, int(item.quantity or 0))
        clean = LabelItem(
            quantity=1,
            symbol=item.symbol if item.symbol in SYMBOL_LABELS else "none",
            text=(item.text or "").strip(),
            value=(item.value or "").strip(),
            note=(item.note or "").strip(),
        )
        labels.extend([clean] * quantity)
    return labels


def _draw_label(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    item: LabelItem,
    settings: LabelSheetSettings,
) -> None:
    pdf.saveState()

    if settings.cut_marks:
        _draw_cut_marks(pdf, x, y, width, height)

    if settings.show_border:
        pdf.setStrokeColor(colors.HexColor("#9aa1a9"))
        pdf.setLineWidth(0.35)
        pdf.rect(x, y, width, height, stroke=1, fill=0)

    padding = max(1.4 * mm, min(2.8 * mm, height * 0.14, width * 0.07))
    symbol_size = min(height - 2 * padding, width * 0.24, 12 * mm)
    symbol_x = x + padding
    symbol_y = y + (height - symbol_size) / 2

    has_symbol = item.symbol != "none"
    if has_symbol:
        _draw_symbol(pdf, item.symbol, symbol_x, symbol_y, symbol_size, symbol_size)
        text_x = symbol_x + symbol_size + padding
    else:
        text_x = x + padding

    text_width = max(1, x + width - padding - text_x)
    base_size = min(11.5, max(6.0, (height / mm) * 0.43)) * settings.font_scale
    title_size = base_size
    value_size = max(5.2, base_size * 0.82)
    note_size = max(4.6, base_size * 0.64)

    lines: list[tuple[str, str, float]] = []
    if item.text:
        lines.append(("Helvetica-Bold", item.text, title_size))
    if item.value:
        lines.append(("Helvetica", item.value, value_size))
    if item.note:
        for note_line in _wrap_text(item.note, "Helvetica", note_size, text_width, 2):
            lines.append(("Helvetica", note_line, note_size))

    if not lines:
        lines.append(("Helvetica", "", value_size))

    line_heights = [size * 1.12 for _, _, size in lines]
    total_height = sum(line_heights)
    cursor_y = y + (height + total_height) / 2

    pdf.setFillColor(colors.HexColor("#111827"))
    for (font_name, text, size), line_height in zip(lines, line_heights):
        cursor_y -= line_height
        fitted_text = _ellipsize(text, font_name, size, text_width)
        fitted_size = _fit_font_size(fitted_text, font_name, size, text_width, min_size=4.5)
        pdf.setFont(font_name, fitted_size)
        pdf.drawString(text_x, cursor_y + (line_height - fitted_size) * 0.25, fitted_text)

    pdf.restoreState()


def _draw_cut_marks(pdf: canvas.Canvas, x: float, y: float, width: float, height: float) -> None:
    mark = 2.0 * mm
    offset = 0.55 * mm
    pdf.saveState()
    pdf.setStrokeColor(colors.HexColor("#c4c9cf"))
    pdf.setLineWidth(0.25)

    corners = [
        (x, y),
        (x + width, y),
        (x, y + height),
        (x + width, y + height),
    ]
    for cx, cy in corners:
        x_dir = -1 if cx == x else 1
        y_dir = -1 if cy == y else 1
        pdf.line(cx + x_dir * offset, cy, cx + x_dir * (offset + mark), cy)
        pdf.line(cx, cy + y_dir * offset, cx, cy + y_dir * (offset + mark))

    pdf.restoreState()


def _draw_symbol(pdf: canvas.Canvas, symbol: str, x: float, y: float, width: float, height: float) -> None:
    pdf.saveState()
    pdf.translate(x, y)
    pdf.scale(width / 100, height / 100)
    pdf.setStrokeColor(colors.HexColor("#111827"))
    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setLineWidth(4)
    pdf.setLineCap(1)
    pdf.setLineJoin(1)

    drawer = _SYMBOL_DRAWERS.get(symbol, _draw_none)
    drawer(pdf)

    pdf.restoreState()


def _draw_none(pdf: canvas.Canvas) -> None:
    return None


def _draw_resistor(pdf: canvas.Canvas) -> None:
    points = [(5, 50), (18, 50), (25, 30), (35, 70), (45, 30), (55, 70), (65, 30), (75, 70), (82, 50), (95, 50)]
    path = pdf.beginPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    pdf.drawPath(path, stroke=1, fill=0)


def _draw_capacitor(pdf: canvas.Canvas) -> None:
    pdf.line(5, 50, 38, 50)
    pdf.line(38, 18, 38, 82)
    pdf.line(62, 18, 62, 82)
    pdf.line(62, 50, 95, 50)


def _draw_electrolytic(pdf: canvas.Canvas) -> None:
    _draw_capacitor(pdf)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(23, 72, "+")


def _draw_diode(pdf: canvas.Canvas) -> None:
    pdf.line(5, 50, 28, 50)
    pdf.line(72, 50, 95, 50)
    path = pdf.beginPath()
    path.moveTo(28, 20)
    path.lineTo(28, 80)
    path.lineTo(70, 50)
    path.close()
    pdf.drawPath(path, stroke=1, fill=0)
    pdf.line(72, 18, 72, 82)


def _draw_led(pdf: canvas.Canvas) -> None:
    _draw_diode(pdf)
    pdf.line(64, 82, 86, 104)
    pdf.line(86, 104, 80, 87)
    pdf.line(86, 104, 69, 98)
    pdf.line(49, 84, 71, 106)
    pdf.line(71, 106, 65, 89)
    pdf.line(71, 106, 54, 100)


def _draw_transistor_npn(pdf: canvas.Canvas) -> None:
    pdf.circle(50, 50, 35, stroke=1, fill=0)
    pdf.line(22, 50, 44, 50)
    pdf.line(44, 24, 44, 76)
    pdf.line(44, 64, 72, 82)
    pdf.line(44, 36, 72, 18)
    pdf.line(72, 18, 64, 34)
    pdf.line(72, 18, 54, 20)


def _draw_ground(pdf: canvas.Canvas) -> None:
    pdf.line(50, 12, 50, 55)
    pdf.line(25, 55, 75, 55)
    pdf.line(32, 42, 68, 42)
    pdf.line(39, 29, 61, 29)


def _draw_switch(pdf: canvas.Canvas) -> None:
    pdf.circle(25, 50, 5, stroke=1, fill=0)
    pdf.circle(75, 50, 5, stroke=1, fill=0)
    pdf.line(5, 50, 20, 50)
    pdf.line(80, 50, 95, 50)
    pdf.line(30, 54, 70, 76)


def _draw_inductor(pdf: canvas.Canvas) -> None:
    pdf.line(5, 50, 18, 50)
    for x in (18, 34, 50, 66):
        pdf.arc(x, 34, x + 18, 66, 0, 180)
    pdf.line(84, 50, 95, 50)


def _draw_ic(pdf: canvas.Canvas) -> None:
    pdf.rect(24, 20, 52, 60, stroke=1, fill=0)
    for y in (30, 45, 60, 75):
        pdf.line(10, y, 24, y)
        pdf.line(76, y, 90, y)
    pdf.circle(34, 68, 3, stroke=1, fill=0)


def _draw_battery(pdf: canvas.Canvas) -> None:
    pdf.line(5, 50, 30, 50)
    pdf.line(30, 22, 30, 78)
    pdf.line(45, 34, 45, 66)
    pdf.line(45, 50, 60, 50)
    pdf.line(60, 22, 60, 78)
    pdf.line(75, 34, 75, 66)
    pdf.line(75, 50, 95, 50)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(20, 72, "+")


def _draw_fuse(pdf: canvas.Canvas) -> None:
    pdf.line(5, 50, 25, 50)
    pdf.line(75, 50, 95, 50)
    pdf.roundRect(25, 30, 50, 40, 9, stroke=1, fill=0)
    pdf.line(34, 50, 66, 50)


_SYMBOL_DRAWERS = {
    "none": _draw_none,
    "resistor": _draw_resistor,
    "capacitor": _draw_capacitor,
    "electrolytic": _draw_electrolytic,
    "diode": _draw_diode,
    "led": _draw_led,
    "transistor_npn": _draw_transistor_npn,
    "ground": _draw_ground,
    "switch": _draw_switch,
    "inductor": _draw_inductor,
    "ic": _draw_ic,
    "battery": _draw_battery,
    "fuse": _draw_fuse,
}


def _fit_font_size(text: str, font_name: str, font_size: float, max_width: float, min_size: float) -> float:
    size = font_size
    while size > min_size and stringWidth(text, font_name, size) > max_width:
        size -= 0.25
    return max(size, min_size)


def _ellipsize(text: str, font_name: str, font_size: float, max_width: float) -> str:
    if stringWidth(text, font_name, font_size) <= max_width:
        return text

    ellipsis = "..."
    available = max_width - stringWidth(ellipsis, font_name, font_size)
    if available <= 0:
        return ellipsis

    shortened = text
    while shortened and stringWidth(shortened, font_name, font_size) > available:
        shortened = shortened[:-1]
    return shortened.rstrip() + ellipsis


def _wrap_text(text: str, font_name: str, font_size: float, max_width: float, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines and len(words) > len(" ".join(lines).split()):
        lines[-1] = _ellipsize(lines[-1], font_name, font_size, max_width)

    return lines

