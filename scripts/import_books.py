import os
import re

from app import create_app, db
from app.models import Book

BOOKS_DIR = "/books"

app = create_app()


def parse_filename(filename):
    """
    Extract title + author from:
    Title (Author).pdf
    """

    name = os.path.splitext(filename)[0]

    match = re.match(r"(.+?)\s*\((.+?)\)$", name)

    if match:
        title = match.group(1).strip()
        author = match.group(2).strip()
    else:
        title = name
        author = "Unknown"

    return title, author


with app.app_context():

    for file in os.listdir(BOOKS_DIR):

        if not file.lower().endswith((".pdf", ".epub", ".mobi")):
            continue

        existing = Book.query.filter_by(filename=file).first()

        if existing:
            print(f"Skipping (exists): {file}")
            continue

        title, author = parse_filename(file)

        file_path = f"/books/{file}"
        file_type = file.split(".")[-1].lower()

        book = Book(
            title=title,
            author=author,
            filename=file,
            file_path=file_path,
            file_type=file_type,
            category="Unsorted"
        )

        db.session.add(book)

        print(f"Added: {title} ({author})")

    db.session.commit()