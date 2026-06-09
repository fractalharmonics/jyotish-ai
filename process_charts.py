from pathlib import Path
import json
import argparse

from enrich import enrich_chart
from parser_jhora import parse_jhora_txt

INPUT_DIR = Path("charts_in")
OUTPUT_DIR = Path("charts_out")


def process_chart(txt_file, force=False):
    chart_name = txt_file.stem
    output_json = OUTPUT_DIR / f"{chart_name}.json"

    if output_json.exists() and not force:
        print(f"Skipping {chart_name}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    text = txt_file.read_text(
        encoding="utf-8",
        errors="replace"
    )

    parsed = enrich_chart(parse_jhora_txt(text))

    output_json.write_text(
        json.dumps(parsed, indent=2),
        encoding="utf-8"
    )

    print(f"Processed {chart_name}")

def main():
    parser = argparse.ArgumentParser(
        description="Parse JHora TXT exports into structured JSON."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess charts even if output JSON already exists."
    )
    args = parser.parse_args()

    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    for txt_file in INPUT_DIR.glob("*.txt"):
        process_chart(txt_file, force=args.force)

if __name__ == "__main__":
    main()
