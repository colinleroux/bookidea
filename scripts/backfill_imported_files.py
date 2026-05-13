import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app import create_app, db
from app.models import Book, ImportedFile
from app.services.importer import file_sha256, format_label, stored_book_file_path


def main():
    app = create_app()
    created_count = 0
    skipped_count = 0

    with app.app_context():
        for book in Book.query.order_by(Book.id.asc()).all():
            for extension, filename in (
                (".pdf", book.pdf_filename),
                (".epub", book.epub_filename),
                (".mobi", book.mobi_filename),
            ):
                file_path = stored_book_file_path(filename)
                if not file_path:
                    skipped_count += 1
                    continue

                sha256 = file_sha256(file_path)
                if ImportedFile.query.filter_by(sha256=sha256).first():
                    skipped_count += 1
                    continue

                db.session.add(
                    ImportedFile(
                        book_id=book.id,
                        format=format_label(extension),
                        stored_filename=filename,
                        original_filename=Path(filename).name,
                        sha256=sha256,
                        file_size=file_path.stat().st_size,
                    )
                )
                created_count += 1

        db.session.commit()

    print(f"Backfilled {created_count} imported file records. Skipped {skipped_count}.")


if __name__ == "__main__":
    main()
