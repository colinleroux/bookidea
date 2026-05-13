import shutil
import subprocess
from pathlib import Path

from flask import current_app

from app import db
from app.services.importer import (
    file_sha256,
    next_available_path,
    record_imported_file,
    slugify,
    stored_book_file_path,
)


def ebook_convert_command():
    configured_path = current_app.config.get("CALIBRE_EBOOK_CONVERT", "")
    if configured_path:
        candidate = Path(configured_path)
        if candidate.exists():
            return str(candidate)

    return shutil.which("ebook-convert")


def can_convert_epub_to_pdf(book):
    return bool(
        book
        and not book.has_stored_file(book.pdf_filename)
        and book.has_stored_file(book.epub_filename)
        and ebook_convert_command()
    )


def convert_epub_to_pdf(book):
    command = ebook_convert_command()
    if not command:
        return False, "Calibre ebook-convert is not available."

    if book.has_stored_file(book.pdf_filename):
        return False, "This book already has a PDF file."

    epub_path = stored_book_file_path(book.epub_filename)
    if not epub_path:
        return False, "This book does not have an available EPUB file."

    library_dir = Path(current_app.config["LIBRARY_DIR"])
    base_filename = f"{slugify(f'{book.title}-{book.author}')}.pdf"
    pdf_path = next_available_path(library_dir, base_filename)

    try:
        result = subprocess.run(
            [command, str(epub_path), str(pdf_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        if pdf_path.exists():
            pdf_path.unlink(missing_ok=True)
        return False, "EPUB to PDF conversion timed out."
    except Exception as exc:
        if pdf_path.exists():
            pdf_path.unlink(missing_ok=True)
        return False, f"EPUB to PDF conversion could not start: {exc}"

    if result.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size == 0:
        if pdf_path.exists():
            pdf_path.unlink(missing_ok=True)
        details = (result.stderr or result.stdout or "No converter output.").strip()
        return False, f"EPUB to PDF conversion failed: {details[:300]}"

    book.pdf_filename = pdf_path.name
    record_imported_file(
        book,
        ".pdf",
        pdf_path.name,
        pdf_path.name,
        file_sha256(pdf_path),
        pdf_path.stat().st_size,
    )
    db.session.commit()
    return True, f"Created PDF file {pdf_path.name}."
