from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db.repository import Repository


def main() -> None:
    repo = Repository(settings.database_path)
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"
    repo.init_schema(schema_path.read_text(encoding="utf-8"))
    print(f"Initialized database schema at: {settings.database_path}")


if __name__ == "__main__":
    main()
