from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from sqlalchemy import or_

from app.models import Book, Category
from app.services.importer import import_new_books

main = Blueprint("main", __name__)


@main.route("/")
def index():
    query_text = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)

    books_query = Book.query

    if query_text:
        search = f"%{query_text}%"
        books_query = books_query.filter(
            or_(Book.title.ilike(search), Book.author.ilike(search), Book.isbn.ilike(search))
        )

    selected_category = None
    if category_id:
        selected_category = Category.query.get(category_id)
        if selected_category:
            category_ids = gather_category_ids(selected_category)
            books_query = books_query.filter(Book.category_id.in_(category_ids))

    books = books_query.order_by(Book.title.asc()).all()
    categories = Category.query.order_by(Category.name.asc()).all()
    pending_imports = count_pending_imports()

    return render_template(
        "index.html",
        books=books,
        categories=categories,
        pending_imports=pending_imports,
        query_text=query_text,
        selected_category=selected_category,
    )


@main.route("/books/<int:book_id>")
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=book)


@main.route("/import", methods=["POST"])
def import_books():
    result = import_new_books()
    processed_count = len(result["processed"])

    if processed_count:
        flash(f"Imported or updated {processed_count} book files.", "success")
    else:
        flash("No new supported book files were found to import.", "info")

    return redirect(url_for("main.index"))


@main.route("/files/<path:filename>")
def download_book_file(filename):
    return send_from_directory(current_app.config["LIBRARY_DIR"], filename, as_attachment=True)


@main.route("/covers/<path:filename>")
def cover_image(filename):
    return send_from_directory(current_app.config["COVERS_DIR"], filename)


def gather_category_ids(category):
    ids = [category.id]
    for child in category.children:
        ids.extend(gather_category_ids(child))
    return ids


def count_pending_imports():
    new_books_dir = Path(current_app.config["NEW_BOOKS_DIR"])
    if not new_books_dir.exists():
        return 0

    count = 0
    for file_path in new_books_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in {".pdf", ".epub", ".mobi"}:
            count += 1
    return count
