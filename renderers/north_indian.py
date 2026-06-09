"""North Indian D1 rendering backed by Stellium."""

from __future__ import annotations

import re

from stellium.visualization.vedic.north_indian import NorthIndianRenderer

from renderers.stellium_adapter import build_north_indian_chart


PLANET_ABBREVIATIONS = {
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


class DegreeNorthIndianRenderer(NorthIndianRenderer):
    def __init__(
        self,
        *args,
        degree_labels: dict[str, str] | None = None,
        show_planet_degrees: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.degree_labels = degree_labels or {}
        self.show_planet_degrees = show_planet_degrees

    def _get_planets_by_sign(self, chart):
        planets_by_sign = super()._get_planets_by_sign(chart)
        for sign_planets in planets_by_sign.values():
            sign_planets.sort(key=lambda planet: planet.degree)
        return planets_by_sign

    def _planet_label(self, planet):
        label = PLANET_ABBREVIATIONS.get(planet.name, planet.name[:2])
        if self.show_planet_degrees:
            degree_label = self.degree_labels.get(planet.name)
            if degree_label:
                label = f"{label} {degree_label}"
        return label


def render_d1_north_indian(
    chart: dict,
    chart_name: str,
    *,
    show_planet_degrees: bool = False,
) -> str:
    return render_north_indian(
        chart,
        chart_name,
        chart_key="d1",
        show_planet_degrees=show_planet_degrees,
    )


def render_d9_north_indian(chart: dict, chart_name: str) -> str:
    return render_north_indian(
        chart,
        chart_name,
        chart_key="d9",
        show_planet_degrees=False,
    )


def render_north_indian(
    chart: dict,
    chart_name: str,
    *,
    chart_key: str,
    show_planet_degrees: bool = False,
) -> str:
    stellium_chart = build_north_indian_chart(
        chart,
        chart_name,
        chart_key=chart_key,
    )
    renderer = DegreeNorthIndianRenderer(
        size=640,
        theme="classic",
        show_degrees=False,
        label_style="number",
        degree_labels=_degree_labels_from_primary_positions(chart),
        show_planet_degrees=show_planet_degrees,
    )
    svg = renderer.render(stellium_chart)
    return _underline_retrograde_abbreviations(
        svg,
        _retrograde_labels(chart, show_planet_degrees=show_planet_degrees),
    )


def _degree_labels_from_primary_positions(chart: dict) -> dict[str, str]:
    labels = {}
    for position in chart.get("primary_positions", []):
        body = position.get("body")
        if body not in PLANET_ABBREVIATIONS:
            continue

        degree = position.get("degree_in_sign")
        minute = position.get("minute")
        if degree is None or minute is None:
            continue

        labels[body] = f"{int(degree)}°{int(minute):02d}'"

    return labels


def _retrograde_labels(
    chart: dict,
    *,
    show_planet_degrees: bool,
) -> dict[str, str]:
    degree_labels = _degree_labels_from_primary_positions(chart)
    labels = {}

    for position in chart.get("primary_positions", []):
        body = position.get("body")
        if body in {"Rahu", "Ketu"} or body not in PLANET_ABBREVIATIONS:
            continue
        if position.get("retrograde") is not True:
            continue

        abbreviation = PLANET_ABBREVIATIONS[body]
        label = abbreviation
        if show_planet_degrees and body in degree_labels:
            label = f"{abbreviation} {degree_labels[body]}"
        labels[label] = abbreviation

    return labels


def _underline_retrograde_abbreviations(
    svg: str,
    retrograde_labels: dict[str, str],
) -> str:
    for full_label, abbreviation in retrograde_labels.items():
        svg = re.sub(
            rf"(>){re.escape(full_label)}(<)",
            lambda match: _underlined_label(match, abbreviation, full_label),
            svg,
        )
    return svg


def _underlined_label(match, abbreviation: str, full_label: str) -> str:
    suffix = full_label[len(abbreviation) :]
    suffix_tspan = f"<tspan>{suffix}</tspan>" if suffix else ""
    return (
        f"{match.group(1)}"
        f'<tspan text-decoration="underline">{abbreviation}</tspan>'
        f"{suffix_tspan}"
        f"{match.group(2)}"
    )
