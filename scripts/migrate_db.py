import sqlite3
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = BASE_DIR / "migrations"
sys.path.insert(0, str(BASE_DIR))

from config import DATABASE_PATH


def main():
    database_path = Path(DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            connection.executescript(migration_path.read_text(encoding="utf-8"))

    print(f"Applied migrations in {MIGRATIONS_DIR} to {database_path}")


if __name__ == "__main__":
    main()
