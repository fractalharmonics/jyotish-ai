"""Western-style circular D1 rendering backed by Stellium."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image
from playwright.sync_api import sync_playwright
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


def create_western_png(input_path, output_path, *, width: int = 1800) -> bool:
    input_path = Path(input_path)
    output_path = Path(output_path)
    if output_path.exists():
        output_path.unlink()

    chart_width, chart_height = _svg_dimensions(input_path)
    svg_url = input_path.resolve().as_uri()
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{ margin: 0; padding: 0; background: white; }}
    img {{ display: block; width: {width}px; height: {round(width * chart_height / chart_width)}px; }}
  </style>
</head>
<body>
  <img src="{svg_url}" alt="Western chart">
</body>
</html>"""
    with tempfile.TemporaryDirectory() as temp_dir:
        wrapper_path = Path(temp_dir) / "western_chart.html"
        wrapper_path.write_text(html)
        wrapper_url = wrapper_path.resolve().as_uri()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                args=["--allow-file-access-from-files"],
            )
            page = browser.new_page(
                viewport={"width": width, "height": round(width * chart_height / chart_width)},
                device_scale_factor=1,
            )
            page.goto(wrapper_url, wait_until="networkidle")
            page.wait_for_function(
                "() => { const img = document.querySelector('img'); return img && img.complete && img.naturalWidth > 0; }"
            )
            page.screenshot(path=str(output_path), full_page=True)
            browser.close()

    return _png_is_usable(output_path)


def _svg_dimensions(path: Path) -> tuple[float, float]:
    root = ET.fromstring(path.read_text())
    view_box = root.get("viewBox")
    if view_box:
        parts = [float(part) for part in view_box.replace(",", " ").split()]
        if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
            return parts[2], parts[3]

    width = _svg_length(root.get("width"))
    height = _svg_length(root.get("height"))
    if width and height:
        return width, height
    return 780.0, 780.0


def _svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", value)
    return float(match.group(0)) if match else None


def _png_is_usable(path: Path) -> bool:
    if not path.exists():
        print(f"WARNING: Western PNG was not generated: {path}")
        return False
    if path.stat().st_size <= 50_000:
        print(f"WARNING: Western PNG appears too small: {path} ({path.stat().st_size} bytes)")
        return False

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        non_white = 0
        for red, green, blue in rgb.getdata():
            if red < 250 or green < 250 or blue < 250:
                non_white += 1
                if non_white > 1_000:
                    return True

    print(f"WARNING: Western PNG appears blank: {path}")
    return False
