import json
import traceback
from pathlib import Path

from renderers.north_indian import (
    render_d1_north_indian,
    render_d9_north_indian,
    render_d10_north_indian,
    render_d20_north_indian,
)
from renderers.western import create_western_png, render_d1_western


INPUT_DIR = Path("charts_out")
OUTPUT_DIR = Path("charts_rendered")


def render_chart_file(chart_path):
    with chart_path.open("r", encoding="utf-8") as input_file:
        chart = json.load(input_file)

    chart_name = chart_path.stem
    if not has_required_calculated_charts(chart):
        print(
            f"Skipping {chart_name}: missing calculated_charts.d1/d9/d10/d20; "
            "enrichment incomplete"
        )
        return []

    chart_output_dir = OUTPUT_DIR / chart_name
    chart_output_dir.mkdir(parents=True, exist_ok=True)

    outputs = []

    north_path = chart_output_dir / "d1_north_indian.svg"
    try:
        north_svg = render_d1_north_indian(
            chart,
            chart_name,
            show_planet_degrees=True,
        )
        north_path.write_text(north_svg, encoding="utf-8")
        outputs.append(north_path)
        print(f"Rendered {north_path}")
    except Exception as error:
        print(f"ERROR rendering {chart_path} North Indian D1: {error}")
        traceback.print_exc()

    d9_north_path = chart_output_dir / "d9_north_indian.svg"
    try:
        d9_north_svg = render_d9_north_indian(chart, chart_name)
        d9_north_path.write_text(d9_north_svg, encoding="utf-8")
        outputs.append(d9_north_path)
        print(f"Rendered {d9_north_path}")
    except Exception as error:
        print(f"ERROR rendering {chart_path} North Indian D9: {error}")
        traceback.print_exc()

    d10_north_path = chart_output_dir / "d10_north_indian.svg"
    try:
        d10_north_svg = render_d10_north_indian(chart, chart_name)
        d10_north_path.write_text(d10_north_svg, encoding="utf-8")
        outputs.append(d10_north_path)
        print(f"Rendered {d10_north_path}")
    except Exception as error:
        print(f"ERROR rendering {chart_path} North Indian D10: {error}")
        traceback.print_exc()

    d20_north_path = chart_output_dir / "d20_north_indian.svg"
    try:
        d20_north_svg = render_d20_north_indian(chart, chart_name)
        d20_north_path.write_text(d20_north_svg, encoding="utf-8")
        outputs.append(d20_north_path)
        print(f"Rendered {d20_north_path}")
    except Exception as error:
        print(f"ERROR rendering {chart_path} North Indian D20: {error}")
        traceback.print_exc()

    western_path = chart_output_dir / "d1_western.svg"
    western_png_path = chart_output_dir / "d1_western.png"
    try:
        render_d1_western(chart, chart_name, western_path)
        outputs.append(western_path)
        print(f"Rendered {western_path}")
        if create_western_png(western_path, western_png_path):
            outputs.append(western_png_path)
            print(f"Rendered {western_png_path}")
    except Exception as error:
        print(f"ERROR rendering {chart_path} Western D1: {error}")
        traceback.print_exc()

    return outputs


def has_required_calculated_charts(chart):
    calculated_charts = chart.get("calculated_charts")
    if not isinstance(calculated_charts, dict):
        return False
    return all(
        bool(calculated_charts.get(chart_key))
        for chart_key in ("d1", "d9", "d10", "d20")
    )


def main():
    chart_paths = sorted(INPUT_DIR.glob("*.json"))
    if not chart_paths:
        print(f"No chart JSON files found in {INPUT_DIR}")
        return

    for chart_path in chart_paths:
        try:
            render_chart_file(chart_path)
        except Exception as error:
            print(f"ERROR processing {chart_path}: {error}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
