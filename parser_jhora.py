import re


PRIMARY_BODIES = {
    "Lagna", "Sun", "Moon", "Mars", "Mercury",
    "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"
}

SIGN_START_DEGREES = {
    "Ar": 0, "Ta": 30, "Ge": 60, "Cn": 90,
    "Le": 120, "Vi": 150, "Li": 180, "Sc": 210,
    "Sg": 240, "Cp": 270, "Aq": 300, "Pi": 330,
}


def longitude_to_absolute(degree, sign, minute, second):
    return (
        SIGN_START_DEGREES[sign]
        + int(degree)
        + int(minute) / 60
        + float(second) / 3600
    )


def coordinate_to_decimal(coordinate, positive_direction):
    match = re.match(
        r"(?P<degree>\d+)\s+(?P<direction>[NSEW])\s+"
        r"(?P<minute>\d+)'\s+(?P<second>\d+)\"",
        coordinate.strip(),
    )
    if not match:
        return None

    decimal = (
        int(match.group("degree"))
        + int(match.group("minute")) / 60
        + int(match.group("second")) / 3600
    )
    if match.group("direction") != positive_direction:
        decimal *= -1

    return round(decimal, 6)


def parse_coordinates(text):
    coordinate_match = re.search(
        r"Place:\s+"
        r"(?P<longitude>\d+\s+[EW]\s+\d+'\s+\d+\"),\s+"
        r"(?P<latitude>\d+\s+[NS]\s+\d+'\s+\d+\")",
        text,
    )

    if not coordinate_match:
        return None

    longitude_dms = coordinate_match.group("longitude").strip()
    latitude_dms = coordinate_match.group("latitude").strip()

    return {
        "longitude_dms": longitude_dms,
        "latitude_dms": latitude_dms,
        "longitude_decimal": coordinate_to_decimal(longitude_dms, "E"),
        "latitude_decimal": coordinate_to_decimal(latitude_dms, "N"),
    }


def parse_metadata(text):
    metadata = {}

    patterns = {
        "date": r"Date:\s+(.*)",
        "time": r"Time:\s+(.*)",
        "time_zone": r"Time Zone:\s+(.*)",
        "ayanamsa": r"Ayanamsa:\s+(.*)",
        "sidereal_time": r"Sidereal Time:\s+(.*)",
        "tithi": r"Tithi:\s+(.*)",
        "weekday": r"Vedic Weekday:\s+(.*)",
        "nakshatra": r"Nakshatra:\s+(.*)",
        "yoga": r"Yoga:\s+(.*)",
        "karana": r"Karana:\s+(.*)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        metadata[key] = match.group(1).strip() if match else None

    place_match = re.search(
        r"Place:\s+.*?\n\s+(.*)",
        text,
        re.MULTILINE
    )

    metadata["place"] = (
        place_match.group(1).strip()
        if place_match else None
    )
    metadata["coordinates"] = parse_coordinates(text)

    return metadata


def parse_vimshottari(text):
    section_match = re.search(
        r"Vimsottari Dasa.*?:\s*(.*)$",
        text,
        re.DOTALL
    )

    if not section_match:
        return []

    section = section_match.group(1)

    dashas = []
    current_mahadasha = None
    dasha_lords = {
        "Ket", "Ven", "Sun", "Moon", "Mars",
        "Rah", "Jup", "Sat", "Merc"
    }

    entry_pattern = re.compile(
        r"\b(?P<lord>Ket|Ven|Sun|Moon|Mars|Rah|Jup|Sat|Merc)\s+"
        r"(?P<date>\d{4}-\d{2}-\d{2})\b"
    )

    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        is_mahadasha_line = not line[0].isspace()
        first_token = stripped.split()[0]

        if is_mahadasha_line and first_token in dasha_lords:
            current_mahadasha = first_token

        for match in entry_pattern.finditer(stripped):
            dashas.append({
                "mahadasha": current_mahadasha,
                "antardasha": match.group("lord"),
                "start_date": match.group("date")
            })

    return dashas


def parse_jhora_txt(text):
    rows = []
    in_body_table = False

    row_pattern = re.compile(
        r'^(?P<body>.+?)\s+'
        r'(?P<degree>\d{1,2})\s+'
        r'(?P<sign>Ar|Ta|Ge|Cn|Le|Vi|Li|Sc|Sg|Cp|Aq|Pi)\s+'
        r'(?P<minute>\d{2})\'\s+'
        r'(?P<second>\d{2}\.\d+)"\s+'
        r'(?P<nakshatra>\S+)\s+'
        r'(?P<pada>\d)\s+'
        r'(?P<rasi>Ar|Ta|Ge|Cn|Le|Vi|Li|Sc|Sg|Cp|Aq|Pi)\s+'
        r'(?P<navamsa>Ar|Ta|Ge|Cn|Le|Vi|Li|Sc|Sg|Cp|Aq|Pi)$'
    )

    for line in text.splitlines():
        if line.strip().startswith("Body") and "Longitude" in line:
            in_body_table = True
            continue

        if in_body_table and line.strip().startswith("Rasi"):
            break

        if not in_body_table:
            continue

        match = row_pattern.match(line.strip())
        if not match:
            continue

        data = match.groupdict()
        raw_body = data["body"]

        retrograde = "(R)" in raw_body
        clean_body = raw_body.replace("(R)", "").strip()

        chara_karaka = None
        if " - " in clean_body:
            body, chara_karaka = clean_body.split(" - ", 1)
        else:
            body = clean_body

        absolute_degree = longitude_to_absolute(
            data["degree"],
            data["sign"],
            data["minute"],
            data["second"],
        )

        rows.append({
            "body": body.strip(),
            "is_primary": body.strip() in PRIMARY_BODIES,
            "retrograde": retrograde,
            "motion_status": "retrograde" if retrograde else "unknown",
            "speed": None,
            "stationary": None,
            "direct": None,
            "chara_karaka": chara_karaka,
            "sign": data["sign"],
            "degree_in_sign": int(data["degree"]),
            "minute": int(data["minute"]),
            "second": float(data["second"]),
            "absolute_degree": round(absolute_degree, 6),
            "nakshatra": data["nakshatra"],
            "pada": int(data["pada"]),
            "rasi": data["rasi"],
            "navamsa": data["navamsa"],
        })

    primary_positions = [
        row for row in rows
        if row["is_primary"]
    ]

    return {
        "metadata": parse_metadata(text),
        "positions": rows,
        "primary_positions": primary_positions,
        "dashas": {
            "vimshottari": parse_vimshottari(text)
        }
    }
