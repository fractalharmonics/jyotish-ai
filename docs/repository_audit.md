# Repository Audit

## Scope

Reviewed tracked source files, renderers, report code, validation code,
documentation, generated-output locations, and local ignored artifacts.

## PII Findings

- `charts_in/Yashta.txt` contains real chart input data. It is ignored by Git.
- `charts_out/Yashta.json` contains derived real chart data. It is ignored by Git.
- `charts_rendered/Yashta/*` contains rendered real chart output. It is ignored by Git.
- `reports/Yashta_page1.pdf` contains report output for a real chart. It is ignored by Git.

No tracked source file currently contains the chart name, birth date, birth
time, or birth location from the local chart.

## Chart-Specific Assumptions Removed

- `validate_output.py` previously referenced a specific chart path and specific
  natal assertions. It now validates all `charts_out/*.json` files by schema and
  cross-field integrity.
- `docs/technical_notes.md` previously included local chart Rahu/Ketu numeric
  examples. Those values were removed.

## Remaining Domain Constants

The following are not PII and are retained as domain logic:

- Graha order and abbreviations.
- Sign abbreviations and sign names.
- Dignity tables.
- Vedic graha drishti and rashi drishti rules.
- Stellium renderer configuration.

## Generated Output Policy

The following generated or local-data directories are ignored:

- `charts_in/*` except `.gitkeep`
- `charts_out/*` except `.gitkeep`
- `charts_rendered/`
- `reports/`
- `.cache/`

## Recommended Remediation

- Keep real chart input, JSON, SVG, and PDF outputs out of version control.
- Use synthetic sample chart data if committed examples are needed later.
- Keep validation generic and avoid assertions tied to one natal chart.
- Prefer `python3 build_chart_package.py` as the standard one-command workflow.
