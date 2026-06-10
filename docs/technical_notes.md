# Technical Notes

## Source Of Truth

Parsed JHora TXT positions are canonical for D1 source positions.

Enrichment may add derived data, but it should not overwrite parsed source
positions. In particular, `positions` should remain the raw parsed JHora
position table.

## Rahu/Ketu Handling

The JHora export used during validation matches Swiss Ephemeris `MEAN_NODE` for
Rahu/Ketu.

In the currently installed PyJHora build, `dhasavarga()` returns `TRUE_NODE`
values for Rahu/Ketu. The `set_rahu_ketu_as_true_nodes=False` parameter appears
to be ignored by `dhasavarga()`.

Therefore, do not use PyJHora Rahu/Ketu longitudes as canonical unless this
behavior is corrected upstream or explicitly handled in local code.

## Correct Node Reproduction Method

To reproduce the validated JHora Rahu/Ketu values, use direct Swiss Ephemeris
`MEAN_NODE` with sidereal `SIDM_USER` ayanamsa from JHora metadata.

Do not document local chart-specific node longitudes in committed files.

## Current Architecture

- `parser_jhora.py` parses raw source data.
- `enrich.py` adds derived/enriched data.
- `process_charts.py` orchestrates file processing.
- `render_charts.py` renders SVG charts from generated JSON.
- `report/build_report.py` builds the first-page PDF report from generated JSON
  and SVG charts.
- `positions` remains raw.
- `primary_positions` may contain enrichment.

## Divisional Degree Policy

Projected D9/D10/D20 degrees are suppressed because the source JHora TXT export
does not provide full divisional longitudes and the projected-degree method has
not been verified against JHora display conventions. Do not re-enable
divisional degrees or introduce correction factors until the methodology is
validated.

## D10 Method

D10 is derived from source-aligned D1 longitudes with PyJHora
`jhora.horoscope.chart.charts.divisional_positions_from_rasi_positions()` using
`divisional_chart_factor=10` and `chart_method=1`. The installed PyJHora source
documents `dasamsa_chart(..., chart_method=1)` as Traditional Parasara, while
`chart_method=4` is Parivritti Cyclic.

## Report Aspect Rules

Graha drishti uses sign-based Vedic planetary aspects:

- All grahas aspect the 7th sign from their placement.
- Mars additionally aspects the 4th and 8th signs.
- Jupiter additionally aspects the 5th and 9th signs.
- Saturn additionally aspects the 3rd and 10th signs.

Rashi drishti is kept separate from graha drishti:

- Movable signs aspect fixed signs except the adjacent fixed sign.
- Fixed signs aspect movable signs except the adjacent movable sign.
- Dual signs aspect all other dual signs.
