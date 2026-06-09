"""Western-style circular D1 rendering backed by Stellium."""

from __future__ import annotations

from stellium.visualization.builder import ChartDrawBuilder

from renderers.stellium_adapter import build_western_chart


def render_d1_western(chart: dict, chart_name: str, output_path) -> str:
    stellium_chart = build_western_chart(chart, chart_name)
    return (
        ChartDrawBuilder(stellium_chart)
        .with_filename(str(output_path))
        .with_size(760)
        .with_theme("classic")
        .with_house_systems("Whole Sign")
        .with_zodiac_palette("monochrome")
        .with_planet_glyph_palette("default")
        .with_planet_ticks(True)
        .with_degree_ticks(False)
        .preset_minimal()
        .without_header()
        .without_tables()
        .without_moon_phase()
        .save()
    )
