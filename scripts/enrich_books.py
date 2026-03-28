import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db
from app.models import Book
from app.services.importer import (
    ensure_placeholder_cover,
    extract_calibre_metadata,
    extract_cover_with_calibre,
)

app = create_app()


def first_existing_book_file(book, library_dir):
    for filename in (book.pdf_filename, book.epub_filename, book.mobi_filename):
        if not filename:
            continue
        file_path = library_dir / filename
        if file_path.exists():
            return file_path
    return None


with app.app_context():
    library_dir = Path(app.config["LIBRARY_DIR"])
    updated = 0

    for book in Book.query.order_by(Book.title.asc()).all():
        file_path = first_existing_book_file(book, library_dir)
        if not file_path:
            continue

        metadata = extract_calibre_metadata(file_path)
        changed = False

        for field in ("title", "author", "publisher", "description", "isbn", "language", "published_date"):
            if metadata.get(field) and not getattr(book, field):
                setattr(book, field, metadata[field])
                changed = True

        if not book.cover_image:
            book.cover_image = extract_cover_with_calibre(file_path, book) or ensure_placeholder_cover(book)
            changed = True

        if changed:
            updated += 1

    db.session.commit()
    print(f"Updated {updated} books.")
