"""D1 planetary dignity calculation.

This module intentionally keeps the current rules compact and sign-based so the
report layer can depend on a stable API while the astrology rules expand later.
"""

from __future__ import annotations


SIGN_RULERS = {
    "Ar": "Mars",
    "Ta": "Venus",
    "Ge": "Mercury",
    "Cn": "Moon",
    "Le": "Sun",
    "Vi": "Mercury",
    "Li": "Venus",
    "Sc": "Mars",
    "Sg": "Jupiter",
    "Cp": "Saturn",
    "Aq": "Saturn",
    "Pi": "Jupiter",
}

EXALTATION_SIGNS = {
    "Sun": "Ar",
    "Moon": "Ta",
    "Mars": "Cp",
    "Mercury": "Vi",
    "Jupiter": "Cn",
    "Venus": "Pi",
    "Saturn": "Li",
}

DEBILITATION_SIGNS = {
    "Sun": "Li",
    "Moon": "Sc",
    "Mars": "Cn",
    "Mercury": "Pi",
    "Jupiter": "Cp",
    "Venus": "Vi",
    "Saturn": "Ar",
}

MOOLATRIKONA_SIGNS = {
    "Sun": "Le",
    "Moon": "Ta",
    "Mars": "Ar",
    "Mercury": "Vi",
    "Jupiter": "Sg",
    "Venus": "Li",
    "Saturn": "Aq",
}

OWN_SIGNS = {
    "Sun": {"Le"},
    "Moon": {"Cn"},
    "Mars": {"Ar", "Sc"},
    "Mercury": {"Ge", "Vi"},
    "Jupiter": {"Sg", "Pi"},
    "Venus": {"Ta", "Li"},
    "Saturn": {"Cp", "Aq"},
}

NATURAL_RELATIONSHIPS = {
    "Sun": {
        "friends": {"Moon", "Mars", "Jupiter"},
        "neutrals": {"Mercury"},
        "enemies": {"Venus", "Saturn"},
    },
    "Moon": {
        "friends": {"Sun", "Mercury"},
        "neutrals": {"Mars", "Jupiter", "Venus", "Saturn"},
        "enemies": set(),
    },
    "Mars": {
        "friends": {"Sun", "Moon", "Jupiter"},
        "neutrals": {"Venus", "Saturn"},
        "enemies": {"Mercury"},
    },
    "Mercury": {
        "friends": {"Sun", "Venus"},
        "neutrals": {"Mars", "Jupiter", "Saturn"},
        "enemies": {"Moon"},
    },
    "Jupiter": {
        "friends": {"Sun", "Moon", "Mars"},
        "neutrals": {"Saturn"},
        "enemies": {"Mercury", "Venus"},
    },
    "Venus": {
        "friends": {"Mercury", "Saturn"},
        "neutrals": {"Mars", "Jupiter"},
        "enemies": {"Sun", "Moon"},
    },
    "Saturn": {
        "friends": {"Mercury", "Venus"},
        "neutrals": {"Jupiter"},
        "enemies": {"Sun", "Moon", "Mars"},
    },
}

TEMPORARY_FRIEND_HOUSES = {2, 3, 4, 10, 11, 12}
PLANET_ORDER = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
SIGNS = ("Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi")


def dignity_for_chart(chart: dict) -> dict[str, str]:
    primary = {
        position.get("body"): position
        for position in chart.get("primary_positions", [])
    }
    return {
        planet: dignity_for_planet(planet, primary)
        for planet in PLANET_ORDER
        if planet in primary
    }


def dignity_for_planet(planet: str, primary: dict[str, dict]) -> str:
    sign = primary.get(planet, {}).get("sign")
    if sign == EXALTATION_SIGNS.get(planet):
        return "Exalted"
    if sign == DEBILITATION_SIGNS.get(planet):
        return "Debilitated"
    if sign == MOOLATRIKONA_SIGNS.get(planet):
        return "Moolatrikona"
    if sign in OWN_SIGNS.get(planet, set()):
        return "Own"

    ruler = SIGN_RULERS.get(sign)
    natural = _natural_relationship(planet, ruler)
    temporary = _temporary_relationship(planet, ruler, primary)
    return _compound_relationship(natural, temporary)


def _natural_relationship(planet: str, other: str | None) -> str:
    if not other:
        return "neutral"
    relationships = NATURAL_RELATIONSHIPS.get(planet, {})
    if other in relationships.get("friends", set()):
        return "friend"
    if other in relationships.get("enemies", set()):
        return "enemy"
    return "neutral"


def _temporary_relationship(planet: str, other: str | None, primary: dict[str, dict]) -> str:
    if not other:
        return "neutral"
    planet_sign = primary.get(planet, {}).get("sign")
    other_sign = primary.get(other, {}).get("sign")
    if planet_sign not in SIGNS or other_sign not in SIGNS:
        return "neutral"

    house_distance = ((SIGNS.index(other_sign) - SIGNS.index(planet_sign)) % 12) + 1
    return "friend" if house_distance in TEMPORARY_FRIEND_HOUSES else "enemy"


def _compound_relationship(natural: str, temporary: str) -> str:
    score = {
        "friend": 1,
        "neutral": 0,
        "enemy": -1,
    }[natural] + {
        "friend": 1,
        "neutral": 0,
        "enemy": -1,
    }[temporary]

    if score >= 2:
        return "Great Friend"
    if score == 1:
        return "Friend"
    if score == 0:
        return "Neutral"
    if score == -1:
        return "Enemy"
    return "Great Enemy"
