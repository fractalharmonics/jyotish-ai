"""Western-style circular D1 rendering backed by Stellium."""

from __future__ import annotations

import re

from stellium.visualization.builder import ChartDrawBuilder

from renderers.stellium_adapter import build_western_chart


def render_d1_western(chart: dict, chart_name: str, output_path) -> str:
    stellium_chart = build_western_chart(chart, chart_name)
    rendered_path = (
        ChartDrawBuilder(stellium_chart)
        .with_filename(str(output_path))
        .with_size(760)
        .with_theme("classic")
        .with_house_systems("Whole Sign")
        .with_zodiac_palette("grey")
        .with_aspect_palette("classic")
        .with_planet_glyph_palette("default")
        .with_adaptive_colors(False)
        .with_planet_ticks(True)
        .with_degree_ticks(False)
        .preset_minimal()
        .without_header()
        .without_tables()
        .without_moon_phase()
        .save()
    )
    _normalize_glyph_colors(output_path)
    return rendered_path


def _normalize_glyph_colors(path) -> None:
    svg = path.read_text()
    svg = svg.replace(
        '&quot;Symbola&quot;, &quot;Noto Sans Symbols&quot;, &quot;Apple Symbols&quot;, &quot;Segoe UI Symbol&quot;, serif',
        "DejaVu Sans, Arial Unicode MS, Arial, sans-serif",
    )
    svg = re.sub(
        r'(<text\b(?=[^>]*font-family="[^"]*(?:Symbola|DejaVu Sans)[^"]*")[^>]*\sfill=")#[0-9A-Fa-f]{6}(")',
        r"\1#222222\2",
        svg,
    )
    path.write_text(svg)
