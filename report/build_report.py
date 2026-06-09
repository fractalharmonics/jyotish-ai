from __future__ import annotations

import html
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))

from weasyprint import HTML


CHARTS_OUT = ROOT / "charts_out"
CHARTS_RENDERED = ROOT / "charts_rendered"
REPORTS_OUT = ROOT / "reports"
TEMPLATE = Path(__file__).resolve().parent / "templates" / "page_1.html"
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
SIGN_LORDS = {
    "Ar": "Mars",
    "Ta": "Venus",
    "Ge": "Mercury",
    "Cn": "Moon",
    "Le": "Sun",
    "Vi": "Mercury",
    "Li": "Venus",
    "Sc": "Mars",
    "Sg": "Jupiter",
    "Cp": "Saturn",
    "Aq": "Saturn",
    "Pi": "Jupiter",
}
EXALTATION = {
    "Sun": "Ar",
    "Moon": "Ta",
    "Mars": "Cp",
    "Mercury": "Vi",
    "Jupiter": "Cn",
    "Venus": "Pi",
    "Saturn": "Li",
}
DEBILITATION = {
    "Sun": "Li",
    "Moon": "Sc",
    "Mars": "Cn",
    "Mercury": "Pi",
    "Jupiter": "Cp",
    "Venus": "Vi",
    "Saturn": "Ar",
}
FRIENDS = {
    "Sun": {"Moon", "Mars", "Jupiter"},
    "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"},
    "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"},
    "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
}
ENEMIES = {
    "Sun": {"Venus", "Saturn"},
    "Moon": set(),
    "Mars": {"Mercury"},
    "Mercury": {"Moon"},
    "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"},
    "Saturn": {"Sun", "Moon", "Mars"},
}
SPECIAL_ASPECTS = {
    "Mars": ((4, "4th"), (8, "8th")),
    "Jupiter": ((5, "5th"), (9, "9th")),
    "Saturn": ((3, "3rd"), (10, "10th")),
}


def main() -> None:
    chart_paths = sorted(CHARTS_OUT.glob("*.json"))
    if not chart_paths:
        print(f"No chart JSON files found in {CHARTS_OUT}")
        return

    for chart_path in chart_paths:
        output_path, page_count = build_report(chart_path)
        print(f"Wrote {output_path} ({page_count} page)")


def build_report(chart_path: Path) -> Path:
    chart_name = chart_path.stem
    chart = json.loads(chart_path.read_text())
    rendered_dir = CHARTS_RENDERED / chart_name
    d1_svg = (rendered_dir / "d1_north_indian.svg").read_text()
    d9_svg = (rendered_dir / "d9_north_indian.svg").read_text()

    html_text = render_template(
        {
            "report_title": escape(f"{chart_name} Page 1"),
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
        }
    )

    REPORTS_OUT.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_OUT / f"{chart_name}_page1.pdf"
    document = HTML(string=html_text, base_url=str(ROOT)).render()
    document.write_pdf(output_path)
    return output_path, len(document.pages)


def render_template(values: dict[str, str]) -> str:
    template = TEMPLATE.read_text()
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
            f"<td>{escape(dignity(graha, position.get('sign')))}</td>"
            f"<td>{escape(sign_display(d9.get(graha, {}).get('sign')))}</td>"
            f"<td>{escape(position.get('nakshatra') or '')}</td>"
            f"<td>{escape(position.get('chara_karaka') or '')}</td>"
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


def dignity(graha: str, sign: str | None) -> str:
    if graha in {"Rahu", "Ketu"} or sign not in SIGNS:
        return "Node"
    if EXALTATION.get(graha) == sign:
        return "Exalted"
    if DEBILITATION.get(graha) == sign:
        return "Debilitated"
    lord = SIGN_LORDS[sign]
    if lord == graha:
        return "Own sign"
    if lord in FRIENDS.get(graha, set()):
        return "Friend sign"
    if lord in ENEMIES.get(graha, set()):
        return "Enemy sign"
    return "Neutral"


def sign_from(source_sign: str, house_count: int) -> str:
    source_index = SIGNS.index(source_sign)
    return SIGNS[(source_index + house_count - 1) % 12]


def sign_display(sign: str | None) -> str:
    return SIGN_NAMES.get(sign or "", sign or "")


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    main()
