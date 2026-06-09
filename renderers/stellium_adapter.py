"""Shared conversion from local chart JSON to Stellium chart objects."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Iterable

from stellium.core.models import (
    Aspect,
    CalculatedChart,
    CelestialPosition,
    ChartDateTime,
    ChartLocation,
    HouseCusps,
    ObjectType,
)


PLANET_ORDER = (
    "Sun",
    "Moon",
    "Mars",
    "Mercury",
    "Jupiter",
    "Venus",
    "Saturn",
    "Rahu",
    "Ketu",
)

WESTERN_NODE_NAMES = {
    "Rahu": "True Node",
    "Ketu": "South Node",
}

ASPECT_DEFINITIONS = {
    "Opposition": 180,
    "Trine": 120,
    "Square": 90,
}

ASPECT_ORB_DEGREES = 6.0


@dataclass(frozen=True)
class SourceBody:
    body: str
    longitude: float
    speed: float
    retrograde: bool


def build_north_indian_chart(chart: dict, chart_name: str) -> CalculatedChart:
    return build_chart(
        chart,
        chart_name,
        node_names="vedic",
        node_object_type=ObjectType.PLANET,
        include_aspects=False,
        suppress_node_retrograde=True,
    )


def build_western_chart(chart: dict, chart_name: str) -> CalculatedChart:
    return build_chart(
        chart,
        chart_name,
        node_names="western",
        node_object_type=ObjectType.NODE,
        include_aspects=True,
        suppress_node_retrograde=True,
    )


def build_chart(
    chart: dict,
    chart_name: str,
    *,
    node_names: str,
    node_object_type: ObjectType,
    include_aspects: bool,
    suppress_node_retrograde: bool,
) -> CalculatedChart:
    positions = _positions(
        chart,
        node_names=node_names,
        node_object_type=node_object_type,
        suppress_node_retrograde=suppress_node_retrograde,
    )

    return CalculatedChart(
        datetime=_chart_datetime(chart),
        location=_chart_location(chart),
        positions=positions,
        house_systems=_whole_sign_houses_from_lagna(chart),
        aspects=_aspects(positions) if include_aspects else (),
        declination_aspects=(),
        metadata={"name": chart_name},
        ayanamsa=chart.get("metadata", {}).get("ayanamsa"),
    )


def aspect_summary(chart: CalculatedChart) -> dict[str, int]:
    summary = {name: 0 for name in ASPECT_DEFINITIONS}
    for aspect in chart.aspects:
        summary[aspect.aspect_name] = summary.get(aspect.aspect_name, 0) + 1
    return summary


def source_bodies(chart: dict) -> list[SourceBody]:
    d1 = _d1(chart)
    primary_by_body = {
        position["body"]: position for position in chart.get("primary_positions", [])
    }
    bodies = []

    for body in PLANET_ORDER:
        placement = d1.get(body)
        if not placement:
            continue

        source = primary_by_body.get(body, {})
        speed = source.get("speed")
        retrograde = bool(source.get("retrograde"))
        if speed is None:
            speed = -1.0 if retrograde else 0.0

        bodies.append(
            SourceBody(
                body=body,
                longitude=float(placement["absolute_degree"]),
                speed=float(speed),
                retrograde=retrograde,
            )
        )

    return bodies


def _positions(
    chart: dict,
    *,
    node_names: str,
    node_object_type: ObjectType,
    suppress_node_retrograde: bool,
) -> tuple[CelestialPosition, ...]:
    positions = []

    for body in source_bodies(chart):
        is_node = body.body in WESTERN_NODE_NAMES
        name = (
            WESTERN_NODE_NAMES[body.body]
            if node_names == "western" and is_node
            else body.body
        )
        object_type = node_object_type if is_node else ObjectType.PLANET
        speed = 0.0 if suppress_node_retrograde and is_node else body.speed

        positions.append(
            CelestialPosition(
                name=name,
                object_type=object_type,
                longitude=body.longitude,
                speed_longitude=speed,
            )
        )

    lagna = _d1(chart).get("Lagna")
    if not lagna:
        raise ValueError("calculated_charts.d1 missing Lagna")

    positions.append(
        CelestialPosition(
            name="ASC",
            object_type=ObjectType.ANGLE,
            longitude=float(lagna["absolute_degree"]),
        )
    )

    return tuple(positions)


def _aspects(positions: Iterable[CelestialPosition]) -> tuple[Aspect, ...]:
    aspect_objects = [
        position
        for position in positions
        if position.object_type in {ObjectType.PLANET, ObjectType.NODE}
    ]
    aspects = []

    for index, object1 in enumerate(aspect_objects):
        for object2 in aspect_objects[index + 1 :]:
            separation = _separation(object1.longitude, object2.longitude)
            for aspect_name, aspect_degree in ASPECT_DEFINITIONS.items():
                orb = abs(separation - aspect_degree)
                if orb <= ASPECT_ORB_DEGREES:
                    aspects.append(
                        Aspect(
                            object1=object1,
                            object2=object2,
                            aspect_name=aspect_name,
                            aspect_degree=aspect_degree,
                            orb=orb,
                        )
                    )
                    break

    return tuple(aspects)


def _separation(longitude1: float, longitude2: float) -> float:
    difference = abs((longitude1 - longitude2) % 360.0)
    return min(difference, 360.0 - difference)


def _whole_sign_houses_from_lagna(chart: dict) -> dict[str, HouseCusps]:
    lagna = _d1(chart).get("Lagna")
    if not lagna:
        raise ValueError("calculated_charts.d1 missing Lagna")

    asc_sign_index = int(lagna["sign_index"])
    cusps = tuple(((asc_sign_index + i) % 12) * 30.0 for i in range(12))
    return {"Whole Sign": HouseCusps(system="Whole Sign", cusps=cusps)}


def _chart_datetime(chart: dict) -> ChartDateTime:
    local_datetime = _local_datetime(chart)
    utc_datetime = local_datetime.astimezone(dt.UTC)
    return ChartDateTime(
        utc_datetime=utc_datetime,
        local_datetime=local_datetime,
        julian_day=0.0,
    )


def _local_datetime(chart: dict) -> dt.datetime:
    metadata = chart.get("metadata", {})
    date_text = metadata.get("date")
    time_text = metadata.get("time")
    offset = _timezone_offset(metadata.get("time_zone", ""))

    if date_text and time_text:
        for fmt in ("%B %d, %Y %I:%M:%S %p", "%B %d, %Y %H:%M:%S"):
            try:
                parsed = dt.datetime.strptime(f"{date_text} {time_text}", fmt)
                return parsed.replace(tzinfo=offset)
            except ValueError:
                pass

    return dt.datetime(1900, 1, 1, tzinfo=offset)


def _timezone_offset(time_zone_text: str) -> dt.timezone:
    match = re.search(r"(\d+):(\d+):(\d+).*?\((East|West) of GMT\)", time_zone_text)
    if not match:
        return dt.UTC

    hours, minutes, seconds, direction = match.groups()
    delta = dt.timedelta(
        hours=int(hours),
        minutes=int(minutes),
        seconds=int(seconds),
    )
    if direction == "West":
        delta = -delta
    return dt.timezone(delta)


def _chart_location(chart: dict) -> ChartLocation:
    metadata = chart.get("metadata", {})
    coordinates = metadata.get("coordinates", {})
    return ChartLocation(
        latitude=float(coordinates.get("latitude_decimal", 0.0)),
        longitude=float(coordinates.get("longitude_decimal", 0.0)),
        name=metadata.get("place", ""),
        timezone=str(_timezone_offset(metadata.get("time_zone", ""))),
    )


def _d1(chart: dict) -> dict:
    d1 = chart.get("calculated_charts", {}).get("d1")
    if d1:
        return d1

    positions = {}
    for position in chart.get("primary_positions", []):
        body = position.get("body")
        absolute_degree = position.get("absolute_degree")
        if body and absolute_degree is not None:
            positions[body] = {
                "body": body,
                "absolute_degree": absolute_degree,
                "degree_in_sign": position.get("degree_in_sign"),
                "sign_index": _sign_index(position.get("sign")),
            }

    if not positions:
        raise ValueError("chart has neither calculated_charts.d1 nor primary_positions")
    return positions


def _sign_index(sign: str | None) -> int:
    signs = ("Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi")
    if sign not in signs:
        raise ValueError(f"unknown sign: {sign}")
    return signs.index(sign)
