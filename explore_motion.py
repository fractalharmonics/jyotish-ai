import argparse
import contextlib
import importlib
import inspect
import io
import json


INVENTORY_FILE = "pyjhora_inventory.json"

PLANET_NAMES = {
    0: "Sun",
    1: "Moon",
    2: "Mars",
    3: "Mercury",
    4: "Jupiter",
    5: "Venus",
    6: "Saturn",
    7: "Rahu",
    8: "Ketu",
}


def quiet_import(module_name):
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        module = importlib.import_module(module_name)
    return module, captured.getvalue().strip()


def print_candidate_functions(inventory):
    wanted = (
        "jhora.panchanga.drik.sidereal_longitude",
        "jhora.panchanga.drik.planetary_positions",
        "jhora.panchanga.drik.planets_speed_info",
        "jhora.panchanga.drik.planets_in_retrograde",
        "jhora.panchanga.drik.planets_in_stationary",
        "jhora.panchanga.drik.ascendant",
    )

    motion_candidates = inventory["candidate_functions"]["planetary_motion"]
    candidates = [name for name in wanted if name in motion_candidates]

    print("Candidate functions from pyjhora_inventory.json:")
    for name in candidates:
        print(f"- {name}")

    return candidates


def print_signatures(drik, utils):
    functions = (
        drik.sidereal_longitude,
        drik.planetary_positions,
        drik.planets_speed_info,
        drik.planets_in_retrograde,
        drik.planets_in_stationary,
        drik.ascendant,
        utils.julian_day_number,
    )

    print("\nSignatures:")
    for function in functions:
        print(
            f"- {function.__module__}.{function.__name__}"
            f"{inspect.signature(function)}"
        )


def parser_longitudes_by_planet(chart_json):
    if not chart_json:
        return {}

    with open(chart_json, "r", encoding="utf-8") as input_file:
        chart = json.load(input_file)

    return {
        position["body"]: position["absolute_degree"]
        for position in chart["positions"]
        if position["body"] in PLANET_NAMES.values()
    }


def motion_status(planet_id, retrograde_ids, stationary_ids):
    stationary = planet_id in stationary_ids
    retrograde = planet_id in retrograde_ids
    direct = not stationary and not retrograde

    if stationary:
        status = "stationary"
    elif retrograde:
        status = "retrograde"
    else:
        status = "direct"

    return {
        "retrograde": retrograde,
        "direct": direct,
        "stationary": stationary,
        "motion_status": status,
    }


def build_parser():
    parser = argparse.ArgumentParser(
        description="Explore PyJHora planetary motion APIs."
    )
    parser.add_argument("--inventory", default=INVENTORY_FILE)
    parser.add_argument("--chart-json")
    parser.add_argument("--date", help="Birth date as YYYY-MM-DD.")
    parser.add_argument("--time", help="Birth time as HH:MM:SS, 24-hour.")
    parser.add_argument("--place-name", default="Example Place")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--timezone", type=float)
    parser.add_argument("--elevation", type=float, default=0.0)
    return parser


def parse_date(date_text):
    year, month, day = date_text.split("-")
    return int(year), int(month), int(day)


def parse_time(time_text):
    hour, minute, second = time_text.split(":")
    return int(hour), int(minute), int(second)


def has_execution_args(args):
    return all(
        value is not None
        for value in (
            args.date,
            args.time,
            args.latitude,
            args.longitude,
            args.timezone,
        )
    )


def main():
    args = build_parser().parse_args()

    with open(args.inventory, "r", encoding="utf-8") as input_file:
        inventory = json.load(input_file)

    print_candidate_functions(inventory)

    drik, drik_stdout = quiet_import("jhora.panchanga.drik")
    utils, utils_stdout = quiet_import("jhora.utils")
    const, const_stdout = quiet_import("jhora.const")

    import_noise = "\n".join(
        text for text in (drik_stdout, utils_stdout, const_stdout) if text
    )
    if import_noise:
        print("\nPyJHora import stdout:")
        print(import_noise)

    print_signatures(drik, utils)

    if not has_execution_args(args):
        print(
            "\nProvide --date, --time, --latitude, --longitude, and "
            "--timezone to execute the APIs against a chart."
        )
        return

    jd = utils.julian_day_number(parse_date(args.date), parse_time(args.time))
    place = drik.Place(
        args.place_name,
        args.latitude,
        args.longitude,
        args.timezone,
        args.elevation,
    )

    print("\nChart input:")
    print(f"- jd: {jd}")
    print(f"- place: {place}")

    parser_longitudes = parser_longitudes_by_planet(args.chart_json)

    print("\nDirect API execution:")
    try:
        positions = drik.planetary_positions(jd, place)
    except Exception as error:
        print(f"- drik.planetary_positions failed: {error}")
    else:
        print(f"- drik.planetary_positions returned: {positions}")

    speed_info = drik.planets_speed_info(jd, place)
    retrograde_ids = set(drik.planets_in_retrograde(jd, place))

    try:
        stationary_ids = set(drik.planets_in_stationary(jd, place))
    except Exception as error:
        print(f"- drik.planets_in_stationary failed: {error}")
        print("- Retrying stationary check with mean-node Rahu/Ketu mode")
        const._use_true_nodes_for_rahu_ketu = False
        stationary_ids = set(drik.planets_in_stationary(jd, place))

    print("\nPlanetary motion from drik.planets_speed_info:")
    print(
        "planet | longitude | parser_longitude | speed | "
        "retrograde | direct | stationary | motion_status"
    )
    for planet_id in sorted(PLANET_NAMES):
        planet = PLANET_NAMES[planet_id]
        data = speed_info[planet_id]
        status = motion_status(
            planet_id,
            retrograde_ids,
            stationary_ids,
        )
        print(
            f"{planet} | "
            f"{data[0]:.6f} | "
            f"{parser_longitudes.get(planet)} | "
            f"{data[3]:.9f} | "
            f"{status['retrograde']} | "
            f"{status['direct']} | "
            f"{status['stationary']} | "
            f"{status['motion_status']}"
        )

    print("\nValidated API mapping:")
    print("- longitude: drik.planets_speed_info(jd, place)[planet_id][0]")
    print("- speed: drik.planets_speed_info(jd, place)[planet_id][3]")
    print("- retrograde: planet_id in drik.planets_in_retrograde(jd, place)")
    print("- stationary: planet_id in drik.planets_in_stationary(jd, place)")
    print("- direct: not retrograde and not stationary")


if __name__ == "__main__":
    main()
