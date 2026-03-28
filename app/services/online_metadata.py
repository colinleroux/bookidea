import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import current_app

from app.services.importer import slugify


OPEN_LIBRARY_BOOKS_URL = "https://openlibrary.org/api/books"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"


def fetch_metadata_by_isbn(isbn):
    clean_isbn = normalize_isbn(isbn)
    if not clean_isbn:
        return {}

    params = urlencode(
        {
            "bibkeys": f"ISBN:{clean_isbn}",
            "format": "json",
            "jscmd": "data",
        }
    )

    try:
        with urlopen(f"{OPEN_LIBRARY_BOOKS_URL}?{params}", timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return {}

    book_data = payload.get(f"ISBN:{clean_isbn}", {})
    if not book_data:
        return {}

    authors = [author.get("name", "").strip() for author in book_data.get("authors", []) if author.get("name")]
    publishers = [publisher.get("name", "").strip() for publisher in book_data.get("publishers", []) if publisher.get("name")]

    return {
        "title": book_data.get("title"),
        "subtitle": book_data.get("subtitle"),
        "author": ", ".join(authors) if authors else None,
        "publisher": publishers[0] if publishers else None,
        "published_date": book_data.get("publish_date"),
        "page_count": book_data.get("number_of_pages"),
        "description": normalize_description(book_data.get("notes") or book_data.get("description")),
        "cover_url": OPEN_LIBRARY_COVER_URL.format(isbn=clean_isbn),
    }


def normalize_description(value):
    if isinstance(value, dict):
        return value.get("value")
    if isinstance(value, str):
        return value.strip()
    return None


def normalize_isbn(value):
    if not value:
        return ""
    return "".join(character for character in value if character.isdigit() or character.upper() == "X")


def save_cover_from_url(book, image_url):
    if not image_url:
        return None

    covers_dir = Path(current_app.config["COVERS_DIR"])
    filename = f"{slugify(f'{book.title}-{book.author}')}.jpg"
    destination = covers_dir / filename

    try:
        with urlopen(image_url, timeout=15) as response:
            content = response.read()
    except (HTTPError, URLError, TimeoutError):
        return None

    if not content:
        return None

    destination.write_bytes(content)
    return f"covers/{filename}"
