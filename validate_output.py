import json
from pathlib import Path


CHART_PATHS = (
    Path("charts_out/Yashta/Yashta.json"),
    Path("charts_out/Yashta.json"),
)

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

def chart_path():
    for path in CHART_PATHS:
        if path.exists():
            return path
    raise AssertionError(
        "No generated chart JSON found at "
        f"{' or '.join(str(path) for path in CHART_PATHS)}"
    )


def assert_contains_keys(container, expected_keys, label):
    missing = expected_keys - set(container)
    assert not missing, f"{label} missing keys: {sorted(missing)}"


def main():
    with chart_path().open("r", encoding="utf-8") as input_file:
        chart = json.load(input_file)

    assert_contains_keys(chart, EXPECTED_TOP_LEVEL_KEYS, "top-level JSON")

    metadata = chart["metadata"]
    assert_contains_keys(metadata, EXPECTED_METADATA_KEYS, "metadata")
    assert_contains_keys(
        metadata["coordinates"],
        EXPECTED_COORDINATE_KEYS,
        "metadata.coordinates",
    )

    primary_positions = chart["primary_positions"]
    primary_by_body = {
        position["body"]: position
        for position in primary_positions
    }

    assert len(primary_positions) == 10, (
        f"primary_positions expected 10 entries, got {len(primary_positions)}"
    )
    assert list(primary_by_body) == EXPECTED_PRIMARY_BODIES, (
        "primary_positions bodies mismatch: "
        f"expected {EXPECTED_PRIMARY_BODIES}, got {list(primary_by_body)}"
    )

    calculated_charts = chart["calculated_charts"]
    assert_contains_keys(
        calculated_charts,
        EXPECTED_CALCULATED_CHARTS,
        "calculated_charts",
    )

    d1 = calculated_charts["d1"]
    for body in EXPECTED_PRIMARY_BODIES:
        assert body in d1, f"calculated_charts.d1 missing body: {body}"
        for chart_name in EXPECTED_CALCULATED_CHARTS:
            entry = calculated_charts[chart_name][body]
            assert "degree_in_sign" in entry, (
                f"calculated_charts.{chart_name}.{body} missing degree_in_sign"
            )
            assert "absolute_degree" in entry, (
                f"calculated_charts.{chart_name}.{body} missing absolute_degree"
            )
        assert d1[body]["sign"] == primary_by_body[body]["sign"], (
            f"calculated_charts.d1 sign mismatch for {body}: "
            f"calculated={d1[body]['sign']} "
            f"primary={primary_by_body[body]['sign']}"
        )

    d1_sun = d1["Sun"]
    assert d1_sun["degree_in_sign"] is not None, (
        "calculated_charts.d1.Sun degree_in_sign expected to exist"
    )
    assert d1_sun["absolute_degree"] is not None, (
        "calculated_charts.d1.Sun absolute_degree expected to exist"
    )
    assert d1_sun["degree_source"] == "source_longitude", (
        "calculated_charts.d1.Sun degree_source expected source_longitude, "
        f"got {d1_sun.get('degree_source')}"
    )

    d9 = calculated_charts["d9"]
    d9_sun = d9["Sun"]
    assert d9_sun["sign"] == "Ta", (
        f"calculated_charts.d9.Sun sign expected Ta, got {d9_sun['sign']}"
    )
    assert d9_sun["degree_in_sign"] is None, (
        "calculated_charts.d9.Sun degree_in_sign expected null"
    )
    assert d9_sun["absolute_degree"] is None, (
        "calculated_charts.d9.Sun absolute_degree expected null"
    )
    assert d9_sun["degree_status"] == "not_jhora_verified", (
        "calculated_charts.d9.Sun degree_status expected not_jhora_verified, "
        f"got {d9_sun.get('degree_status')}"
    )
    assert d9_sun["degree_source"] == "suppressed_projected_degree", (
        "calculated_charts.d9.Sun degree_source expected "
        "suppressed_projected_degree, "
        f"got {d9_sun.get('degree_source')}"
    )

    for node in ("Rahu", "Ketu"):
        assert d1[node].get("node_source") == "swisseph_mean_node_corrected", (
            f"{node} node_source expected swisseph_mean_node_corrected, "
            f"got {d1[node].get('node_source')}"
        )

    mercury = primary_by_body["Mercury"]
    assert mercury["retrograde"] is True, "Mercury retrograde expected true"
    assert mercury["motion_status"] == "retrograde", (
        "Mercury motion_status expected retrograde, "
        f"got {mercury['motion_status']}"
    )

    print("Validation passed")


if __name__ == "__main__":
    main()
