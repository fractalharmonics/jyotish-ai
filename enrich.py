import contextlib
import importlib.util
from datetime import datetime
import io
import re


PYJHORA_SPEC = importlib.util.find_spec("jhora")
PYJHORA_MODULE = None
PYJHORA_IMPORT_ERROR = None

try:
    import jhora as PYJHORA_MODULE
except Exception as error:
    PYJHORA_IMPORT_ERROR = error


PLANET_IDS = {
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

def parse_birth_date(date_text):
    return datetime.strptime(date_text, "%B %d, %Y")


def parse_birth_time(time_text):
    return datetime.strptime(time_text, "%I:%M:%S %p")


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
    if match.group("direction") == "West":
        offset *= -1

    return offset


def build_jd_and_place(metadata, notes):
    with contextlib.redirect_stdout(io.StringIO()):
        from jhora import utils
        from jhora.panchanga import drik

    birth_date = parse_birth_date(metadata["date"])
    birth_time = parse_birth_time(metadata["time"])
    timezone = parse_timezone(metadata["time_zone"])

    jd = utils.julian_day_number(
        (birth_date.year, birth_date.month, birth_date.day),
        (birth_time.hour, birth_time.minute, birth_time.second),
    )

    place_name = metadata["place"]
    place_data = None

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            resolved_place = utils.get_place(place_name)
    except Exception as error:
        notes.append(f"PyJHora place lookup failed: {error}")
    else:
        if resolved_place:
            place_data = {
                "name": resolved_place[0],
                "latitude": resolved_place[1],
                "longitude": resolved_place[2],
                "timezone": resolved_place[3],
                "elevation": resolved_place[4] if len(resolved_place) > 4 else None,
            }

    if place_data is None:
        raise ValueError(f"Could not resolve coordinates for place: {place_name}")

    place = drik.Place(
        place_data["name"],
        place_data["latitude"],
        place_data["longitude"],
        timezone,
        place_data.get("elevation"),
    )

    return jd, place


def apply_motion_enrichment(chart, notes):
    with contextlib.redirect_stdout(io.StringIO()):
        from jhora import const
        from jhora.panchanga import drik

    jd, place = build_jd_and_place(chart["metadata"], notes)
    speed_info = drik.planets_speed_info(jd, place)
    retrograde_ids = set(drik.planets_in_retrograde(jd, place))

    original_true_node_setting = const._use_true_nodes_for_rahu_ketu
    try:
        stationary_ids = set(drik.planets_in_stationary(jd, place))
    except Exception as error:
        notes.append(f"PyJHora stationary detection failed: {error}")
        notes.append(
            "Retrying stationary detection with "
            "const._use_true_nodes_for_rahu_ketu = False"
        )
        const._use_true_nodes_for_rahu_ketu = False
        stationary_ids = set(drik.planets_in_stationary(jd, place))
    finally:
        const._use_true_nodes_for_rahu_ketu = original_true_node_setting

    enriched_primary_positions = []
    for position in chart["primary_positions"]:
        enriched_position = dict(position)
        body = enriched_position["body"]

        if body == "Lagna":
            enriched_position.update({
                "speed": None,
                "retrograde": False,
                "stationary": None,
                "direct": None,
                "motion_status": "not_applicable",
            })
            enriched_primary_positions.append(enriched_position)
            continue

        planet_id = PLANET_IDS.get(body)
        if planet_id is None or planet_id not in speed_info:
            enriched_position["motion_status"] = "unknown"
            enriched_primary_positions.append(enriched_position)
            continue

        speed = speed_info[planet_id][3]
        stationary = planet_id in stationary_ids
        retrograde = planet_id in retrograde_ids
        direct = not stationary and not retrograde

        if stationary:
            motion_status = "stationary"
        elif retrograde:
            motion_status = "retrograde"
        elif direct:
            motion_status = "direct"
        else:
            motion_status = "unknown"

        enriched_position.update({
            "speed": speed,
            "retrograde": retrograde,
            "stationary": stationary,
            "direct": direct,
            "motion_status": motion_status,
        })
        enriched_primary_positions.append(enriched_position)

    chart["primary_positions"] = enriched_primary_positions
    notes.append("PyJHora motion enrichment completed successfully")


def enrich_chart(chart):
    # Future PyJHora-derived calculations should be added here.
    # For now, only record whether PyJHora can be imported.
    notes = []
    module_file = None
    module_package = None

    if PYJHORA_SPEC:
        module_file = PYJHORA_SPEC.origin
        module_package = PYJHORA_SPEC.parent

    if PYJHORA_IMPORT_ERROR:
        pyjhora_available = False
        notes.append(str(PYJHORA_IMPORT_ERROR))
    else:
        pyjhora_available = True
        notes.append("PyJHora imported successfully")
        module_file = getattr(PYJHORA_MODULE, "__file__", None)
        module_package = getattr(PYJHORA_MODULE, "__package__", None)
        try:
            apply_motion_enrichment(chart, notes)
        except Exception as error:
            notes.append(f"PyJHora motion enrichment failed: {error}")

    notes.append({
        "module_file": module_file,
        "module_package": module_package,
    })

    chart["enrichment"] = {
        "pyjhora_available": pyjhora_available,
        "notes": notes,
    }
    chart["data_notes"] = {
        "positions": "Raw parsed JHora position table. Not enriched.",
        "primary_positions": (
            "Primary chart bodies with enrichment applied where available."
        ),
        "enrichment": (
            "Computed fields added by local deterministic Python/PyJHora layer."
        ),
    }

    return chart
