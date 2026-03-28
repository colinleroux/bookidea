import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.services.importer import import_new_books

app = create_app()


with app.app_context():
    result = import_new_books()
    for item in result["processed"]:
        print(f"{item['action'].title()}: {item['title']} ({item['author']})")

    if not result["processed"]:
        print("No new supported files found in the import queue.")
