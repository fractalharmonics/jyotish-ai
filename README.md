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
- `inspect_pyjhora.py` and `explore_motion.py` are temporary exploration tools
  for mapping PyJHora APIs.

## Usage

Put JHora TXT exports in `charts_in/`, then run:

```bash
python3 process_charts.py
```

To regenerate outputs even when JSON already exists:

```bash
python3 process_charts.py --force
```

Input and output chart files are ignored by Git. The `charts_in/` and
`charts_out/` directories are kept in the repository with `.gitkeep` files.

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

Motion enrichment uses PyJHora when available. The current local environment
needed these runtime packages:

```bash
python -m pip install pyswisseph numpy geocoder pytz timezonefinder geopy python-dateutil
```

If PyJHora import or motion enrichment fails, processing should still complete
and the failure is recorded in `enrichment.notes`.
