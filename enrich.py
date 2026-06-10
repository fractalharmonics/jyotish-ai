import contextlib
import importlib.util
from datetime import datetime
import io
import re

import swisseph as swe


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

SIGNS = ("Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi")
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
D10_CHART_METHOD = 1
D10_METHOD = "Traditional Parasara Dasamsa"
D10_METHOD_STATUS = "confirmed_pyjhora_chart_method_1"
D10_METHOD_NOTE = (
    "D10 calculated from source-aligned D1 longitudes with PyJHora "
    "jhora.horoscope.chart.charts.divisional_positions_from_rasi_positions("
    "divisional_chart_factor=10, chart_method=1); PyJHora documents "
    "dasamsa_chart chart_method=1 as Traditional Parasara."
)


def parse_birth_date(date_text):
    return datetime.strptime(date_text, "%B %d, %Y")


def parse_chart_time(time_text):
    normalized_time = " ".join(str(time_text).strip().split())
    formats = (
        "%I:%M:%S %p",
        "%I:%M %p",
        "%H:%M:%S",
        "%H:%M",
    )
    for time_format in formats:
        try:
            return datetime.strptime(normalized_time.upper(), time_format)
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format: {time_text}")


def parse_birth_time(time_text):
    return parse_chart_time(time_text)


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


def parse_ayanamsa_degrees(ayanamsa_text):
    degrees, minutes, seconds = ayanamsa_text.split("-")
    return int(degrees) + int(minutes) / 60 + float(seconds) / 3600


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
    coordinates = metadata.get("coordinates")

    if coordinates:
        place_data = {
            "name": place_name,
            "latitude": coordinates["latitude_decimal"],
            "longitude": coordinates["longitude_decimal"],
            "timezone": timezone,
            "elevation": None,
        }

    if place_data is None:
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


def chart_entry(body, sign_index, degree_in_sign, source, factor, node_source=None):
    sign_index = int(sign_index)
    entry = {
        "body": body,
        "sign": INDEX_TO_SIGN[sign_index],
        "sign_index": sign_index,
        "source": source,
    }
    if factor == 1:
        degree_in_sign = round(float(degree_in_sign), 6)
        entry.update({
            "degree_in_sign": degree_in_sign,
            "absolute_degree": round(sign_index * 30 + degree_in_sign, 6),
            "degree_source": "source_longitude",
        })
    else:
        entry.update({
            "degree_in_sign": None,
            "absolute_degree": None,
            "degree_status": "not_jhora_verified",
            "degree_source": "suppressed_projected_degree",
        })
    if node_source:
        entry["node_source"] = node_source
    return entry


def corrected_mean_node_longitudes(jd, place, ayanamsa_value):
    jd_utc = jd - place.timezone / 24.0
    swe.set_sid_mode(swe.SIDM_USER, jd, ayanamsa_value)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    rahu_data, _ = swe.calc_ut(jd_utc, swe.MEAN_NODE, flags)
    rahu = rahu_data[0] % 360
    return {
        "Rahu": rahu,
        "Ketu": (rahu + 180) % 360,
    }


def varga_sign_from_source_longitude(
    source_absolute_degree,
    factor,
    drik,
    charts_module=None,
):
    if factor == 10 and charts_module is not None:
        source_sign = int(source_absolute_degree // 30) % 12
        source_degree = source_absolute_degree % 30
        positions = charts_module.divisional_positions_from_rasi_positions(
            [["X", [source_sign, source_degree]]],
            divisional_chart_factor=10,
            chart_method=D10_CHART_METHOD,
        )
        return positions[0][1][0]

    sign_index, _ = drik.dasavarga_from_long(
        source_absolute_degree,
        divisional_chart_factor=factor,
    )
    return sign_index


def add_corrected_nodes(
    calculated_chart,
    factor,
    node_longitudes,
    drik,
    charts_module=None,
):
    for body in ("Rahu", "Ketu"):
        source_absolute_degree = node_longitudes[body]
        sign_index = varga_sign_from_source_longitude(
            source_absolute_degree,
            factor,
            drik,
            charts_module,
        )
        degree_in_sign = source_absolute_degree % 30 if factor == 1 else None
        calculated_chart[body] = chart_entry(
            body,
            sign_index,
            degree_in_sign,
            "pyjhora_calculated",
            factor,
            node_source="swisseph_mean_node_corrected",
        )


def add_calculated_lagna(
    calculated_chart,
    jd,
    place,
    factor,
    drik,
    source_absolute_degree=None,
    charts_module=None,
):
    sign_index, degree_in_sign = drik.ascendant(jd, place)[:2]
    if source_absolute_degree is None:
        source_absolute_degree = sign_index * 30 + degree_in_sign
    lagna_sign_index = varga_sign_from_source_longitude(
        source_absolute_degree,
        factor,
        drik,
        charts_module,
    )
    lagna_degree = source_absolute_degree % 30 if factor == 1 else None
    calculated_chart["Lagna"] = chart_entry(
        "Lagna",
        lagna_sign_index,
        lagna_degree,
        "pyjhora_calculated",
        factor,
    )


def source_longitudes_from_positions(raw_positions):
    return {
        planet_id: sign_index * 30 + degree_in_sign
        for planet_id, (sign_index, degree_in_sign) in raw_positions
    }


def source_longitudes_from_chart(chart, fallback_positions):
    source_longitudes = source_longitudes_from_positions(fallback_positions)
    for position in chart.get("primary_positions", []):
        body = position["body"]
        planet_id = BODY_TO_PYJHORA_ID.get(body)
        if planet_id is not None:
            source_longitudes[planet_id] = position["absolute_degree"]

    return source_longitudes


def raw_positions_for_factor(
    jd,
    place,
    factor,
    drik,
    charts_module,
    source_longitudes=None,
):
    if factor == 10:
        rasi_positions = [
            [planet_id, [int(source_longitude // 30) % 12, source_longitude % 30]]
            for planet_id, source_longitude in (source_longitudes or {}).items()
            if planet_id != "L"
        ]
        return charts_module.divisional_positions_from_rasi_positions(
            rasi_positions,
            divisional_chart_factor=10,
            chart_method=D10_CHART_METHOD,
        )

    return drik.dhasavarga(
        jd,
        place,
        divisional_chart_factor=factor,
        set_rahu_ketu_as_true_nodes=False,
        include_western_planets=False,
    )


def calculated_chart_from_positions(raw_positions, source_longitudes, factor):
    calculated_chart = {}
    for planet_id, position in raw_positions:
        body = PYJHORA_ID_TO_BODY.get(planet_id)
        if body is None or body in {"Rahu", "Ketu"}:
            continue

        sign_index, _ = position
        source_absolute_degree = source_longitudes[planet_id]
        degree_in_sign = source_absolute_degree % 30 if factor == 1 else None
        calculated_chart[body] = chart_entry(
            body,
            sign_index,
            degree_in_sign,
            "pyjhora_calculated",
            factor,
        )

    return calculated_chart


def annotate_chart_method(label, calculated_chart):
    if label != "d10":
        return

    for entry in calculated_chart.values():
        entry["method"] = D10_METHOD
        entry["method_status"] = D10_METHOD_STATUS


def apply_calculated_charts(chart, notes):
    with contextlib.redirect_stdout(io.StringIO()):
        from jhora.panchanga import drik
        from jhora.horoscope.chart import charts

    jd, place = build_jd_and_place(chart["metadata"], notes)
    ayanamsa_value = parse_ayanamsa_degrees(chart["metadata"]["ayanamsa"])
    drik.set_ayanamsa_mode("SIDM_USER", ayanamsa_value, jd)
    node_longitudes = corrected_mean_node_longitudes(jd, place, ayanamsa_value)
    d1_positions = drik.dhasavarga(
        jd,
        place,
        divisional_chart_factor=1,
        set_rahu_ketu_as_true_nodes=False,
        include_western_planets=False,
    )
    source_longitudes = source_longitudes_from_chart(chart, d1_positions)
    source_longitudes[BODY_TO_PYJHORA_ID["Rahu"]] = node_longitudes["Rahu"]
    source_longitudes[BODY_TO_PYJHORA_ID["Ketu"]] = node_longitudes["Ketu"]

    calculated_charts = {}
    for label, factor in DIVISIONAL_FACTORS.items():
        try:
            raw_positions = raw_positions_for_factor(
                jd,
                place,
                factor,
                drik,
                charts,
                source_longitudes=source_longitudes,
            )
            calculated_chart = calculated_chart_from_positions(
                raw_positions,
                source_longitudes,
                factor,
            )
            add_calculated_lagna(
                calculated_chart,
                jd,
                place,
                factor,
                drik,
                source_absolute_degree=source_longitudes.get("L"),
                charts_module=charts,
            )
            add_corrected_nodes(
                calculated_chart,
                factor,
                node_longitudes,
                drik,
                charts_module=charts,
            )
            annotate_chart_method(label, calculated_chart)
            calculated_charts[label] = calculated_chart
        except Exception as error:
            notes.append(f"Calculated chart {label} failed: {error}")

    if calculated_charts:
        chart["calculated_charts"] = calculated_charts
        notes.append("Calculated divisional charts added")
        notes.append("Rahu/Ketu nodes corrected with swisseph MEAN_NODE")
        notes.append(
            "Non-D1 varga degree fields suppressed pending "
            "JHora-equivalent validation."
        )
        if "d10" in calculated_charts:
            notes.append(D10_METHOD_NOTE)


def enrich_chart(chart):
    # Future PyJHora-derived calculations should be added here.
    # For now, only record whether PyJHora can be imported.
    notes = []
    module_file = None
    module_package = None
    chart.setdefault("calculated_charts", {})

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
        try:
            apply_calculated_charts(chart, notes)
        except Exception as error:
            notes.append(f"Calculated charts enrichment failed: {error}")

    if not chart.get("calculated_charts"):
        chart["calculated_charts"] = {}

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
        "calculated_charts": (
            "D1 degrees are source-aligned. D9/D10/D20 signs are calculated, "
            "but degrees are suppressed because the source JHora TXT does not "
            "export full varga degrees and projected degrees have not been "
            "verified against JHora display conventions."
        ),
    }

    return chart
