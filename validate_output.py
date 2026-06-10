from __future__ import annotations

import argparse
import json
from pathlib import Path


INPUT_DIR = Path("charts_out")

EXPECTED_TOP_LEVEL_KEYS = {
    "metadata",
    "positions",
    "primary_positions",
    "dashas",
    "enrichment",
    "data_notes",
    "calculated_charts",
}

EXPECTED_METADATA_KEYS = {
    "date",
    "time",
    "place",
    "coordinates",
}

EXPECTED_COORDINATE_KEYS = {
    "longitude_decimal",
    "latitude_decimal",
}

EXPECTED_PRIMARY_BODIES = [
    "Lagna",
    "Sun",
    "Moon",
    "Mars",
    "Mercury",
    "Jupiter",
    "Venus",
    "Saturn",
    "Rahu",
    "Ketu",
]

EXPECTED_CALCULATED_CHARTS = {
    "d1",
    "d9",
    "d10",
    "d20",
}

NON_D1_CHARTS = EXPECTED_CALCULATED_CHARTS - {"d1"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate generated chart JSON structure and integrity."
    )
    strict_group = parser.add_mutually_exclusive_group()
    strict_group.add_argument(
        "--strict",
        action="store_true",
        help="Fail when enrichment-dependent calculated charts are missing.",
    )
    strict_group.add_argument(
        "--non-strict",
        action="store_false",
        dest="strict",
        help="Warn instead of failing when calculated charts are missing.",
    )
    parser.set_defaults(strict=False)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Chart JSON path(s). Defaults to charts_out/*.json.",
    )
    return parser.parse_args()


def chart_paths(paths: list[Path]) -> list[Path]:
    if paths:
        return paths
    discovered = sorted(INPUT_DIR.glob("*.json"))
    if not discovered:
        raise AssertionError(f"No generated chart JSON files found in {INPUT_DIR}")
    return discovered


def assert_contains_keys(container, expected_keys, label):
    missing = expected_keys - set(container)
    assert not missing, f"{label} missing keys: {sorted(missing)}"


def validate_chart(chart: dict, chart_label: str, *, strict: bool) -> list[str]:
    warnings = []
    expected_top_level_keys = set(EXPECTED_TOP_LEVEL_KEYS)
    if not strict:
        expected_top_level_keys.discard("calculated_charts")
    assert_contains_keys(chart, expected_top_level_keys, f"{chart_label} top-level JSON")

    metadata = chart["metadata"]
    assert_contains_keys(metadata, EXPECTED_METADATA_KEYS, f"{chart_label} metadata")
    assert_contains_keys(
        metadata["coordinates"],
        EXPECTED_COORDINATE_KEYS,
        f"{chart_label} metadata.coordinates",
    )

    primary_positions = chart["primary_positions"]
    primary_by_body = {position["body"]: position for position in primary_positions}

    assert list(primary_by_body) == EXPECTED_PRIMARY_BODIES, (
        f"{chart_label} primary_positions bodies mismatch: "
        f"expected {EXPECTED_PRIMARY_BODIES}, got {list(primary_by_body)}"
    )

    calculated_charts = chart.get("calculated_charts")
    if not calculated_charts:
        warning = f"{chart_label}: missing calculated_charts; enrichment incomplete"
        if strict:
            raise AssertionError(warning)
        warnings.append(warning)
        try:
            validate_motion_fields(chart_label, primary_by_body)
        except AssertionError as error:
            warnings.append(f"{chart_label}: {error}; enrichment incomplete")
        return warnings

    assert_contains_keys(
        calculated_charts,
        EXPECTED_CALCULATED_CHARTS,
        f"{chart_label} calculated_charts",
    )

    validate_d1(chart_label, primary_by_body, calculated_charts["d1"])
    validate_divisional_suppression(chart_label, calculated_charts)
    validate_node_corrections(chart_label, calculated_charts["d1"])
    validate_motion_fields(chart_label, primary_by_body)
    return warnings


def validate_d1(chart_label: str, primary_by_body: dict, d1: dict) -> None:
    for body in EXPECTED_PRIMARY_BODIES:
        assert body in d1, f"{chart_label} calculated_charts.d1 missing body: {body}"
        d1_entry = d1[body]
        primary_entry = primary_by_body[body]

        assert d1_entry["sign"] == primary_entry["sign"], (
            f"{chart_label} calculated_charts.d1 sign mismatch for {body}: "
            f"calculated={d1_entry['sign']} primary={primary_entry['sign']}"
        )
        assert d1_entry["degree_in_sign"] is not None, (
            f"{chart_label} calculated_charts.d1.{body} degree_in_sign expected"
        )
        assert d1_entry["absolute_degree"] is not None, (
            f"{chart_label} calculated_charts.d1.{body} absolute_degree expected"
        )
        assert d1_entry.get("degree_source") == "source_longitude", (
            f"{chart_label} calculated_charts.d1.{body} degree_source expected "
            f"source_longitude, got {d1_entry.get('degree_source')}"
        )


def validate_divisional_suppression(chart_label: str, calculated_charts: dict) -> None:
    for chart_name in NON_D1_CHARTS:
        divisional = calculated_charts[chart_name]
        for body in EXPECTED_PRIMARY_BODIES:
            assert body in divisional, (
                f"{chart_label} calculated_charts.{chart_name} missing body: {body}"
            )
            entry = divisional[body]
            assert "sign" in entry, (
                f"{chart_label} calculated_charts.{chart_name}.{body} missing sign"
            )
            assert entry["degree_in_sign"] is None, (
                f"{chart_label} calculated_charts.{chart_name}.{body} "
                "degree_in_sign expected null"
            )
            assert entry["absolute_degree"] is None, (
                f"{chart_label} calculated_charts.{chart_name}.{body} "
                "absolute_degree expected null"
            )
            assert entry.get("degree_status") == "not_jhora_verified", (
                f"{chart_label} calculated_charts.{chart_name}.{body} "
                "degree_status expected not_jhora_verified"
            )
            assert entry.get("degree_source") == "suppressed_projected_degree", (
                f"{chart_label} calculated_charts.{chart_name}.{body} "
                "degree_source expected suppressed_projected_degree"
            )


def validate_node_corrections(chart_label: str, d1: dict) -> None:
    for node in ("Rahu", "Ketu"):
        assert d1[node].get("node_source") == "swisseph_mean_node_corrected", (
            f"{chart_label} {node} node_source expected "
            f"swisseph_mean_node_corrected, got {d1[node].get('node_source')}"
        )


def validate_motion_fields(chart_label: str, primary_by_body: dict) -> None:
    for body, entry in primary_by_body.items():
        assert "retrograde" in entry, f"{chart_label} {body} missing retrograde"
        assert "motion_status" in entry, f"{chart_label} {body} missing motion_status"
        assert "direct" in entry, f"{chart_label} {body} missing direct"
        assert "stationary" in entry, f"{chart_label} {body} missing stationary"
        if body == "Lagna":
            assert entry["motion_status"] == "not_applicable", (
                f"{chart_label} Lagna motion_status expected not_applicable"
            )


def main() -> None:
    args = parse_args()
    had_warnings = False
    for path in chart_paths(args.paths):
        with path.open("r", encoding="utf-8") as input_file:
            try:
                warnings = validate_chart(
                    json.load(input_file),
                    path.stem,
                    strict=args.strict,
                )
            except AssertionError as error:
                print(error)
                raise SystemExit(1) from None
        for warning in warnings:
            had_warnings = True
            print(warning)
        print(f"Validation passed: {path}")

    if had_warnings and args.strict:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
