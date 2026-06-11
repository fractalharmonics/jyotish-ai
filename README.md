# Jyotish AI

Utilities for converting Jagannatha Hora TXT exports into structured JSON, with
an optional PyJHora enrichment layer.

## Project Layout

- `process_charts.py` scans `charts_in/*.txt`, parses each chart, enriches it,
  and writes JSON to `charts_out/<chart_name>.json`.
- `parser_jhora.py` contains the stable JHora TXT parser. It owns metadata,
  positions, primary positions, and Vimshottari dasha parsing.
- `enrich.py` adds deterministic local enrichment. It currently adds PyJHora
  availability notes, planetary motion data for `primary_positions`, and
  top-level `data_notes`.
- `render_charts.py` renders generated chart JSON into SVG charts.

## Usage

Put JHora TXT exports in `charts_in/`, then run:

```bash
./build.sh
```

This runs the full local pipeline:

1. Parse JHora TXT exports.
2. Enrich chart JSON.
3. Validate outputs.
4. Render SVG/PNG charts.
5. Build PDF reports.

`build.sh` always uses `.venv/bin/python` so the build does not accidentally run
with system Python.

Input chart files, generated chart JSON, rendered charts, and reports are
ignored by Git. The `charts_in/` and `charts_out/` directories are kept in the
repository with `.gitkeep` files.

## Setup

Create the project virtual environment and install dependencies into it:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install pyswisseph numpy geocoder pytz timezonefinder geopy python-dateutil weasyprint stellium playwright
python -m playwright install chromium
```

## Manual/Debug Commands

The wrapper is preferred for normal use. For debugging individual stages:

```bash
source .venv/bin/activate
python3 process_charts.py --force
python3 validate_output.py
python3 render_charts.py
python3 report/build_report.py
```

Avoid using bare `python3 build_chart_package.py` as the primary command. It may
use system Python and fail when dependencies are installed only in `.venv`.

## Example Input

A JHora TXT export should look broadly like this. The values below are generic
placeholders and are only intended to show the format expected by the parser.

```text
C:\Path\To\Jagannatha Hora\data\Example

Natal Chart

Date:          January 1, 2000
Time:          12:00:00 pm
Time Zone:     0:00:00 (East of GMT)
Place:         000 E 00' 00", 00 N 00' 00"
               Example City, Example Region, Example Country
Altitude:      0.00 meters

Tithi:         Example Tithi
Vedic Weekday: Example Weekday
Nakshatra:     Example Nakshatra
Yoga:          Example Yoga
Karana:        Example Karana

Ayanamsa:      00-00-00.00
Sidereal Time: 00:00:00

Body                    Longitude        Nakshatra Pada Rasi Navamsa

Lagna                    0 Ar 00' 00.00" Aswi      1    Ar   Ar
Sun                      1 Ar 00' 00.00" Aswi      1    Ar   Ar
Moon                     2 Ta 00' 00.00" Krit      2    Ta   Ta
Mars                     3 Ge 00' 00.00" Mrig      3    Ge   Ge
Mercury                  4 Cn 00' 00.00" Push      4    Cn   Cn
Jupiter                  5 Le 00' 00.00" Magh      1    Le   Le
Venus                    6 Vi 00' 00.00" UPha      2    Vi   Vi
Saturn                   7 Li 00' 00.00" Swat      3    Li   Li
Rahu                     8 Sc 00' 00.00" Anu       4    Sc   Sc
Ketu                     8 Ta 00' 00.00" Rohi      4    Ta   Ta

Rasi

Vimsottari Dasa:
Sun 2000-01-01
```

## Output Notes

The JSON preserves raw parser output and keeps enrichment separate:

- `positions`: raw parsed JHora position table, not enriched.
- `primary_positions`: primary chart bodies with enrichment applied where
  available.
- `enrichment`: PyJHora status and enrichment notes.
- `data_notes`: short descriptions of raw versus enriched sections.

## Dependencies

The parser uses only the Python standard library.

The full build uses PyJHora-related runtime dependencies, Stellium rendering,
WeasyPrint PDF generation, and Playwright/Chromium rasterization. Install them
into `.venv` with the setup commands above.

`build.sh` requires `.venv/bin/python`. If it is missing, create the virtual
environment and install dependencies before building.

If PyJHora import or motion enrichment fails, processing should still complete
and the failure is recorded in `enrichment.notes`.
