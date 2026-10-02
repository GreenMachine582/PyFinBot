"""Seed PyFinBot with demo data — development only. Run from the project root:

    python scripts/seed_demo.py [--reset]

See src/pyfinbot/dev/seed.py.
"""

import sys
from pathlib import Path

# Imported as src.pyfinbot, like `uvicorn src.pyfinbot.pyfinbot:app`: the
# alembic env (run first, to migrate) imports src.pyfinbot.models, and a
# second copy of the models under another package name would redefine the
# tables.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pyfinbot.dev.seed import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
