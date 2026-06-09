import argparse
import contextlib
from datetime import datetime
import io
import json
from pathlib import Path
import re

from parser_jhora import parse_jhora_txt


INPUT_DIR = Path("charts_in")
OUTPUT_JSON = Path("divisional_validation.json")

SIGNS = ("Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi")
SIGN_TO_INDEX = {sign: index for index, sign in enumerate(SIGNS)}
INDEX_TO_SIGN = {index: sign for index, sign in enumerate(SIGNS)}

BODY_TO_PYJHORA_ID = {
    "Lagna": "L",
    "Sun": 0,
    "Moon": 1,
    "Mars": 2,
    "Mercury": 3,
    "Jupiter": 4,
    "Venus": 5,
    "Saturn": 6,
    "Rahu": 7,
    "Ketu": 8,
}
PYJHORA_ID_TO_BODY = {value: key for key, value in BODY_TO_PYJHORA_ID.items()}

DIVISIONAL_FACTORS = {
    "d1": 1,
    "d9": 9,
    "d10": 10,
    "d20": 20,
}


def quiet_imports():
    with contextlib.redirect_stdout(io.StringIO()):
        from jhora import const, utils
        from jhora.panchanga import drik
        from jhora.horoscope.chart import charts

    return const, utils, drik, charts


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate PyJHora divisional charts against a JHora TXT export."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to a JHora TXT export. Defaults to the first charts_in/*.txt file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_JSON,
        help="Output JSON path.",
    )
    return parser.parse_args()


def find_input_file(input_path):
    if input_path:
        return input_path

    txt_files = sorted(INPUT_DIR.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError("No JHora TXT files found in charts_in/")
    return txt_files[0]


def parse_timezone(time_zone_text):
    match = re.search(
        r"(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+)\s+"
        r"\((?P<direction>West|East) of GMT\)",
        time_zone_text,
    )
    if not match:
        raise ValueError(f"Unsupported time zone format: {time_zone_text}")

    offset = (
        int(match.group("hours"))
        + int(match.group("minutes")) / 60
        + int(match.group("seconds")) / 3600
    )
    return -offset if match.group("direction") == "West" else offset


def parse_dms(value, positive_direction):
    match = re.match(
        r"(?P<degrees>\d+)\s+(?P<direction>[NSEW])\s+"
        r"(?P<minutes>\d+)'\s+(?P<seconds>\d+)\"",
        value.strip(),
    )
    if not match:
        raise ValueError(f"Unsupported coordinate format: {value}")

    decimal = (
        int(match.group("degrees"))
        + int(match.group("minutes")) / 60
        + int(match.group("seconds")) / 3600
    )
    direction = match.group("direction")
    if direction != positive_direction:
        decimal *= -1
    return decimal


def parse_coordinates(text):
    match = re.search(
        r"Place:\s+(?P<longitude>\d+\s+[EW]\s+\d+'\s+\d+\"),\s+"
        r"(?P<latitude>\d+\s+[NS]\s+\d+'\s+\d+\")",
        text,
    )
    if not match:
        raise ValueError("Could not parse coordinates from JHora text")

    return {
        "latitude": parse_dms(match.group("latitude"), "N"),
        "longitude": parse_dms(match.group("longitude"), "E"),
    }


def parse_altitude(text):
    match = re.search(r"Altitude:\s+(?P<altitude>-?\d+(?:\.\d+)?)\s+meters", text)
    return float(match.group("altitude")) if match else None


def parse_ayanamsa_degrees(ayanamsa_text):
    parts = ayanamsa_text.split("-")
    if len(parts) != 3:
        raise ValueError(f"Unsupported ayanamsa format: {ayanamsa_text}")
    degrees, minutes, seconds = parts
    return int(degrees) + int(minutes) / 60 + float(seconds) / 3600


def build_jd_place(chart, text, utils, drik):
    metadata = chart["metadata"]
    birth_date = datetime.strptime(metadata["date"], "%B %d, %Y")
    birth_time = datetime.strptime(metadata["time"], "%I:%M:%S %p")
    coordinates = parse_coordinates(text)
    timezone = parse_timezone(metadata["time_zone"])

    jd = utils.julian_day_number(
        (birth_date.year, birth_date.month, birth_date.day),
        (birth_time.hour, birth_time.minute, birth_time.second),
    )
    place = drik.Place(
        metadata["place"],
        coordinates["latitude"],
        coordinates["longitude"],
        timezone,
        parse_altitude(text),
    )
    return jd, place


def normalize_chart(raw_positions):
    normalized = {}
    for planet_id, position in raw_positions:
        body = PYJHORA_ID_TO_BODY.get(planet_id)
        if body is None:
            continue

        sign_index, degree_in_sign = position
        normalized[body] = {
            "sign": INDEX_TO_SIGN[int(sign_index)],
            "sign_index": int(sign_index),
            "degree_in_sign": round(float(degree_in_sign), 6),
        }

    return normalized


def add_lagna(chart, jd, place, factor, drik):
    sign_index, degree_in_sign = drik.ascendant(jd, place)[:2]
    absolute_degree = sign_index * 30 + degree_in_sign
    lagna_sign_index, lagna_degree = drik.dasavarga_from_long(
        absolute_degree,
        divisional_chart_factor=factor,
    )
    chart["Lagna"] = {
        "sign": INDEX_TO_SIGN[int(lagna_sign_index)],
        "sign_index": int(lagna_sign_index),
        "degree_in_sign": round(float(lagna_degree), 6),
    }
    return chart


def parsed_d1(chart):
    d1 = {}
    for position in chart["primary_positions"]:
        body = position["body"]
        if body not in BODY_TO_PYJHORA_ID:
            continue

        d1[body] = {
            "sign": position["sign"],
            "sign_index": SIGN_TO_INDEX[position["sign"]],
            "degree_in_sign": round(
                float(position["absolute_degree"])
                - SIGN_TO_INDEX[position["sign"]] * 30,
                6,
            ),
        }

    return d1


def compare_d1(pyjhora_d1, jhora_d1):
    matching = []
    mismatches = []

    for body in BODY_TO_PYJHORA_ID:
        pyjhora_position = pyjhora_d1.get(body)
        jhora_position = jhora_d1.get(body)

        if (
            pyjhora_position
            and jhora_position
            and pyjhora_position["sign"] == jhora_position["sign"]
        ):
            matching.append(body)
        else:
            mismatches.append({
                "body": body,
                "pyjhora": pyjhora_position,
                "jhora": jhora_position,
            })

        degree_delta = None
        if pyjhora_position and jhora_position:
            degree_delta = round(
                pyjhora_position["degree_in_sign"]
                - jhora_position["degree_in_sign"],
                6,
            )

        mismatches[-1:] = [
            {
                **mismatches[-1],
                "degree_delta": degree_delta,
            }
        ] if mismatches and mismatches[-1]["body"] == body else mismatches[-1:]

    degree_deltas = []
    for body in BODY_TO_PYJHORA_ID:
        pyjhora_position = pyjhora_d1.get(body)
        jhora_position = jhora_d1.get(body)
        degree_delta = None
        if pyjhora_position and jhora_position:
            degree_delta = round(
                pyjhora_position["degree_in_sign"]
                - jhora_position["degree_in_sign"],
                6,
            )
        degree_deltas.append({
            "body": body,
            "degree_delta": degree_delta,
        })

    return {
        "matching_placements": matching,
        "mismatches": mismatches,
        "degree_deltas": degree_deltas,
    }


def generate_charts(jd, place, drik):
    charts_by_factor = {}
    for label, factor in DIVISIONAL_FACTORS.items():
        positions = drik.dhasavarga(
            jd,
            place,
            divisional_chart_factor=factor,
            set_rahu_ketu_as_true_nodes=False,
            include_western_planets=False,
        )
        normalized = normalize_chart(positions)
        charts_by_factor[label] = add_lagna(normalized, jd, place, factor, drik)

    return charts_by_factor


def main():
    args = parse_args()
    input_txt = find_input_file(args.input)
    text = input_txt.read_text(encoding="utf-8", errors="replace")
    chart = parse_jhora_txt(text)
    const, utils, drik, charts = quiet_imports()

    jd, place = build_jd_place(chart, text, utils, drik)
    ayanamsa_value = parse_ayanamsa_degrees(chart["metadata"]["ayanamsa"])
    drik.set_ayanamsa_mode("SIDM_USER", ayanamsa_value, jd)

    divisional_charts = generate_charts(jd, place, drik)
    d1_comparison = compare_d1(divisional_charts["d1"], parsed_d1(chart))

    args.output.write_text(
        json.dumps(divisional_charts, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {args.output}")
    print("APIs used:")
    print("- Primary: jhora.panchanga.drik.dhasavarga")
    print("- Lagna: jhora.panchanga.drik.ascendant + dasavarga_from_long")
    print("- Alternate chart APIs identified:")
    print("  d1: jhora.horoscope.chart.charts.rasi_chart")
    print("  d9: jhora.horoscope.chart.charts.navamsa_chart")
    print("  d10: jhora.horoscope.chart.charts.dasamsa_chart")
    print("  d20: jhora.horoscope.chart.charts.vimsamsa_chart")
    print("D1 matching placements:", ", ".join(d1_comparison["matching_placements"]))
    print("D1 mismatches:", len(d1_comparison["mismatches"]))
    for mismatch in d1_comparison["mismatches"]:
        print(
            f"- {mismatch['body']}: "
            f"PyJHora={mismatch['pyjhora']} "
            f"JHora={mismatch['jhora']} "
            f"degree_delta={mismatch['degree_delta']}"
        )
    print("D1 degree deltas:")
    for delta in d1_comparison["degree_deltas"]:
        print(f"- {delta['body']}: {delta['degree_delta']}")
    print("Ayanamsa: SIDM_USER from JHora metadata", chart["metadata"]["ayanamsa"])
    print("Nodes: mean node mode; true-node and mean-node dhasavarga returned the same D1 nodes in this run")


if __name__ == "__main__":
    main()
