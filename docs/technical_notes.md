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

Expected validated values for the local test chart:

- Rahu: approximately `75.099789`
- Ketu: approximately `255.099789`

## Current Architecture

- `parser_jhora.py` parses raw source data.
- `enrich.py` adds derived/enriched data.
- `process_charts.py` orchestrates file processing.
- `positions` remains raw.
- `primary_positions` may contain enrichment.
