from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))

from weasyprint import HTML

from renderers.stellium_adapter import build_western_chart


CHARTS_OUT = ROOT / "charts_out"
CHARTS_RENDERED = ROOT / "charts_rendered"
REPORTS_OUT = ROOT / "reports"
TEMPLATE = Path(__file__).resolve().parent / "templates" / "page_1.html"
PAGE_2_TEMPLATE = Path(__file__).resolve().parent / "templates" / "page_2.html"
STYLES = Path(__file__).resolve().parent / "styles.css"

GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
ABBREVIATIONS = {
    "Sun": "Su",
    "Moon": "Mo",
    "Mars": "Ma",
    "Mercury": "Me",
    "Jupiter": "Ju",
    "Venus": "Ve",
    "Saturn": "Sa",
    "Rahu": "Ra",
    "Ketu": "Ke",
}
SIGNS = ("Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi")
SIGN_NAMES = {
    "Ar": "Aries",
    "Ta": "Taurus",
    "Ge": "Gemini",
    "Cn": "Cancer",
    "Le": "Leo",
    "Vi": "Virgo",
    "Li": "Libra",
    "Sc": "Scorpio",
    "Sg": "Sagittarius",
    "Cp": "Capricorn",
    "Aq": "Aquarius",
    "Pi": "Pisces",
}
SPECIAL_ASPECTS = {
    "Mars": ((4, "4th"), (8, "8th")),
    "Jupiter": ((5, "5th"), (9, "9th")),
    "Saturn": ((3, "3rd"), (10, "10th")),
}
MOVABLE_SIGNS = {"Ar", "Cn", "Li", "Cp"}
FIXED_SIGNS = {"Ta", "Le", "Sc", "Aq"}
DUAL_SIGNS = {"Ge", "Vi", "Sg", "Pi"}


def main() -> None:
    chart_paths = sorted(CHARTS_OUT.glob("*.json"))
    if not chart_paths:
        print(f"No chart JSON files found in {CHARTS_OUT}")
        return

    for chart_path in chart_paths:
        output_path, page_count = build_report(chart_path)
        page_label = "page" if page_count == 1 else "pages"
        print(f"Wrote {output_path} ({page_count} {page_label})")


def build_report(chart_path: Path) -> tuple[Path, int]:
    chart_name = chart_path.stem
    chart = json.loads(chart_path.read_text())
    rendered_dir = CHARTS_RENDERED / chart_name
    d1_svg = (rendered_dir / "d1_north_indian.svg").read_text()
    d9_svg = (rendered_dir / "d9_north_indian.svg").read_text()
    western_chart = western_chart_for_report(rendered_dir)
    page_2 = render_template(
        {
            "western_chart": western_chart,
            "western_rows": western_rows(chart),
            "western_aspect_rows": western_aspect_rows(chart, chart_name),
        },
        template_path=PAGE_2_TEMPLATE,
    )

    html_text = render_template(
        {
            "report_title": escape(f"{chart_name} Report"),
            "styles": STYLES.read_text(),
            "name": escape(chart_name),
            "birth_date": escape(chart.get("metadata", {}).get("date", "")),
            "birth_time": escape(chart.get("metadata", {}).get("time", "")),
            "place": escape(chart.get("metadata", {}).get("place", "")),
            "ayanamsa": escape(chart.get("metadata", {}).get("ayanamsa", "")),
            "d1_north_svg": d1_svg,
            "d9_north_svg": d9_svg,
            "graha_rows": graha_rows(chart),
            "aspect_rows": aspect_rows(chart),
            "rashi_rows": rashi_rows(chart),
            "page_2": page_2,
        }
    )

    REPORTS_OUT.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_OUT / f"{chart_name}_report.pdf"
    document = HTML(string=html_text, base_url=str(ROOT)).render()
    document.write_pdf(output_path)
    return output_path, len(document.pages)


def western_chart_for_report(rendered_dir: Path) -> str:
    png_path = rendered_dir / "d1_western.png"
    if png_path.exists() and png_path.stat().st_size > 50_000:
        return (
            '<img class="western-chart-image" '
            f'src="{png_path.resolve().as_uri()}" '
            'alt="Western chart">'
        )

    print(
        f"WARNING: {png_path} missing or blank-looking; embedding d1_western.svg. "
        "Western glyph rendering may differ in PDF."
    )
    return (rendered_dir / "d1_western.svg").read_text()


def render_template(values: dict[str, str], *, template_path: Path = TEMPLATE) -> str:
    template = template_path.read_text()
    for key, value in values.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def graha_rows(chart: dict) -> str:
    primary = primary_positions(chart)
    d9 = chart.get("calculated_charts", {}).get("d9", {})
    rows = []
    for graha in GRAHAS:
        position = primary.get(graha)
        if not position:
            continue
        rows.append(
            "<tr>"
            f"<td>{escape(ABBREVIATIONS[graha])}</td>"
            f"<td>{escape(longitude_text(position))}</td>"
            f"<td>{escape(position.get('nakshatra') or '')}</td>"
            f"<td>{escape(position.get('pada') or '')}</td>"
            f"<td>{escape(position.get('chara_karaka') or '')}</td>"
            f"<td>{escape(sign_display(d9.get(graha, {}).get('sign')))}</td>"
            f"<td>{escape(motion_text(position))}</td>"
            f"<td>{escape(speed_text(position.get('speed')))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def western_rows(chart: dict) -> str:
    primary = primary_positions(chart)
    asc_sign = chart.get("calculated_charts", {}).get("d1", {}).get("Lagna", {}).get("sign")
    rows = []
    for graha in GRAHAS:
        position = primary.get(graha)
        if not position:
            continue
        sign = position.get("sign")
        rows.append(
            "<tr>"
            f"<td>{escape(ABBREVIATIONS[graha])}</td>"
            f"<td>{escape(longitude_text(position))}</td>"
            f"<td>{escape(whole_sign_house(asc_sign, sign))}</td>"
            f"<td>{escape(motion_text(position))}</td>"
            f"<td>{escape(speed_text(position.get('speed')))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def western_aspect_rows(chart: dict, chart_name: str) -> str:
    stellium_chart = build_western_chart(chart, chart_name)
    rows = []
    for aspect in stellium_chart.aspects:
        rows.append(
            "<tr>"
            f"<td>{escape(western_body_label(aspect.object1.name))}</td>"
            f"<td>{escape(aspect.aspect_name)}</td>"
            f"<td>{escape(western_body_label(aspect.object2.name))}</td>"
            f"<td>{escape(f'{aspect.orb:.2f}°')}</td>"
            "</tr>"
        )
    if not rows:
        return '<tr><td colspan="4" class="muted">No Opposition, Trine, or Square aspects within configured orb.</td></tr>'
    return "\n".join(rows)


def rashi_rows(chart: dict) -> str:
    primary = primary_positions(chart)
    sign_to_grahas: dict[str, list[str]] = {sign: [] for sign in SIGNS}
    for graha in GRAHAS:
        position = primary.get(graha)
        if position and position.get("sign") in sign_to_grahas:
            sign_to_grahas[position["sign"]].append(graha)

    occupied_signs = [sign for sign in SIGNS if sign_to_grahas[sign]]
    rows = []
    for sign in occupied_signs:
        aspected_signs = rashi_drishti_signs(sign)
        targets = []
        for aspected_sign in aspected_signs:
            for graha in sign_to_grahas[aspected_sign]:
                targets.append(f"{ABBREVIATIONS[graha]} ({sign_display(aspected_sign)})")

        rows.append(
            "<tr>"
            f"<td>{escape(sign_display(sign))}</td>"
            f"<td>{escape(', '.join(sign_display(item) for item in aspected_signs))}</td>"
            f"<td>{escape(', '.join(targets) or 'None')}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def aspect_rows(chart: dict) -> str:
    primary = primary_positions(chart)
    sign_to_grahas: dict[str, list[str]] = {sign: [] for sign in SIGNS}
    for graha in GRAHAS:
        position = primary.get(graha)
        if position and position.get("sign") in sign_to_grahas:
            sign_to_grahas[position["sign"]].append(graha)

    rows = []
    for graha in GRAHAS:
        position = primary.get(graha)
        if not position:
            continue

        source_sign = position.get("sign")
        if source_sign not in SIGNS:
            continue

        aspect_specs = [(7, "7th")]
        aspect_specs.extend(SPECIAL_ASPECTS.get(graha, ()))
        aspect_parts = []
        special_parts = []
        targets = []
        for count, label in aspect_specs:
            target_sign = sign_from(source_sign, count)
            aspect_parts.append(f"{label}: {sign_display(target_sign)}")
            if count != 7:
                special_parts.append(label)
            for target in sign_to_grahas[target_sign]:
                if target != graha:
                    targets.append(f"{ABBREVIATIONS[target]} ({sign_display(target_sign)})")

        rows.append(
            "<tr>"
            f"<td>{escape(ABBREVIATIONS[graha])}</td>"
            f"<td>{escape('; '.join(aspect_parts))}</td>"
            f"<td>{escape(', '.join(special_parts) or 'None')}</td>"
            f"<td>{escape(', '.join(targets) or 'None')}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def primary_positions(chart: dict) -> dict[str, dict]:
    return {
        position["body"]: position
        for position in chart.get("primary_positions", [])
        if position.get("body") in GRAHAS
    }


def longitude_text(position: dict) -> str:
    sign = sign_display(position.get("sign"))
    degree = int(position.get("degree_in_sign") or 0)
    minute = int(position.get("minute") or 0)
    second = float(position.get("second") or 0)
    return f"{sign} {degree}°{minute:02d}'{second:05.2f}\""


def sign_from(source_sign: str, house_count: int) -> str:
    source_index = SIGNS.index(source_sign)
    return SIGNS[(source_index + house_count - 1) % 12]


def rashi_drishti_signs(sign: str) -> list[str]:
    if sign in MOVABLE_SIGNS:
        return [
            item
            for item in SIGNS
            if item in FIXED_SIGNS and item != sign_from(sign, 2)
        ]
    if sign in FIXED_SIGNS:
        return [
            item
            for item in SIGNS
            if item in MOVABLE_SIGNS and item != sign_from(sign, 12)
        ]
    if sign in DUAL_SIGNS:
        return [item for item in SIGNS if item in DUAL_SIGNS and item != sign]
    return []


def sign_display(sign: str | None) -> str:
    return sign or ""


def whole_sign_house(asc_sign: str | None, sign: str | None) -> str:
    if asc_sign not in SIGNS or sign not in SIGNS:
        return ""
    return str(((SIGNS.index(sign) - SIGNS.index(asc_sign)) % 12) + 1)


def motion_text(position: dict) -> str:
    status = position.get("motion_status")
    if status == "direct" or position.get("direct") is True:
        return "Direct"
    if status == "retrograde" or position.get("retrograde") is True:
        return "Retrograde"
    if status == "stationary" or position.get("stationary") is True:
        return "Stationary"
    if status == "not_applicable":
        return "Not applicable"
    if status:
        return str(status).replace("_", " ").title()
    return ""


def speed_text(speed: object) -> str:
    if speed is None:
        return "—"
    try:
        return f"{float(speed):.4f}°/day"
    except (TypeError, ValueError):
        return str(speed)


def western_body_label(name: str) -> str:
    if name == "True Node":
        return "Ra"
    if name == "South Node":
        return "Ke"
    return ABBREVIATIONS.get(name, name)


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    main()
