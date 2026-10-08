"""Export a PyFinBot report (holdings, capital gains or dividends) as CSV or
JSON. Run from the project root:

    python scripts/cli.py holdings --user alice --format json
    python scripts/cli.py gains --user alice --fy 2024 -o gains.csv

`python scripts/cli.py --help` lists the reports and options. See
src/pyfinbot/cli.py.
"""

import sys
from pathlib import Path

# Imported as src.pyfinbot, like scripts/create_user.py and
# `uvicorn src.pyfinbot.pyfinbot:app`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pyfinbot.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
