import contextlib
from datetime import datetime
import io
import json
from pathlib import Path
import re

import swisseph as swe

from parser_jhora import parse_jhora_txt


INPUT_DIR = Path("charts_in")
OUTPUT_JSON = Path("node_investigation.json")

JHORA_RAHU = 75.099789
JHORA_KETU = 255.099789


def quiet_imports():
    with contextlib.redirect_stdout(io.StringIO()):
        from jhora import const, utils
        from jhora.panchanga import drik

    return const, utils, drik


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


def parse_ayanamsa_degrees(ayanamsa_text):
    degrees, minutes, seconds = ayanamsa_text.split("-")
    return int(degrees) + int(minutes) / 60 + float(seconds) / 3600


def norm360(value):
    return value % 360


def signed_delta(value, reference):
    delta = (value - reference + 180) % 360 - 180
    return round(delta, 6)


def node_record(label, rahu, ketu, node_type, ayanamsa_application, jd_used, reference):
    return {
        "label": label,
        "node_type": node_type,
        "ayanamsa_application": ayanamsa_application,
        "jd_used": jd_used,
        "rahu": {
            "longitude": round(rahu, 6),
            "delta_from_jhora": signed_delta(rahu, reference["rahu"]),
        },
        "ketu": {
            "longitude": round(ketu, 6),
            "delta_from_jhora": signed_delta(ketu, reference["ketu"]),
        },
    }


def build_time_context(chart, utils):
    metadata = chart["metadata"]
    birth_date = datetime.strptime(metadata["date"], "%B %d, %Y")
    birth_time = datetime.strptime(metadata["time"], "%I:%M:%S %p")
    timezone = parse_timezone(metadata["time_zone"])
    date_tuple = (birth_date.year, birth_date.month, birth_date.day)
    time_tuple = (birth_time.hour, birth_time.minute, birth_time.second)
    jd_local = utils.julian_day_number(date_tuple, time_tuple)
    jd_utc = jd_local - timezone / 24.0

    return {
        "date_tuple": date_tuple,
        "time_tuple": time_tuple,
        "timezone": timezone,
        "jd_local": jd_local,
        "jd_utc": jd_utc,
        "ayanamsa_text": metadata["ayanamsa"],
        "ayanamsa_degrees": parse_ayanamsa_degrees(metadata["ayanamsa"]),
    }


def swisseph_node_records(time_context, reference):
    records = []
    ayanamsa = time_context["ayanamsa_degrees"]
    jd_local = time_context["jd_local"]
    jd_utc = time_context["jd_utc"]
    flags_tropical = swe.FLG_SWIEPH | swe.FLG_SPEED
    flags_sidereal = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    pyjhora_flags_tropical = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_TRUEPOS
    pyjhora_flags_sidereal = pyjhora_flags_tropical | swe.FLG_SIDEREAL

    swe.set_sid_mode(swe.SIDM_USER, jd_local, ayanamsa)

    for node_type, planet in (("mean", swe.MEAN_NODE), ("true", swe.TRUE_NODE)):
        sidereal_data, _ = swe.calc_ut(jd_utc, planet, flags_sidereal)
        tropical_data, _ = swe.calc_ut(jd_utc, planet, flags_tropical)
        pyjhora_sidereal_data, _ = swe.calc_ut(jd_utc, planet, pyjhora_flags_sidereal)
        pyjhora_tropical_data, _ = swe.calc_ut(jd_utc, planet, pyjhora_flags_tropical)

        sidereal_rahu = norm360(sidereal_data[0])
        manual_rahu = norm360(tropical_data[0] - ayanamsa)
        pyjhora_sidereal_rahu = norm360(pyjhora_sidereal_data[0])
        pyjhora_manual_rahu = norm360(pyjhora_tropical_data[0] - ayanamsa)

        records.append(node_record(
            f"swisseph_{node_type}_node_sidereal_flag",
            sidereal_rahu,
            norm360(sidereal_rahu + 180),
            node_type,
            "internal Swiss Ephemeris sidereal mode SIDM_USER",
            jd_utc,
            reference,
        ))
        records.append(node_record(
            f"swisseph_{node_type}_node_sidereal_flag_pyjhora_flags",
            pyjhora_sidereal_rahu,
            norm360(pyjhora_sidereal_rahu + 180),
            node_type,
            "internal Swiss Ephemeris SIDM_USER using PyJHora flags",
            jd_utc,
            reference,
        ))
        records.append(node_record(
            f"swisseph_{node_type}_node_manual_ayanamsa",
            manual_rahu,
            norm360(manual_rahu + 180),
            node_type,
            "manual tropical longitude minus JHora ayanamsa",
            jd_utc,
            reference,
        ))
        records.append(node_record(
            f"swisseph_{node_type}_node_manual_ayanamsa_pyjhora_flags",
            pyjhora_manual_rahu,
            norm360(pyjhora_manual_rahu + 180),
            node_type,
            "manual tropical longitude minus JHora ayanamsa using PyJHora flags",
            jd_utc,
            reference,
        ))

    return records


def pyjhora_node_records(time_context, reference, drik, const):
    records = []
    jd_utc = time_context["jd_utc"]
    ayanamsa = time_context["ayanamsa_degrees"]
    drik.set_ayanamsa_mode("SIDM_USER", ayanamsa, time_context["jd_local"])

    rahu = drik.sidereal_longitude(jd_utc, const._RAHU)
    ketu = drik.sidereal_longitude(jd_utc, const._KETU)
    records.append(node_record(
        "pyjhora_sidereal_longitude_const_rahu",
        rahu,
        ketu,
        "true",
        "internal PyJHora SIDM_USER; const._RAHU maps to Swiss TRUE_NODE",
        jd_utc,
        reference,
    ))

    for use_true_node, node_type in ((False, "mean"), (True, "true")):
        place = drik.Place(
            "node investigation",
            0.0,
            0.0,
            time_context["timezone"],
        )
        positions = drik.dhasavarga(
            time_context["jd_local"],
            place,
            divisional_chart_factor=1,
            set_rahu_ketu_as_true_nodes=use_true_node,
            include_western_planets=False,
        )
        node_positions = {planet_id: position for planet_id, position in positions}
        rahu_sign, rahu_degree = node_positions[const.RAHU_ID]
        ketu_sign, ketu_degree = node_positions[const.KETU_ID]
        records.append(node_record(
            f"pyjhora_dhasavarga_set_true_nodes_{use_true_node}",
            rahu_sign * 30 + rahu_degree,
            ketu_sign * 30 + ketu_degree,
            node_type,
            "internal PyJHora SIDM_USER; dhasavarga parameter tested",
            jd_utc,
            reference,
        ))

    return records


def time_sensitivity_records(time_context, reference):
    records = []
    ayanamsa = time_context["ayanamsa_degrees"]
    flags_sidereal = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    swe.set_sid_mode(swe.SIDM_USER, time_context["jd_local"], ayanamsa)

    for label, jd in (
        ("swisseph_true_node_using_local_jd_instead_of_utc", time_context["jd_local"]),
        ("swisseph_mean_node_using_local_jd_instead_of_utc", time_context["jd_local"]),
    ):
        planet = swe.TRUE_NODE if "true" in label else swe.MEAN_NODE
        data, _ = swe.calc_ut(jd, planet, flags_sidereal)
        rahu = norm360(data[0])
        records.append(node_record(
            label,
            rahu,
            norm360(rahu + 180),
            "true" if planet == swe.TRUE_NODE else "mean",
            "internal Swiss Ephemeris sidereal mode SIDM_USER; intentionally using local JD",
            jd,
            reference,
        ))

    return records


def main():
    input_file = find_input_file()
    text = input_file.read_text(encoding="utf-8", errors="replace")
    chart = parse_jhora_txt(text)
    const, utils, drik = quiet_imports()
    time_context = build_time_context(chart, utils)
    reference = {
        "rahu": JHORA_RAHU,
        "ketu": JHORA_KETU,
    }

    records = []
    records.extend(pyjhora_node_records(time_context, reference, drik, const))
    records.extend(swisseph_node_records(time_context, reference))
    records.extend(time_sensitivity_records(time_context, reference))

    closest = min(
        records,
        key=lambda record: abs(record["rahu"]["delta_from_jhora"]),
    )

    output = {
        "reference_jhora": reference,
        "time_context": time_context,
        "results": records,
        "closest_rahu_match": closest,
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_JSON}")
    print("JD local:", time_context["jd_local"])
    print("JD UTC:", time_context["jd_utc"])
    print("Timezone:", time_context["timezone"])
    print("Ayanamsa:", time_context["ayanamsa_text"], time_context["ayanamsa_degrees"])
    print()
    print("label | node_type | ayanamsa | jd_used | rahu | rahu_delta | ketu | ketu_delta")
    for record in records:
        print(
            f"{record['label']} | "
            f"{record['node_type']} | "
            f"{record['ayanamsa_application']} | "
            f"{record['jd_used']} | "
            f"{record['rahu']['longitude']} | "
            f"{record['rahu']['delta_from_jhora']} | "
            f"{record['ketu']['longitude']} | "
            f"{record['ketu']['delta_from_jhora']}"
        )

    print()
    print("Closest Rahu match:", closest["label"], closest["rahu"])


if __name__ == "__main__":
    main()
