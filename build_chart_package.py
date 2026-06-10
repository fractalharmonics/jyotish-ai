from __future__ import annotations

import subprocess
import sys


COMMANDS = (
    ("process charts", [sys.executable, "process_charts.py", "--force"]),
    ("validate output", [sys.executable, "validate_output.py", "--non-strict"]),
    ("render charts", [sys.executable, "render_charts.py"]),
    ("build report", [sys.executable, "report/build_report.py"]),
)


def main() -> None:
    if sys.prefix == sys.base_prefix:
        print(
            "Warning: not running inside a virtual environment. "
            "Dependencies may be missing."
        )

    for label, command in COMMANDS:
        print(f"== {label} ==", flush=True)
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
