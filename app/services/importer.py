import re
import shutil as shutil_module
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from flask import current_app

from app import db
from app.models import Book

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

try:
    from ebooklib import epub
except ImportError:  # pragma: no cover
    epub = None


SUPPORTED_EXTENSIONS = {".pdf", ".epub", ".mobi"}


def slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "book"


def parse_filename(file_path):
    name = file_path.stem
    match = re.match(r"(.+?)\s*\((.+?)\)$", name)

    if match:
        return {"title": match.group(1).strip(), "author": match.group(2).strip()}

    return {"title": name.replace("_", " ").strip(), "author": "Unknown"}


def extract_pdf_metadata(file_path):
    if PdfReader is None:
        return {}

    try:
        reader = PdfReader(str(file_path))
        metadata = reader.metadata or {}
        page_count = len(reader.pages)
        return {
            "title": metadata.get("/Title"),
            "author": metadata.get("/Author"),
            "description": metadata.get("/Subject"),
            "publisher": metadata.get("/Producer"),
            "page_count": page_count,
        }
    except Exception:
        return {}


def _first_epub_metadata(book, namespace, name):
    values = book.get_metadata(namespace, name)
    if not values:
        return None
    value = values[0][0]
    return value.strip() if isinstance(value, str) else value


def extract_epub_metadata(file_path):
    if epub is None:
        return {}

    try:
        book = epub.read_epub(str(file_path))
        description = _first_epub_metadata(book, "DC", "description")
        language = _first_epub_metadata(book, "DC", "language")
        publisher = _first_epub_metadata(book, "DC", "publisher")
        published_date = _first_epub_metadata(book, "DC", "date")

        return {
            "title": _first_epub_metadata(book, "DC", "title"),
            "author": _first_epub_metadata(book, "DC", "creator"),
            "description": description,
            "language": language,
            "publisher": publisher,
            "published_date": published_date,
            "isbn": _extract_epub_identifier(book),
        }
    except Exception:
        return {}


def _extract_epub_identifier(book):
    for value, _ in book.get_metadata("DC", "identifier"):
        if isinstance(value, str) and "isbn" in value.lower():
            return value.split(":")[-1].strip()
    identifiers = book.get_metadata("DC", "identifier")
    if identifiers:
        value = identifiers[0][0]
        return value.strip() if isinstance(value, str) else value
    return None


def extract_metadata(file_path):
    metadata = parse_filename(file_path)
    calibre_metadata = extract_calibre_metadata(file_path)
    metadata.update({k: v for k, v in calibre_metadata.items() if v})
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        metadata.update({k: v for k, v in extract_pdf_metadata(file_path).items() if v})
    elif extension == ".epub":
        metadata.update({k: v for k, v in extract_epub_metadata(file_path).items() if v})

    metadata["title"] = metadata.get("title") or file_path.stem
    metadata["author"] = metadata.get("author") or "Unknown"
    return metadata


def calibre_command():
    configured_path = current_app.config.get("CALIBRE_EBOOK_META", "")
    if configured_path:
        candidate = Path(configured_path)
        if candidate.exists():
            return str(candidate)

    return shutil_module.which("ebook-meta")


def extract_calibre_metadata(file_path):
    command = calibre_command()
    if not command:
        return {}

    try:
        result = subprocess.run(
            [command, str(file_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except Exception:
        return {}

    if result.returncode != 0:
        return {}

    metadata = {}
    field_map = {
        "title": "title",
        "author(s)": "author",
        "publisher": "publisher",
        "comments": "description",
        "isbn": "isbn",
        "languages": "language",
        "published": "published_date",
    }

    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower()
        mapped_field = field_map.get(normalized_key)
        if mapped_field and value.strip():
            metadata[mapped_field] = value.strip()

    return metadata


def extract_cover_with_calibre(file_path, book):
    command = calibre_command()
    if not command:
        return None

    covers_dir = Path(current_app.config["COVERS_DIR"])
    slug = slugify(f"{book.title}-{book.author}")
    destination = covers_dir / f"{slug}.jpg"

    try:
        result = subprocess.run(
            [command, str(file_path), "--get-cover", str(destination)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception:
        return None

    if result.returncode != 0 or not destination.exists() or destination.stat().st_size == 0:
        if destination.exists():
            destination.unlink(missing_ok=True)
        return None

    return f"covers/{destination.name}"


def ensure_placeholder_cover(book):
    covers_dir = Path(current_app.config["COVERS_DIR"])
    slug = slugify(f"{book.title}-{book.author}")
    cover_path = covers_dir / f"{slug}.svg"

    should_refresh = False
    if cover_path.exists() and cover_path.suffix.lower() == ".svg":
        existing_svg = cover_path.read_text(encoding="utf-8")
        should_refresh = "Personal Library Edition" in existing_svg

    if not cover_path.exists() or should_refresh:
        title = escape_xml(book.title[:40])
        author = escape_xml(book.author[:40])
        palette_seed = sum(ord(char) for char in f"{book.title}{book.author}")
        palettes = [
            ("#0f172a", "#2563eb", "#7dd3fc", "#f8fafc"),
            ("#3f1d2e", "#db2777", "#f9a8d4", "#fff7ed"),
            ("#172554", "#7c3aed", "#c4b5fd", "#fdf4ff"),
            ("#052e16", "#16a34a", "#86efac", "#f0fdf4"),
            ("#3b0764", "#f59e0b", "#fde68a", "#fffbeb"),
        ]
        bg_dark, bg_mid, accent, text_light = palettes[palette_seed % len(palettes)]
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="960" viewBox="0 0 640 960">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg_dark}" />
      <stop offset="55%" stop-color="{bg_mid}" />
      <stop offset="100%" stop-color="{accent}" />
    </linearGradient>
  </defs>
  <rect width="640" height="960" fill="url(#bg)" />
  <circle cx="520" cy="140" r="110" fill="{accent}" fill-opacity="0.18" />
  <circle cx="130" cy="820" r="150" fill="{text_light}" fill-opacity="0.10" />
  <rect x="42" y="42" width="556" height="876" rx="28" fill="none" stroke="{text_light}" stroke-opacity="0.45" stroke-width="4" />
  <rect x="86" y="110" width="160" height="10" rx="5" fill="{text_light}" fill-opacity="0.65" />
  <rect x="86" y="136" width="92" height="10" rx="5" fill="{text_light}" fill-opacity="0.35" />
  <text x="320" y="330" text-anchor="middle" font-size="42" font-family="Georgia, serif" fill="{text_light}">{title}</text>
  <text x="320" y="420" text-anchor="middle" font-size="26" font-family="Georgia, serif" fill="{text_light}" fill-opacity="0.82">{author}</text>
  <text x="320" y="820" text-anchor="middle" font-size="22" font-family="Arial, sans-serif" fill="{text_light}" fill-opacity="0.88">Library Atelier Edition</text>
</svg>
"""
        cover_path.write_text(svg, encoding="utf-8")

    return f"covers/{cover_path.name}"


def cover_file_path(cover_value):
    if not cover_value:
        return None
    filename = Path(cover_value).name
    return Path(current_app.config["COVERS_DIR"]) / filename


def escape_xml(value):
    return escape(value)


def next_available_path(directory, filename):
    candidate = directory / filename
    counter = 1
    while candidate.exists():
        candidate = directory / f"{Path(filename).stem}-{counter}{Path(filename).suffix}"
        counter += 1
    return candidate


def resolve_existing_book(metadata):
    stem = slugify(metadata.get("source_stem", ""))
    if stem:
        for book in Book.query.all():
            existing_stems = {
                slugify(Path(filename).stem)
                for filename in (book.pdf_filename, book.epub_filename, book.mobi_filename)
                if filename
            }
            if stem in existing_stems:
                return book

    title = (metadata.get("title") or "").strip()
    author = (metadata.get("author") or "").strip()
    if not title:
        return None

    query = Book.query.filter(db.func.lower(Book.title) == title.lower())
    if author:
        query = query.filter(db.func.lower(Book.author) == author.lower())
    return query.first()


def assign_format_filename(book, extension, filename):
    if extension == ".pdf":
        book.pdf_filename = filename
    elif extension == ".epub":
        book.epub_filename = filename
    elif extension == ".mobi":
        book.mobi_filename = filename


def should_mark_for_review(book):
    missing_core_fields = [
        not book.description,
        not book.isbn,
        book.author == "Unknown",
        not (book.category_id or False),
    ]
    return any(missing_core_fields)


def import_new_books(limit=None):
    source_dir = Path(current_app.config["NEW_BOOKS_DIR"])
    library_dir = Path(current_app.config["LIBRARY_DIR"])

    processed = []
    skipped = []
    processed_count = 0

    for file_path in sorted(source_dir.iterdir()):
        if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        if limit is not None and processed_count >= limit:
            break

        metadata = extract_metadata(file_path)
        metadata["source_stem"] = file_path.stem
        existing_book = resolve_existing_book(metadata)
        destination = next_available_path(library_dir, file_path.name)
        shutil.move(str(file_path), destination)

        book = existing_book or Book(
            title=metadata["title"],
            author=metadata["author"],
        )

        book.title = metadata.get("title") or book.title
        book.author = metadata.get("author") or book.author
        book.subtitle = metadata.get("subtitle") or book.subtitle
        book.description = metadata.get("description") or book.description
        book.isbn = metadata.get("isbn") or book.isbn
        book.publisher = metadata.get("publisher") or book.publisher
        book.published_date = metadata.get("published_date") or book.published_date
        book.language = metadata.get("language") or book.language
        book.page_count = metadata.get("page_count") or book.page_count
        assign_format_filename(book, destination.suffix.lower(), destination.name)
        book.needs_review = should_mark_for_review(book)

        if not book.cover_image:
            book.cover_image = extract_cover_with_calibre(destination, book) or ensure_placeholder_cover(book)

        if existing_book is None:
            db.session.add(book)
            action = "created"
        else:
            action = "updated"

        processed.append({"title": book.title, "author": book.author, "action": action})
        processed_count += 1

    db.session.commit()
    remaining = count_pending_import_files(source_dir)
    return {"processed": processed, "skipped": skipped, "remaining": remaining}


def count_pending_import_files(source_dir):
    count = 0
    for file_path in source_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            count += 1
    return count
