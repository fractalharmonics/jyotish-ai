import contextlib
from datetime import datetime
import io
import json
from pathlib import Path
import re

import swisseph as swe

from enrich import (
    BODY_TO_PYJHORA_ID,
    build_jd_and_place,
    corrected_mean_node_longitudes,
    parse_ayanamsa_degrees,
)
from parser_jhora import parse_jhora_txt


INPUT_DIR = Path("charts_in")
OUTPUT_JSON = Path("d9_offset_investigation.json")

BODIES = [
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

SWISSEPH_PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
    "Ketu": swe.MEAN_NODE,
}

JHORA_D9_REFERENCE = {
    "Lagna": 25.871117,
    "Sun": 7.904611,
    "Moon": 27.429125,
    "Mars": 7.883386,
    "Mercury": 25.196347,
    "Jupiter": 12.390703,
    "Venus": 19.385972,
    "Saturn": 25.127481,
    "Rahu": 16.037511,
    "Ketu": 16.037511,
}


def quiet_imports():
    with contextlib.redirect_stdout(io.StringIO()):
        from jhora import utils
        from jhora.panchanga import drik
        from jhora.horoscope.chart import charts

    return utils, drik, charts


def find_input_file():
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


def parse_birth_context(metadata, utils):
    birth_date = datetime.strptime(metadata["date"], "%B %d, %Y")
    birth_time = datetime.strptime(metadata["time"], "%I:%M:%S %p")
    timezone = parse_timezone(metadata["time_zone"])
    date_tuple = (birth_date.year, birth_date.month, birth_date.day)
    time_tuple = (birth_time.hour, birth_time.minute, birth_time.second)
    jd_local = utils.julian_day_number(date_tuple, time_tuple)
    jd_utc = jd_local - timezone / 24.0
    ayanamsa = parse_ayanamsa_degrees(metadata["ayanamsa"])
    return {
        "date_tuple": date_tuple,
        "time_tuple": time_tuple,
        "timezone": timezone,
        "jd_local": jd_local,
        "jd_utc": jd_utc,
        "ayanamsa": ayanamsa,
    }


def navamsa_degree(source_absolute_degree):
    source_degree_in_sign = source_absolute_degree % 30
    navamsa_size = 30 / 9
    navamsa_fraction = (source_degree_in_sign % navamsa_size) / navamsa_size
    return navamsa_fraction * 30


def signed_delta(value, reference):
    return round(value - reference, 6)


def parsed_d1_longitudes(chart):
    return {
        position["body"]: position["absolute_degree"]
        for position in chart["primary_positions"]
        if position["body"] in BODIES
    }


def pyjhora_d1_longitudes(jd, place, drik, charts):
    rasi = charts.rasi_chart(jd, place)
    output = {}
    for planet_id, (sign_index, degree_in_sign) in rasi:
        body = "Lagna" if planet_id == "L" else next(
            key for key, value in BODY_TO_PYJHORA_ID.items()
            if value == planet_id
        )
        if body in BODIES:
            output[body] = sign_index * 30 + degree_in_sign
    return output


def direct_swisseph_longitudes(context, place, drik, flags, label):
    swe.set_sid_mode(swe.SIDM_USER, context["jd_local"], context["ayanamsa"])
    output = {}
    for body in BODIES:
        if body == "Lagna":
            ascendant = drik.ascendant(context["jd_local"], place)
            output[body] = ascendant[0] * 30 + ascendant[1]
            continue

        planet = SWISSEPH_PLANETS[body]
        data, _ = swe.calc_ut(context["jd_utc"], planet, flags)
        longitude = data[0] % 360
        if body == "Ketu":
            longitude = (longitude + 180) % 360
        output[body] = longitude
    return label, output


def current_calculated_input_longitudes(chart):
    output = {}
    d1 = chart["calculated_charts"]["d1"]
    for body in BODIES:
        output[body] = d1[body]["absolute_degree"]
    return output


def source_report(label, longitudes):
    rows = {}
    deltas = []
    for body in BODIES:
        longitude = longitudes[body]
        d9_degree = navamsa_degree(longitude)
        delta = signed_delta(d9_degree, JHORA_D9_REFERENCE[body])
        deltas.append(delta)
        rows[body] = {
            "source_absolute_degree": round(longitude, 6),
            "source_degree_in_sign": round(longitude % 30, 6),
            "projected_d9_degree": round(d9_degree, 6),
            "jhora_d9_reference": JHORA_D9_REFERENCE[body],
            "delta": delta,
        }

    planet_deltas = [rows[body]["delta"] for body in BODIES if body != "Lagna"]
    return {
        "label": label,
        "rows": rows,
        "summary": {
            "min_delta": min(deltas),
            "max_delta": max(deltas),
            "mean_planet_delta": round(sum(planet_deltas) / len(planet_deltas), 6),
            "range_planet_delta": round(max(planet_deltas) - min(planet_deltas), 6),
        },
    }


def main():
    utils, drik, charts = quiet_imports()
    input_file = find_input_file()
    text = input_file.read_text(encoding="utf-8", errors="replace")
    parsed_chart = parse_jhora_txt(text)
    context = parse_birth_context(parsed_chart["metadata"], utils)
    notes = []
    jd, place = build_jd_and_place(parsed_chart["metadata"], notes)
    drik.set_ayanamsa_mode("SIDM_USER", context["ayanamsa"], context["jd_local"])

    chart_json = json.load(open("charts_out/Yashta.json", encoding="utf-8"))

    base_flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    pyjhora_flags = base_flags | swe.FLG_TRUEPOS | swe.FLG_NOGDEFL | swe.FLG_NONUT
    apparent_no_aberration_flags = base_flags | swe.FLG_NOABERR

    sources = [
        source_report("parsed_jhora_d1_absolute_degree", parsed_d1_longitudes(parsed_chart)),
        source_report("pyjhora_rasi_chart_d1_absolute_degree", pyjhora_d1_longitudes(jd, place, drik, charts)),
        source_report("current_calculated_charts_d1_absolute_degree", current_calculated_input_longitudes(chart_json)),
    ]

    for label, longitudes in (
        direct_swisseph_longitudes(context, place, drik, base_flags, "direct_swisseph_sidereal_apparent"),
        direct_swisseph_longitudes(context, place, drik, pyjhora_flags, "direct_swisseph_sidereal_pyjhora_flags"),
        direct_swisseph_longitudes(context, place, drik, apparent_no_aberration_flags, "direct_swisseph_sidereal_no_aberration"),
    ):
        sources.append(source_report(label, longitudes))

    output = {
        "context": context,
        "jhora_d9_reference": JHORA_D9_REFERENCE,
        "sources": sources,
        "findings": {
            "formula": (
                "navamsa_fraction = (source_degree_in_sign % (30/9)) / (30/9); "
                "d9_degree_in_sign = navamsa_fraction * 30"
            ),
            "observed": (
                "Using parsed JHora D1 and corrected mean nodes removes the D1-degree reuse bug, "
                "but the supplied D9 references remain about 0.14 degrees ahead for planets/nodes."
            ),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_JSON}")
    for source in sources:
        summary = source["summary"]
        print(
            source["label"],
            "mean_planet_delta=",
            summary["mean_planet_delta"],
            "range_planet_delta=",
            summary["range_planet_delta"],
        )
        for body in BODIES:
            row = source["rows"][body]
            print(
                f"  {body}: src={row['source_absolute_degree']} "
                f"d9={row['projected_d9_degree']} "
                f"ref={row['jhora_d9_reference']} "
                f"delta={row['delta']}"
            )


if __name__ == "__main__":
    main()
